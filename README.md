# Laura Gao investment model

Liability-driven investment model for the 2026-27 Laura Gao case: fund ten fixed $50,000 payments
(2033-2042) with certainty, then build the largest responsible facility contribution for 2033.

> **AI use and citation.** This code, its reports and the documents in `docs/` were generated with
> Claude (Anthropic), an AI assistant; the commit history shows it. Competition rules say AI-generated
> work cannot be submitted as the team's own, and any AI material that is included must be cited. Use this
> repository as a reference and checking tool: rebuild the numbers you submit yourselves, and cite it
> (for example "Laura Gao investment model, generated with Claude (Anthropic), October 2026") wherever its
> output appears in the IPS or Final Report.

**Part 1 — core funding model (built)**
- `curve.py` — Treasury par curve to zero-coupon curve (bootstrapping).
- `instruments.py`, `ladder.py` — WInS-permitted Treasuries and iBonds ETFs; cheapest cash-flow-matched
  reserve as a linear program (HiGHS).
- `calibrate.py`, `esg.py` — monthly scenario generator calibrated to 1994-2026 data: three-factor
  Nelson-Siegel yield curve, US / developed / emerging stocks with fat tails (Student-t), inflation,
  USD/TWD and Taiwan building costs.
- `strategies.py`, `engine.py` — strategy rules (lock schedule, mix, rebalancing band, 2031 floor,
  contribution rule) simulated month by month; Monte Carlo scoring against Laura's goals; nested
  2031 simulation for the co-sponsor range.
- `backtest.py` — historical replay: 184 real six-year paths (2005-2026) applied to today's curve.
- `simple.py` — exact re-implementation of the former team's guide (Steps 1-7).

**Part 2 — growth sleeve (built)**
- `growth/core.py`, `black_litterman.py`, `lookthrough.py` — nine-ETF core: market-cap prior, views from
  13 firms' published capital-market assumptions, constrained optimiser (no tech/communication or
  China+Taiwan overweight), resampled over 500 posterior draws for stable weights.
- `growth/satellite.py`, `qualitative.py` — 35-stock satellite: S&P 500 risk and return-quality screens,
  then the values (Laura fit) and company-strength model with yes/no gates; HRP weights.
- `growth/portfolio.py`, `scoring.py` — the satellite as one more Black-Litterman asset (alpha view over
  its style benchmark), sized and judged with the Part 1 Monte Carlo, including commissions and WInS
  whole-share orders.

See `docs/MODEL.md` for the design and results.

## Data (no API keys)
Treasury nominal and real par curves (home.treasury.gov), Treasury securities (TreasuryDirect), CPI
(FRED CSV; also the long USD/TWD series DEXTAUS), the Kim-Wright term structure model and H.10 USD/TWD
rates (Federal Reserve Board), Taiwan's construction cost index (DGBAS), Taiwan money-market and USD/TWD
forward rates (Central Bank of the Republic of China (Taiwan)), factor
and portfolio returns (Kenneth French Data Library), prices (Yahoo Finance chart API), ETF holdings
(iShares), company financials and analyst ratings (Nasdaq). Raw downloads are cached in `data/raw/`; each
downloader checks a response before it replaces a cached file. The raw files are the providers' data: check
their terms before redistributing the repository. The October 2026 news check on the selected
stocks used Bigdata.com (https://bigdata.com); its effect is recorded in `config/qualitative_judgments.csv`.

## Configuration
| File | What it holds |
|---|---|
| `config/asof.yaml` | The run dates: Treasury curve date, last month of data, price date. The engine's month timeline follows the curve date |
| `config/wins_account.yaml` | The WInS account: cash, funds to sell, the reserve ladder held. Update after each trading session |
| `config/case.yaml`, `wins_rules.yaml` | The case's cash flows; WInS session rules (commissions, 0% interest on cash) |
| `config/cma.yaml`, `qualitative.yaml`, `qualitative_judgments.csv` | Black-Litterman views; the qualitative model and its judgments |

To refresh before the Final Report: change the dates in `config/asof.yaml`, update
`config/wins_account.yaml`, then run `python scripts/run_all.py --refresh`. It re-downloads the data that
moves with the dates, keeps the cached copy of any source that is unreachable (and says so), then reruns
every script in order.

## Quick start
```
python -m venv .venv && . .venv/bin/activate && pip install -e . pytest
python -m pytest                    # offline (cached data); also run on every push (.github/workflows)
python scripts/run_all.py           # every script below and the studies the docs quote, then the doc check (about 100 s)
python scripts/validate_plans_v2.py
python scripts/build_core.py
python scripts/build_satellite.py
python scripts/validate_model.py    # how good is the model: generator checks, convergence, replay, BL sensitivity
python scripts/report_numbers.py    # headline numbers for the IPS and Final Report
python scripts/factor_evidence.py   # long-run evidence for the views (Kenneth French data)
python scripts/rate_path_study.py   # which expected rate path; Kim-Wright scenario
python scripts/doc_numbers.py       # do the figures in docs/ match the reports? (also a test)
python scripts/policy_study.py      # 2031 floor frontier, range calibration, reverse stress test
python scripts/wins_rebalance.py    # orders that bring WInS in line with the IPS (ladder top-up first)
python scripts/wins_ladder_check.py # does the WInS ladder meet every payment at 0% interest on cash?
```

Studies behind the assumptions (each writes one report; `run_all.py` reruns all but the policy search and the waterfall):
```
python scripts/fx_variants.py            # USD/TWD drift, cost-FX correlation and cost drift in Taiwan terms
python scripts/fx_hedge_frontier.py      # hedging 0-100% of the facility, under two beliefs about the forward
python scripts/fx_horizon.py             # does USD/TWD mean-revert over six years? (no)
python scripts/taiwan_fx_corr.py         # building-cost growth vs USD/TWD in history
python scripts/taiwan_drift_study.py     # which building-cost drift forecasts best in real time
python scripts/equity_horizon.py         # do US stocks mean-revert over six years? (no)
python scripts/vol_proxy_check.py        # does scaling a short history's volatility by a longer one work?
python scripts/stock_rate_corr.py        # results under each historical stock-rate correlation regime
python scripts/crash_comovement.py       # do rates fall when stocks crash?
python scripts/corr_shrink_oos.py        # which correlation shrinkage forecasts best out of sample
python scripts/tracking_error_oos.py     # the core's tracking error corrected out of sample
python scripts/ladder_premium.py         # does the ladder's premium hold when rates move?
python scripts/satellite_oos.py          # the satellite's selection bias, out of sample
python scripts/satellite_risk_sensitivity.py   # the satellite verdict with that bias corrected
python scripts/policy_search.py --grid --workers 6   # 3,456 policies (about 3.5 min)
python scripts/policy_robust.py          # the IPS and the search's best policies under 11 assumption shifts
python scripts/round6_waterfall.py       # what each October 22 change did to the IPS headline (about 3 min)
```
`python scripts/doc_numbers.py --fix` rewrites figures in `docs/` that a model change has moved.
`docs/loop/IMPROVEMENT_LOG.md` records each round of the October 2026 improvement loop.

See `docs/VALIDATION.md` for the check of the former team's numbers.
