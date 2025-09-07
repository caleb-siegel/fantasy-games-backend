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
        self.mock_data = True  # Set to False when you have a real API key
    
    def get_nfl_odds(self, week: int) -> List[Dict]:
        """Get NFL moneyline odds for a specific week"""
        if self.mock_data:
            return self._get_mock_nfl_odds(week)
        
        try:
            # Calculate date range for the week
            start_date, end_date = self._get_week_date_range(week)
            
            # Make API request
            url = f"{self.base_url}/sports/americanfootball_nfl/odds"
            params = {
                'apiKey': self.api_key,
                'regions': 'us',
                'markets': 'h2h',  # Head to head (moneyline)
                'dateFormat': 'iso',
                'commenceTimeFrom': start_date.isoformat(),
                'commenceTimeTo': end_date.isoformat()
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            odds_data = response.json()
            
            # Transform API response to our format
            formatted_odds = []
            for game in odds_data:
                formatted_game = {
                    'id': game['id'],
                    'home_team': game['home_team'],
                    'away_team': game['away_team'],
                    'start_time': game['commence_time'],
                    'week': week,
                    'home_odds': self._extract_odds(game['bookmakers'], game['home_team']),
                    'away_odds': self._extract_odds(game['bookmakers'], game['away_team'])
                }
                formatted_odds.append(formatted_game)
            
            return formatted_odds
            
        except requests.RequestException as e:
            print(f"Error fetching odds: {e}")
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
    
    def _get_week_date_range(self, week: int) -> tuple:
        """Calculate date range for NFL week"""
        # NFL season typically starts in September
        # This is a simplified calculation - you might want to use actual NFL schedule
        season_start = datetime(2024, 9, 5)  # Approximate start of 2024 season
        week_start = season_start + timedelta(weeks=week-1)
        week_end = week_start + timedelta(days=7)
        
        return week_start, week_end
    
    def _get_mock_nfl_odds(self, week: int) -> List[Dict]:
        """Mock NFL odds data for development/testing"""
        mock_games = [
            {
                'id': f'game_{week}_1',
                'home_team': 'Kansas City Chiefs',
                'away_team': 'Buffalo Bills',
                'start_time': (datetime.now() + timedelta(days=1)).isoformat(),
                'week': week,
                'home_odds': 1.85,
                'away_odds': 1.95
            },
            {
                'id': f'game_{week}_2',
                'home_team': 'Dallas Cowboys',
                'away_team': 'Philadelphia Eagles',
                'start_time': (datetime.now() + timedelta(days=2)).isoformat(),
                'week': week,
                'home_odds': 2.10,
                'away_odds': 1.75
            },
            {
                'id': f'game_{week}_3',
                'home_team': 'San Francisco 49ers',
                'away_team': 'Los Angeles Rams',
                'start_time': (datetime.now() + timedelta(days=3)).isoformat(),
                'week': week,
                'home_odds': 1.65,
                'away_odds': 2.25
            },
            {
                'id': f'game_{week}_4',
                'home_team': 'Miami Dolphins',
                'away_team': 'New York Jets',
                'start_time': (datetime.now() + timedelta(days=4)).isoformat(),
                'week': week,
                'home_odds': 1.90,
                'away_odds': 1.90
            }
        ]
        
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
