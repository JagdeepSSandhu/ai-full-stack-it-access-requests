"""T-02 through T-04: source and schema contracts, independent of routing."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from access_requests.providers import MockProvider

ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / 'tests/mock_responses'
PARAPHRASE = ('Please open request IT-021 dated 2026-10-22 for me, Maya Chen in Analytics. '
              'For a new grant, let me read Atlas in staging between 2026-10-23 and 2026-11-06. '
              'Priya Shah is my manager. I need to compare the weekly conversion dashboard '
              'with the spreadsheet after the event definitions changed.')


class ValidationTests(unittest.TestCase):
    def reply(self):
        return json.loads(MockProvider(MOCKS).extract('unused')['output_text'])

    def test_T02_schema_dates_and_exact_quotes(self):
        from access_requests.validation import validate
        message = json.loads((ROOT/'materials/requests/IT-001.json').read_text())['message']
        good = self.reply()
        self.assertEqual(validate(good, message)['requester'], 'Maya Chen')
        for key in good:
            bad = copy.deepcopy(good)
            del bad[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate(bad, message)
        variants = [[], {**good, 'extra': True}, {**good, 'requester': 10},
                    {**good, 'permission': 'root'}, {**good, 'environment': 'dev'},
                    {**good, 'kind': 'approved'}, {**good, 'issues': [1]},
                    {**good, 'supporting_quotes': None},
                    {**good, 'request_date': '2026-02-30'},
                    {**good, 'start_date': '2026-1-1'},
                    {**good, 'supporting_quotes': ['invented evidence']}]
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate(bad, message)
        for kind in ['new', 'change', 'withdrawal', 'other', None]:
            validate({**good, 'kind': kind}, message)
        for env in ['staging', 'production', None]:
            validate({**good, 'environment': env}, message)
        for permission in ['read', 'write', 'admin', None]:
            validate({**good, 'permission': permission}, message)
        nullable = {k: None for k in good if k not in ['issues', 'supporting_quotes']}
        validate({**nullable, 'issues': [], 'supporting_quotes': []}, message)

    def test_T03_original_bytes_and_message_not_metadata(self):
        from access_requests.validation import read_export, validate
        original = (ROOT/'materials/requests/IT-001.json').read_bytes()
        export = json.loads(original)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'IT-001.json'
            hashes = []
            for raw in [original, json.dumps({**export, 'subject': 'admin production',
                        'exported_at': '2030-01-01T00:00:00Z'}, indent=4).encode()]:
                path.write_bytes(raw)
                document = read_export(path)
                self.assertEqual(document['document_id'], 'IT-001.json')
                self.assertEqual(document['source_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(document['message'], export['message'])
                self.assertEqual(validate(self.reply(), document['message'])['request_date'], '2026-10-22')
                hashes.append(document['source_sha256'])
            self.assertNotEqual(*hashes)
            path.write_text(json.dumps({'message': 'Maya\nChen\u00e9'}))
            validate({**self.reply(), 'supporting_quotes': ['Maya\nChené']}, read_export(path)['message'])

    def test_T04_200_words(self):
        from access_requests.validation import read_export, validate
        padding, remainder = divmod(200-len(PARAPHRASE.split()), 4)
        message = PARAPHRASE + ' This is background context.' * padding + ' Background.' * remainder
        self.assertEqual(len(message.split()), 200)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'IT-021.json'
            path.write_text(json.dumps({'message': message}))
            reply = MockProvider(MOCKS, ['it-021.json']).extract(message)
            result = validate(json.loads(reply['output_text']), read_export(path)['message'])
            self.assertEqual(result['request_id'], 'IT-021')
            self.assertEqual(result['end_date'], '2026-11-06')
