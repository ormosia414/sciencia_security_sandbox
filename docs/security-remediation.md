# Search and Export Remediation

Sciencia AI Review Intelligence Sandbox

Author: Phoebe Zhang

## Task and result

The search/export repair stage addressed two findings from the local assessment:
search input could change SQL conditions, and database-export credentials appeared
in URLs and logs. Parameter binding kept search values separate from SQL, while
header-based credentials and changes to application and server logging removed
the tested exposure paths. Normal search and database downloads still worked.

Role-based access control was completed afterward. The current role rules,
credential configuration, and role-aware verification are described in
[Access control](access-control.md). The results below belong to the earlier
search/export repair stage.

## Search: separate values from SQL instructions

In the [earlier assessment](security-assessment.md), both recorded injection
inputs changed filtering and returned all nine sample reviews. The original
`reviews()` inserted caller values directly into SQL strings, allowing input to
be interpreted as part of the query rather than only as a value.

The repair in [app/app.py](../app/app.py) changed the route to build SQL from fixed
fragments and pass both `app_id` and the `LIKE` pattern separately to
`execute(sql, params)`.
The query structure stays fixed even when an input contains quotes or SQL-looking
text. The change applied to every search value, without character-blocking rules
or special cases for the two known test strings.

The regressions compared complete returned rows, including IDs, application IDs,
fields, and order. The unfiltered query returned nine reviews; Focus returned
its three, and an unknown application returned none. `useful` returned `focus-001`
and `travel-003`; adding the Focus filter returned only `focus-001`. Travel plus
`summaries` returned none, although the keyword alone found `focus-001`. A keyword
with no match returned an empty list. Ordinary apostrophes worked in a synthetic
review and app ID. Both historical injection inputs returned empty lists after
the repair, followed by successful normal queries.

Existing `%` and `_` wildcard semantics, descending review dates, the 200-row
limit, and the JSON field set were retained and tested. Parameter binding protects
SQL structure; it does not assign permissions. The original unfiltered endpoint
already exposed all nine samples to the same caller, so the earlier filter
manipulation did not demonstrate additional user privileges.

## Export credentials and logs: protect the complete request path

The earlier implementation accepted a token in the export URL. The assessment
script found that value in application and server logs, then used it from a new
client to download the database. A header would still expose the credential if
a logger copied its value, so the logging paths also needed to change.

At this stage, `export_db()` directly compared the shared credential supplied in
`Authorization: Bearer <EXPORT_TOKEN>` with the configured export token. The
parser accepted a case-insensitive Bearer scheme and required one space followed
by a nonempty token. Requests with missing, incorrect, empty, or malformed
credentials returned the existing 403 response with a generic error in the tests.
The repaired route no longer accepted the URL `token` parameter for authorization,
including when a header was missing or incorrect. A valid header worked even with
an irrelevant legacy query value. The tests saved the accepted downloads and
opened them as SQLite files.
They contained the expected three apps, nine reviews, and three history rows,
with the expected review ID/app mappings.

Clients had to replace query tokens with the header. An ordinary browser link
alone could not supply it. The [current usage example](../README.md#database-export)
uses the same header mechanism with the later Operator credential.

The repair changed three logging paths before records were written:

- `record_request()` recorded method, path, and response status, without headers
  or query values.
- `CredentialSafeRequestHandler.log_request()` removed the query string before
  Werkzeug wrote a normal access record. This covered valid HTTP requests carrying
  incorrect credentials or obsolete URL tokens.
- HTTP parsing can fail before Flask runs. The standard parser may pass a raw
  request line to `send_error()`, which then reaches the inherited error logger.
  The repaired handler passed only the status code to the base implementation,
  so the error log and response used the standard reason instead of the supplied
  diagnostic text.

The ordinary live-server test checked raw application logs, Werkzeug records, and
console output for random credentials and their encoded forms. It also required
a log record with the expected status for each request, preventing an empty log
from satisfying the check. A separate regression sent one fixed malformed request
containing a random legacy-query marker. It required a protocol 400, no Flask
export-request record, and a retained `code 400, message Bad Request` error record
without the marker or raw request line.

The [same parser test failed before the patch](evidence/security-remediation/runs/20261102T200332547810Z-before-parser-patch/parser-error.output.txt)
when the raw server log contained the encoded marker. It passed afterward without
changing its expectation. This supports the repair for that parsing path;
other server exceptions were not tested. The repaired logs retained request
outcomes and standard error categories while omitting query values and raw
diagnostic details that could copy credentials.

## Verification summary

The [final pre-role recorded run](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/run-summary.json)
identifies the search/export repair snapshot before role enforcement:

| Test group | Test methods | Result | Actual output |
|---|---:|---|---|
| Search | 12 | PASS | [Search](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/search.output.txt) |
| Export interface/application log | 3 | PASS | [Export client](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/export-client.output.txt) |
| Ordinary real-server log | 1 | PASS | [Live server](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/live-server.output.txt) |
| HTTP parsing-error log | 1 | PASS | [Parser error](evidence/security-remediation/runs/20261102T200429152769Z-after-parser-patch/parser-error.output.txt) |

All four groups exited with status zero, with no failures, errors, or skips.
The export methods exercised a 16-combination credential matrix; those combinations
are not additional test methods. Repeated runs are not counted as new tests.

Tests used temporary application copies, independent databases/logs, and synthetic
records. Interface checks used Flask's test client; the two server groups used the
provided `run_local_server()` on loopback and stopped their owned services. Log
assertions inspected raw content before cleanup, not publicly sanitized copies.

At test execution, the repairs were uncommitted changes based on
`c61504d80935fba0ab60abe0330a3712518425b4`. They were later committed in
`c7a64f2fb187697131bc585714b863f4ab15b632`. That run's pre/post hashes
match all nine listed source, fixture, and test files in that delivery commit
before role enforcement. This connects the tested snapshot to the committed
repairs; the tests did not run against a commit that was created afterward.
The comparison concerns the listed files, not every document or evidence file.
The [evidence guide](evidence/security-remediation/README.md) provides reproduction
commands and distinguishes these results from older runs.

## Permissions design and subsequent implementation

The repair stage still had no role checks. I proposed Viewer for approved
reviewers and analysts, and Operator for maintainers handling imports and backups.
The design gave Operator all Viewer reading and CSV permissions, then added
import and full-database export. Both roles would read all apps, with `app_id`
serving only as a filter. It covered the homepage, review search, statistics,
history, exports, and the limited public health/static and method-only OPTIONS
exceptions.

The design distinguished a review extract from a maintenance download. CSV
contained review fields and ingestion timestamps; a full database also included
schema, app mappings, and complete import history. That broader scope supported
Operator-only database downloads. At the time, `admin_runs()` used `SELECT *` and
returned `message`. The proposal limited Viewer history to six named fields but
allowed the possibility of additional safe maintenance messages for Operators.
That was a design option, not a field restriction already enforced by the code.

The model was later approved and implemented. The final implementation gives
**both roles the same six history fields**: `run_id`, `app_id`, `started_at`,
`fetched_count`, `inserted_count`, and `status`. It excludes free-text messages
for both roles rather than adding an Operator diagnostic response. Operator
inherits Viewer permissions, and server-configured role credentials determine
the caller's role. The old shared export credential no longer offers an
independent authorization path: database export requires Operator permission.

The [implemented permission table](access-control.md#implemented-rules) is the
single reference for current route rules, including HEAD and OPTIONS. Its
[verification section](access-control.md#verification) records the later tests;
those results are separate from the search/export-only run above. Neither
hiding a button nor a client-supplied role declaration can replace server checks.

## Protection boundary

The logging repair covered the provided local startup entry point and
`run_local_server()`. Other launchers, servers, proxies, and browsers were outside
that verification, as were other server-error paths. The application remains a
local development sandbox with demo/debug settings.

Old logs and downloaded copies do not disappear when code is fixed. Download
recipients remain responsible for storage and retention; an export endpoint
cannot control how they keep the received file. Role enforcement has since been
completed, while these local-use and copy-handling limits remain.
