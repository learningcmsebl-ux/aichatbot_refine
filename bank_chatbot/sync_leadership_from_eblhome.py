#!/usr/bin/env python3
"""Sync EBL Home leadership profiles from MySQL into PostgreSQL."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))

from app.services.ebl_leadership_postgres import get_ebl_leadership_db
from app.services.eblhome_leadership_sync import get_eblhome_leadership_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync EBL Home leadership profiles")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        leaders = get_eblhome_leadership_sync().fetch_leaders()
        if args.dry_run:
            print(f"Would sync {len(leaders)} leadership profiles")
            for leader in leaders[:8]:
                print(f"- {leader['full_name']} | {leader.get('designation')} | {leader['category']}")
            return 0

        db = get_ebl_leadership_db()
        stats = db.sync_leaders(leaders, clear_existing=args.clear)

        print("\n" + "=" * 60)
        print("EBL HOME LEADERSHIP SYNC SUMMARY")
        print("=" * 60)
        print(f"Total profiles from MySQL: {stats['total']}")
        print(f"New profiles inserted:     {stats['inserted']}")
        print(f"Existing profiles updated: {stats['updated']}")
        print(f"Errors:                    {stats['errors']}")
        print(f"Index total now:           {db.total_leaders()}")
        print("=" * 60)

        status_path = Path(__file__).parent / "logs" / "leadership_sync_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            json.dumps(
                {
                    "last_run_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "last_run_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "success": stats["errors"] == 0,
                    "total_leaders": db.total_leaders(),
                    **stats,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 1 if stats["errors"] else 0
    except Exception as exc:
        logger.error("Leadership sync failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
