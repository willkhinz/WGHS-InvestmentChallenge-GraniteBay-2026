"""How wrong is the core's 1.30% tracking error, judged out of sample?

Usage: python scripts/tracking_error_oos.py
`scripts/corr_shrink_oos.py` re-estimates the generator's equity correlations on rolling 109-month
windows and scores them on the next 36 or 72 months. The zero-target estimate (the generator's default)
understates the core's active risk against the market, in log terms, by `active_risk_bias` (negative
means the forecast was too low). This rescales the headline tracking error in
reports/report_numbers.json by exp(-active_risk_bias) for each panel (7 or 9 funds) and horizon (36 or
72 months), and rescales the core's volatility by exp(-market_vol_bias) under the market-volatility
bias, so the two corrections can be compared. Writes reports/tracking_error_oos.csv.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NUMBERS = ROOT / "reports" / "report_numbers.json"
OOS = ROOT / "reports" / "corr_shrink_oos.csv"
OUT = ROOT / "reports" / "tracking_error_oos.csv"
TARGET = "zero target, LW intensity"


def rescale(value: float, log_bias: float) -> float:
    """Undo a forecast/realised log bias: realised = forecast * exp(-bias)."""
    return float(value * np.exp(-log_bias))


def build(numbers: dict, oos: pd.DataFrame) -> pd.DataFrame:
    """Rescale the headline tracking error and volatility for every panel and horizon."""
    te, vol = float(numbers["core"]["tracking_error"]), float(numbers["core"]["volatility"])
    zero = oos[oos["candidate"] == TARGET]
    rows = []
    for row in zero.itertuples(index=False):
        rows.append({
            "funds": int(row.funds), "horizon_m": int(row.horizon_m),
            "active_risk_bias": float(row.active_risk_bias),
            "tracking_error": te, "tracking_error_corrected": rescale(te, row.active_risk_bias),
            "market_vol_bias": float(row.market_vol_bias),
            "volatility": vol, "volatility_corrected": rescale(vol, row.market_vol_bias),
        })
    return pd.DataFrame(rows)


def main(out: Path = OUT):
    d = build(json.loads(NUMBERS.read_text()), pd.read_csv(OOS))
    d.round(6).to_csv(out, index=False)
    show = d.copy()
    for c in ("tracking_error", "tracking_error_corrected", "volatility", "volatility_corrected"):
        show[c] = (100 * show[c]).map("{:.2f}%".format)
    for c in ("active_risk_bias", "market_vol_bias"):
        show[c] = (100 * show[c]).map("{:+.1f}%".format)
    print(f"Core tracking error {100 * d['tracking_error'].iloc[0]:.2f}% and volatility "
          f"{100 * d['volatility'].iloc[0]:.2f}% ({NUMBERS.relative_to(ROOT)}, zero target)")
    print(show.to_string(index=False))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
