# CourtQuant 2.0 — Phase 1 Progress

## Step 1: Protect the database and make ingestion non-destructive

**Status: Implemented and tested — 2026-11-03**

### Safety and baseline
- Extracted the uploaded v1.5.0 archive into a separate working directory.
- Preserved the original uploaded ZIP.
- Created a separate pre-change SQLite backup and verified it against the source using SHA-256.
- Created an additional pre-migration database snapshot before changing the working database.
- Baseline database contained 1,449 matches and one placed-bet record.
- Baseline `matches` table had no primary-key constraint on `match_id`.
- Baseline match history covered January 4, 2026 through May 25, 2026 only.

### Changes
- Replaced destructive `pandas.to_sql(..., if_exists="replace")` ingestion with parameterized SQLite upserts.
- `match_id` is now the primary key and is used for idempotent updates.
- Added a safe migration for legacy `matches` tables that lack the primary key.
- Existing records are preserved during migration.
- Added validation for missing tournament IDs and match numbers.
- Made season-ingestion errors visible to the CLI.
- Ensured SQLite connections are explicitly closed.
- Added `tests/test_ingest.py`.

### Validation
- Four ingestion tests pass:
  1. New database gets a `match_id` primary key.
  2. Legacy table migration preserves rows and restores the primary key.
  3. Re-ingestion is idempotent and records from separate seasons coexist.
  4. Missing match identity is rejected.
- The working database retains all 1,449 original match records.
- `match_id` is the primary key.
- No duplicate match IDs.
- SQLite `PRAGMA integrity_check` returns `ok`.
- Temporary test fixtures were removed from the working database.

### Remaining Phase 1 work
- Canonical player identity resolution and aliases.
- Tournament/event-to-surface mapping.
- Live odds outcome-name matching and parser validation.
- Additional API timeout, rate-limit, and error handling.
- Broader tests for player matching and surface assignment.

### Important data limitation
The uploaded database already contained only 2026 matches. The ingestion fix prevents future overwrites but cannot restore seasons that were previously removed. Re-ingest the desired historical years after confirming the data source and match schema.
