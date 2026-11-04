"""
Market odds utility functions for CourtQuant.
"""

def american_to_decimal(american_odds: float) -> float:
    if american_odds > 0:
        return (american_odds / 100.0) + 1.0
    else:
        return (100.0 / abs(american_odds)) + 1.0

def decimal_to_american(decimal_odds: float) -> float:
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1.0) * 100.0)
    else:
        return round(-100.0 / (decimal_odds - 1.0))

def calculate_ev(model_prob: float, american_odds: float) -> float:
    dec_odds = american_to_decimal(american_odds)
    ev = (model_prob * dec_odds) - 1.0
    return round(ev * 100.0, 2)
