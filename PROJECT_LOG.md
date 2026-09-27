# Codey-Estimator — Project Log

Reverse-chronological. Every change gets an entry.

## 2026-09-27 — Add ruff + mypy (strict) to the library

**What was done**
- Added `[project.optional-dependencies].lint` (`ruff>=0.6`, `mypy>=1.10`) to
  `pyproject.toml`, plus `[tool.ruff]` (line-length 100, `E/F/I/UP/B/SIM` rules,
  first-party import grouping) and `[tool.mypy]` (`strict = true`, scoped to
  `src/codey_estimator`; `tests/*` exempted from strict mode since tests are
  allowed looser typing than the library itself, per this repo's own
  stdlib-only/strict rule applying to `src/`, not to test code).
- Added a `lint` job to `.github/workflows/test.yml`, parallel to the existing
  `pytest` job: `ruff check src tests` then `mypy`.
- Fixed every finding both tools raised against the existing Phase 2 code —
  no findings were suppressed or ignored:
  - `src/codey_estimator/calc/engine.py`, `dto.py`: three lines over the
    100-column limit, wrapped (no logic change).
  - `src/codey_estimator/money.py`, `units.py`: three `isinstance(x, A) or
    isinstance(x, B)` chains merged into `isinstance(x, (A, B))` — same
    semantics, ruff's SIM101.
  - `tests/test_purity.py`: a nested `if` merged into one `and`-joined
    condition (SIM102) — same semantics.
  - `tests/*`: unused imports removed, import blocks re-sorted (ruff
    `--fix`, both purely cosmetic).
  - `mypy --strict` findings, all in `calc/engine.py`: added a `_LineRaw`
    TypedDict (replacing two bare `dict` annotations) so the internal raw
    line-computation shape is fully typed instead of untyped, and rewrote
    the `sell_before_discount` ternary to test `line.price_override_cents
    is not None` directly (instead of through an intermediate bool) so
    mypy can narrow `int | None` to `int` across the branch. No calculation
    logic changed — verified by re-running the full suite.
- Ran the full test suite after every fix: **64 passed**, unchanged from
  before this task. `ruff check src tests` and `mypy` are both clean.

**Areas of concern**
- **Termux caveat (confirmed via web search, not assumed):** `pip install
  ruff` fails on Termux/Android — no compatible wheel, and building from
  source fails too (missing `-lgcc` linking; see
  [astral-sh/ruff#17527](https://github.com/astral-sh/ruff/issues/17527) and
  [astral-sh/ruff#4436](https://github.com/charliermarsh/ruff/issues/4436)).
  **On the phone, install ruff with `pkg install ruff`** (Termux ships a
  prebuilt binary package), not `pip install -e ".[lint]"`. `mypy` has no
  such problem — it's pure Python and installs fine via pip anywhere,
  including Termux. This only affects local dev linting on-device; it does
  not affect running the library or its tests, and CI (GitHub Actions,
  ubuntu-latest) is unaffected since it installs via pip on glibc Linux.

**Not done**
- No pre-commit hook was added (not asked for). Lint runs in CI and on
  demand (`ruff check src tests && mypy`), not automatically on every local
  commit.

## 2026-09-27 — Phase 2: codey_estimator library foundation, built through the pipeline

**What was done**
- Ran the full pipeline end to end for the first time: Architect (opus) → Implementer
  (sonnet) → Code Reviewer (sonnet) → fixup Implementer pass → Verifier (haiku).
  All roles driven this session via `general-purpose` + model override, since
  custom `.claude/agents/*.md` types register on a fresh session scan, not
  mid-session — confirmed by a failed `estimator-architect` dispatch attempt.
- Architect produced the full Phase 2 spec (money/units/calc/dto) with exact
  formulas, worked examples (A/B/B2/B3/C/D), and 11 open questions — resolved
  with the user and recorded as two addenda in `docs/DECISIONS.md`.
- Implementer built `src/codey_estimator/` (`money.py`, `units.py`, `errors.py`,
  `dto.py`, `calc/engine.py`) plus 9 test files and
  `.github/workflows/test.yml`, all stdlib-only. Reported 3 deliberate spec
  deviations (documented in the commit history and DECISIONS.md).
- Code Reviewer found 3 low-severity findings (no money bugs): an error-code
  collision between the genuine `LINE_TYPE_MISMATCH` case and the allowance/fee
  "needs override" case, a purity-test coverage gap (`dto.py` wasn't scanned for
  float literals), and a missing negative test for the `FIXED_PER_UNIT`+`HR`
  validation branch.
- Fixup Implementer pass addressed all 3: new `ALLOWANCE_FEE_REQUIRES_OVERRIDE`
  error code, extended the purity scan to `dto.py`, added the missing test.
- Verifier independently re-ran the suite from a clean install: **64/64
  passing**, exit code 0, no skips/xfails. Confirmed the three fixup tests by
  name.
- Branch strategy changed at the user's request: created `main` (the repo had
  none before — `claude/epic-archimedes-z3luuu` was the only branch and
  GitHub's default), and all commits from this point go straight to `main`, no
  PR review checkpoint. This is the user's explicit choice for a solo project;
  logged so future sessions don't wonder why there's no PR history.
- Added `.gitignore` (build artifacts: `__pycache__/`, `*.egg-info/`, etc.)

**Commits:** `f8a7101` (decisions + pipeline), `db97cac` (spec Q&A), `8fb989b`
(Phase 2 initial implementation), `895770d` (code-review fixups).

**Areas of concern (tracked)**
- **No lint/type-checker configured.** The Verifier confirmed there's no
  `mypy`/`ruff`/similar in `pyproject.toml`, no Makefile, and CI only runs
  `pytest`. Worth adding before the codebase grows past Phase 2 — flagged for
  the user's decision, not added unilaterally.
- D2 scraper risk (see prior entry) still stands, still Phase 11/12, not
  touched this phase.
- CT sales-tax method (D6) still needs accountant confirmation before it
  governs real customer tax calculations — Phase 2's materials-only default is
  a test-case choice, not a tax filing.
- Live DB read-only check (§21) still not run — needed before Phase 3
  (schema/migrations), not before Phase 2.

**Not done (by design)**
- No catalog/, retailers/, ports.py, DB repositories, or any I/O — out of
  scope for Phase 2 per the architect's spec.
- Codey-OS `NEW_ISSUES.md` still doesn't have F1–F6 logged (still read-only
  Codey-OS access this session).

**Next:** Phase 3 (schema & migrations in Codey-OS) is blocked on push access
to Codey-OS and the §21 live-DB check. Until then, Phase 4-adjacent library
work (catalog/normalizer, ManualAdapter, CsvImportAdapter — all still
Codey-Estimator-only, no DB) can proceed through the same pipeline.

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
