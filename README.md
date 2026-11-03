# Sciencia AI Review Intelligence Sandbox

A local Flask/SQLite teaching application for importing, searching, summarizing,
and exporting synthetic app reviews. The provider is
`data/provider_reviews.json`, a local mock with three apps and nine reviews.
There is no live external provider API or AI model: summaries calculate review
counts, average ratings, and word frequencies.

## Current implementation

System analysis and a focused local security assessment are complete. The
implementation now binds both search inputs as SQL parameters, accepts database
export credentials through a Bearer header, and protects the tested application,
normal server-access, and HTTP parsing-error logging paths. The supplied local
startup entry point installs the server log handler used by the regressions.

Viewer/Operator permissions are a proposal awaiting review, not implemented
roles. Import, history, and CSV still have no caller-role checks; the database
export token is a shared operation credential, not personal identity. This remains
a local teaching app with demo configuration and development/debug settings,
not a production-ready or comprehensively secured service.

## Reading guide

- **Understand the system:** [System overview](docs/system-overview.md).
  This Module 1 analysis describes the pre-remediation architecture and risks;
  its search, export, and logging descriptions are historical where later fixes
  changed the implementation.
- **Read the findings before fixes:** [Focused assessment](docs/security-assessment.md)
  and its [evidence guide](docs/evidence/security-assessment/README.md).
  These describe the 27 October 2026 assessment of the earlier code.
- **Review the current repairs and permission decisions:**
  [Security remediation](docs/security-remediation.md). Its
  [evidence guide](docs/evidence/security-remediation/README.md) identifies the
  preferred run for the committed repair snapshot, the parser patch comparison,
  and reproduction commands.
- **Look up earlier normal behavior:** [Verification results](docs/verification-results.md).
  The 17 October 2026 records predate the repairs and are not current acceptance
  tests.

The original [overview template](docs/system_overview.md) is retained as teaching
material, not the final system report. The [student brief](STUDENT_START_HERE.md)
and [scope](SECURITY_SCOPE.md) are the original task documents. They have not been
rewritten to match later stages. These materials are provided for review; public
publication is not an assignment requirement.

## Install and start

The commands below use a POSIX shell and Python 3. Reuse an existing compatible
project environment if available; for a fresh checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Start from the project root:

```sh
.venv/bin/python -B app/app.py
```

Open `http://127.0.0.1:5000`. Startup creates `data/reviews.db` and writes local
logs under `logs/`. Use this entry point, or the application's
`run_local_server()` function, so the current access/error log handler is installed.
A different Flask launcher does not automatically receive that handler.

## Current usage

Use the homepage buttons to import samples. The client sends an app ID; the
backend reads that app's JSON records and stores them in SQLite. Repeated imports
skip existing review IDs and add another history row.

- `/reviews` reads stored reviews; optional `app_id` and `q` filters can be
  combined. SQLite LIKE wildcards `%` and `_` retain their existing meaning.
- `/analysis/summary` returns ordinary statistics for stored reviews.
- `/admin/runs` returns import history. Its name does not provide an admin role.
- `/export.csv` downloads all stored reviews, independently of earlier filters.
- `/health` returns status and UTC time, not database-readiness verification.

Import, history, and CSV requests currently require no application identity
credential. The proposed permission table does not restrict these routes yet.

### Database export

`/export.db` requires `Authorization: Bearer <EXPORT_TOKEN>`:

```sh
mkdir -p .private-verification
curl --header 'Authorization: Bearer <EXPORT_TOKEN>' \
  --output .private-verification/downloaded-reviews.db \
  http://127.0.0.1:5000/export.db
```

Replace the placeholder locally with the configured sandbox value. Use one space
and a nonempty token; the Bearer scheme is case-insensitive. Missing, incorrect,
empty, or malformed credentials return the existing generic 403 response.
The old URL `token` parameter never authorizes a download and cannot compensate
for an invalid header. An ordinary browser link alone cannot supply this Bearer
header. The attachment contains the whole database, including app mappings and
import history, rather than only the CSV review extract.

Application request logs retain method, path, and status without headers or query
values. The provided server handler removes query strings from normal access
records and replaces parser diagnostics with standard status reasons before
logging. The recorded tests cover normal credential cases and one identified
bad-request-syntax path, not every possible exception. Other servers, proxies,
browsers, and clients need their own log settings. Old logs and downloaded copies
are not erased by these code changes.

## Current regression tests

Use the existing environment; these checks use standard-library `unittest`,
without requiring pytest. Search and interface checks use Flask's in-process
client and independent temporary copies/databases:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_search.py -v
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -k ExportCredentialTests -v
```

The next two groups start an actual temporary server, bind only to `127.0.0.1`,
check raw logs, and stop their owned process:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -k LiveExportLogTests -v
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -k HttpParseErrorLogTests -v
```

A server test skipped because local listening is restricted is **not** a verified
pass. The [retained run and counts](docs/evidence/security-remediation/README.md)
separate test methods from credential request combinations and identify the
source hashes used. These commands reproduce assertions, not historical timestamps.

`tests/test_public_evidence.py` contains separate offline sanitizer regressions.
`tests/test_smoke.py` is the original health helper and can initialize runtime
files in its checkout when called directly; it is not the current isolated
acceptance entry point.

Do not use `docs/verify_normal.py` or
`docs/evidence/security-assessment/assess_local.py` as current acceptance tests.
They retain the old URL-token/logging or vulnerable-query expectations. Their
[historical scope](docs/verification-results.md) and
[assessment version](docs/evidence/security-assessment/README.md) explain the
matching source snapshots; old outputs should not be rewritten to fit repairs.

## Scope and local material

Work is limited to this local teaching sandbox and synthetic data, as described
in [SECURITY_SCOPE.md](SECURITY_SCOPE.md). The original first module required
system understanding before active testing. Later focused local assessment and
repair work is documented separately; production, client, and third-party
systems are outside this project.

Reports and checked, sanitized evidence are review materials. Configuration
values are explicitly demos, not real credentials. `.venv/`, the runtime
`data/reviews.db`, raw `logs/*.log`, OS metadata, and `.private-verification/`
are ignored local material. Keep downloads and other private data out of version
control; ignore rules do not remove files already tracked or previously shared.
