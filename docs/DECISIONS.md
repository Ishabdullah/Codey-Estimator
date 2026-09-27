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

## Addendum: Phase 2 architect spec — open questions resolved (2026-09-27)

The Architect agent's Phase 2 spec (money/units/calc/dto) raised 11 open
questions. Answered as follows; binding for the Implementer:

- **Q1 (combined-line tax):** Under materials-only tax, a combined line (or an
  override) is taxed only on its material share, pro-rated by
  `net_sell × material_sell / components_sell`. Equipment/subcontractor
  portions, and allowance/fee lines with no material, are never taxed.
- **Q2 (tax rate precision):** Integer basis points is fine (CT's 6.35% = 635
  bp is exact). Finer precision is a future change if a jurisdiction needs it.
- **Q3 (discount tie-break):** Not re-asked — largest-remainder allocation
  with ties going to the lower line index, as the architect proposed, stands.
- **Q4/Q5 (fixed_flat labor):** The flat rate locks **both** cost and sell to
  a single flat amount (quantity is stored for display only, never multiplied
  into the flat amount's math). It still charges even at quantity 0. Bill rate
  is mandatory on every labor line; there is no markup-on-cost fallback
  anywhere (confirms D6b removes the plan §15 fallback entirely).
- **Q6 (labor unit validation):** Not re-asked — HOURLY requires `labor_unit
  == HR`; FIXED_PER_UNIT requires `labor_unit != HR`. Stands as spec'd.
- **Q7 (customer view details):** Not re-asked — the customer view shows the
  requested material quantity before waste (never the package count or waste
  math), omits internal fields (section, tax rate, line-level discount
  breakdown), and simply excludes hidden lines from the visible list (their
  price still counts toward the displayed totals). Stands as spec'd.
- **Q8 (package/quantity guard rails):** Package quantities and units must
  always reflect **actual retailer packaging** (a real product's sold
  quantity/unit — e.g. a 50 ft PEX roll, a 4×8 drywall sheet, a 1-gallon paint
  can), never an invented or synthetic package size. This means `package_qty
  >= 1` (whole real-world packages) is correct and stays as the Phase 2 guard;
  fractional packages aren't a Phase 2 concern because Phase 2 has no retailer
  data yet. **Carried forward to Phase 4 (catalog/pricing):** the product
  normalizer and retailer adapters must always source `package_qty` /
  `package_unit` from the retailer's actual listing, never let an estimator
  type in an arbitrary package size by hand for a linked retailer product.
  Manual-entry price-book items (no retailer link) are the one place a
  free-typed package size is acceptable, since there's no retailer listing to
  contradict.
- **Q9 (allowance/fee lines):** The price-override mechanism (reason required,
  audited) is fine for now; no dedicated flat-price field needed.
- **Q10 (CI workflow):** Included in Phase 2 — `.github/workflows/test.yml`
  (pytest on push) is part of this task, not a follow-up.
- **Q11 (Money type):** Not re-asked — `Cents = int` type alias plus helper
  functions (not a wrapper class) is accepted, matching the INTEGER-cents DB
  columns Phase 3 will create.

## Addendum: Phase 4b architect spec — `ports.py` + `refresh.py` open questions resolved (2026-09-27)

The Architect agent's Phase 4b spec (repository Protocols + refresh policy,
token bucket, daily budget, backoff, circuit breaker) raised 9 open questions.
Resolved by the orchestrator per this repo's own governance (none of these
touch a real tax/RBAC/schema decision only the user can make — they're
implementation-technique choices within already-decided architecture); binding
for the Implementer:

- **Q1 (blocking — purity test vs. `datetime`/`time.monotonic`):** Resolved in
  favor of keeping `test_purity.py`'s forbidden-imports list exactly as-is.
  `refresh.py` uses `EpochSeconds = int` (UTC Unix seconds) throughout, and
  every clock read goes through a **required** `now_fn: Clock` parameter — no
  default, no wall-clock import inside the library. This matches the existing
  determinism rule the calc engine already follows. Codey-OS converts its
  SQLite `TEXT` timestamps to epoch seconds at the repository boundary, not
  inside this library. `refresh.py` is a single module, not a `refresh/`
  package, for this task's actual scope — split it later only if it grows
  enough to need it.
- **Q2 (retailer/store identity):** Confirmed — `retailer_code: str` and
  `store_code: str` in the ports, never the Core DB's integer ids. Codey-OS
  maps codes/store-codes to its own `retailer_id`/`retailer_stores.id` at the
  repository implementation layer. Matches D1's library/Core boundary exactly.
- **Q3 (config defaults / "high value" basis):** Approved as **library
  defaults only, fully overridable** — not a business decision on real pricing
  policy: `frequent_min_uses=5`, `high_value_threshold_cents=10_000`
  ($100.00/package), `high_value_interval_days=60`, volatile categories
  `copper`/`lumber`/`sheet_goods` at 30 days. **"High value" compares the
  package price** (`current_price_cents`), not a computed per-unit-of-measure
  price. Codey-OS supplies real production numbers when Phase 5 (Price Book)
  is built; revisit then, not now.
  - **Naming correction (orchestrator, not the architect's call to make
    unreviewed):** the spec's `RefreshSubject` field named `unit_price_cents`
    is documented as "per package," which collides with
    `PriceObservationData.unit_price_cents` elsewhere in the *same* spec — a
    genuinely different thing (a computed per-unit-of-measure price for
    cross-package comparison, e.g. $/sq ft). Two dataclasses in one module
    using the same field name for two different concepts is exactly the kind
    of DTO ambiguity this repo's own rules (customer-view allow-list
    discipline) exist to catch before it ships. **The Implementer renames
    `RefreshSubject`'s field to `package_price_cents`** throughout the spec's
    examples/tests; no other change. The `price_book_items.use_count`
    (lifetime) vs. `uses_in_window` (90-day) mismatch the spec flagged is
    correctly deferred — it's a Phase 3/5 schema question, not a Phase 4b one.
- **Q4 (search-cache max age):** Confirmed — a required parameter, no library
  default. Codey-OS picks the actual freshness window when Phase 4c/6 wires up
  remote search.
- **Q5 (daily budget: calendar day, fixed UTC offset, no persistence):**
  Approved as specified, including the known limitation that a fixed offset
  drifts about an hour across Connecticut's two annual DST transitions — this
  is a soft API-spend cap, not a safety-critical boundary, so the drift is an
  accepted limitation, not a defect. No `BudgetRepo` Protocol in this task;
  whether/how Codey-OS persists `BudgetState` across a process restart is a
  Phase 10 (refresh queue & worker) decision, not this one.
- **Q6 (no jitter in backoff):** Confirmed — single-worker-thread system, no
  thundering-herd concern, and randomness is already forbidden in this
  library. The caller isn't given a jitter hook.
- **Q7 (`RetailerProductRepo.update_refresh_state` added beyond the four
  originally-asked methods):** Approved — keep it. Without it, the
  check-then-reschedule refresh loop can't be expressed through the port at
  all, which would just force Codey-OS to reach around the interface.
- **Q8 (`FAILED`/`PENDING` → `is_due() == False`):** Confirmed — matches plan
  §12's model where a failed product needs an admin reset or a manual
  "Refresh Price" action before it's retried automatically, rather than being
  silently retried by the policy itself.
- **Q9 (circuit breaker scope: generic, one per retailer, in-memory only):**
  Confirmed. Per-product `consecutive_failures` feeding
  `retailer_products.refresh_status='failed'` is Codey-OS worker logic
  (Phase 10), explicitly out of scope for this library task.

## Addendum: Phase 4a architect spec — `catalog` (normalizer/matcher) decisions (2026-09-27)

The Architect agent's Phase 4a spec (product normalizer, canonical key,
matcher) raised 7 open questions and explicitly flagged 4 of them (Q1, Q2, Q3,
Q6 in its own numbering) as touching schema or money — genuine business/data
judgment calls, not implementation technique, so they went to the user rather
than being decided by the orchestrator. Answered 2026-09-27:

- **UPC/model identity vs. a conflicting required attribute:** **flag for
  human review, never auto-discard or auto-merge.** When a candidate's
  barcode or model number matches a canonical material the system already
  tracks, but a required attribute (e.g. pipe size) conflicts with the stored
  record, the match keeps its full confidence (a barcode match is strong
  evidence) but its **status drops to `PROPOSED`, never `AUTO_CONFIRMED`** —
  a person confirms or rejects it. This is the architect's recommended
  default (spec §8.1, tests M11/M12) and matches plan §11.6's own principle
  ("where matching is uncertain, preserve the separate retailer products")
  applied to the identity-plus-conflict case specifically: the data is
  contradictory, which is a review case, not an auto-decision either way.
- **Confidence as integer basis points (0–10000), not a float:** approved —
  consistent with D3 and this library's existing basis-point convention
  (markup_bp, tax_rate_bp, etc. in the calc engine). Not a new decision, just
  applying an already-decided convention.
- **Default subtype when a listing's title is silent** (e.g. no "Type X" /
  "pressure-treated" in the text): **assume the plain/standard version**
  (drywall → `REGULAR`, lumber → `UNTREATED`). Approved because the risk is
  well-contained by the matcher's own design: a wrong default only ever caps
  a match at `PROPOSED` (needs human confirmation) — it never lets a
  mis-guessed subtype silently `AUTO_CONFIRM` into a real estimate.
- **Matcher weights and thresholds:** approved as proposed — `REQUIRED=10`,
  `SUBTYPE=6`, other `OPTIONAL=3`, `INFO=0`; `AUTO_CONFIRM >= 9000 bp`,
  `PROPOSED >= 6000 bp`, else `NO_MATCH`. These are **library defaults, not
  binding production tuning** — same posture as the Phase 4b `RefreshPolicyConfig`
  defaults. Revisit with real cross-retailer listing data once Phase 4a/13
  actually runs against retailer products, not before.
- **Canonical key format** (adds a category prefix and includes `SUBTYPE`,
  vs. the architecture plan's own illustrative example): **pending — the
  user asked to see the exact format with real examples before approving.**
  Given directly in the same conversation turn as this addendum (see
  `PROJECT_LOG.md`/chat for the worked table). Do not implement `keys.py`
  until this line is updated to "approved."
- **Package-inference provenance (Q6):** approved as scoped — `infer_package`
  itself assigns no provenance; whether a package size counts as
  `RETAILER_LISTING` or `MANUAL_ENTRY` is decided by the adapter/caller, per
  the existing Q8 addendum (adapters must source `package_qty`/`package_unit`
  from the actual retailer listing; free-typed sizes are manual-entry only).
  The specific unit choices (drywall in SF, lumber in EA not LF, paint in
  QT/GAL kept to whole quart/gallon amounts, fasteners with no count
  returning `None` rather than guessing a weight-based unit) are approved as
  sound, ordinary construction-estimating conventions.
- **Minor documented limitations, not decisions (Q7):** lumber length with no
  unit uses a `<=24 -> feet, else inches` heuristic; dimensions written only
  in inches (`48 in. x 96 in.`) aren't parsed; nail sizes other than
  penny/`Nd` aren't parsed. Accepted as v1 gaps, logged for a future
  follow-up alongside the deferred ~100-real-title normalizer corpus (plan
  §26) and the fittings category — not blocking this phase.

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
