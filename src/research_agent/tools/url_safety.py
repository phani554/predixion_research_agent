"""URL safety and SSRF validation for external network requests."""
from __future__ import annotations

import ipaddress
import socket
import urllib.parse

from research_agent.tools.base import BlockedError, PermanentToolError


def check_url(url: str) -> None:
    """Validate that a URL is safe to fetch and does not target internal or private network resources.

    Raises BlockedError if the URL uses an unsupported scheme or targets a private, loopback,
    or link-local address. Raises PermanentToolError if the host cannot be resolved.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as exc:
        raise BlockedError(f"Malformed URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise BlockedError(f"Blocked unsupported URL scheme '{scheme}'. Only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise BlockedError("Blocked URL with missing hostname.")

    if hostname.lower() == "localhost":
        raise BlockedError("Blocked access to localhost.")

    # Check if host is an explicit IP address
    try:
        ip = ipaddress.ip_address(hostname)
        _verify_ip(ip)
        return
    except ValueError:
        pass  # Not an IP literal, resolve via DNS

    # Resolve hostname to IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise PermanentToolError(f"Failed to resolve host '{hostname}': {exc}") from exc

    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
            _verify_ip(ip)
        except ValueError:
            continue


def _verify_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Check that an IP address is publicly routable and not in restricted ranges."""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise BlockedError(f"Blocked access to non-public/private IP address: {ip}")

