#!/usr/bin/env python3
"""Sync EBL Home application links (ebllinks) from MySQL into PostgreSQL."""
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

from app.services.ebl_apps_postgres import get_ebl_apps_db
from app.services.eblhome_apps_sync import EblHomeAppsSync, get_eblhome_apps_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync EBL Home application links into PostgreSQL")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        mysql_sync = get_eblhome_apps_sync()
        apps = mysql_sync.fetch_apps()

        if args.dry_run:
            print(f"Would sync {len(apps)} application links")
            for app in apps[:8]:
                print(f"- {app['title']}: {app['app_url']}")
            return 0

        apps_db = get_ebl_apps_db()
        stats = apps_db.sync_apps(apps, clear_existing=args.clear)

        print("\n" + "=" * 60)
        print("EBL HOME APPS SYNC SUMMARY")
        print("=" * 60)
        print(f"Total apps from MySQL:  {stats['total']}")
        print(f"New apps inserted:      {stats['inserted']}")
        print(f"Existing apps updated:  {stats['updated']}")
        print(f"Errors:                 {stats['errors']}")
        print(f"Index total now:        {apps_db.total_apps()}")
        print("=" * 60)

        status_path = Path(__file__).parent / "logs" / "apps_sync_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            json.dumps(
                {
                    "last_run_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "last_run_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "exit_code": 0 if stats["errors"] == 0 else 1,
                    "success": stats["errors"] == 0,
                    "total_apps": apps_db.total_apps(),
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
        logger.error("Apps sync failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
