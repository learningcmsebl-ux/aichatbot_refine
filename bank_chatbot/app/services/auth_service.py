"""Employee authentication service (AD + JWT)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.auth import EmployeeUser, LoginResponse
from app.services.ldap_auth import LdapAuthService, normalize_username
from app.services.ldap_provision import get_ldap_provision

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"


class AuthService:
    def __init__(self) -> None:
        self.ldap_auth = LdapAuthService()

    def login(self, username: str, password: str) -> LoginResponse:
        normalized = normalize_username(username)
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is required",
            )

        ldap_profile = self.ldap_auth.authenticate_and_get_profile(username, password)
        if not ldap_profile:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        resolved_username = ldap_profile.get("username") or normalized
        user = self._resolve_employee_profile(resolved_username, ldap_profile=ldap_profile)
        token, expires_in = self._create_access_token(user)
        must_change = self.must_change_password_for_user(user.username)
        return LoginResponse(
            access_token=token,
            expires_in=expires_in,
            user=user,
            must_change_password=must_change,
        )

    def must_change_password_for_user(self, username: str) -> bool:
        try:
            from app.database.postgres import get_db
            from app.services import portal_user_service as portal_svc

            db = get_db()
            if db:
                try:
                    return portal_svc.resolve_must_change_password(db, username)
                finally:
                    db.close()
        except Exception as exc:
            logger.debug("[AUTH] must_change_password check skipped: %s", exc)
        try:
            return get_ldap_provision().must_change_password(username)
        except Exception:
            return False

    def change_password(self, user: EmployeeUser, current_password: str, new_password: str) -> None:
        get_ldap_provision().change_password(user.username, current_password, new_password)
        try:
            from app.database.postgres import get_db
            from app.services import portal_user_service as portal_svc

            db = get_db()
            if db:
                try:
                    portal_svc.clear_must_change_password(db, user.username)
                finally:
                    db.close()
        except Exception as exc:
            logger.warning("[AUTH] clear must_change_password failed: %s", exc)

    def _resolve_employee_profile(
        self,
        username: str,
        ldap_profile: Optional[Dict[str, Any]] = None,
    ) -> EmployeeUser:
        """Enrich login with AD + phonebook profile when available."""
        profile: Optional[dict] = None
        try:
            from app.core.dependencies import get_container

            phonebook = get_container().phonebook_db
            if phonebook:
                profile = phonebook.search_by_login_username(username)
                if not profile:
                    profile = phonebook.search_by_employee_id(username)
        except Exception as exc:
            logger.debug("[AUTH] Phonebook lookup skipped: %s", exc)

        full_name = None
        email = None
        employee_id = username
        department = None
        designation = None
        ad_object_id = None
        upn = None

        if profile:
            full_name = profile.get("full_name")
            email = profile.get("email")
            employee_id = profile.get("employee_id") or username
            department = profile.get("department")
            designation = profile.get("designation")
            ad_object_id = profile.get("ad_object_id")
            upn = profile.get("upn")

        if ldap_profile:
            full_name = full_name or ldap_profile.get("display_name")
            email = email or ldap_profile.get("email")
            employee_id = ldap_profile.get("employee_id") or employee_id
            department = department or ldap_profile.get("department")
            designation = designation or ldap_profile.get("designation")
            username = ldap_profile.get("username") or username
            # Stable AD identifier (objectGUID) + UPN come straight from the
            # directory bind — never from client input.
            ad_object_id = ldap_profile.get("ad_object_id") or ad_object_id
            upn = ldap_profile.get("upn") or upn

        if not full_name:
            full_name = self.ldap_auth.lookup_display_name(username)

        return EmployeeUser(
            username=username,
            employee_id=employee_id,
            full_name=full_name,
            email=email,
            department=department,
            designation=designation,
            ad_object_id=ad_object_id,
            upn=upn,
        )

    def _create_access_token(self, user: EmployeeUser) -> tuple[str, int]:
        expires_minutes = settings.JWT_EXPIRE_MINUTES
        expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        payload = {
            "sub": user.username,
            "employee_id": user.employee_id,
            "full_name": user.full_name,
            "email": user.email,
            "department": user.department,
            "designation": user.designation,
            # Stable AD identity claims used for secure per-user chat history.
            "ad_object_id": user.ad_object_id,
            "upn": user.upn,
            "exp": expire,
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
        return token, expires_minutes * 60

    def decode_token(self, token: str) -> EmployeeUser:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please sign in again.",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        return EmployeeUser(
            username=username,
            employee_id=payload.get("employee_id"),
            full_name=payload.get("full_name"),
            email=payload.get("email"),
            department=payload.get("department"),
            designation=payload.get("designation"),
            ad_object_id=payload.get("ad_object_id"),
            upn=payload.get("upn"),
        )

    def refresh_user_profile(self, username: str) -> EmployeeUser:
        """Re-load display fields from phonebook / AD (no password required)."""
        return self._resolve_employee_profile(normalize_username(username))


_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
