#!/usr/bin/env python3
"""
Sync EBL Home schedule of charge metadata from MySQL (ebl_home) into PostgreSQL.

Stores titles, SOC types, and eblhome download/page URLs only — not file binaries.

Usage:
    python sync_soc_from_eblhome.py [--clear] [--dry-run]
"""
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

from app.services.ebl_soc_postgres import get_ebl_soc_db
from app.services.eblhome_soc_sync import EblHomeSocSync, get_eblhome_soc_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync EBL Home schedule of charge metadata into PostgreSQL")
    parser.add_argument("--clear", action="store_true", help="Clear existing index before sync")
    parser.add_argument("--dry-run", action="store_true", help="Fetch from MySQL without writing to PostgreSQL")
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

        mysql_sync = EblHomeSocSync(**sync_kwargs) if sync_kwargs else get_eblhome_soc_sync()
        logger.info("Fetching schedule of charge items from MySQL (%s/%s)...", mysql_sync.host, mysql_sync.database)
        items = mysql_sync.fetch_items()

        if args.dry_run:
            print("\n" + "=" * 60)
            print("EBL HOME SOC DRY RUN")
            print("=" * 60)
            print(f"Would sync {len(items)} SOC items")
            for item in items[:5]:
                print(f"\n- {item['title']}")
                print(f"  Type: {item.get('soc_type') or 'N/A'}")
                print(f"  Download: {item.get('download_url') or 'N/A'}")
                print(f"  Page: {item.get('page_url')}")
            if len(items) > 5:
                print(f"\n... and {len(items) - 5} more")
            print("=" * 60)
            return 0

        soc_db = get_ebl_soc_db()
        stats = soc_db.sync_items(items, clear_existing=args.clear)

        print("\n" + "=" * 60)
        print("EBL HOME SOC SYNC SUMMARY")
        print("=" * 60)
        print(f"Total items from MySQL: {stats['total']}")
        print(f"New items inserted:     {stats['inserted']}")
        print(f"Existing items updated: {stats['updated']}")
        print(f"Errors:                 {stats['errors']}")
        print(f"Index total now:        {soc_db.total_items()}")
        print("=" * 60)

        status_path = Path(__file__).parent / "logs" / "soc_sync_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            json.dumps(
                {
                    "last_run_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "last_run_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "exit_code": 0 if stats["errors"] == 0 else 1,
                    "success": stats["errors"] == 0,
                    "total_items": soc_db.total_items(),
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
        logger.error("Sync failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
