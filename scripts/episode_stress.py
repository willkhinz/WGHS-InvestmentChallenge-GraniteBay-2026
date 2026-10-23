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


def splice_2022(sc):
    """Replace model months 3-14 with the actual Jan-Dec 2022 equity, rate and FX moves."""
    seg, starts = history_paths([g.history for g in CORE], start=SPLICE_START, end=SPLICE_END,
                                months=15)
    if len(starts) != 1 or starts[0] != SPLICE_START:
        raise ValueError(f"2022 splice needs one path at {SPLICE_START.date()}, got {starts}")
    if starts[0] + pd.offsets.MonthEnd(START_OFFSET_MONTHS) != pd.Timestamp("2022-01-31"):
        raise ValueError("2022 splice does not start four months before January 2022")
    eq = sc.eq_log.copy()
    eq[:, 3:15, :] = seg.eq_log[0, 3:15, :]
    beta = sc.beta.copy()
    for m in range(3, 15):
        beta[:, m + 1] = beta[:, m] + (seg.beta[0, m + 1] - seg.beta[0, m])
    beta[:, 15:] = sc.beta[:, 15:] + (beta[:, 15] - sc.beta[:, 15])[:, None, :]
    fx = sc.fx_log.copy()
    for m in range(3, 15):
        fx[:, m + 1] = fx[:, m] + (seg.fx_log[0, m + 1] - seg.fx_log[0, m])
    fx[:, 15:] = sc.fx_log[:, 15:] + (fx[:, 15] - sc.fx_log[:, 15])[:, None]
    return dc.replace(sc, eq_log=eq, beta=beta, fx_log=fx), seg


def weighted_log_eq(sc, w):
    """Core-weighted log equity return in each month of the six-year investment window."""
    return (sc.eq_log[:, engine.M_2027:engine.M_2033, :] * w).sum(2)


def equity_stats(log_eq):
    """Cumulative return and worst 12 months over Jan 2027-Dec 2032, per path."""
    cum = np.cumsum(log_eq, axis=1)
    rolling = cum[:, 11:] - np.concatenate([np.zeros((len(cum), 1)), cum[:, :-12]], axis=1)
    return np.expm1(cum[:, -1]), np.expm1(rolling.min(axis=1))


def path_metrics(res, stats, i):
    cum, worst = stats
    return {
        "facility_jan2033": float(res["facility"][i]),
        "contribution_85": float(res["contribution"][i]),
        "floor_2033": float(res["floor_2033"][i]),
        "funded_share": float(res["funded"][i]),
        "facility_real_tw2027": float(res["facility_real_tw2027"][i]),
        "equity_cum_6y": float(cum[i]),
        "equity_worst_12m": float(worst[i]),
    }


def distribution_metrics(res, stats, q):
    cum, worst = stats
    return {
        "facility_jan2033": float(np.percentile(res["facility"], q)),
        "contribution_85": float(np.percentile(res["contribution"], q)),
        "floor_2033": float(np.percentile(res["floor_2033"], q)),
        "funded_share": float(res["funded"].mean()),
        "facility_real_tw2027": float(np.percentile(res["facility_real_tw2027"], q)),
        "equity_cum_6y": float(np.percentile(cum, q)),
        "equity_worst_12m": float(np.percentile(worst, q)),
    }


def row(path_set_name, episode, start="", first_bad_month="", available=1, n_paths=1, note="", **metrics):
    return {
        "path_set": path_set_name,
        "episode": episode,
        "start": start,
        "first_bad_month": first_bad_month,
        "available": available,
        "n_paths": n_paths,
        **metrics,
        "note": note,
    }


def main():
    core, p, sc, st, cfg = build_inputs()
    w = np.asarray(core["w_bl"])
    sim_res = engine.run(st, sc, cfg)
    sim_stats = equity_stats(weighted_log_eq(sc, w))
    rows = [
        row("Simulated (20,000, seed 11)", "Median", n_paths=N_SIM,
            **distribution_metrics(sim_res, sim_stats, 50)),
        row("Simulated (20,000, seed 11)", "5th percentile", n_paths=N_SIM,
            **distribution_metrics(sim_res, sim_stats, 5)),
    ]
    for label, recentre in PATH_SETS:
        hsc, starts = path_set(recentre, core)
        res = engine.run(st, hsc, cfg)
        stats = equity_stats(weighted_log_eq(hsc, w))
        for name, bad in EPISODES:
            start = episode_start(bad)
            if start not in starts:
                rows.append(row(label, name, start=start.date().isoformat(),
                                first_bad_month=bad.date().isoformat(), available=0, n_paths=0,
                                note="start not available in this path set"))
                continue
            i = starts.index(start)
            rows.append(row(label, name, start=start.date().isoformat(),
                            first_bad_month=bad.date().isoformat(), **path_metrics(res, stats, i)))
        worst = int(np.argmin(res["facility"]))
        rows.append(row(label, "Worst path", start=starts[worst].date().isoformat(),
                        **path_metrics(res, stats, worst),
                        note="lowest January 2033 facility among the 184 paths"))
    rows.append(row("History paths", "2022 stock-and-bond sell-off", first_bad_month="2022-01-31",
                    available=0, n_paths=0,
                    note="no full six-year path: the last available start is 2020-07-31"))
    spliced, _ = splice_2022(sc)
    spliced_res = engine.run(st, spliced, cfg)
    spliced_stats = equity_stats(weighted_log_eq(spliced, w))
    rows.append(row("Simulated with 2022 spliced", "2022 sell-off, median", n_paths=N_SIM,
                    **distribution_metrics(spliced_res, spliced_stats, 50),
                    note="months 3-14 replaced with the actual Jan-Dec 2022 equity, rate and FX "
                         "moves; other simulated months unchanged"))

    print(f"{'Path set':<45} {'Episode':<33} {'Start':<10} {'Facility':>10} {'Contrib':>10} "
          f"{'Floor':>10} {'Funded':>7} {'Real':>10} {'Equity':>8} {'Worst12':>8}")
    for r in rows:
        print(f"{r['path_set'][:44]:<45} {r['episode'][:32]:<33} {r['start']:<10} "
              f"{r.get('facility_jan2033', 0):>10,.0f} {r.get('contribution_85', 0):>10,.0f} "
              f"{r.get('floor_2033', 0):>10,.0f} {r.get('funded_share', 0):>6.0%} "
              f"{r.get('facility_real_tw2027', 0):>10,.0f} {r.get('equity_cum_6y', 0):>+7.1%} "
              f"{r.get('equity_worst_12m', 0):>+7.1%}")


if __name__ == "__main__":
    main()
