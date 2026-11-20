from __future__ import annotations
import json
import re
from typing import Any, Iterator, Optional
from .models import Candidate

_BUY = {"buy", "buyprice", "todaybuyprice", "platformbuy", "purchase", "purchaseprice", "bid"}
_SELL = {"sell", "sellprice", "todaysellprice", "platformsell", "sale", "saleprice", "ask"}
_BASE = {"price", "base", "baseprice", "current", "last", "lastprice", "rate", "spot", "pricepergram"}
_PATH_BLACK = re.compile(r"(history|chart|candle|volume|percent|change|fee|wage|count|timestamp|"
                         r"max_?24|min_?24|prev|weekly|monthly|silver|xag|g24|24k|999|coin|usd|eur)", re.I)


def normalize_key(key: str) -> str:
    """camelCase / snake_case / kebab -> lower alnum. buyPrice == buy_price == buyprice."""
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def role_of_key(key: str) -> Optional[str]:
    k = normalize_key(key)
    if k in _BUY: return "buy"
    if k in _SELL: return "sell"
    if k in _BASE: return "base"
    return None


def parse_number(v: Any) -> Optional[float]:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        s = s.replace(",", "").replace("٬", "").strip()
        if re.fullmatch(r"\d+(\.\d+)?", s):
            return float(s)
    return None


def _split(path: str) -> list[tuple[str, Optional[tuple[str, str]]]]:
    segs = []
    for seg in path.split("."):
        m = re.fullmatch(r"([^\[\]]+)(?:\[([^=\]]+)=([^\]]+)\])?", seg)
        if not m:
            raise ValueError(f"bad path segment: {seg}")
        segs.append((m.group(1), (m.group(2), m.group(3)) if m.group(2) else None))
    return segs


def get_path(obj: Any, path: str) -> list[tuple[str, Any]]:
    """Mini selector: a.b, a.0.b, a[name=Gold750].buyPrice. Returns [(concrete_path, value)]."""
    cur = [("", obj)]
    for key, flt in _split(path):
        nxt = []
        for p, o in cur:
            if isinstance(o, dict) and key in o:
                child = o[key]
            elif isinstance(o, list) and key.isdigit() and int(key) < len(o):
                child = o[int(key)]
            else:
                continue
            base = f"{p}.{key}" if p else key
            if flt:
                if isinstance(child, list):
                    for i, item in enumerate(child):
                        if isinstance(item, dict) and str(item.get(flt[0])) == flt[1]:
                            nxt.append((f"{base}.{i}", item))
                elif isinstance(child, dict) and str(child.get(flt[0])) == flt[1]:
                    nxt.append((base, child))
            else:
                nxt.append((base, child))
        cur = nxt
    return cur


def walk_numeric(obj: Any, path: str = "", depth: int = 0) -> Iterator[tuple[str, str, float]]:
    if depth > 14:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if isinstance(v, (dict, list)):
                yield from walk_numeric(v, p, depth + 1)
            else:
                n = parse_number(v)
                if n is not None:
                    yield p, str(k), n
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:200]):
            yield from walk_numeric(v, f"{path}.{i}", depth + 1)


def generic_candidates(body: str, url: str) -> list[Candidate]:
    """Discovery listing for sources WITHOUT a verified recipe. Unit is unknown on purpose."""
    try:
        data = json.loads(body)
    except Exception:
        return []
    out, seen = [], set()
    for p, k, n in walk_numeric(data):
        role = role_of_key(k)
        if role is None or _PATH_BLACK.search(p) or n <= 0:
            continue
        if (p, n) in seen:
            continue
        seen.add((p, n))
        out.append(Candidate(path=p, role=role, raw=n, unit=None, source_url=url, label=k,
                             role_evidence=f"key '{k}' suggests {role} (unverified)"))
    return out


def recipe_candidates(body: str, url: str, selectors: list[dict]) -> list[Candidate]:
    """Extract exactly what a recipe says. Unit and role come from the recipe."""
    data = json.loads(body)
    out = []
    for sel in selectors:
        for p, v in get_path(data, sel["path"]):
            n = parse_number(v)
            if n is None:
                continue
            out.append(Candidate(path=p, role=sel["role"], raw=n, unit=sel.get("unit"), source_url=url,
                                 label=sel["path"], product_evidence=sel.get("product", ""),
                                 role_evidence=sel.get("note", "recipe mapping")))
    return out
