from __future__ import annotations
import argparse
import json
import logging
import os
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import __version__
from .analyzer import analyze_company
from .checkpoint import Checkpoint
from .config import Config
from .http import RequestsFetcher
from .inventory import Company, load_inventory
from .models import CompanyResult, Mode, Status
from .security import RedactingFilter, redact
from .state import StateClient, age_minutes

log = logging.getLogger("zarsaman")


def setup_logging(cfg: Config, run_id: str) -> Path:
    cfg.ensure_dirs()
    path = cfg.logs_dir / f"run_{run_id}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    for h in (logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt)
        h.addFilter(RedactingFilter([cfg.state_key]))
        log.addHandler(h)
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="zarsaman_analyzer", description="Zarsaman gold price source discovery & validation bot")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command")
    r = sub.add_parser("run", help="analyse sources and write reports")
    r.add_argument("--stage", choices=["http", "browser", "both"], default="both")
    r.add_argument("--only-failed", action="store_true", help="only companies whose last state shows an error/no success")
    r.add_argument("--only-stale", action="store_true", help="only companies not updated within the fresh window")
    r.add_argument("--skip-fresh-minutes", type=float, default=None, help="skip companies updated within N minutes")
    r.add_argument("--stage2-all", action="store_true", help="run the browser stage for every company, not only unresolved")
    r.add_argument("--company-id", type=int, action="append", default=[])
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--workers", type=int, default=0)
    r.add_argument("--resume", action="store_true")
    r.add_argument("--offline", action="store_true", help="do not call the state endpoint")
    r.add_argument("--no-browser", action="store_true")
    r.add_argument("--insecure", action="store_true", help="disable TLS verification (not recommended)")
    r.add_argument("--workspace", default="")
    r.add_argument("--inventory", default="", help="path to sources CSV (default: <workspace>/input/sources.csv)")
    s = sub.add_parser("status", help="show state mode and company freshness")
    s.add_argument("--offline", action="store_true")
    s.add_argument("--workspace", default="")
    pb = sub.add_parser("probe", help="show what the analyzer sees for one company (for diagnosing failures)")
    pb.add_argument("--company-id", type=int, required=True)
    pb.add_argument("--workspace", default="")
    pb.add_argument("--inventory", default="")
    pb.add_argument("--insecure", action="store_true")
    d = sub.add_parser("doctor", help="check environment, dependencies and the state endpoint")
    d.add_argument("--workspace", default="")
    d.add_argument("--offline", action="store_true")
    return p


def _cfg(args) -> Config:
    cfg = Config()
    if getattr(args, "workspace", ""):
        cfg.workspace = Path(args.workspace)
    if getattr(args, "insecure", False):
        cfg.verify_tls = False
    if getattr(args, "workers", 0):
        cfg.workers = args.workers
    cfg.ensure_dirs()
    return cfg


def select(companies: List[Company], args, snap, cfg: Config) -> List[Company]:
    out = companies
    if args.company_id:
        out = [c for c in out if c.company_id in set(args.company_id)]
    rec = snap.records if snap else {}
    thr = args.skip_fresh_minutes if args.skip_fresh_minutes is not None else cfg.fresh_minutes
    if args.only_failed:
        out = [c for c in out if (not rec.get(c.company_id)) or rec[c.company_id].get("last_error")
               or (rec[c.company_id].get("consecutive_failures") or 0) > 0]
    if args.only_stale or args.skip_fresh_minutes is not None:
        def stale(c: Company) -> bool:
            r = rec.get(c.company_id)
            a = age_minutes(r.get("last_updated_at")) if r else None
            return a is None or a > thr
        out = [c for c in out if stale(c)]
    if args.limit:
        out = out[: args.limit]
    return out


def cmd_run(args) -> int:
    cfg = _cfg(args)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = setup_logging(cfg, run_id)
    log.info("Zarsaman analyzer %s | run %s", __version__, run_id)
    inv_path = Path(args.inventory) if args.inventory else cfg.input_dir / "sources.csv"
    if not inv_path.is_file():
        log.error("Inventory not found: %s (see INPUTS_NEEDED.md)", inv_path)
        return 2
    started = datetime.now().isoformat(timespec="seconds")
    fetcher = RequestsFetcher(cfg)
    snap = StateClient(cfg, fetcher, offline=args.offline).fetch()
    log.info("State mode: %s | %s", snap.mode.value, snap.detail)
    if snap.mode.value != "LIVE_STATE":
        log.warning("Running WITHOUT live Zarsaman state. Reference comparison is disabled.")
    companies = select(load_inventory(inv_path), args, snap, cfg)
    cp = Checkpoint.resume_latest(cfg.checkpoint_dir) if args.resume else None
    if cp is None:
        cp = Checkpoint(cfg.checkpoint_dir, run_id)
    else:
        run_id = cp.run_id
        log.info("Resuming run %s with %d completed companies", run_id, len(cp.results))
    todo = [c for c in companies if c.company_id not in cp.results]
    log.info("Companies selected: %d | to analyse: %d | stage=%s", len(companies), len(todo), args.stage)

    domain_locks: Dict[str, threading.Semaphore] = defaultdict(lambda: threading.Semaphore(cfg.per_domain_limit))

    overrides = load_overrides(cfg)
    if overrides:
        log.info("Human role overrides loaded for companies: %s", sorted(overrides))

    def work(c: Company) -> CompanyResult:
        if args.stage == "browser":
            return CompanyResult(c.company_id, c.name, status=Status.FAIL)   # filled by the browser stage
        return analyze_company(c, cfg, fetcher, snap, overrides=overrides)

    if todo:
        with ThreadPoolExecutor(max_workers=cfg.workers) as ex:
            futs = {ex.submit(work, c): c for c in todo}
            for fut in as_completed(futs):
                r = fut.result()
                cp.record(r)
                log.info("[%s] %s %s %s", r.status.value, r.company_id, r.name,
                         (f"buy={r.final_buy:,.0f} sell={r.final_sell:,.0f}" if r.final_buy else "; ".join(r.reasons)[:160])
                         + ((" | " + "; ".join(w for w in r.warnings if not w.startswith("role_note"))[:140])
                            if r.status != Status.READY_FOR_PHP and r.status != Status.BASE_ONLY_READY and r.warnings else ""))

    if args.stage in ("browser", "both") and not args.no_browser:
        from .browser import BrowserUnavailable, analyze_browser, playwright_capture_factory
        try:
            cap = playwright_capture_factory(cfg)
        except BrowserUnavailable as e:
            log.warning("Browser stage skipped: %s", e)
            cap = None
        if cap:
            cmap = {c.company_id: c for c in companies}
            targets = [cid for cid, r in cp.results.items() if cid in cmap and
                       (args.stage2_all or args.stage == "browser" or r.status in (Status.FAIL, Status.NEEDS_REVIEW)) and
                       r.failure_class not in ("dns", "excluded") and r.status != Status.SKIPPED]
            log.info("Browser stage: %d companies", len(targets))
            for cid in targets:
                br = analyze_browser(cmap[cid], cfg, cap)
                old = cp.results[cid]
                if br.status in (Status.READY_FOR_PHP, Status.BASE_ONLY_READY) or old.status == Status.FAIL:
                    cp.record(br)
                log.info("[browser %s] %s %s", br.status.value, cid, cmap[cid].name)

    from .phpgen import generate, lint
    from .report import write_all
    results = [r for cid, r in cp.results.items() if cid in {c.company_id for c in companies}] or list(cp.results.values())
    php_dir = cfg.output_dir / "recipes" / run_id
    php_files = generate(results, cfg, php_dir)
    lint_out = lint(php_files)
    meta = {"run_id": run_id, "started_at": started, "finished_at": datetime.now().isoformat(timespec="seconds"),
            "state_mode": snap.mode.value, "state_detail": snap.detail, "stage": args.stage, "version": __version__}
    paths = write_all(run_id, results, meta, cfg, php_files, lint_out)
    inv_names = [r for r in results if "buy_gt_sell" in r.warnings]
    if inv_names:
        tp = cfg.output_dir / f"role_overrides_TEMPLATE_{run_id}.json"
        tp.write_text(json.dumps({str(r.company_id): {"labels_inverted": False, "note": f"{r.name}: buy={r.final_buy} > sell={r.final_sell}. Set true ONLY after verifying on the site that the source's 'buy' is the customer's purchase price."} for r in inv_names}, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Role-override template: %s (copy to input/role_overrides.json after verifying)", tp)
    cnt = {s.value: sum(1 for r in results if r.status == s) for s in Status}
    log.info("Summary: %s", cnt)
    for k, v in paths.items():
        log.info("Wrote %s: %s", k, v)
    log.info("Log: %s", log_path)
    return 0


def load_overrides(cfg: Config) -> Dict[int, Dict]:
    p = cfg.input_dir / "role_overrides.json"
    if not p.is_file():
        return {}
    try:
        return {int(k): v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if isinstance(v, dict)}
    except Exception:
        log.warning("role_overrides.json is invalid and was ignored")
        return {}


def cmd_probe(args) -> int:
    from .analyzer import _json
    from .recipes import RECIPES
    from .roles import resolve, walk_json
    cfg = _cfg(args)
    inv = Path(args.inventory) if args.inventory else cfg.input_dir / "sources.csv"
    comp = next((c for c in load_inventory(inv) if c.company_id == args.company_id), None)
    if not comp:
        print("company not in inventory")
        return 2
    f = RequestsFetcher(cfg)
    urls = [(u.url, "AGGREGATOR" if u.aggregator else u.kind) for u in comp.urls]
    rec = RECIPES.get(comp.company_id)
    if rec:
        urls.insert(0, (rec.url, "RECIPE"))
    print(f"== {comp.company_id} {comp.name}")
    for url, kind in urls:
        r = f.fetch(url, headers=rec.headers if rec and kind == "RECIPE" else None)
        print(f"\n-- [{kind}] {redact(url)}\n   HTTP {r.status} ok={r.ok} class={r.failure_class} err={r.error} type={r.content_type} len={len(r.text)}")
        print("   body[:500]:", redact(r.text[:500].replace("\n", " ")))
        d = _json(r.text) if r.ok else None
        if d is not None:
            rej = []
            cands = walk_json(d, url, cfg, rejected=rej)
            for c in cands:
                print(f"   candidate {c.role:5} {c.locator} = {c.raw} unit={c.unit}")
            for x in rej[:10]:
                print(f"   rejected(out of range) {x['role']} {x['locator']} = {x['raw']}")
            print("   resolution:", resolve(cands).reason)
            if rec and kind == "RECIPE":
                print("   recipe extract:", rec.extract(d))
    return 0


def cmd_status(args) -> int:
    cfg = _cfg(args)
    snap = StateClient(cfg, None if args.offline else RequestsFetcher(cfg), offline=args.offline).fetch()
    print(f"State mode : {snap.mode.value}\nDetail     : {redact(snap.detail, [cfg.state_key])}")
    fresh = stale = failed = 0
    for cid, r in sorted(snap.records.items()):
        a = age_minutes(r.get("last_updated_at"))
        if a is None:
            failed += 1
        elif a <= cfg.fresh_minutes:
            fresh += 1
        else:
            stale += 1
    print(f"Records    : {len(snap.records)} | fresh(<{cfg.fresh_minutes:g}m)={fresh} stale={stale} never={failed}")
    if snap.mode.value != "LIVE_STATE":
        print("WARNING: data above is NOT live server state.")
    return 0


def cmd_doctor(args) -> int:
    cfg = _cfg(args)
    ok = True
    print(f"Python        : {sys.version.split()[0]} {'OK' if sys.version_info >= (3, 11) else 'FAIL (3.11+ required)'}")
    ok &= sys.version_info >= (3, 11)
    for mod, need in (("requests", True), ("playwright", False)):
        try:
            __import__(mod)
            print(f"{mod:<14}: OK")
        except ImportError:
            print(f"{mod:<14}: MISSING{'' if need else ' (optional: browser stage disabled)'}")
            ok &= not need
    inv = cfg.input_dir / "sources.csv"
    print(f"Inventory     : {'OK ' + str(inv) if inv.is_file() else 'MISSING ' + str(inv)}")
    print(f"State key     : {'set (hidden)' if cfg.state_key else 'NOT SET -> LOCAL_CACHE/offline mode'}")
    print(f"State endpoint: {cfg.state_endpoint}")
    if not args.offline:
        snap = StateClient(cfg, RequestsFetcher(cfg)).fetch()
        print(f"State result  : HTTP {snap.http_status} -> {snap.mode.value}\n  {redact(snap.detail, [cfg.state_key])}")
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "probe":
        return cmd_probe(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    p.print_help()
    return 0
