"""
Handlers package for ChatOrchestrator.

This package contains focused handler classes extracted from the ChatOrchestrator
to address the God Object anti-pattern.

Classes:
- QueryClassifier: Classifies queries into categories (fee, location, phonebook, etc.)
- ResponseFormatter: Formats responses, fixes currency symbols, cleans markdown
- DisambiguationHandler: Manages disambiguation state and resolution
"""

from .query_classifier import QueryClassifier
from .response_formatter import ResponseFormatter
from .disambiguation_handler import DisambiguationHandler
from .lead_capture_handler import LeadCaptureHandler
from .phonebook_handler import PhonebookHandler
from .forms_handler import FormsHandler
from .app_links_handler import AppLinksHandler
from .leadership_handler import LeadershipHandler
from .soc_handler import SocHandler
from .proposals_handler import ProposalsHandler
from .circulars_handler import CircularsHandler

__all__ = [
    "QueryClassifier",
    "ResponseFormatter", 
    "DisambiguationHandler",
    "LeadCaptureHandler",
    "PhonebookHandler",
    "FormsHandler",
    "AppLinksHandler",
    "LeadershipHandler",
    "SocHandler",
    "ProposalsHandler",
    "CircularsHandler",
]
