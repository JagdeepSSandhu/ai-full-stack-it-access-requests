"""Bounded workers, renewable leases and durable delayed retries."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from .intake import process
from .store import production_settings


def run(store, provider, *, workers=4, rate=0, retries=2, backoff=1, lease=60, on_result=None):
    if workers < 1 or rate < 0 or retries < 0 or backoff < 0 or lease <= 0:
        raise ValueError('Invalid scheduler limits')
    limiter = threading.Lock()
    next_call = [0.0]
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            claim = store.claim(lease=lease)
            if claim is None:
                if not store.pending():
                    return
                time.sleep(.02)
                continue
            if json_settings(claim['settings']) != production_settings(provider.configuration):
                store.release(claim['id'], claim['token'])
                stop.set()
                raise ValueError('Pending attempt settings differ; resume with its original provider settings')
            stopped = threading.Event()

            def heartbeat():
                while not stopped.wait(lease/3):
                    if not store.renew(claim['id'],claim['token'],lease=lease):
                        return

            heartbeat_thread = threading.Thread(target=heartbeat,daemon=True)
            heartbeat_thread.start()
            try:
                if rate:
                    with limiter:
                        delay = max(0,next_call[0]-time.monotonic())
                        next_call[0] = max(next_call[0],time.monotonic())+1/rate
                    if delay:
                        time.sleep(delay)
                document = store.document(claim['id'])
                result = process(document,provider,claim['policy'])
                committed = store.finish(claim['id'],result,token=claim['token'])
                if committed and result.get('transient') and claim['retry_count'] < retries:
                    store.retry_later(claim['id'],delay=backoff*2**claim['retry_count'])
                if committed and on_result:
                    on_result()
            finally:
                stopped.set()
                heartbeat_thread.join()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker) for _ in range(workers)]
        for future in futures:
            future.result()


def json_settings(text):
    import json
    return json.loads(text)
