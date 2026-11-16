"""Direct Responses API adapter with an injectable HTTP transport."""
from dataclasses import dataclass, field
import json
import os
import urllib.request
import urllib.error
from .providers import ProviderError
from .prompt import PROMPT
from .validation import SCHEMA


@dataclass
class Settings:
    model: str = 'gpt-4.1-2025-04-14'
    endpoint: str = 'https://api.openai.com/v1/responses'
    max_output_tokens: int = 2500
    temperature: float = 0
    timeout: float = 30
    secret: str = field(default='', repr=False)

    @classmethod
    def from_env(cls):
        return cls(model=os.environ.get('MODEL_ID', cls.model),
                   endpoint=os.environ.get('MODEL_ENDPOINT', cls.endpoint),
                   max_output_tokens=int(os.environ.get('MAX_OUTPUT_TOKENS', 2500)),
                   temperature=float(os.environ.get('MODEL_TEMPERATURE', 0)),
                   timeout=float(os.environ.get('MODEL_TIMEOUT', 30)),
                   secret=os.environ.get('API_KEY', ''))


def http_transport(url, headers, body, timeout):
    request = urllib.request.Request(url, json.dumps(body).encode(), headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        return exc.code, ''  # Provider diagnostics may contain credentials; never persist them.
    except (OSError, TimeoutError) as exc:
        raise ProviderError('Provider connection failed or timed out', transient=True) from exc


class OpenAIProvider:
    def __init__(self, settings, *, transport=http_transport):
        self.settings = settings
        self.transport = transport
        self.response_source = 'openai/' + settings.model
        self.configuration = {'provider': 'openai', 'model': settings.model,
                              'endpoint': settings.endpoint, 'max_output_tokens': settings.max_output_tokens,
                              'temperature': settings.temperature, 'timeout': settings.timeout}

    def request(self, message):
        return {'model': self.settings.model, 'instructions': PROMPT, 'input': message,
                'max_output_tokens': self.settings.max_output_tokens,
                'temperature': self.settings.temperature, 'store': False,
                'text': {'format': {'type': 'json_schema', 'name': 'access_request',
                                    'schema': SCHEMA, 'strict': True}}}

    def evidence(self, message):
        return {'url': self.settings.endpoint, 'headers': {'Authorization': 'Bearer [REDACTED]'},
                'body': self.request(message), 'configuration': self.configuration,
                'response_handling': 'Check HTTP status, completed response and message status; reject refusal, '
                'incomplete/absent output, invalid JSON/schema/dates/quotes; route valid facts for human review.'}

    def extract(self, message, *, document_id=None):
        if not self.settings.secret:
            raise ProviderError('Missing API_KEY; configure credentials or use --provider mock')
        try:
            status, raw = self.transport(self.settings.endpoint,
                    {'Authorization': 'Bearer '+self.settings.secret, 'Content-Type': 'application/json'},
                    self.request(message), self.settings.timeout)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError('Provider transport failed', transient=True) from exc
        if status != 200:
            raise ProviderError(f'Provider HTTP {status}; retry transient failures or check configuration',
                                transient=status in (408, 429) or status >= 500)
        try:
            envelope = json.loads(raw)
            if envelope.get('status') != 'completed':
                raise ProviderError('Provider response incomplete or not completed')
            text = []
            for item in envelope.get('output', []):
                if item.get('type') != 'message':
                    continue
                if item.get('status') != 'completed':
                    raise ProviderError('Provider output message incomplete')
                for content in item.get('content', []):
                    if content.get('type') == 'refusal':
                        raise ProviderError('Provider refused extraction')
                    if content.get('type') == 'output_text':
                        text.append(content['text'])
            if not text:
                raise ProviderError('Provider returned no extraction text')
            actual_model = envelope.get('model', self.settings.model)
            return {'status': 'completed', 'output_text': ''.join(text),
                    'response_source': 'openai/'+actual_model}
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError('Malformed provider response envelope') from exc
