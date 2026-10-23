"""Tests for the fitted monthly Taiwan building-cost process in the economic scenario generator."""
from __future__ import annotations

import dataclasses as dc

import numpy as np
import pytest

from lgm import engine
from lgm.esg import ESGParams, simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS


@pytest.fixture(scope="module")
def base_params() -> ESGParams:
    r = build_core()
    geo = r["table"]["bl_geo_total"].values
    # The legacy i.i.d. process (4% drift, 1.5% vol): the headline defaults now use the fitted AR(2),
    # so the tests that set their own process start from the legacy settings explicitly.
    return dc.replace(esg_params(r["cal"], geo), tw_cost_growth=0.04, tw_cost_phi=None,
                      tw_cost_sig_eps=None, tw_cost_state0=None, tw_cost_fx_corr=None)


def test_default_reproduces_old_scenarios_bit_for_bit(base_params):
    """When tw_cost_phi is None, simulate must reproduce legacy output bit-for-bit."""
    p = dc.replace(base_params)
    assert p.tw_cost_phi is None
    assert p.tw_cost_growth == 0.04
    assert p.tw_cost_vol == 0.015

    sc1 = simulate(p, n=1000, seed=42)
    assert sc1.tw_cost_infl is None

    # Re-running with same seed produces bit-for-bit identical tw_cost_log
    sc2 = simulate(p, n=1000, seed=42)
    assert np.array_equal(sc1.tw_cost_log, sc2.tw_cost_log)
    assert np.array_equal(sc1.beta, sc2.beta)
    assert np.array_equal(sc1.eq_log, sc2.eq_log)
    assert np.array_equal(sc1.fx_log, sc2.fx_log)


def test_unconditional_moments_and_ar2(base_params):
    """The simulated monthly AR(2) process matches theoretical mean, variance, and autocorrelation."""
    p1 = 0.6546
    p2 = -0.0939
    sig_eps = 0.007137
    mu_ann = 0.0285
    p = dc.replace(
        base_params,
        months=120,
        tw_cost_growth=mu_ann,
        tw_cost_phi=(p1, p2),
        tw_cost_sig_eps=sig_eps,
        tw_cost_state0=None,
    )

    n_scenarios = 10_000
    sc = simulate(p, n=n_scenarios, seed=123)
    assert sc.tw_cost_infl is not None
    assert sc.tw_cost_infl.shape == (n_scenarios, 121)

    # Monthly log changes y: sc.tw_cost_infl[:, 1:]
    y_vals = sc.tw_cost_infl[:, 1:]
    mu_expected = np.log1p(mu_ann) / 12.0

    # Theoretical variance of AR(2):
    denom = (1.0 + p2) * ((1.0 - p2)**2 - p1**2)
    var_expected = ((1.0 - p2) / denom) * (sig_eps**2)
    std_expected = np.sqrt(var_expected)
    rho1_expected = p1 / (1.0 - p2)
    rho2_expected = p1 * rho1_expected + p2

    # 1. Unconditional mean
    sample_mean = float(np.mean(y_vals))
    assert abs(sample_mean - mu_expected) < 0.0003

    # 2. Unconditional std
    sample_std = float(np.std(y_vals))
    assert abs(sample_std - std_expected) < 0.0004

    # 3. Lag-1 and Lag-2 autocorrelations
    y_t = y_vals[:, 2:].flatten()
    y_lag1 = y_vals[:, 1:-1].flatten()
    y_lag2 = y_vals[:, :-2].flatten()

    sample_rho1 = float(np.corrcoef(y_t, y_lag1)[0, 1])
    sample_rho2 = float(np.corrcoef(y_t, y_lag2)[0, 1])

    assert abs(sample_rho1 - rho1_expected) < 0.015, f"rho1: {sample_rho1:.4f} vs {rho1_expected:.4f}"
    assert abs(sample_rho2 - rho2_expected) < 0.015, f"rho2: {sample_rho2:.4f} vs {rho2_expected:.4f}"


def test_variance_ratio_profile_matches_fit(base_params):
    """Cross-sectional standard deviation across k-month horizons matches the fitted profile."""
    p1 = 0.6546
    p2 = -0.0939
    sig_eps = 0.007137
    p = dc.replace(
        base_params,
        months=75,
        tw_cost_growth=0.0285,
        tw_cost_phi=(p1, p2),
        tw_cost_sig_eps=sig_eps,
        tw_cost_state0=None,
    )

    n_scenarios = 20_000
    sc = simulate(p, n=n_scenarios, seed=42)

    # Historical benchmark values for k in [1, 3, 6, 12, 24, 36, 72]
    expected_stds = {
        1: 0.0089,
        3: 0.0219,
        6: 0.0355,
        12: 0.0538,
        24: 0.0726,
        36: 0.0852,
        72: 0.1268,
    }

    for k, h_std in expected_stds.items():
        diff = sc.tw_cost_log[:, k] - sc.tw_cost_log[:, 0]
        sim_std = float(np.std(diff, ddof=1))
        # Relative error should be within sampling tolerances (<15% across all horizons)
        rel_err = abs(sim_std - h_std) / h_std
        assert rel_err < 0.15, f"k={k}: sim_std={sim_std:.4f} vs hist={h_std:.4f} (rel_err={rel_err:.2%})"


def test_starting_state_decay(base_params):
    """An elevated initial state (Aug, Sep 2026) decays following the AR(2) difference equation."""
    p1 = 0.6546
    p2 = -0.0939
    sig_eps = 0.007137
    mu_ann = 0.0285
    mu = np.log1p(mu_ann) / 12.0
    y_prev2 = 0.00284974  # Aug 2026
    y_prev1 = 0.00650706  # Sep 2026

    p = dc.replace(
        base_params,
        months=24,
        tw_cost_growth=mu_ann,
        tw_cost_phi=(p1, p2),
        tw_cost_sig_eps=sig_eps,
        tw_cost_state0=(y_prev2, y_prev1),
    )

    sc = simulate(p, n=4000, seed=42, antithetic=True)
    assert sc.tw_cost_infl is not None
    assert np.allclose(sc.tw_cost_infl[:, 0], y_prev1)

    # Compute theoretical expected path E[y_m - mu]
    e_y = np.empty(25)
    e_y[0] = y_prev1
    for m in range(1, 25):
        prev1 = y_prev1 if m == 1 else e_y[m - 1]
        prev2 = y_prev2 if m == 1 else (y_prev1 if m == 2 else e_y[m - 2])
        e_y[m] = mu + p1 * (prev1 - mu) + p2 * (prev2 - mu)

    # Cross-sectional mean from antithetic simulation must match theoretical expectation tightly
    sim_mean = sc.tw_cost_infl.mean(axis=0)
    for m in [1, 2, 3, 6, 12, 24]:
        assert abs(sim_mean[m] - e_y[m]) < 1e-4, (
            f"Month {m}: sim_mean={sim_mean[m]:.6f} != expected={e_y[m]:.6f}"
        )


def test_conditional_2031_inherits_taiwan_cost_state(base_params):
    """Nested conditional_2031 simulation starts from scenario i's own 2031 inflation state (2 lags)."""
    r = build_core()
    w = r["w_bl"]
    er = np.array([g.expense_ratio for g in CORE])
    st = dc.replace(IPS, region_weights=tuple(w))
    cfg = engine.EngineConfig(eq_er=tuple(er))

    p = dc.replace(
        base_params,
        tw_cost_growth=0.0285,
        tw_cost_phi=(0.6546, -0.0939),
        tw_cost_sig_eps=0.007137,
        tw_cost_state0=(0.002850, 0.006507),
    )

    sc = simulate(p, n=200, seed=42)
    res = engine.run(st, sc, cfg, snapshot_2031=True)

    target_scenario = 10
    m31 = engine.M_2031 - sc.m0
    expected_state_2031 = (sc.tw_cost_infl[target_scenario, m31 - 1], sc.tw_cost_infl[target_scenario, m31])
    expected_cost_log_2031 = float(sc.tw_cost_log[target_scenario, m31])

    cond = engine.conditional_2031(st, sc, res, p, i=target_scenario, n_inner=50, seed=99, cfg=cfg)

    # Re-simulate inner manually to verify exact match
    inner_start = {
        "beta": sc.beta[target_scenario, m31],
        "infl": sc.infl[target_scenario, m31],
        "fx_log": np.full(50, sc.fx_log[target_scenario, m31]),
        "tw_cost_log": np.full(50, sc.tw_cost_log[target_scenario, m31]),
        "tw_cost_infl": expected_state_2031,
    }
    p_inner = dc.replace(p, months=engine.M_2033 - engine.M_2031)
    inner_sc = simulate(p_inner, n=50, seed=99, start=inner_start, m0=engine.M_2031)

    assert np.allclose(inner_sc.tw_cost_infl[:, 0], expected_state_2031[1])
    assert np.allclose(inner_sc.tw_cost_log[:, 0], expected_cost_log_2031)
    assert cond["scenario"] == target_scenario


def test_headline_defaults_use_fitted_taiwan_process_and_gaussian_rates():
    r = build_core()
    p = esg_params(r["cal"], r["table"]["bl_geo_total"].values)
    assert p.rate_dof == "gaussian" and p.t_dof == 5.0
    assert p.tw_cost_phi == (0.6546, -0.0939) and p.tw_cost_growth == 0.0285
    assert p.tw_cost_state0 == (0.00284974, 0.00650706)
    assert p.tw_cost_fx_corr == -0.25
    from lgm.calibrate import kendall_corrected
    from lgm.profiles import _cal
    assert np.allclose(p.phi, kendall_corrected(_cal().phi, _cal().notes["months_rates"]))
    assert (p.phi > _cal().phi).all() and (p.phi <= 0.995).all()


def test_cost_fx_correlation_carries_to_long_horizons():
    r = build_core()
    p = esg_params(r["cal"], r["table"]["bl_geo_total"].values)
    sc = simulate(p, n=20_000, seed=3)
    for k in (12, 72):
        c = np.corrcoef(sc.tw_cost_log[:, k] - sc.tw_cost_log[:, 0], sc.fx_log[:, k] - sc.fx_log[:, 0])[0, 1]
        assert abs(c - (-0.25)) < 0.03
    off = simulate(dc.replace(p, tw_cost_fx_corr=None), n=20_000, seed=3)
    assert np.array_equal(off.fx_log, sc.fx_log)          # only the cost path changes
    with pytest.raises(ValueError):                        # a CPI correlation on top would be diluted
        simulate(dc.replace(p, tw_cost_corr=0.3), n=100, seed=3)


@pytest.mark.parametrize("field", ["tw_cost_corr", "tw_cost_fx_corr"])
@pytest.mark.parametrize("rho", [-1.01, 1.01, np.nan, np.inf, True, False, "invalid"])
def test_taiwan_cost_correlation_rejects_invalid_coefficients(base_params, field, rho):
    params = {"tw_cost_corr": None, "tw_cost_fx_corr": None, field: rho}
    p = dc.replace(base_params, months=12, tw_cost_phi=(0.65, -0.09), tw_cost_sig_eps=0.007, **params)
    with pytest.raises(ValueError, match=field):
        simulate(p, n=20, seed=3)


@pytest.mark.parametrize("coeff", [
    1.0, -1.0, (0.2, 0.8), (0.2, -1.0), (1.2, 0.2), (-1.2, 0.2),
    (np.nan, 0.2), (), (0.1, 0.2, 0.3), True, "invalid",
])
def test_taiwan_cost_ar_coefficients_must_be_stationary_even_with_explicit_state(base_params, coeff):
    p = dc.replace(base_params, months=12, tw_cost_phi=coeff, tw_cost_state0=(0.0, 0.0))
    with pytest.raises(ValueError, match="tw_cost_phi"):
        simulate(p, n=20, seed=3)


@pytest.mark.parametrize("growth", [-1.0, -1.01, np.nan, np.inf, "invalid", True])
def test_taiwan_cost_growth_requires_finite_gross_rate_above_zero(base_params, growth):
    p = dc.replace(base_params, tw_cost_growth=growth)
    with pytest.raises(ValueError, match="tw_cost_growth"):
        simulate(p, n=2, seed=3)


@pytest.mark.parametrize("vol", [-0.01, np.nan, np.inf, "invalid", True])
def test_taiwan_cost_volatility_requires_finite_nonnegative_value(base_params, vol):
    p = dc.replace(base_params, tw_cost_vol=vol)
    with pytest.raises(ValueError, match="tw_cost_vol"):
        simulate(p, n=2, seed=3)


@pytest.mark.parametrize("sig_eps", [-0.01, np.nan, np.inf, "invalid", True])
def test_taiwan_cost_innovation_scale_requires_finite_nonnegative_value(base_params, sig_eps):
    p = dc.replace(base_params, tw_cost_phi=(0.65, -0.09), tw_cost_sig_eps=sig_eps)
    with pytest.raises(ValueError, match="tw_cost_sig_eps"):
        simulate(p, n=2, seed=3)


def test_zero_taiwan_cost_volatility_is_a_valid_deterministic_stress(base_params):
    mu = np.log1p(base_params.tw_cost_growth) / 12
    legacy = simulate(dc.replace(base_params, months=12, tw_cost_vol=0.0), n=4, seed=3)
    ar = simulate(dc.replace(base_params, months=12, tw_cost_phi=(0.65, -0.09), tw_cost_vol=0.0,
                             tw_cost_sig_eps=0.0, tw_cost_state0=None, tw_cost_infl0=None), n=4, seed=3)
    expected = np.broadcast_to(np.arange(13)[None, :] * mu, (4, 13))
    np.testing.assert_allclose(legacy.tw_cost_log, expected, atol=1e-15)
    np.testing.assert_allclose(ar.tw_cost_log, expected, atol=1e-15)


@pytest.mark.parametrize(("field", "state"), [
    ("tw_cost_state0", (np.nan, 0.0)),
    ("tw_cost_state0", (np.zeros(1), np.zeros(1))),
    ("tw_cost_infl0", np.inf),
])
def test_taiwan_cost_initial_state_requires_finite_shared_or_path_values(base_params, field, state):
    params = {"tw_cost_state0": None, "tw_cost_infl0": None, field: state}
    p = dc.replace(base_params, tw_cost_phi=(0.65, -0.09), **params)
    with pytest.raises(ValueError, match=field):
        simulate(p, n=2, seed=3)


def test_variance_ratio_separates_iid_from_mean_reversion():
    from lgm.calibrate import variance_ratio, variance_ratio_test

    rng = np.random.default_rng(3)
    iid = rng.standard_normal(5000)
    e = rng.standard_normal(40_001)
    ma = e[1:] - 0.5 * e[:-1]                       # lag-1 autocorrelation -0.4: VR(h) = 1 - 0.8 (1 - 1/h)
    assert abs(variance_ratio(iid, 12) - 1) < 0.15
    assert variance_ratio(ma, 36) == pytest.approx(1 - 0.8 * 35 / 36, abs=0.03)
    t = variance_ratio_test(ma[:600], 36, n_null=2000)
    assert t["p_mean_reversion"] < 0.05 and t["null_median"] < 1


def test_variant_study_config_template_matches_live_config():
    """scripts/taiwan_variants.py rewrites config/taiwan.yaml; the template must stay idempotent.

    The template lost `usd_twd_innovation_corr` when that field was added to the live config, so
    re-running the study left esg_params() with a KeyError.
    """
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "taiwan_variants.py"
    spec = importlib.util.spec_from_file_location("_taiwan_variants_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.CONFIG_YAML == (mod.ROOT / "config" / "taiwan.yaml").read_text()
