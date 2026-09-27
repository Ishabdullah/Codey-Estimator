# Codey-Estimator — Project Log

Reverse-chronological. Every change gets an entry.

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
