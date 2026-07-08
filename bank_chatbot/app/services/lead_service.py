"""Lead Generation business logic, RBAC, validation, and audit logging."""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import EmployeeUser
from app.models.lead import (
    LeadActivityLog,
    LeadAssignmentHistory,
    LeadFeedback,
    LeadLifecycleStatus,
    LeadMaster,
    LeadProductType,
    LeadStatusHistory,
    LeadUserRole,
    LeadUserRoleRecord,
    format_lead_reference_no,
)
from app.models.leads import (
    LeadActivityCreateRequest,
    LeadAssignRequest,
    LeadCreateRequest,
    LeadDetail,
    LeadFeedbackCreateRequest,
    LeadFeedbackOut,
    LeadStatusHistoryOut,
    LeadStatusUpdateRequest,
    LeadSummary,
)

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    LeadLifecycleStatus.CONVERTED.value,
    LeadLifecycleStatus.NOT_INTERESTED.value,
    LeadLifecycleStatus.REJECTED.value,
    LeadLifecycleStatus.CLOSED.value,
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    LeadLifecycleStatus.SUBMITTED.value: {
        LeadLifecycleStatus.ASSIGNED.value,
        LeadLifecycleStatus.REJECTED.value,
        LeadLifecycleStatus.CLOSED.value,
    },
    LeadLifecycleStatus.ASSIGNED.value: {
        LeadLifecycleStatus.CONTACTED.value,
        LeadLifecycleStatus.REJECTED.value,
        LeadLifecycleStatus.CLOSED.value,
    },
    LeadLifecycleStatus.CONTACTED.value: {
        LeadLifecycleStatus.INTERESTED.value,
        LeadLifecycleStatus.FOLLOW_UP_REQUIRED.value,
        LeadLifecycleStatus.NOT_INTERESTED.value,
        LeadLifecycleStatus.REJECTED.value,
        LeadLifecycleStatus.CLOSED.value,
    },
    LeadLifecycleStatus.INTERESTED.value: {
        LeadLifecycleStatus.CONVERTED.value,
        LeadLifecycleStatus.FOLLOW_UP_REQUIRED.value,
        LeadLifecycleStatus.NOT_INTERESTED.value,
    },
    LeadLifecycleStatus.FOLLOW_UP_REQUIRED.value: {
        LeadLifecycleStatus.CONTACTED.value,
        LeadLifecycleStatus.INTERESTED.value,
        LeadLifecycleStatus.CONVERTED.value,
        LeadLifecycleStatus.NOT_INTERESTED.value,
        LeadLifecycleStatus.CLOSED.value,
    },
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _actor_id(user: EmployeeUser) -> str:
    return user.employee_id or user.username


def _status_label(status: str) -> str:
    return status.replace("_", " ").title()


def mask_mobile(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "****"
    return f"{'*' * max(len(digits) - 4, 4)}{digits[-4:]}"


def mask_email(value: Optional[str]) -> Optional[str]:
    if not value or "@" not in value:
        return None
    local, domain = value.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def normalize_mobile(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("880") and len(digits) == 13:
        return f"+{digits}"
    if digits.startswith("01") and len(digits) == 11:
        return digits
    if len(digits) == 10 and digits[0] == "1":
        return f"0{digits}"
    return value.strip()


def _valid_bd_mobile(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("880"):
        digits = "0" + digits[3:]
    elif not digits.startswith("0") and len(digits) == 10:
        digits = "0" + digits
    return bool(re.match(r"^01[3-9]\d{8}$", digits))


def validate_lead_create(data: LeadCreateRequest) -> None:
    if not data.customer_mobile and not data.customer_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of customer_mobile or customer_email is required",
        )
    if data.customer_mobile and not _valid_bd_mobile(data.customer_mobile):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Bangladesh mobile number format",
        )


def get_user_roles(db: Session, user: EmployeeUser) -> Set[LeadUserRole]:
    actor = _actor_id(user)
    identity_keys = {actor, user.username}
    if user.employee_id:
        identity_keys.add(user.employee_id)
    try:
        from app.services.ldap_auth import LdapAuthService

        ad_profile = LdapAuthService().lookup_by_username(user.username)
        if ad_profile:
            if ad_profile.get("employee_id"):
                identity_keys.add(str(ad_profile["employee_id"]))
            if ad_profile.get("username"):
                identity_keys.add(str(ad_profile["username"]))
    except Exception as exc:
        logger.debug("[LEAD] AD identity enrichment skipped: %s", exc)

    rows = (
        db.query(LeadUserRoleRecord)
        .filter(LeadUserRoleRecord.employee_id.in_(identity_keys))
        .all()
    )
    roles = {LeadUserRole(row.role) for row in rows if row.role in LeadUserRole._value2member_map_}
    if not roles:
        roles = {LeadUserRole.EMPLOYEE}
    return roles


def role_names(roles: Set[LeadUserRole]) -> List[str]:
    return sorted(r.value for r in roles)


def get_user_permissions(roles: Set[LeadUserRole]) -> dict[str, bool]:
    """Portal/API capability flags derived from DB roles."""
    return {
        "view_all": can_manage_all_leads(roles),
        "assign": can_assign_leads(roles),
        "export": can_export_leads(roles),
        "manage_roles": _has_any_role(roles, LeadUserRole.ADMIN),
        "update_status": _has_any_role(
            roles,
            LeadUserRole.SALES_USER,
            LeadUserRole.SALES_MANAGER,
            LeadUserRole.ADMIN,
        ),
        "view_assigned_queue": _has_any_role(
            roles,
            LeadUserRole.SALES_USER,
            LeadUserRole.SALES_MANAGER,
            LeadUserRole.ADMIN,
        ),
    }


def get_lead_permissions(
    user: EmployeeUser,
    lead: LeadMaster,
    roles: Set[LeadUserRole],
) -> dict[str, bool]:
    return {
        "can_view": can_view_lead(user, lead, roles),
        "can_update_status": can_update_lead_status(user, lead, roles),
        "can_assign": can_assign_leads(roles),
        "can_add_feedback": can_add_feedback(user, lead, roles),
        "can_delete": _has_any_role(roles, LeadUserRole.ADMIN),
    }


def _has_any_role(roles: Set[LeadUserRole], *allowed: LeadUserRole) -> bool:
    return bool(roles.intersection(allowed))


def _is_lead_owner(user: EmployeeUser, lead: LeadMaster) -> bool:
    actor = _actor_id(user)
    return lead.created_by_employee_id in {actor, user.username}


def _is_lead_assignee(user: EmployeeUser, lead: LeadMaster) -> bool:
    if not lead.assigned_to_user_id:
        return False
    actor = _actor_id(user)
    return lead.assigned_to_user_id in {actor, user.username}


def can_view_lead(user: EmployeeUser, lead: LeadMaster, roles: Set[LeadUserRole]) -> bool:
    if _has_any_role(roles, LeadUserRole.ADMIN, LeadUserRole.SALES_MANAGER):
        return True
    if _has_any_role(roles, LeadUserRole.SALES_USER) and _is_lead_assignee(user, lead):
        return True
    if _is_lead_owner(user, lead):
        return True
    return False


def can_manage_all_leads(roles: Set[LeadUserRole]) -> bool:
    return _has_any_role(roles, LeadUserRole.ADMIN, LeadUserRole.SALES_MANAGER)


def can_assign_leads(roles: Set[LeadUserRole]) -> bool:
    return _has_any_role(roles, LeadUserRole.ADMIN, LeadUserRole.SALES_MANAGER)


def can_update_lead_status(user: EmployeeUser, lead: LeadMaster, roles: Set[LeadUserRole]) -> bool:
    if can_manage_all_leads(roles):
        return True
    if _has_any_role(roles, LeadUserRole.SALES_USER) and _is_lead_assignee(user, lead):
        return True
    return False


def can_add_feedback(user: EmployeeUser, lead: LeadMaster, roles: Set[LeadUserRole]) -> bool:
    return can_update_lead_status(user, lead, roles)


def can_export_leads(roles: Set[LeadUserRole]) -> bool:
    return can_manage_all_leads(roles)


def require_lead_access(
    user: EmployeeUser,
    lead: LeadMaster,
    roles: Set[LeadUserRole],
) -> None:
    if not can_view_lead(user, lead, roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _next_lead_reference(db: Session) -> str:
    seq_val = db.execute(text("SELECT nextval('lead_reference_seq')")).scalar()
    return format_lead_reference_no(int(seq_val))


def _log_status_change(
    db: Session,
    lead: LeadMaster,
    old_status: Optional[str],
    new_status: str,
    changed_by: str,
    note: Optional[str] = None,
) -> None:
    db.add(
        LeadStatusHistory(
            lead_id=lead.id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            note=note,
        )
    )


def _log_activity(
    db: Session,
    lead_id: int,
    activity_type: str,
    performed_by: str,
    activity_details: Optional[str] = None,
) -> LeadActivityLog:
    entry = LeadActivityLog(
        lead_id=lead_id,
        activity_type=activity_type,
        activity_details=activity_details,
        performed_by=performed_by,
    )
    db.add(entry)
    return entry


def create_lead(
    db: Session,
    user: EmployeeUser,
    data: LeadCreateRequest,
) -> LeadMaster:
    validate_lead_create(data)
    actor = _actor_id(user)
    ref = _next_lead_reference(db)

    mobile = normalize_mobile(data.customer_mobile) if data.customer_mobile else None
    lead = LeadMaster(
        lead_reference_no=ref,
        customer_name=data.customer_name.strip(),
        customer_mobile=mobile,
        customer_email=str(data.customer_email) if data.customer_email else None,
        preferred_contact_time=data.preferred_contact_time,
        customer_location=data.customer_location,
        preferred_branch=data.preferred_branch,
        product_type=data.product_type.value,
        remarks=data.remarks,
        status=LeadLifecycleStatus.SUBMITTED.value,
        created_by_employee_id=actor,
        created_by_name=user.full_name,
        created_by_department=user.department,
        created_by_branch=data.created_by_branch,
        created_by_mobile=data.created_by_mobile,
        created_by_email=user.email,
        chat_session_id=data.chat_session_id,
    )
    db.add(lead)
    db.flush()

    _log_status_change(
        db,
        lead,
        old_status=None,
        new_status=LeadLifecycleStatus.SUBMITTED.value,
        changed_by=actor,
        note="Lead created",
    )
    _log_activity(db, lead.id, "created", actor, f"Lead {ref} submitted")
    db.commit()
    db.refresh(lead)
    logger.info("[LEAD] Created %s by %s", ref, actor)
    return lead


def get_lead_by_reference(db: Session, lead_reference_no: str) -> Optional[LeadMaster]:
    ref = lead_reference_no.strip().upper()
    if not ref.startswith("LD-"):
        ref = f"LD-{ref.replace('LD', '').strip('-')}"
    return (
        db.query(LeadMaster)
        .filter(
            LeadMaster.lead_reference_no == ref,
            LeadMaster.deleted_at.is_(None),
        )
        .first()
    )


def to_summary(lead: LeadMaster, *, mask_pii: bool = False) -> LeadSummary:
    mobile = mask_mobile(lead.customer_mobile) if mask_pii else lead.customer_mobile
    email = mask_email(lead.customer_email) if mask_pii else lead.customer_email
    return LeadSummary(
        lead_reference_no=lead.lead_reference_no,
        customer_name=lead.customer_name,
        customer_mobile=mobile,
        customer_email=email,
        product_type=lead.product_type,
        product_type_label=LeadProductType.label_for(lead.product_type),
        status=lead.status,
        status_label=_status_label(lead.status),
        preferred_branch=lead.preferred_branch,
        assigned_to_user_id=lead.assigned_to_user_id,
        created_by_employee_id=lead.created_by_employee_id,
        created_by_name=lead.created_by_name,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def to_detail(lead: LeadMaster, *, mask_pii: bool = False) -> LeadDetail:
    summary = to_summary(lead, mask_pii=mask_pii)
    return LeadDetail(
        **summary.model_dump(),
        preferred_contact_time=lead.preferred_contact_time,
        customer_location=lead.customer_location,
        remarks=lead.remarks,
        created_by_department=lead.created_by_department,
        created_by_branch=lead.created_by_branch,
        created_by_email=lead.created_by_email,
        closed_at=lead.closed_at,
        chat_session_id=str(lead.chat_session_id) if lead.chat_session_id else None,
    )


def _validate_assignee(employee_id: str) -> None:
    """Ensure assignee exists in Active Directory."""
    value = employee_id.strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Assignee employee ID is required",
        )
    if not settings.LDAP_SERVER or not settings.LDAP_BIND_USER:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LDAP is not configured for assignee validation",
        )
    from app.services.ldap_auth import LdapAuthService

    profile = LdapAuthService().lookup_directory_user(value)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee '{value}' not found in Active Directory",
        )


def _scoped_leads_query(
    db: Session,
    user: EmployeeUser,
    roles: Set[LeadUserRole],
    *,
    status_filter: Optional[str] = None,
    product_type: Optional[str] = None,
    branch: Optional[str] = None,
    assigned_to: Optional[str] = None,
    created_by: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    search: Optional[str] = None,
):
    q = db.query(LeadMaster).filter(LeadMaster.deleted_at.is_(None))

    if can_manage_all_leads(roles):
        pass
    elif _has_any_role(roles, LeadUserRole.SALES_USER):
        actor = _actor_id(user)
        q = q.filter(
            or_(
                LeadMaster.assigned_to_user_id.in_({actor, user.username}),
                LeadMaster.created_by_employee_id.in_({actor, user.username}),
            )
        )
    else:
        actor = _actor_id(user)
        q = q.filter(LeadMaster.created_by_employee_id.in_({actor, user.username}))

    if status_filter:
        q = q.filter(LeadMaster.status == status_filter)
    if product_type:
        q = q.filter(LeadMaster.product_type == product_type)
    if branch:
        q = q.filter(LeadMaster.preferred_branch.ilike(f"%{branch}%"))
    if assigned_to:
        q = q.filter(LeadMaster.assigned_to_user_id == assigned_to)
    if created_by:
        q = q.filter(LeadMaster.created_by_employee_id == created_by)
    if date_from:
        q = q.filter(LeadMaster.created_at >= date_from)
    if date_to:
        q = q.filter(LeadMaster.created_at <= date_to)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                LeadMaster.lead_reference_no.ilike(term),
                LeadMaster.customer_name.ilike(term),
                LeadMaster.customer_mobile.ilike(term),
                LeadMaster.customer_email.ilike(term),
            )
        )
    return q


def list_leads(
    db: Session,
    user: EmployeeUser,
    roles: Set[LeadUserRole],
    *,
    status_filter: Optional[str] = None,
    product_type: Optional[str] = None,
    branch: Optional[str] = None,
    assigned_to: Optional[str] = None,
    created_by: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[LeadMaster], int]:
    q = _scoped_leads_query(
        db,
        user,
        roles,
        status_filter=status_filter,
        product_type=product_type,
        branch=branch,
        assigned_to=assigned_to,
        created_by=created_by,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )

    total = q.count()
    rows = (
        q.order_by(LeadMaster.created_at.desc())
        .offset(offset)
        .limit(min(limit, 500))
        .all()
    )
    return rows, total


def list_my_submitted(
    db: Session,
    user: EmployeeUser,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[LeadMaster], int]:
    actor = _actor_id(user)
    q = db.query(LeadMaster).filter(
        LeadMaster.deleted_at.is_(None),
        LeadMaster.created_by_employee_id.in_({actor, user.username}),
    )
    total = q.count()
    rows = q.order_by(LeadMaster.created_at.desc()).offset(offset).limit(min(limit, 500)).all()
    return rows, total


def list_assigned(
    db: Session,
    user: EmployeeUser,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[LeadMaster], int]:
    actor = _actor_id(user)
    q = db.query(LeadMaster).filter(
        LeadMaster.deleted_at.is_(None),
        LeadMaster.assigned_to_user_id.in_({actor, user.username}),
    )
    total = q.count()
    rows = q.order_by(LeadMaster.created_at.desc()).offset(offset).limit(min(limit, 500)).all()
    return rows, total


def update_status(
    db: Session,
    user: EmployeeUser,
    lead: LeadMaster,
    roles: Set[LeadUserRole],
    data: LeadStatusUpdateRequest,
) -> LeadMaster:
    if not can_update_lead_status(user, lead, roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update lead status")

    new_status = data.status.value
    old_status = lead.status
    if old_status == new_status:
        return lead

    if old_status in TERMINAL_STATUSES and not _has_any_role(roles, LeadUserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lead is in terminal status '{old_status}'",
        )

    allowed = ALLOWED_TRANSITIONS.get(old_status, set())
    if new_status not in allowed and not _has_any_role(roles, LeadUserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition from '{old_status}' to '{new_status}'",
        )

    actor = _actor_id(user)
    lead.status = new_status
    lead.updated_at = _utcnow()
    if new_status in TERMINAL_STATUSES:
        lead.closed_at = _utcnow()

    _log_status_change(db, lead, old_status, new_status, actor, data.note)
    _log_activity(db, lead.id, "status_update", actor, f"{old_status} -> {new_status}")
    db.commit()
    db.refresh(lead)
    return lead


def assign_lead(
    db: Session,
    user: EmployeeUser,
    lead: LeadMaster,
    roles: Set[LeadUserRole],
    data: LeadAssignRequest,
) -> LeadMaster:
    if not can_assign_leads(roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign leads")

    actor = _actor_id(user)
    old_assignee = lead.assigned_to_user_id
    new_assignee = data.assigned_to_user_id.strip()
    _validate_assignee(new_assignee)
    lead.assigned_to_user_id = new_assignee
    if lead.status == LeadLifecycleStatus.SUBMITTED.value:
        lead.status = LeadLifecycleStatus.ASSIGNED.value
        _log_status_change(
            db,
            lead,
            LeadLifecycleStatus.SUBMITTED.value,
            LeadLifecycleStatus.ASSIGNED.value,
            actor,
            data.note,
        )
    lead.updated_at = _utcnow()

    db.add(
        LeadAssignmentHistory(
            lead_id=lead.id,
            old_assigned_to=old_assignee,
            new_assigned_to=new_assignee,
            assigned_by=actor,
            note=data.note,
        )
    )
    _log_activity(db, lead.id, "assignment", actor, f"Assigned to {new_assignee}")
    db.commit()
    db.refresh(lead)
    return lead


def add_feedback(
    db: Session,
    user: EmployeeUser,
    lead: LeadMaster,
    roles: Set[LeadUserRole],
    data: LeadFeedbackCreateRequest,
) -> LeadFeedback:
    if not can_add_feedback(user, lead, roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot add feedback")

    actor = _actor_id(user)
    entry = LeadFeedback(
        lead_id=lead.id,
        feedback_text=data.feedback_text.strip(),
        feedback_by=actor,
        feedback_to_employee_id=data.feedback_to_employee_id.strip(),
    )
    db.add(entry)
    _log_activity(db, lead.id, "feedback", actor, "Feedback recorded")
    db.commit()
    db.refresh(entry)
    return entry


def get_feedback_for_lead(
    db: Session,
    user: EmployeeUser,
    lead: LeadMaster,
    roles: Set[LeadUserRole],
) -> List[LeadFeedback]:
    require_lead_access(user, lead, roles)
    q = db.query(LeadFeedback).filter(LeadFeedback.lead_id == lead.id)
    if not can_manage_all_leads(roles) and not _is_lead_owner(user, lead):
        actor = _actor_id(user)
        q = q.filter(
            or_(
                LeadFeedback.feedback_to_employee_id.in_({actor, user.username}),
                LeadFeedback.feedback_by.in_({actor, user.username}),
            )
        )
    return q.order_by(LeadFeedback.created_at.desc()).all()


def get_status_history(
    db: Session,
    user: EmployeeUser,
    lead: LeadMaster,
    roles: Set[LeadUserRole],
) -> List[LeadStatusHistory]:
    require_lead_access(user, lead, roles)
    return (
        db.query(LeadStatusHistory)
        .filter(LeadStatusHistory.lead_id == lead.id)
        .order_by(LeadStatusHistory.changed_at.desc())
        .all()
    )


def add_activity(
    db: Session,
    user: EmployeeUser,
    lead: LeadMaster,
    roles: Set[LeadUserRole],
    data: LeadActivityCreateRequest,
) -> LeadActivityLog:
    if not can_update_lead_status(user, lead, roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot log activity")
    actor = _actor_id(user)
    entry = _log_activity(db, lead.id, data.activity_type, actor, data.activity_details)
    db.commit()
    db.refresh(entry)
    return entry


def soft_delete_lead(
    db: Session,
    user: EmployeeUser,
    lead: LeadMaster,
    roles: Set[LeadUserRole],
) -> None:
    if not _has_any_role(roles, LeadUserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    actor = _actor_id(user)
    lead.deleted_at = _utcnow()
    _log_activity(db, lead.id, "deleted", actor, "Soft deleted")
    db.commit()


def assign_role(
    db: Session,
    admin: EmployeeUser,
    employee_id: str,
    role: LeadUserRole,
) -> LeadUserRoleRecord:
    actor = _actor_id(admin)
    existing = (
        db.query(LeadUserRoleRecord)
        .filter(
            LeadUserRoleRecord.employee_id == employee_id,
            LeadUserRoleRecord.role == role.value,
        )
        .first()
    )
    if existing:
        return existing
    record = LeadUserRoleRecord(
        employee_id=employee_id,
        role=role.value,
        created_by=actor,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_roles(db: Session) -> List[LeadUserRoleRecord]:
    return db.query(LeadUserRoleRecord).order_by(LeadUserRoleRecord.employee_id).all()


def revoke_role(
    db: Session,
    admin: EmployeeUser,
    employee_id: str,
    role: LeadUserRole,
) -> None:
    deleted = (
        db.query(LeadUserRoleRecord)
        .filter(
            LeadUserRoleRecord.employee_id == employee_id,
            LeadUserRoleRecord.role == role.value,
        )
        .delete(synchronize_session=False)
    )
    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )
    db.commit()
    logger.info(
        "[LEAD] Revoked role %s from %s by %s",
        role.value,
        employee_id,
        _actor_id(admin),
    )


def export_leads_csv(
    db: Session,
    user: EmployeeUser,
    roles: Set[LeadUserRole],
    **list_kwargs,
) -> str:
    if not can_export_leads(roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot export leads")
    rows, _ = list_leads(db, user, roles, limit=10000, offset=0, **list_kwargs)
    actor = _actor_id(user)
    logger.info("[LEAD] Export by %s: %d rows", actor, len(rows))

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "lead_reference_no",
            "customer_name",
            "customer_mobile",
            "customer_email",
            "product_type",
            "status",
            "preferred_branch",
            "assigned_to_user_id",
            "created_by_employee_id",
            "created_by_name",
            "created_at",
        ]
    )
    for lead in rows:
        writer.writerow(
            [
                lead.lead_reference_no,
                lead.customer_name,
                lead.customer_mobile or "",
                lead.customer_email or "",
                lead.product_type,
                lead.status,
                lead.preferred_branch or "",
                lead.assigned_to_user_id or "",
                lead.created_by_employee_id,
                lead.created_by_name or "",
                lead.created_at.isoformat(),
            ]
        )
    return buf.getvalue()


def get_dashboard_stats(
    db: Session,
    user: EmployeeUser,
    roles: Set[LeadUserRole],
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    """Aggregate lead counts for dashboard (scoped by RBAC) via SQL GROUP BY."""
    q = _scoped_leads_query(
        db, user, roles, date_from=date_from, date_to=date_to
    )
    total = q.count()
    status_rows = (
        q.with_entities(LeadMaster.status, func.count())
        .group_by(LeadMaster.status)
        .all()
    )
    product_rows = (
        q.with_entities(LeadMaster.product_type, func.count())
        .group_by(LeadMaster.product_type)
        .all()
    )
    pending_statuses = {
        LeadLifecycleStatus.ASSIGNED.value,
        LeadLifecycleStatus.CONTACTED.value,
        LeadLifecycleStatus.FOLLOW_UP_REQUIRED.value,
    }
    pending_assigned = q.filter(
        LeadMaster.assigned_to_user_id.isnot(None),
        LeadMaster.status.in_(pending_statuses),
    ).count()
    by_status = {status: count for status, count in status_rows}
    by_product = {
        LeadProductType.label_for(product): count
        for product, count in sorted(product_rows, key=lambda r: r[0])
    }
    return {
        "total": total,
        "by_status": by_status,
        "by_product": by_product,
        "pending_assigned": pending_assigned,
    }


def feedback_to_out(entry: LeadFeedback) -> LeadFeedbackOut:
    return LeadFeedbackOut(
        id=entry.id,
        feedback_text=entry.feedback_text,
        feedback_by=entry.feedback_by,
        feedback_to_employee_id=entry.feedback_to_employee_id,
        created_at=entry.created_at,
    )


def status_history_to_out(entry: LeadStatusHistory) -> LeadStatusHistoryOut:
    return LeadStatusHistoryOut(
        old_status=entry.old_status,
        new_status=entry.new_status,
        changed_by=entry.changed_by,
        changed_at=entry.changed_at,
        note=entry.note,
    )
