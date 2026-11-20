from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class Status(str, Enum):
    READY_FOR_PHP = "READY_FOR_PHP"
    BASE_ONLY_READY = "BASE_ONLY_READY"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class Mode(str, Enum):
    PAIR = "PAIR"
    BASE_ONLY = "BASE_ONLY"
    NONE = "NONE"


class StateMode(str, Enum):
    LIVE_STATE = "LIVE_STATE"
    LOCAL_CACHE = "LOCAL_CACHE"
    NO_REFERENCE = "NO_REFERENCE"


class FailureClass(str, Enum):
    NONE = ""
    DNS = "dns"
    NETWORK = "network"
    TIMEOUT = "timeout"
    TLS = "tls"
    HTTP_ERROR = "http_error"
    BLOCKED = "blocked"
    PARSE = "parse"
    NO_CANDIDATE = "no_candidate"
    AMBIGUOUS = "ambiguous"
    UNSTABLE = "unstable"
    UNSAFE_URL = "unsafe_url"
    EXCLUDED = "excluded"


@dataclass
class Candidate:
    """One numeric observation with full provenance."""
    source_url: str
    locator: str                 # JSON path or DOM/text locator
    raw: Any
    role: str                    # buy | sell | base
    unit: str                    # toman | rial | soot_toman | soot_rial | unspecified
    factor: float
    value: float                 # normalized Toman per gram
    label: str = ""
    role_evidence: str = ""
    unit_evidence: str = ""
    product_evidence: str = ""
    observed_at: str = ""

    def to_row(self) -> Dict[str, Any]:
        d = asdict(self)
        d["raw"] = str(self.raw)[:80]
        return d


@dataclass
class Resolution:
    mode: Mode = Mode.NONE
    buy: Optional[float] = None
    sell: Optional[float] = None
    base: Optional[float] = None
    reason: str = ""
    flags: List[str] = field(default_factory=list)
    chosen: List[Candidate] = field(default_factory=list)


@dataclass
class CompanyResult:
    company_id: int
    name: str
    status: Status = Status.FAIL
    mode: Mode = Mode.NONE
    final_buy: Optional[float] = None
    final_sell: Optional[float] = None
    method: str = ""
    source_url: str = ""
    failure_class: str = ""
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stable: Optional[bool] = None
    second_visit: Optional[Dict[str, Any]] = None
    reference: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    backups: List[str] = field(default_factory=list)
    recipe_id: Optional[int] = None
    elapsed_sec: float = 0.0
    fixture: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["mode"] = self.mode.value
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "CompanyResult":
        d = dict(d)
        d["status"] = Status(d.get("status", "FAIL"))
        d["mode"] = Mode(d.get("mode", "NONE"))
        allowed = CompanyResult.__dataclass_fields__.keys()
        return CompanyResult(**{k: v for k, v in d.items() if k in allowed})
