import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger("access")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Emits one structured JSON access-log line per request, carrying the
    request id, route, method, response status, and execution time."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        request_id = getattr(request.state, "request_id", None)

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        route = request.scope.get("route")
        endpoint = route.path if route is not None else request.url.path

        logger.info(
            "http_request_completed",
            extra={
                "request_id": request_id,
                "endpoint": endpoint,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else None,
            },
        )
        return response
