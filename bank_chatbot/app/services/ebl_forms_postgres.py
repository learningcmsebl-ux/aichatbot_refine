"""
EBL Home forms index — searchable metadata and download links only.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from typing import Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()

EBL_FORMS_MAX_RESULTS = int(os.getenv("EBL_FORMS_MAX_RESULTS", "10"))


class EblForm(Base):
    __tablename__ = "ebl_forms_index"

    id = Column(Integer, primary_key=True, index=True)
    source_post_id = Column(Integer, unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False, index=True)
    department = Column(String(255), index=True, nullable=True)
    subject = Column(String(255), index=True, nullable=True)
    docorder = Column(Integer, nullable=True)
    post_type = Column(String(64), nullable=False, default="forms_download")
    page_url = Column(Text, nullable=False)
    download_url = Column(Text, nullable=True)
    attachment_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EblFormsDB:
    """PostgreSQL index for EBL Home form metadata and links."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        if database_url is None:
            database_url = os.getenv(
                "EBL_FORMS_DB_URL",
                os.getenv("PHONEBOOK_DB_URL")
                or os.getenv("POSTGRES_DB_URL")
                or (
                    f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:"
                    f"{os.getenv('POSTGRES_PASSWORD', '')}@"
                    f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
                    f"{os.getenv('POSTGRES_PORT', '5432')}/"
                    f"{os.getenv('POSTGRES_DB', 'bank_chatbot')}"
                ),
            )

        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            echo=False,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def get_session(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _normalize_limit(limit: Optional[int], default: int) -> int:
        effective_limit = default if limit is None else limit
        if effective_limit <= 0:
            return 0
        return min(effective_limit, EBL_FORMS_MAX_RESULTS)

    @staticmethod
    def _to_dict(form: EblForm) -> Dict:
        return {
            "id": form.id,
            "source_post_id": form.source_post_id,
            "title": form.title,
            "department": form.department,
            "subject": form.subject,
            "docorder": form.docorder,
            "post_type": form.post_type,
            "page_url": form.page_url,
            "download_url": form.download_url,
            "attachment_id": form.attachment_id,
        }

    def upsert_form(self, form_data: Dict) -> bool:
        try:
            with self.get_session() as session:
                existing = session.query(EblForm).filter(
                    EblForm.source_post_id == form_data["source_post_id"]
                ).first()
                if existing:
                    for key, value in form_data.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                else:
                    session.add(EblForm(**form_data))
            return True
        except Exception as exc:
            logger.error("Failed to upsert form %s: %s", form_data.get("title"), exc)
            return False

    def sync_forms(self, forms: List[Dict], clear_existing: bool = False) -> Dict[str, int]:
        stats = {"total": len(forms), "inserted": 0, "updated": 0, "errors": 0}
        try:
            with self.get_session() as session:
                if clear_existing:
                    deleted = session.query(EblForm).delete()
                    session.commit()
                    logger.info("Cleared %s existing form records", deleted)

                for form_data in forms:
                    try:
                        existing = session.query(EblForm).filter(
                            EblForm.source_post_id == form_data["source_post_id"]
                        ).first()
                        if existing:
                            for key, value in form_data.items():
                                if hasattr(existing, key) and value is not None:
                                    setattr(existing, key, value)
                            stats["updated"] += 1
                        else:
                            session.add(EblForm(**form_data))
                            stats["inserted"] += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to sync form %s: %s",
                            form_data.get("title", "unknown"),
                            exc,
                        )
                        stats["errors"] += 1
        except Exception:
            logger.error("Form sync failed", exc_info=True)
            raise
        return stats

    @staticmethod
    def _search_tokens(query: str) -> List[str]:
        stop_words = {
            "the", "a", "an", "of", "for", "to", "from", "in", "on", "at", "and",
            "or", "is", "are", "was", "were", "what", "where", "how", "can", "i",
            "me", "my", "get", "find", "search", "download", "need", "want", "link",
            "form", "forms", "template", "ebl", "home", "eblhome",
        }
        tokens = [
            token.strip()
            for token in re.split(r"[\s,.;:!?]+", (query or "").lower())
            if len(token.strip()) > 2 and token.strip() not in stop_words
        ]
        return tokens

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        query_clean = (query or "").strip()
        effective_limit = self._normalize_limit(limit, 5)
        if not query_clean or effective_limit == 0:
            return []

        tokens = self._search_tokens(query_clean)
        with self.get_session() as session:
            q = session.query(EblForm)

            if tokens:
                conditions = []
                for token in tokens:
                    pattern = f"%{token}%"
                    conditions.append(
                        or_(
                            func.lower(EblForm.title).like(pattern),
                            func.lower(EblForm.department).like(pattern),
                            func.lower(EblForm.subject).like(pattern),
                        )
                    )
                for condition in conditions:
                    q = q.filter(condition)
            else:
                pattern = f"%{query_clean.lower()}%"
                q = q.filter(
                    or_(
                        func.lower(EblForm.title).like(pattern),
                        func.lower(EblForm.department).like(pattern),
                        func.lower(EblForm.subject).like(pattern),
                    )
                )

            results = (
                q.order_by(EblForm.docorder.asc().nullslast(), EblForm.title.asc())
                .limit(effective_limit)
                .all()
            )
            return [self._to_dict(form) for form in results]

    def count_search_results(self, query: str) -> int:
        query_clean = (query or "").strip()
        if not query_clean:
            return 0

        tokens = self._search_tokens(query_clean)
        with self.get_session() as session:
            q = session.query(EblForm)
            if tokens:
                for token in tokens:
                    pattern = f"%{token}%"
                    q = q.filter(
                        or_(
                            func.lower(EblForm.title).like(pattern),
                            func.lower(EblForm.department).like(pattern),
                            func.lower(EblForm.subject).like(pattern),
                        )
                    )
            else:
                pattern = f"%{query_clean.lower()}%"
                q = q.filter(
                    or_(
                        func.lower(EblForm.title).like(pattern),
                        func.lower(EblForm.department).like(pattern),
                        func.lower(EblForm.subject).like(pattern),
                    )
                )
            return q.count()

    def total_forms(self) -> int:
        with self.get_session() as session:
            return session.query(EblForm).count()

    def get_by_source_post_id(self, source_post_id: int) -> Optional[Dict]:
        with self.get_session() as session:
            form = session.query(EblForm).filter(
                EblForm.source_post_id == source_post_id
            ).first()
            return self._to_dict(form) if form else None


_ebl_forms_db: Optional[EblFormsDB] = None


def get_ebl_forms_db(database_url: Optional[str] = None) -> EblFormsDB:
    global _ebl_forms_db
    if _ebl_forms_db is None:
        _ebl_forms_db = EblFormsDB(database_url)
    return _ebl_forms_db
