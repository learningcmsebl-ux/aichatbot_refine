# Lead Generation Module

Employee lead capture via chatbot, sales management via Lead Portal, and REST APIs with DB-backed RBAC.

## Components

| Component | URL / path | Purpose |
|-----------|------------|---------|
| Chatbot API | `http://localhost:8001` | Lead capture + status intents in chat |
| Lead Portal | `http://localhost:3002` | Sales dashboard, assignment, export |
| PostgreSQL | `chatbot_db` | `lead_master`, audit tables, `lead_user_roles` |
| Redis | optional | Chat lead-capture session state |

## Setup

### 1. Database migrations

```powershell
docker exec -i chatbot_postgres psql -U chatbot_user -d chatbot_db < bank_chatbot/migrations/add_lead_generation.sql
docker exec -i chatbot_postgres psql -U chatbot_user -d chatbot_db < bank_chatbot/migrations/drop_legacy_leads.sql
```

### 2. Environment

In `bank_chatbot/.env`:

```
ENABLE_LEAD_GENERATION=True
AUTH_ENABLED=True
```

Restart API: `docker compose -f bank_chatbot/docker-compose.yml up -d chatbot`

### 3. Seed roles

```sql
INSERT INTO lead_user_roles (employee_id, role, created_by)
VALUES ('2872', 'admin', 'system')
ON CONFLICT ON CONSTRAINT uq_lead_user_roles_employee_role DO NOTHING;

-- Sales manager example
INSERT INTO lead_user_roles (employee_id, role, created_by)
VALUES ('3001', 'sales_manager', 'system')
ON CONFLICT DO NOTHING;

-- Sales user example
INSERT INTO lead_user_roles (employee_id, role, created_by)
VALUES ('3002', 'sales_user', 'system')
ON CONFLICT DO NOTHING;
```

Roles: `employee` (implicit default), `sales_user`, `sales_manager`, `admin`.

### 4. Start Lead Portal

```powershell
cd bank_chatbot
docker compose up -d lead-portal
```

Or dev: `cd lead_portal && npm run dev` (port 3002).

## RBAC matrix

| Capability | Employee | Sales User | Sales Manager | Admin |
|------------|----------|------------|---------------|-------|
| Create lead (API/chat) | Yes | Yes | Yes | Yes |
| View own submitted | Yes | Yes | Yes | Yes |
| View assigned leads | — | Yes | Yes | Yes |
| View all leads | — | — | Yes | Yes |
| Update status | — | Assigned only | Yes | Yes |
| Assign / reassign | — | — | Yes | Yes |
| Add feedback | — | Assigned | Yes | Yes |
| Export CSV | — | — | Yes | Yes |
| Manage roles | — | — | — | Yes |
| Soft delete | — | — | — | Yes |

Authorization is enforced on **every** API call. Portal UI hides actions by role but is not trusted for security.

## Chatbot usage

**Create** (logged-in employee):

- `create a lead for credit card`
- `submit customer lead for personal loan`

Guided flow: customer details → confirmation → `Lead submitted successfully. Your Lead ID is LD-000123.`

**Status**:

- `show my submitted leads`
- `status of lead LD-000123`
- `show feedback for my leads`

**Commands during capture**: `cancel`, `start again`, `yes` to confirm.

Normal fee/product questions (e.g. “credit card annual fee”) are **not** routed to lead capture.

## REST API (`/api/leads`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create lead |
| GET | `/me/roles` | Current user roles + permissions |
| GET | `/stats` | Dashboard aggregates |
| GET | `/my-submitted` | Referrer’s leads |
| GET | `/assigned` | Sales queue |
| GET | `/search?q=` | Search |
| GET | `/` | Filtered list |
| GET | `/export.csv` | CSV export (manager/admin) |
| GET | `/{ref}` | Detail + per-lead permissions |
| PATCH | `/{ref}/status` | Status update |
| PATCH | `/{ref}/assign` | Assignment |
| POST | `/{ref}/feedback` | Feedback to referrer |
| GET | `/{ref}/status-history` | Audit trail |
| POST | `/{ref}/activity` | Activity log |
| GET/POST/DELETE | `/roles` | Admin role management (DELETE: `?employee_id=&role=`) |
| DELETE | `/{ref}` | Soft delete (admin) |

All endpoints require JWT when `AUTH_ENABLED=True`.

## Security notes

- Customer mobile/email stored in PostgreSQL only — **not** in browser localStorage (JWT/user profile only).
- Chat status responses mask PII for non-sales viewers.
- Application logs use lead reference + employee ID only (no raw mobile/email in log lines).
- Lead capture state in Redis expires after 1 hour.

## Tests

```powershell
cd bank_chatbot
python test_lead_service.py
python test_lead_api.py
```

## Smoke checklist

### Chatbot

- [ ] Login as employee
- [ ] `create a lead for credit card` → guided flow → receives LD- ID
- [ ] `show my submitted leads` lists the lead
- [ ] `what is credit card annual fee` → Fee Engine / RAG (not lead flow)

### Lead Portal

- [ ] Login at http://localhost:3002
- [ ] Dashboard shows stats
- [ ] My Submitted / All Leads / Assigned (role-dependent)
- [ ] Lead detail: status update, assign, feedback (role-dependent)
- [ ] Export CSV (manager/admin only)

### API

- [ ] `GET /api/leads/me/roles` returns roles for logged-in user
- [ ] Employee cannot export (403)
- [ ] Admin can assign and export

## File map

```
bank_chatbot/
  migrations/add_lead_generation.sql
  app/models/lead.py          # SQLAlchemy ORM
  app/models/leads.py         # Pydantic DTOs
  app/services/lead_service.py
  app/services/handlers/lead_capture_handler.py
  app/api/lead_routes.py
  test_lead_service.py
lead_portal/                  # React app port 3002
```
