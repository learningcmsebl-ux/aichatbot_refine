"""
Charge Registry — single source of truth for all fee-schedule domain knowledge.

Why this exists
---------------
Previously, keyword→charge-type mappings were hardcoded in three separate files:
  • fee_engine_client.py  (charge type maps, product line keywords, card/loan product maps)
  • query_classifier.py   (routing keyword lists for fee intent detection)
  • handlers/disambiguation_handler.py (fee type labels)

Adding a new charge type (e.g., "VAT Recovery Fee") required touching all of them.

Now there is one file to update. Both fee_engine_client.py and query_classifier.py
import from here; the routing and resolution logic stays in those files.

Structure
---------
  Product-line detection       → CARD_CONTEXT_KEYWORDS, SKYBANKING_KEYWORDS, …
  Charge type maps             → CARD_CHARGE_TYPE_MAP, RETAIL_CHARGE_TYPE_MAP, SKYBANKING_CHARGE_TYPE_MAP
  Product name maps            → CARD_PRODUCT_MAP, LOAN_PRODUCT_MAP, SKYBANKING_PRODUCT_NAME_MAP
  Routing helpers              → RETAIL_ASSET_EXCLUSIVE_FEE_TERMS, RETAIL_ASSET_PRODUCT_KEYWORDS
"""

from __future__ import annotations
from typing import Dict, List

# ─────────────────────────────────────────────────────────────────────────────
# Product-line detection keywords
# Used by FeeEngineClient._detect_product_line()
# ─────────────────────────────────────────────────────────────────────────────

CARD_CONTEXT_KEYWORDS: List[str] = [
    "card", "credit card", "debit card", "prepaid",
    "visa", "mastercard", "unionpay", "diners", "takapay",
]

SKYBANKING_KEYWORDS: List[str] = [
    "skybanking", "sky banking", "digital banking",
    "online banking", "ebl skybanking", "skybanking app", "ebl app", "mobile app",
]

PRIORITY_BANKING_KEYWORDS: List[str] = [
    "priority banking", "priority customer", "priority account",
]

# Fee/charge names that exclusively belong to retail assets (no card context needed).
# These are present in both product-line detection AND routing keywords.
RETAIL_ASSET_EXCLUSIVE_CHARGE_NAMES: List[str] = [
    "stamp charge", "stamp duty",
    "reschedule", "restructure",
    "notarization fee", "noc fee", "loan repayment certificate",
    "loan outstanding certificate",
    "cib charge", "cib fee",
    "other charges", "other charge",
    "penal interest", "partial payment", "early settlement",
    "security replacement", "legal expense",
    "vetting", "valuation fee", "valuation charge",
    "vetting & valuation", "vetting and valuation",
    "insurance charge", "documentation charge",
]

# Retail asset product/loan keywords (without charge names).
RETAIL_ASSET_PRODUCT_KEYWORDS: List[str] = [
    "loan", "retail asset", "fast cash", "fast loan", "overdraft", "od",
    "personal loan", "home loan", "car loan",
    "business loan", "executive loan", "assure loan", "women's loan",
    "edu loan", "education loan", "auto loan",
    "loan processing", "emi loan", "secured loan", "unsecured loan",
]

# Combined: product-line detector uses both product keywords and charge names.
RETAIL_ASSET_CONTEXT_KEYWORDS: List[str] = (
    RETAIL_ASSET_PRODUCT_KEYWORDS + RETAIL_ASSET_EXCLUSIVE_CHARGE_NAMES
)

# Retail-asset-exclusive fee terms used by QueryClassifier to route to fee engine.
# Subset of RETAIL_ASSET_EXCLUSIVE_CHARGE_NAMES — only those that are unambiguously
# fee-schedule queries even without an explicit loan/product keyword in the query.
RETAIL_ASSET_EXCLUSIVE_FEE_TERMS: List[str] = [
    "partial payment fee", "partial payment",
    "early settlement fee", "early settlement", "early_settlement",
    "stamp charge", "stamp duty",
    "reschedule & restructure fee", "reschedule and restructure fee",
    "reschedule & restructure exit fee", "reschedule and restructure exit fee",
    "reschedule fee", "rescheduling fee",
    "restructure fee", "restructuring fee",
    "notarization fee", "noc fee", "loan repayment certificate",
    "loan outstanding certificate", "loan outstanding certificate fee",
    "cib charge", "cib fee", "other charges", "other charge",
]

# ─────────────────────────────────────────────────────────────────────────────
# Card product keyword map
# Used by FeeEngineClient._extract_card_info_from_query()
# ─────────────────────────────────────────────────────────────────────────────

CARD_PRODUCT_MAP: Dict[str, str] = {
    "world rfcd": "World RFCD",                                  # longest match first
    "global/mastercard world rfcd": "World RFCD",
    "global/master card world rfcd": "World RFCD",
    "women platinum": "Women Platinum",
    "women signature": "Signature Lite/Women Signature",
    "signature acci": "Signature Acci",
    "corporate platinum": "Corporate Platinum",
    "army/air force/ navy platinum": "Army/Air Force/ Navy Platinum",
    "army/air force/navy platinum": "Army/Air Force/ Navy Platinum",
    "navy platinum": "Army/Air Force/ Navy Platinum",
    "army platinum": "Army/Air Force/ Navy Platinum",
    "air force platinum": "Army/Air Force/ Navy Platinum",
    "signature lite": "Signature Lite/Women Signature",
    "priority signature": "Priority Signature",
    "mastercard women prepaid card": "Mastercard Women Prepaid Card",
    "payroll": "Payroll",
    "rfcd": "World RFCD",
    "unionpay classic": "UnionPay Classic",
    "union pay classic": "UnionPay Classic",
    "classic": "Classic",
    "gold": "Gold",
    "platinum": "Platinum",
    "signature": "Signature",
    "infinite": "Infinite",
    "titanium": "Titanium",
    "world": "World",
}

# ─────────────────────────────────────────────────────────────────────────────
# Loan product keyword map
# Used by FeeEngineClient._map_query_to_loan_product()
# ─────────────────────────────────────────────────────────────────────────────

LOAN_PRODUCT_MAP: Dict[str, str] = {
    "fast cash": "FAST_CASH_OD",
    "fast cash od": "FAST_CASH_OD",
    "fast cash overdraft": "FAST_CASH_OD",
    "fast loan": "FAST_LOAN_SECURED_EMI",
    "education loan": "EDU_LOAN_SECURED",
    "edu loan": "EDU_LOAN_SECURED",
    "personal loan": "EXECUTIVE_LOAN",
    "executive loan": "EXECUTIVE_LOAN",
    "executive": "EXECUTIVE_LOAN",
    "assure loan": "ASSURE_LOAN",
    "assure": "ASSURE_LOAN",
    "women's loan": "WOMENS_LOAN",
    "womens loan": "WOMENS_LOAN",
    "women loan": "WOMENS_LOAN",
    "auto loan": "AUTO_LOAN",
    "home loan": "HOME_LOAN",
    "car loan": "AUTO_LOAN",
    "other charges": "OTHER_CHARGES",
    "other charge": "OTHER_CHARGES",
}

# ─────────────────────────────────────────────────────────────────────────────
# Charge type maps — keyword (lower-cased) → charge_type enum value
#
# Ordering note: Each map is consumed sorted by key-length descending so that
# "supplementary annual fee" always wins over the shorter "annual fee".
# ─────────────────────────────────────────────────────────────────────────────

# Card fee charge types (CREDIT_CARDS / DEBIT_CARDS product line)
CARD_CHARGE_TYPE_MAP: Dict[str, str] = {
    # Supplementary cards — checked first (longest before general annual fee)
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
    "supplementary": "SUPPLEMENTARY_ANNUAL",
    "additional card fee": "SUPPLEMENTARY_ANNUAL",
    "additional card annual fee": "SUPPLEMENTARY_ANNUAL",

    # Annual fees (primary card)
    "annual fee": "ISSUANCE_ANNUAL_PRIMARY",
    "yearly fee": "ISSUANCE_ANNUAL_PRIMARY",
    "renewal fee": "ISSUANCE_ANNUAL_PRIMARY",
    "issuance fee": "ISSUANCE_ANNUAL_PRIMARY",
    "issuance charge": "ISSUANCE_ANNUAL_PRIMARY",
    "issuance cost": "ISSUANCE_ANNUAL_PRIMARY",
    "primary card fee": "ISSUANCE_ANNUAL_PRIMARY",
    "primary card annual fee": "ISSUANCE_ANNUAL_PRIMARY",

    # Replacement fees — longest/most-specific first
    "pin replacement fee": "PIN_REPLACEMENT",
    "pin replacement": "PIN_REPLACEMENT",
    "pin fee": "PIN_REPLACEMENT",
    "card replacement fee": "CARD_REPLACEMENT",
    "replacement fee": "CARD_REPLACEMENT",
    "card replacement": "CARD_REPLACEMENT",

    # Payment fees
    "late payment": "LATE_PAYMENT",
    "late fee": "LATE_PAYMENT",

    # ATM/cash withdrawal — more specific before generic
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
    "cctv footage": "ATM_CCTV_FOOTAGE_INSIDE_DHAKA",
    "atm cctv footage": "ATM_CCTV_FOOTAGE_INSIDE_DHAKA",

    # Lounge access
    "lounge access": "GLOBAL_LOUNGE_ACCESS_FEE",
    "lounge fee": "GLOBAL_LOUNGE_ACCESS_FEE",
    "sky lounge": "GLOBAL_LOUNGE_ACCESS_FEE",
    "airport lounge": "GLOBAL_LOUNGE_ACCESS_FEE",

    # Payment / FX rates
    "all card related payment": "ALL_CARD_RELATED_PAYMENT",
    "card related payment": "ALL_CARD_RELATED_PAYMENT",
    "payment rate": "ALL_CARD_RELATED_PAYMENT",
    "refund rate": "ALL_CARD_RELATED_PAYMENT",

    # Priority banking
    "fcy endorsement": "FCY_ENDORSEMENT_FEE",
    "foreign currency endorsement": "FCY_ENDORSEMENT_FEE",
    "endorsement fee": "FCY_ENDORSEMENT_FEE",

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
    "customer verification/cib fee": "CUSTOMER_VERIFICATION_CIB",
    "customer verification cib fee": "CUSTOMER_VERIFICATION_CIB",
    "cib verification fee": "CUSTOMER_VERIFICATION_CIB",
    "cib verification": "CUSTOMER_VERIFICATION_CIB",
    "customer verification fee": "CUSTOMER_VERIFICATION_CIB",
    "credit card cib verification fee": "CUSTOMER_VERIFICATION_CIB",
    "credit card cib verification": "CUSTOMER_VERIFICATION_CIB",
    "cib verification fee for credit card": "CUSTOMER_VERIFICATION_CIB",
    "cib charge for credit card": "CUSTOMER_VERIFICATION_CIB",
    "credit card cib charge": "CUSTOMER_VERIFICATION_CIB",
    "credit card cib fee": "CUSTOMER_VERIFICATION_CIB",
    "cib charge for card": "CUSTOMER_VERIFICATION_CIB",
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

    # Global lounge / SkyLounge free-visit counts
    "global lounge free visit": "GLOBAL_LOUNGE_FREE_VISITS_ANNUAL",
    "global lounge free visits": "GLOBAL_LOUNGE_FREE_VISITS_ANNUAL",
    "domestic skylounge free visit": "SKYLOUNGE_FREE_VISITS_DOM_ANNUAL",
    "international skylounge free visit": "SKYLOUNGE_FREE_VISITS_INTL_ANNUAL",

    # Voucher / cheque / undelivered
    "sales voucher retrieval": "SALES_VOUCHER_RETRIEVAL",
    "sales voucher": "SALES_VOUCHER_RETRIEVAL",
    "return cheque fee": "RETURN_CHEQUE_FEE",
    "return cheque": "RETURN_CHEQUE_FEE",
    "undelivered card": "UNDELIVERED_CARD_FEE",
    "pin destruction": "UNDELIVERED_CARD_FEE",
}

# Retail asset charge types (RETAIL_ASSETS product line)
#
# DATA MODEL INVARIANT (confirmed 2025-12-30):
# All enhancement/reduction processing fees use PROCESSING_FEE + charge_context,
# NOT separate LIMIT_ENHANCEMENT_FEE/LIMIT_REDUCTION_FEE charge_types.
RETAIL_CHARGE_TYPE_MAP: Dict[str, str] = {
    # Processing fees (context determined by charge_context field)
    "processing_fee": "PROCESSING_FEE",
    "fast cash limit enhancement processing fee": "PROCESSING_FEE",
    "fast cash limit reduction processing fee": "PROCESSING_FEE",
    "limit enhancement processing fee": "PROCESSING_FEE",
    "limit reduction processing fee": "PROCESSING_FEE",
    "fast cash processing fee": "PROCESSING_FEE",
    "processing fee": "PROCESSING_FEE",

    # Standalone limit enhancement/reduction fees (future-compat; not currently used)
    "limit enhancement fee": "LIMIT_ENHANCEMENT_FEE",
    "limit reduction fee": "LIMIT_REDUCTION_FEE",

    # Other fees
    "limit cancellation fee": "LIMIT_CANCELLATION_FEE",
    "closing fee": "LIMIT_CANCELLATION_FEE",
    "renewal fee": "RENEWAL_FEE",
    "partial_payment_fee": "PARTIAL_PAYMENT_FEE",
    "partial payment fee": "PARTIAL_PAYMENT_FEE",
    "early settlement fee": "EARLY_SETTLEMENT_FEE",
    "early_settlement_fee": "EARLY_SETTLEMENT_FEE",
    "early settlement": "EARLY_SETTLEMENT_FEE",
    "settlement fee": "EARLY_SETTLEMENT_FEE",
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
    "stamp duty": "STAMP_CHARGE",
    "stamp charge": "STAMP_CHARGE",
    "loan outstanding certificate fee": "LOAN_OUTSTANDING_CERTIFICATE_FEE",
    "loan outstanding certificate": "LOAN_OUTSTANDING_CERTIFICATE_FEE",
    "outstanding certificate fee": "LOAN_OUTSTANDING_CERTIFICATE_FEE",
    # Reschedule / restructure fees
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

# Skybanking service charge types
SKYBANKING_CHARGE_TYPE_MAP: Dict[str, str] = {
    "add money fee": "Add Money Fee",
    "add money": "Add Money Fee",
    "annual service fee": "Annual Service Fee",
    "bill payment": "Bill Payment",
    "certificate fee": "Certificate Fee",
    "balance certificate fee": "Certificate Fee",
    "balance certificate": "Certificate Fee",
    "fund transfer": "Fund Transfer",
    "fund transfer fee": "Fund Transfer",
    "government payment": "Government Payment",
    "government payment fee": "Government Payment",
    "a challan fee": "Government Payment",
    "a challan": "Government Payment",
    "a-challan fee": "Government Payment",
    "a-challan": "Government Payment",
    "achallan fee": "Government Payment",
    "achallan": "Government Payment",
    "challan fee": "Government Payment",
    "challan": "Government Payment",
    "service charge": "Service Charge",
    "duplicate pin charge": "Service Charge",
    "duplicate pin": "Service Charge",
    "statement / certificate fee": "Service Charge",
    "statement certificate fee": "Service Charge",
    "statement fee": "Service Charge",
    # Backward-compat / generic
    "account certificate fee": "Certificate Fee",
    "transfer fee": "Fund Transfer",
    "transaction fee": "Service Charge",
    "skybanking fee": "Service Charge",
}

# ─────────────────────────────────────────────────────────────────────────────
# Skybanking product name map
# Used by FeeEngineClient._extract_skybanking_product_name()
# Maps query keywords → exact product_name values in the database.
# ─────────────────────────────────────────────────────────────────────────────

SKYBANKING_PRODUCT_NAME_MAP: Dict[str, str] = {
    "add money fee": "Add Money Fee",
    "add money": "Add Money Fee",
    "annual service fee": "Skybanking Service Annual Fee",
    "service annual fee": "Skybanking Service Annual Fee",
    "skybanking service annual fee": "Skybanking Service Annual Fee",
    "visa credit card bill payment": "VISA Credit Card Bill Payment",
    "credit card bill payment": "VISA Credit Card Bill Payment",
    "visa bill payment": "VISA Credit Card Bill Payment",
    "bill payment fee": "VISA Credit Card Bill Payment",
    "account certificate": "Account Certificate",
    "balance certificate": "Balance Certificate",
    "dps certificate": "DPS Certificate",
    "loan outstanding certificate": "Loan Outstanding Certificate",
    "outstanding certificate": "Loan Outstanding Certificate",
    "loan tax certificate": "Loan Tax Certificate",
    "tax certificate": "Loan Tax Certificate",
    "noc against loan": "NOC Against Loan",
    "noc certificate": "NOC Against Loan",
    "a challan fee": "A challan fee",
    "a challan": "A challan fee",
    "a-challan fee": "A challan fee",
    "a-challan": "A challan fee",
    "achallan fee": "A challan fee",
    "achallan": "A challan fee",
    "challan fee": "A challan fee",
    "challan": "A challan fee",
    "npsb fund transfer": "NPSB Fund Transfer",
    "npsb transfer": "NPSB Fund Transfer",
    "npsb": "NPSB Fund Transfer",
    "rtgs fund transfer": "RTGS Fund Transfer",
    "rtgs transfer": "RTGS Fund Transfer",
    "rtgs": "RTGS Fund Transfer",
    "binimoy fund transfer": "Binimoy Fund Transfer (Bank to Bank)",
    "binimoy transfer": "Binimoy Fund Transfer (Bank to Bank)",
    "binimoy": "Binimoy Fund Transfer (Bank to Bank)",
    "binomoy fund transfer": "Binimoy Fund Transfer (Bank to Bank)",
    "binomoy transfer": "Binimoy Fund Transfer (Bank to Bank)",
    "binomoy": "Binimoy Fund Transfer (Bank to Bank)",
    "duplicate pin charge": "Duplicate PIN Charge",
    "duplicate pin": "Duplicate PIN Charge",
    "statement / certificate fee": "Statement / Certificate Fee",
    "statement certificate fee": "Statement / Certificate Fee",
    "statement fee": "Statement / Certificate Fee",
}
