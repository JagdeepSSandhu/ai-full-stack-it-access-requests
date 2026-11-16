"""T-40: artifact readiness is distinct from external submission evidence."""
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class SubmissionTests(unittest.TestCase):
    def test_T40_required_artifacts_and_root_link(self):
        from access_requests.submission import readiness, REQUIRED
        link='https://github.com/JagdeepSSandhu/ai-full-stack-it-access-requests'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for name in REQUIRED:
                path=root/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('fixture inventory; no model response required')
            self.assertTrue(readiness(root,link)['artifacts_ready'])
            for name in REQUIRED:
                path=root/name; path.unlink()
                result=readiness(root,link)
                self.assertFalse(result['artifacts_ready'])
                self.assertIn(name,result['missing'])
                path.write_text('fixture inventory')
            for invalid in [link+'/tree/main',link+'/pull/1','https://example.com/repository']:
                self.assertFalse(readiness(root,invalid)['root_link_valid'])
        actual=readiness(ROOT,link)
        self.assertTrue(actual['artifacts_ready'],actual)
        self.assertEqual(actual['external_pending'],['capture/commit verification','default-branch push','Classroom submission'])
