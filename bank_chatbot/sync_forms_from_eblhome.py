#!/usr/bin/env python3
"""
Sync EBL Home forms metadata from MySQL (ebl_home) into PostgreSQL.

Stores titles, departments, and eblhome download/page URLs only — not file binaries.

Usage:
    python sync_forms_from_eblhome.py [--clear] [--dry-run]
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

from app.services.ebl_forms_postgres import get_ebl_forms_db
from app.services.eblhome_forms_sync import EblHomeFormsSync, get_eblhome_forms_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync EBL Home forms metadata into PostgreSQL")
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

        mysql_sync = EblHomeFormsSync(**sync_kwargs) if sync_kwargs else get_eblhome_forms_sync()
        logger.info("Fetching forms from MySQL (%s/%s)...", mysql_sync.host, mysql_sync.database)
        forms = mysql_sync.fetch_forms()

        if args.dry_run:
            print("\n" + "=" * 60)
            print("EBL HOME FORMS DRY RUN")
            print("=" * 60)
            print(f"Would sync {len(forms)} forms")
            for form in forms[:5]:
                print(f"\n- {form['title']}")
                print(f"  Department: {form.get('department') or 'N/A'}")
                print(f"  Download: {form.get('download_url') or 'N/A'}")
                print(f"  Page: {form.get('page_url')}")
            if len(forms) > 5:
                print(f"\n... and {len(forms) - 5} more")
            print("=" * 60)
            return 0

        forms_db = get_ebl_forms_db()
        stats = forms_db.sync_forms(forms, clear_existing=args.clear)

        print("\n" + "=" * 60)
        print("EBL HOME FORMS SYNC SUMMARY")
        print("=" * 60)
        print(f"Total forms from MySQL: {stats['total']}")
        print(f"New forms inserted:     {stats['inserted']}")
        print(f"Existing forms updated: {stats['updated']}")
        print(f"Errors:                 {stats['errors']}")
        print(f"Index total now:        {forms_db.total_forms()}")
        print("=" * 60)

        status_path = Path(__file__).parent / "logs" / "forms_sync_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            json.dumps(
                {
                    "last_run_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "last_run_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "exit_code": 0 if stats["errors"] == 0 else 1,
                    "success": stats["errors"] == 0,
                    "total_forms": forms_db.total_forms(),
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
