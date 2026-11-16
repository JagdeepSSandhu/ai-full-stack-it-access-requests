# Verification commands and evidence

All observations below used mock responses and configuration provider=mock,
model=fixture-v1, unless explicitly described as an intercepted provider contract.
They are pipeline checks, not live extraction-quality measurements. No real model
was called and tests do not read API_KEY. Runtime observed: Python 3.12.3 on Linux.

## Commands and intended comparisons

```bash
env -u API_KEY python3 -m unittest discover -s tests -v
env -u API_KEY python3 -m access_requests intake materials/requests materials/synthetic
env -u API_KEY python3 -m access_requests queue
env -u API_KEY python3 -m access_requests accuracy --report deliverables/accuracy.md
```

Use --db and --output global flags for an isolated workspace as in README.md.
The full suite runs T-01–T-39 at this stage, plus the three preserved starter
checks. planning/test-run.txt records the actual whole-suite run; T-40 is added
in the final submission-readiness step.

| Cases | Intended assertions/comparisons |
|---|---|
| T-01–T-04 | Saved mock events, original-byte hashes, filenames, decoded quote substrings, schema/dates, metadata isolation and 200-word input |
| T-05–T-20 | Expected E01–E21 facts authored in planning/plan.md, ordered policy routes, missing/conflicting/corrected facts and instruction overrides |
| T-21–T-25 | Malformed, refused, incomplete and failed responses do not yield successful extractions; HTTP contract model/settings and redaction match saved protocol fixtures |
| T-26–T-31 | Current/history separation, reuse, changed source, failed retries, batch omission and settings/policy provenance |
| T-32 | Two processes leave one coherent current entry per document; a stale worker cannot replace a new source; process death before generation switch leaves old output readable |
| T-33–T-36 | Slow work does not hide completed work; killed workers resume; transient retries preserve attempts; 400- and 2,000-message mock batches are accounted for |
| T-37–T-39 | Real CLI commands operate offline in isolated workspaces; independent comparison detects mutated facts, errors and missing records; handover artifacts match documented configuration |

## Observed mock results

Step-by-step whole-suite checks passed through step 10: 41 tests. The latest
saved run records the post-documentation suite count and output. No test results
were used to author expected facts. Expected scalar values were transcribed
from the plan before implementation and are in tests/expected.json.

The generated benchmark snapshot contains 21 mock records. Its accuracy report
observed 252/252 exact scalar matches, 63/63 routing fields, 21/21 documents with
supported quote substrings and 24/24 expected issue categories. Negative controls
with one wrong permission, an omitted record and a failed extraction produce 25
scalar mismatches while retaining the denominator of 252. These scores check the
fixture-backed pipeline and comparator, not live model performance.

One observed full-suite workload run after step 9 processed the 400-message mock
batch in 3.987 seconds and the 2,000-message batch in 28.449 seconds with four
workers, no rate cap, default retry settings and no live calls. These are measured
processing times excluding registration, not a required SLA or provider forecast.
Other run timings are printed by T-36 and retained in planning/test-run.txt.

The intercepted provider-contract observation uses OpenAI gpt-4.1-2025-04-14,
temperature 0, max_output_tokens 2500, strict schema and timeout 30 seconds.
Saved completed, refused, incomplete and HTTP 429 fixtures are processed without
network access. Authorization is a dummy injected value; request evidence is
redacted. Production API_KEY loading was inspected in Settings.from_env, not
executed by tests. No live provider observations are included.

## Observed repairs

During step 3's targeted checks, the withdrawal test variant removed the identifier
from the source but retained the old supporting quote. Validation correctly
rejected that stale quote. The test's quote was changed to the same edited source;
the plan-derived expected null identifier and clarification route were unchanged.

## Assumptions and limits

Operations are supported on a single host with one local SQLite database.
Overlapping processes, short transactions, fenced claims and coherent publication
are exercised; geographically distributed independent databases and network mounts
are not supported. Registration order determines the latest revision, because no
authoritative source revision sequence is supplied. History keeps prior results
separately, including success before a failed retry. Pending retries are shown
separately from completed current records, with prior errors accessible in history.

For interruption recovery, a killed worker's lease expires before another worker
reclaims unfinished work. Heartbeats renew live claims, and completed work is not
re-extracted on an unchanged rerun. Calls can repeat after a crash between provider
response and commit. Publication depends on local Linux flock, symlink, rename and
fsync behavior; an interrupted pointer switch is tested, but physical power-loss
and filesystem corruption are not simulated.

The workload assumptions come from the source's ordinary 200–400 messages and
roughly 2,000 during a surge. Worker count, timeout, retries and per-process rate
are configurable. The workload accounting checks use mocks; actual provider
capacity, real response latency, shared quotas, global rate coordination and
extraction accuracy are unmeasured. T-36 uses successful template replies; delayed
and error replies are exercised separately in T-33–T-35, not mixed into the large
batch. Rate-limit/outage recovery is simulated; real HTTP/network outages are not.

The JSON Schema validator covers the vocabulary in the supplied schema, not the
entire JSON Schema standard. Quote substring validation does not prove every model
fact is correct; independent expected facts and human review remain necessary.
The accuracy benchmark covers the 20 exports and one paraphrase. Issue coverage
uses field/category mentions, not a semantic assessment of arbitrary wording.
Policy semantic changes need corresponding routing-code changes and tests.

Generations and attempt history grow without automatic retention cleanup.
Facilitator capture/commit pairing, remote default-branch push and Classroom
submission remain external checks, not outcomes established by this suite.
