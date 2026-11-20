from __future__ import annotations
import logging
import re

_PATTERNS = [
    re.compile(r"(?i)(x-api-key\s*[:=]\s*)[^\s,;'\"]+"),
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;'\"]+"),
    re.compile(r"(?i)([?&](?:key|api[_-]?key|accesskey|token|secret)=)[^&\s'\"]+"),
]


def redact(text: str, secrets: tuple = ()) -> str:
    out = str(text)
    for s in secrets:
        if s and len(s) >= 4:
            out = out.replace(s, "***REDACTED***")
    for p in _PATTERNS:
        out = p.sub(r"\1***REDACTED***", out)
    return out


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: tuple = ()):
        super().__init__()
        self.secrets = secrets

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage(), self.secrets)
        record.args = ()
        return True
