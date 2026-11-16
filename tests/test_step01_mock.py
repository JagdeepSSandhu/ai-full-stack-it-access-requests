"""T-01: the application mock adapter, offline and fixture backed."""
import concurrent.futures
import json
from pathlib import Path
import socket
import threading
import unittest
from unittest.mock import patch

FIXTURES = Path(__file__).parent / 'mock_responses'


class MockProviderTests(unittest.TestCase):
    def test_T01_scripted_events_and_origin_without_network(self):
        from access_requests.providers import MockProvider, ProviderError
        gate = threading.Event()
        with patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')):
            provider = MockProvider(FIXTURES, ['it-001.json', 'error.json',
                                            'refusal.json', 'interrupted.json', 'it-001.json'], gate=gate)
            reply = provider.extract('message')
            self.assertEqual(reply['response_source'], 'mock')
            self.assertEqual(json.loads(reply['output_text'])['requester'], 'Maya Chen')
            with self.assertRaisesRegex(ProviderError, 'temporarily unavailable'):
                provider.extract('message')
            self.assertEqual(provider.extract('message')['status'], 'refused')
            self.assertEqual(provider.extract('message')['status'], 'incomplete')
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(provider.extract, 'message', delay=True)
                self.assertFalse(future.done())
                gate.set()
                self.assertEqual(future.result(timeout=2)['response_source'], 'mock')
            self.assertEqual(len(provider.calls), 5)
            self.assertEqual(provider.configuration['provider'], 'mock')
