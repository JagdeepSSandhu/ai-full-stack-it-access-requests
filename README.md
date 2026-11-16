# AI Full Stack Challenge — IT Access Requests

I got everything done by not challenging Codex. I said yes to everything it wanted.

## Setup and reproducible mock intake

Run from the repository root on Linux with CPython 3.11 or later. Implementation
checks were run on Python 3.12.3. No third-party dependencies are required;
requirements.lock records that dependency set. The validator implements the
type, properties, required, additionalProperties, enum and items vocabulary of
the supplied snapshot.schema.json, plus date and supporting-quote checks.

```bash
python3 --version
env -u API_KEY python3 -m access_requests intake materials/requests materials/synthetic
env -u API_KEY python3 -m access_requests queue
env -u API_KEY python3 -m access_requests accuracy --report deliverables/accuracy.md
env -u API_KEY python3 -m unittest discover -s tests -v
```

Default mode uses saved responses in tests/mock_responses/, labelled mock with
model fixture-v1. It never reads API_KEY or contacts a model. Mock fixtures do
not establish actual model extraction accuracy. Twenty original exports and one
authored paraphrase produce 21 records; expected facts, quotes and routing rules
are in planning/plan.md and tests/expected.json, independently of measured outputs.

Intake accepts files or directories of UTF-8 JSON exports. New messages in the
same export format are supported by the provider adapter; mock mode requires a
matching lowercase filename in the fixture directory. Missing mock fixtures
become explicit errors, not synthetic successes.

## Inspect and recover

An intake command can run in one terminal while another inspects the same state:

```bash
python3 -m access_requests queue
python3 -m access_requests history IT-001.json
python3 -m access_requests resume
python3 -m access_requests retry IT-001.json
python3 -m access_requests export
```

Queue output includes completed/error current records and a separate pending
list. All successes await human review. A manager is a contact, not an approval.
Security Review examines risk and forwards its recommendation to the system
owner for a decision; the application never grants access or approves requests.

SQLite at state/requests.db is authoritative. Current output snapshots are
deliverables/extractions.jsonl and deliverables/queue.json, linked by document_id,
source_sha256 and attempt_id. `export` publishes both from one database snapshot.
Each is a symlink through deliverables/current to one immutable generation;
resolve current once before opening both files if publication may occur between
reads. Prior attempts are separate in SQLite, available through `history`, and
included in deliverables/history.jsonl. Source bytes, settings and policy version
are retained in the database. Completed results are reused only when source and
relevant processing inputs are unchanged. Batch omissions do not withdraw records.

`intake`, `resume` and `retry` publish snapshots when the command finishes. During
intake use `queue` to inspect ready work, or run `export` for a partial snapshot.
Existing committed snapshots can be inspected without a database; generate a new
local database with intake before using the database-backed queue command.

Every terminal extraction error includes an explicit retry_command with its
database, document and attempt. For an isolated workspace, put global flags before
the command, for example:

```bash
python3 -m access_requests --db /tmp/northstar.db --output /tmp/northstar-results intake materials/requests materials/synthetic
python3 -m access_requests --db /tmp/northstar.db queue
python3 -m access_requests --db /tmp/northstar.db retry IT-001.json --attempt 1
```

An explicit retry creates a new attempt, even after success. Failed retries show
the latest error, with earlier successes only in history. Retry retains the
chosen attempt's source bytes and policy; use the original provider/model
settings shown in history. Resuming requires those settings too. During a delayed
transient retry the document is pending; earlier failed attempts remain in history.

## Provider and configuration

The implemented live integration uses the OpenAI Responses API, direct JSON over
HTTPS and strict structured output. The documented configuration is
gpt-4.1-2025-04-14, temperature 0, max_output_tokens 2500, timeout 30 seconds and
store false. The facilitator supplies API_KEY in the environment; the application
reads it only when the openai provider is selected. Tests inject a dummy credential
directly and intercept transport, without reading API_KEY or contacting a model.
See docs/provider.md and deliverables/request-evidence.json for the contract and
credential-redacted request example. No live observation has been made.

For an optional operator-run provider intake, with the supplied environment set:

```bash
python3 -m access_requests --provider openai --db state/live.db --output state/live-results --rate 1 intake materials/requests
```

| Setting | Default and purpose |
|---|---|
| API_KEY | Required only for live provider authentication; never stored in settings or request evidence |
| MODEL_ID | gpt-4.1-2025-04-14 |
| MODEL_ENDPOINT | https://api.openai.com/v1/responses |
| MODEL_TEMPERATURE | 0 |
| MAX_OUTPUT_TOKENS | 2500 |
| MODEL_TIMEOUT | 30 seconds |
| --db / --output | state/requests.db / deliverables |
| --provider / --fixtures | mock / tests/mock_responses/ |
| --workers / --rate | 4 concurrent workers / unlimited starts per second; rate is per process |
| --retries / --backoff | 2 transient retries / 1-second exponential base delay |
| --lease | 60 seconds, renewed every third of a lease while a call runs |
| --policy | Supplied materials/office-policy.md text by default; its SHA-256 identifies the policy version |
| --script | Optional comma-separated saved mock replies for reproducible error/retry examples |

Relevant model/request settings, prompt, schema, policy and raw-byte source hash
determine refresh. Logging verbosity and scheduling limits do not affect extracted
facts. Routing rules are implemented in policy.py; when policy semantics change,
update and test that implementation alongside policy text, then rerun intake on
affected documents. Arbitrary new routing rules are not interpreted from prose.
Provider HTTP diagnostics are not recorded; errors use redacted summaries.

## Operating limits and verification

Shared operation supports overlapping processes on a single host using one local
SQLite database. It does not support network filesystems or independent regional
databases. Latest intake registration order determines the current source revision;
export timestamps do not order business updates. An obsolete worker is fenced from
changing the current result. A killed worker's claim can be recovered after its
lease expires; completed work remains recorded. If a process dies after a provider
returns but before a result commits, the call may run again: model calls are at
least once, with one coherent current record per document.

Workers and call rates are bounded per process, not globally across operators or
other internal tools. Use a suitable shared provider quota and lower --rate when
needed. Model calls have configurable timeouts and bounded transient retries.
Filesystem publication requires Linux flock, symlinks, atomic rename and fsync.
Generations are retained; disk usage grows and cleanup is an operator task.

Verification commands, comparisons, observed mock results, interruption behavior
and limits are recorded in deliverables/verification.md. The accuracy command is
for the supplied benchmark and paraphrase, not an evaluation of arbitrary intake
messages. It counts all 252 scalar opportunities, even when extraction fails or a
record is missing. Alternate purpose paraphrases need human source review.

The coding session is captured by the repository's enabled Entire setup and its
commit hooks. Final facilitator capture verification, a default-branch push and
Classroom root-link submission require actual external evidence; local tests do
not prove those actions occurred. Human validation of every spec line remains
the reviewer's decision.
