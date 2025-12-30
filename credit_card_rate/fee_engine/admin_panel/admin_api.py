"""
Admin Panel API for Fee Engine Management
Provides web interface for viewing and editing card fees
"""

from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import csv
import io
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
import os
import secrets
import hashlib
from sqlalchemy import create_engine, Column, String, Date, Integer, DECIMAL, Text, DateTime, Boolean, or_, and_
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
        CardFeeMaster, SkybankingFeeMaster, RetailAssetChargeMaster, get_database_url, SessionLocal, Base
    )
except ImportError:
    # If running from Docker, try different import path
    sys.path.insert(0, '/app')
    from fee_engine_service import (
        CardFeeMaster, SkybankingFeeMaster, RetailAssetChargeMaster, get_database_url, SessionLocal, Base
    )

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
            return HTMLResponse(
                content=f.read(),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
            )
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

@app.get("/api/export/rules", dependencies=[Depends(verify_admin)])
async def export_card_fees_csv(
    charge_type: Optional[str] = Query(None),
    card_category: Optional[str] = Query(None),
    card_network: Optional[str] = Query(None),
    card_product: Optional[str] = Query(None),
    product_line: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Export card fees to CSV"""
    try:
        query = db.query(CardFeeMaster)
        
        # Apply same filters as list_rules
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
        
        # Get all records (no pagination for export)
        rules = query.order_by(
            CardFeeMaster.effective_from.desc(),
            CardFeeMaster.priority.desc(),
            CardFeeMaster.card_category,
            CardFeeMaster.card_network,
            CardFeeMaster.card_product
        ).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Fee ID", "Effective From", "Effective To", "Charge Type", "Card Category",
            "Card Network", "Card Product", "Full Card Name", "Fee Value", "Fee Unit",
            "Fee Basis", "Min Fee Value", "Min Fee Unit", "Max Fee Value", "Max Fee Unit",
            "Free Entitlement Count", "Condition Type", "Note Reference", "Priority",
            "Status", "Product Line", "Remarks", "Created At", "Updated At"
        ])
        
        # Write data
        for rule in rules:
            writer.writerow([
                str(rule.fee_id),
                rule.effective_from.isoformat() if rule.effective_from else "",
                rule.effective_to.isoformat() if rule.effective_to else "",
                rule.charge_type,
                rule.card_category,
                rule.card_network,
                rule.card_product,
                rule.full_card_name or "",
                float(rule.fee_value) if rule.fee_value else "",
                rule.fee_unit,
                rule.fee_basis,
                float(rule.min_fee_value) if rule.min_fee_value else "",
                rule.min_fee_unit or "",
                float(rule.max_fee_value) if rule.max_fee_value else "",
                rule.free_entitlement_count or "",
                rule.condition_type,
                rule.note_reference or "",
                rule.priority,
                rule.status,
                rule.product_line or "",
                rule.remarks or "",
                rule.created_at.isoformat() if rule.created_at else "",
                rule.updated_at.isoformat() if rule.updated_at else ""
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=card_fees_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting card fees: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error exporting card fees: {str(e)}")

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

@app.get("/api/export/retail-asset-charges", dependencies=[Depends(verify_admin)])
async def export_retail_asset_charges_csv(
    loan_product: Optional[str] = Query(None),
    charge_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Export retail asset charges to CSV"""
    try:
        query = db.query(RetailAssetChargeMaster)
        
        # Apply same filters as list_retail_asset_charges
        if status_filter:
            query = query.filter(RetailAssetChargeMaster.status == status_filter.upper())
        else:
            query = query.filter(RetailAssetChargeMaster.status == "ACTIVE")
        
        if loan_product:
            query = query.filter(RetailAssetChargeMaster.loan_product == loan_product)
        if charge_type:
            query = query.filter(RetailAssetChargeMaster.charge_type == charge_type)
        
        # Get all records (no pagination for export)
        charges = query.order_by(
            RetailAssetChargeMaster.effective_from.desc(),
            RetailAssetChargeMaster.loan_product,
            RetailAssetChargeMaster.charge_type
        ).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Charge ID", "Effective From", "Effective To", "Loan Product", "Loan Product Name",
            "Charge Type", "Charge Description", "Fee Value", "Fee Unit", "Fee Basis",
            "Tier 1 Threshold", "Tier 1 Fee Value", "Tier 1 Fee Unit", "Tier 1 Max Fee",
            "Tier 2 Threshold", "Tier 2 Fee Value", "Tier 2 Fee Unit", "Tier 2 Max Fee",
            "Min Fee Value", "Min Fee Unit", "Max Fee Value", "Max Fee Unit",
            "Condition Type", "Condition Description", "Employee Fee Value", "Employee Fee Unit",
            "Employee Fee Description", "Note Reference", "Status", "Created At", "Updated At"
        ])
        
        # Write data
        for charge in charges:
            writer.writerow([
                str(charge.charge_id),
                charge.effective_from.isoformat() if charge.effective_from else "",
                charge.effective_to.isoformat() if charge.effective_to else "",
                charge.loan_product,
                charge.loan_product_name or "",
                charge.charge_type,
                charge.charge_description or "",
                float(charge.fee_value) if charge.fee_value else "",
                charge.fee_unit,
                charge.fee_basis,
                float(charge.tier_1_threshold) if charge.tier_1_threshold else "",
                float(charge.tier_1_fee_value) if charge.tier_1_fee_value else "",
                charge.tier_1_fee_unit or "",
                float(charge.tier_1_max_fee) if charge.tier_1_max_fee else "",
                float(charge.tier_2_threshold) if charge.tier_2_threshold else "",
                float(charge.tier_2_fee_value) if charge.tier_2_fee_value else "",
                charge.tier_2_fee_unit or "",
                float(charge.tier_2_max_fee) if charge.tier_2_max_fee else "",
                float(charge.min_fee_value) if charge.min_fee_value else "",
                charge.min_fee_unit or "",
                float(charge.max_fee_value) if charge.max_fee_value else "",
                charge.max_fee_unit or "",
                charge.condition_type,
                charge.condition_description or "",
                float(charge.employee_fee_value) if charge.employee_fee_value else "",
                charge.employee_fee_unit or "",
                charge.employee_fee_description or "",
                charge.note_reference or "",
                charge.status,
                charge.created_at.isoformat() if charge.created_at else "",
                charge.updated_at.isoformat() if charge.updated_at else ""
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=retail_asset_charges_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting retail asset charges: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error exporting retail asset charges: {str(e)}")

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

# Get single branch - must be before /api/locations to avoid routing conflicts
@app.get("/api/locations/branches/{branch_id}", dependencies=[Depends(verify_admin)])
async def get_branch(
    branch_id: str,
    db: Session = Depends(get_location_db)
):
    """Get a single branch by ID"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        branch = db.query(Branch).filter(Branch.branch_id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        return {
            "id": str(branch.branch_id),
            "code": branch.branch_code,
            "name": branch.branch_name,
            "address": {
                "street": branch.address.street_address,
                "city": branch.address.city.city_name,
                "region": branch.address.city.region.region_name,
                "zip_code": branch.address.zip_code
            },
            "status": branch.status,
            "is_head_office": branch.is_head_office
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting branch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting branch: {str(e)}")

# Get single machine - must be before /api/locations to avoid routing conflicts
@app.get("/api/locations/machines/{machine_id}", dependencies=[Depends(verify_admin)])
async def get_machine(
    machine_id: str,
    db: Session = Depends(get_location_db)
):
    """Get a single machine by ID"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        from uuid import UUID as UUIDType
        try:
            machine_uuid = UUIDType(machine_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid machine ID format")
        machine = db.query(Machine).filter(Machine.machine_id == machine_uuid).first()
        if not machine:
            raise HTTPException(status_code=404, detail="Machine not found")
        
        return {
            "id": str(machine.machine_id),
            "machine_type": machine.machine_type,
            "machine_count": machine.machine_count,
            "address": {
                "street": machine.address.street_address,
                "city": machine.address.city.city_name,
                "region": machine.address.city.region.region_name,
                "zip_code": machine.address.zip_code
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting machine: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting machine: {str(e)}")

# Get single priority center - must be before /api/locations to avoid routing conflicts
@app.get("/api/locations/priority-centers/{priority_id}", dependencies=[Depends(verify_admin)])
async def get_priority_center(
    priority_id: str,
    db: Session = Depends(get_location_db)
):
    """Get a single priority center by ID"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        priority = db.query(PriorityCenter).filter(PriorityCenter.priority_center_id == priority_id).first()
        if not priority:
            raise HTTPException(status_code=404, detail="Priority center not found")
        
        return {
            "id": str(priority.priority_center_id),
            "name": priority.center_name or priority.city.city_name,
            "address": {
                "city": priority.city.city_name,
                "region": priority.city.region.region_name
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting priority center: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting priority center: {str(e)}")

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
        
        # Filter out "Bangladesh" and ensure "Dhaka" is included
        region_list = [r[0] for r in regions if r[0] and r[0].lower() != 'bangladesh']
        
        # Add Dhaka if not already present
        if 'Dhaka' not in region_list:
            region_list.append('Dhaka')
            region_list.sort()
        
        return {
            "cities": [c[0] for c in cities],
            "regions": region_list
        }
    except Exception as e:
        logger.error(f"Error getting location filters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting location filters: {str(e)}")

# Get single branch
# Pydantic models for location updates
class BranchUpdate(BaseModel):
    branch_code: Optional[str] = None
    branch_name: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    zip_code: Optional[str] = None
    status: Optional[str] = None
    is_head_office: Optional[bool] = None

class MachineUpdate(BaseModel):
    machine_type: Optional[str] = None
    machine_count: Optional[int] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    zip_code: Optional[str] = None

class PriorityCenterUpdate(BaseModel):
    center_name: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None

# Update branch
@app.put("/api/locations/branches/{branch_id}", dependencies=[Depends(verify_admin)])
async def update_branch(
    branch_id: str,
    branch_data: BranchUpdate,
    db: Session = Depends(get_location_db)
):
    """Update a branch"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        branch = db.query(Branch).filter(Branch.branch_id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        # Get or create city and region
        region_name = branch_data.region
        city_name = branch_data.city
        
        if not region_name or not city_name:
            raise HTTPException(status_code=400, detail="Region and city are required")
        
        # Find or create region
        region = db.query(Region).filter(Region.region_name == region_name).first()
        if not region:
            # Create region if it doesn't exist
            region_code = region_name.upper()[:10]
            region = Region(
                region_code=region_code,
                region_name=region_name,
                country_code="BD"
            )
            db.add(region)
            db.flush()
        
        # Find or create city
        city = db.query(City).filter(
            City.city_name == city_name,
            City.region_id == region.region_id
        ).first()
        if not city:
            city = City(
                city_name=city_name,
                region_id=region.region_id
            )
            db.add(city)
            db.flush()
        
        # Find or create address
        street_address = branch_data.street_address or branch.address.street_address
        zip_code = branch_data.zip_code
        
        address = db.query(Address).filter(
            Address.street_address == street_address,
            Address.city_id == city.city_id
        ).first()
        
        if not address:
            address = Address(
                street_address=street_address,
                city_id=city.city_id,
                zip_code=zip_code
            )
            db.add(address)
            db.flush()
        else:
            # Update address if needed
            if zip_code:
                address.zip_code = zip_code
        
        # Update branch
        if branch_data.branch_code:
            branch.branch_code = branch_data.branch_code
        if branch_data.branch_name:
            branch.branch_name = branch_data.branch_name
        branch.address_id = address.address_id
        if branch_data.status:
            branch.status = branch_data.status
        if branch_data.is_head_office is not None:
            branch.is_head_office = branch_data.is_head_office
        
        db.commit()
        
        return {
            "id": str(branch.branch_id),
            "code": branch.branch_code,
            "name": branch.branch_name,
            "message": "Branch updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating branch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating branch: {str(e)}")

# Update machine
@app.put("/api/locations/machines/{machine_id}", dependencies=[Depends(verify_admin)])
async def update_machine(
    machine_id: str,
    machine_data: MachineUpdate,
    db: Session = Depends(get_location_db)
):
    """Update a machine"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        from uuid import UUID as UUIDType
        try:
            machine_uuid = UUIDType(machine_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid machine ID format")
        machine = db.query(Machine).filter(Machine.machine_id == machine_uuid).first()
        if not machine:
            raise HTTPException(status_code=404, detail="Machine not found")
        
        # Get or create city and region
        region_name = machine_data.region
        city_name = machine_data.city
        
        if not region_name or not city_name:
            raise HTTPException(status_code=400, detail="Region and city are required")
        
        # Find or create region
        region = db.query(Region).filter(Region.region_name == region_name).first()
        if not region:
            region_code = region_name.upper()[:10]
            region = Region(
                region_code=region_code,
                region_name=region_name,
                country_code="BD"
            )
            db.add(region)
            db.flush()
        
        # Find or create city
        city = db.query(City).filter(
            City.city_name == city_name,
            City.region_id == region.region_id
        ).first()
        if not city:
            city = City(
                city_name=city_name,
                region_id=region.region_id
            )
            db.add(city)
            db.flush()
        
        # Find or create address
        street_address = machine_data.street_address or machine.address.street_address
        zip_code = machine_data.zip_code
        
        address = db.query(Address).filter(
            Address.street_address == street_address,
            Address.city_id == city.city_id
        ).first()
        
        if not address:
            address = Address(
                street_address=street_address,
                city_id=city.city_id,
                zip_code=zip_code
            )
            db.add(address)
            db.flush()
        else:
            if zip_code:
                address.zip_code = zip_code
        
        # Update machine
        if machine_data.machine_type:
            machine.machine_type = machine_data.machine_type
        if machine_data.machine_count:
            machine.machine_count = machine_data.machine_count
        machine.address_id = address.address_id
        
        db.commit()
        
        return {
            "id": str(machine.machine_id),
            "machine_type": machine.machine_type,
            "message": "Machine updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating machine: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating machine: {str(e)}")

# Update priority center
@app.put("/api/locations/priority-centers/{priority_id}", dependencies=[Depends(verify_admin)])
async def update_priority_center(
    priority_id: str,
    priority_data: PriorityCenterUpdate,
    db: Session = Depends(get_location_db)
):
    """Update a priority center"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        priority = db.query(PriorityCenter).filter(PriorityCenter.priority_center_id == priority_id).first()
        if not priority:
            raise HTTPException(status_code=404, detail="Priority center not found")
        
        # Get or create city and region
        region_name = priority_data.region
        city_name = priority_data.city
        
        if not region_name or not city_name:
            raise HTTPException(status_code=400, detail="Region and city are required")
        
        # Find or create region
        region = db.query(Region).filter(Region.region_name == region_name).first()
        if not region:
            region_code = region_name.upper()[:10]
            region = Region(
                region_code=region_code,
                region_name=region_name,
                country_code="BD"
            )
            db.add(region)
            db.flush()
        
        # Find or create city
        city = db.query(City).filter(
            City.city_name == city_name,
            City.region_id == region.region_id
        ).first()
        if not city:
            city = City(
                city_name=city_name,
                region_id=region.region_id
            )
            db.add(city)
            db.flush()
        
        # Update priority center
        if priority_data.center_name:
            priority.center_name = priority_data.center_name
        priority.city_id = city.city_id
        
        db.commit()
        
        return {
            "id": str(priority.priority_center_id),
            "name": priority.center_name,
            "message": "Priority center updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating priority center: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating priority center: {str(e)}")

# ===== SKYBANKING FEES API =====

# Pydantic models for Skybanking fees
class SkybankingFeeResponse(BaseModel):
    fee_id: str
    effective_from: date
    effective_to: Optional[date]
    charge_type: str
    network: Optional[str]
    product: str
    product_name: str
    fee_amount: Optional[Decimal]
    fee_unit: str
    fee_basis: str
    is_conditional: bool
    condition_description: Optional[str]
    status: str
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

class SkybankingFeeCreate(BaseModel):
    effective_from: date
    effective_to: Optional[date] = None
    charge_type: str
    network: Optional[str] = None
    product: str
    product_name: str
    fee_amount: Optional[Decimal] = None
    fee_unit: str
    fee_basis: str
    is_conditional: bool = False
    condition_description: Optional[str] = None
    status: str = "ACTIVE"
    remarks: Optional[str] = None

class SkybankingFeeUpdate(BaseModel):
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    charge_type: Optional[str] = None
    network: Optional[str] = None
    product: Optional[str] = None
    product_name: Optional[str] = None
    fee_amount: Optional[Decimal] = None
    fee_unit: Optional[str] = None
    fee_basis: Optional[str] = None
    is_conditional: Optional[bool] = None
    condition_description: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None

# Get all Skybanking fees
@app.get("/api/skybanking-fees", dependencies=[Depends(verify_admin)])
async def get_skybanking_fees(
    page: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=1000),
    charge_type: Optional[str] = None,
    product: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all Skybanking fees with pagination and filters"""
    try:
        query = db.query(SkybankingFeeMaster)
        
        # Apply filters
        if charge_type:
            query = query.filter(SkybankingFeeMaster.charge_type.ilike(f"%{charge_type}%"))
        if product:
            query = query.filter(SkybankingFeeMaster.product.ilike(f"%{product}%"))
        if status:
            query = query.filter(SkybankingFeeMaster.status == status)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        fees = query.order_by(
            SkybankingFeeMaster.effective_from.desc(),
            SkybankingFeeMaster.charge_type,
            SkybankingFeeMaster.product_name
        ).offset(page * page_size).limit(page_size).all()
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "fee_id": str(fee.fee_id),
                    "effective_from": fee.effective_from.isoformat() if fee.effective_from else None,
                    "effective_to": fee.effective_to.isoformat() if fee.effective_to else None,
                    "charge_type": fee.charge_type,
                    "network": fee.network,
                    "product": fee.product,
                    "product_name": fee.product_name,
                    "fee_amount": float(fee.fee_amount) if fee.fee_amount else None,
                    "fee_unit": fee.fee_unit,
                    "fee_basis": fee.fee_basis,
                    "is_conditional": fee.is_conditional,
                    "condition_description": fee.condition_description,
                    "status": fee.status,
                    "remarks": fee.remarks,
                    "created_at": fee.created_at.isoformat() if fee.created_at else None,
                    "updated_at": fee.updated_at.isoformat() if fee.updated_at else None
                }
                for fee in fees
            ]
        }
    except Exception as e:
        logger.error(f"Error getting Skybanking fees: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting Skybanking fees: {str(e)}")

# Get single Skybanking fee
@app.get("/api/skybanking-fees/{fee_id}", dependencies=[Depends(verify_admin)])
async def get_skybanking_fee(
    fee_id: str,
    db: Session = Depends(get_db)
):
    """Get a single Skybanking fee by ID"""
    try:
        from uuid import UUID as UUIDType
        try:
            fee_uuid = UUIDType(fee_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid fee ID format")
        fee = db.query(SkybankingFeeMaster).filter(SkybankingFeeMaster.fee_id == fee_uuid).first()
        if not fee:
            raise HTTPException(status_code=404, detail="Skybanking fee not found")
        
        return {
            "fee_id": str(fee.fee_id),
            "effective_from": fee.effective_from.isoformat() if fee.effective_from else None,
            "effective_to": fee.effective_to.isoformat() if fee.effective_to else None,
            "charge_type": fee.charge_type,
            "network": fee.network,
            "product": fee.product,
            "product_name": fee.product_name,
            "fee_amount": float(fee.fee_amount) if fee.fee_amount else None,
            "fee_unit": fee.fee_unit,
            "fee_basis": fee.fee_basis,
            "is_conditional": fee.is_conditional,
            "condition_description": fee.condition_description,
            "status": fee.status,
            "remarks": fee.remarks,
            "created_at": fee.created_at.isoformat() if fee.created_at else None,
            "updated_at": fee.updated_at.isoformat() if fee.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Skybanking fee: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting Skybanking fee: {str(e)}")

# Create Skybanking fee
@app.post("/api/skybanking-fees", dependencies=[Depends(verify_admin)])
async def create_skybanking_fee(
    fee_data: SkybankingFeeCreate,
    db: Session = Depends(get_db)
):
    """Create a new Skybanking fee"""
    try:
        new_fee = SkybankingFeeMaster(
            effective_from=fee_data.effective_from,
            effective_to=fee_data.effective_to,
            charge_type=fee_data.charge_type,
            network=fee_data.network,
            product=fee_data.product,
            product_name=fee_data.product_name,
            fee_amount=fee_data.fee_amount,
            fee_unit=fee_data.fee_unit,
            fee_basis=fee_data.fee_basis,
            is_conditional=fee_data.is_conditional,
            condition_description=fee_data.condition_description,
            status=fee_data.status,
            remarks=fee_data.remarks
        )
        db.add(new_fee)
        db.commit()
        db.refresh(new_fee)
        
        return {
            "fee_id": str(new_fee.fee_id),
            "message": "Skybanking fee created successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating Skybanking fee: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating Skybanking fee: {str(e)}")

# Update Skybanking fee
@app.put("/api/skybanking-fees/{fee_id}", dependencies=[Depends(verify_admin)])
async def update_skybanking_fee(
    fee_id: str,
    fee_data: SkybankingFeeUpdate,
    db: Session = Depends(get_db)
):
    """Update a Skybanking fee"""
    try:
        from uuid import UUID as UUIDType
        try:
            fee_uuid = UUIDType(fee_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid fee ID format")
        fee = db.query(SkybankingFeeMaster).filter(SkybankingFeeMaster.fee_id == fee_uuid).first()
        if not fee:
            raise HTTPException(status_code=404, detail="Skybanking fee not found")
        
        # Update fields
        if fee_data.effective_from is not None:
            fee.effective_from = fee_data.effective_from
        if fee_data.effective_to is not None:
            fee.effective_to = fee_data.effective_to
        if fee_data.charge_type is not None:
            fee.charge_type = fee_data.charge_type
        if fee_data.network is not None:
            fee.network = fee_data.network
        if fee_data.product is not None:
            fee.product = fee_data.product
        if fee_data.product_name is not None:
            fee.product_name = fee_data.product_name
        if fee_data.fee_amount is not None:
            fee.fee_amount = fee_data.fee_amount
        if fee_data.fee_unit is not None:
            fee.fee_unit = fee_data.fee_unit
        if fee_data.fee_basis is not None:
            fee.fee_basis = fee_data.fee_basis
        if fee_data.is_conditional is not None:
            fee.is_conditional = fee_data.is_conditional
        if fee_data.condition_description is not None:
            fee.condition_description = fee_data.condition_description
        if fee_data.status is not None:
            fee.status = fee_data.status
        if fee_data.remarks is not None:
            fee.remarks = fee_data.remarks
        
        db.commit()
        
        return {
            "fee_id": str(fee.fee_id),
            "message": "Skybanking fee updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating Skybanking fee: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating Skybanking fee: {str(e)}")

# Delete Skybanking fee
@app.delete("/api/skybanking-fees/{fee_id}", dependencies=[Depends(verify_admin)])
async def delete_skybanking_fee(
    fee_id: str,
    db: Session = Depends(get_db)
):
    """Delete a Skybanking fee"""
    try:
        from uuid import UUID as UUIDType
        try:
            fee_uuid = UUIDType(fee_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid fee ID format")
        fee = db.query(SkybankingFeeMaster).filter(SkybankingFeeMaster.fee_id == fee_uuid).first()
        if not fee:
            raise HTTPException(status_code=404, detail="Skybanking fee not found")
        
        db.delete(fee)
        db.commit()
        
        return {
            "message": "Skybanking fee deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting Skybanking fee: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting Skybanking fee: {str(e)}")

@app.get("/api/skybanking-fees/export-csv", dependencies=[Depends(verify_admin)])
async def export_skybanking_fees_csv(
    charge_type: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Export Skybanking fees to CSV"""
    try:
        query = db.query(SkybankingFeeMaster)
        
        # Apply filters
        if status:
            query = query.filter(SkybankingFeeMaster.status == status.upper())
        else:
            query = query.filter(SkybankingFeeMaster.status == "ACTIVE")
        
        if charge_type:
            query = query.filter(SkybankingFeeMaster.charge_type == charge_type)
        if product:
            query = query.filter(SkybankingFeeMaster.product == product)
        
        # Get all records (no pagination for export)
        fees = query.order_by(
            SkybankingFeeMaster.effective_from.desc(),
            SkybankingFeeMaster.charge_type,
            SkybankingFeeMaster.product
        ).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Fee ID", "Effective From", "Effective To", "Charge Type", "Network",
            "Product", "Product Name", "Fee Amount", "Fee Unit", "Fee Basis",
            "Is Conditional", "Condition Description", "Status", "Remarks",
            "Created At", "Updated At"
        ])
        
        # Write data
        for fee in fees:
            writer.writerow([
                str(fee.fee_id),
                fee.effective_from.isoformat() if fee.effective_from else "",
                fee.effective_to.isoformat() if fee.effective_to else "",
                fee.charge_type,
                fee.network or "",
                fee.product,
                fee.product_name or "",
                float(fee.fee_amount) if fee.fee_amount else "",
                fee.fee_unit,
                fee.fee_basis,
                "Yes" if fee.is_conditional else "No",
                fee.condition_description or "",
                fee.status,
                fee.remarks or "",
                fee.created_at.isoformat() if fee.created_at else "",
                fee.updated_at.isoformat() if fee.updated_at else ""
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=skybanking_fees_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting Skybanking fees: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error exporting Skybanking fees: {str(e)}")

# Export Branches to CSV
@app.get("/api/export/locations/branches", dependencies=[Depends(verify_admin)])
async def export_branches_csv(
    city: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_location_db)
):
    """Export branches to CSV"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        from sqlalchemy import or_
        query = db.query(Branch).join(Address).join(City).join(Region)
        
        # Apply filters
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
        
        # Get all records (no pagination for export)
        branches = query.order_by(Branch.branch_name).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Branch Code",
            "Branch Name",
            "Street Address",
            "City",
            "Region",
            "ZIP Code",
            "Status",
            "Is Head Office"
        ])
        
        # Write data
        for branch in branches:
            writer.writerow([
                branch.branch_code or "",
                branch.branch_name or "",
                branch.address.street_address if branch.address else "",
                branch.address.city.city_name if branch.address and branch.address.city else "",
                branch.address.city.region.region_name if branch.address and branch.address.city and branch.address.city.region else "",
                branch.address.zip_code if branch.address else "",
                branch.status or "",
                "Yes" if branch.is_head_office else "No"
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=branches_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting branches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error exporting branches: {str(e)}")

# Export Machines (ATM/CRM/RTDM) to CSV
@app.get("/api/export/locations/machines", dependencies=[Depends(verify_admin)])
async def export_machines_csv(
    type: Optional[str] = Query(None, description="Machine type: atm, crm, rtdm"),
    city: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_location_db)
):
    """Export machines (ATM/CRM/RTDM) to CSV"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        machine_types = []
        if not type:
            machine_types = ["ATM", "CRM", "RTDM"]
        elif type == "atm":
            machine_types = ["ATM"]
        elif type == "crm":
            machine_types = ["CRM"]
        elif type == "rtdm":
            machine_types = ["RTDM"]
        
        query = db.query(Machine).join(Address).join(City).join(Region)
        query = query.filter(Machine.machine_type.in_(machine_types))
        
        # Apply filters
        if city:
            query = query.filter(City.city_name.ilike(f"%{city}%"))
        if region:
            query = query.filter(Region.region_name.ilike(f"%{region}%"))
        if search:
            query = query.filter(Address.street_address.ilike(f"%{search}%"))
        
        # Get all records (no pagination for export)
        machines = query.order_by(Machine.machine_type, City.city_name).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Machine Type",
            "Count",
            "Street Address",
            "City",
            "Region",
            "ZIP Code"
        ])
        
        # Write data
        for machine in machines:
            writer.writerow([
                machine.machine_type or "",
                machine.machine_count or 1,
                machine.address.street_address if machine.address else "",
                machine.address.city.city_name if machine.address and machine.address.city else "",
                machine.address.city.region.region_name if machine.address and machine.address.city and machine.address.city.region else "",
                machine.address.zip_code if machine.address else ""
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=machines_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting machines: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error exporting machines: {str(e)}")

# Export Priority Centers to CSV
@app.get("/api/export/locations/priority-centers", dependencies=[Depends(verify_admin)])
async def export_priority_centers_csv(
    city: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_location_db)
):
    """Export priority centers to CSV"""
    if not LOCATION_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Location service not available")
    
    try:
        query = db.query(PriorityCenter).join(City).join(Region)
        
        # Apply filters
        if city:
            query = query.filter(City.city_name.ilike(f"%{city}%"))
        if region:
            query = query.filter(Region.region_name.ilike(f"%{region}%"))
        if search:
            query = query.filter(City.city_name.ilike(f"%{search}%"))
        
        # Get all records (no pagination for export)
        priority_centers = query.order_by(City.city_name, PriorityCenter.center_name).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Center Name",
            "City",
            "Region"
        ])
        
        # Write data
        for pc in priority_centers:
            writer.writerow([
                pc.center_name or pc.city.city_name if pc.city else "",
                pc.city.city_name if pc.city else "",
                pc.city.region.region_name if pc.city and pc.city.region else ""
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=priority_centers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting priority centers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error exporting priority centers: {str(e)}")

# Get filters for Skybanking fees
@app.get("/api/skybanking-filters", dependencies=[Depends(verify_admin)])
async def get_skybanking_filters(db: Session = Depends(get_db)):
    """Get filter options for Skybanking fees"""
    try:
        # Get unique charge types
        charge_types = db.query(SkybankingFeeMaster.charge_type).distinct().all()
        charge_types = sorted([ct[0] for ct in charge_types if ct[0]])
        
        # Get unique products
        products = db.query(SkybankingFeeMaster.product).distinct().all()
        products = sorted([p[0] for p in products if p[0]])
        
        # Get unique networks
        networks = db.query(SkybankingFeeMaster.network).distinct().all()
        networks = sorted([n[0] for n in networks if n[0]])
        
        # Get unique fee units
        fee_units = db.query(SkybankingFeeMaster.fee_unit).distinct().all()
        fee_units = sorted([u[0] for u in fee_units if u[0]])
        
        # Get unique fee basis
        fee_basis = db.query(SkybankingFeeMaster.fee_basis).distinct().all()
        fee_basis = sorted([b[0] for b in fee_basis if b[0]])
        
        return {
            "charge_types": charge_types,
            "products": products,
            "networks": networks,
            "fee_units": fee_units,
            "fee_basis": fee_basis
        }
    except Exception as e:
        logger.error(f"Error getting Skybanking filters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting Skybanking filters: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ADMIN_PANEL_PORT", "8009"))
    host = os.getenv("ADMIN_PANEL_HOST", "0.0.0.0")
    uvicorn.run("admin_api:app", host=host, port=port, reload=False)

