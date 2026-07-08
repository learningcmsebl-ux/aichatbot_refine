"""
Response Formatter - Handles response formatting and text transformations.

Extracted from ChatOrchestrator to address the God Object anti-pattern.
This class is responsible for formatting responses, fixing currency symbols,
cleaning markdown, and other text transformations.
"""

import re
import logging
from typing import Optional, List
from datetime import datetime
import pytz

from app.core.config import settings

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Formats chatbot responses and performs text transformations.
    
    Responsibilities:
    - Clean markdown formatting
    - Fix currency symbols (prevent hallucination)
    - Fix bank name consistency
    - Format datetime strings
    - Format source markers
    
    Usage:
        formatter = ResponseFormatter()
        text = formatter.clean_markdown("**Bold text**")  # Returns "Bold text"
        text = formatter.fix_currency_symbols("₹100", context="BDT")  # Returns "BDT 100"
    """
    
    def __init__(self, timezone: str = "Asia/Dhaka"):
        """
        Initialize ResponseFormatter.
        
        Args:
            timezone: Timezone for datetime formatting (default: Asia/Dhaka)
        """
        self.timezone = timezone
        try:
            self.tz = pytz.timezone(timezone)
        except Exception:
            self.tz = pytz.UTC
            logger.warning(f"Invalid timezone '{timezone}', using UTC")
    
    def clean_markdown(self, text: str) -> str:
        """
        Remove markdown formatting from text.
        
        Args:
            text: Text potentially containing markdown
            
        Returns:
            Clean text without markdown syntax
        """
        if not text:
            return text
        
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
    
    def fix_currency_symbols(self, text: str, context: str = "") -> str:
        """
        Fix currency symbol hallucinations.
        
        Replaces incorrect currency symbols (like ₹) with correct ones (BDT)
        based on context.
        
        Args:
            text: Text potentially containing wrong currency symbols
            context: Context string to determine correct currency
            
        Returns:
            Text with corrected currency symbols
        """
        if not text:
            return text
        
        has_bdt_in_context = "BDT" in context if context else False
        
        if has_bdt_in_context:
            # Replace ₹ (Indian Rupee) with BDT
            text = re.sub(r'₹\s*(\d+(?:[.,]\d+)?)', r'BDT \1', text)
            text = re.sub(r'₹\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)', r'BDT \1', text)
        
        return text
    
    def fix_bank_name(self, text: str) -> str:
        """
        Fix bank name to ensure consistent usage.
        
        Replaces "Eastern Bank Limited" or "Eastern Bank Ltd." 
        with "Eastern Bank PLC." (with period).
        
        Args:
            text: Text potentially containing bank name variations
            
        Returns:
            Text with consistent bank name
        """
        if not text:
            return text
        
        # Replace "Eastern Bank Limited" with "Eastern Bank PLC."
        text = re.sub(r'Eastern Bank Limited', 'Eastern Bank PLC.', text, flags=re.IGNORECASE)
        # Replace "Eastern Bank Ltd." with "Eastern Bank PLC."
        text = re.sub(r'Eastern Bank Ltd\.', 'Eastern Bank PLC.', text, flags=re.IGNORECASE)
        # Replace "Eastern Bank Ltd" without period
        text = re.sub(r'Eastern Bank Ltd\b', 'Eastern Bank PLC.', text, flags=re.IGNORECASE)
        # Ensure "Eastern Bank PLC" (without period) becomes "Eastern Bank PLC."
        text = re.sub(r'\bEastern Bank PLC\b(?!\.)', 'Eastern Bank PLC.', text, flags=re.IGNORECASE)
        
        return text
    
    def get_current_datetime(self, format_type: str = "full") -> str:
        """
        Get current date and time as a formatted string.

        Uses settings.TIMEZONE when available (default UTC), matching the
        original ChatOrchestrator behavior. Falls back to system local time
        if the configured timezone is invalid.

        Args:
            format_type: "full" for date+time, "date" for date only, "time" for time only

        Returns:
            Formatted datetime string, e.g. "Monday, June 21, 2026 at 08:24:30 PM UTC"
        """
        try:
            timezone_str = getattr(settings, 'TIMEZONE', 'UTC')
            tz = pytz.timezone(timezone_str)
        except Exception:
            tz = None

        now = datetime.now(tz) if tz else datetime.now()

        date_str = now.strftime("%A, %B %d, %Y")
        if format_type == "date":
            return date_str

        time_str = now.strftime("%I:%M:%S %p")
        if format_type == "time":
            return time_str

        if tz:
            return f"{date_str} at {time_str} {now.strftime('%Z')}"
        return f"{date_str} at {time_str}"
    
    def format_sources_marker(self, sources: List[str]) -> str:
        """
        Format sources into a marker string for embedding in responses.
        
        Args:
            sources: List of source strings
            
        Returns:
            Formatted sources marker string
        """
        if not sources:
            return ""
        
        unique_sources = list(dict.fromkeys(sources))  # Preserve order, remove duplicates
        sources_str = ", ".join(unique_sources)
        return f"\n\n__SOURCES__{sources_str}__SOURCES__"
    
    def cap_prompt_section(self, label: str, text: str, max_chars: int = 4000) -> str:
        """
        Cap a prompt section to prevent overly large prompts.
        
        Args:
            label: Label for the section (for logging)
            text: Text to cap
            max_chars: Maximum characters allowed
            
        Returns:
            Capped text (truncated with ellipsis if needed)
        """
        if not text:
            return text
        
        if len(text) <= max_chars:
            return text
        
        logger.warning(f"[PROMPT] Capping {label} section from {len(text)} to {max_chars} chars")
        return text[:max_chars] + "... [truncated]"
    
    def format_error_response(self, error: Exception, user_friendly: bool = True) -> str:
        """
        Format an error into a user-friendly response.
        
        Args:
            error: The exception that occurred
            user_friendly: Whether to return user-friendly message
            
        Returns:
            Formatted error message
        """
        if user_friendly:
            return "I apologize, but I encountered an issue processing your request. Please try again or rephrase your question."
        else:
            return f"Error: {str(error)}"
    
    def format_disambiguation_prompt(
        self,
        options: List[dict],
        prompt_type: str = "loan_product"
    ) -> str:
        """
        Format a disambiguation prompt for the user.
        
        Args:
            options: List of option dictionaries
            prompt_type: Type of disambiguation (loan_product, fee_type, etc.)
            
        Returns:
            Formatted prompt string
        """
        if not options:
            return "Please provide more details about your query."
        
        if prompt_type == "loan_product":
            prompt_lines = [
                "Multiple loan products have this fee available.",
                "Please specify which loan product you're interested in:",
                ""
            ]
            for idx, option in enumerate(options, 1):
                name = option.get("loan_product_name", option.get("loan_product", ""))
                prompt_lines.append(f"{idx}. {name}")
        
        elif prompt_type == "fee_type":
            prompt_lines = [
                "Multiple fee types match your query.",
                "Please specify which fee you're asking about:",
                ""
            ]
            for idx, option in enumerate(options, 1):
                label = option.get("label", option.get("charge_type", ""))
                prompt_lines.append(f"{idx}. {label}")
        
        else:
            prompt_lines = [
                "Please select an option:",
                ""
            ]
            for idx, option in enumerate(options, 1):
                label = option.get("label", str(option))
                prompt_lines.append(f"{idx}. {label}")
        
        prompt_lines.extend([
            "",
            "Please reply with the number or name of your choice."
        ])
        
        return "\n".join(prompt_lines)
    
    def extract_query_anchors(self, query: str) -> List[str]:
        """
        Extract key anchors from a query for context matching.
        
        Args:
            query: The user's query
            
        Returns:
            List of anchor terms
        """
        if not query:
            return []
        
        # Common stop words to filter out
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "as", "into", "through", "during", "before",
            "after", "above", "below", "between", "under", "again",
            "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "just", "what", "which", "who",
            "whom", "this", "that", "these", "those", "am", "it", "its",
            "i", "me", "my", "myself", "you", "your", "yourself", "he",
            "him", "his", "himself", "she", "her", "hers", "herself",
            "we", "us", "our", "ourselves", "they", "them", "their",
        }
        
        # Tokenize and filter
        words = re.findall(r'\b[a-zA-Z]+\b', query.lower())
        anchors = [w for w in words if w not in stop_words and len(w) > 2]
        
        return anchors
    
    def truncate_text(self, text: str, max_length: int = 500, suffix: str = "...") -> str:
        """
        Truncate text to maximum length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add when truncated
            
        Returns:
            Truncated text
        """
        if not text or len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
