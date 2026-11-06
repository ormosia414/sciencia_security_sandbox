# Local role-based access control

Author: Phoebe Zhang

## Result and design

Search and export repairs addressed SQL handling and credential logging, but
imports, history, CSV, and other reading routes still needed a consistent access
policy. The approved Viewer/Operator model now enforces that policy before
protected handlers run, without adding accounts, a login page, per-app rules,
or an external identity service. The
[earlier permission design](security-remediation.md#permissions-design-and-subsequent-implementation)
explains how the model developed.

In `app/app.py`, `identify_role()` maps a valid Bearer credential to a role using
server configuration. `enforce_permissions()` checks a central endpoint allowlist.
Operator inherits the complete Viewer permission set, then adds import and
whole-database export. An input such as `role=Operator` or `X-Role: Operator`
does not influence either step. Both roles may read every app; `app_id` remains
a search filter.

## Implemented rules

| Method and route | No valid identity | Viewer | Operator |
|---|---|---|---|
| `GET /` | 401 | Allow counts and endpoint descriptions | Same; also shows import controls |
| `GET /reviews` | 401 | Allow all apps, optional filters | Same |
| `GET /analysis/summary` | 401 | Allow one/all-app statistics | Same |
| `GET /admin/runs` | 401 | Allow safe history summaries | Same safe summaries |
| `GET /export.csv` | 401 | Allow all stored reviews | Same |
| `POST /ingest` | 401 | 403 | Allow imports |
| `GET /export.db` | 401 | 403 | Allow whole-database download |
| `GET /health` | Public | Public | Public |
| `GET /static/style.css` | Public | Public | Public |

Only that exact stylesheet filename is allowed through the static route; other
filenames receive 404, even with role credentials. New static files do not become
public automatically. Health returns `status` and a UTC `time`, not database or
dependency readiness. HEAD requires the same permission as the corresponding
GET and returns no body. Flask-generated OPTIONS is public but returns only
method metadata, with no business content or operations. Unmatched paths and
unsupported methods retain Flask's 404/405 behavior.

401 means the request has no recognized identity, including missing, empty,
wrong, or malformed credentials. It returns `{"error": "authentication required"}`
and `WWW-Authenticate: Bearer`. A recognized role lacking permission receives
403 and `{"error": "forbidden"}`. Neither response echoes credentials. This
intentionally replaces the former export-only generic 403 for invalid tokens.

`admin_runs()` explicitly selects `run_id`, `app_id`, `started_at`,
`fetched_count`, `inserted_count`, and `status`, ordered by descending run ID with
the existing 100-row limit. Viewer responses contain exactly those six fields.
Operators receive the same safe operational counts/status rather than unchecked
free-text `message` values. This keeps maintenance visibility without creating a
new raw-diagnostic response. No history storage fields were removed or rewritten.
Operator database exports still contain the complete stored database and need
appropriate custody after download.

## Configuration and local use

`app/config.py` reads `SCIENCIA_VIEWER_TOKEN` and `SCIENCIA_OPERATOR_TOKEN` from
the environment at process startup. There are no built-in role credentials.
Configure two independently generated secrets privately, using nonempty Bearer
characters (letters, digits, `.`, `_`, `~`, `+`, `/`, `-`, with optional trailing
`=`). Missing, malformed, or identical values invalidate the whole pair: neither
role is authorized until configuration is corrected and the process restarted.

Use the [README setup and header examples](../README.md#install-and-start).
All protected requests use `Authorization: Bearer <ROLE_TOKEN>` with one space;
the scheme is case-insensitive. A normal browser visit lacks that header and is
rejected. Even an Operator's HTML form does not automatically supply a header;
a header-capable client can perform the full import/read/export workflow.
Viewer HTML omits import controls, while the server independently rejects direct
Viewer import requests. No secret is placed in HTML or styles.

The previous `INTERNAL_EXPORT_TOKEN` configuration and export-specific check
have been removed. Only Operator authorization reaches `export_db()`. The old
shared value cannot replace an Operator credential, and URL `token` parameters
are ignored for authorization, including when paired with invalid headers.

Application logs still record method, path, and status without query values or
headers. The provided local server removes query strings from ordinary access
records and drops raw parser diagnostics before writing protocol errors. These
protections remain necessary for rejected requests and obsolete URL clients.

## Verification

The [recorded run](evidence/access-control/runs/20261105T220103622742Z/run-summary.json)
on 5 November 2026 (UTC) tested uncommitted changes based on `9330b11`.
Pre/post SHA-256 hashes identify the actual source, fixture, and tests; they are
not a claim that the baseline commit already contained these changes.

- Search: 12 methods passed, retaining full-row comparisons, combination filters,
  apostrophes, wildcard behavior, sorting/limit, and both historical input cases.
- Access boundaries: 10 methods passed. They check every protected route against
  absent/invalid credentials, both roles' readable content, denied writes,
  Operator insertion/download, exact history fields, forged role claims,
  retired-token rejection, invalid configuration, HEAD/OPTIONS, static limits,
  and raw application-log contents.
- Export and server logs: 5 methods passed (3 interface/application-log methods,
  1 actual server method, 1 protocol-parser method). The export credential matrix
  has 17 request combinations, including Viewer denial; combinations are not
  additional test methods. Downloads were saved and opened as valid SQLite files
  with three apps, nine reviews, three history rows, and expected review mappings.

All groups exited zero, with no failures, errors, or skips in the recorded run.
Tests copy the app and synthetic fixture to temporary directories and create
independent databases/logs. One access test resets only its own test database to
show that an Operator really inserts records. Viewer/invalid import denials leave
review and history counts unchanged. Real servers bind only to loopback through
`run_local_server()` and are stopped by test cleanup.

Log assertions inspect raw application logs, dedicated Werkzeug logs, and console
output before temporary cleanup. They reject Viewer, Operator, invalid, and legacy
test values and their encoded forms, while requiring non-sensitive request
records with expected statuses. The parsing regression still requires a real
protocol 400 with a useful standard error record. Public evidence contains test
results, not raw logs, database attachments, or random credentials.

Commands, outputs, and hashes are in the
[evidence guide](evidence/access-control/README.md), together
with notes on the earlier development checks. Existing project database and
application-log bytes were unchanged across the recorded run.

## Remaining scope

A role credential identifies a permission class, not a named person. Anyone
holding an Operator credential has its authority; local storage, distribution,
and rotation remain the maintainer's responsibility. Download retention is not
enforced. The service remains a local development
sandbox, including its existing debug settings, not a production identity design.
The server-log protection applies to the supplied local startup path; other
servers, proxies, browsers, and untested error paths require separate review.
Earlier reports and scripts retain their historical pre-role expectations and
are not current acceptance tests. These targeted regressions do not cover every
security issue.
