from __future__ import annotations
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse

TICKER_IDS = set(range(71, 80)) | set(range(90, 102))      # market tickers / currencies
KNOWN_SILVER_IDS = {1018, 1038}
AGGREGATOR_HOSTS = ("goldinex.org", "zarscan.ir", "zarscope.com", "talabaz.org", "iran-market")
NOISE_HOSTS = ("google.com", "gstatic.com", "googletagmanager.com", "recaptcha", "instagram.com", "t.me",
               "telegram.me", "aparat.com", "cloudflare.com", "jsdelivr.net", "cdnjs.com", "sentry.io")


@dataclass
class SourceUrl:
    url: str
    kind: str          # api | website
    aggregator: bool = False
    source_id: int = 0


@dataclass
class Company:
    company_id: int
    name: str
    urls: List[SourceUrl] = field(default_factory=list)
    exclude_reason: str = ""


def is_noise(url: str) -> bool:
    h = (urlparse(url).hostname or "").lower()
    return any(n in h or n in url.lower() for n in NOISE_HOSTS)


def is_aggregator(url: str) -> bool:
    h = (urlparse(url).hostname or "").lower()
    return any(a in h for a in AGGREGATOR_HOSTS)


def exclusion_reason(cid: int, name: str) -> str:
    if cid in TICKER_IDS:
        return "ticker/currency record (not a seller)"
    if cid in KNOWN_SILVER_IDS or "نقره" in name or "silver" in name.lower():
        return "silver record"
    return ""


def load_inventory(path: Path) -> List[Company]:
    comps: Dict[int, Company] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if str(row.get("is_active", "1")).strip() not in ("1", "true", "True"):
                continue
            try:
                cid = int(row["company_id"])
            except (KeyError, ValueError):
                continue
            name = row.get("company_name") or f"company_{cid}"
            c = comps.setdefault(cid, Company(cid, name, exclude_reason=exclusion_reason(cid, name)))
            sid = int(row.get("id") or 0) if str(row.get("id") or "").isdigit() else 0
            for col, kind in (("api_url", "api"), ("website_url", "website")):
                u = (row.get(col) or "").strip()
                if u and u.upper() != "NULL" and u.startswith("http") and not is_noise(u):
                    if all(x.url != u for x in c.urls):
                        c.urls.append(SourceUrl(u, kind, is_aggregator(u), sid))
    return sorted(comps.values(), key=lambda c: c.company_id)
