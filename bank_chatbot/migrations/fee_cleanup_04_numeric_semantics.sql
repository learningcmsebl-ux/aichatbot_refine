-- Fee data cleanup (stage 4): fix clearly-wrong numeric encodings (excluding INTEREST_RATE — see review queue)
-- Idempotent: only updates rows still in the pre-fix state.

-- RISK_ASSURANCE_FEE: 0.0035 TEXT → 0.35% ON_OUTSTANDING
UPDATE card_fee_master
SET
    fee_value    = 0.35,
    fee_unit     = 'PERCENT',
    fee_basis    = 'ON_OUTSTANDING',
    answer_text  = 'The risk assurance fee is 0.35% on outstanding balance.',
    remarks      = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_04] 0.0035 TEXT → 0.35% PERCENT',
    updated_at   = NOW()
WHERE charge_type = 'RISK_ASSURANCE_FEE'
  AND fee_unit = 'TEXT'
  AND fee_value = 0.0035;

-- Safety net: any remaining TEXT-unit rows with tiny decimal values (rate-like)
UPDATE card_fee_master
SET
    fee_value   = fee_value * 100,
    fee_unit    = 'PERCENT',
    fee_basis   = COALESCE(NULLIF(fee_basis, ''), 'ON_OUTSTANDING'),
    answer_text = COALESCE(
        NULLIF(btrim(answer_text), ''),
        'The ' || lower(replace(charge_type, '_', ' ')) || ' is ' || (fee_value * 100)::TEXT || '% on outstanding balance.'
    ),
    remarks     = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_04] auto-converted decimal TEXT rate to PERCENT',
    updated_at  = NOW()
WHERE fee_unit = 'TEXT'
  AND fee_value > 0
  AND fee_value < 1
  AND charge_type <> 'ALL_CARD_RELATED_PAYMENT';
