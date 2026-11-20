"""Operator CLI. Mock mode is the reproducible default."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from .providers import MockProvider
from .prompt import POLICY_TEXT
from .publication import publish
from .review_files import external_path, private_directory
from .scheduler import run
from .store import Store, production_settings
from .validation import read_export

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE = ('All successful outputs await human review. A manager is a contact, not approval. '
            'Security Review examines risk and forwards its recommendation to the system owner for a decision.')


def parser():
    p = argparse.ArgumentParser(description='Prepare Northstar access requests for human review')
    p.add_argument('--db', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--provider', choices=['mock','openai'], default='mock')
    p.add_argument('--fixtures', default=str(ROOT/'tests/mock_responses'))
    p.add_argument('--script', help='Comma-separated fixture script for mock examples')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--rate', type=float, default=0, help='Maximum call starts/second in this process; 0 is unlimited')
    p.add_argument('--retries', type=int, default=2)
    p.add_argument('--backoff', type=float, default=1)
    p.add_argument('--lease', type=float, default=60)
    p.add_argument('--policy', type=Path, help='Explicit version of office policy text')
    commands = p.add_subparsers(dest='command', required=True)
    intake = commands.add_parser('intake')
    intake.add_argument('paths', nargs='+', type=Path)
    commands.add_parser('queue')
    commands.add_parser('resume')
    commands.add_parser('export')
    retry = commands.add_parser('retry')
    retry.add_argument('document_id', nargs='?')
    retry.add_argument('--attempt', type=int)
    history = commands.add_parser('history')
    history.add_argument('document_id')
    accuracy = commands.add_parser('accuracy')
    accuracy.add_argument('--expected',type=Path,default=ROOT/'tests/expected.json')
    accuracy.add_argument('--report',type=Path)
    ready = commands.add_parser('readiness')
    ready.add_argument('repository_link')
    return p


def default_db(provider):
    root = Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local'/'state')
    return root/'northstar-access-requests'/provider/'requests.db'


def result_summary(record):
    return {key: record[key] for key in ('attempt_id', 'status', 'owner', 'next_action')}


def queue_summary(store):
    return {'current': [result_summary(row) for row in store.current()],
            'pending': [{key: row[key] for key in ('attempt_id', 'state', 'retry_count')}
                        for row in store.pending()],
            'guidance': GUIDANCE}


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'readiness':
            from .submission import readiness
            result = readiness(ROOT,args.repository_link)
            print(json.dumps(result,indent=2))
            return 0 if result['artifacts_ready'] and result['root_link_valid'] else 2
        store = Store(args.db or default_db(args.provider))
        output = args.output or store.path.parent/'results'
        if args.command == 'accuracy':
            from .accuracy import compare, write_report
            expected = json.loads(args.expected.read_text())
            documents = {p.name:read_export(p) for folder in ['requests','synthetic']
                         for p in (ROOT/'materials'/folder).glob('*.json')}
            records = store.current()
            if any(row['response_source'] != 'mock' or row['document_id'] not in documents
                   or row['source_sha256'] != documents[row['document_id']]['source_sha256']
                   for row in records):
                raise ValueError('Accuracy is limited to mock results for the supplied fictional benchmark')
            report = compare(records,expected,documents)
            if args.report:
                write_report(args.report,report,expected)
            result = {key: value for key, value in report.items() if isinstance(value, int)}
        elif args.command == 'queue':
            result = queue_summary(store)
        elif args.command == 'history':
            result = [{'attempt_id': row['attempt_id'], 'state': row['state'],
                       'result': result_summary(row['result']) if row['result'] else None}
                      for row in store.history(args.document_id)]
        elif args.command == 'export':
            result = {'generation':publish(store,output).name}
        else:
            if args.provider == 'mock':
                provider = MockProvider(args.fixtures,args.script.split(',') if args.script else None)
            else:
                from .openai_provider import OpenAIProvider, Settings
                provider = OpenAIProvider(Settings.from_env())
            output = private_directory(output)
            policy = args.policy.read_text() if args.policy else POLICY_TEXT
            if args.command == 'intake':
                paths = []
                for path in args.paths:
                    if args.provider == 'openai':
                        external_path(path)
                    paths.extend(sorted(path.glob('*.json')) if path.is_dir() else [path])
                if not paths:
                    raise ValueError('No JSON exports found')
                if args.provider == 'openai':
                    paths = [external_path(path) for path in paths]
                    for path in paths:
                        private_directory(path.parent, create=False)
                        if path.is_symlink() or not path.is_file():
                            raise ValueError('Live intake requires regular export files')
                for path in paths:
                    store.register(read_export(path),provider.configuration,policy=policy)
            elif args.command == 'retry':
                attempt = args.attempt
                if attempt is None:
                    if not args.document_id:
                        raise ValueError('Retry requires a document_id or --attempt')
                    history = store.history(args.document_id)
                    if not history:
                        raise ValueError('Unknown document_id')
                    attempt = history[-1]['attempt_id']
                old = store.attempt(attempt)
                if args.document_id and old['document_id'] != args.document_id:
                    raise ValueError('Attempt belongs to another document')
                if json.loads(old['settings']) != production_settings(provider.configuration):
                    raise ValueError('Retry requires the original provider/model settings shown in history')
                store.register(store.document(attempt),provider.configuration,policy=old['policy'],force=True)
            run(store,provider,workers=args.workers,rate=args.rate,retries=args.retries,
                backoff=args.backoff,lease=args.lease)
            publish(store,output)
            result = queue_summary(store)
        print(json.dumps(result,indent=2))
        return 0
    except (OSError, sqlite3.Error):
        print('Unable to access a required input or review file',file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
