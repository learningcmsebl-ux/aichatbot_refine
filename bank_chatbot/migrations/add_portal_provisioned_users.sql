-- Portal sales agents provisioned via Lead Portal admin (AD + local audit)
-- Run once: docker exec -i chatbot_postgres psql -U chatbot_user -d chatbot_db < bank_chatbot/migrations/add_portal_provisioned_users.sql

CREATE TABLE IF NOT EXISTS portal_provisioned_users (
    id                  BIGSERIAL PRIMARY KEY,
    username            VARCHAR(255) NOT NULL UNIQUE,
    employee_id         VARCHAR(255),
    full_name           VARCHAR(255),
    email               VARCHAR(255),
    ad_dn               VARCHAR(512),
    lead_role           VARCHAR(50)  NOT NULL DEFAULT 'sales_user',
    must_change_password BOOLEAN     NOT NULL DEFAULT TRUE,
    provisioned_by      VARCHAR(255) NOT NULL,
    provisioned_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    disabled_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_portal_provisioned_users_employee
    ON portal_provisioned_users (employee_id);

CREATE INDEX IF NOT EXISTS idx_portal_provisioned_users_provisioned_at
    ON portal_provisioned_users (provisioned_at DESC);
