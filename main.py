"""
Main orchestration entry point for CourtQuant.
"""

import argparse
from src.ingest import initialize_database, fetch_and_store_season
from src.backtest import run_historical_backtest

def main():
    parser = argparse.ArgumentParser(description="CourtQuant Engine")
    parser.add_argument("--mode", type=str, choices=["ingest", "backtest", "all"], default="all")
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2026)

    args = parser.parse_args()

    if args.mode in ["ingest", "all"]:
        print("=== Step 1: Initializing Database & Ingesting Data (through 2026) ===")
        initialize_database()
        failed_years = []
        for yr in range(args.start_year, args.end_year + 1):
            try:
                fetch_and_store_season(yr)
            except Exception as exc:
                failed_years.append(yr)
                print(f"ERROR: Could not ingest {yr}: {exc}")

        if failed_years:
            print(f"\nIngestion completed with failures for: {failed_years}")
        else:
            print("\nIngestion completed successfully for all requested years.")

    if args.mode in ["backtest", "all"]:
        print("\n=== Step 2: Running Historical Backtest ===")
        df_results = run_historical_backtest()
        if not df_results.empty:
            print("\nLatest 5 Trades:")
            print(df_results.tail(5).to_string(index=False))

if __name__ == "__main__":
    main()
