import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "x-request-id"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generates a request id if the caller didn't supply one, stores it on
    request.state.request_id for downstream use (logging, error responses),
    and always echoes it back in the response headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_id = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming_id if incoming_id else str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
