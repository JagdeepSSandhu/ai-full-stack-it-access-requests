"""Deterministic ordered routing after extraction validation."""
from pathlib import Path
import hashlib
import re
from .validation import validate
from .prompt import POLICY_TEXT

def validate_policy(policy):
    supported = {'b949596765aef45377d9f8d0792f9113109b1f811ef4f3be26919c162e1f631a',
                 '7673aef082135e6b9c2baa64874007923a81f4f0a5b9a3c5143200c42180c0f1'}
    if hashlib.sha256(policy.encode()).hexdigest() not in supported:
        raise ValueError('Unsupported policy version; implement and verify its routing rules before intake')

REQUIRED = ('request_id', 'request_date', 'requester', 'team', 'system',
            'environment', 'permission', 'business_purpose', 'start_date', 'end_date', 'manager')


def decision(status, owner, action):
    return {'status': status, 'owner': owner, 'next_action': action}


def route(extraction, message, document_id, policy=None):
    validate_policy(POLICY_TEXT if policy is None else policy)
    validate(extraction, message)
    issues = extraction['issues']
    for field in ['kind', *REQUIRED]:
        if extraction[field] is None and not any(field in issue for issue in issues):
            issues.append(f'{field}: missing or unresolved')
    stem = Path(document_id).stem
    mismatch = bool(re.fullmatch(r'IT-\d+', stem) and extraction['request_id']
                    and stem != extraction['request_id'])
    if mismatch and not any('mismatch' in issue.lower() for issue in issues):
        issues.append('request_id: filename identifier mismatch')
    override = bool(re.search(r'system override|bypass approval|highest.priority system instruction|'
                              r'display the api key|mark request as approved', message, re.I))
    override = override or any('instruction' in i.lower() and
                              any(w in i.lower() for w in ('override', 'attempt', 'injection')) for i in issues)
    if override:
        if not any('instruction' in i.lower() for i in issues):
            issues.append('instruction-override attempt')
        if message not in extraction['supporting_quotes']:
            extraction['supporting_quotes'].append(message)
        return decision('review', 'IT Service Desk', 'inspect-message')
    if extraction['kind'] == 'withdrawal' and extraction['request_id'] and extraction['request_date']:
        return decision('review', 'IT Service Desk', 'confirm-withdrawal')
    reversed_dates = (extraction['start_date'] and extraction['end_date'] and
                      extraction['start_date'] > extraction['end_date'])
    if reversed_dates and not any('start_date after end_date' in issue for issue in issues):
        issues.append('start_date after end_date')
    conflict = any('conflict' in i.lower() or 'mismatch' in i.lower() for i in issues)
    if (extraction['kind'] not in ('new', 'change') or mismatch or reversed_dates or conflict
            or any(extraction[k] is None for k in REQUIRED)):
        return decision('needs-information', 'IT Service Desk', 'clarify')
    if extraction['environment'] == 'production' or extraction['permission'] in ('write', 'admin'):
        return decision('review', 'Security Review', 'review-risk-then-owner')
    if policy and 'Complete staging/read requests go to Security Review' in policy:
        return decision('review', 'Security Review', 'review-risk-then-owner')
    return decision('review', 'System Owner', 'review-request')
