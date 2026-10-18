# Normal Function Verification Results

Verification runs: 2026-10-17. Final delivery review: 2026-10-18.
Target: the current local `sciencia_security_sandbox`.

## Results and methodology

The latest clean-copy reproduction run, `20261017T220551322403Z-80538566`, recorded
**68 PASS, 0 FAIL, and 1 N/A (NOT_APPLICABLE)**.
Totals are calculated from individual check records, not a fixed target count.
The existing smoke-test function passed by direct Python invocation; no pytest
run was performed.

Two runs are retained separately:

- **Historical functional verification (2026-10-17):**
  [results](evidence/normal-verification.json) and
  [redacted log](evidence/runtime-log.redacted.txt). This unchanged evidence
  records 66 PASS and 0 FAIL. Its original source tree contained a runtime database.
- **Clean-copy reproduction (2026-10-17, UTC):**
  [results](evidence/runs/20261017T220551322403Z-80538566/normal-verification.json),
  [redacted log](evidence/runs/20261017T220551322403Z-80538566/runtime-log.redacted.txt), and
  [clean-copy checks](evidence/runs/20261017T220551322403Z-80538566/clean-copy-check.json).
  Started at `2026-10-17T22:05:51.322403+00:00` and completed at `2026-10-17T22:05:51.742914+00:00`.
  The source copy contained neither `data/reviews.db` nor `logs/app.log` before
  or after execution. Database inspection was **NOT_APPLICABLE: no existing
  runtime database**, not a passing database inspection.

Comparison of the historical and latest JSON check lists identifies these additions:

- **Original database presence unchanged — PASS:** `expected=false`,
  `actual=false`; the absent source database was not created.
- **Original log presence unchanged — PASS:** `expected=false`, `actual=false`;
  the absent source log was not created.
- **Existing runtime database inspection — N/A (NOT_APPLICABLE):** no existing
  runtime database was available. This inspection record is not counted as PASS.

No historical check was removed. The two added PASS records account for the
increase from 66 to 68 PASS; the additional N/A record is reported separately.
The latest run also corrects CSV parsing to reopen the saved download. Existing
source/configuration and historical evidence were preserved. No application
business code was changed.

The review uses three evidence categories:

- **Source-code review:** inspection of the current implementation, configuration,
  database schema, sample data, tests, and documentation.
- **Initial manual observation:** earlier checks of the application page, imports,
  queries, statistics, ingestion history, and CSV export, including inspection of
  responses, downloaded CSV data, and local logs.
- **Automated functional verification:** subsequent execution of
  `docs/verify_normal.py` in a temporary project copy with an initially empty
  database. The script verified representative normal scenarios across all
  functional categories against fixture and database contents. Check totals are
  derived from each run's recorded results.

The functional results below were confirmed by both recorded runs, except where
a run-specific difference is stated. Initial manual observation provides context
but is not counted as automated evidence. HTTP 200
responses alone were insufficient: record values, counts, ordering, statistics,
and export contents were compared with expected results. Successful normal
functionality does not establish application security.

- [Verification script](verify_normal.py): creates a temporary source copy and
  empty database without importing the original application into its process.

## Environment and isolation

- Project root: the `sciencia_security_sandbox` directory. All paths in this
  report are relative to the project root unless stated otherwise.
- Existing interpreter: `.venv/bin/python`, Python **3.9.6**, macOS **26.6.2 arm64**.
- SQLite **3.51.0**; Flask **3.0.3**; Werkzeug **3.1.9**; Jinja2 **3.1.6**;
  MarkupSafe **3.0.3**; itsdangerous **2.2.0**; click **8.1.8**; blinker **1.9.0**.
- No dependency installation. `pytest` is absent, confirmed by module discovery;
  `requirements.txt` declares only Flask.
- The historical source review found no commits on Git branch `main`. The clean
  reproduction copy omitted `.git`; its source state is identified by file hashes.
- Historical server URL: `http://127.0.0.1:64534`. Latest reproduction URL:
  `http://127.0.0.1:52411`. Each run requests a free loopback port. Its JSON records
  the exact temporary directory and startup command.
- `verification_date` is derived from the actual UTC start time, recorded as
  `started_at`; `verification_timezone` is explicitly `UTC`. `recorded_utc`
  records completion time. Dates are no longer fixed in the script.
- The runner copies `app/`, `tests/`, `requirements.txt`, and provider JSON.
  Caches/OS metadata are excluded. The original database and log are not copied;
  new runtime files are created only under the temporary directory.
- Copied application/configuration bytes matched originals. `ENABLE_DEBUG=True`
  and `LOG_REQUEST_DETAILS=True` were preserved. The wrapper initializes the
  copied database, then calls `app.app.run(host='127.0.0.1', port=selected_port,
  debug=app.ENABLE_DEBUG, use_reloader=False)`. Disabling the reloader is a launch
  choice, not a source/configuration edit. The wrapper is included in the JSON.
- The verification server used a free loopback port rather than requiring port
  5000. The script terminated its own server subprocess in a `finally` block.
- Each run compared source non-doc file hashes before and after execution.
  Existing files were unchanged. The clean run also explicitly checked that its
  absent source database and log remained absent. Only the separate runtime
  directory received a new database, logs, and download files.

Reproduce from the project root with the existing environment:

```sh
.venv/bin/python -B docs/verify_normal.py
```

The runner writes new files under `docs/evidence/runs/<run_id>/`; a UTC timestamp
and random suffix identify each run. Existing evidence is not overwritten. It
exits nonzero for a recorded failure and retains private runtime files separately
under the OS temporary root. An absent source database is never opened or created;
its inspection is marked NOT_APPLICABLE. Errors opening an existing database
remain errors and are not silently treated as absence.
It uses Python's HTTP client with proxies disabled and only `127.0.0.1`. Token
values are read locally and are not put in shell commands or shared output.
Do not share the temporary directory's raw logs or database/CSV downloads.

## Steps, expected results, and actual results

All recorded requests below returned HTTP 200. This evidence covers the stated
normal scenarios, not all possible application behavior. Unknown-app 404,
invalid-token 403, malformed data, and other error paths were not exercised by
these runs; any description of them is from Source-code review. Content checks
are described separately.
Exact expected/actual values and request order are in each run's JSON evidence.

### 1. Fixture, clean start, homepage, and CSS — PASS

Expected: fixture keys match the UI mapping, rows have expected fields and unique
IDs, and a new database contains zero apps, reviews, and runs.

Actual: **3 applications, 9 records**, 3 per app. Every row has `review_id`,
integer `rating`, `text`, `created_at`, `app_version`, `user_region`. All supplied
string types, timezone-aware parseable dates, and ratings from 1 to 5 were checked.
These are verifier checks, not application-side validation guarantees.

| Provider key | Display name | Review IDs | Ratings |
|---|---|---|---|
| `com.sciencia.focus` | Focus AI | `focus-001`, `focus-002`, `focus-003` | 5, 2, 4 |
| `com.sciencia.notes` | Smart Notes | `notes-001`, `notes-002`, `notes-003` | 1, 5, 3 |
| `com.sciencia.travel` | Travel Companion | `travel-001`, `travel-002`, `travel-003` | 4, 2, 5 |

Initial table counts were 0/0/0. `GET /` contained the three correct POST forms,
app IDs/names, stylesheet reference, and three zero counts. CSS bytes matched the
source and the content type was `text/css`. After import, the homepage showed
three “3 stored reviews” counts. Served content was checked, not visual layout.

### 2. First and repeated imports — PASS

Expected: first `POST /ingest` for each app fetches/inserts 3; repeating fetches 3,
inserts 0, and adds history without changing review counts.

| Step | App | fetched | inserted | DB apps | DB reviews | DB runs |
|---|---|---|---|---|---|---|
| 1 | Focus | 3 | 3 | 1 | 3 | 1 |
| 2 | Notes | 3 | 3 | 2 | 6 | 2 |
| 3 | Travel | 3 | 3 | 3 | 9 | 3 |
| 4 | Focus repeat | 3 | 0 | 3 | 9 | 4 |
| 5 | Notes repeat | 3 | 0 | 3 | 9 | 5 |
| 6 | Travel repeat | 3 | 0 | 3 | 9 | 6 |

Actual matched each expected step. All nine stored reviews matched every fixture
field, the enclosing app ID, and a populated `ingested_at`. Stored application
names matched `APP_NAMES`. The source fixture remained unchanged.

### 3. Review queries — PASS

Expected results came from fixture text/dates independently of endpoint SQL.
All response fields, values, and descending date order matched.

| Parameters | Expected and actual |
|---|---|
| None | All 9 records, newest first |
| Each of the 3 app IDs | Correct 3 records per app |
| `q=useful` | `travel-003`, `focus-001`, in that order |
| Focus app and `q=useful` | `focus-001` only |
| `q=unfindableword` | Empty JSON list |

Only ordinary keywords were sent; no SQL punctuation probes or attack inputs.

### 4. Independent summary calculations — PASS

Counts/averages came from the fixture. Word counts used an independent dictionary
tally, not the app's `Counter` or summary function. All eight terms, counts, and
the recorded tie order matched. Token length is tested before punctuation stripping.

| Scope | Count | Average | Eight terms in observed order |
|---|---|---|---|
| Focus | 3 | 3.67 | summaries, useful, search, after, latest, update, overall, export (all 1) |
| Notes | 3 | 3.00 | login, prevented, opening, notes, simple, interface, reliable, sync (all 1) |
| Travel | 3 | 3.67 | planner, helpful, clean, saved, itinerary, after, update, useful (all 1) |
| All | 9 | 3.44 | useful (2), after (2), update (2), summaries (1), search (1), latest (1), overall (1), export (1) |

All-app rating sum: 31. Tie order depends on row encounter order; source SQL does
not promise stable tie ordering.

### 5. Ingestion history — PASS

Expected/actual: 6 rows, run IDs **6, 5, 4, 3, 2, 1**. Every row had `run_id`,
`app_id`, `started_at`, `fetched_count`, `inserted_count`, `status`, `message`.
App IDs/counts matched the six imports, status was SUCCESS, completion messages
matched, timestamps parsed, and the full response equalled database history.

### 6. CSV export — PASS

The revised script saves the HTTP attachment, then reopens that file with
`encoding='utf-8'` and `newline=''` and parses it using `csv.reader`. The latest
evidence records `csv.parsed_from=saved_download_file` and the download SHA-256.
The historical script saved the file but parsed the in-memory response bytes;
the earlier report's statement that it parsed the saved copy was inaccurate.
Both runs produced matching CSV content. The expected header was:

```text
review_id,app_id,rating,text,created_at,app_version,user_region,ingested_at
```

There were **9 data rows, 3 per app**, plus the header. All eight field values in
every row matched SQLite after string conversion. Filename was `reviews.csv`
and content type was `text/csv`. The `notes-003` text, **“Works, but notifications
are inconsistent.”**, retained its comma inside one parsed field. Spreadsheet
formula behavior was not tested.

### 7. Database export with the provided demo token — PASS

One normal `GET /export.db` used the provided demo token, read locally from
configuration. Shared request evidence masks its value. No invalid-token attempt
or bypass was made.

The HTTP client saved the database attachment as a separate file, which was
opened read-only with SQLite. All three table definitions and all contents
matched the temporary live database: **3 apps,
9 reviews, 6 runs**. Internal SQLite sequence metadata is additional to the three
application tables. Filename was `reviews.db`; the download's
`PRAGMA integrity_check` returned `ok`.

### 8. Health and existing test — PASS

`GET /health` returned the expected keys, `status=ok`, and a parseable UTC time.
The unchanged `tests/test_smoke.py::test_health` ran in a separate process in the
temporary project, exit code 0, output `test_health: PASS`.

The following command shows the recorded invocation with a portable interpreter
path. Here, `<project-root>` denotes the original project root; the working
directory was the temporary project copy.

```sh
<project-root>/.venv/bin/python -c "import runpy; m=runpy.run_path('tests/test_smoke.py'); m['test_health'](); print('test_health: PASS')"
```

This executes the sole existing test function and assertions. Pytest collection,
plugins, or a broader pytest suite were not run. The one existing test covers
only health; the additional normal HTTP checks covered the other functions.

### 9. Logging, preservation, and shutdown — PASS

Private runtime logs contained server startup messages, application paths/query
dictionaries, and server HTTP method, URL, address, and status records. Ordinary
search parameters appeared. POST form app ID was not in the application detail
record: ingestion showed `args={}`. `record_request()` does not log bodies.

The demo export token appeared in raw query logs. This is an observed
confidentiality concern. For the check **Demo token appears in private raw query
logs**, PASS means that the expected observation occurred, not that a security
requirement was satisfied. The revised evidence marks it `kind=observation` and
includes this interpretation. NOT_APPLICABLE is reported separately from PASS.
Shared evidence masks the value and removes PIN lines if present; both
configuration secret values were checked absent before evidence was saved. The verification server was terminated,
and original non-doc file hashes remained unchanged.

In the historical run, the existing database was inspected read-only: **2 apps,
6 reviews, 2 runs**, plus one sequence row. The clean-copy run had no source
database or log; database inspection was NOT_APPLICABLE and neither file was
created there. Both runs created and used a separate empty runtime database.
Historical source logs contained debugger activation messages. The automated
no-reloader logs contained no debugger activation or PIN line. Historical records
do not establish current server availability.

## Complete project file review inventory

Excluded `.git`, `.venv`, caches, and third-party dependency directories. Baseline
hashes are in the JSON. Script manifest labels such as “Read in full” establish
file access, not technical review by themselves. The source review examined route
checks, SQL construction, transaction behavior, schema constraints, configuration,
and data transformations against the documented flows and recorded outputs.
Hashes establish snapshot identity only. Current executable application, schema,
fixture, and test files match the recorded runtime snapshots; the current verifier
matches the latest executed script hash. The historical empty placeholder
`app/security-notes.md` is now absent; it is not an application dependency and
does not affect those runtime results. Document hashes represent verification-time
snapshots and may differ after report revisions.

| File | Review status |
|---|---|
| `SECURITY_SCOPE.md` | Read fully; local scope and external exclusions followed. |
| `STUDENT_START_HERE.md` | Read fully; six Module 1 deliverable requirements covered. |
| `README.md` | Read fully; setup reviewed; normalization/sentiment wording clarified in main report. |
| `.gitignore` | Read fully; runtime data, venv, caches, and OS metadata exclusions reviewed. |
| `requirements.txt` | Read fully; only Flask declared. |
| `app/app.py` | Read fully; every route/helper, SQL, startup, logging, responses reviewed. |
| `app/db.py` | Read fully; schema, connection flags, paths, transactions reviewed. |
| `app/config.py` | Read fully as local constants; demo values never included in shared output. Flags checked at runtime. |
| `app/templates/index.html` | Read fully; forms, hidden IDs, counts, CSS, endpoint text reviewed. |
| `app/static/style.css` | Read fully; runtime bytes matched. |
| `app/security-notes.md` | Historical snapshot: empty (0 bytes). Currently absent; not required by the application. |
| `data/provider_reviews.json` | Read fully; every app and record checked. |
| `data/reviews.db` | Historical run: all definitions/rows inspected read-only. Clean-copy run: absent; inspection NOT_APPLICABLE; not created. |
| `logs/app.log` | Historical source log reviewed and preserved. Clean-copy source log absent and not created. Separate runtime logs were redacted. |
| `tests/test_smoke.py` | Read fully; sole function executed unchanged in copy. |
| `docs/system-overview.md` | Read fully, updated as formal main document. |
| `docs/system_overview.md` | Original high-level template retained as background. The formal system analysis is `docs/system-overview.md`. |
| `.DS_Store`, `app/.DS_Store` | Inventoried/hashed; OS metadata, not project source. |
| `docs/verify_normal.py` | Revised for optional source database, UTC dates, saved-file CSV parsing, per-run evidence, and explicit observation semantics. Executed in a clean copy. |
| `docs/verification-results.md` | New report checked against runtime evidence. |
| `docs/evidence/normal-verification.json` | Generated/parsed/reviewed; expected/actual checks, versions, and redacted requests. |
| `docs/evidence/runtime-log.redacted.txt` | Historical log retained unchanged. |
| `docs/evidence/runs/<run_id>/` | New results, redacted runtime log, and clean-copy checks; linked above. |

## Verification limitations

- The existing test function passed by direct invocation. Pytest was unavailable,
  so pytest collection and plugins were not exercised.
- Final manual preview inspection confirmed both diagrams display clearly,
  without obvious label overlap, with the correct JSON flow and CSV source.
  This manual diagram observation is separate from the automated run evidence.
  No independent Mermaid parser or rendering tool was run.
- HTTP page and CSS content were checked, but browser layout was not visually
  assessed.
- No attacks, access-control bypasses, concurrency tests, or stress tests were
  performed. Large-input behavior and failure recovery were not tested.
- No check failed in either recorded run. The clean run contains an explicitly
  not-applicable source-database inspection. The totals include functional checks,
  preservation checks, and observations; they are not a security compliance score.
- The historical reproduction defect was a required read-only open of a missing
  source database. The guard and clean-copy run address that case. No corruption
  or permission-error recovery for an existing source database was tested.
- Successful normal behavior does not establish the absence of security defects.

## Final delivery review and submission readiness

The 2026-10-18 review reconciled the current source, script, both JSON result
sets, and their redacted logs without rerunning the application or tests. The
recorded totals remain 66 PASS / 0 FAIL historically and 68 PASS / 0 FAIL / 1 N/A
for the clean copy. No result was changed to fit the report. No script change was
required for the reviewed Module 1 scenarios.

Read-only Git inspection found 13 staged files, no commit, and no configured
remote. The staged set contains the application, sample provider, task/scope
files, requirements, test, `.gitignore`, and the old template. The two formal
reports, verification script, and historical/latest evidence are still untracked;
a commit of the current index alone would omit the main deliverables.
The previously inventoried empty `app/security-notes.md` is currently absent.
It is not an application dependency; its absence and the retained old template
are not delivery blockers.

No virtual environment, cache, OS metadata, runtime database/sidecar, `.env`, or
raw log was found in the staged set. Review of staged and untracked delivery
candidates identified no real credential material, unredacted demo token/secret,
or Debugger PIN. `app/config.py` explicitly marks its values as demo-only and is
suitable to retain. Provider records are the nine sandbox samples; no external
business dataset was identified. Evidence retains local environment paths and
should be handled in the required private repository rather than treated as
anonymous data. Local report links resolve.

Before submission, manually review and stage the formal reports, verifier, and
both evidence sets; inspect the resulting staged diff and file list; then make
the intended commit. Configure a private repository/remote if following the
submission workflow in `STUDENT_START_HERE.md`. Remote visibility has not been
verified because no remote is configured. Staging, commit, repository creation,
push, and sending the repository link remain manual submission steps.
