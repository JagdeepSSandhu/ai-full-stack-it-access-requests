"""T-37: documented operator actions through real CLI subprocesses, mocked model."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def test_runtime_rejects_repo_paths_and_insecure_review_directories(self):
        from access_requests.publication import publish
        from access_requests.store import Store

        with self.assertRaisesRegex(ValueError, 'outside Git'):
            Store(ROOT/'state'/'blocked.db')
        with tempfile.TemporaryDirectory() as td:
            public = Path(td)/'public'
            public.mkdir()
            public.chmod(0o755)
            with self.assertRaisesRegex(ValueError, 'owner-only'):
                Store(public/'blocked.db')
            store = Store(Path(td)/'state.db')
            output = Path(td)/'repo-link'
            output.symlink_to(ROOT, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'outside Git'):
                publish(store, output)

    def test_T37_operator_commands(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'state.db'; output=Path(td)/'deliverables'
            base=[sys.executable,'-m','access_requests','--db',str(db),'--output',str(output),
                  '--fixtures',str(ROOT/'tests/mock_responses'),'--retries','0']
            def cli(*args):
                result=subprocess.run([*base,*args],cwd=ROOT,capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr)
                return json.loads(result.stdout)
            cli('intake',*[str(ROOT/f'materials/requests/IT-{n:03}.json') for n in [1,2,6]])
            queue=cli('queue')
            self.assertEqual([r['next_action'] for r in queue['current']],
                             ['review-request','review-risk-then-owner','inspect-message'])
            self.assertIn('human',queue['guidance'].lower())
            self.assertIn('recommendation',queue['guidance'].lower())
            cli('--script','error.json','retry','IT-001.json')
            self.assertEqual(cli('queue')['current'][0]['status'],'error')
            history=cli('history','IT-001.json')
            self.assertNotIn('Maya Chen',json.dumps(history))
            self.assertNotIn('IT-001',json.dumps(queue))
            self.assertNotIn('extraction',history[0]['result'])
            cli('retry','--attempt',str(history[-1]['attempt_id']))
            cli('resume')
            cli('export')
            generation=(output/'current').resolve()
            records=[json.loads(s) for s in (generation/'extractions.jsonl').read_text().splitlines()]
            exported=json.loads((generation/'queue.json').read_text())
            self.assertEqual(len(records),3)
            self.assertEqual(exported[0]['attempt_id'],records[0]['attempt_id'])
            self.assertEqual(exported[0]['source_sha256'],records[0]['source_sha256'])
            self.assertEqual(records[0]['extraction']['requester'],'Maya Chen')
            self.assertEqual(db.stat().st_mode & 0o777,0o600)
            self.assertEqual(generation.stat().st_mode & 0o777,0o700)
            self.assertEqual((generation/'extractions.jsonl').stat().st_mode & 0o777,0o600)
            self.assertEqual(cli('queue')['pending'],[])
