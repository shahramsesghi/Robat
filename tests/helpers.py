import json
from zarsaman_analyzer.http import FetchResult


class FakeFetcher:
    """Maps url -> list of responses (consumed in order; last repeats)."""
    def __init__(self, routes):
        self.routes = {k: (list(v) if isinstance(v, list) else [v]) for k, v in routes.items()}
        self.calls = []

    def fetch(self, url, method="GET", headers=None, body=None):
        self.calls.append((url, dict(headers or {})))
        r = self.routes.get(url)
        if r is None:
            return FetchResult(url=url, error="Failed to resolve host", failure_class="dns")
        item = r.pop(0) if len(r) > 1 else r[0]
        if isinstance(item, FetchResult):
            return item
        text = item if isinstance(item, str) else json.dumps(item)
        return FetchResult(url=url, ok=True, status=200, text=text, final_url=url)


def ok(text, status=200):
    return FetchResult(url="", ok=status == 200, status=status, text=text if isinstance(text, str) else json.dumps(text),
                       error="" if status == 200 else f"HTTP {status}")
