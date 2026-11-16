"""SQLite is the authoritative state; each operation has its own connection."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from .intake import process
from .prompt import POLICY_TEXT, PROMPT
from .validation import SCHEMA


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def production_settings(configuration):
    return {key: value for key, value in configuration.items() if key in
            ('provider', 'model', 'endpoint', 'max_output_tokens', 'temperature')}


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS documents(document_id TEXT PRIMARY KEY, latest INTEGER);
                CREATE TABLE IF NOT EXISTS attempts(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL, raw BLOB NOT NULL, fingerprint TEXT NOT NULL,
                    settings TEXT NOT NULL, policy TEXT NOT NULL, policy_version TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending', result TEXT, created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS attempts_document ON attempts(document_id, id);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def register(self, document, configuration, *, policy=POLICY_TEXT, force=False):
        settings = production_settings(configuration)
        fingerprint = digest(json.dumps({'source': document['source_sha256'], 'settings': settings,
                        'policy': digest(policy), 'prompt': digest(PROMPT), 'schema': SCHEMA}, sort_keys=True))
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT a.* FROM documents d JOIN attempts a ON a.id=d.latest '
                             'WHERE d.document_id=?', (document['document_id'],)).fetchone()
            if not force and old and old['fingerprint'] == fingerprint:
                if old['state'] != 'done' or (old['result'] and json.loads(old['result'])['status'] != 'error'):
                    return None
            attempt = db.execute('INSERT INTO attempts(document_id,source_sha256,raw,fingerprint,settings,'
                                 'policy,policy_version,created) VALUES(?,?,?,?,?,?,?,?)',
                (document['document_id'], document['source_sha256'], document['raw'], fingerprint,
                 json.dumps(settings, sort_keys=True), policy, digest(policy), time.time())).lastrowid
            db.execute('INSERT INTO documents VALUES(?,?) ON CONFLICT(document_id) '
                       'DO UPDATE SET latest=excluded.latest', (document['document_id'], attempt))
            return attempt

    def attempt(self, attempt_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM attempts WHERE id=?', (attempt_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown attempt')
        return dict(row)

    def document(self, attempt_id):
        attempt = self.attempt(attempt_id)
        return {'document_id': attempt['document_id'], 'source_sha256': attempt['source_sha256'],
                'raw': attempt['raw'], 'message': json.loads(attempt['raw'].decode('utf-8'))['message']}

    def finish(self, attempt_id, result):
        attempt = self.attempt(attempt_id)
        result = {**result, 'attempt_id': attempt_id, 'source_sha256': attempt['source_sha256'],
                  'settings': json.loads(attempt['settings']), 'policy_version': attempt['policy_version']}
        with self.connection() as db:
            db.execute('UPDATE attempts SET state=?,result=? WHERE id=?', ('done',json.dumps(result),attempt_id))
        return result

    def ingest(self, document, provider, *, policy=POLICY_TEXT, force=False):
        attempt = self.register(document, provider.configuration, policy=policy, force=force)
        if attempt is not None:
            return self.finish(attempt, process(document, provider, policy))
        return next((r for r in self.current() if r['document_id'] == document['document_id']), None)

    def current(self):
        with self.connection() as db:
            rows = db.execute('SELECT a.result FROM documents d JOIN attempts a ON a.id=d.latest '
                              'WHERE a.result IS NOT NULL ORDER BY d.document_id').fetchall()
        return [json.loads(row['result']) for row in rows]

    def pending(self):
        with self.connection() as db:
            rows = db.execute('SELECT a.id AS attempt_id,a.document_id,a.state,a.source_sha256 '
                              'FROM documents d JOIN attempts a ON a.id=d.latest '
                              'WHERE a.state != ? ORDER BY a.id', ('done',)).fetchall()
        return [dict(row) for row in rows]

    def history(self, document_id):
        with self.connection() as db:
            rows = db.execute('SELECT * FROM attempts WHERE document_id=? ORDER BY id', (document_id,)).fetchall()
        return [{'attempt_id': row['id'], 'source_sha256': row['source_sha256'],
                 'state': row['state'], 'policy_version': row['policy_version'],
                 'settings': json.loads(row['settings']),
                 'result': json.loads(row['result']) if row['result'] else None} for row in rows]
