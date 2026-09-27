# Codey-Estimator — Project Log

Reverse-chronological. Every change gets an entry.

## 2026-09-27 — Phase 1: decisions answered, agent pipeline created

**What was done**
- Answered all of §31's D1–D11 decisions with the user; recorded in
  `docs/DECISIONS.md` (not edited into the original plan, to keep an audit trail
  of what was proposed vs. what was decided).
- D9 was revised from the plan's original recommendation: sales reps now see
  cost/margin on **all** estimates (not just their own); editing rates/markups
  stays admin/manager-only.
- New scope added (not in the original plan): `labor_rates` gets three billing
  modes (`hourly`, `fixed_per_unit`, `fixed_flat`) and a new append-only
  `labor_rate_history` table driving an inline min/avg/max trend badge. Detailed
  in `docs/DECISIONS.md` addendum.
- Set up the agent pipeline for all future implementation work: `CLAUDE.md`
  (governance rules) plus `.claude/agents/estimator-architect.md` (opus),
  `estimator-implementer.md` (sonnet), `estimator-code-reviewer.md` (sonnet),
  `estimator-verifier.md` (haiku). This session acts as orchestrator, handing
  work between them per task.

**Key decision, flagged as a risk (not a recommendation)**
- D2: user chose to build a Home Depot/Lowe's scraper despite the audit's ToS
  and Termux-feasibility warnings (§9–10 of the plan). Accepted as-is, logged
  under "Areas of Concern" in `docs/DECISIONS.md`. This work is Phase 11/12,
  not part of the current Phase 2 library work.

**Not done (by design)**
- No code written yet. `docs/ARCHITECTURE_PLAN.md` §31 recommendations were not
  edited in place — `docs/DECISIONS.md` is the record of what was actually
  decided, including the D9 revision.
- Codey-OS `NEW_ISSUES.md` still doesn't have F1–F6 logged (this session only
  has read-only Codey-OS access; queued, needs push access or the user to apply
  it there).

**Areas of concern (tracked)**
- D2 scraper: ToS violation risk + Termux headless-browser infeasibility (see
  `docs/DECISIONS.md`).
- CT sales-tax method (D6, materials-only default) still needs accountant
  confirmation before it governs real customer tax calculations.
- Live DB contents still unverified (§21 read-only check not yet run — needed
  before Phase 3, not Phase 2).

**Next:** Phase 2 — architect agent produces the detailed spec for the
`codey_estimator` library foundation (money/units/calc/dto), incorporating the
D3/D6/D6b/D9 decisions and the labor rate addendum; then implementer → code
review → verifier.

## 2026-09-27 — Phase 0: system audit & architecture plan

**What was done**
- Cloned and read (read-only) `Ishabdullah/Codey-OS` @ `91ee3c1`,
  `Ishabdullah/Restoricon` @ `73eee40`, and `Ishabdullah/Codey-Aigentik` (main).
- Wrote `docs/ARCHITECTURE_PLAN.md` (32 sections, per the planning brief).
- Created this log and `README.md`.

**Key findings**
- The Restoricon repo is a static GitHub Pages site. The real business backend is
  `Codey-OS/restoricon_core` (Python stdlib HTTP + SQLite on the phone, behind a
  Cloudflare Tunnel, serving quote./portal./admin.restoricon.com).
- The current "Quote Portal" is lead intake + a client-side calculator + booking.
  It never creates estimates.
- `estimates` table exists but has no creator/assignee, no update/versioning/status
  logic, no number generator, no UI, and `ON DELETE CASCADE` from customers.
- Security findings F1–F6 (plan §5): the most important is that customer-facing
  estimate responses return `line_items_json` unfiltered.

**Not done (by design)**
- No code written. No changes to Codey-OS, Codey-Aigentik, or Restoricon.
- Findings F1–F6 are not yet logged in Codey-OS `NEW_ISSUES.md` (this session has
  read-only access to Codey-OS). Queued for Phase 1.

**Areas of concern (tracked)**
- Retailer data legality/cost (plan §9, §10, D2).
- CT sales-tax method needs accountant input (D6).
- Live DB contents are unverified. The read-only check command is in plan §21.

**Next:** await approval and answers to D1–D11 (plan §31).
