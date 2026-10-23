"""Cash-flow-matched operating reserve (dedicated bond portfolio) as a linear program.

Choose holdings x_j >= 0 to minimise cost sum_j p_j x_j such that every payment is met.
Cash received before a payment (coupons, maturities, fund terminations) is reinvested at a
conservative rate r until that payment; any surplus after a payment rolls to the next one:

    s_k = s_{k-1} * (1+r)^(T_k - T_{k-1}) + sum_j A_kj x_j - L_k,   s_k >= 0

where A_kj is instrument j's cash arriving in (T_{k-1}, T_k], grown at r to T_k.
Solved with HiGHS (scipy.optimize.linprog). Only WInS-permitted instruments are used.
"""
from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from numbers import Integral, Real

import numpy as np
from scipy.optimize import linprog

from .curve import ZeroCurve
from .dates import as_date, year_frac
from .instruments import TermFund, TreasuryBond, TreasuryStrip


def _payment_rows(payments) -> tuple[tuple[dt.date, float], ...]:
    try:
        rows = tuple(payments)
    except TypeError as exc:
        raise ValueError("payments must be a nonempty sequence of date and positive amount pairs") from exc
    if not rows:
        raise ValueError("payments must be a nonempty sequence of date and positive amount pairs")
    out = []
    for row in rows:
        try:
            date, amount = tuple(row)
            date = as_date(date)
        except (TypeError, ValueError) as exc:
            raise ValueError("payments must contain valid date and amount pairs") from exc
        if isinstance(amount, (bool, np.bool_)) or not isinstance(amount, Real):
            raise ValueError("payment amounts must be finite positive real numbers")
        try:
            amount = float(amount)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("payment amounts must be finite positive real numbers") from exc
        if not np.isfinite(amount) or amount <= 0.0:
            raise ValueError("payment amounts must be finite positive real numbers")
        if out and date <= out[-1][0]:
            raise ValueError("payment dates must be strictly increasing")
        out.append((date, amount))
    return tuple(out)


def _reinvestment_rate(value: float) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError("reinvest must be a finite real rate greater than -100%")
    try:
        rate = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("reinvest must be a finite real rate greater than -100%") from exc
    if not np.isfinite(rate) or rate <= -1.0:
        raise ValueError("reinvest must be a finite real rate greater than -100%")
    return rate


def _constraint_dollars(name: str, values, labels: list[str]) -> dict[str, float]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError(f"{name} must map instrument labels to finite nonnegative amounts")
    out = {}
    for label, amount in values.items():
        if label not in labels:
            raise ValueError(f"{name} contains unknown instrument label {label!r}")
        if isinstance(amount, (bool, np.bool_)) or not isinstance(amount, Real):
            raise ValueError(f"{name}[{label!r}] must be a finite nonnegative amount")
        try:
            amount = float(amount)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name}[{label!r}] must be a finite nonnegative amount") from exc
        if not np.isfinite(amount) or amount < 0.0:
            raise ValueError(f"{name}[{label!r}] must be a finite nonnegative amount")
        out[label] = amount
    return out


@dataclass
class LadderResult:
    cost: float
    holdings: dict[str, float]          # label -> dollars invested
    units: dict[str, float]             # label -> face (bonds) or dollars (funds)
    surplus: list[float] = field(default_factory=list)
    status: str = ""


def payment_schedule(first: str = "2033-01-01", n: int = 10, amount: float = 50_000.0) -> list[tuple[dt.date, float]]:
    d0 = as_date(first)
    if isinstance(n, (bool, np.bool_)) or not isinstance(n, Integral) or n < 1:
        raise ValueError("n must be a positive integer")
    if isinstance(amount, (bool, np.bool_)) or not isinstance(amount, Real):
        raise ValueError("amount must be a finite positive real number")
    try:
        amount = float(amount)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("amount must be a finite positive real number") from exc
    if not np.isfinite(amount) or amount <= 0.0:
        raise ValueError("amount must be a finite positive real number")
    rows = []
    for k in range(int(n)):
        year = d0.year + k
        day = min(d0.day, calendar.monthrange(year, d0.month)[1])
        date = dt.date(year, d0.month, day)
        rows.append((date, amount))
    return list(_payment_rows(rows))


def _flows(inst, curve: ZeroCurve, settle: dt.date):
    if isinstance(inst, TreasuryBond):
        return inst.cashflows(settle), inst.dirty_price(curve) / 100.0, inst.label or inst.cusip, 100.0
    if isinstance(inst, TermFund):
        return inst.cashflows(settle, curve), 1.0, inst.ticker, 1.0
    if isinstance(inst, TreasuryStrip):
        return inst.cashflows(settle), inst.dirty_price(curve) / 100.0, inst.label or inst.cusip, 100.0
    raise TypeError(inst)


def build_matrix(instruments, payments, curve: ZeroCurve, reinvest: float):
    instruments = tuple(instruments)
    payments = _payment_rows(payments)
    reinvest = _reinvestment_rate(reinvest)
    if not isinstance(curve, ZeroCurve):
        raise ValueError("curve must be a curve.ZeroCurve instance")
    settle = curve.date
    pay_dates = [as_date(d) for d, _ in payments]
    A = np.zeros((len(payments), len(instruments)))
    prices, labels, scale = [], [], []
    for j, inst in enumerate(instruments):
        flows, price, label, unit = _flows(inst, curve, settle)
        if not isinstance(label, str) or not label:
            raise ValueError("every instrument must have a nonempty string label")
        if label in labels:
            raise ValueError(f"instrument labels must be unique; duplicate label {label!r}")
        if not flows:
            raise ValueError(f"instrument {label!r} has no future cash flows at the curve date")
        if not np.isfinite(price) or price <= 0.0 or not np.isfinite(unit) or unit <= 0.0:
            raise ValueError(f"instrument {label!r} must have a finite positive price and unit scale")
        prices.append(price)
        labels.append(label)
        scale.append(unit)
        for d, cf in flows:
            k = next((i for i, pd in enumerate(pay_dates) if d <= pd), None)
            if k is None:
                continue  # arrives after the last payment: no credit (conservative)
            A[k, j] += (cf / unit) * (1 + reinvest) ** year_frac(d, pay_dates[k])
    if not np.isfinite(A).all() or np.any(A < 0.0):
        raise ValueError("instrument cash flows must produce a finite nonnegative ladder matrix")
    return A, np.array(prices), labels, scale


def solve(instruments, payments, curve: ZeroCurve, reinvest: float = 0.03,
          fixed: dict[str, float] | None = None, minimum: dict[str, float] | None = None) -> LadderResult:
    """Cheapest cash-flow-matched portfolio. `fixed` pins dollar amounts by label; `minimum`
    sets dollar floors (e.g. to force one rung per payment for a simpler ladder)."""
    instruments = tuple(instruments)
    payments = _payment_rows(payments)
    A, p, labels, _ = build_matrix(instruments, payments, curve, reinvest)
    fixed = _constraint_dollars("fixed", fixed, labels)
    minimum = _constraint_dollars("minimum", minimum, labels)
    for label in fixed.keys() & minimum.keys():
        if minimum[label] > fixed[label]:
            raise ValueError(f"fixed amount for {label!r} is below its minimum")
    K, J = A.shape
    L = np.array([a for _, a in payments])
    pay_dates = [as_date(d) for d, _ in payments]
    g = [0.0] + [(1 + reinvest) ** year_frac(pay_dates[k - 1], pay_dates[k]) for k in range(1, K)]
    # variables: x (J) dollars-of-price units, s (K) surplus
    c = np.concatenate([p, np.zeros(K)])
    Aeq = np.zeros((K, J + K))
    for k in range(K):
        Aeq[k, :J] = A[k]
        Aeq[k, J + k] = -1.0
        if k > 0:
            Aeq[k, J + k - 1] = g[k]
    bounds = [(0, None)] * (J + K)
    if fixed:
        for j, lab in enumerate(labels):
            if lab in fixed:
                units = fixed[lab] / p[j]
                bounds[j] = (units, units)
    if minimum:
        for j, lab in enumerate(labels):
            if lab in minimum and lab not in fixed:
                bounds[j] = (minimum[lab] / p[j], None)
    res = linprog(c, A_eq=Aeq, b_eq=L, bounds=bounds, method="highs")
    if not res.success:
        return LadderResult(float("nan"), {}, {}, [], res.message)
    x = res.x[:J]
    hold = {lab: float(xj * pj) for lab, xj, pj in zip(labels, x, p) if xj * pj > 0.5}
    units = {lab: float(xj) for lab, xj in zip(labels, x) if xj > 1e-9}   # bonds: face $; funds: $
    return LadderResult(float(res.fun), hold, units, list(res.x[J:]), "optimal")


def check_coverage(instruments, dollars: dict[str, float], payments, curve: ZeroCurve, reinvest: float = 0.03):
    """Given fixed dollar holdings, return the surplus after each payment (negative = shortfall)."""
    instruments = tuple(instruments)
    payments = _payment_rows(payments)
    if not isinstance(curve, ZeroCurve):
        raise ValueError("curve must be a curve.ZeroCurve instance")
    reinvest = _reinvestment_rate(reinvest)
    dollars = _constraint_dollars("dollars", dollars, [
        _flows(inst, curve, curve.date)[2] for inst in instruments
    ])
    A, p, labels, _ = build_matrix(instruments, payments, curve, reinvest)
    x = np.array([dollars.get(lab, 0.0) / pj for lab, pj in zip(labels, p)])
    pay_dates = [as_date(d) for d, _ in payments]
    s, out = 0.0, []
    for k, (_, amt) in enumerate(payments):
        if k > 0:
            s *= (1 + reinvest) ** year_frac(pay_dates[k - 1], pay_dates[k])
        s += float(A[k] @ x) - amt
        out.append(s)
    return out


def zero_coupon_cost(curve: ZeroCurve, payments, as_of: dt.date | str | None = None) -> float:
    """Value of the payments on the zero curve. `as_of` re-bases times (guide convention)."""
    payments = _payment_rows(payments)
    if not isinstance(curve, ZeroCurve):
        raise ValueError("curve must be a curve.ZeroCurve instance")
    base = as_date(as_of) if as_of else curve.date
    return float(sum(a * curve.df(year_frac(base, d)) for d, a in payments))


def wins_reserve_universe():
    """Instruments the reserve may use: WInS-listed Treasury bonds and the iBonds term funds."""
    from .instruments import IBONDS_TREASURY, ibonds_fund, wins_treasury_bonds

    return wins_treasury_bonds(2032, 2042) + [ibonds_fund(t) for t in IBONDS_TREASURY if IBONDS_TREASURY[t] >= 2032]


def premium(curve: ZeroCurve, reinvest: float = 0.03, instruments=None) -> float:
    """Cost of the cheapest real-instrument ladder over the payments' zero-coupon value. This is the
    engine's `kappa0`; it grows as the assumed reinvestment rate for cash awaiting a payment falls."""
    pays = payment_schedule()
    if pays[0][0] <= curve.date:
        raise ValueError("first payment must be strictly after the curve date")
    universe = tuple(instruments) if instruments is not None else ()
    if not universe:
        universe = tuple(wins_reserve_universe())
    active = [inst for inst in universe if _flows(inst, curve, curve.date)[0]]
    if not active:
        raise ValueError("premium needs at least one instrument with future cash flows")
    lp = solve(active, pays, curve, reinvest)
    return lp.cost / zero_coupon_cost(curve, pays) - 1.0


def idle_cash_days(instruments, units: dict[str, float], payments, curve: ZeroCurve, reinvest: float = 0.0) -> dict[str, float]:
    """Calculate idle cash dollar-days and dollar-weighted average days for a funded ladder.

    Cash received strictly before payment T_k idles until T_k.
    Any surplus remaining after T_k idles from T_k to T_{k+1}.
    """
    instruments = tuple(instruments)
    payments = _payment_rows(payments)
    reinvest = _reinvestment_rate(reinvest)
    if not isinstance(curve, ZeroCurve):
        raise ValueError("curve must be a curve.ZeroCurve instance")
    settle = curve.date
    pay_dates = [as_date(d) for d, _ in payments]
    K = len(payments)
    inst_by_label = {}
    for inst in instruments:
        flows, _, label, _ = _flows(inst, curve, settle)
        if label in inst_by_label:
            raise ValueError(f"instrument labels must be unique; duplicate label {label!r}")
        if not flows:
            raise ValueError(f"instrument {label!r} has no future cash flows at the curve date")
        inst_by_label[label] = inst
    units = _constraint_dollars("units", units, list(inst_by_label))

    total_dollar_days = 0.0
    surplus = 0.0
    total_payments = sum(amt for _, amt in payments)

    for k, (pd, amt) in enumerate(payments):
        prev_d = pay_dates[k - 1] if k > 0 else settle
        cash_arrived = 0.0
        for lab, u in units.items():
            if u <= 0 or lab not in inst_by_label:
                continue
            inst = inst_by_label[lab]
            flows, _, _, unit_scale = _flows(inst, curve, settle)
            for d, cf in flows:
                if prev_d < d <= pd:
                    dollars = u * (cf / unit_scale)
                    cash_arrived += dollars
                    idle_d = (pd - d).days
                    total_dollar_days += dollars * idle_d

        if k > 0:
            surplus *= (1 + reinvest) ** year_frac(pay_dates[k - 1], pd)
        avail = cash_arrived + surplus
        surplus = avail - amt
        if surplus > 0 and k < K - 1:
            next_pd = pay_dates[k + 1]
            total_dollar_days += surplus * (next_pd - pd).days

    weighted_avg_days = total_dollar_days / total_payments if total_payments > 0 else 0.0
    return {
        "total_dollar_days": total_dollar_days,
        "weighted_avg_days": weighted_avg_days,
    }
