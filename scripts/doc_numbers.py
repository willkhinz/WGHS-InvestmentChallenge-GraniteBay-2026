"""Check that the figures docs/MODEL.md and docs/VALIDATION.md quote match the reports they come from.

Usage: python scripts/doc_numbers.py [--fix]
Each check reads one figure from a committed report, formats it the way the docs write it, and looks
for that text in the doc. A model change that moves a number then fails tests/test_doc_numbers.py
until the doc is updated, instead of leaving a stale figure behind. Run scripts/run_all.py first.
Exit status 1 if any figure is missing. With --fix, each missing figure whose old version (the same
text with any numbers) appears exactly once in its doc is rewritten in place; the rest are listed.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "reports"


def k(x: float) -> str:
    """$197.6k style; a negative is -$0.2k, never $-0.2k."""
    return ("-" if x < 0 else "") + f"${abs(x) / 1000:,.1f}k"


def rng(a: float, b: float) -> str:
    return f"{k(a)}-{k(b)}"


def hedge_sentence() -> str:
    """The FX hedging sentence in docs/MODEL.md's USD/TWD bullet, from reports/fx_hedge_frontier.csv."""
    hf = pd.read_csv(R / "fx_hedge_frontier.csv").set_index(["belief", "hedge_ratio"])
    rw, fw = hf.loc["random walk (headline)"], hf.loc["forward unbiased"]
    best = fw.real_p5.idxmax()
    return (f"Partial hedges (`scripts/fx_hedge_frontier.py`, a share of the median facility sold forward in\n"
            f"  January 2027): on the random walk every hedge lowers the real 5th percentile as well as the median\n"
            f"  (fully hedged {k(rw.loc[1.0, 'real_p5'])} and {k(rw.loc[1.0, 'real_median'])} against "
            f"{k(rw.loc[0.0, 'real_p5'])} and {k(rw.loc[0.0, 'real_median'])}). Only if the forward is an\n"
            f"  unbiased forecast does hedging pay, and then modestly: the median is unchanged within "
            f"{k(fw.real_median.max() - fw.real_median.min())}\n"
            f"  and the 5th percentile rises from {k(fw.loc[0.0, 'real_p5'])} to at most {k(fw.real_p5.max())} "
            f"(at {best:.0%} hedged). Most of the\n"
            f"  real risk is the facility's own dollar value, which no currency hedge removes.")


def corr_shrink_sentence() -> str:
    """The out-of-sample shrinkage sentence in docs/MODEL.md's calibration notes, from reports/corr_shrink_oos.csv."""
    d = pd.read_csv(R / "corr_shrink_oos.csv")
    z, m = (d[d.candidate == c].set_index(["funds", "horizon_m"]) for c in
            ("zero target, LW intensity", "mean target, LW intensity for zero"))
    n = len(z)
    def count(better) -> str:
        hits = int(better.sum())
        return "all " + ("four" if n == 4 else str(n)) if hits == n else f"{hits} of {n}"
    a, b = z.loc[(9, 36)], m.loc[(9, 36)]
    return (f"scored on the next three years, the zero target misjudged the market's volatility by "
            f"{a.market_vol_bias:+.1%} on average against {b.market_vol_bias:+.1%} for the average target, and "
            f"understated the core's active risk by {-a.active_risk_bias:.0%} against {-b.active_risk_bias:.0%}. "
            f"It was closer on the market's volatility in {count(z.market_vol_bias.abs() < m.market_vol_bias.abs())} "
            f"tests (7 or 9 funds, 3 or 6 years), on active risk in "
            f"{count(z.active_risk_bias.abs() < m.active_risk_bias.abs())}, and its minimum-variance portfolio was "
            f"calmer in {count(z.min_variance_vol < m.min_variance_vol)}")


def taiwan_equity_sentence() -> str:
    """The cost-growth-vs-stocks sentence in docs/MODEL.md's Taiwan bullet, from reports/taiwan_fx_corr.csv."""
    t = pd.read_csv(R / "taiwan_fx_corr.csv").set_index("horizon_m")
    short = t.loc[[1, 3, 12, 24], "history_corr_equity"]
    return (f"Against US stocks, cost growth has moved with them over 1 to 24 months ({short.min():+.2f} to "
            f"{short.max():+.2f}) and against them over 72 months ({t.loc[72, 'history_corr_equity']:+.2f}), but that "
            f"last figure rests on {int(t.loc[72, 'independent_windows'])} independent windows; the model's "
            f"{t.model_corr_equity.min():+.2f} to {t.model_corr_equity.max():+.2f} sits inside the range.")


def decision_rows() -> list[str]:
    """The 'Decisions for the client' table in docs/MODEL.md: what the evidence says on each choice the
    model leaves open."""
    d = lambda x: ("+" if x >= 0 else "-") + k(abs(x))
    pr = pd.read_csv(R / "policy_robust.csv")
    b = pr[pr["shift"] == "base"].set_index("name")
    ips, alt = b.loc["IPS"], b.loc["P2361"]
    cs = json.loads((R / "policy_study.json").read_text())["contribution_share"]
    hf = pd.read_csv(R / "fx_hedge_frontier.csv").set_index(["belief", "hedge_ratio"])
    fw = hf.loc["forward unbiased"]
    td = pd.read_csv(R / "taiwan_drift_study.csv").pivot(index="origins", columns="rule", values="rmse")
    fx = pd.read_csv(R / "fx_variants.csv").set_index("variant")
    sat = pd.read_csv(R / "satellite_scoring.csv").set_index(["beliefs", "commissions", "candidate"])
    s20 = sat.loc[("Black-Litterman posterior", "$25 (WInS)", "Core + 20% satellite"), "median_vs_core"]
    s20f = sat.loc[("Black-Litterman posterior", "none", "Core + 20% satellite"), "median_vs_core"]
    sr = pd.read_csv(R / "strips_reserve.csv").set_index(["universe", "reinvestment_rate"])
    sx, w3, w0 = sr.loc[("STRIPS (ask quotes)", 0.0)], sr.loc[("WInS universe", 0.03)], sr.loc[("WInS universe", 0.0)]
    return [
        f"| Growth mix and 2031 floor | {alt.equity_share:.0%} equity with a {alt.floor_share:.0%} floor instead of the IPS's "
        f"{ips.equity_share:.0%} and {ips.floor_share:.0%}: median {d(alt['median'] - ips['median'])}, 5th percentile "
        f"{d(alt.p5 - ips.p5)}, a 2031 floor worth {k(alt.secured_2031_median - ips.secured_2031_median)} more at maturity; certainty "
        f"equivalents within {k(abs(alt.ce_gamma4 - ips.ce_gamma4))} at risk aversion 4 | How much the co-sponsors need "
        f"promised in 2031 | Policy study |",
        "| Contribution share | 75%, 85% and 95% give typical contributions of "
        + ", ".join(f"${c['contribution_median'] / 1000:.0f}k" for c in cs) + "; Laura keeps "
        + ", ".join(f"${c['kept_median'] / 1000:.0f}k" for c in cs) + " | Preference | Policy study |",
        f"| Hedge USD/TWD | On the random walk every hedge lowers the real 5th percentile and median; if the forward "
        f"were unbiased, at most {d(fw.real_p5.max() - fw.loc[0.0, 'real_p5'])} on the 5th percentile | Evidence says do not "
        f"hedge | USD/TWD |",
        f"| Taiwan building-cost drift | The long-run average forecast six-year cost growth better in real time "
        f"(RMSE {td.loc['all', 'expanding']:.3f} vs {td.loc['all', 'trailing_10y']:.3f}); the ten-year drift would mean "
        f"{d(fx.loc['random_walk_tw_drift_10y', 'real_median'] - fx.loc['random_walk', 'real_median'])} of real median | "
        f"Evidence supports the long-run average | Taiwan building costs |",
        f"| Stock satellite | {d(s20)} median at 20% with WInS commissions, {d(s20f)} without | A values choice, "
        f"not a return one | Part 2b |",
        f"| Reserve outside WInS | STRIPS need no reinvestment assumption and, at the retail ask, cost about what the "
        f"WInS ladder costs assuming 3% ({sx.cost_over_zero / sx.zero_coupon_value:+.2%} vs "
        f"{w3.cost_over_zero / w3.zero_coupon_value:+.2%} over zero-coupon value): {k(w0.cost - sx.cost)} cheaper than "
        f"making the WInS ladder certain, {d(sx.median_facility - w0.median_facility)} of median | Only if WInS rules do "
        f"not bind | `scripts/strips_reserve.py` |",
    ]


def sensitivity_rows() -> list[str]:
    """The 'What the numbers rest on' table in docs/MODEL.md: each assumption, the alternative tried,
    and what it does to the IPS (headline median, 5th percentile, or real median where that is the point)."""
    rn = json.loads((R / "report_numbers.json").read_text())
    plan, st, sl = rn["plan"], rn["stress"], rn["sleeves"]
    d = lambda x: ("+" if x >= 0 else "-") + (k(abs(x)) if abs(x) >= 1000 else f"${abs(x):,.0f}")
    fx = pd.read_csv(R / "fx_variants.csv").set_index("variant")
    rp = json.loads((R / "rate_path_scenario.json").read_text())
    sr = pd.read_csv(R / "stock_rate_corr.csv")
    sr = sr[sr.strategy.str.startswith("IPS")].set_index("variant")
    lp = pd.read_csv(R / "ladder_premium.csv")
    lp = lp[(lp.kind == "score") & lp.strategy.str.startswith("IPS")].set_index("variant")
    sat = pd.read_csv(R / "satellite_scoring.csv").set_index(["beliefs", "commissions", "candidate"])
    sat20 = sat.loc[("Black-Litterman posterior", "$25 (WInS)", "Core + 20% satellite"), "median_vs_core"]
    eqm = sl["equilibrium|wins_commissions|Black-Litterman core"]["median"] - plan["median"]
    pr = pd.read_csv(R / "policy_robust.csv")
    pr = pr[pr.name == "IPS"].set_index("shift")
    cs = pd.read_csv(R / "corr_shrink_ips.csv").set_index("target")
    dv = lambda shift, col="median": d(pr.loc[shift, col] - pr.loc["base", col])
    import yaml

    us = np.array([f["us"] for f in yaml.safe_load((ROOT / "config" / "cma.yaml").read_text())["firms"].values()])
    pts = lambda x: f"{x * 100:+.1f}".replace("+-", "-")
    tw = yaml.safe_load((ROOT / "config" / "taiwan.yaml").read_text())["fitted_monthly"]["drifts"]
    kappa0 = json.loads((R / "report_numbers.json").read_text())["stress"]["reserve_certain_at_0pct_reinvestment"]["ladder_premium_at_3pct"]
    return [
        f"| Equity forecasts | 13-firm median | lowest / highest firm ({pts(us.min() - np.median(us))} / {pts(us.max() - np.median(us))} points) | "
        f"{dv('eq_cma_lowest')} / {dv('eq_cma_highest')} median |",
        f"| Equity volatility | history since 2005 | x0.8 / x1.2 | {dv('eq_vol_0.8', 'p5')} / {dv('eq_vol_1.2', 'p5')} 5th pct |",
        f"| Equity correlations | shrunk toward zero | toward their average | {d(cs.loc['mean', 'median'] - cs.loc['zero', 'median'])} median, "
        f"{d(cs.loc['mean', 'p5'] - cs.loc['zero', 'p5'])} 5th pct |",
        f"| Rates at the January 2027 lock | as today | 0.75 points lower / higher | "
        f"{d(st['rates_minus_75bp_at_lock']['median'] - plan['median'])} / {d(st['rates_plus_75bp_at_lock']['median'] - plan['median'])} median |",
        f"| Cash awaiting a ladder payment | earns 3% | earns 0% (WInS pays none) | "
        f"{d(st['reserve_certain_at_0pct_reinvestment']['median_change'])} median |",
        f"| Expected rate path | unchanged | forwards less Kim-Wright term premium | "
        f"{d(rp['kim_wright']['median'] - rp['unchanged']['median'])} median |",
        f"| Equity views | Black-Litterman posterior | equilibrium (views wrong) | {d(eqm)} median |",
        f"| Stock-rate correlation | {sr.loc['today (2017-08..2026)', 'model_corr_month1']:+.2f} (2017-2026) | "
        f"2000-2021 regime ({sr.loc['2000..2021', 'model_corr_month1']:+.2f}) | "
        f"{d(sr.loc['2000..2021', 'median_vs_today'])} median, {d(sr.loc['2000..2021', 'p5_vs_today'])} 5th pct |",
        f"| Ladder premium | constant {kappa0:.1%} | moves with rates | {d(lp.loc['rate slope', 'median_vs_engine'])} median, "
        f"{d(lp.loc['rate slope', 'p5_vs_engine'])} 5th pct |",
        f"| Stock satellite | none | 20% of equity, $25 trades | {d(sat20)} median |",
        f"| USD/TWD drift | none (random walk) | today's forward ({fx.loc['forward_latest', 'fx_drift']:.2%} a year) | "
        f"{d(fx.loc['forward_latest', 'real_median'] - fx.loc['random_walk', 'real_median'])} real median |",
        f"| Taiwan building-cost drift | {tw['full_sample_35y']:.2%} (1991-2026) | {tw['last_10y']:.2%} (last ten years) | "
        f"{d(fx.loc['random_walk_tw_drift_10y', 'real_median'] - fx.loc['random_walk', 'real_median'])} real median |",
    ]


def episodes_bullet() -> str:
    """The named-crises bullet in docs/VALIDATION.md section 7, from reports/episode_stress.csv."""
    e = pd.read_csv(R / "episode_stress.csv")
    asit = e[e.path_set == "History as it happened"].set_index("episode")
    sim = e[e.path_set.str.startswith("Simulated (")].set_index("episode")
    spl = e[e.path_set.str.startswith("Simulated with 2022")].set_index("episode")
    named = ["2008 financial crisis", "2011 euro crisis", "2015-16 China and oil sell-off", "COVID"]
    fac = [asit.loc[n, "facility_jan2033"] for n in named]
    med, p5 = sim.loc["Median", "facility_jan2033"], sim.loc["5th percentile", "facility_jan2033"]
    w = asit.loc["Worst path"]
    n_paths = re.search(r"among the (\d+) paths", w.note).group(1)
    funds = (asit.loc[named + ["Worst path"], "funded_share"] == 1).all()
    s22 = {c: spl.loc[f"2022 sell-off, median ({c})", "facility_jan2033"] for c in ("all", "rate only", "equity only")}
    return (f"- **Named crises just after the lock:** 2008, 2011, 2015-16 and COVID, each started so that its\n"
            f"  first bad month falls just after the January 2027 lock, "
            f"{'fund every payment' if funds else 'do not all fund every payment'}\n"
            f"  (`scripts/episode_stress.py`). As it happened, their facilities are {k(fac[0])}, {k(fac[1])},\n"
            f"  {k(fac[2])} and {k(fac[3])}, {'all above' if min(fac) > med else 'not all above'} the "
            f"simulated median. The worst of the {n_paths} paths, from\n"
            f"  {pd.Timestamp(w.start).strftime('%B %Y')}, gives {k(w.facility_jan2033)} against the simulated "
            f"5th percentile of {k(p5)}: rates had\n"
            f"  already fallen by the lock (5-year zero rate {w.zero5_jan2027:.2%} against "
            f"{sim.loc['Median', 'zero5_jan2027']:.2%} on the median path), so\n"
            f"  the first deposit locks only {w.locked_share_2027:.1%} of the ladder. Splicing 2022's first "
            f"twelve months into the\n"
            f"  simulation lifts the median facility to {k(s22['all'])}: the rate rise alone adds "
            f"{k(s22['rate only'] - med)} and the stock\n"
            f"  fall alone costs {k(med - s22['equity only'])} (`reports/episode_stress.csv`).")



def checks() -> list[tuple[str, str, str]]:
    """(doc, what, text that must appear)."""
    rn = json.loads((R / "report_numbers.json").read_text())
    ps = json.loads((R / "policy_study.json").read_text())
    plan, stress, q = rn["plan"], rn["stress"], rn["quotes_2031"]["median"]
    sl = rn["sleeves"]
    fx = pd.read_csv(R / "fx_variants.csv").set_index("variant")
    out = [
        ("MODEL", "rate stress, base to -75bp", f"the IPS median falls from\n{k(plan['median'])} to "
                                              f"{k(stress['rates_minus_75bp_at_lock']['median'])}"),
        ("MODEL", "rate stress, +75bp", f"0.75 points higher: {k(stress['rates_plus_75bp_at_lock']['median'])}"),
        ("MODEL", "3-fund sleeve medians",
         f"| VTI/VEA/VWO 60/30/10 (3 funds) | {k(sl['bl|wins_commissions|VTI/VEA/VWO 60/30/10']['median'])} | "
         f"{k(sl['bl|no_commissions|VTI/VEA/VWO 60/30/10']['median'])} | "
         f"{k(sl['equilibrium|wins_commissions|VTI/VEA/VWO 60/30/10']['median'])} |"),
        ("MODEL", "BL core medians",
         f"| Black-Litterman core (9 funds) | {k(sl['bl|wins_commissions|Black-Litterman core']['median'])} | "
         f"{k(sl['bl|no_commissions|Black-Litterman core']['median'])} | "
         f"{k(sl['equilibrium|wins_commissions|Black-Litterman core']['median'])} |"),
        ("MODEL", "secured in 2031 (typical)", f"above the {k(q['guaranteed_contribution'])}"),
        ("MODEL", "10-90 contribution range", f"| Model 10th-90th percentile (historically ~98% of outcomes) | "
                                             f"{rng(*q['contribution_range'])} |"),
        ("MODEL", "calibrated 20-80 contribution range", f"| 20th-80th percentile (historically ~80% of outcomes) | "
                                                        f"{rng(*q['contribution_range_calibrated'])} |"),
        ("MODEL", "reverse stress, worst 1% mean", f"average a {k(ps['reverse_stress']['worst_1pct']['facility_mean'])} facility"),
        ("MODEL", "real median if the forward is right", f"the real median would be {k(fx.loc['forward_latest', 'real_median'])} "
                                                       f"instead of {k(plan['real_median'])}"),
        ("MODEL", "real median, loop summary", f"(real median $156.8k -> {k(plan['real_median'])})"),
    ]
    views = sl['bl|no_commissions|Black-Litterman core']['median'] - sl['bl|no_commissions|VTI/VEA/VWO 60/30/10']['median']
    trail = sl['bl|wins_commissions|VTI/VEA/VWO 60/30/10']['median'] - sl['bl|wins_commissions|Black-Litterman core']['median']
    out.append(("MODEL", "core vs 3 funds",
                f"The core's views are worth about {k(views)} before commissions. Its six extra funds cost about "
                f"{k(views + trail)} in\nWInS commissions, so with $25 trades it trails the 3-fund portfolio by {k(trail)}. "
                f"So the core is a\nrisk-control choice, not a return engine: it holds technology and China+Taiwan below "
                f"the market's\nshare for about {trail / plan['median']:.1%} of the median."))
    for row in ps["floor_frontier"]:
        f = row["floor_share"]
        if abs(f - 0.2) < 1e-9:
            continue                     # the doc's table shows the 0, 40, 60, 80 and 100% floors
        label = f"{f:.0%}" + (" (IPS)" if abs(f - 0.6) < 1e-9 else "")
        lo, hi = row["range_2031_typical"]
        range_txt = k(lo) if lo == hi else rng(lo, hi)
        secured = "$0" if row["secured_2031_typical"] == 0 else k(row["secured_2031_typical"])
        out.append(("MODEL", f"floor frontier {label}",
                    f"| {label} | {k(row['median'])} | {k(row['p5'])} | {k(row['p95'])} | {secured} | {range_txt} |"))
    lo_b, hi_b = q["floor_dec_2032_band"]
    out.append(("MODEL", "2031 floor band", f"floor the IPS buys varies from {k(lo_b)} to {k(hi_b)} with that month's rates"))
    ff = {round(r["floor_share"], 2): r for r in ps["floor_frontier"]}
    ips_ff, f80 = ff[0.6], ff[0.8]
    gap_best = max(max(r[f"ce_gamma{g}"] for r in ff.values()) - ips_ff[f"ce_gamma{g}"] for g in (2, 4, 8))
    gap_6080 = max(abs(ips_ff[f"ce_gamma{g}"] - f80[f"ce_gamma{g}"]) for g in (2, 4, 8))
    out.append(("MODEL", "floor CE gaps", f"within {k(gap_best)} of the best for each, and 60% and 80% differ by under "
                                          f"{k(np.ceil(gap_6080 / 100) * 100)}"))
    out.append(("MODEL", "80% floor trade-off",
                f"for {k(ips_ff['median'] - f80['median'])} of\nmedian, an 80% floor secures "
                f"${(f80['secured_2031_typical'] - ips_ff['secured_2031_typical']) / 1000:.0f}k more"))
    cs = ps["contribution_share"]
    out.append(("MODEL", "contribution shares",
                "give typical contributions of " + ", ".join(f"${c['contribution_median'] / 1000:.0f}k" for c in cs[:2])
                + f" and ${cs[2]['contribution_median'] / 1000:.0f}k and leave\nLaura "
                + ", ".join(f"${c['kept_median'] / 1000:.0f}k" for c in cs[:2]) + f" and ${cs[2]['kept_median'] / 1000:.0f}k"))
    zero = stress["reserve_certain_at_0pct_reinvestment"]
    out.append(("MODEL", "reserve certain at 0%", f"then lowers the median facility by {k(-zero['median_change'])}"))
    out.append(("VALIDATION", "reserve certain at 0%", f"(median -{k(-zero['median_change'])})"))
    out.append(("MODEL", "Taiwan cost-FX correlation range",
                f"range from {rng(fx.loc['random_walk_no_cost_fx_corr', 'real_p5'], fx.loc['random_walk_no_cost_fx_corr', 'real_p95'])} "
                f"to\n  {rng(fx.loc['random_walk', 'real_p5'], fx.loc['random_walk', 'real_p95'])}"))
    cb = ps["range_calibration_history"]
    out.append(("MODEL", "range calibration",
                f"the January 2033 result {cb['recentred']['inside_80pct_range']:.1%} of the time; "
                f"{cb['recentred']['below_range']:.1%} fell below it. As history happened: "
                f"{cb['as_happened']['inside_80pct_range']:.1%}, none below."))
    out.append(("MODEL", "calibrated band",
                f"percentile band held {cb['calibrated_band']['inside_recentred']:.1%} of the re-centred results "
                f"({cb['calibrated_band']['inside_as_happened']:.1%} as history happened)"))
    w1 = ps["reverse_stress"]["worst_1pct"]
    pb = ps["reverse_stress"]["prob_facility_below"]
    out.append(("MODEL", "reverse stress paths", f"with stocks down {-w1['stocks_cum_return_2028_2033']:.0%}\n"
                                                 f"over 2028-2033 and a worst 12 months of {w1['worst_12_months']:.0%}"))
    out.append(("MODEL", "reverse stress probabilities",
                f"$100k is {pb['100000']:.2%}, below $120k {pb['120000']:.1%}, below $140k {pb['140000']:.1%}."))
    hv = pd.read_csv(R / "validation_hrp.csv").set_index("rule").realised_vol
    out.append(("MODEL", "HRP linkage vols",
                f"single-linkage HRP had realised volatility of {hv.iloc[0]:.1%}: level with\naverage-linkage HRP "
                f"({hv.iloc[1]:.1%}) and below Ward-linkage HRP ({hv.iloc[2]:.1%}), inverse-variance ({hv.iloc[3]:.1%}) "
                f"and equal\nweights ({hv.iloc[4]:.1%})"))
    sw = pd.read_csv(R / "satellite_weights.csv", index_col=0)
    top = sw.hrp_weight.sort_values(ascending=False).head(3)
    out.append(("MODEL", "satellite top weights",
                "Largest weights: " + ", ".join(f"{t} {w:.1%}" for t, w in top.items()) + "."))
    names = {"Health Care": "Health care", "Information Technology": "Information technology",
             "Consumer Discretionary": "Consumer discretionary", "Communication Services": "Communication",
             "Real Estate": "Real estate"}
    for sec, g in sw.groupby("sector"):
        out.append(("MODEL", f"satellite sector {sec}", f"| {names.get(sec, sec)} | {len(g)} | {g.hrp_weight.sum():.1%} |"))
    td = pd.read_csv(R / "taiwan_drift_study.csv")
    tdp = td.pivot(index="origins", columns="rule", values="rmse")
    blocks = tdp.drop(index="all")
    wins = int((blocks["expanding"] < blocks["trailing_10y"]).sum())
    words = {4: "each of the four", 3: "three of the four", 2: "two of the four", 1: "one of the four", 0: "none of the four"}
    out.append(("MODEL", "Taiwan drift forecast",
                f"missed the next\n  74 months' cost growth by {tdp.loc['all', 'expanding']:.3f} (RMSE of the log change) against "
                f"{tdp.loc['all', 'trailing_10y']:.3f} for the trailing ten-year\n  average, and beat it in {words[wins]} "
                f"five-year blocks of origins"))
    sat = pd.read_csv(R / "satellite_scoring.csv")
    piv = sat.pivot_table(index=["beliefs", "commissions"], columns="candidate", values="median_vs_core")
    for beliefs, comm, label in (("Equilibrium (no alpha)", "$25 (WInS)", "Equilibrium (no alpha) | $25 per trade (WInS)"),
                                 ("Black-Litterman posterior", "$25 (WInS)", "BL posterior (+0.22%) | $25 per trade (WInS)"),
                                 ("Black-Litterman posterior", "none", "BL posterior (+0.22%) | none"),
                                 ("Satellite alpha as hoped (+0.82%)", "$25 (WInS)", "Alpha as hoped (+0.82%) | $25 per trade (WInS)")):
        cells = [piv.loc[(beliefs, comm), f"Core + {s}% satellite"] / 1000 for s in (10, 20, 30)]
        txt = " | ".join(("+" if c >= 0 else "−") + f"${abs(c):.1f}k" for c in cells)
        out.append(("MODEL", f"satellite verdict: {label}", f"| {label} | {txt} |"))
    sv = sat.set_index(["beliefs", "commissions", "candidate"])
    base_sat = sv.loc[("Black-Litterman posterior", "$25 (WInS)", "BL core only"), "median"]
    bl20 = -sv.loc[("Black-Litterman posterior", "$25 (WInS)", "Core + 20% satellite"), "median_vs_core"]
    hoped20 = -sv.loc[("Satellite alpha as hoped (+0.82%)", "$25 (WInS)", "Core + 20% satellite"), "median_vs_core"]
    per_pp = (bl20 - hoped20) / (0.82 - 0.22)          # the hoped and posterior alphas, in points
    out.append(("MODEL", "satellite run base", f"The base BL core median in this run is {k(base_sat)}. It is "
                                               f"{k(abs(base_sat - plan['median']))} "
                                               f"{'above' if base_sat >= plan['median'] else 'below'} the core's own run"))
    out.append(("MODEL", "satellite alpha sensitivity",
                f"each extra 1pp of alpha moves the median by about ${per_pp:,.0f}. With $25 commissions\n"
                f"the satellite needs about {bl20 / per_pp:.1f}pp a year of alpha beyond the posterior to break even"))
    out.append(("MODEL", "satellite cost share", f"commission it costs about {bl20 / base_sat:.1%} of the median facility"))
    rs = pd.read_csv(R / "satellite_risk_sensitivity.csv")
    def rsk(reading, comm, col):
        return rs[(rs.reading == reading) & (rs.commissions == comm)][col].iloc[0]
    sk = lambda x: ("+" if x >= 0 else "-") + k(abs(x))
    out.append(("MODEL", "satellite risk correction",
                f"and no commissions the median stays positive ({sk(rsk('as_estimated', 'none', 'median_vs_core'))} as estimated, "
                f"{sk(rsk('risk_only', 'none', 'median_vs_core'))}\n  to {sk(rsk('with_return', 'none', 'median_vs_core'))} "
                f"corrected), but the 5th percentile goes from {sk(rsk('as_estimated', 'none', 'p5_vs_core'))} to "
                f"{sk(rsk('with_return', 'none', 'p5_vs_core'))}\n  to {sk(rsk('risk_only', 'none', 'p5_vs_core'))} "
                f"against the core alone; with $25 commissions from {sk(rsk('as_estimated', '$25 (WInS)', 'p5_vs_core'))} "
                f"to {sk(rsk('with_return', '$25 (WInS)', 'p5_vs_core'))}\n  to {sk(rsk('risk_only', '$25 (WInS)', 'p5_vs_core'))}."))
    conv = pd.read_csv(R / "validation_convergence.csv")
    se = conv.std() / np.sqrt(len(conv))
    out.append(("VALIDATION", "convergence",
                f"the median facility is ${conv['median'].mean():,.0f} with a standard\n  error of ${se['median']:,.0f}; "
                f"the 5th percentile's is ${se['p5']:,.0f}."))
    sd = conv.std()
    out.append(("VALIDATION", "single-run precision",
                f"moves by ${sd['median']:,.0f}\n  in the median and ${sd['p5']:,.0f} in the 5th percentile from seed to seed; "
                f"the headline's 5th percentile is\n  ${plan['p5'] - conv['p5'].mean():,.0f} "
                f"{'above' if plan['p5'] >= conv['p5'].mean() else 'below'} the 8-seed average"))
    bt = pd.read_csv(R / "backtest.csv")
    ips = bt[(bt.paths.str.startswith("History re-centred")) & (bt.strategy == "IPS, Black-Litterman core")].iloc[0]
    out.append(("VALIDATION", "replay vs simulation",
                f"the IPS median is {k(ips['median'])} against {k(plan['median'])}\n  simulated; its 5th percentile is "
                f"{k(ips['p5'])} against {k(plan['p5'])} simulated"))
    out.append(("VALIDATION", "named crises after the lock", episodes_bullet()))
    pv = pd.read_csv(R / "plans_v2_validation.csv").set_index("strategy")
    for short, full in (("S8 hybrid", "S8 Hybrid, half-hedged"), ("S6 lock, stock surplus", "S6 Bond-first, equity surplus"),
                        ("S9 lock, 60/40, floor", "S9 Bond-first, 60/40 surplus, 60% floor")):
        r = pv.loc[full]
        floor = "0 / 0" if r.floor_2031_k == 0 else f"{r.v2_floor_k:.1f} / {r.floor_2031_k:.1f}"
        out.append(("VALIDATION", f"Plans v2 table: {short}",
                    f"| {short} | {r.v2_funded:.0%} / {r.funded:.0%} | {r.v2_p5_k:.1f} / {r.p5_k:.1f} | "
                    f"{r.v2_median_k:.1f} / {r.median_k:.1f} | {r.v2_p95_k:.1f} / {r.p95_k:.1f} | {floor} | "
                    f"{r.v2_r10_k:.1f}-{r.v2_r90_k:.1f} / {r.range80_lo_k:.1f}-{r.range80_hi_k:.1f} |"))
    esg = pd.read_csv(R / "validation_esg.csv").set_index("check")
    lo, hi = (esg.loc[f"10-year yield change to Jan 2033, {p}"] for p in ("p5", "p95"))
    pt = lambda x: f"{x * 100:+.1f}"
    out.append(("VALIDATION", "10-year yield change spread",
                f"spans {pt(lo.model)} to {pt(hi.model)} points (5th-95th\n  percentile), against "
                f"{pt(lo.history_2005_2026)} to {pt(hi.history_2005_2026)} points"))
    rp = json.loads((R / "rate_path_scenario.json").read_text())
    out.append(("MODEL", "Kim-Wright path", f"the median facility is\n  ${(rp['unchanged']['median'] - rp['kim_wright']['median']) / 1000:.1f}k lower"))
    s1 = bt[(bt.paths.str.startswith("History re-centred")) & (bt.strategy.str.startswith("S1"))].iloc[0]
    s1_sim = pv.loc["S1 Index-first, all equity", "funded"]
    out.append(("VALIDATION", "replay, all-stock funded",
                f"All-stock funds every payment in {s1.funded:.1%} of real paths against {s1_sim:.1%} simulated"))
    out.append(("VALIDATION", "replay paths", f"{int(ips.n_paths)} real six-year paths (starts "
                f"{pd.Timestamp(ips.first_start):%B %Y} to {pd.Timestamp(ips.last_start):%B %Y})"))
    rc = ps["range_calibration_history"]
    out.append(("VALIDATION", "2031 range calibration",
                f"contained the January 2033 result {rc['recentred']['inside_80pct_range']:.1%} of the time re-centred\n  "
                f"({rc['as_happened']['inside_80pct_range']:.1%} as it happened)"))
    out.append(("VALIDATION", "2031 calibrated band",
                f"band held {rc['calibrated_band']['inside_recentred']:.1%} ({rc['calibrated_band']['inside_as_happened']:.1%} as\n  it happened)"))
    esg_v = pd.read_csv(R / "validation_esg.csv").set_index("check")
    kurt = esg_v[esg_v.index.str.contains("kurtosis")]
    out.append(("VALIDATION", "generator kurtosis",
                f"monthly excess kurtosis {kurt.model.min():.1f}-{kurt.model.max():.1f} against "
                f"{kurt.history_2005_2026.min():.1f}-{kurt.history_2005_2026.max():.1f} in 2005-2026"))
    out.append(("VALIDATION", "VTV-VGK correlation", f"(VTV-VGK, {esg_v.loc['Correlation VTV-VGK', 'model']:.3f})"))
    hrp = pd.read_csv(R / "validation_hrp.csv").set_index("rule").realised_vol
    out.append(("VALIDATION", "HRP linkage vols",
                f"volatility ({hrp.iloc[0]:.1%}) is level with average-linkage HRP ({hrp.iloc[1]:.1%}) and below Ward "
                f"({hrp.iloc[2]:.1%}), inverse-variance\n  ({hrp.iloc[3]:.1%}) and equal weights ({hrp.iloc[4]:.1%})"))
    bl = pd.read_csv(R / "bl_sensitivity.csv")
    pc = lambda c: f"{bl[c].min():.1%} to {bl[c].max():.1%}"
    out.append(("VALIDATION", "BL stability",
                f"resampled weights hold BBJP at {bl.BBJP.min() * 100:.1f}-{bl.BBJP.max():.1%} and BBCA at "
                f"{bl.BBCA.min() * 100:.1f}-{bl.BBCA.max():.1%}"))
    out.append(("VALIDATION", "BL single optimum", f"and {pc('single_optimum_BBCA')}"))
    s1r, s2r = pv.loc["S1 Index-first, all equity"], pv.loc["S2 Index-first, static 60/40"]
    out.append(("VALIDATION", "Plans v2 table: S1",
                f"| S1 all equity | {s1r.v2_funded:.1%} / {s1r.funded:.1%} | 0 / 0 | {s1r.v2_median_k:.1f} / {s1r.median_k:.1f} | "
                f"{s1r.v2_p95_k:.1f} / {s1r.p95_k:.1f} | — | — |"))
    out.append(("VALIDATION", "Plans v2 table: S2",
                f"| S2 static 60/40 | {s2r.v2_funded:.1%} / {s2r.funded:.1%} | {s2r.v2_p5_k:.1f} / {s2r.p5_k:.1f} | "
                f"{s2r.v2_median_k:.1f} / {s2r.median_k:.1f} | {s2r.v2_p95_k:.1f} / {s2r.p95_k:.1f} | 0 / 0 | "
                f"{s2r.v2_r10_k:.1f}-{s2r.v2_r90_k:.1f} / {s2r.range80_lo_k:.1f}-{s2r.range80_hi_k:.1f} |"))
    blm = pd.read_csv(R / "bl_sensitivity.csv")
    out.append(("MODEL", "BL stability", f"BBJP between {blm.single_optimum_BBJP.min():.1%} and {blm.single_optimum_BBJP.max():.1%}. "
                                         f"The weights are the average optimum"))
    out.append(("MODEL", "BL resampled BBJP", f"Over the same grid BBJP stays\n  at {blm.BBJP.min() * 100:.1f}-{blm.BBJP.max():.1%}"))
    rs0 = pd.read_csv(R / "satellite_risk_sensitivity.csv").iloc[0]
    out.append(("MODEL", "satellite vol", f"volatility ({rs0.satellite_vol:.1%}) comes from history back to 2005"))
    out.append(("MODEL", "satellite beta", f"covariance with the market (beta {rs0.satellite_beta:.2f})"))
    v2 = json.loads((R / "plans_v2_rate_stress.json").read_text())
    out.append(("VALIDATION", "Plans v2 rate stress",
                f"{k(v2['base_median'])} -> {k(v2['minus_75bp_median'])} "
                f"({v2['minus_75bp_median'] / v2['base_median'] - 1:.0%}) (`reports/plans_v2_rate_stress.json`)"))
    sr = pd.read_csv(R / "stock_rate_corr.csv")
    ips_sr = sr[sr.strategy.str.startswith("IPS")].set_index("variant")
    s2_sr = sr[sr.strategy.str.startswith("S2")].set_index("variant")
    out.append(("MODEL", "stock-rate correlation, IPS p5",
                f"percentile ranges from {k(ips_sr.p5.min())} (the 2000-2021 regime) to {k(ips_sr.p5.max())} (today's)"))
    out.append(("MODEL", "stock-rate correlation, open 60/40 p5",
                f"its 5th percentile runs from {k(s2_sr.loc['2022..2026', 'p5'])}\nto {k(s2_sr.loc['2000..2021', 'p5'])}"))
    cc = pd.read_csv(R / "crash_comovement.csv").iloc[0]
    out.append(("MODEL", "crash months", f"rose {cc.crash_mean_dr:.2f} points on average and fell in "
                                         f"{cc.crash_share_rates_down:.0%} of them"))
    fh = pd.read_csv(R / "fx_horizon.csv").set_index(["sample", "horizon_m"])
    a, b = fh.loc[("H.10 2000-2026", 74)], fh.loc[("DEXTAUS 1983-2026", 74)]
    out.append(("MODEL", "FX variance ratios",
                f"(variance ratio {a.variance_ratio:.2f}), but a random walk of the same length gives a median of "
                f"{a.rw_null_median:.2f} and {a.variance_ratio:.2f} or less\n  {a.p_mean_reversion:.0%} of the time; "
                f"on FRED's copy of the same rate from 1983 the ratio is {b.variance_ratio:.2f}"))
    out.append(("MODEL", "FX 74-month spread", f"spread (sd {a.model_sd:.1%}) lies between the two samples' "
                                               f"{a.hist_sd:.1%} and {b.hist_sd:.1%}"))
    lp = pd.read_csv(R / "ladder_premium.csv")
    fit = lp[(lp.kind == "fit") & (lp.date == "Jan 2027")].iloc[0]
    ips_lp = lp[(lp.kind == "score") & lp.strategy.str.startswith("IPS")].set_index("variant")
    out.append(("MODEL", "ladder premium fit", f"gives {fit.lp_at_today_rate:.2%} at today's 5-year rate plus "
                                               f"{fit.slope:.2f} points\nper point of rate ({fit.lp_min:.1%} to {fit.lp_max:.1%}"))
    sl, lv = ips_lp.loc["rate slope"], ips_lp.loc["rate slope, Jan 2027 LP level"]
    out.append(("MODEL", "ladder premium impact",
                f"changes the IPS median by +${sl.median_vs_engine:,.0f} and its 5th percentile by +{k(sl.p5_vs_engine)}; "
                f"with the lower level as well,\n+{k(lv.median_vs_engine)} and +{k(lv.p5_vs_engine)}"))
    eh = pd.read_csv(R / "equity_horizon.csv")
    e74 = eh[(eh.returns == "nominal") & (eh.start == 1926) & (eh.horizon_m == 74)].iloc[0]
    out.append(("VALIDATION", "equity variance ratio", f"74-month variance ratio since 1926 is {e74.variance_ratio:.2f}\n  "
                f"against {e74.null_median:.2f} for i.i.d. returns of the same length (p = {e74.p_mean_reversion:.2f}; "
                f"every start date and horizon tested,\n  nominal or excess, has p of {eh.p_mean_reversion.min():.2f} or more)"))
    c = rn["core"]
    out.append(("MODEL", "BL risk aversion", f"δ = {c['delta']:.2f} makes the market earn"))
    out.append(("MODEL", "BL market geometric", f"(market geometric {c['market_geometric_prior']:.2%})"))
    out.append(("VALIDATION", "BL risk aversion", f"With today's inputs δ is {c['delta']:.2f}."))
    mkt = pd.read_csv(R / "core_bl.csv").set_index("etf").w_mkt
    for etf, w in c["weights"].items():
        out.append(("MODEL", f"core weight {etf}", f"| {etf} | {mkt[etf]:.1%} | {w:.1%} |"))
    g = c["regions"]
    out.append(("MODEL", "core regions", f"The core holds {g['US']:.0%} US, {g['developed']:.0%} developed and "
                                         f"{g['emerging']:.0%} emerging stocks"))
    out.append(("MODEL", "core summary",
                f"It expects {c['expected_geometric_net']:.1%} a year after fees\n(market {c['market_expected_geometric_net']:.1%}), "
                f"with {c['volatility']:.1%} volatility, a {c['fee']:.2%} average fee and a {c['tracking_error']:.2%} tracking error. "
                f"Look-through\ntech/communication is {c['tech_comm']:.1%} (market {c['tech_comm_market']:.1%}); "
                f"China+Taiwan is {c['china_taiwan']:.1%} (market {c['china_taiwan_market']:.1%})."))
    out.append(("MODEL", "FX hedge frontier", hedge_sentence()))
    out.append(("MODEL", "Taiwan cost vs stocks", taiwan_equity_sentence()))
    out.append(("MODEL", "correlation shrinkage out of sample", corr_shrink_sentence()))
    teo = pd.read_csv(R / "tracking_error_oos.csv").set_index(["funds", "horizon_m"])
    out.append(("MODEL", "core tracking error out of sample",
                f"the core's {rn['core']['tracking_error']:.2%} tracking error below is about "
                f"{teo.loc[(9, 36), 'tracking_error_corrected']:.2%} over three years and "
                f"{teo.loc[(9, 72), 'tracking_error_corrected']:.2%} over six"))
    ev = pd.read_csv(R / "equity_vol_history.csv").set_index("period").annual_vol
    out.append(("VALIDATION", "equity vol history",
                f"volatility was {ev['2005-2026']:.1%} a year in 2005-2026, the window the equity volatilities come from, "
                f"against {ev['1946-2026']:.1%} for 1946-2026; only 1926-1945 (the Depression and the war) lifts the 1926-2026 figure to "
                f"{ev['1926-2026']:.1%}"))
    vf = pd.read_csv(R / "equity_vol_forecast.csv")
    vf = vf[(vf.horizon_m == 72) & (vf.period == "1981 on")].set_index("window")
    out.append(("VALIDATION", "equity vol window forecast",
                f"a trailing 21-year volatility missed the next six\n  years' by {vf.rms['21 years']:.2f} in logs (root mean "
                f"square; bias {vf.bias['21 years']:+.1%}), against {vf.rms['9 years']:.2f} for 9 years, "
                f"{vf.rms['3 years']:.2f} for 3 years\n  and {vf.rms['since 1926']:.2f} for all history since 1926"))
    vp = pd.read_csv(R / "vol_proxy_check.csv")
    em = vp[vp.em_china_pair]
    by = vp.groupby("start").scaled_closer
    words = {3: "3 of 4", 4: "all 4"}
    out.append(("VALIDATION", "vol proxy check",
                f"scaling each by the other moved it closer in {words.get(int(em.scaled_closer.sum()), int(em.scaled_closer.sum()))} "
                f"cases. With any fund as the proxy it helped in {by.sum()['2011-04-30']} of {by.size()['2011-04-30']} pairs from\n  "
                f"2011 but only {by.sum()['2017-08-31']} of {by.size()['2017-08-31']} from 2017"))
    out.append(("MODEL", "headline in the sensitivity intro",
                f"The IPS median is {k(plan['median'])} and its 5th percentile {k(plan['p5'])}."))
    zr = stress["reserve_certain_at_0pct_reinvestment"]
    out.append(("MODEL", "ladder premiums", f"At 0% the cheapest ladder costs {zr['ladder_premium']:.1%} over zero-coupon "
                                            f"value instead of {zr['ladder_premium_at_3pct']:.1%}."))
    v = rn["core"]["views"]
    out.append(("MODEL", "BL view sizes",
                f"international developed minus US ({v['International developed minus US']:+.2%}), emerging minus developed "
                f"({v['Emerging minus international developed']:+.2%}), US value minus growth ({v['US value minus US growth']:+.2%}:"))
    out.append(("MODEL", "BL small-cap view", f"US small minus large ({v['US small minus US large']:+.2%}:"))
    srm = pd.read_csv(R / "stock_rate_corr.csv")
    srm = srm[srm.strategy.str.startswith("IPS")]
    out.append(("MODEL", "stock-rate IPS median", f"the IPS median stays within "
                                                  f"{k(np.ceil(srm.median_vs_today.abs().max() / 100) * 100)} and its 5th"))
    so = pd.read_csv(R / "satellite_oos.csv")
    sel, ctrl = so.sel_vol_ratio.mean(), so.ctrl_vol_ratio_median.mean()
    out.append(("MODEL", "satellite out of sample",
                f"volatility fell by a factor of {sel:.2f} out of sample, against {ctrl:.2f} for random 35-name baskets"))
    out.append(("MODEL", "satellite selection effect", f"selection made in-sample risk look about {sel / ctrl - 1:.0%} too low"))
    lpm = pd.read_csv(R / "ladder_premium.csv")
    lpm = lpm[(lpm.kind == "score") & lpm.strategy.str.startswith("IPS")].set_index("variant")
    out.append(("MODEL", "ladder slope, loop summary",
                f"a rate-dependent ladder premium (+${lpm.loc['rate slope', 'median_vs_engine']:,.0f} median"))
    out += [("MODEL", f"sensitivity row {i + 1}", row) for i, row in enumerate(sensitivity_rows())]
    out += [("MODEL", f"decision row {i + 1}", row) for i, row in enumerate(decision_rows())]
    tw10 = fx.loc["random_walk", "real_median"] - fx.loc["random_walk_tw_drift_10y", "real_median"]
    out.append(("MODEL", "Taiwan drift effect", f"the real median by {k(tw10)} (`scripts/fx_variants.py`"))
    return out


NUMBER = r"[−+-]?\$?\d[\d,]*(?:\.\d+)?k?%?"


def _flat(text: str) -> str:
    """Line breaks and indentation do not count: a figure may be rewrapped freely."""
    return re.sub(r"\s+", " ", text).strip()


def _literal(text: str) -> str:
    """Regex for literal text, any run of whitespace matching any other."""
    return r"\s+".join(re.escape(w) for w in re.split(r"\s+", text))


def _split(text: str) -> tuple[str, list[str]]:
    """(table-row label kept literally, the rest split into literal / number / literal ...)."""
    head = ""
    if text.startswith("| "):                      # a table row: its first cell is the row's label, keep it
        cut = text.index(" | ", 2) + 3
        head, text = text[:cut], text[cut:]
    return head, re.split(f"({NUMBER})", text)


def pattern(text: str) -> re.Pattern:
    """The expected text with every number generalised (one group each), to find its stale version."""
    head, parts = _split(text)
    return re.compile(_literal(head) + "".join(f"({NUMBER})" if i % 2 else _literal(x) for i, x in enumerate(parts)))


def fix() -> list[tuple[str, str, str]]:
    """Rewrite each stale figure found exactly once, number by number, so the doc keeps its own line
    breaks; return the ones that could not be placed."""
    paths = {"MODEL": ROOT / "docs" / "MODEL.md", "VALIDATION": ROOT / "docs" / "VALIDATION.md"}
    texts = {d: p.read_text() for d, p in paths.items()}
    left = []
    for doc, what, text in missing():
        hits = list(pattern(text).finditer(texts[doc]))
        if len(hits) != 1:
            left.append((doc, what, text))
            continue
        m, new = hits[0], _split(text)[1][1::2]
        t = texts[doc]
        for g in range(len(new), 0, -1):            # right to left, so earlier spans stay valid
            t = t[:m.start(g)] + new[g - 1] + t[m.end(g):]
        texts[doc] = t
    for d, p in paths.items():
        p.write_text(texts[d])
    return left


def missing() -> list[tuple[str, str, str]]:
    docs = {d: _flat((ROOT / "docs" / f"{d}.md").read_text()) for d in ("MODEL", "VALIDATION")}
    return [c for c in checks() if _flat(c[2]) not in docs[c[0]]]


def main() -> int:
    if "--fix" in sys.argv:
        for doc, what, text in fix():
            print(f"could not place: {doc} {what}: {text!r}")
    bad = missing()
    for doc, what, text in checks():
        print(f"{'MISSING' if (doc, what, text) in bad else 'ok':8s} {doc:10s} {what}: {text!r}")
    print(f"\n{len(bad)} of {len(checks())} figures missing from the docs")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
