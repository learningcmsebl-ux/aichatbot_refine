-- Fee data cleanup (stage 1): controlled vocabulary + business-review queue
-- Safe to re-run (IF NOT EXISTS / ON CONFLICT DO NOTHING).

-- Canonical alias registry (documents raw → canonical mappings; optional lookup for admin tooling)
CREATE TABLE IF NOT EXISTS fee_field_aliases (
    alias_id        SERIAL PRIMARY KEY,
    table_name      VARCHAR(50)  NOT NULL,
    field_name      VARCHAR(50)  NOT NULL,
    raw_value       VARCHAR(255) NOT NULL,
    canonical_value VARCHAR(255) NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_fee_field_aliases UNIQUE (table_name, field_name, raw_value)
);

-- Rows that need human/business sign-off before numeric changes
CREATE TABLE IF NOT EXISTS fee_data_review_queue (
    review_id   SERIAL PRIMARY KEY,
    table_name  VARCHAR(50)  NOT NULL,
    row_id      UUID         NOT NULL,
    issue_code  VARCHAR(50)  NOT NULL,
    severity    VARCHAR(10)  NOT NULL DEFAULT 'HIGH',
    summary     TEXT         NOT NULL,
    status      VARCHAR(20)  NOT NULL DEFAULT 'OPEN',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    CONSTRAINT uq_fee_data_review_queue UNIQUE (table_name, row_id, issue_code)
);

INSERT INTO fee_field_aliases (table_name, field_name, raw_value, canonical_value, notes) VALUES
    ('card_fee_master', 'charge_type', 'All Card Related Payment',       'ALL_CARD_RELATED_PAYMENT', 'Duplicate free-text row'),
    ('card_fee_master', 'charge_type', 'All_Card_Related_Payment',       'ALL_CARD_RELATED_PAYMENT', 'Snake-case duplicate'),
    ('card_fee_master', 'charge_type', ' Partial payment fee',           'PARTIAL_PAYMENT_FEE',      'Misplaced retail row; deactivated in card table'),
    ('card_fee_master', 'charge_type', 'Government Fees for Skybanking',  'Government Payment',       'Belongs in skybanking_fee_master'),
    ('card_fee_master', 'charge_type', 'Priority_banking',                'FCY_ENDORSEMENT_FEE',      'Priority banking product line'),
    ('card_fee_master', 'card_product', 'Women  Platinum',              'Women Platinum',           'Collapse double space'),
    ('card_fee_master', 'card_network', 'payment rate',                 'ANY',                      'Not a card network'),
    ('card_fee_master', 'card_network', 'A Challan Fee',                'ANY',                      'Not a card network'),
    ('card_fee_master', 'card_network', 'All Card Related Payment',     'ANY',                      'Not a card network'),
    ('card_fee_master', 'card_network', 'Mortgage Loan Payment Protection', 'ANY',                  'Not a card network'),
    ('card_fee_master', 'card_network', 'Foreign Currency (FCY)  Endorsement', 'ANY',               'Not a card network'),
    ('skybanking_fee_master', 'network', 'Skybanking A challan fee',    '',                         'Polluted network field; canonical is empty/NULL')
ON CONFLICT (table_name, field_name, raw_value) DO NOTHING;

-- Flag INTEREST_RATE rows for business review (0.25 BDT / "BDT 0.25 per year" likely wrong unit)
INSERT INTO fee_data_review_queue (table_name, row_id, issue_code, severity, summary)
SELECT
    'card_fee_master',
    fee_id,
    'INTEREST_RATE_UNIT_SUSPECT',
    'HIGH',
    'INTEREST_RATE stored as fee_unit=BDT fee_value=0.25 with answer_text "BDT 0.25 per year". '
    || 'Confirm whether this should be a monthly/annual PERCENT rate (e.g. 2.5% or 25% p.a.) before changing.'
FROM card_fee_master
WHERE charge_type = 'INTEREST_RATE'
  AND fee_unit = 'BDT'
  AND fee_value = 0.25
ON CONFLICT (table_name, row_id, issue_code) DO NOTHING;
