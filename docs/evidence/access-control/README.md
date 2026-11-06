# Access-control regression evidence

The preferred run is
[`runs/20261105T220103622742Z/run-summary.json`](runs/20261105T220103622742Z/run-summary.json).
It records an uncommitted role-enforcement snapshot based on `9330b11`, not a test
of that baseline alone. `source_before` and `source_after` identify the tested
files. All three groups exited zero: search 12 methods, access 10, export/server
5, with no failures, errors, or skips. The export group comprises three interface
methods and two real-loopback methods. Its 17 credential request combinations are
separate from test-method counts.

The adjacent output files retain actual unittest results. Each group records its
UTC start/end, command, exit status, method count, failures, errors, and skips.
`source_unchanged_during_run` checks hashes before/after, and
`existing_runtime_unchanged` compares the original database and app-log bytes
without publishing those files. Output uses the existing public-evidence
sanitizer for environment information. Raw logs and downloaded databases remain
inside private temporary test copies and are removed by cleanup.

From project root, using the existing environment:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_search.py -v
.venv/bin/python -B -m unittest discover -s tests -p test_access.py -v
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -v
```

`test_export.py` includes the live-server and parsing-error groups. They require
local socket permission and use only `127.0.0.1`. A skipped socket test is not a
pass. The tests inject random role credentials in copied applications and check
raw logs before cleanup; no caller credentials are needed to run them.

To create a new independent record rather than replace these files:

```sh
.venv/bin/python -B docs/evidence/access-control/record_tests.py
```

The recorder creates a new timestamped directory and treats skips as incomplete.
It invokes only the three commands above, not old vulnerability scripts.
Earlier search/export-only evidence is preserved under
[`../security-remediation/`](../security-remediation/README.md); it predates roles
and is not proof of current authorization. Initial development checks exposed a
copied-module template/static lookup issue in the test harness; registering the
copied module during import corrected it without weakening assertions. Both
socket tests were initially skipped in the restricted environment. The saved run
above executed both successfully; earlier failures and skips are not relabeled
as passes.
