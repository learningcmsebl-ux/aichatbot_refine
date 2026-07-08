-- Fee data cleanup (stage 5): backfill skybanking answer_text where NULL/empty
-- Idempotent: only fills rows with no answer_text.

UPDATE skybanking_fee_master
SET
    answer_text = CASE fee_id
        WHEN 'e553eb28-c36e-473b-abe3-c1a65f0700c4'::uuid THEN
            'The VISA Credit Card Bill Payment fee through Skybanking is BDT 11.50 per transaction.'
        WHEN '5f0fe483-2429-44c9-9079-d909d419239d'::uuid THEN
            'The Balance Certificate fee for Skybanking is BDT 345 per request.'
        WHEN 'ccc038d9-8b5f-4ea2-88e2-1619be864b59'::uuid THEN
            'The DPS Certificate fee for Skybanking is BDT 345 per request.'
        WHEN '23185fef-6f6f-4598-b62e-7ac00e370f18'::uuid THEN
            'The Loan Outstanding Certificate fee for Skybanking is BDT 575 per request.'
        WHEN '240ff1c5-2a3c-44c1-b176-23e01bb134fd'::uuid THEN
            'The NOC Against Loan fee for Skybanking is BDT 575 per request.'
        WHEN '3583a262-ddf7-49b0-af53-9f00cef856c4'::uuid THEN
            'The NPSB Fund Transfer fee through Skybanking is BDT 9.99 per transaction.'
        ELSE answer_text
    END,
    remarks    = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_05] backfilled answer_text',
    updated_at = NOW()
WHERE fee_id IN (
    'e553eb28-c36e-473b-abe3-c1a65f0700c4',
    '5f0fe483-2429-44c9-9079-d909d419239d',
    'ccc038d9-8b5f-4ea2-88e2-1619be864b59',
    '23185fef-6f6f-4598-b62e-7ac00e370f18',
    '240ff1c5-2a3c-44c1-b176-23e01bb134fd',
    '3583a262-ddf7-49b0-af53-9f00cef856c4'
)
AND (answer_text IS NULL OR btrim(answer_text) = '');

-- Generic fallback for any remaining skybanking rows (deterministic sentence from fields)
UPDATE skybanking_fee_master
SET
    answer_text = CASE
        WHEN fee_unit = 'PERCENT' AND fee_amount IS NOT NULL THEN
            'The ' || product_name || ' fee through Skybanking is ' || fee_amount::TEXT || '%.'
        WHEN fee_amount IS NOT NULL AND fee_amount = 0 THEN
            'The ' || product_name || ' fee through Skybanking is free.'
        WHEN fee_amount IS NOT NULL THEN
            'The ' || product_name || ' fee through Skybanking is BDT ' || fee_amount::TEXT || '.'
        ELSE
            'Please contact Eastern Bank PLC. for the latest Skybanking fee on ' || product_name || '.'
    END,
    remarks    = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_05] auto-generated answer_text',
    updated_at = NOW()
WHERE (answer_text IS NULL OR btrim(answer_text) = '')
  AND status = 'ACTIVE';
