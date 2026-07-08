"""
Active Directory / LDAP authentication for employee login.

Mirrors the SkyPay MIS login flow: validate credentials via LDAP bind
(user@domain, then DOMAIN\\user NTLM fallback).
"""

from __future__ import annotations

import logging
import re
import uuid as _uuid
from typing import Any, Dict, List, Optional, Tuple

from ldap3 import NTLM, SIMPLE, Connection, Server
from ldap3.core.exceptions import LDAPException

from app.core.config import settings

logger = logging.getLogger(__name__)


def normalize_username(raw: str) -> str:
    """Strip domain/email prefix — same rules as SkyPay Login.aspx GetUsername."""
    value = (raw or "").strip()
    if not value:
        return ""
    if "\\" in value:
        return value.split("\\", 1)[1].strip()
    if "@" in value:
        return value.split("@", 1)[0].strip()
    return value


def _build_bind_identities(username: str) -> List[Tuple[str, str]]:
    """Return (bind_user, authentication) pairs to try."""
    identities: List[Tuple[str, str]] = []
    domain = (settings.LDAP_DOMAIN or "").strip()
    netbios = (settings.LDAP_NETBIOS_DOMAIN or "").strip()
    email_domain = (settings.LDAP_EMAIL_DOMAIN or "").strip()

    if domain:
        identities.append((f"{username}@{domain}", SIMPLE))
    if netbios:
        identities.append((f"{netbios}\\{username}", NTLM))
    if email_domain:
        suffix = email_domain if email_domain.startswith("@") else f"@{email_domain}"
        identities.append((f"{username}{suffix}", SIMPLE))
    # Last resort: raw username
    identities.append((username, SIMPLE))
    return identities


def _ldap_attr(entry, name: str) -> Optional[str]:
    if not hasattr(entry, name):
        return None
    value = getattr(entry, name)
    if not value:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value)


def _format_guid(value: Any) -> Optional[str]:
    """
    Normalize an AD objectGUID into a canonical string.

    objectGUID is the most stable per-user identifier in Active Directory: unlike
    sAMAccountName / UPN / email it never changes, even if the account is renamed
    or moved. We use it as the primary key for per-user chat history.
    """
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip().strip("{}").lower()
        return cleaned or None
    if isinstance(value, (bytes, bytearray)):
        try:
            # AD stores objectGUID little-endian; bytes_le renders it correctly.
            return str(_uuid.UUID(bytes_le=bytes(value)))
        except Exception:
            try:
                return bytes(value).hex()
            except Exception:
                return None
    return str(value)


def _read_object_guid(entry) -> Optional[str]:
    """Extract objectGUID from an ldap3 entry, preferring raw bytes."""
    if not hasattr(entry, "objectGUID"):
        return None
    attr = getattr(entry, "objectGUID")
    try:
        raw = getattr(attr, "raw_values", None)
        if raw:
            return _format_guid(raw[0])
    except Exception:
        pass
    try:
        return _format_guid(attr.value)
    except Exception:
        return _format_guid(attr)


def _auth_search_base() -> str:
    """Domain-wide base for login profile lookup (not the phonebook-sync OU)."""
    custom = (getattr(settings, "LDAP_AUTH_SEARCH_BASE", None) or "").strip()
    if custom:
        return custom
    domain = (settings.LDAP_DOMAIN or "").strip()
    if domain and "." in domain:
        return ",".join(f"DC={part}" for part in domain.split(".") if part)
    return (settings.LDAP_BASE_DN or "").strip()


def _clean_ad_display_name(raw: Optional[str]) -> Optional[str]:
    """Strip EBL-style org prefixes from AD cn, e.g. 'HO/ICT - Tanvir Jubair Islam'."""
    name = (raw or "").strip()
    if not name:
        return None
    if " - " in name:
        left, _, right = name.partition(" - ")
        right = right.strip()
        if right and ("/" in left or len(left) <= 24):
            return right
    return name


def _resolve_display_name(entry) -> Optional[str]:
    display = _ldap_attr(entry, "displayName")
    if display:
        return _clean_ad_display_name(display) or display

    given = _ldap_attr(entry, "givenName")
    surname = _ldap_attr(entry, "sn")
    if given and surname:
        return f"{given} {surname}".strip()
    if given:
        return given

    cn = _ldap_attr(entry, "cn")
    return _clean_ad_display_name(cn) or cn


class LdapAuthService:
    """Authenticate employees against Active Directory via LDAP bind."""

    def __init__(self) -> None:
        self.ldap_server = settings.LDAP_SERVER
        self.port = settings.LDAP_PORT
        self.use_ssl = settings.LDAP_USE_SSL

    def _server(self) -> Server:
        return Server(
            self.ldap_server,
            port=self.port,
            use_ssl=self.use_ssl,
            connect_timeout=settings.LDAP_CONNECT_TIMEOUT,
        )

    def authenticate(self, username: str, password: str) -> bool:
        return self.authenticate_and_get_profile(username, password) is not None

    def authenticate_and_get_profile(
        self,
        username: str,
        password: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Validate credentials and read display fields from AD using the user's session.
        """
        normalized = normalize_username(username)
        if not normalized or not password:
            return None

        if not self.ldap_server:
            logger.error("[AUTH] LDAP_SERVER is not configured")
            return None

        for bind_user, auth_method in _build_bind_identities(normalized):
            conn: Optional[Connection] = None
            try:
                conn = Connection(
                    self._server(),
                    user=bind_user,
                    password=password,
                    authentication=auth_method,
                    auto_bind=False,
                    receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
                )
                if not conn.bind():
                    continue

                logger.info(
                    "[AUTH] LDAP bind succeeded for user '%s' via %s",
                    normalized,
                    bind_user,
                )
                profile = self._read_profile_from_connection(conn, normalized)
                if profile:
                    return profile
                return {
                    "display_name": None,
                    "email": None,
                    "employee_id": normalized,
                    "department": None,
                    "designation": None,
                    "username": normalized,
                }
            except LDAPException as exc:
                logger.debug("[AUTH] LDAP bind error for %s: %s", bind_user, exc)
            except Exception as exc:
                logger.debug("[AUTH] Unexpected bind error for %s: %s", bind_user, exc)
            finally:
                if conn is not None:
                    try:
                        conn.unbind()
                    except Exception:
                        pass

        logger.info("[AUTH] LDAP bind failed for user '%s'", normalized)
        return None

    def _read_profile_from_connection(
        self,
        conn: Connection,
        normalized_username: str,
    ) -> Optional[Dict[str, Any]]:
        search_base = _auth_search_base()
        if not search_base:
            return None

        safe = re.escape(normalized_username)
        search_filter = (
            "(&(objectClass=user)(objectCategory=person)"
            f"(|(sAMAccountName={safe})(userPrincipalName={safe}*)(mail={safe}*)))"
        )
        try:
            conn.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=[
                    "displayName",
                    "cn",
                    "givenName",
                    "sn",
                    "mail",
                    "employeeID",
                    "sAMAccountName",
                    "userPrincipalName",
                    "objectGUID",
                    "title",
                    "department",
                ],
                size_limit=1,
            )
            if not conn.entries:
                logger.info(
                    "[AUTH] No AD entry for '%s' under %s",
                    normalized_username,
                    search_base,
                )
                return None

            entry = conn.entries[0]
            display_name = _resolve_display_name(entry)
            return {
                "display_name": display_name,
                "email": _ldap_attr(entry, "mail"),
                "employee_id": _ldap_attr(entry, "employeeID") or _ldap_attr(entry, "sAMAccountName") or normalized_username,
                "department": _ldap_attr(entry, "department"),
                "designation": _ldap_attr(entry, "title"),
                "username": _ldap_attr(entry, "sAMAccountName") or normalized_username,
                # Stable AD identifier + UPN captured for secure per-user history.
                "ad_object_id": _read_object_guid(entry),
                "upn": _ldap_attr(entry, "userPrincipalName"),
            }
        except Exception as exc:
            logger.warning("[AUTH] AD profile read failed for %s: %s", normalized_username, exc)
            return None

    def _try_bind(self, bind_user: str, password: str, authentication) -> bool:
        conn: Optional[Connection] = None
        try:
            conn = Connection(
                self._server(),
                user=bind_user,
                password=password,
                authentication=authentication,
                auto_bind=False,
                receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
            )
            return bool(conn.bind())
        except LDAPException as exc:
            logger.debug("[AUTH] LDAP bind error for %s: %s", bind_user, exc)
            return False
        except Exception as exc:
            logger.debug("[AUTH] Unexpected bind error for %s: %s", bind_user, exc)
            return False
        finally:
            if conn is not None:
                try:
                    conn.unbind()
                except Exception:
                    pass

    def lookup_display_name(self, username: str) -> Optional[str]:
        """
        Optional AD lookup for display name after successful bind.
        Uses the configured service account when available.
        """
        normalized = normalize_username(username)
        if not normalized or not settings.LDAP_BASE_DN:
            return None
        if not settings.LDAP_BIND_USER or not settings.LDAP_BIND_PASSWORD:
            return None

        conn: Optional[Connection] = None
        try:
            conn = Connection(
                self._server(),
                user=settings.LDAP_BIND_USER,
                password=settings.LDAP_BIND_PASSWORD,
                auto_bind=True,
                receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
            )
            profile = self._read_profile_from_connection(conn, normalized)
            if profile:
                return profile.get("display_name")
        except Exception as exc:
            logger.debug("[AUTH] AD display name lookup failed for %s: %s", normalized, exc)
        finally:
            if conn is not None:
                try:
                    conn.unbind()
                except Exception:
                    pass
        return None

    def _service_connection(self) -> Optional[Connection]:
        if not settings.LDAP_SERVER or not settings.LDAP_BIND_USER or not settings.LDAP_BIND_PASSWORD:
            return None
        try:
            conn = Connection(
                self._server(),
                user=settings.LDAP_BIND_USER,
                password=settings.LDAP_BIND_PASSWORD,
                auto_bind=True,
                receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
            )
            return conn if conn.bound else None
        except Exception as exc:
            logger.debug("[AUTH] Service account bind failed: %s", exc)
            return None

    def _profile_from_entry(self, entry, fallback_employee_id: str) -> Dict[str, Any]:
        display_name = _resolve_display_name(entry)
        username = _ldap_attr(entry, "sAMAccountName")
        email = _ldap_attr(entry, "mail")
        if not username and email and "@" in email:
            username = email.split("@", 1)[0]
        return {
            "display_name": display_name,
            "full_name": display_name,
            "email": email,
            "employee_id": _ldap_attr(entry, "employeeID") or fallback_employee_id,
            "department": _ldap_attr(entry, "department"),
            "designation": _ldap_attr(entry, "title"),
            "username": username,
            "ad_object_id": _read_object_guid(entry),
            "upn": _ldap_attr(entry, "userPrincipalName"),
            "ad_dn": str(entry.entry_dn),
            "source": "active_directory",
        }

    def lookup_by_employee_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Look up an existing AD user by employeeID using the service account."""
        emp_id = (employee_id or "").strip()
        if not emp_id:
            return None

        conn = self._service_connection()
        if not conn:
            return None

        search_base = _auth_search_base()
        if not search_base:
            conn.unbind()
            return None

        safe = re.escape(emp_id)
        search_filter = (
            "(&(objectClass=user)(objectCategory=person)"
            f"(|(employeeID={safe})(employeeNumber={safe})))"
        )
        try:
            conn.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=[
                    "displayName",
                    "cn",
                    "givenName",
                    "sn",
                    "mail",
                    "employeeID",
                    "employeeNumber",
                    "sAMAccountName",
                    "userPrincipalName",
                    "objectGUID",
                    "title",
                    "department",
                    "distinguishedName",
                ],
                size_limit=1,
            )
            if not conn.entries:
                logger.info("[AUTH] No AD entry for employee ID '%s'", emp_id)
                return None
            profile = self._profile_from_entry(conn.entries[0], emp_id)
            if not profile.get("username"):
                logger.info("[AUTH] AD entry for '%s' has no sAMAccountName/mail", emp_id)
                return None
            return profile
        except Exception as exc:
            logger.warning("[AUTH] AD lookup by employee ID failed for %s: %s", emp_id, exc)
            return None
        finally:
            try:
                conn.unbind()
            except Exception:
                pass

    def lookup_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Look up an existing AD user by sAMAccountName using the service account."""
        normalized = normalize_username(username)
        if not normalized:
            return None

        conn = self._service_connection()
        if not conn:
            return None

        search_base = _auth_search_base()
        if not search_base:
            conn.unbind()
            return None

        safe = re.escape(normalized)
        search_filter = (
            "(&(objectClass=user)(objectCategory=person)"
            f"(|(sAMAccountName={safe})(userPrincipalName={safe}*)(mail={safe}*)))"
        )
        try:
            conn.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=[
                    "displayName",
                    "cn",
                    "givenName",
                    "sn",
                    "mail",
                    "employeeID",
                    "employeeNumber",
                    "sAMAccountName",
                    "userPrincipalName",
                    "objectGUID",
                    "title",
                    "department",
                    "distinguishedName",
                ],
                size_limit=1,
            )
            if not conn.entries:
                return None
            return self._profile_from_entry(conn.entries[0], normalized)
        except Exception as exc:
            logger.warning("[AUTH] AD lookup by username failed for %s: %s", normalized, exc)
            return None
        finally:
            try:
                conn.unbind()
            except Exception:
                pass

    def lookup_directory_user(self, employee_id_or_login: str) -> Optional[Dict[str, Any]]:
        """Resolve an employee by AD employeeID/employeeNumber or Windows login."""
        value = (employee_id_or_login or "").strip()
        if not value:
            return None
        profile = self.lookup_by_employee_id(value)
        if profile:
            return profile
        return self.lookup_by_username(value)
