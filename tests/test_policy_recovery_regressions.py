"""Regression checks for policy changes and mixed provider settings."""
from pathlib import Path
import tempfile
import unittest

from access_requests.policy import route
from access_requests.prompt import POLICY_TEXT
from access_requests.providers import MockProvider
from access_requests.scheduler import run
from access_requests.store import Store
from access_requests.validation import read_export

ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / 'tests/mock_responses'


class PolicyRecoveryTests(unittest.TestCase):
    def test_unimplemented_policy_change_is_rejected(self):
        import json
        fixture = json.loads((MOCKS / 'it-002.json').read_text())['extraction']
        doc = read_export(ROOT / 'materials/requests/IT-002.json')
        changed = POLICY_TEXT.replace('Complete new/change requests involving production, write or admin',
                                      'Complete new/change requests involving production or admin')
        with self.assertRaisesRegex(ValueError, 'Unsupported policy'):
            route(fixture, doc['message'], doc['document_id'], changed)

    def test_mismatched_settings_leave_attempt_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'state.db')
            doc = read_export(ROOT / 'materials/requests/IT-001.json')
            provider = MockProvider(MOCKS)
            settings = dict(provider.configuration, model='different-model')
            store.register(doc, settings)
            with self.assertRaisesRegex(ValueError, 'settings differ'):
                run(store, provider, workers=1, lease=60)
            self.assertEqual(store.pending()[0]['state'], 'pending')
            self.assertEqual(provider.calls, [])
