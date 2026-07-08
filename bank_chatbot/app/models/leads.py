"""Pydantic DTOs for Lead Generation APIs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.lead import LeadLifecycleStatus, LeadProductType, LeadUserRole


class LeadCreateRequest(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=255)
    customer_mobile: Optional[str] = Field(None, max_length=50)
    customer_email: Optional[str] = Field(None, max_length=255)
    preferred_contact_time: Optional[str] = Field(None, max_length=100)
    customer_location: Optional[str] = Field(None, max_length=255)
    preferred_branch: Optional[str] = Field(None, max_length=255)
    product_type: LeadProductType
    remarks: Optional[str] = None
    chat_session_id: Optional[UUID] = None
    created_by_branch: Optional[str] = Field(None, max_length=255)
    created_by_mobile: Optional[str] = Field(None, max_length=50)

    @field_validator("customer_mobile")
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        return v.strip()

    @field_validator("customer_email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        import re
        if not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", v.strip()):
            raise ValueError("Invalid email address")
        return v.strip()


class LeadStatusUpdateRequest(BaseModel):
    status: LeadLifecycleStatus
    note: Optional[str] = None


class LeadAssignRequest(BaseModel):
    assigned_to_user_id: str = Field(..., min_length=1, max_length=255)
    note: Optional[str] = None


class LeadFeedbackCreateRequest(BaseModel):
    feedback_text: str = Field(..., min_length=1)
    feedback_to_employee_id: str = Field(..., min_length=1, max_length=255)


class LeadActivityCreateRequest(BaseModel):
    activity_type: str = Field(..., min_length=1, max_length=100)
    activity_details: Optional[str] = None


class LeadRoleAssignRequest(BaseModel):
    employee_id: str = Field(..., min_length=1, max_length=255)
    role: LeadUserRole


class LeadSummary(BaseModel):
    lead_reference_no: str
    customer_name: str
    customer_mobile: Optional[str] = None
    customer_email: Optional[str] = None
    product_type: str
    product_type_label: str
    status: str
    status_label: str
    preferred_branch: Optional[str] = None
    assigned_to_user_id: Optional[str] = None
    created_by_employee_id: str
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LeadDetail(LeadSummary):
    preferred_contact_time: Optional[str] = None
    customer_location: Optional[str] = None
    remarks: Optional[str] = None
    created_by_department: Optional[str] = None
    created_by_branch: Optional[str] = None
    created_by_email: Optional[str] = None
    closed_at: Optional[datetime] = None
    chat_session_id: Optional[str] = None


class LeadStatusHistoryOut(BaseModel):
    old_status: Optional[str]
    new_status: str
    changed_by: str
    changed_at: datetime
    note: Optional[str] = None


class LeadFeedbackOut(BaseModel):
    id: int
    feedback_text: str
    feedback_by: str
    feedback_to_employee_id: str
    created_at: datetime


class LeadActivityOut(BaseModel):
    id: int
    activity_type: str
    activity_details: Optional[str]
    performed_by: str
    created_at: datetime


class LeadAssignmentOut(BaseModel):
    old_assigned_to: Optional[str]
    new_assigned_to: Optional[str]
    assigned_by: str
    assigned_at: datetime
    note: Optional[str] = None


class LeadRoleOut(BaseModel):
    employee_id: str
    role: str
    created_at: datetime
    created_by: Optional[str] = None


class LeadListResponse(BaseModel):
    items: List[LeadSummary]
    total: int


class LeadCreateResponse(BaseModel):
    lead_reference_no: str
    message: str = "Lead submitted successfully."


class LeadPermissions(BaseModel):
    view_all: bool = False
    assign: bool = False
    export: bool = False
    manage_roles: bool = False
    update_status: bool = False
    view_assigned_queue: bool = False


class LeadMyRolesResponse(BaseModel):
    roles: List[str]
    permissions: LeadPermissions


class LeadDetailPermissions(BaseModel):
    can_view: bool = True
    can_update_status: bool = False
    can_assign: bool = False
    can_add_feedback: bool = False
    can_delete: bool = False


class LeadDashboardStats(BaseModel):
    total: int
    by_status: dict[str, int]
    by_product: dict[str, int]
    pending_assigned: int


class LeadDetailWithPermissions(LeadDetail):
    permissions: LeadDetailPermissions = LeadDetailPermissions()
