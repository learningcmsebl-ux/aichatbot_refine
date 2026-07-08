"""EBL Home application links API."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

try:
    services_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services")
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)
    from ebl_apps_postgres import get_ebl_apps_db

    APPS_AVAILABLE = True
except ImportError as exc:
    APPS_AVAILABLE = False
    logging.getLogger(__name__).warning("Apps index unavailable: %s", exc)

apps_router = APIRouter(prefix="/apps", tags=["apps"])
STATUS_FILE = Path(__file__).resolve().parents[2] / "logs" / "apps_sync_status.json"


class AppResponse(BaseModel):
    id: Optional[int] = None
    source_post_id: int
    title: str
    app_url: str
    page_url: str


class AppsSearchResponse(BaseModel):
    query: str
    results: List[AppResponse]
    total: int
    limit: int


@apps_router.get("/health")
async def apps_health():
    if not APPS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Apps index service not available")

    db = get_ebl_apps_db()
    sync_status = None
    if STATUS_FILE.exists():
        try:
            sync_status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "status": "healthy" if db.total_apps() > 0 else "empty",
        "service": "EBL Home Applications Index",
        "total_apps": db.total_apps(),
        "last_sync": sync_status,
    }


@apps_router.get("/search", response_model=AppsSearchResponse)
async def search_apps(
    q: str = Query(..., description="Application name search"),
    limit: int = Query(5, ge=1, le=20),
):
    if not APPS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Apps index service not available")

    db = get_ebl_apps_db()
    results = db.search(q, limit=limit)
    return AppsSearchResponse(
        query=q,
        results=[AppResponse(**row) for row in results],
        total=db.count_search_results(q),
        limit=limit,
    )
