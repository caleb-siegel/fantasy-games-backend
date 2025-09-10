from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, League, LeagueMember, Matchup, Bet
from datetime import datetime
import itertools
import random
import secrets
import string

leagues_bp = Blueprint('leagues', __name__)

def generate_round_robin_schedule(teams, weeks_required=14):
    """
    Generate a round-robin schedule for the given teams.
    For 6 teams, this will create 3 matchups per week.
    
    Args:
        teams: List of team/user IDs
        weeks_required: Number of weeks to generate (default 14 for regular season)
    
    Returns:
        List of rounds, where each round contains a list of matchups
    """
    if len(teams) < 2:
        return []
    
    # If odd number of teams, add a bye
    if len(teams) % 2 == 1:
        teams = teams + ['BYE']
    
    n = len(teams)
    rounds = []
    fixed = teams[0]
    rotating = teams[1:]
    
    # Generate rounds
    for round_num in range(n - 1):
        if len(rounds) >= weeks_required:
            break
            
        round_matches = []
        
        # Create matchups for this round
        for i in range(n // 2):
            home_team = teams[i]
            away_team = teams[n - 1 - i]
            
            # Skip if either team is BYE
            if home_team != 'BYE' and away_team != 'BYE':
                round_matches.append({
                    'home': home_team,
                    'away': away_team
                })
        
        rounds.append(round_matches)
        
        # Rotate teams (except the first one)
        if len(rotating) > 1:
            rotating = [rotating[-1]] + rotating[:-1]
            teams = [fixed] + rotating
    
    return rounds[:weeks_required]

def generate_playoff_bracket(standings, playoff_teams=4):
    """
    Generate playoff bracket based on standings.
    
    Args:
        standings: List of LeagueMember objects sorted by rank
        playoff_teams: Number of teams to make playoffs (default 4)
    
    Returns:
        List of playoff rounds with matchups
    """
    if len(standings) < playoff_teams:
        playoff_teams = len(standings)
    
    playoff_standings = standings[:playoff_teams]
    rounds = []
    
    if playoff_teams == 4:
        # Week 15: Semifinals
        rounds.append([
            {'home': playoff_standings[0].user_id, 'away': playoff_standings[3].user_id},
            {'home': playoff_standings[1].user_id, 'away': playoff_standings[2].user_id}
        ])
        
        # Week 16: Finals (winners of semifinals)
        rounds.append([
            {'home': 'TBD', 'away': 'TBD'}  # Will be filled after semifinals
        ])
        
        # Week 17: Championship (if needed)
        rounds.append([
            {'home': 'TBD', 'away': 'TBD'}  # Will be filled after finals
        ])
    
    elif playoff_teams == 6:
        # Week 15: Wildcard round
        rounds.append([
            {'home': playoff_standings[3].user_id, 'away': playoff_standings[6].user_id},
            {'home': playoff_standings[4].user_id, 'away': playoff_standings[5].user_id}
        ])
        
        # Week 16: Semifinals
        rounds.append([
            {'home': playoff_standings[0].user_id, 'away': 'TBD'},  # vs wildcard winner
            {'home': playoff_standings[1].user_id, 'away': playoff_standings[2].user_id}
        ])
        
        # Week 17: Finals
        rounds.append([
            {'home': 'TBD', 'away': 'TBD'}  # Will be filled after semifinals
        ])
    
    return rounds

def create_matchups_from_schedule(league_id, schedule, start_week=1):
    """
    Create Matchup objects from a generated schedule.
    
    Args:
        league_id: ID of the league
        schedule: List of rounds with matchups
        start_week: Starting week number
    
    Returns:
        List of created Matchup objects
    """
    matchups = []
    
    for round_num, round_matches in enumerate(schedule):
        week = start_week + round_num
        
        for match in round_matches:
            # Skip TBD matchups (for playoffs)
            if match['home'] == 'TBD' or match['away'] == 'TBD':
                continue
                
            matchup = Matchup(
                league_id=league_id,
                week=week,
                user1_id=match['home'],
                user2_id=match['away']
            )
            matchups.append(matchup)
    
    return matchups

@leagues_bp.route('/user', methods=['GET'])
@jwt_required()
def get_user_leagues():
    """Get all leagues for the current user"""
    try:
        user_id = int(get_jwt_identity())
        
        # Get all leagues where user is a member
        memberships = LeagueMember.query.filter_by(user_id=user_id).all()
        leagues = []
        
        for membership in memberships:
            league = membership.league
            league_data = league.to_dict()
            
            # Add user-specific data
            league_data['is_commissioner'] = league.commissioner_id == user_id
            league_data['is_active'] = True  # For now, all leagues are active
            
            # Calculate user's record in this league (mock data for now)
            league_data['record'] = "0-0"
            league_data['total_winnings'] = 0.0
            league_data['avg_balance'] = 100.0
            league_data['longest_win_streak'] = 0
            
            leagues.append(league_data)
        
        return jsonify({
            'leagues': leagues
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch user leagues', 'details': str(e)}), 500

@leagues_bp.route('', methods=['POST'])
@jwt_required()
def create_league():
    """Create a new league"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({'error': 'League name is required'}), 400
        
        # Create league
        league = League(
            name=data['name'],
            commissioner_id=user_id
        )
        
        db.session.add(league)
        db.session.flush()  # Get the league ID
        
        # Add creator as first member
        member = LeagueMember(
            league_id=league.id,
            user_id=user_id
        )
        
        db.session.add(member)
        db.session.commit()
        
        return jsonify({
            'message': 'League created successfully',
            'league': league.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create league', 'details': str(e)}), 500

@leagues_bp.route('/join', methods=['POST'])
@jwt_required()
def join_league():
    """Join a league using invite code"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        
        if not data or 'invite_code' not in data:
            return jsonify({'error': 'Invite code is required'}), 400
        
        # Find league by invite code
        league = League.query.filter_by(invite_code=data['invite_code']).first()
        
        if not league:
            return jsonify({'error': 'Invalid invite code'}), 404
        
        # Check if user is already a member
        existing_member = LeagueMember.query.filter_by(
            league_id=league.id,
            user_id=user_id
        ).first()
        
        if existing_member:
            return jsonify({'error': 'You are already a member of this league'}), 400
        
        # Add user as member
        member = LeagueMember(
            league_id=league.id,
            user_id=user_id
        )
        
        db.session.add(member)
        db.session.commit()
        
        return jsonify({
            'message': 'Successfully joined league',
            'league': league.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to join league', 'details': str(e)}), 500

@leagues_bp.route('/<int:league_id>', methods=['GET'])
@jwt_required()
def get_league_details(league_id):
    """Get league details including members and standings"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is a member of the league
        member = LeagueMember.query.filter_by(
            league_id=league_id, 
            user_id=user_id
        ).first()
        
        if not member:
            return jsonify({'error': 'You are not a member of this league'}), 403
        
        league = League.query.get(league_id)
        if not league:
            return jsonify({'error': 'League not found'}), 404
        
        # Get all members with their stats
        members = LeagueMember.query.filter_by(league_id=league_id).all()
        members_data = [member.to_dict() for member in members]
        
        # Get recent matchups
        recent_matchups = Matchup.query.filter_by(league_id=league_id)\
            .order_by(Matchup.week.desc()).limit(5).all()
        matchups_data = [matchup.to_dict() for matchup in recent_matchups]
        
        league_data = league.to_dict()
        league_data['members'] = members_data
        league_data['recent_matchups'] = matchups_data
        
        return jsonify({'league': league_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get league details', 'details': str(e)}), 500

@leagues_bp.route('/<int:league_id>/standings', methods=['GET'])
@jwt_required()
def get_league_standings(league_id):
    """Get league standings"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is a member of the league
        member = LeagueMember.query.filter_by(
            league_id=league_id, 
            user_id=user_id
        ).first()
        
        if not member:
            return jsonify({'error': 'You are not a member of this league'}), 403
        
        # Get all members sorted by wins (descending), then by points_for (descending)
        members = LeagueMember.query.filter_by(league_id=league_id)\
            .order_by(LeagueMember.wins.desc(), LeagueMember.points_for.desc()).all()
        
        standings = []
        for i, member in enumerate(members, 1):
            member_data = member.to_dict()
            member_data['rank'] = i
            member_data['win_percentage'] = (
                member.wins / (member.wins + member.losses) 
                if (member.wins + member.losses) > 0 else 0
            )
            standings.append(member_data)
        
        return jsonify({'standings': standings}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get standings', 'details': str(e)}), 500

@leagues_bp.route('/<int:league_id>/schedule', methods=['POST'])
@jwt_required()
def generate_schedule(league_id):
    """Generate schedule for a league (commissioner only)"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is commissioner
        league = League.query.get(league_id)
        if not league:
            return jsonify({'error': 'League not found'}), 404
        
        if league.commissioner_id != user_id:
            return jsonify({'error': 'Only the commissioner can generate schedules'}), 403
        
        # Get all league members
        members = LeagueMember.query.filter_by(league_id=league_id).all()
        if len(members) < 2:
            return jsonify({'error': 'Need at least 2 members to generate schedule'}), 400
        
        # Extract user IDs
        team_ids = [member.user_id for member in members]
        
        # Generate regular season schedule (weeks 1-14)
        regular_season_schedule = generate_round_robin_schedule(team_ids, 14)
        
        # Create matchups for regular season
        regular_season_matchups = create_matchups_from_schedule(
            league_id, regular_season_schedule, start_week=1
        )
        
        # Add all matchups to database
        for matchup in regular_season_matchups:
            db.session.add(matchup)
        
        # Mark league as setup complete
        league.is_setup_complete = True
        league.setup_completed_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Schedule generated successfully',
            'matchups_created': len(regular_season_matchups)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to generate schedule', 'details': str(e)}), 500

@leagues_bp.route('/<int:league_id>/playoffs', methods=['POST'])
@jwt_required()
def generate_playoffs(league_id):
    """Generate playoff bracket (commissioner only)"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is commissioner
        league = League.query.get(league_id)
        if not league:
            return jsonify({'error': 'League not found'}), 404
        
        if league.commissioner_id != user_id:
            return jsonify({'error': 'Only the commissioner can generate playoffs'}), 403
        
        # Get standings
        standings = LeagueMember.query.filter_by(league_id=league_id)\
            .order_by(LeagueMember.wins.desc(), LeagueMember.points_for.desc()).all()
        
        if len(standings) < 2:
            return jsonify({'error': 'Need at least 2 teams for playoffs'}), 400
        
        # Generate playoff bracket
        playoff_schedule = generate_playoff_bracket(standings, playoff_teams=4)
        
        # Create playoff matchups (weeks 15-17)
        playoff_matchups = create_matchups_from_schedule(
            league_id, playoff_schedule, start_week=15
        )
        
        # Add playoff matchups to database
        for matchup in playoff_matchups:
            db.session.add(matchup)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Playoff bracket generated successfully',
            'playoff_matchups_created': len(playoff_matchups)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to generate playoffs', 'details': str(e)}), 500

@leagues_bp.route('/<int:league_id>/matchups/<int:week>', methods=['GET'])
@jwt_required()
def get_week_matchups(league_id, week):
    """Get all matchups for a specific week"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is a member of the league
        member = LeagueMember.query.filter_by(
            league_id=league_id, 
            user_id=user_id
        ).first()
        
        if not member:
            return jsonify({'error': 'You are not a member of this league'}), 403
        
        # Get matchups for the week with comprehensive bet data
        matchups = Matchup.query.filter_by(
            league_id=league_id,
            week=week
        ).all()
        
        # Get comprehensive matchup data with bets
        matchups_data = []
        for matchup in matchups:
            # Get bets for both users in this matchup
            from app.models import Bet
            user1_bets = Bet.query.filter_by(
                matchup_id=matchup.id,
                user_id=matchup.user1_id
            ).all()
            
            user2_bets = Bet.query.filter_by(
                matchup_id=matchup.id,
                user_id=matchup.user2_id
            ).all()
            
            # Calculate totals
            user1_total_bet = sum(bet.amount for bet in user1_bets)
            user2_total_bet = sum(bet.amount for bet in user2_bets)
            user1_potential_payout = sum(bet.potential_payout for bet in user1_bets)
            user2_potential_payout = sum(bet.potential_payout for bet in user2_bets)
            
            # Format bet data
            user1_bets_data = []
            for bet in user1_bets:
                bet_data = {
                    'id': bet.id,
                    'amount': bet.amount,
                    'potential_payout': bet.potential_payout,
                    'status': bet.status,
                    'betting_option': {
                        'id': bet.betting_option.id,
                        'outcome_name': bet.betting_option.outcome_name,
                        'outcome_point': bet.betting_option.outcome_point,
                        'bookmaker': bet.betting_option.bookmaker,
                        'american_odds': bet.betting_option.american_odds,
                        'decimal_odds': bet.betting_option.decimal_odds,
                        'market_type': bet.betting_option.market_type
                    },
                    'game': {
                        'id': bet.betting_option.game.id,
                        'home_team': bet.betting_option.game.home_team,
                        'away_team': bet.betting_option.game.away_team,
                        'start_time': bet.betting_option.game.start_time.isoformat()
                    }
                }
                user1_bets_data.append(bet_data)
            
            user2_bets_data = []
            for bet in user2_bets:
                bet_data = {
                    'id': bet.id,
                    'amount': bet.amount,
                    'potential_payout': bet.potential_payout,
                    'status': bet.status,
                    'betting_option': {
                        'id': bet.betting_option.id,
                        'outcome_name': bet.betting_option.outcome_name,
                        'outcome_point': bet.betting_option.outcome_point,
                        'bookmaker': bet.betting_option.bookmaker,
                        'american_odds': bet.betting_option.american_odds,
                        'decimal_odds': bet.betting_option.decimal_odds,
                        'market_type': bet.betting_option.market_type
                    },
                    'game': {
                        'id': bet.betting_option.game.id,
                        'home_team': bet.betting_option.game.home_team,
                        'away_team': bet.betting_option.game.away_team,
                        'start_time': bet.betting_option.game.start_time.isoformat()
                    }
                }
                user2_bets_data.append(bet_data)
            
            matchup_data = {
                'id': matchup.id,
                'league_id': matchup.league_id,
                'week': matchup.week,
                'user1_id': matchup.user1_id,
                'user2_id': matchup.user2_id,
                'user1_username': matchup.user1.username,
                'user2_username': matchup.user2.username,
                'winner_id': matchup.winner_id,
                'created_at': matchup.created_at.isoformat(),
                'user1_bets': user1_bets_data,
                'user2_bets': user2_bets_data,
                'user1_total_bet': user1_total_bet,
                'user2_total_bet': user2_total_bet,
                'user1_potential_payout': user1_potential_payout,
                'user2_potential_payout': user2_potential_payout,
                'is_locked': False  # TODO: Implement lock logic
            }
            matchups_data.append(matchup_data)
        
        return jsonify({'matchups': matchups_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get week matchups', 'details': str(e)}), 500

@leagues_bp.route('/<int:league_id>/standings/comprehensive', methods=['GET'])
@jwt_required()
def get_comprehensive_standings(league_id):
    """Get comprehensive standings with all calculated metrics"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is a member of the league
        member = LeagueMember.query.filter_by(
            league_id=league_id, 
            user_id=user_id
        ).first()
        
        if not member:
            return jsonify({'error': 'You are not a member of this league'}), 403
        
        # Get all members with their stats
        members = LeagueMember.query.filter_by(league_id=league_id)\
            .order_by(LeagueMember.wins.desc(), LeagueMember.points_for.desc()).all()
        
        standings = []
        for i, member in enumerate(members, 1):
            # Calculate comprehensive stats - handle None values
            wins = member.wins or 0
            losses = member.losses or 0
            total_games = wins + losses
            win_percentage = (wins / total_games * 100) if total_games > 0 else 0
            avg_money_per_week = (member.points_for or 0) / max(1, total_games)
            
            # Get bet statistics
            from app.models import Bet
            user_bets = Bet.query.join(Matchup).filter(
                Matchup.league_id == league_id,
                Bet.user_id == member.user_id
            ).all()
            
            bets_won = len([bet for bet in user_bets if bet.status == 'won'])
            bets_lost = len([bet for bet in user_bets if bet.status == 'lost'])
            bets_pending = len([bet for bet in user_bets if bet.status == 'pending'])
            total_bets_placed = len(user_bets)
            
            # Calculate current streak (simplified - would need more complex logic)
            current_streak = 0
            win_streak_type = 'none'
            
            member_data = {
                'id': member.id,
                'league_id': member.league_id,
                'user_id': member.user_id,
                'username': member.user.username,
                'wins': wins,
                'losses': losses,
                'points_for': member.points_for or 0,
                'points_against': member.points_against or 0,
                'joined_at': member.joined_at.isoformat(),
                'rank': i,
                'win_percentage': win_percentage,
                'avg_money_per_week': avg_money_per_week,
                'money_earned_total': member.points_for or 0,
                'money_against': member.points_against or 0,
                'current_streak': current_streak,
                'longest_win_streak': 0,  # Would need historical data
                'longest_loss_streak': 0,  # Would need historical data
                'bets_won': bets_won,
                'bets_lost': bets_lost,
                'bets_pending': bets_pending,
                'total_bets_placed': total_bets_placed,
                'win_streak_type': win_streak_type
            }
            standings.append(member_data)
        
        return jsonify({'standings': standings}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get comprehensive standings', 'details': str(e)}), 500

@leagues_bp.route('/<int:league_id>/players/<int:user_id>', methods=['GET'])
@jwt_required()
def get_player_profile(league_id, user_id):
    """Get comprehensive player profile"""
    try:
        current_user_id = int(get_jwt_identity())
        
        # Check if current user is a member of the league
        member = LeagueMember.query.filter_by(
            league_id=league_id, 
            user_id=current_user_id
        ).first()
        
        if not member:
            return jsonify({'error': 'You are not a member of this league'}), 403
        
        # Get the target player's membership
        player_member = LeagueMember.query.filter_by(
            league_id=league_id,
            user_id=user_id
        ).first()
        
        if not player_member:
            return jsonify({'error': 'Player not found in this league'}), 404
        
        # Get player's user info
        player_user = User.query.get(user_id)
        if not player_user:
            return jsonify({'error': 'Player not found'}), 404
        
        # Calculate comprehensive stats
        total_games = player_member.wins + player_member.losses
        win_percentage = (player_member.wins / total_games * 100) if total_games > 0 else 0
        avg_money_per_week = player_member.points_for / max(1, total_games)
        
        # Get bet statistics
        from app.models import Bet
        user_bets = Bet.query.join(Matchup).filter(
            Matchup.league_id == league_id,
            Bet.user_id == user_id
        ).all()
        
        bets_won = len([bet for bet in user_bets if bet.status == 'won'])
        bets_lost = len([bet for bet in user_bets if bet.status == 'lost'])
        bets_pending = len([bet for bet in user_bets if bet.status == 'pending'])
        total_bets_placed = len(user_bets)
        
        # Get recent matchups
        recent_matchups = Matchup.query.filter_by(league_id=league_id)\
            .filter((Matchup.user1_id == user_id) | (Matchup.user2_id == user_id))\
            .order_by(Matchup.week.desc()).limit(5).all()
        
        recent_weeks = []
        for matchup in recent_matchups:
            is_user1 = matchup.user1_id == user_id
            opponent_id = matchup.user2_id if is_user1 else matchup.user1_id
            opponent_user = User.query.get(opponent_id)
            
            # Get bets for this matchup
            matchup_bets = Bet.query.filter_by(
                user_id=user_id,
                matchup_id=matchup.id
            ).all()
            
            result = 'win' if matchup.winner_id == user_id else 'loss' if matchup.winner_id else 'pending'
            money_earned = sum(bet.potential_payout - bet.amount for bet in matchup_bets if bet.status == 'won')
            money_against = sum(bet.amount for bet in matchup_bets if bet.status == 'lost')
            bets_placed = len(matchup_bets)
            bets_won_count = len([bet for bet in matchup_bets if bet.status == 'won'])
            
            recent_weeks.append({
                'week': matchup.week,
                'opponent': opponent_user.username if opponent_user else 'Unknown',
                'result': result,
                'money_earned': money_earned,
                'money_against': money_against,
                'bets_placed': bets_placed,
                'bets_won': bets_won_count
            })
        
        profile_data = {
            'id': user_id,
            'username': player_user.username,
            'league_id': league_id,
            'wins': player_member.wins,
            'losses': player_member.losses,
            'points_for': player_member.points_for,
            'points_against': player_member.points_against,
            'joined_at': player_member.joined_at.isoformat(),
            'avg_money_per_week': avg_money_per_week,
            'money_earned_total': player_member.points_for,
            'money_against': player_member.points_against,
            'current_streak': 0,  # Would need more complex calculation
            'longest_win_streak': 0,  # Would need historical data
            'longest_loss_streak': 0,  # Would need historical data
            'bets_won': bets_won,
            'bets_lost': bets_lost,
            'bets_pending': bets_pending,
            'total_bets_placed': total_bets_placed,
            'win_streak_type': 'none',  # Would need more complex calculation
            'win_percentage': win_percentage,
            'recent_weeks': recent_weeks,
            'head_to_head': []  # Would need more complex calculation
        }
        
        return jsonify({'profile': profile_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get player profile', 'details': str(e)}), 500

@leagues_bp.route('/<int:league_id>/matchups/all', methods=['GET'])
@jwt_required()
def get_all_matchups(league_id):
    """Get all matchups for a league"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is a member of the league
        member = LeagueMember.query.filter_by(
            league_id=league_id, 
            user_id=user_id
        ).first()
        
        if not member:
            return jsonify({'error': 'You are not a member of this league'}), 403
        
        # Get all matchups with comprehensive bet data
        matchups = Matchup.query.filter_by(league_id=league_id)\
            .order_by(Matchup.week.asc()).all()
        
        # Get comprehensive matchup data with bets
        matchups_data = []
        for matchup in matchups:
            # Get bets for both users in this matchup
            from app.models import Bet
            user1_bets = Bet.query.filter_by(
                matchup_id=matchup.id,
                user_id=matchup.user1_id
            ).all()
            
            user2_bets = Bet.query.filter_by(
                matchup_id=matchup.id,
                user_id=matchup.user2_id
            ).all()
            
            # Calculate totals
            user1_total_bet = sum(bet.amount for bet in user1_bets)
            user2_total_bet = sum(bet.amount for bet in user2_bets)
            user1_potential_payout = sum(bet.potential_payout for bet in user1_bets)
            user2_potential_payout = sum(bet.potential_payout for bet in user2_bets)
            
            # Format bet data
            user1_bets_data = []
            for bet in user1_bets:
                bet_data = {
                    'id': bet.id,
                    'amount': bet.amount,
                    'potential_payout': bet.potential_payout,
                    'status': bet.status,
                    'betting_option': {
                        'id': bet.betting_option.id,
                        'outcome_name': bet.betting_option.outcome_name,
                        'outcome_point': bet.betting_option.outcome_point,
                        'bookmaker': bet.betting_option.bookmaker,
                        'american_odds': bet.betting_option.american_odds,
                        'decimal_odds': bet.betting_option.decimal_odds,
                        'market_type': bet.betting_option.market_type
                    },
                    'game': {
                        'id': bet.betting_option.game.id,
                        'home_team': bet.betting_option.game.home_team,
                        'away_team': bet.betting_option.game.away_team,
                        'start_time': bet.betting_option.game.start_time.isoformat()
                    }
                }
                user1_bets_data.append(bet_data)
            
            user2_bets_data = []
            for bet in user2_bets:
                bet_data = {
                    'id': bet.id,
                    'amount': bet.amount,
                    'potential_payout': bet.potential_payout,
                    'status': bet.status,
                    'betting_option': {
                        'id': bet.betting_option.id,
                        'outcome_name': bet.betting_option.outcome_name,
                        'outcome_point': bet.betting_option.outcome_point,
                        'bookmaker': bet.betting_option.bookmaker,
                        'american_odds': bet.betting_option.american_odds,
                        'decimal_odds': bet.betting_option.decimal_odds,
                        'market_type': bet.betting_option.market_type
                    },
                    'game': {
                        'id': bet.betting_option.game.id,
                        'home_team': bet.betting_option.game.home_team,
                        'away_team': bet.betting_option.game.away_team,
                        'start_time': bet.betting_option.game.start_time.isoformat()
                    }
                }
                user2_bets_data.append(bet_data)
            
            matchup_data = {
                'id': matchup.id,
                'league_id': matchup.league_id,
                'week': matchup.week,
                'user1_id': matchup.user1_id,
                'user2_id': matchup.user2_id,
                'user1_username': matchup.user1.username,
                'user2_username': matchup.user2.username,
                'winner_id': matchup.winner_id,
                'created_at': matchup.created_at.isoformat(),
                'user1_bets': user1_bets_data,
                'user2_bets': user2_bets_data,
                'user1_total_bet': user1_total_bet,
                'user2_total_bet': user2_total_bet,
                'user1_potential_payout': user1_potential_payout,
                'user2_potential_payout': user2_potential_payout,
                'is_locked': False  # TODO: Implement lock logic
            }
            matchups_data.append(matchup_data)
        
        return jsonify({'matchups': matchups_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get all matchups', 'details': str(e)}), 500
