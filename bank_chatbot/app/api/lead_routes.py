"""REST API for Lead Generation module."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.postgres import get_db
from app.models.auth import EmployeeUser
from app.models.lead import LeadUserRole
from app.models.leads import (
    LeadActivityCreateRequest,
    LeadActivityOut,
    LeadAssignRequest,
    LeadCreateRequest,
    LeadCreateResponse,
    LeadDashboardStats,
    LeadDetail,
    LeadDetailPermissions,
    LeadDetailWithPermissions,
    LeadFeedbackCreateRequest,
    LeadFeedbackOut,
    LeadListResponse,
    LeadMyRolesResponse,
    LeadPermissions,
    LeadRoleAssignRequest,
    LeadRoleOut,
    LeadStatusHistoryOut,
    LeadStatusUpdateRequest,
    LeadSummary,
)
from app.services import lead_service as svc

lead_router = APIRouter(prefix="/leads", tags=["Leads"])


def _db_or_503() -> Session:
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


def _roles(db: Session, user: EmployeeUser):
    return svc.get_user_roles(db, user)


def _lead_or_404(db: Session, ref: str):
    lead = svc.get_lead_by_reference(db, ref)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def _mask_for_user(user: EmployeeUser, lead, roles) -> bool:
    """Mask PII when employee views leads they don't own and aren't sales staff on."""
    if svc.can_manage_all_leads(roles):
        return False
    if svc._has_any_role(roles, LeadUserRole.SALES_USER) and svc._is_lead_assignee(user, lead):
        return False
    return not svc._is_lead_owner(user, lead)


@lead_router.post("", response_model=LeadCreateResponse, status_code=status.HTTP_201_CREATED)
def create_lead(
    body: LeadCreateRequest,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        lead = svc.create_lead(db, current_user, body)
        return LeadCreateResponse(
            lead_reference_no=lead.lead_reference_no,
            message=f"Lead submitted successfully. Your Lead ID is {lead.lead_reference_no}.",
        )
    finally:
        db.close()


@lead_router.get("/my-submitted", response_model=LeadListResponse)
def my_submitted_leads(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        rows, total = svc.list_my_submitted(db, current_user, limit=limit, offset=offset)
        return LeadListResponse(
            items=[svc.to_summary(r, mask_pii=False) for r in rows],
            total=total,
        )
    finally:
        db.close()


@lead_router.get("/assigned", response_model=LeadListResponse)
def assigned_leads(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        if not svc._has_any_role(
            roles,
            LeadUserRole.SALES_USER,
            LeadUserRole.SALES_MANAGER,
            LeadUserRole.ADMIN,
        ):
            raise HTTPException(status_code=403, detail="Sales role required")
        rows, total = svc.list_assigned(db, current_user, limit=limit, offset=offset)
        return LeadListResponse(
            items=[svc.to_summary(r) for r in rows],
            total=total,
        )
    finally:
        db.close()


@lead_router.get("/me/roles", response_model=LeadMyRolesResponse)
def my_lead_roles(
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        perms = svc.get_user_permissions(roles)
        return LeadMyRolesResponse(
            roles=svc.role_names(roles),
            permissions=LeadPermissions(**perms),
        )
    finally:
        db.close()


@lead_router.get("/stats", response_model=LeadDashboardStats)
def lead_dashboard_stats(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        stats = svc.get_dashboard_stats(
            db, current_user, roles, date_from=date_from, date_to=date_to
        )
        return LeadDashboardStats(**stats)
    finally:
        db.close()


@lead_router.get("/search", response_model=LeadListResponse)
def search_leads(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        rows, total = svc.list_leads(db, current_user, roles, search=q, limit=limit, offset=offset)
        return LeadListResponse(
            items=[
                svc.to_summary(r, mask_pii=_mask_for_user(current_user, r, roles))
                for r in rows
            ],
            total=total,
        )
    finally:
        db.close()


@lead_router.get("/export.csv", response_class=PlainTextResponse)
def export_leads(
    status_filter: Optional[str] = Query(None, alias="status"),
    product_type: Optional[str] = None,
    branch: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        csv_data = svc.export_leads_csv(
            db,
            current_user,
            roles,
            status_filter=status_filter,
            product_type=product_type,
            branch=branch,
            date_from=date_from,
            date_to=date_to,
        )
        return PlainTextResponse(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
        )
    finally:
        db.close()


@lead_router.get("", response_model=LeadListResponse)
def list_leads(
    status_filter: Optional[str] = Query(None, alias="status"),
    product_type: Optional[str] = None,
    branch: Optional[str] = None,
    assigned_to: Optional[str] = None,
    created_by: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        rows, total = svc.list_leads(
            db,
            current_user,
            roles,
            status_filter=status_filter,
            product_type=product_type,
            branch=branch,
            assigned_to=assigned_to,
            created_by=created_by,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        return LeadListResponse(
            items=[
                svc.to_summary(r, mask_pii=_mask_for_user(current_user, r, roles))
                for r in rows
            ],
            total=total,
        )
    finally:
        db.close()


@lead_router.get("/roles", response_model=List[LeadRoleOut])
def list_lead_roles(
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        if not svc._has_any_role(roles, LeadUserRole.ADMIN):
            raise HTTPException(status_code=403, detail="Admin only")
        records = svc.list_roles(db)
        return [
            LeadRoleOut(
                employee_id=r.employee_id,
                role=r.role,
                created_at=r.created_at,
                created_by=r.created_by,
            )
            for r in records
        ]
    finally:
        db.close()


@lead_router.post("/roles", response_model=LeadRoleOut, status_code=status.HTTP_201_CREATED)
def assign_lead_role(
    body: LeadRoleAssignRequest,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        if not svc._has_any_role(roles, LeadUserRole.ADMIN):
            raise HTTPException(status_code=403, detail="Admin only")
        record = svc.assign_role(db, current_user, body.employee_id, body.role)
        return LeadRoleOut(
            employee_id=record.employee_id,
            role=record.role,
            created_at=record.created_at,
            created_by=record.created_by,
        )
    finally:
        db.close()


@lead_router.delete("/roles", status_code=status.HTTP_204_NO_CONTENT)
def revoke_lead_role(
    employee_id: str = Query(..., min_length=1),
    role: LeadUserRole = Query(...),
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        if not svc._has_any_role(roles, LeadUserRole.ADMIN):
            raise HTTPException(status_code=403, detail="Admin only")
        svc.revoke_role(db, current_user, employee_id, role)
    finally:
        db.close()


@lead_router.get("/{lead_reference_no}", response_model=LeadDetailWithPermissions)
def get_lead(
    lead_reference_no: str,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        lead = _lead_or_404(db, lead_reference_no)
        svc.require_lead_access(current_user, lead, roles)
        mask = _mask_for_user(current_user, lead, roles)
        detail = svc.to_detail(lead, mask_pii=mask)
        perms = svc.get_lead_permissions(current_user, lead, roles)
        return LeadDetailWithPermissions(
            **detail.model_dump(),
            permissions=LeadDetailPermissions(**perms),
        )
    finally:
        db.close()


@lead_router.patch("/{lead_reference_no}/status", response_model=LeadDetail)
def update_lead_status(
    lead_reference_no: str,
    body: LeadStatusUpdateRequest,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        lead = _lead_or_404(db, lead_reference_no)
        lead = svc.update_status(db, current_user, lead, roles, body)
        return svc.to_detail(lead)
    finally:
        db.close()


@lead_router.patch("/{lead_reference_no}/assign", response_model=LeadDetail)
def assign_lead(
    lead_reference_no: str,
    body: LeadAssignRequest,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        lead = _lead_or_404(db, lead_reference_no)
        svc.require_lead_access(current_user, lead, roles)
        lead = svc.assign_lead(db, current_user, lead, roles, body)
        return svc.to_detail(lead)
    finally:
        db.close()


@lead_router.post("/{lead_reference_no}/feedback", response_model=LeadFeedbackOut, status_code=201)
def create_feedback(
    lead_reference_no: str,
    body: LeadFeedbackCreateRequest,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        lead = _lead_or_404(db, lead_reference_no)
        entry = svc.add_feedback(db, current_user, lead, roles, body)
        return svc.feedback_to_out(entry)
    finally:
        db.close()


@lead_router.get("/{lead_reference_no}/feedback", response_model=List[LeadFeedbackOut])
def list_feedback(
    lead_reference_no: str,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        lead = _lead_or_404(db, lead_reference_no)
        entries = svc.get_feedback_for_lead(db, current_user, lead, roles)
        return [svc.feedback_to_out(e) for e in entries]
    finally:
        db.close()


@lead_router.get("/{lead_reference_no}/status-history", response_model=List[LeadStatusHistoryOut])
def status_history(
    lead_reference_no: str,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        lead = _lead_or_404(db, lead_reference_no)
        entries = svc.get_status_history(db, current_user, lead, roles)
        return [svc.status_history_to_out(e) for e in entries]
    finally:
        db.close()


@lead_router.post("/{lead_reference_no}/activity", response_model=LeadActivityOut, status_code=201)
def log_activity(
    lead_reference_no: str,
    body: LeadActivityCreateRequest,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        lead = _lead_or_404(db, lead_reference_no)
        entry = svc.add_activity(db, current_user, lead, roles, body)
        return LeadActivityOut(
            id=entry.id,
            activity_type=entry.activity_type,
            activity_details=entry.activity_details,
            performed_by=entry.performed_by,
            created_at=entry.created_at,
        )
    finally:
        db.close()


@lead_router.delete("/{lead_reference_no}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead_reference_no: str,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        roles = _roles(db, current_user)
        lead = _lead_or_404(db, lead_reference_no)
        svc.soft_delete_lead(db, current_user, lead, roles)
    finally:
        db.close()
