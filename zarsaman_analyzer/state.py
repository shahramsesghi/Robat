"""Zarsaman state: LIVE_STATE (HTTP 200 + ok=true) | LOCAL_CACHE | NO_REFERENCE."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Config
from .models import StateMode
from .security import redact


@dataclass
class StateSnapshot:
    mode: StateMode = StateMode.NO_REFERENCE
    http_status: int = 0
    detail: str = ""
    records: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    fetched_at: str = ""

    def record(self, cid: int) -> Optional[Dict[str, Any]]:
        return self.records.get(cid)


def parse_ts(v: Any) -> Optional[datetime]:
    if not v:
        return None
    s = str(v).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def age_minutes(ts: Any, now: Optional[datetime] = None) -> Optional[float]:
    t = parse_ts(ts)
    if t is None:
        return None
    return ((now or datetime.now()) - t).total_seconds() / 60.0


def diagnose(status: int, body: str, key_sent: bool) -> str:
    b = (body or "")[:300]
    if status == 200:
        return "endpoint reachable"
    if status == 403 and b.lstrip().startswith("{") and "forbidden" in b.lower():
        return ("HTTP 403 JSON 'forbidden': PHP code was reached and REJECTED the key. Likely causes: key value differs "
                "from the server key, server reads a different header/param than X-API-Key, or the key was empty."
                + ("" if key_sent else " (No key was sent.)"))
    if status in (401, 403) and "<html" in b.lower():
        return ("HTTP %d with HTML: rejected before PHP (web-server auth / Directory Privacy / WAF). "
                "Exempt this file from that rule instead of weakening the API key." % status)
    if status == 0:
        return "no HTTP response (network/DNS/TLS)"
    return f"unexpected HTTP {status}"


class StateClient:
    def __init__(self, cfg: Config, fetcher=None, offline: bool = False):
        self.cfg = cfg
        self.fetcher = fetcher
        self.offline = offline

    def local_path(self) -> Path:
        return self.cfg.state_dir / "price_state.json"

    def load_local(self) -> Dict[int, Dict[str, Any]]:
        p = self.local_path()
        if not p.is_file():
            alt = self.cfg.input_dir / "price_state.json"
            p = alt if alt.is_file() else p
        if not p.is_file():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
        out: Dict[int, Dict[str, Any]] = {}
        for k, v in data.items():
            try:
                cid = int(k)
            except ValueError:
                continue
            out[cid] = {"name": v.get("name", ""), "last_buy": v.get("last_buy"), "last_sell": v.get("last_sell"),
                        "last_updated_at": v.get("last_success_at"), "last_error": v.get("last_error", ""),
                        "consecutive_failures": v.get("consecutive_failures", 0)}
        return out

    def fetch(self) -> StateSnapshot:
        snap = StateSnapshot(fetched_at=datetime.now().isoformat(timespec="seconds"))
        if not self.offline and self.fetcher is not None:
            headers = {"Accept": "application/json"}
            if self.cfg.state_key:
                headers["X-API-Key"] = self.cfg.state_key      # header only, never in the URL
            r = self.fetcher.fetch(self.cfg.state_endpoint, headers=headers)
            snap.http_status = r.status
            if r.status == 200:
                try:
                    j = json.loads(r.text)
                except Exception:
                    j = None
                if isinstance(j, dict) and j.get("ok") is True:
                    for row in j.get("companies") or []:
                        try:
                            cid = int(row.get("id"))
                        except (TypeError, ValueError):
                            continue
                        snap.records[cid] = {"name": row.get("name", ""), "last_buy": row.get("last_buy"),
                                             "last_sell": row.get("last_sell"),
                                             "last_updated_at": row.get("last_updated_at"),
                                             "last_error": "", "consecutive_failures": row.get("consecutive_failures", 0)}
                    snap.mode = StateMode.LIVE_STATE
                    snap.detail = f"live state: {len(snap.records)} companies"
                    return snap
                snap.detail = "HTTP 200 but invalid JSON or ok!=true"
            else:
                snap.detail = diagnose(r.status, r.text, bool(self.cfg.state_key)) + (f" [{r.error}]" if r.error else "")
        elif self.offline:
            snap.detail = "offline mode"
        local = self.load_local()
        if local:
            snap.mode = StateMode.LOCAL_CACHE
            snap.records = local
            snap.detail = (snap.detail + " | " if snap.detail else "") + f"using LOCAL CACHE ({len(local)} records) - NOT live"
        else:
            snap.mode = StateMode.NO_REFERENCE
            snap.detail = (snap.detail + " | " if snap.detail else "") + "no reference data"
        snap.detail = redact(snap.detail, [self.cfg.state_key])
        return snap
