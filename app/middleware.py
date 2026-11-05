"""Request IDs: one per request, sent back to the client and written in the logs."""

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

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
