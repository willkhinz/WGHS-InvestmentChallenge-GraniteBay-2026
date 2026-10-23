# Agent brief r7-te — the core's tracking error, corrected for what the out-of-sample test found

**Read first:** `docs/loop/COMMON.md` (standing rules: they apply in full), then `docs/MODEL.md`
"Part 1" (the paragraph on shock correlations) and "Part 2a" (the core summary with its 1.30%
tracking error), then `scripts/corr_shrink_oos.py`.
**Your worktree:** branch `r7-te`, based on `improve`. Already created for you; you are in it.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`.

## 0. What is settled
`reports/corr_shrink_oos.csv` shows the generator's correlation estimate (zero target) understates the
core's active risk against the market out of sample: by about 11% over the next 3 years and 19% over
6 years (column `active_risk_bias`, a log error, candidate "zero target, LW intensity"). The model and
its defaults stay as they are.

## 1. Tasks
1. New script `scripts/tracking_error_oos.py`: read `reports/report_numbers.json` (core
   `tracking_error`) and `reports/corr_shrink_oos.csv`; for each panel (7 or 9 funds) and horizon (36
   or 72 months) print the tracking error scaled by `exp(-active_risk_bias)` for the zero-target row.
   Also print the same for the market-volatility bias (`market_vol_bias`) applied to the core's
   `volatility`, so the two corrections can be compared. Write `reports/tracking_error_oos.csv`.
2. `tests/test_tracking_error_oos.py`: with a hand-made CSV where the bias is log(0.9), the scaled
   tracking error is the original divided by 0.9.
3. `docs/loop/r7_te_findings.md`: the table, and two sentences on what it means for how the core's
   1.30% tracking error should be quoted. Every number from the script. Commit after each task.

## You own
`scripts/tracking_error_oos.py`, `reports/tracking_error_oos.csv`, `tests/test_tracking_error_oos.py`,
`docs/loop/r7_te_findings.md`. Nothing else.

## Acceptance criteria
- [ ] Script runs in seconds, writes the CSV; tests pass; final pytest line pasted verbatim.
- [ ] `run_all.py` leaves every pre-existing report byte-identical.

## Not yours to decide
Whether MODEL.md changes, and whether the script joins run_all.
