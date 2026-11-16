"""T-33–T-36: slow calls, killed workers, outages and mock workloads."""
import concurrent.futures
import json
import multiprocessing
from pathlib import Path
import tempfile
import threading
import time
import unittest
from access_requests.store import Store
from access_requests.validation import read_export
from access_requests.providers import MockProvider
from test_step02_validation import PARAPHRASE

ROOT=Path(__file__).resolve().parents[1]
MOCKS=ROOT/'tests/mock_responses'


class GatedProvider(MockProvider):
    def extract(self,message,*,document_id=None,**kwargs):
        return super().extract(message,document_id=document_id,delay=document_id=='IT-001.json')


def killed_worker(db,gate):
    from access_requests.scheduler import run
    run(Store(db),GatedProvider(MOCKS,gate=gate),workers=1,lease=.2)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'state.db')

    def register(self,*numbers):
        for n in numbers:
            self.store.register(read_export(ROOT/f'materials/requests/IT-{n:03}.json'),MockProvider(MOCKS).configuration)

    def test_T33_slow_call_leaves_other_work_available(self):
        from access_requests.scheduler import run
        self.register(1,2)
        gate=threading.Event()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future=pool.submit(run,self.store,GatedProvider(MOCKS,gate=gate),workers=2,lease=.3)
            try:
                deadline=time.monotonic()+5
                while len(self.store.current())<1 and time.monotonic()<deadline: time.sleep(.01)
                self.assertEqual(self.store.current()[0]['extraction']['request_id'],'IT-002')
                self.assertEqual(self.store.current()[0]['owner'],'Security Review')
                self.assertFalse(future.done())
            finally: gate.set()
            future.result(timeout=5)
        self.assertEqual(len(self.store.current()),2)

    def test_T34_killed_worker_resume(self):
        from access_requests.scheduler import run
        self.store.ingest(read_export(ROOT/'materials/requests/IT-002.json'),MockProvider(MOCKS))
        self.register(1,18)
        gate=multiprocessing.Event()
        worker=multiprocessing.Process(target=killed_worker,args=(self.store.path,gate))
        worker.start()
        deadline=time.monotonic()+5
        while self.store.pending()[0]['state']!='running' and time.monotonic()<deadline: time.sleep(.01)
        worker.terminate(); worker.join(5)
        self.assertFalse(worker.is_alive())
        time.sleep(.25)
        run(self.store,MockProvider(MOCKS),workers=2,lease=.3)
        self.assertEqual(len(self.store.current()),3)
        self.assertEqual(len(self.store.history('IT-002.json')),1)
        self.assertEqual(self.store.pending(),[])

    def test_T35_transient_retries_and_terminal_failure(self):
        from access_requests.scheduler import run
        self.register(1,2,18)
        class Outage(MockProvider):
            def __init__(self):
                super().__init__(MOCKS)
                self.perdoc={'IT-001.json':MockProvider(MOCKS,['error.json','it-001.json']),
                             'IT-002.json':MockProvider(MOCKS,['error.json','error.json'])}
            def extract(self,message,*,document_id=None):
                if document_id in self.perdoc:
                    return self.perdoc[document_id].extract(message,document_id=document_id)
                return super().extract(message,document_id=document_id)
        provider=Outage()
        run(self.store,provider,workers=2,retries=1,backoff=.01)
        records={r['document_id']:r for r in self.store.current()}
        self.assertEqual(records['IT-001.json']['next_action'],'review-request')
        self.assertEqual(records['IT-002.json']['status'],'error')
        self.assertEqual(records['IT-018.json']['owner'],'System Owner')
        self.assertEqual(len(self.store.history('IT-001.json')),2)
        self.store.ingest(read_export(ROOT/'materials/requests/IT-002.json'),MockProvider(MOCKS),force=True)
        self.assertEqual(self.store.current()[1]['owner'],'Security Review')

    def test_T36_workload_accounting(self):
        from access_requests.scheduler import run
        class Template(MockProvider):
            def extract(self,message,*,document_id=None):
                reply=MockProvider(MOCKS,['it-021.json']).extract(message)
                reply['output_text']=reply['output_text'].replace('IT-021',Path(document_id).stem)
                return reply
        provider=Template(MOCKS)
        for count in [400,2000]:
            db=Store(Path(self.temp.name)/f'load-{count}.db')
            for n in range(1000,1000+count):
                name=f'IT-{n}.json'; message=PARAPHRASE.replace('IT-021',f'IT-{n}')
                raw=json.dumps({'message':message}).encode()
                import hashlib
                db.register({'document_id':name,'message':message,'raw':raw,
                    'source_sha256':hashlib.sha256(raw).hexdigest()},provider.configuration)
            started=time.monotonic()
            run(db,provider,workers=4)
            records=db.current()
            self.assertEqual(len(records),count)
            self.assertEqual(len({r['document_id'] for r in records}),count)
            self.assertTrue(all(r['status']=='review' and r['owner']=='System Owner' for r in records))
            self.assertEqual(db.pending(),[])
            print(f'MOCK workload: {count} messages, workers=4, processing_seconds={time.monotonic()-started:.3f}')
