"""Business logic for portal user provisioning and password-change tracking."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import EmployeeUser
from app.models.lead import LeadUserRole
from app.models.portal_user import (
    PortalProvisionedUser,
    PortalUserSummary,
    RegisterPortalUserRequest,
)
from app.services import lead_service as lead_svc
from app.services.ldap_auth import LdapAuthService
from app.services.ldap_provision import get_ldap_provision

logger = logging.getLogger(__name__)


def to_summary(row: PortalProvisionedUser) -> PortalUserSummary:
    return PortalUserSummary(
        username=row.username,
        employee_id=row.employee_id,
        full_name=row.full_name,
        email=row.email,
        lead_role=row.lead_role,
        must_change_password=row.must_change_password,
        provisioned_by=row.provisioned_by,
        provisioned_at=row.provisioned_at,
        disabled_at=row.disabled_at,
    )


def list_provisioned_users(
    db: Session, limit: int = 200, offset: int = 0
) -> Tuple[List[PortalProvisionedUser], int]:
    q = db.query(PortalProvisionedUser).filter(PortalProvisionedUser.disabled_at.is_(None))
    total = q.count()
    rows = (
        q.order_by(PortalProvisionedUser.provisioned_at.desc())
        .offset(offset)
        .limit(min(limit, 500))
        .all()
    )
    return rows, total


def get_provisioned_user(db: Session, username: str) -> Optional[PortalProvisionedUser]:
    normalized = username.strip().lower()
    return (
        db.query(PortalProvisionedUser)
        .filter(PortalProvisionedUser.username == normalized)
        .first()
    )


def get_provisioned_by_employee_id(db: Session, employee_id: str) -> Optional[PortalProvisionedUser]:
    emp_id = employee_id.strip()
    return (
        db.query(PortalProvisionedUser)
        .filter(
            PortalProvisionedUser.employee_id == emp_id,
            PortalProvisionedUser.disabled_at.is_(None),
        )
        .first()
    )


def resolve_must_change_password(db: Session, username: str) -> bool:
    row = get_provisioned_user(db, username)
    if row and row.must_change_password:
        return True
    return get_ldap_provision().must_change_password(username)


def clear_must_change_password(db: Session, username: str) -> None:
    row = get_provisioned_user(db, username)
    if not row:
        return
    row.must_change_password = False
    db.commit()


def require_lead_admin(db: Session, user: EmployeeUser) -> None:
    roles = lead_svc.get_user_roles(db, user)
    if not lead_svc._has_any_role(roles, LeadUserRole.ADMIN):  # noqa: SLF001
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


def lookup_employee_profile(employee_id: str) -> Dict[str, str | None]:
    """Resolve employee from Active Directory only."""
    emp_id = (employee_id or "").strip()
    if not emp_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee ID is required")

    if not settings.LDAP_SERVER or not settings.LDAP_BIND_USER:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LDAP is not configured for employee lookup",
        )

    ldap = LdapAuthService()
    profile = ldap.lookup_directory_user(emp_id)
    if not profile or not profile.get("username"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No employee found in Active Directory for ID '{emp_id}'",
        )

    profile["username"] = str(profile["username"]).strip().lower()
    profile["employee_id"] = str(profile.get("employee_id") or emp_id).strip()
    profile["full_name"] = profile.get("full_name") or profile.get("display_name")
    profile["source"] = "active_directory"
    return profile


def register_portal_user(
    db: Session,
    admin: EmployeeUser,
    data: RegisterPortalUserRequest,
) -> PortalProvisionedUser:
    """Fetch employee from Active Directory by ID and register in the lead system."""
    require_lead_admin(db, admin)

    profile = lookup_employee_profile(data.employee_id)
    username = profile["username"]
    employee_id = profile["employee_id"]

    existing = get_provisioned_user(db, username) or get_provisioned_by_employee_id(db, employee_id)
    if existing and existing.disabled_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee {employee_id} ({username}) is already registered in the lead portal",
        )

    actor = admin.employee_id or admin.username
    if existing:
        existing.username = username
        existing.employee_id = employee_id
        existing.full_name = profile.get("full_name")
        existing.email = profile.get("email")
        existing.ad_dn = profile.get("ad_dn")
        existing.lead_role = data.lead_role.value
        existing.must_change_password = False
        existing.provisioned_by = actor
        existing.disabled_at = None
        row = existing
    else:
        row = PortalProvisionedUser(
            username=username,
            employee_id=employee_id,
            full_name=profile.get("full_name"),
            email=profile.get("email"),
            ad_dn=profile.get("ad_dn"),
            lead_role=data.lead_role.value,
            must_change_password=False,
            provisioned_by=actor,
        )
        db.add(row)

    db.flush()
    lead_svc.assign_role(db, admin, employee_id, data.lead_role)
    if employee_id.lower() != username:
        lead_svc.assign_role(db, admin, username, data.lead_role)

    db.commit()
    db.refresh(row)
    logger.info("[PORTAL] Registered %s (ID %s) from AD by %s", username, employee_id, actor)
    return row
