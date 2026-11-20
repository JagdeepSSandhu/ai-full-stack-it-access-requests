# AI Full Stack Challenge — IT Access Requests

The implementation uses mock-backed checks and a human review queue. Known limitations and follow-up decisions are documented with the evidence.

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
env -u API_KEY python3 -m access_requests accuracy
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

Queue output shows attempt IDs, status, routing and pending work. Use the same
attempt ID to find full records in the protected snapshots. All successes await
human review. A manager is a contact, not an approval.
Security Review examines risk and forwards its recommendation to the system
owner for a decision; the application never grants access or approves requests.

The default review root is
`${XDG_STATE_HOME:-$HOME/.local/state}/northstar-access-requests/<provider>/`.
SQLite at `requests.db` is authoritative. `results/extractions.jsonl` and
`results/queue.json` share document IDs, source hashes and attempt IDs.
`results/history.jsonl` contains the full prior results and provider settings.
Each file points through `results/current` to one immutable generation. Resolve
`current` once when reading several files during publication.

The database retains source bytes and restored records. Review directories and
files are owner-only, and runtime artifacts must stay outside Git worktrees.
Run real intake from a restricted operator environment where coding agents and
session recorders have no access to the input or review directory. If you used
the previous in-repo database path, copy the database into a private directory
while intake is stopped, then use `--db` to point at the copy. Publish into a
fresh private output directory. Completed results are reused only when source
and processing inputs are unchanged.

`intake`, `resume` and `retry` publish snapshots when the command finishes. During
intake use `queue` to inspect ready work, or run `export` for a partial snapshot.
Existing committed snapshots can be inspected without a database; generate a new
local database with intake before using the database-backed queue command.

Detailed extraction errors and retry commands are available in the protected
snapshots. You can retry using the numeric attempt ID from CLI output. To run
with isolated review state, put global flags before the command.

```bash
review_dir=$(mktemp -d)
python3 -m access_requests --db "$review_dir/requests.db" intake materials/requests materials/synthetic
python3 -m access_requests --db "$review_dir/requests.db" queue
python3 -m access_requests --db "$review_dir/requests.db" retry --attempt 1
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

Live intake sends a limited vocabulary of access-request terms and request-local
placeholders. Date and request ID values, other free-text words, and the office
policy stay local. The model can still see access concepts such as `production`
and `admin`, plus the ordering of the clues. Use live mode only if that data and
the destination are approved. Model extraction quality after minimization has
only been checked with intercepted responses. Unclear facts go to human review.

To try live mode using a fictional export, set the supplied credential in the
operator environment first.

```bash
sample_dir=$(mktemp -d)
cp materials/requests/IT-001.json "$sample_dir/"
python3 -m access_requests --provider openai --rate 1 intake "$sample_dir"
python3 -m access_requests --provider openai queue
```

| Setting | Default and purpose |
|---|---|
| API_KEY | Required only for live provider authentication; never stored in settings or request evidence |
| MODEL_ID | gpt-4.1-2025-04-14 |
| MODEL_ENDPOINT | Approved HTTPS endpoint `https://api.openai.com/v1/responses`; other values are rejected |
| MODEL_TEMPERATURE | 0 |
| MAX_OUTPUT_TOKENS | 2500 |
| MODEL_TIMEOUT | 30 seconds |
| --db / --output | Per-provider `requests.db` / `results/` alongside the selected database; both outside Git |
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
affected documents. Unsupported policy hashes are rejected before registration;
update the supported hash only after implementing and testing the new rules.
Arbitrary new routing rules are not interpreted from prose.
Provider HTTP diagnostics are not recorded; errors use redacted summaries.

## Operating limits and verification

Shared operation supports overlapping processes under the review account on a
single host using one local SQLite database. It does not support network filesystems or independent regional
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

Entire captures development sessions through the repository hooks. The
submission includes filtered excerpts from the build, assessment and privacy
work. Use the handoff index to find the user directions and original checkpoint
references. Keep real operating data outside that capture environment.

Run the offline artifact inventory with:

```bash
python3 -m access_requests readiness https://github.com/JagdeepSSandhu/ai-full-stack-it-access-requests
```

See deliverables/submission.md for capture evidence and remaining external checks.

See [assessment follow-up](deliverables/assessment-followup.md) for data handling risks, a conditional regulated-repository handoff, and an unrun paired evaluation design.
