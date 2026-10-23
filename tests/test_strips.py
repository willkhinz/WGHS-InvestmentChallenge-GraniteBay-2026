import datetime as dt
import numpy as np
import pytest

from lgm.curve import ZeroCurve, bootstrap
from lgm.data.strips import december_notes_universe, strips_universe
from lgm.data.treasury import par_curve
from lgm.dates import year_frac
from lgm.instruments import TreasuryStrip
from lgm.ladder import idle_cash_days, solve


def test_treasury_strip_flows_and_pricing():
    settle = dt.date(2026, 10, 20)
    mat = dt.date(2032, 11, 15)
    s = TreasuryStrip(cusip="9128337S3", maturity=mat, price=73.652, label="UST I-STRIPS Nov-2032")

    # Cash flows: exactly 100 face at maturity
    cfs = s.cashflows(settle)
    assert len(cfs) == 1
    assert cfs[0] == (mat, 100.0)

    # Cash flows after maturity are empty
    assert s.cashflows(dt.date(2033, 1, 1)) == []

    # Accrued interest on a zero-coupon bond is always 0
    assert s.accrued(settle) == 0.0

    # With price override, dirty and clean price match quoted price
    dummy_curve = ZeroCurve(settle, np.array([1.0, 10.0]), np.array([-0.05, -0.50]))
    assert s.dirty_price(dummy_curve) == 73.652
    assert s.clean_price(dummy_curve) == 73.652

    # YTM calculation: verify round-trip
    t = year_frac(settle, mat)
    y = s.ytm(73.652, settle)
    assert 100.0 / (1.0 + y / 2.0) ** (2.0 * t) == pytest.approx(73.652, abs=1e-5)

    # Without price override, prices directly off curve
    s_curve = TreasuryStrip(cusip="9128337S3", maturity=mat, price=None)
    assert s_curve.dirty_price(dummy_curve) == pytest.approx(100.0 * dummy_curve.df(t), abs=1e-6)


def test_matured_strip_does_not_use_stale_quote_or_past_curve_price():
    settle = dt.date(2026, 10, 20)
    curve = ZeroCurve(settle, np.array([1.0, 10.0]), np.array([-0.05, -0.50]))
    strip = TreasuryStrip("expired", dt.date(2025, 11, 15), price=99.0)
    assert strip.cashflows(settle) == []
    assert strip.dirty_price(curve) == strip.clean_price(curve) == strip.curve_price(curve) == 0.0
    with pytest.raises(ValueError, match="yield is undefined for a matured"):
        strip.ytm(99.0, settle)
    with pytest.raises(ValueError, match="duration is undefined for a matured"):
        strip.mod_duration(curve)
    with pytest.raises(ValueError, match="dirty price must be a finite positive"):
        strip.ytm(0.0, dt.date(2024, 1, 1))


def test_lp_synthetic_curve_exact_analytical_match():
    """On a flat 4% curve where each zero-coupon bond matures exactly on the payment date,
    the LP solution at 0% reinvestment must analytically buy exactly the payment face amount
    with zero surplus and cost sum(L_k * df_k)."""
    d0 = dt.date(2026, 1, 1)
    r = 0.04
    knots = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    log_df = -r * knots
    curve = ZeroCurve(d0, knots, log_df)

    pays = [(dt.date(2027, 1, 1), 50_000.0), (dt.date(2028, 1, 1), 50_000.0), (dt.date(2029, 1, 1), 50_000.0)]
    instruments = [
        TreasuryStrip(f"Z{k}", d, price=None, label=f"ZERO-{d.year}")
        for k, (d, _) in enumerate(pays)
    ]

    res = solve(instruments, pays, curve, reinvest=0.0)
    assert res.status == "optimal"

    # Analytical cost
    expected_cost = sum(amt * float(curve.df(year_frac(d0, d))) for d, amt in pays)
    assert res.cost == pytest.approx(expected_cost, rel=1e-6)

    # Units held: in ladder.py, units is face dollars (so 50,000 face)
    for inst in instruments:
        assert res.units[inst.label] == pytest.approx(50_000.0, rel=1e-5)

    # Surplus after every payment must be exactly 0
    for s in res.surplus:
        assert s == pytest.approx(0.0, abs=1e-6)


def test_idle_cash_days_analytical():
    """If $50,000 arrives 30 days before payment, weighted average idle days must be 30.0."""
    d0 = dt.date(2026, 1, 1)
    curve = ZeroCurve(d0, np.array([0.5, 1.0]), np.array([-0.02, -0.04]))
    pays = [(dt.date(2027, 1, 1), 50_000.0)]
    # Strip matures Dec 2, 2026 -> 30 days before Jan 1, 2027
    inst = [TreasuryStrip("Z1", dt.date(2026, 12, 2), price=None, label="Z1")]
    res = solve(inst, pays, curve, reinvest=0.0)
    idle = idle_cash_days(inst, res.units, pays, curve, reinvest=0.0)
    assert idle["weighted_avg_days"] == pytest.approx(30.0, abs=1e-5)


def test_strips_loader_and_oct20_curve_consistency():
    zc = bootstrap(par_curve("2026-10-20"))
    strips = strips_universe(use_market_quotes=True)
    assert len(strips) == 10

    # Maturities cover Nov 15 of 2032 through 2041
    years = [s.maturity.year for s in strips]
    assert years == list(range(2032, 2042))
    assert all(s.maturity.month == 11 and s.maturity.day == 15 for s in strips)

    # Market yields are all within 15 bps of the bootstrapped par curve zero rates
    for s in strips:
        t = year_frac(zc.date, s.maturity)
        curve_zero = float(zc.zero(t))
        mkt_yld = s.ytm(s.price, zc.date)
        spread_bps = abs(mkt_yld - curve_zero) * 10_000
        assert spread_bps < 15.0, f"{s.label}: spread {spread_bps:.1f} bps too large"


def test_december_note_loader():
    dec_notes = december_notes_universe(use_market_quotes=True)
    assert len(dec_notes) == 1
    n = dec_notes[0]
    assert n.cusip == "91282CPQ8"
    assert n.maturity == dt.date(2032, 12, 31)
    assert n.coupon == pytest.approx(0.03875, abs=1e-5)
    assert n.clean_quote == pytest.approx(93.980, abs=1e-3)


def test_ask_quotes_are_what_a_buyer_pays():
    mid = {s.cusip: s.price for s in strips_universe(use_market_quotes=True)}
    ask = {s.cusip: s.price for s in strips_universe(use_market_quotes=True, side="ask")}
    assert mid.keys() == ask.keys() and all(ask[c] > mid[c] for c in mid)
    # Public.com's retail half-spread on these STRIPS is about 1.5% of price
    assert all(0.005 < ask[c] / mid[c] - 1 < 0.03 for c in mid)
