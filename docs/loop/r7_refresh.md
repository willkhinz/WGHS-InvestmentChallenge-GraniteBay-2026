# Agent brief r7-refresh — does `run_all.py --refresh` work before the Final Report needs it?

**Read first:** `docs/loop/COMMON.md` (standing rules: they apply in full, except rule 6's "do not
re-download": this brief is about downloading), then `README.md` "Configuration" and the docstring of
`scripts/run_all.py`.
**Your worktree:** branch `r7-refresh`, based on `improve`. Already created for you; you are in it.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`. Your context is about 200K tokens: pipe long outputs through
`tail -40` and keep notes in your findings doc as you go.

## 0. What is settled
The committed reports are as of the Oct 20, 2026 curve and Sep 30, 2026 month-end. The team will
refresh before the Final Report by changing `config/asof.yaml` and running `run_all.py --refresh`.
Nobody has tried it since the audit. **Do not commit any downloaded data, any changed report or any
change to `config/`; this is a dry run.**

## 1. Tasks
1. Record `git status --short` (should be clean). Change `config/asof.yaml` to the most recent
   Treasury curve date that has published data (try yesterday's and today's business date) and the
   latest month-end with data (keep the existing month-end if the new one is not out yet). Note what
   you set.
2. Run `PYTHONPATH=<worktree>/src PY scripts/run_all.py --refresh 2>&1 | tail -60`, once, in the
   foreground. It downloads from Treasury, FRED, the Federal Reserve and Yahoo. Record every source
   that failed (the script prints "stale: ...") and every script that exited non-zero, with the last
   20 lines of its error.
3. If it ran: record the new IPS median, 5th percentile and real median from
   `reports/report_numbers.json`, and how many figures `scripts/doc_numbers.py` says are stale.
4. For each failure, find the cause and describe the smallest fix (file:line). Do not apply fixes to
   `src/` or `scripts/`; the planner will.
5. Write `docs/loop/r7_refresh_findings.md` (dates set, sources refreshed or stale, scripts failed,
   new headline, doc figures stale, each fix proposed). Then restore the tree: `git checkout -- .` and
   `git clean -fd data/ reports/` so only your findings doc differs from `improve`. Commit it.

## Acceptance criteria
- [ ] `git diff improve --stat` shows only `docs/loop/r7_refresh_findings.md`.
- [ ] Every failed source and failed script is listed with its error and a proposed fix.
- [ ] The headline figures you report are copied from the refreshed `report_numbers.json` before restoring.

## Not yours to decide
Whether to adopt refreshed data, and any fix.
