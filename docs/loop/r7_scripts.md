# Agent brief r7-scripts — do the scripts outside run_all still run after today's input validation?

**Read first:** `docs/loop/COMMON.md` (standing rules: they apply in full), then this brief.
**Your worktree:** branch `r7-scripts`, based on `improve`. Already created for you; you are in it.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`.

## 0. What happened, and what is settled
Between 16:48 and 18:17 on 2026-10-22 another agent added input validation across `src/lgm/esg.py`,
`engine.py`, `strategies.py`, `curve.py`, `ladder.py` and `instruments.py` (about 30 commits; see
`git log f6e0613..b8c0036`). `scripts/run_all.py` still runs every script it lists and leaves every
report byte-identical, and 393 tests pass. **Settled: the model's numbers.** Do not change any
default or any report that run_all writes.

## 1. The question
Eleven scripts are not run by `run_all.py`, so nothing has checked that the new validation accepts
what they pass in:
`esg_garch_conditional, esg_variants, fx_drift_study, policy_search, rate_tails, rate_tails_impact,
round6_waterfall, taiwan_costs, taiwan_validation, taiwan_variants` (and `run_all` itself, already fine).
A check that rejects a legitimate input (for example a zero volatility in a sensitivity case, a
scalar where a vector used to be accepted, a GARCH tuple, a continuation state, a matured instrument)
breaks one of these.

## 2. Tasks, in order
1. For each of the ten scripts, run it in the cheapest mode that still exercises its code path, in the
   foreground (`PYTHONPATH=<worktree>/src PY scripts/<name>.py ...`). Read each script's docstring and
   `__main__` first; use a small scenario count argument where it takes one. `policy_search.py --grid
   --workers 4` takes about 4 minutes and is worth running in full (it is the policy grid the docs
   quote). `round6_waterfall.py` takes about 4 minutes. Do not run anything that downloads data
   (`--refresh`, `--rescreen`): if a script can only run by downloading, record it as "needs network"
   and skip it.
2. For every failure, find the cause. If it is a validation check rejecting an input the script
   legitimately uses, make the smallest fix in `src/` that accepts it (keep rejecting genuinely bad
   input), and add a regression test in the matching `tests/test_*.py` that fails before your fix.
   If the script itself is stale (it calls an API that changed long before today), fix the script
   instead and say so. One commit per fix.
3. After all fixes: `PYTHONPATH=<worktree>/src PY -m pytest -q`, `PY -m pyflakes src scripts tests`,
   `PYTHONPATH=<worktree>/src PY scripts/run_all.py`, and confirm `git status --short reports/` shows
   no modified pre-existing report (except files the ten scripts themselves rewrite: list those, and
   do not commit their changes unless the change is only a re-run of identical numbers).
4. Write `docs/loop/r7_scripts_findings.md`: one row per script with the command you ran, the
   outcome (ran / failed and fixed / failed, not fixed / needs network), wall time, and the commit
   that fixed it. Commit it.

## You own
`src/lgm/*.py` (only to loosen a check that wrongly rejects valid input), `tests/`, the ten scripts,
`docs/loop/r7_scripts_findings.md`. Nothing else.

## Acceptance criteria
- [ ] All ten scripts attempted; each has a row in the findings doc with its outcome and command.
- [ ] Every fix has a regression test that fails without it.
- [ ] Final pytest line pasted verbatim in your report; pyflakes clean.
- [ ] `run_all.py` leaves every pre-existing report byte-identical.
- [ ] One commit per fix, plus the findings commit.

## Not yours to decide
Whether to remove a validation check entirely, change a default, or change any reported number.
If the only fix you can see does one of these, report `question` with the details.
