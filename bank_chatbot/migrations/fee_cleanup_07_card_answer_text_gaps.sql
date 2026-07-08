-- Fee data cleanup (stage 7): remaining card answer_text gaps
-- Idempotent.

-- SKYLOUNGE Platinum/VISA row missing answer_text (other products use generic zero-fee line)
UPDATE card_fee_master
SET
    answer_text = 'BDT 0.00 per year',
    remarks     = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_07] backfilled SKYLOUNGE answer_text',
    updated_at  = NOW()
WHERE fee_id = '4e2c1439-2f67-4d3b-b16a-76705bdf0195'
  AND (answer_text IS NULL OR btrim(answer_text) = '');
