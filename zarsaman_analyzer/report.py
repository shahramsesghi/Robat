from __future__ import annotations
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from .config import Config
from .models import CompanyResult, Status
from .security import redact


def write_all(run_id: str, results: List[CompanyResult], meta: Dict[str, Any], cfg: Config,
              php_files: List[Path], lint: Dict[str, str]) -> Dict[str, Path]:
    d = cfg.output_dir
    d.mkdir(parents=True, exist_ok=True)
    results = sorted(results, key=lambda r: r.company_id)
    paths: Dict[str, Path] = {}
    sec = [cfg.state_key]

    jp = d / f"analysis_{run_id}.json"
    jp.write_text(redact(json.dumps({"meta": meta, "results": [r.to_dict() for r in results]},
                                    ensure_ascii=False, indent=2), sec), encoding="utf-8")
    paths["json"] = jp

    cp = d / f"analysis_{run_id}.csv"
    with open(cp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["company_id", "name", "status", "mode", "final_buy", "final_sell", "stable", "failure_class",
                    "method", "source_url", "reasons", "warnings"])
        for r in results:
            w.writerow([r.company_id, r.name, r.status.value, r.mode.value, r.final_buy or "", r.final_sell or "",
                        r.stable, r.failure_class, redact(r.method), redact(r.source_url),
                        " | ".join(r.reasons), " | ".join(r.warnings)])
    paths["csv"] = cp

    ep = d / f"analysis_evidence_{run_id}.csv"
    with open(ep, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["company_id", "name", "status", "source_url", "locator", "role", "raw", "unit", "factor", "value_toman",
                    "label", "role_evidence", "unit_evidence", "product_evidence"])
        for r in results:
            for e in r.evidence:
                w.writerow([r.company_id, r.name, r.status.value, redact(e["source_url"]), e["locator"], e["role"], e["raw"],
                            e["unit"], e["factor"], e["value"], e["label"], e["role_evidence"], e["unit_evidence"],
                            e["product_evidence"]])
    paths["evidence"] = ep

    cnt = Counter(r.status.value for r in results)
    fcls = Counter(r.failure_class for r in results if r.failure_class)
    lines = [f"# Zarsaman source analysis - {run_id}", "",
             f"- Started: {meta.get('started_at')}  | Finished: {meta.get('finished_at')}",
             f"- **State mode: {meta.get('state_mode')}** - {meta.get('state_detail')}",
             "- Local cache is never treated as live server state." if meta.get("state_mode") != "LIVE_STATE" else
             "- Live state used only as a similarity cross-check (not proof of product or role correctness).",
             f"- Stage: {meta.get('stage')} | Companies analysed: {len(results)}", "",
             "## Status summary", ""] + [f"- {k}: {v}" for k, v in sorted(cnt.items())]
    lines += ["", "## Failure classes (network vs parsing)", ""] + ([f"- {k}: {v}" for k, v in sorted(fcls.items())] or ["- none"])
    for title, sts in (("Ready for PHP (explicit buy/sell, stable)", [Status.READY_FOR_PHP]),
                       ("Base-only ready (one verified quote; no buy/sell supplied)", [Status.BASE_ONLY_READY])):
        rows = [r for r in results if r.status in sts]
        lines += ["", f"## {title}: {len(rows)}", ""]
        for r in rows:
            lines.append(f"- {r.company_id} {r.name}: buy={r.final_buy:,.0f} sell={r.final_sell:,.0f} | `{redact(r.method)}`")
    groups: Dict[Any, List[CompanyResult]] = {}
    for r in results:
        if r.final_buy and r.status in (Status.READY_FOR_PHP, Status.BASE_ONLY_READY, Status.NEEDS_REVIEW):
            groups.setdefault((r.final_buy, r.final_sell), []).append(r)
    dup = [(k, v) for k, v in groups.items() if len(v) >= 2]
    lines += ["", "## Identical quotes across companies (likely shared upstream)", ""]
    lines += [f"- {k[0]:,.0f} / {k[1]:,.0f}: " + ", ".join(f"{x.company_id} {x.name}" for x in v) for k, v in dup] or ["- none"]
    rows = [r for r in results if r.status == Status.NEEDS_REVIEW]
    lines += ["", f"## Needs review: {len(rows)}", ""]
    for r in rows:
        lines.append(f"- {r.company_id} {r.name}: {'; '.join(r.reasons + r.warnings)[:220]}")
    rows = [r for r in results if r.status == Status.FAIL]
    lines += ["", f"## Failed: {len(rows)}", ""]
    for r in rows:
        lines.append(f"- {r.company_id} {r.name} [{r.failure_class}]: {'; '.join(r.reasons)[:200]}")
    rows = [r for r in results if r.status == Status.SKIPPED]
    lines += ["", f"## Skipped: {len(rows)}", ""]
    for r in rows:
        lines.append(f"- {r.company_id} {r.name}: {'; '.join(r.reasons)}")
    lines += ["", "## PHP recipes", "", f"- Generated {max(0, len(php_files) - 1)} proposal(s) under `recipes/{run_id}/` (NOT deployed)."]
    lines += [f"- {k}: {v}" for k, v in lint.items()]
    mp = d / f"REPORT_{run_id}.md"
    mp.write_text(redact("\n".join(lines), sec), encoding="utf-8")
    paths["report"] = mp

    pr = ["# PHP review prompt", "",
          "Review the proposed recipes in `recipes/" + run_id + "/` against production `run_scrapers.php`.",
          "Rules: preserve explicit buy/sell; never invent a spread; single quote = BASE_ONLY; do not swap buy/sell by sorting.",
          "Do not deploy; do not touch the live DB.", "", "## Verified candidates", ""]
    for r in results:
        if r.status in (Status.READY_FOR_PHP, Status.BASE_ONLY_READY):
            pr.append(f"- {r.company_id} {r.name} [{r.status.value}] {redact(r.source_url)} buy={r.final_buy:,.0f} sell={r.final_sell:,.0f}")
    pr += ["", "## Open items (human decision)", ""]
    for r in results:
        if r.status == Status.NEEDS_REVIEW:
            pr.append(f"- {r.company_id} {r.name}: {'; '.join(r.reasons + r.warnings)[:200]}")
    pp = d / f"PROMPT_FOR_PHP_REVIEW_{run_id}.md"
    pp.write_text(redact("\n".join(pr), sec), encoding="utf-8")
    paths["php_prompt"] = pp
    return paths
