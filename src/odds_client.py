"""
The Odds API integration module for CourtQuant.
Dynamically fetches active tennis sports and matches live odds with surface Elo model execution.
Supports US DFS and US Exchange regions ('us_dfs,us_ex') with robust deduplication.
"""

import sqlite3
import requests
import pandas as pd
from src.model import SurfaceEloEngine
from src.execution import size_position
from src.market import calculate_ev

BASE_URL = "https://api.the-odds-api.com/v4"

def fetch_active_tennis_sports(api_key: str) -> list:
    """
    Queries /v4/sports to dynamically find all active tennis sport keys.
    """
    url = f"{BASE_URL}/sports"
    params = {"apiKey": api_key}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        sports = res.json()
        return [s for s in sports if 'tennis' in s.get('key', '') and s.get('active', False)]
    except Exception as e:
        print(f"Error querying active sports from The Odds API: {e}")
        return []

def fetch_live_tennis_odds(api_key: str, sport_key: str) -> list:
    """
    Fetches live bookmaker market odds combining US DFS sites ('us_dfs') and US Exchanges ('us_ex').
    """
    url = f"{BASE_URL}/sports/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": "us_dfs,us_ex",  # Both US DFS and US Exchanges
        "markets": "h2h",
        "oddsFormat": "american"
    }
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"Error fetching odds for {sport_key}: {e}")
        return []

def parse_odds_to_dataframe(odds_data: list) -> pd.DataFrame:
    """
    Parses raw JSON odds payload into structured DataFrame for analysis with deduplication.
    """
    rows = []
    for event in odds_data:
        event_id = event.get("id")
        commence_time = event.get("commence_time")
        home_player = event.get("home_team")
        away_player = event.get("away_team")
        
        for bookmaker in event.get("bookmakers", []):
            book_title = bookmaker.get("title")
            for market in bookmaker.get("markets", []):
                if market.get("key") == "h2h":
                    outcomes = market.get("outcomes", [])
                    if len(outcomes) == 2:
                        rows.append({
                            "event_id": event_id,
                            "commence_time": commence_time,
                            "player_1": home_player,
                            "p1_odds": outcomes[0].get("price"),
                            "player_2": away_player,
                            "p2_odds": outcomes[1].get("price"),
                            "bookmaker": book_title
                        })
    df = pd.DataFrame(rows)
    if not df.empty:
        # Deduplicate identical fixture + bookmaker lines
        df = df.drop_duplicates(subset=["event_id", "player_1", "player_2", "bookmaker"])
    return df

def parse_odds_and_find_bets(api_key: str, db_path: str = "data/tennis.db", bankroll: float = 10000.0, kelly_fraction: float = 0.25, min_ev_pct: float = 4.0):
    """
    Fetches active tennis odds across active keys, evaluates surface Elo probabilities,
    and returns deduplicated recommended actionable bets.
    """
    active_sports = fetch_active_tennis_sports(api_key)
    if not active_sports:
        active_sports = [{"key": "tennis_atp"}, {"key": "tennis_wta"}]
        
    engine = SurfaceEloEngine()
    try:
        conn = sqlite3.connect(db_path)
        query = "SELECT winner_id, winner_name, loser_id, loser_name, surface, tourney_date, tourney_id FROM matches ORDER BY tourney_date ASC;"
        df_hist = pd.read_sql(query, conn)
        conn.close()
        
        player_name_to_id = {}
        for _, r in df_hist.iterrows():
            w_id = int(r['winner_id'])
            l_id = int(r['loser_id'])
            player_name_to_id[r['winner_name'].lower()] = w_id
            player_name_to_id[r['loser_name'].lower()] = l_id
            engine.update_ratings(w_id, l_id, r['surface'], str(r['tourney_id']))
    except Exception as e:
        player_name_to_id = {}

    all_odds_rows = []
    seen_events = set()
    for s in active_sports:
        data = fetch_live_tennis_odds(api_key, s['key'])
        if data:
            df_p = parse_odds_to_dataframe(data)
            if not df_p.empty:
                all_odds_rows.append(df_p)
                
    if not all_odds_rows:
        return None, None
        
    df_raw = pd.concat(all_odds_rows, ignore_index=True)
    
    bets = []
    all_evals = []
    seen_recommendations = set()
    
    for _, row in df_raw.iterrows():
        p1 = row['player_1']
        p2 = row['player_2']
        p1_odds = row['p1_odds']
        p2_odds = row['p2_odds']
        book = row['bookmaker']
        
        id1 = player_name_to_id.get(p1.lower(), 999001)
        id2 = player_name_to_id.get(p2.lower(), 999002)
        
        elo1 = engine.get_blended_elo(id1, "Hard")
        elo2 = engine.get_blended_elo(id2, "Hard")
        prob1 = engine.calculate_win_probability(elo1, elo2)
        prob2 = 1.0 - prob1
        
        size1 = size_position(prob1, p1_odds, bankroll, kelly_fraction=kelly_fraction, min_ev_pct=min_ev_pct)
        size2 = size_position(prob2, p2_odds, bankroll, kelly_fraction=kelly_fraction, min_ev_pct=min_ev_pct)
        
        eval_item1 = {
            "Match": f"{p1} vs {p2}",
            "Bet Target": p1,
            "Bookmaker": book,
            "Offered Odds": p1_odds,
            "Model Win Prob": round(prob1, 3),
            "EV %": size1.get("ev_pct", calculate_ev(prob1, p1_odds)),
            "Action": size1["action"],
            "Stake ($)": size1.get("stake_dollars", 0.0),
            "Stake %": size1.get("stake_pct", 0.0)
        }
        eval_item2 = {
            "Match": f"{p1} vs {p2}",
            "Bet Target": p2,
            "Bookmaker": book,
            "Offered Odds": p2_odds,
            "Model Win Prob": round(prob2, 3),
            "EV %": size2.get("ev_pct", calculate_ev(prob2, p2_odds)),
            "Action": size2["action"],
            "Stake ($)": size2.get("stake_dollars", 0.0),
            "Stake %": size2.get("stake_pct", 0.5)
        }
        
        all_evals.extend([eval_item1, eval_item2])
        
        if size1["action"] == "BET":
            key1 = (eval_item1["Match"], eval_item1["Bet Target"], eval_item1["Bookmaker"])
            if key1 not in seen_recommendations:
                seen_recommendations.add(key1)
                bets.append(eval_item1)
                
        if size2["action"] == "BET":
            key2 = (eval_item2["Match"], eval_item2["Bet Target"], eval_item2["Bookmaker"])
            if key2 not in seen_recommendations:
                seen_recommendations.add(key2)
                bets.append(eval_item2)
            
    df_bets = pd.DataFrame(bets)
    df_all = pd.DataFrame(all_evals).drop_duplicates(subset=["Match", "Bet Target", "Bookmaker"])
    
    return df_bets, df_all
