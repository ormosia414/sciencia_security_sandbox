import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "reviews.db")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS apps (
                app_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                rating INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                app_version TEXT,
                user_region TEXT,
                ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (app_id) REFERENCES apps(app_id)
            );

            CREATE TABLE IF NOT EXISTS ingestion_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fetched_count INTEGER NOT NULL,
                inserted_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                FOREIGN KEY (app_id) REFERENCES apps(app_id)
            );
            """
        )
