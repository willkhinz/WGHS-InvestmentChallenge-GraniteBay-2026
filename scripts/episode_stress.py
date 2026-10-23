"""Named historical episodes applied just after the January 2027 lock.

Usage: python scripts/episode_stress.py
Writes reports/episode_stress.csv.
"""
from __future__ import annotations

import csv
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
FIELDS = (
    "path_set", "episode", "start", "first_bad_month", "available", "n_paths",
    "facility_jan2033", "contribution_85", "floor_2033", "funded_share",
    "facility_real_tw2027", "equity_cum_6y", "equity_worst_12m", "locked_share_2027",
    "note",
)


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


def splice_2022(sc, components=("equity", "rate", "fx")):
    """Replace model months 3-14 with actual Jan-Dec 2022 moves for specified components.
    
    components: tuple of any of "equity", "rate", "fx"
    """
    seg, starts = history_paths([g.history for g in CORE], start=SPLICE_START, end=SPLICE_END,
                                months=15)
    if len(starts) != 1 or starts[0] != SPLICE_START:
        raise ValueError(f"2022 splice needs one path at {SPLICE_START.date()}, got {starts}")
    if starts[0] + pd.offsets.MonthEnd(START_OFFSET_MONTHS) != pd.Timestamp("2022-01-31"):
        raise ValueError("2022 splice does not start four months before January 2022")
    eq = sc.eq_log.copy()
    beta = sc.beta.copy()
    fx = sc.fx_log.copy()
    if "equity" in components:
        eq[:, 3:15, :] = seg.eq_log[0, 3:15, :]
    if "rate" in components:
        for m in range(3, 15):
            beta[:, m + 1] = beta[:, m] + (seg.beta[0, m + 1] - seg.beta[0, m])
        beta[:, 15:] = sc.beta[:, 15:] + (beta[:, 15] - sc.beta[:, 15])[:, None, :]
    if "fx" in components:
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


def locked_share_2027(res, sc, cfg):
    """Locked share of ladder PV at Jan 2027 = lock_cost_2027 / total_ladder_pv_2027."""
    tau = engine.pay_tau(engine.M_2027)
    unit = engine.PMT * sc.df(engine.M_2027, np.maximum(tau, 0)) * (1 + engine.kappa(engine.M_2027, cfg, sc))
    total_pv = unit.sum(1)
    return res["lock_cost_2027"] / total_pv


def path_metrics(res, stats, i, sc=None, cfg=None):
    cum, worst = stats
    m = {
        "facility_jan2033": float(res["facility"][i]),
        "contribution_85": float(res["contribution"][i]),
        "floor_2033": float(res["floor_2033"][i]),
        "funded_share": float(res["funded"][i]),
        "facility_real_tw2027": float(res["facility_real_tw2027"][i]),
        "equity_cum_6y": float(cum[i]),
        "equity_worst_12m": float(worst[i]),
    }
    if sc is not None and cfg is not None:
        ls = locked_share_2027(res, sc, cfg)
        m["locked_share_2027"] = float(ls[i])
    return m


def distribution_metrics(res, stats, q, sc=None, cfg=None):
    cum, worst = stats
    m = {
        "facility_jan2033": float(np.percentile(res["facility"], q)),
        "contribution_85": float(np.percentile(res["contribution"], q)),
        "floor_2033": float(np.percentile(res["floor_2033"], q)),
        "funded_share": float(res["funded"].mean()),
        "facility_real_tw2027": float(np.percentile(res["facility_real_tw2027"], q)),
        "equity_cum_6y": float(np.percentile(cum, q)),
        "equity_worst_12m": float(np.percentile(worst, q)),
    }
    if sc is not None and cfg is not None:
        ls = locked_share_2027(res, sc, cfg)
        m["locked_share_2027"] = float(np.percentile(ls, q))
    return m


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


def write_csv(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "path_set": r["path_set"],
                "episode": r["episode"],
                "start": r["start"],
                "first_bad_month": r["first_bad_month"],
                "available": int(r["available"]),
                "n_paths": int(r["n_paths"]),
                "facility_jan2033": f"{r['facility_jan2033']:.1f}" if "facility_jan2033" in r else "",
                "contribution_85": f"{r['contribution_85']:.1f}" if "contribution_85" in r else "",
                "floor_2033": f"{r['floor_2033']:.1f}" if "floor_2033" in r else "",
                "funded_share": f"{r['funded_share']:.3f}" if "funded_share" in r else "",
                "facility_real_tw2027": f"{r['facility_real_tw2027']:.1f}" if "facility_real_tw2027" in r else "",
                "equity_cum_6y": f"{r['equity_cum_6y']:.6f}" if "equity_cum_6y" in r else "",
                "equity_worst_12m": f"{r['equity_worst_12m']:.6f}" if "equity_worst_12m" in r else "",
                "locked_share_2027": f"{r['locked_share_2027']:.4f}" if "locked_share_2027" in r else "",
                "note": r["note"],
            })
    print(f"wrote {CSV}")


def main():
    core, p, sc, st, cfg = build_inputs()
    w = np.asarray(core["w_bl"])
    sim_res = engine.run(st, sc, cfg)
    sim_stats = equity_stats(weighted_log_eq(sc, w))
    rows = [
        row("Simulated (20,000, seed 11)", "Median", n_paths=N_SIM,
            **distribution_metrics(sim_res, sim_stats, 50, sc, cfg)),
        row("Simulated (20,000, seed 11)", "5th percentile", n_paths=N_SIM,
            **distribution_metrics(sim_res, sim_stats, 5, sc, cfg)),
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
                            first_bad_month=bad.date().isoformat(),
                            **path_metrics(res, stats, i, hsc, cfg)))
        worst = int(np.argmin(res["facility"]))
        worst_bad = starts[worst] + pd.offsets.MonthEnd(START_OFFSET_MONTHS)
        rows.append(row(label, "Worst path", start=starts[worst].date().isoformat(),
                        first_bad_month=worst_bad.date().isoformat(),
                        **path_metrics(res, stats, worst, hsc, cfg),
                        note="lowest January 2033 facility among the 184 paths"))
    rows.append(row("History paths", "2022 stock-and-bond sell-off", first_bad_month="2022-01-31",
                    available=0, n_paths=0,
                    note="no full six-year path: the last available start is 2020-07-31"))
    spliced_all, seg = splice_2022(sc, components=("equity", "rate", "fx"))
    spliced_all_res = engine.run(st, spliced_all, cfg)
    spliced_all_stats = equity_stats(weighted_log_eq(spliced_all, w))
    rows.append(row("Simulated with 2022 spliced", "2022 sell-off, median (all)",
                    start=SPLICE_START.date().isoformat(), first_bad_month="2022-01-31",
                    n_paths=N_SIM,
                    **distribution_metrics(spliced_all_res, spliced_all_stats, 50, sc, cfg),
                    note="15-month segment 2021-09-30..2022-12-31: months 3-14 replaced with the "
                         "actual Jan-Dec 2022 equity, rate and FX moves; other simulated months "
                         "unchanged"))

    # Splice decomposition: equity-only, rate-only, FX-only
    unspliced_median_facility = float(np.percentile(sim_res["facility"], 50))
    for comp_name, components in [
        ("equity only", ("equity",)),
        ("rate only", ("rate",)),
        ("fx only", ("fx",)),
    ]:
        spliced_comp, _ = splice_2022(sc, components=components)
        spliced_comp_res = engine.run(st, spliced_comp, cfg)
        spliced_comp_stats = equity_stats(weighted_log_eq(spliced_comp, w))
        median_facility = float(np.percentile(spliced_comp_res["facility"], 50))
        median_floor = float(np.percentile(spliced_comp_res["floor_2033"], 50))
        median_real = float(np.percentile(spliced_comp_res["facility_real_tw2027"], 50))
        change = median_facility - unspliced_median_facility
        rows.append(row("Simulated with 2022 spliced", f"2022 sell-off, median ({comp_name})",
                        start=SPLICE_START.date().isoformat(), first_bad_month="2022-01-31",
                        n_paths=N_SIM,
                        facility_jan2033=median_facility,
                        contribution_85=float(np.percentile(spliced_comp_res["contribution"], 50)),
                        floor_2033=median_floor,
                        funded_share=float(spliced_comp_res["funded"].mean()),
                        facility_real_tw2027=median_real,
                        equity_cum_6y=float(np.percentile(spliced_comp_stats[0], 50)),
                        equity_worst_12m=float(np.percentile(spliced_comp_stats[1], 50)),
                        locked_share_2027=float(np.percentile(locked_share_2027(spliced_comp_res, sc, cfg), 50)),
                        note=f"15-month segment 2021-09-30..2022-12-31: months 3-14 replaced with "
                             f"actual Jan-Dec 2022 {comp_name} moves; other simulated months unchanged; "
                             f"facility change vs unspliced median: {change:+.1f}"))

    print(f"{'Path set':<45} {'Episode':<38} {'Start':<10} {'Facility':>10} {'Contrib':>10} "
          f"{'Floor':>10} {'Funded':>7} {'Real':>10} {'Equity':>8} {'Worst12':>8} {'Lock27':>7}")
    def fmt(r, key, spec):
        return format(r[key], spec) if key in r else "—"

    for r in rows:
        print(f"{r['path_set'][:44]:<45} {r['episode'][:37]:<38} {r['start']:<10} "
              f"{fmt(r, 'facility_jan2033', '>10,.0f')} {fmt(r, 'contribution_85', '>10,.0f')} "
              f"{fmt(r, 'floor_2033', '>10,.0f')} {fmt(r, 'funded_share', '>6.0%')} "
              f"{fmt(r, 'facility_real_tw2027', '>10,.0f')} {fmt(r, 'equity_cum_6y', '>+7.1%')} "
              f"{fmt(r, 'equity_worst_12m', '>+7.1%')} {fmt(r, 'locked_share_2027', '>7.2%')}")
    write_csv(rows)


if __name__ == "__main__":
    main()