"""Regenerate every report in dependency order.

Usage: python scripts/run_all.py [--refresh]
  --refresh  first re-download the market data that moves with the dates in config/asof.yaml (Treasury
             curves for the curve year, CPI, USD/TWD, Kim-Wright, monthly ETF and satellite prices), and
             let the WInS scripts refetch closing prices. Change config/asof.yaml before refreshing.
Stops at the first script that fails; the WInS ladder check's exit status is reported, not fatal.
Then the studies whose reports the docs quote, and last `doc_numbers.py`, which fails if a figure in
docs/MODEL.md or docs/VALIDATION.md no longer matches its report (`doc_numbers.py --fix` rewrites them).
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER = [  # (script, passes --refresh, failure is fatal)
    ("validate_plans_v2", False, True),
    ("build_core", False, True),
    ("policy_study", False, True),          # before report_numbers: it calibrates the 2031 range
    ("report_numbers", False, True),
    ("build_satellite", True, True),
    ("factor_evidence", False, True),
    ("rate_path_study", False, True),
    ("validate_model", False, True),        # after build_satellite: its HRP check reads the selection
    ("wins_rebalance", True, True),         # after report_numbers: it reads the core weights
    ("wins_ladder_check", False, False),
    # studies quoted in the docs (each reads the headline ESG through growth.scoring.esg_params)
    ("fx_variants", False, True),
    ("taiwan_fx_corr", False, True),
    ("satellite_oos", False, True),         # after build_satellite
    ("satellite_risk_sensitivity", False, True),
    ("stock_rate_corr", False, True),
    ("crash_comovement", False, True),
    ("corr_shrink_oos", False, True),
    ("tracking_error_oos", False, True),
    ("ladder_premium", False, True),
    ("fx_horizon", False, True),
    ("equity_horizon", False, True),
    ("vol_proxy_check", False, True),
    ("taiwan_drift_study", False, True),
    ("fx_hedge_frontier", False, True),
    ("strips_reserve", False, True),        # a reserve outside WInS (STRIPS at mid and ask)
    ("policy_robust", False, True),         # IPS under 11 shifts (the top policies come from the last policy_search)
    ("episode_stress", False, True),        # named crises after the lock (docs/VALIDATION.md section 7)
    ("doc_numbers", False, True),           # last: every quoted figure against its report
]


def refresh_market_data():
    import pandas as pd

    from lgm.asof import CURVE_DATE
    from lgm.backtest import PROXY
    from lgm.data import fed, fred, treasury, yahoo
    from lgm.growth.universe import BOND, CORE

    year = int(CURVE_DATE[:4])
    selected = pd.read_csv(ROOT / "reports" / "satellite_selected.csv", index_col=0).index.tolist()
    tickers = sorted({g.history for g in CORE} | {BOND.etf, "VTI", "VEA", "VWO", *PROXY.values(), *selected})
    steps = [(f"Treasury nominal {y}", lambda y=y: treasury.fetch_year(y, refresh=True)) for y in (year - 1, year)]
    steps += [(f"Treasury real {y}", lambda y=y: treasury.real_year(y, refresh=True)) for y in (year - 1, year)]
    steps += [("FRED CPI", lambda: fred.cpi(refresh=True)), ("Fed H.10 USD/TWD", lambda: fed.usd_twd(refresh=True)),
              ("Fed Kim-Wright", lambda: fed.kim_wright(refresh=True))]
    steps += [(f"Yahoo {t}", lambda t=t: yahoo.history(t, start="2000-01-01", interval="1mo", refresh=True)) for t in tickers]
    failed = []
    for label, fetch in steps:
        try:
            fetch()
        except Exception as e:                      # one unreachable source must not stop the rest
            failed.append(label)
            print(f"  {label}: kept the cached copy ({type(e).__name__}: {str(e)[:80]})")
        if label.startswith("Yahoo"):
            time.sleep(0.3)
    print(f"refreshed {len(steps) - len(failed)} of {len(steps)} sources" + (f"; stale: {', '.join(failed)}" if failed else ""))


def main(refresh: bool = False) -> int:
    if refresh:
        refresh_market_data()
    for name, takes_refresh, fatal in ORDER:
        args = [sys.executable, str(ROOT / "scripts" / f"{name}.py")] + (["--refresh"] if refresh and takes_refresh else [])
        t0 = time.time()
        done = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
        print(f"{name:<20} exit {done.returncode}  {time.time() - t0:5.0f}s")
        if done.returncode and fatal:
            print(done.stdout[-2000:], done.stderr[-4000:], sep="\n")
            return done.returncode
        if name == "wins_ladder_check":
            print("  " + done.stdout.strip().splitlines()[-1] if done.returncode == 0 else
                  "  " + "\n  ".join(done.stdout.strip().splitlines()[-3:]))
    return 0


if __name__ == "__main__":
    sys.exit(main(refresh="--refresh" in sys.argv))
