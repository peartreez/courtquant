"""
Parlay combination and Expected Value engine for CourtQuant.
Combines positive EV individual wager legs into multi-leg parlays across US DFS and Exchanges.
"""

import pandas as pd
import itertools
from src.market import american_to_decimal, decimal_to_american, calculate_ev

def generate_parlay_suggestions(df_bets: pd.DataFrame, max_legs: int = 3, max_parlays: int = 6) -> list:
    """
    Takes positive EV individual bets and generates multi-leg parlay combinations 
    while avoiding conflicting selections on the same match.
    """
    if df_bets is None or df_bets.empty or len(df_bets) < 2:
        return []
        
    parlays = []
    sorted_bets = df_bets.sort_values(by="EV %", ascending=False).to_dict('records')
    
    for r in range(2, min(max_legs + 1, len(sorted_bets) + 1)):
        for combo in itertools.combinations(sorted_bets, r):
            # Ensure no duplicate matches in the same parlay
            matches = [leg['Match'] for leg in combo]
            if len(set(matches)) < len(matches):
                continue
                
            combined_dec = 1.0
            combined_prob = 1.0
            leg_details = []
            
            for leg in combo:
                dec = american_to_decimal(leg['Offered Odds'])
                combined_dec *= dec
                combined_prob *= leg['Model Win Prob']
                leg_details.append(f"{leg['Bet Target']} ({leg['Offered Odds']:+d}) [{leg['Bookmaker']}]")
                
            parlay_american = decimal_to_american(combined_dec)
            parlay_ev = calculate_ev(combined_prob, parlay_american)
            
            if parlay_ev > 2.0: # Minimum 2% EV threshold for parlays
                parlays.append({
                    "Leg Count": len(combo),
                    "Legs Description": " + ".join(leg_details),
                    "Combined Odds": parlay_american,
                    "Combined Win Prob (%)": round(combined_prob * 100.0, 1),
                    "Combined EV (%)": parlay_ev,
                })
                
    parlays = sorted(parlays, key=lambda x: x["Combined EV (%)"], reverse=True)
    return parlays[:max_parlays]
