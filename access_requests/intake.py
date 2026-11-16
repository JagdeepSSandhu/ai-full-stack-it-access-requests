"""Single-document extraction; persistence and scheduling are separate layers."""
import json
from .validation import validate
from .policy import route


def extract_valid(document, provider, policy=None):
    reply = provider.extract(document['message'], document_id=document['document_id'])
    extraction = validate(json.loads(reply['output_text']), document['message'])
    return {'document_id': document['document_id'], 'source_sha256': document.get('source_sha256'),
            'extraction': extraction, **route(extraction, document['message'], document['document_id'], policy),
            'error': None, 'response_source': reply['response_source']}
