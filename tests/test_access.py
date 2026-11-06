"""Role boundaries on copied applications and synthetic SQLite data only."""
import csv
import io
import logging
import unittest
from unittest.mock import patch

import test_export
from test_export import no_credentials, verify_database


class AccessControlTests(unittest.TestCase):
    # Reuse only the isolated setup, not the export test methods.
    setUp = test_export.ExportCredentialTests.setUp
    protected = [("GET", "/"), ("GET", "/reviews"),
                 ("GET", "/analysis/summary"), ("GET", "/admin/runs"),
                 ("GET", "/export.csv"), ("POST", "/ingest"), ("GET", "/export.db")]
    history_fields = {"run_id", "app_id", "started_at", "fetched_count", "inserted_count", "status"}

    def headers(self, role):
        return {"Authorization": "Bearer " + self.tokens[role]}

    def counts(self):
        with self.db.connect() as conn:
            return tuple(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                         for table in ("reviews", "ingestion_runs"))

    def test_all_protected_routes_reject_invalid_identity_without_writes(self):
        for credential in (None, "", "Bearer ", "Bearer", "Basic invalid",
                           "Bearer " + self.tokens["wrong"], "Bearer  invalid"):
            for method, path in self.protected:
                with self.subTest(method=method, path=path, credential_kind="missing-or-invalid"):
                    response = self.client.open(path, method=method,
                        headers={} if credential is None else {"Authorization": credential},
                        data={"app_id": "com.sciencia.focus"})
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json(), {"error": "authentication required"})
                    self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
                    no_credentials(self, response.get_data(as_text=True), self.tokens)
        self.assertEqual(self.counts(), (9, 3))

    def test_both_roles_read_same_data_and_csv(self):
        expected_ids = {r["review_id"] for rows in self.fixture.values() for r in rows}
        for role in ("viewer", "valid"):
            headers = self.headers(role)
            response = self.client.get("/reviews", headers=headers)
            self.assertEqual({r["review_id"] for r in response.get_json()}, expected_ids)
            self.assertEqual({r["app_id"] for r in response.get_json()}, set(self.fixture))
            summary = self.client.get("/analysis/summary", headers=headers).get_json()
            self.assertEqual(summary["review_count"], 9)
            response = self.client.get("/export.csv", headers=headers)
            self.assertEqual(response.status_code, 200)
            rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
            self.assertEqual({r["review_id"] for r in rows}, expected_ids)
            self.assertEqual(len(rows), 9)
            home = self.client.get("/", headers=headers)
            self.assertEqual(home.status_code, 200)
            self.assertEqual(b'action="/ingest"' in home.data, role == "valid")
            no_credentials(self, home.get_data(as_text=True), self.tokens)

    def test_viewer_history_allowlist_and_operator_safe_history(self):
        # A sensitive-looking free-text message must not be forwarded to either role.
        with self.db.connect() as conn:
            conn.execute("UPDATE ingestion_runs SET message = ?", (self.tokens["wrong"],))
        for role in ("viewer", "valid"):
            response = self.client.get("/admin/runs", headers=self.headers(role))
            rows = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(rows), 3)
            self.assertEqual([r["run_id"] for r in rows], [3, 2, 1])
            for row in rows:
                self.assertEqual(set(row), self.history_fields)
                self.assertEqual((row["fetched_count"], row["inserted_count"], row["status"]), (3, 3, "SUCCESS"))
            no_credentials(self, response.get_data(as_text=True), self.tokens)

    def test_viewer_denials_do_not_write_and_operator_import_works(self):
        for path, method in (("/ingest", "POST"), ("/export.db", "GET")):
            response = self.client.open(path, method=method, headers=self.headers("viewer"),
                                        data={"app_id": "com.sciencia.focus"})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json(), {"error": "forbidden"})
        self.assertEqual(self.counts(), (9, 3))
        # Reset only the test database to demonstrate an actual insertion.
        with self.db.connect() as conn:
            conn.execute("DELETE FROM ingestion_runs")
            conn.execute("DELETE FROM reviews")
            conn.execute("DELETE FROM apps")
        response = self.client.post("/ingest", headers=self.headers("valid"),
                                    data={"app_id": "com.sciencia.focus"})
        self.assertEqual(response.get_json(), {"app_id": "com.sciencia.focus", "fetched": 3, "inserted": 3})
        self.assertEqual(self.counts(), (3, 1))
        rows = self.client.get("/reviews", headers=self.headers("viewer")).get_json()
        self.assertEqual({r["review_id"] for r in rows}, {r["review_id"] for r in self.fixture["com.sciencia.focus"]})

    def test_operator_download_is_valid_sqlite(self):
        with self.client.get("/export.db", headers=self.headers("valid")) as response:
            self.assertEqual(response.status_code, 200)
            verify_database(self, response.data, self.runtime / "role-download.db", self.fixture)

    def test_role_claims_and_legacy_credentials_cannot_elevate(self):
        self.module.app.config["INTERNAL_EXPORT_TOKEN"] = self.tokens["legacy"]
        for role, expected in ((None, 401), ("viewer", 403)):
            headers = {"X-Role": "Operator", "Role": "Operator"}
            if role:
                headers.update(self.headers(role))
            for path, method in (("/ingest", "POST"), ("/export.db", "GET")):
                response = self.client.open(path, method=method, headers=headers,
                    query_string={"role": "Operator", "token": self.tokens["valid"]},
                    data={"role": "Operator", "app_id": "com.sciencia.focus"})
                self.assertEqual(response.status_code, expected)
        for key in ("legacy", "viewer"):
            response = self.client.get("/export.db", headers=self.headers(key),
                                       query_string={"token": self.tokens["valid"]})
            self.assertEqual(response.status_code, 401 if key == "legacy" else 403)
        self.assertEqual(self.counts(), (9, 3))

    def test_head_and_options_follow_method_rules_without_writes(self):
        for method, path in self.protected:
            if method == "GET":
                for role in (None, "viewer", "valid"):
                    response = self.client.head(path, headers={} if role is None else self.headers(role))
                    expected = 401 if role is None else 403 if role == "viewer" and path == "/export.db" else 200
                    self.assertEqual(response.status_code, expected)
                    self.assertEqual(response.data, b"")
                    response.close()
            response = self.client.options(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"")
            self.assertIn(method, response.headers["Allow"])
        self.assertEqual(self.counts(), (9, 3))

    def test_public_exceptions_are_narrow(self):
        response = self.client.get("/health")
        self.assertEqual(set(response.get_json()), {"status", "time"})
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertTrue(response.get_json()["time"].endswith("+00:00"))
        response = self.client.get("/static/style.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"font", response.data)
        response.close()
        (self.runtime / "app/static/not-public.txt").write_text("synthetic private content")
        for path in ("/static/not-public.txt", "/static/../config.py"):
            for role in (None, "viewer", "valid"):
                response = self.client.get(path, headers={} if role is None else self.headers(role))
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(b"synthetic private content", response.data)

    def test_missing_empty_duplicate_or_malformed_configuration_fails_closed(self):
        for viewer, operator in ((None, self.tokens["valid"]), ("", self.tokens["valid"]),
                                 (self.tokens["viewer"], ""),
                                 (self.tokens["valid"], self.tokens["valid"]),
                                 ("white space", self.tokens["valid"])):
            with patch.dict(self.module.app.config, VIEWER_TOKEN=viewer, OPERATOR_TOKEN=operator):
                for role in ("viewer", "valid"):
                    response = self.client.get("/reviews", headers=self.headers(role))
                    self.assertEqual(response.status_code, 401)
                self.assertEqual(self.client.get("/health").status_code, 200)

    def test_raw_application_logs_cover_roles_and_denials_without_secrets(self):
        for role in ("viewer", "valid", "wrong"):
            for method, path in self.protected:
                response = self.client.open(path, method=method, headers=self.headers(role),
                    query_string={"token": self.tokens["legacy"]}, data={"app_id": "com.sciencia.focus"})
                expected = 401 if role == "wrong" else 403 if role == "viewer" and path in ("/ingest", "/export.db") else 200
                self.assertEqual(response.status_code, expected)
                response.close()
        for handler in logging.getLogger().handlers:
            handler.flush()
        raw = self.raw_log.read_text()
        no_credentials(self, raw, self.tokens)
        self.assertIn("path=/reviews status=200", raw)
        self.assertIn("path=/ingest status=403", raw)
        self.assertIn("path=/export.db status=401", raw)


if __name__ == "__main__":
    unittest.main()
