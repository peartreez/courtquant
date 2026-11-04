# CourtQuant

Quantitative tennis betting engine and Streamlit command center.

This repository is the flattened v2 working tree. Local version folders (`court-quant-v1.x`) are kept off GitHub.

## Overview

CourtQuant ingests ATP match history into SQLite, maintains a surface-adjusted Elo model, sizes bets with a fractional Kelly rule, and shops live h2h lines from The Odds API (`us_dfs` and `us_ex` regions).

## Quick start

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env
# put your Odds API key in .env

python3 main.py --mode ingest --start-year 2023 --end-year 2026
python3 -m streamlit run dashboard.py
python3 -m unittest tests/test_ingest.py
```

The SQLite database is created at `data/tennis.db` and is gitignored.

## Layout

- `main.py` — ingest and backtest CLI
- `dashboard.py` — Streamlit terminal
- `src/` — ingest, Elo, market math, odds client, execution, tracker, parlays, CLV
- `tests/` — ingest safety tests
