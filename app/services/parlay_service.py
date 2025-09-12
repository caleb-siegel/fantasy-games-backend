"""
Parlay Betting Calculation Utilities

This module provides functions to calculate parlay odds, payouts, and profits
based on American odds from multiple betting options.
"""

from functools import reduce
from typing import List, Dict, Union


def american_to_decimal(american_odds: int) -> float:
    """
    Convert American odds to decimal odds.
    
    Args:
        american_odds: American odds (e.g., -150, +200)
        
    Returns:
        Decimal odds (e.g., 1.67, 3.0)
    """
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


def parlay_decimal_odds(american_odds_list: List[int]) -> float:
    """
    Calculate the combined decimal odds for a parlay.
    
    Args:
        american_odds_list: List of American odds for each leg
        
    Returns:
        Combined decimal odds for the parlay
    """
    if len(american_odds_list) < 2:
        raise ValueError("Parlay must have at least 2 legs")
    
    decimal_odds = [american_to_decimal(odds) for odds in american_odds_list]
    return reduce(lambda x, y: x * y, decimal_odds)


def parlay_payout(stake: float, american_odds_list: List[int]) -> float:
    """
    Calculate the total payout for a parlay bet.
    
    Args:
        stake: The amount wagered
        american_odds_list: List of American odds for each leg
        
    Returns:
        Total payout amount
    """
    odds = parlay_decimal_odds(american_odds_list)
    return round(stake * odds, 2)


def parlay_profit(stake: float, american_odds_list: List[int]) -> Dict[str, float]:
    """
    Calculate parlay profit and return information.
    
    Args:
        stake: The amount wagered
        american_odds_list: List of American odds for each leg
        
    Returns:
        Dictionary with 'return', 'profit', 'decimal_odds', and 'stake'
    """
    decimal_odds = parlay_decimal_odds(american_odds_list)
    total_return = parlay_payout(stake, american_odds_list)
    
    return {
        "stake": stake,
        "decimal_odds": round(decimal_odds, 4),
        "return": total_return,
        "profit": round(total_return - stake, 2)
    }


def validate_parlay_bets(betting_options: List[Dict]) -> bool:
    """
    Validate that betting options can be combined into a parlay.
    
    Args:
        betting_options: List of betting option dictionaries
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    if len(betting_options) < 2:
        raise ValueError("Parlay must have at least 2 legs")
    
    if len(betting_options) > 10:
        raise ValueError("Parlay cannot have more than 10 legs")
    
    # Check that no options are locked
    for option in betting_options:
        if option.get('is_locked', False):
            raise ValueError("Cannot include locked betting options in parlay")
    
    return True


def calculate_parlay_from_options(stake: float, betting_options: List[Dict]) -> Dict[str, Union[float, List[Dict]]]:
    """
    Calculate parlay information from betting options.
    
    Args:
        stake: The amount wagered
        betting_options: List of betting option dictionaries
        
    Returns:
        Dictionary with parlay calculation results and leg details
    """
    validate_parlay_bets(betting_options)
    
    american_odds_list = [option['american_odds'] for option in betting_options]
    parlay_info = parlay_profit(stake, american_odds_list)
    
    # Add leg details
    legs = []
    for i, option in enumerate(betting_options):
        leg_info = {
            "leg_number": i + 1,
            "betting_option_id": option['id'],
            "game_id": option['game_id'],
            "outcome_name": option['outcome_name'],
            "outcome_point": option.get('outcome_point'),
            "market_type": option['market_type'],
            "bookmaker": option['bookmaker'],
            "american_odds": option['american_odds'],
            "decimal_odds": option['decimal_odds']
        }
        legs.append(leg_info)
    
    return {
        **parlay_info,
        "legs": legs,
        "leg_count": len(betting_options)
    }


# Example usage and testing
if __name__ == "__main__":
    # Test with example odds
    test_odds = [-110, +150, -200]
    test_stake = 100
    
    result = parlay_profit(test_stake, test_odds)
    print(f"Parlay calculation for odds {test_odds} with stake ${test_stake}:")
    print(f"Decimal odds: {result['decimal_odds']}")
    print(f"Total return: ${result['return']}")
    print(f"Profit: ${result['profit']}")
    
    # Test validation
    try:
        validate_parlay_bets([{"game_id": "1"}, {"game_id": "2"}])
        print("✓ Validation passed")
    except ValueError as e:
        print(f"✗ Validation failed: {e}")
