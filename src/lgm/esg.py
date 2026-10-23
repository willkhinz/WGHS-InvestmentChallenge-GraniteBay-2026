"""Economic scenario generator (monthly).

State per scenario and month:
- Nelson-Siegel factors (level, slope, curvature) of the continuously compounded zero curve,
  AR(1) toward long-run means. A fixed residual keeps today's curve exact at month 0.
- Equity log returns for US, developed ex-US and emerging markets.
- US CPI inflation (year over year), AR(1) toward its long-run mean.
- log USD/TWD (positive = the dollar buys more Taiwan dollars) and a Taiwan building-cost index.
Shocks are jointly Student-t (one common mixing variable per month), so bad months hit
stocks, rates and FX together, as in 2008 and 2020.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import nelson_siegel as ns
from .asof import month_of
from .curve import ZeroCurve

TAU_GRID = np.array([0.0833, 0.25, 0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 25, 30], dtype=float)


@dataclass
class ESGParams:
    months: int
    beta0: np.ndarray                # starting NS factors
    resid: np.ndarray                # today's curve minus NS fit on TAU_GRID (cc, decimals)
    beta_mu: np.ndarray              # long-run NS factors
    phi: np.ndarray                  # monthly AR(1) per factor
    cov: np.ndarray                  # (K+5, K+5) monthly joint shock covariance: K equities, 3 rate
                                     # factors, inflation, USD/TWD (in that order)
    eq_geo: np.ndarray               # (K,) annual median (geometric) equity returns, gross of fees
    eq_vol_scale: float = 1.0
    infl0: float = 0.0374
    infl_mu: float = 0.03
    infl_phi: float = 0.966
    fx_drift: float = 0.0            # annual log drift of USD/TWD
    tw_cost_growth: float = 0.04     # Taiwan building-cost inflation, annual
    tw_cost_vol: float = 0.015
    t_dof: float | None = 5.0        # Student-t degrees of freedom (>2); None or inf = Gaussian
    rate_floor: float = -0.005
    eq_mu_cov: np.ndarray | None = None  # (K, K) annual covariance of expected equity returns
    eq_garch: tuple[float, float] | dict | None = None  # optional (alpha, beta) or dict for GARCH(1,1) vol clustering
    tw_cost_phi: float | tuple[float, ...] | None = None  # monthly AR(1) scalar or AR(2) tuple; None = legacy i.i.d.
    tw_cost_infl0: float | tuple[float, ...] | None = None  # initial monthly log changes (Aug, Sep 2026); None = stationary
    tw_cost_corr: float | None = None  # correlation of tw_cost innovations with US CPI shock
    tw_cost_fx_corr: float | None = None  # correlation of tw_cost innovations with the USD/TWD shock
    tw_cost_sig_eps: float | None = None  # monthly innovation standard deviation; None = derived from tw_cost_vol
    tw_cost_state0: float | tuple[float, ...] | None = None  # alias for tw_cost_infl0
    rate_dof: float | None | str = None  # Student-t dof for rate block; None = legacy (shares t_dof); 'gaussian' or inf = Gaussian
    rate_shared: float = 0.0             # share of equity mixing variance used by rates, in [0, 1]
    infl_dof: float | None | str = None  # Student-t dof for inflation; None = legacy (shares t_dof)
    fx_dof: float | None | str = None    # Student-t dof for USD/TWD; None = legacy (shares t_dof)


@dataclass
class Scenarios:
    beta: np.ndarray       # (N, M+1, 3)
    eq_log: np.ndarray     # (N, M, K)
    infl: np.ndarray       # (N, M+1)
    fx_log: np.ndarray     # (N, M+1), 0 at start
    tw_cost_log: np.ndarray  # (N, M+1), 0 at start
    resid: np.ndarray
    rate_floor: float = -0.005
    m0: int = 0            # absolute month of index 0 (non-zero for nested simulations)
    eq_drift_err: np.ndarray | None = None
    garch_h: np.ndarray | None = None
    tw_cost_infl: np.ndarray | None = None
    fx_log_2027: np.ndarray | None = None  # Jan 2027 baseline retained by nested simulations
    tw_cost_log_2027: np.ndarray | None = None

    @property
    def n(self) -> int:
        return self.beta.shape[0]

    def zero_cc(self, m: int, tau) -> np.ndarray:
        """(N, k) continuously compounded zero rates at month m."""
        tau = np.atleast_1d(np.asarray(tau, dtype=float))
        z = ns.zero(self.beta[:, m - self.m0, :], tau) + np.interp(tau, TAU_GRID, self.resid)[None, :]
        return np.maximum(z, self.rate_floor)

    def df(self, m: int, tau) -> np.ndarray:
        tau = np.atleast_1d(np.asarray(tau, dtype=float))
        return np.exp(-self.zero_cc(m, tau) * np.maximum(tau, 0.0)[None, :])

    def curve(self, i: int, m: int, date) -> ZeroCurve:
        """Scenario i's curve at month m as a ZeroCurve object (for LP pricing)."""
        knots = np.concatenate([[0.0], TAU_GRID])
        z = self.zero_cc(m, TAU_GRID)[i]
        return ZeroCurve(date, knots, np.concatenate([[0.0], -z * TAU_GRID]))


def initial_state(curve: ZeroCurve) -> tuple[np.ndarray, np.ndarray]:
    z = np.log1p(curve.zero(TAU_GRID))
    beta0 = ns.fit(TAU_GRID, z)
    return beta0, z - ns.zero(beta0, TAU_GRID)


def _mixing(dof: float, rng: np.random.Generator, shape: tuple) -> np.ndarray:
    """Student-t mixing variable with unit second moment: sqrt((dof - 2) / chi2(dof))."""
    if np.isposinf(dof):
        return np.ones(shape)
    if not np.isfinite(dof) or dof <= 2:
        raise ValueError(f"Student-t degrees of freedom must be > 2, got {dof}")
    return np.sqrt((dof - 2) / rng.chisquare(dof, size=shape))


def _dof(value, name: str, *, allow_gaussian: bool = False) -> float | None:
    """Normalize a tail option; None inherits the legacy block behavior."""
    expected = (
        "a number > 2, float('inf'), 'gaussian', or None"
        if allow_gaussian else "a number > 2, float('inf'), or None"
    )
    if value is None:
        return None
    if isinstance(value, str):
        if allow_gaussian and value.strip().lower() == "gaussian":
            return np.inf
        raise ValueError(f"{name} must be {expected}, got {value!r}")
    try:
        dof = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be {expected}, got {value!r}") from exc
    if np.isposinf(dof):
        return np.inf
    if not np.isfinite(dof) or dof <= 2:
        raise ValueError(f"{name} must be {expected}, got {value!r}")
    return dof


def _garch_parameters(value, n_equities: int):
    """Normalize and validate the optional stationary GARCH(1,1) configuration."""
    if value is None:
        return None
    try:
        if isinstance(value, (tuple, list)):
            if len(value) not in (2, 3):
                raise ValueError("expected (alpha, beta[, h0])")
            alpha, beta = float(value[0]), float(value[1])
            h0 = float(value[2]) if len(value) == 3 else 1.0
            raw_idx = 0
        elif isinstance(value, dict):
            alpha, beta = float(value["alpha"]), float(value["beta"])
            h0 = float(value.get("h0", 1.0))
            raw_idx = value.get("factor_idx", 0)
        else:
            alpha, beta = float(value.alpha), float(value.beta)
            h0 = float(getattr(value, "h0", 1.0))
            raw_idx = getattr(value, "factor_idx", 0)
        if isinstance(raw_idx, (bool, np.bool_)) or not isinstance(raw_idx, (int, np.integer)):
            raise ValueError("factor_idx must be an integer")
        factor_idx = int(raw_idx)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"eq_garch configuration is invalid: {exc}") from exc
    if factor_idx != raw_idx or not 0 <= factor_idx < n_equities:
        raise ValueError(f"eq_garch factor_idx must be an integer in [0, {n_equities}), got {raw_idx!r}")
    if not np.isfinite([alpha, beta, h0]).all() or alpha < 0 or beta < 0 or alpha + beta >= 1 or h0 <= 0:
        raise ValueError("eq_garch requires finite alpha,beta >= 0, alpha + beta < 1, and h0 > 0")
    return alpha, beta, h0, factor_idx


def _block_mixing(dof, w_eq, rng: np.random.Generator, shape: tuple):
    """Use Gaussian at inf, a block-specific t draw for finite dof, or legacy equity mixing at None."""
    if isinstance(dof, (int, float, np.number)) and np.isposinf(dof):
        return 1.0
    if isinstance(dof, (int, float, np.number)):
        return _mixing(float(dof), rng, shape)
    return w_eq if w_eq is not None else 1.0


def _correlation(value: float | None, name: str) -> float:
    """Return a finite correlation coefficient or reject an invalid configuration."""
    if value is None:
        return 0.0
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a finite correlation in [-1, 1], got {value!r}")
    try:
        rho = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite correlation in [-1, 1], got {value!r}") from exc
    if not np.isfinite(rho) or not -1.0 <= rho <= 1.0:
        raise ValueError(f"{name} must be a finite correlation in [-1, 1], got {value}")
    return rho


def _tw_cost_ar_coefficients(value):
    """Normalize scalar/AR(1)/AR(2) Taiwan cost persistence and require stationarity."""
    if value is None:
        return None
    try:
        raw = (value,) if np.isscalar(value) else tuple(value)
        if not 1 <= len(raw) <= 2 or any(isinstance(x, (bool, np.bool_)) for x in raw):
            raise ValueError("expected one or two numeric AR coefficients")
        phi1 = float(raw[0])
        phi2 = float(raw[1]) if len(raw) == 2 else 0.0
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"tw_cost_phi must contain one or two numeric coefficients: {exc}") from exc
    if (not np.isfinite([phi1, phi2]).all() or abs(phi2) >= 1.0
            or phi1 + phi2 >= 1.0 or phi2 - phi1 >= 1.0):
        raise ValueError(f"tw_cost_phi must define a stationary AR(1) or AR(2), got {value!r}")
    return phi1, phi2


def _state_values(value, name: str, label: str | None = None) -> np.ndarray:
    """Convert continuation state to finite numeric values, rejecting boolean pseudo-numbers."""
    loc = label if label is not None else f"start[{name!r}]"
    try:
        raw = np.asarray(value, dtype=object)
        if any(isinstance(x, (bool, np.bool_)) for x in raw.flat):
            raise ValueError("boolean values are not valid state data")
        state = np.asarray(raw, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{loc} must contain finite numeric values") from exc
    if not np.isfinite(state).all():
        raise ValueError(f"{loc} must contain finite numeric values")
    return state


def _path_state(value, n: int, name: str, label: str | None = None) -> np.ndarray:
    """Normalize a shared scalar or one finite value per scenario."""
    state = _state_values(value, name, label)
    if state.ndim == 0:
        return np.full(n, float(state))
    loc = label if label is not None else f"start[{name!r}]"
    if state.shape != (n,):
        raise ValueError(f"{loc} must be a scalar or have shape ({n},), got {state.shape}")
    return state


def _tw_cost_state(value, n: int, name: str, label: str | None = None):
    """Normalize one lag state or the (two-lag) AR(2) state."""
    if value is None:
        return None
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return tuple(_path_state(item, n, name, label) for item in value)
    return _path_state(value, n, name, label)


def _parameter_values(value, shape: tuple, name: str) -> np.ndarray:
    """Normalize finite numeric model parameters with an exact shape."""
    try:
        raw = np.asarray(value, dtype=object)
        if any(isinstance(x, (bool, np.bool_)) for x in raw.flat):
            raise ValueError("boolean values are not valid model parameters")
        values = np.asarray(raw, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must contain finite numeric values with shape {shape}") from exc
    if values.shape != shape or not np.isfinite(values).all():
        raise ValueError(f"{name} must contain finite numeric values with shape {shape}")
    return values


def _prepare_start(start, n: int, n_equities: int):
    """Validate and normalize the nested-simulation state contract."""
    if start is None:
        return None
    if not isinstance(start, dict):
        raise ValueError("start must be a mapping of continuation state")
    required = {"beta", "infl", "fx_log", "tw_cost_log"}
    missing = required.difference(start)
    if missing:
        raise ValueError(f"start is missing required state keys: {', '.join(sorted(missing))}")
    out = dict(start)
    beta = _state_values(out["beta"], "beta")
    if beta.shape not in ((3,), (n, 3)):
        raise ValueError(f"start['beta'] must have shape (3,) or ({n}, 3), got {beta.shape}")
    out["beta"] = beta
    out["infl"] = _path_state(out["infl"], n, "infl")
    out["fx_log"] = _path_state(out["fx_log"], n, "fx_log")
    out["tw_cost_log"] = _path_state(out["tw_cost_log"], n, "tw_cost_log")

    if "beta_shift" in out:
        shift = _state_values(out["beta_shift"], "beta_shift")
        if shift.ndim != 0 and shift.shape not in ((3,), (n, 3)):
            raise ValueError(f"start['beta_shift'] must be scalar, (3,), or ({n}, 3), got {shift.shape}")
        out["beta_shift"] = shift
    if "eq_drift_err" in out:
        err = _state_values(out["eq_drift_err"], "eq_drift_err")
        if err.shape not in ((n_equities,), (n, n_equities)):
            raise ValueError(
                f"start['eq_drift_err'] must have shape ({n_equities},) or ({n}, {n_equities}), got {err.shape}"
            )
        out["eq_drift_err"] = err
    for key in ("tw_cost_state", "tw_cost_infl"):
        if key not in out:
            continue
        out[key] = _tw_cost_state(out[key], n, key)
    for key in ("fx_log_2027", "tw_cost_log_2027"):
        if key in out:
            out[key] = _path_state(out[key], n, key)
    return out


def simulate(p: ESGParams, n: int, seed: int = 0, antithetic: bool = True,
             start: dict | None = None, m0: int = 0) -> Scenarios:
    """Simulate n scenarios for p.months months.

    `start` supplies continuation state. Beta accepts a shared vector or one vector per scenario;
    inflation, FX, and cost-index levels accept shared scalars or one value per scenario. Optional
    drift, GARCH, and Taiwan AR states accept shared values or scenario-wise values as appropriate.
    """
    if isinstance(n, (bool, np.bool_)) or not isinstance(n, (int, np.integer)) or n < 1:
        raise ValueError(f"n must be a positive integer, got {n!r}")
    if (isinstance(p.months, (bool, np.bool_)) or not isinstance(p.months, (int, np.integer))
            or p.months < 1):
        raise ValueError(f"months must be a positive integer, got {p.months!r}")
    if (isinstance(m0, (bool, np.bool_)) or not isinstance(m0, (int, np.integer)) or m0 < 0):
        raise ValueError(f"m0 must be a nonnegative integer, got {m0!r}")
    beta0 = _parameter_values(p.beta0, (3,), "beta0")
    beta_mu = _parameter_values(p.beta_mu, (3,), "beta_mu")
    resid = _parameter_values(p.resid, TAU_GRID.shape, "resid")
    infl0 = float(_parameter_values(p.infl0, (), "infl0"))
    infl_mu = float(_parameter_values(p.infl_mu, (), "infl_mu"))
    fx_drift = float(_parameter_values(p.fx_drift, (), "fx_drift"))
    rate_floor = float(_parameter_values(p.rate_floor, (), "rate_floor"))
    t_dof = _dof(p.t_dof, "t_dof")
    rate_dof = _dof(p.rate_dof, "rate_dof", allow_gaussian=True)
    infl_dof = _dof(p.infl_dof, "infl_dof", allow_gaussian=True)
    fx_dof = _dof(p.fx_dof, "fx_dof", allow_gaussian=True)
    try:
        raw_eq_geo = np.asarray(p.eq_geo, dtype=object)
        if any(isinstance(x, (bool, np.bool_)) for x in raw_eq_geo.flat):
            raise ValueError("boolean returns")
        eq_geo = np.asarray(raw_eq_geo, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("eq_geo must be a finite one-dimensional vector of annual returns above -100%") from exc
    if (eq_geo.ndim != 1 or eq_geo.size < 1 or not np.isfinite(eq_geo).all()
            or np.any(eq_geo <= -1.0)):
        raise ValueError("eq_geo must be a finite one-dimensional vector of annual returns above -100%")
    K = eq_geo.size
    try:
        raw_shock_cov = np.asarray(p.cov, dtype=object)
        if any(isinstance(x, (bool, np.bool_)) for x in raw_shock_cov.flat):
            raise ValueError("boolean matrix")
        shock_cov = np.asarray(raw_shock_cov, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("cov must be a finite symmetric positive-definite matrix of shape (K+5, K+5)") from exc
    if shock_cov.shape != (K + 5, K + 5) or not np.isfinite(shock_cov).all():
        raise ValueError("cov must be a finite symmetric positive-definite matrix of shape (K+5, K+5)")
    if not np.allclose(shock_cov, shock_cov.T, rtol=1e-10, atol=1e-14):
        raise ValueError("cov must be symmetric")
    try:
        chol = np.linalg.cholesky(shock_cov)
    except np.linalg.LinAlgError as exc:
        raise ValueError("cov must be positive definite") from exc

    eq_mu_root = None
    if p.eq_mu_cov is not None:
        try:
            raw_eq_mu_cov = np.asarray(p.eq_mu_cov, dtype=object)
            if any(isinstance(x, (bool, np.bool_)) for x in raw_eq_mu_cov.flat):
                raise ValueError("boolean matrix")
            eq_mu_cov = np.asarray(raw_eq_mu_cov, dtype=float)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("eq_mu_cov must be a finite symmetric positive-semidefinite K-by-K matrix") from exc
        if eq_mu_cov.shape != (K, K) or not np.isfinite(eq_mu_cov).all():
            raise ValueError("eq_mu_cov must be a finite symmetric positive-semidefinite K-by-K matrix")
        if not np.allclose(eq_mu_cov, eq_mu_cov.T, rtol=1e-10, atol=1e-14):
            raise ValueError("eq_mu_cov must be symmetric")
        eq_mu_cov = (eq_mu_cov + eq_mu_cov.T) / 2.0
        mu_vals, mu_vecs = np.linalg.eigh(eq_mu_cov)
        psd_tol = 1e-12 * max(1.0, float(np.max(np.abs(mu_vals))))
        if mu_vals.min() < -psd_tol:
            raise ValueError("eq_mu_cov must be positive semidefinite")
        eq_mu_root = mu_vecs @ np.diag(np.sqrt(np.maximum(mu_vals, 0.0)))

    try:
        raw_rate_phi = np.asarray(p.phi, dtype=object)
        if any(isinstance(x, (bool, np.bool_)) for x in raw_rate_phi.flat):
            raise ValueError("boolean coefficients are not numeric persistence inputs")
        rate_phi = np.asarray(raw_rate_phi, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("phi must be a finite stationary length-3 rate-factor vector") from exc
    if rate_phi.shape != (3,) or not np.isfinite(rate_phi).all() or np.any(np.abs(rate_phi) >= 1.0):
        raise ValueError("phi must be a finite stationary length-3 rate-factor vector")
    try:
        if isinstance(p.infl_phi, (bool, np.bool_)):
            raise ValueError("boolean coefficient")
        infl_phi = float(p.infl_phi)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("infl_phi must be finite and stationary (absolute value < 1)") from exc
    if not np.isfinite(infl_phi) or abs(infl_phi) >= 1.0:
        raise ValueError("infl_phi must be finite and stationary (absolute value < 1)")
    if isinstance(p.rate_shared, (bool, np.bool_)):
        raise ValueError(f"rate_shared must be a finite fraction in [0, 1], got {p.rate_shared!r}")
    try:
        rate_shared = float(p.rate_shared)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"rate_shared must be a finite fraction in [0, 1], got {p.rate_shared!r}") from exc
    if not np.isfinite(rate_shared) or not 0.0 <= rate_shared <= 1.0:
        raise ValueError(f"rate_shared must be a finite fraction in [0, 1], got {p.rate_shared!r}")
    garch = _garch_parameters(p.eq_garch, len(p.eq_geo))
    if isinstance(p.eq_vol_scale, (bool, np.bool_)):
        raise ValueError(f"eq_vol_scale must be finite and nonnegative, got {p.eq_vol_scale!r}")
    try:
        eq_vol_scale = float(p.eq_vol_scale)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"eq_vol_scale must be finite and nonnegative, got {p.eq_vol_scale!r}") from exc
    if not np.isfinite(eq_vol_scale) or eq_vol_scale < 0:
        raise ValueError(f"eq_vol_scale must be finite and nonnegative, got {p.eq_vol_scale!r}")
    if garch is not None and eq_vol_scale == 0:
        raise ValueError(f"eq_vol_scale must be positive when eq_garch is enabled, got {p.eq_vol_scale!r}")
    tw_cost_ar = _tw_cost_ar_coefficients(p.tw_cost_phi)
    if isinstance(p.tw_cost_growth, (bool, np.bool_)):
        raise ValueError("tw_cost_growth must be finite and greater than -1")
    try:
        tw_cost_growth = float(p.tw_cost_growth)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("tw_cost_growth must be finite and greater than -1") from exc
    if not np.isfinite(tw_cost_growth) or tw_cost_growth <= -1.0:
        raise ValueError("tw_cost_growth must be finite and greater than -1")
    tw_cost_vol = None
    if tw_cost_ar is None or p.tw_cost_sig_eps is None:
        if isinstance(p.tw_cost_vol, (bool, np.bool_)):
            raise ValueError("tw_cost_vol must be finite and nonnegative")
        try:
            tw_cost_vol = float(p.tw_cost_vol)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("tw_cost_vol must be finite and nonnegative") from exc
        if not np.isfinite(tw_cost_vol) or tw_cost_vol < 0.0:
            raise ValueError("tw_cost_vol must be finite and nonnegative")
    tw_cost_sig_eps = None
    if tw_cost_ar is not None and p.tw_cost_sig_eps is not None:
        if isinstance(p.tw_cost_sig_eps, (bool, np.bool_)):
            raise ValueError("tw_cost_sig_eps must be finite and nonnegative")
        try:
            tw_cost_sig_eps = float(p.tw_cost_sig_eps)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("tw_cost_sig_eps must be finite and nonnegative") from exc
        if not np.isfinite(tw_cost_sig_eps) or tw_cost_sig_eps < 0.0:
            raise ValueError("tw_cost_sig_eps must be finite and nonnegative")
    start = _prepare_start(start, n, K)
    tw_cost_initial_state = None
    if tw_cost_ar is not None and start is None:
        raw_cost_state = p.tw_cost_state0 if p.tw_cost_state0 is not None else p.tw_cost_infl0
        name = "tw_cost_state0" if p.tw_cost_state0 is not None else "tw_cost_infl0"
        tw_cost_initial_state = _tw_cost_state(raw_cost_state, n, name, label=name)
    if garch is not None and start is not None and "garch_h" in start:
        try:
            start_h = _state_values(start["garch_h"], "garch_h")
        except ValueError as exc:
            raise ValueError("starting garch_h must contain finite nonnegative variances") from exc
        if not np.isfinite(start_h).all() or np.any(start_h < 0):
            raise ValueError("starting garch_h must contain finite nonnegative variances")
        if start_h.ndim > 1 or (start_h.ndim == 1 and start_h.shape != (n,)):
            raise ValueError(f"starting garch_h must be a scalar or have shape ({n},), got {start_h.shape}")

    rng = np.random.default_rng(seed)
    M, k = p.months, shock_cov.shape[0]
    half = (n + 1) // 2 if antithetic else n
    z = rng.standard_normal((half, M, k))
    if rate_dof is None and rate_shared == 0.0 and infl_dof is None and fx_dof is None:
        if t_dof:
            w = _mixing(t_dof, rng, (half, M, 1))
            z = z * w
    else:
        # Each block's independent normals are scaled by its own mixing variable before the Cholesky
        # factor, so the covariance is unchanged (E[w^2] = 1, blocks independent) and the part of a block
        # that is correlated with equities keeps the equities' tails. Draw order: equities, rates,
        # inflation, FX (only blocks with their own numeric dof draw).
        K = len(p.eq_geo)
        w_eq = _mixing(t_dof, rng, (half, M, 1)) if t_dof else None
        if w_eq is not None:
            z[..., :K] *= w_eq
        w_rate = _block_mixing(rate_dof, w_eq, rng, (half, M, 1))
        if rate_shared > 0.0 and w_eq is not None:
            lam = rate_shared
            w_rate = np.sqrt(lam * w_eq ** 2 + (1.0 - lam) * np.asarray(w_rate) ** 2)
        for sl, dof, w in ((slice(K, K + 3), None, w_rate), (slice(K + 3, K + 4), infl_dof, None),
                           (slice(K + 4, K + 5), fx_dof, None)):
            w = w if w is not None else _block_mixing(dof, w_eq, rng, (half, M, 1))
            if not (np.isscalar(w) and w == 1.0):
                z[..., sl] *= w
    if antithetic:
        z = np.concatenate([z, -z], axis=0)[:n]
    shocks = z @ chol.T                                       # (n, M, K+5)
    shocks[..., :K] *= eq_vol_scale

    garch_h = None
    if garch is not None:
        alpha, beta, h0, factor_idx = garch
        omega = 1.0 - alpha - beta
        garch_h = np.ones((n, M))
        if start is not None and "garch_h" in start:
            start_h = np.asarray(start["garch_h"])
            garch_h[:, 0] = start_h
        else:
            garch_h[:, 0] = h0

        var0 = shock_cov[factor_idx, factor_idx] * (eq_vol_scale ** 2)
        for m in range(M):
            shocks[:, m, :K] *= np.sqrt(garch_h[:, m, None])
            if m < M - 1:
                garch_h[:, m + 1] = omega + alpha * (shocks[:, m, factor_idx] ** 2 / var0) + beta * garch_h[:, m]

    eq_mu = np.log1p(eq_geo) / 12.0                            # median growth preserved
    eq_drift_err = None
    if start is not None and "eq_drift_err" in start:
        err = np.asarray(start["eq_drift_err"])
        if err.ndim == 1:
            eq_drift_err = np.tile(err, (n, 1))
        else:
            eq_drift_err = err
    elif eq_mu_root is not None:
        z_mu = rng.standard_normal((half, K))
        err_half = z_mu @ eq_mu_root.T
        if antithetic:
            eq_drift_err = np.concatenate([err_half, -err_half], axis=0)[:n]
        else:
            eq_drift_err = err_half[:n]

    if eq_drift_err is not None:
        eq_log = eq_mu[None, None, :] + (eq_drift_err / 12.0)[:, None, :] + shocks[..., :K]
    else:
        eq_log = eq_mu[None, None, :] + shocks[..., :K]

    beta = np.empty((n, M + 1, 3))
    infl = np.empty((n, M + 1))
    beta[:, 0] = beta0 if start is None else start["beta"]
    infl[:, 0] = infl0 if start is None else start["infl"]
    if start is not None:
        beta_shift = start.get("beta_shift")
        if beta_shift is not None:
            beta[:, 0] = beta[:, 0] + beta_shift
    for m in range(M):
        beta[:, m + 1] = beta_mu + rate_phi * (beta[:, m] - beta_mu) + shocks[:, m, K:K + 3]
        infl[:, m + 1] = infl_mu + infl_phi * (infl[:, m] - infl_mu) + shocks[:, m, K + 3]
    fx0 = 0.0 if start is None else start["fx_log"][:, None]
    fx_log = np.concatenate([np.zeros((n, 1)), np.cumsum(fx_drift / 12 + shocks[..., K + 4], axis=1)], axis=1) + fx0
    if tw_cost_ar is not None:
        phi1, phi2 = tw_cost_ar

        mu = float(np.log1p(tw_cost_growth) / 12.0)

        # Innovation standard deviation:
        if tw_cost_sig_eps is not None:
            sig_eps = tw_cost_sig_eps
        else:
            sig_1m = tw_cost_vol / np.sqrt(12.0)
            if phi2 == 0.0:
                sig_eps = sig_1m * np.sqrt(max(1.0 - phi1**2, 0.0))
            else:
                ratio = (1.0 + phi2) * ((1.0 - phi2)**2 - phi1**2) / max(1.0 - phi2, 1e-12)
                sig_eps = sig_1m * np.sqrt(max(ratio, 0.0))

        # Stationary covariance of (y_prev2, y_prev1)
        if phi2 == 0.0:
            var_y = sig_eps**2 / max(1.0 - phi1**2, 1e-12)
            cov_y = phi1 * var_y
        else:
            denom = (1.0 + phi2) * ((1.0 - phi2)**2 - phi1**2)
            var_y = ((1.0 - phi2) / max(denom, 1e-12)) * (sig_eps**2)
            rho1 = phi1 / max(1.0 - phi2, 1e-12)
            cov_y = rho1 * var_y

        state_in = tw_cost_initial_state
        if start is not None:
            if "tw_cost_state" in start:
                state_in = start["tw_cost_state"]
            elif "tw_cost_infl" in start:
                state_in = start["tw_cost_infl"]

        if state_in is None and sig_eps == 0.0:
            y_prev2 = np.full(n, mu)
            y_prev1 = np.full(n, mu)
        elif state_in is None:
            cov_mat = np.array([[var_y, cov_y], [cov_y, var_y]])
            chol_init = np.linalg.cholesky(cov_mat)
            if antithetic:
                z_init_half = rng.standard_normal((half, 2))
                z_init = np.concatenate([z_init_half, -z_init_half], axis=0)[:n]
            else:
                z_init = rng.standard_normal((n, 2))
            init_shocks = z_init @ chol_init.T
            y_prev2 = mu + init_shocks[:, 0]
            y_prev1 = mu + init_shocks[:, 1]
        elif isinstance(state_in, (tuple, list)) and len(state_in) == 2:
            s0 = np.asarray(state_in[0], dtype=float)
            s1 = np.asarray(state_in[1], dtype=float)
            y_prev2 = s0 if s0.ndim > 0 else np.full(n, float(s0))
            y_prev1 = s1 if s1.ndim > 0 else np.full(n, float(s1))
        else:
            s1 = np.asarray(state_in, dtype=float)
            y_prev1 = s1 if s1.ndim > 0 else np.full(n, float(s1))
            y_prev2 = np.full(n, mu)

        if antithetic:
            z_half = rng.standard_normal((half, M))
            z_tw = np.concatenate([z_half, -z_half], axis=0)[:n]
        else:
            z_tw = rng.standard_normal((n, M))

        rho_cpi = _correlation(p.tw_cost_corr, "tw_cost_corr")
        rho_fx = _correlation(p.tw_cost_fx_corr, "tw_cost_fx_corr")
        if rho_cpi and rho_fx:
            # mixing one after the other would dilute the first correlation; the two need a joint factor
            raise ValueError("tw_cost_corr and tw_cost_fx_corr cannot both be set")
        if rho_cpi:
            cpi_std = np.sqrt(shock_cov[K + 3, K + 3])
            z_cpi = shocks[..., K + 3] / (cpi_std if cpi_std > 0 else 1.0)
            z_tw = rho_cpi * z_cpi + np.sqrt(1.0 - rho_cpi**2) * z_tw

        if rho_fx:
            z_fx = shocks[..., K + 4] / np.sqrt(shock_cov[K + 4, K + 4])
            z_tw = rho_fx * z_fx + np.sqrt(1.0 - rho_fx ** 2) * z_tw

        y = np.empty((n, M))
        for m in range(M):
            p1 = y_prev1 if m == 0 else y[:, m - 1]
            p2 = y_prev2 if m == 0 else (y_prev1 if m == 1 else y[:, m - 2])
            y[:, m] = mu + phi1 * (p1 - mu) + phi2 * (p2 - mu) + sig_eps * z_tw[:, m]

        tw0 = 0.0 if start is None else start["tw_cost_log"][:, None]
        tw_cost_log = np.concatenate([np.zeros((n, 1)), np.cumsum(y, axis=1)], axis=1) + tw0
        tw_cost_infl = np.empty((n, M + 1))
        tw_cost_infl[:, 0] = y_prev1
        tw_cost_infl[:, 1:] = y
    else:
        tw = np.log1p(tw_cost_growth) / 12 + tw_cost_vol / np.sqrt(12) * rng.standard_normal((n, M))
        tw0 = 0.0 if start is None else start["tw_cost_log"][:, None]
        tw_cost_log = np.concatenate([np.zeros((n, 1)), np.cumsum(tw, axis=1)], axis=1) + tw0
        tw_cost_infl = None
    m27 = month_of(2027) - m0
    if 0 <= m27 <= M:
        fx_log_2027 = fx_log[:, m27].copy()
        tw_cost_log_2027 = tw_cost_log[:, m27].copy()
    elif start is not None:
        fx_log_2027 = start.get("fx_log_2027")
        tw_cost_log_2027 = start.get("tw_cost_log_2027")
    else:
        fx_log_2027 = tw_cost_log_2027 = None
    return Scenarios(beta, eq_log, infl, fx_log, tw_cost_log, resid, rate_floor, m0, eq_drift_err,
                     garch_h, tw_cost_infl, fx_log_2027, tw_cost_log_2027)
