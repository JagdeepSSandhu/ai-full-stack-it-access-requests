"""Compare measured outputs with independently authored, source-grounded facts."""
from collections import Counter
import json
from pathlib import Path
from .validation import SCALARS


def compare(records, expected, documents):
    counts = Counter(r['document_id'] for r in records)
    actual = {r['document_id']:r for r in records}
    summary = {'scalar_matches':0,'scalar_denominator':len(expected)*len(SCALARS),
               'route_matches':0,'route_denominator':len(expected)*3,
               'quote_support_matches':0,'quote_support_denominator':len(expected),
               'issue_matches':0,'issue_denominator':0,'factual_errors':[], 'purpose_review':[],
               'missing_documents':sorted(set(expected)-set(actual)),
               'unexpected_documents':sorted(set(actual)-set(expected)),
               'duplicate_documents':sorted(k for k,v in counts.items() if v>1),'observations':[]}
    for name, ground in sorted(expected.items()):
        record = actual.get(name,{})
        extraction = record.get('extraction')
        summary['observations'].append({'document_id':name,
             'response_source':record.get('response_source','missing'),
             'configuration':record.get('settings',{'provider':record.get('response_source','missing')}),
             'policy_version':record.get('policy_version')})
        for field in SCALARS:
            value = extraction.get(field) if isinstance(extraction,dict) else None
            if isinstance(extraction,dict) and field in extraction and value == ground['extraction'][field]:
                summary['scalar_matches'] += 1
            else:
                error = {'document_id':name,'field':field,'expected':ground['extraction'][field],
                         'actual':value,'extraction_present':isinstance(extraction,dict)}
                summary['factual_errors'].append(error)
                if field == 'business_purpose' and value is not None:
                    summary['purpose_review'].append(error)
        summary['route_matches'] += sum(record.get(k)==v for k,v in ground['route'].items())
        quotes = extraction.get('supporting_quotes',[]) if isinstance(extraction,dict) else []
        message = documents[name]['message']
        if quotes and all(isinstance(q,str) and q and q in message for q in quotes):
            summary['quote_support_matches'] += 1
        categories = [k for k,v in ground['extraction'].items() if v is None]
        categories += {'IT-006.json':['instruction'],'IT-014.json':['start_date after end_date'],
                       'IT-016.json':['mismatch']}.get(name,[])
        summary['issue_denominator'] += len(categories)
        issues = extraction.get('issues',[]) if isinstance(extraction,dict) else []
        summary['issue_matches'] += sum(any(category.lower() in issue.lower() for issue in issues)
                                        for category in categories)
    return summary


def write_report(path, report, expected):
    lines = ['# Accuracy procedure and observations','',
        'Expected facts were authored from planning/plan.md E01–E21 and the quoted messages/policy, '
        'before application output was measured. tests/expected.json is the independent manifest; '
        'deliverables/expected.json is its submitted copy. The synthetic export is materials/synthetic/IT-021.json.', '',
        'Command: `env -u API_KEY python3 -m access_requests accuracy --report deliverables/accuracy.md`.', '',
        'Compare all 12 scalar fields literally, including expected nulls: 21 × 12 = 252 opportunities. '
        'Missing/error extractions mismatch all 12 fields; missing keys mismatch even expected null. '
        'Missing documents remain in the denominator. Exact business-purpose excerpts are predeclared; '
        'a different purpose is flagged for human review, including potentially accurate paraphrases, '
        'without changing the exact-match score. Factual errors below require source review. '
        'Route fields have 63 opportunities. Quote support counts 21 documents with nonempty exact '
        'substring quotes. Issue coverage counts each expected missing/unresolved field plus the '
        'instruction, mismatch and reversed-date categories; issue wording is not an exact-match field.', '',
        'These are MOCK pipeline observations using fixture-v1, not evidence of live model extraction '
        'accuracy. No live observations were made. The implemented provider contract configuration is '
        'OpenAI gpt-4.1-2025-04-14, temperature 0, max_output_tokens 2500, strict schema; it was tested '
        'only with intercepted HTTP fixtures.', '', '## Source-derived expected facts','',
        '| Document | Expected scalar facts | Expected route | Source evidence |',
        '|---|---|---|---|']
    for name, ground in sorted(expected.items()):
        cells = [name,json.dumps(ground['extraction'],ensure_ascii=False),json.dumps(ground['route']),ground['evidence']]
        lines.append('| '+' | '.join(cell.replace('|','\\|').replace('\n',' ') for cell in cells)+' |')
    lines += ['', '## Observed mock comparisons', '', '```json',json.dumps(report,indent=2), '```','']
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text('\n'.join(lines))
