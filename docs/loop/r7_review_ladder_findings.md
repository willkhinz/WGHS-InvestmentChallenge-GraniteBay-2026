# r7-review-ladder findings — validation added in `f6e0613..b8c0036`

Scope: `git diff f6e0613 b8c0036 -- src/lgm/curve.py src/lgm/instruments.py src/lgm/ladder.py`.
Nothing under `src/`, `scripts/` or `tests/` was edited. Every number cited below is printed by the
named function in `docs/loop/r7_review_ladder_repro.py`:

```
PYTHONPATH=<worktree>/src PY docs/loop/r7_review_ladder_repro.py
```

Severity `hypothetical` means no current caller passes the input; the code path is still reachable
through the public API.

## Findings

| # | File:line | Cat | What happens | Reproducer | Suggested fix | Severity |
|---|-----------|-----|--------------|------------|---------------|----------|
| 1 | `src/lgm/instruments.py:108`, `:114` | c | A `TreasuryStrip` maturing exactly on `curve.date` returns `curve_price` 0.0 (expected `100*df(0)` = 100.0) and `dirty_price` 0.0 even when a quote of 99.0 is supplied (expected 99.0). Only the `<=` boundary is wrong; strictly past maturities correctly stop using stale quotes/past curve prices. | `finding_1_strip_at_curve_date` | Use `maturity < curve.date` so the maturity-date value is priced at `t = 0`. | hypothetical: no caller prices a strip on its maturity date, so the equality never occurs. |
| 2 | `src/lgm/instruments.py:156` | c | `TermFund.growth_factor` returns 0.0 at `t = 0` (expected `(1+y-e)^0` = 1.0). The guard treats "terminates today" as "expired"; the existing test only covers a strictly past termination and does not pin this boundary. | `finding_2_fund_growth_at_termination` | Guard `t < 0.0` instead of `t <= 0.0`. | hypothetical: `TermFund.cashflows` already returns `[]` when termination `<= settle`, so no caller reaches growth at t = 0. |
| 3 | `src/lgm/instruments.py:161-164` | b | `TermFund.cashflows` guards on `settle` but values the flow at `curve.date`; with `settle = curve.date - 30 days` and `termination == curve.date` it returns `[(2026-10-20, 0.0)]` instead of `[]`, so `build_matrix` accepts a zero-value fund with price 1.0. The guard's stated purpose ("no future cash flows") is defeated by a mismatched settle/curve pair. | `finding_3_fund_settle_vs_curve_date` | Guard on `curve.date` (the valuation date), or derive both from one date. | hypothetical: every caller passes `settle = curve.date`. |
| 4 | `src/lgm/ladder.py:243-254` | b | `premium` filters expired instruments but never checks that the first payment is still in the future. With a curve dated 2033-01-01 and `payment_schedule()` (first payment 2033-01-01, ten payments to 2042-01-01), all instrument flows are strictly after settlement, the LP is infeasible, and `premium` returns `nan` (cost `nan`) instead of raising. One year later the same call raises `ValueError` from `zero_coupon_cost`/`curve.df` ("discount maturity must contain finite nonnegative years"), so the failure mode changes type with the date. | `finding_4_premium_at_first_payment` | Require `payments[0][0] > curve.date` in `premium` (or `solve`) and raise `ValueError("first payment is due at settlement")`. | hypothetical now: `8075e26` dropped the 2033 fit from `scripts/ladder_premium.py` rather than fixing the library; no current caller passes such a curve. |

## Hunks checked and found fine (category e)

curve.py

- `@@ -35,6 +35,21 @@ ParCurve` — `__post_init__` validates date, at least two tenors, finite values, strictly increasing positive tenors and yields above -200%; `par_curve` data and `ParCurve.shifted` satisfy this.
- `@@ -43,7 +58,12 @@ ParCurve.par_at` — rejects nonfinite/negative maturity (the old code flat-extrapolated); all callers pass t >= 0 (including `esg.py` knots).
- `@@ -55,6 +75,14 @@ ParCurve.shifted` — rejects bool/nonfinite basis-point shifts; callers pass integers/floats.
- `@@ -66,10 +94,28 @@ ZeroCurve` — `__post_init__` requires at least two increasing nonnegative knots and finite log discounts; bootstrap and the future-date `ZeroCurve(date, knots, log_df)` clones satisfy it.
- `@@ -77,7 +123,13 @@ ZeroCurve.df` — rejects nonfinite/negative t with a message that now names the argument; bootstrap-derived curves and all callers pass t >= 0.
- `@@ -87,6 +139,14 @@ ZeroCurve.zero` — rejects nonfinite/negative t while keeping the `max(t, 1e-9)` convention for t = 0; same callers as `df`.
- `@@ -97,6 +157,16 @@ bootstrap` — requires a `ParCurve` and a non-bool `max_t` at least half a year; all callers pass a `ParCurve` and the default.
- `@@ -104,6 +174,8 @@ bootstrap` — rejects a nonpositive/nonfinite implied discount factor; real par curves give positive factors.

instruments.py

- `@@ -41,21 +41,31 @@ TreasuryBond.cashflows/accrued/dirty_price/clean_price` — an already-expired bond now returns `[]`/0.0 instead of raising `IndexError`; no current universe holds an expired bond, and the new test pins the expired-bond case.
- `@@ -63,6 +73,8 @@ TreasuryBond.ytm` — raises a clear error for a matured bond; no caller prices one.
- `@@ -70,6 +82,8 @@ TreasuryBond.mod_duration` — raises when `p0 <= 0`; the message could also fire for a zero quote, but no real quote is zero and no caller does this.
- `@@ -91,10 +105,14 @@ TreasuryStrip.curve_price/dirty_price` — apart from finding 1's equality, matured strips correctly ignore a stale quote/past curve price (the reproducer's `matured strip ytm` check uses a matured strip); the pricing universes hold only future maturities.
- `@@ -105,11 +123,21 @@ TreasuryStrip.ytm` — matured strip now raises (was 0.0) and dirty price is validated positive/finite; covered by `tests/test_strips.py:44-52`; no production caller with a matured strip.
- `@@ -125,10 +153,14 @@ TermFund.growth_factor/cashflows` — apart from findings 2 and 3, strictly past funds are excluded and `wins_reserve_universe()`'s IBTM fund is filtered by `premium` before `solve`.

ladder.py

- `@@ -11,8 +11,11 @@ imports` — adds `calendar`, `Mapping`, `Integral`, `Real`; no behavior change.
- `@@ -22,6 +25,67 @@ _payment_rows/_reinvestment_rate/_constraint_dollars` — reject empty/non-pair payments, nonpositive/nonfinite amounts, bools, unsorted dates, unknown constraint labels and extra top-up units; real calls pass sorted schedules and label subsets (`held`, `lp.units`), with defaults filling missing labels.
- `@@ -33,7 +97,23 @@ payment_schedule` — validates `n`/`amount`, clamps month-end (leap-day schedule printed: 2032-02-29, 2033-02-28, 2034-02-28, 2035-02-28, 2036-02-29), and round-trips through `_payment_rows`; default and script calls unchanged.
- `@@ -47,12 +127,25 @@ build_matrix` — validates labels (nonempty/unique), future flows, positive finite price and unit, and a finite nonnegative matrix; real universes have unique cusip/ticker labels and fund price 1.0.
- `@@ -61,6 +154,8 @@ build_matrix` — matrix finiteness/nonnegativity guard is redundant after per-instrument checks but rejects nothing valid.
- `@@ -68,7 +163,14 @@ solve` — calls the validators and implements the fixed/minimum precedence correctly: `minimum > fixed` raises "fixed amount ... is below its minimum", and a fixed label keeps its fixed bound; `wins_ladder_check` passes `minimum=held` with no `fixed`, so no conflict.
- `@@ -89,7 +191,7 @@ solve` — minimum is skipped for fixed labels, matching the precedence check above.
- `@@ -102,6 +204,14 @@ check_coverage` — validates payments, curve, reinvest and extra dollar keys; no `src/` or `scripts/` caller passes `dollars` (test passes exact labels), so the stricter key check changes no real result.
- `@@ -116,6 +226,9 @@ zero_coupon_cost` — validates payments and curve; `strips_reserve` passes its own generated schedule, and no caller uses `as_of`.
- `@@ -131,7 +244,13 @@ premium` — apart from finding 4's missing payment-date check, the active filter correctly drops strictly past instruments (including IBTM on a future curve) and raises clearly when none remains.
- `@@ -141,13 +260,23 @@ idle_cash_days` — validates payments, reinvest, curve, duplicate labels, future flows and unknown unit keys; the only caller (`strips_reserve.py:81`) passes `lp.units`, whose keys are a subset of the universe, so the new checks accept it. The `lab not in inst_by_label` branch is dead but harmless.

## Notes, not findings

- `zero_coupon_cost` now rejects payment schedules with duplicate dates or nonpositive amounts even though the function could in principle price an aggregated schedule; no caller passes one.
- `check_coverage`/`idle_cash_days` reject extra keys instead of ignoring them; no caller passes a superset.
- `TreasuryBond.mod_duration`'s "matured" message would also describe a zero clean quote; no quote in the data is zero.
