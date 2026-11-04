import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.ingest import initialize_database, upsert_matches_dataframe


def sample_match(tourney_id="2024-TEST", match_num=1, winner="Player A", tourney_date=20240501):
    return {
        "tourney_id": tourney_id,
        "tourney_name": "Test Open",
        "surface": "Clay",
        "tourney_date": tourney_date,
        "match_num": match_num,
        "winner_id": 1001,
        "winner_name": winner,
        "loser_id": 1002,
        "loser_name": "Player B",
        "score": "6-4 6-4",
    }


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initialize_creates_match_id_primary_key(self):
        initialize_database(self.db_path)
        with closing(sqlite3.connect(self.db_path)) as conn:
            info = conn.execute("PRAGMA table_info(matches)").fetchall()
        primary_keys = [row[1] for row in info if row[5] == 1]
        self.assertEqual(primary_keys, ["match_id"])

    def test_legacy_table_migration_preserves_rows_and_adds_primary_key(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE matches (
                    match_id TEXT, tourney_id TEXT, tourney_name TEXT,
                    surface TEXT, tourney_date INTEGER, match_num INTEGER,
                    winner_id INTEGER, winner_name TEXT, loser_id INTEGER,
                    loser_name TEXT, score TEXT
                )
            """)
            row = sample_match()
            conn.execute("""
                INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"{row['tourney_id']}_{row['match_num']}",
                row["tourney_id"], row["tourney_name"], row["surface"],
                row["tourney_date"], row["match_num"], row["winner_id"],
                row["winner_name"], row["loser_id"], row["loser_name"],
                row["score"]
            ))
            conn.commit()

        initialize_database(self.db_path)
        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            info = conn.execute("PRAGMA table_info(matches)").fetchall()
        self.assertEqual(count, 1)
        self.assertEqual([row[1] for row in info if row[5] == 1], ["match_id"])

    def test_upsert_is_idempotent_and_preserves_other_seasons(self):
        initialize_database(self.db_path)
        df = pd.DataFrame([
            sample_match("2024-TEST", 1, "Player A", 20240501),
            sample_match("2025-TEST", 2, "Player C", 20250501),
        ])
        self.assertEqual(upsert_matches_dataframe(df, self.db_path), 2)
        self.assertEqual(upsert_matches_dataframe(df, self.db_path), 2)

        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            seasons = conn.execute(
                "SELECT COUNT(DISTINCT substr(CAST(tourney_date AS TEXT), 1, 4)) "
                "FROM matches"
            ).fetchone()[0]
        self.assertEqual(count, 2)
        self.assertEqual(seasons, 2)

        # A corrected source row updates the existing match instead of duplicating it.
        updated = pd.DataFrame([sample_match("2024-TEST", 1, "Updated Winner")])
        upsert_matches_dataframe(updated, self.db_path)
        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            winner = conn.execute(
                "SELECT winner_name FROM matches WHERE match_id='2024-TEST_1'"
            ).fetchone()[0]
        self.assertEqual(count, 2)
        self.assertEqual(winner, "Updated Winner")

    def test_missing_match_identity_is_rejected(self):
        initialize_database(self.db_path)
        row = sample_match()
        row["tourney_id"] = None
        with self.assertRaises(ValueError):
            upsert_matches_dataframe(pd.DataFrame([row]), self.db_path)


if __name__ == "__main__":
    unittest.main()
