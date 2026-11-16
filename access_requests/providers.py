"""Provider boundary and deterministic offline adapter."""
import json
from pathlib import Path
import threading


class ProviderError(Exception):
    def __init__(self, message, transient=False):
        super().__init__(message)
        self.transient = transient


class MockProvider:
    def __init__(self, directory, script=None, *, gate=None):
        self.directory = Path(directory)
        self.script = iter(script) if script is not None else None
        self.gate = gate
        self.calls = []
        self.lock = threading.Lock()
        self.configuration = {'provider': 'mock', 'model': 'fixture-v1'}

    def extract(self, message, *, document_id='IT-001.json', delay=False):
        with self.lock:
            name = next(self.script) if self.script is not None else document_id.lower()
            self.calls.append({'document_id': document_id, 'fixture': name})
        if delay and self.gate:
            if not self.gate.wait(10):
                raise ProviderError('Mock gate timed out')
        try:
            reply = json.loads((self.directory / name).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ProviderError(f'Missing or invalid mock fixture: {name}') from exc
        if 'error' in reply:
            raise ProviderError(reply['error'], reply.get('transient', False))
        if 'extraction' in reply:
            reply['output_text'] = json.dumps(reply.pop('extraction'))
        return {**reply, 'response_source': 'mock'}
