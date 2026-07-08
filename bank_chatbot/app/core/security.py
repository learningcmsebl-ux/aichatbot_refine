"""FastAPI security dependencies for employee authentication."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.models.auth import EmployeeUser
from app.services.auth_service import get_auth_service

_bearer = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[EmployeeUser]:
    """Return the authenticated user, or None when auth is disabled."""
    if not settings.AUTH_ENABLED:
        return None
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return get_auth_service().decode_token(credentials.credentials)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> EmployeeUser:
    """Require a valid employee JWT when AUTH_ENABLED is true."""
    if not settings.AUTH_ENABLED:
        return EmployeeUser(username="anonymous", full_name="Anonymous")

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return get_auth_service().decode_token(credentials.credentials)


async def require_analytics_access(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    """
    Protect analytics endpoints: valid JWT, matching X-Analytics-Key, or open when auth disabled.
    """
    if settings.ANALYTICS_API_KEY:
        provided = request.headers.get("X-Analytics-Key", "")
        if provided and provided == settings.ANALYTICS_API_KEY:
            return

    if not settings.AUTH_ENABLED:
        return

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Analytics access requires authentication or X-Analytics-Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    get_auth_service().decode_token(credentials.credentials)
