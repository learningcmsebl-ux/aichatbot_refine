"""ORM + DTOs for portal user provisioning (AD sales agents)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, Column, DateTime, String
from sqlalchemy.sql import func

from app.database.postgres import Base
from app.models.lead import LeadUserRole


class PortalProvisionedUser(Base):
    __tablename__ = "portal_provisioned_users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, unique=True, index=True)
    employee_id = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    ad_dn = Column(String(512), nullable=True)
    lead_role = Column(String(50), nullable=False, default=LeadUserRole.SALES_USER.value)
    must_change_password = Column(Boolean, nullable=False, default=True)
    provisioned_by = Column(String(255), nullable=False)
    provisioned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    disabled_at = Column(DateTime(timezone=True), nullable=True)


class RegisterPortalUserRequest(BaseModel):
    employee_id: str = Field(..., min_length=1, max_length=64, description="EBL employee ID, e.g. 2699")
    lead_role: LeadUserRole = LeadUserRole.SALES_USER


class DirectoryUserPreview(BaseModel):
    username: str
    employee_id: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    source: str = Field(default="active_directory", description="active_directory")
    already_registered: bool = False


class ProvisionPortalUserRequest(BaseModel):
    """Legacy manual form — prefer RegisterPortalUserRequest."""
    username: str = Field(..., min_length=2, max_length=64)
    employee_id: str = Field(..., min_length=1, max_length=64)
    full_name: str = Field(..., min_length=2, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    lead_role: LeadUserRole = LeadUserRole.SALES_USER


class PortalUserSummary(BaseModel):
    username: str
    employee_id: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    lead_role: str
    must_change_password: bool
    provisioned_by: str
    provisioned_at: datetime
    disabled_at: Optional[datetime] = None


class PortalUserListResponse(BaseModel):
    items: List[PortalUserSummary]
    total: int


class ProvisionPortalUserResponse(BaseModel):
    user: PortalUserSummary
    message: str
    temporary_password_hint: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordResponse(BaseModel):
    message: str = "Password updated successfully."
