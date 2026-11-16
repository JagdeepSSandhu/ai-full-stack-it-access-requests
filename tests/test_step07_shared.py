"""T-32: multi-process claims, stale workers and crash-safe publication."""
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from access_requests.providers import MockProvider
from access_requests.validation import read_export
from access_requests.intake import process
from access_requests.store import Store

ROOT=Path(__file__).resolve().parents[1]
MOCKS=ROOT/'tests/mock_responses'


def operator(db, barrier):
    store=Store(db)
    barrier.wait(timeout=10)
    for number in [1,2]:
        store.ingest(read_export(ROOT/f'materials/requests/IT-{number:03}.json'),MockProvider(MOCKS))


def crash_publish(db, target):
    from access_requests.publication import publish
    publish(Store(db),target,hook=lambda stage: os._exit(17) if stage=='before_switch' else None)


class SharedTests(unittest.TestCase):
    def test_T32_overlap_stale_completion_and_publication_crash(self):
        from access_requests.publication import publish, read_generation
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'state.db'
            store=Store(db)
            barrier=multiprocessing.Barrier(2)
            workers=[multiprocessing.Process(target=operator,args=(db,barrier)) for _ in range(2)]
            for p in workers: p.start()
            for p in workers:
                p.join(15)
                self.assertFalse(p.is_alive())
                self.assertEqual(p.exitcode,0)
            self.assertEqual(len(store.current()),2)
            self.assertEqual(len(store.history('IT-001.json')),1)
            target=Path(td)/'deliverables'
            publish(store,target)
            old=read_generation(target)
            self.assertEqual(old['queue'][0]['attempt_id'],old['extractions'][0]['attempt_id'])
            doc=read_export(ROOT/'materials/requests/IT-001.json')
            attempt=store.register(doc,MockProvider(MOCKS).configuration,force=True)
            claim=store.claim(attempt)
            changed=Path(td)/'IT-001.json'
            changed.write_bytes(doc['raw'].replace(b'2026-11-06',b'2026-11-07'))
            store.ingest(read_export(changed),MockProvider(MOCKS,['it-001-updated.json']))
            self.assertFalse(store.finish(attempt,process(doc,MockProvider(MOCKS)),token=claim['token']))
            self.assertEqual(store.current()[0]['extraction']['end_date'],'2026-11-07')
            worker=multiprocessing.Process(target=crash_publish,args=(db,target))
            worker.start(); worker.join(10)
            self.assertEqual(worker.exitcode,17)
            self.assertEqual(read_generation(target),old)
            publish(store,target)
            current=read_generation(target)
            self.assertEqual(current['extractions'][0]['extraction']['end_date'],'2026-11-07')
            for queue, extraction in zip(current['queue'],current['extractions']):
                self.assertEqual(queue['document_id'],extraction['document_id'])
                self.assertEqual(queue['source_sha256'],extraction['source_sha256'])
