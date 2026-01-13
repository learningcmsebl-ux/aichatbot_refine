"""
Fee Engine Microservice
Bank-grade, deterministic fee calculation using single master table design.
Effective from 01st January, 2026.
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import os
from sqlalchemy import create_engine, Column, String, Date, Integer, DECIMAL, Text, DateTime, Boolean, or_, and_, case
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
def get_database_url():
    """Construct database URL from environment variables"""
    # Try FEE_ENGINE_DB_URL first
    url = os.getenv("FEE_ENGINE_DB_URL")
    if url:
        return url
    
    # Try POSTGRES_DB_URL
    url = os.getenv("POSTGRES_DB_URL")
    if url:
        return url
    
    # Construct from individual variables
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'postgres')
    
    # URL encode password if it contains special characters
    from urllib.parse import quote_plus
    password_encoded = quote_plus(password) if password else ''
    
    return f"postgresql://{user}:{password_encoded}@{host}:{port}/{db}"

DATABASE_URL = get_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ENUMs
class CardCategory(str):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    PREPAID = "PREPAID"
    ANY = "ANY"

class CardNetwork(str):
    VISA = "VISA"
    MASTERCARD = "MASTERCARD"
    DINERS = "DINERS"
    UNIONPAY = "UNIONPAY"
    FX = "FX"
    TAKAPAY = "TAKAPAY"
    ANY = "ANY"

class FeeUnit(str):
    BDT = "BDT"
    USD = "USD"
    PERCENT = "PERCENT"
    COUNT = "COUNT"
    TEXT = "TEXT"

class FeeBasis(str):
    PER_TXN = "PER_TXN"
    PER_YEAR = "PER_YEAR"
    PER_MONTH = "PER_MONTH"
    PER_VISIT = "PER_VISIT"
    ON_OUTSTANDING = "ON_OUTSTANDING"

class ConditionType(str):
    NONE = "NONE"
    WHICHEVER_HIGHER = "WHICHEVER_HIGHER"
    FREE_UPTO_N = "FREE_UPTO_N"
    NOTE_BASED = "NOTE_BASED"

class Status(str):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

# Database Model
class CardFeeMaster(Base):
    __tablename__ = "card_fee_master"
    
    fee_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    charge_type = Column(String(255), nullable=False)
    card_category = Column(String(20), nullable=False)
    card_network = Column(String(20), nullable=False)
    card_product = Column(String(100), nullable=False)
    full_card_name = Column(String(200), nullable=True)
    fee_value = Column(DECIMAL(15, 4), nullable=False)
    fee_unit = Column(String(20), nullable=False)
    fee_basis = Column(String(20), nullable=False)
    min_fee_value = Column(DECIMAL(15, 4), nullable=True)
    min_fee_unit = Column(String(20), nullable=True)
    max_fee_value = Column(DECIMAL(15, 4), nullable=True)
    free_entitlement_count = Column(Integer, nullable=True)
    condition_type = Column(String(20), nullable=False, default="NONE")
    note_reference = Column(String(20), nullable=True)
    # Authoritative, non-hallucination fields
    note_number = Column(Integer, nullable=True)
    answer_text = Column(Text, nullable=True)
    priority = Column(Integer, nullable=False, default=100)
    status = Column(String(20), nullable=False, default="ACTIVE")
    remarks = Column(Text, nullable=True)
    product_line = Column(String(50), nullable=False, default="CREDIT_CARDS")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Retail Asset Charge Model
class RetailAssetChargeMaster(Base):
    __tablename__ = "retail_asset_charge_master_v2"
    
    charge_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    loan_product = Column(String(50), nullable=False)
    loan_product_name = Column(String(200), nullable=True)
    charge_type = Column(String(50), nullable=False)
    charge_context = Column(String(50), nullable=False, default="GENERAL")  # Context field (not used for lookups)
    charge_title = Column(String(200), nullable=False)  # NEW: short label for UI
    charge_description = Column(String(500), nullable=True)  # Changed: nullable, longer description
    fee_value = Column(DECIMAL(15, 4), nullable=True)
    fee_unit = Column(String(20), nullable=False)
    fee_basis = Column(String(20), nullable=False)
    # Tier fields renamed for clarity (v2 structure)
    tier_1_threshold_amount = Column(DECIMAL(15, 4), nullable=True)  # Renamed from tier_1_threshold
    tier_1_threshold_currency = Column(String(20), nullable=True)  # NEW: currency for threshold
    tier_1_rate_value = Column(DECIMAL(15, 4), nullable=True)  # Renamed from tier_1_fee_value
    tier_1_rate_unit = Column(String(20), nullable=True)  # Renamed from tier_1_fee_unit
    tier_1_max_fee_value = Column(DECIMAL(15, 4), nullable=True)  # Renamed from tier_1_max_fee
    tier_1_max_fee_currency = Column(String(20), nullable=True)  # NEW: currency for max fee
    tier_2_threshold_amount = Column(DECIMAL(15, 4), nullable=True)  # Renamed from tier_2_threshold
    tier_2_threshold_currency = Column(String(20), nullable=True)  # NEW: currency for threshold
    tier_2_rate_value = Column(DECIMAL(15, 4), nullable=True)  # Renamed from tier_2_fee_value
    tier_2_rate_unit = Column(String(20), nullable=True)  # Renamed from tier_2_fee_unit
    tier_2_max_fee_value = Column(DECIMAL(15, 4), nullable=True)  # Renamed from tier_2_max_fee
    tier_2_max_fee_currency = Column(String(20), nullable=True)  # NEW: currency for max fee
    min_fee_value = Column(DECIMAL(15, 4), nullable=True)
    min_fee_currency = Column(String(20), nullable=True)  # Renamed from min_fee_unit (currency only)
    max_fee_value = Column(DECIMAL(15, 4), nullable=True)
    max_fee_currency = Column(String(20), nullable=True)  # Renamed from max_fee_unit (currency only)
    condition_type = Column(String(20), nullable=False, default="NONE")
    condition_description = Column(Text, nullable=True)
    employee_fee_value = Column(DECIMAL(15, 4), nullable=True)
    employee_fee_unit = Column(String(20), nullable=True)
    employee_fee_description = Column(String(200), nullable=True)
    category_a_fee_value = Column(DECIMAL(15, 4), nullable=True)
    category_a_fee_unit = Column(String(20), nullable=True)
    category_b_fee_value = Column(DECIMAL(15, 4), nullable=True)
    category_b_fee_unit = Column(String(20), nullable=True)
    category_c_fee_value = Column(DECIMAL(15, 4), nullable=True)
    category_c_fee_unit = Column(String(20), nullable=True)
    original_charge_text = Column(Text, nullable=True)
    # Anti-hallucination fields (authoritative text + structured parsing output)
    fee_text = Column(Text, nullable=True)
    fee_rate_value = Column(DECIMAL(15, 4), nullable=True)
    fee_rate_unit = Column(String(20), nullable=True)
    fee_amount_value = Column(DECIMAL(15, 4), nullable=True)
    fee_amount_currency = Column(String(20), nullable=True)
    fee_period = Column(String(20), nullable=True)
    fee_applies_to = Column(String(30), nullable=True)
    answer_text = Column(Text, nullable=True)
    answer_source = Column(String(20), nullable=False, default="SCHEDULE")
    parse_status = Column(String(20), nullable=False, default="UNPARSED")
    parsed_from = Column(String(20), nullable=True)
    parsed_at = Column(DateTime, nullable=True)
    note_reference = Column(String(50), nullable=True)  # Increased length
    priority = Column(Integer, nullable=False, default=100)
    status = Column(String(20), nullable=False, default="ACTIVE")
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    # NEW: Audit fields
    created_by = Column(String(50), nullable=True)
    updated_by = Column(String(50), nullable=True)
    approved_by = Column(String(50), nullable=True)
    approved_at = Column(DateTime, nullable=True)

# Skybanking Fee Model
class SkybankingFeeMaster(Base):
    __tablename__ = "skybanking_fee_master"
    
    fee_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    charge_type = Column(String(100), nullable=False)
    network = Column(String(50), nullable=True)
    product = Column(String(50), nullable=False)
    product_name = Column(String(200), nullable=False)
    fee_amount = Column(DECIMAL(15, 4), nullable=True)
    fee_unit = Column(String(20), nullable=False)
    fee_basis = Column(String(50), nullable=False)
    is_conditional = Column(Boolean, nullable=False, default=False)
    condition_description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="ACTIVE")
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# API Models
class FeeCalculationRequest(BaseModel):
    as_of_date: date = Field(..., description="Date for fee calculation")
    charge_type: str = Field(..., description="Charge type (e.g., CASH_WITHDRAWAL_EBL_ATM)")
    card_category: Literal["CREDIT", "DEBIT", "PREPAID"] = Field(..., description="Card category")
    card_network: str = Field(..., description="Card network (VISA, Mastercard, Platinum/Titanium, etc.)")
    card_product: Optional[str] = Field(None, description="Card product (e.g., Platinum, Classic). Can be None for Platinum/Titanium debit cards.")
    amount: Optional[Decimal] = Field(None, description="Transaction amount (for percentage-based fees)")
    currency: Literal["BDT", "USD"] = Field("BDT", description="Currency")
    usage_index: Optional[int] = Field(None, description="Usage index (for free entitlement logic, e.g., 1st, 2nd, 3rd)")
    outstanding_balance: Optional[Decimal] = Field(None, description="Outstanding balance (for ON_OUTSTANDING basis)")
    product_line: Optional[str] = Field(None, description="Product line: CREDIT_CARDS, SKYBANKING, PRIORITY_BANKING, RETAIL_ASSETS, or None (auto-detect)")

class FeeCalculationResponse(BaseModel):
    status: Literal[
        "CALCULATED",
        "REQUIRES_NOTE_RESOLUTION",
        "NO_RULE_FOUND",
        "FX_RATE_REQUIRED",
        "NEEDS_DISAMBIGUATION",
    ]
    fee_amount: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    fee_basis: Optional[str] = None
    rule_id: Optional[str] = None
    note_reference: Optional[str] = None
    answer_text: Optional[str] = None
    message: Optional[str] = None
    remarks: Optional[str] = None
    charge_type: Optional[str] = None  # Include charge_type in response for better context
    options: Optional[List[Dict[str, Any]]] = None  # For disambiguation (e.g., card products)

# Retail Asset Charges API Models
class RetailAssetChargeRequest(BaseModel):
    as_of_date: date = Field(..., description="Date for charge lookup")
    loan_product: Optional[str] = Field(None, description="Loan product (e.g., FAST_CASH_OD)")
    charge_type: Optional[str] = Field(None, description="Charge type (e.g., PROCESSING_FEE)")
    description_keywords: Optional[List[str]] = Field(None, description="Keywords to match in charge_description (e.g., ['on limit', 'enhancement'])")
    query: Optional[str] = Field(None, description="Original user query (for logging/display only, not used for filtering)")

class RetailAssetChargeResponse(BaseModel):
    status: Literal["FOUND", "NO_RULE_FOUND", "REQUIRES_NOTE_RESOLUTION", "NEEDS_DISAMBIGUATION"]
    charges: List[Dict[str, Any]] = []
    message: Optional[str] = None

# Skybanking Fee API Models
class SkybankingFeeRequest(BaseModel):
    as_of_date: date = Field(..., description="Date for fee lookup")
    charge_type: Optional[str] = Field(None, description="Charge type")
    product: Optional[str] = Field(None, description="Product (e.g., Skybanking)")
    network: Optional[str] = Field(None, description="Network (e.g., VISA)")

class SkybankingFeeResponse(BaseModel):
    status: Literal["FOUND", "NO_RULE_FOUND", "REQUIRES_NOTE_RESOLUTION"]
    fees: List[Dict[str, Any]] = []
    message: Optional[str] = None

# Unified Fee Query Models
class UnifiedFeeRequest(BaseModel):
    product_line: Literal["CREDIT_CARDS", "RETAIL_ASSETS", "SKYBANKING"] = Field(..., description="Product line")
    as_of_date: date = Field(..., description="Date for fee lookup")
    charge_type: Optional[str] = Field(None, description="Charge type")
    # Card-specific fields
    card_category: Optional[Literal["CREDIT", "DEBIT", "PREPAID"]] = None
    card_network: Optional[str] = None
    card_product: Optional[str] = None
    # Retail asset-specific fields
    loan_product: Optional[str] = None
    description_keywords: Optional[List[str]] = None
    query: Optional[str] = Field(None, description="Original user query (for logging/display only, not used for filtering)")
    # Skybanking-specific fields
    product: Optional[str] = None
    network: Optional[str] = None

class UnifiedFeeResponse(BaseModel):
    product_line: str
    status: Literal["FOUND", "NO_RULE_FOUND", "REQUIRES_NOTE_RESOLUTION", "CALCULATED"]
    data: List[Dict[str, Any]] = []
    message: Optional[str] = None

# FastAPI app
app = FastAPI(
    title="Fee Engine Service",
    description="Bank-grade fee calculation microservice using single master table",
    version="1.0.0"
)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """Get database session (non-generator version)"""
    return SessionLocal()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        db = get_db_session()
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "healthy", "service": "fee-engine"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/fees/calculate", response_model=FeeCalculationResponse)
async def calculate_fee(request: FeeCalculationRequest):
    """
    Calculate applicable fee for a card-related event.
    
    Implements:
    - Rule selection (matching card attributes, effective dates, priority)
    - "Whichever higher" logic
    - Free entitlement logic
    - Mixed currency logic
    - Note-based logic
    """
    # Normalize incoming network to canonical DB values.
    # DB is expected to contain: VISA, MASTERCARD, DINERS, UNIONPAY, TAKAPAY (plus ANY in some legacy imports).
    rn = (request.card_network or "").strip()
    rn_upper = rn.upper()
    if "UNIONPAY" in rn_upper or "UNION PAY" in rn_upper:
        request.card_network = "UNIONPAY"
    elif "DINERS" in rn_upper:
        request.card_network = "DINERS"
    elif "TAKAPAY" in rn_upper or "TAKA PAY" in rn_upper:
        request.card_network = "TAKAPAY"
    elif "MASTER" in rn_upper:
        request.card_network = "MASTERCARD"
    elif "VISA" in rn_upper or rn_upper in ["FX", "FX CREDIT", "PLATINUM/TITANIUM", "VISA/MASTERCARD"]:
        # Keep within canonical set (no FX / Platinum-Titanium pseudo-networks)
        request.card_network = "VISA"
    else:
        # Default to VISA if unknown/empty
        request.card_network = "VISA"

    db = get_db_session()
    
    try:
        # 4.1 Rule Selection
        # Match rows where:
        # - effective_from ≤ as_of_date < effective_to (or effective_to is NULL)
        # - charge_type matches
        # - product_line matches (if provided) or defaults to CREDIT_CARDS
        # - card attributes match or are ANY
        # - status = ACTIVE
        # - highest priority wins
        
        # Determine product_line (use provided or default to CREDIT_CARDS)
        product_line = request.product_line if hasattr(request, 'product_line') and request.product_line else "CREDIT_CARDS"
        
        # First, try exact match only (canonical networks + ANY fallback).
        network_filter = (
            (func.upper(CardFeeMaster.card_network) == func.upper(request.card_network)) |
            (CardFeeMaster.card_network == "ANY")
        )
        exact_match_query = db.query(CardFeeMaster).filter(
            CardFeeMaster.status == "ACTIVE",
            CardFeeMaster.charge_type == request.charge_type,
            CardFeeMaster.product_line == product_line,
            CardFeeMaster.effective_from <= request.as_of_date,
            (
                (CardFeeMaster.effective_to.is_(None)) |
                (CardFeeMaster.effective_to > request.as_of_date)
            ),
            (
                (CardFeeMaster.card_category == request.card_category) |
                (CardFeeMaster.card_category == "ANY")
            ),
            network_filter
        )

        # If user did NOT specify card_product, check if multiple products exist.
        # If multiple distinct products match, return NEEDS_DISAMBIGUATION so the chatbot can ask a follow-up question.
        if not request.card_product:
            candidate_rows = (
                db.query(CardFeeMaster.card_product)
                .filter(
                    CardFeeMaster.status == "ACTIVE",
                    CardFeeMaster.charge_type == request.charge_type,
                    CardFeeMaster.product_line == product_line,
                    CardFeeMaster.effective_from <= request.as_of_date,
                    (
                        (CardFeeMaster.effective_to.is_(None))
                        | (CardFeeMaster.effective_to > request.as_of_date)
                    ),
                    (
                        (CardFeeMaster.card_category == request.card_category)
                        | (CardFeeMaster.card_category == "ANY")
                    ),
                    network_filter,
                    CardFeeMaster.card_product.isnot(None),
                )
                .distinct()
                .all()
            )
            candidates = sorted(
                {
                    (r[0] or "").strip()
                    for r in candidate_rows
                    if (r and r[0] and str(r[0]).strip() and str(r[0]).strip().upper() != "ANY")
                }
            )

            if len(candidates) > 1:
                return FeeCalculationResponse(
                    status="NEEDS_DISAMBIGUATION",
                    charge_type=request.charge_type,
                    message=(
                        "Card product is required to answer this fee question. "
                        "Please specify which card product you mean."
                    ),
                    options=[{"card_product": p, "card_product_name": p} for p in candidates],
                )

            # If only one candidate exists, auto-resolve it (no follow-up needed).
            if len(candidates) == 1:
                request.card_product = candidates[0]

        # Build product filter conditionally.
        #
        # IMPORTANT: If a request specifies a product, we include BOTH:
        # - product-specific matches
        # - "ANY" fallback
        # but we MUST prefer product-specific over "ANY" (even if "ANY" has a higher fee_value).
        product_any_penalty = case((CardFeeMaster.card_product == "ANY", 1), else_=0)

        if request.card_product:
            req_prod = (request.card_product or "").strip()
            req_parts = [p.strip() for p in req_prod.split("/") if p.strip()]

            product_conditions = [
                CardFeeMaster.card_product.ilike(req_prod),
                CardFeeMaster.card_product.ilike(f"%{req_prod}%"),
                # Handle DB products like "A/B" as applies to either part
                (
                    CardFeeMaster.card_product.like("%/%")
                    & (
                        func.split_part(CardFeeMaster.card_product, "/", 1).ilike(f"%{req_prod}%")
                        | func.split_part(CardFeeMaster.card_product, "/", 2).ilike(f"%{req_prod}%")
                    )
                ),
            ]

            # If the request contains parts (e.g. "A/B"), match either part against DB product strings.
            if len(req_parts) > 1:
                for part in req_parts:
                    product_conditions.append(CardFeeMaster.card_product.ilike(f"%{part}%"))
                    product_conditions.append(
                        CardFeeMaster.card_product.like("%/%")
                        & (
                            func.split_part(CardFeeMaster.card_product, "/", 1).ilike(f"%{part}%")
                            | func.split_part(CardFeeMaster.card_product, "/", 2).ilike(f"%{part}%")
                        )
                    )

            exact_match_query = exact_match_query.filter(
                or_(
                    CardFeeMaster.card_product == "ANY",
                    *product_conditions,
                )
            )
        else:
            # If no product provided, prefer generic rules
            exact_match_query = exact_match_query.filter(CardFeeMaster.card_product == "ANY")

        exact_match_query = exact_match_query.order_by(
            product_any_penalty.asc(),  # prefer product-specific over ANY
            CardFeeMaster.priority.desc(),
            CardFeeMaster.fee_value.desc(),  # within same specificity/priority, prefer higher fee
        )
        
        exact_rules = exact_match_query.all()
        
        # If exact match found, use it (prioritize exact matches)
        if exact_rules:
            rule = exact_rules[0]
        else:
            # If no exact match, try partial matches
            partial_match_query = db.query(CardFeeMaster).filter(
                CardFeeMaster.status == "ACTIVE",
                CardFeeMaster.charge_type == request.charge_type,
                CardFeeMaster.product_line == product_line,
                CardFeeMaster.effective_from <= request.as_of_date,
                (
                    (CardFeeMaster.effective_to.is_(None)) |
                    (CardFeeMaster.effective_to > request.as_of_date)
                ),
                (
                    (CardFeeMaster.card_category == request.card_category) |
                    (CardFeeMaster.card_category == "ANY")
                ),
                network_filter
            )

            product_any_penalty = case((CardFeeMaster.card_product == "ANY", 1), else_=0)

            if request.card_product:
                req_prod = (request.card_product or "").strip()
                req_parts = [p.strip() for p in req_prod.split("/") if p.strip()]

                partial_product_conditions = [
                    CardFeeMaster.card_product.ilike(f"%{req_prod}%"),
                    CardFeeMaster.card_product == "ANY",
                    (
                        CardFeeMaster.card_product.like("%/%")
                        & (
                            func.split_part(CardFeeMaster.card_product, "/", 1).ilike(f"%{req_prod}%")
                            | func.split_part(CardFeeMaster.card_product, "/", 2).ilike(f"%{req_prod}%")
                        )
                    ),
                ]
                if len(req_parts) > 1:
                    for part in req_parts:
                        partial_product_conditions.append(CardFeeMaster.card_product.ilike(f"%{part}%"))
                        partial_product_conditions.append(
                            CardFeeMaster.card_product.like("%/%")
                            & (
                                func.split_part(CardFeeMaster.card_product, "/", 1).ilike(f"%{part}%")
                                | func.split_part(CardFeeMaster.card_product, "/", 2).ilike(f"%{part}%")
                            )
                        )

                partial_match_query = partial_match_query.filter(or_(*partial_product_conditions))
            else:
                partial_match_query = partial_match_query.filter(CardFeeMaster.card_product == "ANY")
                
            partial_match_query = partial_match_query.order_by(
                product_any_penalty.asc(),
                CardFeeMaster.priority.desc(),
                CardFeeMaster.fee_value.desc(),
            )
            partial_rules = partial_match_query.all()
            
            if not partial_rules:
                return FeeCalculationResponse(
                    status="NO_RULE_FOUND",
                    message=f"No matching fee rule found for {request.charge_type} - {request.card_category} {request.card_network} {request.card_product}"
                )
            
            # Select highest priority rule from partial matches
            rule = partial_rules[0]
        
        # 4.4 Note-based logic
        if rule.condition_type == "NOTE_BASED":
            note_text = None
            try:
                # Try to resolve the note text from card_fee_notes (if present)
                from sqlalchemy import text as sql_text
                note_num_raw = (rule.note_reference or "").strip()
                note_num = int(note_num_raw) if note_num_raw.isdigit() else None
                if note_num is not None:
                    row = db.execute(
                        sql_text("SELECT note_text FROM card_fee_notes WHERE note_number = :n"),
                        {"n": note_num},
                    ).fetchone()
                    note_text = row[0] if row else None
            except Exception:
                note_text = None

            return FeeCalculationResponse(
                status="REQUIRES_NOTE_RESOLUTION",
                note_reference=rule.note_reference,
                answer_text=note_text or getattr(rule, "answer_text", None),
                message=(
                    f"Fee depends on external note definition: {rule.note_reference}"
                    + (f" — {note_text}" if note_text else "")
                ),
                rule_id=str(rule.fee_id)
            )
        
        # 4.3 Free entitlement logic
        if rule.condition_type == "FREE_UPTO_N" and rule.free_entitlement_count:
            if request.usage_index and request.usage_index <= rule.free_entitlement_count:
                return FeeCalculationResponse(
                    status="CALCULATED",
                    fee_amount=Decimal("0"),
                    fee_currency=rule.fee_unit,
                    fee_basis=rule.fee_basis,
                    rule_id=str(rule.fee_id),
                    charge_type=rule.charge_type,
                    answer_text=getattr(rule, "answer_text", None),
                    remarks=f"Free entitlement: {request.usage_index} of {rule.free_entitlement_count} free"
                )
        
        # 4.2 "Whichever higher" logic
        if rule.condition_type == "WHICHEVER_HIGHER":
            if rule.fee_unit == "PERCENT" and rule.min_fee_value and request.amount:
                percent_fee = request.amount * (rule.fee_value / Decimal("100"))
                fixed_fee = rule.min_fee_value
                final_fee = max(percent_fee, fixed_fee)
                
                return FeeCalculationResponse(
                    status="CALCULATED",
                    fee_amount=final_fee,
                    fee_currency=rule.min_fee_unit or rule.fee_unit,
                    fee_basis=rule.fee_basis,
                    rule_id=str(rule.fee_id),
                    answer_text=getattr(rule, "answer_text", None),
                    remarks=f"Whichever higher: {percent_fee} (percent) vs {fixed_fee} (fixed) = {final_fee}"
                )
        
        # Standard fee calculation
        fee_amount = rule.fee_value
        
        # Handle COUNT unit (for free entitlements that have already been checked)
        if rule.fee_unit == "COUNT":
            # COUNT unit means it's a count-based rule, fee_value is the count
            # This is typically used for free entitlements
            if rule.condition_type == "FREE_UPTO_N":
                # Already handled above, but if we get here, it means usage_index > free_entitlement_count
                # Return the count as the fee (though this might need adjustment based on business logic)
                fee_amount = Decimal("0")  # Free entitlement already applied
            else:
                fee_amount = rule.fee_value
        
        # Handle ON_OUTSTANDING basis
        #
        # IMPORTANT:
        # - If outstanding_balance is provided, compute a concrete amount (when percent-based).
        # - If outstanding_balance is NOT provided, return a deterministic rate description
        #   instead of NO_RULE_FOUND (prevents confusing disambiguation prompts).
        if rule.fee_basis == "ON_OUTSTANDING":
            if request.outstanding_balance:
                if rule.fee_unit == "PERCENT":
                    fee_amount = request.outstanding_balance * (rule.fee_value / Decimal("100"))
                else:
                    fee_amount = rule.fee_value
            else:
                # No outstanding balance provided: return an authoritative rate.
                if rule.fee_unit == "PERCENT":
                    return FeeCalculationResponse(
                        status="CALCULATED",
                        fee_amount=None,
                        fee_currency=None,
                        fee_basis=rule.fee_basis,
                        rule_id=str(rule.fee_id),
                        charge_type=rule.charge_type,
                        answer_text=f"{rule.fee_value}% on outstanding balance",
                        remarks=rule.remarks,
                    )
                return FeeCalculationResponse(
                    status="CALCULATED",
                    fee_amount=None,
                    fee_currency=None,
                    fee_basis=rule.fee_basis,
                    rule_id=str(rule.fee_id),
                    charge_type=rule.charge_type,
                    answer_text=getattr(rule, "answer_text", None) or f"{rule.fee_value} on outstanding balance",
                    remarks=rule.remarks,
                )
        
        # Currency matching
        if rule.fee_unit in ["BDT", "USD"]:
            if rule.fee_unit != request.currency:
                # Try to find a rule that matches the requested currency (fee_unit) using the same selection logic.
                product_any_penalty = case((CardFeeMaster.card_product == "ANY", 1), else_=0)

                currency_match_query = db.query(CardFeeMaster).filter(
                    CardFeeMaster.status == "ACTIVE",
                    CardFeeMaster.charge_type == request.charge_type,
                    CardFeeMaster.product_line == product_line,
                    CardFeeMaster.effective_from <= request.as_of_date,
                    (
                        (CardFeeMaster.effective_to.is_(None)) |
                        (CardFeeMaster.effective_to > request.as_of_date)
                    ),
                    (
                        (CardFeeMaster.card_category == request.card_category) |
                        (CardFeeMaster.card_category == "ANY")
                    ),
                    network_filter,
                    CardFeeMaster.fee_unit == request.currency,
                )

                if request.card_product:
                    req_prod = (request.card_product or "").strip()
                    req_parts = [p.strip() for p in req_prod.split("/") if p.strip()]

                    product_conditions = [
                        CardFeeMaster.card_product.ilike(req_prod),
                        CardFeeMaster.card_product.ilike(f"%{req_prod}%"),
                        (
                            CardFeeMaster.card_product.like("%/%")
                            & (
                                func.split_part(CardFeeMaster.card_product, "/", 1).ilike(f"%{req_prod}%")
                                | func.split_part(CardFeeMaster.card_product, "/", 2).ilike(f"%{req_prod}%")
                            )
                        ),
                    ]
                    if len(req_parts) > 1:
                        for part in req_parts:
                            product_conditions.append(CardFeeMaster.card_product.ilike(f"%{part}%"))
                            product_conditions.append(
                                CardFeeMaster.card_product.like("%/%")
                                & (
                                    func.split_part(CardFeeMaster.card_product, "/", 1).ilike(f"%{part}%")
                                    | func.split_part(CardFeeMaster.card_product, "/", 2).ilike(f"%{part}%")
                                )
                            )

                    currency_match_query = currency_match_query.filter(
                        or_(
                            CardFeeMaster.card_product == "ANY",
                            *product_conditions,
                        )
                    )
                else:
                    currency_match_query = currency_match_query.filter(CardFeeMaster.card_product == "ANY")

                currency_rules = currency_match_query.order_by(
                    product_any_penalty.asc(),
                    CardFeeMaster.priority.desc(),
                    CardFeeMaster.fee_value.desc(),
                ).all()

                if currency_rules:
                    rule = currency_rules[0]
                    fee_amount = rule.fee_value
                else:
                    return FeeCalculationResponse(
                        status="FX_RATE_REQUIRED",
                        message=f"Fee rule exists in {rule.fee_unit} but {request.currency} requested. FX rate conversion required."
                    )
        
        return FeeCalculationResponse(
            status="CALCULATED",
            fee_amount=fee_amount,
            fee_currency=rule.fee_unit if rule.fee_unit in ["BDT", "USD"] else request.currency,
            fee_basis=rule.fee_basis,
            rule_id=str(rule.fee_id),
            charge_type=rule.charge_type,
            answer_text=getattr(rule, "answer_text", None),
            remarks=rule.remarks
        )
        
    except Exception as e:
        logger.error(f"Error calculating fee: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fee calculation error: {str(e)}")
    finally:
        db.close()

@app.get("/fees/rules")
async def list_rules(
    charge_type: Optional[str] = Query(None),
    card_category: Optional[str] = Query(None),
    card_network: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    """List fee rules with optional filters"""
    db = get_db_session()
    try:
        query = db.query(CardFeeMaster).filter(CardFeeMaster.status == "ACTIVE")
        
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
        
        rules = query.limit(limit).all()
        
        return {
            "total": len(rules),
            "rules": [
                {
                    "fee_id": str(r.fee_id),
                    "charge_type": r.charge_type,
                    "card_category": r.card_category,
                    "card_network": r.card_network,
                    "card_product": r.card_product,
                    "full_card_name": r.full_card_name,
                    "fee_value": float(r.fee_value),
                    "fee_unit": r.fee_unit,
                    "fee_basis": r.fee_basis,
                    "condition_type": r.condition_type,
                    "priority": r.priority
                }
                for r in rules
            ]
        }
    finally:
        db.close()

def extract_charge_context(charge_description: str) -> str:
    """
    Extract charge_context from charge_description using keyword matching.
    
    Returns:
        charge_context: ON_LIMIT, ON_ENHANCED_AMOUNT, ON_REDUCED_AMOUNT, or GENERAL
        (Only valid enum values for charge_context_enum)
    """
    if not charge_description:
        return "GENERAL"
    
    desc_lower = charge_description.lower()
    
    # Check for enhancement keywords first (before generic limit)
    if any(keyword in desc_lower for keyword in ["enhancement", "enhance", "limit enhancement", "enhance limit"]):
        return "ON_ENHANCED_AMOUNT"
    
    # Check for reduction keywords
    if any(keyword in desc_lower for keyword in ["reduction", "reduce", "limit reduction", "reduce limit"]):
        return "ON_REDUCED_AMOUNT"
    
    # Check for explicit limit/loan amount phrases (not standalone "limit")
    if any(keyword in desc_lower for keyword in ["on limit", "on loan amount", "loan amount"]):
        return "ON_LIMIT"
    
    # Default to GENERAL
    return "GENERAL"


def _render_retail_asset_answer_text(charge: RetailAssetChargeMaster) -> Optional[str]:
    """
    Deterministically render an authoritative answer string for a retail-asset charge.

    Priority:
    1) answer_text (manual/parsed)
    2) fee_text / original_charge_text (verbatim schedule text)
    3) tiered/numeric fields rendered deterministically
    """
    for text in [charge.answer_text, charge.fee_text, charge.original_charge_text]:
        if text and str(text).strip():
            return str(text).strip()

    # Tiered structure
    if charge.tier_1_rate_value is not None:
        parts = []
        t1 = f"Tier 1: {charge.tier_1_rate_value}"
        if charge.tier_1_rate_unit == "PERCENT":
            t1 += "%"
        elif charge.tier_1_rate_unit:
            t1 += f" {charge.tier_1_rate_unit}"
        if charge.tier_1_max_fee_value is not None:
            t1 += f" (max {charge.tier_1_max_fee_value} {charge.tier_1_max_fee_currency or 'BDT'})"
        parts.append(t1)

        if charge.tier_2_rate_value is not None:
            t2 = f"Tier 2: {charge.tier_2_rate_value}"
            if charge.tier_2_rate_unit == "PERCENT":
                t2 += "%"
            elif charge.tier_2_rate_unit:
                t2 += f" {charge.tier_2_rate_unit}"
            if charge.tier_2_max_fee_value is not None:
                t2 += f" (max {charge.tier_2_max_fee_value} {charge.tier_2_max_fee_currency or 'BDT'})"
            parts.append(t2)

        return "; ".join(parts) if parts else None

    # Numeric fee_value
    if charge.fee_value is not None:
        text = f"{charge.fee_value} {charge.fee_unit}"
        if charge.min_fee_value is not None or charge.max_fee_value is not None:
            min_part = f"Min: {charge.min_fee_value} {(charge.min_fee_currency or 'BDT')}" if charge.min_fee_value is not None else ""
            max_part = f"Max: {charge.max_fee_value} {(charge.max_fee_currency or 'BDT')}" if charge.max_fee_value is not None else ""
            both = ", ".join([p for p in [min_part, max_part] if p])
            if both:
                text += f" ({both})"
        return text

    # Parsed structured fields
    if charge.fee_rate_value is not None:
        suffix = "%" if charge.fee_rate_unit == "PERCENT" else (f" {charge.fee_rate_unit}" if charge.fee_rate_unit else "")
        base = f"{charge.fee_rate_value}{suffix}"
        if charge.fee_applies_to:
            base += f" on {charge.fee_applies_to.lower().replace('_', ' ')}"
        if charge.fee_period:
            base += f" ({charge.fee_period.lower().replace('_', ' ')})"
        return base

    if charge.fee_amount_value is not None:
        return f"{charge.fee_amount_currency or 'BDT'} {charge.fee_amount_value}"

    return None

@app.post("/retail-asset-charges/query", response_model=RetailAssetChargeResponse)
async def query_retail_asset_charges(request: RetailAssetChargeRequest):
    """
    Query retail asset charges by loan product, charge type, and description keywords.

    NOTE: This endpoint uses charge_description text matching for lookups.
    The charge_context column is NOT used for filtering.
    """
    db = get_db_session()
    try:
        # Build query - filter by loan_product and charge_type only
        query = db.query(RetailAssetChargeMaster).filter(
            RetailAssetChargeMaster.status == "ACTIVE",
            or_(
                RetailAssetChargeMaster.effective_to.is_(None),
                RetailAssetChargeMaster.effective_to >= request.as_of_date
            ),
            RetailAssetChargeMaster.effective_from <= request.as_of_date
        )

        # Filter by loan product if provided
        if request.loan_product:
            query = query.filter(RetailAssetChargeMaster.loan_product == request.loan_product)

        # Filter by charge type if provided
        if request.charge_type:
            query = query.filter(RetailAssetChargeMaster.charge_type == request.charge_type)

        # Order by priority (highest first), then by effective_from (newest first)
        charges = query.order_by(
            RetailAssetChargeMaster.priority.desc(),
            RetailAssetChargeMaster.effective_from.desc()
        ).all()

        if not charges:
            return RetailAssetChargeResponse(
                status="NO_RULE_FOUND",
                message=f"No retail asset charges found for the specified criteria"
            )

        # Filter by description_keywords if provided
        if request.description_keywords:
            filtered_charges = []
            for charge in charges:
                haystack = " ".join(
                    s for s in [
                        charge.charge_description,
                        charge.fee_text,
                        charge.answer_text,
                        charge.original_charge_text,
                    ]
                    if s
                ).lower()
                # Match if ANY keyword is found in description/text fields
                if any(keyword.lower() in haystack for keyword in request.description_keywords):
                    filtered_charges.append(charge)
            
            # If we found matches, use filtered list; otherwise keep all (no matches means fallback)
            if filtered_charges:
                charges = filtered_charges

        if not charges:
            return RetailAssetChargeResponse(
                status="NO_RULE_FOUND",
                message=f"No retail asset charges found matching the description keywords"
            )

        # If loan_product + charge_type are specified but description_keywords is not,
        # check for collisions (multiple charges with different descriptions)
        if request.loan_product and request.charge_type and not request.description_keywords:
            # Group by charge_description patterns
            descriptions_found = set(charge.charge_description for charge in charges)

            if len(descriptions_found) > 1:
                # Multiple descriptions found - need disambiguation
                charge_list = []
                for charge in charges:
                    answer_text = _render_retail_asset_answer_text(charge)
                    charge_dict = {
                        "charge_id": str(charge.charge_id),
                        "loan_product": charge.loan_product,
                        "loan_product_name": charge.loan_product_name,
                        "charge_type": charge.charge_type,
                        "charge_context": charge.charge_context,  # Use actual field from v2
                        "charge_title": charge.charge_title,
                        "charge_description": charge.charge_description,
                        "answer_text": answer_text,
                        "fee_text": charge.fee_text,
                        "fee_rate_value": float(charge.fee_rate_value) if charge.fee_rate_value else None,
                        "fee_rate_unit": charge.fee_rate_unit,
                        "fee_amount_value": float(charge.fee_amount_value) if charge.fee_amount_value else None,
                        "fee_amount_currency": charge.fee_amount_currency,
                        "fee_period": charge.fee_period,
                        "fee_applies_to": charge.fee_applies_to,
                        "answer_source": charge.answer_source,
                        "parse_status": charge.parse_status,
                        "parsed_from": charge.parsed_from,
                        "parsed_at": charge.parsed_at.isoformat() if charge.parsed_at else None,
                        "fee_value": float(charge.fee_value) if charge.fee_value else None,
                        "fee_unit": charge.fee_unit,
                        "fee_basis": charge.fee_basis,
                        "min_fee_value": float(charge.min_fee_value) if charge.min_fee_value else None,
                        "min_fee_unit": charge.min_fee_currency,  # Map currency to unit for backward compat
                        "min_fee_currency": charge.min_fee_currency,
                        "max_fee_value": float(charge.max_fee_value) if charge.max_fee_value else None,
                        "max_fee_unit": charge.max_fee_currency,  # Map currency to unit for backward compat
                        "max_fee_currency": charge.max_fee_currency,
                        # Map v2 tier field names to v1 names for backward compatibility
                        "tier_1_threshold": float(charge.tier_1_threshold_amount) if charge.tier_1_threshold_amount else None,
                        "tier_1_fee_value": float(charge.tier_1_rate_value) if charge.tier_1_rate_value else None,
                        "tier_1_fee_unit": charge.tier_1_rate_unit,
                        "tier_1_max_fee": float(charge.tier_1_max_fee_value) if charge.tier_1_max_fee_value else None,
                        "tier_2_threshold": float(charge.tier_2_threshold_amount) if charge.tier_2_threshold_amount else None,
                        "tier_2_fee_value": float(charge.tier_2_rate_value) if charge.tier_2_rate_value else None,
                        "tier_2_fee_unit": charge.tier_2_rate_unit,
                        "tier_2_max_fee": float(charge.tier_2_max_fee_value) if charge.tier_2_max_fee_value else None,
                        # Also include v2 field names for new code
                        "tier_1_threshold_amount": float(charge.tier_1_threshold_amount) if charge.tier_1_threshold_amount else None,
                        "tier_1_rate_value": float(charge.tier_1_rate_value) if charge.tier_1_rate_value else None,
                        "tier_1_rate_unit": charge.tier_1_rate_unit,
                        "tier_1_max_fee_value": float(charge.tier_1_max_fee_value) if charge.tier_1_max_fee_value else None,
                        "tier_2_threshold_amount": float(charge.tier_2_threshold_amount) if charge.tier_2_threshold_amount else None,
                        "tier_2_rate_value": float(charge.tier_2_rate_value) if charge.tier_2_rate_value else None,
                        "tier_2_rate_unit": charge.tier_2_rate_unit,
                        "tier_2_max_fee_value": float(charge.tier_2_max_fee_value) if charge.tier_2_max_fee_value else None,
                        "condition_type": charge.condition_type,
                        "condition_description": charge.condition_description,
                        "note_reference": charge.note_reference,
                        "remarks": charge.remarks,
                        "priority": charge.priority
                    }
                    charge_list.append(charge_dict)
                
                return RetailAssetChargeResponse(
                    status="NEEDS_DISAMBIGUATION",
                    charges=charge_list,
                    message=f"Multiple charges found for {request.loan_product} - {request.charge_type}. Please specify which one based on description."
                )
        
        # Single charge or charge_context was specified - format and return
        charge_list = []
        for charge in charges:
            answer_text = _render_retail_asset_answer_text(charge)
            charge_dict = {
                "charge_id": str(charge.charge_id),
                "loan_product": charge.loan_product,
                "loan_product_name": charge.loan_product_name,
                "charge_type": charge.charge_type,
                "charge_context": charge.charge_context,  # Use actual field from v2
                "charge_title": charge.charge_title,
                "charge_description": charge.charge_description,
                "answer_text": answer_text,
                "fee_text": charge.fee_text,
                "fee_rate_value": float(charge.fee_rate_value) if charge.fee_rate_value else None,
                "fee_rate_unit": charge.fee_rate_unit,
                "fee_amount_value": float(charge.fee_amount_value) if charge.fee_amount_value else None,
                "fee_amount_currency": charge.fee_amount_currency,
                "fee_period": charge.fee_period,
                "fee_applies_to": charge.fee_applies_to,
                "answer_source": charge.answer_source,
                "parse_status": charge.parse_status,
                "parsed_from": charge.parsed_from,
                "parsed_at": charge.parsed_at.isoformat() if charge.parsed_at else None,
                "fee_value": float(charge.fee_value) if charge.fee_value else None,
                "fee_unit": charge.fee_unit,
                "fee_basis": charge.fee_basis,
                "min_fee_value": float(charge.min_fee_value) if charge.min_fee_value else None,
                "min_fee_unit": charge.min_fee_currency,  # Map currency to unit for backward compat
                "min_fee_currency": charge.min_fee_currency,
                "max_fee_value": float(charge.max_fee_value) if charge.max_fee_value else None,
                "max_fee_unit": charge.max_fee_currency,  # Map currency to unit for backward compat
                "max_fee_currency": charge.max_fee_currency,
                # Map v2 tier field names to v1 names for backward compatibility
                "tier_1_threshold": float(charge.tier_1_threshold_amount) if charge.tier_1_threshold_amount else None,
                "tier_1_fee_value": float(charge.tier_1_rate_value) if charge.tier_1_rate_value else None,
                "tier_1_fee_unit": charge.tier_1_rate_unit,
                "tier_1_max_fee": float(charge.tier_1_max_fee_value) if charge.tier_1_max_fee_value else None,
                "tier_2_threshold": float(charge.tier_2_threshold_amount) if charge.tier_2_threshold_amount else None,
                "tier_2_fee_value": float(charge.tier_2_rate_value) if charge.tier_2_rate_value else None,
                "tier_2_fee_unit": charge.tier_2_rate_unit,
                "tier_2_max_fee": float(charge.tier_2_max_fee_value) if charge.tier_2_max_fee_value else None,
                # Also include v2 field names for new code
                "tier_1_threshold_amount": float(charge.tier_1_threshold_amount) if charge.tier_1_threshold_amount else None,
                "tier_1_rate_value": float(charge.tier_1_rate_value) if charge.tier_1_rate_value else None,
                "tier_1_rate_unit": charge.tier_1_rate_unit,
                "tier_1_max_fee_value": float(charge.tier_1_max_fee_value) if charge.tier_1_max_fee_value else None,
                "tier_2_threshold_amount": float(charge.tier_2_threshold_amount) if charge.tier_2_threshold_amount else None,
                "tier_2_rate_value": float(charge.tier_2_rate_value) if charge.tier_2_rate_value else None,
                "tier_2_rate_unit": charge.tier_2_rate_unit,
                "tier_2_max_fee_value": float(charge.tier_2_max_fee_value) if charge.tier_2_max_fee_value else None,
                "condition_type": charge.condition_type,
                "condition_description": charge.condition_description,
                "note_reference": charge.note_reference,
                "remarks": charge.remarks,
                "priority": charge.priority
            }
            charge_list.append(charge_dict)
        
        # Deterministic "not available" message if we have rows but no authoritative answer_text
        if charge_list and all((c.get("answer_text") is None or str(c.get("answer_text")).strip() == "") for c in charge_list):
            return RetailAssetChargeResponse(
                status="FOUND",
                charges=charge_list,
                message="Fee information is not available in the Retail Asset Charges Schedule for the selected criteria."
            )

        return RetailAssetChargeResponse(
            status="FOUND",
            charges=charge_list
        )
    except Exception as e:
        logger.error(f"Error querying retail asset charges: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Retail asset charge query error: {str(e)}")
    finally:
        db.close()

@app.get("/retail-asset-charges/loan-products")
async def get_loan_products_for_charge_type(
    charge_type: Optional[str] = Query(None, description="Charge type (e.g., PROCESSING_FEE)")
):
    """
    Get distinct loan products available for a specific charge type.
    Returns list of loan products that have charges for the specified charge_type.
    """
    db = get_db_session()
    try:
        # Build query
        query = db.query(RetailAssetChargeMaster.loan_product, RetailAssetChargeMaster.loan_product_name).filter(
            RetailAssetChargeMaster.status == "ACTIVE"
        )
        
        # Filter by charge type if provided
        if charge_type:
            query = query.filter(RetailAssetChargeMaster.charge_type == charge_type)
        
        # Get distinct loan products
        results = query.distinct().all()
        
        # Format response
        loan_products = []
        for loan_product, loan_product_name in results:
            loan_products.append({
                "loan_product": loan_product,
                "loan_product_name": loan_product_name or loan_product
            })
        
        return {
            "charge_type": charge_type,
            "loan_products": loan_products,
            "total": len(loan_products)
        }
    except Exception as e:
        logger.error(f"Error getting loan products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting loan products: {str(e)}")
    finally:
        db.close()

@app.post("/skybanking-fees/query", response_model=SkybankingFeeResponse)
async def query_skybanking_fees(request: SkybankingFeeRequest):
    """
    Query Skybanking fees by charge type, product, and/or network.
    """
    db = get_db_session()
    try:
        # Build query
        query = db.query(SkybankingFeeMaster).filter(
            SkybankingFeeMaster.status == "ACTIVE",
            or_(
                SkybankingFeeMaster.effective_to.is_(None),
                SkybankingFeeMaster.effective_to >= request.as_of_date
            ),
            SkybankingFeeMaster.effective_from <= request.as_of_date
        )
        
        # Filter by charge type if provided
        if request.charge_type:
            query = query.filter(SkybankingFeeMaster.charge_type == request.charge_type)
        
        # Filter by product if provided
        if request.product:
            query = query.filter(SkybankingFeeMaster.product == request.product)
        
        # Filter by network if provided
        if request.network:
            query = query.filter(SkybankingFeeMaster.network == request.network)
        
        # Order by effective_from (newest first)
        fees = query.order_by(
            SkybankingFeeMaster.effective_from.desc(),
            SkybankingFeeMaster.charge_type
        ).all()
        
        if not fees:
            return SkybankingFeeResponse(
                status="NO_RULE_FOUND",
                message=f"No Skybanking fees found for the specified criteria"
            )
        
        # Format response
        fee_list = []
        for fee in fees:
            fee_dict = {
                "fee_id": str(fee.fee_id),
                "charge_type": fee.charge_type,
                "network": fee.network,
                "product": fee.product,
                "product_name": fee.product_name,
                "fee_amount": float(fee.fee_amount) if fee.fee_amount else None,
                "fee_unit": fee.fee_unit,
                "fee_basis": fee.fee_basis,
                "is_conditional": fee.is_conditional,
                "condition_description": fee.condition_description,
                "remarks": fee.remarks,
                "effective_from": str(fee.effective_from),
                "effective_to": str(fee.effective_to) if fee.effective_to else None
            }
            fee_list.append(fee_dict)
        
        return SkybankingFeeResponse(
            status="FOUND",
            fees=fee_list
        )
    except Exception as e:
        logger.error(f"Error querying Skybanking fees: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Skybanking fee query error: {str(e)}")
    finally:
        db.close()

@app.post("/fees/query", response_model=UnifiedFeeResponse)
async def query_fees_unified(request: UnifiedFeeRequest):
    """
    Unified fee query endpoint for all product lines.
    Routes to appropriate handler based on product_line.
    """
    try:
        if request.product_line == "CREDIT_CARDS":
            # Use existing card fee calculation logic
            card_request = FeeCalculationRequest(
                as_of_date=request.as_of_date,
                charge_type=request.charge_type or "",
                card_category=request.card_category or "CREDIT",
                card_network=request.card_network or "VISA",
                card_product=request.card_product,
                product_line="CREDIT_CARDS"
            )
            result = await calculate_fee(card_request)
            
            if result.status == "CALCULATED":
                return UnifiedFeeResponse(
                    product_line="CREDIT_CARDS",
                    status="FOUND",
                    data=[{
                        "fee_id": result.rule_id,
                        "charge_type": result.charge_type,
                        "fee_amount": float(result.fee_amount) if result.fee_amount else None,
                        "fee_currency": result.fee_currency,
                        "fee_basis": result.fee_basis,
                        "remarks": result.remarks
                    }]
                )
            else:
                return UnifiedFeeResponse(
                    product_line="CREDIT_CARDS",
                    status=result.status,
                    message=result.message
                )
        
        elif request.product_line == "RETAIL_ASSETS":
            # Use retail asset charges query
            retail_request = RetailAssetChargeRequest(
                as_of_date=request.as_of_date,
                loan_product=request.loan_product,
                charge_type=request.charge_type,
                description_keywords=request.description_keywords,
                query=request.query
            )
            result = await query_retail_asset_charges(retail_request)

            return UnifiedFeeResponse(
                product_line="RETAIL_ASSETS",
                status=result.status,
                data=result.charges,
                message=result.message
            )
        
        elif request.product_line == "SKYBANKING":
            # Use Skybanking fees query
            skybanking_request = SkybankingFeeRequest(
                as_of_date=request.as_of_date,
                charge_type=request.charge_type,
                product=request.product,
                network=request.network
            )
            result = await query_skybanking_fees(skybanking_request)
            
            return UnifiedFeeResponse(
                product_line="SKYBANKING",
                status=result.status,
                data=result.fees,
                message=result.message
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown product_line: {request.product_line}")
    
    except Exception as e:
        logger.error(f"Error in unified fee query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unified fee query error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("FEE_ENGINE_PORT", "8003"))
    host = os.getenv("FEE_ENGINE_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
