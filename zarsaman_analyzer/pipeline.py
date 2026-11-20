from __future__ import annotations
import json
import time
from typing import Callable, Optional
from .config import Config
from .extract import generic_candidates, recipe_candidates
from .fetch import FetchResult, fetch
from .inventory import Company
from .models import CompanyResult, FailureKind, Resolution, Status
from .roles import resolve
from .secrets_redact import redact
from .state import CompanyState, StateSnapshot


def stable(a: Resolution, b: Resolution, tol: float) -> bool:
    if a.status != b.status or a.buy is None or b.buy is None:
        return False
    for x, y in ((a.buy, b.buy), (a.sell, b.sell)):
        if x is None or y is None or x <= 0 or abs(x - y) / x > tol:
            return False
    return True


def _evidence(cands) -> list:
    return [{"path": c.path, "role": c.role, "raw": c.raw, "unit": c.unit, "url": redact(c.source_url),
             "role_evidence": c.role_evidence, "product_evidence": c.product_evidence} for c in cands]


def analyze_company(co: Company, recipe: Optional[dict], snapshot: StateSnapshot, cfg: Config,
                    fetcher: Callable[..., FetchResult] = fetch, sleep=time.sleep) -> CompanyResult:
    t0 = time.time()
    res = CompanyResult(co.company_id, co.name, Status.FAIL, state_mode=snapshot.mode.value)

    if recipe:
        res.api_url, res.recipe_provenance = recipe["url"], recipe.get("provenance", "unknown")
        resolutions, last_cands = [], []
        for i in range(max(2, cfg.repeat_visits)):
            if i:
                sleep(cfg.repeat_delay_s)
            fr = fetcher(recipe["url"], cfg, headers=recipe.get("headers"))
            if not fr.ok:
                res.failure_kind = fr.kind.value
                res.notes.append(f"visit {i+1} failed: {redact(fr.error)} (HTTP {fr.status})")
                res.status = Status.FAIL if i == 0 else Status.NEEDS_REVIEW
                res.elapsed_s = time.time() - t0
                return res
            try:
                cands = recipe_candidates(fr.body, recipe["url"], recipe["selectors"])
            except (ValueError, KeyError) as e:
                res.failure_kind = FailureKind.PARSE.value
                res.notes.append(f"parse error: {e}")
                res.elapsed_s = time.time() - t0
                return res
            last_cands = cands
            resolutions.append(resolve(cands, cfg))
        res.evidence = _evidence(last_cands)
        first = resolutions[0]
        res.buy, res.sell = first.buy, first.sell
        res.notes.append(first.note)
        if first.status in (Status.READY_FOR_PHP, Status.BASE_ONLY_READY):
            if all(stable(first, r, cfg.stability_tolerance) for r in resolutions[1:]):
                res.status = first.status
                res.mode = "pair" if first.status == Status.READY_FOR_PHP else "base_only"
                res.notes.append(f"stable over {len(resolutions)} visits (tol {cfg.stability_tolerance:.2%})")
            else:
                res.status = Status.NEEDS_REVIEW
                res.notes.append("price changed beyond tolerance or status differed between visits")
        else:
            res.status = first.status
        _compare_reference(res, snapshot, cfg)
        res.elapsed_s = time.time() - t0
        return res

    # No recipe: discovery listing only. Unit and product are unverified => never above NEEDS_REVIEW.
    if not co.api_urls:
        res.status = Status.SKIPPED
        res.notes.append("no api_url and no recipe")
        return res
    kinds = []
    for url in co.api_urls[:3]:
        fr = fetcher(url, cfg)
        if not fr.ok:
            kinds.append(fr.kind.value)
            res.notes.append(f"{redact(url)}: {redact(fr.error)}")
            continue
        cands = generic_candidates(fr.body, url)
        if cands:
            res.api_url = url
            res.evidence = _evidence(cands)
            res.status = Status.NEEDS_REVIEW
            res.notes.append("candidates found; unit/product/role unverified - create a recipe after manual check")
            res.elapsed_s = time.time() - t0
            return res
        res.notes.append(f"{redact(url)}: reachable but no price-like JSON fields")
    res.failure_kind = (kinds[0] if kinds and len(set(kinds)) == 1 else
                        FailureKind.NETWORK_OTHER.value if kinds else FailureKind.PARSE.value)
    res.status = Status.FAIL
    res.elapsed_s = time.time() - t0
    return res


def _compare_reference(res: CompanyResult, snap: StateSnapshot, cfg: Config) -> None:
    """Informational only. Never proof of correctness. Cache is never treated as live."""
    if not snap.is_live or res.buy is None:
        return
    st: Optional[CompanyState] = snap.companies.get(res.company_id)
    if not st or st.buy is None:
        return
    age = st.age_minutes()
    if age is None or age > cfg.fresh_minutes:
        res.notes.append("live reference exists but is not fresh; comparison skipped")
        return
    res.reference_diff_pct = round((res.buy - st.buy) / st.buy * 100, 3)
