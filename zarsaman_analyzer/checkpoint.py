from __future__ import annotations
import json
import os
import threading
from pathlib import Path
from typing import Dict, Optional

from .models import CompanyResult


class Checkpoint:
    def __init__(self, directory: Path, run_id: str):
        self.dir = directory
        self.run_id = run_id
        self.path = directory / f"checkpoint_{run_id}.json"
        self.latest = directory / "latest.json"
        self.results: Dict[int, CompanyResult] = {}
        self.lock = threading.Lock()

    def record(self, r: CompanyResult) -> None:
        with self.lock:
            self.results[r.company_id] = r
            self._save()

    def _save(self) -> None:
        payload = {"run_id": self.run_id, "results": {str(k): v.to_dict() for k, v in self.results.items()}}
        for target in (self.path, self.latest):
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, target)       # atomic

    @classmethod
    def resume_latest(cls, directory: Path) -> Optional["Checkpoint"]:
        p = directory / "latest.json"
        if not p.is_file():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
        cp = cls(directory, data["run_id"])
        for k, v in data.get("results", {}).items():
            cp.results[int(k)] = CompanyResult.from_dict(v)
        return cp
