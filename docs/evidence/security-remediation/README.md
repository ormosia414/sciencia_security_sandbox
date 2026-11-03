# Remediation Evidence Guide

Use the [remediation report](../../security-remediation.md) for the analysis and
permissions proposal. This guide identifies the supporting records and how to
reproduce the retained tests. It does not alter the recorded JSON or outputs.

## Preferred run for the current code

Start with
[20261102T200429152769Z-after-parser-patch](runs/20261102T200429152769Z-after-parser-patch/run-summary.json).
It covers the parser-error addition together with the existing regressions.
All groups passed, with exit status 0 and no failures, errors, or skips:

- Search: 12 methods, [output](runs/20261102T200429152769Z-after-parser-patch/search.output.txt).
- Export interface/application log: 3 methods,
  [output](runs/20261102T200429152769Z-after-parser-patch/export-client.output.txt).
- Ordinary real-server log: 1 method,
  [output](runs/20261102T200429152769Z-after-parser-patch/live-server.output.txt).
- HTTP parsing-error log: 1 method,
  [output](runs/20261102T200429152769Z-after-parser-patch/parser-error.output.txt).

The [pre-execution record](runs/20261102T200429152769Z-after-parser-patch/run-start.json)
contains the UTC start time, baseline commit, uncommitted-worktree declaration,
commands, and `source_hashes_before`. The summary records completion time and
`source_hashes_after`. Each group has its own `*.result.json` containing actual
start/completion times, command, exit status, method/failure/error/skip counts,
and the hash of its published `*.output.txt`. These group records also appear
inside the summary.

The baseline is `c61504d80935fba0ab60abe0330a3712518425b4`; it does not contain
the repairs. The latest pre/post hashes of nine source, fixture, and test files
match each other and the current reviewed files. They identify the tested working
tree more precisely than the baseline commit alone. Earlier document inventories
are not substitutes for this run record.

## Evidence for the conclusions

[tests/test_search.py](../../../tests/test_search.py) compares full result rows,
IDs, app IDs, and ordering. It covers normal filters, combined filters that must
exclude other apps, ordinary apostrophes, existing LIKE wildcards, the 200-row
limit, and the two inputs retained in the
[earlier assessment](../../security-assessment.md). Each method has a fresh
nine-review database; quote and limit methods add isolated synthetic fixtures.

[tests/test_export.py](../../../tests/test_export.py) defines 16 credential
combinations: three expect 200 and 13 expect 403. The interface methods select or
reuse those cases, and the ordinary live method checks the matrix once. This is
a request-combination count, not an extra set of test methods. Accepted downloads
are saved and opened read-only; checks cover SQLite integrity, the three app
tables, counts (3 apps, 9 reviews, 3 history rows), and review ID/app mappings.

The ordinary live test uses `run_local_server()` with the reloader disabled and
checks raw app, Werkzeug, and console logs. It searches for four distinct random
credentials and their encoded forms. It requires an app record and access record
for each export request and verifies the expected statuses. The parser method
separately requires 400 rather than Flask's 403, no Flask export-request record,
a standard non-sensitive error record, and no random marker or raw request line.
These assertions run before temporary cleanup; full raw logs and downloads are
not public attachments. A passing server method also checks termination of its
owned process. If local listening is denied, the method skips; a skip is not a pass.

## Parser patch: before and after

The
[before-patch run](runs/20261102T200332547810Z-before-parser-patch/run-summary.json)
executes only the new parser regression against the earlier logging implementation.
Its [output](runs/20261102T200332547810Z-before-parser-patch/parser-error.output.txt)
records one failure, exit status 1, and no errors or skips. The test first
confirmed a protocol 400 and absence of Flask export handling, then failed because
the raw server log contained the encoded marker. This intentional comparison
remains recorded as a failure, not relabelled as PASS or an expected-failure test.

The same method passes in the preferred after-patch run. `tests/test_export.py`
has the same hash in both phases; `app/app.py` changes for the `send_error()`
override. Both send one fixed malformed request template with a fresh random
marker. No fuzzing or other parser paths were exercised. The standard reason
`Bad Request` and status remain logged after the patch. The comparison establishes
this path, not all error handling in other servers or configurations.

## Reproduction

From the project root, with its existing compatible Python environment:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_search.py -v
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -k ExportCredentialTests -v
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -k LiveExportLogTests -v
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -k HttpParseErrorLogTests -v
```

The tests copy the application and synthetic data, use independent databases and
logs, and generate test-only credentials. Server tests bind only to `127.0.0.1`;
HTTP proxies are disabled. Cleanup stops their servers and removes temporary
artifacts. These commands rerun assertions; they do not recreate past timestamps
or automatically produce the original recorded outputs. No tests were rerun for
this document organization.

## Older material and public handling

- [20261102T194801327029Z](runs/20261102T194801327029Z/run-summary.json) retained
  search (12), interface/application-log (3), and ordinary server (1) outputs
  before the parser regression and patch. Its app and export-test hashes therefore
  differ from the latest files; it does not verify the parser repair.
- [workspace-manifest.json](workspace-manifest.json) is the earlier
  documentation-time source inventory, explicitly not a test execution record.
  It describes the pre-parser repair snapshot and remains unchanged.
- Initial implementation-time output was not saved as a standalone artifact.
  Later recorded runs are separate executions, not reconstructed or backdated
  transcripts. Module 1/2 reports, evidence, and scripts retain their historical
  meaning; scripts expecting URL-token acceptance or vulnerable filtering are
  not current regression expectations.

Public outputs normalize environment identifiers and redact configured secrets
using the existing sanitizer. The before-patch failure output retains the failed
assertion without revealing its random marker. No actual test credentials,
databases, downloaded files, full raw server logs, or private backups belong in
this directory. Private recording material is ignored by Git. Retained hashes
and actual test outputs support this local assessment without establishing a
production severity rating or a new authorization policy.
