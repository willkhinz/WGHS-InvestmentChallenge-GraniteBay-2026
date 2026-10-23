# r7-review: the new input validation in `src/lgm/esg.py` (f6e0613..b8c0036)

Read-only review of the validation work added to `src/lgm/esg.py`. `f6e0613..b8c0036` contains 16
commits touching that file; its diff is 392 insertions / 78 deletions across 11 hunks. Method: read the whole diff against `f6e0613`, compare each check with the
pre-range behaviour, run the real calibration through it, run the probes below, and run the test suite.
Nothing under `src/`, `scripts/` or `tests/` was changed by this review.

Every finding has a runnable reproducer in `docs/loop/r7_review_esg_repro.py`:

```
PYTHONPATH=<worktree>/src <venv>/bin/python docs/loop/r7_review_esg_repro.py
```

## Findings

| file:line | cat | what happens | reproducer | suggested fix | severity |
|---|---|---|---|---|---|
| `src/lgm/esg.py:490` (also `:599`, `:604`) | (b) | `cov` is validated into the local `shock_cov`, but the GARCH variance anchor and the two Taiwan-cost correlation standard deviations still index the **raw** `p.cov`. A list-of-lists passes the new validation (it is explicitly converted with `np.asarray`) and `simulate` then raises `TypeError: list indices must be integers or slices, not tuple`. | `finding_1_raw_cov_after_validation` | Use `shock_cov[factor_idx, factor_idx]` and `shock_cov[K+3, K+3]` / `shock_cov[K+4, K+4]`, i.e. the matrix that was validated, or reject list input. | affects only hypothetical input (`esg_params` passes an ndarray) |
| `src/lgm/esg.py:214` and `:216` (called from `:435-437`) | (d) | When the Taiwan AR initial state comes from the parameters (`tw_cost_state0` / `tw_cost_infl0`), the error message still says `start['tw_cost_state0']`, naming an argument the caller did not pass. | `finding_2_param_state_error_names_start` | Pass the source (parameter name vs `start` key) into `_state_values`/`_path_state`, or phrase the message as "the initial Taiwan cost state". | affects only hypothetical input (real calibration state is finite) |
| `src/lgm/esg.py:118-121` | (d) | `_dof` rejects every string except `"gaussian"`, so `rate_dof="inf"` is rejected immediately after the message says "positive infinity" is allowed. Every other field validator written in this range (`_correlation`, `_tw_cost_ar_coefficients`, `_state_values`, `_parameter_values`) coerces numeric strings. | `finding_3_dof_infinity_string` | Accept `"inf"`/`"infinity"` in `_dof`, or say `float("inf")` in the message. | affects only hypothetical input |

Reproducer output (verbatim, `PYTHONPATH=src .../python docs/loop/r7_review_esg_repro.py`):

```
finding_1 (b) cov given as a list-of-lists, GARCH path (line 490):
  expected: the validated matrix is used, or cov is rejected while validating
  actual:   TypeError: list indices must be integers or slices, not tuple
finding_1 (b) cov given as a list-of-lists, correlation path (line 599):
  expected: the validated matrix is used, or cov is rejected while validating
  actual:   TypeError: list indices must be integers or slices, not tuple
finding_2 (d) p.tw_cost_state0=(nan, 0.0), start=None:
  expected: ValueError naming tw_cost_state0 (the parameter that was actually set)
  actual:   ValueError: start['tw_cost_state0'] must contain finite numeric values
finding_3 (d) rate_dof='inf':
  expected: accepted as positive infinity (the message lists positive infinity as allowed)
  actual:   ValueError: rate_dof must be a Student-t dof > 2, positive infinity, or 'gaussian', got 'inf'
finding_3 (d) contrast, tw_cost_corr='0.3':
  expected: accepted, because float(value) coercion is used here
  actual:   ran without error
```

## Hunks checked and found fine (category e)

1. `@@ -16,6 +16,7 @@` (`month_of` import) — fine.
2. `@@ -38,7 +39,7 @@` (`t_dof` comment) — documentation only.
3. `@@ -49,7 +50,7 @@` (`rate_shared` comment) — documentation only.
4. `@@ -67,6 +68,8 @@` (`Scenarios.fx_log_2027`/`.tw_cost_log_2027`) — defaults `None`; `engine.run` accepts `None` whenever it recomputes January 2027 from the same path, and `backtest.py:69` never needs them (`m0=0`).
5. `@@ -97,30 +100,358 @@` (validation helpers and the `simulate` prelude) — apart from findings 1-3, fine. `_garch_parameters`, `_correlation`, `_tw_cost_ar_coefficients`, `_state_values`, `_path_state`, `_tw_cost_state`, `_parameter_values` reject what they advertise (bools, non-finite values, bad shapes, non-stationary AR(2), non-PSD matrices); the real calibration (`build_core()` → `esg_params`) passes every check.
6. `@@ -128,57 +459,41 @@` (mixing, shocks, GARCH setup) — fine. `_block_mixing` keeps the pre-range meaning (Gaussian at `+inf`, own t draw for finite dof, legacy equity mixing at `None`); the legacy branch condition and the `rate_shared` blend are unchanged; only the failure mode for `t_dof=+inf` changed (it is now the Gaussian limit instead of NaNs). The GARCH recursion is numerically identical for valid input.
7. `@@ -186,12 +501,9 @@` (equity-drift root, `eq_drift_err`) — fine: the normalized PSD root is used, and `start["eq_drift_err"]` is pre-validated to `(K,)`/`(n,K)`.
8. `@@ -204,34 +516,27 @@` (beta, inflation, FX, cost locals) — fine: normalized locals replace the raw fields with identical arithmetic for valid input.
9. `@@ -248,18 +553,17 @@` (Taiwan AR state selection, zero-volatility initial state) — fine: lag order and the tuple/one-lag handling are unchanged, and the new deterministic `sig_eps == 0` initial state is a deliberate addition covered by `tests/test_taiwan_esg.py`.
10. `@@ -286,19 +590,19 @@` (Taiwan cost correlations) — fine apart from the raw-`p.cov` std at line 599 (finding 1): `_correlation` validates the coefficients, and "both set" is still rejected.
11. `@@ -312,8 +616,18 @@` (Jan-2027 FX/cost baselines and return) — fine. `month_of(2027)=2` matches `engine.M_2027`; when the horizon does not reach January 2027 the nested start's baseline is used, and `engine.run` raises a clear error only when it is absent, which is the documented continuation contract.

Additional checks behind "fine":

- Default behaviour is unchanged: `tests/test_rate_tails.py::test_default_rate_tails_bit_for_bit_identical` and `tests/test_taiwan_esg.py::test_default_reproduces_old_scenarios_bit_for_bit` pass.
- The only in-repo `simulate(..., start=...)` callers (`scripts/validate_plans_v2.py:59-62`, `scripts/policy_robust.py:218-237`) and `engine.conditional_2031` (`src/lgm/engine.py:609-622`) pass shapes the strict `_prepare_start` accepts: beta `(3,)`/`(n,3)`, path states `(n,)` or scalars, drift `(K,)`, GARCH `h` scalar, Taiwan state as a 2-tuple. Tightening `(1,3)`/`(1,)` broadcasting therefore has no in-repo caller; it is the documented contract, so it is not counted as a finding.
- Tail-block semantics, the RNG draw order and the legacy iid Taiwan-cost branch are unchanged for valid input; the `rate_shared` and `_block_mixing` rewrites are equivalent (checked against `f6e0613`).

## Tests

```
393 passed in 31.11s
```
