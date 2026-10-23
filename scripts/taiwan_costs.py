"""Calibration of Taiwan construction cost index for the LGM ESG model.

Outputs:
- reports/taiwan_costs.json
- config/taiwan_costs_proposal.yaml (the r1 proposal; it is not the live model config)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from lgm.data import fed, fred, taiwan

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "taiwan_costs.json"
CONFIG_PATH = ROOT / "config" / "taiwan_costs_proposal.yaml"


def compute_sample_stats(s_monthly: pd.Series, s_12m: pd.Series) -> dict[str, float]:
    """Compute annual growth and volatility metrics for a given period."""
    log_mean = float(s_monthly.mean() * 12)
    log_median = float(s_monthly.median() * 12)
    simple_mean = float(np.expm1(log_mean))
    simple_median = float(np.expm1(log_median))

    # Rolling 12-month metrics
    chg12_log_mean = float(s_12m.mean())
    chg12_log_median = float(s_12m.median())
    chg12_simple_mean = float(np.expm1(s_12m).mean())
    chg12_simple_median = float(np.expm1(s_12m).median())

    # Volatility
    monthly_ann_vol = float(s_monthly.std() * np.sqrt(12))
    std_12m = float(s_12m.std())
    ratio = float(std_12m / monthly_ann_vol) if monthly_ann_vol > 0 else 0.0

    return {
        "annual_log_mean": round(log_mean, 6),
        "annual_log_median": round(log_median, 6),
        "annual_simple_mean": round(simple_mean, 6),
        "annual_simple_median": round(simple_median, 6),
        "rolling_12m_log_mean": round(chg12_log_mean, 6),
        "rolling_12m_log_median": round(chg12_log_median, 6),
        "rolling_12m_simple_mean": round(chg12_simple_mean, 6),
        "rolling_12m_simple_median": round(chg12_simple_median, 6),
        "monthly_ann_vol": round(monthly_ann_vol, 6),
        "std_12m": round(std_12m, 6),
        "vol_ratio_12m_to_monthly": round(ratio, 4),
    }


def simulate_72m_iid(growth: float, vol: float, n: int = 100_000, seed: int = 42) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    mu_m = np.log1p(growth) / 12.0
    sig_m = vol / np.sqrt(12.0)
    shocks = rng.standard_normal((n, 72))
    tot_log = 72 * mu_m + sig_m * np.sum(shocks, axis=1)
    tot_smp = np.expm1(tot_log)
    p = lambda q: float(np.percentile(tot_smp, q))
    return {
        "p5": round(p(5), 6),
        "p10": round(p(10), 6),
        "p50": round(p(50), 6),
        "p90": round(p(90), 6),
        "p95": round(p(95), 6),
        "mean": round(float(tot_smp.mean()), 6),
        "spread_95_5": round(p(95) - p(5), 6),
    }


def simulate_72m_ar1(growth: float, vol: float, phi: float, n: int = 100_000, seed: int = 42) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    mu_m = np.log1p(growth) / 12.0
    sig_m = vol / np.sqrt(12.0)
    sig_eps = sig_m * np.sqrt(max(1.0 - phi**2, 1e-6))

    tw = np.zeros((n, 72))
    state = rng.standard_normal(n) * sig_m
    shocks = rng.standard_normal((n, 72))
    for t in range(72):
        state = phi * state + sig_eps * shocks[:, t]
        tw[:, t] = mu_m + state

    tot_log = np.sum(tw, axis=1)
    tot_smp = np.expm1(tot_log)
    p = lambda q: float(np.percentile(tot_smp, q))
    return {
        "p5": round(p(5), 6),
        "p10": round(p(10), 6),
        "p50": round(p(50), 6),
        "p90": round(p(90), 6),
        "p95": round(p(95), 6),
        "mean": round(float(tot_smp.mean()), 6),
        "spread_95_5": round(p(95) - p(5), 6),
    }


def main():
    # 1. Load data
    cci = taiwan.cci()
    tw_cpi = taiwan.cpi()
    us_cpi = fred.cpi()["CPIAUCNS"]
    usd_twd = fed.usd_twd().resample("ME").last()

    # Align to monthly period index
    to_m = lambda s: s.to_period("M")

    d_cci = np.log(cci / cci.shift(1)).dropna()
    d_tw_cpi = np.log(tw_cpi / tw_cpi.shift(1)).dropna()
    d_us_cpi = np.log(us_cpi / us_cpi.shift(1)).dropna()
    d_fx = np.log(usd_twd / usd_twd.shift(1)).dropna()

    chg12_log = np.log(cci / cci.shift(12)).dropna()

    # 2. Periods: Full sample, Last 20 years, Last 10 years
    end_dt = cci.index[-1]
    dt_20y = end_dt - pd.DateOffset(years=20)
    dt_10y = end_dt - pd.DateOffset(years=10)

    periods = {
        "full_sample": (d_cci, chg12_log),
        "last_20_years": (d_cci.loc[dt_20y:], chg12_log.loc[dt_20y:]),
        "last_10_years": (d_cci.loc[dt_10y:], chg12_log.loc[dt_10y:]),
    }

    sample_stats = {
        name: compute_sample_stats(m_sub, y_sub)
        for name, (m_sub, y_sub) in periods.items()
    }

    # 3. Persistence
    ar1_monthly = float(d_cci.autocorr(1))
    ar2_monthly = float(d_cci.autocorr(2))
    ar1_12m = float(chg12_log.autocorr(1))
    ar12_12m = float(chg12_log.autocorr(12))

    persistence = {
        "ar1_monthly_log_change": round(ar1_monthly, 4),
        "ar2_monthly_log_change": round(ar2_monthly, 4),
        "ar1_12m_inflation": round(ar1_12m, 4),
        "ar12_12m_inflation": round(ar12_12m, 4),
    }

    # 4. Correlations
    m_cci = d_cci.copy()
    m_tw_cpi = d_tw_cpi.copy()
    m_us_cpi = d_us_cpi.copy()
    m_fx = d_fx.copy()

    m_cci.index = to_m(m_cci.index)
    m_tw_cpi.index = to_m(m_tw_cpi.index)
    m_us_cpi.index = to_m(m_us_cpi.index)
    m_fx.index = to_m(m_fx.index)

    df_corr = pd.DataFrame({
        "cci": m_cci,
        "usd_twd": m_fx,
        "us_cpi": m_us_cpi,
        "tw_cpi": m_tw_cpi,
    }).dropna()

    corr_matrix = df_corr.corr()
    correlations = {
        "with_usd_twd": round(float(corr_matrix.loc["cci", "usd_twd"]), 4),
        "with_us_cpi": round(float(corr_matrix.loc["cci", "us_cpi"]), 4),
        "with_tw_cpi": round(float(corr_matrix.loc["cci", "tw_cpi"]), 4),
        "overlapping_months": int(len(df_corr)),
        "overlap_start": str(df_corr.index[0]),
        "overlap_end": str(df_corr.index[-1]),
    }

    # 5. 72-month rolling windows
    g72_smp = (cci / cci.shift(72) - 1).dropna()
    g72_log = np.log(cci / cci.shift(72)).dropna()

    p_smp = lambda q: float(np.percentile(g72_smp, q))
    p_log = lambda q: float(np.percentile(g72_log, q))

    historical_72m = {
        "n_windows": int(len(g72_smp)),
        "first_window_end": str(g72_smp.index[0].date()),
        "last_window_end": str(g72_smp.index[-1].date()),
        "simple": {
            "p5": round(p_smp(5), 6),
            "p10": round(p_smp(10), 6),
            "p25": round(p_smp(25), 6),
            "p50": round(p_smp(50), 6),
            "p75": round(p_smp(75), 6),
            "p90": round(p_smp(90), 6),
            "p95": round(p_smp(95), 6),
            "min": round(float(g72_smp.min()), 6),
            "max": round(float(g72_smp.max()), 6),
            "mean": round(float(g72_smp.mean()), 6),
            "spread_95_5": round(p_smp(95) - p_smp(5), 6),
        },
        "log": {
            "p5": round(p_log(5), 6),
            "p10": round(p_log(10), 6),
            "p50": round(p_log(50), 6),
            "p90": round(p_log(90), 6),
            "p95": round(p_log(95), 6),
            "min": round(float(g72_log.min()), 6),
            "max": round(float(g72_log.max()), 6),
            "mean": round(float(g72_log.mean()), 6),
            "spread_95_5": round(p_log(95) - p_log(5), 6),
        },
    }

    # 6. Model comparisons
    current_model_72m = simulate_72m_iid(growth=0.04, vol=0.015)
    # Proposed i.i.d. baseline: growth=2.85%, effective_vol=5.40%
    proposed_iid_72m = simulate_72m_iid(growth=0.0285, vol=0.0538)
    # Proposed AR(1) model: growth=2.85%, vol=3.10%, phi=0.60
    proposed_ar1_72m = simulate_72m_ar1(growth=0.0285, vol=0.0309, phi=0.5983)

    report_data = {
        "series": "DGBAS Construction Cost Index (Total Index, 2021=100)",
        "frequency": "monthly",
        "data_start": str(cci.index[0].date()),
        "data_end": str(cci.index[-1].date()),
        "n_obs": int(len(cci)),
        "growth_and_volatility": sample_stats,
        "persistence": persistence,
        "correlations": correlations,
        "cumulative_72m_comparison": {
            "historical_empirical": historical_72m["simple"],
            "current_assumption_iid_4pct_growth_1_5pct_vol": current_model_72m,
            "proposed_iid_dropin_2_85pct_growth_5_38pct_vol": proposed_iid_72m,
            "proposed_persistent_ar1_2_85pct_growth_3_09pct_vol_phi_0_60": proposed_ar1_72m,
        },
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"Wrote report: {REPORT_PATH}")

    # 7. Write the proposed config (a separate file: config/taiwan.yaml is the live model config)
    config_yaml = """# Proposed Taiwan Building-Cost Model Parameters
# Calibrated from official DGBAS Construction Cost Index (1991-01 to 2026-09)
# Generated by scripts/taiwan_costs.py; documented in docs/loop/r1_taiwan_findings.md

# Option 1: Drop-in replacement for existing ESGParams (preserves i.i.d. architecture)
# Uses historical 35-year drift (2.85%) and effective annual volatility (5.38%)
# matching the 12-month and 72-month cumulative dispersion under an i.i.d. walk.
iid_dropin:
  tw_cost_growth: 0.0285   # Full sample mean annual growth (reports/taiwan_costs.json: 0.0282-0.0286)
  tw_cost_vol: 0.0538      # 12-month standard deviation (reports/taiwan_costs.json: std_12m=0.0538)
  t_dof: null              # i.i.d. Gaussian increments as in existing esg.py

# Option 2: Structurally faithful persistent process (recommended)
# Reflects strong monthly AR(1) autocorrelation (phi=0.598) and common inflation shocks.
persistent_process:
  tw_cost_growth: 0.0285   # Long-run annual mean log drift (full sample: 2.82%, 20-yr: 2.62%)
  tw_cost_monthly_vol: 0.0309  # Annualized volatility of monthly log innovations (std * sqrt(12))
  tw_cost_phi: 0.5983      # AR(1) persistence of monthly log cost changes
  tw_cost_innovation_vol: 0.0248  # Innovation std: vol * sqrt(1 - phi^2) = 0.0309 * 0.8013
  correlations:
    us_cpi: 0.4783         # Correlation with US CPI inflation (joint global commodity shocks)
    usd_twd: -0.1256       # Correlation with USD/TWD monthly log changes
    tw_cpi: 0.0754         # Correlation with domestic Taiwan CPI
"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(config_yaml)
    print(f"Wrote config: {CONFIG_PATH}")

    # 8. Print human-readable summary
    print("\n" + "=" * 70)
    print("TAIWAN CONSTRUCTION COST INDEX CALIBRATION SUMMARY")
    print("=" * 70)
    print(f"Source: DGBAS 營造工程物價總指數 ({report_data['data_start']} to {report_data['data_end']}, {report_data['n_obs']} months)")
    print("\n1. Annual Growth & Volatility by Period:")
    for period, st in sample_stats.items():
        print(f"  {period:15s}: Mean Log={st['annual_log_mean']*100:.2f}%, Simple={st['annual_simple_mean']*100:.2f}% | "
              f"Median Log={st['annual_log_median']*100:.2f}%, Simple={st['annual_simple_median']*100:.2f}%")
        print(f"                   Monthly Vol (x sqrt 12)={st['monthly_ann_vol']*100:.2f}% | 12m Std={st['std_12m']*100:.2f}% | "
              f"Ratio={st['vol_ratio_12m_to_monthly']:.2f}")

    print("\n2. Persistence & Autocorrelation:")
    print(f"  AR(1) Monthly Log Change: {ar1_monthly:.4f}")
    print(f"  AR(2) Monthly Log Change: {ar2_monthly:.4f}")
    print(f"  AR(1) 12-Month Inflation: {ar1_12m:.4f}")
    print("  -> Vol ratio of 1.74 and monthly AR(1) of 0.60 reject the i.i.d. assumption.")

    print("\n3. Monthly Log Change Correlations:")
    print(f"  With USD/TWD:   {correlations['with_usd_twd']:+.4f} (N={correlations['overlapping_months']})")
    print(f"  With US CPI:    {correlations['with_us_cpi']:+.4f}")
    print(f"  With Taiwan CPI:{correlations['with_tw_cpi']:+.4f}")

    print("\n4. 72-Month Cumulative Simple Growth Distribution (Quantity that matters):")
    print(f"  {'Model / Series':<40s} {'p5':>8s} {'p50 (Med)':>10s} {'p95':>8s} {'Spread (95-5)':>14s}")
    print("  " + "-" * 74)
    hist = historical_72m["simple"]
    print(f"  {'Historical Empirical (357 windows)':<40s} {hist['p5']*100:>7.2f}% {hist['p50']*100:>9.2f}% {hist['p95']*100:>7.2f}% {hist['spread_95_5']*100:>13.2f}%")
    print(f"  {'Current Model (4% growth, 1.5% vol, iid)':<40s} {current_model_72m['p5']*100:>7.2f}% {current_model_72m['p50']*100:>9.2f}% {current_model_72m['p95']*100:>7.2f}% {current_model_72m['spread_95_5']*100:>13.2f}%")
    print(f"  {'Proposed i.i.d. (2.85% growth, 5.38% vol)':<40s} {proposed_iid_72m['p5']*100:>7.2f}% {proposed_iid_72m['p50']*100:>9.2f}% {proposed_iid_72m['p95']*100:>7.2f}% {proposed_iid_72m['spread_95_5']*100:>13.2f}%")
    print(f"  {'Proposed AR(1) (2.85% gr, 3.09% vol, phi=0.6)':<40s} {proposed_ar1_72m['p5']*100:>7.2f}% {proposed_ar1_72m['p50']*100:>9.2f}% {proposed_ar1_72m['p95']*100:>7.2f}% {proposed_ar1_72m['spread_95_5']*100:>13.2f}%")
    print("=" * 70)


if __name__ == "__main__":
    main()
