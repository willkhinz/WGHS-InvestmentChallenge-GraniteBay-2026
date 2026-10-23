"""Monthly simulation of Laura's portfolio under a strategy, across many scenarios.

Timeline (month 0 = first of the month after the curve date, `asof.START`; months shown for the
Oct 20, 2026 curve):
  m=2  Jan 2027  +$300,000; lock per rule; invest the rest
  m=14 Jan 2028  +$150,000; complete any lock shortfall first; invest
  m=26, 38, 62   January rebalancing checks
  m=50 Jan 2031  finish the ladder if the rule says so; move the floor into IBTM; quote range
  m=74 Jan 2033  buy any unlocked part of the reserve; what is left is the facility fund
Everything is vectorised over scenarios.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from numbers import Integral, Real

import numpy as np

from .asof import month_of
from .esg import Scenarios, TAU_GRID
from .strategies import Strategy

M_2027, M_2028, M_2031, M_2033 = (month_of(y) for y in (2027, 2028, 2031, 2033))
REBAL_MONTHS = tuple(month_of(y) for y in (2029, 2030, 2032))
N_PAY, PMT = 10, 50_000.0
IBTM_MATURITY_M = month_of(2032, 12) + 0.5      # Dec 15, 2032
ER = {"eq": np.array([0.0003, 0.0003, 0.0006]), "VGIT": 0.0003, "IBTM": 0.0007}
VGIT_TAU, VGIT_DUR, VGIT_CONV = 5.5, 5.1, 31.0
COMMISSION_ETF, COMMISSION_BOND = 25.0, 10.0


@dataclass
class EngineConfig:
    kappa0: float = 0.018         # real-instrument ladder cost over zero-coupon value, Jan 2027 ladder
    deposits: tuple = ((M_2027, 300_000.0), (M_2028, 150_000.0))
    commissions: bool = True
    eq_er: tuple = (0.0003, 0.0003, 0.0006)   # expense ratio per equity asset, same order as the ESG
    extra_tickets: int = 0        # more trades per invest event, e.g. 34 when a 35-stock basket is one asset
    extra_ticket_min: float = 10_000.0   # below this, a small top-up stays in the ETFs (no basket trades)
    annual_cost: float = 0.0      # recurring commissions per year (e.g. basket reconstitution)
    fund_groups: tuple | None = None  # equity slots traded as one fund, e.g. VTI = (0, 1, 2); None = each slot
    compound_costs: bool = True   # commissions owed grow at the invested assets' return, as if paid when incurred
    sell_at_settlement: bool = True  # Jan 2033: one sale ticket per fund still held (the contribution is paid in cash)
    kappa_rate_slope: float = 0.0  # premium change per unit of the scenario's 5-year rate above `kappa_rate_ref`
    kappa_rate_ref: float | None = None  # 5-year zero rate (cc) the premium kappa0 belongs to; required with a slope


def pay_tau(m: float) -> np.ndarray:
    """Years from month m to each payment (Jan 1, 2033 + k)."""
    return (M_2033 + 12 * np.arange(N_PAY) - m) / 12.0


def kappa(m: float, cfg: EngineConfig, sc: Scenarios | None = None) -> float | np.ndarray:
    """Premium scales with the ladder's average remaining time (reinvestment and fee drag). With
    `kappa_rate_slope` and scenarios, it also moves with the scenario's 5-year rate, (N, 1): cash awaiting
    a payment is assumed to earn a fixed 3%, so the LP's premium rises with market rates
    (`scripts/ladder_premium.py`)."""
    k0 = _real_config("kappa0", cfg.kappa0, lower=-1.0, strict_lower=True)
    k = k0 * pay_tau(m).clip(0).mean() / pay_tau(M_2027).mean()
    slope = _real_config("kappa_rate_slope", cfg.kappa_rate_slope)
    if slope == 0.0 or sc is None:
        result = k
    else:
        if cfg.kappa_rate_ref is None:
            raise ValueError("kappa_rate_slope needs kappa_rate_ref (today's 5-year zero rate)")
        ref = _real_config("kappa_rate_ref", cfg.kappa_rate_ref)
        result = k + slope * (sc.zero_cc(m, 5.0) - ref)
    if not np.isfinite(result).all() or np.any(np.asarray(result) <= -1.0):
        raise ValueError("scenario ladder premium must be finite and greater than -100%")
    return result


@dataclass
class State:
    eq: np.ndarray            # (N, 3) dollars
    vgit: np.ndarray          # (N,) dollars
    ibtm_face: np.ndarray     # (N,) growth-sleeve IBTM, dollars at maturity
    floor_face: np.ndarray    # (N,) floor IBTM, dollars at maturity
    cash: np.ndarray          # (N,)
    locked: np.ndarray        # (N, K) fraction of each payment matched
    costs: np.ndarray         # (N,) commissions paid
    ratchet_ref: np.ndarray | None = None
    ratchet_y: np.ndarray | None = None


def target_equity_share(st: Strategy, m: int) -> float:
    """Target equity share at month m, interpolating linearly from Jan 2028 to Jan 2032 if glide path is set."""
    if st.equity_share_end is None or m <= M_2028:
        return st.equity_share
    m_end = month_of(2032)
    frac = min(max((m - M_2028) / (m_end - M_2028), 0.0), 1.0)
    return st.equity_share + frac * (st.equity_share_end - st.equity_share)


def _ibtm_df(sc: Scenarios, m: int) -> np.ndarray:
    tau = max(IBTM_MATURITY_M - m, 0.0) / 12.0
    return sc.df(m, [tau])[:, 0]


def growth_value(s: State, sc: Scenarios, m: int) -> np.ndarray:
    return s.eq.sum(1) + s.vgit + s.ibtm_face * _ibtm_df(sc, m) + s.cash


def _finite_path(name: str, value, shape: tuple[int | None, ...], *,
                 min_axes: tuple[int, ...] = (), shape_text: str | None = None) -> np.ndarray:
    text = str(shape) if shape_text is None else shape_text
    try:
        raw = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"scenarios.{name} must be a finite numeric array with shape {text}") from exc
    if raw.dtype.kind not in "iuf":
        raise ValueError(f"scenarios.{name} must be a finite numeric array with shape {text}")
    try:
        arr = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"scenarios.{name} must be a finite numeric array with shape {text}") from exc
    valid_shape = arr.ndim == len(shape) and all(
        expected is None or (actual >= expected if i in min_axes else actual == expected)
        for i, (actual, expected) in enumerate(zip(arr.shape, shape))
    )
    if not valid_shape or not np.isfinite(arr).all():
        raise ValueError(f"scenarios.{name} must be a finite numeric array with shape {text}")
    return arr


def _validate_state(state: State, n: int, K: int) -> None:
    specs = {
        "eq": ((n, K), True),
        "vgit": ((n,), True),
        "ibtm_face": ((n,), True),
        "floor_face": ((n,), True),
        "cash": ((n,), True),
        "locked": ((n, N_PAY), False),
        "costs": ((n,), True),
    }
    for name, (shape, nonnegative) in specs.items():
        try:
            raw = np.asarray(getattr(state, name))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"state.{name} must be a finite numeric array with shape {shape}") from exc
        has_boolean = raw.dtype.kind == "b" or (
            raw.dtype.kind == "O" and any(isinstance(x, (bool, np.bool_)) for x in raw.flat)
        )
        if has_boolean:
            raise ValueError(f"state.{name} must be a finite numeric array with shape {shape}")
        try:
            arr = np.asarray(raw, dtype=float)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"state.{name} must be a finite numeric array with shape {shape}") from exc
        if arr.shape != shape or not np.isfinite(arr).all():
            raise ValueError(f"state.{name} must be a finite numeric array with shape {shape}")
        if nonnegative and np.any(arr < 0.0):
            raise ValueError(f"state.{name} must be nonnegative")
        if name == "locked" and np.any((arr < 0.0) | (arr > 1.0)):
            raise ValueError("state.locked values must be fractions in [0, 1]")
        setattr(state, name, arr)
    for name in ("ratchet_ref", "ratchet_y"):
        value = getattr(state, name)
        if value is None:
            continue
        try:
            raw = np.asarray(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"state.{name} must be a finite numeric vector with shape ({n},)") from exc
        has_boolean = raw.dtype.kind == "b" or (
            raw.dtype.kind == "O" and any(isinstance(x, (bool, np.bool_)) for x in raw.flat)
        )
        if has_boolean:
            raise ValueError(f"state.{name} must be a finite numeric vector with shape ({n},)")
        try:
            arr = np.asarray(raw, dtype=float)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"state.{name} must be a finite numeric vector with shape ({n},)") from exc
        if arr.shape != (n,) or not np.isfinite(arr).all():
            raise ValueError(f"state.{name} must be a finite numeric vector with shape ({n},)")
        if name == "ratchet_ref" and np.any(arr < 0.0):
            raise ValueError("state.ratchet_ref must be nonnegative")
        setattr(state, name, arr)


def _real_config(name: str, value, *, lower: float | None = None,
                 strict_lower: bool = False) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"cfg.{name} must be a finite real number")
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"cfg.{name} must be a finite real number") from exc
    if not np.isfinite(x):
        raise ValueError(f"cfg.{name} must be finite")
    if lower is not None and (x <= lower if strict_lower else x < lower):
        relation = ">" if strict_lower else ">="
        raise ValueError(f"cfg.{name} must be {relation} {lower}")
    return x


def _validate_engine_config(cfg: EngineConfig, K: int) -> dict[int, float]:
    for name in ("commissions", "compound_costs", "sell_at_settlement"):
        if not isinstance(getattr(cfg, name), (bool, np.bool_)):
            raise ValueError(f"cfg.{name} must be boolean")
    if isinstance(cfg.extra_tickets, (bool, np.bool_)) or not isinstance(cfg.extra_tickets, Integral) or cfg.extra_tickets < 0:
        raise ValueError("cfg.extra_tickets must be a nonnegative integer")
    _real_config("extra_ticket_min", cfg.extra_ticket_min, lower=0.0)
    _real_config("annual_cost", cfg.annual_cost, lower=0.0)
    _real_config("kappa0", cfg.kappa0, lower=-1.0, strict_lower=True)
    slope = _real_config("kappa_rate_slope", cfg.kappa_rate_slope)
    if cfg.kappa_rate_ref is None:
        if slope != 0.0:
            raise ValueError("cfg.kappa_rate_ref is required when kappa_rate_slope is nonzero")
    else:
        _real_config("kappa_rate_ref", cfg.kappa_rate_ref)

    raw_deposits = cfg.deposits
    try:
        pairs = tuple(raw_deposits.items()) if isinstance(raw_deposits, Mapping) else tuple(raw_deposits)
    except (TypeError, ValueError) as exc:
        raise ValueError("cfg.deposits must be month and amount pairs") from exc
    deposits: dict[int, float] = {}
    for item in pairs:
        try:
            pair = tuple(item)
        except (TypeError, ValueError) as exc:
            raise ValueError("cfg.deposits must be month and amount pairs") from exc
        if (len(pair) != 2 or isinstance(pair[0], (bool, np.bool_))
                or not isinstance(pair[0], Integral) or not 0 <= pair[0] <= M_2033):
            raise ValueError(f"cfg.deposits entries need unique integer months in [0, {M_2033}]")
        month = int(pair[0])
        if month in deposits:
            raise ValueError(f"cfg.deposits contains duplicate month {month}")
        deposits[month] = _real_config(f"deposits[{month}]", pair[1], lower=0.0)

    if cfg.fund_groups is not None:
        try:
            groups = tuple(tuple(group) for group in cfg.fund_groups)
        except (TypeError, ValueError) as exc:
            raise ValueError("cfg.fund_groups must partition the equity indices") from exc
        flat = [i for group in groups for i in group]
        if (not groups or any(not group for group in groups)
                or any(isinstance(i, (bool, np.bool_)) or not isinstance(i, Integral) for i in flat)
                or len(flat) != K or set(map(int, flat)) != set(range(K))):
            raise ValueError("cfg.fund_groups must partition the equity indices exactly once")
    return deposits


def _engine_config(cfg: EngineConfig | None) -> EngineConfig:
    if cfg is None:
        return EngineConfig()
    if not isinstance(cfg, EngineConfig):
        raise ValueError("cfg must be an engine.EngineConfig instance or None")
    return replace(cfg)


def _funds(w: np.ndarray, cfg: EngineConfig) -> list[np.ndarray]:
    """Index sets of the equity funds actually held (one ticket and one drift check each)."""
    groups = cfg.fund_groups or [(i,) for i in range(len(w))]
    return [np.array(g) for g in groups if w[list(g)].sum() > 0]


def _invest(s: State, sc: Scenarios, m: int, st: Strategy, amount: np.ndarray, cfg: EngineConfig,
            eq_target: float | None = None):
    """Invest `amount` at the strategy's target mix."""
    eq_target = st.equity_share if eq_target is None else eq_target
    w = np.array(st.region_weights)
    s.eq += np.outer(amount * eq_target, w)
    bonds = amount * (1 - eq_target)
    if st.bond_vehicle == "VGIT":
        s.vgit += bonds
    else:
        s.ibtm_face += bonds / _ibtm_df(sc, m)
    if cfg.commissions:
        tickets = len(_funds(w, cfg)) * (eq_target > 0) + (eq_target < 1)
        s.costs += np.where(amount > 0, COMMISSION_ETF * tickets, 0.0)
        s.costs += np.where(amount >= cfg.extra_ticket_min, COMMISSION_ETF * cfg.extra_tickets, 0.0)


def _rebalance(s: State, sc: Scenarios, m: int, st: Strategy, cfg: EngineConfig,
               force: bool | np.ndarray = False, eq_target: float | None = None):
    df = _ibtm_df(sc, m)
    bonds = s.vgit + s.ibtm_face * df
    total = s.eq.sum(1) + bonds + s.cash
    eq_share = np.divide(s.eq.sum(1), total, out=np.zeros_like(total), where=total > 0)
    region = np.divide(s.eq, s.eq.sum(1, keepdims=True), out=np.zeros_like(s.eq), where=s.eq.sum(1, keepdims=True) > 0)
    target_eq = st.equity_share if eq_target is None else eq_target
    drift = np.abs(eq_share - target_eq) > st.band
    target = np.array(st.region_weights)
    for f in _funds(target, cfg):
        drift |= (np.abs(region[:, f].sum(1) - target[f].sum()) > 0.05) & (s.eq.sum(1) > 0)
    do = drift | force
    if not np.any(do):
        return
    s.eq[do] = 0.0
    s.vgit[do] = 0.0
    s.ibtm_face[do] = 0.0
    s.cash[do] = 0.0
    amount = np.where(do, total, 0.0)
    _invest(s, sc, m, st, amount, cfg, eq_target=target_eq)


def _lock(s: State, sc: Scenarios, m: int, target: float, budget: np.ndarray, cfg: EngineConfig) -> np.ndarray:
    """Raise every payment's matched fraction toward `target`, longest payment first, within budget.
    Returns money spent."""
    tau = pay_tau(m)
    unit = PMT * sc.df(m, np.maximum(tau, 0)) * (1 + kappa(m, cfg, sc))      # (N, K) cost of a full payment
    need = np.clip(target - s.locked, 0, None)                              # (N, K)
    spent = np.zeros(sc.n)
    left = budget.copy()
    for k in range(N_PAY - 1, -1, -1):
        cost_k = need[:, k] * unit[:, k]
        frac = np.where(cost_k > 0, np.minimum(1.0, left / np.where(cost_k > 0, cost_k, 1)), 0.0)
        s.locked[:, k] += need[:, k] * frac
        paid = cost_k * frac
        left -= paid
        spent += paid
    if cfg.commissions:
        s.costs += np.where(spent > 0, 5 * COMMISSION_ETF + 5 * COMMISSION_BOND, 0.0)
    return spent


def _liquidate(s: State, sc: Scenarios, m: int, amount: np.ndarray):
    """Sell growth assets pro rata to raise `amount` (capped at what exists)."""
    df = _ibtm_df(sc, m)
    total = s.eq.sum(1) + s.vgit + s.ibtm_face * df + s.cash
    f = np.divide(np.minimum(amount, total), total, out=np.zeros_like(total), where=total > 0)
    s.eq *= (1 - f)[:, None]
    s.vgit *= 1 - f
    s.ibtm_face *= 1 - f
    s.cash *= 1 - f
    return np.minimum(amount, total)


def _invested(s: State, sc: Scenarios, m: int) -> np.ndarray:
    """Everything outside the reserve ladder: the growth sleeve plus the floor, at month m prices."""
    return growth_value(s, sc, m) + s.floor_face * _ibtm_df(sc, m)


def _step(s: State, sc: Scenarios, m: int, cfg: "EngineConfig"):
    """Advance one month: markets move, fees accrue."""
    v0 = _invested(s, sc, m) if cfg.compound_costs else None
    s.eq *= np.exp(sc.eq_log[:, m - sc.m0, :]) * (1 - np.asarray(cfg.eq_er) / 12)
    if cfg.commissions and cfg.annual_cost and m >= M_2027:
        s.costs += cfg.annual_cost / 12
    y0 = np.expm1(sc.zero_cc(m, [VGIT_TAU])[:, 0])
    y1 = np.expm1(sc.zero_cc(m + 1, [VGIT_TAU])[:, 0])
    dy = y1 - y0
    s.vgit *= (1 + y0) ** (1 / 12) - VGIT_DUR * dy + 0.5 * VGIT_CONV * dy ** 2 - ER["VGIT"] / 12
    s.ibtm_face *= 1 - ER["IBTM"] / 12
    s.floor_face *= 1 - ER["IBTM"] / 12
    short = np.expm1(sc.zero_cc(m, [0.25])[:, 0])
    s.cash *= (1 + short) ** (1 / 12)
    if v0 is not None:
        # Commissions are settled from the portfolio in 2033; growing what is owed at the portfolio's
        # own monthly return is the same as having paid each one when it was incurred.
        v1 = _invested(s, sc, m + 1)
        s.costs *= np.divide(v1, v0, out=np.ones_like(v0), where=v0 > 0)


def run(st: Strategy, sc: Scenarios, cfg: EngineConfig | None = None, state: State | None = None,
        snapshot_2031: bool = False) -> dict:
    """Simulate from month sc.m0. With `state`, the events at month sc.m0 are taken as done
    (used to continue a scenario from its January 2031 position)."""
    if not isinstance(st, Strategy):
        raise ValueError("st must be a strategies.Strategy instance")
    cfg = _engine_config(cfg)
    if not isinstance(snapshot_2031, (bool, np.bool_)):
        raise ValueError("snapshot_2031 must be boolean")
    m0 = getattr(sc, "m0", 0)
    if isinstance(m0, bool) or not isinstance(m0, Integral) or not 0 <= m0 <= M_2033:
        raise ValueError(f"scenario m0 must be an integer month from 0 through {M_2033}")
    horizon = M_2033 - int(m0)
    n = sc.n
    if isinstance(n, bool) or not isinstance(n, Integral) or n <= 0:
        raise ValueError("scenarios must contain a positive integer number of paths")
    eq_log = _finite_path("eq_log", sc.eq_log, (int(n), None, None), shape_text="(n, months, assets)")
    if eq_log.shape[1] < horizon or eq_log.shape[2] == 0:
        raise ValueError(f"scenarios.eq_log must cover {horizon} months and at least one equity")
    K = eq_log.shape[2]
    if len(st.region_weights) != K:
        raise ValueError(f"strategy region_weights has {len(st.region_weights)} entries but scenarios have {K} equities")
    try:
        raw_eq_er = np.asarray(cfg.eq_er, dtype=object)
        if any(isinstance(x, (bool, np.bool_)) or not isinstance(x, Real) for x in raw_eq_er.flat):
            raise ValueError("expense ratios must be real numbers")
        eq_er = np.asarray([float(x) for x in raw_eq_er.flat], dtype=float).reshape(raw_eq_er.shape)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"cfg.eq_er must be a finite vector in [0, 12) with shape ({K},)") from exc
    if eq_er.shape != (K,) or not np.isfinite(eq_er).all() or np.any((eq_er < 0.0) | (eq_er >= 12.0)):
        raise ValueError(f"cfg.eq_er must be a finite vector in [0, 12) with shape ({K},)")
    cfg.eq_er = tuple(eq_er)
    deposits = _validate_engine_config(cfg, K)
    _finite_path("beta", sc.beta, (int(n), horizon + 1, 3), min_axes=(1,))
    _finite_path("infl", sc.infl, (int(n), horizon + 1), min_axes=(1,))
    _finite_path("fx_log", sc.fx_log, (int(n), horizon + 1), min_axes=(1,))
    _finite_path("tw_cost_log", sc.tw_cost_log, (int(n), horizon + 1), min_axes=(1,))
    _finite_path("resid", sc.resid, (len(TAU_GRID),))
    if m0 <= M_2027:
        i27 = M_2027 - int(m0)
        fx_2027 = sc.fx_log[:, i27]
        tw_cost_2027 = sc.tw_cost_log[:, i27]
    else:
        fx_base = getattr(sc, "fx_log_2027", None)
        tw_cost_base = getattr(sc, "tw_cost_log_2027", None)
        if fx_base is None or tw_cost_base is None:
            raise ValueError("nested scenarios need their January 2027 FX and Taiwan-cost baselines")
        fx_2027 = _finite_path("fx_log_2027", fx_base, (int(n),))
        tw_cost_2027 = _finite_path("tw_cost_log_2027", tw_cost_base, (int(n),))
    if isinstance(sc.rate_floor, (bool, np.bool_)) or not isinstance(sc.rate_floor, Real):
        raise ValueError("scenarios.rate_floor must be a finite scalar")
    try:
        rate_floor = float(sc.rate_floor)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("scenarios.rate_floor must be a finite scalar") from exc
    if not np.isfinite(rate_floor):
        raise ValueError("scenarios.rate_floor must be a finite scalar")
    s = state if state is not None else State(
        np.zeros((n, K)), np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n),
        np.zeros((n, N_PAY)), np.zeros(n),
    )
    if not isinstance(s, State):
        raise ValueError("state must be an engine.State instance or None")
    _validate_state(s, int(n), K)
    out: dict = {}
    for m in range(sc.m0, M_2033 + 1):
        if state is not None and m == sc.m0:
            pass
        elif m in deposits:
            cash_in = np.full(n, deposits[m])
            target = st.lock_2027 if m == M_2027 else st.lock_2028
            spent = _lock(s, sc, m, target, cash_in, cfg) if target > 0 else np.zeros(n)
            if m == M_2027:
                out["lock_cost_2027"] = spent + 0.0
            _invest(s, sc, m, st, cash_in - spent, cfg)
            if m == M_2028:
                _rebalance(s, sc, m, st, cfg)
                s.ratchet_ref = growth_value(s, sc, m).copy()
                tau = max(IBTM_MATURITY_M - m, 0.0) / 12.0
                s.ratchet_y = -np.log(_ibtm_df(sc, m)) / tau - ER["IBTM"]
        elif m in REBAL_MONTHS or m == M_2031:
            if m == M_2031 and st.lock_2031 > 0:
                tau = pay_tau(m)
                unit = PMT * sc.df(m, tau) * (1 + kappa(m, cfg, sc))
                need_cost = (np.clip(st.lock_2031 - s.locked, 0, None) * unit).sum(1)
                raised = _liquidate(s, sc, m, need_cost)
                _lock(s, sc, m, st.lock_2031, raised, cfg)
            g = growth_value(s, sc, m)
            if m == M_2031:
                out["growth_2031"] = g.copy()
                out["assets_2031"] = (g + s.floor_face * _ibtm_df(sc, m)).copy()

            eq_target = target_equity_share(st, m)
            r_move = np.zeros(n)
            if st.ratchet_trigger is not None and st.ratchet_share > 0 and s.ratchet_ref is not None:
                dt = (m - M_2028) / 12.0
                ref = s.ratchet_ref * np.exp(s.ratchet_y * dt)
                excess = np.maximum(g - st.ratchet_trigger * ref, 0.0)
                r_move = st.ratchet_share * excess

            g_rem = g - r_move
            floor_share = st.effective_floor_share
            is_floor_year = (m == month_of(st.floor_year)) and (floor_share > 0)
            f_move = g_rem * floor_share if is_floor_year else np.zeros(n)
            to_move = r_move + f_move

            # Moving money into the floor and rebalancing the rest is one trade per fund: the forced
            # rebalance charges a ticket for each fund and the sleeve's bond fund. The floor's IBTM needs
            # its own ticket only when the sleeve holds VGIT.
            floor_ticket = COMMISSION_ETF * (st.bond_vehicle == "VGIT")
            if is_floor_year:
                moved = _liquidate(s, sc, m, to_move)
                s.floor_face += moved / _ibtm_df(sc, m)
                _rebalance(s, sc, m, st, cfg, force=True, eq_target=eq_target)
                if cfg.commissions:
                    s.costs += floor_ticket
            elif np.any(to_move > 0):
                moved = _liquidate(s, sc, m, to_move)
                s.floor_face += moved / _ibtm_df(sc, m)
                _rebalance(s, sc, m, st, cfg, force=(to_move > 0), eq_target=eq_target)
                if cfg.commissions:
                    s.costs += np.where(to_move > 0, floor_ticket, 0.0)
            else:
                _rebalance(s, sc, m, st, cfg, eq_target=eq_target)

            if m == M_2031:
                out["floor_2033"] = s.floor_face * (1 - ER["IBTM"] / 12) ** (M_2033 - m)  # value reaching Dec 2032
                out["locked_2031"] = s.locked.mean(1)
                if snapshot_2031:
                    out["state_2031"] = State(
                        *(a.copy() for a in (s.eq, s.vgit, s.ibtm_face, s.floor_face, s.cash, s.locked, s.costs)),
                        ratchet_ref=None if s.ratchet_ref is None else s.ratchet_ref.copy(),
                        ratchet_y=None if s.ratchet_y is None else s.ratchet_y.copy(),
                    )
        if m == M_2033:
            break
        _step(s, sc, m, cfg)
    # January 2033 settlement
    if cfg.commissions and cfg.sell_at_settlement:
        # IBTM has matured into cash; each equity fund, VGIT and the extra names are sold
        held = sum((s.eq[:, f].sum(1) > 0).astype(float) for f in _funds(np.array(st.region_weights), cfg))
        s.costs += COMMISSION_ETF * (held + (s.vgit > 0) + np.where(s.eq.sum(1) > 0, cfg.extra_tickets, 0))
    assets = s.eq.sum(1) + s.vgit + s.ibtm_face + s.floor_face + s.cash - s.costs
    open_cost = ((1 - s.locked) * PMT * sc.df(M_2033, pay_tau(M_2033)) * (1 + kappa(M_2033, cfg, sc))).sum(1)
    funded = assets >= open_cost - 1e-6
    facility = np.maximum(assets - open_cost, 0.0)
    i33 = M_2033 - sc.m0
    real = facility * np.exp(sc.fx_log[:, i33] - fx_2027) / np.exp(sc.tw_cost_log[:, i33] - tw_cost_2027)
    out.update({"funded": funded, "facility": facility, "contribution": facility * st.contribution_share,
                "facility_real_tw2027": real, "assets_2033": assets, "open_cost_2033": open_cost,
                "shortfall": np.maximum(open_cost - assets, 0.0), "locked_2033": s.locked.mean(1),
                "costs_2033": s.costs.copy()})
    out.setdefault("floor_2033", np.zeros(n))
    out.setdefault("growth_2031", np.zeros(n))
    out.setdefault("assets_2031", np.zeros(n))
    out.setdefault("lock_cost_2027", np.zeros(n))
    return out


def summarize(res: dict[str, np.ndarray]) -> dict[str, float]:
    f = res["facility"]
    p = lambda q: float(np.percentile(f, q))
    tail = f[f <= np.percentile(f, 5)]
    return {"funded": float(res["funded"].mean()), "p5": p(5), "p10": p(10), "median": p(50),
            "p90": p(90), "p95": p(95), "cvar5": float(tail.mean()) if tail.size else 0.0,
            "real_median": float(np.median(res["facility_real_tw2027"]))}


def state_for(snap: State, i: int, n: int) -> State:
    """Scenario i's state repeated n times."""
    n = _positive_integer("n", n)
    if not isinstance(snap, State):
        raise ValueError("snap must be an engine.State instance")
    if (isinstance(i, (bool, np.bool_)) or not isinstance(i, Integral)
            or np.asarray(snap.eq).ndim < 1 or not 0 <= i < np.asarray(snap.eq).shape[0]):
        raise ValueError("i must be an integer scenario index present in snap")
    i = int(i)
    rep = lambda a: np.repeat(a[i:i + 1], n, axis=0)
    return State(rep(snap.eq), rep(snap.vgit), rep(snap.ibtm_face), rep(snap.floor_face), rep(snap.cash),
                 rep(snap.locked), rep(snap.costs),
                 ratchet_ref=None if snap.ratchet_ref is None else rep(snap.ratchet_ref),
                 ratchet_y=None if snap.ratchet_y is None else rep(snap.ratchet_y))


def _positive_integer(name: str, value) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _quote_seed(seed) -> int | None:
    if seed is None:
        return None
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer or None")
    return int(seed)


def _conditional_rank(sc: Scenarios, res: dict) -> tuple[int, np.ndarray]:
    if not isinstance(res, Mapping):
        raise ValueError("res must be a mapping returned by engine.run")
    n = getattr(sc, "n", None)
    if isinstance(n, (bool, np.bool_)) or not isinstance(n, Integral) or n < 1:
        raise ValueError("scenarios must contain a positive integer number of paths")
    n = int(n)
    if not isinstance(res.get("state_2031"), State):
        raise ValueError("res must include state_2031; call engine.run(..., snapshot_2031=True)")
    for name in ("floor_2033", "growth_2031"):
        try:
            values = np.asarray(res[name], dtype=float)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"res[{name!r}] must be a finite vector with shape ({n},)") from exc
        if values.shape != (n,) or not np.isfinite(values).all():
            raise ValueError(f"res[{name!r}] must be a finite vector with shape ({n},)")
    rank = res.get("assets_2031", res["growth_2031"])
    try:
        rank = np.asarray(rank, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"res['assets_2031'] must be a finite vector with shape ({n},)") from exc
    if rank.shape != (n,) or not np.isfinite(rank).all():
        raise ValueError(f"res['assets_2031'] must be a finite vector with shape ({n},)")
    return n, rank


def conditional_2031(st: Strategy, sc: Scenarios, res: dict, params, i: int | None = None,
                     n_inner: int = 4000, seed: int = 99, cfg: EngineConfig | None = None,
                     keep_drift: bool = True) -> dict:
    """What Laura could tell co-sponsors in January 2031: re-simulate 2031-2033 from one
    scenario's 2031 position. Default: the scenario with the median 2031 growth value."""
    from dataclasses import replace as dc_replace

    from .esg import simulate

    if not isinstance(st, Strategy):
        raise ValueError("st must be a strategies.Strategy instance")
    cfg = _engine_config(cfg)
    if not isinstance(keep_drift, (bool, np.bool_)):
        raise ValueError("keep_drift must be boolean")
    n_inner = _positive_integer("n_inner", n_inner)
    seed = _quote_seed(seed)
    n, rank_on = _conditional_rank(sc, res)
    if i is None:
        # Rank on what the client holds in Jan 2031, before that month's floor move: growth assets
        # plus any floor already bought (an earlier floor year, or ratchet moves). Without an
        # earlier floor this equals growth_2031, so 2031-floor policies rank exactly as before.
        i = int(np.argsort(rank_on)[len(rank_on) // 2])
    elif isinstance(i, (bool, np.bool_)) or not isinstance(i, Integral) or not 0 <= i < n:
        raise ValueError(f"i must be an integer scenario index in [0, {n})")
    else:
        i = int(i)
    start = {"beta": sc.beta[i, M_2031 - sc.m0], "infl": sc.infl[i, M_2031 - sc.m0],
             "fx_log": np.full(n_inner, sc.fx_log[i, M_2031 - sc.m0]),
             "tw_cost_log": np.full(n_inner, sc.tw_cost_log[i, M_2031 - sc.m0])}
    if sc.m0 <= M_2027:
        fx_2027 = sc.fx_log[i, M_2027 - sc.m0]
        tw_cost_2027 = sc.tw_cost_log[i, M_2027 - sc.m0]
    else:
        fx_base = getattr(sc, "fx_log_2027", None)
        tw_cost_base = getattr(sc, "tw_cost_log_2027", None)
        if fx_base is None or tw_cost_base is None:
            raise ValueError("conditional_2031 needs January 2027 FX and Taiwan-cost baselines")
        fx_2027, tw_cost_2027 = fx_base[i], tw_cost_base[i]
    start["fx_log_2027"] = np.full(n_inner, fx_2027)
    start["tw_cost_log_2027"] = np.full(n_inner, tw_cost_2027)
    if keep_drift and getattr(sc, "eq_drift_err", None) is not None:
        start["eq_drift_err"] = sc.eq_drift_err[i]
    if getattr(sc, "garch_h", None) is not None:
        start["garch_h"] = sc.garch_h[i, M_2031 - sc.m0]
    if getattr(sc, "tw_cost_infl", None) is not None:
        idx = M_2031 - sc.m0
        start["tw_cost_infl"] = (sc.tw_cost_infl[i, max(idx - 1, 0)], sc.tw_cost_infl[i, idx])
    p = dc_replace(params, months=M_2033 - M_2031)
    inner = simulate(p, n_inner, seed=seed, start=start, m0=M_2031)
    r = run(st, inner, cfg, state=state_for(res["state_2031"], i, n_inner))
    f = r["facility"]
    return {"scenario": i, "floor": float(res["floor_2033"][i]), "growth_2031": float(res["growth_2031"][i]),
            "p10": float(np.percentile(f, 10)), "median": float(np.median(f)), "p90": float(np.percentile(f, 90)),
            "p5": float(np.percentile(f, 5)), "p95": float(np.percentile(f, 95)), "inner": f}


def conditional_2031_band(st: Strategy, sc: Scenarios, res: dict, params, q: float = 0.5,
                          width: float = 0.05, k: int = 21, n_inner: int = 3000, seed: int = 99,
                          cfg: EngineConfig | None = None, percentiles=(5, 10, 20, 50, 80, 90, 95)) -> dict:
    """The 2031 quote for a world at percentile q of Jan 2031 wealth, made stable: the median, across k
    scenarios spread evenly over percentiles q-width..q+width, of each scenario's own quote. One
    scenario alone is noisy: within the 45-55th percentile band the floor bought in Jan 2031 varies by
    about +/-$4k with that month's interest rates."""
    def finite_real(name, value):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise ValueError(f"{name} must be a finite real number")
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be a finite real number") from exc
        if not np.isfinite(value):
            raise ValueError(f"{name} must be a finite real number")
        return value

    q = finite_real("q", q)
    width = finite_real("width", width)
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    if not 0.0 <= width <= 1.0:
        raise ValueError("width must be in [0, 1]")
    n_inner = _positive_integer("n_inner", n_inner)
    k = _positive_integer("k", k)
    seed = _quote_seed(seed)
    if not isinstance(st, Strategy):
        raise ValueError("st must be a strategies.Strategy instance")
    cfg = _engine_config(cfg)
    n, rank_on = _conditional_rank(sc, res)
    if k > n:
        raise ValueError(f"k must be no greater than the number of scenarios ({n})")
    try:
        pct = tuple(percentiles)
    except TypeError as exc:
        raise ValueError("percentiles must be a nonempty sequence of unique values in [0, 100]") from exc
    pcs = tuple(finite_real("percentiles", pc) for pc in pct)
    if not pcs or any(not 0.0 <= pc <= 100.0 for pc in pcs) or len(set(pcs)) != len(pcs):
        raise ValueError("percentiles must be a nonempty sequence of unique values in [0, 100]")
    order = np.argsort(rank_on)
    n = len(order)
    picks = [int(order[int(round(x * (n - 1)))]) for x in np.linspace(max(q - width, 0), min(q + width, 1), k)]
    rows = [conditional_2031(st, sc, res, params, i=i, n_inner=n_inner, seed=seed, cfg=cfg) for i in picks]
    floors = np.array([c["floor"] for c in rows])
    out = {"scenarios": picks, "floor": float(np.median(floors)),
           "floor_range": (float(floors.min()), float(floors.max())),
           "growth_2031": float(np.median([c["growth_2031"] for c in rows]))}
    for pc in pcs:
        out[f"p{pc:g}"] = float(np.median([np.percentile(c["inner"], pc) for c in rows]))
    out["median"] = out.get("p50", float(np.median([c["median"] for c in rows])))
    return out
