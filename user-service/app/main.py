from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.v1.endpoints import health as health_endpoints
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import configure_logging, get_logger
from app.core.metrics import render_metrics
from app.db.session import engine
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.metrics_middleware import PrometheusMiddleware
from app.middleware.request_id import RequestIDMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("user_service_starting", extra={"env": settings.APP_ENV})
    yield
    await engine.dispose()
    logger.info("user_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Order matters: outermost middleware added last runs first. We want
    # request-id assigned before logging/metrics observe the request.
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": f"https://errors.finflow.com/{exc.error_type}",
                "title": exc.error_type.replace("_", " ").title(),
                "status": exc.status_code,
                "detail": exc.detail,
                "trace_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("unhandled_exception", extra={"request_id": request_id})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "https://errors.finflow.com/internal_error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred",
                "trace_id": request_id,
            },
        )

    # Health checks are mounted at the root path (not versioned) so
    # orchestrators (Kubernetes, ECS, ALB) can probe a stable path.
    app.include_router(health_endpoints.router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        body, content_type = render_metrics()
        return Response(content=body, media_type=content_type)

    return app


app = create_app()
