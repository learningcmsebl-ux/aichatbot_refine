"""Compliance circulars handler — EBL Home link_insert circular URLs."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SOURCE_FOOTER = "(Source: EBL Home Circulars)"


@dataclass(frozen=True)
class CircularsLookupResult:
    response_text: str
    search_term: str = ""
    result_count: int = 0
    found: bool = False
    unavailable: bool = False
    error: bool = False


class CircularsHandler:
    def extract_search_term(self, query: str) -> str:
        query_lower = (query or "").lower().strip()
        patterns = (
            r"^(?:open|access|find|search|need|where|show\s+me)\s+(?:the\s+)?(.+)$",
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
            r"open|access|find|search|need|where|link|url|circular|circulars|"
            r"ebl|home|eblhome|bfiu|bangladesh|bank)\b"
        )
        term = re.sub(noise, " ", term, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", term).strip()

    def format_response(self, circulars_db: Any, results: List[Dict], search_term: str) -> str:
        if not results:
            return self._format_not_found(search_term)

        lines: List[str] = []
        lines.append(
            "I found this circular link on EBL Home:\n"
            if len(results) == 1
            else "I found the following circular links on EBL Home:\n"
        )

        for index, item in enumerate(results[:5], 1):
            lines.append(f"{index}. {item['title']}")
            if item.get("department"):
                lines.append(f"   Department: {item['department']}")
            lines.append(f"   Open: {item['link_url']}")
            lines.append("")

        total_count = circulars_db.count_search_results(search_term)
        if total_count > len(results):
            lines.append(f"We found {total_count} matching circular(s). Showing the top {min(len(results), 5)}.\n")

        lines.append(SOURCE_FOOTER)
        return "\n".join(lines)

    @staticmethod
    def _format_not_found(search_term: str) -> str:
        return (
            f"I couldn't find a circular link for '{search_term}'. "
            "Try 'BFIU circulars', 'Bangladesh Bank circulars', or 'AOF observations'.\n"
            f"\n{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_unavailable() -> str:
        return (
            "I'm having trouble accessing the EBL Home circulars index right now.\n\n"
            f"{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_empty_index() -> str:
        return (
            "The EBL Home circulars index has not been loaded yet.\n\n"
            f"{SOURCE_FOOTER}"
        )

    def lookup(self, query: str, circulars_db: Optional[Any]) -> CircularsLookupResult:
        if circulars_db is None:
            return CircularsLookupResult(response_text=self._format_unavailable(), unavailable=True)
        try:
            if circulars_db.total_items() == 0:
                return CircularsLookupResult(response_text=self._format_empty_index(), unavailable=True)
            search_term = self.extract_search_term(query) or (query or "").strip()
            results = circulars_db.search(search_term, limit=5)
            if results:
                return CircularsLookupResult(
                    response_text=self.format_response(circulars_db, results, search_term),
                    search_term=search_term,
                    result_count=len(results),
                    found=True,
                )
            return CircularsLookupResult(
                response_text=self._format_not_found(search_term),
                search_term=search_term,
                found=False,
            )
        except Exception as exc:
            logger.error("[CIRCULARS] Error: %s", exc, exc_info=True)
            return CircularsLookupResult(response_text=self._format_unavailable(), error=True)
