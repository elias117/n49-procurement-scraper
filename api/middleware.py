"""API middleware for CORS, request logging, and global exception handling."""
from __future__ import annotations

import logging
import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api import config

logger = logging.getLogger("api")


class APICORSMiddleware(CORSMiddleware):
    """CORS policy configured from environment variables."""

    def __init__(self, app):
        super().__init__(
            app=app,
            allow_origins=config.CORS_ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status code, and duration."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)

        message = (
            f"{request.method} {request.url.path} -> "
            f"{response.status_code} ({duration_ms}ms)"
        )

        if response.status_code >= 500:
            logger.error(message)
        elif response.status_code >= 400:
            logger.warning(message)
        else:
            logger.info(message)

        return response


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and return a safe JSON response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled exception while processing request")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "status": 500},
            )
