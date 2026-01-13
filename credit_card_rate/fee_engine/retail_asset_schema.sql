-- Retail Asset Charges Database Schema
-- Normalized schema for retail loan and asset charges
-- Based on Retail Asset Schedule of Charges

-- Create ENUM types for retail assets
CREATE TYPE loan_product_enum AS ENUM (
    'FAST_CASH_OD',
    'FAST_LOAN_SECURED_EMI',
    'EDU_LOAN_SECURED',
    'EDU_LOAN_UNSECURED',
    'OTHER_EMI_LOANS',
    'EXECUTIVE_LOAN',
    'ASSURE_LOAN',
    'WOMENS_LOAN',
    'AUTO_LOAN',
    'TWO_WHEELER_LOAN',
    'HOME_LOAN',
    'HOME_CREDIT',
    'MORTGAGE_LOAN',
    'HOME_LOAN_PAYMENT_PROTECTION',
    'OTHER_CHARGES',
    'ANY'
);

CREATE TYPE charge_type_enum AS ENUM (
    'PROCESSING_FEE',
    'LIMIT_ENHANCEMENT_FEE',
    'LIMIT_REDUCTION_FEE',
    'LIMIT_CANCELLATION_FEE',
    'RENEWAL_FEE',
    'PARTIAL_PAYMENT_FEE',
    'EARLY_SETTLEMENT_FEE',
    'SECURITY_LIEN_CONFIRMATION',
    'QUOTATION_CHANGE_FEE',
    'NOTARIZATION_FEE',
    'NOC_FEE',
    'PENAL_INTEREST',
    'CIB_CHARGE',
    'CPV_CHARGE',
    'VETTING_VALUATION_CHARGE',
    'SECURITY_REPLACEMENT_FEE',
    'STAMP_CHARGE',
    'LOAN_OUTSTANDING_CERTIFICATE_FEE',
    'RESCHEDULE_RESTRUCTURE_FEE',
    'RESCHEDULE_RESTRUCTURE_EXIT_FEE',
    'OTHER'
);

CREATE TYPE fee_unit_enum AS ENUM ('BDT', 'USD', 'PERCENT', 'COUNT', 'TEXT', 'ACTUAL_COST');
CREATE TYPE fee_basis_enum AS ENUM ('PER_LOAN', 'PER_AMOUNT', 'PER_INSTALLMENT', 'PER_INSTANCE', 'ON_OUTSTANDING', 'ON_OVERDUE', 'PER_QUOTATION_CHANGE');
CREATE TYPE condition_type_enum AS ENUM ('NONE', 'WHICHEVER_HIGHER', 'TIERED', 'NOTE_BASED');
CREATE TYPE status_enum AS ENUM ('ACTIVE', 'INACTIVE');

-- Master table for retail asset charges
CREATE TABLE retail_asset_charge_master (
    charge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    effective_from DATE NOT NULL,
    effective_to DATE,
    
    -- Product identification
    loan_product loan_product_enum NOT NULL,
    loan_product_name VARCHAR(200) NOT NULL,  -- Original product name from Excel
    
    -- Charge identification
    charge_type charge_type_enum NOT NULL,
    charge_description VARCHAR(500) NOT NULL,  -- Original description from Excel
    
    -- Fee structure
    fee_value DECIMAL(15, 4),  -- Main fee value (percentage or fixed amount)
    fee_unit fee_unit_enum NOT NULL,
    fee_basis fee_basis_enum NOT NULL,
    
    -- Tiered fee structure (for "Up to X amount" scenarios)
    tier_1_threshold DECIMAL(15, 4),  -- e.g., 50,00,000 (50 lakh)
    tier_1_fee_value DECIMAL(15, 4),  -- e.g., 0.575%
    tier_1_fee_unit fee_unit_enum,
    tier_1_max_fee DECIMAL(15, 4),  -- e.g., 17,250
    
    tier_2_threshold DECIMAL(15, 4),  -- e.g., Above 50 lakh
    tier_2_fee_value DECIMAL(15, 4),  -- e.g., 0.345%
    tier_2_fee_unit fee_unit_enum,
    tier_2_max_fee DECIMAL(15, 4),  -- e.g., 23,000
    
    -- Min/Max constraints
    min_fee_value DECIMAL(15, 4),
    min_fee_unit fee_unit_enum,
    max_fee_value DECIMAL(15, 4),
    max_fee_unit fee_unit_enum,
    
    -- Conditions and special rules
    condition_type condition_type_enum NOT NULL DEFAULT 'NONE',
    condition_description TEXT,  -- e.g., "minimum 30% of outstanding must be paid", "after 6 months"
    
    -- Employee pricing
    employee_fee_value DECIMAL(15, 4),  -- Usually 0 for "Free"
    employee_fee_unit fee_unit_enum,
    employee_fee_description VARCHAR(200),  -- e.g., "Free", "50% discount"
    
    -- Category-based pricing (for Executive Loan, etc.)
    category_a_fee_value DECIMAL(15, 4),
    category_a_fee_unit fee_unit_enum,
    category_b_fee_value DECIMAL(15, 4),
    category_b_fee_unit fee_unit_enum,
    category_c_fee_value DECIMAL(15, 4),  -- Usually 0 for "Free"
    category_c_fee_unit fee_unit_enum,
    
    -- Additional information
    original_charge_text TEXT,  -- Store original text from Excel for reference
    note_reference VARCHAR(20),
    priority INTEGER NOT NULL DEFAULT 100,
    status status_enum NOT NULL DEFAULT 'ACTIVE',
    remarks TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_retail_charge_effective_dates ON retail_asset_charge_master(effective_from, effective_to);
CREATE INDEX idx_retail_charge_product ON retail_asset_charge_master(loan_product);
CREATE INDEX idx_retail_charge_type ON retail_asset_charge_master(charge_type);
CREATE INDEX idx_retail_charge_status ON retail_asset_charge_master(status);
CREATE INDEX idx_retail_charge_lookup ON retail_asset_charge_master(loan_product, charge_type, status, effective_from, effective_to);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_retail_asset_charge_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
CREATE TRIGGER update_retail_asset_charge_master_updated_at
    BEFORE UPDATE ON retail_asset_charge_master
    FOR EACH ROW
    EXECUTE FUNCTION update_retail_asset_charge_updated_at();

-- Comments for documentation
COMMENT ON TABLE retail_asset_charge_master IS 'Master table for all retail asset/loan charges - single source of truth';
COMMENT ON COLUMN retail_asset_charge_master.charge_id IS 'Primary key UUID';
COMMENT ON COLUMN retail_asset_charge_master.loan_product IS 'Normalized loan product type';
COMMENT ON COLUMN retail_asset_charge_master.loan_product_name IS 'Original product name from source document';
COMMENT ON COLUMN retail_asset_charge_master.charge_type IS 'Type of charge (processing fee, partial payment, etc.)';
COMMENT ON COLUMN retail_asset_charge_master.charge_description IS 'Original charge description from source document';
COMMENT ON COLUMN retail_asset_charge_master.tier_1_threshold IS 'First tier threshold (e.g., 50 lakh)';
COMMENT ON COLUMN retail_asset_charge_master.tier_2_threshold IS 'Second tier threshold (e.g., above 50 lakh)';
COMMENT ON COLUMN retail_asset_charge_master.original_charge_text IS 'Original charge amount text from Excel for reference';









