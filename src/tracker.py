"""
Live Trade & Bet Logging module for CourtQuant.
Stores placed bets, opening/closing odds, actual results, P&L, and CLV performance in SQLite.
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime

def initialize_tracker_db(db_path: str = "data/tennis.db"):
    """
    Initializes the placed_bets table in SQLite if it does not exist.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS placed_bets (
            bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            match TEXT,
            bet_target TEXT,
            bookmaker TEXT,
            offered_odds INTEGER,
            stake_dollars REAL,
            model_prob REAL,
            ev_pct REAL,
            closing_odds INTEGER,
            status TEXT DEFAULT 'PENDING',
            pnl REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()

def log_placed_bet(match: str, bet_target: str, bookmaker: str, offered_odds: int, stake_dollars: float, model_prob: float, ev_pct: float, db_path: str = "data/tennis.db") -> bool:
    """
    Logs a new active trade into the SQLite database.
    """
    initialize_tracker_db(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO placed_bets (timestamp, match, bet_target, bookmaker, offered_odds, stake_dollars, model_prob, ev_pct, status, pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0.0)
    """, (now_str, match, bet_target, bookmaker, offered_odds, stake_dollars, model_prob, ev_pct))
    conn.commit()
    conn.close()
    return True

def get_placed_bets(db_path: str = "data/tennis.db") -> pd.DataFrame:
    """
    Retrieves all logged trades as a clean DataFrame.
    """
    initialize_tracker_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql("SELECT * FROM placed_bets ORDER BY bet_id DESC;", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def update_bet_result(bet_id: int, status: str, closing_odds: int = None, db_path: str = "data/tennis.db"):
    """
    Updates the settlement result (WON, LOST, PUSH) and calculates P&L.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch bet details
    cursor.execute("SELECT offered_odds, stake_dollars FROM placed_bets WHERE bet_id = ?;", (bet_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
        
    offered_odds, stake = row
    pnl = 0.0
    
    if status == 'WON':
        if offered_odds > 0:
            pnl = stake * (offered_odds / 100.0)
        else:
            pnl = stake * (100.0 / abs(offered_odds))
    elif status == 'LOST':
        pnl = -stake
        
    cursor.execute("""
        UPDATE placed_bets
        SET status = ?, pnl = ?, closing_odds = ?
        WHERE bet_id = ?;
    """, (status, round(pnl, 2), closing_odds, bet_id))
    
    conn.commit()
    conn.close()
