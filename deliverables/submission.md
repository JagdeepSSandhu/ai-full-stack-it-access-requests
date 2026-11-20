# Submission handoff

Offline readiness command:

```bash
python3 -m access_requests readiness https://github.com/JagdeepSSandhu/ai-full-stack-it-access-requests
```

The inventory checks nonempty required files and the root-link shape. It does not
validate source correctness, capture integrity, remote state or Classroom state.

## How the user directed the work

The files below contain filtered records from the actual Entire sessions.
Each record includes its original transcript line number. The export keeps the
user directions and selected responses and verification excerpts. Account IDs,
workspace paths, and raw tool payloads were removed.

| User direction | Session evidence |
|---|---|
| Specified the source documents, requirement table, and verification column | [Build session, lines 3–6](session.jsonl#L3-L6) |
| Chose the plan-from-spec skill and limited that turn to the plan | [Build session, lines 8–12](session.jsonl#L8-L12) |
| Required the plan order, failing tests first, separate commits, and mock-only development | [Build session, lines 14 onward](session.jsonl#L14) |
| Provided grading feedback and requested a plan revision | [Assessment session, lines 3 and 9](session-assessment.jsonl#L3) |
| Requested the PII review, directed the fixes, shared the rubric feedback, and authorized the commit | [Privacy follow-up session](session-privacy.jsonl) |

`session-capture.json` gives the build export checksum and original capture
reference. The privacy follow-up export ends at its pre-commit snapshot. Use the
new commit's automatic Entire checkpoint to verify the commit pairing. Run real
intake from a restricted operator environment outside this capture setup.

Final external checks remain pending:

1. Compare the final commit's Entire-Checkpoint and session pairing with the
   facilitator's capture instructions (C-05). Locally inspect `git log -1
   --format=%B`, `entire status --json` and the documented read-only session info.
2. Confirm the intended default branch and push the application, outputs and
   capture through the authorized submission workflow; inspect remote contents
   afterwards (C-06).
3. Submit only the root repository link above to the Classroom assignment and
   inspect that actual submission (C-07).

The facilitator can use the session index above when reviewing the submission.
