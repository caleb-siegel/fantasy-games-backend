from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, League, LeagueMember, Matchup
from datetime import datetime
import itertools
import random

leagues_bp = Blueprint('leagues', __name__)

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
        data = request.get_json()
        user_id = int(get_jwt_identity())
        
        if not data or 'name' not in data:
            return jsonify({'error': 'League name is required'}), 400
        
        league_name = data['name'].strip()
        if not league_name:
            return jsonify({'error': 'League name cannot be empty'}), 400
        
        # Create league
        league = League(name=league_name, commissioner_id=user_id)
        db.session.add(league)
        db.session.flush()  # Get the league ID
        
        # Add commissioner as first member
        member = LeagueMember(league_id=league.id, user_id=user_id)
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
        data = request.get_json()
        user_id = int(get_jwt_identity())
        
        if not data or 'invite_code' not in data:
            return jsonify({'error': 'Invite code is required'}), 400
        
        invite_code = data['invite_code'].strip().upper()
        
        # Find league by invite code
        league = League.query.filter_by(invite_code=invite_code).first()
        if not league:
            return jsonify({'error': 'Invalid invite code'}), 404
        
        # Check if user is already a member
        existing_member = LeagueMember.query.filter_by(
            league_id=league.id, 
            user_id=user_id
        ).first()
        
        if existing_member:
            return jsonify({'error': 'You are already a member of this league'}), 409
        
        # Add user to league
        member = LeagueMember(league_id=league.id, user_id=user_id)
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
    """Generate weekly schedule for the league"""
    try:
        user_id = int(get_jwt_identity())
        
        # Check if user is the commissioner
        league = League.query.get(league_id)
        if not league:
            return jsonify({'error': 'League not found'}), 404
        
        if league.commissioner_id != user_id:
            return jsonify({'error': 'Only the commissioner can generate schedules'}), 403
        
        # Get all league members
        members = LeagueMember.query.filter_by(league_id=league_id).all()
        if len(members) < 2:
            return jsonify({'error': 'Need at least 2 members to generate schedule'}), 400
        
        # Get data for schedule generation
        data = request.get_json() or {}
        weeks = data.get('weeks', 10)  # Default 10 weeks
        
        # Clear existing matchups for this league
        Matchup.query.filter_by(league_id=league_id).delete()
        
        # Generate round-robin schedule
        user_ids = [member.user_id for member in members]
        matchups = []
        
        # Create all possible pairs
        pairs = list(itertools.combinations(user_ids, 2))
        
        # Distribute pairs across weeks
        for week in range(1, weeks + 1):
            week_matchups = []
            
            # For each week, try to assign matchups
            remaining_pairs = pairs.copy()
            used_users = set()
            
            while remaining_pairs and len(week_matchups) < len(user_ids) // 2:
                for pair in remaining_pairs[:]:
                    if pair[0] not in used_users and pair[1] not in used_users:
                        matchup = Matchup(
                            league_id=league_id,
                            week=week,
                            user1_id=pair[0],
                            user2_id=pair[1]
                        )
                        week_matchups.append(matchup)
                        used_users.add(pair[0])
                        used_users.add(pair[1])
                        remaining_pairs.remove(pair)
                        break
                else:
                    break
            
            matchups.extend(week_matchups)
        
        # Add matchups to database
        for matchup in matchups:
            db.session.add(matchup)
        
        db.session.commit()
        
        return jsonify({
            'message': f'Schedule generated for {weeks} weeks',
            'matchups': len(matchups)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to generate schedule', 'details': str(e)}), 500

@leagues_bp.route('/<int:league_id>/confirm-setup', methods=['POST'])
@jwt_required()
def confirm_league_setup(league_id):
    """Commissioner confirms league setup and generates all matchups"""
    try:
        user_id = int(get_jwt_identity())
        
        # Get league and verify commissioner
        league = League.query.get(league_id)
        if not league:
            return jsonify({'error': 'League not found'}), 404
        
        if league.commissioner_id != user_id:
            return jsonify({'error': 'Only the commissioner can confirm league setup'}), 403
        
        if league.is_setup_complete:
            return jsonify({'error': 'League setup is already complete'}), 400
        
        # Get all league members
        members = LeagueMember.query.filter_by(league_id=league_id).all()
        member_ids = [member.user_id for member in members]
        
        if len(member_ids) < 2:
            return jsonify({'error': 'League must have at least 2 members to generate matchups'}), 400
        
        # Generate regular season matchups (weeks 1-14)
        regular_season_matchups = generate_regular_season_matchups(league_id, member_ids)
        
        # Generate playoff matchups (weeks 15-17)
        playoff_matchups = generate_playoff_matchups(league_id, member_ids)
        
        # Add all matchups to database
        all_matchups = regular_season_matchups + playoff_matchups
        for matchup in all_matchups:
            db.session.add(matchup)
        
        # Mark league as setup complete
        league.is_setup_complete = True
        league.setup_completed_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'League setup confirmed successfully',
            'regular_season_matchups': len(regular_season_matchups),
            'playoff_matchups': len(playoff_matchups),
            'total_matchups': len(all_matchups)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to confirm league setup', 'details': str(e)}), 500

def generate_regular_season_matchups(league_id, member_ids):
    """Generate regular season matchups for weeks 1-14"""
    matchups = []
    
    # Create a copy of member_ids to work with
    members = member_ids.copy()
    
    # For odd number of members, add a "bye" member (use -1 as placeholder)
    if len(members) % 2 == 1:
        members.append(-1)
    
    # Generate matchups for each week
    for week in range(1, 15):  # weeks 1-14
        week_matchups = []
        
        # Rotate members for each week (round-robin style)
        if week > 1:
            # Move first member to end, shift others up
            members = members[1:] + [members[0]]
        
        # Pair up members
        for i in range(0, len(members), 2):
            user1_id = members[i]
            user2_id = members[i + 1]
            
            # Skip if either is a bye week
            if user1_id == -1 or user2_id == -1:
                continue
            
            matchup = Matchup(
                league_id=league_id,
                week=week,
                user1_id=user1_id,
                user2_id=user2_id
            )
            week_matchups.append(matchup)
        
        matchups.extend(week_matchups)
    
    return matchups

def generate_playoff_matchups(league_id, member_ids):
    """Generate playoff bracket for weeks 15-17"""
    matchups = []
    
    # For playoffs, we'll use a simple bracket system
    # Week 15: Quarterfinals (if 8+ members) or Semifinals (if 4-7 members)
    # Week 16: Semifinals (if 8+ members) or Finals (if 4-7 members)  
    # Week 17: Finals (if 8+ members) or Championship (if 4-7 members)
    
    num_members = len(member_ids)
    
    if num_members >= 8:
        # 8+ members: Full bracket
        # Week 15: Quarterfinals (8 teams -> 4 teams)
        # Week 16: Semifinals (4 teams -> 2 teams)
        # Week 17: Finals (2 teams -> 1 champion)
        
        # For now, we'll create placeholder matchups that will be filled based on regular season standings
        # The actual seeding will be determined by regular season performance
        
        # Week 15 - Quarterfinals (4 matchups)
        for i in range(4):
            if i * 2 + 1 < len(member_ids):
                matchup = Matchup(
                    league_id=league_id,
                    week=15,
                    user1_id=member_ids[i * 2],
                    user2_id=member_ids[i * 2 + 1]
                )
                matchups.append(matchup)
        
        # Week 16 - Semifinals (2 matchups) - Use actual members for now
        # In a real implementation, these would be filled by quarterfinal winners
        semifinal_members = member_ids[4:8] if len(member_ids) >= 8 else member_ids[2:4]
        for i in range(2):
            if i * 2 + 1 < len(semifinal_members):
                matchup = Matchup(
                    league_id=league_id,
                    week=16,
                    user1_id=semifinal_members[i * 2],
                    user2_id=semifinal_members[i * 2 + 1]
                )
                matchups.append(matchup)
        
        # Week 17 - Finals (1 matchup) - Use actual members for now
        # In a real implementation, this would be filled by semifinal winners
        if len(member_ids) >= 2:
            matchup = Matchup(
                league_id=league_id,
                week=17,
                user1_id=member_ids[0],
                user2_id=member_ids[1]
            )
            matchups.append(matchup)
        
    elif num_members >= 4:
        # 4-7 members: Smaller bracket
        # Week 15: Semifinals (4 teams -> 2 teams)
        # Week 16: Finals (2 teams -> 1 champion)
        # Week 17: No games (or consolation)
        
        # Week 15 - Semifinals
        for i in range(min(2, num_members // 2)):
            if i * 2 + 1 < len(member_ids):
                matchup = Matchup(
                    league_id=league_id,
                    week=15,
                    user1_id=member_ids[i * 2],
                    user2_id=member_ids[i * 2 + 1]
                )
                matchups.append(matchup)
        
        # Week 16 - Finals - Use actual members for now
        # In a real implementation, this would be filled by semifinal winners
        if len(member_ids) >= 2:
            matchup = Matchup(
                league_id=league_id,
                week=16,
                user1_id=member_ids[0],
                user2_id=member_ids[1]
            )
            matchups.append(matchup)
        
    else:
        # Less than 4 members: Simple head-to-head for remaining weeks
        for week in range(15, 18):
            if len(member_ids) >= 2:
                matchup = Matchup(
                    league_id=league_id,
                    week=week,
                    user1_id=member_ids[0],
                    user2_id=member_ids[1]
                )
                matchups.append(matchup)
    
    return matchups
