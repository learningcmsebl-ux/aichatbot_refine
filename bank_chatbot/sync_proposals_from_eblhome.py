#!/usr/bin/env python3
"""
Sync EBL Home proposal updates from MySQL (ebl_home) into PostgreSQL.

Stores titles and eblhome download/page URLs only — not file binaries.

Usage:
    python sync_proposals_from_eblhome.py [--clear] [--dry-run]
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

from app.services.ebl_proposals_postgres import get_ebl_proposals_db
from app.services.eblhome_proposals_sync import EblHomeProposalsSync, get_eblhome_proposals_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync EBL Home proposals metadata into PostgreSQL")
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

        mysql_sync = EblHomeProposalsSync(**sync_kwargs) if sync_kwargs else get_eblhome_proposals_sync()
        logger.info("Fetching proposals from MySQL (%s/%s)...", mysql_sync.host, mysql_sync.database)
        proposals = mysql_sync.fetch_proposals()

        if args.dry_run:
            print("\n" + "=" * 60)
            print("EBL HOME PROPOSALS DRY RUN")
            print("=" * 60)
            print(f"Would sync {len(proposals)} proposals")
            for proposal in proposals[:5]:
                print(f"\n- {proposal['title']}")
                print(f"  Download: {proposal.get('download_url') or 'N/A'}")
                print(f"  Page: {proposal.get('page_url')}")
            if len(proposals) > 5:
                print(f"\n... and {len(proposals) - 5} more")
            print("=" * 60)
            return 0

        proposals_db = get_ebl_proposals_db()
        stats = proposals_db.sync_items(proposals, clear_existing=args.clear)

        print("\n" + "=" * 60)
        print("EBL HOME PROPOSALS SYNC SUMMARY")
        print("=" * 60)
        print(f"Total proposals from MySQL: {stats['total']}")
        print(f"New proposals inserted:     {stats['inserted']}")
        print(f"Existing proposals updated: {stats['updated']}")
        print(f"Errors:                     {stats['errors']}")
        print(f"Index total now:            {proposals_db.total_items()}")
        print("=" * 60)

        status_path = Path(__file__).parent / "logs" / "proposals_sync_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            json.dumps(
                {
                    "last_run_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "last_run_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "exit_code": 0 if stats["errors"] == 0 else 1,
                    "success": stats["errors"] == 0,
                    "total_proposals": proposals_db.total_items(),
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
