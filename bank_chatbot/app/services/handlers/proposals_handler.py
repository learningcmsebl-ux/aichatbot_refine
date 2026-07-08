"""Proposal update handler — EBL Home credit/ops status documents."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SOURCE_FOOTER = "(Source: EBL Home Proposal Updates)"


@dataclass(frozen=True)
class ProposalsLookupResult:
    response_text: str
    search_term: str = ""
    result_count: int = 0
    found: bool = False
    unavailable: bool = False
    error: bool = False


class ProposalsHandler:
    def extract_search_term(self, query: str) -> str:
        query_lower = (query or "").lower().strip()
        patterns = (
            r"^(?:download|get|find|search|need|where|how\s+to|show\s+me|check)\s+(?:the\s+)?(.+)$",
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
            r"download|get|find|search|need|where|how|check|status|track|"
            r"proposal|update|ebl|home|eblhome)\b"
        )
        term = re.sub(noise, " ", term, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", term).strip()

    @staticmethod
    def _download_proxy_url(source_post_id: int) -> str:
        return f"/api/proposals/download/{source_post_id}"

    def format_response(self, proposals_db: Any, results: List[Dict], search_term: str) -> str:
        if not results:
            return self._format_not_found(search_term)

        lines: List[str] = []
        lines.append(
            "I found this proposal update guide on EBL Home:\n"
            if len(results) == 1
            else "I found the following proposal update guides on EBL Home:\n"
        )

        for index, item in enumerate(results[:5], 1):
            lines.append(f"{index}. {item['title']}")
            if item.get("source_post_id"):
                lines.append(f"   Download: {self._download_proxy_url(item['source_post_id'])}")
            lines.append("")

        total_count = proposals_db.count_search_results(search_term)
        if total_count > len(results):
            lines.append(f"We found {total_count} matching guide(s). Showing the top {min(len(results), 5)}.\n")

        lines.append(SOURCE_FOOTER)
        return "\n".join(lines)

    @staticmethod
    def _format_not_found(search_term: str) -> str:
        return (
            f"I couldn't find a proposal update guide for '{search_term}'. "
            "Try keywords like 'credit card limit enhancement', 'fast cash status', or 'CPV status'.\n"
            f"\n{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_unavailable() -> str:
        return (
            "I'm having trouble accessing the proposal updates index right now.\n\n"
            f"{SOURCE_FOOTER}"
        )

    @staticmethod
    def _format_empty_index() -> str:
        return (
            "The proposal updates index has not been loaded yet.\n\n"
            f"{SOURCE_FOOTER}"
        )

    def lookup(self, query: str, proposals_db: Optional[Any]) -> ProposalsLookupResult:
        if proposals_db is None:
            return ProposalsLookupResult(response_text=self._format_unavailable(), unavailable=True)
        try:
            if proposals_db.total_items() == 0:
                return ProposalsLookupResult(response_text=self._format_empty_index(), unavailable=True)
            search_term = self.extract_search_term(query) or (query or "").strip()
            results = proposals_db.search(search_term, limit=5)
            if results:
                return ProposalsLookupResult(
                    response_text=self.format_response(proposals_db, results, search_term),
                    search_term=search_term,
                    result_count=len(results),
                    found=True,
                )
            return ProposalsLookupResult(
                response_text=self._format_not_found(search_term),
                search_term=search_term,
                found=False,
            )
        except Exception as exc:
            logger.error("[PROPOSALS] Error: %s", exc, exc_info=True)
            return ProposalsLookupResult(response_text=self._format_unavailable(), error=True)
