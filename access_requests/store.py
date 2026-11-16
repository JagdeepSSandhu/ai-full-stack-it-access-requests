"""SQLite is the authoritative state; each operation has its own connection."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid
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
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, attempt_id INTEGER,
                    event TEXT, token TEXT, recorded REAL);
            ''')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(attempts)')}
            for name, declaration in [('token','TEXT'), ('lease_until','REAL NOT NULL DEFAULT 0'),
                                      ('available_after','REAL NOT NULL DEFAULT 0'),
                                      ('retry_count','INTEGER NOT NULL DEFAULT 0')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE attempts ADD COLUMN {name} {declaration}')

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

    def claim(self, attempt_id=None, *, lease=60, now=None):
        now = time.time() if now is None else now
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT a.* FROM documents d JOIN attempts a ON a.id=d.latest '
                "WHERE (a.state='pending' OR (a.state='running' AND a.lease_until<=?)) "
                'AND a.available_after<=? AND (? IS NULL OR a.id=?) ORDER BY a.id LIMIT 1',
                (now,now,attempt_id,attempt_id)).fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            db.execute("UPDATE attempts SET state='running',token=?,lease_until=? WHERE id=?",
                       (token,now+lease,row['id']))
            db.execute('INSERT INTO events(attempt_id,event,token,recorded) VALUES(?,?,?,?)',
                       (row['id'],'claim',token,now))
            return {**dict(row), 'token':token, 'lease_until':now+lease}

    def renew(self, attempt_id, token, *, lease=60):
        with self.connection() as db:
            return db.execute("UPDATE attempts SET lease_until=? WHERE id=? AND token=? AND state='running' "
                              'AND id IN (SELECT latest FROM documents)',
                              (time.time()+lease,attempt_id,token)).rowcount == 1

    def finish(self, attempt_id, result, *, token=None):
        attempt = self.attempt(attempt_id)
        result = {**result, 'attempt_id': attempt_id, 'source_sha256': attempt['source_sha256'],
                  'settings': json.loads(attempt['settings']), 'policy_version': attempt['policy_version']}
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            active = db.execute('SELECT a.token,a.state,a.lease_until,d.latest FROM attempts a '
                'JOIN documents d USING(document_id) WHERE a.id=?', (attempt_id,)).fetchone()
            if token is not None and (active['token'] != token or active['state'] != 'running' or
                                      active['lease_until'] < time.time() or active['latest'] != attempt_id):
                db.execute('INSERT INTO events(attempt_id,event,token,recorded) VALUES(?,?,?,?)',
                           (attempt_id,'rejected-stale-completion',token,time.time()))
                return False
            db.execute('UPDATE attempts SET state=?,result=? WHERE id=?', ('done',json.dumps(result),attempt_id))
        return result

    def ingest(self, document, provider, *, policy=POLICY_TEXT, force=False):
        attempt = self.register(document, provider.configuration, policy=policy, force=force)
        if attempt is not None:
            claim = self.claim(attempt)
            if claim:
                return self.finish(attempt, process(document, provider, policy), token=claim['token'])
        return next((r for r in self.current() if r['document_id'] == document['document_id']), None)

    def retry_later(self, attempt_id, *, delay):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT a.* FROM attempts a JOIN documents d ON d.latest=a.id '
                             "WHERE a.id=? AND a.state='done'", (attempt_id,)).fetchone()
            if row is None:
                return None
            new = db.execute('INSERT INTO attempts(document_id,source_sha256,raw,fingerprint,settings,'
                             'policy,policy_version,created,available_after,retry_count) '
                             'VALUES(?,?,?,?,?,?,?,?,?,?)',
                (row['document_id'],row['source_sha256'],row['raw'],row['fingerprint'],row['settings'],
                 row['policy'],row['policy_version'],time.time(),time.time()+delay,row['retry_count']+1)).lastrowid
            db.execute('UPDATE documents SET latest=? WHERE document_id=?',(new,row['document_id']))
            return new

    def current(self):
        with self.connection() as db:
            rows = db.execute('SELECT a.result FROM documents d JOIN attempts a ON a.id=d.latest '
                              'WHERE a.result IS NOT NULL ORDER BY d.document_id').fetchall()
        return [json.loads(row['result']) for row in rows]

    def pending(self):
        with self.connection() as db:
            rows = db.execute('SELECT a.id AS attempt_id,a.document_id,a.state,a.source_sha256,'
                              'a.available_after,a.retry_count '
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
