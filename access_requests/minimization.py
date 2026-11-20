"""Project messages to fixed extraction cues and request-local placeholders."""
from collections import Counter
import re

from .validation import check_schema


CUES = frozenset("""
access admin administrator am approval approved are as asked at between boss by can change changed
clarify correction could current date dated dates details end environment for from grant granted
has have here i in is it manager me my name need new next on only or permission please previous prod
production read reading ready request requesting same should since stage staging start submit
submitted system team than the then this through to until update was we were with withdraw withdrawal
withdrawn would write writing - /
""".split())
DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}\Z')
REQUEST_ID = re.compile(r'IT-[0-9]+\Z', re.ASCII | re.IGNORECASE)
DATE_FIELDS = ('request_date', 'start_date', 'end_date')
TEXT_FIELDS = ('request_id', 'requester', 'team', 'system', 'business_purpose', 'manager')


def segments(message):
    for word in re.finditer(r'\S+', message):
        start, end = word.span()
        token = word.group()
        after_open = token.lstrip('(')
        core = after_open.rstrip(').,;:!?')
        core_start = end - len(after_open)
        core_end = core_start + len(core)
        for start, end, is_word in ((start, core_start, False),
                                    (core_start, core_end, True), (core_end, end, False)):
            if start != end:
                yield start, end, is_word


class Projection:
    def __init__(self, message):
        self.source = message
        self.starts = {}
        self.ends = {}
        aliases = {}
        counts = Counter()
        pieces = []
        offset = previous_end = 0
        for start, end, is_word in segments(message):
            if pieces and start > previous_end:
                pieces.append('\n' if '\n' in message[previous_end:start] else ' ')
                offset += 1
            raw = message[start:end]
            piece = raw.lower()
            if is_word and (not raw.isascii() or piece not in CUES):
                kind = 'DATE' if DATE.fullmatch(raw) else 'ID' if REQUEST_ID.fullmatch(raw) else 'TEXT'
                if raw not in aliases:
                    counts[kind] += 1
                    aliases[raw] = f'[{kind}_{counts[kind]}]'
                piece = aliases[raw]
            self.starts[offset] = start
            pieces.append(piece)
            offset += len(piece)
            self.ends[offset] = end
            previous_end = end
        self.text = ''.join(pieces)

    def restore_span(self, value):
        if value:
            for match in re.finditer(re.escape(value), self.text):
                if match.start() in self.starts and match.end() in self.ends:
                    return self.source[self.starts[match.start()]:self.ends[match.end()]]
        raise ValueError('Extraction contains a value or quote without a complete source span')

    def restore(self, extraction):
        check_schema(extraction)
        restored = dict(extraction)
        for field in (*TEXT_FIELDS, *DATE_FIELDS):
            value = extraction[field]
            if value is None:
                continue
            if field in DATE_FIELDS and not re.fullmatch(r'\[DATE_[0-9]+\]', value):
                raise ValueError('Extraction date must reference a source date placeholder')
            restored[field] = self.restore_span(value)
        restored['supporting_quotes'] = [
            self.restore_span(quote) for quote in extraction['supporting_quotes']
        ]
        return restored
