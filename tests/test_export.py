"""Export regressions on private copies; no original runtime data is opened.

Use unittest discovery with -k ExportCredentialTests for in-process checks, or
-k LiveExportLogTests for the real loopback server and raw-log checks.
Test credentials are random, never assertion messages or published fixtures.
"""
import importlib.util
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote, quote_plus, urlencode
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]


def copied_runtime(test):
    directory = tempfile.TemporaryDirectory(prefix="sciencia-export-tests-")
    test.addCleanup(directory.cleanup)
    runtime = Path(directory.name)
    shutil.copytree(ROOT / "app", runtime / "app",
                    ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    (runtime / "data").mkdir()
    shutil.copy2(ROOT / "data/provider_reviews.json", runtime / "data/provider_reviews.json")
    return runtime


def test_tokens():
    return {name: secrets.token_urlsafe(24) + "/+="
            for name in ("valid", "viewer", "wrong", "legacy", "malformed")}


def credential_cases(tokens):
    valid = tokens["valid"]
    return [
        ("valid-header", "Bearer " + valid, {}, 200),
        ("lowercase-scheme", "bearer " + valid, {}, 200),
        ("viewer-denied", "Bearer " + tokens["viewer"], {}, 403),
        ("missing-header", None, {}, 401),
        ("empty-header", "", {}, 401),
        ("empty-bearer", "Bearer ", {}, 401),
        ("scheme-without-value", "Bearer", {}, 401),
        ("wrong-value", "Bearer " + tokens["wrong"], {}, 401),
        ("wrong-scheme", "Basic " + tokens["malformed"], {}, 401),
        ("extra-space", "Bearer  " + valid, {}, 401),
        ("tab-separator", "Bearer\t" + valid, {}, 401),
        ("extra-field", "Bearer " + valid + " extra", {}, 401),
        ("non-ascii-value", "Bearer \u00e9", {}, 401),
        ("legacy-only", None, {"token": valid}, 401),
        ("legacy-with-wrong-header", "Bearer " + tokens["wrong"], {"token": valid}, 401),
        ("legacy-with-empty-header", "Bearer ", {"token": valid}, 401),
        ("valid-header-ignores-legacy", "Bearer " + valid, {"token": tokens["legacy"]}, 200),
    ]


def no_credentials(test, text, tokens):
    variants = {encoded for value in tokens.values()
                for encoded in (value, quote(value, safe=""), quote(value), quote_plus(value))}
    test.assertTrue(all(value not in text for value in variants),
                    "A raw log or response contains a test credential")


def verify_database(test, body, destination, fixture):
    test.assertTrue(body.startswith(b"SQLite format 3\0"), "Expected SQLite attachment")
    destination.write_bytes(body)
    with sqlite3.connect(destination.as_uri() + "?mode=ro", uri=True) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        test.assertEqual(tables, ["apps", "ingestion_runs", "reviews"])
        test.assertEqual({t: conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in tables},
                         {"apps": 3, "ingestion_runs": 3, "reviews": 9})
        test.assertEqual(conn.execute("SELECT review_id, app_id FROM reviews ORDER BY review_id").fetchall(),
                         sorted((r["review_id"], app) for app, rows in fixture.items() for r in rows))
        test.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Flask locates templates/static files through the registered module path.
    with patch.dict(sys.modules, {name: module}):
        spec.loader.exec_module(module)
    return module


class ExportCredentialTests(unittest.TestCase):
    def setUp(self):
        self.runtime = copied_runtime(self)
        self.tokens = test_tokens()
        root_logger = logging.getLogger()
        handlers, level = set(root_logger.handlers), root_logger.level

        def close_test_handlers():
            for handler in set(root_logger.handlers) - handlers:
                root_logger.removeHandler(handler)
                handler.close()
            root_logger.setLevel(level)

        self.addCleanup(close_test_handlers)
        config = load_module("config", self.runtime / "app/config.py")
        config.OPERATOR_TOKEN = self.tokens["valid"]
        config.VIEWER_TOKEN = self.tokens["viewer"]
        self.db = load_module("db", self.runtime / "app/db.py")
        with patch.dict(sys.modules, {"config": config, "db": self.db}):
            self.module = load_module("export_regression_app", self.runtime / "app/app.py")
        self.module.app.config["TESTING"] = True
        self.raw_log = self.runtime / "unit-application.log"
        root_logger.addHandler(logging.FileHandler(self.raw_log))
        root_logger.setLevel(logging.INFO)
        self.db.init_db()
        self.fixture = json.loads((self.runtime / "data/provider_reviews.json").read_text())
        self.client = self.module.app.test_client()
        for app_id in self.fixture:
            response = self.client.post("/ingest", data={"app_id": app_id},
                                        headers={"Authorization": "Bearer " + self.tokens["valid"]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["inserted"], 3)

    def test_valid_attachment_and_ignored_legacy_query(self):
        for label, header, params, status in credential_cases(self.tokens):
            if status != 200:
                continue
            with self.subTest(case=label):
                with self.client.get("/export.db", query_string=params,
                                     headers={"Authorization": header}) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("attachment", response.headers.get("Content-Disposition", ""))
                    verify_database(self, response.data, self.runtime / (label + ".db"), self.fixture)

    def test_rejections_are_generic_and_do_not_use_legacy_query(self):
        for label, header, params, status in credential_cases(self.tokens):
            if status == 200:
                continue
            with self.subTest(case=label):
                headers = {} if header is None else {"Authorization": header}
                with self.client.get("/export.db", query_string=params, headers=headers) as response:
                    self.assertEqual(response.status_code, status)
                    self.assertTrue(response.get_json() == {"error": "forbidden" if status == 403 else "authentication required"},
                                    "Rejection must use the generic error body")
                    no_credentials(self, response.get_data(as_text=True) + str(response.headers), self.tokens)

    def test_raw_application_log_keeps_metadata_without_credentials(self):
        for label, header, params, status in credential_cases(self.tokens):
            headers = {} if header is None else {"Authorization": header}
            with self.client.get("/export.db", query_string=params, headers=headers) as response:
                self.assertEqual(response.status_code, status, msg=label)
        for handler in logging.getLogger().handlers:
            handler.flush()
        raw = self.raw_log.read_text()
        no_credentials(self, raw, self.tokens)
        lines = [line for line in raw.splitlines() if "request method=GET path=/export.db status=" in line]
        self.assertEqual(len(lines), len(credential_cases(self.tokens)))
        self.assertTrue(any("status=200" in line for line in lines))
        self.assertTrue(any("status=401" in line for line in lines))


class LiveExportLogTests(unittest.TestCase):
    def test_real_server_raw_logs_and_export_controls(self):
        runtime = copied_runtime(self)
        tokens = test_tokens()
        fixture = json.loads((runtime / "data/provider_reviews.json").read_text())
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
        except PermissionError:
            self.skipTest("Loopback listening is restricted; live server log verification was not executed")
        # Private test-only config, read before importing the copied application.
        (runtime / "test-credential.json").write_text(json.dumps({"token": tokens["valid"], "viewer": tokens["viewer"]}))
        launcher = runtime / "launch_export_test.py"
        launcher.write_text(
            "import sys,json,logging\nfrom pathlib import Path\n"
            "sys.path.insert(0,str(Path(__file__).parent/'app'))\n"
            "import config\n"
            "config.OPERATOR_TOKEN=json.loads(Path('test-credential.json').read_text())['token']\nconfig.VIEWER_TOKEN=json.loads(Path('test-credential.json').read_text())['viewer']\n"
            "import app\n"
            "logging.getLogger('werkzeug').addHandler(logging.FileHandler('logs/server-access.raw.log'))\n"
            "app.run_local_server(int(sys.argv[1]),use_reloader=False)\n")
        capture = (runtime / "console.raw.log").open("w")
        process = subprocess.Popen([sys.executable, str(launcher), str(port)], cwd=runtime,
            stdout=capture, stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1"))

        def stop_owned_server():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            capture.close()

        self.addCleanup(stop_owned_server)
        base = "http://127.0.0.1:" + str(port)
        opener = build_opener(ProxyHandler({}))
        for attempt in range(100):
            if process.poll() is not None:
                self.fail("Owned server exited before readiness; raw private console not printed")
            try:
                with opener.open(base + "/health", timeout=1) as response:
                    if json.load(response)["status"] == "ok":
                        break
            except OSError:
                time.sleep(0.05)
        else:
            self.fail("Owned loopback server did not become ready")
        for app_id in fixture:
            with opener.open(Request(base + "/ingest", data=urlencode({"app_id": app_id}).encode(),
                                            headers={"Authorization": "Bearer " + tokens["valid"]}), timeout=5) as response:
                self.assertEqual(json.load(response)["inserted"], 3)
        # Exercise role credentials in actual server logs, not only export headers.
        for role_key in ("viewer", "valid", "wrong"):
            for path in ("/reviews", "/analysis/summary", "/admin/runs", "/export.csv"):
                try:
                    response = opener.open(Request(base + path,
                        headers={"Authorization": "Bearer " + tokens[role_key]}), timeout=5)
                except HTTPError as error:
                    response = error
                with response:
                    self.assertEqual(response.code, 401 if role_key == "wrong" else 200)
                    no_credentials(self, response.read().decode(), tokens)
        for role_key, expected in (("viewer", 403), ("wrong", 401)):
            req = Request(base + "/ingest?" + urlencode({"token": tokens["legacy"]}),
                data=urlencode({"app_id": next(iter(fixture))}).encode(),
                headers={"Authorization": "Bearer " + tokens[role_key]})
            try:
                response = opener.open(req, timeout=5)
            except HTTPError as error:
                response = error
            with response:
                self.assertEqual(response.code, expected)
                no_credentials(self, response.read().decode(), tokens)
        expected_statuses = []
        for label, header, params, expected_status in credential_cases(tokens):
            with self.subTest(case=label):
                headers = {} if header is None else {"Authorization": header}
                url = base + "/export.db" + (("?" + urlencode(params)) if params else "")
                req = Request(url, headers=headers)
                try:
                    response = opener.open(req, timeout=5)
                except HTTPError as error:
                    response = error
                with response:
                    body = response.read()
                    self.assertEqual(response.code, expected_status)
                    no_credentials(self, str(response.headers), tokens)
                    if expected_status == 200:
                        verify_database(self, body, runtime / (label + ".db"), fixture)
                    else:
                        self.assertTrue(json.loads(body) == {"error": "forbidden" if expected_status == 403 else "authentication required"},
                                        "Rejection must remain generic")
                        no_credentials(self, body.decode(), tokens)
                expected_statuses.append(expected_status)
        stop_owned_server()
        self.assertIsNotNone(process.poll(), "Owned test server must be stopped")
        app_raw = (runtime / "logs/app.log").read_text()
        server_raw = (runtime / "logs/server-access.raw.log").read_text()
        console_raw = (runtime / "console.raw.log").read_text()
        for raw in (app_raw, server_raw, console_raw):
            no_credentials(self, raw, tokens)
        app_lines = [line for line in app_raw.splitlines() if "request method=GET path=/export.db status=" in line]
        access_lines = [line for line in server_raw.splitlines() if '"GET /export.db HTTP/1.1"' in line]
        self.assertEqual(len(app_lines), len(expected_statuses), "Application log must contain every export")
        self.assertEqual(len(access_lines), len(expected_statuses), "Werkzeug log must contain every export")
        self.assertEqual([int(line.rsplit("status=", 1)[1]) for line in app_lines], expected_statuses)
        self.assertEqual([int(line.split('HTTP/1.1" ', 1)[1].split()[0]) for line in access_lines], expected_statuses)
        self.assertTrue(all("?" not in line for line in access_lines), "Access log must omit query strings")
        for path in ("/reviews", "/analysis/summary", "/admin/runs", "/export.csv"):
            lines = [line for line in server_raw.splitlines() if '"GET ' + path + ' HTTP/1.1"' in line]
            self.assertEqual([int(line.split('HTTP/1.1" ', 1)[1].split()[0]) for line in lines],
                             [200, 200, 401], "Both roles and invalid credentials must have real access records")


class HttpParseErrorLogTests(unittest.TestCase):
    def test_parse_error_keeps_status_without_raw_request(self):
        runtime = copied_runtime(self)
        marker = secrets.token_urlsafe(24) + "/+="
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
        except PermissionError:
            self.skipTest("Loopback listening is restricted; parser error log check was not executed")
        (runtime / "test-credential.json").write_text(json.dumps({"token": marker, "viewer": secrets.token_urlsafe(32)}))
        launcher = runtime / "launch_parser_test.py"
        launcher.write_text(
            "import sys,json,logging\nfrom pathlib import Path\n"
            "sys.path.insert(0,str(Path(__file__).parent/'app'))\n"
            "import config\n"
            "config.OPERATOR_TOKEN=json.loads(Path('test-credential.json').read_text())['token']\nconfig.VIEWER_TOKEN=json.loads(Path('test-credential.json').read_text())['viewer']\n"
            "import app\n"
            "logging.getLogger('werkzeug').addHandler(logging.FileHandler('logs/server-access.raw.log'))\n"
            "app.run_local_server(int(sys.argv[1]),use_reloader=False)\n")
        capture = (runtime / "console.raw.log").open("w")
        process = subprocess.Popen([sys.executable, str(launcher), str(port)], cwd=runtime,
            stdout=capture, stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1"))

        def stop_owned_server():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            capture.close()

        self.addCleanup(stop_owned_server)
        opener = build_opener(ProxyHandler({}))
        for attempt in range(100):
            if process.poll() is not None:
                self.fail("Owned parser-test server exited; private console not printed")
            try:
                with opener.open("http://127.0.0.1:" + str(port) + "/health", timeout=1) as response:
                    if json.load(response)["status"] == "ok":
                        break
            except OSError:
                time.sleep(0.05)
        else:
            self.fail("Owned parser-test server did not become ready")

        # One fixed four-word request line exercises stdlib's bad-syntax branch.
        # The random value and its encoded form must never appear in test output.
        encoded = quote_plus(marker)
        request_line = "GET /export.db?token=" + encoded + " extra HTTP/1.1"
        received = bytearray()
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            connection.sendall((request_line + "\r\n\r\n").encode("ascii"))
            connection.shutdown(socket.SHUT_WR)
            while True:
                try:
                    part = connection.recv(4096)
                except ConnectionResetError:
                    break
                if not part:
                    break
                received.extend(part)
        status_line = bytes(received).split(b"\r\n", 1)[0]
        self.assertEqual(status_line.split()[1:2], [b"400"],
                         "Protocol parsing must reject the request with 400, not an application authentication response")
        stop_owned_server()
        self.assertIsNotNone(process.poll(), "Owned parser-test server must be stopped")
        server_raw = (runtime / "logs/server-access.raw.log").read_text()
        app_raw = (runtime / "logs/app.log").read_text()
        console_raw = (runtime / "console.raw.log").read_text()
        self.assertIn("code 400, message", server_raw, "A protocol error record must exist")
        self.assertNotIn("request method=GET path=/export.db", app_raw,
                         "Malformed request must be rejected before Flask route processing")
        for raw in (server_raw, console_raw, app_raw):
            no_credentials(self, raw, {"parser_marker": marker})
            self.assertTrue(request_line not in raw, "The untrusted request line must not be logged")
        self.assertIn("code 400, message Bad Request", server_raw,
                      "Retain the status and standard non-sensitive error category")


if __name__ == "__main__":
    unittest.main()
