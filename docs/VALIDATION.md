# Validation of the former CS team's numbers

Every figure in the two documents the CS team left behind — the model rebuild guide ("Init plan") and
"Laura Gao case v2: specific instruments for each plan" (Plans v2) — was checked against primary sources
or reproduced independently with this codebase. Checked Oct 21, 2026.

**Verdict:** the guide's arithmetic is exact, and the team's simulation results reproduce within 0–5%.
Eight discrepancies in the documents and three errors about WInS itself were found; none changes a
strategy conclusion.

## 1. Primary-source data

| Item | Document value | Primary source | Result |
| --- | --- | --- | --- |
| Treasury par yields, Oct 16 (5/7/10/20-yr) | 4.89 / 4.98 / 5.09 / 5.47 | Treasury daily par yield CSV | Exact |
| Treasury 2-yr, Oct 16 (guide Step 6) | 4.74 | Treasury | Exact |
| Treasury curve, Oct 20 (Plans v2 basis) | used for all pricing | Treasury | Loaded directly |
| Five Treasury bonds: CUSIP, coupon, maturity | 912810PU6 5.000% May-37 ... 912810QT8 3.125% Nov-41 | TreasuryDirect securities API | All five exact |
| ETF closes, Oct 20 (VTI, VEA, VWO, VGIT, IBTM-IBTR) | 377.09, 69.78, 58.25, 57.03, 21.89, 23.16, 24.27, 23.89, 23.70 | Yahoo Finance | All within $0.01 |
| iBonds expense ratio | 0.07% | iShares (IBTR page) | Exact |
| IBTR launch date | Mar 25, 2026 | iShares | Exact |

## 2. Guide, Steps 1-7 (deterministic and spreadsheet Monte Carlo)

All 23 published figures reproduce to the dollar (`tests/test_guide_steps.py`), including the Step 4
curve lock of $298,927 from Treasury's official Oct 16 curve, the 29% facility drop in Step 3, the
Step 6 floor of $117,594, and the Step 7 simulation ranges (60/40: 96.5% funded, $16k / $210k / $507k;
all-stock 86%; lock-and-balance $140k / $200k / $290k; random-rate reserve $388k-$442k).

## 3. Model outputs (reproduced with the rebuilt engine)

Facility money in Jan 2033, $ thousands. Rebuilt engine: 20,000 scenarios, the team's documented
inputs (stocks 6.06%/yr net, 16.5% volatility, rates unchanged on average), fat tails (Student-t, 5 df).

| Plan | Funded: theirs / ours | 5th pct | Median | 95th pct | 2031 floor | 2031 10th-90th pct range |
| --- | --- | --- | --- | --- | --- | --- |
| S1 all equity | 86.8% / 86.7% | 0 / 0 | 212.8 / 220.7 | 759.3 / 780.5 | — | — |
| S2 static 60/40 | 96.4% / 96.8% | 16.2 / 18.6 | 208.0 / 215.2 | 508.3 / 523.1 | 0 / 0 | 120.7-332.4 / 146.3-380.7 |
| S8 hybrid | 100% / 100% | 94.2 / 97.2 | 194.9 / 199.2 | 355.3 / 367.7 | 124.3 / 118.9 | 191.9-230.2 / 181.9-220.9 |
| S6 lock, stock surplus | 100% / 100% | 106.2 / 107.9 | 197.7 / 199.8 | 365.5 / 370.4 | 0 / 0 | 150.2-261.7 / 148.2-269.4 |
| S9 lock, 60/40, floor | 100% / 100% | 137.9 / 141.9 | 193.5 / 195.9 | 273.2 / 274.9 | 114.6 / 111.2 | 181.4-208.6 / 175.0-203.5 |

Figures are after the October 2026 code-review fixes (section 6) and the switch to the Fed's H.10
USD/TWD series. S8's 2031 floor and range are up to 5% below the former team's; our VGIT now compounds
its yield correctly, which theirs may not. S2's 2031 range comes from one median world and moves a lot
with small calibration changes, because S2 holds no floor.

Other model claims:

| Claim | Theirs | Ours |
| --- | --- | --- |
| Zero-coupon cost of the ladder, Oct 16 (guide 4C) | $295,584 | $295,559 |
| Real-instrument ladder, Oct 16 (guide 4C) | $300,769 | $300,396 (LP, 3% reinvestment) |
| Real-instrument ladder, Oct 20 (Plans v2) | $300.1k | $299,717 |
| Rates 0.75 pts lower at the lock, and staying lower: lock-and-balance median | $192k -> $159k (-17%) | $195.9k -> $160.2k (-18%) (`reports/plans_v2_rate_stress.json`) |
| Fat tails change results by | < $5k | < $5k (Gaussian vs t5) |
| Facility buys less in Taiwan terms | ~25% | 21% at 4%/yr building costs; 25% needs ~5%/yr |
| Plans v2 nine-instrument ladder funds ten payments | yes | yes: coupons 2027-32 pay the 2033 payment; $4k-$16k surplus each year |

## 4. Discrepancies found

1. **Plans v2 bond prices** are 0.6-0.7 points above prices from Treasury's curve (yields 5-9 bp lower).
   Conservative (overstates ladder cost ~0.7%), not reproducible from published data. Use WInS quotes.
2. **Plans v2 Jan 2033 ladder ($411.8k)** vs $404.6k on an unchanged curve (+1.8%); consistent with
   their double-counted fund fee (their own footnote) plus the bond-price gap above.
3. **Fund fee counted twice** in Plans v2's internal ladder cost (~$2k) — their footnote; fixed here.
4. **Taiwan "25% less"** needs ~5%/yr building-cost growth; the team's stated range is 3-6%.
5. **"10-year yield spiked to ~5.33%" (week of Oct 12-16)** — a search-result claim used in our
   exemplar's grader notes; Treasury closes peaked at 5.21% (Oct 13). Corrected in the exemplar.
6. **IBTR assets** — exemplar IPS said ~$11 million (July 2026); iShares shows $111.4 million (Oct 19).
   Corrected.
7. **Oct 19 7-year yield** — exemplar documents interpolated 5.02%; Treasury published 5.04%. The lock
   cost becomes $297,228 (was $297,325); the rate fall that breaches $300,000 is 0.097 pts. Corrected.
8. **Background check recommends TIPS** for the reserve; TIPS are not permitted. Ignored.

## 5. Checked inside WInS (Session Rules tab, quote pages and bond list, Oct 21, 2026)

| Item | Plans v2 | WInS | Result |
| --- | --- | --- | --- |
| Starting cash | $300,000 | $300,000 | Confirmed |
| Trade cap | 200 | 200 | Confirmed |
| Commissions | $25 per ETF, $10 per bond | $25 per stock/ETF, $10 per bond | Confirmed |
| Trading window | to Nov 6 | Sep 28 09:30 - Nov 6 16:00 ET | Confirmed |
| Minimum stock price | $5 | **$3.00** | Wrong in Plans v2 |
| Government bonds | US, UK, DE, FR, IT, NL | **US Treasury bonds only** (the screen lists other markets, but session rules allow US only) | Wrong in Plans v2 |
| Bond types | notes and bonds | **42 original-issue T-bonds only** (no T-notes); nothing maturing Mar 2031 - Jan 2036 | New constraint |
| UST 5.000% May-2037 (912810PU6) | used for the Jan 2038 payment | **Not listed in WInS**; nearest is 4.750% Feb-2037 (912810PT9) | Replace |
| Other four Plans v2 bonds | used | Listed | Confirmed |
| ETFs: VTI, VEA, VWO, VGIT, IBTL-IBTR, TLT, TLH, SGOV, VT, ACWI | used | Listed; Oct 20 prices match | Confirmed |
| Not stated in Plans v2 | — | No fractional shares; no day trading; 0% interest on cash; ~40 exchanges incl. Taiwan (TW) and Hong Kong | New constraints |

The WInS bond list is saved in `data/wins/treasury_bonds.csv` and the ladder optimiser only uses it.
The cheapest WInS-feasible ladder for a Jan 2027 purchase on the Oct 20 curve costs $299,717
(`ladder.solve`), identical to the optimum with the unlisted bond, because the optimiser never needed it.

## 6. Independent code review (October 21, 2026)

A separate reviewer read the code for correctness and tested each suspicion with scratch scripts.
Six issues were confirmed and fixed. Four of the fixes (views, commissions, VGIT, the 2031 check) have
regression tests in `tests/test_review_fixes.py`:

| Issue | Effect before the fix | Fix |
| --- | --- | --- |
| Black-Litterman views converted from geometric to arithmetic with single-fund variances | EM view 0.83% instead of 0.63%; small-cap 1.57% instead of 1.79% | Each leg gains half its own basket variance |
| Optimiser used the posterior covariance with the prior risk aversion | With no views it held 32% VTV against a 30% market weight; uncertainty counted twice once resampled | Optimise with the prior covariance; uncertainty enters through resampling |
| Commissions charged per weight slot, not per fund | The 3-fund VTI/VEA/VWO baseline paid for 9 funds (about $465 of median) | Count funds held; `fund_groups` for funds spread over several slots |
| VGIT and cash compounded an annual yield monthly as y/12 | S2 median $1.55k too high, S9 $0.37k | Monthly factor (1 + y)^(1/12) |
| No January 2031 rebalancing check for plans without a floor | S2 median $0.8k lower | Check the band in January 2031 |
| Satellite alpha view converted to arithmetic twice | 0.875% instead of 1.0% (the view at the time; it is now 0.82%); about $30 | No conversion for that view |

The reviewer also suggested deriving risk aversion from the regions' arithmetic returns (each region's
geometric forecast plus half its own basket variance). Adopted: at the time it raised δ from 1.74 to
1.80. With today's inputs δ is 1.74.

Checked and found correct: the nested 2031 simulation (matches the outer run to $0.01 with zero
volatility), deterministic engine growth, generator moments, curve bootstrapping, the ladder LP
($299,717), HRP (identical to the reference implementation), whole-share rounding and the shock order.

## 7. How good is the model

Run `python scripts/validate_model.py` (reports `validation_esg.csv`, `validation_convergence.csv`,
`backtest.csv`, `bl_sensitivity.csv`).

- **Generator reproduces its inputs:** each fund's median return exactly, its volatility within 0.05
  points, and the one correlation checked (VTV-VGK, 0.793).
- **Tails are fatter than history:** monthly excess kurtosis 3.9-6.0 against 0.1-3.4 in 2005-2026,
  so crash risk is, if anything, overstated.
- **No long-horizon mean reversion to leave out:** US stocks' 74-month variance ratio since 1926 is 0.75
  against 0.91 for i.i.d. returns of the same length (p = 0.26; every start date and horizon tested,
  nominal or excess, has p of 0.26 or more), so i.i.d. monthly shocks do not overstate six-year
  risk (`scripts/equity_horizon.py`). The same test on USD/TWD: `docs/MODEL.md`.
- **Volatility window is representative:** the US market's volatility was 15.4% a year in 2005-2026,
  the window the equity volatilities come from, against 14.9% for 1946-2026; only 1926-1945 (the
  Depression and the war) lifts the 1926-2026 figure to 18.3% (`reports/equity_vol_history.csv`). The
  robustness study's x1.2 volatility case covers a return to that. As a forecast, a window of about
  that length did best: from every half-year since 1981, a trailing 21-year volatility missed the next six
  years' by 0.23 in logs (root mean square; bias +3.6%), against 0.27 for 9 years, 0.46 for 3 years
  and 0.31 for all history since 1926 (`reports/equity_vol_forecast.csv`; before 1981 the long windows
  reach into the Depression and overstate it).
- **Short-history volatilities:** EMXC and MCHI are scaled by EEM and FXI (`docs/MODEL.md`). On funds
  whose 2005-2026 history is known, pretending they started in 2011 or 2017 (`scripts/vol_proxy_check.py`):
  EEM's and FXI's short windows understated their full-window volatility from both start years, and
  scaling each by the other moved it closer in 3 of 4 cases. With any fund as the proxy it helped in
  62 of 72 pairs from 2011 but only 28 of 72 from 2017, so the method relies on the proxy being the
  same market, as EEM is for EMXC.
- **Rates:** the 10-year yield's change to January 2033 spans -2.8 to +2.8 points (5th-95th
  percentile), against -2.7 to +2.4 points over every 74-month window since 1994.
- **Convergence:** across 8 seeds of 20,000 scenarios the median facility is $197,055 with a standard
  error of $31; the 5th percentile's is $114. A single run, like the headline's (seed 11), moves by $88
  in the median and $323 in the 5th percentile from seed to seed; the headline's 5th percentile is
  $497 above the 8-seed average. Comparisons between strategies use the same scenarios, so they
  are far more precise than either level.
- **Historical replay:** 184 real six-year paths (starts April 2005 to July 2020) applied to today's
  curve. With returns re-centred on our expectations, the IPS median is $195.6k against $197.0k
  simulated; its 5th percentile is $154.8k against $146.1k simulated, so the simulation is the more
  cautious. All-stock funds every payment in 89.1% of real paths against 86.7% simulated.
- **Named crises just after the lock:** 2008, 2011, 2015-16 and COVID, each started so that its
  first bad month falls just after the January 2027 lock, fund every payment
  (`scripts/episode_stress.py`). As it happened, their facilities are $207.9k, $216.5k,
  $240.1k and $213.9k, all above the simulated median. The worst of the 184 paths, from
  October 2008, gives $136.2k against the simulated 5th percentile of $146.1k: rates had
  already fallen by the lock (5-year zero rate 3.65% against 4.95% on the median path), so
  the first deposit locks only 85.0% of the ladder. Splicing 2022's first twelve months into the
  simulation lifts the median facility to $207.4k: the rate rise alone adds $16.5k and the stock
  fall alone costs $5.8k (`reports/episode_stress.csv`).
- **Expected rate path:** forecasting the curve 74 months ahead from 320 month-ends (1994-2020), the
  error in the cost of ten payments is 7.7% for "unchanged", 7.5% for forwards minus the Kim-Wright term
  premium and 10.0% for pure forwards. "Unchanged" stays: it ties on accuracy and has the least bias.
- **2031 range calibration:** on the same 184 paths, the model's 10th-90th percentile range quoted from
  each path's own January 2031 position contained the January 2033 result 99.5% of the time re-centred
  (98.4% as it happened): it behaves like a 98% range. The 20th-80th percentile band held 82.1% (75.5% as
  it happened), so that is the range to quote as "80%" (`reports/policy_study.json`).
- **Satellite weighting:** re-estimated each January since 2019, single-linkage HRP's realised
  volatility (16.1%) is level with average-linkage HRP (16.2%) and below Ward (16.7%), inverse-variance
  (16.9%) and equal weights (18.2%) (`reports/validation_hrp.csv`).
- **Black-Litterman stability:** over tau 0.025-0.10 and value-view uncertainty 1.5-5 points, the
  resampled weights hold BBJP at 6.6-6.9% and BBCA at 3.8-3.9%; a single optimum swings them from 2.6%
  to 9.5% and 2.3% to 6.0%.

## 8. Reproduce

```
python -m pytest                      # includes every guide figure and the audit fixes
python scripts/validate_plans_v2.py   # section 3 table -> reports/plans_v2_validation.csv, plans_v2_rate_stress.json
python scripts/validate_model.py      # section 7 -> reports/validation_*.csv, backtest.csv, bl_sensitivity.csv
```

## 9. Audit of this repository (October 21, 2026)

A second review (`WGHS_AUDIT.md`, kept beside the repository) re-ran every test and script; the
committed reports reproduced to within about $20. Its findings were fixed as follows, with regression
tests in `tests/test_audit_fixes.py`:

| Finding | Fix |
| --- | --- |
| The WInS ladder check judged only the last payment and assumed 3% interest on cash (WInS pays 0%) | Checks every payment at WInS's 0%; prints the cheapest top-up and exits 1 if short. The ladder held is $189 short for 2034; 6 more IBTO shares fix it |
| Reinvestment risk sat outside "100% funded" | `ladder.premium` derives the ladder premium from the LP (a test pins `kappa0` to it); a stress prices the reserve to be certain at 0% reinvestment (median -$7.8k) |
| The 2031 "80% range" held 98% of real outcomes | Calibrated on history: the 20th-80th percentile band held about 80% (section 7); both ranges are now reported |
| Rate stresses faded back to today's curve by 2033 | The long-run level moves with the shock |
| Negative-equity companies scored a neutral 3 on ROE and leverage | ROE not scored, leverage scores 1 (HLT 4.0 -> 3.5; selection unchanged) |
| Stale "+1.0%" alpha label; HRP and rate-stress claims with no script behind them | Label follows `config/cma.yaml`; `validate_model.py` and `validate_plans_v2.py` now produce those numbers |
| Dates and WInS account state hard-coded across files; WInS scripts always re-downloaded prices | `config/asof.yaml` (the engine's month timeline follows the curve date), `config/wins_account.yaml`, a price cache, `scripts/run_all.py [--refresh]` |
| Downloaders cached whatever came back (FRED served an HTML maintenance page with status 200 during the audit) | Every downloader checks the response before overwriting its cache; a refresh keeps the cached copy of any source that fails |

## 10. Self-review during the improvement loop (October 22, 2026)

A read of the engine, the order scripts and the documents, with each finding fixed and, where it
is code, tested (`docs/loop/IMPROVEMENT_LOG.md` gives the effects):

| Finding | Fix |
| --- | --- |
| The 2031 floor move charged 4 ETF tickets on top of the forced rebalance, which already charges one per fund | One ticket per fund; a separate floor ticket only when the sleeve holds VGIT (`tests/test_review_fixes.py`) |
| `wins_rebalance.py` ignored the ladder check's shortfall | The cheapest top-up (6 IBTO) is ordered first (`tests/test_audit_fixes.py`) |
| A Taiwan cost correlation with both CPI and USD/TWD would have diluted the first | Refused (`tests/test_taiwan_esg.py`); the headline uses only USD/TWD |
| A non-finite, nonnumeric, boolean, or out-of-range Taiwan cost correlation could distort dependence or produce NaNs | Accept only finite numeric coefficients in [-1, 1] (`tests/test_taiwan_esg.py`) |
| Nonstationary Taiwan building-cost AR coefficients could create explosive paths when an explicit state bypassed stationary initialization | Validate AR(1)/AR(2) stationarity before drawing (`tests/test_taiwan_esg.py`) |
| Taiwan cost drift or volatility outside its domain could create NaNs, negative volatility, or fail at stationary initialization | Require growth > -100%, finite nonnegative volatility, and support deterministic zero-volatility paths (`tests/test_taiwan_esg.py`) |
| Non-finite or wrongly sized Taiwan cost starting lags could poison the AR(2) path | Require finite shared or per-scenario initial state values (`tests/test_taiwan_esg.py`) |
| Invalid Student-t degrees of freedom or boolean/out-of-range rate-tail shares could produce NaNs or select unintended tails | Validate ESG tail controls as numeric values before drawing; positive infinity is the Gaussian limit (`tests/test_rate_tails.py`) |
| Invalid GARCH coefficients, volatility scale, initial variance shape, or factor index could create non-finite paths or fail during broadcasting | Require stationary coefficients, a finite nonnegative scale (positive with GARCH), an integer equity factor, and scalar or path-sized finite starting variances (`tests/test_esg_v2.py`) |
| Nonstationary Nelson-Siegel or inflation persistence could make simulated levels explode | Require finite rate-factor AR coefficients with absolute values below one and a stationary inflation AR coefficient (`tests/test_rate_tails.py`) |
| Asymmetric, non-finite, or invalid covariance matrices could be partially ignored by Cholesky/eigendecomposition | Validate shock covariance as symmetric positive-definite and expected-return covariance as symmetric positive-semidefinite (`tests/test_rate_tails.py`) |
| Invalid sample counts, horizons, or annual geometric returns could fail during allocation or produce NaN equity drift | Require positive integer counts/horizon and finite equity returns above -100% (`tests/test_rate_tails.py`) |
| Malformed nested-simulation state could broadcast silently or fail deep in path generation | Require the four core continuation fields and validate optional drift/GARCH/Taiwan state shapes and finiteness (`tests/test_rate_tails.py`, `tests/test_esg_v2.py`) |
| Malformed initial curve, residual, FX-drift, or inflation state could fail during interpolation or produce invalid paths | Require finite model state with the expected Nelson-Siegel and residual shapes (`tests/test_rate_tails.py`) |
| `esg_params` took an `infl_phi` argument and ignored it | Removed; the fitted value is used, as before |
| The equity correlation target was changed on an argument, not a test | Tested out of sample and reverted (`scripts/corr_shrink_oos.py`) |
| Doc sentences gone stale as figures moved: "up from 1.74" when δ was 1.74, "$-0.2k below" for a base that was above, 99.5% given for both calibration samples | Rewritten, each with a check in `scripts/doc_numbers.py`; negatives now print as -$x |
