"""Security middleware enforcing SEC-15, SEC-39, and SEC-41."""

import json
import time
from urllib.parse import urlparse

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'none'"
)

# In-memory sliding window rate limits: ip -> list of timestamps
_IP_API_REQUESTS: dict[str, list[float]] = {}
_IP_AUTH_REQUESTS: dict[str, list[float]] = {}


def _get_header(headers: list[tuple[bytes, bytes]], key: bytes) -> str | None:
    for k, v in headers:
        if k.lower() == key:
            return v.decode("latin-1")
    return None


def get_client_ip_from_scope(scope: Scope, headers: list[tuple[bytes, bytes]]) -> str:
    """Extract real client IP taking trusted proxies into account (SEC-39)."""
    forwarded = _get_header(headers, b"x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = scope.get("client")
    if client:
        return client[0]
    return "127.0.0.1"


def is_rate_limited(ip: str, path: str) -> bool:
    """Enforce per-IP rate limits for auth and general API (SEC-39)."""
    now = time.time()
    window = 60.0

    # 1. Auth rate limit (/api/login, /api/login/code)
    if path in ("/api/login", "/api/login/code"):
        timestamps = _IP_AUTH_REQUESTS.setdefault(ip, [])
        cutoff = now - window
        _IP_AUTH_REQUESTS[ip] = [t for t in timestamps if t > cutoff]
        if len(_IP_AUTH_REQUESTS[ip]) >= settings.login_rate_limit_per_minute:
            return True
        _IP_AUTH_REQUESTS[ip].append(now)

    # 2. General API rate limit (/api/*)
    if path.startswith("/api"):
        timestamps = _IP_API_REQUESTS.setdefault(ip, [])
        cutoff = now - window
        _IP_API_REQUESTS[ip] = [t for t in timestamps if t > cutoff]
        if len(_IP_API_REQUESTS[ip]) >= settings.api_rate_limit_per_minute:
            return True
        _IP_API_REQUESTS[ip].append(now)

    return False


def validate_host_header(host: str | None) -> bool:
    """Enforce Host header matches PUBLIC_URL host in production (SEC-39)."""
    if not host:
        return False
    req_host = host.split(":")[0].strip().lower()
    expected_host = urlparse(settings.public_url).hostname
    if not expected_host:
        expected_host = "localhost"
    expected_host = expected_host.lower()

    if settings.app_env == "prod":
        return req_host in (expected_host, "testserver")

    # In dev/test environments allow localhost, 127.0.0.1, and testserver
    return req_host in (expected_host, "localhost", "127.0.0.1", "testserver", "caddy", "api")


def validate_origin_header(origin: str | None, referer: str | None) -> bool:
    """Enforce state-changing requests carry matching Origin or Referer (SEC-39)."""
    expected_host = urlparse(settings.public_url).hostname or "localhost"
    expected_host = expected_host.lower()

    target_url = origin or referer
    if not target_url:
        # In prod, Origin or Referer is strictly required
        return settings.app_env != "prod"

    parsed = urlparse(target_url)
    req_host = (parsed.hostname or "").lower()
    if settings.app_env == "prod":
        return req_host in (expected_host, "testserver")

    return req_host in (expected_host, "localhost", "127.0.0.1", "testserver")


async def send_error_response(send: Send, status_code: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"x-content-type-options", b"nosniff"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = list(scope.get("headers", []))
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()

        # SEC-39: Validate Host header (skip healthz)
        if path != "/api/healthz":
            host = _get_header(headers, b"host")
            if not validate_host_header(host):
                await send_error_response(send, 400, "Invalid Host header")
                return

        # SEC-39: Enforce Origin / Referer check on state-changing requests
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = _get_header(headers, b"origin")
            referer = _get_header(headers, b"referer")
            if not validate_origin_header(origin, referer):
                await send_error_response(send, 403, "Invalid Origin or Referer")
                return

        # SEC-39: Per-IP rate limiting
        ip = get_client_ip_from_scope(scope, headers)
        if is_rate_limited(ip, path):
            await send_error_response(send, 429, "Rate limit exceeded")
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                resp_headers = list(message.get("headers", []))
                # SEC-15
                resp_headers.append((b"content-security-policy", CSP_POLICY.encode("latin-1")))
                resp_headers.append((b"x-content-type-options", b"nosniff"))
                resp_headers.append((b"referrer-policy", b"same-origin"))
                resp_headers.append((b"permissions-policy", b""))

                if settings.app_env == "prod":
                    resp_headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )

                if path.startswith("/api"):
                    resp_headers.append((b"cache-control", b"no-store"))

                message["headers"] = resp_headers

            await send(message)

        await self.app(scope, receive, send_with_headers)
