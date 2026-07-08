-- Fee data cleanup (stage 10): fix CUSTOMER_VERIFICATION_CIB VISA ANY outlier (1.73 vs 115 BDT)
-- Idempotent: only updates the suspect row if still at 1.73.

UPDATE card_fee_master
SET
    fee_value    = 115.0000,
    answer_text  = 'BDT 115.00 per transaction',
    remarks      = COALESCE(NULLIF(btrim(remarks), ''), '')
                   || ' [fee_cleanup_10] aligned VISA ANY CIB fee with other VISA products (was 1.73 BDT)',
    updated_at   = NOW()
WHERE fee_id = 'f386a2d1-67ee-471a-b8db-7d9bdf2c2fc1'
  AND status = 'ACTIVE'
  AND charge_type = 'CUSTOMER_VERIFICATION_CIB'
  AND card_product = 'ANY'
  AND card_network = 'VISA'
  AND fee_value = 1.73;
