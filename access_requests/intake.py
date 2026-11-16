"""Single-document extraction; persistence and scheduling are separate layers."""
import json
import shlex
from .providers import ProviderError
from .validation import validate
from .policy import route


def extract_valid(document, provider, policy=None):
    reply = provider.extract(document['message'], document_id=document['document_id'])
    if reply.get('status') != 'completed':
        raise ValueError('Provider response ' + str(reply.get('status', 'missing completion status')))
    extraction = validate(json.loads(reply['output_text']), document['message'])
    return {'document_id': document['document_id'], 'source_sha256': document.get('source_sha256'),
            'extraction': extraction, **route(extraction, document['message'], document['document_id'], policy),
            'error': None, 'response_source': reply['response_source']}


def process(document, provider, policy=None):
    try:
        return extract_valid(document, provider, policy)
    except (ProviderError, ValueError, KeyError, TypeError) as exc:
        name = document['document_id']
        return {'document_id': name, 'source_sha256': document.get('source_sha256'),
                'extraction': None, 'status': 'error', 'owner': 'IT Service Desk',
                'next_action': 'retry-extraction', 'error': str(exc),
                'transient': isinstance(exc, ProviderError) and exc.transient,
                'response_source': getattr(provider, 'response_source', 'mock'),
                'retry_command': 'python3 -m access_requests retry ' + shlex.quote(name)}
