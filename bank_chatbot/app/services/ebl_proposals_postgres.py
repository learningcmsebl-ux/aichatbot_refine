"""
EBL Home proposals index — searchable metadata and download links only.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from typing import Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()

EBL_PROPOSALS_MAX_RESULTS = int(os.getenv("EBL_PROPOSALS_MAX_RESULTS", "10"))


class EblProposal(Base):
    __tablename__ = "ebl_proposals_index"

    id = Column(Integer, primary_key=True, index=True)
    source_post_id = Column(Integer, unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False, index=True)
    post_type = Column(String(64), nullable=False, default="proposal_update")
    page_url = Column(Text, nullable=False)
    download_url = Column(Text, nullable=True)
    attachment_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EblProposalsDB:
    """PostgreSQL index for EBL Home proposal metadata and links."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        if database_url is None:
            database_url = os.getenv(
                "EBL_PROPOSALS_DB_URL",
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
        return min(effective_limit, EBL_PROPOSALS_MAX_RESULTS)

    @staticmethod
    def _to_dict(proposal: EblProposal) -> Dict:
        return {
            "id": proposal.id,
            "source_post_id": proposal.source_post_id,
            "title": proposal.title,
            "post_type": proposal.post_type,
            "page_url": proposal.page_url,
            "download_url": proposal.download_url,
            "attachment_id": proposal.attachment_id,
        }

    def sync_items(self, items: List[Dict], clear_existing: bool = False) -> Dict[str, int]:
        stats = {"total": len(items), "inserted": 0, "updated": 0, "errors": 0}
        try:
            with self.get_session() as session:
                if clear_existing:
                    deleted = session.query(EblProposal).delete()
                    session.commit()
                    logger.info("Cleared %s existing proposal records", deleted)

                for item_data in items:
                    try:
                        existing = session.query(EblProposal).filter(
                            EblProposal.source_post_id == item_data["source_post_id"]
                        ).first()
                        if existing:
                            for key, value in item_data.items():
                                if hasattr(existing, key) and value is not None:
                                    setattr(existing, key, value)
                            stats["updated"] += 1
                        else:
                            session.add(EblProposal(**item_data))
                            stats["inserted"] += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to sync proposal %s: %s",
                            item_data.get("title", "unknown"),
                            exc,
                        )
                        stats["errors"] += 1
        except Exception:
            logger.error("Proposal sync failed", exc_info=True)
            raise
        return stats

    @staticmethod
    def _search_tokens(query: str) -> List[str]:
        stop_words = {
            "the", "a", "an", "of", "for", "to", "from", "in", "on", "at", "and",
            "or", "is", "are", "was", "were", "what", "where", "how", "can", "i",
            "me", "my", "get", "find", "search", "download", "need", "want", "link",
            "proposal", "proposals", "update", "status", "ebl", "home", "eblhome",
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
            q = session.query(EblProposal)

            if tokens:
                for token in tokens:
                    pattern = f"%{token}%"
                    q = q.filter(func.lower(EblProposal.title).like(pattern))
            else:
                pattern = f"%{query_clean.lower()}%"
                q = q.filter(func.lower(EblProposal.title).like(pattern))

            results = q.order_by(EblProposal.title.asc()).limit(effective_limit).all()
            return [self._to_dict(proposal) for proposal in results]

    def count_search_results(self, query: str) -> int:
        query_clean = (query or "").strip()
        if not query_clean:
            return 0

        tokens = self._search_tokens(query_clean)
        with self.get_session() as session:
            q = session.query(EblProposal)
            if tokens:
                for token in tokens:
                    pattern = f"%{token}%"
                    q = q.filter(func.lower(EblProposal.title).like(pattern))
            else:
                pattern = f"%{query_clean.lower()}%"
                q = q.filter(func.lower(EblProposal.title).like(pattern))
            return q.count()

    def total_items(self) -> int:
        with self.get_session() as session:
            return session.query(EblProposal).count()

    def get_by_source_post_id(self, source_post_id: int) -> Optional[Dict]:
        with self.get_session() as session:
            proposal = session.query(EblProposal).filter(
                EblProposal.source_post_id == source_post_id
            ).first()
            return self._to_dict(proposal) if proposal else None


_ebl_proposals_db: Optional[EblProposalsDB] = None


def get_ebl_proposals_db(database_url: Optional[str] = None) -> EblProposalsDB:
    global _ebl_proposals_db
    if _ebl_proposals_db is None:
        _ebl_proposals_db = EblProposalsDB(database_url)
    return _ebl_proposals_db
