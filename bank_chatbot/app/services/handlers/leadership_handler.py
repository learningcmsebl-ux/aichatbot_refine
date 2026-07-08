"""
Leadership Handler — EBL Home management committee and board of directors.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SOURCE_FOOTER = "(Source: EBL Home Leadership)"

_CATEGORY_LABELS = {
    "management": "Management Committee",
    "director": "Board of Directors",
}

_LIST_QUERY_PATTERNS = (
    (re.compile(r"\b(board\s+of\s+directors?|board\s+members?|directors?\s+board)\b"), "director"),
    (re.compile(r"\b(management\s+committee|mancom|management\s+team|ebl\s+management|bank\s+management|leadership\s+team)\b"), "management"),
)

_EXECUTIVE_ROLE_TERMS = (
    "managing director",
    "deputy managing director",
    "chief financial officer",
    "chief technology officer",
    "chief information officer",
    "chief risk officer",
    "chairman",
    "chairperson",
    "cfo",
    "cto",
    "cio",
    "cro",
    "dmd",
    "md and ceo",
    "md & ceo",
)


@dataclass(frozen=True)
class LeadershipLookupResult:
    response_text: str
    search_term: str = ""
    result_count: int = 0
    found: bool = False
    unavailable: bool = False
    error: bool = False


class LeadershipHandler:
    """Parse leadership queries and return EBL Home profiles with photos."""

    def detect_list_category(self, query: str) -> Optional[str]:
        query_lower = (query or "").lower().strip()
        for pattern, category in _LIST_QUERY_PATTERNS:
            if pattern.search(query_lower):
                return category
        return None

    def extract_search_term(self, query: str) -> str:
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return ""

        patterns = (
            r"^(?:who\s+is\s+(?:the\s+)?|tell\s+me\s+about\s+(?:the\s+)?|show\s+me\s+(?:the\s+)?|find\s+(?:the\s+)?)(.+)$",
            r"^(?:ebl\s*home|eblhome)\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                return self._cleanup_search_term(match.group(1))

        return self._cleanup_search_term(query)

    @staticmethod
    def _cleanup_search_term(search_term: str) -> str:
        term = re.sub(r"\s+", " ", (search_term or "").strip())
        term = re.sub(r"[?.!]+$", "", term).strip()
        noise = (
            r"\b(the|a|an|for|from|on|in|at|to|please|can|you|me|my|i|"
            r"who|is|are|tell|about|show|find|photo|picture|profile|"
            r"ebl|home|eblhome|bank|management|committee|director|directors)\b"
        )
        term = re.sub(noise, " ", term, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", term).strip()

    @staticmethod
    def _category_label(category: str) -> str:
        return _CATEGORY_LABELS.get(category, category.replace("_", " ").title())

    @staticmethod
    def _photo_proxy_url(source_post_id: int) -> str:
        # Same-origin relative path so portraits load on dia.ebl-bd.com (and any gateway host).
        return f"/api/leadership/photo/{source_post_id}"

    def format_profile(self, leader: Dict) -> List[str]:
        lines = [
            f"Name: {leader['full_name']}",
            f"Designation: {leader.get('designation') or 'N/A'}",
            f"Category: {self._category_label(leader.get('category', ''))}",
        ]
        if leader.get("source_post_id") and leader.get("photo_url"):
            lines.append(f"Photo: {self._photo_proxy_url(leader['source_post_id'])}")
        elif leader.get("photo_url"):
            lines.append(f"Photo: {leader['photo_url']}")
        return lines

    def format_response(self, results: List[Dict], *, list_category: Optional[str] = None) -> str:
        if not results:
            return ""

        lines: List[str] = []
        if list_category:
            label = self._category_label(list_category)
            lines.append(f"Here is the {label} from EBL Home:\n")
        elif len(results) == 1:
            lines.append("Here is the leadership profile from EBL Home:\n")
        else:
            lines.append("I found the following leadership profiles on EBL Home:\n")

        for index, leader in enumerate(results, 1):
            if len(results) > 1:
                lines.append(f"{index}. {leader['full_name']}")
                profile_lines = self.format_profile(leader)
                for profile_line in profile_lines[1:]:
                    lines.append(f"   {profile_line}")
            else:
                lines.extend(self.format_profile(leader))
            lines.append("")

        lines.append(SOURCE_FOOTER)
        return "\n".join(lines)

    @staticmethod
    def _format_not_found(search_term: str) -> str:
        return (
            f"I couldn't find a leadership profile for '{search_term}' in the EBL Home index. "
            "Please try:\n"
            "- Using the executive role (e.g., 'Who is the CFO?')\n"
            "- Using the person's name\n"
            "- Asking for 'management committee' or 'board of directors'\n"
            f"\n{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_unavailable() -> str:
        return (
            "I'm having trouble accessing the EBL Home leadership index right now. "
            "Please try again in a moment.\n\n"
            f"{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_empty_index() -> str:
        return (
            "The EBL Home leadership index has not been loaded yet. "
            "Please ask your administrator to run the leadership sync job.\n\n"
            f"{SOURCE_FOOTER}"
        )

    def lookup(self, query: str, leadership_db: Optional[Any]) -> LeadershipLookupResult:
        if leadership_db is None:
            return LeadershipLookupResult(response_text=self._format_unavailable(), unavailable=True)

        try:
            if leadership_db.total_leaders() == 0:
                return LeadershipLookupResult(response_text=self._format_empty_index(), unavailable=True)

            list_category = self.detect_list_category(query)
            if list_category:
                results = leadership_db.list_by_category(list_category, limit=15)
                search_term = list_category
                if results:
                    return LeadershipLookupResult(
                        response_text=self.format_response(results, list_category=list_category),
                        search_term=search_term,
                        result_count=len(results),
                        found=True,
                    )
                return LeadershipLookupResult(
                    response_text=self._format_not_found(search_term),
                    search_term=search_term,
                    found=False,
                )

            search_term = self.extract_search_term(query) or (query or "").strip()
            results = leadership_db.smart_search(query, limit=5)
            if not results and search_term != query:
                results = leadership_db.smart_search(search_term, limit=5)

            if results:
                return LeadershipLookupResult(
                    response_text=self.format_response(results),
                    search_term=search_term,
                    result_count=len(results),
                    found=True,
                )

            return LeadershipLookupResult(
                response_text=self._format_not_found(search_term),
                search_term=search_term,
                found=False,
            )
        except Exception as exc:
            logger.error("[LEADERSHIP] Error for leadership query: %s", exc, exc_info=True)
            return LeadershipLookupResult(response_text=self._format_unavailable(), error=True)
