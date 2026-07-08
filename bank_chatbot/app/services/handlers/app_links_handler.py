"""
Application Links Handler — search EBL Home ebllinks and return open URLs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SOURCE_FOOTER = "(Source: EBL Home Applications)"


@dataclass(frozen=True)
class AppLinksLookupResult:
    response_text: str
    search_term: str = ""
    result_count: int = 0
    found: bool = False
    unavailable: bool = False
    error: bool = False


class AppLinksHandler:
    """Parse application link queries and return EBL Home app URLs."""

    def extract_search_term(self, query: str) -> str:
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return ""

        patterns = (
            r"^(?:open|access|launch|visit|go to|login to|log in to|find|search|need|where(?:\s+is|\s+can\s+i\s+(?:find|access|open))?|show\s+me)\s+(?:the\s+)?(.+)$",
            r"^(.+?)\s+(?:app|application|portal|hub|system)\s+(?:link|url|login)?$",
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
            r"open|access|launch|visit|go|login|log|link|url|"
            r"app|application|portal|hub|system|ebl|home|eblhome)\b"
        )
        term = re.sub(noise, " ", term, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", term).strip()

    def search(self, apps_db: Any, query: str, *, limit: int = 5) -> tuple[List[Dict], str]:
        search_term = self.extract_search_term(query)
        if not search_term:
            search_term = (query or "").strip()
        return apps_db.search(search_term, limit=limit), search_term

    def format_response(self, apps_db: Any, results: List[Dict], search_term: str) -> str:
        if not results:
            return self._format_not_found(search_term)

        lines: List[str] = []
        lines.append(
            "I found this application on EBL Home:\n"
            if len(results) == 1
            else "I found the following applications on EBL Home:\n"
        )

        for index, app in enumerate(results[:5], 1):
            lines.append(f"{index}. {app['title']}")
            lines.append(f"   Open: {app['app_url']}")
            if app.get("page_url"):
                lines.append(f"   EBL Home page: {app['page_url']}")
            lines.append("")

        total_count = apps_db.count_search_results(search_term)
        if total_count > len(results):
            lines.append(
                f"We found {total_count} matching application(s) in total. Showing the top {min(len(results), 5)}.\n"
            )
            lines.append("Please provide more details to narrow down the search.\n")

        lines.append(SOURCE_FOOTER)
        return "\n".join(lines)

    @staticmethod
    def _format_not_found(search_term: str) -> str:
        return (
            f"I couldn't find an application link for '{search_term}' in the EBL Home applications index. "
            "Please try:\n"
            "- Using the full application name (e.g., 'ICT Requisition Hub')\n"
            "- Adding keywords like portal, hub, or login\n"
            "- Browsing all links at http://eblhome/all-links/\n"
            f"\n{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_unavailable() -> str:
        return (
            "I'm having trouble accessing the EBL Home applications index right now. "
            "Please try again in a moment.\n\n"
            f"{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_empty_index() -> str:
        return (
            "The EBL Home applications index has not been loaded yet. "
            "Please ask your administrator to run the apps sync job.\n\n"
            f"{SOURCE_FOOTER}"
        )

    def lookup(self, query: str, apps_db: Optional[Any]) -> AppLinksLookupResult:
        if apps_db is None:
            return AppLinksLookupResult(response_text=self._format_unavailable(), unavailable=True)

        try:
            if apps_db.total_apps() == 0:
                return AppLinksLookupResult(response_text=self._format_empty_index(), unavailable=True)

            results, search_term = self.search(apps_db, query)
            if results:
                return AppLinksLookupResult(
                    response_text=self.format_response(apps_db, results, search_term),
                    search_term=search_term,
                    result_count=len(results),
                    found=True,
                )

            return AppLinksLookupResult(
                response_text=self._format_not_found(search_term),
                search_term=search_term,
                found=False,
            )
        except Exception as exc:
            logger.error("[APP_LINKS] Error for application query: %s", exc, exc_info=True)
            return AppLinksLookupResult(response_text=self._format_unavailable(), error=True)
