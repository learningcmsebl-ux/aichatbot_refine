"""
Chat Orchestrator - Coordinates all components for chat processing.
"""

import uuid
import logging
from typing import Optional, AsyncGenerator, List, Dict, Any
from datetime import datetime
import pytz

from openai import AsyncOpenAI

from app.core.config import settings
from app.database.postgres import PostgresChatMemory, get_db
from app.database.redis_client import RedisCache, get_cache_key

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

logger = logging.getLogger(__name__)

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

Guidelines:
1. Always be professional, friendly, and helpful
2. Use the provided context from the knowledge base to answer questions accurately
3. If information is not available in the context, politely inform the user
4. For banking queries, always use the provided context from LightRAG
5. Never make up specific numbers, rates, or product details
6. If asked about products, services, or policies, refer to the knowledge base context
7. For general greetings or small talk, respond naturally without requiring context
8. When asked about the current date or time, use the provided current date and time information to answer accurately

When responding:
- Be concise but thorough
- Use clear, simple language
- Structure product information clearly
- Always prioritize accuracy over speed
- For date/time queries, provide the exact current date and time as provided in the context"""
    
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
        """Detect if query is about contact information (phone, address, email, etc.)
        This should ALWAYS check phonebook first, never LightRAG"""
        query_lower = query.lower().strip()
        
        # Comprehensive contact-related keywords - ANY of these means check phonebook first
        contact_keywords = [
            # Phone/Telephone
            'phone', 'telephone', 'tel', 'call', 'calling', 'dial', 'dialing',
            'number', 'phone number', 'telephone number', 'contact number',
            'mobile', 'cell', 'cellphone', 'mobile number', 'cell number',
            'pabx', 'extension', 'ext', 'ip phone', 'ip phone number',
            'direct line', 'direct number', 'landline',
            
            # Contact/Communication
            'contact', 'contacts', 'contact info', 'contact information',
            'reach', 'reach out', 'reachable', 'how to contact', 'how can i contact',
            'get in touch', 'get in touch with', 'connect with', 'connect to',
            
            # Email
            'email', 'e-mail', 'mail', 'email address', 'mail address',
            'email id', 'mail id', 'send email', 'email to',
            
            # Address/Location
            'address', 'location', 'where', 'where is', 'where are',
            'office address', 'work address', 'business address',
            
            # Employee/Staff related (these are always phonebook queries)
            'employee', 'employees', 'staff', 'staff member', 'staff members',
            'emp id', 'emp_id', 'employee id', 'employee number',
            'who is', 'who are', 'who works', 'who is working',
            
            # Designation/Department (often contact queries)
            'designation', 'department', 'division',
            'manager', 'director', 'officer', 'head of', 'head',
            'ceo', 'cfo', 'coo', 'president', 'executive',
            
            # Other contact-related
            'hotline', 'helpline', 'support line', 'customer service',
            'branch contact', 'office contact', 'head office', 'headquarters',
            'contact center', 'contact centre', 'call center', 'call centre'
        ]
        
        # Check if query contains ANY contact-related keywords
        # If yes, ALWAYS check phonebook first (never LightRAG)
        return any(keyword in query_lower for keyword in contact_keywords)
    
    def _is_phonebook_query(self, query: str) -> bool:
        """Detect if query is about phone book/employee contact information
        This should ALWAYS check phonebook first, never LightRAG"""
        query_lower = query.lower().strip()
        
        # Comprehensive phone book keywords - ANY of these means check phonebook first
        phonebook_keywords = [
            # Direct contact methods
            'phone', 'contact', 'number', 'telephone', 'tel', 'call',
            'email', 'address', 'mobile', 'cell', 'cellphone',
            'extension', 'ext', 'pabx', 'ip phone', 'ip phone number',
            'direct line', 'direct number', 'landline',
            
            # Employee/Staff identifiers
            'employee', 'employees', 'staff', 'staff member', 'staff members',
            'emp id', 'emp_id', 'employee id', 'employee number',
            'who is', 'who are', 'who works', 'who is working',
            
            # Contact information requests
            'contact info', 'contact information', 'contact details',
            'phone number', 'telephone number', 'contact number',
            'email address', 'mail address', 'office address',
            
            # Designation/Department (often used for contact queries)
            'designation', 'department', 'division',
            'manager', 'director', 'officer', 'head of', 'head',
            'ceo', 'cfo', 'coo', 'president', 'executive',
            
            # Directory/List queries
            'directory', 'phonebook', 'phone book', 'contact list',
            'employee directory', 'staff directory', 'employee list', 'staff list'
        ]
        
        # Check if query contains phone book keywords
        # If yes, ALWAYS check phonebook first (never LightRAG)
        return any(keyword in query_lower for keyword in phonebook_keywords)
    
    def _is_employee_query(self, query: str) -> bool:
        """Detect if query is about employee information"""
        query_lower = query.lower().strip()
        
        employee_keywords = [
            'employee', 'employees', 'staff', 'staff member', 'staff members',
            'emp id', 'emp_id', 'employee id', 'employee number',
            'designation', 'ip phone', 'ip phone number', 'pabx', 'extension',
            'who works', 'who is working', 'who are the employees', 'employee list',
            'staff list', 'employee directory', 'staff directory', 'employee contact',
            'staff contact', 'employee email', 'staff email', 'employee phone',
            'staff phone', 'employee information', 'staff information'
        ]
        
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
            'savings account', 'current account', 'fixed deposit', 'fd', 'rd', 'recurring deposit',
            'account opening', 'account balance', 'account statement', 'account fee',
            'account interest', 'account rate', 'account minimum balance',
            
            # Banking Services
            'online banking', 'mobile banking', 'internet banking', 'atm', 'cash withdrawal',
            'fund transfer', 'remittance', 'foreign exchange', 'forex', 'currency exchange',
            'locker', 'safe deposit', 'cheque', 'draft', 'demand draft',
            
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
    
    async def _get_lightrag_context(
        self,
        query: str,
        knowledge_base: Optional[str] = None
    ) -> str:
        """Get context from LightRAG (with caching)"""
        kb = knowledge_base or settings.LIGHTRAG_KNOWLEDGE_BASE
        cache_key = get_cache_key(query, kb)
        
        # Check cache first
        cached = await self.redis_cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT for query: {query[:50]}... (key: {cache_key})")
            return self._format_lightrag_context(cached)
        
        logger.info(f"Cache MISS for query: {query[:50]}... (key: {cache_key})")
        
        # Query LightRAG
        try:
            logger.info(f"Querying LightRAG for: {query[:50]}... (knowledge_base: {kb})")
            response = await self.lightrag_client.query(
                query=query,
                knowledge_base=kb,
                mode="hybrid",  # Match other LightRAG instance
                top_k=8,  # KG Top K: 8 (was 5)
                chunk_top_k=5,  # Chunk Top K: 5 (was 10)
                include_references=True,
                only_need_context=False,  # Get full response, not just context
                max_entity_tokens=2500,  # Max tokens for entities
                max_relation_tokens=3500,  # Max tokens for relations
                max_total_tokens=12000,  # Overall max tokens
                enable_rerank=True  # Enable reranking
                # Note: only_need_prompt and stream are UI settings, not API parameters
            )
            
            # Cache the response
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
            user_message = f"Context from knowledge base:\n{context}\n\nUser query: {query}{datetime_info}"
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
        knowledge_base: Optional[str] = None
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
        
        # CRITICAL: Check for banking product/compliance/management/financial/milestone/user document queries FIRST
        # These should go to LightRAG, NOT phonebook
        is_banking_product_query = self._is_banking_product_query(query)
        is_compliance_query = self._is_compliance_query(query)
        is_management_query = self._is_management_query(query)
        is_financial_query = self._is_financial_report_query(query)
        is_milestone_query = self._is_milestone_query(query)
        is_user_doc_query = self._is_user_document_query(query)
        
        # If it's a banking product/compliance/management/financial/milestone/user document query, skip phonebook and go to LightRAG
        if is_banking_product_query or is_compliance_query or is_management_query or is_financial_query or is_milestone_query or is_user_doc_query:
            logger.info(f"[ROUTING] Query detected as special (banking product/compliance/management/financial/milestone/user doc) - skipping phonebook, using LightRAG")
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
            
            # If it's any kind of contact/phonebook/employee query, ALWAYS check phonebook first
            should_check_phonebook = (
                (is_phonebook_query or is_contact_query or is_employee_query) 
                and not is_small_talk 
                and PHONEBOOK_DB_AVAILABLE
            )
        
        logger.info(f"[DEBUG] Phonebook priority: phonebook={is_phonebook_query}, contact={is_contact_query}, employee={is_employee_query}, small_talk={is_small_talk}, available={PHONEBOOK_DB_AVAILABLE}, will_check={should_check_phonebook}")
        
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
        
        if not is_small_talk:
            # Smart routing: determine which knowledge base to use based on query content
            # This prevents confusion between financial reports and user documents
            if knowledge_base is None:
                knowledge_base = self._get_knowledge_base(query)
            
            context = await self._get_lightrag_context(query, knowledge_base)
        
        # Build messages
        messages = self._build_messages(query, context, conversation_history)
        
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
                    yield cleaned_content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            error_message = "I apologize, but I'm experiencing technical difficulties. Please try again later."
            yield error_message
            full_response = error_message
        
        # Clean markdown formatting from full response before saving
        full_response = self._clean_markdown_formatting(full_response)
        
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
                        knowledge_base=knowledge_base
                    )
        finally:
            memory.close()
            if db:
                db.close()
    
    async def process_chat_sync(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None
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
        
        # CRITICAL: Check for banking product/compliance/management/financial/milestone/user document queries FIRST
        # These should go to LightRAG, NOT phonebook
        is_banking_product_query = self._is_banking_product_query(query)
        is_compliance_query = self._is_compliance_query(query)
        is_management_query = self._is_management_query(query)
        is_financial_query = self._is_financial_report_query(query)
        is_milestone_query = self._is_milestone_query(query)
        is_user_doc_query = self._is_user_document_query(query)
        
        # If it's a banking product/compliance/management/financial/milestone/user document query, skip phonebook and go to LightRAG
        if is_banking_product_query or is_compliance_query or is_management_query or is_financial_query or is_milestone_query or is_user_doc_query:
            logger.info(f"[ROUTING] Query detected as special (banking product/compliance/management/financial/milestone/user doc) - skipping phonebook, using LightRAG")
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
            
            # If it's any kind of contact/phonebook/employee query, ALWAYS check phonebook first
            should_check_phonebook = (
                (is_phonebook_query or is_contact_query or is_employee_query) 
                and not is_small_talk 
                and PHONEBOOK_DB_AVAILABLE
            )
        
        logger.info(f"[DEBUG] Phonebook priority: phonebook={is_phonebook_query}, contact={is_contact_query}, employee={is_employee_query}, small_talk={is_small_talk}, available={PHONEBOOK_DB_AVAILABLE}, will_check={should_check_phonebook}")
        
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
        
        if not is_small_talk:
            # Smart routing: determine which knowledge base to use based on query content
            # This prevents confusion between financial reports and user documents
            if knowledge_base is None:
                knowledge_base = self._get_knowledge_base(query)
            
            context = await self._get_lightrag_context(query, knowledge_base)
        
        # Build messages
        messages = self._build_messages(query, context, conversation_history)
        
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
                        knowledge_base=knowledge_base
                    )
        finally:
            memory.close()
            if db:
                db.close()
        
        return {
            "response": full_response,
            "session_id": session_id
        }

