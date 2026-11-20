from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTS = {"localhost", "ip6-localhost", "metadata.google.internal"}


class BlockedURL(Exception):
    pass


class DNSFailure(Exception):
    pass


def _ip_blocked(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast
            or a.is_reserved or a.is_unspecified)


def validate_url(url: str, resolver=socket.getaddrinfo) -> None:
    """Raise BlockedURL / DNSFailure. HTTP(S) only, ports 80/443, public IPs only."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise BlockedURL(f"bad scheme: {p.scheme!r}")
    host = (p.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS:
        raise BlockedURL(f"blocked host: {host!r}")
    if p.port not in (None, 80, 443):
        raise BlockedURL(f"bad port: {p.port}")
    try:
        ipaddress.ip_address(host)
        ips = [host]
    except ValueError:
        try:
            ips = sorted({ai[4][0] for ai in resolver(host, None)})
        except socket.gaierror as e:
            raise DNSFailure(str(e)) from e
    for ip in ips:
        if _ip_blocked(ip):
            raise BlockedURL(f"private/reserved address: {ip}")
