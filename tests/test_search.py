"""Search regressions using a copied app and a fresh SQLite file per test.

Run: .venv/bin/python -B -m unittest discover -s tests -p test_search.py -v
Flask's test client exercises the route without opening a listening socket.
"""
import importlib.util
import json
import logging
import secrets
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FOCUS = "com.sciencia.focus"
TRAVEL = "com.sciencia.travel"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Flask locates templates/static files through the registered module path.
    with patch.dict(sys.modules, {name: module}):
        spec.loader.exec_module(module)
    return module


class SearchRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="sciencia-search-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.runtime = Path(cls.temporary.name)
        shutil.copytree(ROOT / "app", cls.runtime / "app",
                        ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        cls.provider = json.loads((ROOT / "data/provider_reviews.json").read_text())
        existing_handlers = set(logging.getLogger().handlers)

        def close_test_handlers():
            for handler in set(logging.getLogger().handlers) - existing_handlers:
                logging.getLogger().removeHandler(handler)
                handler.close()

        cls.addClassCleanup(close_test_handlers)
        config = load_module("config", cls.runtime / "app/config.py")
        config.VIEWER_TOKEN = secrets.token_urlsafe(32)
        config.OPERATOR_TOKEN = secrets.token_urlsafe(32)
        cls.viewer_token = config.VIEWER_TOKEN
        cls.db = load_module("db", cls.runtime / "app/db.py")
        # Imports resolve to the copied modules, not the project's runtime paths.
        with patch.dict(sys.modules, {"config": config, "db": cls.db}):
            cls.module = load_module("search_regression_app", cls.runtime / "app/app.py")
        cls.module.app.config["TESTING"] = True

    def setUp(self):
        self.db.DB_PATH = str(self.runtime / "data" / (self._testMethodName + ".db"))
        self.db.init_db()
        self.client = self.module.app.test_client()
        self.expected = []
        with self.db.connect() as conn:
            for app_id, reviews in self.provider.items():
                conn.execute("INSERT INTO apps VALUES (?, ?)", (app_id, app_id))
                for review in reviews:
                    row = dict(review, app_id=app_id)
                    self.insert_review(conn, row)
                    self.expected.append(row)

    @staticmethod
    def insert_review(conn, row):
        columns = ("review_id", "app_id", "rating", "text", "created_at",
                   "app_version", "user_region")
        conn.execute("INSERT INTO reviews (" + ", ".join(columns) +
                     ") VALUES (?, ?, ?, ?, ?, ?, ?)", [row[c] for c in columns])

    def assert_reviews(self, params, expected):
        response = self.client.get("/reviews", query_string=params,
                                   headers={"Authorization": "Bearer " + self.viewer_token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        actual = response.get_json()
        expected = sorted(expected, key=lambda row: row["created_at"], reverse=True)[:200]
        # Full row comparison verifies IDs, apps, fields, values, and ordering.
        self.assertEqual(actual, expected)
        self.assertEqual([(r["review_id"], r["app_id"]) for r in actual],
                         [(r["review_id"], r["app_id"]) for r in expected])

    def test_no_filters(self):
        self.assert_reviews({}, self.expected)

    def test_real_application(self):
        self.assert_reviews({"app_id": FOCUS}, [r for r in self.expected if r["app_id"] == FOCUS])

    def test_nonexistent_application(self):
        self.assert_reviews({"app_id": "com.sciencia.missing"}, [])

    def test_matching_keyword(self):
        rows = [r for r in self.expected if r["review_id"] in {"focus-001", "travel-003"}]
        self.assert_reviews({"q": "useful"}, rows)

    def test_nonmatching_keyword(self):
        self.assert_reviews({"q": "unfindableword"}, [])

    def test_combined_match(self):
        self.assert_reviews({"app_id": FOCUS, "q": "useful"},
                            [r for r in self.expected if r["review_id"] == "focus-001"])

    def test_combined_keyword_only_matches_another_application(self):
        self.assert_reviews({"app_id": TRAVEL, "q": "summaries"}, [])
        self.assert_reviews({"q": "summaries"},
                            [r for r in self.expected if r["review_id"] == "focus-001"])

    def test_ordinary_apostrophes_in_application_and_text(self):
        quoted_app = "com.sciencia.reader's"
        row = {"review_id": "quote-001", "app_id": quoted_app, "rating": 4,
               "text": "A reader's view is useful.", "created_at": "2026-10-01T00:00:00Z",
               "app_version": "test", "user_region": "US"}
        with self.db.connect() as conn:
            conn.execute("INSERT INTO apps VALUES (?, ?)", (quoted_app, "Synthetic quote example"))
            self.insert_review(conn, row)
        self.assert_reviews({"q": "reader's"}, [row])
        self.assert_reviews({"app_id": quoted_app, "q": "reader's"}, [row])

    def test_existing_like_wildcards(self):
        self.assert_reviews({"q": "%"}, self.expected)
        self.assert_reviews({"q": "u_eful"},
                            [r for r in self.expected if r["review_id"] in {"focus-001", "travel-003"}])

    def test_recorded_app_id_injection_returns_no_rows(self):
        self.assert_reviews({"app_id": "com.sciencia.missing' OR '1'='1"}, [])
        self.assert_reviews({}, self.expected)

    def test_recorded_keyword_injection_preserves_application_filter(self):
        self.assert_reviews({"app_id": FOCUS, "q": "unfindableword%' OR 1=1 -- "}, [])
        self.assert_reviews({"app_id": FOCUS},
                            [r for r in self.expected if r["app_id"] == FOCUS])

    def test_descending_order_and_limit_200(self):
        extra = [{"review_id": f"limit-{i:03d}", "app_id": FOCUS, "rating": 3,
                  "text": "Synthetic pagination example", "app_version": "test", "user_region": "US",
                  "created_at": (datetime(2026, 10, 1) + timedelta(minutes=i)).isoformat() + "Z"}
                 for i in range(201)]
        with self.db.connect() as conn:
            for row in extra:
                self.insert_review(conn, row)
        self.assert_reviews({}, self.expected + extra)


if __name__ == "__main__":
    unittest.main()
