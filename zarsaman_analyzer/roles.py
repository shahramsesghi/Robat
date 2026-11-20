"""Role candidates and resolution. No synthetic spreads; never sorts to decide buy vs sell."""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

from .config import Config
from .models import Candidate, Mode, Resolution
from .units import GENERIC_UNITS, normalize, parse_number, unit_from_label

BUY_TOK = {"buy", "bid", "purchase", "kharid", "خرید"}
SELL_TOK = {"sell", "ask", "sale", "foroosh", "فروش"}
BASE_TOK = {"price", "base", "current", "last", "rate", "spot", "value"}
EXCLUDE_TOK = {"change", "percent", "pct", "fee", "wage", "max", "min", "high", "low", "history",
               "volume", "old", "prev", "previous", "tomorrow", "avg", "average", "open", "close",
               "id", "count", "timestamp", "time", "date", "ounce", "oz", "usd", "dollar", "silver", "coin"}


def tokens(key: str) -> List[str]:
    k = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(key))
    k = re.sub(r"[^0-9A-Za-z\u0600-\u06FF]+", " ", k).lower()
    return [t for t in k.split() if t]


def classify_key(key: str) -> Optional[str]:
    t = set(tokens(key))
    if not t or t & EXCLUDE_TOK:
        return None
    b, s = bool(t & BUY_TOK), bool(t & SELL_TOK)
    if b and s:
        return None
    if b:
        return "buy"
    if s:
        return "sell"
    if t & BASE_TOK:
        return "base"
    return None


def walk_json(node: Any, url: str, cfg: Config, ctx: str = "", path: str = "", out: Optional[List[Candidate]] = None,
              depth: int = 0, rejected: Optional[List[Dict[str, Any]]] = None) -> List[Candidate]:
    """Collect labelled numeric candidates. Unit comes only from explicit words in the key path."""
    out = [] if out is None else out
    if depth > 14:
        return out
    if isinstance(node, dict):
        for k, v in node.items():
            walk_json(v, url, cfg, ctx + " " + str(k), f"{path}.{k}" if path else str(k), out, depth + 1, rejected)
    elif isinstance(node, list):
        for i, v in enumerate(node[:200]):
            walk_json(v, url, cfg, ctx, f"{path}.{i}", out, depth + 1, rejected)
    else:
        key = path.rsplit(".", 1)[-1]
        role = classify_key(key)
        if role is None:
            return out
        n = parse_number(node)
        if n is None or n <= 0:
            return out
        unit = unit_from_label(ctx)
        if unit not in GENERIC_UNITS:
            return out
        val = normalize(n, unit)
        if not cfg.in_range(val):
            if rejected is not None:
                rejected.append({"locator": path, "role": role, "raw": node})
            return out
        out.append(Candidate(
            source_url=url, locator=path, raw=node, role=role, unit=unit,
            factor=1.0 if unit == "unspecified" else (0.1 if unit == "rial" else 1.0), value=val,
            label=key, role_evidence=f"key_label:{key}",
            unit_evidence="explicit_label" if unit != "unspecified" else "range_consistent_only",
            product_evidence="key_mentions_18k" if _P18.search(ctx + " " + path) else ""))
    return out


_P18 = re.compile(r"(geram18|gram18|g18|gold18|18k|750|yekgram18|irg18|18[_\s-]?(?:karat|carat|عیار))", re.I)
_PRICE_NUM = r"([0-9۰-۹٠-٩][0-9۰-۹٠-٩,٬\.]{5,})"


def html_candidates(text: str, url: str, cfg: Config) -> List[Candidate]:
    """Weak evidence: labelled numbers in visible text. Always unit=unspecified."""
    out: List[Candidate] = []
    plain = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", text or "", flags=re.I)
    plain = re.sub(r"<[^>]+>", " ", plain)
    for role, label in (("buy", "خرید"), ("sell", "فروش")):
        for m in re.finditer(label + r"[^0-9۰-۹٠-٩]{0,40}" + _PRICE_NUM, plain):
            n = parse_number(m.group(1))
            if n and cfg.in_range(n):
                out.append(Candidate(url, f"text:{label}@{m.start()}", m.group(1), role, "unspecified", 1.0, n,
                                     label=label, role_evidence="visible_label",
                                     unit_evidence="range_consistent_only"))
    return out


def _parent(path: str) -> str:
    return path.rsplit(".", 1)[0] if "." in path else ""


def dedupe(cands: List[Candidate]) -> List[Candidate]:
    seen = set()
    out = []
    for c in cands:
        k = (c.locator, round(c.value, 2), c.role)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def _flag_evidence(res: Resolution) -> None:
    if any(c.unit == "unspecified" for c in res.chosen):
        res.flags.append("unit_unverified")
    if any(not c.product_evidence for c in res.chosen):
        res.flags.append("product_unverified")


def resolve(cands: List[Candidate]) -> Resolution:
    """Preserve explicit buy/sell pairs; one unique value -> BASE_ONLY; otherwise ambiguous."""
    cands = dedupe(cands)
    res = Resolution()
    if not cands:
        res.reason = "no_candidates"
        return res
    # explicit pairs: buy+sell sharing the same parent object
    by_parent: Dict[str, Dict[str, List[Candidate]]] = {}
    for c in cands:
        if c.role in ("buy", "sell"):
            by_parent.setdefault(_parent(c.locator), {}).setdefault(c.role, []).append(c)
    pairs = [(p, d["buy"], d["sell"]) for p, d in by_parent.items() if "buy" in d and "sell" in d]
    distinct_pairs = {(round(b[0].value, 2), round(s[0].value, 2)) for _, b, s in pairs if len(b) == 1 and len(s) == 1}
    if len(distinct_pairs) == 1 and all(len(b) == 1 and len(s) == 1 for _, b, s in pairs):
        _, b, s = pairs[0]
        buy, sell = b[0].value, s[0].value
        res.chosen = [b[0], s[0]]
        if abs(buy - sell) < 0.5:
            res.mode, res.base, res.buy, res.sell = Mode.BASE_ONLY, buy, buy, buy
            res.reason = "buy_equals_sell_treated_as_base"
        else:
            res.mode, res.buy, res.sell = Mode.PAIR, buy, sell
            res.reason = "explicit_labelled_pair"
            if buy > sell:
                res.flags.append("buy_gt_sell")   # never swapped
        _flag_evidence(res)
        return res
    if len(distinct_pairs) > 1:
        res.reason = f"ambiguous_pairs={len(distinct_pairs)}"
        return res
    if any(len(d.get("buy", [])) + len(d.get("sell", [])) for d in by_parent.values()) and not pairs:
        one_sided = [c for c in cands if c.role in ("buy", "sell")]
        if not [c for c in cands if c.role == "base"]:
            res.reason = "one_sided_quote_only"
            res.flags.append("one_sided")
            res.chosen = one_sided[:2]
            return res
    bases = [c for c in cands if c.role == "base"]
    uniq = {round(c.value, 2) for c in bases}
    if len(uniq) == 1:
        c = bases[0]
        res.mode, res.base, res.buy, res.sell = Mode.BASE_ONLY, c.value, c.value, c.value
        res.chosen = [c]
        res.reason = "single_unique_base"
        _flag_evidence(res)
        return res
    res.reason = f"ambiguous_candidates={len(cands)} distinct_base={len(uniq)}"
    return res
