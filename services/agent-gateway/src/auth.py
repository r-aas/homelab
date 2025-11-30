"""JWT authentication middleware for Agent Gateway."""

import json
import logging
from typing import Optional

import httpx
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate JWT tokens with auth-server."""

    def __init__(self, app):
        super().__init__(app)
        self.public_paths = set(settings.public_paths.split(","))
        self.client = httpx.AsyncClient(timeout=10.0)

    async def dispatch(self, request: Request, call_next):
        """Validate token before processing request."""
        path = request.url.path

        # Skip auth for public paths
        if not settings.auth_enabled or self._is_public_path(path):
            return await call_next(request)

        # Get token from Authorization header
        token = self._extract_token(request)
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authentication token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token with auth-server
        user = await self._validate_token(token)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Add user info to request state
        request.state.user = user

        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        # Exact match
        if path in self.public_paths:
            return True
        # Prefix match for paths ending in /
        for public_path in self.public_paths:
            if public_path.endswith("/") and path.startswith(public_path):
                return True
        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract Bearer token from Authorization header."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    async def _validate_token(self, token: str) -> Optional[dict]:
        """Validate token with auth-server."""
        try:
            response = await self.client.get(
                f"{settings.auth_server_url}/validate",
                headers={
                    "Authorization": f"Bearer {token}",
                },
            )
            if response.status_code == 200:
                # Auth server returns user info in response headers or body
                result = response.json() if response.text else {}
                # Also check for user info in headers
                if "X-User-Sub" in response.headers:
                    result["sub"] = response.headers.get("X-User-Sub")
                    result["username"] = response.headers.get("X-User-Username")
                    result["email"] = response.headers.get("X-User-Email")
                return result if result else {"validated": True}
            logger.warning(f"Token validation failed: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Auth server error: {e}")
            # Fail open in dev, fail closed in prod
            return None
