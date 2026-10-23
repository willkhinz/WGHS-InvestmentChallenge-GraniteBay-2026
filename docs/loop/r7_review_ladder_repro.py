"""Reproducers for docs/loop/r7_review_ladder_findings.md.

Run with the worktree's src first:

    PYTHONPATH=<worktree>/src PY docs/loop/r7_review_ladder_repro.py

Each finding function prints one line: expected vs actual.
"""
from __future__ import annotations

import datetime as dt
import math

from lgm import ladder as L
from lgm.asof import CURVE_DATE
from lgm.curve import ZeroCurve, bootstrap
from lgm.data.treasury import par_curve
from lgm.instruments import TermFund, TreasuryBond, TreasuryStrip

CURVE = dt.date.fromisoformat(CURVE_DATE)


def _curve() -> ZeroCurve:
    return bootstrap(par_curve(CURVE_DATE))


def finding_1_strip_at_curve_date() -> None:
    """TreasuryStrip.curve_price/dirty_price guard uses maturity <= curve.date."""
    zc = _curve()
    strip = TreasuryStrip("REPRO", CURVE)
    quoted = TreasuryStrip("REPRO", CURVE, price=99.0)
    expected = 100.0 * float(zc.df(0.0))
    print(
        "finding_1_strip_at_curve_date: "
        f"expected curve_price={expected:.6f} (100*df(0)), actual={strip.curve_price(zc):.6f}; "
        f"expected quoted dirty=99.000000, actual={quoted.dirty_price(zc):.6f}"
    )


def finding_2_fund_growth_at_termination() -> None:
    """TermFund.growth_factor returns 0.0 for t == 0."""
    zc = _curve()
    fund = TermFund("IBTO", CURVE, ytm=0.04)
    print(
        "finding_2_fund_growth_at_termination: "
        f"expected growth_factor=1.000000, actual={fund.growth_factor(zc):.6f}"
    )


def finding_3_fund_settle_vs_curve_date() -> None:
    """TermFund.cashflows guards on settle but values at curve.date."""
    zc = _curve()
    fund = TermFund("IBTO", CURVE, ytm=0.04)
    settle = CURVE - dt.timedelta(days=30)
    flows, price, _, _ = L._flows(fund, zc, settle)
    print(
        "finding_3_fund_settle_vs_curve_date: "
        f"expected [] (termination {fund.termination} <= curve date {zc.date}, settle {settle}), actual={flows}; "
        f"build_matrix price={price:.6f}"
    )


def finding_4_premium_at_first_payment() -> None:
    """premium filters expired instruments but not payments already due."""
    zc = _curve()
    pays = L.payment_schedule()
    later = ZeroCurve(pays[0][0], zc.knots, zc.log_df)
    active = [inst for inst in L.wins_reserve_universe() if L._flows(inst, later, later.date)[0]]
    lp = L.solve(active, pays, later, 0.03)
    premium = L.premium(later, 0.03)
    try:
        L.premium(ZeroCurve(later.date.replace(year=2034), zc.knots, zc.log_df), 0.03)
    except ValueError as exc:
        next_year = f"ValueError({str(exc)!r})"
    else:
        next_year = "accepted"
    print(
        "finding_4_premium_at_first_payment: "
        f"expected ValueError (first payment {pays[0][0]} is due at settlement), "
        f"actual premium={premium!r} (LP infeasible={not math.isfinite(lp.cost)}, cost={lp.cost!r}); "
        f"n={len(pays)}, last={pays[-1][0]}; at 2034 {next_year}"
    )


def fine_checks() -> None:
    """Values cited in the fine lines of the findings doc."""
    zc = _curve()
    bond = TreasuryBond("REPRO", 0.04, dt.date(2033, 5, 15), label="REPRO")
    strip = TreasuryStrip("REPRO", dt.date(2025, 11, 15))
    leap = [d.isoformat() for d, _ in L.payment_schedule("2032-02-29", 5, 1000.0)]
    fund = TermFund("IBTM", dt.date(2032, 12, 15))
    try:
        L.solve([fund], L.payment_schedule(), ZeroCurve(dt.date(2033, 1, 1), zc.knots, zc.log_df))
    except ValueError as exc:
        expired = str(exc)
    else:
        expired = "accepted"
    try:
        L.solve([bond], L.payment_schedule(), zc, fixed={"REPRO": 1.0}, minimum={"REPRO": 2.0})
    except ValueError as exc:
        bounds = str(exc)
    else:
        bounds = "accepted"
    try:
        L.check_coverage([TreasuryStrip("REPRO", dt.date(2033, 1, 1), label="A")],
                         {"A": 100.0, "B": 1.0}, L.payment_schedule(), zc)
    except ValueError as exc:
        coverage = str(exc)
    else:
        coverage = "accepted"
    try:
        L.idle_cash_days([TreasuryStrip("REPRO", dt.date(2033, 1, 1), label="A")],
                         {"A": 100.0, "B": 1.0}, L.payment_schedule(), zc)
    except ValueError as exc:
        idle = str(exc)
    else:
        idle = "accepted"
    try:
        strip.ytm(99.0, CURVE)
    except ValueError as exc:
        strip_ytm = str(exc)
    else:
        strip_ytm = "accepted"
    print(
        "fine_checks: "
        f"bond dirty={bond.dirty_price(zc):.6f}, clean={bond.clean_price(zc):.6f}; "
        f"matured strip ytm={strip_ytm!r}; leap schedule={leap}; "
        f"fixed<minimum={bounds!r}; check_coverage extra label={coverage!r}; "
        f"idle_cash_days extra label={idle!r}; expired fund in solve={expired!r}"
    )


def main() -> None:
    finding_1_strip_at_curve_date()
    finding_2_fund_growth_at_termination()
    finding_3_fund_settle_vs_curve_date()
    finding_4_premium_at_first_payment()
    fine_checks()


if __name__ == "__main__":
    main()
