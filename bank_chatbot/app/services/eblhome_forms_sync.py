"""
Read-only sync helpers for EBL Home forms metadata from MySQL (ebl_home).
"""

from __future__ import annotations

import html
import logging
import os
from typing import Dict, List, Optional
from urllib.parse import quote

import pymysql

logger = logging.getLogger(__name__)

FORMS_QUERY = """
SELECT
    fd.ID AS source_post_id,
    fd.post_title AS title,
    fd.post_type AS post_type,
    dept.meta_value AS department,
    subj.meta_value AS subject,
    COALESCE(docorder.meta_value, docorder2.meta_value) AS docorder,
    att.ID AS attachment_id,
    att.guid AS download_url
FROM ebl_posts fd
JOIN ebl_postmeta file_id
    ON file_id.post_id = fd.ID
   AND file_id.meta_key IN ('form_upload_file', 'file_upload', 'upload_file')
JOIN ebl_posts att
    ON att.ID = CAST(file_id.meta_value AS UNSIGNED)
LEFT JOIN ebl_postmeta dept
    ON dept.post_id = fd.ID
   AND dept.meta_key = 'department_name'
LEFT JOIN ebl_postmeta subj
    ON subj.post_id = fd.ID
   AND subj.meta_key = 'subject'
LEFT JOIN ebl_postmeta docorder
    ON docorder.post_id = fd.ID
   AND docorder.meta_key = 'docorder'
LEFT JOIN ebl_postmeta docorder2
    ON docorder2.post_id = fd.ID
   AND docorder2.meta_key = 'document_order'
WHERE fd.post_type LIKE 'forms_download%%'
  AND fd.post_status = 'publish'
  AND att.guid IS NOT NULL
  AND att.guid <> ''
ORDER BY fd.post_title
"""


class EblHomeFormsSync:
    """Fetch published forms metadata from the ebl_home WordPress MySQL database."""

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

    @staticmethod
    def _parse_docorder(value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        try:
            return int(str(value).strip())
        except ValueError:
            return None

    def fetch_forms(self) -> List[Dict]:
        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                cursor.execute(FORMS_QUERY)
                rows = cursor.fetchall()

            forms: List[Dict] = []
            for row in rows:
                title = self._clean_text(row.get("title"))
                source_post_id = row.get("source_post_id")
                if not title or not source_post_id:
                    continue

                post_type = self._clean_text(row.get("post_type")) or "forms_download"
                forms.append(
                    {
                        "source_post_id": int(source_post_id),
                        "title": title,
                        "department": self._clean_text(row.get("department")) or None,
                        "subject": self._clean_text(row.get("subject")) or None,
                        "docorder": self._parse_docorder(row.get("docorder")),
                        "post_type": post_type,
                        "page_url": self._build_page_url(int(source_post_id), post_type),
                        "download_url": self._clean_text(row.get("download_url")) or None,
                        "attachment_id": int(row["attachment_id"]) if row.get("attachment_id") else None,
                    }
                )

            logger.info("Fetched %s published forms from MySQL %s", len(forms), self.database)
            return forms
        except Exception as exc:
            logger.error("Failed to fetch forms from MySQL: %s", exc, exc_info=True)
            raise
        finally:
            if connection is not None:
                connection.close()


def get_eblhome_forms_sync() -> EblHomeFormsSync:
    return EblHomeFormsSync()
