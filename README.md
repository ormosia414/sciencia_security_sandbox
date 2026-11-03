# Sciencia AI Review Intelligence Sandbox

A small, self-contained review-ingestion and analysis application used for the Cyber Security Internship project.

## Module 1 reading guide

Read the [system understanding and initial security analysis](docs/system-overview.md)
first for the architecture, data flows, access points, protected information,
trust assumptions, and investigation priorities. Then read the
[verification results](docs/verification-results.md) for the methods, recorded
normal behavior, evidence links, and limitations.

For the later stages, see the [focused security assessment](docs/security-assessment.md)
for pre-fix findings and [search/export remediation](docs/security-remediation.md)
for implemented changes, regression results, evidence limitations, and the
proposed permissions awaiting review. Earlier reports retain their historical
meaning rather than describing the current interface.

The [scope](SECURITY_SCOPE.md) and [original student brief](STUDENT_START_HERE.md)
define the teaching task. These materials are provided for review; public
publication is not a Module 1 deliverable requirement. Evidence uses environment
placeholders and redacts credentials and debug identifiers. The original Module 1
task excluded active security testing; later focused local work is documented
separately.

Supporting material includes the source in `app/`, sample data in `data/`,
the verification script in `docs/verify_normal.py`, evidence in `docs/evidence/`,
and tests in `tests/`. The original [overview template](docs/system_overview.md)
is retained for context; it is not the final report and its simplified flow
should not replace the final report's implementation-based diagrams.

## What the system does

The application simulates a lightweight internal data workflow:

1. A user selects an App and triggers an ingestion run.
2. The backend loads review records from a local mock-provider file (`data/provider_reviews.json`); no external provider API is contacted.
3. Review fields are inserted into SQLite; existing review IDs are skipped rather than updated.
4. Users can search stored reviews, inspect ingestion runs, export data, and view counts, average ratings, and word frequencies. This is ordinary statistics, not AI sentiment classification.

The sandbox is intentionally small so that the architecture, data flow, and security posture can be understood end to end.

## Components

- Flask web application
- SQLite database
- Local JSON mock review provider
- Local application logs
- Simple HTML interface
- CSV/database export endpoints

## Review materials and private local files

The reports and sanitized evidence are intended for review. Configuration values
in `app/config.py` are explicitly demo values, and provider records are synthetic.
The sanitizer tests use invented paths and identities as fixtures, not real
machine information.

The ignored virtual environment, runtime database, raw logs, OS metadata, and
`.private-verification/` backups are local material, not tracked deliverables.
Downloaded databases and CSV files should also remain private local files.
Only sanitized evidence belongs in the evidence directory for review; ignoring a
file does not remove anything already tracked or previously published.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app/app.py
```

Then open: `http://127.0.0.1:5000`

The database is created automatically at `data/reviews.db`.

## Database export

The current `/export.db` endpoint requires an Authorization header:

```sh
curl --header 'Authorization: Bearer <EXPORT_TOKEN>' \
  --output downloaded-reviews.db http://127.0.0.1:5000/export.db
```

Replace the placeholder locally with the configured sandbox value. The Bearer
scheme is case-insensitive; use one space followed by the nonempty token.
Missing, incorrect, empty, or malformed credentials return 403 with the same
generic error. A `token` URL query parameter never grants permission, even when
combined with a missing or incorrect header. CSV export is unchanged.

Application request logs retain method, path, and status, without headers or
query values. The supplied local server entry point (`python app/app.py`, or
`run_local_server()` for a chosen local port) also omits query strings from
Werkzeug access records before writing them. HTTP parser errors use only the
standard status reason: the local handler discards raw diagnostic messages
before inherited error logging and responses. This was checked for the single
bad-request-syntax path in the [remediation report](docs/security-remediation.md),
not every possible exception. Other launchers, WSGI servers, proxies, browsers,
and clients need their own logging configuration; this project
does not control their logs. Do not put credentials in URLs.

The earlier reports and scripts remain historical baselines. In particular,
`docs/verify_normal.py` and `docs/evidence/security-assessment/assess_local.py`
expect the former query-token/logging behavior; their expectations do not define
the current interface. Do not rerun them as current regression tests or rewrite
their evidence to match these fixes.

## Internship scope

This repository is a **local security sandbox**. It should be reviewed and tested only on your own local copy.

Please read `SECURITY_SCOPE.md` before beginning any active security testing.

For the first module, focus on understanding the architecture, assets, data flow, access points, trust boundaries, and areas that may deserve deeper security review. Do not begin active exploitation or scanning until specifically instructed.
