# Agent brief r7-episodes — named historical episodes, right after the lock

**Read first:** `docs/loop/COMMON.md` (standing rules: they apply in full), then `docs/MODEL.md`
("What the numbers rest on", "Part 1", "Policy study"), then this brief.
**Your worktree:** branch `r7-episodes`, based on `improve`. Already created for you; you are in it.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`.

## 0. What is settled
The headline IPS numbers (median $196,989, 5th percentile $146,102; `reports/report_numbers.json`) and
the 184-path historical replay (`scripts/validate_model.py`, `backtest()`; `reports/backtest.csv`).
Do not change either, or any `src/` default.

## 1. The question
Co-sponsors understand "what if 2008 happened just after we locked the payments?" better than a
percentile. The replay already runs real six-year paths, but nobody has pulled out the named
episodes. Build that table.

`lgm.backtest.history_paths(tickers, recentre=...)` returns `(Scenarios, starts)`: path `j` replays
real history from month `starts[j]`, mapped onto the model's timeline, whose month 0 is November 2026
and whose January 2027 lock is month 2 (`engine.M_2027`). A path is available only if 74 months of
history follow its start, so the last start is July 2020.

## 2. Tasks, in order
1. New script `scripts/episode_stress.py`. Build the core as `scripts/report_numbers.py` does
   (`build_core()`, IPS with `region_weights=tuple(core["w_bl"])`, `EngineConfig(eq_er=...)`), and the
   history paths both as they happened (`recentre=None`) and re-centred on the BL expected returns
   (`recentre=core["table"]["bl_geo_total"].values`), exactly as `validate_model.backtest()` does.
2. Episodes: for each, choose the path whose start puts the episode's first bad month at model month
   3 (February 2027, just after the lock): the 2008 financial crisis (first bad month September 2008),
   the 2011 euro crisis (August 2011), the 2015-16 China and oil sell-off (August 2015), COVID
   (February 2020). Also report the replay's single worst path and its start date. If an episode's
   start month is not available, say so in the table; do not substitute another date silently.
3. For each episode and both path sets, report: the January 2033 facility, the 85% contribution, the
   floor bought in January 2031 (`floor_2033`), whether every payment is funded, and the real facility
   in Taiwan terms (`facility_real_tw2027`); plus the core's cumulative equity return over the six
   years and its worst 12 months. Put the simulated median and 5th percentile next to them for
   comparison (from the same run as `report_numbers.json`: 20,000 scenarios, seed 11).
4. The 2022 stock-and-bond sell-off has no full six-year path yet. Do not fabricate one. Report it as
   unavailable, and add one row that applies only its first 12 months (Jan-Dec 2022 equity, rate and
   FX moves) as a stress: take the simulated scenarios, replace their months 3-14 shocks with the
   2022 history, and report the median facility of those scenarios. Explain exactly how you spliced it
   in the findings doc; if you cannot do it cleanly through the `Scenarios` arrays, report `question`
   for this item instead and finish the rest.
5. Write `reports/episode_stress.csv` and `docs/loop/r7_episodes_findings.md` (the table, one
   paragraph per episode on what happened to the facility and why). Every number comes from the
   script. Add `tests/test_episode_stress.py` checking that the chosen start dates put each episode's
   first bad month at model month 3, and that the IPS funds every payment on every episode path (the
   replay found 100% funded). Commit after each task.

## You own
`scripts/episode_stress.py`, `reports/episode_stress.csv`, `tests/test_episode_stress.py`,
`docs/loop/r7_episodes_findings.md`. Nothing else (do not edit `run_all.py`, MODEL.md or VALIDATION.md).

## Acceptance criteria
- [ ] Script runs in under 2 minutes and writes the CSV; every number in the findings doc is in it.
- [ ] Four named episodes plus the worst path, both path sets; 2022 handled as task 4 says.
- [ ] Tests pass; final pytest line pasted verbatim; pyflakes clean.
- [ ] `run_all.py` leaves every pre-existing report byte-identical.

## Not yours to decide
Whether the table goes into MODEL.md or the IPS, and any change to the strategy.
