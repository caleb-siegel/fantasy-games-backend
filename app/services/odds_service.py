import requests
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class OddsService:
    """Service for integrating with external sports odds APIs"""
    
    def __init__(self):
        # You can use The Odds API, OddsJam, or Sportsbook API
        # For this example, I'll use The Odds API format
        self.api_key = os.getenv('ODDS_API_KEY', 'your-api-key-here')
        self.base_url = 'https://api.the-odds-api.com/v4'
        
        # Fallback mock data for development/testing
        self.mock_data = self.api_key == 'your-api-key-here'  # Use mock data if no real API key
    
    def get_nfl_odds(self, week: int) -> List[Dict]:
        """Get NFL odds for a specific week and save all betting options to database"""
        if self.mock_data:
            return self._get_mock_nfl_odds(week)
        
        try:
            # Use the exact endpoint format from your working API call
            url = f"{self.base_url}/sports/americanfootball_nfl/odds"
            params = {
                'apiKey': self.api_key,
                'regions': 'us',
                'oddsFormat': 'american',
                'markets': 'h2h,spreads,totals'
            }
            
            print(f"🌐 Fetching NFL odds from: {url}")
            print(f"🔑 Using API key: {self.api_key[:8]}...")
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            odds_data = response.json()
            print(f"✅ Successfully fetched {len(odds_data)} NFL games")
            
            # Save all betting options to database
            self._save_betting_options_to_db(odds_data, week)
            
            # Return formatted games for API response
            formatted_odds = []
            for game in odds_data:
                formatted_game = {
                    'id': game['id'],
                    'home_team': game['home_team'],
                    'away_team': game['away_team'],
                    'start_time': game['commence_time'],
                    'week': week
                }
                formatted_odds.append(formatted_game)
            
            return formatted_odds
            
        except requests.RequestException as e:
            print(f"❌ Error fetching odds: {e}")
            return self._get_mock_nfl_odds(week)  # Fallback to mock data
    
    def get_game_odds(self, game_id: str) -> Optional[Dict]:
        """Get odds for a specific game"""
        if self.mock_data:
            return self._get_mock_game_odds(game_id)
        
        try:
            url = f"{self.base_url}/sports/americanfootball_nfl/odds"
            params = {
                'apiKey': self.api_key,
                'regions': 'us',
                'markets': 'h2h',
                'eventIds': game_id
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            games = response.json()
            if games:
                game = games[0]
                return {
                    'home_odds': self._extract_odds(game['bookmakers'], game['home_team']),
                    'away_odds': self._extract_odds(game['bookmakers'], game['away_team'])
                }
            
            return None
            
        except requests.RequestException as e:
            print(f"Error fetching game odds: {e}")
            return self._get_mock_game_odds(game_id)
    
    def get_game_result(self, game_id: str) -> Optional[str]:
        """Get the result of a completed game"""
        if self.mock_data:
            return self._get_mock_game_result(game_id)
        
        try:
            url = f"{self.base_url}/sports/americanfootball_nfl/scores"
            params = {
                'apiKey': self.api_key,
                'eventIds': game_id
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            games = response.json()
            if games:
                game = games[0]
                if game['completed']:
                    home_score = game['scores'][0]['score']
                    away_score = game['scores'][1]['score']
                    
                    if home_score > away_score:
                        return 'home_win'
                    elif away_score > home_score:
                        return 'away_win'
                    else:
                        return 'tie'  # Handle ties if needed
            
            return None
            
        except requests.RequestException as e:
            print(f"Error fetching game result: {e}")
            return self._get_mock_game_result(game_id)
    
    def _extract_odds(self, bookmakers: List[Dict], team: str) -> float:
        """Extract odds for a specific team from bookmaker data"""
        for bookmaker in bookmakers:
            for market in bookmaker['markets']:
                if market['key'] == 'h2h':
                    for outcome in market['outcomes']:
                        if outcome['name'] == team:
                            return float(outcome['price'])
        return 1.0  # Default odds if not found
    
    def _convert_american_to_decimal(self, american_odds: int) -> float:
        """Convert American odds to decimal odds"""
        if american_odds > 0:
            # Positive American odds: decimal = (american / 100) + 1
            return (american_odds / 100) + 1
        else:
            # Negative American odds: decimal = (100 / |american|) + 1
            return (100 / abs(american_odds)) + 1
    
    def _save_betting_options_to_db(self, odds_data: List[Dict], week: int):
        """Save all betting options from API to database"""
        from app.models import Game, BettingOption
        from app import db
        
        betting_options_saved = 0
        
        for game_data in odds_data:
            # Save or update game
            existing_game = Game.query.get(game_data['id'])
            if existing_game:
                existing_game.home_team = game_data['home_team']
                existing_game.away_team = game_data['away_team']
                existing_game.start_time = datetime.fromisoformat(game_data['commence_time'])
                existing_game.week = week
            else:
                game = Game(
                    id=game_data['id'],
                    home_team=game_data['home_team'],
                    away_team=game_data['away_team'],
                    start_time=datetime.fromisoformat(game_data['commence_time']),
                    week=week
                )
                db.session.add(game)
            
            # Clear existing betting options for this game
            BettingOption.query.filter_by(game_id=game_data['id']).delete()
            
            # Save all betting options from all bookmakers
            for bookmaker in game_data.get('bookmakers', []):
                bookmaker_name = bookmaker['key']
                
                for market in bookmaker.get('markets', []):
                    market_type = market['key']  # h2h, spreads, totals
                    
                    for outcome in market.get('outcomes', []):
                        betting_option = BettingOption(
                            game_id=game_data['id'],
                            market_type=market_type,
                            outcome_name=outcome['name'],
                            outcome_point=outcome.get('point'),
                            bookmaker=bookmaker_name,
                            american_odds=outcome['price'],
                            decimal_odds=self._convert_american_to_decimal(outcome['price'])
                        )
                        db.session.add(betting_option)
                        betting_options_saved += 1
        
        db.session.commit()
        print(f"💾 Saved {betting_options_saved} betting options to database")
    
    def _get_week_date_range(self, week: int) -> tuple:
        """Calculate date range for NFL week"""
        # NFL season typically starts in September
        # This is a simplified calculation - you might want to use actual NFL schedule
        season_start = datetime(2024, 9, 5)  # Approximate start of 2024 season
        week_start = season_start + timedelta(weeks=week-1)
        week_end = week_start + timedelta(days=7)
        
        return week_start, week_end
    
    def _get_mock_nfl_odds(self, week: int) -> List[Dict]:
        """Mock NFL odds data for development/testing - Week 1 2024"""
        import random
        
        # Week 1 NFL 2024 schedule (simplified)
        week1_games = [
            ('Baltimore Ravens', 'Kansas City Chiefs'),
            ('Buffalo Bills', 'Arizona Cardinals'),
            ('Cincinnati Bengals', 'New England Patriots'),
            ('Cleveland Browns', 'Dallas Cowboys'),
            ('Denver Broncos', 'Seattle Seahawks'),
            ('Houston Texans', 'Indianapolis Colts'),
            ('Jacksonville Jaguars', 'Miami Dolphins'),
            ('Las Vegas Raiders', 'Los Angeles Chargers'),
            ('Los Angeles Rams', 'Detroit Lions'),
            ('New York Giants', 'Minnesota Vikings'),
            ('New York Jets', 'San Francisco 49ers'),
            ('Pittsburgh Steelers', 'Atlanta Falcons'),
            ('Tampa Bay Buccaneers', 'Washington Commanders'),
            ('Tennessee Titans', 'Chicago Bears'),
            ('Green Bay Packers', 'Philadelphia Eagles'),
            ('Carolina Panthers', 'New Orleans Saints')
        ]
        
        mock_games = []
        for i, (away_team, home_team) in enumerate(week1_games):
            # Generate realistic odds (1.5 to 3.0 range)
            home_odds = round(random.uniform(1.5, 3.0), 2)
            away_odds = round(random.uniform(1.5, 3.0), 2)
            
            # Generate game times throughout the weekend
            if i < 4:  # Thursday games
                game_time = datetime.now() + timedelta(days=1, hours=20)
            elif i < 12:  # Sunday early games
                game_time = datetime.now() + timedelta(days=3, hours=13)
            elif i < 14:  # Sunday late games
                game_time = datetime.now() + timedelta(days=3, hours=16)
            else:  # Sunday night and Monday games
                game_time = datetime.now() + timedelta(days=3, hours=20)
            
            mock_games.append({
                'id': f'game_{week}_{i+1}',
                'home_team': home_team,
                'away_team': away_team,
                'start_time': game_time.isoformat(),
                'week': week,
                'home_odds': home_odds,
                'away_odds': away_odds
            })
        
        return mock_games
    
    def _get_mock_game_odds(self, game_id: str) -> Dict:
        """Mock game odds for a specific game"""
        return {
            'home_odds': 1.85,
            'away_odds': 1.95
        }
    
    def _get_mock_game_result(self, game_id: str) -> str:
        """Mock game result - randomly determine winner"""
        import random
        return random.choice(['home_win', 'away_win'])
