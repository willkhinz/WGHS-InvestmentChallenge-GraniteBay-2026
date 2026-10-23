"""Tests for ESG v2 enhancements: expected-return uncertainty and volatility clustering."""
import dataclasses as dc

import numpy as np
import pytest

from lgm import engine
from lgm.calibrate import calibrate_cma_dispersion, calibrate_equity_garch
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS


def _start_state(p, n):
    return {
        "beta": np.tile(p.beta0, (n, 1)),
        "infl": np.full(n, p.infl0),
        "fx_log": np.zeros(n),
        "tw_cost_log": np.zeros(n),
    }


def test_eq_mu_cov_none_reproduces_exact():
    """Setting eq_mu_cov=None reproduces baseline scenarios exactly."""
    core = build_core()
    p1 = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p2 = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p2.eq_mu_cov = None

    sc1 = simulate(p1, n=2000, seed=42)
    sc2 = simulate(p2, n=2000, seed=42)

    assert np.array_equal(sc1.eq_log, sc2.eq_log)
    assert np.array_equal(sc1.beta, sc2.beta)
    assert np.array_equal(sc1.infl, sc2.infl)
    assert np.array_equal(sc1.fx_log, sc2.fx_log)
    assert np.array_equal(sc1.tw_cost_log, sc2.tw_cost_log)


def test_calibrate_cma_dispersion():
    """CMA cross-firm dispersion produces valid covariance matrix matching region structure."""
    cov = calibrate_cma_dispersion()
    K = len(CORE)
    assert cov.shape == (K, K)
    assert np.allclose(cov, cov.T)
    # Eigenvalues must be non-negative (PSD)
    eigs = np.linalg.eigvalsh(cov)
    assert np.all(eigs >= -1e-12)

    # Assets in the same region must share identical variances and covariances:
    # US large growth (0), US large value (1), US small cap (2)
    assert np.isclose(cov[0, 0], cov[1, 1])
    assert np.isclose(cov[0, 1], cov[0, 0])
    # Europe (3) and Japan (4) are both intl_dev
    assert np.isclose(cov[3, 3], cov[4, 4])
    assert np.isclose(cov[3, 4], cov[3, 3])


def test_eq_mu_cov_spread_and_antithetic():
    """With eq_mu_cov, cross-scenario spread matches covariance and antithetic pairs mirror."""
    core = build_core()
    cov_cma = calibrate_cma_dispersion()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_mu_cov = cov_cma

    n = 30000
    sc = simulate(p, n=n, seed=7)
    assert sc.eq_drift_err is not None
    half = n // 2

    # Antithetic mirroring
    assert np.allclose(sc.eq_drift_err[:half], -sc.eq_drift_err[half:])
    assert np.allclose(sc.eq_drift_err.mean(axis=0), 0.0)

    # Spread of the drawn drifts matches cov_cma within sampling error
    drift_cov = np.cov(sc.eq_drift_err, rowvar=False)
    assert np.allclose(drift_cov, cov_cma, atol=2.5e-5)

    # Cross-scenario spread of annualised mean log returns
    # Var(12 * mean_m) = Var(drift) + (144 / M) * Var(shock)
    ann_mean = sc.eq_log.mean(axis=1) * 12
    sample_ann_cov = np.cov(ann_mean, rowvar=False)
    expected_ann_cov = cov_cma + (144.0 / p.months) * p.cov[:len(CORE), :len(CORE)]
    assert np.allclose(sample_ann_cov, expected_ann_cov, atol=1e-3)


def test_conditional_2031_drift_handling():
    """Nested simulation conditional_2031 respects keep_drift parameter."""
    core = build_core()
    cov_cma = calibrate_cma_dispersion()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_mu_cov = cov_cma

    sc = simulate(p, n=500, seed=11)
    import dataclasses as dc
    st = dc.replace(IPS, region_weights=tuple(core["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE))
    r = engine.run(st, sc, cfg, snapshot_2031=True)

    # With keep_drift=True (default), inner simulation preserves scenario i's drawn drift
    target_idx = 10
    expected_drift = sc.eq_drift_err[target_idx]

    start = {"beta": sc.beta[target_idx, engine.M_2031 - sc.m0],
             "infl": sc.infl[target_idx, engine.M_2031 - sc.m0],
             "fx_log": np.full(100, sc.fx_log[target_idx, engine.M_2031 - sc.m0]),
             "tw_cost_log": np.full(100, sc.tw_cost_log[target_idx, engine.M_2031 - sc.m0]),
             "eq_drift_err": expected_drift}
    inner = simulate(p, n=100, seed=99, start=start, m0=engine.M_2031)
    assert np.allclose(inner.eq_drift_err, expected_drift)

    # Calling conditional_2031 directly runs without error
    cond_kept = engine.conditional_2031(st, sc, r, p, i=target_idx, n_inner=200, cfg=cfg, keep_drift=True)
    cond_redrawn = engine.conditional_2031(st, sc, r, p, i=target_idx, n_inner=200, cfg=cfg, keep_drift=False)
    assert "floor" in cond_kept
    assert "floor" in cond_redrawn


def test_eq_garch_none_reproduces_exact():
    """Setting eq_garch=None reproduces baseline scenarios exactly."""
    core = build_core()
    p1 = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p2 = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p2.eq_garch = None

    sc1 = simulate(p1, n=2000, seed=42)
    sc2 = simulate(p2, n=2000, seed=42)

    assert np.array_equal(sc1.eq_log, sc2.eq_log)
    assert np.array_equal(sc1.beta, sc2.beta)
    assert sc1.garch_h is None
    assert sc2.garch_h is None


def test_calibrate_equity_garch():
    """GARCH calibration on VTI yields stationary parameters and valid historical autocorrelations."""
    cal = calibrate_equity_garch()
    assert 0.0 < cal["alpha"] < 0.5
    assert 0.0 < cal["beta"] < 0.95
    assert cal["persistence"] < 1.0
    assert cal["uncond_vol_ann"] > 0.10
    assert 0.0 < cal["h0_today"] < 2.0
    assert len(cal["autocorr_lags_1_6"]) == 6
    # History has positive lag-1 autocorrelation
    assert cal["autocorr_lags_1_6"][0] > 0.20


def test_eq_garch_vol_and_median_invariants():
    """GARCH(1,1) preserves unconditional annual volatility (within 0.2 pts) and median return (within 0.1%/yr)."""
    core = build_core()
    cal = calibrate_equity_garch()
    p_base = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p_garch = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p_garch.eq_garch = (cal["alpha"], cal["beta"], 1.0)

    n = 20000
    sc_base = simulate(p_base, n=n, seed=11)
    sc_garch = simulate(p_garch, n=n, seed=11)

    # 1. Unconditional annual volatility within 0.2 points (0.002) of today's
    vols_base = sc_base.eq_log.std(axis=(0, 1)) * np.sqrt(12)
    vols_garch = sc_garch.eq_log.std(axis=(0, 1)) * np.sqrt(12)
    vol_diff = np.abs(vols_garch - vols_base) * 100
    assert np.max(vol_diff) < 0.20

    # 2. Median 74-month return within 0.1%/yr of today's
    meds_base = np.median(np.exp(sc_base.eq_log.sum(axis=1)) ** (12 / p_base.months) - 1, axis=0)
    meds_garch = np.median(np.exp(sc_garch.eq_log.sum(axis=1)) ** (12 / p_garch.months) - 1, axis=0)
    med_diff = np.abs(meds_garch - meds_base) * 100
    assert np.max(med_diff) < 0.10

    # 3. GARCH variance array present and symmetric under antithetic pairing
    assert sc_garch.garch_h is not None
    half = n // 2
    assert np.allclose(sc_garch.garch_h[:half], sc_garch.garch_h[half:])


def test_eq_garch_autocorrelation_clustering():
    """GARCH process generates positive squared-return autocorrelation at lags 1-6."""
    import pandas as pd
    core = build_core()
    cal = calibrate_equity_garch()
    p_garch = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p_garch.eq_garch = (cal["alpha"], cal["beta"], 1.0)

    sc = simulate(p_garch, n=5000, seed=11)
    acs = []
    for i in range(2000):
        s = pd.Series((sc.eq_log[i, :, 0] - sc.eq_log[i, :, 0].mean()) ** 2)
        acs.append([s.autocorr(lag) for lag in range(1, 7)])
    mean_ac = np.nanmean(acs, axis=0)

    # Lag 1 autocorrelation must be significantly positive (clustering)
    assert mean_ac[0] > 0.05
    # Positive at lags 1, 2, 3
    assert mean_ac[1] > 0.03
    assert mean_ac[2] > 0.02


@pytest.mark.parametrize("spec", [
    (0.1,), (-0.1, 0.2), (0.1, -0.2), (0.5, 0.5), (np.nan, 0.2), (0.1, 0.2, 0.0),
    {"alpha": 0.1, "beta": 0.2, "factor_idx": 99},
    {"alpha": 0.1, "beta": 0.2, "factor_idx": 0.5},
    {"alpha": 0.1, "beta": 0.2, "factor_idx": 0.0},
    {"alpha": 0.1, "beta": 0.2, "factor_idx": True},
])
def test_invalid_garch_configurations_are_rejected(spec):
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_garch = spec
    with pytest.raises(ValueError, match="eq_garch"):
        simulate(p, n=2, seed=1)


@pytest.mark.parametrize("scale", [0.0, -1.0, np.nan, np.inf, "invalid", None, True, False])
def test_garch_requires_positive_equity_volatility_scale(scale):
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_garch = (0.1, 0.2, 1.0)
    p.eq_vol_scale = scale
    with pytest.raises(ValueError, match="eq_vol_scale"):
        simulate(p, n=2, seed=1)


@pytest.mark.parametrize("scale", [-1.0, np.nan, np.inf, "invalid", None, True, False])
def test_equity_volatility_scale_rejects_invalid_values_without_garch(scale):
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_vol_scale = scale
    with pytest.raises(ValueError, match="eq_vol_scale"):
        simulate(p, n=2, seed=1)


def test_zero_equity_volatility_scale_is_a_valid_stress_without_garch():
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_vol_scale = 0.0
    sc = simulate(p, n=2, seed=1)
    expected = np.log1p(p.eq_geo) / 12.0
    np.testing.assert_array_equal(sc.eq_log, np.broadcast_to(expected, sc.eq_log.shape))


@pytest.mark.parametrize("start_h", [-0.1, np.nan, np.inf, True])
def test_garch_rejects_invalid_starting_variances(start_h):
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_garch = (0.1, 0.2, 1.0)
    with pytest.raises(ValueError, match="starting garch_h"):
        simulate(p, n=2, seed=1, start={**_start_state(p, 2), "garch_h": start_h})


@pytest.mark.parametrize("start_h", [np.ones(1), np.ones((2, 1))])
def test_garch_rejects_misshaped_starting_variances(start_h):
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_garch = (0.1, 0.2, 1.0)
    with pytest.raises(ValueError, match="starting garch_h must be a scalar or have shape"):
        simulate(p, n=2, seed=1, start={**_start_state(p, 2), "garch_h": start_h})


def test_garch_starting_variance_scalar_and_path_vector_are_equivalent():
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p.eq_garch = (0.1, 0.2, 1.0)
    start = _start_state(p, 4)
    scalar = simulate(p, n=4, seed=6, start={**start, "garch_h": 0.7})
    vector = simulate(p, n=4, seed=6, start={**start, "garch_h": np.full(4, 0.7)})
    np.testing.assert_array_equal(scalar.eq_log, vector.eq_log)
    np.testing.assert_array_equal(scalar.garch_h, vector.garch_h)


def test_garch_tuple_and_mapping_configs_match():
    core = build_core()
    params = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p_tuple = dc.replace(params, eq_garch=(0.1, 0.7, 1.0))
    p_mapping = dc.replace(params, eq_garch={"alpha": 0.1, "beta": 0.7, "h0": 1.0, "factor_idx": 0})
    a = simulate(p_tuple, n=100, seed=4)
    b = simulate(p_mapping, n=100, seed=4)
    np.testing.assert_array_equal(a.eq_log, b.eq_log)
    np.testing.assert_array_equal(a.garch_h, b.garch_h)


def test_cov_list_of_lists_works_with_garch_and_correlation():
    """Regression: a list-of-lists cov should work (validated into shock_cov)."""
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    p_list_cov = dc.replace(p, cov=p.cov.tolist())
    # With GARCH
    p_garch = dc.replace(p_list_cov, eq_garch=(0.1, 0.7, 1.0), months=2)
    sc1 = simulate(p_garch, n=2, seed=0)
    assert sc1.eq_log.shape == (2, 2, 9)
    # With Taiwan cost correlation
    p_corr = dc.replace(p_list_cov, tw_cost_corr=0.3, tw_cost_fx_corr=None, months=2)
    sc2 = simulate(p_corr, n=2, seed=0)
    assert sc2.tw_cost_log.shape == (2, 3)


def test_tw_cost_state0_param_error_message():
    """Regression: bad param-level tw_cost_state0 names the parameter, not start[...]."""
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    with pytest.raises(ValueError, match=r"^tw_cost_state0 must contain finite numeric values$"):
        simulate(dc.replace(p, tw_cost_state0=(np.nan, 0.0), months=2), n=2, seed=0)
