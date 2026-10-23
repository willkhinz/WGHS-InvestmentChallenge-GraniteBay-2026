import numpy as np
import pytest

from lgm import engine
from lgm.esg import simulate
from lgm.profiles import cs_team
from lgm.strategies import IPS, S1, S2, S9


@pytest.fixture(scope="module")
def setup():
    p = cs_team()
    return p, simulate(p, n=8000, seed=5)


def test_locked_strategies_always_fund(setup):
    _, sc = setup
    for st in (S9, IPS):
        assert engine.run(st, sc)["funded"].all()


def test_plans_v2_reproduction(setup):
    p, sc = setup
    s1, s2, s9 = (engine.summarize(engine.run(st, sc)) for st in (S1, S2, S9))
    assert s1["funded"] == pytest.approx(0.868, abs=0.015)
    assert s2["funded"] == pytest.approx(0.964, abs=0.015)
    assert s9["median"] == pytest.approx(193_500, rel=0.05)
    assert s9["p5"] == pytest.approx(137_900, rel=0.07)


def test_2031_floor_and_range(setup):
    p, sc = setup
    r = engine.run(S9, sc, snapshot_2031=True)
    c = engine.conditional_2031(S9, sc, r, p, n_inner=2000)
    assert c["floor"] == pytest.approx(114_600, rel=0.05)
    assert c["p10"] >= c["floor"]
    assert c["p10"] == pytest.approx(181_400, rel=0.06) and c["p90"] == pytest.approx(208_600, rel=0.06)


def test_band_materialises_generator_percentiles_once(setup):
    p, sc = setup
    r = engine.run(S9, sc, snapshot_2031=True)
    percentiles = (pc for pc in (5, 50, 95))
    out = engine.conditional_2031_band(S9, sc, r, p, k=3, n_inner=50, percentiles=percentiles)
    assert {"p5", "p50", "p95"} <= set(out)


def test_ips_contribution_rule(setup):
    _, sc = setup
    r = engine.run(IPS, sc)
    assert np.allclose(r["contribution"], 0.85 * r["facility"])
