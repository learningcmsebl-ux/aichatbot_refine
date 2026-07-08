"""User-scoped chat session CRUD service."""

from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.postgres import (
    ChatMessage,
    get_db,
    _prepare_message_for_storage,
    _decode_stored_message,
)
from app.models.chat_session import ChatSession

logger = logging.getLogger(__name__)

MAX_TITLE_LEN = 40
MAX_PREVIEW_LEN = 100


@dataclass
class ChatIdentity:
    """
    Authenticated user identity used to own and scope chat history.

    `user_id` is the stable ownership key (AD objectGUID when available, else the
    Windows login). It is always derived from the backend AD token — never from a
    client-supplied field. The remaining fields are stored as metadata only.
    `legacy_user_ids` lists prior keys the same user's history may sit under, so we
    can reconcile ownership after upgrading to the stable AD identifier.
    """

    user_id: str
    ad_object_id: Optional[str] = None
    email: Optional[str] = None
    upn: Optional[str] = None
    username: Optional[str] = None
    legacy_user_ids: List[str] = field(default_factory=list)


def identity_from_employee(employee: Any, fallback_user_id: Optional[str] = None) -> ChatIdentity:
    """Build a ChatIdentity from an authenticated EmployeeUser (or a bare id)."""
    if employee is None:
        uid = (fallback_user_id or "").strip()
        return ChatIdentity(user_id=uid)
    return ChatIdentity(
        user_id=employee.stable_user_id,
        ad_object_id=employee.ad_object_id,
        email=employee.email,
        upn=employee.upn,
        username=employee.username,
        legacy_user_ids=list(employee.legacy_identity_keys),
    )


def _apply_identity_meta(obj: Any, identity: Optional[ChatIdentity]) -> None:
    """Stamp identity metadata columns onto a ChatSession/ChatMessage row."""
    if identity is None:
        return
    if getattr(obj, "ad_object_id", None) is None and identity.ad_object_id:
        obj.ad_object_id = identity.ad_object_id
    if getattr(obj, "user_email", None) is None and identity.email:
        obj.user_email = identity.email
    if getattr(obj, "user_upn", None) is None and identity.upn:
        obj.user_upn = identity.upn
    if getattr(obj, "username", None) is None and identity.username:
        obj.username = identity.username


class SessionOwnershipError(Exception):
    """Raised when a session reference belongs to a different user."""

    def __init__(self, session_reference_no: str, owner_id: str, requested_by: str) -> None:
        self.session_reference_no = session_reference_no
        self.owner_id = owner_id
        self.requested_by = requested_by
        super().__init__(
            f"Session {session_reference_no!r} belongs to {owner_id!r}, not {requested_by!r}"
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_title(text: str) -> str:
    t = text.strip()
    return t[:MAX_TITLE_LEN].rstrip() + ("…" if len(t) > MAX_TITLE_LEN else "")


def _make_preview(text: str) -> str:
    t = text.strip()
    return t[:MAX_PREVIEW_LEN].rstrip() + ("…" if len(t) > MAX_PREVIEW_LEN else "")


def claim_orphan_messages(db: Session, session_reference_no: str, user_id: str) -> int:
    """Stamp user_id on legacy messages that have no owner for this session reference."""
    updated = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_reference_no,
            ChatMessage.user_id.is_(None),
        )
        .update({ChatMessage.user_id: user_id}, synchronize_session=False)
    )
    if updated:
        db.commit()
        logger.info(
            "[SESSION] Claimed %s orphan message(s) for %s on %r",
            updated,
            user_id,
            session_reference_no,
        )
    return updated


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def mint_user_scoped_reference(user_id: str, original_reference: str) -> str:
    """Create a new session reference when the client id is owned by another user."""
    suffix = uuid.uuid4().hex[:12]
    base = (original_reference or "session")[:200]
    return f"{user_id}::{base}::{suffix}"


def _reclaim_legacy_messages(
    db: Session,
    session_reference_no: str,
    user_id: str,
    legacy_user_ids: List[str],
) -> int:
    """Re-key messages owned by a user's prior identity to their stable AD id."""
    if not legacy_user_ids:
        return 0
    updated = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_reference_no,
            ChatMessage.user_id.in_(legacy_user_ids),
        )
        .update({ChatMessage.user_id: user_id}, synchronize_session=False)
    )
    if updated:
        db.commit()
        logger.info(
            "[SESSION] Reclaimed %s legacy-owned message(s) for %s on %r",
            updated,
            user_id,
            session_reference_no,
        )
    return updated


def ensure_session(
    db: Session,
    session_reference_no: str,
    user_id: str,
    identity: Optional[ChatIdentity] = None,
) -> ChatSession:
    """
    Get or create a ChatSession for (reference_no, user_id).

    `user_id` is the stable, AD-derived ownership key. When `identity` is provided
    we stamp metadata columns and reconcile any history that was stored under the
    user's legacy identity (e.g. the Windows login before the AD objectGUID was
    available), so the user keeps access to their prior conversations.
    """
    legacy_ids = list(identity.legacy_user_ids) if identity else []

    sess = (
        db.query(ChatSession)
        .filter(ChatSession.session_reference_no == session_reference_no)
        .first()
    )
    if sess:
        # Allow the owner OR any of the owner's prior identities. Anything else
        # is a different user and must be rejected.
        if sess.user_id != user_id and sess.user_id not in legacy_ids:
            raise SessionOwnershipError(session_reference_no, sess.user_id, user_id)
        # Upgrade a legacy-owned session to the stable key + reclaim its messages.
        if sess.user_id != user_id:
            sess.user_id = user_id
            _reclaim_legacy_messages(db, session_reference_no, user_id, legacy_ids)
        if sess.deleted_at is not None:
            sess.deleted_at = None
        _apply_identity_meta(sess, identity)
        sess.updated_at = _utcnow()
        db.commit()
        db.refresh(sess)
        claim_orphan_messages(db, session_reference_no, user_id)
        return sess

    assert_reference_access(db, session_reference_no, user_id, legacy_user_ids=legacy_ids)

    sess = ChatSession(
        id=uuid.uuid4(),
        session_reference_no=session_reference_no,
        user_id=user_id,
        title="New Chat",
    )
    _apply_identity_meta(sess, identity)
    db.add(sess)
    try:
        db.commit()
        db.refresh(sess)
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_reference_no == session_reference_no,
                ChatSession.deleted_at.is_(None),
            )
            .first()
        )
        if not existing:
            raise
        if existing.user_id != user_id and existing.user_id not in legacy_ids:
            raise SessionOwnershipError(session_reference_no, existing.user_id, user_id)
        return existing

    claim_orphan_messages(db, session_reference_no, user_id)
    _reclaim_legacy_messages(db, session_reference_no, user_id, legacy_ids)
    logger.info("[SESSION] Created session %s for user %s", sess.id, user_id)
    return sess


def touch_session(
    db: Session,
    session: ChatSession,
    first_user_message: Optional[str] = None,
    last_message_preview: Optional[str] = None,
) -> None:
    """Update title (once from first message) and preview."""
    if first_user_message and session.title == "New Chat":
        session.title = _make_title(first_user_message)
    if last_message_preview:
        session.preview = _make_preview(last_message_preview)
    session.updated_at = _utcnow()
    db.commit()


# ---------------------------------------------------------------------------
# Message persistence
# ---------------------------------------------------------------------------

def add_message(
    db: Session,
    session: ChatSession,
    role: str,
    text: str,
    source_module: Optional[str] = None,
) -> ChatMessage:
    """
    Persist one message. Content is redacted of sensitive banking data and
    optionally encrypted at rest before storage. Identity metadata is copied from
    the owning session so every row is self-describing.
    """
    msg = ChatMessage(
        session_id=session.session_reference_no,
        chat_session_id=session.id,
        user_id=session.user_id,
        role=role,
        message=_prepare_message_for_storage(text),
        source_module=source_module,
        ad_object_id=session.ad_object_id,
        user_email=session.user_email,
        user_upn=session.user_upn,
        username=session.username,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _owner_keys(user_id: str, legacy_user_ids: Optional[List[str]] = None) -> List[str]:
    """All identity keys that count as 'this same user' for ownership queries."""
    keys = [user_id]
    for k in legacy_user_ids or []:
        if k and k not in keys:
            keys.append(k)
    return keys


def list_sessions(
    db: Session,
    user_id: str,
    archived: bool = False,
    limit: int = 200,
    legacy_user_ids: Optional[List[str]] = None,
) -> List[ChatSession]:
    q = db.query(ChatSession).filter(
        ChatSession.user_id.in_(_owner_keys(user_id, legacy_user_ids)),
        ChatSession.deleted_at.is_(None),
    )
    if archived:
        q = q.filter(ChatSession.archived_at.isnot(None))
    else:
        q = q.filter(ChatSession.archived_at.is_(None))
    return q.order_by(ChatSession.updated_at.desc()).limit(limit).all()


def search_sessions(
    db: Session,
    user_id: str,
    query: str,
    limit: int = 50,
    legacy_user_ids: Optional[List[str]] = None,
) -> List[ChatSession]:
    pattern = f"%{query.lower()}%"
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id.in_(_owner_keys(user_id, legacy_user_ids)),
            ChatSession.deleted_at.is_(None),
            ChatSession.archived_at.is_(None),
            (
                ChatSession.title.ilike(pattern)
                | ChatSession.preview.ilike(pattern)
            ),
        )
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .all()
    )


def get_session_for_user(
    db: Session,
    session_id: str,
    user_id: str,
    legacy_user_ids: Optional[List[str]] = None,
) -> Optional[ChatSession]:
    """Return session only if owned by the user (or a legacy id) and not deleted."""
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id.in_(_owner_keys(user_id, legacy_user_ids)),
            ChatSession.deleted_at.is_(None),
        )
        .first()
    )


def get_session_by_reference_for_user(
    db: Session,
    session_reference_no: str,
    user_id: str,
) -> Optional[ChatSession]:
    """Return session by client reference only if owned by user."""
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.session_reference_no == session_reference_no,
            ChatSession.user_id == user_id,
            ChatSession.deleted_at.is_(None),
        )
        .first()
    )


def assert_reference_access(
    db: Session,
    session_reference_no: str,
    user_id: str,
    legacy_user_ids: Optional[List[str]] = None,
) -> None:
    """
    Verify the authenticated user may read or mutate messages for
    session_reference_no. Raises SessionOwnershipError when the reference is owned
    by a *different* user.

    `legacy_user_ids` are the caller's own prior identity keys (e.g. Windows login
    before the AD objectGUID was captured); ownership by any of these is treated as
    the same user, so users never lose access to their own history.
    """
    allowed = {user_id, *(legacy_user_ids or [])}

    sess = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_reference_no == session_reference_no,
            ChatSession.deleted_at.is_(None),
        )
        .first()
    )
    if sess:
        if sess.user_id not in allowed:
            raise SessionOwnershipError(session_reference_no, sess.user_id, user_id)
        return

    other_user_message = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_reference_no,
            ChatMessage.user_id.isnot(None),
            ChatMessage.user_id.notin_(allowed),
        )
        .first()
    )
    if other_user_message:
        raise SessionOwnershipError(
            session_reference_no,
            other_user_message.user_id or "",
            user_id,
        )


def get_messages(
    db: Session,
    session: ChatSession,
) -> List[ChatMessage]:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    # Transparently decrypt content before returning to API callers.
    for msg in messages:
        msg.message = _decode_stored_message(msg.message)
    return messages


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def rename_session(db: Session, session: ChatSession, title: str) -> ChatSession:
    session.title = title[:MAX_TITLE_LEN]
    session.updated_at = _utcnow()
    db.commit()
    db.refresh(session)
    return session


def archive_session(db: Session, session: ChatSession) -> ChatSession:
    session.archived_at = _utcnow() if not session.archived_at else None
    session.updated_at = _utcnow()
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session: ChatSession) -> None:
    session.deleted_at = _utcnow()
    session.updated_at = _utcnow()
    db.commit()
