#!/usr/bin/env python3
"""Sync EBL Home compliance circulars (link_insert) from MySQL into PostgreSQL."""
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

from app.services.ebl_circulars_postgres import get_ebl_circulars_db
from app.services.eblhome_circulars_sync import EblHomeCircularsSync, get_eblhome_circulars_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync EBL Home compliance circulars into PostgreSQL")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mysql-host", type=str, help="Override EBLHOME_MYSQL_HOST")
    parser.add_argument("--mysql-db", type=str, help="Override EBLHOME_MYSQL_DB")
    parser.add_argument("--base-url", type=str, help="Override EBLHOME_BASE_URL")
    args = parser.parse_args()

    try:
        sync_kwargs = {}
        if args.mysql_host:
            sync_kwargs["host"] = args.mysql_host
        if args.mysql_db:
            sync_kwargs["database"] = args.mysql_db
        if args.base_url:
            sync_kwargs["base_url"] = args.base_url

        mysql_sync = (
            EblHomeCircularsSync(**sync_kwargs) if sync_kwargs else get_eblhome_circulars_sync()
        )
        logger.info("Fetching circulars from MySQL (%s/%s)...", mysql_sync.host, mysql_sync.database)
        items = mysql_sync.fetch_circulars()

        if args.dry_run:
            print("\n" + "=" * 60)
            print("EBL HOME CIRCULARS DRY RUN")
            print("=" * 60)
            print(f"Would sync {len(items)} circulars")
            for item in items[:8]:
                print(f"\n- {item['title']}")
                print(f"  Department: {item.get('department') or 'N/A'}")
                print(f"  Link: {item.get('link_url')}")
                print(f"  Page: {item.get('page_url')}")
            if len(items) > 8:
                print(f"\n... and {len(items) - 8} more")
            print("=" * 60)
            return 0

        circulars_db = get_ebl_circulars_db()
        stats = circulars_db.sync_items(items, clear_existing=args.clear)

        print("\n" + "=" * 60)
        print("EBL HOME CIRCULARS SYNC SUMMARY")
        print("=" * 60)
        print(f"Total circulars from MySQL: {stats['total']}")
        print(f"New circulars inserted:     {stats['inserted']}")
        print(f"Existing circulars updated: {stats['updated']}")
        print(f"Errors:                     {stats['errors']}")
        print(f"Index total now:            {circulars_db.total_items()}")
        print("=" * 60)

        status_path = Path(__file__).parent / "logs" / "circulars_sync_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            json.dumps(
                {
                    "last_run_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "last_run_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "exit_code": 0 if stats["errors"] == 0 else 1,
                    "success": stats["errors"] == 0,
                    "total_items": circulars_db.total_items(),
                    "inserted": stats["inserted"],
                    "updated": stats["updated"],
                    "errors": stats["errors"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 1 if stats["errors"] else 0
    except Exception as exc:
        logger.error("Circulars sync failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
