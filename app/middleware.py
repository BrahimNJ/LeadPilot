"""Request IDs: one per request, sent back to the client and written in the logs."""

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.ratelimit import RateLimiter

REQUEST_ID_HEADER = "X-Request-ID"
# Accept the caller's ID (a load balancer or another service) only if it is harmless.
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

logger = logging.getLogger("leadpilot.requests")


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
    request.state.request_id = request_id

    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000

    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "%s %s -> %d in %.1f ms [%s]",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


# The interactive docs load their script and styles from a CDN, so they can't take this CSP.
_DOCS_PATHS = ("/docs", "/redoc")
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.update(_SECURITY_HEADERS)
    if not request.url.path.startswith(_DOCS_PATHS):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


Middleware = Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]


def body_limit_middleware(max_bytes: int) -> Middleware:
    """Refuse a body that is too large before anything reads it."""

    async def limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # A chunked body doesn't announce its size, so it couldn't be checked up front.
        if "chunked" in request.headers.get("Transfer-Encoding", "").lower():
            return JSONResponse({"detail": "a Content-Length is required"}, status_code=411)
        length = request.headers.get("Content-Length", "0")
        if length.isdecimal() and int(length) > max_bytes:
            return JSONResponse({"detail": "request body too large"}, status_code=413)
        return await call_next(request)

    return limit


def _client_key(request: Request, trust_forwarded_for: bool) -> str:
    if trust_forwarded_for:
        forwarded = request.headers.get("X-Forwarded-For", "")
        # Only the last entry comes from the proxy: earlier ones are whatever the caller sent.
        if last := forwarded.rsplit(",", 1)[-1].strip():
            return last
    return request.client.host if request.client else "unknown"


def rate_limit_middleware(limit: int, trust_forwarded_for: bool) -> Middleware:
    limiter = RateLimiter(limit)

    async def rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Uptime checks must not be throttled, and /health does nothing costly.
        if request.url.path != "/health":
            client = _client_key(request, trust_forwarded_for)
            logger.debug("rate limit key: %s", client)
            if wait := limiter.check(client, time.time()):
                return JSONResponse(
                    {"detail": "too many requests, slow down"},
                    status_code=429,
                    headers={"Retry-After": str(wait)},
                )
        return await call_next(request)

    return rate_limit
