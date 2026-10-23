import dataclasses as dc

import numpy as np
import pandas as pd

from lgm import engine
from lgm.backtest import PROXY, history_paths
from lgm.data import yahoo
from lgm.growth.core import build_core
from lgm.growth.universe import CORE
from lgm.strategies import IPS

import scripts.episode_stress as ep


def _ips_inputs():
    core = build_core()
    st = dc.replace(IPS, region_weights=tuple(core["w_bl"]))
    cfg = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE))
    return core, st, cfg


def test_episode_starts_put_first_bad_month_at_model_month_3():
    tickers = [PROXY.get(g.history, g.history) for g in CORE]
    raw = np.log1p(yahoo.monthly_returns(tickers, start="2000-01-01"))
    sc, starts = ep.path_set(False, None)
    for _, bad in ep.EPISODES:
        start = ep.episode_start(bad)
        assert start + pd.offsets.MonthEnd(ep.START_OFFSET_MONTHS) == bad
        i = starts.index(start)
        assert np.allclose(sc.eq_log[i, engine.M_2027 + 1], raw.loc[bad].values)


def test_episode_paths_fund_every_payment():
    core, st, cfg = _ips_inputs()
    for recentre in (False, True):
        sc, starts = ep.path_set(recentre, core)
        res = engine.run(st, sc, cfg)
        assert res["funded"].all()
        for _, bad in ep.EPISODES:
            assert res["funded"][starts.index(ep.episode_start(bad))] == 1.0
        assert res["funded"][int(np.argmin(res["facility"]))] == 1.0


def test_2022_splice_starts_four_months_before_january_2022():
    seg, starts = history_paths([g.history for g in CORE], start=ep.SPLICE_START,
                                end=ep.SPLICE_END, months=15)
    assert starts == [ep.SPLICE_START]
    assert ep.SPLICE_START + pd.offsets.MonthEnd(ep.START_OFFSET_MONTHS) == pd.Timestamp("2022-01-31")
    assert seg.eq_log.shape == (1, 15, len(CORE))
