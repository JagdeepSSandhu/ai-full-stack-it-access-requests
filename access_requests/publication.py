"""Publish a consistent snapshot by atomically switching one generation pointer."""
import fcntl
import json
import os
from pathlib import Path
import uuid


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish(store, directory, *, hook=lambda stage: None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/'.publish.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with store.connection() as db:
            db.execute('BEGIN')
            rows = db.execute('SELECT a.result FROM documents d JOIN attempts a ON a.id=d.latest '
                              'WHERE a.result IS NOT NULL ORDER BY d.document_id').fetchall()
            records = [json.loads(row['result']) for row in rows]
            history = [dict(row) for row in db.execute('SELECT id,document_id,source_sha256,state,'
                       'settings,policy_version,result FROM attempts ORDER BY id')]
        queue = [{k:r[k] for k in ('document_id','source_sha256','attempt_id','status','owner','next_action',
                                  'error','policy_version')} for r in records]
        generation = directory/'.generations'/uuid.uuid4().hex
        generation.mkdir(parents=True)
        contents = {'extractions.jsonl': ''.join(json.dumps(r)+'\n' for r in records),
                    'queue.json':json.dumps(queue,indent=2)+'\n',
                    'history.jsonl': ''.join(json.dumps(r)+'\n' for r in history)}
        for name, content in contents.items():
            with (generation/name).open('w') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        sync_directory(generation)
        sync_directory(generation.parent)
        for name in contents:
            path = directory/name
            if not path.is_symlink():
                if path.exists():
                    raise ValueError(f'Refusing to replace existing regular output: {path}')
                path.symlink_to('current/'+name)
        hook('before_switch')
        temporary = directory/('.current-'+uuid.uuid4().hex)
        temporary.symlink_to(generation.relative_to(directory), target_is_directory=True)
        os.replace(temporary,directory/'current')
        sync_directory(directory)
        return generation


def read_generation(directory):
    # Resolve once; independent opens through `current` could straddle a switch.
    generation = (Path(directory)/'current').resolve(strict=True)
    return {'queue':json.loads((generation/'queue.json').read_text()),
            'extractions':[json.loads(line) for line in (generation/'extractions.jsonl').read_text().splitlines()]}
