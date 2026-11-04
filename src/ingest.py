"""
Historical match ingestion for CourtQuant.

Season ingestion is additive and idempotent:
- Existing seasons are preserved.
- Re-ingesting a season updates matching records by match_id.
- The matches table keeps a primary-key constraint on match_id.
"""

import os
import sqlite3
from contextlib import closing
from typing import Optional

import pandas as pd

CSV_URL_TEMPLATE = (
    "https://huggingface.co/datasets/jmatarese/atp-data/raw/main/"
    "atp/atp_matches_{year}.csv"
)

MATCH_COLUMNS = [
    "match_id",
    "tourney_id",
    "tourney_name",
    "surface",
    "tourney_date",
    "match_num",
    "winner_id",
    "winner_name",
    "loser_id",
    "loser_name",
    "score",
]

CREATE_MATCHES_SQL = """
    CREATE TABLE IF NOT EXISTS matches (
        match_id TEXT PRIMARY KEY NOT NULL,
        tourney_id TEXT,
        tourney_name TEXT,
        surface TEXT,
        tourney_date INTEGER,
        match_num INTEGER,
        winner_id INTEGER,
        winner_name TEXT,
        loser_id INTEGER,
        loser_name TEXT,
        score TEXT
    )
"""

UPSERT_SQL = """
    INSERT INTO matches (
        match_id, tourney_id, tourney_name, surface, tourney_date,
        match_num, winner_id, winner_name, loser_id, loser_name, score
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(match_id) DO UPDATE SET
        tourney_id = excluded.tourney_id,
        tourney_name = excluded.tourney_name,
        surface = excluded.surface,
        tourney_date = excluded.tourney_date,
        match_num = excluded.match_num,
        winner_id = excluded.winner_id,
        winner_name = excluded.winner_name,
        loser_id = excluded.loser_id,
        loser_name = excluded.loser_name,
        score = excluded.score
"""


def _ensure_parent_directory(db_path: str) -> None:
    parent = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(parent, exist_ok=True)


def _table_columns(conn: sqlite3.Connection, table_name: str) -> list:
    return [
        row[1]
        for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    ]


def _has_match_id_primary_key(conn: sqlite3.Connection) -> bool:
    info = conn.execute('PRAGMA table_info("matches")').fetchall()
    return any(row[1] == "match_id" and row[5] == 1 for row in info)


def _migrate_matches_table(conn: sqlite3.Connection) -> None:
    """
    Rebuild legacy matches tables that lost their primary key (for example,
    after a pandas to_sql(..., if_exists="replace") operation).
    Existing rows are preserved; duplicate match IDs are collapsed.
    """
    existing_columns = _table_columns(conn, "matches")
    if not existing_columns:
        conn.execute(CREATE_MATCHES_SQL)
        return

    missing = [column for column in MATCH_COLUMNS if column not in existing_columns]
    if missing:
        raise RuntimeError(
            "Cannot safely migrate matches table; missing columns: "
            + ", ".join(missing)
        )

    if _has_match_id_primary_key(conn):
        return

    null_ids = conn.execute(
        """
        SELECT COUNT(*) FROM matches
        WHERE match_id IS NULL OR TRIM(CAST(match_id AS TEXT)) = ''
        """
    ).fetchone()[0]
    if null_ids:
        raise RuntimeError(
            f"Cannot safely migrate matches table: {null_ids} rows have empty match_id."
        )

    conn.execute("ALTER TABLE matches RENAME TO matches_legacy_backup")
    conn.execute(CREATE_MATCHES_SQL)

    # INSERT OR IGNORE safely collapses duplicate IDs if a legacy table contains any.
    columns_sql = ", ".join(f'"{column}"' for column in MATCH_COLUMNS)
    conn.execute(
        f"""
        INSERT OR IGNORE INTO matches ({columns_sql})
        SELECT {columns_sql}
        FROM matches_legacy_backup
        ORDER BY rowid
        """
    )
    conn.execute("DROP TABLE matches_legacy_backup")


def initialize_database(db_path: str = "data/tennis.db") -> None:
    """Create the database or safely restore the matches primary-key constraint."""
    _ensure_parent_directory(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            if not _table_columns(conn, "matches"):
                conn.execute(CREATE_MATCHES_SQL)
            else:
                _migrate_matches_table(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _clean_match_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the source data into the canonical match columns."""
    required = [
        "tourney_id", "tourney_name", "surface", "tourney_date", "match_num",
        "winner_id", "winner_name", "loser_id", "loser_name", "score",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError("Source data is missing columns: " + ", ".join(missing))

    clean = df[required].copy()
    if clean["tourney_id"].isna().any() or clean["match_num"].isna().any():
        raise ValueError("Cannot construct match_id when tourney_id or match_num is missing.")

    clean["tourney_id"] = clean["tourney_id"].astype(str)
    clean["match_num"] = pd.to_numeric(clean["match_num"], errors="raise").astype(int)
    clean.insert(
        0,
        "match_id",
        clean["tourney_id"] + "_" + clean["match_num"].astype(str),
    )

    # Convert pandas/NumPy missing values and scalars into SQLite-compatible values.
    def sqlite_value(value):
        if pd.isna(value):
            return None
        if hasattr(value, "item"):
            return value.item()
        return value

    for column in MATCH_COLUMNS:
        clean[column] = clean[column].map(sqlite_value)

    return clean[MATCH_COLUMNS]


def upsert_matches_dataframe(df: pd.DataFrame, db_path: str = "data/tennis.db") -> int:
    """
    Upsert match records by match_id.

    Returns the number of source rows processed. Repeated IDs update existing
    records rather than creating duplicates.
    """
    clean = _clean_match_dataframe(df)
    initialize_database(db_path)

    rows = list(clean.itertuples(index=False, name=None))
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(UPSERT_SQL, rows)
        conn.commit()

    return len(rows)


def fetch_and_store_season(year: int, db_path: str = "data/tennis.db") -> int:
    """
    Fetch one ATP season and upsert its matches without replacing other seasons.

    Returns the number of source rows processed. Raises errors so the caller can
    detect a failed season rather than silently treating it as successful.
    """
    url = CSV_URL_TEMPLATE.format(year=year)
    df = pd.read_csv(url)
    processed = upsert_matches_dataframe(df, db_path)
    print(f"Successfully processed {processed} matches for {year}.")
    return processed
