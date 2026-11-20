"""Optional Playwright stage. Read-only: loads pages, captures JSON network responses. Never clicks or submits."""
from __future__ import annotations
import json
import time
from typing import Callable, List, Tuple

from .analyzer import _json, finalize, stable
from .config import Config
from .inventory import Company
from .models import CompanyResult, FailureClass, Mode, Resolution, Status
from .roles import resolve, walk_json
from .security import check_url

Capture = List[Tuple[str, str]]   # (response_url, body_text)


class BrowserUnavailable(RuntimeError):
    pass


def playwright_capture_factory(cfg: Config) -> Callable[[str], Capture]:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as e:
        raise BrowserUnavailable("playwright not installed (pip install playwright && python -m playwright install chromium)") from e

    def capture(url: str) -> Capture:
        from playwright.sync_api import sync_playwright
        ok, why = check_url(url)
        if not ok:
            raise RuntimeError(f"url_blocked:{why}")
        out: Capture = []
        with sync_playwright() as p:
            br = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                ctx = br.new_context(locale="fa-IR", ignore_https_errors=not cfg.verify_tls)
                page = ctx.new_page()

                def on_resp(r):
                    try:
                        ct = (r.headers.get("content-type") or "").lower()
                        if "json" in ct and check_url(r.url, resolve=False)[0]:
                            body = r.text()
                            if body and len(body) < cfg.max_bytes:
                                out.append((r.url, body))
                    except Exception:
                        pass
                page.on("response", on_resp)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                page.wait_for_timeout(min(cfg.browser_wait_ms, 12000))
            finally:
                br.close()
        return out
    return capture


def _best(capture: Capture, cfg: Config):
    for url, text in capture:
        d = _json(text)
        if d is None:
            continue
        r = resolve(walk_json(d, url, cfg))
        if r.mode != Mode.NONE:
            return url, r
    return None, Resolution()


def analyze_browser(company: Company, cfg: Config, capture_fn: Callable[[str], Capture],
                    sleep: Callable[[float], None] = time.sleep) -> CompanyResult:
    res = CompanyResult(company.company_id, company.name)
    pages = [u.url for u in company.urls if not u.aggregator and u.kind == "website"] or \
            [u.url for u in company.urls if not u.aggregator]
    if not pages:
        res.status = Status.SKIPPED
        res.reasons.append("no_primary_url")
        return res
    for page_url in pages[:2]:
        try:
            cap1 = capture_fn(page_url)
        except Exception as e:
            res.failure_class = FailureClass.NETWORK.value
            res.reasons.append(f"browser_error:{type(e).__name__}:{str(e)[:120]}")
            continue
        api_url, r1 = _best(cap1, cfg)
        if r1.mode == Mode.NONE:
            res.reasons.append(f"browser_no_candidate:{page_url}")
            continue
        sleep(cfg.repeat_delay_sec)
        try:
            cap2 = capture_fn(page_url)
        except Exception:
            cap2 = []
        r2 = Resolution()
        for u, t in cap2:
            if u == api_url and _json(t) is not None:
                r2 = resolve(walk_json(_json(t), u, cfg))
                break
        res.status = Status.FAIL
        res.reasons = []
        return finalize(res, r1, r2, cfg, f"browser|{page_url}", api_url or page_url)
    if res.status == Status.FAIL and not res.failure_class:
        res.failure_class = FailureClass.NO_CANDIDATE.value
    return res
