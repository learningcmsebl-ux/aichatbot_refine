"""
Create `card_fee_notes` table and import schedule Notes into Postgres.

Source:
  credit_card_rate/CARD_CHARGES_AND_FEES_SCHEDULE_UPDATE_18.12.2025.txt

It looks for the "CHARGE TYPE: Notes" section and then parses entries like:
  CHARGE TYPE: 17. Issuance/annual/renewal fee (including VAT) for FX cards: ...

Connection:
  Uses the same env vars as fee_engine_service.py (FEE_ENGINE_DB_URL preferred).

Run (PowerShell example):
  $env:FEE_ENGINE_DB_URL="postgresql://chatbot_user:chatbot_password_123@localhost:5432/chatbot_db"
  python credit_card_rate/fee_engine/import_card_fee_notes.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import List

from sqlalchemy import text

from fee_engine_service import engine


@dataclass(frozen=True)
class Note:
    note_number: int
    note_text: str


def parse_notes_from_schedule(schedule_path: Path) -> List[Note]:
    content = schedule_path.read_text(encoding="utf-8", errors="replace").splitlines()

    # Find the Notes section marker
    start_idx = None
    for i, line in enumerate(content):
        if line.strip() == "CHARGE TYPE: Notes":
            start_idx = i
            break

    if start_idx is None:
        raise RuntimeError("Could not find 'CHARGE TYPE: Notes' section in schedule file.")

    notes: List[Note] = []
    note_line_re = re.compile(r"^\s*CHARGE TYPE:\s*(\d+)\.\s*(.+?)\s*$")

    for line in content[start_idx + 1 :]:
        m = note_line_re.match(line)
        if not m:
            continue
        note_number = int(m.group(1))
        note_text = m.group(2).strip()
        if not note_text:
            continue
        notes.append(Note(note_number=note_number, note_text=note_text))

    if not notes:
        raise RuntimeError("Found Notes section but parsed 0 notes.")

    # Deduplicate by note number (keep last occurrence if any)
    dedup: dict[int, str] = {}
    for n in notes:
        dedup[n.note_number] = n.note_text

    return [Note(k, dedup[k]) for k in sorted(dedup.keys())]


def ensure_table() -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS card_fee_notes (
                    note_number INTEGER PRIMARY KEY,
                    note_text TEXT NOT NULL,
                    source_file TEXT,
                    effective_from DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_card_fee_notes_effective_from
                ON card_fee_notes(effective_from);
                """
            )
        )
        conn.commit()


def upsert_notes(notes: List[Note], source_file: str, effective_from: date) -> None:
    with engine.connect() as conn:
        for n in notes:
            conn.execute(
                text(
                    """
                    INSERT INTO card_fee_notes (note_number, note_text, source_file, effective_from, updated_at)
                    VALUES (:note_number, :note_text, :source_file, :effective_from, CURRENT_TIMESTAMP)
                    ON CONFLICT (note_number) DO UPDATE
                    SET note_text = EXCLUDED.note_text,
                        source_file = EXCLUDED.source_file,
                        effective_from = EXCLUDED.effective_from,
                        updated_at = CURRENT_TIMESTAMP;
                    """
                ),
                {
                    "note_number": n.note_number,
                    "note_text": n.note_text,
                    "source_file": source_file,
                    "effective_from": effective_from,
                },
            )
        conn.commit()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    schedule_path = repo_root / "credit_card_rate" / "CARD_CHARGES_AND_FEES_SCHEDULE_UPDATE_18.12.2025.txt"

    if not schedule_path.exists():
        raise RuntimeError(f"Schedule file not found: {schedule_path}")

    notes = parse_notes_from_schedule(schedule_path)
    ensure_table()
    upsert_notes(
        notes=notes,
        source_file=schedule_path.name,
        effective_from=date(2026, 1, 1),
    )

    print(f"[OK] Imported/updated {len(notes)} notes into card_fee_notes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

