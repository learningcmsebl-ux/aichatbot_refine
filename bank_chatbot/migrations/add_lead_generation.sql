-- Migration: Lead Generation module (lead_master + audit/role tables)
-- Run once. Safe to re-run (uses IF NOT EXISTS).

-- Sequence for human-readable Lead IDs (LD-000123)
CREATE SEQUENCE IF NOT EXISTS lead_reference_seq START 1;

-- ---------------------------------------------------------------------------
-- Role assignments (Employee, Sales User, Sales Manager, Admin)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_user_roles (
    id              BIGSERIAL PRIMARY KEY,
    employee_id     VARCHAR(255) NOT NULL,
    role            VARCHAR(50)  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(255),
    CONSTRAINT uq_lead_user_roles_employee_role UNIQUE (employee_id, role)
);

CREATE INDEX IF NOT EXISTS idx_lead_user_roles_employee
    ON lead_user_roles (employee_id);

CREATE INDEX IF NOT EXISTS idx_lead_user_roles_role
    ON lead_user_roles (role);

-- ---------------------------------------------------------------------------
-- Lead master
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_master (
    id                      BIGSERIAL PRIMARY KEY,
    lead_reference_no       VARCHAR(20)  NOT NULL UNIQUE,

    -- Customer (PII — backend only)
    customer_name           VARCHAR(255) NOT NULL,
    customer_mobile         VARCHAR(50),
    customer_email          VARCHAR(255),
    preferred_contact_time  VARCHAR(100),
    customer_location       VARCHAR(255),
    preferred_branch        VARCHAR(255),
    product_type            VARCHAR(50)  NOT NULL,
    remarks                 TEXT,
    status                  VARCHAR(50)  NOT NULL DEFAULT 'submitted',

    assigned_to_user_id     VARCHAR(255),

    -- Referrer / employee who submitted the lead
    created_by_employee_id  VARCHAR(255) NOT NULL,
    created_by_name         VARCHAR(255),
    created_by_department   VARCHAR(255),
    created_by_branch       VARCHAR(255),
    created_by_mobile       VARCHAR(50),
    created_by_email        VARCHAR(255),

    chat_session_id         UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,

    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    closed_at               TIMESTAMPTZ,
    deleted_at              TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_lead_master_reference
    ON lead_master (lead_reference_no);

CREATE INDEX IF NOT EXISTS idx_lead_master_created_by
    ON lead_master (created_by_employee_id, deleted_at, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_lead_master_assigned
    ON lead_master (assigned_to_user_id, status, deleted_at);

CREATE INDEX IF NOT EXISTS idx_lead_master_status
    ON lead_master (status, deleted_at, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_lead_master_product
    ON lead_master (product_type, deleted_at);

CREATE INDEX IF NOT EXISTS idx_lead_master_branch
    ON lead_master (preferred_branch, deleted_at);

CREATE INDEX IF NOT EXISTS idx_lead_master_created_at
    ON lead_master (created_at DESC);

-- ---------------------------------------------------------------------------
-- Status history
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_status_history (
    id          BIGSERIAL PRIMARY KEY,
    lead_id     BIGINT       NOT NULL REFERENCES lead_master(id) ON DELETE CASCADE,
    old_status  VARCHAR(50),
    new_status  VARCHAR(50)  NOT NULL,
    changed_by  VARCHAR(255) NOT NULL,
    changed_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    note        TEXT
);

CREATE INDEX IF NOT EXISTS idx_lead_status_history_lead
    ON lead_status_history (lead_id, changed_at DESC);

-- ---------------------------------------------------------------------------
-- Feedback to referring employee
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_feedback (
    id                      BIGSERIAL PRIMARY KEY,
    lead_id                 BIGINT       NOT NULL REFERENCES lead_master(id) ON DELETE CASCADE,
    feedback_text           TEXT         NOT NULL,
    feedback_by             VARCHAR(255) NOT NULL,
    feedback_to_employee_id VARCHAR(255) NOT NULL,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lead_feedback_lead
    ON lead_feedback (lead_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_lead_feedback_to_employee
    ON lead_feedback (feedback_to_employee_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Activity / communication log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_activity_log (
    id                BIGSERIAL PRIMARY KEY,
    lead_id           BIGINT       NOT NULL REFERENCES lead_master(id) ON DELETE CASCADE,
    activity_type     VARCHAR(100) NOT NULL,
    activity_details  TEXT,
    performed_by      VARCHAR(255) NOT NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lead_activity_lead
    ON lead_activity_log (lead_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Assignment history
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_assignment_history (
    id               BIGSERIAL PRIMARY KEY,
    lead_id          BIGINT       NOT NULL REFERENCES lead_master(id) ON DELETE CASCADE,
    old_assigned_to  VARCHAR(255),
    new_assigned_to  VARCHAR(255),
    assigned_by      VARCHAR(255) NOT NULL,
    assigned_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    note             TEXT
);

CREATE INDEX IF NOT EXISTS idx_lead_assignment_lead
    ON lead_assignment_history (lead_id, assigned_at DESC);
