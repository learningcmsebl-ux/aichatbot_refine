"""
PostgreSQL database connection and models for conversation memory.
"""

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Index, text
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
# This ensures lead tables are created during init_db()
try:
    from app.database.leads import Lead
except ImportError:
    pass  # Leads module may not be available
try:
    from app.services.analytics import Question, PerformanceMetric, ConversationLog
except ImportError:
    # Analytics module not available - tables won't be created
    pass
engine = None
SessionLocal = None


class ChatMessage(Base):
    """Chat message model for storing conversation history"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Index for faster queries
    __table_args__ = (
        Index('idx_session_created', 'session_id', 'created_at'),
    )


async def init_db():
    """Initialize database connection and create tables"""
    global engine, SessionLocal
    
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"connect_timeout": 5}
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
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
    
    def add_message(self, session_id: str, role: str, message: str) -> Optional[ChatMessage]:
        """Add a message to the conversation history"""
        if not self._available:
            logger.debug("Database not available, skipping message storage")
            return None
        try:
            chat_message = ChatMessage(
                session_id=session_id,
                role=role,
                message=message
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
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """Get conversation history for a session"""
        if not self._available:
            logger.debug("Database not available, returning empty history")
            return []
        try:
            query = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
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

