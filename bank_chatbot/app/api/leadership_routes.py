"""EBL Home leadership profiles API."""

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

from app.api.forms_routes import resolve_fetch_url
from app.core.config import settings

try:
    services_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services")
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)
    from ebl_leadership_postgres import get_ebl_leadership_db

    LEADERSHIP_AVAILABLE = True
except ImportError as exc:
    LEADERSHIP_AVAILABLE = False
    logging.getLogger(__name__).warning("Leadership index unavailable: %s", exc)

logger = logging.getLogger(__name__)

leadership_router = APIRouter(prefix="/leadership", tags=["leadership"])
STATUS_FILE = Path(__file__).resolve().parents[2] / "logs" / "leadership_sync_status.json"


class LeaderResponse(BaseModel):
    id: Optional[int] = None
    source_post_id: int
    full_name: str
    designation: Optional[str] = None
    category: str
    post_type: str
    priority: Optional[int] = None
    level_priority: Optional[int] = None
    photo_url: Optional[str] = None
    photo_proxy_url: Optional[str] = None
    page_url: str


class LeadershipSearchResponse(BaseModel):
    query: str
    results: List[LeaderResponse]
    total: int
    limit: int


def build_photo_proxy_url(source_post_id: int) -> str:
    return f"{settings.public_api_base_url}/leadership/photo/{source_post_id}"


@leadership_router.get("/health")
async def leadership_health():
    if not LEADERSHIP_AVAILABLE:
        raise HTTPException(status_code=503, detail="Leadership index service not available")

    db = get_ebl_leadership_db()
    sync_status = None
    if STATUS_FILE.exists():
        try:
            sync_status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "status": "healthy" if db.total_leaders() > 0 else "empty",
        "service": "EBL Home Leadership Index",
        "total_leaders": db.total_leaders(),
        "photo_proxy_base": f"{settings.public_api_base_url}/leadership/photo",
        "last_sync": sync_status,
    }


@leadership_router.get("/search", response_model=LeadershipSearchResponse)
async def search_leadership(
    q: str = Query(..., description="Name or designation search"),
    limit: int = Query(5, ge=1, le=20),
):
    if not LEADERSHIP_AVAILABLE:
        raise HTTPException(status_code=503, detail="Leadership index service not available")

    db = get_ebl_leadership_db()
    results = db.smart_search(q, limit=limit)
    enriched = []
    for row in results:
        item = dict(row)
        item["photo_proxy_url"] = build_photo_proxy_url(row["source_post_id"])
        enriched.append(LeaderResponse(**item))
    return LeadershipSearchResponse(
        query=q,
        results=enriched,
        total=db.total_leaders(),
        limit=limit,
    )


@leadership_router.get("/photo/{source_post_id}")
async def leadership_photo(source_post_id: int):
    """Proxy leadership portrait from EBL Home for HTTPS chat UI embedding."""
    if not LEADERSHIP_AVAILABLE:
        raise HTTPException(status_code=503, detail="Leadership index service not available")

    db = get_ebl_leadership_db()
    leader = db.get_by_source_post_id(source_post_id)
    if not leader or not leader.get("photo_url"):
        raise HTTPException(status_code=404, detail="Leadership photo not found")

    fetch_url, fetch_headers = resolve_fetch_url(leader["photo_url"])

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            upstream = await client.get(fetch_url, headers=fetch_headers)
    except httpx.HTTPError as exc:
        logger.error("[LEADERSHIP] Photo fetch failed for %s: %s", fetch_url, exc)
        raise HTTPException(status_code=502, detail="Could not fetch photo from EBL Home") from exc

    if upstream.status_code >= 400:
        logger.error("[LEADERSHIP] Upstream returned %s for %s", upstream.status_code, fetch_url)
        raise HTTPException(status_code=502, detail="Could not fetch photo from EBL Home")

    media_type = upstream.headers.get("content-type", "image/jpeg")
    return Response(
        content=upstream.content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
