# Normal Functional Verification

Sciencia AI Review Intelligence Sandbox

Author: Phoebe Zhang

Recorded verification runs: 2026-10-17

## 1. Purpose and evidence

This report documents how normal local behavior was checked and what the results
support. It complements the [system understanding and security analysis](system-overview.md).
The scope was the supplied teaching application and synthetic review data, not
external systems or active security testing.

Three evidence sources are distinguished:

- **Source-code review:** application routes, SQL, schema, configuration, template,
  stylesheet, provider fixture, dependencies, and the existing test were examined
  to understand behavior and identify checks that are absent or only described
  in code.
- **Initial manual observation:** the application page, imports, queries,
  statistics, history, CSV responses, and local logs were inspected manually.
  The final report diagrams were also checked in Markdown preview.
- **Automated functional verification:** `docs/verify_normal.py` sent normal
  loopback HTTP requests against an isolated copy and compared content with
  fixture data, independent calculations, and SQLite records. These checks were
  automated, not a set of manually executed tests.

The retained records show:

| Run | PASS | FAIL | N/A | Evidence |
|---|---|---|---|---|
| Historical functional run | 66 | 0 | Not recorded | [Results](evidence/normal-verification.json), [redacted log](evidence/runtime-log.redacted.txt) |
| Latest clean-copy run | 68 | 0 | 1 | [Results](evidence/runs/20261017T220551322403Z-80538566/normal-verification.json), [redacted log](evidence/runs/20261017T220551322403Z-80538566/runtime-log.redacted.txt), [clean-copy checks](evidence/runs/20261017T220551322403Z-80538566/clean-copy-check.json) |

The latest run adds two passing preservation checks: **Original database presence
unchanged** and **Original log presence unchanged**. Each recorded `false` before
and after execution: the clean source copy had no runtime database or log, and
neither was created there. **Existing runtime database inspection** was N/A
(`NOT_APPLICABLE`) because there was no existing database to inspect. It is not
counted as PASS. No historical check was removed. Public copies of both records
normalize environment identifiers as described in Section 4; the recorded results
and verification-time hashes are retained.

Totals include functional checks, preservation checks, and observations. PASS
means the stated expectation matched the observation; it is not a security
certification. Successful normal behavior does not establish that the application
is secure.

## 2. Environment, isolation, and reproduction

The recorded environment used Python 3.9.6 on macOS 26.6.2 arm64, SQLite 3.51.0,
Flask 3.0.3, Werkzeug 3.1.9, and Jinja2 3.1.6. Additional package versions and exact
normalized launch commands are in the JSON records. Existing dependencies were used; none
were installed for verification.

The script copied the application, tests, requirements, and provider JSON to a
separate temporary runtime directory. It did not copy the source database or log.
Application and configuration bytes were preserved, and the runtime database
started with zero applications, reviews, and history records. The server listened
only on `127.0.0.1`; HTTP proxies were disabled. Debug and request-detail logging
retained their configured values, while the reloader was disabled to keep a
single server process. Only the verification server was stopped afterward.

The latest verification was launched from a clean project copy without original
runtime files. Database inspection is optional when no source database exists;
it does not create one. Existing-database read errors are not silently treated
as absence. Source non-document file hashes were unchanged after each run.

The current script can be invoked from the project root using an existing
compatible environment:

```sh
.venv/bin/python -B docs/verify_normal.py
```

Each execution writes redacted evidence into a new `docs/evidence/runs/<run_id>/`
directory, preserving earlier evidence. Verification dates and start/completion
timestamps are generated from actual execution time in UTC. Raw runtime logs
and downloads remain separate from shared evidence. The command above is for
reproduction; this document describes the retained runs rather than a new run.

## 3. Functional scenarios and results

All recorded HTTP requests returned 200, but acceptance depended on content
comparisons, not status alone. Both runs confirmed the results below except
where a method difference is identified.

| Scenario | Expected result and observed evidence | Outcome |
|---|---|---|
| Provider fixture | Three application keys match the UI mapping; all nine records have the six expected fields, unique IDs, appropriate sample types, ratings, and parseable dates. | Matched |
| Homepage and CSS | Three correct import forms and zero counts initially; counts reflect imported records afterward. CSS bytes and content type match the source. | Matched |
| First import of every app | Each request fetches and inserts three reviews. Database totals rise to three apps, nine reviews, and three history records. Stored fields and app names match the fixture. | Matched |
| Repeat import of every app | Each request fetches three and inserts zero. Reviews remain at nine; history increases to six records. | Matched |
| Review queries | All-app query returns nine records; each app returns its three. Fields, values, and descending review-date order match expected records. | Matched |
| Ordinary keyword queries | `useful` returns two records across apps and one for Focus AI. `unfindableword` returns an empty list. | Matched |
| Summary | Per-app and overall counts, rounded averages, and eight term/count pairs match independent fixture calculations. | Matched |
| Import history | Six records, IDs 6 through 1, correct fields, app IDs, timestamps, counts, SUCCESS status, and messages; response matches SQLite history. | Matched |
| CSV export | Correct eight-column header; nine data rows, three per app; all values match SQLite and comma-containing text remains one field. | Matched |
| Database export | The supplied demo token permits a database attachment. All three application table definitions and contents match the runtime database; downloaded-file integrity check returns `ok`. | Matched |
| Health and existing smoke test | Health returns the expected status and UTC time. The unchanged existing test function completes successfully by direct Python invocation. | Matched |

The fixture contains Focus AI, Smart Notes, and Travel Companion, with three
reviews each. Their mean ratings are 3.67, 3.00, and 3.67; the overall mean is
3.44 across nine reviews. Word frequencies were tallied independently using a
dictionary rather than calling the application's summary function. Full term
lists and expected/actual comparisons remain in the JSON evidence. Tie order
matched the recorded runs but is not guaranteed by the source SQL.

The CSV header is:

```text
review_id,app_id,rating,text,created_at,app_version,user_region,ingested_at
```

The latest script saved the attachment and reopened it with UTF-8 encoding and
`newline=''` before parsing with `csv.reader`. The evidence records
`parsed_from=saved_download_file` and the file hash. The historical run also
saved the attachment, but parsed the in-memory response; its content checks
passed without establishing a saved-file readback. The Notes review containing
“Works, but notifications are inconsistent.” retained its comma correctly.

The database attachment was saved separately and opened read-only. It contained
three applications, nine reviews, and six import-history records. SQLite's
internal sequence metadata is additional to those application tables. Only the
provided valid demo token was used; token rejection and bypass were not tested.

## 4. Logging observations and protected evidence

Recorded runtime logs contain server startup/access records and application
request paths with query dictionaries. Ordinary search parameters appear.
Import requests show `args={}` because their app selection is in the POST form;
`record_request()` does not log form bodies or response content.

Normal database export confirmed that the demo token enters raw query logs and
server access URLs. **Demo token appears in private raw query logs — PASS** means
that this observation was confirmed. It does not mean a confidentiality or
security requirement was satisfied. The latest evidence explicitly labels this
as an observation and explains its interpretation.

Public evidence masks configured secret/token values and removes Debugger PIN
lines if present. Environment identifiers are normalized recursively in JSON
keys and values and in published logs: `<PROJECT_ROOT>` identifies the source
directory, `<TEMP_RUNTIME>` the isolated runtime, `<PYTHON_EXECUTABLE>` the
interpreter, and `<LOCAL_PORT>` the temporary server port. Other local paths use
distinct numbered aliases. Nested commands, errors, and expected/actual objects
use the same mapping. Commands containing placeholders document a run; they are
not literal commands to execute without replacing the placeholders.

This is a presentation-only cleanup, not a new functional run. Check names,
statuses, expected/actual comparison relationships, counts, statistics, dependency
versions, and verification-time source hashes are preserved. The records include
`public_sanitization` metadata to distinguish these public copies from raw local
materials. Source hashes identify the original verified files, not the bytes of
the subsequently sanitized JSON or the updated sanitizer.

Only unpublished raw material is private: pre-normalization copies are retained
under the ignored `.private-verification/` directory. That directory is excluded
from future verifier inventories. Original raw runtime logs, databases, and
downloads also remain outside the published evidence. The JSON and redacted-log
attachments linked in this report are the sanitized public versions.

The output sanitizer is covered by offline checks for nested keys and values,
command arguments, error text, distinct path aliases, identity/secret masking,
port normalization, and unchanged counts, versions, hashes, and statuses. It
rejects key collisions or normalization that would change expected/actual equality.
These checks do not import the application, start a server, or rerun the functional
scenarios. They can be run separately with:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_public_evidence.py
```

## 5. Coverage and limitations

The source review covered `app/app.py`, `app/db.py`, `app/config.py`, the template
and CSS, `data/provider_reviews.json`, `requirements.txt`, and
`tests/test_smoke.py`, alongside the task/scope documents and project reports.
Evidence manifests and hashes identify file snapshots; file access or hashing
alone is not a technical review. The executable source and fixture match the
recorded runtime snapshots. The verifier was subsequently updated for public
output sanitization and checked offline; the retained script hashes describe
the earlier functional runs, not a new execution of the updated script.

- The application smoke test available for those runs, `test_health`, was called directly in a separate process
  against the temporary project. Pytest was not installed; its collection and
  plugins were not run. This is a verification limitation, not an application
  vulnerability.
- Coverage comprises representative normal scenarios in each functional category,
  not every input or behavior. Unknown-app 404, invalid-token 403, malformed input,
  existing-database error recovery, concurrency, large inputs, and stress behavior
  were not exercised. Descriptions of untested error branches come from code.
- No active exploitation, access-control bypass, or external-system testing was
  performed. Code risks and confirmed normal-operation observations remain
  distinct from unverified security consequences.
- The diagrams were manually checked in Markdown preview. No independent Mermaid
  parser or rendering tool was used. Automated HTML/CSS checks verified served
  content, not visual browser layout.

These results support the documented normal data flows. Security concerns and
priorities for further investigation are developed in the
[system analysis](system-overview.md).
