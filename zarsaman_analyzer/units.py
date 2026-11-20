"""Unit normalisation. Conversion factors are explicit; magnitude never selects a factor."""
from __future__ import annotations
import re
from typing import Any, Optional

# unit -> factor to Toman per gram. soot_* only via explicit declaration (recipes).
UNIT_FACTORS = {
    "toman": 1.0,
    "rial": 0.1,
    "soot_toman": 1000.0,   # per-soot quote -> per-gram (1 gram = 1000 soot); recipe-declared only
    "soot_rial": 100.0,
}
# Units generic discovery may use (soot_* is never inferred).
GENERIC_UNITS = {"toman", "rial", "unspecified"}


class UnknownUnit(ValueError):
    pass


_FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_number(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).translate(_FA)
    for ch in ("٬", "،", ",", " ", "\u200c", "\u00a0"):
        s = s.replace(ch, "")
    s = s.replace("٫", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    return float(s)


def normalize(value: float, unit: str) -> float:
    """Return Toman/gram. 'unspecified' is passed through unchanged (flagged by callers)."""
    if unit == "unspecified":
        return float(value)
    if unit not in UNIT_FACTORS:
        raise UnknownUnit(f"unknown unit: {unit!r}")
    return float(value) * UNIT_FACTORS[unit]


def factor_of(unit: str) -> float:
    if unit == "unspecified":
        return 1.0
    if unit not in UNIT_FACTORS:
        raise UnknownUnit(f"unknown unit: {unit!r}")
    return UNIT_FACTORS[unit]


_RIAL_HINT = re.compile(r"(rial|irr|rls|ریال)", re.I)
_TOMAN_HINT = re.compile(r"(toman|tmn|irt|تومان)", re.I)


def unit_from_label(text: str) -> str:
    """Only explicit words in a key/label establish a unit; otherwise 'unspecified'."""
    t = text or ""
    r, m = bool(_RIAL_HINT.search(t)), bool(_TOMAN_HINT.search(t))
    if r and not m:
        return "rial"
    if m and not r:
        return "toman"
    return "unspecified"
