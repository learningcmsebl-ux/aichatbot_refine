"""
EBL Home application links index — searchable metadata and URLs only.
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

EBL_APPS_MAX_RESULTS = int(os.getenv("EBL_APPS_MAX_RESULTS", "10"))


class EblApp(Base):
    __tablename__ = "ebl_apps_index"

    id = Column(Integer, primary_key=True, index=True)
    source_post_id = Column(Integer, unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False, index=True)
    app_url = Column(Text, nullable=False)
    page_url = Column(Text, nullable=False)
    post_type = Column(String(64), nullable=False, default="ebllinks")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EblAppsDB:
    """PostgreSQL index for EBL Home intranet application links."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        if database_url is None:
            database_url = os.getenv(
                "EBL_APPS_DB_URL",
                os.getenv("EBL_FORMS_DB_URL")
                or os.getenv("PHONEBOOK_DB_URL")
                or os.getenv("POSTGRES_DB_URL")
                or (
                    f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:"
                    f"{os.getenv('POSTGRES_PASSWORD', '')}@"
                    f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
                    f"{os.getenv('POSTGRES_PORT', '5432')}/"
                    f"{os.getenv('POSTGRES_DB', 'bank_chatbot')}"
                ),
            )

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
        return min(effective_limit, EBL_APPS_MAX_RESULTS)

    @staticmethod
    def _to_dict(app: EblApp) -> Dict:
        return {
            "id": app.id,
            "source_post_id": app.source_post_id,
            "title": app.title,
            "app_url": app.app_url,
            "page_url": app.page_url,
            "post_type": app.post_type,
        }

    def sync_apps(self, apps: List[Dict], clear_existing: bool = False) -> Dict[str, int]:
        stats = {"total": len(apps), "inserted": 0, "updated": 0, "errors": 0}
        try:
            with self.get_session() as session:
                if clear_existing:
                    session.query(EblApp).delete()
                    session.commit()

                for app_data in apps:
                    try:
                        existing = session.query(EblApp).filter(
                            EblApp.source_post_id == app_data["source_post_id"]
                        ).first()
                        if existing:
                            for key, value in app_data.items():
                                if hasattr(existing, key) and value is not None:
                                    setattr(existing, key, value)
                            stats["updated"] += 1
                        else:
                            session.add(EblApp(**app_data))
                            stats["inserted"] += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to sync app %s: %s",
                            app_data.get("title", "unknown"),
                            exc,
                        )
                        stats["errors"] += 1
        except Exception:
            logger.error("App sync failed", exc_info=True)
            raise
        return stats

    @staticmethod
    def _search_tokens(query: str) -> List[str]:
        stop_words = {
            "the", "a", "an", "of", "for", "to", "from", "in", "on", "at", "and",
            "or", "is", "are", "what", "where", "how", "can", "i", "me", "my",
            "open", "access", "launch", "visit", "go", "login", "log", "link",
            "url", "app", "application", "portal", "hub", "system", "ebl", "home",
            "eblhome", "please", "show", "find", "get", "need", "want",
        }
        return [
            token.strip()
            for token in re.split(r"[\s,.;:!?]+", (query or "").lower())
            if len(token.strip()) > 2 and token.strip() not in stop_words
        ]

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        query_clean = (query or "").strip()
        effective_limit = self._normalize_limit(limit, 5)
        if not query_clean or effective_limit == 0:
            return []

        tokens = self._search_tokens(query_clean)
        with self.get_session() as session:
            q = session.query(EblApp)
            if tokens:
                for token in tokens:
                    pattern = f"%{token}%"
                    q = q.filter(
                        or_(
                            func.lower(EblApp.title).like(pattern),
                            func.lower(EblApp.app_url).like(pattern),
                        )
                    )
            else:
                pattern = f"%{query_clean.lower()}%"
                q = q.filter(
                    or_(
                        func.lower(EblApp.title).like(pattern),
                        func.lower(EblApp.app_url).like(pattern),
                    )
                )
            results = q.order_by(EblApp.title.asc()).limit(effective_limit).all()
            return [self._to_dict(app) for app in results]

    def count_search_results(self, query: str) -> int:
        query_clean = (query or "").strip()
        if not query_clean:
            return 0
        tokens = self._search_tokens(query_clean)
        with self.get_session() as session:
            q = session.query(EblApp)
            if tokens:
                for token in tokens:
                    pattern = f"%{token}%"
                    q = q.filter(
                        or_(
                            func.lower(EblApp.title).like(pattern),
                            func.lower(EblApp.app_url).like(pattern),
                        )
                    )
            else:
                pattern = f"%{query_clean.lower()}%"
                q = q.filter(
                    or_(
                        func.lower(EblApp.title).like(pattern),
                        func.lower(EblApp.app_url).like(pattern),
                    )
                )
            return q.count()

    def total_apps(self) -> int:
        with self.get_session() as session:
            return session.query(EblApp).count()

    def get_by_source_post_id(self, source_post_id: int) -> Optional[Dict]:
        with self.get_session() as session:
            app = session.query(EblApp).filter(
                EblApp.source_post_id == source_post_id
            ).first()
            return self._to_dict(app) if app else None


_ebl_apps_db: Optional[EblAppsDB] = None


def get_ebl_apps_db(database_url: Optional[str] = None) -> EblAppsDB:
    global _ebl_apps_db
    if _ebl_apps_db is None:
        _ebl_apps_db = EblAppsDB(database_url)
    return _ebl_apps_db
