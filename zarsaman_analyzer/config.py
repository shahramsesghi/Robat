from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

DEFAULT_ENDPOINT = "https://zarsaman.ir/api/state.json.php"


@dataclass
class Config:
    workspace: Path = field(default_factory=lambda: Path.cwd() / "zarsaman_workspace")
    toman_range: Tuple[float, float] = (15_000_000.0, 35_000_000.0)   # configurable sanity range
    stability_tolerance: float = 0.005        # 0.5% repeat-visit tolerance
    repeat_delay_sec: float = 2.0
    live_match_tolerance: float = 0.03
    fresh_minutes: float = 15.0
    http_timeout: float = 12.0
    max_bytes: int = 2_000_000
    max_redirects: int = 4
    workers: int = 6
    per_domain_limit: int = 2
    verify_tls: bool = True
    state_endpoint: str = field(default_factory=lambda: os.environ.get("ZAR_STATE_ENDPOINT", DEFAULT_ENDPOINT))
    state_key: str = field(default_factory=lambda: os.environ.get("ZAR_STATE_API_KEY", ""))
    browser_tabs: int = 4
    browser_wait_ms: int = 12000

    @property
    def input_dir(self) -> Path: return self.workspace / "input"
    @property
    def output_dir(self) -> Path: return self.workspace / "output" / "source_analysis"
    @property
    def checkpoint_dir(self) -> Path: return self.workspace / "output" / "checkpoints"
    @property
    def logs_dir(self) -> Path: return self.workspace / "logs"
    @property
    def state_dir(self) -> Path: return self.workspace / "state"

    def ensure_dirs(self) -> None:
        for p in (self.input_dir, self.output_dir, self.checkpoint_dir, self.logs_dir, self.state_dir):
            p.mkdir(parents=True, exist_ok=True)

    def in_range(self, v: float) -> bool:
        return self.toman_range[0] <= v <= self.toman_range[1]
