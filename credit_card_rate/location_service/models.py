"""
SQLAlchemy models for location service
Normalized database schema for locations
"""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class Region(Base):
    """Region master data"""
    __tablename__ = "regions"
    
    region_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_code = Column(String(10), unique=True, nullable=False)
    region_name = Column(String(100), nullable=False, index=True)
    country_code = Column(String(10), nullable=False, default="50")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    cities = relationship("City", back_populates="region", cascade="all, delete-orphan")


class City(Base):
    """City master data"""
    __tablename__ = "cities"
    
    city_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_name = Column(String(100), nullable=False, index=True)
    region_id = Column(UUID(as_uuid=True), ForeignKey("regions.region_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    region = relationship("Region", back_populates="cities")
    addresses = relationship("Address", back_populates="city", cascade="all, delete-orphan")
    priority_centers = relationship("PriorityCenter", back_populates="city", cascade="all, delete-orphan")
    
    # Index for faster lookups
    __table_args__ = (
        Index('idx_city_region', 'city_name', 'region_id'),
    )


class Address(Base):
    """Normalized address data"""
    __tablename__ = "addresses"
    
    address_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    street_address = Column(Text, nullable=False)
    zip_code = Column(String(20), nullable=True)
    city_id = Column(UUID(as_uuid=True), ForeignKey("cities.city_id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    city = relationship("City", back_populates="addresses")
    branches = relationship("Branch", back_populates="address", cascade="all, delete-orphan")
    machines = relationship("Machine", back_populates="address", cascade="all, delete-orphan")


class Branch(Base):
    """Branch locations"""
    __tablename__ = "branches"
    
    branch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_code = Column(String(20), unique=True, nullable=False, index=True)
    branch_name = Column(String(200), nullable=False, index=True)
    address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.address_id"), nullable=False, index=True)
    status = Column(String(10), nullable=False, default="A", index=True)
    is_head_office = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    address = relationship("Address", back_populates="branches")
    machines = relationship("Machine", back_populates="branch", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_branch_name', 'branch_name'),
        Index('idx_branch_status', 'status'),
    )


class Machine(Base):
    """ATM/CRM/RTDM locations"""
    __tablename__ = "machines"
    
    machine_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    machine_type = Column(String(10), nullable=False, index=True)  # ATM, CRM, RTDM
    machine_count = Column(Integer, nullable=False, default=1)
    address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.address_id"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.branch_id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    address = relationship("Address", back_populates="machines")
    branch = relationship("Branch", back_populates="machines")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_machine_type', 'machine_type'),
        Index('idx_machine_branch', 'branch_id'),
    )


class PriorityCenter(Base):
    """Priority center cities"""
    __tablename__ = "priority_centers"
    
    priority_center_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id = Column(UUID(as_uuid=True), ForeignKey("cities.city_id"), nullable=False, unique=True, index=True)
    center_name = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    city = relationship("City", back_populates="priority_centers")

