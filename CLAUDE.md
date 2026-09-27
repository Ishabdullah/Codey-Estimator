# Codey-Estimator — Governance & Agent Pipeline

This repo is a pure-Python, stdlib-only domain library (`codey_estimator`) for
Restoricon, LLC's estimating system. See `docs/ARCHITECTURE_PLAN.md` for the
full design and `docs/DECISIONS.md` for the answered D1–D11 decisions — read
both before touching anything here. `PROJECT_LOG.md` gets a new entry after
every change, reverse-chronological, no exceptions.

## Constraints that never change

- **stdlib only** in `src/codey_estimator/`. No `sqlite3` import, no HTTP, no
  third-party packages in `calc/`, `money.py`, `units.py`, `dto.py`. Adapters
  (`retailers/`) are the only place I/O and third-party deps are allowed.
- **Everything must run in Termux on the user's phone** and in GitHub Actions
  identically. Before recommending any dependency, confirm it has no native
  build step that fails on Termux/Android.
- **Money is integer cents** in every new table/dataclass (D3). Rounding is
  `ROUND_HALF_UP` per component, then summed (plan §15).
- **The calc engine is pure and deterministic.** Same input → same output,
  forever, versioned via `CALC_ENGINE_VERSION`. No wall-clock, no randomness, no
  I/O inside `calc/`.
- **Customer-visible data only ever passes through an allow-list serializer**
  (`CustomerEstimateView`). Never ship a "zero out these fields" approach — that
  was flaw F1 in the audit. Every DTO change needs the forbidden-keys test
  updated.
- **No code is "done" without tests that pass**, and a log entry. A bug fix
  doesn't get scope creep; a calc change doesn't get an unrelated refactor.

## The pipeline

This session (whoever is driving it) is the **Orchestrator**. It never writes
production code directly for anything beyond a trivial one-line fix — it hands
work to the right agent and reviews what comes back. Four roles, four models:

| Role | Agent file | Model | Job |
|---|---|---|---|
| Architect | `.claude/agents/estimator-architect.md` | opus | Turns a phase/task from the plan into a concrete, file-by-file spec: exact function signatures, data shapes, edge cases, and the worked numeric examples tests must assert against. Never writes implementation code, only the spec + test fixtures/examples. |
| Implementer | `.claude/agents/estimator-implementer.md` | sonnet | Writes the code and the tests exactly to the architect's spec, on this branch. Runs the test suite itself before handing back. |
| Code Reviewer | `.claude/agents/estimator-code-reviewer.md` | sonnet | Reviews the implementer's diff against the spec, this file's constraints, and the architecture plan. Never fixes code itself — reports findings back to the orchestrator, who either sends it back to the implementer or overrides with the user's sign-off. |
| Verifier | `.claude/agents/estimator-verifier.md` | haiku | Runs the actual test suite / lint / any live check fresh, from a clean checkout state, and reports pass/fail with the literal command output. Cheap, fast, no judgment calls — just "did it actually pass." |

**Flow for every task:**
1. Orchestrator picks the next task off the plan (`docs/ARCHITECTURE_PLAN.md`
   §29/§32) and gives the Architect the task + relevant decisions from
   `docs/DECISIONS.md`.
2. Architect returns a spec. Orchestrator sanity-checks it against the plan and
   decisions, and — for anything touching money/tax/RBAC/schema — surfaces it to
   the user before implementation starts.
3. Implementer codes + writes tests + runs them locally, reports back.
4. Code Reviewer reviews the diff. Findings go back to the Implementer for
   anything not cosmetic; the Orchestrator only overrides a reviewer finding
   with the user's explicit sign-off.
5. Verifier re-runs the suite from scratch (not trusting the implementer's own
   "tests pass" claim) and reports literal output.
6. Orchestrator updates `PROJECT_LOG.md` (what changed, key findings, what
   wasn't done and why, areas of concern) and commits.

No step is skipped because a task "looks small." Rule 4 in Codey-OS's own
pipeline (schema/RBAC/auth/lifecycle changes need explicit reviewer sign-off)
applies here too, and is stricter for this repo's Phase 3+ work since it
touches a live production SQLite DB on the user's phone.

## Termux / delivery reminder

The user runs this on Termux on an S24 Ultra. Any code handed to them directly
(not via a PR) must be copy-paste-ready into their home directory, and any
setup command given to them must be one that actually works in Termux (no
`apt`-only packages without checking `pkg` availability first, no tools that
need a GUI or a browser Termux can't run).
