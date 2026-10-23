# r7-scripts findings — scripts outside `run_all` after the 2026-10-22 input validation

Branch `r7-scripts`, based on `improve` at `9a14f67`. All runs used
`PYTHONPATH=<worktree>/src` with `PY=/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`.
Wall times are `/usr/bin/time -p` `real` seconds for the command shown in the same row.

## Summary

- All ten scripts were attempted and exit 0 on the fixed tree. **No validation check in `src/lgm`
  rejected a legitimate input**, so no production code was changed.
- Two scripts were stale config writers and were fixed (one commit each). Both fixes have a
  regression test that fails on the previous script.
- Baseline before fixes: `393 passed in 25.09s`, pyflakes clean, `run_all.py` 109.46s with reports
  byte-identical. Final after fixes: `395 passed in 25.17s`, pyflakes clean, `run_all.py` 120.79s
  with `git status --short reports/` empty.
- Commands for the final checks:
  - `$PY -m pytest` (bare, because `pyproject.toml` sets `addopts = "-q"`; `pytest -q` becomes
    `-qq` and suppresses the summary line)
  - `$PY -m pyflakes src scripts tests`
  - `$PY scripts/run_all.py`

## Runs

| Script | Command | Wall (s) | Outcome | Fix commit |
|---|---|---:|---|---|
| `esg_garch_conditional.py` | `$PY scripts/esg_garch_conditional.py` | 14.57 | ran | — |
| `esg_variants.py` | `$PY scripts/esg_variants.py 200` | 26.53 | ran (200 scenarios: cheapest path) | — |
| `fx_drift_study.py` | `$PY scripts/fx_drift_study.py` | 0.86 | ran | — |
| `policy_search.py` | `$PY scripts/policy_search.py --grid --workers 4` | 262.10 | ran (full grid) | — |
| `rate_tails.py` | `$PY scripts/rate_tails.py` | 2.03 | ran | — |
| `rate_tails_impact.py` | `$PY scripts/rate_tails_impact.py` | 13.57 | ran | — |
| `round6_waterfall.py` | `$PY scripts/round6_waterfall.py` | 8.37 | ran | — |
| `taiwan_costs.py` | `$PY scripts/taiwan_costs.py` | 0.47 | ran; fixed stale output path | `b30b5c4` |
| `taiwan_validation.py` | `$PY scripts/taiwan_validation.py` | 3.77 | ran | — |
| `taiwan_variants.py` | `$PY scripts/taiwan_variants.py` | 4.90 | ran; fixed stale config template | `f8b264b` |

No script needed the network; the cached inputs were sufficient.

## Fixes

### `f8b264b` — `taiwan_variants.py` config template lost a scoring field

Running the script exited 0 but rewrote `config/taiwan.yaml` from an embedded template that predates
`usd_twd_innovation_corr` (added to the live config in `b03cab2`). The next `esg_params()` call then
raised `KeyError: 'usd_twd_innovation_corr'` in `src/lgm/growth/scoring.py:48`, so the script was
destructive to later runs despite its own success.

Fix: hoist the template to `CONFIG_YAML` and restore the field (and its comment) exactly as it
appears in the live config. Regression test
`tests/test_taiwan_esg.py::test_variant_study_config_template_matches_live_config` asserts the
template equals `config/taiwan.yaml`; it fails on the previous script because `CONFIG_YAML` does not
exist. Re-running the fixed script leaves `config/taiwan.yaml` byte-identical.

### `b30b5c4` — `taiwan_costs.py` overwrote the live config with the r1 proposal

The r1 calibration writes a complete `config/taiwan.yaml`, but its schema predates the r2/r3
rewrite (no `fitted_monthly` section), so running it broke `esg_params()` for every later script.

Fix: write the proposal to `config/taiwan_costs_proposal.yaml` instead; updated the docstring,
comment, and print. Regression test
`tests/test_taiwan.py::test_taiwan_costs_proposal_does_not_overwrite_live_config` asserts the path
is the proposal file and not the live config; it fails on the previous script. Re-running the fixed
script leaves `config/taiwan.yaml` untouched; the generated proposal was deleted after verification.

## Reports the ten scripts rewrite

Identical re-run (no diff, nothing to commit):

- `reports/fx_drift_study.csv`
- `reports/fx_forward_check.csv`
- `reports/rate_tails.csv`
- `reports/round6_waterfall.csv`
- `reports/taiwan_costs.json`
- `config/taiwan.yaml` (after `f8b264b`; previously clobbered by both Taiwan scripts)

Differed from `HEAD` and were restored (not committed), because the committed reports predate the
2026-10-22 model/config changes, and `esg_variants` was run at 200 scenarios rather than the
committed 20,000:

- `reports/esg_garch_conditional.csv`
- `reports/esg_garch_headline.csv`
- `reports/esg_variants.csv`
- `reports/policy_search.csv`
- `reports/policy_search_top.csv`
- `reports/rate_tails_impact.csv`
- `reports/taiwan_validation.csv`
- `reports/taiwan_variants.csv`

After restoring those and deleting the proposal, `git status --short` was clean; after the final
`run_all.py`, `git status --short reports/` was empty.
