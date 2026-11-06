"""Record only existing isolated role/search/export regressions; no baseline probes.

Run from project root: .venv/bin/python -B docs/evidence/access-control/record_tests.py
Raw test output is held in memory; public files pass the existing sanitizer.
"""
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from urllib.parse import quote, quote_plus

ROOT = Path(__file__).resolve().parents[3]
FILES = ["app/app.py", "app/config.py", "app/db.py", "app/templates/index.html",
         "app/static/style.css", "data/provider_reviews.json", "requirements.txt",
         "tests/test_search.py", "tests/test_export.py", "tests/test_access.py",
         "docs/evidence/access-control/record_tests.py"]


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}


def runtime_hashes():
    # Read only to verify existing user data was left untouched. Never publish bytes.
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            if (ROOT / name).is_file() else None
            for name in ("data/reviews.db", "logs/app.log")}


def run():
    spec = importlib.util.spec_from_file_location("public_verifier", ROOT / "docs/verify_normal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = [os.environ.get(key, "") for key in ("SCIENCIA_VIEWER_TOKEN", "SCIENCIA_OPERATOR_TOKEN")]
    values = [encoded for value in values if value for encoded in (value, quote(value), quote_plus(value))]
    sanitizer = module.PublicEvidenceSanitizer(project_root=ROOT, python_executable=sys.executable,
        usernames=[getpass.getuser()], hostnames=[socket.gethostname()], sensitive_values=values)
    started = datetime.now(timezone.utc)
    destination = Path(__file__).parent / "runs" / started.strftime("%Y%m%dT%H%M%S%fZ")
    destination.mkdir(parents=True, exist_ok=False)
    before, runtime_before = hashes(), runtime_hashes()
    record = {"started_at": started.isoformat(), "timezone": "UTC",
              "baseline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "snapshot": "Uncommitted access-control implementation, identified by source hashes",
              "source_before": before, "groups": []}
    for label, pattern in (("search", "test_search.py"), ("access", "test_access.py"), ("export-and-server", "test_export.py")):
        command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"]
        group_start = datetime.now(timezone.utc)
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        clean = sanitizer.sanitize(result.stdout)
        (destination / (label + ".output.txt")).write_text(clean)
        ran = re.search(r"Ran (\d+) tests?", result.stdout)
        counts = {key: int(match.group(1)) if (match := re.search(key + r"=(\d+)", result.stdout)) else 0
                  for key in ("failures", "errors", "skipped")}
        total = int(ran.group(1)) if ran else None
        record["groups"].append({"name": label, "command": sanitizer.sanitize(command),
            "started_at": group_start.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
            "exit_status": result.returncode, "test_methods": total, **counts,
            "passed": total - sum(counts.values()) if total is not None else None,
            "output": label + ".output.txt"})
    record.update(finished_at=datetime.now(timezone.utc).isoformat(), source_after=hashes(),
                  existing_runtime_unchanged=runtime_hashes() == runtime_before)
    record["source_unchanged_during_run"] = record["source_before"] == record["source_after"]
    serialized = json.dumps(sanitizer.sanitize(record), indent=2) + "\n"
    (destination / "run-summary.json").write_text(serialized)
    print(json.dumps({"record": str(destination.relative_to(ROOT)), "groups": record["groups"],
                      "source_unchanged": record["source_unchanged_during_run"],
                      "existing_runtime_unchanged": record["existing_runtime_unchanged"]}, indent=2))
    return int(not record["source_unchanged_during_run"] or not record["existing_runtime_unchanged"]
               or any(group["exit_status"] or group["skipped"] or group["test_methods"] is None
                      for group in record["groups"]))


if __name__ == "__main__":
    raise SystemExit(run())
