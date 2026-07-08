"""
Read-only sync helpers for EBL Home application links (ebllinks) from MySQL.
"""

from __future__ import annotations

import html
import logging
import os
from typing import Dict, List, Optional
from urllib.parse import quote

import pymysql

logger = logging.getLogger(__name__)

APPS_QUERY = """
SELECT
    p.ID AS source_post_id,
    p.post_title AS title,
    p.post_type AS post_type,
    link.meta_value AS app_url
FROM ebl_posts p
JOIN ebl_postmeta link
    ON link.post_id = p.ID
   AND link.meta_key = 'link'
WHERE p.post_type = 'ebllinks'
  AND p.post_status = 'publish'
  AND link.meta_value IS NOT NULL
  AND TRIM(link.meta_value) <> ''
ORDER BY p.post_title
"""


class EblHomeAppsSync:
    """Fetch published ebllinks application shortcuts from ebl_home."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.host = host or os.getenv("EBLHOME_MYSQL_HOST", "192.168.3.57")
        self.port = port or int(os.getenv("EBLHOME_MYSQL_PORT", "3306"))
        self.user = user or os.getenv("EBLHOME_MYSQL_USER", "tanvir")
        self.password = password or os.getenv("EBLHOME_MYSQL_PASSWORD", "tanvir")
        self.database = database or os.getenv("EBLHOME_MYSQL_DB", "ebl_home")
        self.base_url = (base_url or os.getenv("EBLHOME_BASE_URL", "http://eblhome")).rstrip("/")

    def _connect(self):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )

    @staticmethod
    def _clean_text(value: Optional[str]) -> str:
        return html.unescape((value or "").strip())

    def _build_page_url(self, source_post_id: int, post_type: str) -> str:
        return f"{self.base_url}/?post_type={quote(post_type)}&p={source_post_id}"

    def fetch_apps(self) -> List[Dict]:
        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                cursor.execute(APPS_QUERY)
                rows = cursor.fetchall()

            apps: List[Dict] = []
            for row in rows:
                title = self._clean_text(row.get("title"))
                source_post_id = row.get("source_post_id")
                app_url = self._clean_text(row.get("app_url"))
                if not title or not source_post_id or not app_url:
                    continue

                post_type = self._clean_text(row.get("post_type")) or "ebllinks"
                apps.append(
                    {
                        "source_post_id": int(source_post_id),
                        "title": title,
                        "app_url": app_url,
                        "page_url": self._build_page_url(int(source_post_id), post_type),
                        "post_type": post_type,
                    }
                )

            logger.info("Fetched %s published application links from MySQL %s", len(apps), self.database)
            return apps
        except Exception as exc:
            logger.error("Failed to fetch application links from MySQL: %s", exc, exc_info=True)
            raise
        finally:
            if connection is not None:
                connection.close()


def get_eblhome_apps_sync() -> EblHomeAppsSync:
    return EblHomeAppsSync()
