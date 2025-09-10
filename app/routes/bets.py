from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, LeagueMember, Matchup, Bet, Game, BettingOption
from app.services.odds_service import OddsService
from datetime import datetime, timedelta
import os

bets_bp = Blueprint('bets', __name__)

# Initialize odds service
odds_service = OddsService()

def check_user_league_membership(user_id):
    """Check if user is a member of any league"""
    membership = LeagueMember.query.filter_by(user_id=user_id).first()
    return membership is not None


@bets_bp.route('/options/week/<int:week>', methods=['GET'])
def get_weekly_betting_options(week):
    """Get all betting options for a specific week organized by game"""
    try:
        # Get all games for the week
        games = Game.query.filter_by(week=week).all()
        
        games_with_options = []
        for game in games:
            # Get all betting options for this game
            betting_options = BettingOption.query.filter_by(game_id=game.id).all()
            
            # Organize options by market type
            organized_options = {}
            for option in betting_options:
                market_type = option.market_type
                if market_type not in organized_options:
                    organized_options[market_type] = {}
                
                outcome_key = f"{option.outcome_name}_{option.outcome_point or ''}"
                if outcome_key not in organized_options[market_type]:
                    organized_options[market_type][outcome_key] = {
                        'outcome_name': option.outcome_name,
                        'outcome_point': option.outcome_point,
                        'bookmakers': []
                    }
                
                organized_options[market_type][outcome_key]['bookmakers'].append({
                    'id': option.id,
                    'bookmaker': option.bookmaker,
                    'american_odds': option.american_odds,
                    'decimal_odds': option.decimal_odds
                })
            
            games_with_options.append({
                'game': game.to_dict(),
                'betting_options': organized_options
            })
        
        return jsonify({
            'week': week,
            'games': games_with_options
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get betting options', 'details': str(e)}), 500

@bets_bp.route('', methods=['POST'])
@jwt_required()
def place_bet():
    """Place a bet on a betting option"""
    try:
        data = request.get_json()
        user_id = int(get_jwt_identity())
        
        # Check if user is a member of any league
        if not check_user_league_membership(user_id):
            return jsonify({'error': 'You must join a league before placing bets'}), 403
        
        # Validate required fields
        required_fields = ['matchup_id', 'betting_option_id', 'amount', 'week']
        if not data or not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        matchup_id = data['matchup_id']
        betting_option_id = data['betting_option_id']
        amount = float(data['amount'])
        week = int(data['week'])
        
        # Validate amount
        if amount <= 0 or amount > 100:
            return jsonify({'error': 'Bet amount must be between $1 and $100'}), 400
        
        # Check if user is part of the matchup
        matchup = Matchup.query.get(matchup_id)
        if not matchup:
            return jsonify({'error': 'Matchup not found'}), 404
        
        if user_id not in [matchup.user1_id, matchup.user2_id]:
            return jsonify({'error': 'You are not part of this matchup'}), 403
        
        # Check if betting option exists and is not locked
        betting_option = BettingOption.query.get(betting_option_id)
        if not betting_option:
            return jsonify({'error': 'Betting option not found'}), 404
        
        if betting_option.is_locked:
            return jsonify({'error': 'This betting option is locked and cannot be bet on'}), 400
        
        # Check if game has already started
        game = betting_option.game
        if datetime.utcnow() >= game.start_time:
            return jsonify({'error': 'Cannot bet on games that have already started'}), 400
        
        # Calculate total bets for this user in this week across all matchups
        existing_bets = Bet.query.filter_by(
            user_id=user_id,
            week=week
        ).all()
        
        total_bet_amount = sum(bet.amount for bet in existing_bets)
        
        if total_bet_amount + amount > 100:
            return jsonify({
                'error': f'Weekly limit exceeded. You have ${100 - total_bet_amount:.2f} remaining'
            }), 400
        
        # Calculate potential payout using current odds
        potential_payout = amount * betting_option.decimal_odds
        
        # Create bet with odds snapshot
        bet = Bet(
            user_id=user_id,
            matchup_id=matchup_id,
            betting_option_id=betting_option_id,
            amount=amount,
            potential_payout=potential_payout,
            week=week,
            odds_snapshot_decimal=betting_option.decimal_odds,
            odds_snapshot_american=betting_option.american_odds,
            bookmaker_snapshot=betting_option.bookmaker,
            status='pending'
        )
        
        db.session.add(bet)
        db.session.commit()
        
        return jsonify({
            'message': 'Bet placed successfully',
            'bet': bet.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': 'Invalid bet amount'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to place bet', 'details': str(e)}), 500

@bets_bp.route('/batch', methods=['POST'])
@jwt_required()
def place_batch_bets():
    """Place multiple bets at once"""
    try:
        data = request.get_json()
        user_id = int(get_jwt_identity())
        
        # Check if user is a member of any league
        if not check_user_league_membership(user_id):
            return jsonify({'error': 'You must join a league before placing bets'}), 403
        
        # Validate required fields
        if not data or 'bets' not in data or 'week' not in data:
            return jsonify({'error': 'Missing bets array or week'}), 400
        
        bets_data = data['bets']
        week = int(data['week'])
        
        if not isinstance(bets_data, list) or len(bets_data) == 0:
            return jsonify({'error': 'Bets must be a non-empty array'}), 400
        
        # Validate each bet
        for i, bet_data in enumerate(bets_data):
            required_fields = ['matchup_id', 'betting_option_id', 'amount']
            if not all(field in bet_data for field in required_fields):
                return jsonify({'error': f'Bet {i+1} missing required fields'}), 400
            
            amount = float(bet_data['amount'])
            if amount <= 0 or amount > 100:
                return jsonify({'error': f'Bet {i+1} amount must be between $1 and $100'}), 400
        
        # Calculate total bet amount
        total_amount = sum(float(bet['amount']) for bet in bets_data)
        if total_amount > 100:
            return jsonify({'error': f'Total bet amount ${total_amount:.2f} exceeds weekly limit of $100'}), 400
        
        # Check existing bets for this user in this week
        existing_bets = Bet.query.filter_by(
            user_id=user_id,
            week=week
        ).all()
        
        existing_total = sum(bet.amount for bet in existing_bets)
        if existing_total + total_amount > 100:
            return jsonify({
                'error': f'Weekly limit exceeded. You have ${100 - existing_total:.2f} remaining'
            }), 400
        
        # Validate all betting options and matchups
        placed_bets = []
        for bet_data in bets_data:
            matchup_id = bet_data['matchup_id']
            betting_option_id = bet_data['betting_option_id']
            amount = float(bet_data['amount'])
            
            # Check if user is part of the matchup
            matchup = Matchup.query.get(matchup_id)
            if not matchup:
                return jsonify({'error': f'Matchup {matchup_id} not found'}), 404
            
            if user_id not in [matchup.user1_id, matchup.user2_id]:
                return jsonify({'error': 'You are not part of one or more matchups'}), 403
            
            # Check if betting option exists and is not locked
            betting_option = BettingOption.query.get(betting_option_id)
            if not betting_option:
                return jsonify({'error': f'Betting option {betting_option_id} not found'}), 404
            
            if betting_option.is_locked:
                return jsonify({'error': f'Betting option {betting_option_id} is locked'}), 400
            
            # Check if game has already started
            game = betting_option.game
            if datetime.utcnow() >= game.start_time:
                return jsonify({'error': 'Cannot bet on games that have already started'}), 400
            
            # Calculate potential payout using current odds
            potential_payout = amount * betting_option.decimal_odds
            
            # Create bet with odds snapshot
            bet = Bet(
                user_id=user_id,
                matchup_id=matchup_id,
                betting_option_id=betting_option_id,
                amount=amount,
                potential_payout=potential_payout,
                week=week,
                odds_snapshot_decimal=betting_option.decimal_odds,
                odds_snapshot_american=betting_option.american_odds,
                bookmaker_snapshot=betting_option.bookmaker,
                status='pending'
            )
            
            db.session.add(bet)
            placed_bets.append(bet)
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully placed {len(placed_bets)} bets',
            'bets': [bet.to_dict() for bet in placed_bets],
            'total_amount': total_amount
        }), 201
        
    except ValueError as e:
        return jsonify({'error': 'Invalid bet data'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to place bets', 'details': str(e)}), 500

@bets_bp.route('/matchup/<int:league_id>/<int:week>', methods=['GET'])
@jwt_required()
def get_user_matchup(league_id, week):
    """Get the user's matchup for a specific league and week"""
    try:
        user_id = int(get_jwt_identity())
        
        # Find the matchup where the user is participating in this league and week
        matchup = Matchup.query.filter(
            Matchup.league_id == league_id,
            Matchup.week == week,
            (Matchup.user1_id == user_id) | (Matchup.user2_id == user_id)
        ).first()
        
        if not matchup:
            return jsonify({'error': 'No matchup found for this league and week'}), 404
        
        return jsonify({'matchup': matchup.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get matchup', 'details': str(e)}), 500

@bets_bp.route('/matchup/<int:matchup_id>/user/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_bets_for_matchup(matchup_id, user_id):
    """Get all bets for a specific user in a specific matchup"""
    try:
        current_user_id = int(get_jwt_identity())
        
        # Verify the matchup exists and user is part of it
        matchup = Matchup.query.get(matchup_id)
        if not matchup:
            return jsonify({'error': 'Matchup not found'}), 404
        
        if user_id not in [matchup.user1_id, matchup.user2_id]:
            return jsonify({'error': 'User is not part of this matchup'}), 403
        
        # Get all bets for this user in this matchup
        bets = Bet.query.filter_by(
            user_id=user_id,
            matchup_id=matchup_id
        ).all()
        
        bets_data = [bet.to_dict() for bet in bets]
        
        return jsonify({
            'bets': bets_data,
            'matchup_id': matchup_id,
            'user_id': user_id,
            'week': matchup.week
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get user bets for matchup', 'details': str(e)}), 500

@bets_bp.route('/user/<int:week>', methods=['GET'])
@jwt_required()
def get_user_bets(week):
    """Get all bets for a user in a specific week"""
    try:
        user_id = int(get_jwt_identity())
        
        # Get all matchups for the user in this week
        matchups = Matchup.query.filter(
            (Matchup.user1_id == user_id) | (Matchup.user2_id == user_id),
            Matchup.week == week
        ).all()
        
        matchup_ids = [matchup.id for matchup in matchups]
        
        # Get all bets for these matchups
        bets = Bet.query.filter(
            Bet.user_id == user_id,
            Bet.matchup_id.in_(matchup_ids)
        ).all()
        
        bets_data = [bet.to_dict() for bet in bets]
        
        # Calculate total bet amount and remaining balance
        total_bet_amount = sum(bet.amount for bet in bets)
        remaining_balance = 100 - total_bet_amount
        
        return jsonify({
            'bets': bets_data,
            'total_bet_amount': total_bet_amount,
            'remaining_balance': remaining_balance,
            'week': week
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get user bets', 'details': str(e)}), 500



@bets_bp.route('/admin/force-update', methods=['POST'])
def force_update_odds():
    """Force update odds (admin only)"""
    try:
        # For testing purposes, allow without auth
        # In production, you might want to check for admin role
        
        data = request.get_json() or {}
        week = data.get('week', 1)
        
        # Manually update odds for the specified week
        odds_service = OddsService()
        odds_data = odds_service.get_nfl_odds(week)
        
        if odds_data:
            updated_games = 0
            new_games = 0
            
            for game_data in odds_data:
                existing_game = Game.query.get(game_data['id'])
                
                if existing_game:
                    # Update existing game
                    existing_game.home_team = game_data['home_team']
                    existing_game.away_team = game_data['away_team']
                    existing_game.start_time = datetime.fromisoformat(game_data['start_time'])
                    updated_games += 1
                else:
                    # Create new game
                    game = Game(
                        id=game_data['id'],
                        home_team=game_data['home_team'],
                        away_team=game_data['away_team'],
                        start_time=datetime.fromisoformat(game_data['start_time']),
                        week=week
                    )
                    db.session.add(game)
                    new_games += 1
            
            db.session.commit()
            message = f"Updated {updated_games} games, Added {new_games} new games for week {week}"
        else:
            message = f"No odds data available for week {week}"
        
        return jsonify({'message': message}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to force update', 'details': str(e)}), 500

@bets_bp.route('/admin/process-outcomes', methods=['POST'])
@jwt_required()
def force_process_outcomes():
    """Force process bet outcomes (admin only)"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is admin (for now, any authenticated user can do this)
        
        # Manually process bet outcomes
        odds_service = OddsService()
        current_time = datetime.utcnow()
        
        # Find completed games that haven't been processed
        completed_games = Game.query.filter(
            Game.start_time < current_time,
            Game.result.is_(None)
        ).all()
        
        processed_bets = 0
        
        for game in completed_games:
            # Get game result from API
            game_result = odds_service.get_game_result(game.id)
            
            if game_result:
                game.result = game_result
                
                # Process all bets for this game
                bets = Bet.query.filter_by(game_id=game.id).filter(
                    Bet.status.in_(['pending', 'locked'])
                ).all()
                
                for bet in bets:
                    # Determine if bet won or lost
                    if game_result == 'home_win' and bet.team == game.home_team:
                        bet.status = 'won'
                    elif game_result == 'away_win' and bet.team == game.away_team:
                        bet.status = 'won'
                    else:
                        bet.status = 'lost'
                    
                    processed_bets += 1
        
        if processed_bets > 0:
            db.session.commit()
            message = f"Processed {processed_bets} bet outcomes"
        else:
            message = "No bet outcomes to process"
        
        return jsonify({'message': message}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to process outcomes', 'details': str(e)}), 500
