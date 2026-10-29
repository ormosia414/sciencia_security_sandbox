# Assessment Evidence Guide

This guide supports the [focused assessment](../../security-assessment.md).
It records where to find the observations and how the scripted tests were run.
The JSON, logs, and executed script are retained unchanged; this editorial review
did not rerun tests.

## Run, environment, and reproduction

The completed run is
[20261027T124512135714Z/results.json](20261027T124512135714Z/results.json),
with a [runtime log](20261027T124512135714Z/runtime-log.redacted.txt) and
[console capture](20261027T124512135714Z/server-console.redacted.txt).
Its application source commit is `0236b55eefb1a0922d1290fd6c17e5be256f5737`.
Recorded times are **2026-10-27 12:45:12.135714–12:45:12.814374 UTC**.
The environment used Python 3.9.6, Flask 3.0.3, and Werkzeug 3.1.9; the SQLite
version and configuration flags are also recorded in the JSON. No dependencies
were installed. There are 20 recorded HTTP requests, excluding readiness polling.

The [assessment script](assess_local.py) uses the existing environment:

```sh
.venv/bin/python -B docs/evidence/security-assessment/assess_local.py
```

Each invocation copies tracked project files to a fresh private temporary
location and checks that no source database or log was copied. Application and
configuration bytes are preserved. The copy creates its own empty database and
logs; debug and request logging keep their configured values. A small launcher
disables the reloader and listens only on `127.0.0.1`. HTTP proxies are disabled.
The normal homepage/form control is scripted HTTP, not manual browser activity.
Read-only database connections inspect the copy or downloaded attachments.
Only the script's owned server is stopped.

If runtime files unexpectedly become tracked in a future copy, the empty-copy
assertion stops execution rather than reusing them. This method does not copy or
write the original project's runtime database or logs.

## Data progression and credential-free operations

The completed scenarios use one database without an intermediate reset:

1. `initial_state` contains zero applications, reviews, and history rows.
2. `normal-homepage` and `normal-form-import` load the page and submit its Focus
   selection. `observations.normal_import` records the transition to one app,
   three reviews, and one history row. `normal-history`, `normal-csv`, and
   `observations.normal_csv` record the three-review normal control.
3. `credential-free-direct-import` submits Notes from a new client.
   `observations.credential_free_import` records the transition from three to
   six reviews and from one to two history rows. `credential-free-history`
   returns both runs. `credential-free-csv` and
   `observations.credential_free_csv` contain six reviews, three per imported
   app; Travel contributes zero. The downloaded CSV was reopened and parsed,
   and its sample fields matched the fixture. The request records identify the
   clients and absence of supplied cookies, sessions, or authorization headers.
4. `prepare-third-app` imports Travel. The check `All samples stored` records
   three apps, nine reviews, and three history rows. All subsequent search and
   token requests use that state, without resetting the database.

Six CSV rows and nine database-download rows therefore describe different
stages of one run. The normal control was also credential-free; it establishes
the expected workflow, not an authenticated user for comparison.

## Search controls and probes

The following labels identify records in the completed JSON:

- `all-review-control`: nine reviews without filters.
- `real-app-control`: three Focus reviews; `missing-app-control`: zero reviews.
- `matching-keyword-control`: `q=useful` globally returns two IDs, `travel-003`
  and `focus-001`. No Focus-scoped `useful` request is recorded in this
  assessment; its count must not be presented as a result of this run.
- `absent-keyword-control` and `scoped-absent-keyword-control`:
  `q=unfindableword` returns zero globally and zero with the Focus app ID.
- `app-id-condition-probe` and `keyword-condition-probe`: exact input parameters,
  encoded URLs, full response JSON, record IDs, application sets, and expected
  empty results are retained. Both actually return all nine sample IDs.
  The keyword probe returns reviews from outside the accompanying Focus filter.

`observations.sql_read_only_state` contains identical before/after counts and
hashes of all three tables' contents. The unfiltered control also shows why
changing a filter did not demonstrate extra user privileges in this application.
Source explanation: `app/app.py`, `reviews()`, lines 89–103; the contrasting
parameterized app filter is in `summary()` at lines 106–113.

## Token logging and download

`db-missing-token` and `db-incorrect-token` record 403 responses and
`{"error":"invalid token"}` bodies. `db-valid-demo-token` records a successful
SQLite attachment. `observations.token_in_logs` includes the application's query
dictionary, a server access URL, and the token extracted from that dictionary.
These records are also visible in the linked runtime log.

`db-log-token-replay` records the fresh client's successful response after using
that extracted token. `observations.replay_download` records the saved file's
hash, successful SQLite integrity check, and application table counts: three
apps, nine reviews, and three history rows. The check `Read-only exports leave
database unchanged` compares against the same nine-review baseline.

`<EXPORT_TOKEN>` consistently links the valid control, log extraction, and
replay. The intentionally incorrect demo input is not an accepted credential.
Source explanation: `app/app.py`, `record_request()` and `before_request()`,
lines 36–43; `export_db()`, lines 148–154; and `LOG_REQUEST_DETAILS` in
`app/config.py`. Fixed-token reuse alone is not treated as a vulnerability.
The concern is the additional credential exposure through logs. Neither the
request records nor the tester's log access proves other users' OS permissions.

## Preservation, execution notes, and evidence handling

`source_hashes`, `copied_tracked_hashes`, the two original-file preservation
checks, and `owned_server_stopped` record copy identity, original-file
preservation, and server shutdown. Raw downloads and runtime material remain
in private local storage, outside the review attachments.

The [first attempt](20261027T124303401494Z/results.json) is `INCOMPLETE`:
binding a socket raised `PermissionError` before a server launch or any HTTP
request. Its two PASS records concern original-file preservation, not security
findings. A separately authorized retry created a different temporary copy and
produced the completed run above.

The completed console contains a resource-tracker warning about a semaphore at
shutdown. Its cause was not investigated. The owned server had stopped, all
recorded response/content expectations matched, and original file hashes were
unchanged. The warning is retained, without classifying it as an application
vulnerability or treating it as a failed test of the three hypotheses.

JSON timestamps are UTC; runtime log timestamps use the runtime's local clock.
PASS means the stated expectation matched an observation, including expectations
that confirm unsafe behavior. It is not a passed security requirement.

The existing recursive sanitizer replaces local environment identifiers and
configured credentials. Public placeholders preserve associations, input values,
and comparison relationships. Unpublished originals remain under the ignored
`.private-verification/` directory. These attachments do not establish remote
reachability, OS log-read permissions, or the intended authorization policy.
