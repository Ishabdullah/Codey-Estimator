# Decisions D1–D11 (§31 of ARCHITECTURE_PLAN.md) — Answered

Recorded 2026-09-27. These answers are binding for all implementation phases
unless the user revises them (revisions get a new dated entry below, not an
edit of the original).

| ID | Decision | Answer |
|---|---|---|
| **D1** | Code location | **Library + Core integration.** Codey-Estimator stays a pure stdlib library (`codey_estimator`); Codey-OS `restoricon_core` integrates it via PRs. One DB, one API. |
| **D2** | Retailer data source | **Build a scraper for Home Depot/Lowe's.** User confirmed after risk disclosure (ToS-violation exposure for Restoricon LLC; headless Chromium is not practical on Termux/Android; retail prices vary by store/ZIP and don't confirm *your* Pro price). This is logged as an accepted risk, not a recommendation — see "Areas of Concern" below. Out of scope until Phase 11/12; does not block Phase 2. |
| **D3** | Money format | **Integer cents** in all new tables. Legacy `REAL` columns untouched. |
| **D4** | Schema approach | **Extend the existing `estimates` table** (header) + new `estimate_versions` / `estimate_line_items` tables. No parallel table set. |
| **D5** | Workflow / internal review | **Optional per-user "requires approval" flag.** `DRAFT → (INTERNAL_REVIEW → APPROVED_INTERNAL)? → SENT → VIEWED → ACCEPTED/DECLINED/CHANGES_REQUESTED/EXPIRED/CANCELLED → CONVERTED`. |
| **D6** | Tax method | **Materials-only taxable** (labor lines are not taxed) — test default; engine still supports other methods per the plan. **CT-specific confirmation with an accountant is still recommended before this ships to production tax calculations.** |
| **D6b** | Labor billing method | **Explicit bill-rate.** `labor_sell = labor_qty × labor_bill_rate`, distinct from `labor_cost_rate` (payroll cost). Not markup-on-cost. |
| **D7** | Estimate → Contract → Job | **Yes.** Acceptance generates a Contract (existing `contracts` table, still needs signature) before any Project/Job is created. |
| **D8** | Public quote.restoricon.com calculator | **Remove the public $/sq ft ranges.** Replace with a "request an estimate" flow; no price expectations set before a real estimator looks at the job. |
| **D9** | Cost/margin visibility | **REVISED 2026-09-27.** Sales reps, sales_manager, manager, and admin can all see cost/margin on **every** estimate (not just their own). **Editing** labor rates, markups, and price-book defaults is restricted to admin/manager — sales can view pricing inputs but not change them. *(Original plan default — sales see only their own — is superseded by this answer.)* |
| **D10** | Acceptance evidence / expiry | **Typed full name + consent checkbox always required; drawn signature optional** (reuses the existing contract signature pad). Default share-link expiry: **30 days**. |
| **D11** | AI agent (Codey/CCOS) send permission | **Yes — draft only.** `ai_agent` token gets read/search/draft-create permissions and **never** `send:estimates`. No automated pricing reaches a customer without a human clicking send. |

## Addendum: Labor rate modes and rate-history trend (2026-09-27)

Raised by the user alongside D9; extends plan §13 (`labor_rates`) and §17 (admin RBAC).

- **`labor_rates.rate_type`** gets three modes, chosen per estimate line at time of
  use (not fixed per labor_type record — the same labor type, e.g. "plumber," can
  be billed different ways on different jobs):
  1. `hourly` — `labor_sell = labor_qty × labor_bill_rate` (qty is hours).
  2. `fixed_per_unit` — `labor_sell = labor_qty × labor_bill_rate`, but qty is a
     non-hour unit (e.g. per fixture, per room). Mechanically identical to
     `hourly` in the calc engine; the distinction is display/unit-label only
     (`labor_unit` already carries this — `hr` vs `fixture` vs `room` etc.), so
     this does **not** need a separate formula branch, only a value in
     `labor_unit` other than `hr`.
  3. `fixed_flat` — `labor_sell = labor_bill_rate` (a single flat amount for the
     whole line; `labor_qty` is ignored/locked to 1 in calc, but still stored for
     display, e.g. "flat rate — drywall hang, 1 room").
- **`labor_rate_history`** (NEW table, append-only, mirrors `price_observations`
  for materials): `id, labor_rate_id, labor_type, rate_type, cost_rate_cents,
  bill_rate_cents, effective_from, changed_by_user_id, changed_at, reason?`.
  Every edit to a `labor_rates` row's cost/bill rate inserts a history row before
  the update (trigger or service-layer, matching the `price_observations`
  append-only pattern).
- **Trend display:** wherever a labor rate is entered or shown (estimate line
  labor picker, Price Book / Labor Rates admin page), show a small range badge
  computed from the **last N=6 changes** (configurable) for that `labor_type` +
  `rate_type`: `min–max bill rate (avg)`, e.g. `"$32–$38/hr (avg $35) over last 6
  changes"`. This is a read-only aggregate query (`MIN/MAX/AVG` over
  `labor_rate_history` ordered by `effective_from DESC LIMIT 6`), not a chart —
  matches D10's "inline, not a separate page" answer.
- RBAC: viewing labor_rate_history/trend follows the same D9 rule (sales +
  admin/manager can see it); **editing** a labor rate (which inserts history)
  requires admin/manager, per the D9 revision above.

## Outstanding (not decisions, but still needed before later phases)

- The §21 read-only DB check command output (live `estimates`/`documents`/FTS5
  check) — needed before Phase 3 schema work, not before Phase 2 library work.
- Accountant confirmation of D6's materials-only tax treatment for CT
  real-property contractor work, before this governs a real customer-facing tax
  calculation.
- Confirmation of a licensed retailer data provider account (BigBox/SerpApi) is
  no longer needed given the D2 answer, but the scraper's legal exposure should
  be revisited with the business owner (you) before Phase 11/12 ships to
  production — see Areas of Concern.

## Areas of Concern (carried forward into PROJECT_LOG.md per change)

- **D2 scraper risk (HIGH, accepted):** direct scraping of Home Depot/Lowe's
  likely violates their Terms of Service and risks IP bans or legal action
  against Restoricon, LLC. It's also technically fragile: bot protection, and
  headless-browser scraping is not practical on Termux/Android (the eventual
  runtime target), so it will likely need to run somewhere other than the phone,
  or fail intermittently. Logged as an accepted risk per explicit user
  confirmation on 2026-09-27, not as an engineering recommendation. Revisit if
  it becomes unreliable or a ToS enforcement action occurs.
