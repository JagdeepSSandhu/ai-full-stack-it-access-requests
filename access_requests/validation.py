"""Validate the exact JSON Schema vocabulary used by snapshot.schema.json."""
from datetime import date
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'snapshot.schema.json').read_text())
SCALARS = [key for key in SCHEMA['properties'] if key not in ('issues', 'supporting_quotes')]


def read_export(path):
    path = Path(path)
    raw = path.read_bytes()
    export = json.loads(raw.decode('utf-8'))
    if not isinstance(export, dict) or not isinstance(export.get('message'), str):
        raise ValueError('Export requires a message string')
    return {'document_id': path.name, 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'raw': raw, 'message': export['message']}


def check_schema(value, schema=SCHEMA, path='$'):
    types = {'object': dict, 'array': list, 'string': str, 'null': type(None)}
    names = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
    if not any(isinstance(value, types[name]) for name in names):
        raise ValueError(f'{path}: invalid type')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{path}: invalid enum value')
    if isinstance(value, dict):
        if set(schema.get('required', [])) - value.keys():
            raise ValueError(f'{path}: missing required keys')
        properties = schema['properties']
        if schema.get('additionalProperties') is False and value.keys() - properties.keys():
            raise ValueError(f'{path}: unexpected properties')
        for key, item in value.items():
            if key in properties:
                check_schema(item, properties[key], f'{path}.{key}')
    if isinstance(value, list):
        for item in value:
            check_schema(item, schema['items'], path+'[]')


def validate(extraction, message):
    check_schema(extraction)
    for field in ('request_date', 'start_date', 'end_date'):
        value = extraction[field]
        if value is not None:
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
            except ValueError as exc:
                raise ValueError(f'{field}: expected valid YYYY-MM-DD') from exc
    for quote in extraction['supporting_quotes']:
        if not quote or quote not in message:
            raise ValueError('Supporting quote is not a nonempty message substring')
    return extraction
