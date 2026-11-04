"""
Streamlit command-center dashboard for CourtQuant.
"""

import os
import sqlite3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from src.market import american_to_decimal, calculate_ev
from src.odds_client import fetch_live_tennis_odds, parse_odds_and_find_bets

load_dotenv()
env_api_key = os.getenv("ODDS_API_KEY", "")

st.set_page_config(page_title="CourtQuant Terminal", layout="wide")
st.title("🎾 CourtQuant: Quantitative Tennis Terminal & Execution Engine")

st.sidebar.header("Configuration & API Setup")
api_key_input = st.sidebar.text_input("The Odds API Key", type="password", value=env_api_key)
bankroll_input = st.sidebar.number_input("Active Bankroll ($)", value=10000.0, step=500.0)
kelly_frac_input = st.sidebar.slider("Kelly Fraction", min_value=0.1, max_value=1.0, value=0.25, step=0.05)
min_ev_input = st.sidebar.slider("Min EV Hurdle (%)", min_value=1.0, max_value=10.0, value=4.0, step=0.5)

tab_bets, tab_tracker, tab_parlays, tab_live, tab_backtest, tab_clv = st.tabs([
    "📝 Live Trade Logger & Ledger",
    "🎲 Multi-Leg Parlay Combinations",
    "🎯 Recommended Actionable Bets", 
    "📊 Live Line Shopping", 
    "📈 Backtest & Trajectory", 
    "⚖️ CLV & Performance"
])

with tab_bets:
    st.subheader("Today's Actionable Value Wagers")
    st.markdown("Scans active ATP/WTA markets, matches players to surface-adjusted Elo model probabilities, and calculates optimal Kelly stakes.")
    
    if st.button("Scan Active Markets & Generate Bet Recommendations"):
        if not api_key_input:
            st.error("Please enter a valid Odds API key in the sidebar or .env file.")
        else:
            with st.spinner("Fetching active tennis markets & running model evaluation..."):
                df_bets, df_all = parse_odds_and_find_bets(
                    api_key=api_key_input,
                    db_path="data/tennis.db",
                    bankroll=bankroll_input,
                    kelly_fraction=kelly_frac_input,
                    min_ev_pct=min_ev_input
                )
                
                if df_bets is not None and not df_bets.empty:
                    st.success(f"Found {len(df_bets)} actionable value bet(s) matching your +{min_ev_input}% EV hurdle!")
                    
                    # Highlight cards for top bets
                    for _, row in df_bets.iterrows():
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Wager Target", row['Bet Target'])
                        col2.metric("Offered Odds", f"{row['Offered Odds']:+d}")
                        col3.metric("Model Edge (EV)", f"+{row['EV %']}%")
                        col4.metric("Recommended Stake", f"${row['Stake ($)']:,.2f} ({row['Stake %']}%)")
                        st.write(f"**Match:** {row['Match']} | **Bookmaker:** {row['Bookmaker']} | **Model Win Prob:** {row['Model Win Prob']*100:.1f}%")
                        st.divider()
                        
                    st.dataframe(df_bets, width='stretch')
                elif df_all is not None and not df_all.empty:
                    st.info("Live market data loaded, but no wagers currently exceed your minimum EV hurdle.")
                    st.dataframe(df_all, width='stretch')
                else:
                    st.warning("No active market lines returned for tennis events right now. Check active tournament schedules.")





with tab_tracker:
    st.subheader("Live Trade Logger & Performance Tracking")
    st.markdown("Record real-money wagers taken across US DFS and Exchange markets to evaluate model execution, hit rates, net P&L, and Closing Line Value (CLV).")
    
    from src.tracker import log_placed_bet, get_placed_bets, update_bet_result
    
    # Form to manually log a bet
    with st.expander("➕ Log New Wager Manually", expanded=False):
        with st.form("manual_bet_form"):
            col1, col2 = st.columns(2)
            m_match = col1.text_input("Match / Event", "Jannik Sinner vs Carlos Alcaraz")
            m_target = col2.text_input("Bet Selection / Target", "Jannik Sinner")
            
            col3, col4, col5 = st.columns(3)
            m_book = col3.selectbox("Platform / Bookmaker", ["Kalshi", "Polymarket", "PrizePicks", "Underdog Fantasy", "Novig", "DraftKings Pick6", "Dabble", "ProphetX"])
            m_odds = col4.number_input("American Odds", value=-110, step=5)
            m_stake = col5.number_input("Stake ($)", value=100.0, step=10.0)
            
            col6, col7 = st.columns(2)
            m_prob = col6.number_input("Model Prob (%)", value=55.0, step=1.0) / 100.0
            m_ev = col7.number_input("Model EV (%)", value=5.0, step=0.5)
            
            submit_bet = st.form_submit_button("Record Wager to Database")
            if submit_bet:
                log_placed_bet(m_match, m_target, m_book, int(m_odds), float(m_stake), float(m_prob), float(m_ev))
                st.success(f"Successfully recorded ${m_stake:.2f} wager on {m_target}!")

    # Display logged bets table & summary stats
    df_placed = get_placed_bets()
    if df_placed is not None and not df_placed.empty:
        total_staked = df_placed['stake_dollars'].sum()
        total_pnl = df_placed['pnl'].sum()
        wins = len(df_placed[df_placed['status'] == 'WON'])
        losses = len(df_placed[df_placed['status'] == 'LOST'])
        pending = len(df_placed[df_placed['status'] == 'PENDING'])
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Bets Logged", len(df_placed))
        m2.metric("Total Volume Staked", f"${total_staked:,.2f}")
        m3.metric("Net Realized P&L", f"${total_pnl:,.2f}")
        m4.metric("Record (W-L-P)", f"{wins}-{losses}-{pending}")
        
        st.subheader("Active & Past Wagers")
        st.dataframe(df_placed, width='stretch')
        
        # Settlement controls
        st.subheader("Update Wager Settlement")
        bet_to_update = st.selectbox("Select Bet ID to Settle", df_placed['bet_id'].tolist())
        col_status, col_close, col_btn = st.columns(3)
        new_status = col_status.selectbox("Outcome", ["WON", "LOST", "PUSH"])
        close_odds = col_close.number_input("Market Closing Odds", value=-110, step=5)
        if col_btn.button("Settle Wager"):
            update_bet_result(bet_to_update, new_status, closing_odds=close_odds)
            st.success(f"Updated Bet ID #{bet_to_update} status to {new_status}!")
            st.rerun()
    else:
        st.info("No active bets logged yet. Use the form above or click 'Record Wager' on recommended bets!")


with tab_parlays:
    st.subheader("Multi-Leg Parlay & DFS Slip Combinations")
    st.markdown("Combines positive EV individual wager legs into 2-leg and 3-leg parlays across US DFS platforms and Exchanges (`us_dfs,us_ex`), compounding edge while avoiding correlated matches.")
    
    if st.button("Generate Optimal Parlay Suggestions"):
        if not api_key_input:
            st.error("Please enter a valid Odds API key in the sidebar or .env file.")
        else:
            with st.spinner("Scanning active markets and compiling optimal parlay legs..."):
                df_bets, _ = parse_odds_and_find_bets(
                    api_key=api_key_input,
                    db_path="data/tennis.db",
                    bankroll=bankroll_input,
                    kelly_fraction=kelly_frac_input,
                    min_ev_pct=min_ev_input
                )
                
                if df_bets is not None and not df_bets.empty:
                    from src.parlay import generate_parlay_suggestions
                    parlays_list = generate_parlay_suggestions(df_bets)
                    
                    if parlays_list:
                        st.success(f"Generated {len(parlays_list)} optimal parlay combinations!")
                        for p in parlays_list:
                            c1, c2, c3 = st.columns(3)
                            c1.metric(p['Parlay Type'] if 'Parlay Type' in p else f"{p['Leg Count']}-Leg Parlay", f"{p['Combined Odds']:+d}")
                            c2.metric("Combined Win Prob", f"{p['Combined Win Prob (%)']}%")
                            c3.metric("Combined EV %", f"+{p['Combined EV (%)']}%")
                            st.write(f"**Legs:** {p['Legs Description']}")
                            st.divider()
                        st.dataframe(pd.DataFrame(parlays_list), width='stretch')
                    else:
                        st.info("Not enough independent positive EV legs found right now to construct high-probability parlays.")
                else:
                    st.warning("No individual positive EV wagers found to build parlays from.")


with tab_live:
    st.subheader("Raw Live Odds Comparison")
    if st.button("Fetch Raw Market Lines"):
        if not api_key_input:
            st.error("Please enter a valid Odds API key in the sidebar or .env file.")
        else:
            from src.odds_client import fetch_active_tennis_sports, parse_odds_to_dataframe
            active_sports = fetch_active_tennis_sports(api_key_input)
            if active_sports:
                all_rows = []
                for s in active_sports:
                    raw = fetch_live_tennis_odds(api_key_input, s['key'])
                    if raw:
                        df_parsed = parse_odds_to_dataframe(raw)
                        if not df_parsed.empty:
                            all_rows.append(df_parsed)
                if all_rows:
                    df_full_odds = pd.concat(all_rows, ignore_index=True)
                    st.success(f"Loaded {len(df_full_odds)} market lines across {len(active_sports)} active tennis tour endpoints.")
                    st.dataframe(df_full_odds, width='stretch')
                else:
                    st.warning("No match lines found in active tournament keys.")
            else:
                st.error("Could not fetch active tennis sport keys from The Odds API.")

with tab_backtest:
    st.subheader("Historical Simulation & Bankroll Trajectory (Updated through 2026)")
    db_path = "data/tennis.db"
    try:
        conn = sqlite3.connect(db_path)
        df_matches = pd.read_sql("SELECT COUNT(*) as cnt, MAX(tourney_date) as max_date FROM matches;", conn)
        conn.close()
        st.metric("Matches Stored in SQLite", f"{df_matches['cnt'].iloc[0]:,}", help=f"Latest match date: {df_matches['max_date'].iloc[0]}")
    except Exception:
        st.info("Database not initialized yet. Run `python3 main.py --mode ingest --end-year 2026`.")

    if st.button("Run Full Historical Backtest Simulation"):
        from src.backtest import run_historical_backtest
        with st.spinner("Executing end-to-end historical model backtest..."):
            df_bt = run_historical_backtest(initial_bankroll=bankroll_input)
            if not df_bt.empty:
                st.line_chart(df_bt.set_index(pd.to_datetime(df_bt['date']))['bankroll'])
                st.dataframe(df_bt.tail(25), width='stretch')

with tab_clv:
    st.subheader("Closing Line Value (CLV) Performance Log")
    st.markdown("Compares locked-in wager prices against de-vigged market closing prices.")
    sample_clv_data = [
        {"Date": "2026-10-25", "Match": "Jannik Sinner vs Carlos Alcaraz", "Bet Odds": -120, "Close Odds A": -140, "Close Odds B": +120, "No-Vig CLV%": "+2.45%"},
        {"Date": "2026-10-26", "Match": "Novak Djokovic vs Taylor Fritz", "Bet Odds": +135, "Close Odds A": +120, "Close Odds B": -145, "No-Vig CLV%": "+3.10%"}
    ]
    st.dataframe(pd.DataFrame(sample_clv_data), width='stretch')
