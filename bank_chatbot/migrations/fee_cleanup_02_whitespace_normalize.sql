-- Fee data cleanup (stage 2): trim and collapse internal whitespace on lookup keys
-- Idempotent: only updates rows that still differ after normalization.

-- Helper: collapse runs of whitespace to a single space, then trim ends
CREATE OR REPLACE FUNCTION fee_normalize_ws(input TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT NULLIF(btrim(regexp_replace(COALESCE(input, ''), '\s+', ' ', 'g')), '');
$$;

-- card_fee_master
UPDATE card_fee_master
SET
    charge_type    = fee_normalize_ws(charge_type),
    card_product   = fee_normalize_ws(card_product),
    card_network   = fee_normalize_ws(card_network),
    full_card_name = fee_normalize_ws(full_card_name),
    updated_at     = NOW()
WHERE
    charge_type    IS DISTINCT FROM fee_normalize_ws(charge_type)
    OR card_product   IS DISTINCT FROM fee_normalize_ws(card_product)
    OR card_network   IS DISTINCT FROM fee_normalize_ws(card_network)
    OR full_card_name IS DISTINCT FROM fee_normalize_ws(full_card_name);

-- skybanking_fee_master
UPDATE skybanking_fee_master
SET
    charge_type  = fee_normalize_ws(charge_type),
    product      = fee_normalize_ws(product),
    product_name = fee_normalize_ws(product_name),
    network      = fee_normalize_ws(network),
    updated_at   = NOW()
WHERE
    charge_type  IS DISTINCT FROM fee_normalize_ws(charge_type)
    OR product      IS DISTINCT FROM fee_normalize_ws(product)
    OR product_name IS DISTINCT FROM fee_normalize_ws(product_name)
    OR network      IS DISTINCT FROM fee_normalize_ws(network);

-- retail_asset_charge_master_v2
UPDATE retail_asset_charge_master_v2
SET
    charge_title       = fee_normalize_ws(charge_title),
    charge_description = fee_normalize_ws(charge_description),
    loan_product_name  = fee_normalize_ws(loan_product_name),
    updated_at         = NOW()
WHERE
    charge_title       IS DISTINCT FROM fee_normalize_ws(charge_title)
    OR charge_description IS DISTINCT FROM fee_normalize_ws(charge_description)
    OR loan_product_name  IS DISTINCT FROM fee_normalize_ws(loan_product_name);
