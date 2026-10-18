"""Normal local verification only; run with the project's existing Python.

Creates private runtime files under the OS temporary directory. No application
source changes, external requests, dependency installation, or attack inputs.
Only redacted evidence is written to docs/evidence/. Raw runtime files remain
in the private temporary directory for local inspection, never in the report.
"""
import ast
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler, Request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence"
EXCLUDE = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file()
                  and not EXCLUDE.intersection(p.relative_to(ROOT).parts))


def run():
    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    evidence_dir = OUT / "runs" / run_id
    evidence_dir.mkdir(parents=True, exist_ok=False)
    original = {str(p.relative_to(ROOT)): digest(p) for p in project_files()
                if p.relative_to(ROOT).parts[0] != "docs"}
    manifest = []
    for p in project_files():
        if "evidence" in p.relative_to(ROOT).parts:
            continue
        data = p.read_bytes()
        name = str(p.relative_to(ROOT))
        status = "Read in full"
        if p.name == ".DS_Store":
            status = "Inventoried and hashed; OS metadata, not application content"
        elif p.suffix == ".db":
            status = "Read-only SQLite: all table definitions and rows inspected"
        elif p.name == "app.log":
            status = "Read in full; sensitive values removed from shared output"
        else:
            data.decode("utf-8")
        manifest.append({"file": name, "bytes": len(data), "sha256": digest(p), "review": status})

    # A review archive need not contain runtime data. Never create it in ROOT.
    original_db_path = ROOT / "data/reviews.db"
    original_db_exists = original_db_path.exists()
    original_log_exists = (ROOT / "logs/app.log").exists()
    original_db = {"status": "NOT_APPLICABLE",
                   "reason": "Not applicable: no existing runtime database.", "tables": {}}
    if original_db_exists:
        # Existing database errors remain errors; only absence is not applicable.
        with sqlite3.connect(original_db_path.as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
            definitions = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()
            tables = {}
            for name, definition in definitions:
                rows = conn.execute('SELECT * FROM "' + name.replace('"', '""') + '"').fetchall()
                tables[name] = {"definition": definition, "rows": len(rows),
                                "content_sha256": hashlib.sha256(repr(rows).encode()).hexdigest()}
        original_db = {"status": "REVIEWED", "tables": tables}

    # Parse constants as data; do not import original app modules.
    config = {}
    for node in ast.parse((ROOT / "app/config.py").read_text()).body:
        if isinstance(node, ast.Assign):
            config[node.targets[0].id] = ast.literal_eval(node.value)
    names = None
    for node in ast.parse((ROOT / "app/app.py").read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "APP_NAMES" for t in node.targets):
            names = ast.literal_eval(node.value)
    provider = json.loads((ROOT / "data/provider_reviews.json").read_text())
    all_rows = [dict(row, app_id=app_id) for app_id, rows in provider.items() for row in rows]
    checks = []
    responses = []

    def check(name, expected, actual, kind="functional_check"):
        checks.append({"check": name, "expected": expected, "actual": actual,
                       "kind": kind,
                       "status": "PASS" if actual == expected else "FAIL"})

    if original_db_exists:
        check("Existing runtime database inspection", "REVIEWED", original_db["status"], kind="preservation_check")
    else:
        checks.append({"check": "Existing runtime database inspection", "expected": None,
                       "actual": original_db["reason"], "kind": "preservation_check",
                       "status": "NOT_APPLICABLE"})
    check("Provider applications match UI mapping", sorted(names), sorted(provider))
    check("Provider review IDs are unique", len(all_rows), len({r["review_id"] for r in all_rows}))
    required = {"review_id", "rating", "text", "created_at", "app_version", "user_region"}
    check("All provider records have the six expected fields", True,
          all(set(r) == required for rows in provider.values() for r in rows))
    check("Sample field types and ratings", True, all(
        type(r["rating"]) is int and 1 <= r["rating"] <= 5 and
        all(isinstance(r[k], str) for k in required - {"rating"}) and
        datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).tzinfo is not None
        for rows in provider.values() for r in rows))

    temp = Path(tempfile.mkdtemp(prefix="sciencia-module1-"))
    for directory in ("app", "tests"):
        shutil.copytree(ROOT / directory, temp / directory, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    (temp / "data").mkdir()
    shutil.copy2(ROOT / "data/provider_reviews.json", temp / "data/provider_reviews.json")
    shutil.copy2(ROOT / "requirements.txt", temp / "requirements.txt")
    check("Copied source and configuration bytes", True, all(
        digest(p) == digest(temp / p.relative_to(ROOT))
        for p in (ROOT / "app").rglob("*") if p.is_file()
        and "__pycache__" not in p.parts and p.name != ".DS_Store"))

    launcher = temp / "launch.py"
    launcher.write_text(
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parent / 'app'))\n"
        "import app\napp.init_db()\n"
        "app.app.run(host='127.0.0.1', port=int(sys.argv[1]), "
        "debug=app.ENABLE_DEBUG, use_reloader=False)\n")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    opener = build_opener(ProxyHandler({}))
    base = "http://127.0.0.1:" + str(port)
    capture = open(temp / "server-console.log", "w")
    proc = subprocess.Popen([sys.executable, str(launcher), str(port)], cwd=temp,
                            env=env, stdout=capture, stderr=subprocess.STDOUT)

    def request(path, params=None, form=None, record=True):
        url = base + path + (("?" + urlencode(params)) if params else "")
        data = urlencode(form).encode() if form is not None else None
        with opener.open(Request(url, data=data), timeout=5) as response:
            body = response.read()
            headers = dict(response.headers)
            status = response.status
        if record:
            responses.append({"method": "POST" if form is not None else "GET", "path": path,
                              "params": {k: "[REDACTED]" if k == "token" else v for k, v in (params or {}).items()},
                              "form": form, "status": status, "bytes": len(body)})
        return body, headers

    def get_json(path, params=None, form=None):
        return json.loads(request(path, params, form)[0])

    def database():
        conn = sqlite3.connect((temp / "data/reviews.db").as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def stored_rows():
        with database() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM reviews ORDER BY rowid")]

    try:
        for attempt in range(100):
            if proc.poll() is not None:
                raise RuntimeError("Local server exited; inspect private server-console.log")
            try:
                health = json.loads(request("/health", record=False)[0])
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("Local server did not become ready")
        with database() as conn:
            initial = {t: conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
                       for t in ("apps", "reviews", "ingestion_runs")}
        check("Fresh database counts", {"apps": 0, "reviews": 0, "ingestion_runs": 0}, initial)
        page, headers = request("/")
        html = page.decode()
        check("Empty homepage forms, names, CSS link and zero counts", True,
              html.count('action="/ingest" method="post"') == 3 and
              html.count("0 stored reviews") == 3 and '/static/style.css' in html and
              all(n in html and app_id in html for app_id, n in names.items()))
        css, headers = request("/static/style.css")
        check("CSS exact bytes and MIME", True,
              css == (ROOT / "app/static/style.css").read_bytes() and headers["Content-Type"].startswith("text/css"))

        ingestion = []
        cumulative = 0
        for repeat in (False, True):
            for app_id, rows in provider.items():
                result = get_json("/ingest", form={"app_id": app_id})
                expected = {"app_id": app_id, "fetched": len(rows), "inserted": 0 if repeat else len(rows)}
                check(("Repeat" if repeat else "First") + " import " + app_id, expected, result)
                cumulative += expected["inserted"]
                with database() as conn:
                    state = {t: conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
                             for t in ("apps", "reviews", "ingestion_runs")}
                index = len(ingestion) + 1
                check("Database counts after import " + str(index),
                      {"apps": min(index, len(provider)), "reviews": cumulative, "ingestion_runs": index}, state)
                ingestion.append(dict(result, repeat=repeat, database_counts=state))

        stored = stored_rows()
        expected_by_id = {r["review_id"]: r for r in all_rows}
        check("Every stored review matches provider fields", True,
              all({k: row[k] for k in expected_by_id[row["review_id"]]} == expected_by_id[row["review_id"]]
                  and bool(row["ingested_at"]) for row in stored))
        with database() as conn:
            actual_names = dict(conn.execute("SELECT app_id, display_name FROM apps"))
        check("Stored application mapping", names, actual_names)
        html = request("/")[0].decode()
        check("Populated homepage counts", 3, html.count("3 stored reviews"))

        review_fields = {"review_id", "app_id", "rating", "text", "created_at", "app_version", "user_region"}
        queries = [("all", {}), *[(app_id, {"app_id": app_id}) for app_id in provider],
                   ("ordinary match", {"q": "useful"}),
                   ("application and keyword", {"app_id": "com.sciencia.focus", "q": "useful"}),
                   ("ordinary no match", {"q": "unfindableword"})]
        query_results = []
        for label, params in queries:
            expected = sorted((r for r in all_rows
                               if (not params.get("app_id") or r["app_id"] == params["app_id"])
                               and params.get("q", "").lower() in r["text"].lower()),
                              key=lambda r: r["created_at"], reverse=True)[:200]
            actual = get_json("/reviews", params)
            check("Query values, fields and descending dates: " + label, expected, actual)
            check("Query response field set: " + label, True, all(set(r) == review_fields for r in actual))
            query_results.append({"label": label, "params": params, "review_ids": [r["review_id"] for r in actual]})

        summaries = []
        # Independent frequency tally from the fixture, with explicit first-seen
        # tie ordering. Do not call the application's summary or Counter code.
        for app_id in [*provider, None]:
            subset = [r for r in all_rows if app_id is None or r["app_id"] == app_id]
            freq = {}
            for row in subset:
                for word in row["text"].split():
                    if len(word) > 4:
                        term = word.strip('.,!?()[]"').lower()
                        freq[term] = freq.get(term, 0) + 1
            common = [[term, count] for term, count in sorted(freq.items(), key=lambda item: -item[1])[:8]]
            expected = {"review_count": len(subset), "average_rating": round(sum(r["rating"] for r in subset) / len(subset), 2),
                        "common_terms": common}
            actual = get_json("/analysis/summary", {"app_id": app_id} if app_id else {})
            check("Independent summary: " + (app_id or "all"), expected, actual)
            summaries.append({"app_id": app_id or "all", "result": actual})

        history = get_json("/admin/runs")
        history_fields = {"run_id", "app_id", "started_at", "fetched_count", "inserted_count", "status", "message"}
        check("History count and descending IDs", list(range(6, 0, -1)), [r["run_id"] for r in history])
        check("History fields and run contents", True, all(
            set(r) == history_fields and r["app_id"] == ingestion[5-i]["app_id"] and
            r["fetched_count"] == 3 and r["inserted_count"] == ingestion[5-i]["inserted"] and
            r["status"] == "SUCCESS" and r["message"] == "mock provider ingestion completed" and
            bool(datetime.fromisoformat(r["started_at"])) for i, r in enumerate(history)))
        with database() as conn:
            history_db = [dict(r) for r in conn.execute("SELECT * FROM ingestion_runs ORDER BY run_id DESC")]
        check("History response matches all database rows", history_db, history)

        raw_csv, headers = request("/export.csv")
        csv_download = temp / "downloaded-reviews.csv"
        csv_download.write_bytes(raw_csv)
        with csv_download.open("r", encoding="utf-8", newline="") as saved_csv:
            parsed = list(csv.reader(saved_csv))
        columns = ["review_id", "app_id", "rating", "text", "created_at", "app_version", "user_region", "ingested_at"]
        check("CSV header", columns, parsed[0])
        check("CSV row count", len(all_rows), len(parsed)-1)
        expected_csv = sorted([[str(r[c]) for c in columns] for r in stored])
        check("All CSV fields and values", expected_csv, sorted(parsed[1:]))
        check("CSV download and content type", True, headers.get("Content-Disposition") == "attachment; filename=reviews.csv"
              and headers["Content-Type"].startswith("text/csv"))
        comma_rows = [r for r in stored if "," in r["text"]]
        csv_by_id = {r[0]: r for r in parsed[1:]}
        check("CSV comma text survives parser", True, len(comma_rows) > 0 and all(csv_by_id[r["review_id"]][3] == r["text"] for r in comma_rows))

        db_bytes, headers = request("/export.db", {"token": config["INTERNAL_EXPORT_TOKEN"]})
        download = temp / "downloaded-reviews.db"
        download.write_bytes(db_bytes)
        with sqlite3.connect(download.as_uri() + "?mode=ro", uri=True) as exported, database() as live:
            exported_tables = [r[0] for r in exported.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            check("Database export application tables", ["apps", "ingestion_runs", "reviews"], exported_tables)
            for table in exported_tables:
                left = exported.execute("SELECT * FROM " + table + " ORDER BY 1").fetchall()
                right = [tuple(r) for r in live.execute("SELECT * FROM " + table + " ORDER BY 1")]
                check("Exported table contents: " + table, right, left)
                check("Exported table definition: " + table,
                      live.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0],
                      exported.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0])
            check("Exported database integrity", "ok", exported.execute("PRAGMA integrity_check").fetchone()[0])
        check("Database attachment filename", True, "reviews.db" in headers.get("Content-Disposition", ""))
        health = get_json("/health")
        check("Health status and UTC timestamp", True, set(health) == {"status", "time"} and health["status"] == "ok"
              and datetime.fromisoformat(health["time"]).utcoffset().total_seconds() == 0)

        # Existing test, unchanged: pytest is not installed in the supplied venv.
        test_command = [sys.executable, "-c", "import runpy; m=runpy.run_path('tests/test_smoke.py'); m['test_health'](); print('test_health: PASS')"]
        test = subprocess.run(test_command, cwd=temp, env=env, text=True, capture_output=True)
        check("Existing test_health function (direct runner)", 0, test.returncode)
        test_result = {"command": test_command, "returncode": test.returncode,
                       "stdout": test.stdout, "stderr": test.stderr, "runner": "direct function invocation; not pytest"}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        capture.close()

    raw_log = (temp / "logs/app.log").read_text()
    check("Log has application query parameters", True, "request path=/reviews args=" in raw_log and "'q': 'useful'" in raw_log)
    check("Log has POST path but does not log form app_id", True,
          "request path=/ingest args={}" in raw_log)
    check("Log includes development server startup and HTTP access", True,
          "Running on http://127.0.0.1:" in raw_log and '"GET /export.csv HTTP/1.1" 200' in raw_log)
    check("Demo token appears in private raw query logs", True,
          config["INTERNAL_EXPORT_TOKEN"] in raw_log, kind="observation")
    checks[-1]["interpretation"] = (
        "PASS confirms that token logging was observed. This is a confidentiality "
        "concern, not a passed security requirement.")
    check("Only owned server stopped", True, proc.poll() is not None)
    check("Original database presence unchanged", original_db_exists, original_db_path.exists(), kind="preservation_check")
    check("Original log presence unchanged", original_log_exists, (ROOT / "logs/app.log").exists(), kind="preservation_check")
    after = {str(p.relative_to(ROOT)): digest(p) for p in project_files()
             if p.relative_to(ROOT).parts[0] != "docs"}
    check("All original non-doc files remain byte-identical", original, after)

    def redact(value):
        for key in ("APP_SECRET", "INTERNAL_EXPORT_TOKEN"):
            value = value.replace(config[key], "[REDACTED]")
        value = re.sub(r"(?im)^.*Debugger.*PIN.*$", "[Debugger PIN hidden]", value)
        value = re.sub(r"\x1b\[[0-9;]*m", "", value)
        return value

    redacted_log = redact(raw_log)
    assert all(config[k] not in redacted_log for k in ("APP_SECRET", "INTERNAL_EXPORT_TOKEN"))
    (evidence_dir / "runtime-log.redacted.txt").write_text(redacted_log)
    result = {"run_id": run_id, "verification_date": started_at.date().isoformat(),
              "verification_timezone": "UTC", "started_at": started_at.isoformat(),
              "recorded_utc": datetime.now(timezone.utc).isoformat(),
              "status_semantics": "PASS means the expected result or observation matched; it does not establish security. NOT_APPLICABLE is not counted as PASS.",
              "project_root": str(ROOT), "runtime_copy": str(temp), "base_url": base,
              "python": sys.version, "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
              "packages": {name: importlib.metadata.version(name) for name in ["Flask", "Werkzeug", "Jinja2", "MarkupSafe", "itsdangerous", "click", "blinker"]},
              "pytest_installed": importlib.util.find_spec("pytest") is not None,
              "startup_command": [sys.executable, str(launcher), str(port)],
              "startup_wrapper": launcher.read_text(), "config_flags": {k: config[k] for k in ["ENABLE_DEBUG", "LOG_REQUEST_DETAILS"]},
              "manifest": manifest, "original_db": original_db,
              "provider": {k: {"name": names[k], "count": len(v), "fields": sorted(required), "review_ids": [r["review_id"] for r in v]} for k, v in provider.items()},
              "ingestion": ingestion, "queries": query_results, "summaries": summaries, "history": history,
              "csv": {"parsed_from": "saved_download_file", "download_filename": csv_download.name,
                      "download_sha256": digest(csv_download),
                      "header": parsed[0], "rows": len(parsed)-1, "comma_review_ids": [r["review_id"] for r in comma_rows],
                      "per_app": {k: sum(r[1] == k for r in parsed[1:]) for k in provider}},
              "requests": responses, "existing_test": test_result, "checks": checks,
              "totals": {s: sum(c["status"] == s for c in checks) for s in ["PASS", "FAIL", "NOT_APPLICABLE"]}}
    serialized = redact(json.dumps(result, indent=2, ensure_ascii=False))
    # Do not publish even an accidental unredacted secret.
    assert all(config[k] not in serialized for k in ("APP_SECRET", "INTERNAL_EXPORT_TOKEN"))
    (evidence_dir / "normal-verification.json").write_text(serialized + "\n")
    print(json.dumps({"run_id": run_id, "evidence_directory": str(evidence_dir),
                      "verification_date": result["verification_date"], "verification_timezone": "UTC",
                      "runtime_copy": str(temp), "base_url": base, "totals": result["totals"],
                      "failures": [c["check"] for c in checks if c["status"] == "FAIL"]}))
    if result["totals"]["FAIL"]:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
