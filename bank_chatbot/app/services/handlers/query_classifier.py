"""
Query Classifier - Classifies queries into categories.

Extracted from ChatOrchestrator to address the God Object anti-pattern.
This class is responsible for determining the type/category of a user query.
"""

import re
import logging
from typing import Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Enumeration of query types for routing."""
    SMALL_TALK = "small_talk"
    DATETIME = "datetime"
    CONTACT_INFO = "contact_info"
    PHONEBOOK = "phonebook"
    EMPLOYEE = "employee"
    FINANCIAL_REPORT = "financial_report"
    USER_DOCUMENT = "user_document"
    ORGANIZATIONAL_OVERVIEW = "organizational_overview"
    MANAGEMENT = "management"
    MILESTONE = "milestone"
    FEE_SCHEDULE = "fee_schedule"
    RETAIL_ASSET_FEE = "retail_asset_fee"
    SKYBANKING_FEE = "skybanking_fee"
    CARD_RATES = "card_rates"
    LOCATION = "location"
    COMPLIANCE = "compliance"
    BANKING_PRODUCT = "banking_product"
    LOAN_PRODUCT_LINE = "loan_product_line"
    GENERAL = "general"


class QueryClassifier:
    """
    Classifies user queries into categories for routing.
    
    This class extracts all _is_*_query methods from ChatOrchestrator
    into a focused, single-responsibility class.
    
    Usage:
        classifier = QueryClassifier()
        query_type = classifier.classify("What is the annual fee for Platinum card?")
        # Returns QueryType.FEE_SCHEDULE
        
        # Or check specific types
        if classifier.is_fee_schedule_query("annual fee for card"):
            # Handle fee query
    """
    
    def __init__(self, location_intent_getter=None):
        """
        Initialize QueryClassifier.
        
        Args:
            location_intent_getter: Optional function to get location intent flags.
                                   If not provided, will import from location_intent module.
        """
        if location_intent_getter:
            self._get_location_intent_flags = location_intent_getter
        else:
            from app.services.location_intent import get_location_intent_flags
            self._get_location_intent_flags = get_location_intent_flags
    
    def classify(self, query: str) -> QueryType:
        """
        Classify a query into a QueryType.
        
        Returns the most specific matching QueryType, checking in priority order.
        
        Args:
            query: The user's query string
            
        Returns:
            QueryType enum value indicating the query category
        """
        # Priority order matters - check more specific types first
        
        # 1. Small talk (greetings, thanks)
        if self.is_small_talk(query):
            return QueryType.SMALL_TALK
        
        # 2. Date/time queries
        if self.is_datetime_query(query):
            return QueryType.DATETIME
        
        # 3. Contact/phonebook queries
        if self.is_contact_info_query(query):
            return QueryType.CONTACT_INFO
        
        if self.is_phonebook_query(query):
            return QueryType.PHONEBOOK
        
        if self.is_employee_query(query):
            return QueryType.EMPLOYEE
        
        # 4. Location queries
        if self.is_location_query(query):
            return QueryType.LOCATION
        
        # 5. Fee queries (check order matters)
        if self.is_retail_asset_fee_query(query):
            return QueryType.RETAIL_ASSET_FEE
        
        if self.is_skybanking_fee_query(query):
            return QueryType.SKYBANKING_FEE
        
        if self.is_fee_schedule_query(query):
            return QueryType.FEE_SCHEDULE
        
        # 6. Organizational queries
        if self.is_organizational_overview_query(query):
            return QueryType.ORGANIZATIONAL_OVERVIEW
        
        if self.is_management_query(query):
            return QueryType.MANAGEMENT
        
        if self.is_milestone_query(query):
            return QueryType.MILESTONE
        
        # 7. Product queries
        if self.is_banking_product_query(query):
            return QueryType.BANKING_PRODUCT
        
        if self.is_broad_loan_product_line_query(query):
            return QueryType.LOAN_PRODUCT_LINE
        
        # 8. Document queries
        if self.is_financial_report_query(query):
            return QueryType.FINANCIAL_REPORT
        
        if self.is_user_document_query(query):
            return QueryType.USER_DOCUMENT
        
        # 9. Compliance queries
        if self.is_compliance_query(query):
            return QueryType.COMPLIANCE
        
        # Default
        return QueryType.GENERAL
    
    def is_small_talk(self, query: str) -> bool:
        """Detect if query is small talk (greetings, thanks, etc.)"""
        query_lower = query.lower().strip()
        
        # CRITICAL: Contact/phonebook keywords override - never treat as small talk
        contact_keywords = [
            'phone', 'telephone', 'tel', 'call', 'contact', 'number', 'phone number',
            'mobile', 'cell', 'email', 'address', 'extension', 'ext', 'pabx', 'ip phone',
            'employee', 'staff', 'emp id', 'who is', 'who are', 'who works',
            'designation', 'department', 'manager', 'director', 'head of'
        ]
        
        if any(keyword in query_lower for keyword in contact_keywords):
            return False
        
        # Banking keywords override - never treat as small talk
        banking_keywords = [
            "loan", "card", "account", "balance", "deposit", "withdrawal",
            "interest", "rate", "fee", "service", "product", "banking",
            "credit", "debit", "transaction", "statement", "minimum", "maximum"
        ]
        
        if any(keyword in query_lower for keyword in banking_keywords):
            return False
        
        # Small talk patterns
        small_talk_phrases = [
            "good morning", "good afternoon", "good evening",
            "how are you", "how's it going", "what's up",
            "thank you", "appreciate it",
            "see you",
            "what are you", "who are you", "what can you do",
        ]
        if any(phrase in query_lower for phrase in small_talk_phrases):
            return True

        small_talk_words = ["hi", "hello", "hey", "thanks", "bye", "goodbye", "farewell"]
        return any(re.search(rf"\\b{re.escape(w)}\\b", query_lower) for w in small_talk_words)
    
    def is_datetime_query(self, query: str) -> bool:
        """Detect if query is asking about date or time"""
        query_lower = query.lower().strip()
        
        datetime_keywords = [
            "date", "time", "what time", "what date", "current time", "current date",
            "today", "now", "what day", "what is the time", "what is the date",
            "tell me the time", "tell me the date", "time now", "date today"
        ]
        
        return any(keyword in query_lower for keyword in datetime_keywords)
    
    def is_contact_info_query(self, query: str) -> bool:
        """Detect if query is about contact information (phone number or email)"""
        query_lower = query.lower().strip()
        
        # Exclude queries about email processes/policies
        email_process_keywords = [
            'email confirmation', 'email verification', 'email requirement',
            'email required', 'email process', 'email policy', 'email procedure',
            'email workflow', 'email approval', 'email notification',
            'send email', 'email sent', 'email received', 'email delivery',
            'email template', 'email format', 'email content',
            'prior email confirmation', 'prior confirmation', 'subject to prior',
            'subject to email', 'processing subject to', 'confirmation required',
            'prior email', 'email prior'
        ]
        
        if any(keyword in query_lower for keyword in email_process_keywords):
            return False
        
        # Contact patterns
        contact_patterns = [
            r'\bphone number\b', r'\btelephone number\b', r'\bcontact number\b',
            r'\bmobile number\b', r'\bcell number\b', r'\bphone\b', r'\btelephone\b',
            r'\bmobile\b', r'\bcell\b', r'\bcellphone\b', r'\btel\b', r'\bcall\b',
            r'\bpabx\b', r'\bextension\b', r'\bext\b', r'\bip phone\b', r'\bip phone number\b',
            r'\bdirect line\b', r'\bdirect number\b', r'\blandline\b',
            r'\bemail address of\b', r'\bemail of\b', r'\bemail for\b', r'\bemail id of\b',
            r'\bemail id for\b', r'\bmail address of\b', r'\bmail address for\b',
            r'\bwhat is the email\b', r'\bwhat is email\b', r'\bget email\b',
            r'\bfind email\b', r'\bcontact email\b', r'\bemail contact\b'
        ]
        
        return any(re.search(pattern, query_lower) for pattern in contact_patterns)
    
    def is_phonebook_query(self, query: str) -> bool:
        """Detect if query is about phone book directory"""
        query_lower = query.lower().strip()
        
        phonebook_keywords = [
            'phonebook', 'phone book', 'employee directory', 'staff directory',
            'contact list', 'employee list', 'staff list', 'directory'
        ]
        
        return any(keyword in query_lower for keyword in phonebook_keywords)
    
    def is_employee_query(self, query: str) -> bool:
        """Detect if query is about employee information (for phonebook lookup)"""
        query_lower = query.lower().strip()

        # Guardrail: Staffing/manpower requirement questions are NOT phonebook lookups
        staffing_intent_keywords = [
            "required", "requirement", "requirements", "needed", "need", "minimum",
            "manpower", "headcount", "personnel",
        ]
        staffing_count_keywords = ["how many", "number of", "count of"]
        outlet_context_keywords = [
            "agent", "agent outlet", "outlet", "booth", "counter", "branch", "service point"
        ]
        ops_context_keywords = [
            "customer service", "cash transaction", "cash transactions", 
            "cash withdrawal", "cash deposit"
        ]
        
        if (
            ("staff" in query_lower or any(k in query_lower for k in ["manpower", "headcount", "personnel"]))
            and any(k in query_lower for k in staffing_count_keywords)
            and any(k in query_lower for k in staffing_intent_keywords)
            and (any(k in query_lower for k in outlet_context_keywords) or 
                 any(k in query_lower for k in ops_context_keywords))
        ):
            logger.info(f"[ROUTING] Staffing requirement query detected - NOT routing to phonebook: '{query}'")
            return False
        
        # Pattern: "find" or "search" followed by employee ID pattern
        find_search_patterns = [
            r'\b(find|search|lookup|contact|info about)\s+([a-z0-9_]+)',
            r'\b(who is)\s+([a-z0-9_]+)',
        ]
        for pattern in find_search_patterns:
            match = re.search(pattern, query_lower)
            if match:
                search_term = match.group(2) if len(match.groups()) >= 2 else ""
                if search_term and len(search_term) >= 3:
                    if '_' in search_term or re.match(r'^[a-z0-9]+$', search_term):
                        logger.info(f"[ROUTING] Detected find/search query with employee ID/name pattern '{search_term}' → phonebook")
                        return True
        
        # Pattern: "who is" + role/designation queries
        who_is_patterns = [
            r'who\s+is\s+(the\s+)?(branch\s+)?manager',
            r'who\s+is\s+(the\s+)?(.*\s+)?manager\s+of',
            r'who\s+is\s+the\s+(.*\s+)?manager',
            r'who\s+is\s+(the\s+)?(head|director|officer|executive)\s+of',
            r'who\s+is\s+(the\s+)?(.*\s+)?(head|director|officer|executive)',
        ]
        if any(re.search(pattern, query_lower) for pattern in who_is_patterns):
            logger.info(f"[ROUTING] Detected 'who is' role query → phonebook")
            return True
        
        # Pattern: Role + "of" + location/branch
        role_location_patterns = [
            r'(branch\s+)?manager\s+of',
            r'manager\s+of\s+(.*\s+)?branch',
            r'(head|director|officer)\s+of\s+(.*\s+)?branch',
            r'(.*\s+)?manager\s+at\s+(.*\s+)?branch',
        ]
        if any(re.search(pattern, query_lower) for pattern in role_location_patterns):
            logger.info(f"[ROUTING] Detected role + location query → phonebook")
            return True
        
        # Specific employee search keywords
        employee_keywords = [
            'employee id', 'employee number', 'emp id', 'emp_id',
            'employee phone', 'employee email', 'employee contact',
            'staff phone', 'staff email', 'staff contact',
            'who is employee', 'who are employees', 'find employee',
            'search employee', 'lookup employee', 'employee directory',
            'staff directory', 'employee list', 'staff list'
        ]
        
        # "employee" or "staff" combined with contact-related terms
        if 'employee' in query_lower or 'staff' in query_lower:
            contact_terms = ['phone', 'email', 'contact', 'number', 'id', 'search', 'find', 'lookup', 'who']
            if any(term in query_lower for term in contact_terms):
                return True
        
        return any(keyword in query_lower for keyword in employee_keywords)
    
    def is_financial_report_query(self, query: str) -> bool:
        """Detect if query is about financial reports"""
        query_lower = query.lower().strip()
        
        financial_keywords = [
            'financial report', 'annual report', 'quarterly report', 'financial statement',
            'revenue', 'profit', 'loss', 'income statement', 'balance sheet',
            'cash flow', 'earnings', 'dividend', 'financial year', 'fiscal year',
            'audit', 'auditor', 'financial performance', 'financial results',
            'quarterly results', 'annual results', 'financial data', 'financial metrics'
        ]
        
        return any(keyword in query_lower for keyword in financial_keywords)
    
    def is_user_document_query(self, query: str) -> bool:
        """Detect if query is about user-uploaded documents"""
        query_lower = query.lower().strip()
        
        user_doc_keywords = [
            'user document', 'uploaded document', 'custom document', 'my document',
            'document i uploaded', 'document i provided', 'my file', 'uploaded file',
            'custom file', 'user file', 'personal document', 'my upload'
        ]
        
        return any(keyword in query_lower for keyword in user_doc_keywords)
    
    def is_organizational_overview_query(self, query: str) -> bool:
        """Detect if query is asking for high-level organizational overview about EBL"""
        query_lower = query.lower().strip()
        
        overview_patterns = [
            (r'tell\s+me\s+about\s+(ebl|eastern\s+bank)', 'tell me about EBL/Eastern Bank'),
            (r'what\s+is\s+(ebl|eastern\s+bank)', 'what is EBL/Eastern Bank'),
            (r'^about\s+(ebl|eastern\s+bank)', 'about EBL/Eastern Bank'),
            (r'who\s+is\s+(ebl|eastern\s+bank)', 'who is EBL/Eastern Bank'),
            (r'describe\s+(ebl|eastern\s+bank)', 'describe EBL/Eastern Bank'),
        ]
        
        for pattern, description in overview_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"[ROUTING] Detected organizational overview query: '{description}'")
                return True
        
        return False
    
    def is_management_query(self, query: str) -> bool:
        """Detect if query is about EBL management/management committee"""
        query_lower = query.lower().strip()
        
        management_keywords = [
            'management', 'management committee', 'mancom', 'managing director',
            'md and ceo', 'deputy managing director', 'chief financial officer', 'cfo',
            'chief technology officer', 'cto', 'chief risk officer', 'cro',
            'head of', 'unit head', 'executive committee', 'management team',
            'who is the managing director', 'who is the cfo', 'who is the cto',
            'management structure', 'organizational structure', 'management hierarchy',
            'ebl management', 'ebl executives', 'bank management', 'leadership team'
        ]
        
        return any(keyword in query_lower for keyword in management_keywords)
    
    def is_milestone_query(self, query: str) -> bool:
        """Detect if query is about EBL milestones/history/achievements"""
        query_lower = query.lower().strip()
        query_normalized = query_lower.replace('mile stone', 'milestone').replace('mile-stone', 'milestone')
        
        # Check organizational overview first
        if self.is_organizational_overview_query(query):
            return False
        
        milestone_keywords = [
            'milestone', 'milestones', 'history', 'historical', 'achievement', 'achievements',
            'timeline', 'journey', 'evolution', 'development', 'growth', 'progress',
            'founded', 'establishment', 'established', 'inception', 'origin', 'beginnings',
            'ebl milestone', 'ebl milestones', 'ebl history', 'bank milestone', 'bank milestones',
            'what are the milestones', 'ebl achievements',
            'bank achievements', 'company history', 'bank history', 'corporate history'
        ]
        
        return any(keyword in query_normalized for keyword in milestone_keywords)
    
    def is_fee_schedule_query(self, query: str) -> bool:
        """
        STRONG detector for fee/charge schedule queries (card fees).
        EXCLUDES: Retail asset charges and Skybanking fees.
        """
        query_lower = query.lower().strip()

        # Guardrail: Skybanking fee queries
        skybanking_keywords = [
            "skybanking", "sky banking", "ebl skybanking",
            "digital banking", "mobile banking", "online banking",
            "skybanking app", "ebl app", "mobile app"
        ]
        if any(kw in query_lower for kw in skybanking_keywords):
            return False
        
        # Guardrail: Transaction-limit queries
        limit_intent_keywords = [
            "maximum number", "max number", "how many", "number of",
            "limit", "limits", "allowed", "permit", "per day", "daily", "in a day",
        ]
        transaction_words = ["transaction", "transactions", "cash withdrawal", "withdrawal", "deposit"]
        account_words = ["savings account", "current account", "account"]
        fee_intent_words = ["fee", "fees", "charge", "charges", "rate", "pricing", "price", "cost", "commission"]

        if (
            any(k in query_lower for k in limit_intent_keywords)
            and any(w in query_lower for w in transaction_words)
            and any(w in query_lower for w in account_words)
            and not any(w in query_lower for w in fee_intent_words)
        ):
            return False

        # Guardrail: Payroll banking queries
        if ("payroll" in query_lower and "category" in query_lower) or "payroll banking" in query_lower:
            if any(k in query_lower for k in ["issuance fee", "debit card issuance", "debit card", "coverage", "eligibility", "criteria"]):
                return False
        
        # EXCLUDE retail asset/loan queries
        retail_asset_keywords = [
            "fast cash", "fast loan", "education loan", "edu loan",
            "personal loan", "home loan", "car loan", "auto loan",
            "business loan", "executive loan", "assure loan", "women's loan",
            "retail asset", "loan processing", "loan fee", "loan charge",
            "overdraft", "od", "emi loan", "secured loan", "unsecured loan",
            "cib charge", "cib fee", "other charges", "other charge"
        ]
        
        if any(kw in query_lower for kw in retail_asset_keywords):
            return False
        
        # Card-related context keywords
        card_context_keywords = [
            "card", "atm", "lounge", "supplementary", "pin", "rfcd",
            "visa", "mastercard", "diners", "unionpay", "taka pay",
            "credit card", "debit card", "prepaid card",
            "classic", "gold", "platinum", "infinite", "signature", "titanium", "world"
        ]
        
        # Specific fee types
        specific_fee_keywords = [
            "annual fee", "yearly fee", "renewal fee", "issuance fee", "issuance charge", 
            "joining fee", "replacement fee", "card replacement", "pin replacement", 
            "pin fee", "late payment fee", "late fee", "overlimit fee", "over-limit fee",
            "cash advance fee", "cash withdrawal fee", "atm withdrawal fee", 
            "withdrawal fee", "transaction fee",
            "duplicate statement fee", "duplicate estatement", "certificate fee",
            "chequebook fee", "customer verification fee", "cib fee", 
            "transaction alert fee", "sms alert", "transaction alert",
            "sales voucher fee", "sales voucher", "return cheque fee",
            "undelivered card fee", "atm receipt fee", "cctv footage fee",
            "cctv", "fund transfer fee", "wallet transfer fee",
            "interest rate", "rate of interest", "apr", "card interest", "credit card rate",
            "lounge", "lounge access", "sky lounge", "airport lounge", "lounge visit",
            "skylounge", "global lounge", "lounge free visit", "lounge fee", "priority pass",
            "supplementary fee", "supplementary charge", "supplementary annual fee",
            "free supplementary", "supplementary card free",
            "fee schedule", "charges schedule", "card charges", "card fees",
            "fee information", "charge information",
            "fee", "fees", "charge", "charges"
        ]
        
        generic_terms = ["cost", "pricing", "price"]
        
        if any(kw in query_lower for kw in specific_fee_keywords):
            has_card_context = any(ctx in query_lower for ctx in card_context_keywords)
            has_schedule_ref = any(ref in query_lower for ref in ["fee schedule", "charges schedule", "card charges", "card fees"])
            has_specific_phrase = any(
                kw in query_lower
                for kw in [
                    "annual fee", "issuance fee", "replacement fee", "late payment fee",
                    "overlimit fee", "cash withdrawal fee", "atm withdrawal fee", "cash advance fee",
                    "sales voucher fee", "transaction alert fee", "lounge fee", "lounge free visit",
                    "supplementary fee", "supplementary annual fee",
                ]
            )
            if has_specific_phrase:
                return True
            return has_card_context or has_schedule_ref
        
        has_generic_term = any(term in query_lower for term in generic_terms)
        if has_generic_term:
            has_card_context = any(ctx in query_lower for ctx in card_context_keywords)
            return has_card_context
        
        return False
    
    def is_retail_asset_fee_query(self, query: str) -> bool:
        """Detect if query is about retail asset charges (loans, fast cash, etc.)"""
        query_lower = query.lower().strip()

        # Guardrail: process/procedure/how-to questions
        has_process_intent = any(k in query_lower for k in ["process", "procedure", "how to", "steps", "method"])
        has_fee_intent = any(k in query_lower for k in ["fee", "fees", "charge", "charges", "cost", "pricing", "price"])
        if has_process_intent and not has_fee_intent:
            return False
        
        # Retail-asset-exclusive fee terms
        retail_asset_exclusive_fees = [
            'partial payment fee', 'partial payment',
            'early settlement fee', 'early settlement', 'early_settlement',
            'stamp charge', 'stamp duty',
            'reschedule & restructure fee', 'reschedule and restructure fee',
            'reschedule & restructure exit fee', 'reschedule and restructure exit fee',
            'reschedule fee', 'rescheduling fee',
            'restructure fee', 'restructuring fee',
            'notarization fee', 'noc fee', 'loan repayment certificate',
            'loan outstanding certificate', 'loan outstanding certificate fee',
            'cib charge', 'cib fee', 'other charges', 'other charge',
        ]
        has_exclusive_fee = any(fee_term in query_lower for fee_term in retail_asset_exclusive_fees)
        has_card_keyword = any(card_kw in query_lower for card_kw in ['card', 'credit card', 'debit card', 'visa', 'mastercard'])
        
        if has_exclusive_fee and not has_card_keyword:
            logger.info(f"[ROUTING] Retail asset exclusive fee query detected: '{query}'")
            return True
        
        retail_asset_keywords = [
            "fast cash", "fast loan", "education loan", "edu loan",
            "personal loan", "home loan", "car loan", "auto loan",
            "business loan", "executive loan", "assure loan", "women's loan",
            "retail asset", "loan processing", "overdraft", "od", "emi loan"
        ]
        
        fee_keywords = [
            "fee", "fees", "charge", "charges", "cost", "pricing", "price",
            "processing fee", "enhancement fee", "reduction fee", "cancellation fee",
            "renewal fee", "settlement fee", "early_settlement_fee", "settlement"
        ]
        
        has_retail_asset = any(kw in query_lower for kw in retail_asset_keywords)
        has_fee_keyword = any(kw in query_lower for kw in fee_keywords)
        
        if has_retail_asset and has_fee_keyword:
            logger.info(f"[ROUTING] Retail asset fee query detected: '{query}'")
            return True
        
        return False
    
    def is_skybanking_fee_query(self, query: str) -> bool:
        """Detect if query is about Skybanking fees/charges"""
        query_lower = query.lower().strip()
        
        skybanking_keywords = [
            "skybanking", "sky banking", "ebl skybanking",
            "digital banking", "mobile banking", "online banking",
            "skybanking app", "ebl app", "mobile app"
        ]
        
        fee_keywords = [
            "fee", "fees", "charge", "charges", "cost", "pricing", "price",
            "certificate fee", "account certificate", "fund transfer fee",
            "transfer fee", "transaction fee"
        ]
        
        has_skybanking = any(kw in query_lower for kw in skybanking_keywords)
        has_fee_keyword = any(kw in query_lower for kw in fee_keywords)
        
        if has_skybanking and has_fee_keyword:
            logger.info(f"[ROUTING] Skybanking fee query detected: '{query}'")
            return True
        
        return False

    def is_generic_skybanking_fee_query(self, query: str) -> bool:
        """Detect overly-generic Skybanking fee queries that need clarification"""
        query_lower = query.lower().strip()

        skybanking_keywords = [
            "skybanking", "sky banking", "ebl skybanking",
            "digital banking", "mobile banking", "online banking",
            "skybanking app", "ebl app", "mobile app"
        ]
        fee_keywords = ["fee", "fees", "charge", "charges", "cost", "pricing", "price"]

        if not (any(kw in query_lower for kw in skybanking_keywords) and any(kw in query_lower for kw in fee_keywords)):
            return False

        specific_fee_terms = [
            "add money", "fund transfer", "npsb", "binimoy", "binomoy", "rtgs",
            "statement", "certificate", "account certificate", "balance certificate",
            "dps certificate", "loan outstanding certificate", "loan tax certificate",
            "noc", "duplicate pin", "bill payment", "government payment",
            "a challan", "a-challan", "achallan", "challan", "annual service", "service charge",
        ]

        return not any(term in query_lower for term in specific_fee_terms)
    
    def is_card_rates_query(self, query: str) -> bool:
        """Legacy method - delegates to is_fee_schedule_query"""
        return self.is_fee_schedule_query(query)
    
    def is_location_query(self, query: str) -> bool:
        """Detect if query is about locations (branches, ATMs, CRMs, etc.)"""
        query_lower = query.lower()

        # Guardrail: machine-capability questions
        machine_location_terms = ["atm", "atms", "crm", "rtdm"]
        intent_flags = self._get_location_intent_flags(query)
        has_location_cue = intent_flags.has_location_cue
        has_geo_token = intent_flags.has_geo_token
        has_in_location_phrase = intent_flags.has_in_location_phrase
        
        if any(k in query_lower for k in machine_location_terms):
            if not has_location_cue and not has_geo_token and not has_in_location_phrase:
                logger.info(f"[ROUTING] Machine capability query (no location cues); skipping location service: '{query}'")
                return False

        # Guardrail: process/policy questions
        process_intent_keywords = [
            "process", "procedure", "steps", "how to", "policy", "guideline",
            "what must", "checklist", "requirement", "required", "surrender",
        ]
        has_process_intent = any(k in query_lower for k in process_intent_keywords)
        has_branch_keyword = any(k in query_lower for k in ["branch", "branches", "bank branch", "ebl branch"])
        
        if has_branch_keyword and has_process_intent and not has_location_cue and not has_geo_token and not has_in_location_phrase:
            logger.info(f"[ROUTING] Branch process query (no location cues); skipping location service: '{query}'")
            return False
        
        location_keywords = [
            'branch', 'branches', 'bank branch', 'ebl branch',
            'head office', 'headoffice', 'headquarter', 'headquarters', 'corporate office', 'main office',
            'atm', 'atms', 'automated teller machine', 'cash machine', 'cashpoint',
            'crm', 'customer relationship machine', 'customer service machine',
            'rtdm', 'retail transaction deposit machine', 'deposit machine',
            'priority center', 'priority centre', 'priority centers', 'priority centres',
            'priority banking center', 'priority banking centre',
            'where is', 'where are', 'where can i find', 'where can i locate',
            'find branch', 'find atm', 'locate', 'location', 'address', 'address of',
            'location of', 'tell me location', 'what is the location', 'what is the address',
            'nearest branch', 'nearest atm', 'near me', 
            'in dhaka', 'in chittagong', 'in sylhet', 'in khulna', 'in rajshahi',
            'dhaka branch', 'chittagong branch', 'sylhet branch'
        ]
        
        location_patterns = [
            r'\blocation\s+of\b',
            r'\baddress\s+of\b',
            r'\bwhere\s+is\b',
            r'\bwhere\s+are\b',
            r'\btell\s+me\s+(the\s+)?(location|address)',
            r'\bwhat\s+is\s+the\s+(location|address)',
            r'\bhow\s+many\s+priority\s+(center|centre)',
            r'\bhow\s+many\s+priority\s+(center|centre)s',
            r'\bnumber\s+of\s+priority\s+(center|centre)',
            r'\bcount\s+of\s+priority\s+(center|centre)',
            r'\bpriority\s+(center|centre).*\b(how many|number|count|total)',
        ]
        
        has_location_keyword = any(kw in query_lower for kw in location_keywords)
        branch_keywords = ['branch', 'branches', 'bank branch', 'ebl branch']
        has_branch_keyword = any(kw in query_lower for kw in branch_keywords)
        has_location_pattern = any(re.search(pattern, query_lower) for pattern in location_patterns)
        has_branch_name_pattern = bool(re.search(r'\b(branch|atm|crm|rtdm|priority\s+center|priority\s+centre)\b', query_lower, re.IGNORECASE))
        
        has_priority_center_count_query = bool(
            re.search(r'\b(how many|number|count|total).*priority\s+(center|centre)', query_lower, re.IGNORECASE) or
            re.search(r'\bpriority\s+(center|centre).*\b(how many|number|count|total|does.*have|has)', query_lower, re.IGNORECASE)
        )
        
        is_location = has_location_keyword or has_location_pattern or has_branch_name_pattern or has_priority_center_count_query
        
        if has_branch_keyword and not has_location_cue and not has_geo_token and not has_in_location_phrase:
            if is_location and not has_location_pattern and not has_priority_center_count_query:
                is_location = False
        
        if is_location:
            logger.info(f"[ROUTING] Detected location query: '{query}'")
            return True
        
        return False
    
    def is_compliance_query(self, query: str) -> bool:
        """Detect if query is about compliance, AML, regulatory, or policy matters"""
        query_lower = query.lower().strip()
        
        compliance_keywords = [
            'aml', 'anti money laundering', 'anti-money laundering', 'money laundering',
            'aml policy', 'aml compliance', 'aml regulation', 'aml requirements',
            'aml customer', 'aml customers', 'aml sensitive', 'aml risk',
            'compliance', 'regulatory', 'regulation', 'regulations', 'regulatory compliance',
            'compliance policy', 'compliance requirement', 'compliance requirements',
            'regulatory policy', 'regulatory requirement', 'regulatory requirements',
            'policy', 'policies', 'procedure', 'procedures', 'guideline', 'guidelines',
            'bank policy', 'banking policy', 'bank policies', 'banking policies',
        ]
        
        return any(keyword in query_lower for keyword in compliance_keywords)
    
    def is_banking_product_query(self, query: str) -> bool:
        """Detect if query is about banking products"""
        query_lower = query.lower().strip()
        
        # Check for banking product keywords
        product_keywords = [
            'credit card', 'debit card', 'savings account', 'current account',
            'fixed deposit', 'fd', 'dps', 'loan', 'mortgage', 'overdraft',
            'insurance', 'investment', 'mutual fund', 'bond', 'treasury',
        ]
        
        return any(keyword in query_lower for keyword in product_keywords)
    
    def is_broad_loan_product_line_query(self, query: str) -> bool:
        """Detect if query is a broad loan product line query"""
        query_lower = query.lower().strip()
        
        broad_patterns = [
            r'what\s+(loan|lending)\s+products?\s+do\s+you\s+(have|offer)',
            r'list\s+(of\s+)?(loan|lending)\s+products?',
            r'(loan|lending)\s+products?\s+(available|offered)',
            r'types?\s+of\s+(loan|lending)',
        ]
        
        return any(re.search(pattern, query_lower) for pattern in broad_patterns)
