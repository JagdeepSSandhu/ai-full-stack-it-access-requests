"""T-39: reproducible handover commands and required evidence, in an isolated store."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class HandoverTests(unittest.TestCase):
    def test_T39_documented_mock_commands_and_artifacts(self):
        readme=(ROOT/'README.md').read_text()
        for text in ['python3 --version','python3 -m access_requests intake',
                     'python3 -m access_requests queue','python3 -m access_requests resume',
                     'python3 -m access_requests retry','python3 -m access_requests accuracy',
                     'python3 -m unittest discover -s tests','MODEL_ID','API_KEY','single host']:
            self.assertIn(text,readme)
        evidence=json.loads((ROOT/'deliverables/request-evidence.json').read_text())
        self.assertEqual(evidence['body']['model'],'gpt-4.1-2025-04-14')
        self.assertEqual(evidence['headers']['Authorization'],'Bearer [REDACTED]')
        self.assertIn('response_handling',evidence)
        verification=(ROOT/'deliverables/verification.md').read_text()
        for text in ['Observed','mock','2,000','single host','interruption','limits']:
            self.assertIn(text,verification)
        with tempfile.TemporaryDirectory() as td:
            base=[sys.executable,'-m','access_requests','--db',str(Path(td)/'state.db'),
                  '--output',str(Path(td)/'deliverables')]
            def command(*args):
                run=subprocess.run([*base,*args],cwd=ROOT,text=True,capture_output=True,timeout=20)
                self.assertEqual(run.returncode,0,run.stderr)
                return json.loads(run.stdout)
            command('intake','materials/requests','materials/synthetic')
            self.assertEqual(len(command('queue')['current']),21)
            report=command('accuracy','--report',str(Path(td)/'accuracy.md'))
            self.assertEqual(report['scalar_matches'],252)
            self.assertEqual(report['issue_matches'],24)
            self.assertTrue(all(o['response_source']=='mock' for o in report['observations']))
            self.assertTrue(all(o['configuration']['model']=='fixture-v1' for o in report['observations']))
