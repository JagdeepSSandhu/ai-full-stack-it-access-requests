# Repository Guidelines

## Project Structure & Module Organization

- `access_requests/`: Python CLI and intake pipeline. `policy.py` routes requests; `validation.py` enforces the schema; provider modules extract facts; `store.py`, `scheduler.py` and `publication.py` handle persistence, recovery and snapshots.
- `tests/`: unittest cases, independent expectations in `expected.json`, and saved replies in `mock_responses/`.
- `materials/`: fictional request exports, synthetic paraphrase and office policy.
- `docs/`, `CHALLENGE.md`, `snapshot.schema.json`: workflow instructions and authoritative requirements.
- `planning/`: spec, implementation/test plan, saved test run and validation evidence.
- `deliverables/`: submission examples, accuracy reports and filtered session evidence.

## Build, Test, and Development Commands

Use Linux with CPython 3.11+ from the repository root. No build step or third-party dependencies are required; `requirements.lock` documents dependencies.

```bash
python3 tools/check_prerequisites.py
env -u API_KEY python3 -m unittest discover -s tests -v
env -u API_KEY python3 -m access_requests intake materials/requests materials/synthetic
env -u API_KEY python3 -m access_requests queue
env -u API_KEY python3 -m access_requests accuracy
```

These check setup, run tests, process mock intake, inspect the queue and compare benchmark facts. Use global `--db` and `--output` flags before the subcommand for isolated state outside Git.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions/modules and `PascalCase` classes. Match nearby code and prefer standard-library facilities. No formatter or linter is configured. Keep extraction, validation, routing and persistence responsibilities distinct; retain one decision point per policy rule.

## Testing Guidelines

Use `unittest` with `test_*.py` files and `test_*` methods; preserve existing `T-xx` case references. Write regression tests before behavioral fixes and record the initial outcome. Run the full suite after each implementation step. Tests must work without API_KEY or network access; inject saved replies or intercepted transports. Derive expected facts from messages and policy. Mock success does not demonstrate live model accuracy. Coverage follows the numbered spec; no percentage threshold is configured.

## Commit & Pull Request Guidelines

Use concise imperative subjects. Follow existing `Test first: <step>` and `Step <n>: <step>` conventions for planned work. PRs should explain behavior, affected requirements, validation commands/results and remaining limits. Update planning evidence when behavior changes. Include relevant filtered session logs and index links; Entire creates commit checkpoints automatically.

## Security & Configuration

Keep credentials in environment variables and operational databases outside Git worktrees. Use fictional fixtures in development and review session exports before publication. Follow `docs/provider.md` for live configuration. Preserve human approval: the application prepares a review queue and never grants access.
