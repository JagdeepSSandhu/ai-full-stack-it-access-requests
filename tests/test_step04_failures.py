"""T-21–T-24: no partial/refused data reaches review routing."""
import json
from pathlib import Path
import unittest
from access_requests.providers import MockProvider
from access_requests.validation import read_export

ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT/'tests/mock_responses'


class FailureTests(unittest.TestCase):
    def error(self, fixture):
        from access_requests.intake import process
        result = process(read_export(ROOT/'materials/requests/IT-001.json'), MockProvider(MOCKS,[fixture]))
        self.assertEqual((result['status'], result['owner'], result['next_action']),
                         ('error','IT Service Desk','retry-extraction'))
        self.assertIsNone(result['extraction'])
        self.assertTrue(result['error'])
        self.assertIn('IT-001.json', result['retry_command'])
        return result

    def test_T21_malformed(self):
        self.error('malformed-json.json')

    def test_T22_independent_failure(self):
        from access_requests.intake import process
        self.error('error.json')
        result = process(read_export(ROOT/'materials/requests/IT-002.json'), MockProvider(MOCKS))
        self.assertEqual(result['owner'], 'Security Review')
        self.assertEqual(result['extraction']['permission'], 'write')

    def test_T23_refusal(self):
        self.assertIn('refus', self.error('refusal.json')['error'].lower())

    def test_T24_interrupted(self):
        self.assertIn('incomplete', self.error('interrupted.json')['error'].lower())
        self.assertIn('incomplete', self.error('incomplete-valid.json')['error'].lower())
