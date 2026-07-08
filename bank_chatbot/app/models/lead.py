"""
Lead Generation ORM models and shared enums.
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.postgres import Base


class LeadUserRole(str, enum.Enum):
    EMPLOYEE = "employee"
    SALES_USER = "sales_user"
    SALES_MANAGER = "sales_manager"
    ADMIN = "admin"


class LeadLifecycleStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    ASSIGNED = "assigned"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    FOLLOW_UP_REQUIRED = "follow_up_required"
    CONVERTED = "converted"
    NOT_INTERESTED = "not_interested"
    REJECTED = "rejected"
    CLOSED = "closed"


class LeadProductType(str, enum.Enum):
    CREDIT_CARD = "credit_card"
    PERSONAL_LOAN = "personal_loan"
    HOME_LOAN = "home_loan"
    AUTO_LOAN = "auto_loan"
    SME_LOAN = "sme_loan"
    DEPOSIT_ACCOUNT = "deposit_account"
    DPS = "dps"
    FDR = "fdr"
    DEBIT_CARD = "debit_card"
    PAYROLL_BANKING = "payroll_banking"
    OTHER = "other"

    @classmethod
    def label_for(cls, value: str) -> str:
        labels = {
            cls.CREDIT_CARD.value: "Credit Card",
            cls.PERSONAL_LOAN.value: "Personal Loan",
            cls.HOME_LOAN.value: "Home Loan",
            cls.AUTO_LOAN.value: "Auto Loan",
            cls.SME_LOAN.value: "SME Loan",
            cls.DEPOSIT_ACCOUNT.value: "Deposit Account",
            cls.DPS.value: "DPS",
            cls.FDR.value: "FDR",
            cls.DEBIT_CARD.value: "Debit Card",
            cls.PAYROLL_BANKING.value: "Payroll Banking",
            cls.OTHER.value: "Other",
        }
        return labels.get(value, value.replace("_", " ").title())


class LeadMaster(Base):
    __tablename__ = "lead_master"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    lead_reference_no = Column(String(20), unique=True, nullable=False, index=True)

    customer_name = Column(String(255), nullable=False)
    customer_mobile = Column(String(50), nullable=True)
    customer_email = Column(String(255), nullable=True)
    preferred_contact_time = Column(String(100), nullable=True)
    customer_location = Column(String(255), nullable=True)
    preferred_branch = Column(String(255), nullable=True)
    product_type = Column(String(50), nullable=False)
    remarks = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=LeadLifecycleStatus.SUBMITTED.value)

    assigned_to_user_id = Column(String(255), nullable=True)

    created_by_employee_id = Column(String(255), nullable=False)
    created_by_name = Column(String(255), nullable=True)
    created_by_department = Column(String(255), nullable=True)
    created_by_branch = Column(String(255), nullable=True)
    created_by_mobile = Column(String(50), nullable=True)
    created_by_email = Column(String(255), nullable=True)

    chat_session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    status_history = relationship("LeadStatusHistory", back_populates="lead", cascade="all, delete-orphan")
    feedback_entries = relationship("LeadFeedback", back_populates="lead", cascade="all, delete-orphan")
    activity_log = relationship("LeadActivityLog", back_populates="lead", cascade="all, delete-orphan")
    assignment_history = relationship("LeadAssignmentHistory", back_populates="lead", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_lead_master_created_by", "created_by_employee_id", "deleted_at", "created_at"),
        Index("idx_lead_master_assigned", "assigned_to_user_id", "status", "deleted_at"),
        Index("idx_lead_master_status", "status", "deleted_at", "created_at"),
        Index("idx_lead_master_product", "product_type", "deleted_at"),
        Index("idx_lead_master_branch", "preferred_branch", "deleted_at"),
    )


class LeadUserRoleRecord(Base):
    __tablename__ = "lead_user_roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    employee_id = Column(String(255), nullable=False, index=True)
    role = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)

    __table_args__ = (
        Index("uq_lead_user_roles_employee_role", "employee_id", "role", unique=True),
    )


class LeadStatusHistory(Base):
    __tablename__ = "lead_status_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    lead_id = Column(BigInteger, ForeignKey("lead_master.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(String(255), nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    note = Column(Text, nullable=True)

    lead = relationship("LeadMaster", back_populates="status_history")


class LeadFeedback(Base):
    __tablename__ = "lead_feedback"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    lead_id = Column(BigInteger, ForeignKey("lead_master.id", ondelete="CASCADE"), nullable=False, index=True)
    feedback_text = Column(Text, nullable=False)
    feedback_by = Column(String(255), nullable=False)
    feedback_to_employee_id = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    lead = relationship("LeadMaster", back_populates="feedback_entries")


class LeadActivityLog(Base):
    __tablename__ = "lead_activity_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    lead_id = Column(BigInteger, ForeignKey("lead_master.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_type = Column(String(100), nullable=False)
    activity_details = Column(Text, nullable=True)
    performed_by = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    lead = relationship("LeadMaster", back_populates="activity_log")


class LeadAssignmentHistory(Base):
    __tablename__ = "lead_assignment_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    lead_id = Column(BigInteger, ForeignKey("lead_master.id", ondelete="CASCADE"), nullable=False, index=True)
    old_assigned_to = Column(String(255), nullable=True)
    new_assigned_to = Column(String(255), nullable=True)
    assigned_by = Column(String(255), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    note = Column(Text, nullable=True)

    lead = relationship("LeadMaster", back_populates="assignment_history")


def format_lead_reference_no(sequence_value: int) -> str:
    """Format sequence value as LD-000123."""
    return f"LD-{sequence_value:06d}"
