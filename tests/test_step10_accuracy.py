"""T-38: comparison against independent plan facts, including negative controls."""
import copy
import json
from pathlib import Path
import unittest
from access_requests.providers import MockProvider
from access_requests.validation import read_export
from access_requests.intake import process
from test_step02_validation import PARAPHRASE

ROOT=Path(__file__).resolve().parents[1]
MOCKS=ROOT/'tests/mock_responses'


class AccuracyTests(unittest.TestCase):
    def test_T38_independent_comparison_fixed_denominator(self):
        from access_requests.accuracy import compare
        expected=json.loads((ROOT/'tests/expected.json').read_text())
        documents={p.name:read_export(p) for p in (ROOT/'materials/requests').glob('*.json')}
        documents['IT-021.json']={'document_id':'IT-021.json','message':PARAPHRASE}
        records=[process(doc,MockProvider(MOCKS)) for doc in documents.values()]
        good=compare(records,expected,documents)
        self.assertEqual(good['scalar_matches'],252)
        self.assertEqual(good['scalar_denominator'],252)
        self.assertEqual(good['route_matches'],63)
        self.assertEqual(good['quote_support_matches'],21)
        self.assertEqual(good['factual_errors'],[])
        wrong=copy.deepcopy(records)
        next(r for r in wrong if r['document_id']=='IT-001.json')['extraction']['permission']='admin'
        wrong=[r for r in wrong if r['document_id']!='IT-002.json']
        next(r for r in wrong if r['document_id']=='IT-003.json')['extraction']=None
        bad=compare(wrong,expected,documents)
        self.assertEqual(bad['scalar_denominator'],252)
        self.assertEqual(bad['scalar_matches'],227)
        self.assertEqual(len(bad['factual_errors']),25)
        self.assertIn('IT-002.json',bad['missing_documents'])
        self.assertEqual(len(bad['observations']),21)
