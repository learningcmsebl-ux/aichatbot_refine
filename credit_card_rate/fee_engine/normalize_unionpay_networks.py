"""
Normalize UnionPay network values in card_fee_master.

Goal:
- Update existing rows where card_network contains UnionPay variants (e.g., "UnionPay International")
  to the canonical value: "UNIONPAY"

Run:
  python normalize_unionpay_networks.py

Uses the same DB connection env vars as fee_engine_service.py.
"""

from sqlalchemy import text

from fee_engine_service import engine


def main() -> int:
    with engine.connect() as conn:
        before = conn.execute(
            text(
                """
                SELECT COUNT(*)::int
                FROM card_fee_master
                WHERE card_network ILIKE '%unionpay%'
                   OR card_network ILIKE '%union pay%'
                """
            )
        ).scalar_one()

        # Normalize (idempotent)
        result = conn.execute(
            text(
                """
                UPDATE card_fee_master
                SET card_network = 'UNIONPAY'
                WHERE card_network <> 'UNIONPAY'
                  AND (
                        card_network ILIKE '%unionpay%'
                     OR card_network ILIKE '%union pay%'
                  )
                """
            )
        )
        conn.commit()

        after = conn.execute(
            text(
                """
                SELECT COUNT(*)::int
                FROM card_fee_master
                WHERE card_network = 'UNIONPAY'
                """
            )
        ).scalar_one()

        print("UnionPay normalization complete")
        print(f"- Rows matching UnionPay variants (before): {before}")
        print(f"- Rows updated: {result.rowcount}")
        print(f"- Rows with card_network='UNIONPAY' (after): {after}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

