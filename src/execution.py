"""
Position sizing and risk engine for CourtQuant.
"""

from src.market import calculate_ev, american_to_decimal

def size_position(model_prob: float, offered_american_odds: float, bankroll: float, kelly_fraction: float = 0.25, max_risk_pct: float = 0.02, min_ev_pct: float = 4.0) -> dict:
    ev_pct = calculate_ev(model_prob, offered_american_odds)
    if ev_pct < min_ev_pct:
        return {"action": "PASS", "ev_pct": ev_pct, "stake_dollars": 0.0}
    
    dec_odds = american_to_decimal(offered_american_odds)
    b = dec_odds - 1.0
    p = model_prob
    q = 1.0 - p
    
    full_kelly = (b * p - q) / b
    if full_kelly <= 0:
        return {"action": "PASS", "ev_pct": ev_pct, "stake_dollars": 0.0}
        
    stake_pct = min(full_kelly * kelly_fraction, max_risk_pct)
    stake_dollars = round(bankroll * stake_pct, 2)
    
    return {
        "action": "BET",
        "ev_pct": ev_pct,
        "stake_pct": round(stake_pct * 100.0, 2),
        "stake_dollars": stake_dollars
    }
