"""
Closing Line Value (CLV) tracking module for CourtQuant.
Compares locked-in wager prices against de-vigged closing lines.
"""

import numpy as np
from src.market import american_to_decimal

def calculate_clv(bet_american_odds: float, closing_american_odds_a: float, closing_american_odds_b: float, bet_on_player_a: bool = True) -> dict:
    """
    Calculates Price CLV and No-Vig CLV against closing market lines.
    """
    dec_bet = american_to_decimal(bet_american_odds)
    
    dec_close_a = american_to_decimal(closing_american_odds_a)
    dec_close_b = american_to_decimal(closing_american_odds_b)
    
    # Proportional de-vigging of closing line
    imp_a = 1.0 / dec_close_a
    imp_b = 1.0 / dec_close_b
    total_imp = imp_a + imp_b
    
    fair_prob_a = imp_a / total_imp
    fair_prob_b = imp_b / total_imp
    
    if bet_on_player_a:
        price_clv = (dec_bet / dec_close_a) - 1.0
        no_vig_clv = (dec_bet * fair_prob_a) - 1.0
    else:
        price_clv = (dec_bet / dec_close_b) - 1.0
        no_vig_clv = (dec_bet * fair_prob_b) - 1.0
        
    return {
        "price_clv_pct": round(price_clv * 100.0, 2),
        "no_vig_clv_pct": round(no_vig_clv * 100.0, 2),
        "beating_closing": no_vig_clv > 0.0
    }
