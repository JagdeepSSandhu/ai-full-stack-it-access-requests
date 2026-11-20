"""Worked examples obey extraction and masked-provider contracts offline."""
import json
import unittest

from access_requests.minimization import Projection
from access_requests.openai_provider import OpenAIProvider, Settings
from access_requests.prompt import LIVE_PROMPT, PROMPT
from access_requests.validation import SCALARS, validate


def examples(prompt):
    return json.loads(prompt.split('Worked examples (input/output pairs):\n', 1)[1])


class PromptExampleTests(unittest.TestCase):
    def test_examples_validate_and_explain_every_unresolved_fact(self):
        for example in examples(PROMPT):
            with self.subTest(message=example['input']):
                output = validate(example['output'], example['input'])
                for field in SCALARS:
                    if output[field] is None:
                        self.assertTrue(any(field in issue for issue in output['issues']), field)

    def test_live_examples_round_trip_through_provider(self):
        for raw, masked in zip(examples(PROMPT), examples(LIVE_PROMPT), strict=True):
            with self.subTest(message=raw['input']):
                self.assertEqual(Projection(raw['input']).text, masked['input'])

                def transport(url, headers, body, timeout):
                    self.assertEqual(body['input'], masked['input'])
                    self.assertEqual(examples(body['instructions']), examples(LIVE_PROMPT))
                    return 200, json.dumps({
                        'status': 'completed',
                        'output': [{'type': 'message', 'status': 'completed', 'content': [{
                            'type': 'output_text', 'text': json.dumps(masked['output'])}]}]})

                provider = OpenAIProvider(Settings(secret='dummy-secret'), transport=transport)
                result = provider.extract(raw['input'])
                self.assertEqual(json.loads(result['output_text']), raw['output'])
