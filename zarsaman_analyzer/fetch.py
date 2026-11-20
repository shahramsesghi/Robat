from __future__ import annotations
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin
from .config import Config
from .models import FailureKind
from .secrets_redact import redact
from .urlsafety import BlockedURL, DNSFailure, validate_url

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")


@dataclass
class FetchResult:
    ok: bool
    url: str
    final_url: str = ""
    status: int = 0
    body: str = ""
    kind: FailureKind = FailureKind.NONE
    error: str = ""
    elapsed_s: float = 0.0
    content_type: str = ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # we follow manually so every hop is validated
        return None


def fetch(url: str, cfg: Config, headers: dict | None = None, retries: int = 1) -> FetchResult:
    t0 = time.time()
    hdrs = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.8, */*;q=0.5",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8"}
    hdrs.update(headers or {})
    cur, last = url, FetchResult(False, url)
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    for attempt in range(retries + 1):
        cur = url
        try:
            for _ in range(cfg.max_redirects + 1):
                validate_url(cur)
                req = urllib.request.Request(cur, headers=hdrs)
                try:
                    resp = opener.open(req, timeout=cfg.http_timeout_s)
                except urllib.error.HTTPError as e:
                    if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                        cur = urljoin(cur, e.headers["Location"])
                        continue
                    try:
                        ebody = e.read(4000).decode("utf-8", errors="replace")
                    except Exception:
                        ebody = ""
                    last = FetchResult(False, url, cur, e.code, body=ebody, kind=FailureKind.HTTP_ERROR,
                                       error=f"HTTP {e.code}", elapsed_s=time.time() - t0,
                                       content_type=e.headers.get("Content-Type", "") if e.headers else "")
                    break
                raw = resp.read(cfg.max_bytes + 1)
                if len(raw) > cfg.max_bytes:
                    last = FetchResult(False, url, cur, resp.status, kind=FailureKind.PARSE,
                                       error="response too large", elapsed_s=time.time() - t0)
                    break
                body = raw.decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
                return FetchResult(True, url, cur, resp.status, body, elapsed_s=time.time() - t0,
                                   content_type=resp.headers.get("Content-Type", ""))
            else:
                last = FetchResult(False, url, cur, kind=FailureKind.HTTP_ERROR, error="too many redirects",
                                   elapsed_s=time.time() - t0)
        except BlockedURL as e:
            return FetchResult(False, url, cur, kind=FailureKind.BLOCKED_URL, error=str(e), elapsed_s=time.time() - t0)
        except DNSFailure as e:
            last = FetchResult(False, url, cur, kind=FailureKind.NETWORK_DNS, error=f"DNS: {e}", elapsed_s=time.time() - t0)
        except urllib.error.URLError as e:
            reason = e.reason
            kind = FailureKind.NETWORK_DNS if isinstance(reason, socket.gaierror) else FailureKind.NETWORK_OTHER
            last = FetchResult(False, url, cur, kind=kind, error=redact(str(reason)), elapsed_s=time.time() - t0)
        except (socket.timeout, TimeoutError, ssl.SSLError, ConnectionError, OSError) as e:
            last = FetchResult(False, url, cur, kind=FailureKind.NETWORK_OTHER, error=redact(str(e)), elapsed_s=time.time() - t0)
        if last.kind in (FailureKind.NETWORK_DNS,) or (last.status in (400, 401, 403, 404, 410)):
            break
        if attempt < retries:
            time.sleep(1.5 ** attempt)
    return last
