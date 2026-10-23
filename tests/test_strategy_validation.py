"""Guard strategy and engine allocation inputs against silent capital misallocation."""
from types import SimpleNamespace

import numpy as np
import pytest

from lgm import engine
from lgm.strategies import IPS, Strategy


@pytest.mark.parametrize(("field", "value"), [
    ("lock_2027", 1.01),
    ("lock_2028", -0.01),
    ("lock_2031", np.nan),
    ("equity_share", True),
    ("equity_share", 10 ** 2000),
    ("band", np.inf),
    ("floor_share_2031", -0.1),
    ("floor_share", 1.1),
    ("contribution_share", False),
    ("equity_share_end", np.nan),
    ("ratchet_share", 1.1),
])
def test_strategy_fraction_controls_are_bounded(field, value):
    with pytest.raises(ValueError, match=field):
        Strategy("invalid", **{field: value})


@pytest.mark.parametrize("weights", [
    (), (0.5, 0.4), (0.5, -0.1, 0.6), (np.nan, 0.5, 0.5), (True, False),
    (10 ** 2000, 0.0), (1e308, 1e308),
])
def test_strategy_region_weights_must_be_finite_nonnegative_and_sum_to_one(weights):
    with pytest.raises(ValueError, match="region_weights"):
        Strategy("invalid", region_weights=weights)


@pytest.mark.parametrize("kwargs", [
    {"bond_vehicle": "BND"},
    {"bond_vehicle": []},
    {"floor_year": 2033},
    {"ratchet_trigger": -1.0},
    {"ratchet_trigger": np.inf},
    {"ratchet_trigger": 10 ** 2000},
])
def test_strategy_rejects_unsupported_discrete_and_ratchet_inputs(kwargs):
    with pytest.raises(ValueError):
        Strategy("invalid", **kwargs)


def test_strategy_normalizes_weights_to_a_float_tuple():
    st = Strategy("valid", region_weights=np.array([0.6, 0.3, 0.100000005]))
    assert st.region_weights == pytest.approx((0.6, 0.3, 0.100000005 / 1.000000005))
    assert sum(st.region_weights) == pytest.approx(1.0)


@pytest.mark.parametrize(("strategy", "cfg", "message"), [
    (Strategy("wrong equity count", region_weights=(0.5, 0.5)), engine.EngineConfig(), "region_weights"),
    (IPS, engine.EngineConfig(eq_er=(0.001, 0.002)), "cfg.eq_er"),
    (IPS, engine.EngineConfig(eq_er=(0.001, np.nan, 0.002)), "cfg.eq_er"),
    (IPS, engine.EngineConfig(eq_er=(0.001, True, 0.002)), "cfg.eq_er"),
    (IPS, engine.EngineConfig(eq_er=("0.001", "0.002", "0.003")), "cfg.eq_er"),
    (IPS, engine.EngineConfig(eq_er=(0.001, 12.0, 0.002)), "cfg.eq_er"),
])
def test_engine_rejects_allocation_vectors_not_matching_the_equity_universe(strategy, cfg, message):
    sc = SimpleNamespace(n=2, eq_log=np.zeros((2, engine.M_2033, 3)))
    with pytest.raises(ValueError, match=message):
        engine.run(strategy, sc, cfg)


def _valid_scenario():
    n, k, months = 2, 3, engine.M_2033
    return SimpleNamespace(
        n=n,
        m0=0,
        eq_log=np.zeros((n, months, k)),
        beta=np.zeros((n, months + 1, 3)),
        infl=np.zeros((n, months + 1)),
        fx_log=np.zeros((n, months + 1)),
        tw_cost_log=np.zeros((n, months + 1)),
        resid=np.zeros(len(engine.TAU_GRID)),
        rate_floor=-0.005,
    )


@pytest.mark.parametrize("field", ["beta", "infl", "fx_log", "tw_cost_log"])
def test_engine_rejects_short_scenario_state_paths(field):
    sc = _valid_scenario()
    setattr(sc, field, getattr(sc, field)[:, :-1])
    with pytest.raises(ValueError, match=f"scenarios\\.{field}"):
        engine.run(IPS, sc)


def test_engine_rejects_nonfinite_equity_log_returns():
    sc = _valid_scenario()
    sc.eq_log[0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="scenarios.eq_log"):
        engine.run(IPS, sc)


def test_engine_2d_eq_log_names_the_expected_3d_shape():
    sc = _valid_scenario()
    sc.eq_log = sc.eq_log[:, :, 0]
    with pytest.raises(ValueError, match=r"shape \(n, months, assets\)"):
        engine.run(IPS, sc)


def test_engine_rejects_boolean_scenario_paths():
    sc = _valid_scenario()
    sc.eq_log = sc.eq_log.astype(object)
    sc.eq_log[0, 0, 0] = True
    with pytest.raises(ValueError, match="scenarios.eq_log"):
        engine.run(IPS, sc)


def test_engine_rejects_string_rate_floor():
    sc = _valid_scenario()
    sc.rate_floor = "-0.005"
    with pytest.raises(ValueError, match="scenarios.rate_floor"):
        engine.run(IPS, sc)


def test_engine_rejects_wrong_continuation_state_type():
    with pytest.raises(ValueError, match="engine.State"):
        engine.run(IPS, _valid_scenario(), state={})


def test_engine_rejects_wrong_strategy_and_configuration_types():
    with pytest.raises(ValueError, match="strategies.Strategy"):
        engine.run(object(), _valid_scenario())
    with pytest.raises(ValueError, match="engine.EngineConfig"):
        engine.run(IPS, _valid_scenario(), cfg={})
    with pytest.raises(ValueError, match="snapshot_2031 must be boolean"):
        engine.run(IPS, _valid_scenario(), snapshot_2031="false")


def test_state_for_rejects_out_of_range_scenario_indices():
    state = engine.State(
        eq=np.zeros((2, 3)), vgit=np.zeros(2), ibtm_face=np.zeros(2), floor_face=np.zeros(2),
        cash=np.zeros(2), locked=np.zeros((2, engine.N_PAY)), costs=np.zeros(2),
    )
    with pytest.raises(ValueError, match="integer scenario index"):
        engine.state_for(state, -1, 4)


@pytest.mark.parametrize(("field", "value", "message"), [
    ("eq", np.full((2, 3), -1.0), "state.eq must be nonnegative"),
    ("locked", np.full((2, engine.N_PAY), 1.01), "state.locked values"),
    ("costs", np.array([0.0, np.inf]), "state.costs must be a finite"),
])
def test_engine_rejects_malformed_continuation_state(field, value, message):
    state = engine.State(
        eq=np.zeros((2, 3)), vgit=np.zeros(2), ibtm_face=np.zeros(2),
        floor_face=np.zeros(2), cash=np.zeros(2), locked=np.zeros((2, engine.N_PAY)),
        costs=np.zeros(2),
    )
    setattr(state, field, value)
    with pytest.raises(ValueError, match=message):
        engine.run(IPS, _valid_scenario(), state=state)


@pytest.mark.parametrize(("cfg", "message"), [
    (engine.EngineConfig(extra_tickets=-1), "extra_tickets"),
    (engine.EngineConfig(annual_cost=-1.0), "annual_cost"),
    (engine.EngineConfig(extra_ticket_min=np.nan), "extra_ticket_min"),
    (engine.EngineConfig(kappa0=-1.0), "kappa0"),
    (engine.EngineConfig(kappa_rate_slope=0.1), "kappa_rate_ref"),
    (engine.EngineConfig(commissions="false"), "commissions"),
    (engine.EngineConfig(deposits=((2, -1.0),)), "deposits\\[2\\]"),
    (engine.EngineConfig(deposits=((2, 1.0), (2, 2.0))), "duplicate month"),
    (engine.EngineConfig(deposits=((engine.M_2033 + 1, 1.0),)), "integer months"),
    (engine.EngineConfig(fund_groups=((0, 1),)), "partition the equity indices"),
    (engine.EngineConfig(fund_groups=((0, 1), (1, 2))), "partition the equity indices"),
    (engine.EngineConfig(fund_groups=((0, 1, True),)), "partition the equity indices"),
])
def test_engine_rejects_invalid_configuration_that_can_distort_capital(cfg, message):
    with pytest.raises(ValueError, match=message):
        engine.run(IPS, _valid_scenario(), cfg)
