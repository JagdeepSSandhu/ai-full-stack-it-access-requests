"""Operator CLI. Mock mode is the reproducible default."""
import argparse
import json
from pathlib import Path
import sys
from .providers import MockProvider
from .prompt import POLICY_TEXT
from .publication import publish
from .scheduler import run
from .store import Store
from .validation import read_export

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE = ('All successful outputs await human review. A manager is a contact, not approval. '
            'Security Review examines risk and forwards its recommendation to the system owner for a decision.')


def parser():
    p = argparse.ArgumentParser(description='Prepare Northstar access requests for human review')
    p.add_argument('--db', default='state/requests.db')
    p.add_argument('--output', default='deliverables')
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
    retry.add_argument('document_id')
    retry.add_argument('--attempt', type=int)
    history = commands.add_parser('history')
    history.add_argument('document_id')
    accuracy = commands.add_parser('accuracy')
    accuracy.add_argument('--expected',type=Path,default=ROOT/'tests/expected.json')
    accuracy.add_argument('--report',type=Path)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        store = Store(args.db)
        if args.command == 'accuracy':
            from .accuracy import compare, write_report
            expected = json.loads(args.expected.read_text())
            documents = {p.name:read_export(p) for folder in ['requests','synthetic']
                         for p in (ROOT/'materials'/folder).glob('*.json')}
            result = compare(store.current(),expected,documents)
            if args.report:
                write_report(args.report,result,expected)
        elif args.command == 'queue':
            result = {'current':store.current(),'pending':store.pending(),'guidance':GUIDANCE}
        elif args.command == 'history':
            result = store.history(args.document_id)
        elif args.command == 'export':
            result = {'generation':str(publish(store,args.output))}
        else:
            if args.provider == 'mock':
                provider = MockProvider(args.fixtures,args.script.split(',') if args.script else None)
            else:
                from .openai_provider import OpenAIProvider, Settings
                provider = OpenAIProvider(Settings.from_env())
            policy = args.policy.read_text() if args.policy else POLICY_TEXT
            if args.command == 'intake':
                paths = []
                for path in args.paths:
                    paths.extend(sorted(path.glob('*.json')) if path.is_dir() else [path])
                if not paths:
                    raise ValueError('No JSON exports found')
                for path in paths:
                    store.register(read_export(path),provider.configuration,policy=policy)
            elif args.command == 'retry':
                history = store.history(args.document_id)
                if not history:
                    raise ValueError('Unknown document_id')
                attempt = args.attempt or history[-1]['attempt_id']
                old = store.attempt(attempt)
                if old['document_id'] != args.document_id:
                    raise ValueError('Attempt belongs to another document')
                from .store import production_settings
                if json.loads(old['settings']) != production_settings(provider.configuration):
                    raise ValueError('Retry requires the original provider/model settings shown in history')
                store.register(store.document(attempt),provider.configuration,policy=old['policy'],force=True)
            run(store,provider,workers=args.workers,rate=args.rate,retries=args.retries,
                backoff=args.backoff,lease=args.lease)
            publish(store,args.output)
            result = {'current':store.current(),'pending':store.pending(),'guidance':GUIDANCE}
        print(json.dumps(result,indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
