"""REST API for user-scoped chat sessions."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.database.postgres import get_db
from app.models.auth import EmployeeUser
from app.services import chat_session_service as svc

sessions_router = APIRouter(prefix="/chat/sessions", tags=["Chat Sessions"])

# ---------------------------------------------------------------------------
# Pydantic DTOs
# ---------------------------------------------------------------------------


class SessionOut(BaseModel):
    id: str
    session_reference_no: str
    title: str
    preview: Optional[str]
    created_at: str
    updated_at: str
    archived_at: Optional[str]

    @classmethod
    def from_orm(cls, s) -> "SessionOut":
        return cls(
            id=str(s.id),
            session_reference_no=s.session_reference_no,
            title=s.title,
            preview=s.preview,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
            archived_at=s.archived_at.isoformat() if s.archived_at else None,
        )


class MessageOut(BaseModel):
    id: int
    role: str
    message: str
    source_module: Optional[str]
    created_at: str

    @classmethod
    def from_orm(cls, m) -> "MessageOut":
        return cls(
            id=m.id,
            role=m.role,
            message=m.message,
            source_module=m.source_module,
            created_at=m.created_at.isoformat(),
        )


class SessionWithMessages(SessionOut):
    messages: List[MessageOut] = []


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=40)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session_or_404(session_id: str, current_user: EmployeeUser, db):
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    # Ownership is checked against the AD-authenticated stable id (+ legacy keys),
    # never a client-supplied value, so users can only touch their own sessions.
    sess = svc.get_session_for_user(
        db,
        str(sid),
        current_user.stable_user_id,
        legacy_user_ids=current_user.legacy_identity_keys,
    )
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@sessions_router.get("", response_model=List[SessionOut])
def list_sessions(
    archived: bool = Query(False),
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        sessions = svc.list_sessions(
            db,
            current_user.stable_user_id,
            archived=archived,
            legacy_user_ids=current_user.legacy_identity_keys,
        )
        return [SessionOut.from_orm(s) for s in sessions]
    finally:
        db.close()


@sessions_router.get("/search", response_model=List[SessionOut])
def search_sessions(
    q: str = Query(..., min_length=1),
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        sessions = svc.search_sessions(
            db,
            current_user.stable_user_id,
            q,
            legacy_user_ids=current_user.legacy_identity_keys,
        )
        return [SessionOut.from_orm(s) for s in sessions]
    finally:
        db.close()


@sessions_router.get("/{session_id}", response_model=SessionWithMessages)
def get_session(
    session_id: str,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        sess = _get_session_or_404(session_id, current_user, db)
        messages = svc.get_messages(db, sess)
        result = SessionWithMessages(
            **SessionOut.from_orm(sess).model_dump(),
            messages=[MessageOut.from_orm(m) for m in messages],
        )
        return result
    finally:
        db.close()


@sessions_router.patch("/{session_id}", response_model=SessionOut)
def rename_session(
    session_id: str,
    body: RenameRequest,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        sess = _get_session_or_404(session_id, current_user, db)
        sess = svc.rename_session(db, sess, body.title)
        return SessionOut.from_orm(sess)
    finally:
        db.close()


@sessions_router.post("/{session_id}/archive", response_model=SessionOut)
def toggle_archive(
    session_id: str,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        sess = _get_session_or_404(session_id, current_user, db)
        sess = svc.archive_session(db, sess)
        return SessionOut.from_orm(sess)
    finally:
        db.close()


@sessions_router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    current_user: EmployeeUser = Depends(get_current_user),
):
    db = get_db()
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        sess = _get_session_or_404(session_id, current_user, db)
        svc.delete_session(db, sess)
    finally:
        db.close()
