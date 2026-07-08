-- Fee data cleanup (stage 9): deactivate exact duplicate active rows + queue CCTV review
-- Idempotent: dedupe only affects ACTIVE rows; review queue uses ON CONFLICT DO NOTHING.

-- 9a) Deactivate exact duplicates (keep earliest created_at, then lowest fee_id)
WITH ranked AS (
    SELECT
        fee_id,
        ROW_NUMBER() OVER (
            PARTITION BY
                charge_type,
                card_product,
                card_network,
                card_category,
                product_line,
                fee_value,
                fee_unit,
                fee_basis,
                effective_from,
                COALESCE(effective_to, 'infinity'::date),
                priority,
                COALESCE(answer_text, '')
            ORDER BY created_at ASC, fee_id ASC
        ) AS rn
    FROM card_fee_master
    WHERE status = 'ACTIVE'
)
UPDATE card_fee_master c
SET
    status     = 'INACTIVE',
    remarks    = COALESCE(NULLIF(btrim(c.remarks), ''), '')
                 || ' [fee_cleanup_09] deactivated exact duplicate (kept earlier row)',
    updated_at = NOW()
FROM ranked r
WHERE c.fee_id = r.fee_id
  AND r.rn > 1
  AND c.status = 'ACTIVE';

-- 9b) Queue VISA CREDIT CCTV rows at 21 BDT for business review
INSERT INTO fee_data_review_queue (table_name, row_id, issue_code, severity, summary)
SELECT
    'card_fee_master',
    fee_id,
    'CCTV_VISA_CREDIT_SUSPECT',
    'HIGH',
    charge_type || ' for VISA CREDIT is BDT 21.00; DINERS/UNIONPAY CREDIT use BDT '
    || CASE charge_type
        WHEN 'ATM_CCTV_FOOTAGE_INSIDE_DHAKA' THEN '2,300'
        WHEN 'ATM_CCTV_FOOTAGE_OUTSIDE_DHAKA' THEN '3,450'
        ELSE '2,300/3,450'
       END
    || '. Confirm against official SOC before changing fee_value or answer_text.'
FROM card_fee_master
WHERE status = 'ACTIVE'
  AND charge_type IN ('ATM_CCTV_FOOTAGE_INSIDE_DHAKA', 'ATM_CCTV_FOOTAGE_OUTSIDE_DHAKA')
  AND card_product = 'ANY'
  AND card_network = 'VISA'
  AND card_category = 'CREDIT'
  AND fee_value = 21
ON CONFLICT (table_name, row_id, issue_code) DO NOTHING;
