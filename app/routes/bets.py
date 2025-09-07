from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, LeagueMember, Matchup, Bet, Game
from app.services.odds_service import OddsService
from datetime import datetime, timedelta
import os

bets_bp = Blueprint('bets', __name__)

# Initialize odds service
odds_service = OddsService()

@bets_bp.route('/odds/week/<int:week>', methods=['GET'])
@jwt_required()
def get_weekly_odds(week):
    """Get NFL moneyline odds for a specific week"""
    try:
        # Get odds from external API
        odds_data = odds_service.get_nfl_odds(week)
        
        if not odds_data:
            return jsonify({'error': 'No odds data available for this week'}), 404
        
        # Store games in database if not already present
        for game_data in odds_data:
            existing_game = Game.query.get(game_data['id'])
            if not existing_game:
                game = Game(
                    id=game_data['id'],
                    home_team=game_data['home_team'],
                    away_team=game_data['away_team'],
                    start_time=datetime.fromisoformat(game_data['start_time']),
                    week=week
                )
                db.session.add(game)
        
        db.session.commit()
        
        return jsonify({'odds': odds_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get odds', 'details': str(e)}), 500

@bets_bp.route('', methods=['POST'])
@jwt_required()
def place_bet():
    """Place a bet on a game"""
    try:
        data = request.get_json()
        user_id = int(get_jwt_identity())
        
        # Validate required fields
        required_fields = ['matchup_id', 'game_id', 'team', 'amount']
        if not data or not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        matchup_id = data['matchup_id']
        game_id = data['game_id']
        team = data['team']
        amount = float(data['amount'])
        
        # Validate amount
        if amount <= 0 or amount > 100:
            return jsonify({'error': 'Bet amount must be between $1 and $100'}), 400
        
        # Check if user is part of the matchup
        matchup = Matchup.query.get(matchup_id)
        if not matchup:
            return jsonify({'error': 'Matchup not found'}), 404
        
        if user_id not in [matchup.user1_id, matchup.user2_id]:
            return jsonify({'error': 'You are not part of this matchup'}), 403
        
        # Check if game exists
        game = Game.query.get(game_id)
        if not game:
            return jsonify({'error': 'Game not found'}), 404
        
        # Check if game has already started
        if datetime.utcnow() >= game.start_time:
            return jsonify({'error': 'Cannot bet on games that have already started'}), 400
        
        # Calculate weekly balance used
        weekly_bets = Bet.query.filter_by(
            user_id=user_id,
            matchup_id=matchup_id
        ).all()
        
        total_bet_amount = sum(bet.amount for bet in weekly_bets)
        
        if total_bet_amount + amount > 100:
            return jsonify({
                'error': f'Weekly limit exceeded. You have ${100 - total_bet_amount:.2f} remaining'
            }), 400
        
        # Get current odds for the team
        odds_data = odds_service.get_game_odds(game_id)
        if not odds_data:
            return jsonify({'error': 'Odds not available for this game'}), 400
        
        # Find the odds for the selected team
        team_odds = None
        if team == game.home_team:
            team_odds = odds_data.get('home_odds')
        elif team == game.away_team:
            team_odds = odds_data.get('away_odds')
        
        if not team_odds:
            return jsonify({'error': 'Invalid team selection'}), 400
        
        # Calculate potential payout
        potential_payout = amount * team_odds
        
        # Create bet
        bet = Bet(
            user_id=user_id,
            matchup_id=matchup_id,
            game_id=game_id,
            team=team,
            amount=amount,
            odds=team_odds,
            potential_payout=potential_payout,
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

@bets_bp.route('/matchup/<int:matchup_id>', methods=['GET'])
@jwt_required()
def get_matchup_bets(matchup_id):
    """Get all bets for a specific matchup"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is part of the matchup
        matchup = Matchup.query.get(matchup_id)
        if not matchup:
            return jsonify({'error': 'Matchup not found'}), 404
        
        if user_id not in [matchup.user1_id, matchup.user2_id]:
            return jsonify({'error': 'You are not part of this matchup'}), 403
        
        # Get all bets for this matchup
        bets = Bet.query.filter_by(matchup_id=matchup_id).all()
        
        # Separate bets by user
        user1_bets = [bet.to_dict() for bet in bets if bet.user_id == matchup.user1_id]
        user2_bets = [bet.to_dict() for bet in bets if bet.user_id == matchup.user2_id]
        
        # Calculate totals
        user1_total = sum(bet['amount'] for bet in user1_bets)
        user2_total = sum(bet['amount'] for bet in user2_bets)
        
        return jsonify({
            'matchup': matchup.to_dict(),
            'user1_bets': {
                'bets': user1_bets,
                'total_amount': user1_total,
                'remaining_balance': 100 - user1_total
            },
            'user2_bets': {
                'bets': user2_bets,
                'total_amount': user2_total,
                'remaining_balance': 100 - user2_total
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get matchup bets', 'details': str(e)}), 500
