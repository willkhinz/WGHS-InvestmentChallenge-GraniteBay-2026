# Improvement loop log

A planner (Claude) writes briefs in `docs/loop/`, a worker (Gemini via `agy`) implements each one on its
own branch and worktree, and the planner verifies the result before merging it into `improve`.
Nothing here is adopted into the headline numbers until the planner has checked it.

Baseline (branch `improve` at the start of round 1, = `origin/core-model` c76a18b):
- `python -m pytest`: 61 passed.
- `python scripts/run_all.py`: about 27 s; regenerates every file in `reports/` byte-identically.
- IPS median facility $197,910, 5th percentile $147,375 (`reports/report_numbers.json`, `plan`).

## Round 1 (dispatched 2026-10-21)
| Thread | Branch | Brief | Question |
|---|---|---|---|
| lgm-esg | r1-esg | `docs/loop/r1_esg.md` | Does the scenario generator understate risk by treating expected returns as known and volatility as constant? |
| lgm-policy | r1-policy | `docs/loop/r1_policy.md` | Is the IPS policy (lock all, 60/40, 60% floor in 2031) close to the best in a wider family, including dynamic rules? |
| lgm-taiwan | r1-taiwan | `docs/loop/r1_taiwan.md` | Replace the assumed 4%/1.5% Taiwan building-cost inflation with data |

### Round 1 results (verified by the planner, all three merged into `improve`)
After merging: 77 tests pass; `run_all.py` leaves every pre-existing report byte-identical. Nothing
was switched on by default.
- **r1-taiwan.** Official DGBAS construction cost index 1991-2026 and Taiwan CPI. Checked by
  re-downloading `ccispl.ods` and `cpispl.ods` from DGBAS: SHA-256 identical to the committed files.
  The index is persistent (monthly AR(1) 0.60), and 72-month growth spans -0.3% to +44.1% (p5-p95)
  against 19.1%-34.4% under the 4% assumption. Gap: the proposed AR(1) starts at the long-run mean,
  but the latest reading is +7.3% y/y. Round 2 measures the effect of the starting state.
- **r1-policy.** Opt-in glide path, floor timing and ratchet; 3,456 policies, all 100% funded. The
  IPS is within $2.2k of the best CE at gamma 4 and $2.4k at gamma 2; the median "winner" (+$12.7k)
  cuts p5 by $38.7k. Bug found by the planner: `conditional_2031` ranks scenarios on growth assets
  only, so for policies that floor before 2031 the "median 2031 scenario" is arbitrary (the reported
  $234k secured for P2485 is that artifact). Fixed in round 2.
- **r1-esg.** Opt-in expected-return uncertainty (calibrated from forecaster dispersion) changes the
  facility by under $0.5k at any percentile: off. Opt-in GARCH volatility clustering lowered the
  20-80 band's historical coverage from 81% to 72%, but every history path started at the
  unconditional variance, which removes GARCH's only advantage for the 2031 quote. Round 2 tests it
  with the filtered state.

## Bridge change (2026-10-21)
At the user's request the loop skill gained a permanent memory watchdog: at yellow or red system
memory pressure the daemon stops every worker and holds delivery; the planner fixes the cause and
releases at green. COMMON.md rule 11 asks workers to keep peak memory under about 2 GB.

## Round 2 (dispatched 2026-10-21)
| Thread | Branch | Brief | Question |
|---|---|---|---|
| lgm-taiwan | r2-taiwan | `docs/loop/r2_taiwan.md` | Persistent Taiwan cost process from today's 7.3% state; real cost paths in the replay |
| lgm-esg | r2-esg | `docs/loop/r2_esg.md` | Does GARCH help the 2031 quote when it starts from the filtered variance? |
| lgm-policy | r2-policy | `docs/loop/r2_policy.md` | Fix the 2031 scenario ranking; re-rank with a value on the 2031 promise |

### Round 2 results (verified by the planner)
- **r2-esg (merged).** The GARCH variance filter recovers simulated variance paths exactly; today's
  state is 0.70 of the long-run variance. Starting each historical path from its own filtered 2031
  variance does not rescue GARCH: the 20-80 band's coverage is 73% (re-centred) against 81% for the
  baseline, and it ties or loses in every regime tercile (calm 89% vs 97%, normal 57% vs 72%,
  turbulent 74% vs 74%). The reason is structural: monthly persistence of 0.87 has a 5-month
  half-life, so 96% of what is known in Jan 2031 has washed out by 2033. GARCH stays off.
  Side observation (thin evidence, about 4 independent windows): after turbulent 2031 starts,
  outcomes landed above the 80th percentile 25-38% of the time, which looks like post-crash rebounds.
- **r2-policy (merged).** The ranking fix removes the $234k artifact: P2485 now secures $195.7k,
  in line with its $193.0k median floor. The planner then simplified the fix so every policy ranks on
  total Jan 2031 wealth before that month's floor move (identical for 2031-floor policies, and
  correct for ratchets too); `policy_search_top.csv` was generated before this change.
  On the full grid the IPS is on the efficient frontier: only three ratchet variants beat it on
  median, p5, CVaR5 and the 2031 secured amount at once, each by under $100. The real choice it
  leaves is a preference: P2361 (40% equity, 100% floor in 2031) gives up $3.9k of median for
  +$8.6k at p5, +$9.9k CVaR5, the same CE at gamma 4, and $195k secured in 2031 instead of $118k.

## Round 3 (dispatched 2026-10-21, while r2-taiwan is still running)
| Thread | Branch | Brief | Question |
|---|---|---|---|
| lgm-esg | r3-strips | `docs/loop/r3_strips.md` | Real-world reserve with no reinvestment assumption: STRIPS and December maturities |
| lgm-policy | r3-robust | `docs/loop/r3_robust.md` | Does the policy choice survive pessimistic returns, vol, tails and rate shocks? |
| lgm-taiwan | r3-taiwan | `docs/loop/r3_taiwan.md` | Refit the Taiwan cost process on monthly changes; validate unconditional and conditional |

### r2-taiwan (merged, specification not adopted)
Plumbing merged: opt-in persistent process, state pass-through to `conditional_2031`, real DGBAS
cost paths in the historical replay (real median $169.9k against $155.1k with the 4% line, on the
same 184 paths). The specification is wrong: `tw_cost_phi = 0.97` is the AR(1) of the overlapping
12-month rate, which i.i.d. monthly noise already pushes to 0.92 (planner's simulation, 0.916), and
it is then applied to the instantaneous rate, giving a 72-month p5-p95 of -15% to +66% against
history's -0.3% to +44%. Monthly changes have autocorrelation 0.60 / 0.30 / 0.03 at lags 1 / 2 / 12,
and the k-month dispersion is 1.7x the i.i.d. scaling at every horizon from 12 to 72 months:
persistence lasts months, not years. So "the starting state dominates" is unproven. Round 3 refits.

### r3-robust (merged)
Seven shortlisted policies x 11 assumption shifts, common random numbers. Maximum regret across shifts
(gap to the best shortlisted policy under each shift):

| Policy | median | p5 | CVaR5 | CE gamma 4 | CE gamma 8 | secured 2031 |
|---|---:|---:|---:|---:|---:|---:|
| IPS (60/40, 60% floor 2031) | 39.6k | 16.6k | 19.6k | 6.8k | 12.5k | 92.1k |
| P2305 (40/60, no floor) | 41.3k | 9.7k | 10.9k | 4.4k | 6.8k | 231.2k |
| P2333 (40/60, 60% floor 2030) | 49.0k | 2.7k | 2.9k | 9.5k | 1.8k | 93.3k |
| P2361 (40/60, 100% floor 2031) | 50.3k | 4.3k | 4.9k | 11.1k | 3.7k | 0.8k |
| P2485 (40 to 0, 100% floor 2030) | 55.4k | 2.2k | 1.5k | 14.9k | 5.7k | 4.8k |
| P1729 (70/30, no floor, 75% lock) | 23.5k | 34.7k | 39.6k | 17.2k | 31.2k | 231.2k |
| P0964 (all equity, 50% lock) | 10.4k | 64.5k | 73.3k | 49.0k | 117.3k | 231.2k |

No policy is robust on every objective; the IPS is in the middle on each. Under the lowest-forecast
equity returns (-2.8 points), every 40%-equity policy beats the IPS on median as well.
Found in review: under `t_dof = 3`, one scenario's 5-year rate falls about 4.5 points in the two
months before the 2027 lock and ends $450 short for every policy, so all CE values in the
`tails_tdof3` rows are that artifact (about $27). Cause: the common Student-t mixing variable gives
rate shocks fat tails that history does not have (5-year zero, monthly change: history excess
kurtosis 0.6, worst month -0.81 pp; model at t5 worst month -1.99 pp; Gaussian rates -1.22 pp).

## Round 4
| Thread | Branch | Brief | Question |
|---|---|---|---|
| lgm-rates | r4-rates | `docs/loop/r4_rates.md` | Give rate shocks their own (thinner) tails, keep crash correlations, measure the effect |
| lgm-taiwan | r4-fx | `docs/loop/r4_fx.md` | USD/TWD drift: random walk vs interest-differential forward, tested on TWD history |

### r3-strips (merged, with a correction)
Real Public.com quotes for the ten Nov-15 STRIPS 2032-2041 and the 3.875% Dec-31-2032 note; the
planner re-fetched one page and found the same quote. Quotes sit 1-11 bp from the model's zero curve.
Correction: the LP prices at the quoted mid, but the retail half-spread is 1.5-1.8%. At the ask the
STRIPS ladder costs +1.54% over zero-coupon value (reported: -0.06%), against +3.70% for the WInS
ladder at 0% reinvestment and +1.82% at 3%. So outside WInS a reserve that needs no reinvestment
assumption costs about what the WInS ladder costs when it assumes 3%: roughly $6k cheaper than
making the WInS ladder certain. Idle cash falls from 197 to 47 days. Institutional spreads are far
tighter (the worker cites 2-5 bp). Zero-coupon bonds create taxable imputed interest for a taxable owner.

### r3-taiwan (merged)
Monthly AR(2) (phi 0.655, -0.094) reproduces the data's lag-1 and lag-2 autocorrelations exactly
(planner's check: 0.598, 0.298) and the variance-ratio profile from 1 to 72 months (72 months: 13.7%
model, 12.7% history). Conditional check: 95.5% coverage over 66 high-inflation start windows (4
independent episodes). Today's +7.3% state moves the real median by -$0.2k; the long-run drift moves
it by up to $11k. Real median: $167.4k at the full-sample drift (2.85%), $169.6k at the 20-year
drift, $158.6k at the 10-year drift, against $156.8k under the old 4%/1.5% assumption.

## Gemini quota outage (2026-10-21 22:37)
Both round-4 runs stopped on "Individual quota reached ... Resets in 40h" (the Google account's
Antigravity limit). At the user's instruction the planner finished round 4 itself and cancelled the
two queued briefs in the bridge so Gemini does not redo them when the quota resets.

### r4-rates (merged; Tasks 1-3 by Gemini, findings by the planner)
Opt-in per-block shock tails (`rate_dof`, `rate_shared`, `infl_dof`, `fx_dof`). Gaussian rate shocks
reproduce history's worst 0.1% of monthly 5-year moves (-0.80 pp both) and remove the 2-5 point
jumps; t14 matches history's kurtosis. Crash-month stock/rate co-movement (history 0.39) is absent in
every variant including today's (0.03), so nothing is lost. The worker's MLE degrees of freedom for
the rate series are pinned at the search bound of 2 and contradict the moment estimates (7-14); not
used. Headline: median -$64, worst scenario $73.7k -> $83.7k, CE gamma 8 +$1.1k; the t3 stress CE
artifact disappears. Merge conflict in `ESGParams` (with r3-taiwan's fields) resolved by keeping both.

### r4-fx (merged; data and forecast study by Gemini, forward checks, variants and findings by the planner)
CBC money-market rates 1987-2026 (planner re-downloaded: 472/472 rows identical) and, added by the
planner, the CBC's actual USD/TWD forward rates 1991-2026. The forward premium puzzle holds for TWD:
Fama slopes 0.02 / 0.09 / 0.17 at 12 / 36 / 72 months and -0.09 on the actual 6-month forward, all
rejecting an unbiased forward; the random walk has the lowest error at 12 and 36 months. Real median
(AR(2) Taiwan costs, full-sample drift): $167.4k at zero FX drift, $145.9k at the forward (-2.28%/yr).
The FX assumption moves the real median twice as much as the Taiwan cost drift.

## Round 5: integration (planner, branch `r5-integrate`, merged into `improve` on 2026-10-22)
Data-backed fixes switched on for the headline numbers (`growth.scoring.esg_params`; the former team's
`cs_team` profile is untouched):
- Gaussian rate shocks (`rate_dof="gaussian"`); equities, inflation and FX keep Student-t(5).
- Taiwan building costs: fitted AR(2) at the 2.85% full-sample drift from the Aug/Sep 2026 readings;
  the historical replay uses the real DGBAS paths (`history_paths(real_tw_cost=True)` by default).
- New: the 2031 "typical world" quote is the median over 21 scenarios between the 45th and 55th
  percentile of Jan 2031 wealth (`engine.conditional_2031_band`). Over three seeds and two rate-tail
  settings the single-scenario floor ranged $114.0k-$120.0k; the band floor $116.8k-$118.7k
  ($117.4k-$117.7k with Gaussian rates).
Headline after integration: median $197,846 (was $197,910), p5 $147,396 (+$22), CVaR5 $136,629 (+$415),
real median $167,359 (was $156,834), typical secured contribution in 2031 $99.8k (was $100.7k), 80%
contribution range $159.9k-$175.1k (was $161.3k-$176.6k). 106 tests pass; `run_all.py` reproduces
the committed reports. `docs/MODEL.md` and `docs/VALIDATION.md` updated.
Not switched on, pending the user: the policy (IPS vs the 40%-equity alternatives), a STRIPS reserve
outside WInS, FX hedging, and the choice of Taiwan cost drift.

## Round 6: planner alone, no agents (2026-10-22, on `improve` after merging r5-integrate)
At the user's instruction the planner continued without Gemini or subagents. One commit per item:
- **Commissions compound** (`EngineConfig.compound_costs`): fees grow at the invested assets' return
  as if paid when incurred, instead of being subtracted at face value in 2033. IPS median -$275.
- **Doc consistency checker** (`scripts/doc_numbers.py`, `tests/test_doc_numbers.py`): 27 figures in
  MODEL.md and VALIDATION.md are read from the reports and must match; `--fix` rewrites a stale figure
  when its number-generalised pattern appears exactly once. Built after the planner itself mis-quoted a
  CE gap in MODEL.md.
- **Policy search rerun** (`--grid`, 3,456 policies): IPS within $2.2k of the best CE at gamma 4
  (rank 546), every max-regret figure within $0.6k of the earlier run. Conclusions unchanged.
- **Satellite selection bias, out of sample** (`scripts/satellite_oos.py`): the screen re-run at four
  2023 dates against 300 random 35-name baskets each. Selection makes in-sample volatility look about
  12% too low and the low-risk picks were no calmer than random afterwards. With the corrected risk
  (vol 15.1% -> 16.9%, beta 0.89 -> 0.99; `scripts/satellite_risk_sensitivity.py`) the commission-free
  satellite still adds about +$0.5k at the median but its 5th percentile turns slightly negative; with
  WInS's $25 commissions it loses about $3.1-3.3k at the median either way. Verdict unchanged.
- **Taiwan cost growth vs USD/TWD** (`scripts/taiwan_fx_corr.py`): -0.18 to -0.33 over 12- to 72-month
  changes, 2000-2026; set to -0.25. Real 5th-95th range $113.5k-$247.3k -> $111.3k-$251.6k, median
  unchanged.
- **Rate persistence bias** (`calibrate.kendall_corrected`): OLS AR(1) over 393 months is biased low;
  0.984/0.979/0.954 -> 0.994/0.989/0.964. 74-month 5-year change sd 1.26 -> 1.61 points (history 1.84);
  10-year 5th-95th change -2.8/+2.8 (history -2.7/+2.4). IPS median unchanged.
Headline now: median $197,593, p5 $147,153, CVaR5 $136,262, real median $167,008, typical secured 2031
contribution $99.8k, 80% contribution range $160.3k-$175.5k. 109 tests pass; docs checked by script.

### Round 6, continued (same day, planner alone)
- **Stock-rate correlation** (`scripts/stock_rate_corr.py`): the calibration window's -0.16 averages
  +0.41 (2017-2021) and -0.47 (2022-2026); over 1994-2026 the sign follows inflation. Rescaling the
  equity x rate block to each regime moves the IPS median under $0.2k and its 5th percentile by at
  most $1.6k; the open-liability 60/40 swings by $20k. Default kept.
- **Crash co-movement** (`scripts/crash_comovement.py`): r4's 0.39 crash correlation rests on 12
  months (p = 0.11); crash months show no average flight to quality. Gap closed, no copula needed.
- **USD/TWD and equity mean reversion** (`scripts/fx_horizon.py`, `scripts/equity_horizon.py`,
  `calibrate.variance_ratio_test`): neither is significant against a resampled i.i.d. null of the
  same length (USD/TWD 2000-2026 74-month p = 0.14, and trending from 1983; US stocks since 1926
  p >= 0.26). Random walk and i.i.d. equity shocks kept.
- **Ladder premium vs rates** (`scripts/ladder_premium.py`): the LP premium rises 0.57 points per
  point of rate under the fixed 3% reinvestment assumption. Opt-in `kappa_rate_slope`; IPS effect
  +$27 median, +$0.5k p5. Constant 1.8% kept (slightly cautious).
- **J.P. Morgan 2027 LTCMA** (Oct 19, 2026; US 7.5%, EAFE 7.7%, EM 7.1%, read from the report's USD
  table) replaces the 2026 edition: median -$123. Vanguard's latest run (Jun 30, 2026) is current.
- **Sale tickets at settlement** (`EngineConfig.sell_at_settlement`): the contribution is paid in
  cash, so each fund still held is sold once in Jan 2033. IPS -$225; satellite -$875 more (break-even
  alpha 4.1 -> 5.3 points).
- **ESG refactor**: tail-mixing branches folded into helpers, output bit-for-bit identical.
- **Pipeline and docs**: `run_all.py` now regenerates the nine studies the docs quote and ends with
  `doc_numbers.py` (72 s, byte-identical reports). The checker grew from 27 to 70 figures; on the
  way it caught over a dozen stale figures or sentences, including "the six extra funds cost the same in
  commissions" (no longer true) and the 2031 band calibration (80.4% -> 81.5%).

### Round 6, afternoon (planner alone)
- **Taiwan cost drift in real time** (`scripts/taiwan_drift_study.py`): from every month-end
  2001-2020, the average since 1991 forecast the next 74 months' cost growth better than the trailing
  ten-year average (RMSE 0.167 vs 0.222) in each of the four five-year blocks. Supports the headline's
  2.85%; the ten-year drift would cost $8.7k of real median (now computed, `fx_variants`).
- **FX hedge frontier** (`scripts/fx_hedge_frontier.py`): on the random walk every hedge ratio lowers
  both the real 5th percentile and the median; if the forward were unbiased, hedging is about free in
  the median and lifts the 5th percentile by at most $4.2k. Decision support for the client.
- **Policy grid rerun** after the day's changes: IPS within $2.2k of the best CE at gamma 4 (rank 533
  of 3,456); max regrets within $1.0k. Conclusions unchanged. `policy_robust --summary` now says it
  reads the existing CSV (it had silently skipped the recompute once).
- **"What the numbers rest on"** table at the top of MODEL.md, generated from the reports: three things
  move the outcome by more than $10k (the rate level at the 2027/28 locks, which firm is right about
  stocks, and USD/TWD in Taiwan terms); every other modelling choice moves the median by under $1.5k.
- **Docs and tooling**: both docs read end to end; doc_numbers ignores line breaks and `--fix` replaces
  numbers only; 108 figures checked; a test fails if a quoted report is not rewritten by run_all;
  computed (not typed) CMA shifts in `policy_robust` and table labels; pyflakes clean and in CI; a
  fresh clone passes the tests and reproduces every committed report byte for byte.
Headline: median $197,244, p5 $146,831, CVaR5 $135,959, real median $166,709; 119 tests pass.

### Round 6, late afternoon: two calibration biases in the equity risk
- **Correlation shrinkage target**: Ledoit-Wolf toward the identity pulled every equity pair toward
  zero (average 0.69 -> 0.64), so the core's volatility read 14.9% against 15.4% with the sample
  correlations. Equity pairs now shrink toward their own average (constant-correlation target, same
  intensity). IPS 5th percentile -$1.1k, median +$33, weights within 0.3pp. Crash-month correlation
  already matched history (0.38 model, 0.39 history, worst 5% of months since 2017).
- **Short-history volatilities**: EMXC (history from 2017) and MCHI (from 2011) missed 2008. Their
  volatility is now scaled by EEM / FXI's full-window over same-window ratio (19.3% -> 23.1%,
  23.1% -> 25.7%). This exposed a Black-Litterman artifact: with relative views only, the market's
  posterior return still drifted above the consensus prior, by +0.15 points before and +0.38 after,
  because one view's covariance with the market changed sign. The posterior is now shifted so the
  market earns its prior (`black_litterman.anchor_to_prior`, weights unchanged to 1e-16). Together:
  IPS median -$0.5k, 5th percentile -$0.9k; the views' worth in the median falls from $1.3k to $0.7k.
  Policy conclusions re-checked below.
- **Policy grid after the three equity-risk corrections** (correlations, short-history vols, BL level):
  IPS within $1.8k / $2.5k / $8.3k of the best CE at gamma 2 / 4 / 8 (rank 780 of 3,456 at gamma 4;
  this morning $2.3k / $2.2k / $7.2k). The direction is consistent: more equity risk and a lower equity
  return favour the lower-equity, full-floor policies (P2305, P2361) a little more. The IPS is still
  close to the best at moderate risk aversion; at high risk aversion the gap is now $8.3k, which
  strengthens the case the client should weigh in "Decisions for the client" (growth mix and floor).

### Round 6: where the day's headline change came from
`scripts/round6_waterfall.py` rebuilds the IPS headline (20,000 scenarios, seed 11) from this morning's
model, switching the day's changes on one at a time; the last row matches `report_numbers.json` to the dollar.
Every row runs on the final engine, so the first includes the floor-ticket fix below (+$100 against
the morning's published $197,846).

| Change | Median | 5th pct | Real median |
|---|---|---|---|
| Morning model (round 5 merged) | $197,946 | $147,482 | $167,444 |
| Commissions compounded | -$262 | -$64 | -$249 |
| Sale tickets in January 2033 | -$225 | -$225 | -$191 |
| Taiwan cost growth correlated with USD/TWD | $0 | $0 | -$52 |
| Rate persistence bias-corrected (Kendall) | +$26 | -$163 | -$49 |
| J.P. Morgan 2027 assumptions | -$122 | -$101 | -$101 |
| Equity correlations shrunk toward their average | +$26 | -$1,136 | +$224 |
| EMXC and MCHI volatility include 2008 | +$1,156 | +$233 | +$1,092 |
| Black-Litterman market level anchored to the consensus | -$1,664 | -$1,151 | -$1,455 |
| Correlation target back to zero (below) | +$108 | +$1,227 | -$116 |
| **Now** | **$196,989** | **$146,102** | **$166,547** |

The anchoring row is larger than the volatility-proxy row it was added to correct because the morning model
already had a drift: anchoring the morning model alone moved its median from $197,846 to $197,372 (-$474,
before the ticket fix).
With anchoring on, the volatility proxies are worth +$121 in the median, not +$1,154. So of the day's
-$957 in the median, about -$0.5k is costs that were real but unmodelled (compounding, the sale tickets) and
-$0.5k a Black-Litterman artifact removed; the risk corrections are close to neutral in the median. The
5th percentile falls $1.4k, mostly from the same costs, the rate-persistence correction and the anchoring.

### Round 6, evening: the correlation target, tested out of sample and reverted
The afternoon's switch to a constant-correlation target (equity pairs shrunk toward their 0.69 average
instead of zero) rested on an argument, not a test: the zero target lowers the sample's average
correlation. `scripts/corr_shrink_oos.py` tests it: correlations re-estimated on rolling 109-month windows
from 2005 (every 6 months), scored on the next 36 or 72 months, on 7 funds with full history and on all 9
(EEM and FXI standing in for EMXC and MCHI). Against the target as adopted, the zero target misjudged
the market's volatility less in all four tests (+1.1% against +3.3% on average for 9 funds over three
years), understated the core's active risk less in all four (11% against 26%), and gave a calmer
minimum-variance portfolio in all four; correlation error split two-two. Ledoit-Wolf's own optimal
intensity toward the average is about 1 (every pair set to the average), and that forecast worst on
correlation error and minimum-variance risk. So the zero target is the default again (`"mean"` stays an
option, tested). Caveats: about four independent periods, and correlations since 2005 have mostly drifted
down from their 2008-era level, which favours the target that pulls them down.
- Headline: median $196,879, 5th percentile $145,992 (+$1.2k), real median $166,464.
- Policy grid rerun: IPS within $1.9k / $2.3k / $7.6k of the best CE at gamma 2 / 4 / 8 (rank 634 of
  3,456 at gamma 4), against $1.8k / $2.5k / $8.3k with the average target and $2.3k / $2.2k / $7.2k this
  morning.
- Both targets understate active risk out of sample (the core's tracking error is probably low by a
  tenth or more); MODEL.md says so. Shrinking more toward the average would fix that and would worsen
  everything else, so it is noted, not adopted.
- **Volatility window, tested as a forecast** (`scripts/equity_horizon.py`, `reports/equity_vol_forecast.csv`):
  from every half-year since 1981, a trailing 21-year US volatility (the generator's window is about 21
  years) missed the next six years' by 0.23 in logs, against 0.27 for 9 years and 0.31 for all history.
  No change.
- **Volatility proxies, tested on funds with full history** (`scripts/vol_proxy_check.py`): EEM and FXI,
  truncated to 2011 or 2017, understated their 2005-2026 volatility; scaling each by the other moved it
  closer in 3 of 4 cases. With unrelated proxies the method helps from 2011 (62 of 72 pairs) but not from
  2017 (28 of 72), so it depends on a same-market proxy, which EEM is for EMXC. No change.
- **Rebalancing band** (scratch run, 20,000 scenarios, seed 11): bands of 2% to 25% around the 60%
  equity share move the IPS median between $196.6k and $196.9k and its 5th percentile between $145.4k and
  $146.4k; 10% instead of 5% is worth +$0.2k / +$0.4k of certainty equivalent at gamma 4 / 8. Too small to
  change the IPS. No change.
- **Capital-market assumptions re-checked against sources**: the 12 firms shared with Portfolio Lab's
  table match it (BlackRock's 9.0% for US equities is its August 2026 workbook, June 30 data; PGIM's 5.2%
  confirmed on PGIM's site). Vanguard published its September 30, 2026 VCMM run on October 21 (US
  4.8-6.8%, developed ex-US 5.3-7.3%, EM 3.7-5.7%, against 4.2-6.2%, 4.5-6.5%, 2-4% in June); the config
  now uses its midpoints. No headline change: every view is a median across firms and the spreads
  sit at their floor, so one firm's revision does not move them. Only the robustness study's
  25th-percentile-firm shift moves (IPS median under it $193.9k -> $194.3k). Amundi and Northern Trust
  publish no developed ex-US figure and stay out.
- **WInS orders include the ladder top-up**: `wins_ladder_check.py` found the reserve held in WInS $189
  short for 2034 at WInS's 0% cash rate, but `wins_rebalance.py`'s order list did not fix it. It now buys
  the cheapest top-up first (6 IBTO, $139) and sizes the growth sleeve from what is left; with it every
  payment is covered (smallest surplus +$9). Regression test in `tests/test_audit_fixes.py`.
- **2031 floor tickets counted twice** (engine review): moving money into the floor charged 4 ETF
  tickets on top of the forced rebalance, which already charges one per fund and the bond fund, so
  the IPS paid 14 tickets for 10 trades (since the first version, then 4 + 4 for 4 trades). The extra
  ticket is now charged only when the sleeve's bonds are VGIT (the floor's IBTM is then a separate
  fund). IPS median +$110; regression test `test_the_2031_floor_move_is_one_ticket_per_fund`. The engine
  now returns `costs_2033`. Policy grid rerun: IPS within $1.8k / $2.2k / $7.6k of the best CE at gamma
  2 / 4 / 8 (rank 637 of 3,456 at gamma 4).
- Headline at the end of round 6: median $196,989, 5th percentile $146,102, CVaR5 $135,214, real
  median $166,547.

### Generator input check

The Taiwan-cost correlation controls now reject non-finite coefficients and values outside [-1, 1].
Previously an invalid FX coefficient could produce NaNs, while the CPI path could silently alter the
innovation variance. Eight parameterized cases cover both controls; valid headline defaults are unchanged.

The tail controls (`t_dof`, `rate_dof`, `infl_dof`, `fx_dof`, and `rate_shared`) now reject degrees of
freedom that cannot define a unit-variance Student-t and invalid mixing shares before consuming random
draws. Unknown tail names no longer fall through to inherited behavior; positive infinity is handled
as Gaussian. Tests preserve the legacy default bit-for-bit and cover invalid values.

The optional GARCH path now requires finite, stationary coefficients, a positive initial variance,
and an in-range equity factor; invalid starting conditional variances also fail early. Calibrated GARCH
paths and the default model are unaffected.

The follow-up edge-case pass now rejects boolean or floating-point factor indices, malformed/non-numeric
volatility scales, and starting variance arrays whose shape cannot map unambiguously to simulation paths.
Scalar continuation state and one value per path remain supported and produce identical paths when equal.
Equity volatility scales are now finite and nonnegative for all scenarios; negative values previously
flipped equity cross-correlations, while zero remains available for a deterministic-equity stress.
Taiwan cost correlation inputs also reject booleans and nonnumeric values, which Python would otherwise
coerce or fail on with an unhelpful low-level exception.
Taiwan building-cost AR(1)/AR(2) persistence is now checked for stationarity before any draws, including
when the caller supplies an explicit state that would otherwise bypass stationary initialization.
Taiwan cost drift and innovation scales now reject invalid domains; zero volatility remains a valid
deterministic stress, including the stationary AR(2) initialization path.
Nelson-Siegel rate factors and inflation now receive the same stationarity guard; wrong-shaped, boolean,
non-finite, or unit-root/explosive AR inputs fail before path generation.
Both shock and expected-return covariance inputs are checked for dimensions, finiteness, symmetry, and
the appropriate positive-definiteness condition before draws; zero expected-return covariance remains valid.
Simulation counts and horizons now require positive integers, continuation month indices must be
nonnegative integers, and annual equity geometric returns must be finite and above -100%.
Nested simulation now checks required continuation keys and validates shared/per-path state shapes and
finite values before generating shocks, including optional drift and Taiwan AR state.
Initial Nelson-Siegel factors, curve residuals, inflation levels, FX drift, and rate floor now require
finite numeric values with exact expected shapes.
The calibrated Taiwan cost AR initial lags also reject non-finite or wrongly sized states before draws.
Boolean equity-volatility scales and rate-tail shares are now rejected explicitly instead of coercing to
zero/one, matching the existing strict checks for correlations and persistence.

### Round 7: strategy and engine allocation guards

The engine previously accepted strategy region weights that did not sum to one, which could create or
destroy principal when investing. Strategies now require finite, nonnegative weights that sum to one
within a small tolerance, then normalize them exactly. Fractions, supported bond vehicles, floor years,
and ratchet thresholds also fail early when invalid.

The engine now validates scenario path dimensions and finite values, plus continuation-state dimensions,
holdings, locked fractions, and ratchet values. Configuration checks reject expense ratios that would
turn monthly equity growth negative; negative ticket counts or recurring costs; duplicate, malformed, or
negative deposits; incomplete or overlapping fund groups; and invalid rate-sensitive ladder prices.
String rate floors and non-State continuation objects now produce clear input errors.

No modeled result moved under the valid defaults. After the full report pipeline, the headline remains
$196,989 median, $146,102 p5, $135,214 CVaR5, and $166,547 real median. The full test suite and pyflakes
pass, and `doc_numbers.py` finds 0 of 126 figures missing. The known WInS check remains a nonfatal $133
2034 shortfall, with a six-share IBTO top-up. The input guards were pushed to the personal fork on
`improve` in commits `f9e5c7f`, `2dabbb3`, `138198a`, and `445d527`; upstream was not changed.

The nested January 2031 quote also exposed a deflator-indexing error: its FX and Taiwan-cost paths keep
their accumulated 2027 levels, but the real-facility calculation treated the nested path's first month as
January 2027. Nested scenarios now carry their January 2027 baselines through continuation, and the engine
requires those baselines when starting after that date. This leaves the full-horizon headline unchanged
and fixes the nested real-dollar output.

A Linux CI run also exposed a platform-dependent tie-order assertion in the 2030-floor ranking test. The
test now checks the invariant directly: `growth_2031` is constant, and the conditional selector chooses
the exact median index by `assets_2031`. It no longer assumes that an arbitrary tied index must miss the
median floor by a fixed dollar percentage.

The conditional 2031 quote helpers now validate scenario indices, snapshot requirements, percentile
bands, sample counts, seed values, and percentile outputs before drawing nested paths. The engine also
rejects wrong strategy/configuration types, invalid continuation-state indices, and non-boolean snapshot
or drift flags with direct errors. These checks do not alter valid model outputs.

The cash-flow ladder solver now normalizes one-shot payment iterables, requires strictly ordered positive
payments and a reinvestment rate above -100%, and rejects duplicate instrument labels and unknown
constraints. A fixed amount now remains fixed when a compatible minimum is also provided; contradictory
fixed/minimum bounds fail explicitly. Annual schedules from leap day roll to February 28 in non-leap years.
Matured Treasury bonds, STRIPS, and term funds now expose no future cash flows or stale prices, and their
yield/duration calculations fail clearly. Explicit ladder matrices reject expired instruments. The
premium helper filters expired candidates from future-date universes. The study also drops its Jan 2033
fit: the first payment is due at settlement, and its previous fit incorrectly credited the already-matured
IBTM toward that payment.

Treasury par/zero curves now validate tenor, knot, and discount-vector shapes and values. Negative or
non-finite maturities fail directly; `ZeroCurve.zero()` no longer turns a past date into a plausible
short rate. Bootstrap horizons must include at least one semiannual point, and nonpositive discount
factors are reported as invalid input data.
- **Commit note:** `2dabbb3` ("Test the volatility-window forecast helper ...") also contains the
  input validation Codex had left uncommitted in `src/lgm/engine.py`, `src/lgm/strategies.py` and
  `tests/test_strategy_validation.py` (swept in by `git commit -a`). The code is tested; only the message
  undersells it. It was already pushed, so the history is left as is rather than rewritten.
