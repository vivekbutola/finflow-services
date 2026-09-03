import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import http_request_duration_seconds, http_requests_total


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Records http_requests_total and http_request_duration_seconds for
    every request, labeled by method, route template, and status code."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_time

        route = request.scope.get("route")
        endpoint = route.path if route is not None else request.url.path

        # Avoid unbounded label cardinality from unmatched/unknown paths
        if route is None and endpoint not in ("/health/live", "/health/ready", "/metrics"):
            endpoint = "unmatched"

        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=str(response.status_code),
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

        return response
