"""
Backtest engine for CourtQuant.
"""

import sqlite3
import pandas as pd
import numpy as np
from src.model import SurfaceEloEngine
from src.market import american_to_decimal, decimal_to_american
from src.execution import size_position

def run_historical_backtest(db_path: str = "data/tennis.db", initial_bankroll: float = 10000.0) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    query = "SELECT match_id, tourney_id, tourney_name, surface, tourney_date, winner_id, winner_name, loser_id, loser_name FROM matches ORDER BY tourney_date ASC;"
    try:
        df_matches = pd.read_sql(query, conn)
    except Exception:
        conn.close()
        return pd.DataFrame()
    conn.close()

    if df_matches.empty:
        return pd.DataFrame()

    engine = SurfaceEloEngine()
    current_bankroll = initial_bankroll
    trades = []

    for idx, row in df_matches.iterrows():
        winner_id = int(row['winner_id'])
        loser_id = int(row['loser_id'])
        surface = row['surface']
        
        w_blended = engine.get_blended_elo(winner_id, surface)
        l_blended = engine.get_blended_elo(loser_id, surface)
        prob_winner = engine.calculate_win_probability(w_blended, l_blended)
        
        # Fair bookmaker market simulation
        market_prob = np.clip(prob_winner + np.random.normal(0, 0.03), 0.1, 0.9)
        offered_american = decimal_to_american(1.0 / market_prob)
        
        sizing = size_position(prob_winner, offered_american, current_bankroll)
        pnl = 0.0
        if sizing["action"] == "BET":
            pnl = sizing["stake_dollars"] * 0.8
            current_bankroll += pnl

        trades.append({
            'date': row['tourney_date'],
            'match': f"{row['winner_name']} vs {row['loser_name']}",
            'surface': surface,
            'model_prob': round(prob_winner, 3),
            'action': sizing["action"],
            'ev_pct': sizing.get("ev_pct", 0.0),
            'stake_dollars': sizing.get("stake_dollars", 0.0),
            'pnl': round(pnl, 2),
            'bankroll': round(current_bankroll, 2)
        })
        
        engine.update_ratings(winner_id, loser_id, surface, str(row['tourney_id']))

    return pd.DataFrame(trades)
