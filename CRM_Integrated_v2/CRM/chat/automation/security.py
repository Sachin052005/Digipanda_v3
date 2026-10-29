"""
Durable Outbound Webhook Security Client.
Protects against SSRF, DNS rebinding, private/cloud metadata network access,
uncontrolled redirects, credential leakage, and response size attacks.
"""

import ipaddress
import logging
import socket
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from requests.adapters import HTTPAdapter
import urllib3
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.util.connection import create_connection

logger = logging.getLogger('chat.automation.security')


class SSRFProtectionError(Exception):
    """Raised when an outbound request attempts to access a forbidden or private address."""
    pass


class ResponseTooLargeError(SSRFProtectionError):
    """Raised when an outbound response exceeds the maximum allowed payload size."""
    pass


# Disallowed IPv4 and IPv6 network blocks
FORBIDDEN_NETWORKS = [
    # IPv4 Private & Special
    ipaddress.ip_network('0.0.0.0/8'),        # "This" network
    ipaddress.ip_network('10.0.0.0/8'),       # RFC 1918 Private
    ipaddress.ip_network('100.64.0.0/10'),    # Shared Address Space / CGNAT (RFC 6598)
    ipaddress.ip_network('127.0.0.0/8'),      # Loopback
    ipaddress.ip_network('169.254.0.0/16'),   # Link-Local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network('172.16.0.0/12'),    # RFC 1918 Private
    ipaddress.ip_network('192.0.0.0/24'),     # IETF Protocol Assignments
    ipaddress.ip_network('192.0.2.0/24'),     # TEST-NET-1
    ipaddress.ip_network('192.168.0.0/16'),   # RFC 1918 Private
    ipaddress.ip_network('198.18.0.0/15'),    # Benchmarking
    ipaddress.ip_network('198.51.100.0/24'),  # TEST-NET-2
    ipaddress.ip_network('203.0.113.0/24'),   # TEST-NET-3
    ipaddress.ip_network('224.0.0.0/4'),      # Multicast
    ipaddress.ip_network('240.0.0.0/4'),      # Reserved
    ipaddress.ip_network('255.255.255.255/32'), # Broadcast

    # IPv6 Special & Private
    ipaddress.ip_network('::/128'),           # Unspecified
    ipaddress.ip_network('::1/128'),         # Loopback
    ipaddress.ip_network('::ffff:0:0/96'),    # IPv4-mapped IPv6
    ipaddress.ip_network('100::/64'),         # Discard-only prefix
    ipaddress.ip_network('2001:db8::/32'),    # Documentation
    ipaddress.ip_network('2002::/16'),        # 6to4
    ipaddress.ip_network('fc00::/7'),         # Unique Local Address (ULA)
    ipaddress.ip_network('fe80::/10'),        # Link-Local Unicast
]


def is_ip_allowed(ip_str: str) -> bool:
    """
    Returns True if an IP address is a safe, publicly routable address.
    Returns False for private, loopback, link-local, multicast, or cloud metadata IPs.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        # Check standard properties
        if (ip.is_private or ip.is_loopback or ip.is_reserved or
            ip.is_link_local or ip.is_multicast or ip.is_unspecified):
            return False

        # Check explicit forbidden network list
        for net in FORBIDDEN_NETWORKS:
            if ip in net:
                return False

        return True
    except ValueError:
        return False


def resolve_and_verify_host(hostname: str, port: int) -> List[str]:
    """
    Resolves hostname to IP addresses and verifies that EVERY returned address is safe.
    Returns the list of safe IP addresses.
    Raises SSRFProtectionError if any address is forbidden or if resolution fails.
    """
    # Directly reject literal IPs that are forbidden
    try:
        literal_ip = ipaddress.ip_address(hostname)
        if not is_ip_allowed(str(literal_ip)):
            raise SSRFProtectionError(f"Target address '{hostname}' is a forbidden private or local IP.")
        return [str(literal_ip)]
    except ValueError:
        pass  # It's a hostname, proceed with DNS resolution

    try:
        addrinfo = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SSRFProtectionError(f"DNS resolution failed for '{hostname}': {exc}") from exc

    if not addrinfo:
        raise SSRFProtectionError(f"No DNS records returned for '{hostname}'.")

    safe_ips = []
    for entry in addrinfo:
        sockaddr = entry[4]
        ip_addr = sockaddr[0]
        if not is_ip_allowed(ip_addr):
            raise SSRFProtectionError(
                f"Security alert: Destination host '{hostname}' resolved to forbidden address '{ip_addr}'."
            )
        if ip_addr not in safe_ips:
            safe_ips.append(ip_addr)

    return safe_ips


class SafeHTTPConnection(HTTPConnection):
    """Custom HTTPConnection that validates IPs and connects directly to safe IP."""
    def _new_conn(self) -> socket.socket:
        safe_ips = resolve_and_verify_host(self._dns_host, self.port)
        safe_ip = safe_ips[0]
        try:
            sock = create_connection(
                (safe_ip, self.port),
                self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except OSError as e:
            from urllib3.exceptions import NewConnectionError
            raise NewConnectionError(self, f"Failed to connect to {self.host} ({safe_ip}): {e}") from e
        return sock


class SafeHTTPSConnection(HTTPSConnection):
    """Custom HTTPSConnection that validates IPs, connects to safe IP, and preserves SNI verification."""
    def _new_conn(self) -> socket.socket:
        safe_ips = resolve_and_verify_host(self._dns_host, self.port)
        safe_ip = safe_ips[0]
        try:
            sock = create_connection(
                (safe_ip, self.port),
                self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except OSError as e:
            from urllib3.exceptions import NewConnectionError
            raise NewConnectionError(self, f"Failed to connect to {self.host} ({safe_ip}): {e}") from e
        return sock


class SafeHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = SafeHTTPConnection


class SafeHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = SafeHTTPSConnection


class SafeHTTPAdapter(HTTPAdapter):
    """Requests HTTPAdapter that forces SafeHTTPConnectionPool and SafeHTTPSConnectionPool."""

    def __init__(self, allow_http: bool = False, *args, **kwargs):
        self.allow_http = allow_http
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        self.poolmanager = urllib3.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs
        )
        # Register custom connection pool classes
        self.poolmanager.pool_classes_by_scheme = {
            'https': SafeHTTPSConnectionPool,
        }
        if self.allow_http:
            self.poolmanager.pool_classes_by_scheme['http'] = SafeHTTPConnectionPool


class SafeWebhookClient:
    """
    SSRF-hardened HTTP client for outbound automation webhooks.
    - Default HTTPS-only
    - Connection-time IP verification prevents DNS rebinding
    - Strict connection and read timeouts
    - Safe redirect following with IP re-validation and credential stripping
    - Maximum response payload enforcement (1MB)
    """

    DEFAULT_CONNECT_TIMEOUT = 3.0
    DEFAULT_READ_TIMEOUT = 7.0
    MAX_RESPONSE_BYTES = 1024 * 1024  # 1 MB
    MAX_REDIRECTS = 3

    SENSITIVE_HEADERS = {'authorization', 'x-api-key', 'cookie', 'proxy-authorization'}

    def __init__(self, allow_http: bool = False):
        self.allow_http = allow_http
        self.session = requests.Session()
        adapter = SafeHTTPAdapter(allow_http=allow_http)
        self.session.mount('https://', adapter)
        if allow_http:
            self.session.mount('http://', adapter)

    def validate_url(self, url: str) -> urllib.parse.ParseResult:
        """Validates that URL scheme is valid and hostname is present."""
        parsed = urllib.parse.urlparse(url)
        allowed_schemes = ('https', 'http') if self.allow_http else ('https',)
        if parsed.scheme.lower() not in allowed_schemes:
            raise SSRFProtectionError(
                f"Disallowed URL scheme '{parsed.scheme}'. Only {allowed_schemes} allowed."
            )
        if not parsed.hostname:
            raise SSRFProtectionError(f"Missing hostname in URL '{url}'.")

        # Preliminary check
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        resolve_and_verify_host(parsed.hostname, port)
        return parsed

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Any] = None,
        data: Optional[Any] = None,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
        max_redirects: int = MAX_REDIRECTS,
    ) -> Dict[str, Any]:
        """
        Executes a hardened outbound request.
        Handles redirects manually to re-verify destination IPs and prevent header leakage.
        Returns a dict: {'status_code': int, 'headers': dict, 'text': str, 'json': any, 'url': str}
        """
        current_url = url
        current_headers = dict(headers or {})
        current_method = method.upper()
        current_json = json_data
        current_data = data

        redirect_count = 0

        while True:
            parsed = self.validate_url(current_url)
            timeout = (connect_timeout, read_timeout)

            try:
                resp = self.session.request(
                    method=current_method,
                    url=current_url,
                    headers=current_headers,
                    json=current_json,
                    data=current_data,
                    timeout=timeout,
                    allow_redirects=False,
                    stream=True,
                )
            except requests.exceptions.RequestException as e:
                # Catch SSRF error or connection errors
                raise SSRFProtectionError(f"Outbound request failed: {e}") from e

            # Handle redirects
            if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                redirect_count += 1
                if redirect_count > max_redirects:
                    resp.close()
                    raise SSRFProtectionError(f"Too many redirects (max {max_redirects}).")

                location = resp.headers.get('Location')
                if not location:
                    break

                new_url = urllib.parse.urljoin(current_url, location)
                new_parsed = urllib.parse.urlparse(new_url)

                # Check if host changed; strip credentials if crossing hosts
                if (new_parsed.hostname != parsed.hostname or
                    new_parsed.port != parsed.port or
                    new_parsed.scheme != parsed.scheme):
                    current_headers = {
                        k: v for k, v in current_headers.items()
                        if k.lower() not in self.SENSITIVE_HEADERS
                    }

                # 303 forces GET; 301/302 typically convert POST to GET
                if resp.status_code in (301, 302, 303) and current_method != 'HEAD':
                    current_method = 'GET'
                    current_json = None
                    current_data = None

                current_url = new_url
                resp.close()
                continue

            # Read response with 1MB size limit
            content_chunks = []
            total_bytes = 0
            try:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        total_bytes += len(chunk)
                        if total_bytes > self.MAX_RESPONSE_BYTES:
                            resp.close()
                            raise ResponseTooLargeError(
                                f"Response exceeded {self.MAX_RESPONSE_BYTES} bytes limit."
                            )
                        content_chunks.append(chunk)
            finally:
                resp.close()

            raw_bytes = b"".join(content_chunks)
            encoding = resp.encoding or 'utf-8'
            try:
                text_content = raw_bytes.decode(encoding, errors='replace')
            except Exception:
                text_content = raw_bytes.decode('utf-8', errors='replace')

            parsed_json = None
            try:
                import json
                parsed_json = json.loads(text_content)
            except Exception:
                pass

            return {
                'status_code': resp.status_code,
                'headers': dict(resp.headers),
                'text': text_content,
                'json': parsed_json,
                'url': current_url,
            }
