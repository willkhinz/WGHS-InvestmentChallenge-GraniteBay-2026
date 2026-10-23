import datetime as dt

import numpy as np
import pytest

from lgm import ladder as L
from lgm.curve import ParCurve, ZeroCurve, bootstrap
from lgm.data.treasury import par_curve
from lgm.instruments import PLANS_V2_BONDS, TermFund, TreasuryBond, ibonds_fund


@pytest.fixture(scope="module")
def zc():
    return bootstrap(par_curve("2026-10-20"))


def test_bootstrap_reprices_par_bonds(zc):
    """A bond paying the par yield as coupon must price at 100 on its own curve."""
    par = par_curve("2026-10-20")
    for t in [2, 5, 10, 20, 30]:
        c = float(par.par_at(t))
        mat = dt.date(2026 + t, 10, 20)
        b = TreasuryBond("x", c, mat)
        assert b.dirty_price(zc) == pytest.approx(100.0, abs=0.02)


def test_matured_treasury_bond_has_no_future_cashflows(zc):
    bond = TreasuryBond("expired", 0.05, dt.date(2025, 11, 15))
    assert bond.cashflows(zc.date) == []
    assert bond.accrued(zc.date) == 0.0
    assert bond.dirty_price(zc) == 0.0
    quoted = TreasuryBond("expired-quoted", 0.05, dt.date(2025, 11, 15), clean_quote=99.0)
    assert quoted.clean_price(zc) == quoted.dirty_price(zc) == 0.0
    with pytest.raises(ValueError, match="yield is undefined for a matured"):
        bond.ytm(100.0, zc.date)
    with pytest.raises(ValueError, match="duration is undefined for a matured"):
        bond.mod_duration(zc)


def test_matured_term_fund_is_not_treated_as_future_cashflow(zc):
    fund = TermFund("OLD", dt.date(2025, 12, 15))
    assert fund.growth_factor(zc) == 0.0
    assert fund.cashflows(zc.date, zc) == []
    with pytest.raises(ValueError, match="no future cash flows"):
        L.build_matrix([fund], L.payment_schedule(), zc, 0.03)


def test_term_fund_with_settle_before_curve_date_still_has_no_flow_at_termination(zc):
    fund = TermFund("AT-CURVE", zc.date)
    settle = zc.date - dt.timedelta(days=30)
    assert fund.cashflows(settle, zc) == []


def test_future_premium_skips_expired_candidates(zc):
    future_curve = ZeroCurve(dt.date(2031, 1, 1), zc.knots, zc.log_df)
    candidates = [TermFund("OLD", dt.date(2030, 12, 15)), *L.wins_reserve_universe()]
    premium = L.premium(future_curve, instruments=candidates)
    assert np.isfinite(premium)
    with pytest.raises(ValueError, match="at least one instrument with future cash flows"):
        L.premium(future_curve, instruments=[TermFund("OLD", dt.date(2030, 12, 15))])


def test_official_curves_match_documents():
    oct16 = par_curve("2026-10-16")
    for t, y in {5: 4.89, 7: 4.98, 10: 5.09, 20: 5.47}.items():
        assert float(oct16.par_at(t)) * 100 == pytest.approx(y, abs=1e-9)
    sep28 = par_curve("2026-09-28")
    for t, y in {2: 4.92, 5: 5.06, 7: 5.15, 10: 5.24, 20: 5.60, 30: 5.56}.items():
        assert float(sep28.par_at(t)) * 100 == pytest.approx(y, abs=1e-9)


def test_curve_objects_reject_malformed_tenors_and_knots():
    with pytest.raises(ValueError, match="increasing positive tenors"):
        ParCurve(dt.date(2026, 1, 1), np.array([1.0, 1.0]), np.array([0.04, 0.05]))
    with pytest.raises(ValueError, match="increasing positive tenors"):
        ParCurve(dt.date(2026, 1, 1), np.array([1.0, 2.0]), np.array([0.04, np.nan]))
    with pytest.raises(ValueError, match="increasing nonnegative knots"):
        ZeroCurve(dt.date(2026, 1, 1), np.array([1.0, 1.0]), np.array([-0.04, -0.05]))


def test_curve_maturity_inputs_reject_past_and_nonfinite_values(zc):
    with pytest.raises(ValueError, match="par maturity"):
        par_curve("2026-10-20").par_at(-0.1)
    for curve_call in (lambda: zc.df(-0.1), lambda: zc.zero(-0.1), lambda: zc.df(np.nan)):
        with pytest.raises(ValueError, match="maturity"):
            curve_call()


@pytest.mark.parametrize("max_t", [0, 0.49, np.nan, np.inf, True])
def test_bootstrap_rejects_invalid_horizons(max_t):
    with pytest.raises(ValueError, match="max_t must be finite and at least 0.5"):
        bootstrap(par_curve("2026-10-20"), max_t=max_t)


def test_guide_zero_coupon_cost_oct16():
    z = bootstrap(par_curve("2026-10-16"))
    cost = sum(50_000 * float(z.df(t)) for t in range(6, 16))
    assert cost == pytest.approx(295_584, rel=0.001)   # guide Step 4C


def test_lp_ladder_meets_every_payment(zc):
    universe = [ibonds_fund(t) for t in ["IBTM", "IBTO", "IBTP", "IBTQ", "IBTR"]] + PLANS_V2_BONDS
    res = L.solve(universe, L.payment_schedule(), zc, reinvest=0.03)
    assert res.status == "optimal"
    assert min(res.surplus) >= -1e-6
    z27 = ZeroCurve(dt.date(2027, 1, 1), zc.knots, zc.log_df)
    assert L.solve(universe, L.payment_schedule(), z27, 0.03).cost == pytest.approx(300_100, rel=0.003)  # Plans v2


def test_plans_v2_nine_rung_ladder_covers_ten_payments(zc):
    universe = [ibonds_fund(t) for t in ["IBTO", "IBTP", "IBTQ", "IBTR"]] + PLANS_V2_BONDS
    p2 = {"IBTO": 20400, "IBTP": 27300, "IBTQ": 25900, "IBTR": 24500, "UST 5.000% May-2037": 40600,
          "UST 4.500% May-2038": 40500, "UST 4.375% Nov-2039": 41100, "UST 4.250% Nov-2040": 42000,
          "UST 3.125% Nov-2041": 37700}
    surplus = L.check_coverage(universe, p2, L.payment_schedule(), zc, 0.03)
    assert min(surplus) > 0          # coupons collected 2027-2032 fund the 2033 payment


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"n": 0}, "n must be a positive integer"),
    ({"n": True}, "n must be a positive integer"),
    ({"amount": 0}, "amount must be a finite positive"),
    ({"amount": np.nan}, "amount must be a finite positive"),
])
def test_payment_schedule_rejects_invalid_count_or_amount(kwargs, message):
    with pytest.raises(ValueError, match=message):
        L.payment_schedule(**kwargs)


def test_payment_schedule_clamps_leap_day_anniversaries():
    payments = L.payment_schedule(first="2032-02-29", n=2, amount=1_000)
    assert payments == [(dt.date(2032, 2, 29), 1_000), (dt.date(2033, 2, 28), 1_000)]


def test_solver_accepts_one_shot_payment_generators(zc):
    payments = L.payment_schedule(n=2)
    result = L.solve([ibonds_fund("IBTM")], (p for p in payments), zc)
    assert result.status == "optimal"
    assert min(result.surplus) >= -1e-6


def test_solver_rejects_unsorted_payments_and_invalid_reinvestment(zc):
    payments = L.payment_schedule(n=2)
    with pytest.raises(ValueError, match="strictly increasing"):
        L.solve([ibonds_fund("IBTO")], payments[::-1], zc)
    with pytest.raises(ValueError, match="greater than -100%"):
        L.solve([ibonds_fund("IBTO")], payments, zc, reinvest=-1.0)


def test_solver_rejects_duplicate_instrument_labels(zc):
    bonds = [
        TreasuryBond("one", 0.05, dt.date(2040, 1, 1), label="duplicate"),
        TreasuryBond("two", 0.04, dt.date(2041, 1, 1), label="duplicate"),
    ]
    with pytest.raises(ValueError, match="labels must be unique"):
        L.solve(bonds, L.payment_schedule(), zc)


def test_solver_validates_constraint_labels_and_precedence(zc):
    instruments = [ibonds_fund(t) for t in ("IBTM", "IBTO", "IBTP", "IBTQ", "IBTR")] + PLANS_V2_BONDS
    payments = L.payment_schedule()
    with pytest.raises(ValueError, match="unknown instrument label"):
        L.solve(instruments, payments, zc, fixed={"missing": 100})
    with pytest.raises(ValueError, match="below its minimum"):
        L.solve(instruments, payments, zc, fixed={"IBTO": 1_000_000}, minimum={"IBTO": 1_000_001})

    fixed = L.solve(instruments, payments, zc, fixed={"IBTO": 1_000_000}, minimum={"IBTO": 500_000})
    assert fixed.status == "optimal"
    assert fixed.holdings["IBTO"] == pytest.approx(1_000_000)
