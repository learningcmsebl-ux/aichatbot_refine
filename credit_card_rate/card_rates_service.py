"""
Card Rates and Fees Microservice
Provides deterministic card fee and rate information from structured schedule data.
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import re
from pathlib import Path
import uvicorn
from datetime import datetime

# File paths
JSON_PATH = Path(__file__).parent / "card_charges.json"

app = FastAPI(
    title="Card Rates Service",
    description="Microservice providing card fees, rates, and charges from structured schedule data",
    version="1.0.0",
)


class CardCharge(BaseModel):
    """Card charge record model"""
    card_full_name: str
    category: str
    network: Optional[str] = None
    product: Optional[str] = None
    charge_type: str
    amount_raw: str


class CardChargeSearchResponse(BaseModel):
    """Search response model"""
    query: str
    results: List[CardCharge]
    total_matches: int


class ChargeTypeResponse(BaseModel):
    """Charge type response model"""
    charge_type: str
    cards: List[CardCharge]
    total_cards: int


class CardInfoResponse(BaseModel):
    """Card info response model"""
    card_name: str
    charges: List[CardCharge]
    total_charges: int


# In-memory data store
CARD_CHARGES: List[Dict] = []
METADATA: Dict[str, Any] = {}


def _load_charges() -> None:
    """Load card charges from JSON file"""
    global CARD_CHARGES, METADATA
    
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"Card charges JSON file not found: {JSON_PATH}")
    
    data = json.loads(JSON_PATH.read_text(encoding='utf-8'))
    CARD_CHARGES = data.get('records', [])
    METADATA = data.get('metadata', {})
    
    print(f"Loaded {len(CARD_CHARGES)} card charge records")
    print(f"Charge types: {len(METADATA.get('charge_types', []))}")


@app.on_event("startup")
async def startup_event() -> None:
    """Load data on startup"""
    _load_charges()


def _normalize(text: str) -> str:
    """Normalize text for matching"""
    if not text:
        return ""
    # Convert to lowercase, remove special chars, normalize spaces
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return ' '.join(text.split())


# Charge type synonyms mapping
CHARGE_SYNONYMS: Dict[str, List[str]] = {
    "annual fee": [
        "annual fee", "yearly fee", "renewal fee", "issuance fee", 
        "joining fee", "issuance/renewal/annual fee", "primary card fee"
    ],
    "supplementary fee": [
        "supplementary", "supplementary card", "supplementary annual fee",
        "additional card fee"
    ],
    "replacement fee": [
        "replacement fee", "card replacement", "card replacement fee",
        "replace card", "lost card", "stolen card"
    ],
    "pin replacement": [
        "pin replacement", "pin fee", "pin replacement fee", "new pin"
    ],
    "interest rate": [
        "interest rate", "rate of interest", "apr", "annual percentage rate",
        "interest", "card interest"
    ],
    "late payment": [
        "late payment fee", "late fee", "late payment", "overdue fee"
    ],
    "overlimit fee": [
        "overlimit fee", "over-limit fee", "over limit", "exceed limit"
    ],
    "cash advance": [
        "cash advance fee", "cash withdrawal fee", "cash withdrawal",
        "atm withdrawal", "cash advance"
    ],
    "lounge access": [
        "lounge", "sky lounge", "airport lounge", "lounge access",
        "lounge visit", "skylounge", "international lounge", "domestic lounge",
        "global lounge", "priority pass", "lounge free", "free lounge"
    ],
    "transaction alert": [
        "transaction alert", "alert fee", "sms alert", "notification fee"
    ],
    "duplicate statement": [
        "duplicate statement", "e-statement", "statement fee", "duplicate estatement"
    ],
    "certificate fee": [
        "certificate fee", "card certificate", "verification certificate"
    ],
    "chequebook fee": [
        "chequebook fee", "card cheque", "cheque book", "card chequebook"
    ],
    "cheque processing": [
        "cheque processing", "card cheque processing", "cheque fee"
    ],
    "customer verification": [
        "customer verification", "cib fee", "verification fee", "cib"
    ],
    "risk assurance": [
        "risk assurance", "risk fee", "assurance fee"
    ],
    "fund transfer": [
        "fund transfer", "money transfer", "transfer fee", "skybanking transfer"
    ],
    "wallet transfer": [
        "wallet transfer", "add money", "mfs", "psp", "mobile wallet"
    ],
    "atm receipt": [
        "atm receipt", "receipt fee", "atm receipt fee"
    ],
    "cctv footage": [
        "cctv", "footage", "cctv footage", "atm footage", "security footage"
    ],
    "undelivered card": [
        "undelivered card", "card destruction", "pin destruction", "undelivered"
    ],
    "overlimit fee": [
        "overlimit", "over limit", "overlimit fee"
    ],
    "sales voucher": [
        "sales voucher", "voucher retrieval", "transaction voucher"
    ],
    "want2buy": [
        "want2buy", "easycredit", "easy credit", "installment", "emi"
    ],
    "return cheque": [
        "return cheque", "bounced cheque", "cheque return"
    ],
}


def _charge_type_matches_query(charge_type: str, query_norm: str) -> bool:
    """Check if charge type matches query"""
    if not charge_type:
        return False
    
    charge_norm = _normalize(charge_type)
    
    # Direct match (highest priority)
    if charge_norm in query_norm or query_norm in charge_norm:
        return True
    
    # Exact keyword matching for specific charge types
    # If query mentions "interest rate", prioritize Interest Rate charge types
    if "interest" in query_norm and "rate" in query_norm:
        if "interest" in charge_norm and "rate" in charge_norm:
            return True
    
    # Synonym matching
    for key, synonyms in CHARGE_SYNONYMS.items():
        if key in query_norm:
            # Check if any synonym appears in charge type
            for syn in synonyms:
                if syn in charge_norm:
                    return True
    
    # Word-level matching
    query_words = set(query_norm.split())
    charge_words = set(charge_norm.split())
    
    # If significant overlap, consider it a match
    if len(query_words & charge_words) >= 2:
        return True
    
    # Check for specific keywords
    keywords = ['fee', 'charge', 'rate', 'cost', 'price']
    if any(kw in query_norm for kw in keywords) and any(kw in charge_norm for kw in keywords):
        return True
    
    return False


def _card_matches_query(card_name: str, product: Optional[str], network: Optional[str], 
                        category: Optional[str], query_norm: str) -> int:
    """Calculate match score for card"""
    score = 0
    
    card_norm = _normalize(card_name or "")
    product_norm = _normalize(product or "")
    network_norm = _normalize(network or "")
    category_norm = _normalize(category or "")
    
    # Exact card name match (highest score)
    if card_norm and card_norm in query_norm:
        score += 10
    
    # Product match (higher priority - product names are more specific)
    if product_norm:
        # Check if entire product name matches (exact match)
        if product_norm in query_norm:
            score += 10  # High score for exact product match
        else:
            # Check individual words
            product_words = product_norm.split()
            for word in product_words:
                if word and len(word) > 2 and word in query_norm:
                    score += 5  # Increased score for product word matches
    
    # Network match
    if network_norm:
        network_words = network_norm.split()
        for word in network_words:
            if word and len(word) > 2 and word in query_norm:
                score += 2
    
    # Category match
    if category_norm:
        category_words = category_norm.split()
        for word in category_words:
            if word and len(word) > 2 and word in query_norm:
                score += 1
    
    # Partial card name match
    if card_norm:
        card_words = card_norm.split()
        for word in card_words:
            if word and len(word) > 3 and word in query_norm:
                score += 1
    
    return score


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "card-rates-service",
        "version": "1.0.0",
        "records_loaded": len(CARD_CHARGES),
        "charge_types": len(METADATA.get('charge_types', [])),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/rates/search", response_model=CardChargeSearchResponse)
async def search_rates(
    q: str = Query(..., description="Natural language query about card charges/fees"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results")
):
    """
    Search for card charges and fees using natural language query.
    
    Examples:
    - "annual fee for visa platinum"
    - "replacement fee credit card"
    - "lounge access infinite card"
    - "interest rate visa classic"
    """
    if not CARD_CHARGES:
        raise HTTPException(status_code=500, detail="Card charges data not loaded")
    
    query_norm = _normalize(q)
    matches: List[tuple[int, Dict]] = []
    
    # Pre-process query to detect specific charge type intent
    query_lower = query_norm.lower()
    is_interest_rate_query = "interest" in query_lower and "rate" in query_lower
    is_lounge_query = any(kw in query_lower for kw in ["lounge", "skylounge", "airport lounge"])
    
    # Debug logging
    if is_interest_rate_query:
        print(f"[DEBUG] Interest rate query detected: '{q}'")
        print(f"[DEBUG] Query normalized: '{query_norm}'")
        print(f"[DEBUG] Will filter to only Interest Rate charge types")
    
    for record in CARD_CHARGES:
        charge_type = record.get('charge_type', '')
        card_name = record.get('full_name', '')
        product = record.get('product')
        network = record.get('network')
        category = record.get('category')
        
        charge_norm = _normalize(charge_type)
        
        # For interest rate queries, ONLY include Interest Rate charge types
        # This filtering happens BEFORE charge type matching to ensure we only get Interest Rate results
        if is_interest_rate_query:
            if "interest" not in charge_norm or "rate" not in charge_norm:
                continue  # Skip non-interest-rate charge types for interest rate queries
            # For interest rate queries, skip the charge type matching check since we've already filtered
            charge_type_matches = True
            if "classic" in card_name.lower():
                print(f"[DEBUG] Found Interest Rate for Classic: {charge_type}, card_score will be calculated")
        else:
            # For other queries, use normal charge type matching
            charge_type_matches = _charge_type_matches_query(charge_type, query_norm)
        
        if not charge_type_matches:
            continue
        
        # Check if card matches
        card_score = _card_matches_query(card_name, product, network, category, query_norm)
        
        # For interest rate queries, be more lenient with card matching
        if is_interest_rate_query:
            # Boost score if product/network matches
            if product and _normalize(product) in query_norm:
                card_score = max(card_score, 8)  # High score for product match
            if network and _normalize(network) in query_norm:
                card_score = max(card_score, 5)  # Good score for network match
            if category and _normalize(category) in query_norm:
                card_score = max(card_score, 2)  # Base score for category match
            # If still no match, include it with low score (for interest rate queries, show all cards if no specific card mentioned)
            if card_score <= 0:
                card_score = 1  # Generic match for interest rate queries
        elif card_score <= 0:
            # For other queries, use standard matching
            if 'card' not in query_norm.lower():
                card_score = 1  # Generic match
            elif any(word in query_norm for word in ['all', 'any', 'every']):
                card_score = 1  # Generic match for "all cards" queries
            else:
                # Check if product name appears in query
                if product and _normalize(product) in query_norm:
                    card_score = 2  # Product match
                elif network and _normalize(network) in query_norm:
                    card_score = 1  # Network match
                else:
                    continue
        
        # Calculate total score (charge type match + card match)
        # Boost score for exact charge type matches
        charge_type_boost = 0
        
        # Very high boost for exact interest rate matches when query is about interest rate
        if is_interest_rate_query and "interest" in charge_norm and "rate" in charge_norm:
            charge_type_boost = 50  # Very high priority for interest rate matches
        
        # High boost for exact charge type name match
        if charge_norm in query_lower or query_lower in charge_norm:
            charge_type_boost = 15
        
        # Boost for lounge-related charge types in lounge queries
        if is_lounge_query and any(kw in charge_norm for kw in ["lounge", "skylounge"]):
            charge_type_boost = 30
        
        total_score = card_score + 5 + charge_type_boost  # Base score + charge type match + boost
        
        matches.append((total_score, record))
    
    if not matches:
        return CardChargeSearchResponse(
            query=q,
            results=[],
            total_matches=0
        )
    
    # Sort by score descending and take top results
    matches.sort(key=lambda x: x[0], reverse=True)
    top_matches = [m[1] for m in matches[:limit]]
    
    results: List[CardCharge] = []
    for rec in top_matches:
        results.append(
            CardCharge(
                card_full_name=rec.get('full_name', 'Unknown Card'),
                category=rec.get('category', 'Unknown'),
                network=rec.get('network'),
                product=rec.get('product'),
                charge_type=rec.get('charge_type', ''),
                amount_raw=rec.get('amount_raw', ''),
            )
        )
    
    return CardChargeSearchResponse(
        query=q,
        results=results,
        total_matches=len(matches)
    )


@app.get("/rates/by-charge-type/{charge_type}", response_model=ChargeTypeResponse)
async def get_by_charge_type(
    charge_type: str,
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results")
):
    """Get all cards for a specific charge type"""
    if not CARD_CHARGES:
        raise HTTPException(status_code=500, detail="Card charges data not loaded")
    
    charge_type_norm = _normalize(charge_type)
    matches = []
    
    for record in CARD_CHARGES:
        record_charge_type = record.get('charge_type', '')
        if _normalize(record_charge_type) == charge_type_norm or charge_type_norm in _normalize(record_charge_type):
            matches.append(record)
    
    results: List[CardCharge] = []
    for rec in matches[:limit]:
        results.append(
            CardCharge(
                card_full_name=rec.get('full_name', 'Unknown Card'),
                category=rec.get('category', 'Unknown'),
                network=rec.get('network'),
                product=rec.get('product'),
                charge_type=rec.get('charge_type', ''),
                amount_raw=rec.get('amount_raw', ''),
            )
        )
    
    return ChargeTypeResponse(
        charge_type=charge_type,
        cards=results,
        total_cards=len(matches)
    )


@app.get("/rates/by-card", response_model=CardInfoResponse)
async def get_by_card(
    card_name: str = Query(..., description="Card name to search for"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results")
):
    """Get all charges for a specific card"""
    if not CARD_CHARGES:
        raise HTTPException(status_code=500, detail="Card charges data not loaded")
    
    card_name_norm = _normalize(card_name)
    matches = []
    
    for record in CARD_CHARGES:
        record_card_name = record.get('full_name', '')
        if card_name_norm in _normalize(record_card_name) or _normalize(record_card_name) in card_name_norm:
            matches.append(record)
    
    results: List[CardCharge] = []
    for rec in matches[:limit]:
        results.append(
            CardCharge(
                card_full_name=rec.get('full_name', 'Unknown Card'),
                category=rec.get('category', 'Unknown'),
                network=rec.get('network'),
                product=rec.get('product'),
                charge_type=rec.get('charge_type', ''),
                amount_raw=rec.get('amount_raw', ''),
            )
        )
    
    return CardInfoResponse(
        card_name=card_name,
        charges=results,
        total_charges=len(matches)
    )


@app.get("/metadata")
async def get_metadata():
    """Get metadata about available charge types and card categories"""
    return METADATA


if __name__ == "__main__":
    uvicorn.run(
        "card_rates_service:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )

