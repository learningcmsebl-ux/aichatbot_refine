-- Fee data cleanup (stage 8): post-cleanup indexes for lookup performance
-- Safe to re-run (IF NOT EXISTS).

CREATE INDEX IF NOT EXISTS idx_card_fee_active_lookup
    ON card_fee_master (status, product_line, charge_type, card_product, card_network)
    WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS idx_skybanking_active_lookup
    ON skybanking_fee_master (status, charge_type, product, product_name)
    WHERE status = 'ACTIVE';

-- retail already has ix_retail_v2_lookup; add answer_text coverage index for admin QA
CREATE INDEX IF NOT EXISTS idx_retail_v2_answer_missing
    ON retail_asset_charge_master_v2 (parse_status)
    WHERE answer_text IS NULL OR btrim(answer_text) = '';
