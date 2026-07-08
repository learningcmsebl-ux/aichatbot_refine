"""
EBL Home leadership index — management committee and board of directors.
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

EBL_LEADERSHIP_MAX_RESULTS = int(os.getenv("EBL_LEADERSHIP_MAX_RESULTS", "15"))

ROLE_ALIASES: Dict[str, List[str]] = {
    "cfo": ["chief financial officer", "cfo"],
    "cto": ["chief technology officer", "chief information officer", "cto", "cio"],
    "cro": ["chief risk officer", "cro"],
    "ceo": ["chief executive officer", "ceo", "managing director", "md and ceo"],
    "md": ["managing director", "md and ceo", "md & ceo"],
    "dmd": ["deputy managing director", "dmd"],
    "chairman": ["chairman", "chairperson", "chair"],
}


class EblLeader(Base):
    __tablename__ = "ebl_leadership_index"

    id = Column(Integer, primary_key=True, index=True)
    source_post_id = Column(Integer, unique=True, nullable=False, index=True)
    full_name = Column(String(500), nullable=False, index=True)
    designation = Column(String(500), index=True, nullable=True)
    category = Column(String(32), nullable=False, index=True)
    post_type = Column(String(64), nullable=False)
    priority = Column(Integer, nullable=True)
    level_priority = Column(Integer, nullable=True)
    photo_url = Column(Text, nullable=True)
    page_url = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EblLeadershipDB:
    """PostgreSQL index for EBL Home leadership profiles."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        if database_url is None:
            database_url = os.getenv(
                "EBL_LEADERSHIP_DB_URL",
                os.getenv("EBL_APPS_DB_URL")
                or os.getenv("EBL_FORMS_DB_URL")
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
    def _to_dict(leader: EblLeader) -> Dict:
        return {
            "id": leader.id,
            "source_post_id": leader.source_post_id,
            "full_name": leader.full_name,
            "designation": leader.designation,
            "category": leader.category,
            "post_type": leader.post_type,
            "priority": leader.priority,
            "level_priority": leader.level_priority,
            "photo_url": leader.photo_url,
            "page_url": leader.page_url,
        }

    def sync_leaders(self, leaders: List[Dict], clear_existing: bool = False) -> Dict[str, int]:
        stats = {"total": len(leaders), "inserted": 0, "updated": 0, "errors": 0}
        with self.get_session() as session:
            if clear_existing:
                session.query(EblLeader).delete()
                session.commit()

            for leader_data in leaders:
                try:
                    existing = session.query(EblLeader).filter(
                        EblLeader.source_post_id == leader_data["source_post_id"]
                    ).first()
                    if existing:
                        for key, value in leader_data.items():
                            if hasattr(existing, key) and value is not None:
                                setattr(existing, key, value)
                        stats["updated"] += 1
                    else:
                        session.add(EblLeader(**leader_data))
                        stats["inserted"] += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to sync leader %s: %s",
                        leader_data.get("full_name", "unknown"),
                        exc,
                    )
                    stats["errors"] += 1
        return stats

    def list_by_category(self, category: str, limit: int = 15) -> List[Dict]:
        effective_limit = min(max(limit, 1), EBL_LEADERSHIP_MAX_RESULTS)
        with self.get_session() as session:
            rows = (
                session.query(EblLeader)
                .filter(EblLeader.category == category)
                .order_by(
                    EblLeader.level_priority.asc().nullslast(),
                    EblLeader.priority.asc().nullslast(),
                    EblLeader.full_name.asc(),
                )
                .limit(effective_limit)
                .all()
            )
            return [self._to_dict(row) for row in rows]

    def search_by_name(self, name: str, limit: int = 5) -> List[Dict]:
        pattern = f"%{name.lower()}%"
        with self.get_session() as session:
            rows = (
                session.query(EblLeader)
                .filter(func.lower(EblLeader.full_name).like(pattern))
                .order_by(EblLeader.level_priority.asc().nullslast(), EblLeader.priority.asc().nullslast())
                .limit(min(limit, EBL_LEADERSHIP_MAX_RESULTS))
                .all()
            )
            return [self._to_dict(row) for row in rows]

    def search_by_designation(self, designation: str, limit: int = 5) -> List[Dict]:
        pattern = f"%{designation.lower()}%"
        with self.get_session() as session:
            rows = (
                session.query(EblLeader)
                .filter(func.lower(EblLeader.designation).like(pattern))
                .order_by(EblLeader.level_priority.asc().nullslast(), EblLeader.priority.asc().nullslast())
                .limit(min(limit, EBL_LEADERSHIP_MAX_RESULTS))
                .all()
            )
            return [self._to_dict(row) for row in rows]

    @staticmethod
    def _detect_precise_role(query_lower: str) -> Optional[str]:
        if re.search(r"\badditional\s+managing\s+director\b", query_lower):
            return "additional_md"
        if re.search(r"\bdeputy\s+managing\s+director\b", query_lower) or re.search(r"\bdmd\b", query_lower):
            return "dmd"
        if re.search(r"\bmanaging\s+director\b", query_lower) or re.search(r"\bmd\b", query_lower):
            return "md"
        return None

    @staticmethod
    def _designation_matches_precise_role(designation: Optional[str], role_key: str) -> bool:
        designation_lower = (designation or "").lower().strip()
        if not designation_lower:
            return False

        if role_key == "md":
            if "additional" in designation_lower or "deputy" in designation_lower:
                return False
            return designation_lower in {
                "managing director",
                "md and ceo",
                "md & ceo",
                "managing director & ceo",
            }

        if role_key == "additional_md":
            return "additional" in designation_lower and "managing director" in designation_lower

        if role_key == "dmd":
            return "deputy" in designation_lower and "managing director" in designation_lower

        return False

    @staticmethod
    def _dedupe_leaders(leaders: List[Dict]) -> List[Dict]:
        by_name: Dict[str, Dict] = {}
        for leader in leaders:
            key = (leader.get("full_name") or "").lower().strip()
            if not key:
                continue
            existing = by_name.get(key)
            if existing is None:
                by_name[key] = leader
                continue
            existing_rank = (
                existing.get("level_priority") if existing.get("level_priority") is not None else 9999,
                existing.get("priority") if existing.get("priority") is not None else 9999,
            )
            new_rank = (
                leader.get("level_priority") if leader.get("level_priority") is not None else 9999,
                leader.get("priority") if leader.get("priority") is not None else 9999,
            )
            if new_rank < existing_rank:
                by_name[key] = leader
        return list(by_name.values())

    def search_by_precise_role(self, role_key: str, limit: int = 5) -> List[Dict]:
        effective_limit = min(max(limit, 1), EBL_LEADERSHIP_MAX_RESULTS)
        with self.get_session() as session:
            rows = (
                session.query(EblLeader)
                .order_by(EblLeader.level_priority.asc().nullslast(), EblLeader.priority.asc().nullslast())
                .all()
            )
            matched = [
                self._to_dict(row)
                for row in rows
                if self._designation_matches_precise_role(row.designation, role_key)
            ]

        if role_key in {"md", "dmd", "additional_md"}:
            management_matches = [leader for leader in matched if leader.get("category") == "management"]
            if management_matches:
                matched = management_matches

        matched = self._dedupe_leaders(matched)
        return matched[:effective_limit]

    def smart_search(self, query: str, *, category: Optional[str] = None, limit: int = 5) -> List[Dict]:
        query_clean = (query or "").strip()
        if not query_clean:
            return []

        query_lower = query_clean.lower()
        effective_limit = min(max(limit, 1), EBL_LEADERSHIP_MAX_RESULTS)

        precise_role = self._detect_precise_role(query_lower)
        if precise_role:
            results = self.search_by_precise_role(precise_role, limit=effective_limit)
            if category:
                results = [r for r in results if r["category"] == category]
            if results:
                return results[:effective_limit]

        for alias_key, alias_terms in ROLE_ALIASES.items():
            if alias_key in {"md", "ceo"}:
                continue
            if re.search(rf"\b{re.escape(alias_key)}\b", query_lower) or alias_key in query_lower:
                for term in alias_terms:
                    results = self.search_by_designation(term, limit=effective_limit)
                    if results:
                        if category:
                            results = [r for r in results if r["category"] == category]
                        if results:
                            return results[:effective_limit]

        name_results = self.search_by_name(query_clean, limit=effective_limit)
        if name_results:
            if category:
                name_results = [r for r in name_results if r["category"] == category]
            if name_results:
                return name_results[:effective_limit]

        tokens = [t for t in re.split(r"[\s,.;:!?]+", query_lower) if len(t) > 2]
        if tokens:
            with self.get_session() as session:
                q = session.query(EblLeader)
                if category:
                    q = q.filter(EblLeader.category == category)
                for token in tokens:
                    pattern = f"%{token}%"
                    q = q.filter(
                        or_(
                            func.lower(EblLeader.full_name).like(pattern),
                            func.lower(EblLeader.designation).like(pattern),
                        )
                    )
                rows = (
                    q.order_by(EblLeader.level_priority.asc().nullslast(), EblLeader.priority.asc().nullslast())
                    .limit(effective_limit)
                    .all()
                )
                if rows:
                    return [self._to_dict(row) for row in rows]

        designation_results = self.search_by_designation(query_clean, limit=effective_limit)
        if category:
            designation_results = [r for r in designation_results if r["category"] == category]
        return designation_results[:effective_limit]

    def total_leaders(self) -> int:
        with self.get_session() as session:
            return session.query(EblLeader).count()

    def get_by_source_post_id(self, source_post_id: int) -> Optional[Dict]:
        with self.get_session() as session:
            row = session.query(EblLeader).filter(EblLeader.source_post_id == source_post_id).first()
            return self._to_dict(row) if row else None


_ebl_leadership_db: Optional[EblLeadershipDB] = None


def get_ebl_leadership_db(database_url: Optional[str] = None) -> EblLeadershipDB:
    global _ebl_leadership_db
    if _ebl_leadership_db is None:
        _ebl_leadership_db = EblLeadershipDB(database_url)
    return _ebl_leadership_db
