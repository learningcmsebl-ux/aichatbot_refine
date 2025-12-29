"""
Admin Panel API for Fee Engine Management
Provides web interface for viewing and editing card fees
"""

from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
import os
import secrets
import hashlib
from sqlalchemy import create_engine, Column, String, Date, Integer, DECIMAL, Text, DateTime, or_, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import from fee_engine_service
import sys
# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

try:
    from fee_engine_service import (
        CardFeeMaster, get_database_url, SessionLocal, Base
    )
except ImportError:
    # If running from Docker, try different import path
    sys.path.insert(0, '/app')
    from fee_engine_service import (
        CardFeeMaster, get_database_url, SessionLocal, Base
    )

# Define Retail Asset Charge Master model
class RetailAssetChargeMaster(Base):
    __tablename__ = "retail_asset_charge_master"
    
    charge_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    loan_product = Column(String(50), nullable=False)
    loan_product_name = Column(String(200), nullable=False)
    charge_type = Column(String(50), nullable=False)
    charge_description = Column(String(500), nullable=False)
    fee_value = Column(DECIMAL(15, 4), nullable=True)
    fee_unit = Column(String(20), nullable=False)
    fee_basis = Column(String(20), nullable=False)
    tier_1_threshold = Column(DECIMAL(15, 4), nullable=True)
    tier_1_fee_value = Column(DECIMAL(15, 4), nullable=True)
    tier_1_fee_unit = Column(String(20), nullable=True)
    tier_1_max_fee = Column(DECIMAL(15, 4), nullable=True)
    tier_2_threshold = Column(DECIMAL(15, 4), nullable=True)
    tier_2_fee_value = Column(DECIMAL(15, 4), nullable=True)
    tier_2_fee_unit = Column(String(20), nullable=True)
    tier_2_max_fee = Column(DECIMAL(15, 4), nullable=True)
    min_fee_value = Column(DECIMAL(15, 4), nullable=True)
    min_fee_unit = Column(String(20), nullable=True)
    max_fee_value = Column(DECIMAL(15, 4), nullable=True)
    max_fee_unit = Column(String(20), nullable=True)
    condition_type = Column(String(20), nullable=False, default="NONE")
    condition_description = Column(Text, nullable=True)
    employee_fee_value = Column(DECIMAL(15, 4), nullable=True)
    employee_fee_unit = Column(String(20), nullable=True)
    employee_fee_description = Column(String(200), nullable=True)
    original_charge_text = Column(Text, nullable=True)
    note_reference = Column(String(20), nullable=True)
    priority = Column(Integer, nullable=False, default=100)
    status = Column(String(20), nullable=False, default="ACTIVE")
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Security
security = HTTPBasic()

# Admin credentials (should be in environment variables)
def get_admin_username():
    return os.getenv("ADMIN_USERNAME", "admin")

def get_admin_password():
    return os.getenv("ADMIN_PASSWORD", "admin123")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    # Simple hash comparison (in production, use bcrypt)
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

def get_password_hash(password: str) -> str:
    """Hash password"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials"""
    correct_username = get_admin_username()
    correct_password = get_admin_password()
    
    if credentials.username != correct_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    if credentials.password != correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return credentials.username

# FastAPI app
app = FastAPI(
    title="Fee Engine Admin Panel",
    description="Admin interface for managing card fees and rates",
    version="1.0.0"
)

# Mount static files (for frontend)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    # Try alternative path (for Docker)
    static_dir = os.path.join("/app", "admin_panel", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"Static files mounted from: {static_dir}")
else:
    logger.warning(f"Static files directory not found: {static_dir}")

# API Models
class FeeRuleResponse(BaseModel):
    fee_id: str
    effective_from: date
    effective_to: Optional[date]
    charge_type: str
    card_category: str
    card_network: str
    card_product: str
    full_card_name: Optional[str]
    fee_value: Decimal
    fee_unit: str
    fee_basis: str
    min_fee_value: Optional[Decimal]
    min_fee_unit: Optional[str]
    max_fee_value: Optional[Decimal]
    free_entitlement_count: Optional[int]
    condition_type: str
    note_reference: Optional[str]
    priority: int
    status: str
    remarks: Optional[str]
    product_line: str
    created_at: datetime
    updated_at: datetime

class FeeRuleUpdate(BaseModel):
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    charge_type: Optional[str] = None
    card_category: Optional[str] = None
    card_network: Optional[str] = None
    card_product: Optional[str] = None
    full_card_name: Optional[str] = None
    fee_value: Optional[Decimal] = None
    fee_unit: Optional[str] = None
    fee_basis: Optional[str] = None
    min_fee_value: Optional[Decimal] = None
    min_fee_unit: Optional[str] = None
    max_fee_value: Optional[Decimal] = None
    free_entitlement_count: Optional[int] = None
    condition_type: Optional[str] = None
    note_reference: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    remarks: Optional[str] = None
    product_line: Optional[str] = None

class FeeRuleCreate(BaseModel):
    effective_from: date
    effective_to: Optional[date] = None
    charge_type: str
    card_category: str
    card_network: str
    card_product: str
    full_card_name: Optional[str] = None
    fee_value: Decimal
    fee_unit: str
    fee_basis: str
    min_fee_value: Optional[Decimal] = None
    min_fee_unit: Optional[str] = None
    max_fee_value: Optional[Decimal] = None
    free_entitlement_count: Optional[int] = None
    condition_type: str = "NONE"
    note_reference: Optional[str] = None
    priority: int = 100
    status: str = "ACTIVE"
    remarks: Optional[str] = None
    product_line: str = "CREDIT_CARDS"

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def fee_rule_to_dict(rule: CardFeeMaster) -> dict:
    """Convert CardFeeMaster to dict"""
    return {
        "fee_id": str(rule.fee_id),
        "effective_from": rule.effective_from.isoformat() if rule.effective_from else None,
        "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
        "charge_type": rule.charge_type,
        "card_category": rule.card_category,
        "card_network": rule.card_network,
        "card_product": rule.card_product,
        "full_card_name": rule.full_card_name,
        "fee_value": float(rule.fee_value),
        "fee_unit": rule.fee_unit,
        "fee_basis": rule.fee_basis,
        "min_fee_value": float(rule.min_fee_value) if rule.min_fee_value else None,
        "min_fee_unit": rule.min_fee_unit,
        "max_fee_value": float(rule.max_fee_value) if rule.max_fee_value else None,
        "free_entitlement_count": rule.free_entitlement_count,
        "condition_type": rule.condition_type,
        "note_reference": rule.note_reference,
        "priority": rule.priority,
        "status": rule.status,
        "remarks": rule.remarks,
        "product_line": rule.product_line,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }

# Routes
@app.get("/", response_class=HTMLResponse)
async def admin_panel():
    """Serve admin panel HTML"""
    html_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if not os.path.exists(html_file):
        # Try alternative path (for Docker)
        html_file = os.path.join("/app", "admin_panel", "static", "index.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Admin Panel</h1><p>Static files not found. Please check the static directory.</p>")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "fee-engine-admin"}

@app.get("/api/rules", dependencies=[Depends(verify_admin)])
async def list_rules(
    charge_type: Optional[str] = Query(None),
    card_category: Optional[str] = Query(None),
    card_network: Optional[str] = Query(None),
    card_product: Optional[str] = Query(None),
    product_line: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List fee rules with filters and pagination"""
    try:
        query = db.query(CardFeeMaster)
        
        # Apply filters
        if status_filter:
            query = query.filter(CardFeeMaster.status == status_filter.upper())
        else:
            query = query.filter(CardFeeMaster.status == "ACTIVE")
        
        if charge_type:
            query = query.filter(CardFeeMaster.charge_type == charge_type)
        if card_category:
            query = query.filter(
                (CardFeeMaster.card_category == card_category) |
                (CardFeeMaster.card_category == "ANY")
            )
        if card_network:
            query = query.filter(
                (CardFeeMaster.card_network == card_network) |
                (CardFeeMaster.card_network == "ANY")
            )
        if card_product:
            query = query.filter(CardFeeMaster.card_product.ilike(f"%{card_product}%"))
        if product_line:
            query = query.filter(CardFeeMaster.product_line == product_line)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        rules = query.order_by(
            CardFeeMaster.effective_from.desc(),
            CardFeeMaster.priority.desc(),
            CardFeeMaster.card_category,
            CardFeeMaster.card_network,
            CardFeeMaster.card_product
        ).offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "rules": [fee_rule_to_dict(rule) for rule in rules]
        }
    except Exception as e:
        logger.error(f"Error listing rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing rules: {str(e)}")

@app.get("/api/rules/{fee_id}", dependencies=[Depends(verify_admin)])
async def get_rule(fee_id: str, db: Session = Depends(get_db)):
    """Get a specific fee rule by ID"""
    try:
        rule = db.query(CardFeeMaster).filter(CardFeeMaster.fee_id == uuid.UUID(fee_id)).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Fee rule not found")
        return fee_rule_to_dict(rule)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fee ID format")
    except Exception as e:
        logger.error(f"Error getting rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting rule: {str(e)}")

@app.post("/api/rules", dependencies=[Depends(verify_admin)])
async def create_rule(rule_data: FeeRuleCreate, db: Session = Depends(get_db)):
    """Create a new fee rule"""
    try:
        new_rule = CardFeeMaster(
            fee_id=uuid.uuid4(),
            effective_from=rule_data.effective_from,
            effective_to=rule_data.effective_to,
            charge_type=rule_data.charge_type,
            card_category=rule_data.card_category,
            card_network=rule_data.card_network,
            card_product=rule_data.card_product,
            full_card_name=rule_data.full_card_name,
            fee_value=rule_data.fee_value,
            fee_unit=rule_data.fee_unit,
            fee_basis=rule_data.fee_basis,
            min_fee_value=rule_data.min_fee_value,
            min_fee_unit=rule_data.min_fee_unit,
            max_fee_value=rule_data.max_fee_value,
            free_entitlement_count=rule_data.free_entitlement_count,
            condition_type=rule_data.condition_type,
            note_reference=rule_data.note_reference,
            priority=rule_data.priority,
            status=rule_data.status,
            remarks=rule_data.remarks,
            product_line=rule_data.product_line
        )
        db.add(new_rule)
        db.commit()
        db.refresh(new_rule)
        return fee_rule_to_dict(new_rule)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating rule: {str(e)}")

@app.put("/api/rules/{fee_id}", dependencies=[Depends(verify_admin)])
async def update_rule(fee_id: str, rule_data: FeeRuleUpdate, db: Session = Depends(get_db)):
    """Update an existing fee rule"""
    try:
        rule = db.query(CardFeeMaster).filter(CardFeeMaster.fee_id == uuid.UUID(fee_id)).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Fee rule not found")
        
        # Update only provided fields
        update_data = rule_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rule, field, value)
        
        rule.updated_at = datetime.now()
        db.commit()
        db.refresh(rule)
        return fee_rule_to_dict(rule)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fee ID format")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating rule: {str(e)}")

@app.delete("/api/rules/{fee_id}", dependencies=[Depends(verify_admin)])
async def delete_rule(fee_id: str, db: Session = Depends(get_db)):
    """Delete a fee rule (soft delete by setting status to INACTIVE)"""
    try:
        rule = db.query(CardFeeMaster).filter(CardFeeMaster.fee_id == uuid.UUID(fee_id)).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Fee rule not found")
        
        rule.status = "INACTIVE"
        rule.updated_at = datetime.now()
        db.commit()
        return {"message": "Fee rule deactivated successfully", "fee_id": fee_id}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fee ID format")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting rule: {str(e)}")

@app.get("/api/filters", dependencies=[Depends(verify_admin)])
async def get_filters(db: Session = Depends(get_db)):
    """Get available filter options"""
    try:
        # Get unique values for filters
        charge_types = db.query(CardFeeMaster.charge_type).distinct().all()
        card_categories = db.query(CardFeeMaster.card_category).distinct().all()
        card_networks = db.query(CardFeeMaster.card_network).distinct().all()
        card_products = db.query(CardFeeMaster.card_product).distinct().all()
        product_lines = db.query(CardFeeMaster.product_line).distinct().all()
        
        return {
            "charge_types": sorted([ct[0] for ct in charge_types if ct[0]]),
            "card_categories": sorted([cc[0] for cc in card_categories if cc[0]]),
            "card_networks": sorted([cn[0] for cn in card_networks if cn[0]]),
            "card_products": sorted([cp[0] for cp in card_products if cp[0] if cp[0]]),
            "product_lines": sorted([pl[0] for pl in product_lines if pl[0]]),
        }
    except Exception as e:
        logger.error(f"Error getting filters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting filters: {str(e)}")

# Retail Asset Charge Models
class RetailAssetChargeResponse(BaseModel):
    charge_id: str
    effective_from: date
    effective_to: Optional[date]
    loan_product: str
    loan_product_name: str
    charge_type: str
    charge_description: str
    fee_value: Optional[Decimal]
    fee_unit: str
    fee_basis: str
    tier_1_threshold: Optional[Decimal]
    tier_1_fee_value: Optional[Decimal]
    tier_1_fee_unit: Optional[str]
    tier_1_max_fee: Optional[Decimal]
    tier_2_threshold: Optional[Decimal]
    tier_2_fee_value: Optional[Decimal]
    tier_2_fee_unit: Optional[str]
    tier_2_max_fee: Optional[Decimal]
    min_fee_value: Optional[Decimal]
    min_fee_unit: Optional[str]
    max_fee_value: Optional[Decimal]
    max_fee_unit: Optional[str]
    condition_type: str
    condition_description: Optional[str]
    employee_fee_value: Optional[Decimal]
    employee_fee_unit: Optional[str]
    employee_fee_description: Optional[str]
    original_charge_text: Optional[str]
    note_reference: Optional[str]
    priority: int
    status: str
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

class RetailAssetChargeUpdate(BaseModel):
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    loan_product: Optional[str] = None
    loan_product_name: Optional[str] = None
    charge_type: Optional[str] = None
    charge_description: Optional[str] = None
    fee_value: Optional[Decimal] = None
    fee_unit: Optional[str] = None
    fee_basis: Optional[str] = None
    tier_1_threshold: Optional[Decimal] = None
    tier_1_fee_value: Optional[Decimal] = None
    tier_1_fee_unit: Optional[str] = None
    tier_1_max_fee: Optional[Decimal] = None
    tier_2_threshold: Optional[Decimal] = None
    tier_2_fee_value: Optional[Decimal] = None
    tier_2_fee_unit: Optional[str] = None
    tier_2_max_fee: Optional[Decimal] = None
    min_fee_value: Optional[Decimal] = None
    min_fee_unit: Optional[str] = None
    max_fee_value: Optional[Decimal] = None
    max_fee_unit: Optional[str] = None
    condition_type: Optional[str] = None
    condition_description: Optional[str] = None
    employee_fee_value: Optional[Decimal] = None
    employee_fee_unit: Optional[str] = None
    employee_fee_description: Optional[str] = None
    original_charge_text: Optional[str] = None
    note_reference: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    remarks: Optional[str] = None

class RetailAssetChargeCreate(BaseModel):
    effective_from: date
    effective_to: Optional[date] = None
    loan_product: str
    loan_product_name: str
    charge_type: str
    charge_description: str
    fee_value: Optional[Decimal] = None
    fee_unit: str = "TEXT"
    fee_basis: str = "PER_AMOUNT"
    tier_1_threshold: Optional[Decimal] = None
    tier_1_fee_value: Optional[Decimal] = None
    tier_1_fee_unit: Optional[str] = None
    tier_1_max_fee: Optional[Decimal] = None
    tier_2_threshold: Optional[Decimal] = None
    tier_2_fee_value: Optional[Decimal] = None
    tier_2_fee_unit: Optional[str] = None
    tier_2_max_fee: Optional[Decimal] = None
    min_fee_value: Optional[Decimal] = None
    min_fee_unit: Optional[str] = None
    max_fee_value: Optional[Decimal] = None
    max_fee_unit: Optional[str] = None
    condition_type: str = "NONE"
    condition_description: Optional[str] = None
    employee_fee_value: Optional[Decimal] = None
    employee_fee_unit: Optional[str] = None
    employee_fee_description: Optional[str] = None
    original_charge_text: Optional[str] = None
    note_reference: Optional[str] = None
    priority: int = 100
    status: str = "ACTIVE"
    remarks: Optional[str] = None

def retail_asset_charge_to_dict(charge: RetailAssetChargeMaster) -> dict:
    """Convert RetailAssetChargeMaster to dict"""
    return {
        "charge_id": str(charge.charge_id),
        "effective_from": charge.effective_from.isoformat() if charge.effective_from else None,
        "effective_to": charge.effective_to.isoformat() if charge.effective_to else None,
        "loan_product": charge.loan_product,
        "loan_product_name": charge.loan_product_name,
        "charge_type": charge.charge_type,
        "charge_description": charge.charge_description,
        "fee_value": float(charge.fee_value) if charge.fee_value else None,
        "fee_unit": charge.fee_unit,
        "fee_basis": charge.fee_basis,
        "tier_1_threshold": float(charge.tier_1_threshold) if charge.tier_1_threshold else None,
        "tier_1_fee_value": float(charge.tier_1_fee_value) if charge.tier_1_fee_value else None,
        "tier_1_fee_unit": charge.tier_1_fee_unit,
        "tier_1_max_fee": float(charge.tier_1_max_fee) if charge.tier_1_max_fee else None,
        "tier_2_threshold": float(charge.tier_2_threshold) if charge.tier_2_threshold else None,
        "tier_2_fee_value": float(charge.tier_2_fee_value) if charge.tier_2_fee_value else None,
        "tier_2_fee_unit": charge.tier_2_fee_unit,
        "tier_2_max_fee": float(charge.tier_2_max_fee) if charge.tier_2_max_fee else None,
        "min_fee_value": float(charge.min_fee_value) if charge.min_fee_value else None,
        "min_fee_unit": charge.min_fee_unit,
        "max_fee_value": float(charge.max_fee_value) if charge.max_fee_value else None,
        "max_fee_unit": charge.max_fee_unit,
        "condition_type": charge.condition_type,
        "condition_description": charge.condition_description,
        "employee_fee_value": float(charge.employee_fee_value) if charge.employee_fee_value else None,
        "employee_fee_unit": charge.employee_fee_unit,
        "employee_fee_description": charge.employee_fee_description,
        "original_charge_text": charge.original_charge_text,
        "note_reference": charge.note_reference,
        "priority": charge.priority,
        "status": charge.status,
        "remarks": charge.remarks,
        "created_at": charge.created_at.isoformat() if charge.created_at else None,
        "updated_at": charge.updated_at.isoformat() if charge.updated_at else None,
    }

# Retail Asset Charge Endpoints
@app.get("/api/retail-asset-charges", dependencies=[Depends(verify_admin)])
async def list_retail_asset_charges(
    loan_product: Optional[str] = Query(None),
    charge_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List retail asset charges with filters and pagination"""
    try:
        query = db.query(RetailAssetChargeMaster)
        
        # Apply filters
        if status_filter:
            query = query.filter(RetailAssetChargeMaster.status == status_filter.upper())
        else:
            query = query.filter(RetailAssetChargeMaster.status == "ACTIVE")
        
        if loan_product:
            query = query.filter(RetailAssetChargeMaster.loan_product == loan_product)
        if charge_type:
            query = query.filter(RetailAssetChargeMaster.charge_type == charge_type)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        charges = query.order_by(
            RetailAssetChargeMaster.effective_from.desc(),
            RetailAssetChargeMaster.priority.desc(),
            RetailAssetChargeMaster.loan_product,
            RetailAssetChargeMaster.charge_type
        ).offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "charges": [retail_asset_charge_to_dict(charge) for charge in charges]
        }
    except Exception as e:
        logger.error(f"Error listing retail asset charges: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing charges: {str(e)}")

@app.get("/api/retail-asset-charges/{charge_id}", dependencies=[Depends(verify_admin)])
async def get_retail_asset_charge(charge_id: str, db: Session = Depends(get_db)):
    """Get a specific retail asset charge by ID"""
    try:
        charge = db.query(RetailAssetChargeMaster).filter(RetailAssetChargeMaster.charge_id == uuid.UUID(charge_id)).first()
        if not charge:
            raise HTTPException(status_code=404, detail="Retail asset charge not found")
        return retail_asset_charge_to_dict(charge)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid charge ID format")
    except Exception as e:
        logger.error(f"Error getting charge: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting charge: {str(e)}")

@app.post("/api/retail-asset-charges", dependencies=[Depends(verify_admin)])
async def create_retail_asset_charge(charge_data: RetailAssetChargeCreate, db: Session = Depends(get_db)):
    """Create a new retail asset charge"""
    try:
        new_charge = RetailAssetChargeMaster(
            charge_id=uuid.uuid4(),
            effective_from=charge_data.effective_from,
            effective_to=charge_data.effective_to,
            loan_product=charge_data.loan_product,
            loan_product_name=charge_data.loan_product_name,
            charge_type=charge_data.charge_type,
            charge_description=charge_data.charge_description,
            fee_value=charge_data.fee_value,
            fee_unit=charge_data.fee_unit,
            fee_basis=charge_data.fee_basis,
            tier_1_threshold=charge_data.tier_1_threshold,
            tier_1_fee_value=charge_data.tier_1_fee_value,
            tier_1_fee_unit=charge_data.tier_1_fee_unit,
            tier_1_max_fee=charge_data.tier_1_max_fee,
            tier_2_threshold=charge_data.tier_2_threshold,
            tier_2_fee_value=charge_data.tier_2_fee_value,
            tier_2_fee_unit=charge_data.tier_2_fee_unit,
            tier_2_max_fee=charge_data.tier_2_max_fee,
            min_fee_value=charge_data.min_fee_value,
            min_fee_unit=charge_data.min_fee_unit,
            max_fee_value=charge_data.max_fee_value,
            max_fee_unit=charge_data.max_fee_unit,
            condition_type=charge_data.condition_type,
            condition_description=charge_data.condition_description,
            employee_fee_value=charge_data.employee_fee_value,
            employee_fee_unit=charge_data.employee_fee_unit,
            employee_fee_description=charge_data.employee_fee_description,
            original_charge_text=charge_data.original_charge_text,
            note_reference=charge_data.note_reference,
            priority=charge_data.priority,
            status=charge_data.status,
            remarks=charge_data.remarks
        )
        db.add(new_charge)
        db.commit()
        db.refresh(new_charge)
        return retail_asset_charge_to_dict(new_charge)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating charge: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating charge: {str(e)}")

@app.put("/api/retail-asset-charges/{charge_id}", dependencies=[Depends(verify_admin)])
async def update_retail_asset_charge(charge_id: str, charge_data: RetailAssetChargeUpdate, db: Session = Depends(get_db)):
    """Update an existing retail asset charge"""
    try:
        charge = db.query(RetailAssetChargeMaster).filter(RetailAssetChargeMaster.charge_id == uuid.UUID(charge_id)).first()
        if not charge:
            raise HTTPException(status_code=404, detail="Retail asset charge not found")
        
        # Update only provided fields
        update_data = charge_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(charge, field, value)
        
        charge.updated_at = datetime.now()
        db.commit()
        db.refresh(charge)
        return retail_asset_charge_to_dict(charge)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid charge ID format")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating charge: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating charge: {str(e)}")

@app.delete("/api/retail-asset-charges/{charge_id}", dependencies=[Depends(verify_admin)])
async def delete_retail_asset_charge(charge_id: str, db: Session = Depends(get_db)):
    """Delete a retail asset charge (soft delete by setting status to INACTIVE)"""
    try:
        charge = db.query(RetailAssetChargeMaster).filter(RetailAssetChargeMaster.charge_id == uuid.UUID(charge_id)).first()
        if not charge:
            raise HTTPException(status_code=404, detail="Retail asset charge not found")
        
        charge.status = "INACTIVE"
        charge.updated_at = datetime.now()
        db.commit()
        return {"message": "Retail asset charge deactivated successfully", "charge_id": charge_id}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid charge ID format")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting charge: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting charge: {str(e)}")

@app.get("/api/retail-asset-filters", dependencies=[Depends(verify_admin)])
async def get_retail_asset_filters(db: Session = Depends(get_db)):
    """Get available filter options for retail asset charges"""
    try:
        # Get unique values for filters
        loan_products = db.query(RetailAssetChargeMaster.loan_product).distinct().all()
        charge_types = db.query(RetailAssetChargeMaster.charge_type).distinct().all()
        
        return {
            "loan_products": sorted([lp[0] for lp in loan_products if lp[0]]),
            "charge_types": sorted([ct[0] for ct in charge_types if ct[0]]),
        }
    except Exception as e:
        logger.error(f"Error getting filters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting filters: {str(e)}")

# Location Service Integration
# Import location service models
import sys
LOCATION_SERVICE_AVAILABLE = False
Region = City = Address = Branch = Machine = PriorityCenter = None
LocationSessionLocal = None

try:
    # Try to import from location_service directory
    # Check multiple possible paths (for Docker and local development)
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "location_service"),  # From project root
        os.path.join("/app", "location_service"),  # Docker container path
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "location_service"),  # Relative from admin_panel
    ]
    
    location_service_path = None
    for path in possible_paths:
        if os.path.exists(path):
            location_service_path = path
            break
    
    if location_service_path:
        sys.path.insert(0, os.path.dirname(location_service_path))
        from location_service.models import Region, City, Address, Branch, Machine, PriorityCenter
        from location_service.location_service import get_database_url, SessionLocal as LocationSessionLocal
        LOCATION_SERVICE_AVAILABLE = True
        logger.info(f"Location service models loaded successfully from: {location_service_path}")
    else:
        logger.warning(f"Location service path not found. Checked: {possible_paths}")
except ImportError as e:
    logger.warning(f"Location service not available: {e}")
except Exception as e:
    logger.warning(f"Error loading location service: {e}")

def get_location_db():
    """Get location service database session"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    db = LocationSessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/locations", dependencies=[Depends(verify_admin)])
async def get_locations(
    type: Optional[str] = Query(None, description="Location type: branch, atm, crm, rtdm, priority_center, head_office"),
    city: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_location_db)
):
    """Get locations with filters"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        from sqlalchemy import or_, and_
        locations = []
        total = 0
        
        # Query branches
        if not type or type == "branch":
            query = db.query(Branch).join(Address).join(City).join(Region)
            if city:
                query = query.filter(City.city_name.ilike(f"%{city}%"))
            if region:
                query = query.filter(Region.region_name.ilike(f"%{region}%"))
            if search:
                query = query.filter(
                    or_(
                        Branch.branch_name.ilike(f"%{search}%"),
                        Address.street_address.ilike(f"%{search}%")
                    )
                )
            branch_count = query.count()
            branches = query.offset(offset if not type or type == "branch" else 0).limit(limit if not type or type == "branch" else 0).all()
            
            for branch in branches:
                locations.append({
                    "id": str(branch.branch_id),
                    "type": "branch",
                    "name": branch.branch_name,
                    "code": branch.branch_code,
                    "address": {
                        "street": branch.address.street_address,
                        "city": branch.address.city.city_name,
                        "region": branch.address.city.region.region_name,
                        "zip_code": branch.address.zip_code
                    },
                    "status": branch.status
                })
            if not type:
                total += branch_count
            elif type == "branch":
                total = branch_count
        
        # Query head office
        if type == "head_office":
            query = db.query(Branch).join(Address).join(City).join(Region).filter(Branch.is_head_office == True)
            if city:
                query = query.filter(City.city_name.ilike(f"%{city}%"))
            if region:
                query = query.filter(Region.region_name.ilike(f"%{region}%"))
            if search:
                query = query.filter(
                    or_(
                        Branch.branch_name.ilike(f"%{search}%"),
                        Address.street_address.ilike(f"%{search}%")
                    )
                )
            ho_count = query.count()
            head_offices = query.offset(offset).limit(limit).all()
            
            for ho in head_offices:
                locations.append({
                    "id": str(ho.branch_id),
                    "type": "head_office",
                    "name": ho.branch_name,
                    "code": ho.branch_code,
                    "address": {
                        "street": ho.address.street_address,
                        "city": ho.address.city.city_name,
                        "region": ho.address.city.region.region_name,
                        "zip_code": ho.address.zip_code
                    },
                    "status": ho.status
                })
            total = ho_count
        
        # Query machines
        machine_types = []
        if not type:
            machine_types = ["ATM", "CRM", "RTDM"]
        elif type == "atm":
            machine_types = ["ATM"]
        elif type == "crm":
            machine_types = ["CRM"]
        elif type == "rtdm":
            machine_types = ["RTDM"]
        
        if machine_types:
            query = db.query(Machine).join(Address).join(City).join(Region)
            query = query.filter(Machine.machine_type.in_(machine_types))
            if city:
                query = query.filter(City.city_name.ilike(f"%{city}%"))
            if region:
                query = query.filter(Region.region_name.ilike(f"%{region}%"))
            if search:
                query = query.filter(Address.street_address.ilike(f"%{search}%"))
            machine_count = query.count()
            machines = query.offset(offset if type in ["atm", "crm", "rtdm"] else 0).limit(limit if type in ["atm", "crm", "rtdm"] else 0).all()
            
            for machine in machines:
                locations.append({
                    "id": str(machine.machine_id),
                    "type": machine.machine_type.lower(),
                    "name": f"{machine.machine_type} - {machine.address.street_address[:50]}",
                    "code": None,
                    "address": {
                        "street": machine.address.street_address,
                        "city": machine.address.city.city_name,
                        "region": machine.address.city.region.region_name,
                        "zip_code": machine.address.zip_code
                    },
                    "status": None,
                    "machine_type": machine.machine_type,
                    "machine_count": machine.machine_count
                })
            if not type:
                total += machine_count
            elif type in ["atm", "crm", "rtdm"]:
                total = machine_count
        
        # Query priority centers
        if not type or type == "priority_center":
            query = db.query(PriorityCenter).join(City).join(Region)
            if city:
                query = query.filter(City.city_name.ilike(f"%{city}%"))
            if region:
                query = query.filter(Region.region_name.ilike(f"%{region}%"))
            if search:
                query = query.filter(City.city_name.ilike(f"%{search}%"))
            pc_count = query.count()
            priority_centers = query.offset(offset if not type or type == "priority_center" else 0).limit(limit if not type or type == "priority_center" else 0).all()
            
            for pc in priority_centers:
                locations.append({
                    "id": str(pc.priority_center_id),
                    "type": "priority_center",
                    "name": pc.center_name or pc.city.city_name,
                    "code": None,
                    "address": {
                        "street": "",
                        "city": pc.city.city_name,
                        "region": pc.city.region.region_name,
                        "zip_code": None
                    },
                    "status": None
                })
            if not type:
                total += pc_count
            elif type == "priority_center":
                total = pc_count
        
        return {"total": total, "locations": locations}
    
    except Exception as e:
        logger.error(f"Error getting locations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting locations: {str(e)}")

@app.get("/api/locations/stats", dependencies=[Depends(verify_admin)])
async def get_location_stats(db: Session = Depends(get_location_db)):
    """Get location counts by type"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        branch_count = db.query(Branch).count()
        head_office_count = db.query(Branch).filter(Branch.is_head_office == True).count()
        atm_count = db.query(Machine).filter(Machine.machine_type == "ATM").count()
        crm_count = db.query(Machine).filter(Machine.machine_type == "CRM").count()
        rtdm_count = db.query(Machine).filter(Machine.machine_type == "RTDM").count()
        priority_center_count = db.query(PriorityCenter).count()
        
        return {
            "branches": branch_count,
            "head_office": head_office_count,
            "atms": atm_count,
            "crms": crm_count,
            "rtdms": rtdm_count,
            "priority_centers": priority_center_count
        }
    except Exception as e:
        logger.error(f"Error getting location stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting location stats: {str(e)}")

@app.get("/api/locations/filters", dependencies=[Depends(verify_admin)])
async def get_location_filters(db: Session = Depends(get_location_db)):
    """Get filter options (cities, regions)"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        cities = db.query(City.city_name).distinct().order_by(City.city_name).all()
        regions = db.query(Region.region_name).distinct().order_by(Region.region_name).all()
        
        return {
            "cities": [c[0] for c in cities],
            "regions": [r[0] for r in regions]
        }
    except Exception as e:
        logger.error(f"Error getting location filters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting location filters: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ADMIN_PANEL_PORT", "8009"))
    host = os.getenv("ADMIN_PANEL_HOST", "0.0.0.0")
    uvicorn.run("admin_api:app", host=host, port=port, reload=False)

