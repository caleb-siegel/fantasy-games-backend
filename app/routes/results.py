from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, LeagueMember, Matchup, Bet, Game
from app.services.odds_service import OddsService
from datetime import datetime

results_bp = Blueprint('results', __name__)

# Initialize odds service
odds_service = OddsService()

@results_bp.route('/update', methods=['POST'])
@jwt_required()
def update_results():
    """Update game results and calculate bet outcomes"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is admin/commissioner (for now, any authenticated user can update)
        # In production, you might want to restrict this to commissioners only
        
        data = request.get_json() or {}
        week = data.get('week')
        
        if week:
            # Update results for specific week
            games = Game.query.filter_by(week=week).all()
        else:
            # Update all games that haven't been processed
            games = Game.query.filter(Game.result.is_(None)).all()
        
        updated_games = 0
        processed_bets = 0
        
        for game in games:
            # Skip if game hasn't started yet
            if datetime.utcnow() < game.start_time:
                continue
            
            # Get game result from API
            game_result = odds_service.get_game_result(game.id)
            
            if game_result:
                game.result = game_result
                updated_games += 1
                
                # Process all bets for this game
                bets = Bet.query.filter_by(game_id=game.id, status='pending').all()
                
                for bet in bets:
                    # Determine if bet won or lost
                    if game_result == 'home_win' and bet.team == game.home_team:
                        bet.status = 'won'
                    elif game_result == 'away_win' and bet.team == game.away_team:
                        bet.status = 'won'
                    else:
                        bet.status = 'lost'
                    
                    processed_bets += 1
        
        # Calculate matchup results for the week
        if week:
            calculate_matchup_results(week)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Results updated successfully',
            'updated_games': updated_games,
            'processed_bets': processed_bets
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update results', 'details': str(e)}), 500

@results_bp.route('/week/<int:week>', methods=['GET'])
@jwt_required()
def get_weekly_results(week):
    """Get weekly results for all matchups"""
    try:
        user_id = int(get_jwt_identity())
        
        # Get all matchups for the week
        matchups = Matchup.query.filter_by(week=week).all()
        
        results = []
        
        for matchup in matchups:
            # Check if user is part of this matchup or league
            league_member = LeagueMember.query.filter_by(
                league_id=matchup.league_id,
                user_id=user_id
            ).first()
            
            if not league_member:
                continue  # Skip if user not in league
            
            # Get all bets for both users in this matchup
            user1_bets = Bet.query.filter_by(
                user_id=matchup.user1_id,
                matchup_id=matchup.id
            ).all()
            
            user2_bets = Bet.query.filter_by(
                user_id=matchup.user2_id,
                matchup_id=matchup.id
            ).all()
            
            # Calculate final balances
            user1_balance = calculate_final_balance(user1_bets)
            user2_balance = calculate_final_balance(user2_bets)
            
            # Determine winner
            winner_id = None
            if user1_balance > user2_balance:
                winner_id = matchup.user1_id
            elif user2_balance > user1_balance:
                winner_id = matchup.user2_id
            
            # Update matchup winner if not already set
            if matchup.winner_id is None and winner_id:
                matchup.winner_id = winner_id
                
                # Update league standings
                update_league_standings(matchup.league_id, matchup.user1_id, matchup.user2_id, winner_id)
            
            matchup_data = matchup.to_dict()
            matchup_data['user1_balance'] = user1_balance
            matchup_data['user2_balance'] = user2_balance
            matchup_data['user1_bets'] = [bet.to_dict() for bet in user1_bets]
            matchup_data['user2_bets'] = [bet.to_dict() for bet in user2_bets]
            
            results.append(matchup_data)
        
        db.session.commit()
        
        return jsonify({
            'week': week,
            'results': results
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get weekly results', 'details': str(e)}), 500

def calculate_final_balance(bets):
    """Calculate final balance after all bets are settled"""
    balance = 100.0  # Starting balance
    
    for bet in bets:
        if bet.status == 'won':
            balance += bet.potential_payout - bet.amount  # Net winnings
        elif bet.status == 'lost':
            balance -= bet.amount  # Lost the bet amount
        # Pending bets don't affect balance yet
    
    return balance

def calculate_matchup_results(week):
    """Calculate results for all matchups in a given week"""
    matchups = Matchup.query.filter_by(week=week).all()
    
    for matchup in matchups:
        # Get all bets for both users
        user1_bets = Bet.query.filter_by(
            user_id=matchup.user1_id,
            matchup_id=matchup.id
        ).all()
        
        user2_bets = Bet.query.filter_by(
            user_id=matchup.user2_id,
            matchup_id=matchup.id
        ).all()
        
        # Calculate final balances
        user1_balance = calculate_final_balance(user1_bets)
        user2_balance = calculate_final_balance(user2_bets)
        
        # Determine winner
        winner_id = None
        if user1_balance > user2_balance:
            winner_id = matchup.user1_id
        elif user2_balance > user1_balance:
            winner_id = matchup.user2_id
        
        # Update matchup winner if not already set
        if matchup.winner_id is None and winner_id:
            matchup.winner_id = winner_id
            
            # Update league standings
            update_league_standings(matchup.league_id, matchup.user1_id, matchup.user2_id, winner_id)

def update_league_standings(league_id, user1_id, user2_id, winner_id):
    """Update league standings after a matchup"""
    # Get league members
    member1 = LeagueMember.query.filter_by(league_id=league_id, user_id=user1_id).first()
    member2 = LeagueMember.query.filter_by(league_id=league_id, user_id=user2_id).first()
    
    if member1 and member2:
        # Update wins/losses
        if winner_id == user1_id:
            member1.wins += 1
            member2.losses += 1
        elif winner_id == user2_id:
            member2.wins += 1
            member1.losses += 1
        
        # Update points (using final balances)
        matchup = Matchup.query.filter_by(league_id=league_id, user1_id=user1_id, user2_id=user2_id).first()
        if matchup:
            user1_bets = Bet.query.filter_by(user_id=user1_id, matchup_id=matchup.id).all()
            user2_bets = Bet.query.filter_by(user_id=user2_id, matchup_id=matchup.id).all()
        else:
            user1_bets = []
            user2_bets = []
        
        user1_balance = calculate_final_balance(user1_bets)
        user2_balance = calculate_final_balance(user2_bets)
        
        member1.points_for += user1_balance
        member1.points_against += user2_balance
        member2.points_for += user2_balance
        member2.points_against += user1_balance
