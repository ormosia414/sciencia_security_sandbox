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

Server-side Bearer credentials now map to Viewer or Operator. Operator inherits
Viewer reads and CSV export, then adds import and whole-database export. Both
roles can read all apps. Only minimal health information, the current stylesheet,
and automatic method-only OPTIONS responses are public. See the
[implemented access rules](docs/access-control.md) for configuration and limits.
This remains a local teaching app with demo/development settings, not a
production-ready or comprehensively secured service. Role credentials identify
a permission class, not an individual account.

## Reading guide

- **Understand the system:** [System overview](docs/system-overview.md).
  This Module 1 analysis describes the pre-remediation architecture and risks;
  its search, export, and logging descriptions are historical where later fixes
  changed the implementation.
- **Read the findings before fixes:** [Focused assessment](docs/security-assessment.md)
  and its [evidence guide](docs/evidence/security-assessment/README.md).
  These describe the 27 October 2026 assessment of the earlier code.
- **Review the earlier search/export repairs and permission design:**
  [Security remediation](docs/security-remediation.md). Its
  [evidence guide](docs/evidence/security-remediation/README.md) identifies the
  preferred run for that pre-role repair snapshot, the parser patch comparison,
  and reproduction commands.
- **Use the current role-protected application:** [Access control](docs/access-control.md)
  and its [recorded regressions](docs/evidence/access-control/README.md).
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

Use two Terminal windows, both opened at the project root. In **Terminal A**,
create the credentials once with the existing Python environment. This generates
separate random Viewer and Operator values without typing or printing them.
It writes three private files under `.private-verification/`: `role-env.sh` for
the server environment, and `viewer.headers` / `operator.headers` for clients.
The directory has mode **700** and each file **600** (owner access only).

The existing `.gitignore` excludes `.private-verification/`. The command checks
that each destination is ignored and untracked before writing, and refuses to
overwrite existing credential files. If all three already exist from a successful
setup, reuse them and skip generation. If only some exist, stop and resolve that
partial setup before starting the app. Do not force-add these files to Git.

```sh
.venv/bin/python -B - <<'PYTHON'
import os
from pathlib import Path
import secrets
import subprocess

private = Path('.private-verification')
names = ('role-env.sh', 'viewer.headers', 'operator.headers')
for name in names:
    path = private / name
    subprocess.run(['git', 'check-ignore', '--quiet', '--', str(path)], check=True)
    if subprocess.check_output(['git', 'ls-files', '--', str(path)], text=True).strip():
        raise SystemExit('Stop: a credential destination is tracked by Git.')
    if path.exists():
        raise SystemExit('Credential files already exist; reuse them instead.')
private.mkdir(mode=0o700, exist_ok=True)
private.chmod(0o700)
viewer = secrets.token_urlsafe(32)
operator = secrets.token_urlsafe(32)
while operator == viewer:
    operator = secrets.token_urlsafe(32)
contents = {
    'role-env.sh': f"export SCIENCIA_VIEWER_TOKEN='{viewer}'\n"
                   f"export SCIENCIA_OPERATOR_TOKEN='{operator}'\n",
    'viewer.headers': f'Authorization: Bearer {viewer}\n',
    'operator.headers': f'Authorization: Bearer {operator}\n',
}
for name, content in contents.items():
    descriptor = os.open(private / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(content)
print('Private credential files created; values were not printed.')
PYTHON
```

Still in **Terminal A**, turn off shell tracing/verbose input, load the generated
file, and start the app. Keep this terminal running the server:

```sh
set +x
set +v
. ./.private-verification/role-env.sh
.venv/bin/python -B app/app.py
```

The two environment variable names match `app/config.py`. Missing, empty,
malformed, or identical role secrets disable all protected routes. Changing
credentials requires updating the matching local files and restarting the server.
Do not regenerate them while a server still uses the previous pair.

The server listens at `http://127.0.0.1:5000`. Startup creates `data/reviews.db` and writes local
logs under `logs/`. Use this entry point, or the application's
`run_local_server()` function, so the current access/error log handler is installed.
A different Flask launcher does not automatically receive that handler.

## Current usage

Requests need `Authorization: Bearer <ROLE_TOKEN>` for the approved role.
An ordinary browser visit to the homepage returns 401 because it does not supply
this header. There is no login page or cookie-based fallback. Homepage forms
also do not automatically attach a Bearer header; use a header-capable client.
Viewer pages omit import controls, but direct requests are checked on the server.

In **Terminal B**, at the same project root, use the header files created in
Terminal A. Do not generate a second pair or source the environment file here.
`curl --header @file` reads the same credentials from disk rather than putting
their values in command-line arguments. `--disable` is the first option to avoid
loading an unrelated curl configuration. For example, an Operator can import:

```sh
curl --disable --fail --silent --show-error \
  --header @.private-verification/operator.headers \
  --data 'app_id=com.sciencia.focus' http://127.0.0.1:5000/ingest
```

The backend reads that app's local JSON and writes SQLite. Repeated imports skip
existing review IDs and add a history row. Viewer or Operator can then read:

```sh
curl --disable --fail --silent --show-error \
  --header @.private-verification/viewer.headers \
  'http://127.0.0.1:5000/reviews?app_id=com.sciencia.focus&q=useful'
```

- `/reviews` retains combined filters and SQLite LIKE wildcards `%` and `_`.
- `/analysis/summary` returns ordinary review statistics for either role.
- `/admin/runs` returns the six safe history fields listed in the access guide;
  neither role receives free-text `message` values from this route.
- `/export.csv` lets either role download all reviews, regardless of earlier filters.
- `/health` publicly returns only status and UTC time, without checking dependencies.
- `/static/style.css` is public; other static filenames are not served.

Missing or invalid identity returns generic **401** with a Bearer challenge.
A recognized Viewer requesting an Operator operation receives generic **403**.
Client-supplied role declarations cannot grant permissions. HEAD follows GET
permissions; automatic OPTIONS returns methods only, without data or writes.

### Database export

`/export.db` requires the Operator credential. In Terminal B, reuse its header
file and save the attachment in the same ignored private directory:

```sh
curl --disable --fail --silent --show-error \
  --header @.private-verification/operator.headers \
  --output .private-verification/downloaded-reviews.db \
  http://127.0.0.1:5000/export.db
```

The former shared `INTERNAL_EXPORT_TOKEN` is removed from current configuration
and authorization. Old shared credentials and URL `token` values cannot grant
access. Use one space and a nonempty Bearer value; the scheme is case-insensitive.
The attachment contains all three tables, not just the CSV review extract.

Application request logs retain method, path, and status without headers or query
values. The provided server handler removes query strings from normal access
records and replaces parser diagnostics with standard status reasons before
logging. The recorded tests cover normal credential cases and one identified
bad-request-syntax path, not every possible exception. Other servers, proxies,
browsers, and clients need their own log settings. Old logs and downloaded copies
are not erased by these code changes.

### Local credential protection limits

Shell history contains the commands and file paths above, not generated secret
values. Keep shell tracing off and do not use curl verbose/trace options, print
these files, or paste their contents into reports. File-backed headers avoid
literal credentials in curl's process arguments, but curl still reads them into
memory. The server receives them through inherited environment variables; those
are not a secret vault. The private files are unencrypted, and sufficiently
privileged local processes can inspect files, environments, or memory. Git ignore
rules prevent ordinary staging, not local access or deliberate publication.
Application/server log protection is separate: use the supplied startup entry
point as described above; it does not control other clients or proxies.

## Current regression tests

Use the existing environment; these checks use standard-library `unittest`,
without requiring pytest. Search and interface checks use Flask's in-process
client and independent temporary copies/databases:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_search.py -v
.venv/bin/python -B -m unittest discover -s tests -p test_access.py -v
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -k ExportCredentialTests -v
```

The next two groups start an actual temporary server, bind only to `127.0.0.1`,
check raw logs, and stop their owned process:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -k LiveExportLogTests -v
.venv/bin/python -B -m unittest discover -s tests -p test_export.py -k HttpParseErrorLogTests -v
```

A server test skipped because local listening is restricted is **not** a verified
pass. The [current role-aware run and counts](docs/evidence/access-control/README.md)
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

Reports and checked, sanitized evidence are review materials. The remaining
committed secret literal is explicitly a demo; role secrets come only from the
local environment. `.venv/`, the runtime
`data/reviews.db`, raw `logs/*.log`, OS metadata, and `.private-verification/`
are ignored local material. Keep downloads and other private data out of version
control; ignore rules do not remove files already tracked or previously shared.
