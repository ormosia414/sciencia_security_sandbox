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

The tested source is an uncommitted working tree based on
`c61504d80935fba0ab60abe0330a3712518425b4`, not the baseline commit alone.
The latest run records hashes of nine source, fixture, and test files before
and after execution; these match the reviewed files. Use the
[evidence guide](evidence/security-remediation/README.md) to reproduce the tests
or distinguish these results from older runs. The results here come from the
saved run, not a new execution during this language edit.

## Proposed permissions — not implemented

I propose a simple Viewer/Operator model for the four operations. **Viewer** is
for named reviewers or analysts who need to analyze approved review data.
**Operator** is for maintainers responsible for imports and backups. This keeps
data changes and backups separate from read-only analysis if the sandbox is shared.
These permissions are proposed and are not enforced by the current application.
The proposal assumes both roles may read all applications; filtering by `app_id`
is not a user-access boundary.

| Operation | Unauthenticated | Viewer | Operator |
|---|---|---|---|
| Import reviews | Deny: changes data and history. | Deny: outside a read-only role. | Allow: responsible for ingestion. |
| Read import history | Deny: requires an approved recipient. | Allow non-sensitive summaries: explains data freshness and counts. | Allow: supports diagnosis and auditing. |
| Export CSV | Deny: bulk reading needs approval. | Allow: supports analysis of approved review data. | Allow: supports checking and approved extracts. |
| Export full database | Deny: no approved backup authority. | Deny: exceeds the review-extract role. | Allow: supports controlled backup and maintenance. |

CSV contains review fields and ingestion timestamps. A full database also gives
the recipient the schema, app mappings, and full history. I recommend limiting
that broader download to Operators. Viewer history access would require messages
and other returned fields to exclude credentials, raw exceptions, and sensitive
operational detail; unsuitable fields would need exclusion or redaction.
The existing shared export token authorizes one operation. It cannot identify
a person or establish membership of either role.

**Decisions to confirm.** Agree who receives each role, whether approved users
may read all apps, and whether Viewers should export CSV and read non-sensitive
history summaries. A single learner's local workflow may justify an explicit
exception to default unauthenticated denial. Operator-only database backups and
the specific history fields available to Viewers also need agreement.

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
