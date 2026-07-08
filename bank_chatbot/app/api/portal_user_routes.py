"""REST API for registering Lead Portal users from Active Directory."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.postgres import get_db
from app.models.auth import EmployeeUser
from app.models.portal_user import (
    DirectoryUserPreview,
    PortalUserListResponse,
    ProvisionPortalUserResponse,
    RegisterPortalUserRequest,
)
from app.services import portal_user_service as svc

portal_user_router = APIRouter(prefix="/portal-users", tags=["Portal Users"])


def _db_or_503() -> Session:
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


@portal_user_router.get("/lookup", response_model=DirectoryUserPreview)
def lookup_employee(
    employee_id: str = Query(..., min_length=1, description="Employee ID, e.g. 2699"),
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        svc.require_lead_admin(db, current_user)
        profile = svc.lookup_employee_profile(employee_id)
        existing = svc.get_provisioned_by_employee_id(db, profile["employee_id"]) or svc.get_provisioned_user(
            db, profile["username"]
        )
        return DirectoryUserPreview(
            username=profile["username"],
            employee_id=profile["employee_id"],
            full_name=profile.get("full_name"),
            email=profile.get("email"),
            department=profile.get("department"),
            designation=profile.get("designation"),
            source=profile.get("source", "active_directory"),
            already_registered=bool(existing and existing.disabled_at is None),
        )
    finally:
        db.close()


@portal_user_router.get("", response_model=PortalUserListResponse)
def list_portal_users(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        svc.require_lead_admin(db, current_user)
        rows, total = svc.list_provisioned_users(db, limit=limit, offset=offset)
        return PortalUserListResponse(
            items=[svc.to_summary(r) for r in rows],
            total=total,
        )
    finally:
        db.close()


@portal_user_router.post("", response_model=ProvisionPortalUserResponse, status_code=status.HTTP_201_CREATED)
def register_portal_user(
    body: RegisterPortalUserRequest,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = _db_or_503()
    try:
        row = svc.register_portal_user(db, current_user, body)
        summary = svc.to_summary(row)
        return ProvisionPortalUserResponse(
            user=summary,
            message=(
                f"{summary.full_name or summary.username} (ID {summary.employee_id}) "
                f"registered as {summary.lead_role}. They can sign in with their existing AD password."
            ),
        )
    finally:
        db.close()
