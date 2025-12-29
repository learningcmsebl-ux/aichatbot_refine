-- Location Service Database Schema
-- Normalized schema for branches, ATMs, CRMs, RTDMs, priority centers, and head office

-- Regions table
CREATE TABLE IF NOT EXISTS regions (
    region_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region_code VARCHAR(10) UNIQUE NOT NULL,
    region_name VARCHAR(100) NOT NULL,
    country_code VARCHAR(10) NOT NULL DEFAULT '50',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_regions_name ON regions(region_name);
CREATE INDEX idx_regions_code ON regions(region_code);

-- Cities table
CREATE TABLE IF NOT EXISTS cities (
    city_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_name VARCHAR(100) NOT NULL,
    region_id UUID NOT NULL REFERENCES regions(region_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cities_name ON cities(city_name);
CREATE INDEX idx_cities_region ON cities(region_id);
CREATE INDEX idx_city_region_composite ON cities(city_name, region_id);

-- Addresses table
CREATE TABLE IF NOT EXISTS addresses (
    address_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    street_address TEXT NOT NULL,
    zip_code VARCHAR(20),
    city_id UUID NOT NULL REFERENCES cities(city_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_addresses_city ON addresses(city_id);

-- Branches table
CREATE TABLE IF NOT EXISTS branches (
    branch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_code VARCHAR(20) UNIQUE NOT NULL,
    branch_name VARCHAR(200) NOT NULL,
    address_id UUID NOT NULL REFERENCES addresses(address_id) ON DELETE CASCADE,
    status VARCHAR(10) NOT NULL DEFAULT 'A',
    is_head_office BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_branches_code ON branches(branch_code);
CREATE INDEX idx_branches_name ON branches(branch_name);
CREATE INDEX idx_branches_address ON branches(address_id);
CREATE INDEX idx_branches_status ON branches(status);
CREATE INDEX idx_branches_head_office ON branches(is_head_office);

-- Machines table (ATM/CRM/RTDM)
CREATE TABLE IF NOT EXISTS machines (
    machine_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_type VARCHAR(10) NOT NULL,  -- ATM, CRM, RTDM
    machine_count INTEGER NOT NULL DEFAULT 1,
    address_id UUID NOT NULL REFERENCES addresses(address_id) ON DELETE CASCADE,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_machines_type ON machines(machine_type);
CREATE INDEX idx_machines_address ON machines(address_id);
CREATE INDEX idx_machines_branch ON machines(branch_id);

-- Priority centers table
CREATE TABLE IF NOT EXISTS priority_centers (
    priority_center_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id UUID UNIQUE NOT NULL REFERENCES cities(city_id) ON DELETE CASCADE,
    center_name VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_priority_centers_city ON priority_centers(city_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to auto-update updated_at
CREATE TRIGGER update_regions_updated_at BEFORE UPDATE ON regions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cities_updated_at BEFORE UPDATE ON cities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_addresses_updated_at BEFORE UPDATE ON addresses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_branches_updated_at BEFORE UPDATE ON branches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_machines_updated_at BEFORE UPDATE ON machines
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_priority_centers_updated_at BEFORE UPDATE ON priority_centers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

