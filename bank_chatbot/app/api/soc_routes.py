"""EBL Home Schedule of Charges API."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.forms_routes import filename_from_url, resolve_fetch_url

try:
    services_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services")
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)
    from ebl_soc_postgres import get_ebl_soc_db

    SOC_AVAILABLE = True
except ImportError as exc:
    SOC_AVAILABLE = False
    logging.getLogger(__name__).warning("SOC index unavailable: %s", exc)

logger = logging.getLogger(__name__)
soc_router = APIRouter(prefix="/soc", tags=["soc"])
STATUS_FILE = Path(__file__).resolve().parents[2] / "logs" / "soc_sync_status.json"


class SocResponse(BaseModel):
    id: Optional[int] = None
    source_post_id: int
    title: str
    soc_type: Optional[str] = None
    page_url: str
    download_url: Optional[str] = None


class SocSearchResponse(BaseModel):
    query: str
    results: List[SocResponse]
    total: int
    limit: int


@soc_router.get("/health")
async def soc_health():
    if not SOC_AVAILABLE:
        raise HTTPException(status_code=503, detail="SOC index service not available")
    db = get_ebl_soc_db()
    sync_status = json.loads(STATUS_FILE.read_text(encoding="utf-8")) if STATUS_FILE.exists() else None
    return {
        "status": "healthy" if db.total_items() > 0 else "empty",
        "service": "EBL Home Schedule of Charges",
        "total_items": db.total_items(),
        "last_sync": sync_status,
    }


@soc_router.get("/search", response_model=SocSearchResponse)
async def search_soc(q: str = Query(...), limit: int = Query(5, ge=1, le=20)):
    if not SOC_AVAILABLE:
        raise HTTPException(status_code=503, detail="SOC index service not available")
    db = get_ebl_soc_db()
    results = db.search(q, limit=limit)
    return SocSearchResponse(
        query=q,
        results=[SocResponse(**row) for row in results],
        total=db.count_search_results(q),
        limit=limit,
    )


@soc_router.get("/download/{source_post_id}")
async def download_soc(source_post_id: int):
    if not SOC_AVAILABLE:
        raise HTTPException(status_code=503, detail="SOC index service not available")
    db = get_ebl_soc_db()
    item = db.get_by_source_post_id(source_post_id)
    if not item or not item.get("download_url"):
        raise HTTPException(status_code=404, detail="Schedule of Charges file not found")

    fetch_url, fetch_headers = resolve_fetch_url(item["download_url"])
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            upstream = await client.get(fetch_url, headers=fetch_headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not fetch file from EBL Home") from exc

    if upstream.status_code >= 400:
        raise HTTPException(status_code=502, detail="Could not fetch file from EBL Home")

    filename = filename_from_url(item["download_url"], f"soc-{source_post_id}.pdf")
    media_type = upstream.headers.get("content-type", "application/pdf")
    return Response(
        content=upstream.content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, max-age=300"},
    )
