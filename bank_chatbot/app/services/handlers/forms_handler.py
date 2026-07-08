"""
Forms Handler — search EBL Home form metadata and return download links.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

SOURCE_FOOTER = "(Source: EBL Home Forms)"


@dataclass(frozen=True)
class FormsLookupResult:
    response_text: str
    search_term: str = ""
    result_count: int = 0
    found: bool = False
    unavailable: bool = False
    error: bool = False


class FormsHandler:
    """Parse form lookup queries and return eblhome download links."""

    def extract_search_term(self, query: str) -> str:
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return ""

        patterns = (
            r"^(?:download|get|find|search|need|where(?:\s+is|\s+can\s+i\s+find)?|show\s+me)\s+(?:the\s+)?(.+)$",
            r"^(.+?)\s+(?:form|forms)\s+(?:download|link|url|template)$",
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
            r"download|get|find|search|need|where|link|url|template|"
            r"form|forms|ebl|home|eblhome)\b"
        )
        term = re.sub(noise, " ", term, flags=re.IGNORECASE)
        term = re.sub(r"\s+", " ", term).strip()
        return term

    def search(self, forms_db: Any, query: str, *, limit: int = 5) -> tuple[List[Dict], str]:
        search_term = self.extract_search_term(query)
        if not search_term:
            search_term = (query or "").strip()
        results = forms_db.search(search_term, limit=limit)
        return results, search_term

    @staticmethod
    def _download_proxy_url(source_post_id: int) -> str:
        return f"{settings.public_api_base_url}/forms/download/{source_post_id}"

    @staticmethod
    def _filename_from_download_url(download_url: str) -> str:
        from urllib.parse import unquote, urlparse
        import os as _os

        path = unquote(urlparse(download_url).path or "")
        return _os.path.basename(path) or "form.doc"

    def format_response(self, forms_db: Any, results: List[Dict], search_term: str) -> str:
        if not results:
            return self._format_not_found(search_term)

        lines: List[str] = []
        if len(results) == 1:
            lines.append("I found this form on EBL Home:\n")
        else:
            lines.append("I found the following forms on EBL Home:\n")

        for index, form in enumerate(results[:5], 1):
            lines.append(f"{index}. {form['title']}")
            if form.get("department"):
                lines.append(f"   Department: {form['department']}")
            if form.get("subject"):
                lines.append(f"   Subject: {form['subject']}")
            if form.get("source_post_id") and form.get("download_url"):
                filename = self._filename_from_download_url(form["download_url"])
                lines.append(f"   Download: {self._download_proxy_url(form['source_post_id'])}")
                lines.append(f"   File: {filename}")
            elif form.get("download_url"):
                lines.append(f"   Download: {form['download_url']}")
            if form.get("page_url"):
                lines.append(f"   Form page: {form['page_url']}")
            lines.append("")

        total_count = forms_db.count_search_results(search_term)
        if total_count > len(results):
            lines.append(
                f"We found {total_count} matching form(s) in total. Showing the top {min(len(results), 5)}.\n"
            )
            lines.append("Please provide more details to narrow down the search.\n")

        lines.append(SOURCE_FOOTER)
        return "\n".join(lines)

    @staticmethod
    def _format_not_found(search_term: str) -> str:
        return (
            f"I couldn't find a matching form for '{search_term}' in the EBL Home forms index. "
            "Please try:\n"
            "- Using the full form name (e.g., 'Asset Movement Form')\n"
            "- Adding the department (e.g., 'Administration asset requisition')\n"
            "- Browsing forms on EBL Home directly\n"
            f"\n{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_unavailable() -> str:
        return (
            "I'm having trouble accessing the EBL Home forms index right now. "
            "Please try again in a moment or browse forms directly on EBL Home.\n\n"
            f"{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_empty_index() -> str:
        return (
            "The EBL Home forms index has not been loaded yet. "
            "Please ask your administrator to run the forms sync job.\n\n"
            f"{SOURCE_FOOTER}"
        )

    def lookup(self, query: str, forms_db: Optional[Any]) -> FormsLookupResult:
        if forms_db is None:
            logger.warning("[FORMS] Forms DB unavailable; cannot serve form request.")
            return FormsLookupResult(response_text=self._format_unavailable(), unavailable=True)

        try:
            if forms_db.total_forms() == 0:
                logger.warning("[FORMS] Forms index is empty.")
                return FormsLookupResult(response_text=self._format_empty_index(), unavailable=True)

            results, search_term = self.search(forms_db, query)
            if results:
                logger.info("[FORMS] Found %s result(s) for: %s", len(results), search_term)
                return FormsLookupResult(
                    response_text=self.format_response(forms_db, results, search_term),
                    search_term=search_term,
                    result_count=len(results),
                    found=True,
                )

            logger.info("[FORMS] No results for '%s' (NOT using LightRAG)", search_term)
            return FormsLookupResult(
                response_text=self._format_not_found(search_term),
                search_term=search_term,
                found=False,
            )
        except Exception as exc:
            logger.error("[FORMS] Error for form query (NOT using LightRAG): %s", exc, exc_info=True)
            return FormsLookupResult(response_text=self._format_unavailable(), error=True)
