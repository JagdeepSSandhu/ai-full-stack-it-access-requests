"""Offline artifact inventory; remote and facilitator actions need external evidence."""
from pathlib import Path
import re

REQUIRED = (
    'README.md','requirements.lock','snapshot.schema.json',
    *('access_requests/'+name+'.py' for name in ['__init__','__main__','providers','openai_provider',
       'prompt','validation','policy','intake','store','scheduler','publication','accuracy','submission']),
    'deliverables/extractions.jsonl','deliverables/queue.json','deliverables/accuracy.md',
    'deliverables/expected.json','deliverables/request-evidence.json','deliverables/verification.md',
    'deliverables/session.jsonl','deliverables/session-capture.json',
    'planning/spec.md','planning/plan.md','planning/test-run.txt',
    '.codex/hooks.json','.entire/settings.json',
)


def readiness(root, repository_link):
    root = Path(root)
    missing = [name for name in REQUIRED if not (root/name).is_file() or (root/name).stat().st_size==0]
    valid = bool(re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?',repository_link))
    return {'artifacts_ready':not missing,'missing':missing,'root_link_valid':valid,
            'repository_link':repository_link,
            'external_pending':['capture/commit verification','default-branch push','Classroom submission']}
