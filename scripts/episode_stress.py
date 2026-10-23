"""Named historical episodes applied just after the January 2027 lock.

Usage: python scripts/episode_stress.py
Writes reports/episode_stress.csv.
"""
from __future__ import annotations

import dataclasses as dc
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import engine
from lgm.backtest import history_paths
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

OUT = Path(__file__).resolve().parents[1] / "reports"
CSV = OUT / "episode_stress.csv"
N_SIM = 20_000
SEED = 11
EPISODES = (
    ("2008 financial crisis", pd.Timestamp("2008-09-30")),
    ("2011 euro crisis", pd.Timestamp("2011-08-31")),
    ("2015-16 China and oil sell-off", pd.Timestamp("2015-08-31")),
    ("COVID", pd.Timestamp("2020-02-29")),
)
PATH_SETS = (
    ("History as it happened", False),
    ("History re-centred on BL expected returns", True),
)
# Model month 0 is November 2026. The first bad month is model month 3 (February 2027), so its
# calendar month is four months after the path start.
START_OFFSET_MONTHS = engine.M_2027 + 2
SPLICE_START = pd.Timestamp("2021-09-30")
SPLICE_END = pd.Timestamp("2022-12-31")


def episode_start(first_bad_month: pd.Timestamp) -> pd.Timestamp:
    """Path start that puts ``first_bad_month`` at model month 3."""
    return first_bad_month - pd.offsets.MonthEnd(START_OFFSET_MONTHS)


def build_inputs():
    """Core, beliefs, simulated scenarios and the IPS engine config, as report_numbers does."""
    core = build_core()
    w = np.asarray(core["w_bl"])
    er = np.array([g.expense_ratio for g in CORE])
    t = core["table"]
    p = esg_params(core["cal"], t["bl_geo_total"].values)
    sc = simulate(p, n=N_SIM, seed=SEED)
    st = dc.replace(IPS, region_weights=tuple(w))
    cfg = engine.EngineConfig(eq_er=tuple(er))
    return core, p, sc, st, cfg


def path_set(recentre: bool, core):
    target = core["table"]["bl_geo_total"].values if recentre else None
    return history_paths([g.history for g in CORE], recentre=target)


def main():
    core, p, sc, st, cfg = build_inputs()
    for label, recentre in PATH_SETS:
        hsc, starts = path_set(recentre, core)
        print(f"{label}: {len(starts)} paths, {starts[0].date()} to {starts[-1].date()}")
        for name, bad in EPISODES:
            start = episode_start(bad)
            status = "available" if start in starts else "NOT AVAILABLE"
            print(f"  {name}: start {start.date()} ({status})")


if __name__ == "__main__":
    main()
