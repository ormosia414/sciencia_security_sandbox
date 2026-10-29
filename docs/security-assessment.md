# Focused Local Security Assessment

Sciencia AI Review Intelligence Sandbox  
Author: Phoebe Zhang

## Results in brief

This assessment followed up three questions from Module 1. Both search
parameters could change SQL filtering and return all nine sample reviews.
The database-export token appeared in request logs, and a new client successfully
used the token extracted from those logs to download the database. Import,
history, and CSV operations also accepted clients without identity credentials;
whether that conflicts with the intended permissions remains unresolved.

The two confirmed weaknesses are rated **Low in the current local teaching
sandbox**. Credential-free operations are **Informational pending a defined
access policy**. These ratings describe observed impact, not permission to leave
unsafe patterns in future deployments. This work assessed behavior and proposed
changes; it did not implement fixes.

## Why these questions, and how they were assessed

The [Module 1 analysis](system-overview.md) identified three places where trust
assumptions matter: client values enter SQL, callers request stored data or
imports, and an export credential enters logs. The code provides direct reasons
to examine them. `reviews()` interpolates input into SQL, several routes have
no caller check, and query logging runs before the export route checks its token.
Small tests with normal controls can establish what these paths actually do
without changing data through SQL or testing unrelated capabilities.

The assessment used application source from commit
`0236b55eefb1a0922d1290fd6c17e5be256f5737` on **27 October 2026**.
A script sent HTTP requests to an isolated local copy listening on `127.0.0.1`,
using unchanged application code, separate storage and logs, and the supplied
synthetic data. The homepage/form control was also scripted, not an interactive
browser test. Responses were checked against record IDs, parsed downloads, and
read-only database inspection rather than HTTP status alone.

There was one continuous run, with no database reset between scenarios. It began
empty. The normal Focus import produced three reviews and one history row; the
credential-free Notes import produced six reviews and two history rows. History
and CSV access were checked at that point. Importing Travel then produced nine
reviews and three history rows, which were used for all search and token tests.
Thus the six-row CSV and nine-row database download describe different stages,
not conflicting results.

The [results JSON](evidence/security-assessment/20261027T124512135714Z/results.json)
contains the recorded requests and state comparisons. The
[evidence guide](evidence/security-assessment/README.md) links each finding to
its records, source locations, logs, and reproduction method. It also retains
precise timing, environment information, and execution limitations. The earlier
[normal verification report](verification-results.md) describes the preceding
stage, not these later security tests.

## 1. Search inputs change SQL conditions

The search route should treat an application ID and keyword as values. In
[app/app.py](../app/app.py), `reviews()` instead places both inside SQL strings.
This makes the boundary between a caller's data and the database's instructions
worth checking. Parameter binding in the separate `summary()` query does not
protect this search query.

Normal controls returned three reviews for Focus, zero for an unknown app ID,
and nine with no filter. The global search for `useful` returned two reviews.
A Focus-scoped `useful` control was not recorded in this assessment.
`unfindableword` returned zero both globally and with the Focus filter.

The script then sent these two read-only parameter sets:

```json
[
  {"app_id": "com.sciencia.missing' OR '1'='1"},
  {"app_id": "com.sciencia.focus", "q": "unfindableword%' OR 1=1 -- "}
]
```

Both should return no reviews if treated as ordinary values. Instead, each
returned HTTP 200 and all nine sample IDs from all three apps. The second input
also defeated the accompanying Focus filter. The injected `OR` changed the
condition; in the keyword case, the comment removed the remaining SQL suffix.
The [search evidence](evidence/security-assessment/README.md#search-controls-and-probes)
retains the exact inputs, responses, IDs, and unchanged table-content hashes.
This establishes SQL injection affecting selection, not merely a query error.

**Severity: Low in this sandbox.** The filter's integrity is affected, but the
same caller could already read all nine reviews through an unfiltered request.
No additional user permission or access to otherwise unavailable data was
proved. The tests did not attempt writes, local-file reads, or other tables.
The limited observed impact does not make the SQL construction acceptable.

Bind both inputs as parameters, building the `LIKE` pattern as a value. Decide
whether search wildcards should remain meaningful or be matched literally.
Parameter binding prevents input from becoming SQL structure; a separate access
policy is needed if users should see different applications.

## 2. Export credentials are copied into logs

Database export has a real control: `export_db()` compares the supplied token
with a configured value. However, `record_request()` records query parameters
before that comparison, and request-detail logging is enabled. This creates a
second place from which the export credential may be obtained.

The controls showed that missing and incorrect tokens each produced 403 with
an invalid-token response. A correct demo token produced a SQLite attachment.
That complete token also appeared in the application's query log and a server
access URL. The script extracted it from the log and used a new client, without
cookies, a session, or an authorization header, to request another download.

The second download succeeded. Its saved file passed SQLite integrity checking
and contained three apps, nine reviews, and three history rows. The
[token evidence](evidence/security-assessment/README.md#token-logging-and-download)
links both downloads and log extraction using the same `<EXPORT_TOKEN>` alias.
The client supplied the accepted credential; it did not bypass the token check.

**Severity: Low in this sandbox.** Reusing a fixed token is not necessarily a
vulnerability by itself. The concern is that logging adds an exposure path for
a credential that grants database downloads. Using this path requires log-read
access, service reachability, and a still-valid token. The tester already had
log access; the tests did not establish that other OS users have it. The demo
value is also available in configuration source, so logs are not its only
source. Together with synthetic data and local listening, these facts limit
the demonstrated impact.

Keep credentials out of URLs and redact them before application logging; server
access logs must be considered too. Define export authorization and credential
lifetime together. Moving a token to a header helps only if that header is also
kept out of logs. These measures protect credentials, rather than repairing SQL
construction or defining which users deserve export access.

## 3. Import, history, and CSV accept credential-free callers

The application provides import, history, and CSV routes without a login or role
check. The question here is which actions a new caller can actually complete,
not whether a nonexistent login can be bypassed. An app ID present in the
provider file validates the selected data, not the caller's identity.

After the normal Focus import, a new client directly submitted the not-yet-imported
Notes ID without cookies, a session, or an authorization header. The response
reported three fetched and three inserted. Independent database inspection
confirmed three new reviews and one new history row. Other new clients read
both history records and downloaded the six-row CSV covering Focus and Notes.
The saved CSV was reopened, parsed, and compared with the sample fields.
The [credential-free operation evidence](evidence/security-assessment/README.md#data-progression-and-credential-free-operations)
records these changes and responses. Unlike these routes, database export
rejected clients without an accepted token.

**Assessment: Informational until permissions are defined.** Credential-free
operation is confirmed. Whether it violates a requirement remains unknown:
a single learner's local tool may intentionally permit every reachable caller
to use these functions. No administrator role was established by the `/admin/`
name, and no authentication bypass was demonstrated. Browser cross-origin
behavior was not tested.

Confirm who may import, read history, and export each kind of data. If those
permissions should differ, enforce them consistently at the routes, with
appropriate browser request protections. This decision needs a usage requirement;
it cannot be supplied by a route name or inferred from the token on another route.

## Recommended next steps

Prioritize parameterized search queries because the input-to-SQL weakness is
confirmed. In parallel, clarify intended users and export permissions so access
controls address an agreed requirement. Before shared or real-data use, stop passing credentials in URLs and prevent application and server logs from recording them. Low describes today's
observed sandbox impact, not low repair value or a rating for future deployment.

The remaining questions are specific: can all local callers import and export,
should CSV and full-database downloads have the same permissions, and who should
read logs or possess export credentials? Those answers determine the appropriate
controls. Testing was limited to the cases described above. Other exploitation paths and OS permissions were not assessed, and the results do not establish a severity rating for a production deployment. Fixes remain recommendations until
implementation is requested.
