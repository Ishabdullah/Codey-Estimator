# RESTORICON ESTIMATING SYSTEM
## ARCHITECTURE & IMPLEMENTATION PLAN

**Status:** PLAN ONLY. Nothing in this document is built. No production code in
Codey-OS, Codey-Aigentik, or Restoricon has been changed.
**Written:** 2026-09-27
**Audit basis:** shallow clones of `main` read on 2026-09-27:
- `Ishabdullah/Codey-OS` @ `91ee3c1` ("Close D3: sales portal 12s auto-refresh…", 2026-09-16)
- `Ishabdullah/Restoricon` @ `73eee40`
- `Ishabdullah/Codey-Aigentik` (main)
- `Ishabdullah/Codey-Estimator` (empty repo, this plan is its first content)

Every "EXISTING" claim below cites a file and line. Anything I could not verify
from the repositories (e.g. how many estimate rows exist in the live phone DB)
is marked **UNVERIFIED** and appears in §31 or in the verification commands in
§21.

Legend used on every recommendation:

| Tag | Meaning |
|---|---|
| **EXISTING** | Restoricon already has it (cited) |
| **NEW** | Must be created |
| **MODIFY** | Existing thing to extend |
| **REPLACE** | Existing thing to eventually replace |
| **MIGRATE** | Existing data to move/transform |
| **PRESERVE** | Must remain untouched |

---

## 1. Executive Summary

**The single most important finding:** the Restoricon *website* repository is
not where the business system lives. It's a static GitHub Pages marketing site
(`Restoricon/CNAME` = `restoricon.com`, `Restoricon/QWEN.md` §2 "Single-page
site… no backend"). The **real system of record** is
**`Codey-OS/restoricon_core/`**. That's a Python-stdlib HTTP API
(`http.server.ThreadingHTTPServer`) over one SQLite database
(`~/.codeyOS/restoricon.db`), running on the S24 Ultra under Termux. It's exposed
through a Cloudflare Tunnel and serves `quote.`, `portal.`, and `admin.restoricon.com`
by Host-header routing (`restoricon_core/api/routes.py:418-423`).

**The second most important finding:** the current "Quote Portal"
(`quote.restoricon.com`, `render_quote_surface()`, `api/web_surfaces.py:713`)
**does not estimate anything**. It's three things:
1. a public lead-intake form that POSTs to `/api/v1/public/leads`, which creates a
   Customer, a Lead (scored), and an Opportunity (`crm_service.py:4120`);
2. a "Structural Drying & Scope Estimator" that runs **entirely in the visitor's
   browser**, using hard-coded multipliers (`$4.20/$5.80/$8.50 per sq ft` × 0.85–1.35,
   `web_surfaces.py:1025-1045`). Nothing is stored;
3. a booking form that POSTs to `/api/v1/public/booking`.

There's also **no estimate-building UI anywhere** in the Core today. The
`estimates` table, `create_estimate`, `get_estimate`, and `list_estimates` exist
(`database.py:205`, `crm_service.py:2305-2428`). But there's no update method, no
status transitions, no numbering generator, no creator field, no staff surface, and
no customer accept/decline flow.

**So "replace the Quote Portal" really means two things:**
- **KEEP** public intake (it works, and it feeds the CRM correctly).
- **BUILD** the estimating system *behind* it, inside `restoricon_core`, as new
  services, API routes, and surfaces. That's exactly how the rest of the Core is
  built, and it matches the Codey-OS rule "the portal should expose capabilities
  from Codey-OS, not create a second disconnected business brain"
  (`Codey-OS/sales_rep_portal.md` §0).

**Recommended shape (needs approval, §31 D1):**
- **Codey-Estimator (this repo)** = a pure-Python, stdlib-only, framework-free
  **domain library** (`codey_estimator`). It holds the calculation engine, money
  and unit math, the product normalizer and matcher, the retailer-adapter interface
  and adapters, the refresh policy, and the storage *interfaces*. It's reusable by the
  Core, CCOS/Codey-OS agents, CLI tools, and future mobile clients.
- **Codey-OS `restoricon_core`** = the integration: schema migrations into the
  *one* Core DB, `EstimateService` / `PricingService`, `/api/v1/...` routes, the
  staff estimator surface, the admin tab, customer delivery, RBAC, and audit. This is
  delivered as PRs to Codey-OS that follow its own pipeline and rules.
- **No new database, no new server, no parallel customer/job records.**

This isn't the phase order from the original brief. I recommend building the
**calculation engine and manual/CSV-priced estimating first**, and the
Home Depot/Lowe's adapters **after** that. The estimator is useful on day one with
manually entered prices. The retailer-data decision, though, carries legal and cost
questions (§9, §10, §30) that shouldn't block the core workflow.

---

## 2. Current System Architecture

### 2.1 Three repositories, one system

```
                    ┌────────────────────────── GitHub Pages ─────────────────────────┐
Visitor ───────────►│ restoricon.com  (Restoricon repo: static HTML/CSS/JS, SW cache)  │
                    │  • links to quote./portal./admin.restoricon.com                  │
                    │  • pre-claim/contact forms use mailto: (script.js)               │
                    └──────────────────────────────────────────────────────────────────┘
                    ┌────────────── Cloudflare Tunnel (per CODEY_MASTER_PLAN §6.6) ─────┐
quote./portal./ ───►│ S24 Ultra / Termux                                                │
admin.restoricon.com│  Codey-OS/restoricon_core  (Python stdlib HTTP, port 8770)        │
                    │   ├─ api/server.py      ThreadingHTTPServer                        │
                    │   ├─ api/routes.py      APIRouter (hand-rolled path matching)      │
                    │   ├─ api/web_surfaces.py server-rendered HTML + vanilla fetch()    │
                    │   ├─ auth.py            users/roles/permissions/tokens             │
                    │   ├─ services/*.py      CRM, Finance, Ops, Scheduling, Audit, …    │
                    │   └─ SQLite  ~/.codeyOS/restoricon.db (WAL, FKs on)                │
                    │  Codey-Aigentik (Node 18+, 127.0.0.1:8081) email/SMS/calendar limb │
                    │  CCOS (Codey-OS/ccos) agent OS shell, plugin manifests             │
                    └───────────────────────────────────────────────────────────────────┘
```

### 2.2 Frontend (EXISTING)

| Item | Finding | Evidence |
|---|---|---|
| Framework | None. Server-rendered HTML strings returned by Python functions, with vanilla JS `fetch()` against `/api/v1/*`. No build step, no client store ("refetch on load and after every action"). | `web_surfaces.py`; `sales_rep_portal.md` §0 citing master plan §6.9 decision 8 |
| Routing | Host-based (`quote.`/`portal.`/`admin.`) plus exact-path matching: `/quote`, `/admin`, `/admin/login`, `/pm`, `/sales`, `/tech`, `/subcontractor`, `/portal`, `/portal/login`, `/` | `routes.py:418-459` |
| Auth UI | `render_login_surface("admin"|"customer")`, with role-based redirect after login | `web_surfaces.py:467` |
| Staff UI | `render_admin_surface()` (~3,400 lines, "11 complete domains"), plus a shared `_render_staff_portal_base()` for PM/Sales/Tech/Sub | `web_surfaces.py:1672, 5058` |
| Customer UI | `render_portal_surface()`: projects, milestones, contracts + signature, invoices, documents, messages | `web_surfaces.py:1164` |
| Design tokens | `--navy #0A192F`, `--charcoal #1E293B`, `--bronze #D4AF37`, `--offwhite #F8FAFC`, shared by the website and the portals | `_get_common_styles()` `web_surfaces.py:118`; `Restoricon/style.css` |
| Mobile | Drawer nav plus single-column layouts; B8.13 "mobile-first pass" is still open | `sales_rep_portal.md` B8.13 |
| Doc generation | **None.** No PDF library in `requirements.txt`. | `Codey-OS/requirements.txt` |
| File upload | Multipart upload into the `documents` store (B6.5), backed up by B7.2 | `routes.py:1152-1340` |
| Live refresh | 12-second polling on the sales portal (D3 resolution) | `sales_rep_portal.md` §4a item 3 |

### 2.3 Backend (EXISTING)

| Item | Finding | Evidence |
|---|---|---|
| Framework | Python stdlib `http.server`; no Flask/FastAPI | `api/server.py` |
| API style | JSON REST under `/api/v1`. Mutations use `POST …/{id}/update`, `…/transition`, and `…/claim` suffixes rather than PATCH/PUT | `routes.py:793-1110` |
| AuthN | `POST /api/v1/auth/login` → opaque `secrets.token_urlsafe(32)` stored in `api_tokens` with expiry/revocation; passwords are PBKDF2-SHA256 | `auth.py:736-900` |
| AuthZ | Role → permission-set matrix plus per-user `custom_permissions_json`, enforced **in the service layer** via `actor.has_permission()` | `auth.py:218-509`, `server.py` comment |
| Rate limiting | In-memory sliding window, 20 requests per 60 s per IP, applied to `/api/v1/public/*` only | `api/rate_limiter.py:16`, `routes.py:465-474` |
| Audit | `audit_log` table plus `AuditService.log()` and `build_audit_details()` (field-level old/new diff envelope, B6.2 standard) | `database.py:552`, `audit_service.py:167-354` |
| Notifications | `NotificationService` POSTs to Aigentik at `127.0.0.1:8081` (`/send-email`, `/send-invite`, `/send-cancellation`) | `notification_service.py` |
| Background jobs | No job queue. Automation runs through `AutomationService` rules; the B7 backup journal/snapshot runs on an interval | `automation_service.py`, master plan §6.10 |
| Integrations | Aigentik (email/SMS/calendar), GCS backup (`google-cloud-storage==2.11.0`), device bridge (B5b) | `requirements.txt`, master plan §6.7 |
| Tests | pytest; 41 files in `tests/test_restoricon_core/` (e.g. `test_api.py` 2,823 lines) | `tests/` |
| Governance | `CLAUDE.md` rules 1–12: architect → implementer → code-reviewer pipeline; rule 4 = schema/RBAC/auth/lifecycle changes need code-reviewer approval; rule 8 = log out-of-scope findings to `NEW_ISSUES.md`; rule 11 = keep `install.sh` current | `Codey-OS/CLAUDE.md` |

### 2.4 Codey-Aigentik (EXISTING)
Node.js ES-module app: IMAP/SMTP via `imapflow`/`nodemailer`, SMS rules, calendar,
customer-intake state machine (`customer-module.js`, including `ESTIMATE_PENDING` /
`ESTIMATE_COMPLETED` states), and a local HTTP server exposing `/send-email`,
`/send-invite`, `/send-cancellation` (`http-server.js:10-59`). Its LLM prompt
already forbids inventing prices (`customer-module.js:884`). **PRESERVE.** The
estimator only *calls* it to send email, which matches the B6.9 boundary.

### 2.5 Restoricon website (EXISTING)
Static pages (`index.html`, service pages, `home-care.html` with HomeCare
Basic/Plus/Complete/Estate tiers), `_partials` header/footer injected by
`build.sh`, a service worker (`sw.js`, cache `restoricon-v10`), and links to the
three Core subdomains in every header/drawer/footer. **PRESERVE.** No estimator
code belongs here. At most, nav-label text changes later (§21).

---

## 3. Current Quote Portal Analysis

| Aspect | Current behavior (EXISTING) | Evidence |
|---|---|---|
| Where it lives | `Codey-OS/restoricon_core/api/web_surfaces.py:713-1162` (`render_quote_surface`) | |
| Frontend routes | `quote.restoricon.com/`, `/quote`, and **also `/`** on the Core host | `routes.py:418, 426, 458` |
| Backend routes | `POST /api/v1/public/leads`, `POST /api/v1/public/booking` (unauthenticated, rate-limited) | `routes.py:476-490` |
| Tables written | `customers` (dedup by email, then phone), `leads` (scored), `opportunities` (stage `NEW_LEAD`), `appointments` (booking) | `crm_service.py:4120-4200+` |
| Quote creation | **None.** No `estimates` row is ever created. | |
| "Estimator" | Client-side JS only: sq ft × category multiplier → price range; air movers `ceil(sqft/120)`, dehumidifiers `ceil(volume/3000)`. Never stored, never tied to a price book. | `web_surfaces.py:1025-1045` |
| Customer association | Yes, via dedup/upsert into `customers` | |
| Employee association | None at intake. Leads start unassigned, and reps claim them (NEW-534 claim workflow) | `sales_rep_portal.md` §4a |
| Notifications / emails | Booking confirmation via Aigentik; the lead alert says "Dispatch notified" | `web_surfaces.py:1076` |
| PDFs | None | |
| Approval/acceptance | None | |
| Admin visibility | Leads and opportunities in the admin/sales surfaces | |
| Permissions | Public, with honeypot fields (`website_hp`/`honeypot`/`bot_check`) and a per-IP rate limit. Writes run as a synthetic `system_web_intake` actor with `ROLE_ADMIN` and `user_id=1` | `crm_service.py:4128-4146` |
| Dead markup | The quote surface HTML includes "Add Customer" and "Create Project" modals that have no public purpose | `web_surfaces.py:958-1027`; the same modal markup is repeated in other surfaces at lines 598, 1394, 2690 |

### KEEP / MODIFY / REPLACE / DEPRECATE

| Tag | Item |
|---|---|
| **KEEP / PRESERVE** | Public lead intake (`/api/v1/public/leads`) and booking (`/api/v1/public/booking`), customer dedup, lead scoring, opportunity creation. These are the correct *front door* of the Lead → Customer → Estimate chain. |
| **MODIFY** | The quote page's heading and copy, and a "Request an Estimate" confirmation that tells the customer an estimator will build their estimate. The admin/sales surfaces get an "Create estimate from this lead/opportunity" action. |
| **REPLACE** | The client-side drying calculator's hard-coded $/sq ft multipliers. Either (a) drive the ranges from price-book/labor-rate data on the server, or (b) remove public pricing entirely. That's a business decision (§31 D8), because published ranges set customer expectations. |
| **DEPRECATE (later, with approval)** | The unused "Add Customer" / "Create Project" modals inside the public quote page (dead code on a public surface). Log to `NEW_ISSUES.md`; don't delete during this project without approval. |
| **NEW (not replacing anything)** | A staff estimator surface, admin estimate management, and a secure customer estimate view with accept/decline. None of these exist today. |

---

## 4. Current Database / Data Model

SQLite, WAL, FKs enforced (`database.py` header). Schema is created with
`CREATE TABLE IF NOT EXISTS` plus an additive `_migrate_schema()`. The house
conventions for migrations (important for everything in §14):
- `ALTER TABLE ADD COLUMN` for new columns. These are **bare `INTEGER`, no FK**,
  because SQLite can't add an FK via ALTER. Validation happens in the service layer
  instead (precedent: `appointments.assigned_user_id`, `subcontractors.user_id`,
  `database.py:410-416, 374-381`).
- Widening a `CHECK` needs a **full table rebuild** (precedent:
  `_migrate_users_role_constraint`, `database.py:980-1400`). That's rule-4 work.
- Uniqueness on added columns goes through a separate unique index
  (`customers.external_id` note, `database.py:56-63`).
- Money is stored as `REAL` (floats) everywhere.

### Relevant EXISTING tables

| Entity | Table | Key facts for the estimator |
|---|---|---|
| Users/auth | `users` (`database.py:28`) | roles: admin, manager, sales, sales_manager, project_manager, technician, ai_agent, customer; `customer_id` links customer logins |
| Tokens | `api_tokens` | opaque, expiring, revocable |
| Employees | `employees` (`:765`) | `user_id UNIQUE` → users; `hourly_rate` (payroll rate, **not** a billing rate) |
| Customers | `customers` (`:64`) | `mailing_address`, `service_address` inline; `assigned_user_id` |
| Contacts | `contacts` (`:567`) | Aigentik-style contact records (not customer sub-contacts) |
| Properties | **does not exist** | B8.1 plans a `properties` table; not built (Appendix A shows only the B8.1 permission half done) |
| Leads | `leads` (`:89`) | `customer_id`, `assigned_user_id`, `estimated_value` |
| Opportunities | `opportunities` (`:115`) | `customer_id`, `project_id`, pipeline stage, insurance claim fields |
| Projects/Jobs | `projects` (`:170`) | `property_address` inline, `estimated_cost`, `contract_amount`, `actual_cost`, `profit` |
| **Estimates** | `estimates` (`:205`) | see §4.1 |
| Contracts | `contracts` (`:230`) | **`estimate_id` FK already exists**; `customer_signature_data`, `status` incl. `superseded`, `version` |
| Documents | `documents` (`:251`) | `document_type` includes `'estimate'`; `permissions_json`; FK customer/project only |
| Invoices | `invoices` (`:270`) | `payments_json`, `deposit_amount` |
| Work orders | `work_orders` (`:619`) | `line_items_json`, `total_cost`, lifecycle draft→verified |
| Vendors | `vendors` (`:805`) | `category` incl. `building_materials` |
| Purchase orders | `purchase_orders` (`:821`) | `vendor_id`, `project_id`, `items_json` |
| Job costing | `financial_transactions` (`:689`) + `FinanceService.get_project_pnl` (`finance_service.py:196`) | `material_cost`, `payroll`, `vendor_expense`… per project |
| Timesheets | `timesheets` (`:784`) | actual labor cost per project/work order |
| Audit | `audit_log` (`:552`) | actor_id/role/type, action, entity_type/id, summary, `details_json` |
| Comms | `communication_history` (`:300`) | append-only, per customer/project/opportunity |
| Business profile | `business_profile` (`:456`) | license/insurance info for proposal headers |

**Not existing:** products, retailer products, prices, price history, price book,
labor rates, estimate versions, estimate line items (as rows), customer share
tokens, acceptances, properties.

### 4.1 The existing `estimates` table in detail (EXISTING)

```sql
estimates(id, estimate_number TEXT UNIQUE NOT NULL, customer_id NOT NULL,
  project_id, line_items_json, subtotal, materials_cost, labor_cost,
  subcontractor_cost, markup_percent, tax_amount, discount_amount, total_amount,
  status CHECK IN ('draft','sent','approved','rejected','expired'),
  expiration_date, version INTEGER DEFAULT 1, notes, created_at, updated_at,
  FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
  FOREIGN KEY (project_id)  REFERENCES projects(id)  ON DELETE SET NULL)
```

Gaps relevant to this project:
1. **No creator or assignee.** Ownership can currently only be recovered from
   `audit_log` rows (`action='create'`, `entity_type='estimate'`, `actor_id`,
   `crm_service.py:2348-2355`).
2. **`ON DELETE CASCADE` on customer.** Deleting a customer would silently destroy
   their estimate history. No `delete_customer` code path exists today (grep:
   none), so this is **latent, not active**, but it contradicts the
   preserve-history requirement.
3. **Caller-supplied `estimate_number`**, with no generator (compare
   `WO-{YYYYMMDD}-{XXXX}` for work orders).
4. **No `update_estimate`, no status transitions, no versioning logic.** The
   `version` column exists but nothing uses it.
5. **Totals are client-supplied floats.** `create_estimate` stores whatever it
   receives (`routes.py:1069-1072`: `Estimate(**json_body)`). There's no
   server-side calculation.

---

## 5. Existing Authentication & Roles

**EXISTING** (`auth.py`):

| Role | Estimate permissions today |
|---|---|
| admin | `read:estimates`, `write:estimates` (+ everything) |
| manager | read + write |
| sales | read + write (`auth.py:358-359`) |
| sales_manager | = sales ∪ `read:team_sales_data` (`auth.py:509`) |
| project_manager | read (`:389`) |
| technician | none; `_row_to_estimate` also hides costs for technicians |
| ai_agent | read (`:444`) |
| customer | `read:own_estimates` (`:488`), scoped to `actor.customer_id` |

Ownership narrowing already exists for leads/opportunities/tasks via
`PERM_READ_TEAM_SALES_DATA` (NEW-533 fix). **It isn't applied to estimates**:
any `sales` user can read every estimate (`list_estimates` has no owner filter,
`crm_service.py:2400-2428`).

### Security findings from the audit (for Codey-OS `NEW_ISSUES.md`, rule 8, not fixed here)

| # | Finding | Severity | Evidence |
|---|---|---|---|
| F1 | **`line_items_json` is returned to customers unfiltered.** `_row_to_estimate` zeroes the header cost fields for customer/technician roles but passes `line_items` through verbatim. If any line item carries cost/markup keys (and the new engine's will), `GET /api/v1/portal/estimates` leaks them. | **Confirmed design flaw; exposure depends on data** | `crm_service.py:2360-2384`, `routes.py:1372-1376` |
| F2 | Customer FK `ON DELETE CASCADE` on `estimates` (see §4.1). | Latent | `database.py:225` |
| F3 | API accepts bearer tokens from the `?token=` query string. Query strings end up in logs, browser history, and Cloudflare logs. The new customer-link design must **not** reuse this mechanism. | Suspected risk | `routes.py:493-500` |
| F4 | Public intake acts as `ROLE_ADMIN` with `user_id=1`, so audit rows attribute website leads to the admin user id. | Low / attribution quality | `crm_service.py:4128-4133` |
| F5 | `estimates` list has no ownership narrowing for `sales`. | Medium (internal) | `crm_service.py:2400` |
| F6 | Docs disagree on the DB path: code uses `~/.codeyOS/restoricon.db` (`database.py:17-19`), while master plan B7 text says `~/.codey_restoricon/core.db`. | Doc hygiene | `CODEY_MASTER_PLAN.md` §6.10 |

---

## 6. Existing Customer/Job/Quote Relationships

**EXISTING** chain today:

```
Website intake ─► Customer ─► Lead ─► Opportunity ─(project_id)─► Project ─► WorkOrder
                     │                                   │              ├─► PurchaseOrder (vendor)
                     │                                   │              ├─► Timesheet / FinancialTransaction
                     ├─► Estimate (customer_id, project_id?)            └─► Invoice
                     └─► Contract (customer_id, project_id?, estimate_id?)
```

Missing links: Estimate→Opportunity, Estimate→Lead, Estimate→Property,
Estimate→creator/assignee, and Estimate acceptance→Contract/Project automation.
All of these are **MODIFY** (add columns) on `estimates`. None of them need new
customer or job entities.

---

## 7. Proposed Estimating Architecture

```
┌────────────────────── Codey-Estimator (this repo) : codey_estimator ──────────────────────┐
│  money.py       integer-cents Money, rounding (ROUND_HALF_UP), tax/markup/margin math      │
│  units.py       unit catalogue + package conversion (ft, LF, SF, SQ, EA, BX, GAL, …)       │
│  calc/          CalculationEngine (pure, deterministic, versioned: CALC_ENGINE_VERSION)    │
│  catalog/       normalizer (text→attributes), matcher (confidence scoring)                 │
│  retailers/     RetailerAdapter ABC, ManualAdapter, CsvImportAdapter,                      │
│                 HomeDepotAdapter, LowesAdapter (licensed-API backed, §9/§10)               │
│  refresh/       RefreshPolicy (intervals, priority), RateLimiter/TokenBucket               │
│  ports.py       Repository protocols (ProductRepo, PriceRepo, EstimateRepo …)              │
│  dto.py         InternalEstimateView vs CustomerEstimateView (allow-list serializers)      │
│  NO I/O except inside adapters · NO sqlite import in calc/ · stdlib only                   │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                    ▲ imported by (pinned git tag, added to requirements.txt + install.sh)
┌───────────────────────── Codey-OS restoricon_core (integration) ──────────────────────────┐
│  database.py      new tables + estimates migration (rule-4)                                │
│  repositories/    SQLite implementations of codey_estimator.ports                          │
│  services/estimate_service.py   create/edit/version/transition/send/accept/convert + RBAC  │
│  services/pricing_service.py    search/compare/refresh/price-book + RBAC                   │
│  services/pricing_worker.py     refresh queue consumer (one thread, PID-safe, rule-4)      │
│  api/routes.py    /api/v1/estimates/*, /api/v1/pricing/*, /api/v1/price-book/*,            │
│                   /api/v1/public/estimate/{token}/*                                        │
│  api/web_surfaces.py  /estimates (staff estimator), admin "Estimates" tab,                 │
│                   customer estimate page (/e/{token}) + portal Estimates panel             │
│  AuditService / NotificationService(Aigentik) / FinanceService / OperationsService reused  │
└───────────────────────────────────────────────────────────────────────────────────────────┘
          ▲ HTTP /api/v1 with ai_agent token          ▲ HTTP /api/v1 with staff/customer auth
   CCOS plugin "estimator" (§23)             Browsers: staff phone, admin desktop, customer
```

Design rules:
- **Pricing acquisition** (catalog/retailers/refresh) and **estimate calculation**
  (calc) are separate packages. The calc engine only ever sees *snapshotted*
  numbers. It never calls a retailer.
- **The backend is authoritative for every total.** The browser renders
  server-computed numbers. A "preview" endpoint (`POST /api/v1/estimates/preview`)
  runs the same engine without saving, so the mobile UI can show live totals
  without duplicating formulas in JavaScript.
- **Customer-visible data is produced only by an allow-list serializer**
  (`CustomerEstimateView`). Hiding internal fields never depends on zeroing them
  after the fact (the F1 lesson).

---

## 8. Proposed Pricing Engine

**Search flow (EXISTING: none. NEW: all):**

```
estimator types "1/2 red pex"
   │
   ▼  normalize query → {nominal_size: 1/2in, color: red, material: PEX, type: pipe}
   ▼  local search: FTS5 over canonical_materials + retailer_products (+ attribute filter)
   ├── hits → return immediately: product, retailer, package, current price, last_checked,
   │          "stale" badge if now > next_refresh_at (and enqueue a refresh job)
   └── no/insufficient hits AND a remote-capable adapter is enabled
          → check search_cache (same normalized query < N days old → reuse result ids)
          → else enqueue a "discover" job; UI shows "Searching retailers…" and polls
            (12-second polling precedent) OR, for an explicit "Search retailers now"
            tap, a bounded synchronous call (timeout ≤ 8 s) through the rate limiter
          → adapter results → normalize → upsert retailer_products
            + append price_observations → propose matches → return
```

**Core principles:**
- A price is an **observation**: `(retailer_product, store/zip, price, observed_at, source)`.
  Observations are append-only. The "current price" is the latest observation,
  denormalized onto `retailer_products.current_price_cents` in the **same
  transaction**.
- Estimates never reference "current price." Each line item copies
  `unit_cost_cents` **and** the `price_observation_id` it came from (§24).
- Retailer credentials live only in Core config/env (B7.3-encrypted backup) and are
  used only inside the adapter on the server. They're never sent to the browser.

---

## 9. Home Depot Integration Strategy

**Facts (verified by web search 2026-09-27, not from memory):**
- Home Depot doesn't offer a general public product/price API for this purpose.
- Licensed third-party data APIs exist, e.g. **SerpApi "Home Depot Product" and
  "Home Depot Search" engines** (title, brand, price, UPC, model, specs) and
  **Traject Data "BigBox API"** (search by UPC/SKU/term, pricing, fulfillment;
  advertised from about $15/month). Sources:
  [SerpApi HD Product](https://serpapi.com/home-depot-product),
  [SerpApi HD Search](https://serpapi.com/home-depot-search-api),
  [BigBox API](https://trajectdata.com/ecommerce/big-box-api/),
  [BigBox pricing](https://trajectdata.com/ecommerce/big-box-api/pricing/).

**Recommendation (decision D2):**

| Option | Termux | Legal/ToS | Cost | Recommendation |
|---|---|---|---|---|
| A. Licensed data API (BigBox or SerpApi) behind `HomeDepotAdapter` | ✅ plain HTTPS via `requests`/`urllib` | Provider carries the acquisition. Still read their terms on caching duration and redistribution | Paid, per request, so it needs a budget cap | **Recommended** |
| B. Direct scraping of homedepot.com | ⚠️ HTML parsing works, but headless browsers (Playwright/Chromium) are **not practical on Termux/Android** and HD pages are bot-protected | **High risk**: retailer terms generally prohibit automated access. Brief item 21 requires respecting terms | "Free" but brittle | **Not recommended** |
| C. Pro Xtra purchase-history / receipt CSV import (`CsvImportAdapter`) | ✅ | ✅ your own data | Free | **Recommended as a complement**: it gives *your actual paid prices*, which are better cost data than shelf price |
| D. Manual entry (`ManualAdapter`) | ✅ | ✅ | Free | **Always available, and built first** |

Store/location matters: HD prices vary by store. The adapter takes a configured
`store_id`/ZIP (Hartford County default) and records it on every observation.

---

## 10. Lowe's Integration Strategy

Same adapter contract. The web search didn't surface a Lowe's equivalent of
BigBox/SerpApi. The one result was an Apify *scraper* actor, which is scraping by
proxy and carries the same ToS concerns as option B. So **Lowe's is the weaker
case today**:
- Phase 1: `ManualAdapter` plus `CsvImportAdapter` (Lowe's Pro/MyLowe's purchase
  history export, **UNVERIFIED** that a usable export exists for your account;
  §31 D2).
- Phase 2: a licensed provider if one is confirmed. The `LowesAdapter` class is
  built only once a lawful source is chosen.
- The comparison table (§10 of the brief) still works: it shows whichever
  retailers have observations, with "no data" cells where Lowe's is missing.

---

## 11. Product Normalization Strategy

**NEW** `codey_estimator.catalog`:

1. **Tokenize and canonicalize** the text: fractions (`1/2`, `½`, `0.5`, `1/2-in`,
   `1/2 in.`) → `nominal_size=0.5in`; lengths (`50 ft`, `50-ft`, `50'`) →
   `length=50ft`; colors; materials (PEX-A/PEX-B → `material=PEX`,
   `subtype=PEX-B`); product type (`pipe`, `tubing`); package counts
   (`10-pack`, `box of 100`).
2. **Category-specific attribute schemas** (plumbing pipe, drywall sheet, lumber,
   fasteners, paint…). Each defines required attributes for a match, e.g. pipe:
   material, nominal_size, length, color (optional).
3. **Canonical material** = the set of required attributes (e.g. `PEX|0.5in|red|50ft|pipe`).
   It's a *definition*, not a product.
4. **Matcher** scores a retailer product against a canonical material:
   - required attributes equal → +weights; any required attribute conflicting → **score 0**;
   - UPC/model-number identity → 1.0 (same retailer or cross-listed);
   - brand differences don't block a match (SharkBite vs Apollo is fine) but are
     recorded as a difference; subtype differences (PEX-A vs PEX-B) cap confidence at 0.7.
5. **Thresholds:** ≥ 0.9 and no conflicts → `auto_confirmed`; 0.6–0.9 →
   `proposed` (shown as "possible equivalent", needs a human confirm); < 0.6 → no
   link. **Uncertain products stay separate** (brief §9).
6. Confirmations and rejections are stored (`material_matches.status`,
   `confirmed_by_user_id`) and audited. A rejected pair is never re-proposed.
7. Deterministic rules first. An LLM-assisted normalizer is optional later. It
   would go through the existing local model under Codey-OS rule 2 (RAM
   discipline) and **only ever proposes**, never auto-confirms.

---

## 12. Price Cache & Refresh Strategy

**NEW** fields on `retailer_products`: `last_checked_at`, `next_refresh_at`,
`refresh_interval_days`, `refresh_status` (`ok|pending|failed|disabled`),
`refresh_error`, `refresh_priority`, `consecutive_failures`.

**RefreshPolicy** (pure function in the library):

| Class | Default interval | Rule |
|---|---|---|
| Normal product | 180 days | default |
| Frequently used (in Price Book, used ≥ N times in 90 days) | 90 days | computed from `price_book_items.use_count` |
| Volatile commodity (lumber, sheet goods, copper) | 30 days (configurable per category) | **recommended addition**: 180 days is too long for lumber/copper |
| High-value (unit cost ≥ configurable threshold) | configurable | |
| Manual "Refresh Price" | immediate | enqueued at top priority; UI can wait up to 8 s, then falls back to polling |
| Used in an estimate being *sent* | optional pre-send check | warns if any line's observation is older than X days (it doesn't auto-change the price) |

**Queue:** a `pricing_jobs` table (not in memory, so it survives restarts). There
is one consumer: `pricing_worker` in the Core process, a single daemon thread
started and stopped with the API server. It has **no separate process**, which
avoids new PID-lifecycle risk (Codey-OS rules 3 and 4). It still needs code-reviewer
sign-off. Jobs are claimed with a conditional `UPDATE … WHERE status='queued'`
(the NEW-534 race-safe pattern).

**Rate limiting:** a token bucket per retailer (`retailers.rate_limit_per_min`),
a daily request budget cap per paid provider (to protect API spend), exponential
backoff on errors, and a circuit breaker after N consecutive failures
(`refresh_status='failed'`, surfaced in admin).

**Never scrape unnecessarily:** local-first search, a `search_cache` for remote
queries, refreshes only when `next_refresh_at` has passed or on a manual request,
and no bulk catalog crawling (brief §11).

---

## 13. Restoricon Price Book

**NEW** `price_book_items`, a curated layer over products:
`id, display_name, category, canonical_material_id?, preferred_retailer_product_id?,
preferred_vendor_id? (→ EXISTING vendors), default_unit, default_waste_pct,
default_markup_pct, default_labor_type?, default_labor_qty_per_unit?, is_favorite,
use_count, last_used_at, active, notes, created_by_user_id, created_at, updated_at`.

**NEW** `labor_rates`: `labor_type` (e.g. plumber, carpenter, helper, drywall
hang), `unit` (hour/SF/LF/EA), `cost_rate_cents` (what it costs Restoricon),
`bill_rate_cents` (what the customer pays), `active`, effective dating
(`effective_from`, `effective_to`) so historical estimates keep their rates.
**MODIFY-not:** `employees.hourly_rate` is payroll and stays separate. Job
costing later compares estimated labor cost against `timesheets.total_cost`.

Later: **assemblies/templates** ("Bathroom demo per SF" = materials + labor
bundle). The schema leaves room for it (`price_book_assemblies`) but it isn't in
the first build.

Discovery-driven: products enter the Product DB when searched or imported, and the
Price Book when an estimator adds or favorites them. There's no full-catalog
crawl.

---

## 14. Estimate Data Model

For each entity: why, reuse?, relationships, indexes, history, migration.
Money columns in new tables are **INTEGER cents** (decision D3). Legacy `REAL`
columns stay populated for backward compatibility.

### 14.1 `estimates` (the header): MODIFY (extend the EXISTING table, don't duplicate it)
- **Why:** it already exists, `contracts.estimate_id` points to it, and the portal
  reads it. A second header table would violate "one source of truth."
- **Add columns:** `created_by_user_id` (immutable, set by the service from the
  actor, never from the request body), `created_by_name` (snapshot at creation, so
  history survives role changes or departures), `assigned_to_user_id`,
  `opportunity_id`, `lead_id`, `property_id` (after B8.1), `title`,
  `current_version_id`, `accepted_version_id`, `accepted_at`,
  `converted_project_id`, `contract_id`, `source` (`engine|legacy|api`),
  `workflow_status` (see §14.7), `expires_at`, `customer_notes`, `terms`,
  `sent_at`, `last_viewed_at`.
- **Rebuild (rule-4) for two constraint changes:** (1) widen the status CHECK
  (or add the new `workflow_status` column and leave the legacy `status` CHECK
  alone, see the D5 option), and (2) change `customer_id` from `ON DELETE CASCADE`
  → `ON DELETE RESTRICT`. This follows the `_migrate_users_role_constraint`
  precedent exactly, under a single transaction, tested on a copy of the live DB.
- **Indexes:** `(created_by_user_id)`, `(assigned_to_user_id)`,
  `(workflow_status, updated_at)`, `(customer_id)` (exists), `(project_id)`,
  `(opportunity_id)`.
- **Numbering:** server-generated `EST-{YYYY}-{NNNN}` (sequence table, gap-tolerant).
  Legacy numbers are kept verbatim.

### 14.2 `estimate_versions`: NEW
- **Why:** you can't overwrite a sent estimate (brief §16). The header row is
  mutable metadata. Versions are the priced content.
- `id, estimate_id, version_number, is_locked, locked_at, locked_reason
  (sent|accepted|superseded), totals (all cents: material_cost, labor_cost,
  equipment_cost, sub_cost, cost_total, subtotal_sell, discount, taxable_base, tax,
  total, gross_profit, gross_margin_bp), calc_engine_version, tax_rate_bp,
  terms_snapshot, customer_notes_snapshot, change_summary, created_by_user_id,
  created_at` with UNIQUE(estimate_id, version_number).
- **Immutability:** the service refuses any write to a locked version or its lines.
  A DB trigger (`BEFORE UPDATE … WHEN OLD.is_locked=1 → RAISE(ABORT)`) adds
  defense in depth.

### 14.3 `estimate_line_items`: NEW (one table, typed columns)
- **Why one table instead of separate EstimateMaterial/EstimateLabor tables:** a
  line in construction estimating is often "material + install labor"
  (e.g. 4 × PEX 50 ft + 3 h plumber). Splitting it across tables forces joins and
  makes line totals ambiguous. One row per line with nullable component groups is
  simpler in SQLite and maps 1:1 to the calc engine's input. `line_type`
  (`material|labor|equipment|subcontractor|combined|allowance|fee`) drives validation.
- Columns: `id, estimate_version_id, sort_order, section, category, description
  (internal), customer_description, visible_to_customer (default 1)`;
  **material:** `price_book_item_id, retailer_product_id, price_observation_id,
  retailer_code_snapshot, product_title_snapshot, package_qty, package_unit,
  unit_cost_cents (snapshot), quantity, unit, waste_pct_bp, material_markup_bp`;
  **labor:** `labor_type, labor_rate_id, labor_qty, labor_unit,
  labor_cost_rate_cents, labor_bill_rate_cents`;
  **equipment:** `equipment_id? (→ EXISTING equipment), equipment_cost_cents,
  equipment_markup_bp`;
  **subcontractor:** `subcontractor_id? (→ EXISTING), sub_cost_cents, sub_markup_bp`;
  **adjustments:** `taxable, discount_cents, price_override_cents?,
  override_reason?`;
  **computed (written by the engine only):** `packages_needed, material_cost_cents,
  labor_cost_cents, cost_total_cents, sell_total_cents, tax_cents, line_total_cents`;
  `internal_note, created_at, updated_at`.
- Index `(estimate_version_id, sort_order)`.
- **History:** snapshot columns mean a line renders identically forever, even if the
  product, price book item, or labor rate changes or is deactivated.

### 14.4 `estimate_share_links`: NEW (§18)
`id, estimate_id, estimate_version_id, customer_id, token_hash (SHA-256, UNIQUE),
created_by_user_id, created_at, expires_at, revoked_at, revoked_by_user_id,
first_viewed_at, last_viewed_at, view_count, delivery_channel, delivered_to`.
The raw token is never stored.

### 14.5 `estimate_decisions`: NEW (append-only)
`id, estimate_version_id, share_link_id?, customer_user_id?, decision
(accepted|declined|changes_requested), signer_name, signature_data?,
consent_text_snapshot, comment, ip, user_agent, decided_at`.

### 14.6 Attachments: MODIFY EXISTING `documents`
Add bare `estimate_id INTEGER` plus `customer_visible INTEGER DEFAULT 0`. Reuse the
B6.5 upload path and the B7.2 backup. **No new attachment table.**

### 14.7 Status: use EXISTING `audit_log` plus the header column
No separate status-event table. Each transition writes an `audit_log` row
(`action='transition'`, details `{from,to,version}`), matching house style.

### 14.8 Pricing tables: all NEW
| Table | Key columns | Indexes / constraints |
|---|---|---|
| `retailers` | code (`homedepot`,`lowes`,`manual`,`csv:<vendor>`), name, adapter, enabled, rate_limit_per_min, daily_budget, vendor_id? (→ EXISTING vendors) | UNIQUE(code) |
| `retailer_stores` | retailer_id, store_code, name, zip | UNIQUE(retailer_id, store_code) |
| `retailer_products` | retailer_id, retailer_sku, upc, model_number, brand, title, description, category_path, attributes_json, package_qty, package_unit, url, image_url (only if the provider's terms permit), current_price_cents, current_observation_id, availability, refresh fields (§12), first_seen_at, active | UNIQUE(retailer_id, retailer_sku); idx(upc); idx(next_refresh_at, refresh_status) |
| `price_observations` | retailer_product_id, store_id, price_cents, was_price_cents, unit_price_cents, availability, observed_at, source (`adapter|manual|csv`), observed_by_user_id, raw_hash | append-only (trigger forbids UPDATE/DELETE); idx(retailer_product_id, observed_at DESC) |
| `canonical_materials` | name, category, attributes_json, attribute_key (normalized string), base_unit | UNIQUE(attribute_key) |
| `material_matches` | canonical_material_id, retailer_product_id, confidence, method, status, decided_by_user_id, decided_at | UNIQUE(canonical_material_id, retailer_product_id) |
| `product_search_fts` | FTS5 virtual table over title/brand/attributes/canonical names | FTS5 availability on Termux's Python sqlite **UNVERIFIED** (check command in §21). Fallback: `LIKE` plus the attribute index |
| `search_cache` | retailer_id, normalized_query, result_skus_json, fetched_at | UNIQUE(retailer_id, normalized_query) |
| `pricing_jobs` | kind (`refresh|discover`), retailer_product_id?, query?, priority, status, attempts, requested_by_user_id, scheduled_for, started_at, finished_at, error | idx(status, priority, scheduled_for) |
| `price_book_items`, `labor_rates` | §13 | |

### 14.9 `properties`: dependency on B8.1 (not owned by this project)
The estimator needs `property_id`. B8.1 already designed `properties`, so this
project **consumes** it rather than defining a competing one. Until B8.1 ships, the
estimate uses `customers.service_address` plus a free-text `site_address` snapshot
on the version (D7).

---

## 15. Estimate Calculation Engine

**NEW**, a pure library `codey_estimator.calc`. It's deterministic, integer-cents,
and versioned (`CALC_ENGINE_VERSION` is stored on every version, so an old
estimate can always be re-derived exactly).

Notation: percentages are stored in basis points (bp; 1% = 100 bp). All rounding
is `ROUND_HALF_UP` to the cent **per component**, then summed. That's the same
convention on screen, on the PDF, and in the DB.

**Per line**
```
qty_with_waste      = quantity × (1 + waste_pct)
packages_needed     = ceil(qty_with_waste / package_qty)          (package_qty ≥ 1; default 1)
material_cost       = packages_needed × unit_cost                 (unit_cost = snapshot price per package)
material_sell       = material_cost × (1 + material_markup)
labor_cost          = labor_qty × labor_cost_rate
labor_sell          = labor_qty × labor_bill_rate                 (if bill rate absent: labor_cost × (1+labor_markup))
equipment_sell      = equipment_cost × (1 + equipment_markup)
sub_sell            = sub_cost × (1 + sub_markup)
cost_total          = material_cost + labor_cost + equipment_cost + sub_cost
sell_before_disc    = price_override  OR  material_sell + labor_sell + equipment_sell + sub_sell
sell_total          = sell_before_disc − line_discount            (never < 0; validation error)
```
**Estimate**
```
subtotal_sell   = Σ sell_total
estimate_disc   = fixed OR percent of subtotal_sell               (allocated pro-rata to lines for tax base)
taxable_base    = Σ (sell_total − allocated_disc) over taxable lines   ← tax method per D6
tax             = round(taxable_base × tax_rate)
total           = subtotal_sell − estimate_disc + tax
cost_total      = Σ line cost_total
gross_profit    = (subtotal_sell − estimate_disc) − cost_total    (tax excluded: it's pass-through)
gross_margin    = gross_profit / (subtotal_sell − estimate_disc)  (0 if denominator 0)
markup_effective= gross_profit / cost_total
```
**Markup vs. margin** are stored and shown separately, always labeled. A 25%
markup is a 20% margin, and confusing the two is a classic estimating loss.

**Guards:** negative quantities are rejected. Margin below a configurable floor
(e.g. < 15%) produces a *warning* on send, not a block. A price override requires
`override_reason` and is audited. Tax rate comes from configuration, never the client.

**Interfaces:** `calculate(EstimateInput) -> EstimateResult` (pure), and
`to_customer_view(EstimateResult) -> CustomerEstimateView` (allow-list: line
customer_description, qty, unit, line customer price, subtotal, discount, tax,
total, terms). The **customer view never contains** cost, markup, waste,
retailer, SKU, observation ids, labor rates, internal notes, or margin.

**Formula sign-off:** these formulas are the proposal. Two things need your
confirmation before Phase 2 code (D6): the tax method, and whether labor is billed
by bill-rate or by markup.

---

## 16. Employee/Estimator Assignment

- **EXISTING identity:** `users` (login identity, role) and `employees` (HR record,
  `user_id UNIQUE`). The **user id** is the stable, always-present key for staff
  (every staff member who can log in has one). `employees` is optional per user.
- **NEW:** `estimates.created_by_user_id` is set **only** by the service from
  `AuthContext.user_id`. The API ignores any `created_by*` field in request bodies,
  and it's immutable after insert (the service never updates it; a trigger
  enforces it). `created_by_name` snapshots `users.full_name` at creation.
  `employees` is looked up for display, not stored, which avoids two sources of truth.
- **NEW:** `assigned_to_user_id` defaults to the creator. Reassignment needs
  `PERM_REASSIGN_ESTIMATES` (new, following the `PERM_REASSIGN_PROJECT_STAFF`
  precedent) and is audited with old/new values.
- **Departures:** `users.active=0` (the existing suspend path) keeps the FK valid,
  and the name snapshot keeps history readable. Users are never hard-deleted while
  referenced. The existing `/api/v1/users/{id}/active-references` route pattern is
  extended to count estimates.
- **Every version and line** also records `created_by_user_id`, so "who priced this
  line" is answerable.

---

## 17. Admin Dashboard Integration

- **MODIFY** `render_admin_surface()`: add an **Estimates** tab, the same pattern
  as the existing domains.
- List columns: number, title, customer, property/site, creator, assignee, status,
  version, total, **cost / GP / margin** (only if `PERM_READ_ESTIMATE_COSTS`),
  created, updated, sent, viewed, decision.
- Filters (server-side query params, paginated with `limit/offset`, indexed):
  `created_by`, `assigned_to`, `customer_id`, `property_id`, `project_id`,
  `status`, `date_from/date_to` (created/sent), `min_total/max_total`, `q`.
- Detail: version history with diffs between versions (computed from line
  snapshots), the audit timeline (`/api/v1/audit-log?entity_type=estimate&entity_id=`,
  which already exists), communications (`communication_history` for the
  customer/opportunity), share-link status and views, and decisions.
- **RBAC (NEW permissions, additive):** `read:all_estimates` (admin, manager,
  sales_manager via team data), `read:estimate_costs` (admin, manager,
  sales_manager, and **sales for their own estimates**; D9), `send:estimates`,
  `approve:estimates` (if internal review is adopted), `reassign:estimates`,
  `manage:price_book`, `refresh:prices`. Plain `sales` users see their own plus
  assigned estimates. This closes F5.

---

## 18. Customer Estimate Portal

**Delivery (NEW):**
1. The estimator taps **Send to customer** → service checks: version complete,
   customer email present, status allows sending, tax configured.
2. The version is **locked** (`locked_reason='sent'`).
3. A share link is created: 32 random bytes (`secrets.token_urlsafe(32)`), with
   **only the SHA-256 stored**. Expiry = estimate expiry (default 30 days,
   configurable).
4. Email goes through the EXISTING `NotificationService.send_email` → Aigentik,
   containing the `https://portal.restoricon.com/e/<token>` link. It's logged to
   `communication_history` (outbound, email) and audited.

**Viewing:**
- `GET /e/<token>` (served by the Core on the `portal.` host) renders the
  **customer view** only. The page fetches
  `GET /api/v1/public/estimate/<token>`, which is rate-limited (the existing
  limiter, plus a stricter per-token bucket) and bound to **exactly one**
  `estimate_version_id`.
- Headers: `Cache-Control: no-store`, `Referrer-Policy: no-referrer`,
  `X-Robots-Tag: noindex`. The token sits in the **path, not `?token=`** (F3), and
  it never becomes a session/API token.
- First view → `first_viewed_at` is set, workflow moves `SENT → VIEWED`, it's
  audited, and the assignee is notified.
- If a newer version was sent, older links show "This estimate has been updated"
  with the new link (only if the newer link was issued to the same customer).
- Logged-in customers see the same `CustomerEstimateView` in `/portal`. **MODIFY**
  `GET /api/v1/portal/estimates` to use the allow-list serializer (fixes F1).

**Decisions:**
- **Accept:** typed full name, consent checkbox (the text is snapshotted), and an
  optional drawn signature (reusing the existing contract signature pad).
  Recorded: IP, user agent, timestamp, version. This produces an
  `estimate_decisions` row and a `ACCEPTED` status. If D7 = yes, it also triggers
  **contract generation** (EXISTING `create_contract` with `estimate_id`).
- **Decline**, with an optional reason. **Request changes**, with a comment, notifies
  the assignee and leaves the status at `CHANGES_REQUESTED`.
- Confirmation screen plus a confirmation email (Aigentik).
- Legal note: electronic acceptance validity (ESIGN/UETA consent language, and CT
  home-improvement contract requirements) → §30, D10.

---

## 19. Estimate Versioning

- Version 1 is created with the estimate. While `is_locked=0`, edits happen **in
  place** (it's a draft, and line-level audit rows record old/new values).
- Any edit to an estimate whose current version is locked calls **Revise**. That
  clones the locked version and its lines into `version_number+1` (unlocked),
  copying snapshots **as they were** (prices don't silently refresh). The estimator
  may then choose "Update prices to current," which is an explicit, audited action
  per line.
- Sending the new version locks it, sets `current_version_id`, marks earlier sent
  versions `superseded` (they're kept and still viewable by admins), and revokes
  or redirects the old share links.
- The admin diff view compares any two versions line by line (added, removed, and
  changed fields with old → new).
- Accepted versions are **permanently** locked. Changes after acceptance go through
  a **change order**. That's future scope, and it maps to master plan Appendix C
  §7/§9 "change orders."

---

## 20. Audit Trail

**EXISTING:** `audit_log` plus `AuditService.log(action, entity_type, entity_id,
change_summary, actor, details)` plus `build_audit_details(before, after, fields)`
(B6.2 old/new standard). **Reuse it, no new audit system.**

Events (entity_type → actions):
- `estimate`: create, update_header, assign, transition(from,to), send, view (actor
  = share link: `actor_id NULL`, `actor_role='customer_link'`, `actor_type='human'`,
  details `{share_link_id, ip}`), accept, decline, request_changes, revise, convert.
- `estimate_line`: add, update (field diff), remove, price_override,
  update_price_to_current.
- `retailer_product` / `price_observation`: refresh_requested, refreshed(old→new
  price), refresh_failed, manual_price_entered, csv_import(batch id, counts).
- `price_book_item`: create/update/deactivate (markup and waste changes carry old/new).
- `material_match`: confirm/reject.

The `actor_role` CHECK is free-text today (only `actor_type` has a CHECK), so
`customer_link` needs no schema change. **Verify** during Phase 3.

---

## 21. Quote Portal Migration

**Data that exists (UNVERIFIED count, since the live DB is on your phone):**
- `estimates` rows created through `POST /api/v1/estimates` (API/agent use only,
  since there's no UI).
- Leads/opportunities/appointments from `quote.restoricon.com`. These are **not
  quotes**, and they stay exactly as they are (PRESERVE).
- No quote PDFs exist (there's no PDF generation). Any `documents` rows with
  `document_type='estimate'` remain untouched.

**Read-only check to run on the phone before Phase 3** (copy/paste into Termux; it
opens the DB **read-only** and changes nothing):
```bash
python3 - <<'EOF'
import sqlite3, os
p = os.path.expanduser('~/.codeyOS/restoricon.db')
db = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
q = lambda s: db.execute(s).fetchall()
print('estimates by status:', q("SELECT status, COUNT(*) FROM estimates GROUP BY status"))
print('estimates w/ line items:', q("SELECT COUNT(*) FROM estimates WHERE line_items_json NOT IN ('[]','')"))
print('estimate docs:', q("SELECT COUNT(*) FROM documents WHERE document_type='estimate'"))
print('contracts linked to estimates:', q("SELECT COUNT(*) FROM contracts WHERE estimate_id IS NOT NULL"))
print('audit create rows for estimates:', q("SELECT COUNT(*) FROM audit_log WHERE entity_type='estimate' AND action='create'"))
try:
    sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)'); print('FTS5: available')
except Exception as e:
    print('FTS5: NOT available ->', e)
print('sqlite version:', sqlite3.sqlite_version)
EOF
```

**Migration strategy (MIGRATE, additive, reversible):**
1. **Snapshot first:** run the B7 backup snapshot and copy the DB file. The
   migration is rehearsed on the copy (`RESTORICON_DB_PATH=<copy>`) before live.
2. Existing rows keep their **id and `estimate_number`** (UNIQUE preserved) and
   get `source='legacy'`.
3. `created_by_user_id` is backfilled from `audit_log` (`action='create'`,
   `entity_type='estimate'`, `actor_id`). If none is found, it's NULL with
   `created_by_name='(pre-estimator record)'`. It's never guessed.
4. Legacy status maps to `workflow_status`: draft→DRAFT, sent→SENT,
   approved→ACCEPTED, rejected→DECLINED, expired→EXPIRED.
5. A **locked** `estimate_versions` row v1 is created per legacy estimate, with
   totals copied from the header floats converted to cents. `line_items_json` is
   parsed into `estimate_line_items` **only if** it matches a recognizable shape.
   Otherwise the raw JSON is kept and displayed read-only ("legacy line items"). The
   original `line_items_json` column is **never dropped**.
6. Contracts' `estimate_id` links are untouched. Customers can keep viewing legacy
   estimates in `/portal`, through the new allow-list serializer.
7. The quote page URL and endpoints stay live throughout. Nothing a customer or
   employee uses today disappears.

---

## 22. Estimate → Job Workflow

```
Lead ─► Customer ─► (Property) ─► Opportunity ─► Estimate v1..vN ─► ACCEPTED
   └ EXISTING        B8.1         EXISTING        NEW engine          │
                                                                     ▼
                                     Contract (EXISTING, estimate_id FK) ─► signed (EXISTING sign_contract)
                                                                     ▼
                     Project (EXISTING) created or linked; contract_amount = accepted total,
                     estimated_cost = accepted cost_total; opportunity → won stage
                                                                     ▼
                     WorkOrders (EXISTING) seeded from labor/sub lines grouped by trade (draft)
                                                                     ▼
                     PurchaseOrders (EXISTING) drafted from material lines grouped by
                     preferred vendor/retailer (retailers.vendor_id → vendors)
                                                                     ▼
                     Job costing: FinanceService.get_project_pnl (EXISTING) gains
                     "estimated vs actual" using the accepted version's snapshot
                                                                     ▼
                     Invoice (EXISTING) deposit/progress from contract terms
```
- **Convert** (`POST /api/v1/estimates/{id}/convert`) requires `ACCEPTED`. If the
  B8.12 handoff rule is adopted, it also requires a signed contract. It's
  idempotent (stores `converted_project_id`, and a second call returns the same
  project) and audited. It **creates drafts only**. Humans dispatch work orders and
  submit POs.
- No duplicated customers or projects: if the opportunity already has
  `project_id`, conversion links to it instead of creating a new one.

---

## 23. Codey-OS Integration Architecture

- **Library boundary:** `codey_estimator` exposes plain functions and dataclasses
  (no HTTP, no DB). CCOS agents *could* import it for pure calculation and
  normalization.
- **Operational boundary (recommended):** agents act on **data** only through the
  Core API with an `ai_agent` token. That way RBAC, audit (`actor_type='agent'`),
  and customer isolation apply to Codey exactly as they do to humans. Codey never
  opens the SQLite file directly for estimates.
- **CCOS plugin** `ccos/plugins/business/estimator/manifest.json` (same manifest
  format as `ccos/plugins/system/system_info/manifest.json`). Capabilities map 1:1
  to API routes:

| Capability | Route | Side effects |
|---|---|---|
| `estimator.search_products` | `GET /api/v1/pricing/search?q=` | none (may enqueue a discover job) |
| `estimator.get_product` | `GET /api/v1/pricing/products/{id}` | none |
| `estimator.compare_retailers` | `GET /api/v1/pricing/compare?q=` | none |
| `estimator.get_price_history` | `GET /api/v1/pricing/products/{id}/history` | none |
| `estimator.refresh_price` | `POST /api/v1/pricing/products/{id}/refresh` | enqueues a job |
| `estimator.search_price_book` / `add_to_price_book` | `/api/v1/price-book…` | write needs `manage:price_book` |
| `estimator.create_estimate` / `get_estimate` / `update_estimate` | `/api/v1/estimates…` | drafts only |
| `estimator.send_estimate` | `POST /api/v1/estimates/{id}/send` | **human confirmation required**, outward-facing |
| `estimator.get_estimate_status` | `GET /api/v1/estimates/{id}` | none |

- `ai_agent` gets read, search, and draft-create permissions by default, and **not**
  `send:estimates` (D11). An agent must never email a customer a price without a
  human approving it.
- **Aigentik follow-up:** the Appendix C §13 workflow ("estimate sent → wait 3 days
  → follow up") is implemented as an `AutomationRule` on the `estimate.sent` event,
  producing a `task` for the assignee. Aigentik sends only if you approve that
  automation.

---

## 24. Security Architecture

| Concern | Design |
|---|---|
| AuthN | EXISTING tokens/login. No new auth system. Customer links are **capability tokens scoped to one version**, and they never grant API sessions. |
| AuthZ | Service-layer `has_permission()` (EXISTING pattern) plus **object-level** checks: sales see own/assigned; customers see only their `customer_id`; share link → one version. |
| Customer isolation | Allow-list `CustomerEstimateView` (fixes F1); public endpoint returns 404 for any token that's unknown, revoked, or expired (no oracle distinguishing them). |
| Internal data | Cost, markup, waste, retailer, SKU, internal notes, and audit are never in customer DTOs; enforced by a unit test that serializes a fully populated estimate and asserts the forbidden keys are absent. |
| Input validation | Explicit field allow-lists on every write (EXISTING `ALLOWED_UPDATE_FIELDS` pattern), numeric bounds, max lines per version (e.g. 500), max string lengths. `Estimate(**json_body)` (current `routes.py:1070`) is replaced by explicit parsing. |
| Price manipulation | Totals are computed server-side only. Client-sent totals are ignored. `unit_cost` comes from an observation id or a permissioned manual entry (audited with old/new). Overrides require a reason and are audited. Locked versions are immutable (service plus trigger). Observations are append-only (trigger). |
| Rate limiting | EXISTING public limiter, plus a per-token limit on `/api/v1/public/estimate/*`, plus per-retailer token buckets and daily budget caps. |
| Secrets | Retailer API keys in Core config/env only, included in the B7.3 encrypted backup, never logged (adapter redacts the key from URLs in logs), never sent to the browser. |
| Transport | Cloudflare Tunnel TLS (EXISTING direction). |
| Token handling | Raw token only in the email/URL. The DB stores the SHA-256. Constant-time compare via hash lookup. Tokens can be revoked. |
| Review | Every schema/RBAC/public-route change goes through the Codey-OS rule-4 code-reviewer pass, plus a dedicated authorization test file. |

---

## 25. Mobile Architecture

The target is the S24 Ultra browser, and Android browsers generally.
- **Staff estimator surface** `/estimates` is a separate lightweight page, *not* a
  tab crammed into the 3,400-line admin surface. It's single-column and
  thumb-reachable, with a sticky bottom "totals and Save" bar.
- Flow (brief §22): Customer picker (search) → New estimate → **Add line** sheet
  (search box with debounced `/pricing/search`, result cards showing retailer
  price and freshness badge, tap to select → quantity stepper → optional labor row
  prefilled from the price-book defaults) → review totals (server preview) → Save
  → Send.
- Uses `inputmode="decimal"` for numbers, 44 px tap targets, and no hover-only UI.
- Offline: out of scope for v1 (the phone *is* the server). A draft autosave to
  `localStorage` protects against accidental navigation only. The server remains
  the source of truth.
- Admin list: a responsive table that collapses to cards under 640 px.
- Performance budget: the list page is under 150 KB of HTML+JS (no framework) and
  the search response is under 300 ms locally.

---

## 26. Testing Strategy

Runs identically in **GitHub Actions** (ubuntu, Python 3.11+) and **Termux**
(`pytest`). No Colab/Kaggle is needed, since there's no ML training.

**Unit (codey_estimator, no DB):**
- Money rounding: property-based cases where Σ of rounded components equals the
  stored total.
- Waste/package math (ceil), markup vs margin, discount allocation, tax methods,
  zero/negative guards, and price override.
- Normalizer: a table of about 100 real product titles → expected attributes (PEX,
  drywall, lumber, fittings, fractions/unicode).
- Matcher: equal / conflicting / uncertain pairs, and a rejected pair is never re-proposed.
- RefreshPolicy intervals and priorities; token bucket.
- Customer serializer forbidden-key test.
- Adapters: recorded JSON fixtures (no live network in CI).

**Integration (restoricon_core, temp SQLite, following EXISTING
`tests/test_restoricon_core` style):**
- Migrations on a fresh DB **and** on a fixture DB shaped like the current live
  schema with legacy estimates (backfill, status map, no data loss, row counts equal).
- Estimate service: create sets creator from the actor (body spoofing ignored);
  edit a locked version → error; revise → v2; send → lock + link + email mock +
  comms row + audit.
- RBAC matrix: every role × every estimate/pricing route (the authorization suite
  mandated by master plan §6.6).
- Public token: valid, expired, revoked, wrong version, brute-force rate limit, no
  cost keys in the response.
- Pricing worker: job claim race (two workers → one wins), backoff, circuit breaker,
  budget cap.

**End-to-end (Playwright in GitHub Actions against a test Core on a temp DB; not on
Termux):** the brief's full scenario: employee logs in → creates estimate →
searches "1/2 red pex" (seeded observations for both retailers) → selects Lowe's
50 ft → qty 4 → adds 3 h plumber → saves → sends (Aigentik mocked) → customer opens
`/e/<token>` → accepts → admin sees ACCEPTED with creator → convert → project exists
with contract_amount = total.

**Live verification (Codey-OS rule 7):** on-device run against a DB copy, then
live, with verbatim output recorded in the log. "Code complete" is not "done."

---

## 27. Deployment Strategy

| Environment | Where | How |
|---|---|---|
| Dev / CI | GitHub Actions (Codey-Estimator and Codey-OS) | pytest + Playwright E2E. The library needs no secrets. Adapter tests use fixtures. |
| Staging | The phone, second Core instance | `RESTORICON_DB_PATH=~/.codeyOS/staging.db RESTORICON_API_PORT=8771`, **not** tunneled; reach it from the phone browser at `127.0.0.1:8771` |
| Production | The phone, existing Core on 8770 behind the tunnel | Deploy = `git pull` of Codey-OS + `pip install` of the pinned `codey_estimator` tag, then a Core restart via the existing `codey restart` |

- **Packaging:** Codey-OS `requirements.txt` gets
  `codey-estimator @ git+https://github.com/Ishabdullah/Codey-Estimator@v0.x.y`,
  and `install.sh` is updated in the same PR (Codey-OS rule 11). The library is
  stdlib-only, so there are no native builds on Termux.
- **Migrations:** run automatically by `DatabaseManager` at startup (EXISTING
  pattern), idempotent, and guarded by a pre-migration backup snapshot.
- **New config/env:** `ESTIMATOR_ENABLED` (feature flag),
  `ESTIMATOR_TAX_RATE_BP`, `ESTIMATOR_DEFAULT_EXPIRY_DAYS`,
  `ESTIMATOR_PUBLIC_BASE_URL` (`https://portal.restoricon.com`),
  `PRICING_HOMEDEPOT_PROVIDER` (`bigbox|serpapi|off`), `PRICING_BIGBOX_API_KEY` /
  `PRICING_SERPAPI_KEY`, `PRICING_DAILY_BUDGET`, `PRICING_DEFAULT_ZIP`. Secrets go
  in `config.json`/env, covered by the B7.3 encrypted backup, and are **never
  committed**.
- **Cloudflare:** the `/e/*` and `/api/v1/public/estimate/*` paths are reachable on
  `portal.`. Everything else under `/estimates` and `/api/v1/pricing` requires login.
  Whether Cloudflare Access fronts staff surfaces is the existing open item in
  master plan §6.6.

---

## 28. Rollback Strategy

1. **Feature flag:** `ESTIMATOR_ENABLED=0` hides the new surfaces and returns 404
   for new routes. Legacy `/api/v1/estimates` GET/POST keep working unchanged.
2. **Additive schema:** new tables and columns are harmless to old code. Rolling
   back the code leaves them unused.
3. **The one non-additive step** (the `estimates` table rebuild for CHECK/FK) runs
   in its own release, after a verified B7 snapshot. It's rehearsed on a copy, and
   rollback = restore the snapshot (the B7.4 drill is already proven). Share links
   issued after the rebuild would be lost on restore, so the rebuild ships **before**
   any customer-facing sending is enabled.
4. **Library pin:** revert the `requirements.txt` pin to the previous tag.
5. **Pricing worker:** a separate flag, `PRICING_WORKER_ENABLED=0`, stops all
   outbound retailer calls instantly (cost/ToS kill switch).

---

## 29. Implementation Phases

Adjusted from the brief's order. Retailer adapters move after the estimating core,
because the core is useful with manual/CSV prices and the retailer questions are
unresolved.

| # | Phase | Repo | Deliverable | Exit criterion |
|---|---|---|---|---|
| 0 | Audit & plan | Codey-Estimator | this document | ✅ done, awaiting approval |
| 1 | Decisions & registration | Codey-OS docs | D1–D11 answered; spoke doc registered in `CODEY_MASTER_PLAN.md` §6 as **Phase B9 — Estimating System** plus Appendix A lines; F1–F6 logged in `NEW_ISSUES.md` | the master plan and this plan agree |
| 2 | **Library foundation** | Codey-Estimator | `money`, `units`, `calc` engine, customer serializer, 100% unit-tested, CI | formulas match §15 and signed-off examples |
| 3 | Schema & migrations | Codey-OS | new pricing + estimate tables, `estimates` column additions, rebuild (CHECK/FK), legacy backfill | rehearsal on a live-DB copy: counts equal, no loss; code-reviewer APPROVED |
| 4 | Pricing core (no retailers) | both | normalizer, repositories, FTS search, `ManualAdapter`, `CsvImportAdapter`, price observations/history | search "1/2 red pex" returns manually entered products in < 300 ms |
| 5 | Price Book & labor rates | both | CRUD + permissions + audit | price-book defaults prefill lines |
| 6 | Estimate service & API | Codey-OS | create/edit/version/transition/assign/preview + RBAC + audit; F1/F5 fixed | RBAC matrix suite green |
| 7 | Staff estimator UI (mobile) | Codey-OS | `/estimates` surface | the §22 phone flow completed on the S24 by you |
| 8 | Admin management | Codey-OS | Estimates tab, filters, version diff, audit timeline | the admin sees all estimates with creators |
| 9 | Customer delivery | Codey-OS | share links, `/e/<token>`, accept/decline/changes, email via Aigentik | E2E test green; live test to your own email |
| 10 | Refresh queue & worker | both | `pricing_jobs`, worker thread, rate limiter, budget cap, kill switch | code-reviewer APPROVED (rule 4) |
| 11 | Home Depot adapter | Codey-Estimator | licensed-provider adapter + fixtures | 20 real lookups within budget |
| 12 | Lowe's adapter / CSV | Codey-Estimator | per D2 | comparison table shows both where data exists |
| 13 | Matching & comparison UI | both | proposed/confirmed matches, compare view | uncertain matches never auto-merge |
| 14 | Estimate → Contract → Job | Codey-OS | convert, contract generation, WO/PO drafts, estimated-vs-actual P&L | E2E through project creation |
| 15 | Quote Portal adjustments & legacy view | Codey-OS | copy changes, calculator decision (D8), legacy estimates visible | nothing previously reachable is lost |
| 16 | Hardening & live verification | all | security review, mobile QA, live verification on device | rule-7 live verified |
| 17 | Codey-OS/CCOS plugin & automation | Codey-OS | manifest, ai_agent permissions, follow-up rule | agent can draft but not send |

---

## 30. Risks

**Technical**
- *Single-device hosting:* if the phone is offline, the estimator and customer links
  are down (an existing architectural fact, master plan §3.6). Mitigation: status
  banner; B7 backups; long-term portability is already a Codey-OS discipline.
- *SQLite concurrency:* WAL handles this scale; the worker is a single thread;
  transactions stay short.
- *Float money in legacy columns:* the new tables use cents; conversion happens only
  at the boundary, with tests.
- *FTS5 availability on Termux:* check with the §21 command; there's a fallback.
- *The Codey-OS codebase is large and hand-routed* (`routes.py` 2,774 lines,
  `web_surfaces.py` 5,445 lines): new routes should live in their own module that
  routes.py delegates to, which keeps review tractable.

**Legal / compliance**
- *Retailer terms of service:* direct scraping is not recommended; use licensed
  providers or your own purchase data. Provider terms may limit how long you can
  cache prices or show images. Read them before enabling.
- *Sales tax:* CT treatment of materials vs. labor for contractors on real-property
  work affects the tax method. **Confirm with your accountant** (D6). The engine
  supports several methods but I won't choose one for you.
- *E-acceptance:* ESIGN/UETA consent wording and CT Home Improvement Act contract
  requirements (e.g. cancellation notice) mean an accepted *estimate* should lead to
  a proper *contract* rather than being treated as the contract (D7, D10).
- *Public price ranges* on the quote page create expectations (D8).

**Operational**
- *Retail shelf price ≠ your cost* (Pro pricing, store variation, volume). The
  CSV import of actual purchases matters more than it looks.
- *Stale prices* on volatile materials; mitigated by per-category intervals.
- *Paid API spend*; mitigated by the daily budget cap and local-first search.
- *Incorrect product matches* causing wrong pricing; mitigated by confidence
  thresholds and human confirmation.

**Maintenance**
- Provider APIs change or shut down, so adapters are isolated and fixtures pinned.
- Two repos must stay in sync, so the library is versioned with tags and Codey-OS
  pins exact versions.
- Governance overhead: Codey-OS requires an architect/implementer/reviewer pipeline
  per change. Budget for it.
- **This session has read-only access to Codey-OS.** Integration PRs to Codey-OS
  need push access added (or you apply them).

---

## 31. Decisions Requiring Approval

Only questions the repositories can't answer and that change architecture or data
integrity:

| ID | Decision | Recommendation |
|---|---|---|
| **D1** | Code location: Codey-Estimator as a **pure library** plus integration PRs into Codey-OS `restoricon_core` (one DB, one API), vs. everything inside Codey-OS, vs. a separate service | **Library + Core integration** |
| **D2** | Retailer data source: licensed API (BigBox/SerpApi, paid) vs. scraping vs. your Pro purchase-history CSVs + manual | **Manual + CSV first, then one licensed HD provider; Lowe's via CSV until a licensed source is found; no direct scraping.** Also: do you have HD Pro Xtra / Lowe's Pro accounts with exportable history? |
| **D3** | Money as integer cents in all new tables (legacy REAL untouched) | **Yes** |
| **D4** | Extend the existing `estimates` table (header) plus new versions/lines tables, vs. a new table set | **Extend** |
| **D5** | Workflow statuses. Proposed: `DRAFT → (INTERNAL_REVIEW → APPROVED_INTERNAL)? → SENT → VIEWED → ACCEPTED / DECLINED / CHANGES_REQUESTED / EXPIRED / CANCELLED → CONVERTED`. Do you want an internal-review step (does someone other than the creator approve before sending)? | Include INTERNAL_REVIEW **as optional** (a per-user "requires approval" flag) |
| **D6** | Tax method (none / materials-only / whole taxable lines) and labor billing (bill rate vs. markup). **Ask your accountant about CT rules.** | Configurable; engine supports both |
| **D7** | Does acceptance auto-generate a Contract (EXISTING contracts + signature) before any Job? Also: build B8.1 `properties` first, or ship with a site-address snapshot? | **Yes, estimate → contract → job.** Build `properties` per B8.1 first if possible |
| **D8** | Public drying calculator on quote.restoricon.com: keep hard-coded ranges, drive from the price book, or remove prices | **Remove $ ranges or drive them from the price book**, your call |
| **D9** | May regular `sales` users see cost/margin on their *own* estimates? | Yes (they need it to price); no for others' |
| **D10** | Acceptance evidence: typed name + consent checkbox, or also a drawn signature? Default share-link expiry (30 days)? | Typed + checkbox, optional drawing; 30 days |
| **D11** | Codey (ai_agent) may draft estimates but never send without human approval | **Yes** |

Also needed from you (a fact, not a decision): the output of the read-only command
in §21.

---

## 32. Recommended First Development Task

**Phase 2: the `codey_estimator` library foundation in this repo.** It touches no
production system and blocks on nothing except D3 and D6's examples.

Scope:
1. `pyproject.toml` (stdlib-only, Python ≥ 3.11), `src/codey_estimator/{money,units,calc,dto}.py`.
2. `CalculationEngine` implementing §15 exactly, with `CALC_ENGINE_VERSION = 1`.
3. `CustomerEstimateView` allow-list serializer and the forbidden-keys test.
4. `tests/` with worked examples you provide or approve, e.g. the brief's
   "4 × 1/2 in. red PEX 50 ft @ $XX.XX + 3 h plumber" computed by hand and asserted.
5. GitHub Actions workflow: pytest on push. The same command works in Termux:
   `cd ~/Codey-Estimator && pip install -e . && pytest`.

### Exact implementation sequence with dependencies

```
P0 Audit ✅
 └─► P1 Decisions D1–D11 + register B9 in Codey-OS master plan + log F1–F6
      ├─► P2 Library: money/units/calc/dto ─────────────────────────────┐
      │                                                                 │
      └─► P3 Core schema+migrations (needs D3,D4,D5; B8.1 if D7=yes)     │
            └─► P4 Pricing core: normalizer, repos, search,             │
                   Manual+CSV adapters (needs P2,P3)                    │
                  └─► P5 Price Book + labor rates (P4)                  │
                        └─► P6 Estimate service+API, F1/F5 fixes (P2,P3,P5)
                              ├─► P7 Staff mobile UI (P6)
                              ├─► P8 Admin tab (P6)
                              └─► P9 Customer delivery (P6; D7,D10)
                                    └─► P14 Estimate→Contract→Job (P9; D7)
            P4 ─► P10 Refresh queue+worker (rule-4 review)
                     └─► P11 HD adapter (D2) ─► P12 Lowe's/CSV (D2) ─► P13 Matching+compare UI
      P6 ─► P15 Quote Portal copy/calculator (D8) + legacy view
      P7–P15 ─► P16 Hardening + live verification ─► P17 CCOS plugin + automation (D11)
```

**Stop point:** no files will be created in Codey-OS, Codey-Aigentik, or
Restoricon, and no library code will be written in this repo, until you approve
this plan and answer the decisions in §31.
