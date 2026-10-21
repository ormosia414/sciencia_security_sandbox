"""Offline sanitizer regression checks. No Flask imports, server, or HTTP calls.

All path/identity fixtures below are invented examples, not local machine data.
"""
import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "normal_verifier", Path(__file__).resolve().parents[1] / "docs/verify_normal.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
Sanitizer = verifier.PublicEvidenceSanitizer


class PublicEvidenceTests(unittest.TestCase):
    def make_sanitizer(self):
        return Sanitizer(project_root="/example/project", runtime_copy="/tmp/unit-runtime",
                         python_executable="/example/project/.venv/bin/python", local_port=54321,
                         usernames=["unit-user"], hostnames=["unit-host.local", "unit-host"],
                         sensitive_values=["demo-only-alpha", "demo-only-beta"])

    def test_nested_keys_values_commands_and_json_roundtrip(self):
        raw = {"project_root": "/example/project", "runtime_copy": "/tmp/unit-runtime",
               "startup_command": ["/example/project/.venv/bin/python", "/tmp/unit-runtime/launch.py", "54321"],
               "existing_test": {"command": ["/example/project/.venv/bin/python", "-c", "run_test()"]},
               "manifest": [{"file": "/example/project/app/app.py", "sha256": "a" * 64}],
               "checks": [{"expected": {"/example/project/app/app.py": "b" * 64},
                           "actual": {"/example/project/app/app.py": "b" * 64}, "status": "PASS"}]}
        clean = self.make_sanitizer().sanitize(raw)
        self.assertEqual(clean, json.loads(json.dumps(clean)))
        self.assertEqual(clean["project_root"], "<PROJECT_ROOT>")
        self.assertEqual(clean["runtime_copy"], "<TEMP_RUNTIME>")
        self.assertEqual(clean["startup_command"],
                         ["<PYTHON_EXECUTABLE>", "<TEMP_RUNTIME>/launch.py", "<LOCAL_PORT>"])
        self.assertEqual(clean["manifest"][0]["sha256"], "a" * 64)
        self.assertEqual(clean["checks"][0]["expected"], clean["checks"][0]["actual"])

    def test_distinct_paths_and_failure_relationship_are_preserved(self):
        raw = {"expected": {"/srv/first/file.txt": 1, "/srv/second/file.txt": 2},
               "actual": {"/srv/second/file.txt": 1, "/srv/first/file.txt": 2}, "status": "FAIL"}
        clean = self.make_sanitizer().sanitize(raw)
        self.assertEqual(len(clean["expected"]), 2)
        self.assertNotEqual(clean["expected"], clean["actual"])
        self.assertEqual(clean["status"], "FAIL")
        self.assertNotIn("/srv/", json.dumps(clean))

    def test_sibling_root_is_not_mistaken_for_project_root(self):
        clean = self.make_sanitizer().sanitize(["/example/project/a.py", "/example/project-other/a.py"])
        self.assertEqual(clean[0], "<PROJECT_ROOT>/a.py")
        self.assertNotEqual(clean[0], clean[1])
        self.assertNotIn("project-other", clean[1])

    def test_runtime_aliases_spaces_and_windows_paths(self):
        sanitizer = Sanitizer(project_root="/example/My Project", runtime_copy="/var/folders/unit/T/runtime",
                              python_executable=r"C:\Users\unit-user\env\python.exe")
        clean = sanitizer.sanitize(["/example/My Project/app.py", "/private/var/folders/unit/T/runtime/file.csv",
                                    r"C:\Users\unit-user\env\python.exe", r"D:\private\other.txt"])
        self.assertEqual(clean[:3], ["<PROJECT_ROOT>/app.py", "<TEMP_RUNTIME>/file.csv", "<PYTHON_EXECUTABLE>"])
        self.assertNotIn("private", clean[3])

    def test_logs_tracebacks_identity_and_secrets(self):
        fake_pin = "-".join(("123", "456", "789"))
        raw = ('File "/example/project/app/app.py", line 10\n'
               'Running on http://127.0.0.1:54321\n'
               'GET /analysis/summary?app_id=com.sciencia.focus HTTP/1.1\n'
               'GET /admin/runs HTTP/1.1\n'
               'unit-user on unit-host.local\n'
               'demo-only-alpha demo-only-beta\n'
               f'Debugger PIN: {fake_pin}\nPort 54321 is unavailable')
        clean = self.make_sanitizer().sanitize(raw)
        self.assertIn("<PROJECT_ROOT>/app/app.py", clean)
        self.assertIn("127.0.0.1:<LOCAL_PORT>", clean)
        self.assertIn("/analysis/summary?app_id=com.sciencia.focus", clean)
        self.assertIn("/admin/runs", clean)
        for private in ["unit-user", "unit-host", "demo-only-alpha", "demo-only-beta", fake_pin, "54321"]:
            self.assertNotIn(private, clean)
        self.assertIn("<LOCAL_USER>", clean)
        self.assertIn("<LOCAL_HOST>", clean)

    def test_counts_versions_hashes_and_statuses_are_unchanged(self):
        raw = {"totals": {"PASS": 68, "FAIL": 0, "NOT_APPLICABLE": 1},
               "packages": {"Flask": "3.0.3"}, "sha256": "c" * 64,
               "average_rating": 3.44, "records": 9, "status": "NOT_APPLICABLE"}
        self.assertEqual(self.make_sanitizer().sanitize(raw), raw)

    def test_idempotence_and_distinct_ports(self):
        sanitizer = self.make_sanitizer()
        raw = ["http://127.0.0.1:54321", "http://localhost:54322", "/tmp/unit-runtime/file.csv"]
        clean = sanitizer.sanitize(raw)
        self.assertEqual(sanitizer.sanitize(clean), clean)
        self.assertNotEqual(clean[0].split(":")[-1], clean[1].split(":")[-1])

    def test_private_backup_directory_is_excluded(self):
        self.assertIn(".private-verification", verifier.EXCLUDE)
        self.assertTrue(all(".private-verification" not in p.parts for p in verifier.project_files()))

    def test_comparison_collapse_is_rejected(self):
        sanitizer = Sanitizer(project_root="/example/project", runtime_copy="/var/folders/unit/T/runtime")
        with self.assertRaisesRegex(ValueError, "expected/actual equality"):
            sanitizer.sanitize({"expected": "/var/folders/unit/T/runtime/file.csv",
                                "actual": "/private/var/folders/unit/T/runtime/file.csv", "status": "FAIL"})


if __name__ == "__main__":
    unittest.main()
