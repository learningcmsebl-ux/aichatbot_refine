"""
Lead generation database models and manager for storing customer leads.
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Enum as SQLEnum, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any
import enum
import logging

from app.database.postgres import Base, get_db
from app.core.config import settings

logger = logging.getLogger(__name__)


class LeadStatus(enum.Enum):
    """Lead status enumeration"""
    PENDING = "pending"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    REJECTED = "rejected"


class LeadType(enum.Enum):
    """Lead type enumeration"""
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    OTHER = "other"


class Lead(Base):
    """Lead model for storing customer lead information"""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True, nullable=False)
    
    # Lead Type
    lead_type = Column(SQLEnum(LeadType), nullable=False)
    
    # Customer Information
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    date_of_birth = Column(String(50), nullable=True)
    
    # Additional Information (stored as JSON for flexibility)
    additional_info = Column(JSON, nullable=True)  # For storing answers to custom questions
    
    # Lead Status
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.PENDING, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    notes = Column(Text, nullable=True)  # For internal team notes
    
    # Indexes for faster queries
    __table_args__ = (
        Index('idx_lead_status', 'status'),
        Index('idx_lead_type', 'lead_type'),
        Index('idx_lead_created', 'created_at'),
    )


class LeadManager:
    """Manager for lead operations"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db if db is not None else get_db()
        self._own_db = db is None
        self._available = self.db is not None
    
    def create_lead(
        self,
        session_id: str,
        lead_type: LeadType,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> Optional[Lead]:
        """Create a new lead"""
        if not self._available:
            logger.warning("Database not available, cannot create lead")
            return None
        
        try:
            lead = Lead(
                session_id=session_id,
                lead_type=lead_type,
                full_name=full_name,
                email=email,
                phone=phone,
                date_of_birth=date_of_birth,
                additional_info=additional_info or {},
                notes=notes,
                status=LeadStatus.PENDING
            )
            self.db.add(lead)
            self.db.commit()
            self.db.refresh(lead)
            logger.info(f"Created lead {lead.id} for session {session_id}")
            return lead
        except Exception as e:
            if self.db:
                self.db.rollback()
            logger.error(f"Error creating lead: {e}")
            return None
    
    def update_lead(
        self,
        lead_id: int,
        **kwargs
    ) -> Optional[Lead]:
        """Update an existing lead"""
        if not self._available:
            return None
        
        try:
            lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                return None
            
            for key, value in kwargs.items():
                if hasattr(lead, key):
                    setattr(lead, key, value)
            
            self.db.commit()
            self.db.refresh(lead)
            return lead
        except Exception as e:
            if self.db:
                self.db.rollback()
            logger.error(f"Error updating lead: {e}")
            return None
    
    def get_leads(
        self,
        status: Optional[LeadStatus] = None,
        lead_type: Optional[LeadType] = None,
        limit: int = 100
    ) -> List[Lead]:
        """Get leads with optional filters"""
        if not self._available:
            return []
        
        try:
            query = self.db.query(Lead)
            
            if status:
                query = query.filter(Lead.status == status)
            if lead_type:
                query = query.filter(Lead.lead_type == lead_type)
            
            return query.order_by(Lead.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting leads: {e}")
            return []
    
    def get_lead_by_session(self, session_id: str) -> Optional[Lead]:
        """Get the most recent lead for a session"""
        if not self._available:
            return None
        
        try:
            return self.db.query(Lead).filter(
                Lead.session_id == session_id
            ).order_by(Lead.created_at.desc()).first()
        except Exception as e:
            logger.error(f"Error getting lead by session: {e}")
            return None
    
    def close(self):
        """Close database session"""
        if self.db and self._own_db and self._available:
            try:
                self.db.close()
            except Exception as e:
                logger.warning(f"Error closing database session: {e}")

