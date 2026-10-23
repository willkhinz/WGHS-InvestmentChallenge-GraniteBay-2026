"""Tests for per-block tail options in ESGParams and rate tail behavior."""
import dataclasses as dc
import numpy as np
import pytest
from scipy import stats

from lgm import calibrate, esg, profiles


@pytest.fixture
def base_params():
    return profiles.cs_team(t_dof=5.0, months=12)


def test_default_rate_tails_bit_for_bit_identical(base_params):
    """Default ESGParams (rate_dof=None, rate_shared=0.0) must produce identical scenarios."""
    sc_default = esg.simulate(base_params, n=500, seed=42)

    # Explicitly identical parameters
    p_same = dc.replace(base_params, rate_dof=None, rate_shared=0.0, infl_dof=None, fx_dof=None)
    sc_same = esg.simulate(p_same, n=500, seed=42)

    np.testing.assert_array_equal(sc_default.beta, sc_same.beta)
    np.testing.assert_array_equal(sc_default.eq_log, sc_same.eq_log)
    np.testing.assert_array_equal(sc_default.infl, sc_same.infl)
    np.testing.assert_array_equal(sc_default.fx_log, sc_same.fx_log)
    np.testing.assert_array_equal(sc_default.tw_cost_log, sc_same.tw_cost_log)

    # Infinite degrees of freedom are the Gaussian limit and require no random mixing draw.
    sc_gaussian = esg.simulate(dc.replace(base_params, t_dof=np.inf), n=500, seed=42)
    sc_normal = esg.simulate(dc.replace(base_params, t_dof=None), n=500, seed=42)
    np.testing.assert_array_equal(sc_gaussian.eq_log, sc_normal.eq_log)
    np.testing.assert_array_equal(sc_gaussian.beta, sc_normal.beta)


@pytest.mark.parametrize("n", [0, -1, 1.5, True, "2"])
def test_scenario_count_must_be_positive_integer(base_params, n):
    with pytest.raises(ValueError, match="n must be a positive integer"):
        esg.simulate(base_params, n=n)


def _valid_start(p, n):
    return {
        "beta": np.tile(p.beta0, (n, 1)),
        "infl": np.full(n, p.infl0),
        "fx_log": np.zeros(n),
        "tw_cost_log": np.zeros(n),
    }


@pytest.mark.parametrize(("key", "value", "message"), [
    ("beta", np.zeros(2), r"start\['beta'\]"),
    ("beta", np.full((2, 3), np.nan), r"start\['beta'\]"),
    ("infl", np.zeros(1), r"start\['infl'\]"),
    ("fx_log", np.inf, r"start\['fx_log'\]"),
    ("tw_cost_log", np.zeros((2, 1)), r"start\['tw_cost_log'\]"),
    ("eq_drift_err", np.zeros(2), r"start\['eq_drift_err'\]"),
])
def test_continuation_state_rejects_invalid_values_and_shapes(base_params, key, value, message):
    start = _valid_start(base_params, 2)
    start[key] = value
    with pytest.raises(ValueError, match=message):
        esg.simulate(base_params, n=2, start=start)


def test_continuation_state_requires_core_fields(base_params):
    with pytest.raises(ValueError, match="start is missing required state keys"):
        esg.simulate(base_params, n=2, start={"beta": base_params.beta0})


@pytest.mark.parametrize("months", [0, -1, 1.5, True, "12"])
def test_horizon_must_be_positive_integer(base_params, months):
    p = dc.replace(base_params, months=months)
    with pytest.raises(ValueError, match="months must be a positive integer"):
        esg.simulate(p, n=2)


@pytest.mark.parametrize(("field", "value"), [
    ("beta0", np.array([np.nan, 0.0, 0.0])),
    ("beta_mu", np.zeros(2)),
    ("resid", np.zeros(2)),
    ("infl0", np.inf),
    ("infl_mu", "invalid"),
    ("fx_drift", True),
    ("rate_floor", np.nan),
])
def test_initial_curve_and_inflation_parameters_must_be_finite_and_well_shaped(base_params, field, value):
    p = dc.replace(base_params, **{field: value})
    with pytest.raises(ValueError, match=field):
        esg.simulate(p, n=2)


@pytest.mark.parametrize("m0", [-1, 1.5, True, "0"])
def test_start_month_must_be_nonnegative_integer(base_params, m0):
    with pytest.raises(ValueError, match="m0 must be a nonnegative integer"):
        esg.simulate(base_params, n=2, m0=m0)


@pytest.mark.parametrize("geo", [
    [-1.0, 0.05, 0.05], [np.nan, 0.05, 0.05], [np.inf, 0.05, 0.05],
    [True, False, True], [[0.05, 0.05, 0.05]], "invalid",
])
def test_equity_geometric_returns_must_be_finite_and_above_minus_one(base_params, geo):
    p = dc.replace(base_params, eq_geo=geo)
    with pytest.raises(ValueError, match="eq_geo must be a finite one-dimensional"):
        esg.simulate(p, n=2)


@pytest.mark.parametrize("phi", [
    [0.9, 1.0, 0.9], [0.9, -1.0, 0.9], [0.9, np.nan, 0.9],
    [0.9, np.inf, 0.9], [0.9, 0.8], "invalid", [False, False, False],
])
def test_rate_factor_persistence_requires_stationary_vector(base_params, phi):
    p = dc.replace(base_params, phi=phi)
    with pytest.raises(ValueError, match="phi must be a finite stationary length-3"):
        esg.simulate(p, n=2, seed=4)


@pytest.mark.parametrize("phi", [1.0, -1.0, np.nan, np.inf, "invalid", True])
def test_inflation_persistence_requires_stationary_coefficient(base_params, phi):
    p = dc.replace(base_params, infl_phi=phi)
    with pytest.raises(ValueError, match="infl_phi must be finite and stationary"):
        esg.simulate(p, n=2, seed=4)


@pytest.mark.parametrize("share", [True, False, -0.1, 1.1, np.nan, np.inf, "invalid", None])
def test_rate_shared_requires_a_numeric_fraction(base_params, share):
    p = dc.replace(base_params, rate_shared=share)
    with pytest.raises(ValueError, match="rate_shared"):
        esg.simulate(p, n=2, seed=4)


@pytest.mark.parametrize("bad_cov", [
    np.full((8, 8), np.nan), np.diag([-1.0] + [1.0] * 7), np.eye(7), np.eye(8, dtype=bool),
])
def test_monthly_shock_covariance_rejects_invalid_matrices(base_params, bad_cov):
    p = dc.replace(base_params, cov=bad_cov)
    with pytest.raises(ValueError, match="cov"):
        esg.simulate(p, n=2, seed=4)


def test_monthly_shock_covariance_rejects_asymmetry(base_params):
    cov = base_params.cov.copy()
    cov[0, 1] += 1e-4
    p = dc.replace(base_params, cov=cov)
    with pytest.raises(ValueError, match="cov must be symmetric"):
        esg.simulate(p, n=2, seed=4)


def test_expected_return_covariance_rejects_invalid_matrices(base_params):
    k = len(base_params.eq_geo)
    asymmetric = np.eye(k) * 1e-4
    asymmetric[0, 1] = 1e-3
    invalid = [
        np.eye(k - 1),
        asymmetric,
        np.diag([-1e-4] + [1e-4] * (k - 1)),
        np.full((k, k), np.nan),
        np.eye(k, dtype=bool),
    ]
    for cov in invalid:
        p = dc.replace(base_params, eq_mu_cov=cov)
        with pytest.raises(ValueError, match="eq_mu_cov"):
            esg.simulate(p, n=2, seed=4)


def test_zero_expected_return_covariance_is_a_valid_degenerate_case(base_params):
    cov = np.zeros((len(base_params.eq_geo), len(base_params.eq_geo)))
    sc = esg.simulate(dc.replace(base_params, eq_mu_cov=cov), n=4, seed=4)
    assert sc.eq_drift_err is not None
    np.testing.assert_array_equal(sc.eq_drift_err, np.zeros_like(sc.eq_drift_err))


def test_covariance_preserved_across_options(base_params):
    """Covariance of shocks must match p.cov for all rate tail variants."""
    variants = [
        dc.replace(base_params, rate_dof="gaussian"),
        dc.replace(base_params, rate_dof=14.0),
        dc.replace(base_params, rate_dof="gaussian", rate_shared=0.25),
        dc.replace(base_params, rate_dof=8.0, rate_shared=0.10, infl_dof="gaussian"),
    ]
    target_cov = base_params.cov

    # Generate 50,000 draws to verify theoretical covariance preservation
    for p in variants:
        sc = esg.simulate(p, n=50000, seed=123)
        # Extract 1-step shocks directly:
        # Equities
        eq_shocks = sc.eq_log[:, 0, :] - np.log1p(p.eq_geo) / 12.0
        eq_shocks /= p.eq_vol_scale
        # Rates
        rate_shocks = sc.beta[:, 1, :] - (p.beta_mu + p.phi * (sc.beta[:, 0, :] - p.beta_mu))
        # Infl
        infl_shocks = sc.infl[:, 1] - (p.infl_mu + p.infl_phi * (sc.infl[:, 0] - p.infl_mu))
        # FX
        fx_shocks = sc.fx_log[:, 1] - p.fx_drift / 12.0

        all_shocks = np.column_stack([eq_shocks, rate_shocks, infl_shocks, fx_shocks])
        emp_cov = np.cov(all_shocks, rowvar=False)

        # Max error between empirical and theoretical covariance should be small
        max_err = np.max(np.abs(emp_cov - target_cov))
        assert max_err < 0.003, f"Covariance mismatch for variant {p.rate_dof}: max_err={max_err}"


def test_rate_kurtosis_separation(base_params):
    """Rate tails should be thinner under rate_dof='gaussian' while equity tails remain heavy."""
    # Today's model (t_dof=5 for all)
    sc_today = esg.simulate(base_params, n=10000, seed=11)
    eq_kurt_today = stats.kurtosis(sc_today.eq_log[:, 0, 0])
    r0_today = sc_today.zero_cc(0, 5.0)[:, 0]
    r1_today = sc_today.zero_cc(1, 5.0)[:, 0]
    rate_kurt_today = stats.kurtosis(r1_today - r0_today)

    # Option A: Gaussian rates
    p_gauss = dc.replace(base_params, rate_dof="gaussian")
    sc_gauss = esg.simulate(p_gauss, n=10000, seed=11)
    eq_kurt_gauss = stats.kurtosis(sc_gauss.eq_log[:, 0, 0])
    r0_gauss = sc_gauss.zero_cc(0, 5.0)[:, 0]
    r1_gauss = sc_gauss.zero_cc(1, 5.0)[:, 0]
    rate_kurt_gauss = stats.kurtosis(r1_gauss - r0_gauss)

    # Equity kurtosis should remain heavy (> 1.5)
    assert eq_kurt_today > 1.5
    assert eq_kurt_gauss > 1.5
    # Rate kurtosis today is fat (> 2.0), but under Gaussian rates it collapses to near zero (< 0.25)
    assert rate_kurt_today > 2.0
    assert rate_kurt_gauss < 0.25


def test_independent_t_rate_dof(base_params):
    """Independent Student-t rate shocks with df=14 produce moderate rate kurtosis."""
    p_t14 = dc.replace(base_params, rate_dof=14.0)
    sc_t14 = esg.simulate(p_t14, n=10000, seed=11)
    r0 = sc_t14.zero_cc(0, 5.0)[:, 0]
    r1 = sc_t14.zero_cc(1, 5.0)[:, 0]
    rate_kurt = stats.kurtosis(r1 - r0)

    # Kurtosis of t(14) should be around 6 / (14 - 4) = 0.60
    assert 0.3 < rate_kurt < 1.0


def test_crash_correlation_positive(base_params):
    """Correlation between equities and 5y rate changes in crash months should remain positive."""
    for r_dof in [None, "gaussian", 14.0]:
        p = dc.replace(base_params, rate_dof=r_dof)
        sc = esg.simulate(p, n=10000, seed=11)
        eq = sc.eq_log[:, 0, 0]
        dr = sc.zero_cc(1, 5.0)[:, 0] - sc.zero_cc(0, 5.0)[:, 0]
        full_corr, crash_corr = calibrate.crash_correlation(eq, dr, q=0.05)

        assert not np.isnan(full_corr)
        assert not np.isnan(crash_corr)
        assert full_corr > 0.0
        assert crash_corr > -0.05, f"Crash correlation was strongly negative ({crash_corr}) for rate_dof={r_dof}"


def test_calibrate_block_tails():
    """Verify that calibrate_block_tails returns expected structure and metrics."""
    res = calibrate.calibrate_block_tails()
    assert "d_level" in res
    assert "d_slope" in res
    assert "d_curv" in res
    assert "d_rate5y" in res
    assert "d_infl" in res
    assert "fx_TWD" in res
    assert "rates_3d_joint" in res
    assert "crash_correlation" in res

    # Check 5y rate change excess kurtosis is near 0.6
    assert 0.4 < res["d_rate5y"]["excess_kurtosis"] < 0.8
    # Check df_mom is near 14
    assert 10.0 < res["d_rate5y"]["df_mom"] < 20.0


@pytest.mark.parametrize("field", ["t_dof", "rate_dof", "infl_dof", "fx_dof"])
@pytest.mark.parametrize("value", [0.0, 2.0, -1.0, np.nan, -np.inf])
def test_invalid_tail_degrees_of_freedom_are_rejected(base_params, field, value):
    p = dc.replace(base_params, months=1, **{field: value})
    with pytest.raises(ValueError, match=field):
        esg.simulate(p, n=2, seed=1)


@pytest.mark.parametrize("field", ["rate_dof", "infl_dof", "fx_dof"])
def test_unknown_tail_names_are_rejected(base_params, field):
    p = dc.replace(base_params, months=1, **{field: "student"})
    with pytest.raises(ValueError, match=field):
        esg.simulate(p, n=2, seed=1)


@pytest.mark.parametrize("value", [-0.01, 1.01, np.nan, np.inf])
def test_rate_shared_must_be_a_finite_fraction(base_params, value):
    p = dc.replace(base_params, months=1, rate_shared=value)
    with pytest.raises(ValueError, match="rate_shared"):
        esg.simulate(p, n=2, seed=1)


def test_dof_string_inf_error_message(base_params):
    """Regression: _dof message says exactly what is accepted (float('inf'), 'gaussian', or None)."""
    p = dc.replace(base_params, months=1, rate_dof="inf")
    with pytest.raises(ValueError, match=r"rate_dof must be a number > 2, float\('inf'\), 'gaussian', or None, got 'inf'"):
        esg.simulate(p, n=2, seed=1)


def test_dof_string_inf_contrast_gaussian_accepted(base_params):
    """'gaussian' string is accepted for allow_gaussian fields."""
    p = dc.replace(base_params, months=1, rate_dof="gaussian")
    # Should not raise
    esg.simulate(p, n=2, seed=1)
