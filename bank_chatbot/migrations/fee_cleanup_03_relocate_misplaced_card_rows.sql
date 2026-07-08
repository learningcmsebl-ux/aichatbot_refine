-- Fee data cleanup (stage 3): fix or deactivate misplaced card_fee_master rows
-- Does NOT delete data; deactivates duplicates and normalizes the canonical survivor.

-- 3a) ALL_CARD_RELATED_PAYMENT — keep one canonical TEXT row, deactivate duplicate
UPDATE card_fee_master
SET
    charge_type    = 'ALL_CARD_RELATED_PAYMENT',
    card_product   = 'ANY',
    card_network   = 'ANY',
    card_category  = 'ANY',
    fee_value      = 0,
    fee_unit       = 'TEXT',
    fee_basis      = 'PER_TXN',
    condition_type = 'NOTE_BASED',
    remarks        = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_03] canonical ALL_CARD_RELATED_PAYMENT',
    updated_at     = NOW()
WHERE fee_id = 'aa289cf6-1e2d-4aa2-9a02-de338c8c26ac'
  AND status = 'ACTIVE';

UPDATE card_fee_master
SET
    status     = 'INACTIVE',
    remarks    = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_03] deactivated duplicate of ALL_CARD_RELATED_PAYMENT',
    updated_at = NOW()
WHERE fee_id = '2e715d77-b975-4995-bca6-944059703df6'
  AND status = 'ACTIVE';

-- 3b) Skybanking challan row in card table — skybanking_fee_master already has Government Payment
UPDATE card_fee_master
SET
    status     = 'INACTIVE',
    remarks    = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_03] deactivated: use skybanking_fee_master Government Payment',
    updated_at = NOW()
WHERE fee_id = 'c979eb5f-83e1-44a4-b552-33d2003469d0'
  AND status = 'ACTIVE';

-- 3c) Mortgage partial payment in card table — retail HOME_LOAN_PAYMENT_PROTECTION has authoritative row
UPDATE card_fee_master
SET
    status     = 'INACTIVE',
    remarks    = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_03] deactivated: use retail_asset HOME_LOAN_PAYMENT_PROTECTION PARTIAL_PAYMENT_FEE',
    updated_at = NOW()
WHERE fee_id = '3fa28efe-b1e7-414e-95f7-6a888e82745f'
  AND status = 'ACTIVE';

-- 3d) Priority banking FCY endorsement — normalize keys and product_line
UPDATE card_fee_master
SET
    charge_type     = 'FCY_ENDORSEMENT_FEE',
    card_product    = 'ANY',
    card_network    = 'ANY',
    card_category   = 'ANY',
    product_line    = 'PRIORITY_BANKING',
    full_card_name  = 'Priority Banking - FCY Endorsement Fee',
    remarks         = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_03] normalized Priority banking row',
    updated_at      = NOW()
WHERE fee_id = 'c170b12c-77d8-45b2-bea4-c7d57abc6d1a'
  AND status = 'ACTIVE';

-- 3e) Skybanking polluted network value
UPDATE skybanking_fee_master
SET
    network    = NULL,
    remarks    = COALESCE(NULLIF(btrim(remarks), ''), '') || ' [fee_cleanup_03] cleared invalid network value',
    updated_at = NOW()
WHERE fee_id = '0a43322c-84f8-4f05-8d78-9e8fc1c749e4'
  AND network = 'Skybanking A challan fee';
