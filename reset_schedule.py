#!/usr/bin/env python3
"""
Script to reset and regenerate matchups for a league.
This will clear existing matchups and create a new schedule.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import League, LeagueMember, Matchup, User, Bet
from datetime import datetime

def generate_round_robin_schedule(teams, weeks_required=14):
    """Generate a round-robin schedule for the given teams."""
    if len(teams) < 2:
        return []
    
    # If odd number of teams, add a bye
    if len(teams) % 2 == 1:
        teams = teams + ['BYE']
    
    n = len(teams)
    rounds = []
    fixed = teams[0]
    rotating = teams[1:]
    
    # Generate rounds - continue until we have enough weeks
    round_num = 0
    while len(rounds) < weeks_required:
        if round_num >= n - 1:
            # Reset rotation for additional rounds
            round_num = 0
            
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
        
        round_num += 1
    
    return rounds[:weeks_required]

def reset_and_regenerate_schedule(league_id):
    """Reset matchups and regenerate schedule for a league."""
    app = create_app()
    
    with app.app_context():
        # Get the league
        league = League.query.get(league_id)
        if not league:
            print(f"League {league_id} not found")
            return
        
        print(f"Resetting schedule for league: {league.name}")
        
        # Get all league members
        members = LeagueMember.query.filter_by(league_id=league_id).all()
        if len(members) < 2:
            print("Need at least 2 members to generate schedule")
            return
        
        print(f"Found {len(members)} members:")
        for member in members:
            user = User.query.get(member.user_id)
            print(f"  - {user.username}")
        
        # Clear existing matchups and related bets
        existing_matchups = Matchup.query.filter_by(league_id=league_id).all()
        print(f"Clearing {len(existing_matchups)} existing matchups...")
        
        # First, delete bets that reference these matchups
        matchup_ids = [m.id for m in existing_matchups]
        if matchup_ids:
            bets_to_delete = Bet.query.filter(Bet.matchup_id.in_(matchup_ids)).all()
            print(f"Deleting {len(bets_to_delete)} bets associated with existing matchups...")
            for bet in bets_to_delete:
                db.session.delete(bet)
        
        # Also delete any bets with null matchup_id (orphaned bets)
        null_bets = Bet.query.filter_by(matchup_id=None).all()
        if null_bets:
            print(f"Deleting {len(null_bets)} bets with null matchup_id...")
            for bet in null_bets:
                db.session.delete(bet)
        
        # Now delete the matchups
        for matchup in existing_matchups:
            db.session.delete(matchup)
        
        # Extract user IDs
        team_ids = [member.user_id for member in members]
        
        # Generate new schedule
        schedule = generate_round_robin_schedule(team_ids, 14)
        
        print(f"Generated {len(schedule)} weeks of matchups:")
        
        # Create new matchups
        matchup_count = 0
        for week_num, week_matches in enumerate(schedule, 1):
            print(f"  Week {week_num}: {len(week_matches)} matchups")
            for match in week_matches:
                matchup = Matchup(
                    league_id=league_id,
                    week=week_num,
                    user1_id=match['home'],
                    user2_id=match['away']
                )
                db.session.add(matchup)
                matchup_count += 1
                
                # Get usernames for display
                user1 = User.query.get(match['home'])
                user2 = User.query.get(match['away'])
                print(f"    {user1.username} vs {user2.username}")
        
        # Commit changes
        db.session.commit()
        
        print(f"\nSuccessfully created {matchup_count} matchups!")
        print(f"Schedule covers {len(schedule)} weeks with {len(schedule[0]) if schedule else 0} matchups per week")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python reset_schedule.py <league_id>")
        sys.exit(1)
    
    league_id = int(sys.argv[1])
    reset_and_regenerate_schedule(league_id)
