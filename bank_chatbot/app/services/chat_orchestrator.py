"""
Chat Orchestrator - Coordinates all components for chat processing.
"""

import uuid
import logging
from typing import Optional, AsyncGenerator, List, Dict, Any
from datetime import datetime
import pytz

from openai import AsyncOpenAI
import httpx

from app.core.config import settings
from app.database.postgres import PostgresChatMemory, get_db
from app.database.redis_client import RedisCache, get_cache_key

logger = logging.getLogger(__name__)

# Import lead management
try:
    from app.database.leads import LeadManager, LeadType, LeadStatus
    LEADS_AVAILABLE = True
except ImportError as e:
    LEADS_AVAILABLE = False
    logger.warning(f"Lead management not available: {e}")

# Analytics logging (optional - will fail gracefully if not available)
try:
    from app.services.analytics import log_conversation
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    def log_conversation(*args, **kwargs):
        pass  # No-op if analytics not available
from app.services.lightrag_client import LightRAGClient

# Import lead management
try:
    from app.database.leads import LeadManager, LeadType, LeadStatus
    LEADS_AVAILABLE = True
except ImportError as e:
    LEADS_AVAILABLE = False
    logger.warning(f"Lead management not available: {e}")

# Import phonebook (PostgreSQL)
try:
    import sys
    import os
    # Add services directory to path to import phonebook_postgres
    services_dir = os.path.dirname(os.path.abspath(__file__))
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)
    from phonebook_postgres import get_phonebook_db
    PHONEBOOK_DB_AVAILABLE = True
except ImportError as e:
    PHONEBOOK_DB_AVAILABLE = False
    logger.warning(f"[WARN] Phone book database not available: {e}")


class ConversationState:
    """Conversation state enumeration"""
    NORMAL = "normal"
    LEAD_COLLECTING = "lead_collecting"
    LEAD_COMPLETE = "lead_complete"


class LeadFlowState:
    """Manages lead collection flow state"""
    def __init__(self):
        self.state = ConversationState.NORMAL
        self.lead_type: Optional[LeadType] = None if not LEADS_AVAILABLE else None
        self.current_question_index = 0
        self.collected_data: Dict[str, Any] = {}
        self.questions: List[Dict[str, str]] = []
    
    def reset(self):
        """Reset the flow state"""
        self.state = ConversationState.NORMAL
        self.lead_type = None
        self.current_question_index = 0
        self.collected_data = {}
        self.questions = []


class ChatOrchestrator:
    """Orchestrates chat processing with PostgreSQL, Redis, and LightRAG"""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.lightrag_client = LightRAGClient()
        self.redis_cache = RedisCache()
        self.system_message = self._get_system_message()
        self.lead_flows: Dict[str, LeadFlowState] = {}  # session_id -> LeadFlowState
    
    def _get_system_message(self) -> str:
        """Get system message for the chatbot"""
        return """You are a helpful and professional banking assistant for a financial institution.
Your role is to assist customers with banking-related queries, product information, account services, and general banking questions.

═══════════════════════════════════════════════════════════════════════════════
🚨 CRITICAL CURRENCY RULE - READ THIS FIRST 🚨
═══════════════════════════════════════════════════════════════════════════════
**ABSOLUTE REQUIREMENT: When the context shows currency codes like "BDT" or "USD", 
you MUST use the EXACT currency code from the context. NEVER replace BDT with ₹ or 
any other symbol. 

EXAMPLES:
- Context says "BDT 287.5" → You MUST output "BDT 287.5" (NOT ₹287.5)
- Context says "BDT 1,725" → You MUST output "BDT 1,725" (NOT ₹1,725)
- Context says "USD 57.5" → You MUST output "USD 57.5"

BDT = Bangladeshi Taka (use "BDT", never use ₹)
USD = US Dollar (use "USD")

This is a CRITICAL requirement - incorrect currency symbols cause serious errors.
═══════════════════════════════════════════════════════════════════════════════

Guidelines:
1. Always be professional, friendly, and helpful
2. **IMPORTANT: When context from the knowledge base is provided, you MUST use it to answer the question. Do NOT say you don't have information if the context contains the answer.**
3. The context provided contains accurate information from the bank's knowledge base - trust it and use it directly
4. If the context contains specific numbers, facts, or details, include them in your response
5. Only say "I don't have information" if the context is truly empty or doesn't contain relevant information
6. For banking queries, always use the provided context from LightRAG
7. **CRITICAL: If the context includes "Card Rates and Fees Information (Official Schedule)", this is official, deterministic data from the card charges schedule. You MUST use this data to answer card fee/rate questions. Do NOT say you don't have the information if this data is present.**
8. **CRITICAL CURRENCY PRESERVATION: When the context shows amounts with currency symbols or codes (BDT, USD, etc.), you MUST use the EXACT currency symbol/code from the context. NEVER replace BDT (Bangladeshi Taka) with ₹ (Indian Rupee) or any other currency symbol. If you see "BDT 287.5" in the context, you MUST output "BDT 287.5" - do NOT change it to ₹287.5 or any other currency. Preserve all currency codes exactly as shown: BDT = Bangladeshi Taka, USD = US Dollar.**
9. Never make up specific numbers, rates, or product details
10. If asked about products, services, or policies, refer to the knowledge base context
11. For general greetings or small talk, respond naturally without requiring context
12. When asked about the current date or time, use the provided current date and time information to answer accurately
13. **For policy-related questions: If the query is missing required entities (like policy name, account type, or customer type), ask a clarification question instead of guessing or providing incomplete information. The system will handle this automatically, but if you receive a query that seems incomplete, ask for the missing information.**

When responding:
- Be concise but thorough
- Use clear, simple language
- Structure product information clearly
- Always prioritize accuracy over speed
- For date/time queries, provide the exact current date and time as provided in the context
- **When context is provided, use it - don't ignore it or say you don't have the information**
- **CRITICAL: Preserve currency symbols and codes exactly as shown in context - BDT means Bangladeshi Taka, USD means US Dollar. Never substitute or change currency symbols. If context says "BDT 287.5", output "BDT 287.5" - never use ₹ or other symbols.**
- **For policy queries missing required information, ask for clarification rather than guessing**"""
    
    def _is_small_talk(self, query: str) -> bool:
        """Detect if query is small talk (greetings, thanks, etc.)"""
        query_lower = query.lower().strip()
        
        # CRITICAL: Contact/phonebook keywords override - never treat as small talk
        # If it's a contact query, it should check phonebook, not be treated as small talk
        contact_keywords = [
            'phone', 'telephone', 'tel', 'call', 'contact', 'number', 'phone number',
            'mobile', 'cell', 'email', 'address', 'extension', 'ext', 'pabx', 'ip phone',
            'employee', 'staff', 'emp id', 'who is', 'who are', 'who works',
            'designation', 'department', 'manager', 'director', 'head of'
        ]
        
        if any(keyword in query_lower for keyword in contact_keywords):
            return False  # Force it into phonebook check (not small talk)
        
        # Banking keywords override - never treat as small talk
        banking_keywords = [
            "loan", "card", "account", "balance", "deposit", "withdrawal",
            "interest", "rate", "fee", "service", "product", "banking",
            "credit", "debit", "transaction", "statement", "minimum", "maximum"
        ]
        
        if any(keyword in query_lower for keyword in banking_keywords):
            return False
        
        # Small talk patterns
        small_talk_patterns = [
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
            "how are you", "how's it going", "what's up",
            "thanks", "thank you", "appreciate it",
            "bye", "goodbye", "see you", "farewell",
            "what are you", "who are you", "what can you do"
        ]
        
        return any(pattern in query_lower for pattern in small_talk_patterns)
    
    def _is_datetime_query(self, query: str) -> bool:
        """Detect if query is asking about date or time"""
        query_lower = query.lower().strip()
        
        datetime_keywords = [
            "date", "time", "what time", "what date", "current time", "current date",
            "today", "now", "what day", "what is the time", "what is the date",
            "tell me the time", "tell me the date", "time now", "date today"
        ]
        
        return any(keyword in query_lower for keyword in datetime_keywords)
    
    def _is_contact_info_query(self, query: str) -> bool:
        """Detect if query is about contact information (ONLY phone number or email)
        This should ALWAYS check phonebook first, never LightRAG
        VERY RESTRICTIVE - only phone and email, nothing else"""
        import re
        query_lower = query.lower().strip()
        
        # Exclude queries about email processes/policies/requirements
        # These should go to LightRAG, not phonebook
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
        
        # If query is about email processes/policies, NOT a contact query
        if any(keyword in query_lower for keyword in email_process_keywords):
            return False
        
        # VERY SPECIFIC: Only phone number and email keywords for CONTACT lookup
        # Everything else goes to LightRAG
        # Use word boundaries to avoid false matches (e.g., "call" in "cancelled")
        contact_patterns = [
            # Phone/Telephone - with word boundaries
            r'\bphone number\b', r'\btelephone number\b', r'\bcontact number\b',
            r'\bmobile number\b', r'\bcell number\b', r'\bphone\b', r'\btelephone\b',
            r'\bmobile\b', r'\bcell\b', r'\bcellphone\b', r'\btel\b', r'\bcall\b',
            r'\bpabx\b', r'\bextension\b', r'\bext\b', r'\bip phone\b', r'\bip phone number\b',
            r'\bdirect line\b', r'\bdirect number\b', r'\blandline\b',
            
            # Email - ONLY for contact lookup (not processes)
            # Must be in context of asking for someone's email
            r'\bemail address of\b', r'\bemail of\b', r'\bemail for\b', r'\bemail id of\b',
            r'\bemail id for\b', r'\bmail address of\b', r'\bmail address for\b',
            r'\bwhat is the email\b', r'\bwhat is email\b', r'\bget email\b',
            r'\bfind email\b', r'\bcontact email\b', r'\bemail contact\b'
        ]
        
        # Check if query contains phone number or email keywords for contact lookup
        # Use regex with word boundaries to avoid false matches
        # If yes, ALWAYS check phonebook first (never LightRAG)
        return any(re.search(pattern, query_lower) for pattern in contact_patterns)
    
    def _is_phonebook_query(self, query: str) -> bool:
        """Detect if query is about phone book directory
        VERY RESTRICTIVE - only explicit phonebook/directory queries"""
        query_lower = query.lower().strip()
        
        # VERY SPECIFIC: Only explicit phonebook/directory keywords
        phonebook_keywords = [
            'phonebook', 'phone book', 'employee directory', 'staff directory',
            'contact list', 'employee list', 'staff list', 'directory'
        ]
        
        # Check if query explicitly mentions phonebook/directory
        return any(keyword in query_lower for keyword in phonebook_keywords)
    
    def _is_employee_query(self, query: str) -> bool:
        """Detect if query is about employee information (for phonebook lookup)
        VERY RESTRICTIVE - only employee search/lookup queries"""
        query_lower = query.lower().strip()
        
        # VERY SPECIFIC: Only employee search/lookup keywords
        # Exclude general "employee" mentions that might be about policies, etc.
        employee_keywords = [
            'employee id', 'employee number', 'emp id', 'emp_id',
            'employee phone', 'employee email', 'employee contact',
            'staff phone', 'staff email', 'staff contact',
            'who is employee', 'who are employees', 'find employee',
            'search employee', 'lookup employee', 'employee directory',
            'staff directory', 'employee list', 'staff list'
        ]
        
        # Also check for "employee" or "staff" combined with contact-related terms
        if 'employee' in query_lower or 'staff' in query_lower:
            # Only if combined with contact/search terms
            contact_terms = ['phone', 'email', 'contact', 'number', 'id', 'search', 'find', 'lookup', 'who']
            if any(term in query_lower for term in contact_terms):
                return True
        
        return any(keyword in query_lower for keyword in employee_keywords)
    
    def _is_financial_report_query(self, query: str) -> bool:
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
    
    def _is_user_document_query(self, query: str) -> bool:
        """Detect if query is about user-uploaded documents"""
        query_lower = query.lower().strip()
        
        user_doc_keywords = [
            'user document', 'uploaded document', 'custom document', 'my document',
            'document i uploaded', 'document i provided', 'my file', 'uploaded file',
            'custom file', 'user file', 'personal document', 'my upload'
        ]
        
        return any(keyword in query_lower for keyword in user_doc_keywords)
    
    def _is_management_query(self, query: str) -> bool:
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
    
    def _is_milestone_query(self, query: str) -> bool:
        """Detect if query is about EBL milestones/history/achievements"""
        query_lower = query.lower().strip()
        
        # Normalize "mile stone" to "milestone" for matching
        query_normalized = query_lower.replace('mile stone', 'milestone').replace('mile-stone', 'milestone')
        
        # Check for "about ebl" or "tell me about ebl" patterns first (high priority)
        if 'about ebl' in query_normalized or 'tell me about ebl' in query_normalized:
            # If it's about EBL and contains milestone/history keywords, it's a milestone query
            if any(kw in query_normalized for kw in ['milestone', 'history', 'achievement', 'timeline', 'journey', 'founded', 'establishment']):
                return True
            # If it's just "about ebl" without contact keywords, treat as informational (milestone/history)
            contact_kw = ['phone', 'contact', 'email', 'address', 'number', 'mobile', 'call']
            if not any(kw in query_normalized for kw in contact_kw):
                return True
        
        milestone_keywords = [
            'milestone', 'milestones', 'history', 'historical', 'achievement', 'achievements',
            'timeline', 'journey', 'evolution', 'development', 'growth', 'progress',
            'founded', 'establishment', 'established', 'inception', 'origin', 'beginnings',
            'ebl milestone', 'ebl milestones', 'ebl history', 'bank milestone', 'bank milestones',
            'what are the milestones', 'ebl achievements',
            'bank achievements', 'company history', 'bank history', 'corporate history',
            'about ebl', 'ebl background', 'ebl information'
        ]
        
        return any(keyword in query_normalized for keyword in milestone_keywords)
    
    def _is_card_rates_query(self, query: str) -> bool:
        """Detect if query is asking specifically about card fees/rates (card rates microservice)"""
        query_lower = query.lower().strip()
        
        # Card product names that indicate a card query (even without the word "card")
        card_products = [
            "classic", "gold", "platinum", "infinite", "signature", "titanium", 
            "world", "visa", "mastercard", "diners club", "unionpay", "taka pay",
            "prepaid", "debit", "credit"
        ]
        
        # Must mention a card - either explicitly or through card product/network names
        has_card_keyword = "card" in query_lower
        has_card_product = any(product in query_lower for product in card_products)
        
        if not has_card_keyword and not has_card_product:
            return False
        
        # Card rates/fees keywords
        card_rates_keywords = [
            # Fees
            "annual fee", "yearly fee", "renewal fee", "issuance fee", "joining fee",
            "replacement fee", "card replacement", "pin replacement", "pin fee",
            "late payment fee", "late fee", "overlimit fee", "over-limit fee",
            "cash advance fee", "cash withdrawal fee", "transaction fee",
            "duplicate statement fee", "certificate fee", "chequebook fee",
            "customer verification fee", "cib fee", "transaction alert fee",
            "sales voucher fee", "return cheque fee", "undelivered card fee",
            "atm receipt fee", "cctv footage fee", "fund transfer fee",
            "wallet transfer fee", "want2buy fee", "easycredit fee",
            "risk assurance fee", "balance maintenance fee",
            
            # Rates
            "interest rate", "rate of interest", "apr", "annual percentage rate",
            "card interest", "credit card rate",
            
            # Lounge access
            "lounge", "lounge access", "sky lounge", "airport lounge", "lounge visit",
            "skylounge", "international lounge", "domestic lounge", "global lounge",
            "lounge free visit", "lounge fee", "priority pass",
            
            # Charges
            "charge", "charges", "fee", "fees", "cost", "price", "pricing"
        ]
        
        return any(kw in query_lower for kw in card_rates_keywords)
    
    def _is_compliance_query(self, query: str) -> bool:
        """Detect if query is about compliance, AML, regulatory, or policy matters"""
        query_lower = query.lower().strip()
        
        compliance_keywords = [
            # AML (Anti-Money Laundering)
            'aml', 'anti money laundering', 'anti-money laundering', 'money laundering',
            'aml policy', 'aml compliance', 'aml regulation', 'aml requirements',
            'aml customer', 'aml customers', 'aml sensitive', 'aml risk',
            
            # Compliance & Regulatory
            'compliance', 'regulatory', 'regulation', 'regulations', 'regulatory compliance',
            'compliance policy', 'compliance requirement', 'compliance requirements',
            'regulatory policy', 'regulatory requirement', 'regulatory requirements',
            
            # Policy & Procedures
            'policy', 'policies', 'procedure', 'procedures', 'guideline', 'guidelines',
            'bank policy', 'banking policy', 'bank policies', 'banking policies',
            'internal policy', 'internal policies', 'operational policy',
            
            # KYC (Know Your Customer)
            'kyc', 'know your customer', 'kyc policy', 'kyc compliance', 'kyc requirement',
            'kyc requirements', 'customer due diligence', 'cdd',
            
            # Risk & Fraud
            'risk management', 'fraud prevention', 'fraud detection', 'suspicious activity',
            'suspicious transaction', 'transaction monitoring', 'sanctions',
            'sanctions screening', 'ofac', 'pep', 'politically exposed person',
            
            # Sensitive Customers
            'sensitive customer', 'sensitive customers', 'high risk customer',
            'high risk customers', 'risk customer', 'risk customers',
            
            # Regulatory Bodies
            'bangladesh bank', 'central bank', 'bb guideline', 'bb guidelines',
            'regulatory authority', 'regulatory authorities'
        ]
        
        return any(keyword in query_lower for keyword in compliance_keywords)
    
    def _check_policy_entities(self, query: str) -> tuple[bool, Optional[str]]:
        """
        Check if a policy query has required entities.
        Returns: (has_required_entities, clarification_question_if_missing)
        """
        import re
        query_lower = query.lower().strip()
        
        # Common policy names/identifiers that might be mentioned
        policy_identifiers = [
            'aml', 'kyc', 'cdd', 'ofac', 'pep', 'sanctions',
            'anti money laundering', 'know your customer', 'customer due diligence',
            'money laundering', 'politically exposed person',
            'credit policy', 'lending policy', 'loan policy', 'card policy',
            'account policy', 'deposit policy', 'withdrawal policy',
            'transaction policy', 'compliance policy', 'risk policy',
            'fraud policy', 'operational policy', 'internal policy',
            'gap policy', 'code of conduct', 'dress code', 'employee policy'
        ]
        
        # Account types that might be relevant
        account_types = [
            'savings', 'current', 'fixed deposit', 'fd', 'rd', 'recurring deposit',
            'corporate', 'commercial', 'retail', 'personal', 'business',
            'super saver', 'stellar', 'platinum', 'gold', 'silver'
        ]
        
        # Customer types
        customer_types = [
            'corporate', 'commercial', 'retail', 'personal', 'individual',
            'business', 'sme', 'small medium enterprise', 'enterprise'
        ]
        
        # Check if query mentions a specific policy name using patterns:
        # - "X policy" (e.g., "GAP policy", "AML policy")
        # - "policy X" (e.g., "policy regarding socks")
        # - Known policy identifiers
        has_policy_name = False
        
        # Pattern 1: Check known policy identifiers first (most reliable)
        if any(identifier in query_lower for identifier in policy_identifiers):
            has_policy_name = True
        
        # Pattern 2: "X policy" - look for any word/phrase before "policy" that's not generic
        # This handles: "GAP policy", "the GAP policy", "AML policy", "what does the GAP policy say"
        generic_words = {'the', 'a', 'an', 'this', 'that', 'what', 'which', 'some', 'any', 'does', 'say', 'is', 'are', 'was', 'were'}
        
        # Find all instances of "X policy" pattern
        policy_before_pattern = r'\b([a-z]+(?:\s+[a-z]+)?)\s+policy\b'
        matches = re.findall(policy_before_pattern, query_lower)
        if matches:
            for match in matches:
                match_clean = match.strip().lower()
                # If it's not a generic word, consider it a policy name
                if match_clean and match_clean not in generic_words:
                    has_policy_name = True
                    break
        
        # Pattern 3: "policy regarding/about/for X" - indicates a specific policy is being discussed
        if re.search(r'\bpolicy\s+(?:regarding|about|for|on|concerning|in|of|say|state|mention|specify|require|allow|prohibit)', query_lower):
            has_policy_name = True
        
        # Pattern 4: If query has "policy" and asks about a specific topic, assume policy name is present
        # e.g., "what does the GAP policy say about socks" - has "policy" and "socks" (specific topic)
        # e.g., "what does the policy say about X" - has "policy" and topic X
        if 'policy' in query_lower:
            # Check if there's a specific topic/subject mentioned (not just "policy" alone)
            # Look for words after "policy" that suggest a specific question
            has_specific_topic = re.search(
                r'policy\s+(?:say|state|mention|specify|require|allow|prohibit|regarding|about|for|on|concerning|in|of)\s+[a-z]+',
                query_lower
            )
            if has_specific_topic:
                has_policy_name = True
        
        # If a specific policy is mentioned, allow it to proceed (don't ask for clarification)
        if has_policy_name:
            return (True, None)
        
        # Safety check: If query has "policy" and mentions a specific topic/subject, allow it through
        # This catches cases like "what does the GAP policy say about socks" where the policy name
        # might not have been detected but there's clearly a specific question being asked
        if 'policy' in query_lower:
            # Check if there's substantive content beyond just "what is the policy?"
            # Look for: specific topics, action verbs, or content after "policy"
            has_substantive_content = (
                # Has a topic/subject mentioned (more than just "policy")
                len(query_lower.split()) > 4 or
                # Has action verbs that suggest a specific question
                any(word in query_lower for word in ['say', 'state', 'mention', 'specify', 'require', 'allow', 'prohibit', 'regarding', 'about', 'for', 'on', 'concerning']) or
                # Has "does" or "do" which suggests asking about something specific
                'does' in query_lower or 'do ' in query_lower
            )
            
            # Only ask for clarification if it's truly vague (like "what is the policy?")
            is_truly_vague = (
                query_lower in ['what is the policy?', 'what is policy?', 'tell me about policy', 'explain policy'] or
                (len(query_lower.split()) <= 4 and 'policy' in query_lower and not has_substantive_content)
            )
            
            if not is_truly_vague:
                # Has enough context, allow it through
                return (True, None)
        
        # Check if query is asking about policy in general (e.g., "what is the policy?")
        # Only trigger if it's truly general without any specific policy mentioned
        is_general_policy_query = (
            ('what' in query_lower and 'policy' in query_lower and not has_policy_name) or
            ('tell me' in query_lower and 'policy' in query_lower and not has_policy_name) or
            ('explain' in query_lower and 'policy' in query_lower and not has_policy_name)
        )
        
        # If it's a general policy query without context, we need clarification
        if is_general_policy_query:
            # Check if account type or customer type is mentioned
            has_account_type = any(acc_type in query_lower for acc_type in account_types)
            has_customer_type = any(cust_type in query_lower for cust_type in customer_types)
            
            if not has_account_type and not has_customer_type:
                return (False, "I'd be happy to help you with policy information. Could you please specify which policy you're asking about? For example:\n- AML (Anti-Money Laundering) policy\n- KYC (Know Your Customer) policy\n- Credit/Lending policy\n- GAP policy\n- Code of Conduct policy\n- Or any other specific policy name")
        
        # Check for queries that need account type context
        # e.g., "what is the policy for account?" - needs account type
        # But only if no specific policy is mentioned
        if 'policy' in query_lower and ('account' in query_lower or 'deposit' in query_lower) and not has_policy_name:
            if not any(acc_type in query_lower for acc_type in account_types):
                return (False, "To provide accurate policy information, could you please specify the account type? For example:\n- Savings account\n- Current account\n- Fixed Deposit (FD)\n- Recurring Deposit (RD)\n- Corporate account\n- Or any other specific account type")
        
        # Check for queries that need customer type context
        # e.g., "what is the policy for customer?" - needs customer type
        # But only if no specific policy is mentioned
        if 'policy' in query_lower and ('customer' in query_lower or 'client' in query_lower) and not has_policy_name:
            if not any(cust_type in query_lower for cust_type in customer_types):
                return (False, "To provide accurate policy information, could you please specify the customer type? For example:\n- Corporate customer\n- Retail/Personal customer\n- Business/SME customer\n- Or any other specific customer category")
        
        # All required entities are present
        return (True, None)
    
    def _is_banking_product_query(self, query: str) -> bool:
        """Detect if query is about banking products/services (should use LightRAG, not phonebook)"""
        query_lower = query.lower().strip()
        
        # Banking product/service keywords - these should go to LightRAG, NOT phonebook
        banking_product_keywords = [
            # Credit/Debit Cards
            'credit card', 'debit card', 'card limit', 'card conversion', 'card upgrade',
            'card feature', 'card benefit', 'card reward', 'card fee', 'card charge',
            'card application', 'card activation', 'card statement', 'card transaction',
            
            # Loans
            'loan', 'personal loan', 'home loan', 'car loan', 'business loan',
            'loan interest', 'loan rate', 'loan term', 'loan eligibility', 'loan application',
            'loan approval', 'loan repayment', 'loan emi', 'loan processing',
            
            # Accounts
            'account', 'accounts',  # Standalone account keyword to catch all account types
            'savings account', 'current account', 'fixed deposit', 'fd', 'rd', 'recurring deposit',
            'rfcd', 'rfd', 'recurring fixed', 'recurring fixed deposit',  # RFCD account types
            'account opening', 'account balance', 'account statement', 'account fee',
            'account interest', 'account rate', 'account minimum balance',
            'account type', 'account types', 'types of account', 'kinds of account',
            
            # Corporate/Commercial Banking
            'corporate customer', 'corporate customers', 'corporate account', 'corporate accounts',
            'corporate banking', 'commercial customer', 'commercial customers',
            'corporate service', 'corporate process', 'corporate procedure',
            'corporate requirement', 'corporate requirements', 'corporate policy',
            'corporate confirmation', 'email confirmation', 'email verification',
            'processing requirement', 'processing requirements', 'before processing',
            'whose email confirmation', 'email confirmation required', 'confirmation required',
            'prior email confirmation', 'prior confirmation', 'subject to prior',
            'subject to email', 'processing subject to', 'subject to confirmation',
            'in case of corporate', 'case of corporate', 'corporate processing',
            'in the case of', 'in case of', 'case of', 'subject to',
            
            # Banking Services
            'online banking', 'mobile banking', 'internet banking', 'atm', 'cash withdrawal',
            'fund transfer', 'remittance', 'foreign exchange', 'forex', 'currency exchange',
            'locker', 'safe deposit', 'cheque', 'draft', 'demand draft',
            'standing instruction', 'standing instructions', 'si', 'si setup', 'si cancellation',
            'si cancel', 'cancel si', 'cancel standing instruction', 'recurring payment',
            'recurring transfer', 'automatic payment', 'automatic transfer', 'auto debit',
            'auto credit', 'scheduled payment', 'scheduled transfer', 'recurring debit',
            'recurring credit', 'auto payment', 'auto transfer',
            
            # Branch/Center Locations
            'priority center', 'priority centre', 'priority centers', 'priority centres',
            'branch', 'branches', 'branch location', 'branch locations',
            'center', 'centre', 'centers', 'centres', 'service center', 'service centre',
            'how many', 'number of', 'count of', 'list of', 'where is', 'where are',
            'sylhet', 'dhaka', 'chittagong', 'city', 'location', 'locations',
            
            # Products & Services
            'banking product', 'financial product', 'service', 'banking service',
            'product feature', 'product benefit', 'product eligibility', 'product requirement',
            'interest rate', 'exchange rate', 'service charge', 'fee structure',
            'conversion', 'upgrade', 'downgrade', 'limit', 'limit increase', 'limit decrease',
            
            # Company Information & History
            'milestone', 'milestones', 'history', 'about ebl', 'ebl history', 'ebl background',
            'company history', 'bank history', 'establishment', 'founded', 'founding',
            'achievement', 'achievements', 'award', 'awards', 'recognition', 'recognition',
            'timeline', 'journey', 'evolution', 'growth', 'development', 'progress'
        ]
        
        # Check for banking product patterns
        return any(keyword in query_lower for keyword in banking_product_keywords)
    
    def _detect_lead_intent(self, query: str) -> Optional[LeadType]:
        """Detect if user wants to apply for credit card or loan"""
        query_lower = query.lower().strip()
        
        # Credit card intent keywords
        credit_card_keywords = [
            'apply for credit card', 'want credit card', 'need credit card',
            'get credit card', 'credit card application', 'apply credit card',
            'interested in credit card', 'credit card interest', 'new credit card',
            'generate a lead for credit card', 'lead for credit card', 'create lead credit card'
        ]
        
        # Loan intent keywords
        loan_keywords = [
            'apply for loan', 'want loan', 'need loan', 'get loan',
            'loan application', 'apply loan', 'interested in loan',
            'loan interest', 'personal loan', 'home loan', 'car loan',
            'business loan', 'new loan', 'generate a lead for loan',
            'lead for loan', 'create lead loan', 'generate lead'
        ]
        
        if any(keyword in query_lower for keyword in credit_card_keywords):
            return LeadType.CREDIT_CARD
        elif any(keyword in query_lower for keyword in loan_keywords):
            return LeadType.LOAN
        
        return None
    
    def _get_lead_questions(self, lead_type: LeadType) -> List[Dict[str, str]]:
        """Get questions for lead collection based on type"""
        if lead_type == LeadType.CREDIT_CARD:
            return [
                {"field": "full_name", "question": "Great! I'd be happy to help you apply for a credit card. May I have your full name?"},
                {"field": "phone", "question": "Thank you! What's your phone number?"},
                {"field": "email", "question": "And your email address?"},
                {"field": "date_of_birth", "question": "What's your date of birth? (DD/MM/YYYY)"},
                {"field": "employment_status", "question": "What's your employment status? (Employed/Self-employed/Student/Retired)"},
                {"field": "monthly_income", "question": "What's your approximate monthly income? (BDT)"},
            ]
        elif lead_type == LeadType.LOAN:
            return [
                {"field": "full_name", "question": "Great! I'd be happy to help you with a loan application. May I have your full name?"},
                {"field": "phone", "question": "Thank you! What's your phone number?"},
                {"field": "email", "question": "And your email address?"},
                {"field": "loan_type", "question": "What type of loan are you interested in? (Personal/Home/Car/Business)"},
                {"field": "loan_amount", "question": "What loan amount are you looking for? (BDT)"},
                {"field": "employment_status", "question": "What's your employment status? (Employed/Self-employed/Student/Retired)"},
                {"field": "monthly_income", "question": "What's your approximate monthly income? (BDT)"},
            ]
        return []
    
    def _extract_answer(self, query: str, field: str) -> Optional[str]:
        """Extract answer from user query based on field type"""
        query_lower = query.lower().strip()
        
        # For email
        if field == "email":
            import re
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            match = re.search(email_pattern, query)
            if match:
                return match.group(0)
        
        # For phone
        elif field == "phone":
            import re
            # Extract digits
            digits = re.sub(r'\D', '', query)
            if len(digits) >= 10:
                return digits
        
        # For date of birth
        elif field == "date_of_birth":
            import re
            date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
            match = re.search(date_pattern, query)
            if match:
                return match.group(0)
        
        # For amounts
        elif field in ["loan_amount", "monthly_income"]:
            import re
            # Extract numbers
            numbers = re.findall(r'\d+', query.replace(',', ''))
            if numbers:
                return numbers[0]
        
        # For other fields, return the query as-is (user might have provided the answer directly)
        return query.strip() if query.strip() else None
    
    def _process_lead_collection(
        self,
        session_id: str,
        query: str
    ) -> tuple[str, bool]:
        """
        Process lead collection flow
        Returns: (response_message, is_complete)
        """
        if session_id not in self.lead_flows:
            self.lead_flows[session_id] = LeadFlowState()
        
        flow = self.lead_flows[session_id]
        
        # Check if user wants to cancel
        if any(word in query.lower() for word in ['cancel', 'stop', 'nevermind', 'no thanks', 'no thank you']):
            flow.reset()
            return "No problem! I've cancelled the application. How else can I help you today?", True
        
        # Get current question
        if flow.current_question_index < len(flow.questions):
            current_q = flow.questions[flow.current_question_index]
            field = current_q["field"]
            
            # Extract answer
            answer = self._extract_answer(query, field)
            
            if answer:
                # Store answer
                flow.collected_data[field] = answer
                flow.current_question_index += 1
                
                # Check if we have more questions
                if flow.current_question_index < len(flow.questions):
                    next_q = flow.questions[flow.current_question_index]
                    return next_q["question"], False
                else:
                    # All questions answered - save lead
                    if LEADS_AVAILABLE:
                        lead_manager = LeadManager()
                        lead = lead_manager.create_lead(
                            session_id=session_id,
                            lead_type=flow.lead_type,
                            full_name=flow.collected_data.get("full_name"),
                            email=flow.collected_data.get("email"),
                            phone=flow.collected_data.get("phone"),
                            date_of_birth=flow.collected_data.get("date_of_birth"),
                            additional_info={k: v for k, v in flow.collected_data.items() 
                                           if k not in ["full_name", "email", "phone", "date_of_birth"]}
                        )
                        
                        if lead:
                            flow.reset()
                            lead_type_name = flow.lead_type.value.replace('_', ' ').title()
                            return f"Thank you! I've submitted your {lead_type_name} application. Our team will contact you shortly. Your application ID is #{lead.id}. Is there anything else I can help you with?", True
                        else:
                            flow.reset()
                            return "I apologize, but there was an error saving your application. Please try again later or contact our support team.", True
                    else:
                        flow.reset()
                        return "I apologize, but the lead generation system is currently unavailable. Please contact our support team directly.", True
            else:
                # Couldn't extract answer - ask again
                return f"I didn't quite catch that. {current_q['question']}", False
        else:
            # No more questions - should not happen
            flow.reset()
            return "Thank you for your interest! How else can I help you?", True
    
    def _get_knowledge_base(self, user_input: str) -> str:
        """
        Determine which knowledge base to use based on query content
        Routes queries to appropriate knowledge bases to avoid confusion
        """
        # Priority order (most specific first):
        
        # 1. Financial reports queries → financial reports knowledge base
        if self._is_financial_report_query(user_input):
            logger.info(f"[ROUTING] Query detected as financial report → using 'ebl_financial_reports'")
            return "ebl_financial_reports"
        
        # 2. Management queries → ebl_website (contains management info) or dedicated KB
        if self._is_management_query(user_input):
            logger.info(f"[ROUTING] Query detected as management → using 'ebl_website'")
            return "ebl_website"  # Management info is in ebl_website knowledge base
        
        # 3. Milestone queries → ebl_milestones knowledge base
        if self._is_milestone_query(user_input):
            logger.info(f"[ROUTING] Query detected as milestone → using 'ebl_milestones'")
            return "ebl_milestones"
        
        # 4. User document queries → user documents knowledge base
        if self._is_user_document_query(user_input):
            logger.info(f"[ROUTING] Query detected as user document → using 'ebl_user_documents'")
            return "ebl_user_documents"
        
        # 5. Employee queries → employees knowledge base (if exists)
        if self._is_employee_query(user_input):
            logger.info(f"[ROUTING] Query detected as employee → using 'ebl_employees'")
            return "ebl_employees"
        
        # 6. Default to configured knowledge base (usually ebl_website)
        default_kb = self.lightrag_client.knowledge_base or "ebl_website"
        logger.info(f"[ROUTING] Query using default knowledge base: '{default_kb}'")
        return default_kb
    
    def _get_current_datetime(self) -> str:
        """Get current date and time in a formatted string"""
        try:
            # Try to get timezone from settings, default to UTC
            timezone_str = getattr(settings, 'TIMEZONE', 'UTC')
            tz = pytz.timezone(timezone_str)
        except Exception:
            # Fallback to system local time if timezone is invalid
            tz = None
        
        if tz:
            now = datetime.now(tz)
        else:
            # Use system local time
            now = datetime.now()
        
        # Format: "Monday, December 9, 2025 at 2:45:30 PM UTC"
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M:%S %p")
        
        if tz:
            timezone_str = now.strftime("%Z")
            return f"{date_str} at {time_str} {timezone_str}"
        else:
            return f"{date_str} at {time_str}"
    
    def _clean_markdown_formatting(self, text: str) -> str:
        """
        Remove markdown formatting from text (especially ** for bold)
        This ensures clean text output without markdown syntax
        """
        if not text:
            return text
        
        import re
        # Remove markdown bold (**text**)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        # Remove markdown italic (*text* or _text_)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'_(.*?)_', r'\1', text)
        # Remove markdown code blocks (```code```)
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # Remove markdown inline code (`code`)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove markdown headers (# Header)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        return text
    
    def _fix_currency_symbols(self, text: str, context: str = "") -> str:
        """
        Fix currency symbol hallucinations - replace incorrect currency symbols with correct ones.
        This is a safety net to catch cases where LLM hallucinates currency symbols.
        """
        if not text:
            return text
        
        import re
        
        # Check if context contains BDT amounts
        has_bdt_in_context = "BDT" in context if context else False
        
        # Pattern to match currency symbols followed by numbers (₹287.5, ₹1,725, etc.)
        # Replace ₹ (Indian Rupee) with BDT if context has BDT
        if has_bdt_in_context:
            # Match ₹ followed by optional space and number
            text = re.sub(r'₹\s*(\d+(?:[.,]\d+)?)', r'BDT \1', text)
            # Also catch cases where ₹ might be used with commas
            text = re.sub(r'₹\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)', r'BDT \1', text)
        
        return text
    
    async def _get_card_rates_context(self, query: str) -> str:
        """
        Call card rates microservice to get deterministic fee/rate data for card queries.
        Returns a formatted text block to include before LightRAG context.
        """
        base_url = getattr(settings, "CARD_RATES_URL", "http://localhost:8002").rstrip("/")
        url = f"{base_url}/rates/search"
        
        try:
            # Increase limit for lounge queries to get all relevant information
            limit = 10 if any(kw in query.lower() for kw in ["lounge", "sky lounge"]) else 5
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, params={"q": query, "limit": limit})
            
            if resp.status_code != 200:
                logger.warning(f"[CARD_RATES] Non-200 response: {resp.status_code}")
                return ""
            
            data = resp.json()
            results = data.get("results") or []
            if not results:
                logger.info("[CARD_RATES] No card rates results for query")
                return ""
            
            lines: List[str] = []
            lines.append("=" * 70)
            lines.append("OFFICIAL CARD RATES AND FEES INFORMATION")
            lines.append("Source: Card Charges and Fees Schedule (Effective from 01st January, 2026)")
            lines.append("=" * 70)
            
            # Group by charge type for better readability
            charge_groups: Dict[str, List[Dict]] = {}
            for item in results:
                charge_type = item.get("charge_type") or "Other"
                if charge_type not in charge_groups:
                    charge_groups[charge_type] = []
                charge_groups[charge_type].append(item)
            
            # Format grouped results
            for charge_type, items in charge_groups.items():
                lines.append(f"\n{charge_type}:")
                for item in items:
                    card_name = item.get("card_full_name") or "Unknown Card"
                    amount_raw = item.get("amount_raw") or ""
                    category = item.get("category") or ""
                    network = item.get("network") or ""
                    product = item.get("product") or ""
                    
                    # Build card identifier
                    card_parts = []
                    if category:
                        card_parts.append(category)
                    if network:
                        card_parts.append(network)
                    if product:
                        card_parts.append(product)
                    
                    # Format amount based on charge type
                    formatted_amount = amount_raw
                    if "interest rate" in charge_type.lower():
                        # Format interest rates clearly
                        try:
                            # Try to parse as number
                            # Remove spaces and check if it's a number
                            clean_amount = amount_raw.strip().replace(" ", "")
                            if clean_amount.replace(".", "").replace("-", "").isdigit():
                                rate_value = float(clean_amount)
                                # In the schedule, 0.25 means 25% annually (decimal format: 0.25 = 25%)
                                if rate_value < 1:
                                    # Decimal format - convert to percentage: 0.25 = 25%
                                    annual_rate_percent = rate_value * 100
                                    formatted_amount = f"{annual_rate_percent}% per annum (or as specified in schedule)"
                                elif rate_value <= 100:
                                    # Value between 1-100, likely already a percentage
                                    formatted_amount = f"{rate_value}% per annum"
                                else:
                                    formatted_amount = f"{amount_raw} (please verify format)"
                            else:
                                formatted_amount = f"{amount_raw} (as per schedule)"
                        except:
                            formatted_amount = f"{amount_raw} (as per schedule)"
                    
                    if card_parts:
                        card_id = " ".join(card_parts)
                        lines.append(f"  • {card_id}: {formatted_amount}")
                    else:
                        lines.append(f"  • {card_name}: {formatted_amount}")
            
            lines.append("\n" + "=" * 70)
            lines.append("IMPORTANT: The above information is from the official Card Charges and Fees Schedule.")
            lines.append("This data is authoritative and should be used to answer card fee/rate questions.")
            lines.append("=" * 70)
            lines.append("")
            
            return "\n".join(lines)
        except httpx.TimeoutException:
            logger.warning("[CARD_RATES] Timeout calling card rates service")
            return ""
        except Exception as e:
            logger.error(f"[CARD_RATES] Error calling card rates service: {e}")
            return ""
    
    def _format_lightrag_context(self, lightrag_response: Dict[str, Any]) -> str:
        """Format LightRAG response into context string"""
        context_parts = []
        
        # PRIORITY 1: If we have a full response (only_need_context=False), use it directly
        # This is the most complete and formatted answer from LightRAG
        if "response" in lightrag_response and lightrag_response.get("response"):
            response_text = lightrag_response["response"]
            # If response is a complete answer (not just a prompt template), use it
            if response_text and not response_text.strip().startswith("---Role---"):
                context_parts.append("Source Data:")
                context_parts.append(response_text)
                # Still include entities/relationships/chunks if available for additional context
            else:
                # Response is a prompt template, fall through to extract structured data
                pass
        
        # PRIORITY 2: Extract structured data (entities, relationships, chunks)
        # This is used when only_need_context=True or when response is not available
        
        # Extract entities from knowledge graph
        if "entities" in lightrag_response:
            entities = lightrag_response.get("entities", [])
            if entities:
                if not context_parts:  # Only add header if we don't have response text
                    context_parts.append("Entities Data From Knowledge Graph(KG):")
                else:
                    context_parts.append("\n\nEntities Data From Knowledge Graph(KG):")
                for entity in entities[:5]:  # Limit to top 5
                    if isinstance(entity, dict):
                        name = entity.get("name", "")
                        desc = entity.get("description", "")
                        if name or desc:
                            context_parts.append(f"- {name}: {desc}")
        
        # Extract relationships
        if "relationships" in lightrag_response:
            relationships = lightrag_response.get("relationships", [])
            if relationships:
                if not context_parts:
                    context_parts.append("Relationships Data From Knowledge Graph(KG):")
                else:
                    context_parts.append("\n\nRelationships Data From Knowledge Graph(KG):")
                for rel in relationships[:5]:  # Limit to top 5
                    if isinstance(rel, dict):
                        source = rel.get("source", "")
                        relation = rel.get("relation", "")
                        target = rel.get("target", "")
                        if source and relation and target:
                            context_parts.append(f"- {source} → {relation} → {target}")
        
        # Extract document chunks
        if "chunks" in lightrag_response:
            chunks = lightrag_response.get("chunks", [])
            if chunks:
                if not context_parts:
                    context_parts.append("Original Texts From Document Chunks(DC):")
                else:
                    context_parts.append("\n\nOriginal Texts From Document Chunks(DC):")
                for chunk in chunks[:10]:  # Limit to top 10
                    if isinstance(chunk, dict):
                        text = chunk.get("text", chunk.get("content", ""))
                        if text:
                            context_parts.append(f"- {text}")
        
        # Final fallback: use response text even if it looks like a prompt
        if not context_parts and "response" in lightrag_response:
            context_parts.append(lightrag_response["response"])
        
        return "\n".join(context_parts) if context_parts else ""
    
    def _improve_query_for_lightrag(self, query: str) -> str:
        """
        Improve query phrasing for better LightRAG results
        Converts conversational queries into more specific, search-friendly formats
        """
        query_lower = query.lower().strip()
        
        # Priority center queries - make them more specific
        if 'priority center' in query_lower or 'priority centre' in query_lower:
            if 'sylhet' in query_lower:
                # Convert "tell me about priority center in sylhet" to more specific query
                if 'how many' not in query_lower and 'number' not in query_lower:
                    # Use a single, comprehensive query that works well with LightRAG
                    return "How many Priority centers are there in Sylhet City and what are their details?"
            elif 'how many' in query_lower or 'number' in query_lower:
                # Already specific enough
                return query
        
        # Location-based queries - make them more specific
        if 'tell me about' in query_lower and ('center' in query_lower or 'centre' in query_lower):
            # Extract location if mentioned
            locations = ['sylhet', 'dhaka', 'chittagong', 'narayanganj']
            for loc in locations:
                if loc in query_lower:
                    return f"What are the Priority Centers in {loc.capitalize()}? How many Priority Centers are in {loc.capitalize()}?"
        
        # Return original query if no improvements needed
        return query
    
    async def _get_lightrag_context(
        self,
        query: str,
        knowledge_base: Optional[str] = None
    ) -> str:
        """Get context from LightRAG (with caching)"""
        kb = knowledge_base or settings.LIGHTRAG_KNOWLEDGE_BASE
        
        # Improve query phrasing for better results
        improved_query = self._improve_query_for_lightrag(query)
        if improved_query != query:
            logger.info(f"[ROUTING] Improved query: '{query[:100]}' → '{improved_query[:100]}'")
        
        cache_key = get_cache_key(improved_query, kb)
        
        # Check cache first
        cached = await self.redis_cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT for query: {improved_query[:50]}... (key: {cache_key})")
            return self._format_lightrag_context(cached)
        
        logger.info(f"Cache MISS for query: {improved_query[:50]}... (key: {cache_key})")
        
        # Query LightRAG
        try:
            logger.info(f"Querying LightRAG for: {improved_query[:50]}... (knowledge_base: {kb})")
            response = await self.lightrag_client.query(
                query=improved_query,
                knowledge_base=kb,
                mode="mix",  # Use 'mix' mode (works better than 'hybrid')
                top_k=5,  # KG Top K: 5 (reduced from 8 for better results)
                chunk_top_k=5,  # Chunk Top K: 5
                include_references=True,
                only_need_context=False,  # Get full response, not just context
                # Removed max_entity_tokens, max_relation_tokens, max_total_tokens, enable_rerank
                # These parameters were causing the query to miss relevant information
                # LightRAG will use its internal defaults which work better
            )
            
            # Cache the response (using improved query for cache key)
            await self.redis_cache.set(cache_key, response)
            
            return self._format_lightrag_context(response)
        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"LightRAG query failed: {error_msg}")
            logger.error(f"Knowledge base: {kb}")
            logger.error(f"Query: {query[:100]}")
            
            # Return empty context on error (chatbot will still respond, just without LightRAG context)
            return ""
    
    def _build_messages(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Build messages for OpenAI API"""
        messages = [
            {"role": "system", "content": self.system_message}
        ]
        
        # Add conversation history
        for msg in conversation_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("message", "")
            })
        
        # Add current date/time information if query is about date/time
        datetime_info = ""
        if self._is_datetime_query(query):
            current_datetime = self._get_current_datetime()
            datetime_info = f"\n\nCurrent Date and Time: {current_datetime}"
        
        # Add current query with context
        if context:
            # Add currency preservation reminder if card rates context is present
            currency_reminder = ""
            if "OFFICIAL CARD RATES AND FEES INFORMATION" in context or "Card Rates and Fees Information" in context:
                currency_reminder = "\n\n" + "="*70 + "\n🚨 CRITICAL CURRENCY RULE 🚨\n" + "="*70 + "\nThe context above contains currency codes like 'BDT' and 'USD'. You MUST use the EXACT currency code from the context.\n\nEXAMPLES:\n- If context shows 'BDT 287.5', you MUST output 'BDT 287.5' (NOT ₹287.5)\n- If context shows 'BDT 1,725', you MUST output 'BDT 1,725' (NOT ₹1,725)\n- If context shows 'USD 57.5', you MUST output 'USD 57.5'\n\nNEVER replace BDT with ₹ or any other currency symbol. BDT = Bangladeshi Taka.\n" + "="*70
            
            user_message = f"Context from knowledge base:\n{context}\n\nUser query: {query}{datetime_info}{currency_reminder}"
        else:
            user_message = f"{query}{datetime_info}"
        
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    async def process_chat(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat query and stream the response
        
        Args:
            query: User's query
            session_id: Session ID for conversation history
            knowledge_base: LightRAG knowledge base name
        
        Yields:
            Response chunks as strings
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Check if user is already in lead collection flow
        if session_id in self.lead_flows and self.lead_flows[session_id].state == ConversationState.LEAD_COLLECTING:
            response, is_complete = self._process_lead_collection(session_id, query)
            if is_complete:
                self.lead_flows[session_id].state = ConversationState.NORMAL
            # Save to memory
            db = get_db()
            memory = PostgresChatMemory(db=db)
            try:
                if memory._available:
                    memory.add_message(session_id, "user", query)
                    memory.add_message(session_id, "assistant", response)
            finally:
                memory.close()
                if db:
                    db.close()
            yield response
            return
        
        # Check for lead intent FIRST (before other processing)
        if LEADS_AVAILABLE:
            lead_intent = self._detect_lead_intent(query)
            
            # If new lead intent detected, start lead collection
            if lead_intent:
                if session_id not in self.lead_flows:
                    self.lead_flows[session_id] = LeadFlowState()
                
                flow = self.lead_flows[session_id]
                flow.state = ConversationState.LEAD_COLLECTING
                flow.lead_type = lead_intent
                flow.questions = self._get_lead_questions(lead_intent)
                flow.current_question_index = 0
                
                # Start with first question
                first_question = flow.questions[0]["question"]
                # Save to memory
                db = get_db()
                memory = PostgresChatMemory(db=db)
                try:
                    if memory._available:
                        memory.add_message(session_id, "user", query)
                        memory.add_message(session_id, "assistant", first_question)
                finally:
                    memory.close()
                    if db:
                        db.close()
                yield first_question
                return
        
        # Get conversation history
        db = get_db()
        memory = PostgresChatMemory(db=db)
        conversation_history = []
        try:
            if memory._available:
                history = memory.get_conversation_history(
                    session_id=session_id,
                    limit=settings.MAX_CONVERSATION_HISTORY
                )
                conversation_history = [
                    {"role": msg.role, "message": msg.message}
                    for msg in history
                ]
        finally:
            memory.close()
            if db:
                db.close()
        
        # ===== ROUTING DECISION LOGGING =====
        logger.info(f"[ROUTING] ===== Processing Query (STREAMING): '{query}' =====")
        logger.info(f"[ROUTING] CODE VERSION: Corporate customer routing fix v2.0 - includes 'in the case of' pattern")
        
        # CRITICAL: Check for banking product/compliance/management/financial/milestone/user document queries FIRST
        # These should go to LightRAG, NOT phonebook
        is_banking_product_query = self._is_banking_product_query(query)
        is_compliance_query = self._is_compliance_query(query)
        is_management_query = self._is_management_query(query)
        is_financial_query = self._is_financial_report_query(query)
        is_milestone_query = self._is_milestone_query(query)
        is_user_doc_query = self._is_user_document_query(query)
        
        # Log all routing checks
        logger.info(f"[ROUTING] Routing checks - banking_product={is_banking_product_query}, compliance={is_compliance_query}, management={is_management_query}, financial={is_financial_query}, milestone={is_milestone_query}, user_doc={is_user_doc_query}")
        
        # If it's a banking product/compliance/management/financial/milestone/user document query, skip phonebook and go to LightRAG
        if is_banking_product_query or is_compliance_query or is_management_query or is_financial_query or is_milestone_query or is_user_doc_query:
            routing_type = []
            if is_banking_product_query:
                routing_type.append("banking_product")
            if is_compliance_query:
                routing_type.append("compliance")
            if is_management_query:
                routing_type.append("management")
            if is_financial_query:
                routing_type.append("financial")
            if is_milestone_query:
                routing_type.append("milestone")
            if is_user_doc_query:
                routing_type.append("user_doc")
            logger.info(f"[ROUTING] ✓ Query detected as special ({', '.join(routing_type)}) → ROUTING TO LIGHTRAG (skipping phonebook)")
            should_check_phonebook = False
            is_phonebook_query = False
            is_contact_query = False
            is_employee_query = False
            is_small_talk = False
        else:
            # Check PostgreSQL phonebook FIRST for ANY contact-related query
            # This ensures contact queries NEVER go to LightRAG - always check phonebook first
            is_small_talk = self._is_small_talk(query)
            is_contact_query = self._is_contact_info_query(query)
            is_phonebook_query = self._is_phonebook_query(query)
            is_employee_query = self._is_employee_query(query)
            
            # Log contact-related checks
            logger.info(f"[ROUTING] Contact checks - small_talk={is_small_talk}, contact={is_contact_query}, phonebook={is_phonebook_query}, employee={is_employee_query}, phonebook_available={PHONEBOOK_DB_AVAILABLE}")
            
            # If it's any kind of contact/phonebook/employee query, ALWAYS check phonebook first
            should_check_phonebook = (
                (is_phonebook_query or is_contact_query or is_employee_query) 
                and not is_small_talk 
                and PHONEBOOK_DB_AVAILABLE
            )
            
            if should_check_phonebook:
                logger.info(f"[ROUTING] ✓ Query detected as contact/phonebook/employee → ROUTING TO PHONEBOOK (NOT LightRAG)")
            elif is_small_talk:
                logger.info(f"[ROUTING] ✓ Query detected as small talk → ROUTING TO OPENAI (no LightRAG)")
            else:
                logger.info(f"[ROUTING] ✓ Query not matched to special categories → ROUTING TO LIGHTRAG (default)")
        
        logger.info(f"[ROUTING] Final decision - will_check_phonebook={should_check_phonebook}, will_use_lightrag={not should_check_phonebook and not is_small_talk}")
        
        # Check phonebook FIRST for contact queries (before LightRAG)
        if should_check_phonebook:
            try:
                phonebook_db = get_phonebook_db()
                
                # Extract search term from query
                import re
                search_term = re.sub(
                    r'\b(phone|contact|number|email|address|mobile|telephone|of|for|the)\b', 
                    '', 
                    query, 
                    flags=re.IGNORECASE
                ).strip()
                
                # Try multiple search strategies
                results = phonebook_db.smart_search(search_term, limit=5)
                
                if results:
                    logger.info(f"[OK] Found {len(results)} results in phonebook for: {search_term}")
                    
                    # Format and return results
                    if len(results) == 1:
                        # Single result - detailed format
                        response = phonebook_db.format_contact_info(results[0])
                        response += "\n\n(Source: Phone Book Database)"
                    else:
                        # Multiple results - list format
                        response = ""
                        for i, emp in enumerate(results[:5], 1):
                            response += f"{i}. {emp['full_name']}\n"
                            if emp.get('designation'):
                                response += f"   Designation: {emp['designation']}\n"
                            if emp.get('department'):
                                response += f"   Department: {emp['department']}\n"
                            if emp.get('email'):
                                response += f"   Email: {emp['email']}\n"
                            if emp.get('mobile'):
                                response += f"   Mobile: {emp['mobile']}\n"
                            response += "\n"
                        
                        total_count = phonebook_db.count_search_results(search_term)
                        response += f"We found {total_count} matching contact(s) in total. Showing only the top 5 results.\n\n"
                        if total_count > 5:
                            response += "Please provide more details to narrow down the search.\n\n"
                        response += "(Source: Phone Book Database)"
                    
                    # Save to memory
                    db = get_db()
                    memory = PostgresChatMemory(db=db)
                    try:
                        if memory._available:
                            memory.add_message(session_id, "user", query)
                            memory.add_message(session_id, "assistant", response)
                            # Log for analytics
                            if ANALYTICS_AVAILABLE:
                                log_conversation(
                                    session_id=session_id,
                                    user_message=query,
                                    assistant_response=response,
                                    knowledge_base=None,  # Phonebook query
                                    client_ip=client_ip
                                )
                    finally:
                        memory.close()
                        if db:
                            db.close()
                    
                    # Stream response
                    for char in response:
                        yield char
                    return  # DO NOT query LightRAG for contact queries
                    
                else:
                    # No results in phonebook - return helpful message (DO NOT use LightRAG)
                    logger.info(f"[INFO] No results in phonebook for '{search_term}' (contact query - NOT using LightRAG)")
                    response = f"I couldn't find any contact information for '{search_term}' in the employee directory. "
                    response += "Please try:\n"
                    response += "- Providing the full name\n"
                    response += "- Using the employee ID\n"
                    response += "- Specifying the department or designation\n"
                    response += "\n(Source: Phone Book Database)"
                    
                    # Save to memory
                    db = get_db()
                    memory = PostgresChatMemory(db=db)
                    try:
                        if memory._available:
                            memory.add_message(session_id, "user", query)
                            memory.add_message(session_id, "assistant", response)
                            # Log for analytics
                            if ANALYTICS_AVAILABLE:
                                log_conversation(
                                    session_id=session_id,
                                    user_message=query,
                                    assistant_response=response,
                                    knowledge_base=None,  # Phonebook query
                                    client_ip=client_ip
                                )
                    finally:
                        memory.close()
                        if db:
                            db.close()
                    
                    # Stream response
                    for char in response:
                        yield char
                    return  # DO NOT query LightRAG for contact queries
                    
            except Exception as e:
                # For contact queries, even if phonebook has an error, don't use LightRAG
                logger.error(f"[ERROR] Phonebook error for contact query (NOT using LightRAG): {e}")
                response = "I'm having trouble accessing the employee directory right now. "
                response += "Please try again in a moment, or contact support for assistance."
                response += "\n\n(Source: Phone Book Database)"
                
                # Save to memory
                db = get_db()
                memory = PostgresChatMemory(db=db)
                try:
                    if memory._available:
                        memory.add_message(session_id, "user", query)
                        memory.add_message(session_id, "assistant", response)
                        # Log for analytics
                        if ANALYTICS_AVAILABLE:
                            log_conversation(
                                session_id=session_id,
                                user_message=query,
                                assistant_response=response,
                                knowledge_base=None  # Phonebook query
                            )
                finally:
                    memory.close()
                    if db:
                        db.close()
                
                # Stream response
                for char in response:
                    yield char
                return  # DO NOT query LightRAG for contact queries
        
        # Determine if we need LightRAG context (only for non-contact queries)
        context = ""
        card_rates_context = ""
        
        if not is_small_talk:
            # Check for policy queries and validate required entities
            if is_compliance_query:
                has_entities, clarification = self._check_policy_entities(query)
                if not has_entities and clarification:
                    logger.info(f"[POLICY] Policy query missing required entities, asking for clarification")
                    # Save to memory
                    db = get_db()
                    memory = PostgresChatMemory(db=db)
                    try:
                        if memory._available:
                            memory.add_message(session_id, "user", query)
                            memory.add_message(session_id, "assistant", clarification)
                            # Log for analytics
                            if ANALYTICS_AVAILABLE:
                                log_conversation(
                                    session_id=session_id,
                                    user_message=query,
                                    assistant_response=clarification,
                                    knowledge_base=None,  # Clarification question
                                    client_ip=client_ip
                                )
                    finally:
                        memory.close()
                        if db:
                            db.close()
                    
                    # Stream clarification question
                    for char in clarification:
                        yield char
                    return  # Don't query LightRAG if entities are missing
            
            # If it's a card rates query, call card rates microservice for deterministic numbers
            if self._is_card_rates_query(query):
                logger.info(f"[CARD_RATES] Detected card rates query: '{query}'")
                card_rates_context = await self._get_card_rates_context(query)
                if card_rates_context:
                    logger.info(f"[CARD_RATES] Card rates context added (length: {len(card_rates_context)} chars)")
                else:
                    logger.warning(f"[CARD_RATES] No context returned from microservice for query: '{query}'")
            
            # Smart routing: determine which knowledge base to use based on query content
            # This prevents confusion between financial reports and user documents
            if knowledge_base is None:
                knowledge_base = self._get_knowledge_base(query)
            
            logger.info(f"[ROUTING] Calling LightRAG with knowledge_base='{knowledge_base}' for query: '{query[:100]}'")
            context = await self._get_lightrag_context(query, knowledge_base)
            if context:
                logger.info(f"[ROUTING] LightRAG returned context (length: {len(context)} chars)")
            else:
                logger.warning(f"[ROUTING] LightRAG returned empty context")
        
        # Combine card rates context (if any) with LightRAG context
        combined_context = ""
        if card_rates_context and context:
            combined_context = f"{card_rates_context}\n\n{context}"
            logger.info(f"[CARD_RATES] Combined context: card_rates={len(card_rates_context)} chars, lightrag={len(context)} chars")
        elif card_rates_context:
            combined_context = card_rates_context
            logger.info(f"[CARD_RATES] Using only card rates context: {len(card_rates_context)} chars")
        else:
            combined_context = context
        
        # Build messages
        messages = self._build_messages(query, combined_context, conversation_history)
        
        # Save user message
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            if memory._available:
                memory.add_message(session_id, "user", query)
        finally:
            memory.close()
            if db:
                db.close()
        
        # Stream response from OpenAI
        full_response = ""
        try:
            stream = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    # Clean markdown formatting from content before yielding
                    cleaned_content = self._clean_markdown_formatting(content)
                    # Fix currency symbols if needed (use combined_context if available)
                    if hasattr(self, '_last_combined_context'):
                        cleaned_content = self._fix_currency_symbols(cleaned_content, self._last_combined_context)
                    yield cleaned_content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            error_message = "I apologize, but I'm experiencing technical difficulties. Please try again later."
            yield error_message
            full_response = error_message
        
        # Clean markdown formatting from full response before saving
        full_response = self._clean_markdown_formatting(full_response)
        # Fix currency symbols as a safety net
        full_response = self._fix_currency_symbols(full_response, combined_context)
        
        # Save assistant response
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            if memory._available:
                memory.add_message(session_id, "assistant", full_response)
                # Log for analytics
                if ANALYTICS_AVAILABLE:
                    log_conversation(
                        session_id=session_id,
                        user_message=query,
                        assistant_response=full_response,
                        knowledge_base=knowledge_base,
                        client_ip=client_ip
                    )
        finally:
            memory.close()
            if db:
                db.close()
    
    async def process_chat_sync(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a chat query and return complete response (non-streaming)
        
        Args:
            query: User's query
            session_id: Session ID for conversation history
            knowledge_base: LightRAG knowledge base name
        
        Returns:
            Dictionary with response and session_id
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get conversation history
        db = get_db()
        memory = PostgresChatMemory(db=db)
        conversation_history = []
        try:
            if memory._available:
                history = memory.get_conversation_history(
                    session_id=session_id,
                    limit=settings.MAX_CONVERSATION_HISTORY
                )
                conversation_history = [
                    {"role": msg.role, "message": msg.message}
                    for msg in history
                ]
        finally:
            memory.close()
            if db:
                db.close()
        
        # ===== ROUTING DECISION LOGGING =====
        logger.info(f"[ROUTING] ===== Processing Query (SYNC): '{query}' =====")
        
        # CRITICAL: Check for banking product/compliance/management/financial/milestone/user document queries FIRST
        # These should go to LightRAG, NOT phonebook
        is_banking_product_query = self._is_banking_product_query(query)
        is_compliance_query = self._is_compliance_query(query)
        is_management_query = self._is_management_query(query)
        is_financial_query = self._is_financial_report_query(query)
        is_milestone_query = self._is_milestone_query(query)
        is_user_doc_query = self._is_user_document_query(query)
        
        # Log all routing checks
        logger.info(f"[ROUTING] Routing checks - banking_product={is_banking_product_query}, compliance={is_compliance_query}, management={is_management_query}, financial={is_financial_query}, milestone={is_milestone_query}, user_doc={is_user_doc_query}")
        
        # If it's a banking product/compliance/management/financial/milestone/user document query, skip phonebook and go to LightRAG
        if is_banking_product_query or is_compliance_query or is_management_query or is_financial_query or is_milestone_query or is_user_doc_query:
            routing_type = []
            if is_banking_product_query:
                routing_type.append("banking_product")
            if is_compliance_query:
                routing_type.append("compliance")
            if is_management_query:
                routing_type.append("management")
            if is_financial_query:
                routing_type.append("financial")
            if is_milestone_query:
                routing_type.append("milestone")
            if is_user_doc_query:
                routing_type.append("user_doc")
            logger.info(f"[ROUTING] ✓ Query detected as special ({', '.join(routing_type)}) → ROUTING TO LIGHTRAG (skipping phonebook)")
            should_check_phonebook = False
            is_phonebook_query = False
            is_contact_query = False
            is_employee_query = False
            is_small_talk = False
        else:
            # Check PostgreSQL phonebook FIRST for ANY contact-related query
            # This ensures contact queries NEVER go to LightRAG - always check phonebook first
            is_small_talk = self._is_small_talk(query)
            is_contact_query = self._is_contact_info_query(query)
            is_phonebook_query = self._is_phonebook_query(query)
            is_employee_query = self._is_employee_query(query)
            
            # Log contact-related checks
            logger.info(f"[ROUTING] Contact checks - small_talk={is_small_talk}, contact={is_contact_query}, phonebook={is_phonebook_query}, employee={is_employee_query}, phonebook_available={PHONEBOOK_DB_AVAILABLE}")
            
            # If it's any kind of contact/phonebook/employee query, ALWAYS check phonebook first
            should_check_phonebook = (
                (is_phonebook_query or is_contact_query or is_employee_query) 
                and not is_small_talk 
                and PHONEBOOK_DB_AVAILABLE
            )
            
            if should_check_phonebook:
                logger.info(f"[ROUTING] ✓ Query detected as contact/phonebook/employee → ROUTING TO PHONEBOOK (NOT LightRAG)")
            elif is_small_talk:
                logger.info(f"[ROUTING] ✓ Query detected as small talk → ROUTING TO OPENAI (no LightRAG)")
            else:
                logger.info(f"[ROUTING] ✓ Query not matched to special categories → ROUTING TO LIGHTRAG (default)")
        
        logger.info(f"[ROUTING] Final decision - will_check_phonebook={should_check_phonebook}, will_use_lightrag={not should_check_phonebook and not is_small_talk}")
        
        # Check phonebook FIRST for contact queries (before LightRAG)
        if should_check_phonebook:
            try:
                phonebook_db = get_phonebook_db()
                
                # Extract search term from query
                import re
                search_term = re.sub(
                    r'\b(phone|contact|number|email|address|mobile|telephone|of|for|the)\b', 
                    '', 
                    query, 
                    flags=re.IGNORECASE
                ).strip()
                
                # Try multiple search strategies
                results = phonebook_db.smart_search(search_term, limit=5)
                
                if results:
                    logger.info(f"[OK] Found {len(results)} results in phonebook for: {search_term}")
                    
                    # Format and return results
                    if len(results) == 1:
                        # Single result - detailed format
                        response = phonebook_db.format_contact_info(results[0])
                        response += "\n\n(Source: Phone Book Database)"
                    else:
                        # Multiple results - list format
                        response = ""
                        for i, emp in enumerate(results[:5], 1):
                            response += f"{i}. {emp['full_name']}\n"
                            if emp.get('designation'):
                                response += f"   Designation: {emp['designation']}\n"
                            if emp.get('department'):
                                response += f"   Department: {emp['department']}\n"
                            if emp.get('email'):
                                response += f"   Email: {emp['email']}\n"
                            if emp.get('mobile'):
                                response += f"   Mobile: {emp['mobile']}\n"
                            response += "\n"
                        
                        total_count = phonebook_db.count_search_results(search_term)
                        response += f"We found {total_count} matching contact(s) in total. Showing only the top 5 results.\n\n"
                        if total_count > 5:
                            response += "Please provide more details to narrow down the search.\n\n"
                        response += "(Source: Phone Book Database)"
                    
                    # Save to memory
                    db = get_db()
                    memory = PostgresChatMemory(db=db)
                    try:
                        if memory._available:
                            memory.add_message(session_id, "user", query)
                            memory.add_message(session_id, "assistant", response)
                            # Log for analytics
                            if ANALYTICS_AVAILABLE:
                                log_conversation(
                                    session_id=session_id,
                                    user_message=query,
                                    assistant_response=response,
                                    knowledge_base=None,  # Phonebook query
                                    client_ip=client_ip
                                )
                    finally:
                        memory.close()
                        if db:
                            db.close()
                    
                    return {
                        "response": response,
                        "session_id": session_id
                    }  # DO NOT query LightRAG for contact queries
                    
                else:
                    # No results in phonebook - return helpful message (DO NOT use LightRAG)
                    logger.info(f"[INFO] No results in phonebook for '{search_term}' (contact query - NOT using LightRAG)")
                    response = f"I couldn't find any contact information for '{search_term}' in the employee directory. "
                    response += "Please try:\n"
                    response += "- Providing the full name\n"
                    response += "- Using the employee ID\n"
                    response += "- Specifying the department or designation\n"
                    response += "\n(Source: Phone Book Database)"
                    
                    # Save to memory
                    db = get_db()
                    memory = PostgresChatMemory(db=db)
                    try:
                        if memory._available:
                            memory.add_message(session_id, "user", query)
                            memory.add_message(session_id, "assistant", response)
                            # Log for analytics
                            if ANALYTICS_AVAILABLE:
                                log_conversation(
                                    session_id=session_id,
                                    user_message=query,
                                    assistant_response=response,
                                    knowledge_base=None,  # Phonebook query
                                    client_ip=client_ip
                                )
                    finally:
                        memory.close()
                        if db:
                            db.close()
                    
                    return {
                        "response": response,
                        "session_id": session_id
                    }  # DO NOT query LightRAG for contact queries
                    
            except Exception as e:
                # For contact queries, even if phonebook has an error, don't use LightRAG
                logger.error(f"[ERROR] Phonebook error for contact query (NOT using LightRAG): {e}")
                response = "I'm having trouble accessing the employee directory right now. "
                response += "Please try again in a moment, or contact support for assistance."
                response += "\n\n(Source: Phone Book Database)"
                
                # Save to memory
                db = get_db()
                memory = PostgresChatMemory(db=db)
                try:
                    if memory._available:
                        memory.add_message(session_id, "user", query)
                        memory.add_message(session_id, "assistant", response)
                        # Log for analytics
                        if ANALYTICS_AVAILABLE:
                            log_conversation(
                                session_id=session_id,
                                user_message=query,
                                assistant_response=response,
                                knowledge_base=None  # Phonebook query
                            )
                finally:
                    memory.close()
                    if db:
                        db.close()
                
                    return {
                        "response": response,
                        "session_id": session_id
                    }  # DO NOT query LightRAG for contact queries
        
        # Determine if we need LightRAG context (only for non-contact queries)
        context = ""
        card_rates_context = ""
        
        if not is_small_talk:
            # Check for policy queries and validate required entities
            if is_compliance_query:
                has_entities, clarification = self._check_policy_entities(query)
                if not has_entities and clarification:
                    logger.info(f"[POLICY] Policy query missing required entities, asking for clarification")
                    # Save to memory
                    db = get_db()
                    memory = PostgresChatMemory(db=db)
                    try:
                        if memory._available:
                            memory.add_message(session_id, "user", query)
                            memory.add_message(session_id, "assistant", clarification)
                            # Log for analytics
                            if ANALYTICS_AVAILABLE:
                                log_conversation(
                                    session_id=session_id,
                                    user_message=query,
                                    assistant_response=clarification,
                                    knowledge_base=None,  # Clarification question
                                    client_ip=client_ip
                                )
                    finally:
                        memory.close()
                        if db:
                            db.close()
                    
                    return {
                        "response": clarification,
                        "session_id": session_id
                    }  # Don't query LightRAG if entities are missing
            
            # If it's a card rates query, call card rates microservice for deterministic numbers
            if self._is_card_rates_query(query):
                logger.info(f"[CARD_RATES] Detected card rates query: '{query}'")
                card_rates_context = await self._get_card_rates_context(query)
                if card_rates_context:
                    logger.info(f"[CARD_RATES] Card rates context added (length: {len(card_rates_context)} chars)")
                else:
                    logger.warning(f"[CARD_RATES] No context returned from microservice for query: '{query}'")
            
            # Smart routing: determine which knowledge base to use based on query content
            # This prevents confusion between financial reports and user documents
            if knowledge_base is None:
                knowledge_base = self._get_knowledge_base(query)
            
            logger.info(f"[ROUTING] Calling LightRAG with knowledge_base='{knowledge_base}' for query: '{query[:100]}'")
            context = await self._get_lightrag_context(query, knowledge_base)
            if context:
                logger.info(f"[ROUTING] LightRAG returned context (length: {len(context)} chars)")
            else:
                logger.warning(f"[ROUTING] LightRAG returned empty context")
        
        # Combine card rates context (if any) with LightRAG context
        combined_context = ""
        if card_rates_context and context:
            combined_context = f"{card_rates_context}\n\n{context}"
            logger.info(f"[CARD_RATES] Combined context: card_rates={len(card_rates_context)} chars, lightrag={len(context)} chars")
        elif card_rates_context:
            combined_context = card_rates_context
            logger.info(f"[CARD_RATES] Using only card rates context: {len(card_rates_context)} chars")
        else:
            combined_context = context
        
        # Store combined context for currency fixing
        self._last_combined_context = combined_context
        
        # Build messages
        messages = self._build_messages(query, combined_context, conversation_history)
        
        # Save user message
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            if memory._available:
                memory.add_message(session_id, "user", query)
        finally:
            memory.close()
            if db:
                db.close()
        
        # Get response from OpenAI
        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                stream=False
            )
            
            full_response = response.choices[0].message.content
            # Clean markdown formatting from response
            full_response = self._clean_markdown_formatting(full_response)
            # Fix currency symbols as a safety net
            full_response = self._fix_currency_symbols(full_response, combined_context)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            full_response = "I apologize, but I'm experiencing technical difficulties. Please try again later."
        
        # Save assistant response
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            if memory._available:
                memory.add_message(session_id, "assistant", full_response)
                # Log for analytics
                if ANALYTICS_AVAILABLE:
                    log_conversation(
                        session_id=session_id,
                        user_message=query,
                        assistant_response=full_response,
                        knowledge_base=knowledge_base,
                        client_ip=client_ip
                    )
        finally:
            memory.close()
            if db:
                db.close()
        
        return {
            "response": full_response,
            "session_id": session_id
        }

