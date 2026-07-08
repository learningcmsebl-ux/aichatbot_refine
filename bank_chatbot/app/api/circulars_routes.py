"""EBL Home compliance circulars API."""

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
    from ebl_circulars_postgres import get_ebl_circulars_db

    CIRCULARS_AVAILABLE = True
except ImportError as exc:
    CIRCULARS_AVAILABLE = False
    logging.getLogger(__name__).warning("Circulars index unavailable: %s", exc)

circulars_router = APIRouter(prefix="/circulars", tags=["circulars"])
STATUS_FILE = Path(__file__).resolve().parents[2] / "logs" / "circulars_sync_status.json"


class CircularResponse(BaseModel):
    id: Optional[int] = None
    source_post_id: int
    title: str
    department: Optional[str] = None
    link_url: str
    page_url: str


class CircularsSearchResponse(BaseModel):
    query: str
    results: List[CircularResponse]
    total: int
    limit: int


@circulars_router.get("/health")
async def circulars_health():
    if not CIRCULARS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Circulars index service not available")
    db = get_ebl_circulars_db()
    sync_status = json.loads(STATUS_FILE.read_text(encoding="utf-8")) if STATUS_FILE.exists() else None
    return {
        "status": "healthy" if db.total_items() > 0 else "empty",
        "service": "EBL Home Circulars",
        "total_items": db.total_items(),
        "last_sync": sync_status,
    }


@circulars_router.get("/search", response_model=CircularsSearchResponse)
async def search_circulars(q: str = Query(...), limit: int = Query(5, ge=1, le=20)):
    if not CIRCULARS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Circulars index service not available")
    db = get_ebl_circulars_db()
    results = db.search(q, limit=limit)
    return CircularsSearchResponse(
        query=q,
        results=[CircularResponse(**row) for row in results],
        total=db.count_search_results(q),
        limit=limit,
    )
