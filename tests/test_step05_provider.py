"""T-25: intercepted Responses HTTP contract; no environment credential access."""
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch
from access_requests.validation import read_export
from access_requests.intake import process
from access_requests.prompt import POLICY_TEXT

ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT/'tests/mock_responses'


class ProviderContractTests(unittest.TestCase):
    def test_T25_contract_status_and_redaction(self):
        from access_requests.openai_provider import OpenAIProvider, Settings
        requests = []
        document = read_export(ROOT/'materials/requests/IT-001.json')
        for fixture, action in [('provider-success.json', 'review-request'),
                                ('provider-refusal.json', 'retry-extraction'),
                                ('provider-incomplete.json', 'retry-extraction'),
                                ('provider-error.json', 'retry-extraction')]:
            response = json.loads((MOCKS/fixture).read_text())
            def transport(url, headers, body, timeout):
                requests.append((url, headers, body, timeout))
                return (response['status'], response['body']) if 'body' in response else (200, json.dumps(response))
            with patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')):
                adapter = OpenAIProvider(Settings(secret='dummy-secret'), transport=transport)
                result = process(document, adapter)
            self.assertEqual(result['next_action'], action)
            if action == 'review-request':
                self.assertEqual(result['extraction']['requester'], 'Maya Chen')
                self.assertTrue(all(quote in document['message']
                                    for quote in result['extraction']['supporting_quotes']))
            self.assertNotIn('dummy-secret', json.dumps(result))
            self.assertNotIn('dummy-secret', json.dumps(adapter.evidence(document['message'])))
            self.assertEqual(result['response_source'], 'openai/gpt-4.1-2025-04-14')
        url, headers, body, timeout = requests[0]
        self.assertEqual(url, 'https://api.openai.com/v1/responses')
        self.assertEqual(headers['Authorization'], 'Bearer dummy-secret')
        self.assertEqual(body['model'], 'gpt-4.1-2025-04-14')
        self.assertEqual(body['text']['format']['type'], 'json_schema')
        self.assertTrue(body['text']['format']['strict'])
        self.assertIn('[TEXT_1] [TEXT_2] from [TEXT_3]', body['input'])
        self.assertIn('[ID_1] dated [DATE_1]', body['input'])
        self.assertNotIn('Maya', json.dumps(body))
        self.assertNotIn('2026-10-22', json.dumps(body))
        self.assertNotIn(POLICY_TEXT, body['instructions'])
        self.assertFalse(body['store'])
        self.assertEqual(timeout, 30)

    def test_model_input_and_evidence_use_the_same_minimized_text(self):
        from access_requests.openai_provider import OpenAIProvider, Settings
        message = ('UnlistedPerson from PrivateTeam requests production admin on host.example.com. '
                   'Email user@example.com, ticket IT-9281, date 2032-04-19. '
                   'Secret sk-example-1234567890 and 123-45-6789.')
        provider = OpenAIProvider(Settings(secret='dummy-secret'))
        body = provider.request(message)
        evidence = provider.evidence(message)
        self.assertEqual(evidence['body'], body)
        self.assertIn('production admin', body['input'])
        for private_value in ('UnlistedPerson', 'PrivateTeam', 'host.example.com', 'user@example.com',
                              'IT-9281', '2032-04-19', 'sk-example-1234567890', '123-45-6789'):
            self.assertNotIn(private_value, json.dumps(evidence))

    def test_reject_unapproved_endpoints_before_transport(self):
        from access_requests.openai_provider import NoRedirects, OpenAIProvider, Settings
        for endpoint in ('http://api.openai.com/v1/responses',
                         'https://other.example.invalid/v1/responses',
                         'https://api.openai.com/v1/responses?extra=1'):
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(ValueError, 'approved'):
                OpenAIProvider(Settings(endpoint=endpoint, secret='dummy-secret'))
        self.assertIsNone(NoRedirects().redirect_request(None, None, 302, '', {}, ''))

    def test_restore_only_complete_placeholders_and_exact_source_spans(self):
        from access_requests.minimization import Projection
        source = 'Example\tPerson called (Example Service), on 2032-04-19.'
        projection = Projection(source)
        self.assertEqual(projection.restore_span('[TEXT_1] [TEXT_2]'), 'Example\tPerson')
        self.assertEqual(projection.restore_span('([TEXT_1] [TEXT_4]),'), '(Example Service),')
        for value in ('TEXT_1', '[TEXT_900]', 'Example Person'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                projection.restore_span(value)
