# CourtQuant 2.0 — Project Roadmap & Technical Handoff

**Status:** Planning / pre-implementation  
**Current version audited:** CourtQuant v1.5.0  
**Project type:** Personal tennis analytics and betting research application  
**Primary environment:** Local Mac, Python, SQLite  
**Recommended direction:** Retain the existing Python engine, fix data and modeling integrity, then migrate the interface to NiceGUI + Plotly.

---

## 1. Project Objective

Evolve CourtQuant from its current working prototype into a reliable, locally operated tennis analytics and betting research application.

The priority is not to rewrite everything or introduce unnecessary infrastructure. It is to establish a trustworthy foundation for:

- Maintaining accurate historical match and player data.
- Generating pre-match predictions using the correct surface ratings.
- Comparing model probabilities against real market prices.
- Backtesting strategies without look-ahead bias or fabricated results.
- Recording recommendations and market prices over time.
- Tracking actual betting performance and closing-line value (CLV).
- Generating and evaluating multi-match parlays.
- Presenting everything through a polished, interactive research dashboard.

**Core principle:** Data integrity and model validity come before interface improvements.

CourtQuant is intended for personal use. It does not need a multi-user SaaS architecture, cloud deployment, authentication system, or distributed infrastructure at this stage.

---

## 2. Current Architecture

The existing application has a reasonably modular Python foundation.

| Component | Current responsibility |
|---|---|
| `main.py` | CLI entry point and execution modes |
| `dashboard.py` | Streamlit dashboard |
| `src/ingest.py` | Historical match ingestion |
| `src/model.py` | Elo rating engine |
| `src/market.py` | Market probability and pricing calculations |
| `src/execution.py` | Bet sizing and execution logic |
| `src/odds_client.py` | Live odds retrieval and model evaluation |
| `src/parlay.py` | Multi-match parlay generation |
| `src/tracker.py` | Bet ledger and settlement tracking |
| `src/clv.py` | Closing-line value calculations |
| `src/backtest.py` | Historical strategy backtesting |

**Current data store:** SQLite (`data/tennis.db`)

The existing Python modules should be retained where practical. The first task is to correct their behavior and establish clean boundaries between data, modeling, betting logic, and presentation.

---

## 3. Critical Problems Identified in the v1.5.0 Audit

These are the issues that should be addressed before relying on CourtQuant's recommendations or performance statistics.

### P0 — Historical ingestion overwrites previous seasons

**File:** `src/ingest.py`

Current implementation:

```python
df_clean.to_sql(
    'matches',
    conn,
    if_exists='replace',
    index=False
)
```

This replaces the entire `matches` table each time a season is ingested.

The main execution flow loops through multiple years, meaning earlier seasons are overwritten by later ones.

**Verified database state in the uploaded archive:**
- 1,449 matches.
- Dates: January 4, 2026 through May 25, 2026.
- Only 2026 records remained.

**Required fix:**
- Replace destructive table replacement with append/upsert logic.
- Establish a stable unique match identifier.
- Preserve the primary-key constraint.
- Prevent duplicate matches when a season is re-ingested.
- Allow incremental ingestion without deleting existing data.

**Acceptance criteria:**
- Ingesting 2023–2026 preserves all available seasons.
- Re-running ingestion does not duplicate records.
- Existing match history remains intact.

### P0 — Historical backtest does not represent real betting performance

**File:** `src/backtest.py`

The current backtest has several fundamental problems:

1. It evaluates the known winner rather than evaluating both possible sides before the match.
2. It generates synthetic market probabilities using random noise.
3. It fabricates odds rather than using historical market prices.
4. It only credits profit when a qualifying bet is placed on the eventual winner.
5. It does not properly account for losing bets.

The result is not a valid historical betting ROI or strategy-performance estimate.

**Important distinction:** The existing implementation can demonstrate that the modeling pipeline executes, but its profitability metrics should not be interpreted as evidence of a betting edge.

**Required fix:**
- Rebuild the backtest around chronological pre-match predictions.
- Calculate probabilities for both players.
- Use historical odds wherever reliable data is available.
- Evaluate both sides against the market.
- Apply the actual betting rules and stake-sizing logic.
- Record wins, losses, pushes, and unavailable prices correctly.
- Deduct losing stakes and calculate actual net P&L.
- Include bookmaker margin and market pricing considerations.
- Clearly distinguish real historical odds from any synthetic test data.

**Acceptance criteria:**
- Every wager is generated using information available before the match.
- Both sides are evaluated.
- Losing bets are included.
- ROI, yield, drawdown, and bankroll calculations reflect actual outcomes.
- Synthetic data cannot accidentally be presented as historical betting performance.

### P0 — Live odds evaluation assumes every match is on Hard

**File:** `src/odds_client.py`

Current implementation:

```python
elo1 = engine.get_blended_elo(id1, "Hard")
elo2 = engine.get_blended_elo(id2, "Hard")
```

Every live fixture is evaluated using Hard court ratings, regardless of the tournament's actual surface.

**Required fix:**
- Associate tournaments/events with their playing surface.
- Support Hard, Clay, and Grass.
- Pass the correct surface into the model.
- If the surface cannot be identified, flag the event rather than silently assuming Hard.

**Acceptance criteria:**
- Every recommendation displays its surface.
- The correct surface rating is used.
- Unknown surfaces are explicitly flagged and excluded from actionable recommendations unless deliberately configured otherwise.

### P0 — Unmatched players silently receive fallback IDs

**File:** `src/odds_client.py`

Current implementation:

```python
id1 = player_name_to_id.get(p1.lower(), 999001)
id2 = player_name_to_id.get(p2.lower(), 999002)
```

Unrecognized players receive artificial IDs and can be assigned baseline ratings, potentially producing misleading probabilities.

**Required fix:**
- Normalize player names.
- Implement alias and name-matching logic.
- Resolve players against a canonical player database.
- Flag unresolved identities.
- Do not generate actionable betting recommendations for unresolved players.

**Acceptance criteria:**
- Player identity is traceable to a canonical record.
- Unmatched players are clearly identified.
- No artificial fallback rating can silently produce an actionable bet.

### P1 — Dashboard tabs do not match their labels

**File:** `dashboard.py`

The first three tab labels and their assigned content are mismatched.

Current labels:

1. Live Trade Logger & Ledger
2. Multi-Leg Parlay Combinations
3. Recommended Actionable Bets
4. Live Line Shopping
5. Backtest
6. CLV

The first three content assignments are in a different order.

**Required fix:**
- Match tab assignments to their labels.
- Review navigation and content organization during the interface migration.

### P1 — No reliable historical prediction and odds snapshots

The supplied implementation does not establish a complete persisted record of what the model knew when it generated a recommendation.

This is essential for reproducibility.

**Required fix:**

Create persistent records for:

- Prediction timestamp.
- Event and match identifiers.
- Player identifiers.
- Surface.
- Model probabilities for both players.
- Rating inputs.
- Model version and configuration.
- Bookmaker and available odds.
- Market-implied probabilities.
- Calculated EV.
- Recommendation status.

Recommended tables:

| Table | Purpose |
|---|---|
| `predictions` | Historical model predictions |
| `odds_snapshots` | Timestamped market prices |
| `model_versions` | Model versions and configurations |
| `player_ratings` | Optional historical rating snapshots |
| `matches` | Canonical historical match results |
| `placed_bets` | Actual wager ledger |

The goal is to reconstruct exactly what CourtQuant knew at a particular point in time.

### P1 — CLV is not yet connected to actual betting data

**Files:** `src/clv.py`, `src/tracker.py`, `dashboard.py`

The dashboard currently displays hardcoded sample CLV records.

The tracker stores a single closing-odds field, which is insufficient for robust two-sided market comparison.

**Required fix:**
- Store both sides' closing prices.
- Capture bookmaker and timestamp.
- Calculate CLV against the actual closing market.
- Distinguish raw odds movement from margin-adjusted probability movement.
- Connect dashboard statistics to persisted records rather than sample data.

### P1 — Odds parser assumes outcome array order

**File:** `src/odds_client.py`

The parser assumes `outcomes[0]` and `outcomes[1]` correspond to the correct players.

**Required fix:**
- Match outcome names to the event's player names.
- Validate that both sides are present.
- Handle missing or malformed markets.
- Add request timeouts, error handling, and rate-limit handling.

### P2 — Additional model and portfolio improvements

These are worthwhile but should follow the foundational fixes.

**Parlay independence**

The current generator excludes two selections from the same match, but multiplies probabilities across different matches as though they are independent.

Different matches can still share player, tournament, or model-related dependencies.

Future improvements:
- Display an independence assumption warning.
- Introduce exposure limits.
- Track shared player and tournament exposure.
- Investigate empirical joint-probability estimation.

**Model configuration and validation**
- Review Elo K-factors and surface weighting.
- Evaluate probability calibration.
- Measure performance by surface, tour, odds range, and player segment.
- Preserve historical model versions.
- Avoid tuning parameters against the same data used to report performance.

**Execution validation**
- Validate probability, odds, stake, and bankroll inputs.
- Apply consistent maximum exposure limits.
- Ensure fractional Kelly calculations handle edge cases safely.

---

## 4. Recommended Technology Architecture

### Recommended stack

| Layer | Technology | Responsibility |
|---|---|---|
| Application logic | Python | Model, predictions, betting logic |
| Database | SQLite | Local persistent data |
| Interface | NiceGUI | Interactive local application |
| Visualization | Plotly | Charts and analytical graphics |
| Data processing | Pandas / NumPy | Historical analysis |
| Scheduling | APScheduler, later | Automated data refreshes |
| Testing | Pytest | Unit and integration tests |

### Why NiceGUI + Plotly?

The project is Python-centric and intended for one user operating locally.

NiceGUI provides:
- More interface flexibility than Streamlit.
- A Python-first development workflow.
- Interactive tables, controls, and layouts.
- A path toward a polished application without requiring a separate React frontend.

Plotly provides:
- Interactive charts.
- Bankroll and equity curves.
- Historical performance analysis.
- Surface and player comparisons.
- Market-versus-model visualizations.

### Architecture principles

1. Keep the modeling engine independent of the interface.
2. Separate database access from model calculations.
3. Make predictions reproducible.
4. Store historical snapshots rather than overwriting important information.
5. Keep the application runnable locally.
6. Avoid unnecessary infrastructure.

**Not recommended at this stage:**
- Redis or Celery.
- Cloud hosting.
- PostgreSQL migration solely for this project.
- Docker-based deployment.
- Multi-user authentication.
- A complete React/FastAPI/Tauri rewrite.

The existing Streamlit dashboard should remain available until the replacement interface is functional.

---

## 5. Implementation Roadmap

Work should proceed in the following order.

### Phase 1 — Data integrity and foundational fixes

**Version target: 2.0.1**

Priority: Critical.

Tasks:
- [ ] Fix destructive historical ingestion.
- [ ] Implement match upserts and duplicate prevention.
- [ ] Restore reliable database constraints.
- [ ] Verify historical seasons and match counts.
- [ ] Build canonical player identity resolution.
- [ ] Remove silent fallback player IDs.
- [ ] Implement tournament-to-surface mapping.
- [ ] Correct live odds outcome parsing.
- [ ] Add API error handling and validation.
- [ ] Add tests for ingestion, matching, and surface assignment.

**Deliverable:** A reliable historical database and correctly identified live fixtures.

### Phase 2 — Rebuild the backtesting engine

**Version target: 2.0.2**

Priority: Critical.

Tasks:
- [ ] Separate pre-match prediction from post-match rating updates.
- [ ] Generate probabilities for both players.
- [ ] Integrate historical odds data where available.
- [ ] Calculate EV for both sides.
- [ ] Apply the configured EV threshold.
- [ ] Apply fractional Kelly and bankroll limits.
- [ ] Record wins and losses.
- [ ] Calculate net P&L, ROI, yield, drawdown, and bankroll.
- [ ] Support chronological walk-forward evaluation.
- [ ] Add data-availability and sample-size reporting.
- [ ] Clearly label any backtest that uses synthetic prices.

**Deliverable:** A defensible historical evaluation framework.

### Phase 3 — Prediction and market-data persistence

**Version target: 2.0.3**

Priority: High.

Tasks:
- [ ] Design prediction schema.
- [ ] Design odds-snapshot schema.
- [ ] Store both sides' market prices.
- [ ] Store model inputs and configuration.
- [ ] Record model version.
- [ ] Persist recommendation timestamps.
- [ ] Connect predictions to actual match results.
- [ ] Store closing prices for CLV.
- [ ] Add database migrations instead of destructive schema replacement.

**Deliverable:** A reproducible historical record of every recommendation and its market context.

### Phase 4 — Refactor the Python engine into reusable services

**Version target: 2.0.4**

Priority: High.

Separate application responsibilities into clear service boundaries:

- Data ingestion service.
- Player identity service.
- Rating/model service.
- Market pricing service.
- Prediction service.
- Betting and execution service.
- Backtesting service.
- Bet tracking and settlement service.
- CLV service.
- Parlay service.

The dashboard should call these services rather than contain important model or betting logic itself.

**Deliverable:** A clean application backend that can support different interfaces without rewriting the model.

### Phase 5 — Build the new research interface

**Version target: 2.1.0**

Priority: Medium, after the backend is reliable.

Recommended dashboard sections:

1. **Overview**
   - Current bankroll and exposure.
   - Active bets.
   - Today's actionable opportunities.
   - Recent model performance.

2. **Live Betting**
   - Upcoming matches.
   - Player and surface information.
   - Model probabilities.
   - Market odds and implied probabilities.
   - EV and recommended stake.
   - Bookmaker comparison.

3. **Parlay Research**
   - Eligible legs.
   - Combined odds.
   - Estimated joint probability.
   - Combined EV.
   - Exposure and correlation warnings.

4. **Bet Tracker**
   - Open and settled wagers.
   - Historical P&L.
   - Performance by bookmaker and bet type.
   - Bankroll and equity curves.

5. **Backtesting**
   - Historical strategy performance.
   - Surface breakdown.
   - Odds-range breakdown.
   - Drawdowns.
   - Calibration and sample sizes.

6. **CLV Analysis**
   - Opening versus closing prices.
   - CLV by bookmaker.
   - CLV by surface.
   - CLV versus realized outcomes.

7. **Player Research**
   - Overall Elo.
   - Surface Elo.
   - Rating history.
   - Recent form and match history.

**Deliverable:** A polished, interactive local CourtQuant research application.

### Phase 6 — Automation and packaging

**Version target: 2.2.0**

Priority: Later.

Tasks:
- [ ] Add scheduled odds refreshes.
- [ ] Add scheduled match-data ingestion.
- [ ] Add stale-data indicators.
- [ ] Add automated database backups.
- [ ] Add configurable refresh intervals.
- [ ] Evaluate local Mac application packaging.
- [ ] Consider PyInstaller or a native PySide6 wrapper if a standalone desktop experience becomes important.

**Deliverable:** A dependable local application that can run with minimal manual maintenance.

---

## 6. Core Modeling Rules to Preserve

The existing model philosophy should remain relatively simple until the underlying data and evaluation are trustworthy.

Current design principles:

- Overall Elo ratings.
- Independent surface Elo ratings for Hard, Clay, and Grass.
- Configurable surface weighting (currently 0.6).
- Logistic probability conversion.
- Chronological rating updates.
- EV hurdle (currently +4%).
- Fractional Kelly sizing (currently 0.25x).
- Parlay legs must individually qualify as positive EV.
- Same-match parlay legs are excluded.
- Current parlay EV threshold is +2%.

These values are existing configuration defaults, not proven optimal parameters. They should remain configurable and be evaluated through proper out-of-sample testing.

**Important:** Do not introduce complicated machine learning before establishing a reliable benchmark using the Elo model.

---

## 7. Development and Testing Standards

Every foundational change should have tests.

Minimum test coverage:

| Area | Required test |
|---|---|
| Ingestion | Re-ingestion does not delete or duplicate matches |
| Database | Unique IDs and constraints remain intact |
| Player matching | Aliases resolve to the correct canonical player |
| Unknown players | Unresolved identities cannot produce actionable bets |
| Surface mapping | Hard, Clay, and Grass use the correct ratings |
| Elo | Ratings update only after the relevant match |
| Probabilities | Both players' probabilities are complementary |
| EV | Correct calculations for both sides |
| Kelly | Stake respects bankroll and exposure limits |
| Backtest | Losing bets reduce bankroll correctly |
| Backtest | No future information enters pre-match predictions |
| Odds | Outcome names map to the correct players |
| CLV | Both sides' prices are recorded and compared |
| Parlay | Same-match exclusions and exposure rules work |

Maintain a clear distinction between:
- Historical source data.
- Model-generated predictions.
- Market observations.
- Actual placed wagers.
- Settled outcomes.

---

## 8. Immediate Next Steps

The first development session should focus exclusively on Phase 1.

Suggested sequence:

1. Extract the current v1.5.0 project into a clean working directory.
2. Make a backup of the existing SQLite database.
3. Inspect the current database schema.
4. Fix ingestion so it preserves historical seasons.
5. Test ingestion against multiple years.
6. Implement player identity resolution.
7. Implement surface mapping.
8. Add tests for these changes.
9. Verify the database before moving to backtesting.

Do not start the dashboard migration yet. The existing interface can remain in use while the backend is corrected.

---

## 9. Project Handoff / Resume Instructions

When returning to this project, use this document as the source of truth for the roadmap.

**Current agreed direction:**
- Keep the existing Python model and modules where practical.
- Fix data integrity before UI development.
- Rebuild the backtest before relying on profitability metrics.
- Add prediction and odds snapshots for reproducibility.
- Move from Streamlit to NiceGUI + Plotly after the backend is reliable.
- Keep the application local and single-user.
- Avoid unnecessary infrastructure and a full rewrite.

**Next task:** Begin Phase 1 — inspect the current project and implement non-destructive historical ingestion.

Before making changes:
- Confirm the current project files and database are available.
- Reinspect the relevant source code rather than assuming it has not changed.
- Preserve a backup of the existing database.
- Implement changes incrementally.
- Run tests after each meaningful change.
- Update this roadmap when milestones are completed or architecture decisions change.

### Suggested prompt for a future session

> We are continuing the CourtQuant 2.0 project. Use the attached CourtQuant Project Roadmap and Technical Handoff as our agreed plan. We previously audited v1.5.0 and identified critical issues with destructive historical ingestion, invalid backtesting, hardcoded Hard-court ratings, player identity fallbacks, and missing prediction/odds snapshots. We agreed to retain the Python engine, fix data integrity first, rebuild the backtesting framework, and eventually migrate the interface to NiceGUI + Plotly. Let's resume with the next incomplete task in the roadmap. Inspect the current files before making changes, preserve the existing database, and work incrementally with tests.

---

**End goal:** CourtQuant should become a reliable personal tennis research platform where historical performance, live recommendations, betting records, and market analysis are all based on traceable data and reproducible calculations.