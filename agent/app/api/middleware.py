"""Middleware helpers for the agent API."""

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request id to each request/response for tracing."""

    header_name = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(self.header_name) or request.headers.get("x-request-id")
        if not request_id:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[self.header_name] = request_id
        return response


import time
from collections import defaultdict, deque

from starlette.responses import JSONResponse


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str = ""):
        super().__init__(app)
        self.api_key = api_key or ""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self.api_key:
            # allow health/docs without key
            if request.url.path not in {"/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"} and not request.url.path.startswith("/docs"):
                provided = request.headers.get("X-API-Key") or request.query_params.get("api_key")
                if provided != self.api_key:
                    return JSONResponse(status_code=401, content={"detail": "invalid or missing API key"})
        return await call_next(request)


class PerIPRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 60, window: int = 60):
        super().__init__(app)
        self.limit = int(limit)
        self.window = int(window)
        self._hits: dict = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # key by client IP
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        dq = self._hits[ip]
        while dq and now - dq[0] > self.window:
            dq.popleft()
        if len(dq) >= self.limit:
            return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})
        dq.append(now)
        return await call_next(request)


class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from app.utils.logger import get_logger

        logger = get_logger("http")
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:
            status = 500
            logger.exception("request failed: %s %s", request.method, request.url.path)
            raise
        duration = (time.perf_counter() - start) * 1000.0
        logger.info("%s %s -> %s (%.2fms)", request.method, request.url.path, status, duration)
        return response


# aliases
ApiKeyMiddleware = APIKeyMiddleware
RateLimitMiddleware = PerIPRateLimitMiddleware
LoggingMiddleware = RequestResponseLoggingMiddleware
RequestLoggingMiddleware = RequestResponseLoggingMiddleware