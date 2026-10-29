"""Focused, authorized loopback assessment; no external requests or data changes.

Run from the project root with its existing Python environment. Only the isolated
copy receives imports and downloads. Raw material stays in ignored local storage;
published evidence reuses the existing recursive sanitizer. No general scanner.
"""
import ast
import csv
import hashlib
import importlib.metadata
import importlib.util
import io
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
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "docs/evidence/security-assessment"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S%fZ")
    out = PUBLIC / run_id
    out.mkdir(exist_ok=False)
    private = ROOT / ".private-verification/security-assessment" / run_id
    private.mkdir(parents=True, mode=0o700)
    os.chmod(private, 0o700)
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")[:-1]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    watched = sorted(set(tracked) | {p.relative_to(ROOT).as_posix()
                     for d in ("data", "logs") for p in (ROOT / d).glob("*") if p.is_file()})
    baseline = {p: sha(ROOT / p) for p in watched}
    config = {n.targets[0].id: ast.literal_eval(n.value)
              for n in ast.parse((ROOT / "app/config.py").read_text()).body if isinstance(n, ast.Assign)}
    fixture = json.loads((ROOT / "data/provider_reviews.json").read_text())
    apps = list(fixture)
    assert len(apps) == 3 and all(len(fixture[a]) == 3 for a in apps)
    temp = Path(tempfile.mkdtemp(prefix="sciencia-focused-assessment-"))
    os.chmod(temp, 0o700)
    for name in tracked:
        destination = temp / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    copied = {p: sha(temp / p) for p in tracked}
    assert all(copied[p] == baseline[p] for p in tracked)
    assert not (temp / "data/reviews.db").exists() and not (temp / "logs/app.log").exists()
    spec = importlib.util.spec_from_file_location("normal_sanitizer", ROOT / "docs/verify_normal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sanitizer = module.PublicEvidenceSanitizer(
        project_root=ROOT, runtime_copy=temp, python_executable=sys.executable,
        sensitive_values=[config["APP_SECRET"], config["INTERNAL_EXPORT_TOKEN"]],
        usernames=[Path.home().name], hostnames=[platform.node(), platform.node().split(".")[0]])
    sanitizer.secrets[config["INTERNAL_EXPORT_TOKEN"]] = "<EXPORT_TOKEN>"
    sanitizer.secrets[config["APP_SECRET"]] = "<APP_SECRET>"
    result = {"source_commit": commit, "started_at": started.isoformat(), "timezone": "UTC",
              "run_id": run_id, "source_root": str(ROOT), "runtime_copy": str(temp),
              "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
              "packages": {k: importlib.metadata.version(k) for k in ("Flask", "Werkzeug")},
              "config_flags": {k: config[k] for k in ("ENABLE_DEBUG", "LOG_REQUEST_DETAILS")},
              "source_hashes": baseline, "copied_tracked_hashes": copied,
              "requests": [], "checks": [], "observations": {},
              "public_sanitization": {"method": "PublicEvidenceSanitizer from docs/verify_normal.py",
                  "token_alias": "<EXPORT_TOKEN>", "description": "Same alias links control, logs and replay; original values stay private."}}
    proc = None
    capture = None

    def check(name, expected, actual):
        result["checks"].append({"check": name, "expected": expected, "actual": actual,
                                 "status": "PASS" if actual == expected else "FAIL"})

    def client():
        # No CookieJar, authentication handlers, cookies, or authorization headers.
        return build_opener(ProxyHandler({}))

    def request(label, path, *, params=None, form=None, opener=None, client_id="fresh-client"):
        url = base + path + (("?" + urlencode(params)) if params else "")
        data = urlencode(form).encode() if form is not None else None
        headers = {"User-Agent": "focused-local-assessment/1", "Accept": "*/*"}
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(url, data=data, headers=headers)
        try:
            response = (opener or client()).open(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            status = response.code
            response_headers = dict(response.headers)
        record = {"label": label, "requested_at": datetime.now(timezone.utc).isoformat(),
                  "client_id": client_id, "method": "POST" if form is not None else "GET",
                  "path": path, "url": url, "params": params or {}, "form": form,
                  "headers_supplied": headers, "cookie_session_authorization_supplied": False,
                  "status": status, "response_headers": response_headers, "response_bytes": len(body)}
        content_type = response_headers.get("Content-Type", "")
        if "json" in content_type:
            record["response_json"] = json.loads(body)
            if path == "/reviews":
                record["review_count"] = len(record["response_json"])
                record["review_ids"] = [r["review_id"] for r in record["response_json"]]
                record["apps_returned"] = sorted({r["app_id"] for r in record["response_json"]})
        elif "csv" in content_type:
            record["response_text"] = body.decode()
        elif "html" in content_type:
            record["form_app_ids"] = re.findall(r'name="app_id" value="([^"]+)"', body.decode())
        else:
            record["body_sha256"] = hashlib.sha256(body).hexdigest()
            record["sqlite_header"] = body[:16] == b"SQLite format 3\0"
        result["requests"].append(record)
        return record, body

    def state():
        with sqlite3.connect((temp / "data/reviews.db").as_uri() + "?mode=ro", uri=True) as db:
            rows = {t: db.execute("SELECT * FROM " + t + " ORDER BY 1").fetchall()
                    for t in ("apps", "reviews", "ingestion_runs")}
        return {"counts": {t: len(v) for t, v in rows.items()},
                "rows_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}

    def csv_evidence(label, body):
        saved = private / (label + ".csv")
        saved.write_bytes(body)
        with saved.open(encoding="utf-8", newline="") as handle:
            parsed = list(csv.DictReader(handle))
        return {"parsed_from": "saved_download_file", "rows": len(parsed),
                "per_app": {a: sum(r["app_id"] == a for r in parsed) for a in apps},
                "review_ids": sorted(r["review_id"] for r in parsed),
                "fixture_fields_match": all(any(r["review_id"] == f["review_id"] and
                    all(r[k] == str(f[k]) for k in f) for f in fixture[r["app_id"]]) for r in parsed)}

    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        sanitizer.ports[str(port)] = "<LOCAL_PORT>"
        base = "http://127.0.0.1:" + str(port)
        result["base_url"] = base
        launcher = temp / "_assessment_launch.py"
        launcher.write_text("import sys\nfrom pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).parent / 'app'))\n"
            "import app\napp.init_db()\n"
            "app.app.run(host='127.0.0.1', port=int(sys.argv[1]), debug=app.ENABLE_DEBUG, use_reloader=False)\n")
        command = [sys.executable, str(launcher), str(port)]
        result["startup_command"] = command
        capture = (private / "server-console.raw.txt").open("w")
        proc = subprocess.Popen(command, cwd=temp, stdout=capture, stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1"))
        readiness = client()
        for attempt in range(60):
            if proc.poll() is not None:
                raise RuntimeError("Owned server exited before readiness; inspect private console")
            try:
                with readiness.open(base + "/health", timeout=1) as response:
                    if json.load(response)["status"] == "ok":
                        break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("Owned loopback server did not become ready")
        result["initial_state"] = state()
        check("Fresh runtime database", {"apps": 0, "reviews": 0, "ingestion_runs": 0}, state()["counts"])

        normal = client()
        page, _ = request("normal-homepage", "/", opener=normal, client_id="normal-form-client")
        check("Homepage offers expected applications", apps, page["form_app_ids"])
        before = state()
        first, _ = request("normal-form-import", "/ingest", form={"app_id": page["form_app_ids"][0]},
                           opener=normal, client_id="normal-form-client")
        after = state()
        result["observations"]["normal_import"] = {"before": before, "after": after}
        check("Normal form import values", {"app_id": apps[0], "fetched": 3, "inserted": 3}, first.get("response_json"))
        check("Normal form import writes", {"apps": 1, "reviews": 3, "ingestion_runs": 1}, after["counts"])
        history, _ = request("normal-history", "/admin/runs", opener=normal, client_id="normal-form-client")
        check("Normal history includes import", 1, len(history["response_json"]))
        _, csv_body = request("normal-csv", "/export.csv", opener=normal, client_id="normal-form-client")
        result["observations"]["normal_csv"] = csv_evidence("normal", csv_body)
        check("Normal CSV row count", 3, result["observations"]["normal_csv"]["rows"])

        before = state()
        direct, _ = request("credential-free-direct-import", "/ingest", form={"app_id": apps[1]}, client_id="new-no-credentials-import")
        after = state()
        result["observations"]["credential_free_import"] = {"before": before, "after": after}
        check("Direct import values", {"app_id": apps[1], "fetched": 3, "inserted": 3}, direct.get("response_json"))
        check("Direct import changes stored data and history", {"apps": 2, "reviews": 6, "ingestion_runs": 2}, after["counts"])
        history, _ = request("credential-free-history", "/admin/runs", client_id="new-no-credentials-history")
        check("Direct history contains both runs", [apps[1], apps[0]], [r["app_id"] for r in history["response_json"]])
        _, csv_body = request("credential-free-csv", "/export.csv", client_id="new-no-credentials-csv")
        csv_result = csv_evidence("credential-free", csv_body)
        result["observations"]["credential_free_csv"] = csv_result
        check("Direct CSV application scope", {apps[0]: 3, apps[1]: 3, apps[2]: 0}, csv_result["per_app"])
        check("Direct CSV matches sample values", True, csv_result["fixture_fields_match"])

        third, _ = request("prepare-third-app", "/ingest", form={"app_id": apps[2]})
        check("Third import preparation", {"app_id": apps[2], "fetched": 3, "inserted": 3}, third.get("response_json"))
        check("All samples stored", {"apps": 3, "reviews": 9, "ingestion_runs": 3}, state()["counts"])
        sql_before = state()
        controls = [("all-review-control", {}, 9), ("real-app-control", {"app_id": apps[0]}, 3),
                    ("missing-app-control", {"app_id": "com.sciencia.missing"}, 0),
                    ("matching-keyword-control", {"q": "useful"}, 2),
                    ("absent-keyword-control", {"q": "unfindableword"}, 0),
                    ("scoped-absent-keyword-control", {"app_id": apps[0], "q": "unfindableword"}, 0)]
        for label, params, count in controls:
            record, _ = request(label, "/reviews", params=params)
            check(label + " count", count, record["review_count"])
            if label == "real-app-control":
                check("Real-app control does not cross apps", [apps[0]], record["apps_returned"])
        probes = [("app-id-condition-probe", {"app_id": "com.sciencia.missing' OR '1'='1"}),
                  ("keyword-condition-probe", {"app_id": apps[0], "q": "unfindableword%' OR 1=1 -- "})]
        for label, params in probes:
            record, _ = request(label, "/reviews", params=params)
            record["expected_if_values_cannot_change_sql_conditions"] = {"review_count": 0, "review_ids": []}
            check(label + " returns existing samples", sorted(f["review_id"] for rows in fixture.values() for f in rows), sorted(record["review_ids"]))
            check(label + " crosses application filter", sorted(apps), record["apps_returned"])
        result["observations"]["sql_read_only_state"] = {"before": sql_before, "after": state()}
        check("Search probes leave all three tables unchanged", sql_before, state())

        for label, params, expected_status in [
                ("db-missing-token", {}, 403), ("db-incorrect-token", {"token": "incorrect-demo-value"}, 403),
                ("db-valid-demo-token", {"token": config["INTERNAL_EXPORT_TOKEN"]}, 200)]:
            record, body = request(label, "/export.db", params=params, client_id=label + "-client")
            check(label + " status", expected_status, record["status"])
            if expected_status == 403:
                check(label + " rejection body", {"error": "invalid token"}, record.get("response_json"))
            else:
                (private / "normal-download.db").write_bytes(body)
                check("Valid-token attachment is SQLite", True, record.get("sqlite_header"))
        raw_log = (temp / "logs/app.log").read_text()
        exports = [line.split("request path=/export.db args=", 1)[1]
                   for line in raw_log.splitlines() if "request path=/export.db args=" in line]
        log_token = ast.literal_eval(exports[-1]).get("token")
        check("Last export token recovered from application log", True, log_token == config["INTERNAL_EXPORT_TOKEN"])
        access_lines = [line for line in raw_log.splitlines() if 'GET /export.db?token=' in line and log_token in line]
        check("Server access record includes full token", True, bool(access_lines))
        result["observations"]["token_in_logs"] = {
            "application_log_excerpt": [line for line in raw_log.splitlines() if "request path=/export.db args=" in line],
            "server_access_excerpt": access_lines,
            "token_extracted_from_log": log_token, "replay_token_source": "last export query dictionary in runtime logs/app.log",
            "assumed_capability": "Tester already has read access to the isolated runtime log; no OS permission boundary was tested."}
        replay, body = request("db-log-token-replay", "/export.db", params={"token": log_token}, client_id="new-client-with-log-token-only")
        check("Log-token replay status", 200, replay["status"])
        download = private / "replayed-download.db"
        download.write_bytes(body)
        with sqlite3.connect(download.as_uri() + "?mode=ro", uri=True) as db:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            counts = {t: db.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in tables}
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        result["observations"]["replay_download"] = {"application_tables": tables, "counts": counts,
                "integrity_check": integrity, "bytes": len(body), "sha256": sha(download)}
        check("Replayed attachment contains expected tables and counts", {"apps": 3, "reviews": 9, "ingestion_runs": 3}, counts)
        check("Replayed attachment integrity", "ok", integrity)
        check("Read-only exports leave database unchanged", sql_before, state())
    except Exception as error:
        result["execution_error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            result["owned_server_stopped"] = proc.poll() is not None
        if capture is not None:
            capture.close()
        current = {p: sha(ROOT / p) for p in watched}
        check("Original tracked files and runtime data unchanged", baseline, current)
        check("Original data/log file inventory unchanged", sorted(p for p in watched if p.startswith(("data/", "logs/"))),
              sorted({p.relative_to(ROOT).as_posix() for d in ("data", "logs") for p in (ROOT / d).glob("*") if p.is_file()}))
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        result["status"] = "INCOMPLETE" if "execution_error" in result else (
            "COMPLETED" if all(c["status"] == "PASS" for c in result["checks"]) else "CHECK_MISMATCH")
        result["check_semantics"] = "PASS means the stated observation matched; some expectations intentionally confirm insecure behavior. Not security compliance."
        (private / "results.raw.json").write_text(json.dumps(result, indent=2) + "\n")
        for name, raw_path in [("runtime-log.redacted.txt", temp / "logs/app.log"),
                               ("server-console.redacted.txt", private / "server-console.raw.txt")]:
            if raw_path.exists():
                sanitized = sanitizer.sanitize(raw_path.read_text())
                assert all(v not in sanitized for v in (config["APP_SECRET"], config["INTERNAL_EXPORT_TOKEN"], str(ROOT), str(temp)))
                (out / name).write_text(sanitized)
        clean = sanitizer.sanitize(result)
        published = json.dumps(clean, indent=2) + "\n"
        assert all(v not in published for v in (config["APP_SECRET"], config["INTERNAL_EXPORT_TOKEN"], str(ROOT), str(temp)))
        assert clean["checks"] == sanitizer.sanitize(result["checks"])
        (out / "results.json").write_text(published)
        print(json.dumps({"run_id": run_id, "status": result["status"], "requests": len(result["requests"]),
                          "mismatches": [c["check"] for c in result["checks"] if c["status"] != "PASS"],
                          "execution_error": clean.get("execution_error"), "owned_server_stopped": result.get("owned_server_stopped")}))
    return 0 if result["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(run())
