"""
Read-only sync for EBL Home leadership profiles (management + directors).
"""

from __future__ import annotations

import html
import logging
import os
from typing import Dict, List, Optional
from urllib.parse import quote

import pymysql

logger = logging.getLogger(__name__)

LEADERSHIP_QUERY = """
SELECT
    p.ID AS source_post_id,
    p.post_title AS full_name,
    p.post_type AS post_type,
    des.meta_value AS designation,
    prio.meta_value AS priority,
    lvl.meta_value AS level_priority,
    att.guid AS photo_url
FROM ebl_posts p
LEFT JOIN ebl_postmeta des
    ON des.post_id = p.ID AND des.meta_key = 'designation'
LEFT JOIN ebl_postmeta prio
    ON prio.post_id = p.ID AND prio.meta_key = 'priority'
LEFT JOIN ebl_postmeta lvl
    ON lvl.post_id = p.ID AND lvl.meta_key = 'level_priority'
LEFT JOIN ebl_postmeta pic
    ON pic.post_id = p.ID AND pic.meta_key = 'upload_picture'
LEFT JOIN ebl_posts att
    ON att.ID = CAST(pic.meta_value AS UNSIGNED)
WHERE p.post_type IN ('ebl_management', 'ebl_director')
  AND p.post_status = 'publish'
ORDER BY p.post_type, p.post_title
"""


class EblHomeLeadershipSync:
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

    @staticmethod
    def _parse_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except ValueError:
            return None

    def _build_page_url(self, source_post_id: int, post_type: str) -> str:
        return f"{self.base_url}/?post_type={quote(post_type)}&p={source_post_id}"

    @staticmethod
    def _category_for_post_type(post_type: str) -> str:
        if post_type == "ebl_director":
            return "director"
        return "management"

    def fetch_leaders(self) -> List[Dict]:
        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                cursor.execute(LEADERSHIP_QUERY)
                rows = cursor.fetchall()

            leaders: List[Dict] = []
            for row in rows:
                full_name = self._clean_text(row.get("full_name"))
                source_post_id = row.get("source_post_id")
                post_type = self._clean_text(row.get("post_type"))
                if not full_name or not source_post_id or not post_type:
                    continue

                leaders.append(
                    {
                        "source_post_id": int(source_post_id),
                        "full_name": full_name,
                        "designation": self._clean_text(row.get("designation")) or None,
                        "category": self._category_for_post_type(post_type),
                        "post_type": post_type,
                        "priority": self._parse_int(row.get("priority")),
                        "level_priority": self._parse_int(row.get("level_priority")),
                        "photo_url": self._clean_text(row.get("photo_url")) or None,
                        "page_url": self._build_page_url(int(source_post_id), post_type),
                    }
                )

            logger.info("Fetched %s leadership profiles from MySQL %s", len(leaders), self.database)
            return leaders
        finally:
            if connection is not None:
                connection.close()


def get_eblhome_leadership_sync() -> EblHomeLeadershipSync:
    return EblHomeLeadershipSync()
