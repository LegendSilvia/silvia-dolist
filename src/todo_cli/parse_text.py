"""Natural-language extraction for todo input.

Pulls due dates, priorities, tags, and project out of a free-form line so
users can type "project review by friday #work @q2" instead of
"--due 2026-05-15 --tags work --project q2 project review".

Strict enough to avoid false positives:
- Date phrases are only stripped when they sit at the end of the line or
  follow a trigger word (due, by, on, before, after).
- Time-only matches ("at 3pm") are ignored.
- Stripping a date never empties the title; if it would, the line is left
  untouched.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional

import parsedatetime

_cal = parsedatetime.Calendar()

_TAG_RE = re.compile(r"#([A-Za-z0-9][A-Za-z0-9_-]*)")
_PROJECT_RE = re.compile(r"@([A-Za-z0-9][A-Za-z0-9_-]*)")
_TRIGGER_RE = re.compile(r"\b(due|by|on|before|after)\s+$", re.IGNORECASE)

# Short forms parsedatetime doesn't recognize. Only abbreviations that
# aren't real English words go here — "tom" is excluded to avoid mangling
# names ("tom called").
_SHORT_DATE_ALIASES = {
    "tmr": "tomorrow",
    "tmrw": "tomorrow",
    "tomo": "tomorrow",
    "tdy": "today",
    "eod": "end of day",
    "eow": "end of week",
    "eom": "end of month",
}
_SHORT_DATE_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _SHORT_DATE_ALIASES) + r")\b",
    re.IGNORECASE,
)

_PRIORITY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:p1|urgent|high\s+priority)\b", re.IGNORECASE), "high"),
    (re.compile(r"\b(?:p3|low\s+priority)\b", re.IGNORECASE), "low"),
    (re.compile(r"\b(?:p2|med(?:ium)?\s+priority)\b", re.IGNORECASE), "med"),
]


@dataclass
class ParsedInput:
    text: str
    due: Optional[date] = None
    due_time: Optional[time] = None
    priority: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    project: Optional[str] = None


def parse_input(line: str, *, ref: Optional[datetime] = None) -> ParsedInput:
    if ref is None:
        ref = datetime.now()
    remainder = line

    tags = _TAG_RE.findall(remainder)
    remainder = _TAG_RE.sub("", remainder)

    project_match = _PROJECT_RE.search(remainder)
    project = project_match.group(1) if project_match else None
    remainder = _PROJECT_RE.sub("", remainder)

    priority: Optional[str] = None
    for pat, val in _PRIORITY_PATTERNS:
        m = pat.search(remainder)
        if m:
            priority = val
            remainder = remainder[: m.start()] + remainder[m.end():]
            break

    due: Optional[date] = None
    due_time: Optional[time] = None
    remainder = _SHORT_DATE_RE.sub(
        lambda m: _SHORT_DATE_ALIASES[m.group(1).lower()], remainder
    )
    nlp_result = _cal.nlp(remainder, sourceTime=ref)
    if nlp_result:
        for parsed_dt, code, start, end, _matched in nlp_result:
            preceding = remainder[:start]
            following = remainder[end:].strip()
            trigger = _TRIGGER_RE.search(preceding)
            if not (trigger or not following):
                continue
            strip_start = trigger.start() if trigger else start
            candidate = (remainder[:strip_start] + remainder[end:]).strip()
            if not candidate:
                continue
            due = parsed_dt.date()
            # codes: 1=date-only, 2=time-only, 3=date+time
            if code in (2, 3):
                due_time = parsed_dt.time().replace(second=0, microsecond=0)
            remainder = candidate
            break

    text = re.sub(r"\s+", " ", remainder).strip()
    return ParsedInput(
        text=text, due=due, due_time=due_time,
        priority=priority, tags=tags, project=project,
    )
