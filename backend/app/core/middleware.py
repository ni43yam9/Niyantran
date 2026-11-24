import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from backend.app.core.config import settings

logger = logging.getLogger("niyantra.audit")

class RequestAuditingMiddleware(BaseHTTPMiddleware):
    """
    Lightweight request auditing middleware:
    - Tracks execution duration per endpoint
    - Attaches X-Response-Time-Ms header
    - Emits structured warnings for slow queries/requests
    - Captures and logs non-sensitive diagnostic context for 5xx errors
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

            if duration_ms > settings.SLOW_REQUEST_THRESHOLD_MS:
                logger.warning(
                    f"[PERF_SLOW_REQUEST] {method} {path} took {duration_ms:.2f}ms "
                    f"(threshold: {settings.SLOW_REQUEST_THRESHOLD_MS}ms) - status: {response.status_code}"
                )
            elif settings.DEBUG:
                logger.debug(f"{method} {path} -> {response.status_code} ({duration_ms:.2f}ms)")

            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"[REQUEST_EXCEPTION] {method} {path} failed after {duration_ms:.2f}ms: {exc}"
            )
            raise exc
