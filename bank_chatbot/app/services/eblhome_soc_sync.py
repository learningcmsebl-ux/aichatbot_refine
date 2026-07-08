"""
Read-only sync helpers for EBL Home schedule of charge metadata from MySQL (ebl_home).
"""

from __future__ import annotations

import html
import logging
import os
from typing import Dict, List, Optional
from urllib.parse import quote

import pymysql

logger = logging.getLogger(__name__)

SOC_QUERY = """
SELECT
    soc.ID AS source_post_id,
    soc.post_title AS title,
    soc.post_type AS post_type,
    soc_type.meta_value AS soc_type,
    att.ID AS attachment_id,
    att.guid AS download_url
FROM ebl_posts soc
JOIN ebl_postmeta file_id
    ON file_id.post_id = soc.ID
   AND file_id.meta_key = 'upload_file'
JOIN ebl_posts att
    ON att.ID = CAST(file_id.meta_value AS UNSIGNED)
LEFT JOIN ebl_postmeta soc_type
    ON soc_type.post_id = soc.ID
   AND soc_type.meta_key = 'type_of_schedule_of_charge'
WHERE soc.post_type = 'schedule_of_charge'
  AND soc.post_status = 'publish'
  AND att.guid IS NOT NULL
  AND att.guid <> ''
ORDER BY soc.post_title
"""


class EblHomeSocSync:
    """Fetch published schedule of charge metadata from the ebl_home WordPress MySQL database."""

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
        return (
            f"{self.base_url}/?post_type={quote(post_type)}&p={source_post_id}"
        )

    def fetch_items(self) -> List[Dict]:
        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                cursor.execute(SOC_QUERY)
                rows = cursor.fetchall()

            items: List[Dict] = []
            for row in rows:
                title = self._clean_text(row.get("title"))
                source_post_id = row.get("source_post_id")
                if not title or not source_post_id:
                    continue

                post_type = self._clean_text(row.get("post_type")) or "schedule_of_charge"
                items.append(
                    {
                        "source_post_id": int(source_post_id),
                        "title": title,
                        "soc_type": self._clean_text(row.get("soc_type")) or None,
                        "post_type": post_type,
                        "page_url": self._build_page_url(int(source_post_id), post_type),
                        "download_url": self._clean_text(row.get("download_url")) or None,
                        "attachment_id": int(row["attachment_id"]) if row.get("attachment_id") else None,
                    }
                )

            logger.info("Fetched %s published SOC items from MySQL %s", len(items), self.database)
            return items
        except Exception as exc:
            logger.error("Failed to fetch SOC items from MySQL: %s", exc, exc_info=True)
            raise
        finally:
            if connection is not None:
                connection.close()


def get_eblhome_soc_sync() -> EblHomeSocSync:
    return EblHomeSocSync()
