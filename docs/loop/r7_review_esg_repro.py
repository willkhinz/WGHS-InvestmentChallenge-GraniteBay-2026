"""Reproducers for docs/loop/r7_review_esg_findings.md.

Run from the worktree root with its src first on the path:
    PYTHONPATH=<worktree>/src <venv>/bin/python docs/loop/r7_review_esg_repro.py

Each function prints the expected result and the actual one. Nothing here mutates files.
"""
from __future__ import annotations

import dataclasses as dc

import numpy as np

from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params


def _params():
    """The parameters the headline numbers use (same construction as tests/test_taiwan_esg.py)."""
    core = build_core()
    return esg_params(core["cal"], core["table"]["bl_geo_total"].values)


def _report(label, expected, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - the exception type is the finding
        print(f"{label}\n  expected: {expected}\n  actual:   {type(exc).__name__}: {exc}")
    else:
        print(f"{label}\n  expected: {expected}\n  actual:   ran without error")


def finding_1_raw_cov_after_validation():
    """(b) `cov` is normalized into `shock_cov`, but three later uses index the raw attribute."""
    p = _params()
    list_cov = p.cov.tolist()

    def garch_path():
        simulate(dc.replace(p, cov=list_cov, eq_garch=(0.1, 0.7, 1.0), months=2), n=2, seed=0)

    def correlation_path():
        simulate(dc.replace(p, cov=list_cov, tw_cost_corr=0.3, tw_cost_fx_corr=None, months=2),
                     n=2, seed=0)

    # The new validator converts list input with np.asarray and accepts it; `simulate` then does
    # p.cov[factor_idx, factor_idx] (line 490) or p.cov[K+3, K+3] / p.cov[K+4, K+4] (599/604).
    _report(
        "finding_1 (b) cov given as a list-of-lists, GARCH path (line 490):",
        "the validated matrix is used, or cov is rejected while validating",
        garch_path,
    )
    _report(
        "finding_1 (b) cov given as a list-of-lists, correlation path (line 599):",
        "the validated matrix is used, or cov is rejected while validating",
        correlation_path,
    )


def finding_2_param_state_error_names_start():
    """(d) Param-level initial state is reported as if it came from `start`."""
    p = _params()
    assert p.tw_cost_state0 is not None, "the fitted parameters must carry tw_cost_state0 for this probe"
    # No `start` is passed: the bad value is p.tw_cost_state0.
    _report(
        "finding_2 (d) p.tw_cost_state0=(nan, 0.0), start=None:",
        "ValueError naming tw_cost_state0 (the parameter that was actually set)",
        lambda: simulate(dc.replace(p, tw_cost_state0=(np.nan, 0.0), months=2), n=2, seed=0),
    )


def finding_3_dof_infinity_string():
    """(d) The `_dof` message advertises positive infinity, but the string "inf" is rejected."""
    p = _params()

    def rate_dof_inf():
        simulate(dc.replace(p, rate_dof="inf", months=2), n=2, seed=0)

    def other_field_numeric_string():
        # Contrast: other field validators coerce numeric strings.
        simulate(dc.replace(p, tw_cost_corr="0.3", tw_cost_fx_corr=None, months=2), n=2, seed=0)

    _report(
        "finding_3 (d) rate_dof='inf':",
        "accepted as positive infinity (the message lists positive infinity as allowed)",
        rate_dof_inf,
    )
    _report(
        "finding_3 (d) contrast, tw_cost_corr='0.3':",
        "accepted, because float(value) coercion is used here",
        other_field_numeric_string,
    )


if __name__ == "__main__":
    finding_1_raw_cov_after_validation()
    finding_2_param_state_error_names_start()
    finding_3_dof_infinity_string()
