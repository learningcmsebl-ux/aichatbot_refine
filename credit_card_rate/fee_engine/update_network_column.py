"""Update card_network column to VARCHAR(100)"""
from fee_engine_service import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE card_fee_master ALTER COLUMN card_network TYPE VARCHAR(100)"))
    conn.commit()
    print("Column card_network updated to VARCHAR(100)")










