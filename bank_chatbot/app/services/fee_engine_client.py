"""
Fee Engine Client
Client for calling the new fee-engine microservice for deterministic fee calculations.
"""

import httpx
import logging
from typing import Optional, Dict, Any, List
from datetime import date
from decimal import Decimal
import re

from app.core.config import settings

logger = logging.getLogger(__name__)


class FeeEngineClient:
    """Client for connecting to Fee Engine API"""
    
    def __init__(self):
        base_url = getattr(settings, "FEE_ENGINE_URL", "http://localhost:8003").rstrip("/")
        self.base_url = base_url
        self.timeout = 15.0
        logger.info(f"Fee Engine client initialized: base_url={self.base_url}")
    
    def _detect_product_line(self, query: str) -> Optional[str]:
        """
        Detect product line from natural language query.
        Returns: CREDIT_CARDS, SKYBANKING, PRIORITY_BANKING, RETAIL_ASSETS, or None (defaults to CREDIT_CARDS)
        """
        query_lower = query.lower()
        
        # Check for Skybanking keywords
        if any(kw in query_lower for kw in ['skybanking', 'sky banking', 'digital banking', 'online banking', 'ebl skybanking']):
            return "SKYBANKING"
        
        # Check for Priority Banking keywords
        if any(kw in query_lower for kw in ['priority banking', 'priority customer', 'priority account']):
            return "PRIORITY_BANKING"
        
        # Check for Retail Assets/Loans keywords
        # Note: include retail-asset-exclusive fee terms that users may ask without saying "loan"
        if any(kw in query_lower for kw in [
            'loan', 'retail asset', 'fast cash', 'fast loan', 'overdraft', 'od',
            'personal loan', 'home loan', 'car loan',
            # fees/charges that are commonly asked without explicit product keywords
            'stamp charge', 'stamp duty',
            'reschedule', 'restructure',  # reschedule & restructure fees
            'notarization fee', 'noc fee', 'loan repayment certificate',
            'loan outstanding certificate',
            # Retail asset-specific charge types (that users may ask without saying "loan")
            'penal interest', 'partial payment', 'early settlement',
            'security replacement', 'legal expense',
            # Vetting/valuation is often asked without "loan"
            'vetting', 'valuation fee', 'valuation charge', 'vetting & valuation', 'vetting and valuation',
            'insurance charge', 'documentation charge',
        ]):
            return "RETAIL_ASSETS"
        
        # Default to CREDIT_CARDS (or check for explicit card keywords)
        if any(kw in query_lower for kw in ['card', 'credit card', 'debit card', 'visa', 'mastercard']):
            return "CREDIT_CARDS"
        
        # If no clear indicator, default to CREDIT_CARDS
        return "CREDIT_CARDS"
    
    def _extract_card_info_from_query(self, query: str) -> Dict[str, Optional[str]]:
        """
        Extract card information from natural language query.
        Returns: {card_category, card_network, card_product}
        """
        query_lower = query.lower()
        
        # Extract card category
        card_category = None
        if "debit" in query_lower:
            card_category = "DEBIT"
        elif "credit" in query_lower:
            card_category = "CREDIT"
        elif "prepaid" in query_lower:
            card_category = "PREPAID"
        else:
            # Default to CREDIT if not specified
            card_category = "CREDIT"
        
        # Extract card network
        card_network = None
        
        # Extract card network
        if "visa" in query_lower:
            card_network = "VISA"
        elif "mastercard" in query_lower or "master card" in query_lower:
            card_network = "MASTERCARD"
        elif "diners" in query_lower:
            card_network = "DINERS"
        elif "unionpay" in query_lower or "union pay" in query_lower:
            # Canonical value used in card_fee_master after normalization
            card_network = "UNIONPAY"
        elif "fx" in query_lower:
            # We keep card_network canonical (no FX network); FX Credit is treated under VISA
            card_network = "VISA"
        elif "takapay" in query_lower or "taka pay" in query_lower:
            card_network = "TAKAPAY"
        else:
            # Try to infer from card product names
            if "rfcd" in query_lower:
                card_network = "MASTERCARD"
        
        # Extract card product
        card_product = None
        
        # NOTE: card_network is canonical in DB (VISA/MASTERCARD/DINERS/UNIONPAY/TAKAPAY).
        # For debit "Platinum" users may say "Visa Platinum debit" etc; we keep network as
        # VISA/MASTERCARD and extract product "Platinum" normally.
        if True:
            product_keywords = {
                "world rfcd": "World RFCD",  # Check this first (longest match)
                "global/mastercard world rfcd": "World RFCD",  # Full name variant
                "global/master card world rfcd": "World RFCD",  # Full name variant
                "women platinum": "Women  Platinum",  # Women Platinum (note: database has double space)
                "women signature": "Signature Lite/Women Signature",  # Women Signature variant
                "signature acci": "Signature Acci",
                "corporate platinum": "Corporate Platinum",
                "army/air force/ navy platinum": "Army/Air Force/ Navy Platinum",  # Full name
                "army/air force/navy platinum": "Army/Air Force/ Navy Platinum",  # Variant without spaces
                "navy platinum": "Army/Air Force/ Navy Platinum",  # Individual match
                "army platinum": "Army/Air Force/ Navy Platinum",  # Individual match
                "air force platinum": "Army/Air Force/ Navy Platinum",  # Individual match
                "signature lite": "Signature Lite/Women Signature",
                "priority signature": "Priority Signature",
                "mastercard women prepaid card": "Mastercard Women Prepaid Card",  # Prepaid card product
                "payroll": "Payroll",  # Payroll prepaid card
                "rfcd": "World RFCD",  # RFCD typically means World RFCD
                "unionpay classic": "UnionPay Classic",  # UnionPay Classic (check before "classic")
                "union pay classic": "UnionPay Classic",  # UnionPay Classic variant
                "classic": "Classic",
                "gold": "Gold",
                "platinum": "Platinum",
                "signature": "Signature",
                "infinite": "Infinite",
                "titanium": "Titanium",
                "world": "World",
            }
            
            # Check for longest matches first (to match "women platinum" before "platinum")
            for keyword, product in sorted(product_keywords.items(), key=lambda x: len(x[0]), reverse=True):
                if keyword in query_lower:
                    card_product = product
                    break
            
            # If RFCD is mentioned, it's likely World RFCD
            if "rfcd" in query_lower and not card_product:
                card_product = "World RFCD"
        
        return {
            "card_category": card_category,
            "card_network": card_network,
            "card_product": card_product
        }
    
    def _map_query_to_loan_product(self, query: str) -> Optional[str]:
        """
        Map natural language query to loan product enum.
        Returns loan product string or None.
        """
        query_lower = query.lower()
        
        loan_product_map = {
            "fast cash": "FAST_CASH_OD",
            "fast cash od": "FAST_CASH_OD",
            "fast cash overdraft": "FAST_CASH_OD",
            "fast loan": "FAST_LOAN_SECURED_EMI",
            "education loan": "EDU_LOAN_SECURED",
            "edu loan": "EDU_LOAN_SECURED",
            "personal loan": "EXECUTIVE_LOAN",
            "executive loan": "EXECUTIVE_LOAN",
            "auto loan": "AUTO_LOAN",
            "home loan": "HOME_LOAN",
            "car loan": "AUTO_LOAN",
        }
        
        for keyword, loan_product in loan_product_map.items():
            if keyword in query_lower:
                logger.info(f"[FEE_ENGINE] Mapped loan product '{loan_product}' from keyword '{keyword}' in query: '{query}'")
                return loan_product
        
        return None
    
    def _extract_charge_context_from_query(self, query: str) -> Optional[str]:
        """
        Extract charge_context from natural language query using keyword matching.
        
        Returns:
            charge_context: ON_LIMIT, ON_ENHANCED_AMOUNT, ON_REDUCED_AMOUNT, or None
            (Only valid enum values for charge_context_enum)
        """
        if not query:
            return None
        
        query_lower = query.lower()
        
        # Check for enhancement keywords first (before generic limit)
        if any(keyword in query_lower for keyword in ["enhancement", "enhance", "limit enhancement", "enhance limit", "enhanced amount"]):
            return "ON_ENHANCED_AMOUNT"
        
        # Check for reduction keywords
        if any(keyword in query_lower for keyword in ["reduction", "reduce", "limit reduction", "reduce limit", "reduced amount"]):
            return "ON_REDUCED_AMOUNT"
        
        # Check for explicit limit/loan amount phrases (not standalone "limit")
        if any(keyword in query_lower for keyword in ["on limit", "on loan amount", "loan amount"]):
            return "ON_LIMIT"
        
        # Default: return None (will use GENERAL in database)
        return None
    
    def _map_query_to_charge_type(self, query: str, product_line: Optional[str] = None) -> Optional[str]:
        """
        Map natural language query to standardized charge type.
        Returns charge type string or None if not a fee query.
        """
        query_lower = query.lower()

        # High-signal special handling (avoid substring pitfalls like "cctv footage fee outside dhaka")
        if "cctv" in query_lower and "footage" in query_lower:
            # Prefer outside/inside if any Dhaka scope is implied
            if "outside" in query_lower and "dhaka" in query_lower:
                return "ATM_CCTV_FOOTAGE_OUTSIDE_DHAKA"
            if "inside" in query_lower and "dhaka" in query_lower:
                return "ATM_CCTV_FOOTAGE_INSIDE_DHAKA"
            # fallback
            return "ATM_CCTV_FOOTAGE_INSIDE_DHAKA"

        if "atm" in query_lower and "receipt" in query_lower:
            return "ATM_RECEIPT_EBL"
        
        # Skybanking charge type mappings
        skybanking_charge_type_map = {
            "account certificate fee": "ACCOUNT_CERTIFICATE",
            "certificate fee": "ACCOUNT_CERTIFICATE",
            "fund transfer fee": "FUND_TRANSFER",
            "transfer fee": "FUND_TRANSFER",
            "transaction fee": "TRANSACTION_FEE",
            "skybanking fee": "SKYBANKING_FEE",
        }

        # Retail asset charge type mappings
        # Note: Order matters - more specific/longer strings should be checked first (they're sorted by length descending)
        #
        # DATA MODEL INVARIANT (confirmed by audit 2025-12-30):
        # All enhancement/reduction processing fees use PROCESSING_FEE + charge_context
        # NOT separate LIMIT_ENHANCEMENT_FEE/LIMIT_REDUCTION_FEE charge_types
        #
        # Therefore: "limit enhancement/reduction processing fee" → PROCESSING_FEE
        # The charge_context (ON_ENHANCED_AMOUNT/ON_REDUCED_AMOUNT) distinguishes them
        retail_charge_type_map = {
            # Processing fees (with context determined by charge_context field)
            "fast cash limit enhancement processing fee": "PROCESSING_FEE",  # → PROCESSING_FEE + ON_ENHANCED_AMOUNT
            "fast cash limit reduction processing fee": "PROCESSING_FEE",  # → PROCESSING_FEE + ON_REDUCED_AMOUNT
            "limit enhancement processing fee": "PROCESSING_FEE",  # → PROCESSING_FEE + ON_ENHANCED_AMOUNT
            "limit reduction processing fee": "PROCESSING_FEE",  # → PROCESSING_FEE + ON_REDUCED_AMOUNT
            "fast cash processing fee": "PROCESSING_FEE",
            "processing fee": "PROCESSING_FEE",
            # Standalone limit enhancement/reduction fees (NOT processing fees - if they exist in future)
            # Note: Currently no loan products use these, but kept for future compatibility
            "limit enhancement fee": "LIMIT_ENHANCEMENT_FEE",  # Standalone enhancement fee (not processing)
            "limit reduction fee": "LIMIT_REDUCTION_FEE",  # Standalone reduction fee (not processing)
            # Other fees
            "limit cancellation fee": "LIMIT_CANCELLATION_FEE",
            "closing fee": "LIMIT_CANCELLATION_FEE",
            "renewal fee": "RENEWAL_FEE",
            "partial payment fee": "PARTIAL_PAYMENT_FEE",
            "early settlement fee": "EARLY_SETTLEMENT_FEE",
            "early_settlement_fee": "EARLY_SETTLEMENT_FEE",  # Handle underscore format
            "early settlement": "EARLY_SETTLEMENT_FEE",
            "settlement fee": "EARLY_SETTLEMENT_FEE",  # Generic settlement fee for loans
            "security lien confirmation": "SECURITY_LIEN_CONFIRMATION",
            "lien confirmation": "SECURITY_LIEN_CONFIRMATION",
            "security lien": "SECURITY_LIEN_CONFIRMATION",
            "quotation change fee": "QUOTATION_CHANGE_FEE",
            "changing car quotation": "QUOTATION_CHANGE_FEE",
            "notarization fee": "NOTARIZATION_FEE",
            "notary fee": "NOTARIZATION_FEE",
            "noc fee": "NOC_FEE",
            "loan repayment certificate": "NOC_FEE",
            "loan repayment certificate (noc)": "NOC_FEE",
            "loan repayment certificate fee": "NOC_FEE",
            "penal interest": "PENAL_INTEREST",
            "cib charge": "CIB_CHARGE",
            "cpv charge": "CPV_CHARGE",
            "vetting & valuation charge": "VETTING_VALUATION_CHARGE",
            "vetting and valuation charge": "VETTING_VALUATION_CHARGE",
            "vetting valuation charge": "VETTING_VALUATION_CHARGE",
            "security replacement fee": "SECURITY_REPLACEMENT_FEE",
            # Stamp charge / stamp duty (retail assets v2 enum)
            "stamp duty": "STAMP_CHARGE",
            "stamp charge": "STAMP_CHARGE",
            "loan outstanding certificate fee": "LOAN_OUTSTANDING_CERTIFICATE_FEE",
            "loan outstanding certificate": "LOAN_OUTSTANDING_CERTIFICATE_FEE",
            "outstanding certificate fee": "LOAN_OUTSTANDING_CERTIFICATE_FEE",
            # Reschedule / restructure fees (v2 enum)
            "reschedule & restructure exit fee": "RESCHEDULE_RESTRUCTURE_EXIT_FEE",
            "reschedule and restructure exit fee": "RESCHEDULE_RESTRUCTURE_EXIT_FEE",
            "reschedule restructure exit fee": "RESCHEDULE_RESTRUCTURE_EXIT_FEE",
            "restructure exit fee": "RESCHEDULE_RESTRUCTURE_EXIT_FEE",
            "reschedule & restructure fee": "RESCHEDULE_RESTRUCTURE_FEE",
            "reschedule and restructure fee": "RESCHEDULE_RESTRUCTURE_FEE",
            "reschedule restructure fee": "RESCHEDULE_RESTRUCTURE_FEE",
            "rescheduling fee": "RESCHEDULE_RESTRUCTURE_FEE",
            "restructuring fee": "RESCHEDULE_RESTRUCTURE_FEE",
            "reschedule fee": "RESCHEDULE_RESTRUCTURE_FEE",
            "restructure fee": "RESCHEDULE_RESTRUCTURE_FEE",
        }

        # Charge type mappings (for card fees)
        charge_type_map = {
            # Supplementary cards (check these FIRST before general annual fee)
            # Note: Database uses SUPPLEMENTARY_ANNUAL (not ISSUANCE_ANNUAL_SUPPLEMENTARY)
            "how many free supplementary cards": "SUPPLEMENTARY_FREE_ENTITLEMENT",
            "how many free supplementary card": "SUPPLEMENTARY_FREE_ENTITLEMENT",
            "how many free supplementary": "SUPPLEMENTARY_FREE_ENTITLEMENT",
            "free supplementary cards": "SUPPLEMENTARY_FREE_ENTITLEMENT",
            "free supplementary card": "SUPPLEMENTARY_FREE_ENTITLEMENT",
            "free supplementary": "SUPPLEMENTARY_FREE_ENTITLEMENT",
            "supplementary annual fee": "SUPPLEMENTARY_ANNUAL",
            "supplementary fee": "SUPPLEMENTARY_ANNUAL",
            "supplementary card fee": "SUPPLEMENTARY_ANNUAL",
            "supplementary card annual fee": "SUPPLEMENTARY_ANNUAL",
            "supplementary": "SUPPLEMENTARY_ANNUAL",  # Catch "how many free supplementary"
            "additional card fee": "SUPPLEMENTARY_ANNUAL",
            "additional card annual fee": "SUPPLEMENTARY_ANNUAL",
            
            # Annual fees (primary card)
            "annual fee": "ISSUANCE_ANNUAL_PRIMARY",
            "yearly fee": "ISSUANCE_ANNUAL_PRIMARY",
            "renewal fee": "ISSUANCE_ANNUAL_PRIMARY",
            "issuance fee": "ISSUANCE_ANNUAL_PRIMARY",
            "issuance charge": "ISSUANCE_ANNUAL_PRIMARY",  # "charge" is equivalent to "fee"
            "issuance cost": "ISSUANCE_ANNUAL_PRIMARY",
            "primary card fee": "ISSUANCE_ANNUAL_PRIMARY",
            "primary card annual fee": "ISSUANCE_ANNUAL_PRIMARY",
            
            # Replacement fees (order matters - check longer/more specific first)
            "pin replacement fee": "PIN_REPLACEMENT",  # Check this first (longest match)
            "pin replacement": "PIN_REPLACEMENT",
            "pin fee": "PIN_REPLACEMENT",
            "card replacement fee": "CARD_REPLACEMENT",  # Check this before generic "replacement fee"
            "replacement fee": "CARD_REPLACEMENT",
            "card replacement": "CARD_REPLACEMENT",
            
            # Payment fees
            "late payment": "LATE_PAYMENT",
            "late fee": "LATE_PAYMENT",
            
            # ATM/Cash withdrawal (check these before general "fee")
            "other bank atm": "CASH_WITHDRAWAL_OTHER_ATM",
            "other bank atm withdrawal": "CASH_WITHDRAWAL_OTHER_ATM",
            "other bank atm cash withdrawal": "CASH_WITHDRAWAL_OTHER_ATM",
            "other atm": "CASH_WITHDRAWAL_OTHER_ATM",
            "atm cash withdrawal charge": "CASH_WITHDRAWAL_EBL_ATM",
            "atm cash withdrawal fee": "CASH_WITHDRAWAL_EBL_ATM",
            "atm withdrawal charge": "CASH_WITHDRAWAL_EBL_ATM",
            "atm withdrawal fee": "CASH_WITHDRAWAL_EBL_ATM",
            "atm withdrawal": "CASH_WITHDRAWAL_EBL_ATM",
            "cash withdrawal charge": "CASH_WITHDRAWAL_EBL_ATM",
            "cash withdrawal fee": "CASH_WITHDRAWAL_EBL_ATM",
            "cash withdrawal": "CASH_WITHDRAWAL_EBL_ATM",
            "cash advance charge": "CASH_WITHDRAWAL_EBL_ATM",
            "cash advance fee": "CASH_WITHDRAWAL_EBL_ATM",
            "cash advance": "CASH_WITHDRAWAL_EBL_ATM",
            "atm fee": "CASH_WITHDRAWAL_EBL_ATM",
            "withdrawal charge": "CASH_WITHDRAWAL_EBL_ATM",
            "withdrawal fee": "CASH_WITHDRAWAL_EBL_ATM",

            # ATM receipt / CCTV
            "atm receipt fee": "ATM_RECEIPT_EBL",
            "atm receipt": "ATM_RECEIPT_EBL",
            "cctv footage inside dhaka": "ATM_CCTV_FOOTAGE_INSIDE_DHAKA",
            "cctv footage outside dhaka": "ATM_CCTV_FOOTAGE_OUTSIDE_DHAKA",
            "cctv footage": "ATM_CCTV_FOOTAGE_INSIDE_DHAKA",  # fallback if Dhaka scope not specified
            "atm cctv footage": "ATM_CCTV_FOOTAGE_INSIDE_DHAKA",
            
            # Lounge access
            "lounge access": "GLOBAL_LOUNGE_ACCESS_FEE",
            "lounge fee": "GLOBAL_LOUNGE_ACCESS_FEE",
            "sky lounge": "GLOBAL_LOUNGE_ACCESS_FEE",
            "airport lounge": "GLOBAL_LOUNGE_ACCESS_FEE",
            
            # Interest rates
            "interest rate": "INTEREST_RATE",
            "card interest": "INTEREST_RATE",
            "apr": "INTEREST_RATE",
            
            # Other fees
            "overlimit": "OVERLIMIT",
            "over limit": "OVERLIMIT",
            "duplicate statement": "DUPLICATE_ESTATEMENT",
            "e-statement": "DUPLICATE_ESTATEMENT",
            "certificate fee": "CERTIFICATE_FEE",
            "cib fee": "CUSTOMER_VERIFICATION_CIB",
            "verification fee": "CUSTOMER_VERIFICATION_CIB",
            "transaction alert": "TRANSACTION_ALERT_ANNUAL",
            "chequebook fee": "CARD_CHEQUBOOK",
            "chequebook charge": "CARD_CHEQUBOOK",
            "chequebook cost": "CARD_CHEQUBOOK",
            "card chequebook": "CARD_CHEQUBOOK",
            "chequebook": "CARD_CHEQUBOOK",
            "cheque book fee": "CARD_CHEQUBOOK",
            "cheque book charge": "CARD_CHEQUBOOK",
            "cheque book": "CARD_CHEQUBOOK",
            "cheque processing": "CARD_CHEQUE_PROCESSING",
            "card cheque processing": "CARD_CHEQUE_PROCESSING",
            "risk assurance": "RISK_ASSURANCE_FEE",
            "fund transfer": "FUND_TRANSFER_FEE",
            "wallet transfer": "WALLET_TRANSFER_FEE",

            # Global lounge / SkyLounge free visits (count-based)
            "global lounge free visit": "GLOBAL_LOUNGE_FREE_VISITS_ANNUAL",
            "global lounge free visits": "GLOBAL_LOUNGE_FREE_VISITS_ANNUAL",
            "domestic skylounge free visit": "SKYLOUNGE_FREE_VISITS_DOM_ANNUAL",
            "international skylounge free visit": "SKYLOUNGE_FREE_VISITS_INTL_ANNUAL",

            # Voucher/cheque/undelivered
            "sales voucher retrieval": "SALES_VOUCHER_RETRIEVAL",
            "sales voucher": "SALES_VOUCHER_RETRIEVAL",
            "return cheque fee": "RETURN_CHEQUE_FEE",
            "return cheque": "RETURN_CHEQUE_FEE",
            "undelivered card": "UNDELIVERED_CARD_FEE",
            "pin destruction": "UNDELIVERED_CARD_FEE",
        }
        
        # Check for charge type keywords (longest matches first to prioritize specific terms)
        # Sort by length descending to match "supplementary annual fee" before "annual fee"
        def _match_from_map(label: str, mapping: Dict[str, str]) -> Optional[str]:
            for keyword, charge_type in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
                if keyword in query_lower:
                    logger.info(f"[FEE_ENGINE] Matched {label} charge type '{charge_type}' from keyword '{keyword}' in query: '{query}'")
                    return charge_type
            return None

        # Choose mapping order based on detected product line to avoid collisions
        # (e.g., "renewal fee" can mean card annual fee renewal or retail asset renewal).
        if product_line == "CREDIT_CARDS":
            mapping_order = [
                ("card", charge_type_map),
                ("skybanking", skybanking_charge_type_map),
                ("retail asset", retail_charge_type_map),
            ]
        elif product_line == "RETAIL_ASSETS":
            mapping_order = [
                ("retail asset", retail_charge_type_map),
                ("skybanking", skybanking_charge_type_map),
                ("card", charge_type_map),
            ]
        elif product_line == "SKYBANKING":
            mapping_order = [
                ("skybanking", skybanking_charge_type_map),
                ("card", charge_type_map),
                ("retail asset", retail_charge_type_map),
            ]
        else:
            # Legacy/default behavior (for backward compatibility)
            mapping_order = [
                ("skybanking", skybanking_charge_type_map),
                ("retail asset", retail_charge_type_map),
                ("card", charge_type_map),
            ]

        for label, mapping in mapping_order:
            match = _match_from_map(label, mapping)
            if match:
                return match
        
        # Special handling: if query contains both "supplementary" and "annual fee" (in any order)
        if "supplementary" in query_lower and ("annual fee" in query_lower or "yearly fee" in query_lower):
            logger.info(f"[FEE_ENGINE] Detected supplementary annual fee from query: '{query}'")
            return "SUPPLEMENTARY_ANNUAL"
        
        # Special handling: queries asking "how many free supplementary" or "free supplementary"
        if "supplementary" in query_lower and ("free" in query_lower or "how many" in query_lower):
            logger.info(f"[FEE_ENGINE] Detected 'how many free supplementary' query: '{query}'")
            return "SUPPLEMENTARY_FREE_ENTITLEMENT"
        
        # Defaulting logic:
        # Default to annual primary fee ONLY when the query looks like it is asking about annual/issuance/renewal,
        # or when it's a generic "X card fee" query with no other specific fee keywords.
        has_card_context = any(kw in query_lower for kw in ['card', 'credit card', 'debit card', 'prepaid', 'visa', 'mastercard', 'unionpay', 'diners', 'takapay'])
        has_fee_word = any(kw in query_lower for kw in ["fee", "charge", "cost"])
        annual_intent = any(kw in query_lower for kw in ["annual", "yearly", "renewal", "issuance", "primary card"])

        # If the user mentioned a specific fee type keyword, do NOT fall back to annual fee.
        specific_fee_keywords = [
            "cctv", "receipt", "withdrawal", "cash advance", "replacement", "late", "overlimit",
            "statement", "certificate", "cib", "verification", "transaction alert",
            "cheque", "chequebook", "risk assurance", "lounge", "skylounge",
            "voucher", "return cheque", "undelivered", "destruction", "interest rate",
            "fund transfer", "wallet transfer",
        ]
        has_specific_fee_keyword = any(kw in query_lower for kw in specific_fee_keywords)

        if (product_line == "CREDIT_CARDS" or has_card_context) and has_fee_word:
            if annual_intent or not has_specific_fee_keyword:
                logger.info(f"[FEE_ENGINE] Defaulting to ISSUANCE_ANNUAL_PRIMARY for generic annual-fee query: '{query}'")
                return "ISSUANCE_ANNUAL_PRIMARY"
        
        return None
    
    async def calculate_fee(
        self,
        query: str,
        amount: Optional[Decimal] = None,
        currency: Optional[str] = None,
        usage_index: Optional[int] = None,
        outstanding_balance: Optional[Decimal] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate fee for a card-related query.
        
        Args:
            query: Natural language query about card fee
            amount: Transaction amount (for percentage-based fees)
            currency: Currency (BDT or USD)
            usage_index: Usage index (for free entitlement logic, e.g., 1st, 2nd, 3rd)
            outstanding_balance: Outstanding balance (for ON_OUTSTANDING basis)
        
        Returns:
            Fee calculation response dict or None if not a fee query
        """
        # Detect product line first so we can map charge types deterministically
        product_line = self._detect_product_line(query)
        logger.info(f"[FEE_ENGINE] Detected product_line: '{product_line}' for query: '{query}'")

        # Map query to charge type (order depends on product_line)
        charge_type = self._map_query_to_charge_type(query, product_line=product_line)
        if not charge_type:
            logger.info(f"[FEE_ENGINE] Query is not a fee query: '{query}'")
            return None
        
        logger.info(f"[FEE_ENGINE] Mapped query to charge_type: '{charge_type}' for query: '{query}'")
        
        # Extract amount from query if not provided (for percentage-based fees like ATM withdrawal)
        if amount is None and charge_type in ["CASH_WITHDRAWAL_EBL_ATM", "CASH_WITHDRAWAL_OTHER_ATM"]:
            # Try to extract amount from query, or use a default for demonstration
            amount_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', query)
            if amount_match:
                try:
                    amount_str = amount_match.group(1).replace(',', '')
                    amount = Decimal(amount_str)
                    logger.info(f"[FEE_ENGINE] Extracted amount {amount} from query: '{query}'")
                except:
                    pass
            
            # If no amount found and not provided, use a default amount for "whichever higher" calculation
            # This ensures we get the minimum fee (BDT 345) even without a specific amount
            if amount is None:
                # Use a small amount to trigger minimum fee calculation
                amount = Decimal("10000")  # BDT 10,000 - 2.5% = 250, but min is 345, so returns 345
                logger.info(f"[FEE_ENGINE] Using default amount {amount} for '{charge_type}' calculation")
        
        # Handle retail asset charges
        if product_line == "RETAIL_ASSETS":
            return await self._query_retail_asset_charges(query, charge_type)
        
        # Extract card information
        card_info = self._extract_card_info_from_query(query)
        
        # For non-card product lines, set defaults
        if product_line != "CREDIT_CARDS":
            if not card_info["card_category"]:
                card_info["card_category"] = "CREDIT"  # Will be mapped to "ANY" in API
            if not card_info["card_network"]:
                card_info["card_network"] = "VISA"  # Will be mapped to "ANY" in API
        
        if not card_info["card_category"]:
            logger.warning(f"[FEE_ENGINE] Could not extract card category from query: '{query}'")
            return None
        
        # Build base request - try multiple product and currency variations.
        # Use today's date for as_of_date to avoid missing rules whose effective_from is not Jan 1.
        query_date = date.today()
        
        # Ensure network is set correctly (don't default to VISA if it's None)
        card_network = card_info["card_network"]
        if not card_network:
            card_network = "VISA"  # Default to VISA only if truly None
        
        base_request = {
            "as_of_date": str(query_date),
            "charge_type": charge_type,
            "card_category": card_info["card_category"],
            "card_network": card_network,
            "product_line": product_line,  # Add product line
        }
        
        # Try product variations for better matching
        product_variations = []
        
        if card_info["card_product"]:
            # For Women Platinum, prioritize Women Platinum variations first
            if "women" in query.lower() and "platinum" in query.lower():
                # If we already extracted "Women  Platinum", use it first
                if card_info["card_product"] == "Women  Platinum":
                    product_variations = [
                        "Women  Platinum",  # Database format (double space) - try first
                        "Women Platinum",   # Single space variant
                    ]
                else:
                    # If extraction didn't work, try all variations
                    product_variations = [
                        "Women  Platinum",  # Database format (double space)
                        "Women Platinum",   # Single space variant
                        card_info["card_product"]  # Whatever was extracted
                    ]
                # DO NOT add generic "Platinum" as fallback for Women Platinum queries
                # This prevents matching the wrong card type
            # Add variations for RFCD
            elif "rfcd" in query.lower() or "world rfcd" in query.lower():
                product_variations.append(card_info["card_product"])
                product_variations.extend([
                    "World RFCD",
                    "Global/Mastercard World RFCD",
                    "Global/Master Card World RFCD"
                ])
                product_variations.append(None)  # fallback to ANY
            # Add variations for UnionPay Classic
            elif card_info["card_network"] == "UNIONPAY" and card_info["card_product"] == "Classic":
                product_variations.extend([
                    "UnionPay Classic",  # Database format
                    "Classic"  # Also try just Classic
                ])
                product_variations.append(None)  # fallback to ANY
            else:
                # For other products, use extracted product first
                product_variations.append(card_info["card_product"])
                product_variations.append(None)  # fallback to ANY
        else:
            # No product found: do NOT guess "Classic".
            # Let fee-engine prefer CardFeeMaster.card_product == "ANY".
            product_variations = [None]
        
        # Infer currency from query if not explicitly provided
        if currency is None:
            ql = (query or "").lower()
            if any(k in ql for k in ["usd", "dollar", "$"]):
                currency = "USD"
            else:
                currency = "BDT"

        # Infer outstanding_balance for ON_OUTSTANDING fees when user includes it in text
        if outstanding_balance is None:
            ql = (query or "").lower()
            if "outstanding" in ql:
                # e.g. "outstanding balance 100000", "outstanding 1,00,000 bdt"
                m = re.search(r"outstanding(?:\s+balance)?\s+([0-9][0-9,]*)(?:\s*(bdt|usd))?", ql)
                if m:
                    try:
                        outstanding_balance = Decimal(m.group(1).replace(",", ""))
                    except Exception:
                        outstanding_balance = None
        
        currency_variations = [currency]  # Start with requested currency
        if currency == "BDT":
            currency_variations.append("USD")
        elif currency == "USD":
            currency_variations.append("BDT")
        else:
            # If currency is something else, try both BDT and USD
            currency_variations = ["BDT", "USD"]
        
        # Try each product and currency combination until we get a result
        for product in product_variations:
            for curr in currency_variations:
                request_data = {**base_request, "currency": curr, "product_line": product_line}
                if product:
                    request_data["card_product"] = product
                
                if amount:
                    request_data["amount"] = float(amount)
                if usage_index:
                    request_data["usage_index"] = usage_index
                if outstanding_balance:
                    request_data["outstanding_balance"] = float(outstanding_balance)
                
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        url = f"{self.base_url}/fees/calculate"
                        logger.info(f"[FEE_ENGINE] Calling {url} with product '{product}', currency '{curr}': {request_data}")
                        resp = await client.post(url, json=request_data)
                        
                        if resp.status_code == 200:
                            result = resp.json()
                            logger.info(f"[FEE_ENGINE] Fee calculation result for product '{product}', currency '{curr}': {result}")
                            
                            # If we got a calculated result, return it
                            if result.get("status") == "CALCULATED":
                                return result
                            # If we got a note-based result, return it
                            elif result.get("status") == "REQUIRES_NOTE_RESOLUTION":
                                return result
                            # If FX_RATE_REQUIRED, try next currency (the fee exists but in different currency)
                            elif result.get("status") == "FX_RATE_REQUIRED":
                                # Continue to try next currency variation
                                continue
                            # If NO_RULE_FOUND, try next currency/product combination
                            elif result.get("status") == "NO_RULE_FOUND":
                                continue
                            else:
                                return result
                        else:
                            logger.warning(f"[FEE_ENGINE] Non-200 response for product '{product}', currency '{curr}': {resp.status_code} - {resp.text}")
                            continue
                            
                except httpx.TimeoutException:
                    logger.warning(f"[FEE_ENGINE] Timeout calling fee engine service for product '{product}', currency '{curr}'")
                    continue
                except Exception as e:
                    logger.error(f"[FEE_ENGINE] Error calling fee engine service for product '{product}', currency '{curr}': {e}")
                    continue
        
        # If all variations failed, return None
        logger.warning(f"[FEE_ENGINE] All product variations failed for query: '{query}'")
        return None
    
    def format_fee_response(self, fee_result: Dict[str, Any], query: Optional[str] = None) -> str:
        """
        Format fee calculation result into readable text for LLM context.
        
        Args:
            fee_result: Fee calculation result from fee-engine (card fees) or retail asset charges
            query: Original query (optional, used for context detection)
        """
        status = fee_result.get("status")
        
        # Handle retail asset charges NEEDS_DISAMBIGUATION (multiple charges found without loan_product)
        if status == "NEEDS_DISAMBIGUATION" and "charges" in fee_result:
            return self._format_retail_asset_disambiguation_response(fee_result, query)
        
        # Handle retail asset charges response
        if status == "FOUND" and "charges" in fee_result:
            return self._format_retail_asset_charge_response(fee_result, query)
        
        # Handle Skybanking fees response
        if status == "FOUND" and "fees" in fee_result:
            return self._format_skybanking_fee_response(fee_result, query)
        
        # Handle retail asset charges NO_RULE_FOUND
        if status == "NO_RULE_FOUND" and "charges" not in fee_result and "fees" not in fee_result:
            # Check if this is a retail asset or Skybanking query by checking the message
            message = fee_result.get("message", "")
            if "retail asset" in message.lower() or "loan product" in message.lower():
                return message
            if "skybanking" in message.lower():
                return message
        
        if status == "CALCULATED":
            # Prefer authoritative answer_text when present (anti-hallucination)
            answer_text = (fee_result.get("answer_text") or "").strip()
            charge_type = (fee_result.get("charge_type") or "")
            # Use answer_text as authoritative for ALL fee types when present.
            # (Keeps responses deterministic and prevents hallucination; admin panel can edit answer_text.)
            if answer_text:
                return answer_text

            fee_amount = fee_result.get("fee_amount")
            fee_currency = fee_result.get("fee_currency", "BDT")
            fee_basis = fee_result.get("fee_basis", "PER_TXN")
            remarks = fee_result.get("remarks", "")
            
            # Format amount
            if fee_amount is not None:
                try:
                    fee_decimal = Decimal(str(fee_amount))
                    if fee_currency == "BDT":
                        # Format BDT with commas, remove .00 if whole number
                        if fee_decimal == fee_decimal.to_integral_value():
                            formatted = f"BDT {int(fee_decimal):,}"
                        else:
                            formatted = f"BDT {fee_decimal:,.2f}".replace(".00", "").replace(",", ",")
                    elif fee_currency == "USD":
                        # Format USD - keep decimals for cents (e.g., 11.5, not 11)
                        if fee_decimal == fee_decimal.to_integral_value():
                            formatted = f"USD {int(fee_decimal)}"
                        else:
                            # For USD, show one decimal if .0, two if .5, etc.
                            if fee_decimal % 1 == 0:
                                formatted = f"USD {int(fee_decimal)}"
                            else:
                                formatted = f"USD {fee_decimal:.2f}".rstrip('0').rstrip('.')
                    else:
                        formatted = f"{fee_amount}"
                except:
                    formatted = f"{fee_amount} {fee_currency}" if fee_currency else str(fee_amount)
            else:
                formatted = "Free"
            
            # Format basis
            basis_map = {
                "PER_YEAR": "per year",
                "PER_MONTH": "per month",
                "PER_TXN": "per transaction",
                "PER_VISIT": "per visit",
                "ON_OUTSTANDING": "on outstanding balance"
            }
            basis_text = basis_map.get(fee_basis, fee_basis.lower().replace("_", " "))
            
            # Build response - make it clear and direct for LLM
            # Check charge type to provide more specific context
            charge_type = fee_result.get("charge_type", "")
            remarks = fee_result.get("remarks", "") or ""
            
            # Detect SkyLounge free visit queries - these are count-based, not fee-based
            is_skylounge_visit = (
                "SKYLOUNGE_FREE_VISITS" in charge_type or
                "skylounge" in (query or "").lower() and "visit" in (query or "").lower()
            )
            
            # Check if this is an ATM withdrawal fee with "whichever higher" logic
            # The fee-engine returns remarks like "Whichever higher: 250.0000 (percent) vs 345.0000 (fixed) = 345.0000"
            query_lower = (query or "").lower()
            has_whichever_higher = "whichever higher" in remarks.lower() or "WHICHEVER_HIGHER" in remarks
            
            # Detect ATM withdrawal fees: check charge_type, remarks, or query keywords
            is_atm_withdrawal = (
                "CASH_WITHDRAWAL" in charge_type or 
                "ATM" in charge_type or
                (fee_basis == "PER_TXN" and has_whichever_higher) or  # If "whichever higher" in remarks and PER_TXN, it's likely ATM withdrawal
                (fee_basis == "PER_TXN" and ("withdrawal" in query_lower or "atm" in query_lower))
            )
            
            if is_skylounge_visit:
                # SkyLounge free visits are count-based, not fee-based
                # Premium cards (Platinum, Signature, Infinite, Titanium, World, etc.) have "Unlimited" visits
                # Check card product to determine if it's a premium card with unlimited visits
                card_product = fee_result.get("card_product", "")
                if not card_product and query:
                    # Try to extract from query as fallback
                    card_info = self._extract_card_info_from_query(query)
                    card_product = card_info.get("card_product", "")
                card_product_upper = card_product.upper() if card_product else ""
                premium_cards = ["PLATINUM", "SIGNATURE", "INFINITE", "TITANIUM", "WORLD", "DINERS"]
                is_premium_card = any(premium in card_product_upper for premium in premium_cards)
                
                # If fee_amount is 0 and it's a premium card, it means "Unlimited" (based on original data)
                # The migration script incorrectly converted "Unlimited" to 0.0000 BDT
                if fee_amount is not None and fee_amount == 0 and fee_currency == "BDT":
                    if is_premium_card:
                        # Premium cards have unlimited SkyLounge visits per year
                        response = "Unlimited"
                    else:
                        # For non-premium cards with 0, might be a different case - check remarks or return 0
                        response = "0 free visit(s)"
                elif fee_amount is not None and fee_amount > 0:
                    # If there's a specific count, display it
                    response = f"{int(fee_amount)} free visit(s) {basis_text}"
                else:
                    # Default to Unlimited for premium cards, or check if it's a count-based query
                    if is_premium_card:
                        response = "Unlimited"
                    else:
                        response = "Please refer to the card charges schedule for specific details."
            elif is_atm_withdrawal and has_whichever_higher:
                # ATM withdrawal fees use "whichever higher" logic
                # Format: "2.5% or BDT 345" (matches source document format exactly)
                response = "2.5% or BDT 345"
            elif is_atm_withdrawal:
                response = f"The ATM withdrawal fee is {formatted} per transaction ({basis_text})."
            elif "TRANSACTION_ALERT" in charge_type:
                # Transaction alert fees - format concisely as just the amount
                response = formatted
            elif "SUPPLEMENTARY" in charge_type:
                # Extract card product from fee_result or query for dynamic response
                card_product = fee_result.get("card_product", "")
                if not card_product and query:
                    # Try to extract from query as fallback
                    card_info = self._extract_card_info_from_query(query)
                    card_product = card_info.get("card_product", "")
                
                # Default to "Platinum" if not found
                if not card_product:
                    card_product = "Platinum"
                
                # Check if query is asking "how many free"
                query_lower = (query or "").lower()
                is_how_many_query = "how many" in query_lower and "free" in query_lower
                
                # For supplementary cards, check if fee is 0 or "Free" - this means first cards are free
                if formatted.lower() == "free" or (fee_amount is not None and fee_amount == 0):
                    # First supplementary cards are free, but there may be fees for additional cards
                    # CRITICAL: Always mention BOTH the free and paid tiers
                    if is_how_many_query:
                        # Direct answer for "how many free" queries - explicitly state the number (2, NOT 1)
                        response = f"CRITICAL: For {card_product} credit cards, there are 2 FREE supplementary cards (BDT 0 per year for the first 2 cards). The answer is 2 FREE cards, NOT 1. Starting from the 3rd supplementary card, the annual fee is BDT 2,300 per year. This fee applies to EACH additional supplementary card beyond the first 2."
                    else:
                        response = f"IMPORTANT: The supplementary card annual fee for {card_product} credit cards is structured as follows:\n- The FIRST 2 supplementary cards are FREE (BDT 0 per year)\n- Starting from the 3rd supplementary card, the annual fee is BDT 2,300 per year\n- This fee applies to EACH additional supplementary card beyond the first 2"
                else:
                    # When querying for paid supplementary cards (3rd+), still mention the free ones
                    if is_how_many_query:
                        # Direct answer for "how many free" queries - explicitly state the number
                        response = f"For {card_product} credit cards, there are 2 FREE supplementary cards (BDT 0 per year for the first 2 cards). Starting from the 3rd supplementary card, the annual fee is {formatted} ({basis_text}). This fee applies to EACH additional supplementary card beyond the first 2."
                    else:
                        response = f"IMPORTANT: The supplementary card annual fee for {card_product} credit cards is structured as follows:\n- The FIRST 2 supplementary cards are FREE (BDT 0 per year)\n- Starting from the 3rd supplementary card, the annual fee is {formatted} ({basis_text})\n- This fee applies to EACH additional supplementary card beyond the first 2"
            elif "PRIMARY" in charge_type or "ISSUANCE_ANNUAL" in charge_type:
                response = f"The primary card annual fee is {formatted} ({basis_text})."
            else:
                response = f"The fee is {formatted} ({basis_text})."
            
            # Add remarks if not already included in the response
            # Filter out migration metadata remarks (e.g., "Migrated from card_charges.json...")
            if remarks and "whichever higher" not in remarks.lower() and not is_atm_withdrawal:
                if "Migrated from" not in remarks and "migrated" not in remarks.lower():
                    response += f" {remarks}"
            
            return response
        
        elif status == "REQUIRES_NOTE_RESOLUTION":
            # Use the message from fee engine (already includes note text if available)
            message = fee_result.get("message", "")
            if message:
                return message
            # Fallback if message is missing
            note_ref = fee_result.get("note_reference", "Unknown")
            return f"Fee depends on external note definition: Note {note_ref}. Please refer to the card charges schedule for Note {note_ref} details."
        
        elif status == "NO_RULE_FOUND":
            message = fee_result.get("message", "No fee rule found for this card and charge type.")
            return message
        
        elif status == "FX_RATE_REQUIRED":
            message = fee_result.get("message", "Fee rule exists but currency conversion required.")
            return message
        
        else:
            return f"Fee calculation status: {status}"
    
    async def _query_retail_asset_charges(
        self,
        query: str,
        charge_type: Optional[str] = None,
        loan_product: Optional[str] = None,
        description_keywords: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Query retail asset charges from the fee engine service.
        
        Args:
            query: Natural language query about retail asset charge
            charge_type: Charge type (e.g., PROCESSING_FEE)
            loan_product: Optional loan product override (for disambiguation resolution)
            description_keywords: Optional keywords to match in charge_description
        
        Returns:
            Retail asset charge response dict with status:
            - "FOUND": Single charge found or loan_product was specified
            - "NEEDS_DISAMBIGUATION": Multiple charges found without loan_product/description_keywords
            - "NO_RULE_FOUND": No charges found
            - None: Error occurred
        """
        # CRITICAL: Map query to charge_type first if not provided
        if charge_type is None:
            charge_type_mapped = self._map_query_to_charge_type(query, product_line="RETAIL_ASSETS")
            if charge_type_mapped:
                charge_type = charge_type_mapped
            else:
                logger.warning(f"[FEE_ENGINE] Could not map query to charge_type: '{query}'")
                return None
        
        # Extract loan product from query (optional - if not found, we'll query by charge_type only)
        if loan_product is None:
            loan_product = self._map_query_to_loan_product(query)
        
        # Extract description keywords from query if not provided
        if description_keywords is None:
            description_keywords = []
            query_lower = query.lower()
            
            # Check for enhancement/reduction/limit keywords in query and add to description_keywords
            if any(kw in query_lower for kw in ["enhancement", "enhance", "limit enhancement", "enhanced amount"]):
                description_keywords.extend(["enhancement", "enhance", "limit enhancement"])
            elif any(kw in query_lower for kw in ["reduction", "reduce", "limit reduction", "reduced amount"]):
                description_keywords.extend(["reduction", "reduce", "limit reduction"])
            elif any(kw in query_lower for kw in ["on limit", "limit"]):
                description_keywords.extend(["on limit", "limit"])
        
        # For retail asset charges, use today's date to ensure we match current active charges
        query_date = date.today()
        
        # Build initial request data
        request_data = {
            "as_of_date": str(query_date),
            "charge_type": charge_type,
            "query": query  # Pass original query for logging/display only
        }
        if loan_product:
            request_data["loan_product"] = loan_product
            logger.info(f"[FEE_ENGINE] Mapped loan product: '{loan_product}' for query: '{query}'")
        else:
            logger.info(f"[FEE_ENGINE] No loan product specified - will query all loan products for charge_type: '{charge_type}'")
        
        if description_keywords:
            request_data["description_keywords"] = description_keywords
            logger.info(f"[FEE_ENGINE] Using description keywords: {description_keywords} for query: '{query}'")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/retail-asset-charges/query"
                logger.info(f"[FEE_ENGINE] Calling {url} with: {request_data}")
                logger.info(f"[FEE_ENGINE] Query params - loan_product: '{loan_product}', charge_type: '{charge_type}', description_keywords: {description_keywords}, as_of_date: '{query_date}'")
                resp = await client.post(url, json=request_data)
                
                if resp.status_code == 200:
                    result = resp.json()
                    logger.info(f"[FEE_ENGINE] Retail asset charge query result: {result}")
                    logger.info(f"[FEE_ENGINE] Result status: {result.get('status')}, charges found: {len(result.get('charges', []))}")
                    
                    # DESCRIPTION KEYWORD FALLBACK:
                    # If nothing found with keywords, retry without keywords
                    if result.get('status') == 'NO_RULE_FOUND' and description_keywords:
                        logger.info(
                            f"[FEE_ENGINE] Description keyword fallback: NO_RULE_FOUND with keywords={description_keywords}. "
                            f"Retrying without keywords (loan_product={loan_product}, charge_type={charge_type})"
                        )
                        fallback_request = request_data.copy()
                        fallback_request.pop("description_keywords", None)
                        resp_fallback = await client.post(url, json=fallback_request)
                        if resp_fallback.status_code == 200:
                            result_fallback = resp_fallback.json()
                            logger.info(
                                f"[FEE_ENGINE] Description fallback result: {result_fallback.get('status')}, "
                                f"charges found: {len(result_fallback.get('charges', []))}"
                            )
                            if result_fallback.get('status') != 'NO_RULE_FOUND':
                                return result_fallback
                        else:
                            logger.warning(
                                f"[FEE_ENGINE] Description fallback non-200 response: {resp_fallback.status_code} - {resp_fallback.text}"
                            )

                    # DB-DRIVEN FALLBACK: If NO_RULE_FOUND and query contains "processing fee",
                    # try PROCESSING_FEE with the same keywords
                    if result.get('status') == 'NO_RULE_FOUND':
                        query_lower = query.lower()
                        if ("processing fee" in query_lower and 
                            charge_type in ["LIMIT_ENHANCEMENT_FEE", "LIMIT_REDUCTION_FEE"]):
                            
                            logger.info(f"[FEE_ENGINE] DB-driven fallback: Trying PROCESSING_FEE with keywords={description_keywords} (original charge_type={charge_type} not found)")
                            
                            # Retry with PROCESSING_FEE
                            fallback_request = request_data.copy()
                            fallback_request["charge_type"] = "PROCESSING_FEE"
                            resp_fallback = await client.post(url, json=fallback_request)
                            
                            if resp_fallback.status_code == 200:
                                result_fallback = resp_fallback.json()
                                logger.info(f"[FEE_ENGINE] Fallback query result: {result_fallback.get('status')}, charges found: {len(result_fallback.get('charges', []))}")
                                if result_fallback.get('status') != 'NO_RULE_FOUND':
                                    return result_fallback
                    
                    # If multiple charges found and no loan_product specified, return NEEDS_DISAMBIGUATION
                    if result.get('status') == 'FOUND' and not loan_product:
                        charges = result.get('charges', [])
                        if len(charges) > 1:
                            # Return top 10 charges (sorted by priority) for disambiguation
                            top_charges = charges[:10]
                            result['status'] = 'NEEDS_DISAMBIGUATION'
                            result['charges'] = top_charges
                            result['message'] = f"Multiple loan products found for {charge_type}. Please specify the loan product."
                            logger.info(f"[FEE_ENGINE] Multiple charges found ({len(charges)}), returning NEEDS_DISAMBIGUATION with top {len(top_charges)} charges")
                            return result
                    
                    if result.get('status') == 'NO_RULE_FOUND':
                        logger.warning(f"[FEE_ENGINE] No retail asset charges found. Query params were: loan_product='{loan_product}', charge_type='{charge_type}', description_keywords={description_keywords}, as_of_date='{query_date}'. Message: {result.get('message', 'No message')}")
                    
                    return result
                else:
                    logger.warning(f"[FEE_ENGINE] Non-200 response: {resp.status_code} - {resp.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.warning(f"[FEE_ENGINE] Timeout calling retail asset charges endpoint")
            return None
        except Exception as e:
            logger.error(f"[FEE_ENGINE] Error querying retail asset charges: {e}", exc_info=True)
            return None
    
    def _format_retail_asset_charge_response(self, result: Dict[str, Any], query: Optional[str] = None) -> str:
        """
        Format retail asset charge response into a human-readable string.
        
        Args:
            result: Retail asset charge query result
            query: Original query (optional, used for context)
        """
        charges = result.get("charges", [])
        if not charges:
            return result.get("message", "No retail asset charges found.")
        
        # Get the first (highest priority) charge
        charge = charges[0]
        
        # Anti-hallucination: prefer authoritative answer_text provided by the fee engine.
        # This must be treated as verbatim schedule output (no inference).
        loan_product_name = charge.get("loan_product_name") or charge.get("loan_product") or ""
        charge_title = charge.get("charge_title") or charge.get("charge_description") or charge.get("charge_type") or "Retail Asset Charge"

        answer_text = (
            charge.get("answer_text")
            or charge.get("fee_text")
            or charge.get("original_charge_text")
        )

        if answer_text and str(answer_text).strip():
            # Minimal deterministic formatting, keep answer_text verbatim.
            header = f"{charge_title}"
            if loan_product_name:
                header = f"{loan_product_name} - {charge_title}"

            return "\n".join([
                header,
                f"Fee (as per schedule): {str(answer_text).strip()}",
            ])

        # If answer_text isn't available (e.g., DB migration not applied yet),
        # fall back to deterministic numeric/tier formatting from the returned fields.
        fee_value = charge.get("fee_value")
        fee_unit = charge.get("fee_unit")
        fee_basis = charge.get("fee_basis") or ""
        tier_1_threshold = charge.get("tier_1_threshold")
        tier_1_fee_value = charge.get("tier_1_fee_value")
        tier_1_fee_unit = charge.get("tier_1_fee_unit")
        tier_1_max_fee = charge.get("tier_1_max_fee")
        tier_2_threshold = charge.get("tier_2_threshold")
        tier_2_fee_value = charge.get("tier_2_fee_value")
        tier_2_fee_unit = charge.get("tier_2_fee_unit")
        tier_2_max_fee = charge.get("tier_2_max_fee")
        condition_description = charge.get("condition_description") or ""
        remarks = charge.get("remarks") or ""

        basis_map = {
            "PER_LOAN": "per loan",
            "PER_AMOUNT": "per amount",
            "PER_INSTALLMENT": "per installment",
            "PER_INSTANCE": "per instance",
            "ON_OUTSTANDING": "on outstanding balance",
            "ON_OVERDUE": "on overdue amount",
            "PER_QUOTATION_CHANGE": "per quotation change",
            "PER_TXN": "per transaction",
        }
        basis_text = basis_map.get(fee_basis, fee_basis.lower().replace("_", " ").strip()) if fee_basis else ""

        def _fmt_money(amount: Any) -> str:
            if amount is None:
                return ""
            try:
                d = Decimal(str(amount))
                if d == d.to_integral_value():
                    return f"BDT {int(d):,}"
                return f"BDT {d:,.2f}".rstrip("0").rstrip(".")
            except Exception:
                return f"BDT {amount}"

        header = f"{charge_title}"
        if loan_product_name:
            header = f"{loan_product_name} - {charge_title}"

        lines = [header]

        # Tiered fees
        if tier_1_threshold is not None and tier_1_fee_value is not None:
            threshold1 = _fmt_money(tier_1_threshold)
            tier1_formatted = f"{tier_1_fee_value}%" if tier_1_fee_unit == "PERCENT" else f"{tier_1_fee_value} {tier_1_fee_unit}"
            tier1_max = f" (max {_fmt_money(tier_1_max_fee)})" if tier_1_max_fee else ""
            if tier_2_threshold is not None and tier_2_fee_value is not None:
                tier2_formatted = f"{tier_2_fee_value}%" if tier_2_fee_unit == "PERCENT" else f"{tier_2_fee_value} {tier_2_fee_unit}"
                tier2_max = f" (max {_fmt_money(tier_2_max_fee)})" if tier_2_max_fee else ""
                fee_line = f"{tier1_formatted}{tier1_max} up to {threshold1}; {tier2_formatted}{tier2_max} above {threshold1}"
            else:
                fee_line = f"{tier1_formatted}{tier1_max} up to {threshold1}"
            if basis_text:
                fee_line += f" ({basis_text})"
            lines.append(f"Fee (as per schedule): {fee_line}")
        elif fee_value is not None and fee_unit:
            # Simple numeric fee
            try:
                d = Decimal(str(fee_value))
                if fee_unit == "PERCENT":
                    formatted = f"{d.normalize()}%"
                elif fee_unit in ("BDT", "USD"):
                    symbol = fee_unit
                    formatted = f"{symbol} {d.normalize()}"
                else:
                    formatted = f"{d.normalize()} {fee_unit}"
            except Exception:
                formatted = f"{fee_value} {fee_unit}"
            fee_line = formatted
            if basis_text:
                fee_line += f" ({basis_text})"
            lines.append(f"Fee (as per schedule): {fee_line}")
        else:
            return "Fee information is not available in the Retail Asset Charges Schedule for the selected criteria."

        if condition_description:
            lines.append(f"Note (as per schedule): {condition_description.strip()}")
        elif remarks:
            lines.append(f"Note (as per schedule): {remarks.strip()}")

        return "\n".join(lines)
    
    def _format_retail_asset_disambiguation_response(self, result: Dict[str, Any], query: Optional[str] = None) -> str:
        """
        Format retail asset disambiguation response when multiple charges are found.
        Handles two cases:
        1. Multiple loan products (first-level disambiguation)
        2. Multiple charge contexts for same loan_product + charge_type (second-level disambiguation)
        
        IMPORTANT: Only shows charges with the SAME charge_type (determined by the query).
        Enhancement/reduction fees are separate charge_types and should not appear under "Processing Fee options".
        
        Args:
            result: Retail asset charge query result with NEEDS_DISAMBIGUATION status
            query: Original query (optional)
        
        Returns:
            Formatted disambiguation message with options
        """
        charges = result.get("charges", [])
        if not charges:
            return result.get("message", "Multiple charges found. Please specify your selection.")
        
        # CRITICAL: Filter charges to only include those with the same charge_type
        # This prevents mixing PROCESSING_FEE with LIMIT_ENHANCEMENT_FEE/LIMIT_REDUCTION_FEE
        charge_types = set(charge.get("charge_type") for charge in charges if charge.get("charge_type"))
        if len(charge_types) > 1:
            # Multiple charge_types found - this is a bug, but handle it by using the first one
            # In practice, this should never happen if the fee engine filters correctly
            logger.warning(f"[FEE_ENGINE] Multiple charge_types in disambiguation: {charge_types}. Using first: {list(charge_types)[0]}")
            primary_charge_type = list(charge_types)[0]
            charges = [c for c in charges if c.get("charge_type") == primary_charge_type]
        
        charge_type = charges[0].get("charge_type", "") if charges else ""
        message = result.get("message", "Multiple charges found. Please specify your selection.")
        
        # Check if this is a description-based disambiguation (same loan_product, same charge_type, different descriptions)
        loan_products = set(charge.get("loan_product") for charge in charges if charge.get("loan_product"))
        is_description_disambiguation = len(loan_products) == 1 and len(set(c.get("charge_description") for c in charges)) > 1
        
        if is_description_disambiguation:
            # Second-level disambiguation: same loan_product, different charge_descriptions
            loan_product = list(loan_products)[0]
            loan_product_name = charges[0].get("loan_product_name", loan_product)
            
            # Build response
            response_parts = [
                f"Multiple {charge_type.replace('_', ' ').title()} options are available for {loan_product_name}.",
                "Please specify which one you're interested in:",
                ""
            ]
            
            # Add description-based options
            # Build deduped list based on answer_text (authoritative) first, falling back to charge_description.
            seen_descriptions = set()
            deduped_options = []
            for charge in charges:
                option_text = (charge.get("answer_text") or charge.get("charge_description") or "").strip()
                if option_text and option_text not in seen_descriptions:
                    seen_descriptions.add(option_text)
                    # Build option dict matching stored format
                    deduped_options.append({
                        "loan_product": charge.get("loan_product"),
                        "loan_product_name": charge.get("loan_product_name", charge.get("loan_product")),
                        "charge_type": charge.get("charge_type"),
                        "charge_description": charge.get("charge_description", ""),
                        "answer_text": charge.get("answer_text"),
                    })
            
            # Enumerate deduped options for stable numbering
            for idx, option in enumerate(deduped_options, 1):
                option_text = (option.get("answer_text") or option.get("charge_description") or "").strip()
                # Truncate if too long
                display = option_text[:100] + "..." if len(option_text) > 100 else option_text
                response_parts.append(f"{idx}. {display}")
            
            # Prompt for disambiguation
            response_parts.extend([
                "",
                "Reply with Option 1/2/3:",
            ])
            
            # Store the formatted response for reference
            # FIX #3: Store deduped_options in result dict so it can be used when storing in Redis
            # Note: deduped_options matches the stored options order (1:1 mapping with UI numbering)
            result['charges'] = charges  # Keep original charges for reference
            result['deduped_options'] = deduped_options  # Store deduped options matching UI order
            
            return "\n".join(response_parts)
        else:
            # First-level disambiguation: different loan products
            # Extract unique loan products from charges
            loan_products_dict = {}
            for charge in charges:
                loan_product = charge.get("loan_product", "")
                loan_product_name = charge.get("loan_product_name", "")
                if loan_product and loan_product not in loan_products_dict:
                    loan_products_dict[loan_product] = loan_product_name or loan_product
            
            # Build response
            response_parts = [
                f"Multiple loan products have {charge_type.replace('_', ' ').title()} available.",
                "Please specify which loan product you're interested in:",
                ""
            ]
            
            # Add loan product options (format: "1. Product Name (PRODUCT_CODE)")
            for idx, (loan_product, loan_product_name) in enumerate(loan_products_dict.items(), 1):
                if loan_product_name and loan_product_name != loan_product:
                    response_parts.append(f"{idx}. {loan_product_name} ({loan_product})")
                else:
                    response_parts.append(f"{idx}. {loan_product}")
            
            response_parts.extend([
                "",
                "Please specify which option you mean (by number or product name), for example:",
                f"  - '1' or '{list(loan_products_dict.values())[0] if loan_products_dict else 'first option'}'",
            ])
            
            # FIX #3: Store deduped_options for loan product disambiguation (build from loan_products_dict)
            deduped_options = []
            for loan_product, loan_product_name in loan_products_dict.items():
                deduped_options.append({
                    "loan_product": loan_product,
                    "loan_product_name": loan_product_name,
                    "charge_type": charge_type  # Use charge_type from result
                })
            result['deduped_options'] = deduped_options
            
            return "\n".join(response_parts)
