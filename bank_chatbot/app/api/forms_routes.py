"""
EBL Home forms index API — metadata, sync status, and download proxy.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import settings

try:
    import sys

    services_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services")
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)
    from ebl_forms_postgres import get_ebl_forms_db

    FORMS_AVAILABLE = True
except ImportError as exc:
    FORMS_AVAILABLE = False
    logging.getLogger(__name__).warning("Forms index unavailable: %s", exc)

logger = logging.getLogger(__name__)

forms_router = APIRouter(prefix="/forms", tags=["forms"])

STATUS_FILE = Path(__file__).resolve().parents[2] / "logs" / "forms_sync_status.json"


class FormResponse(BaseModel):
    id: Optional[int] = None
    source_post_id: int
    title: str
    department: Optional[str] = None
    subject: Optional[str] = None
    page_url: str
    download_url: Optional[str] = None
    download_proxy_url: Optional[str] = None


class FormsSearchResponse(BaseModel):
    query: str
    results: List[FormResponse]
    total: int
    limit: int


def build_download_proxy_url(source_post_id: int) -> str:
    return f"{settings.public_api_base_url}/forms/download/{source_post_id}"


def resolve_fetch_url(stored_download_url: str) -> tuple[str, dict[str, str]]:
    stored = (stored_download_url or "").strip()
    if not stored:
        return stored, {}

    fetch_base = settings.eblhome_fetch_base_url
    fetch_url = re.sub(r"^https?://eblhome(?=[/:]|$)", fetch_base, stored, flags=re.IGNORECASE)
    headers: dict[str, str] = {}
    if re.search(r"^https?://eblhome(?=[/:]|$)", stored, flags=re.IGNORECASE):
        headers["Host"] = "eblhome"
    return fetch_url, headers


def filename_from_url(url: str, fallback: str) -> str:
    path = unquote(urlparse(url).path or "")
    name = os.path.basename(path)
    return name or fallback


@forms_router.get("/health")
async def forms_health():
    if not FORMS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Forms index service not available")

    db = get_ebl_forms_db()
    sync_status = None
    if STATUS_FILE.exists():
        try:
            sync_status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read forms sync status: %s", exc)

    return {
        "status": "healthy" if db.total_forms() > 0 else "empty",
        "service": "EBL Home Forms Index",
        "total_forms": db.total_forms(),
        "download_proxy_base": f"{settings.public_api_base_url}/forms/download",
        "last_sync": sync_status,
    }


@forms_router.get("/search", response_model=FormsSearchResponse)
async def search_forms(
    q: str = Query(..., description="Form title or department search"),
    limit: int = Query(5, ge=1, le=20),
):
    if not FORMS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Forms index service not available")

    db = get_ebl_forms_db()
    results = db.search(q, limit=limit)
    total = db.count_search_results(q)
    enriched = []
    for row in results:
        item = dict(row)
        item["download_proxy_url"] = build_download_proxy_url(row["source_post_id"])
        enriched.append(FormResponse(**item))
    return FormsSearchResponse(
        query=q,
        results=enriched,
        total=total,
        limit=limit,
    )


@forms_router.get("/download/{source_post_id}")
async def download_form(source_post_id: int):
    """
    Proxy download from EBL Home with Content-Disposition: attachment
    so browsers save the file instead of navigating cross-origin.
    """
    if not FORMS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Forms index service not available")

    db = get_ebl_forms_db()
    form = db.get_by_source_post_id(source_post_id)
    if not form or not form.get("download_url"):
        raise HTTPException(status_code=404, detail="Form file not found")

    fetch_url, fetch_headers = resolve_fetch_url(form["download_url"])

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            upstream = await client.get(fetch_url, headers=fetch_headers)
    except httpx.HTTPError as exc:
        logger.error("[FORMS] Download fetch failed for %s: %s", fetch_url, exc)
        raise HTTPException(status_code=502, detail="Could not fetch form from EBL Home") from exc

    if upstream.status_code >= 400:
        logger.error(
            "[FORMS] Upstream returned %s for %s",
            upstream.status_code,
            fetch_url,
        )
        raise HTTPException(status_code=502, detail="Could not fetch form from EBL Home")

    filename = filename_from_url(form["download_url"], f"form-{source_post_id}.doc")
    if filename.lower().endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif filename.lower().endswith(".doc"):
        media_type = "application/msword"
    elif filename.lower().endswith(".pdf"):
        media_type = "application/pdf"
    else:
        media_type = upstream.headers.get("content-type", "application/octet-stream")

    return Response(
        content=upstream.content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, max-age=300",
        },
    )
