"""T-26–T-31: durable versioned intake, with plan-authored E01/E02 facts."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from access_requests.providers import MockProvider
from access_requests.validation import read_export
from access_requests.prompt import POLICY_TEXT

ROOT=Path(__file__).resolve().parents[1]
MOCKS=ROOT/'tests/mock_responses'


class StoreTests(unittest.TestCase):
    def setUp(self):
        from access_requests.store import Store
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'state.db'
        self.store=Store(self.db)
        self.doc=read_export(ROOT/'materials/requests/IT-001.json')

    def changed(self):
        path=Path(self.temp.name)/'IT-001.json'
        path.write_bytes(self.doc['raw'].replace(b'2026-11-06',b'2026-11-07'))
        return read_export(path)

    def test_T26_records_reopen_and_links(self):
        from access_requests.store import Store
        self.store.ingest(self.doc, MockProvider(MOCKS))
        self.store.ingest(read_export(ROOT/'materials/requests/IT-002.json'), MockProvider(MOCKS))
        current=Store(self.db).current()
        self.assertEqual(len(current),2)
        self.assertEqual(current[0]['extraction']['requester'],'Maya Chen')
        self.assertEqual(current[1]['owner'],'Security Review')
        self.assertEqual(current[0]['source_sha256'],hashlib.sha256(self.doc['raw']).hexdigest())
        self.assertEqual(current[0]['response_source'],'mock')
        self.assertIsNone(current[0]['error'])
        self.assertEqual(current[0]['document_id'],'IT-001.json')

    def test_T27_unchanged_reuses(self):
        p=MockProvider(MOCKS)
        self.store.ingest(self.doc,p)
        self.store.ingest(self.doc,p)
        self.assertEqual(len(p.calls),1)
        self.assertEqual(len(self.store.current()),1)
        self.assertEqual(len(self.store.history('IT-001.json')),1)

    def test_T28_source_change_retains_history(self):
        self.store.ingest(self.doc,MockProvider(MOCKS))
        self.store.ingest(self.changed(),MockProvider(MOCKS,['it-001-updated.json']))
        self.assertEqual(self.store.current()[0]['extraction']['end_date'],'2026-11-07')
        history=self.store.history('IT-001.json')
        self.assertEqual(history[0]['result']['extraction']['end_date'],'2026-11-06')
        self.assertEqual(history[0]['source_sha256'],self.doc['source_sha256'])
        self.assertNotEqual(history[0]['source_sha256'],history[1]['source_sha256'])

    def test_T29_failed_retry_after_success(self):
        for changed in [False,True]:
            self.store.ingest(self.doc,MockProvider(MOCKS),force=True)
            self.store.ingest(self.changed() if changed else self.doc,
                              MockProvider(MOCKS,['error.json']),force=True)
            current=self.store.current()[0]
            self.assertEqual(current['status'],'error')
            self.assertIsNone(current['extraction'])
            history=self.store.history('IT-001.json')
            self.assertEqual(history[-2]['result']['extraction']['end_date'],'2026-11-06')
            self.assertNotEqual(history[-2]['attempt_id'],current['attempt_id'])

    def test_T30_batch_omission(self):
        self.store.ingest(self.doc,MockProvider(MOCKS))
        other=read_export(ROOT/'materials/requests/IT-002.json')
        self.store.ingest(other,MockProvider(MOCKS))
        self.store.ingest(other,MockProvider(MOCKS))
        self.assertEqual([x['document_id'] for x in self.store.current()],['IT-001.json','IT-002.json'])

    def test_T31_settings_policy_provenance(self):
        p=MockProvider(MOCKS)
        self.store.ingest(self.doc,p)
        p.configuration['log_level']='debug'
        self.store.ingest(self.doc,p)
        self.assertEqual(len(p.calls),1)
        p.configuration['model']='fixture-v2'
        self.store.ingest(self.doc,p)
        self.assertEqual(len(p.calls),2)
        policy=POLICY_TEXT.replace('Complete staging/read requests go to System Owner with status review and next_action review-request.',
            'Complete staging/read requests go to Security Review with status review and next_action review-risk-then-owner.')
        self.store.ingest(self.doc,p,policy=policy)
        current=self.store.current()[0]
        self.assertEqual(current['owner'],'Security Review')
        self.assertEqual(current['settings']['model'],'fixture-v2')
        self.assertEqual(current['policy_version'],hashlib.sha256(policy.encode()).hexdigest())
        self.assertEqual(self.store.history('IT-001.json')[0]['result']['owner'],'System Owner')
