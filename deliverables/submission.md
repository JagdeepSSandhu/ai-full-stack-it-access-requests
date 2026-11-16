# Submission handoff

Offline readiness command:

```bash
python3 -m access_requests readiness https://github.com/JagdeepSSandhu/ai-full-stack-it-access-requests
```

The inventory checks nonempty required files and the root-link shape. It does not
validate source correctness, capture integrity, remote state or Classroom state.

The enabled Entire capture setup is tracked in .entire/settings.json and
.codex/hooks.json. The session snapshot is deliverables/session.jsonl; metadata,
its SHA-256 and the commit present at snapshot time are in session-capture.json.
The snapshot is bounded to the transcript available when exported. Each build
commit's automatic Entire-Checkpoint footer links the continuing session; no
manual checkpoint was created. A final commit cannot embed its own hash inside
an artifact that contributes to that hash.

Final external checks remain pending:

1. Compare the final commit's Entire-Checkpoint and session pairing with the
   facilitator's capture instructions (C-05). Locally inspect `git log -1
   --format=%B`, `entire status --json` and the documented read-only session info.
2. Confirm the intended default branch and push the application, outputs and
   capture through the authorized submission workflow; inspect remote contents
   afterwards (C-06).
3. Submit only the root repository link above to the Classroom assignment and
   inspect that actual submission (C-07).

No remote push or Classroom submission is asserted by this handoff. Human
validation of each spec line is also separate from a passing automated suite.
