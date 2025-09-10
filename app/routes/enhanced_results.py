from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, League, LeagueMember, Matchup, Bet, BettingOption, Game
from datetime import datetime
import logging

results_bp = Blueprint('results', __name__)

def calculate_final_balance(bets):
    """
    Calculate final balance from a list of bets.
    
    Args:
        bets: List of Bet objects
    
    Returns:
        Final balance (float)
    """
    total_balance = 100.0  # Starting balance
    
    for bet in bets:
        if bet.status == 'won':
            total_balance += bet.potential_payout - bet.amount
        elif bet.status == 'lost':
            total_balance -= bet.amount
        elif bet.status == 'cancelled':
            # Money is returned for cancelled bets
            pass
        # 'pending' bets don't affect balance until resolved
    
    return total_balance

def evaluate_bet(bet):
    """
    Evaluate a single bet based on game results.
    
    Args:
        bet: Bet object to evaluate
    
    Returns:
        Updated bet status
    """
    betting_option = bet.betting_option
    game = betting_option.game
    
    # Check if game is finished
    if not game.result:
        return 'pending'
    
    # Determine bet outcome based on game result and betting option
    if betting_option.market_type == 'h2h':
        # Moneyline bet
        if betting_option.outcome_name == game.home_team:
            # Bet on home team
            if game.result == 'home_win':
                return 'won'
            else:
                return 'lost'
        elif betting_option.outcome_name == game.away_team:
            # Bet on away team
            if game.result == 'away_win':
                return 'won'
            else:
                return 'lost'
    
    elif betting_option.market_type == 'spreads':
        # Spread bet (simplified - would need actual spread logic)
        # This is a placeholder for spread evaluation
        return 'pending'
    
    elif betting_option.market_type == 'totals':
        # Over/Under bet (simplified - would need actual total logic)
        # This is a placeholder for totals evaluation
        return 'pending'
    
    return 'pending'

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

@results_bp.route('/update', methods=['POST'])
@jwt_required()
def update_results():
    """Update game results and evaluate bets"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        
        if not data or 'games' not in data:
            return jsonify({'error': 'Games data is required'}), 400
        
        updated_games = []
        evaluated_bets = []
        
        for game_data in data['games']:
            game_id = game_data.get('id')
            result = game_data.get('result')
            
            if not game_id or not result:
                continue
            
            # Update game result
            game = Game.query.get(game_id)
            if game:
                game.result = result
                updated_games.append(game_id)
                
                # Evaluate all bets for this game
                betting_options = BettingOption.query.filter_by(game_id=game_id).all()
                
                for option in betting_options:
                    bets = Bet.query.filter_by(betting_option_id=option.id).all()
                    
                    for bet in bets:
                        if bet.status == 'pending':
                            new_status = evaluate_bet(bet)
                            if new_status != 'pending':
                                bet.status = new_status
                                bet.resolved_at = datetime.utcnow()
                                evaluated_bets.append(bet.id)
        
        # Update matchups after bet evaluation
        calculate_matchup_results()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Results updated successfully',
            'games_updated': len(updated_games),
            'bets_evaluated': len(evaluated_bets)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update results', 'details': str(e)}), 500

def calculate_matchup_results():
    """Calculate matchup results based on evaluated bets"""
    # Get all matchups that don't have winners yet
    matchups = Matchup.query.filter_by(winner_id=None).all()
    
    for matchup in matchups:
        # Get all bets for both users in this matchup
        user1_bets = Bet.query.filter_by(
            user_id=matchup.user1_id,
            matchup_id=matchup.id
        ).all()
        
        user2_bets = Bet.query.filter_by(
            user_id=matchup.user2_id,
            matchup_id=matchup.id
        ).all()
        
        # Check if all bets are resolved
        user1_pending = any(bet.status == 'pending' for bet in user1_bets)
        user2_pending = any(bet.status == 'pending' for bet in user2_bets)
        
        if not user1_pending and not user2_pending:
            # All bets resolved, calculate final balances
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
        
        return jsonify({'results': results}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to get weekly results', 'details': str(e)}), 500

@results_bp.route('/evaluate-bets', methods=['POST'])
@jwt_required()
def evaluate_all_pending_bets():
    """Evaluate all pending bets based on current game results"""
    try:
        user_id = int(get_jwt_identity())
        
        # Get all pending bets
        pending_bets = Bet.query.filter_by(status='pending').all()
        
        evaluated_count = 0
        
        for bet in pending_bets:
            new_status = evaluate_bet(bet)
            if new_status != 'pending':
                bet.status = new_status
                bet.resolved_at = datetime.utcnow()
                evaluated_count += 1
        
        # Recalculate matchup results
        calculate_matchup_results()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Bets evaluated successfully',
            'bets_evaluated': evaluated_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to evaluate bets', 'details': str(e)}), 500

@results_bp.route('/matchup/<int:matchup_id>/details', methods=['GET'])
@jwt_required()
def get_matchup_details(matchup_id):
    """Get detailed matchup information including all bets"""
    try:
        user_id = int(get_jwt_identity())
        
        matchup = Matchup.query.get(matchup_id)
        if not matchup:
            return jsonify({'error': 'Matchup not found'}), 404
        
        # Check if user is part of this matchup or league
        league_member = LeagueMember.query.filter_by(
            league_id=matchup.league_id,
            user_id=user_id
        ).first()
        
        if not league_member:
            return jsonify({'error': 'You are not a member of this league'}), 403
        
        # Get all bets for both users
        user1_bets = Bet.query.filter_by(
            user_id=matchup.user1_id,
            matchup_id=matchup.id
        ).all()
        
        user2_bets = Bet.query.filter_by(
            user_id=matchup.user2_id,
            matchup_id=matchup.id
        ).all()
        
        # Calculate balances
        user1_balance = calculate_final_balance(user1_bets)
        user2_balance = calculate_final_balance(user2_bets)
        
        # Calculate totals
        user1_total_bet = sum(bet.amount for bet in user1_bets)
        user2_total_bet = sum(bet.amount for bet in user2_bets)
        user1_potential_payout = sum(bet.potential_payout for bet in user1_bets)
        user2_potential_payout = sum(bet.potential_payout for bet in user2_bets)
        
        matchup_data = matchup.to_dict()
        matchup_data.update({
            'user1_balance': user1_balance,
            'user2_balance': user2_balance,
            'user1_total_bet': user1_total_bet,
            'user2_total_bet': user2_total_bet,
            'user1_potential_payout': user1_potential_payout,
            'user2_potential_payout': user2_potential_payout,
            'user1_bets': [bet.to_dict() for bet in user1_bets],
            'user2_bets': [bet.to_dict() for bet in user2_bets],
            'is_locked': any(bet.locked_at for bet in user1_bets + user2_bets)
        })
        
        return jsonify({'matchup': matchup_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get matchup details', 'details': str(e)}), 500
