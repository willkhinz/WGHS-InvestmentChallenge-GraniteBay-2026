# Round 7 review: input validation in `lgm/engine.py` and `lgm/strategies.py`

Scope: `b8c0036` (validation work) against `f6e0613`, the two files it touches. Read-only
review: nothing under `src/`, `scripts/`, or `tests/` was changed. Reproducer:
`docs/loop/r7_review_engine_repro.py` (commit `de2d8cd`).

## Verdict

The validation is sound for every input the repo actually produces: all 393 tests pass and
`scripts/run_all.py` leaves the reports byte-identical. No added check rejects a legitimate
in-repo caller (no class **(a)**). Four gaps remain, all reachable only with hand-built inputs:

| # | Finding | Class | Severity |
|---|---------|-------|----------|
| F1 | `conditional_2031_band` silently drops percentiles when `percentiles` is an iterator | (c) regression | low |
| F2 | 2-D `eq_log` is rejected with a placeholder-shape message `(n, None, None)` | (d) | cosmetic |
| F3 | `run` rewrites the caller's `cfg.eq_er` (list becomes a tuple of `np.float64`) | (c) | minor |
| F4 | List-valued `fx_log` / `tw_cost_log` pass validation, then crash with a raw `TypeError` | (b) | low |

F1 is the only **regression** in behaviour: before this diff the band looped the iterable once,
so a generator produced the same output as a list. F2–F4 are new edge behaviour, not previously
working behaviour.

## How each check was classified

Method: for every added check, I searched all callers (`scripts/*.py`, `tests/*.py`,
`src/lgm/growth/scoring.py`) for values that the check would reject, and ran the full suite.
A check is **(e)** when every legitimate caller passes and the rejection is a real input error;
**(a)/(b)/(c)/(d)** are used strictly per the brief.

### `strategies.py`

| Check (where) | Verdict | Evidence |
|---|---|---|
| `_fraction` on `lock_2027`, `lock_2028`, `lock_2031`, `equity_share`, `band`, `floor_share_2031`, `contribution_share`, `ratchet_share` (`__post_init__`, 52–55) | (e) | All constructors use `[0,1]` fractions; bool/nan/inf genuinely invalid; tests assert the message (`test_strategy_validation.py:11–27`). |
| `_fraction` on optional `equity_share_end`, `floor_share` (56–59) | (e) | `None` still allowed; only validates when set. |
| `region_weights` nonempty, real, finite, `>=0`, sum `1 ± 1e-8`, re-normalised (61–75) | (e) | Default `(0.6,0.3,0.1)` and production 9-fund weights both sum to 1; normalisation is exact-up-to-1e-8 and tested (`:51`). |
| `bond_vehicle ∈ {VGIT, IBTM}` (77–78) | (e) | Only these two are used anywhere. |
| `floor_year ∈ {2029, 2030, 2031, 2032}` (79–81) | (e) | All callers use 2030/2031; the engine ignores other years, so rejecting is right. |
| `ratchet_trigger` finite, `>=0` (82–89) | (e) | Callers pass `None`, `1.1`, `1.2`. |

### `engine.py` — `run` preamble

| Check (where) | Verdict | Evidence |
|---|---|---|
| `st` is a `Strategy` (361–362) | (e) | Was `AttributeError`; every caller passes `Strategy`/`IPS`. |
| `cfg` is `EngineConfig | None` (`_engine_config`, 245–251) | (e) | All callers pass `EngineConfig` or `None`. Note: returns the same object, which is the root of F3. |
| `snapshot_2031` is boolean (364–365) | (e) | Callers pass `True`/`False`/`np.bool_`. |
| scenario `m0` is an `Integral` in `[0, M_2033]` (366–368) | (e) | `simulate` always sets it; nested runs use 50. |
| `sc.n` positive `Integral` (370–372) | (e) | `Scenarios.n` is always `beta.shape[0] >= 1`. |
| `eq_log` finite numeric, 3-D, covers horizon, `>=1` equity (370, 373–377) | (d) for non-3-D; (e) otherwise | Valid paths are unaffected; the 2-D message is F2. The explicit `ndim != 3` branch (374–375) is unreachable because `_finite_path(..., (n, None, None))` already requires 3-D. |
| `len(region_weights) == K` (379–380) | (e) | Production replaces `IPS` with 9 weights against 9-equity scenarios; tests use 3/3. |
| `eq_er` real vector, shape `(K,)`, finite, `[0, 12)` (381–390) | (e) for values, (c) side effect | Valid ratios (0.0–0.0012) pass; the accepted set is sensible. The `cfg.eq_er = tuple(eq_er)` assignment is F3. |
| `commissions`, `compound_costs`, `sell_at_settlement` are boolean (198–200) | (e) | Dataclass defaults and all callers use booleans. |
| `extra_tickets` nonnegative `Integral` (201–202) | (e) | Default 0; no caller uses a bool/float. |
| `extra_ticket_min`, `annual_cost` finite `>=0` (203–204) | (e) | Defaults 0.0; `report_numbers` overrides with positive floats. |
| `kappa0 > -1`, `kappa_rate_slope` finite, `kappa_rate_ref` required iff slope `!= 0` (205–211) | (e) | Only `scripts/ladder_premium.py` sets the slope, and it always sets the ref; default slope is 0. |
| `deposits`: sequence or `Mapping`, unique `Integral` months in `[0, M_2033]`, finite `>=0` amounts (213–230) | (e) | Default is `{M_2027: 2000, M_2028: 2000}`; no script overrides with float months or duplicates. |
| `fund_groups` partitions `range(K)` exactly once (232–240) | (e) | Only `BASELINE_FUNDS` (a partition of 9) and `None` are used. |
| `beta`, `infl`, `fx_log`, `tw_cost_log` finite with shape `(n, >= horizon+1)`; `resid` length `len(TAU_GRID)` (392–396) | (e) for ndarrays, (b) for lists | `simulate` always emits float ndarrays; the list loophole is F4. |
| Nested runner `m0 > M_2027` requires `fx_log_2027`/`tw_cost_log_2027` (397–407) | (e) | `finite` emits both; the inner `simulate(start=...)` propagates them; `test_real_nested_paths.py` covers both the accepted and rejected cases. |
| `rate_floor` finite real scalar (408–415) | (e) | `Scenarios` default `-0.005`; `esg` sets a float. |
| `state` is an `engine.State` (416–423) + `_validate_state` shapes/finite/nonneg/`locked ∈ [0,1]`/`ratchet_ref >= 0` (126–178) | (e) | Every caller passes `State` from `run`/`state_for`; the checks match the engine's invariants. `_validate_state` also rewrites the arrays to float64 in place — benign, no caller reuses the object afterwards. |
| `kappa()` result finite and `> -100%` (69–70) | (e) | `kappa0` default 0.018 and fitted slopes keep it far from the bound. |

### `engine.py` — `conditional_2031*`

| Check (where) | Verdict | Evidence |
|---|---|---|
| `state_for`: `n` positive integer, `snap` is `State`, `i` integer index in range (527–534) | (e) | Policy search passes indices from the same snapshot. |
| `_positive_integer`, `_quote_seed` helpers (543–556) | (e) | `n_inner=50/400`, `seed` int or `None`; scripts do not pass 0 or float. |
| `_conditional_rank`: `res` is a `Mapping`; `sc.n` positive; `state_2031` present; `floor_2033`/`growth_2031`/`assets_2031` finite `(n,)` (558–582) | (e) | All values come from `engine.run(..., snapshot_2031=True)`; `run` setdefaults `floor_2033`/`growth_2031` for every result. |
| `conditional_2031`: `st`/`cfg`/`keep_drift` types, `n_inner`, `seed`, explicit `i` in `[0, n)`, nested baselines present (591–622) | (e) | Policy search passes `i=None` or a real index; `params` is not validated (pre-existing, unchanged). |
| `conditional_2031_band`: `q`/`width` finite in `[0,1]`, `n_inner`/`k` positive, `seed`, `st`/`cfg`, `k <= n` (657–671) | (e) | Callers use `q=0.5, width=0.05, k=3`, all within range. |
| `percentiles` nonempty, unique, finite in `[0,100]` (672–675) | **(c) — F1** | Lists/defaults are fine; a one-shot iterator is consumed by `tuple(percentiles)` and then lost. |

## Confirmed findings

### F1 — band percentiles: iterator consumed by validation, then looped again (class c, regression)

`conditional_2031_band` normalises the iterable at `engine.py:673` (`raw_percentiles = tuple(percentiles)`,
then `pcs = ...`) but the output loop at `engine.py:687` still iterates the **original** object.
For a generator, validation exhausts it, so no `pXX` keys are produced. At `f6e0613` the function
iterated the generator only once (no validation), so generators worked — this diff introduces
the regression. It is silent because the summary line falls back: `out["median"] = out.get("p50", ...)`.

Repro (n=40, seed=7, k=3, n_inner=50):

```
generator keys: ['floor', 'floor_range', 'growth_2031', 'median', 'scenarios']
list keys:      ['floor', 'floor_range', 'growth_2031', 'median', 'p5', 'p50', 'p95', 'scenarios']
```

Every in-repo caller passes `[5, 50, 95]` or the default tuple, so reports are unaffected.
Fix: loop `pcs` (or `raw_percentiles`) instead of `percentiles`.

### F2 — 2-D `eq_log` names placeholder axes (class d, cosmetic)

`_finite_path("eq_log", sc.eq_log, (int(n), None, None))` (`engine.py:373`) formats its message
with the expected shape, so a 2-D array yields
`scenarios.eq_log must be a finite numeric array with shape (40, None, None)`. The explicit
`if eq_log.ndim != 3` check (`engine.py:374–375`, which would report
`(n, months, equities)`) is unreachable: `_finite_path` already enforces `ndim == len(shape) == 3`
before returning. The error is correct in substance, wrong in presentation. Fix: perform the
ndim check before `_finite_path`, or pass the actual/expected text into `_finite_path`.

### F3 — `run` mutates the caller's config (class c, minor)

`cfg.eq_er = tuple(eq_er)` at `engine.py:390` writes through the caller's object because
`_engine_config` (`engine.py:245–251`) returns `cfg` unchanged. A list input is left as a tuple
of `np.float64` after `run`:

```
before ('list', 'float') -> after ('tuple', 'float64')
```

No caller reads `cfg.eq_er` after `run`, and no test depends on the mutation, so impact is
limited to surprise/reentrancy. Fix: `cfg = dc.replace(cfg)` when `cfg` is not `None`, or keep
the converted tuple in a local used by the equity update (`engine.py:339`).

### F4 — array-likes pass validation, originals crash later (class b, low)

`_finite_path` validates and returns a converted float array, but `run` discards the return
values and keeps using `sc.fx_log`, `sc.tw_cost_log`, etc. A list-of-lists input therefore passes
validation and fails at `engine.py:399–400` with
`TypeError: list indices must be integers or slices, not tuple`, rather than the promised
`ValueError: scenarios.fx_log ...`. `beta` as a list fails earlier at `sc.n` with `AttributeError`
(pre-existing property access), and `resid` as a list runs fine because nothing reads it after
validation. Only hand-built inputs are affected; `simulate` always returns ndarrays.

Fix: keep the validated arrays (`sc = dc.replace(sc, fx_log=..., tw_cost_log=..., ...)`) or use
the returned arrays in the settlement block.

## Timing

Method: cached one 20,000-path scenario set (`simulate(params, n=20000, seed=11)`) to an npz,
then timed `engine.run(IPS_9w, sc, cfg=EngineConfig(eq_er=tuple(9)), snapshot_2031=False)`
five times per build and took the median. Old = `f6e0613` `engine.py`/`strategies.py`, new =
`b8c0036`. Same machine, same data, alternating runs.

| Pass | new (b8c0036) | old (f6e0613) | overhead |
|------|---------------|---------------|----------|
| 1 | 0.323 s | 0.300 s | +23 ms (~7.7%) |
| 2 | 0.396 s | 0.375 s | +21 ms (~5.6%) |

Both builds returned `facility_median = 196989` on every run, so the checks do not perturb
results. The absolute times move between passes (background load), but the deltas agree:
validation costs roughly **20–25 ms per `run`, 5–8%**, on a 20k-path horizon. That is a
reasonable price for the added checks; no optimisation is needed for the loop's purposes.

## Residual observations (no action required)

- `_finite_path` converts to float but callers keep the originals; besides F4 this means integer
  scenario arrays stay integer (harmless — arithmetic upcasts).
- `state_for` with a ragged `snap.eq` list raises numpy's own `ValueError` before the index
  check; only invalid hand-built snapshots are affected.
- `conditional_2031(params=None)` raises `TypeError` rather than `ValueError`; `params` was
  never validated and no caller passes `None` (pre-existing).
- The nested-run real-facility change (baseline now `fx_log_2027`/`tw_cost_log_2027` instead of
  month 0 of the inner path) is a genuine fix, covered by
  `test_real_nested_paths.py::test_nested_real_facility_uses_january_2027_not_january_2031`.

## Reproducer

```
PYTHONPATH=$PWD/src /Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python \
    docs/loop/r7_review_engine_repro.py
```

Output at `b8c0036` + `de2d8cd`:

```
F1 REPRO -- band percentile iterator exhausted by validation -- expected ['p5', 'p50', 'p95'] for both, got generator ['floor', 'floor_range', 'growth_2031', 'median', 'scenarios'] / list ['floor', 'floor_range', 'growth_2031', 'median', 'p5', 'p50', 'p95', 'scenarios']
F2 REPRO -- 2-D eq_log error names placeholder axes -- expected an error naming (n, months, equities), got: scenarios.eq_log must be a finite numeric array with shape (40, None, None)
F3 REPRO -- run() mutates caller cfg.eq_er -- expected (list, float) unchanged, got ('list', 'float') -> ('tuple', 'float64')
F4 REPRO -- list fx_log passes validation then crashes -- expected ValueError 'scenarios.fx_log...', got TypeError: list indices must be integers or slices, not tuple
F4 REPRO -- list tw_cost_log passes validation then crashes -- expected ValueError 'scenarios.tw_cost_log...', got TypeError: list indices must be integers or slices, not tuple
F4 note -- same list input for `resid` runs fine: it is validated but never used by run()
```

All outputs are stable across repeated runs. The F1 lines are deterministic; the F3 dtypes are
exact; F4's message is Python's own list-index error.
