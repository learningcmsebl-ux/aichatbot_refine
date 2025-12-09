"""
PostgreSQL database connection and models for conversation memory.
"""

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()
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
            max_overflow=20
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("PostgreSQL database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}")
        raise


async def close_db():
    """Close database connections"""
    global engine
    if engine:
        engine.dispose()
        logger.info("PostgreSQL connections closed")


def get_db() -> Session:
    """Get database session"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Session will be closed by caller


class PostgresChatMemory:
    """PostgreSQL-based chat memory manager"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db or get_db()
        self._own_db = db is None
    
    def add_message(self, session_id: str, role: str, message: str) -> ChatMessage:
        """Add a message to the conversation history"""
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
            self.db.rollback()
            logger.error(f"Error adding message: {e}")
            raise
    
    def get_conversation_history(
        self, 
        session_id: str, 
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """Get conversation history for a session"""
        try:
            query = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    def clear_session(self, session_id: str) -> bool:
        """Clear all messages for a session"""
        try:
            self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).delete()
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error clearing session: {e}")
            return False
    
    def close(self):
        """Close database session"""
        if self.db and self._own_db:
            self.db.close()

