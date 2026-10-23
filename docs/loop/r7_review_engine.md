# Agent brief r7-review-engine — review another agent's input validation in `src/lgm/engine.py src/lgm/strategies.py` (read-only)

**Read first:** `docs/loop/COMMON.md` (standing rules: they apply in full), then this brief.
**Your worktree:** branch `r7-review-engine`, based on `improve`. Already created for you; you are in it.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`.
**Your context window is limited (about 200K tokens).** Read the diff file by file and function by
function (`git diff f6e0613 b8c0036 -- <file>`, or `-U3` hunks), not whole files at once, and keep
notes in your findings doc as you go.

## 0. What is settled
Between 16:48 and 18:17 on 2026-10-22 another agent (Codex) added input validation to `src/lgm/engine.py src/lgm/strategies.py`
(`git log f6e0613..b8c0036 -- src/lgm/engine.py src/lgm/strategies.py`). All 393 tests pass and `scripts/run_all.py` leaves every report
byte-identical, so the default paths work. **This is a review only: do not edit anything under
`src/`, `scripts/` or `tests/`.** The planner decides which findings to fix.

## 1. The question
Is each new check right? For every check added, decide whether it:
(a) rejects input that some caller legitimately passes (search `scripts/` and `src/` for callers),
(b) lets through input it claims to reject, (c) changes behaviour for valid input (anything other
than raising an error), (d) gives an error message that would mislead, or (e) is fine.
Pay special attention to: the State/Scenarios validation in `run`, the January 2027 FX and Taiwan-cost baselines carried into nested runs (commit 0db8b9f), `conditional_2031` and `conditional_2031_band`, and Strategy field checks. Also measure the cost: time one `engine.run` of the IPS on 20,000 scenarios (seed 11, as `scripts/report_numbers.py` builds them) with today's code and with the code at f6e0613 (`git show f6e0613:src/lgm/engine.py` etc. into a temporary package directory outside the repo, put first on PYTHONPATH). Report both times, median of 5 runs each.

## 2. Tasks
1. Go through the diff hunk by hunk. For every finding in (a)-(d), write a minimal reproducer as a
   function in `docs/loop/r7_review_engine_repro.py` (plain Python, runnable with
   `PYTHONPATH=<worktree>/src PY docs/loop/r7_review_engine_repro.py`, printing one line per finding:
   expected vs actual). A finding without a reproducer that runs is not a finding.
2. Write `docs/loop/r7_review_engine_findings.md`: one row per finding (file:line, category a-d,
   what happens, the reproducer's function name, suggested fix in one sentence, severity: affects a
   real caller / affects only hypothetical input). Then one line listing the hunks you checked and
   found fine (category e), so the planner knows nothing was skipped.
3. Commit both files. Commit after task 1 as well, in case your run is cut short.

## Acceptance criteria
- [ ] Every hunk of `git diff f6e0613 b8c0036 -- src/lgm/engine.py src/lgm/strategies.py` is either a finding or listed as fine.
- [ ] Every finding has a reproducer that runs and prints its expected vs actual result.
- [ ] Nothing under `src/`, `scripts/` or `tests/` changed (`git diff improve --stat` shows only your two files).

## Not yours to decide
Whether and how to fix any finding.
