"""
Phonebook Handler - Natural-language query parsing, search, and response formatting.

Extracted from ChatOrchestrator so stream and sync paths share one implementation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SOURCE_FOOTER = "(Source: Phone Book Database)"

_DIVISION_DEPT_KEYWORDS = (
    "banking",
    "division",
    "department",
    "unit",
    "section",
    "retail",
    "sme",
    "corporate",
    "operations",
    "finance",
    "hr",
    "ict",
    "it",
)

_ROLE_KEYWORDS = (
    "head",
    "manager",
    "director",
    "officer",
    "executive",
    "president",
    "ceo",
    "cfo",
    "chief",
    "senior",
    "assistant",
)


@dataclass(frozen=True)
class PhonebookLookupResult:
    """Result of a phonebook lookup (deterministic text for the user)."""

    response_text: str
    search_term: str = ""
    result_count: int = 0
    found: bool = False
    unavailable: bool = False
    error: bool = False


class PhonebookHandler:
    """Parse employee lookup queries and return formatted contact information."""

    def extract_search_term(self, query: str) -> str:
        """Derive a phonebook search term from a natural-language query."""
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return ""

        role_location_pattern = r"(branch\s+)?manager\s+(of|at)\s+(.+?)(?:\s+branch)?$"
        match = re.search(role_location_pattern, query_lower)
        if match:
            location = match.group(3).strip()
            role = f"{match.group(1)}manager" if match.group(1) else "manager"
            search_term = f"{role} {location}"
            logger.info("[PHONEBOOK] Extracted role+location query: '%s' from '%s'", search_term, query)
            return search_term

        find_search_pattern = r"^(find|search|lookup|who is|contact|info about|get)\s+(.+)$"
        match = re.search(find_search_pattern, query_lower, re.IGNORECASE)
        if match:
            search_term = match.group(2).strip()
            logger.info(
                "[PHONEBOOK] Extracted search term '%s' from query '%s' (removed prefix '%s')",
                search_term,
                query,
                match.group(1),
            )
            return self._cleanup_search_term(search_term)

        of_for_patterns = (
            r"\b(phone|contact|email|mobile|telephone)\s+number\s+(?:of|for|about)\s+(.+)$",
            r"\b(phone|contact|email|mobile|telephone)\s+(?:of|for|about)\s+(.+)$",
            r"\b(contact|info|information|details?)\s+(?:info|information|details?)?\s+(?:of|for|about)\s+(.+)$",
        )
        for pattern in of_for_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                search_term = match.group(2).strip() if len(match.groups()) >= 2 else match.group(1).strip()
                logger.info(
                    "[PHONEBOOK] Extracted search term '%s' from query '%s' (contact prefix)",
                    search_term,
                    query,
                )
                return self._cleanup_search_term(search_term)

        search_term = re.sub(
            r"\b(phone|contact|number|email|address|mobile|telephone|who\s+is|what\s+is|tell\s+me|the|is|are|was|were|of|for|about)\b",
            "",
            query,
            flags=re.IGNORECASE,
        ).strip()
        return self._cleanup_search_term(search_term)

    @staticmethod
    def _cleanup_search_term(search_term: str) -> str:
        term = re.sub(r"\s+", " ", (search_term or "").strip())
        term = re.sub(r"[?.!]+$", "", term).strip()
        term = re.sub(r"^(of|for|about)\s+", "", term, flags=re.IGNORECASE).strip()
        term = re.sub(r"\s+(of|for|about)$", "", term, flags=re.IGNORECASE).strip()
        term = re.sub(
            r"\s+(of|at|in)\s+(ebl|eastern\s+bank|eastern\s+bank\s+plc)[\s.]*$",
            "",
            term,
            flags=re.IGNORECASE,
        ).strip()

        original = term
        term = re.sub(r"\bdivision\b", "", term, flags=re.IGNORECASE).strip()
        term = re.sub(r"\s+", " ", term).strip()
        if original != term:
            logger.info("[PHONEBOOK] Removed 'division' from search term: '%s' -> '%s'", original, term)
        return term

    @staticmethod
    def _final_cleanup(search_term: str) -> str:
        term = re.sub(
            r"\s+(of|at|in)\s+(ebl|eastern\s+bank|eastern\s+bank\s+plc)[\s.]*$",
            "",
            search_term,
            flags=re.IGNORECASE,
        ).strip()
        term = re.sub(r"\bdivision\b", "", term, flags=re.IGNORECASE).strip()
        return re.sub(r"\s+", " ", term).strip()

    def search(self, phonebook_db: Any, query: str, *, limit: int = 5) -> tuple[List[Dict], str]:
        """Run phonebook search strategies and return (results, effective_search_term)."""
        search_term = self.extract_search_term(query)
        results = self._search_with_fallbacks(phonebook_db, search_term, limit=limit)

        final_term = self._final_cleanup(search_term)
        if final_term != search_term:
            logger.info("[PHONEBOOK] Final cleanup: '%s' -> '%s'", search_term, final_term)
            search_term = final_term
            if not results:
                results = phonebook_db.smart_search(search_term, limit=limit)

        return results, search_term

    def _search_with_fallbacks(
        self,
        phonebook_db: Any,
        search_term: str,
        *,
        limit: int = 5,
    ) -> List[Dict]:
        if not search_term:
            return []

        term_lower = search_term.lower()
        has_division_keyword = any(
            re.search(rf"\b{re.escape(keyword)}\b", term_lower)
            for keyword in _DIVISION_DEPT_KEYWORDS
        )
        has_role_keyword = any(
            re.search(rf"\b{re.escape(keyword)}\b", term_lower)
            for keyword in _ROLE_KEYWORDS
        )

        if has_division_keyword and not has_role_keyword:
            term_with_head = f"{search_term} head"
            logger.info(
                "[PHONEBOOK] Division/department without role; trying with 'head': '%s'",
                term_with_head,
            )
            results = phonebook_db.smart_search(term_with_head, limit=limit)
            if results:
                return results

            logger.info("[PHONEBOOK] No results with 'head'; trying department search for: '%s'", search_term)
            dept_results = phonebook_db.search_by_department(search_term, limit=limit)
            if dept_results:
                return dept_results

        return phonebook_db.smart_search(search_term, limit=limit)

    def format_response(self, phonebook_db: Any, results: List[Dict], search_term: str) -> str:
        """Format one or many employee matches for chat display."""
        if not results:
            return self._format_not_found(search_term)

        if len(results) == 1:
            return f"{phonebook_db.format_contact_info(results[0])}\n\n{SOURCE_FOOTER}"

        lines: List[str] = []
        for i, emp in enumerate(results[:5], 1):
            lines.append(f"{i}. {emp['full_name']}")
            if emp.get("designation"):
                lines.append(f"   Designation: {emp['designation']}")
            if emp.get("department"):
                lines.append(f"   Department: {emp['department']}")
            if emp.get("email"):
                lines.append(f"   Email: {emp['email']}")
            if emp.get("employee_id"):
                lines.append(f"   Employee ID: {emp['employee_id']}")
            if emp.get("mobile"):
                lines.append(f"   Mobile: {emp['mobile']}")
            if emp.get("ip_phone"):
                lines.append(f"   IP Phone: {emp['ip_phone']}")
            lines.append("")

        total_count = phonebook_db.count_search_results(search_term)
        lines.append(f"We found {total_count} matching contact(s) in total. Showing only the top 5 results.\n")
        if total_count > 5:
            lines.append("Please provide more details to narrow down the search.\n")
        lines.append(SOURCE_FOOTER)
        return "\n".join(lines)

    @staticmethod
    def _format_not_found(search_term: str) -> str:
        return (
            f"I couldn't find any contact information for '{search_term}' in the employee directory. "
            "Please try:\n"
            "- Providing the full name\n"
            "- Using the employee ID\n"
            "- Specifying the department or designation\n"
            f"\n{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_unavailable() -> str:
        return (
            "I'm having trouble accessing the employee directory right now. "
            "Please try again in a moment, or contact support for assistance.\n\n"
            f"{SOURCE_FOOTER}"
        )

    def lookup(self, query: str, phonebook_db: Optional[Any]) -> PhonebookLookupResult:
        """
        End-to-end phonebook lookup. Never falls back to LightRAG.
        """
        if phonebook_db is None:
            logger.warning("[PHONEBOOK] Phonebook DB unavailable; cannot serve phonebook request.")
            return PhonebookLookupResult(
                response_text=self._format_unavailable(),
                unavailable=True,
            )

        try:
            results, search_term = self.search(phonebook_db, query)
            if results:
                logger.info("[PHONEBOOK] Found %s result(s) for: %s", len(results), search_term)
                return PhonebookLookupResult(
                    response_text=self.format_response(phonebook_db, results, search_term),
                    search_term=search_term,
                    result_count=len(results),
                    found=True,
                )

            logger.info("[PHONEBOOK] No results for '%s' (NOT using LightRAG)", search_term)
            return PhonebookLookupResult(
                response_text=self._format_not_found(search_term),
                search_term=search_term,
                found=False,
            )
        except Exception as exc:
            logger.error("[PHONEBOOK] Error for contact query (NOT using LightRAG): %s", exc, exc_info=True)
            return PhonebookLookupResult(
                response_text=self._format_unavailable(),
                error=True,
            )
