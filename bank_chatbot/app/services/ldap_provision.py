"""
Active Directory user provisioning for Lead Portal sales agents.

Requires a service account (LDAP_BIND_USER) with permission to create users
under LDAP_USERS_OU and reset passwords. Password operations typically need
LDAPS (LDAP_USE_SSL=True or port 636).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, status
from ldap3 import MODIFY_REPLACE, SIMPLE, Connection, Server
from ldap3.core.exceptions import LDAPException

from app.core.config import settings
from app.services.ldap_auth import LdapAuthService, normalize_username, _auth_search_base

logger = logging.getLogger(__name__)

_UAC_DISABLED = 514
_UAC_ENABLED = 512


def _email_domain_suffix() -> str:
    domain = (settings.LDAP_EMAIL_DOMAIN or "@ebl-bd.com").strip()
    return domain if domain.startswith("@") else f"@{domain}"


def _upn_domain() -> str:
    return (settings.LDAP_DOMAIN or "ebl.bd").strip()


def _split_name(full_name: str) -> Tuple[str, str]:
    parts = full_name.strip().split(None, 1)
    if not parts:
        return "User", "Account"
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], parts[1]


def _sanitize_cn(value: str) -> str:
    cleaned = re.sub(r'[,+=\\<>#;"/]', "", value.strip())
    return cleaned or "User"


class LdapProvisionService:
    def __init__(self) -> None:
        self._ldap_auth = LdapAuthService()

    def _server(self) -> Server:
        return Server(
            settings.LDAP_SERVER,
            port=settings.LDAP_PORT,
            use_ssl=settings.LDAP_USE_SSL,
            connect_timeout=settings.LDAP_CONNECT_TIMEOUT,
        )

    def _service_connection(self) -> Connection:
        if not settings.LDAP_SERVER:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LDAP is not configured",
            )
        if not settings.LDAP_BIND_USER or not settings.LDAP_BIND_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LDAP service account is not configured for user provisioning",
            )
        conn = Connection(
            self._server(),
            user=settings.LDAP_BIND_USER,
            password=settings.LDAP_BIND_PASSWORD,
            authentication=SIMPLE,
            auto_bind=True,
            receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
        )
        if not conn.bound:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LDAP service account bind failed",
            )
        return conn

    def find_user_dn(self, username: str) -> Optional[str]:
        normalized = normalize_username(username)
        if not normalized:
            return None
        conn = self._service_connection()
        try:
            entry = self._search_user_entry(conn, normalized)
            return str(entry.entry_dn) if entry else None
        finally:
            conn.unbind()

    def user_exists(self, username: str) -> bool:
        return self.find_user_dn(username) is not None

    def _search_user_entry(self, conn: Connection, normalized_username: str):
        search_base = _auth_search_base()
        if not search_base:
            return None
        safe = re.escape(normalized_username)
        search_filter = (
            "(&(objectClass=user)(objectCategory=person)"
            f"(|(sAMAccountName={safe})(userPrincipalName={safe}*)(employeeID={safe})))"
        )
        conn.search(
            search_base=search_base,
            search_filter=search_filter,
            attributes=["sAMAccountName", "pwdLastSet", "userAccountControl", "distinguishedName"],
            size_limit=1,
        )
        return conn.entries[0] if conn.entries else None

    def must_change_password(self, username: str) -> bool:
        normalized = normalize_username(username)
        if not normalized:
            return False
        conn = self._service_connection()
        try:
            entry = self._search_user_entry(conn, normalized)
            if not entry:
                return False
            pwd_last_set = getattr(entry, "pwdLastSet", None)
            if pwd_last_set is None:
                return False
            value = pwd_last_set.value if hasattr(pwd_last_set, "value") else pwd_last_set
            try:
                return int(value) == 0
            except (TypeError, ValueError):
                return False
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("[LDAP] pwdLastSet check failed for %s: %s", normalized, exc)
            return False
        finally:
            conn.unbind()

    def create_user(
        self,
        *,
        username: str,
        employee_id: str,
        full_name: str,
        email: Optional[str],
        initial_password: str,
    ) -> str:
        if not settings.LDAP_PROVISION_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AD user provisioning is disabled (set LDAP_PROVISION_ENABLED=True)",
            )
        users_ou = (settings.LDAP_USERS_OU or "").strip()
        if not users_ou:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LDAP_USERS_OU is not configured",
            )

        normalized = normalize_username(username).lower()
        if not re.match(r"^[a-z][a-z0-9._-]{1,63}$", normalized):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Username must start with a letter and contain only letters, digits, . _ -",
            )

        if self.user_exists(normalized):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Active Directory user '{normalized}' already exists",
            )

        given, surname = _split_name(full_name)
        cn = _sanitize_cn(full_name)
        user_dn = f"CN={cn},{users_ou}"
        upn = f"{normalized}@{_upn_domain()}"
        mail = email or f"{normalized}{_email_domain_suffix()}"

        attributes: Dict[str, Any] = {
            "sAMAccountName": normalized,
            "userPrincipalName": upn,
            "displayName": full_name.strip(),
            "givenName": given,
            "sn": surname,
            "mail": mail,
            "employeeID": employee_id.strip(),
            "userAccountControl": _UAC_DISABLED,
        }

        conn = self._service_connection()
        try:
            if not conn.add(
                user_dn,
                ["top", "person", "organizationalPerson", "user"],
                attributes,
            ):
                detail = conn.result.get("description") or "Failed to create AD user"
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

            try:
                if not conn.extend.microsoft.modify_password(user_dn, initial_password):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=(
                            conn.result.get("description")
                            or "Failed to set initial password (LDAPS may be required)"
                        ),
                    )
            except HTTPException:
                conn.delete(user_dn)
                raise
            except LDAPException as exc:
                conn.delete(user_dn)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to set initial password: {exc}",
                ) from exc

            if not conn.modify(user_dn, {"userAccountControl": [(MODIFY_REPLACE, [_UAC_ENABLED])]}):
                logger.warning("[LDAP] Enable account failed for %s: %s", normalized, conn.result)

            if not conn.modify(user_dn, {"pwdLastSet": [(MODIFY_REPLACE, [0])]}):
                logger.warning("[LDAP] pwdLastSet=0 failed for %s: %s", normalized, conn.result)

            logger.info("[LDAP] Provisioned AD user %s (%s)", normalized, user_dn)
            return user_dn
        except HTTPException:
            raise
        except LDAPException as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Active Directory error: {exc}",
            ) from exc
        finally:
            conn.unbind()

    def change_password(self, username: str, current_password: str, new_password: str) -> None:
        normalized = normalize_username(username)
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid username")

        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New password must be at least 8 characters",
            )

        user_dn = self.find_user_dn(normalized)
        if not user_dn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in AD")

        if not self._ldap_auth.authenticate(normalized, current_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )

        conn = self._service_connection()
        try:
            if not conn.extend.microsoft.modify_password(user_dn, new_password, current_password):
                detail = conn.result.get("description") or "Password change failed"
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
            logger.info("[LDAP] Password changed for %s", normalized)
        except HTTPException:
            raise
        except LDAPException as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Password change failed: {exc}",
            ) from exc
        finally:
            conn.unbind()


_ldap_provision: Optional[LdapProvisionService] = None


def get_ldap_provision() -> LdapProvisionService:
    global _ldap_provision
    if _ldap_provision is None:
        _ldap_provision = LdapProvisionService()
    return _ldap_provision
