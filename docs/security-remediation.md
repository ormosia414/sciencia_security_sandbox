# Search and Export Remediation

Sciencia AI Review Intelligence Sandbox

Author: Phoebe Zhang

## Task and result

The local assessment confirmed that search input could change SQL conditions
and that the database-export credential appeared in URLs and logs. The search
and export changes address these two problems in the teaching sandbox.

Search now treats input as bound values and retains normal filtering. Database
export accepts a Bearer request header. Tests checked that the application and
server logs omit credentials for ordinary requests and the identified protocol
error. For shared use, I recommend separating review analysis from import and
backup responsibilities.

## Search: separate values from SQL instructions

In the [earlier assessment](security-assessment.md), both recorded injection
inputs changed filtering and returned all nine sample reviews. The original
`reviews()` inserted caller values directly into SQL strings, allowing input to
be interpreted as part of the query rather than only as a value.

In [app/app.py](../app/app.py), the route now builds SQL from fixed fragments and
passes both `app_id` and the `LIKE` pattern separately to `execute(sql, params)`.
The query structure stays fixed even when an input contains quotes or SQL-looking
text. The change applies to every search value, without character-blocking rules
or special cases for the two known test strings.

The regressions compare complete returned rows, including IDs, application IDs,
fields, and order. The unfiltered query still returns nine reviews; Focus returns
its three, and an unknown application returns none. `useful` returns `focus-001`
and `travel-003`; adding the Focus filter returns only `focus-001`. Travel plus
`summaries` returns none, although the keyword alone finds `focus-001`. A keyword
with no match returns an empty list. Ordinary apostrophes work in a synthetic
review and app ID. Both historical injection inputs now return empty lists,
followed by successful normal queries.

Existing `%` and `_` wildcard semantics, descending review dates, the 200-row
limit, and the JSON field set are retained and tested. Parameter binding protects
SQL structure; it does not assign permissions. The original unfiltered endpoint
already exposed all nine samples to the same caller, so the earlier filter
manipulation did not demonstrate additional user privileges.

## Export credentials and logs: protect the complete request path

The earlier implementation accepted a token in the export URL. The assessment
script found that value in application and server logs, then used it from a new
client to download the database. A header would still expose the credential if
a logger copied its value, so the logging paths also needed to change.

`export_db()` now accepts `Authorization: Bearer <EXPORT_TOKEN>` and compares
its value with the configured token. The Bearer scheme is case-insensitive
and requires one space followed by a nonempty token. Requests with missing,
incorrect, empty, or malformed credentials returned the existing 403 response
with a generic error in the tests.
The URL `token` parameter never grants permission, including when a header is
missing or incorrect. A valid header works even with an irrelevant legacy query
value. The tests saved the accepted downloads and opened them as SQLite files.
They contained the expected three apps, nine reviews, and three history rows,
with the expected review ID/app mappings.

Old clients must supply the header instead of a query token. An ordinary browser
link alone no longer supplies the required credential; the
[current usage example](../README.md#database-export) shows a header-capable
client.

The logging changes take effect before records are written:

- `record_request()` records method, path, and response status, without headers
  or query values.
- `CredentialSafeRequestHandler.log_request()` removes the query string before
  Werkzeug writes a normal access record. This also covers valid HTTP requests
  that carry incorrect credentials or obsolete URL tokens.
- HTTP parsing can fail before Flask runs. The standard parser may pass a raw
  request line to `send_error()`, which then reaches the inherited error logger.
  The local handler now passes only the status code to the base implementation,
  so the error log and response use the standard reason instead of the supplied
  diagnostic text.

The ordinary live-server test checks raw application logs, Werkzeug records, and
console output for random credentials and their encoded forms. It also checks
that each request has a log record with the expected status, so an empty log
cannot satisfy the check.
A separate regression sends one fixed malformed request containing a random
legacy-query marker. It requires a protocol 400, no Flask export-request record,
and a retained `code 400, message Bad Request` error record without the marker
or raw request line.

The [same parser test failed before the patch](evidence/security-remediation/runs/20261102T200332547810Z-before-parser-patch/parser-error.output.txt)
when the raw server log contained the encoded marker. It passed afterward without
changing its expectation. This supports the repair for that parsing path;
other server exceptions were not tested. The logs retain request outcomes and
standard error categories. Query values and raw diagnostic details are omitted
to avoid copying credentials.

## Verification summary

The [latest recorded run](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/run-summary.json)
corresponds to the current code and tests:

| Test group | Test methods | Result | Actual output |
|---|---:|---|---|
| Search | 12 | PASS | [Search](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/search.output.txt) |
| Export interface/application log | 3 | PASS | [Export client](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/export-client.output.txt) |
| Ordinary real-server log | 1 | PASS | [Live server](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/live-server.output.txt) |
| HTTP parsing-error log | 1 | PASS | [Parser error](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/parser-error.output.txt) |

All four groups exited with status zero, with no failures, errors, or skips.
The export methods exercise a 16-combination credential matrix; those combinations
are not additional test methods. Repeated runs are not counted as new tests.

Tests use temporary application copies, independent databases/logs, and synthetic
records. Interface checks use Flask's test client; the two server groups use the
provided `run_local_server()` on loopback and stop their owned services. Log
assertions inspect raw content before cleanup, not publicly sanitized copies.

At test execution, the repairs were uncommitted changes based on
`c61504d80935fba0ab60abe0330a3712518425b4`. They were later committed in
`c7a64f2fb187697131bc585714b863f4ab15b632`. The latest run's pre/post hashes
match all nine listed source, fixture, and test files in that delivery commit
and the current checkout. This connects the tested snapshot to the committed
repairs; the tests did not run against a commit that was created afterward.
The comparison concerns the listed files, not every document or evidence file.
Use the
[evidence guide](evidence/security-remediation/README.md) to reproduce the tests
or distinguish these results from older runs.

## Proposed permissions — not implemented

The Viewer/Operator direction has been accepted. **Viewer** is for approved
reviewers or analysts; **Operator** is for maintainers responsible for imports
and backups. Operator inherits all Viewer reading and CSV permissions, then adds
import and full-database export. Both roles may read every app: `app_id` is only
a filter, with no per-app permission model. The route rules and field choices
below extend that direction and still need confirmation.
These permissions are proposed and are not enforced by the current application.

I propose the following rules for all current routes in
[app/app.py](../app/app.py), including Flask's static-file route. Unauthenticated
callers and callers whose role cannot be recognized are denied protected
operations by default. Minimal health information and non-sensitive styles are
the only public content exceptions. Automatic `OPTIONS` has a separate, limited
protocol-level exception described below.

| HTTP method and path | Unauthenticated / unknown role | Viewer | Operator | Reason and data scope |
|---|---|---|---|---|
| `GET /` | Deny | Allow | Allow | The homepage reads per-app review counts and shows available operations. |
| `GET /reviews` | Deny | Allow | Allow | Read reviews across all apps, optionally filtered by `app_id` and `q`; newest first, at most 200 rows. |
| `GET /analysis/summary` | Deny | Allow | Allow | Read counts, average ratings, and common terms for one or all apps. Aggregates still reveal stored data. |
| `POST /ingest` | Deny | Deny | Allow | Changes stored data and adds an import-history row. |
| `GET /admin/runs` | Deny | Allow summary fields only | Allow maintenance history | Viewers need freshness and counts; Operators also need diagnostic context. See field limits below. |
| `GET /export.csv` | Deny | Allow | Allow | Export all stored reviews and ingestion timestamps, without applying earlier search filters. |
| `GET /export.db` | Deny | Deny | Allow | Download the whole database, including schema, app mappings, and full history, for controlled backup. |
| `GET /health` | Allow | Allow | Allow | Current fields are `status: "ok"` and `time` (UTC). They provide minimal liveness information, not database or dependency health. |
| `GET /static/<path:filename>` | Allow non-sensitive styles only | Same | Same | The current template loads `/static/style.css`. This exception does not approve future sensitive static files. |

The read routes also support Flask's implicit `HEAD`; it must require the same
permission as the corresponding `GET`, even without a response body. As a limited
protocol-level exception, automatic `OPTIONS` may return supported-method
information without authentication, but must not return business data or execute
an operation. These framework behaviors must not create an alternate access path.

Search and CSV expose the same approved review collection to both roles, but
their output is not identical: search filters and caps results, while CSV exports
all reviews and includes `ingested_at`. A full database additionally contains
schema, app mappings, and full import history. That broader maintenance scope is
why I recommend Operator-only database downloads.

For Viewer history summaries, I propose an explicit allowlist: `run_id`, `app_id`,
`started_at`, `fetched_count`, `inserted_count`, and `status`. The current
`admin_runs()` uses `SELECT *` and also returns `message`. A future implementation
must select the summary fields for Viewers instead of forwarding every column;
free-text messages and raw exceptions should not enter that response. Operators
may receive maintenance messages, but credentials and sensitive raw diagnostics
should be excluded from their responses too.

Every rule must be enforced on the server, including direct HTTP requests.
Hiding an import button from Viewers would improve the interface but cannot
authorize the route. The current shared Bearer token proves possession of one
operation credential, not a person's identity or role. When role checks are
implemented, database export must require Operator permission; the shared token
must not remain an alternative route around that check. Whether to retain it as
an additional requirement or replace it needs agreement, without adding roles.

**Decisions to confirm.** Confirm who receives each role; the all-app read scope
and Viewer CSV access; the proposed history allowlist and Operator message scope;
and the limited public health/static exceptions. Also decide how future Operator
authorization will replace or supplement the shared export credential. These are
design decisions for the next implementation, not changes to current access.

Recipients and retention periods for downloaded copies need a clear policy.
The endpoint transfers a file; it does not enforce how the recipient stores or
keeps that copy.

## Protection boundary and next step

The log changes apply to the provided local startup entry point and
`run_local_server()`. Other launchers, servers, proxies, and browsers need their
own configuration and were not assessed here. Old logs and downloaded copies do
not disappear when code is fixed. The application still uses demo configuration
and development/debug settings.

I recommend agreeing on the intended users and download responsibilities next.
