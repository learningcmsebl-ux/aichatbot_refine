"""SQLAlchemy models for user-scoped chat sessions."""

import uuid
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.postgres import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_reference_no = Column(String(255), unique=True, nullable=False, index=True)
    # Owning identity: stable AD objectGUID when available, else Windows login.
    # All ownership/authorization checks compare against this column.
    user_id = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="New Chat")
    preview = Column(String(300), nullable=True)

    # Identity metadata for traceability (added in add_chat_user_identity migration).
    ad_object_id = Column(String(255), nullable=True, index=True)
    user_email = Column(String(320), nullable=True)
    user_upn = Column(String(320), nullable=True)
    username = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_chat_sessions_user_id", "user_id", "deleted_at", "updated_at"),
    )
