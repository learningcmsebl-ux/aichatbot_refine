"""
PostgreSQL database connection and models for conversation memory.
"""

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Index, text, or_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# Import analytics models to ensure they're registered with Base
# This ensures analytics tables are created during init_db()

# Import lead models to ensure they're registered with Base
try:
    from app.models.lead import (  # noqa: F401 — lead generation module
        LeadMaster,
        LeadUserRoleRecord,
        LeadStatusHistory,
        LeadFeedback,
        LeadActivityLog,
        LeadAssignmentHistory,
    )
except ImportError:
    pass
try:
    from app.services.analytics import Question, PerformanceMetric, ConversationLog
except ImportError:
    pass
try:
    from app.models.chat_session import ChatSession  # noqa: F401 — registers with Base
except ImportError:
    pass
try:
    from app.models.portal_user import PortalProvisionedUser  # noqa: F401
except ImportError:
    pass
engine = None
SessionLocal = None


def _prepare_message_for_storage(message: str) -> str:
    """
    Redact sensitive banking data and (optionally) encrypt a message before it is
    written to the database. Central choke point so every write path is protected.
    """
    text = message or ""
    try:
        if settings.CHAT_HISTORY_REDACTION_ENABLED:
            from app.services.pii_redaction import redact_sensitive

            text = redact_sensitive(text)
    except Exception as exc:  # never block a chat turn on redaction failure
        logger.warning(f"[SECURITY] Redaction failed, dropping raw content: {exc}")
        text = "[redaction-error]"
    try:
        from app.services.message_crypto import encrypt_text

        return encrypt_text(text)
    except Exception as exc:
        logger.debug(f"[SECURITY] Encryption skipped: {exc}")
        return text


def _decode_stored_message(message: Optional[str]) -> Optional[str]:
    """Transparently decrypt stored message content (no-op for plaintext rows)."""
    try:
        from app.services.message_crypto import decrypt_text

        return decrypt_text(message)
    except Exception:
        return message


class ChatMessage(Base):
    """Chat message model — evoloved to support user-scoped chat sessions."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True, nullable=False)
    role = Column(String(20), nullable=False)          # 'user' | 'assistant' | 'system'
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # New columns added in add_chat_sessions migration
    chat_session_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    source_module = Column(String(100), nullable=True)
    # Owning identity. `user_id` holds the stable AD id (objectGUID) when available,
    # otherwise the Windows login — this is the value all authorization checks use.
    user_id = Column(String(255), nullable=True, index=True)

    # Identity metadata (added in add_chat_user_identity migration). Stored for
    # traceability only; never used for authorization decisions.
    ad_object_id = Column(String(255), nullable=True, index=True)
    user_email = Column(String(320), nullable=True)
    user_upn = Column(String(320), nullable=True)
    username = Column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_session_created", "session_id", "created_at"),
        Index("idx_chat_messages_created_at", "created_at"),
    )


async def init_db():
    """Initialize database connection and create tables"""
    global engine, SessionLocal
    
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=settings.POSTGRES_POOL_SIZE,
            max_overflow=settings.POSTGRES_MAX_OVERFLOW,
            pool_recycle=settings.POSTGRES_POOL_RECYCLE,
            pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
            connect_args={"connect_timeout": 5}
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("PostgreSQL database initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize PostgreSQL: {e}")
        logger.warning("Application will continue but database features will be unavailable")
        # Don't raise - allow app to start without DB
        engine = None
        SessionLocal = None


async def close_db():
    """Close database connections"""
    global engine
    if engine:
        engine.dispose()
        logger.info("PostgreSQL connections closed")


def get_db() -> Optional[Session]:
    """Get database session"""
    if SessionLocal is None:
        logger.warning("Database not initialized. Running in degraded mode without persistence.")
        return None
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        logger.warning(f"Failed to get database session: {e}")
        return None


class PostgresChatMemory:
    """PostgreSQL-based chat memory manager"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db if db is not None else get_db()
        self._own_db = db is None
        self._available = self.db is not None
    
    def add_message(
        self,
        session_id: str,
        role: str,
        message: str,
        user_id: Optional[str] = None,
    ) -> Optional[ChatMessage]:
        """Add a message to the conversation history.

        Message content is redacted of sensitive banking data and optionally
        encrypted at rest before being written.
        """
        if not self._available:
            logger.debug("Database not available, skipping message storage")
            return None
        try:
            stored = _prepare_message_for_storage(message)
            chat_message = ChatMessage(
                session_id=session_id,
                role=role,
                message=stored,
                user_id=user_id,
            )
            self.db.add(chat_message)
            self.db.commit()
            self.db.refresh(chat_message)
            return chat_message
        except Exception as e:
            if self.db:
                self.db.rollback()
            logger.warning(f"Error adding message (continuing without persistence): {e}")
            return None
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> List[ChatMessage]:
        """Get conversation history for a session, optionally scoped to a user."""
        if not self._available:
            logger.debug("Database not available, returning empty history")
            return []
        try:
            query = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            )
            if user_id:
                query = query.filter(
                    or_(ChatMessage.user_id == user_id, ChatMessage.user_id.is_(None))
                )
            query = query.order_by(ChatMessage.created_at.asc())

            # Hard upper bound on how much history is ever loaded for context.
            hard_cap = min(
                max(settings.MAX_CONVERSATION_HISTORY, settings.CHAT_HISTORY_CONTEXT_LIMIT),
                50,
            )
            effective_limit = hard_cap if limit is None else min(limit, hard_cap)
            if effective_limit <= 0:
                return []
            query = query.limit(effective_limit)

            messages = query.all()
            # Transparently decrypt content for callers (LLM context, history API).
            for msg in messages:
                msg.message = _decode_stored_message(msg.message)
            return messages
        except Exception as e:
            logger.warning(f"Error getting conversation history (continuing without history): {e}")
            return []
    
    def clear_session(self, session_id: str) -> bool:
        """Clear all messages for a session"""
        if not self._available:
            logger.debug("Database not available, skipping session clear")
            return False
        try:
            self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).delete()
            self.db.commit()
            return True
        except Exception as e:
            if self.db:
                self.db.rollback()
            logger.warning(f"Error clearing session: {e}")
            return False
    
    def close(self):
        """Close database session"""
        if self.db and self._own_db and self._available:
            try:
                self.db.close()
            except Exception as e:
                logger.warning(f"Error closing database session: {e}")

