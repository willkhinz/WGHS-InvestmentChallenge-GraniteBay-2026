"""Tests for scripts/tracking_error_oos.py and reports/tracking_error_oos.csv."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tracking_error_oos", ROOT / "scripts" / "tracking_error_oos.py")
te = importlib.util.module_from_spec(spec)
spec.loader.exec_module(te)

NUMBERS = {"core": {"tracking_error": 0.013, "volatility": 0.1518}}


def test_bias_of_log_0_9_divides_the_tracking_error(tmp_path):
    bias = float(np.log(0.9))
    path = tmp_path / "corr_shrink_oos.csv"
    pd.DataFrame([
        {"funds": 7, "horizon_m": 36, "candidate": te.TARGET,
         "active_risk_bias": bias, "market_vol_bias": bias},
        {"funds": 9, "horizon_m": 72, "candidate": te.TARGET,
         "active_risk_bias": bias, "market_vol_bias": bias},
        {"funds": 7, "horizon_m": 36, "candidate": "sample",
         "active_risk_bias": -1.0, "market_vol_bias": -1.0},
    ]).to_csv(path, index=False)

    out = te.build(NUMBERS, pd.read_csv(path))

    assert len(out) == 2  # only the zero-target rows
    assert np.allclose(out["tracking_error_corrected"], 0.013 / 0.9)
    assert np.allclose(out["volatility_corrected"], 0.1518 / 0.9)


def test_main_writes_one_row_per_panel_and_horizon(tmp_path):
    out_path = tmp_path / "tracking_error_oos.csv"
    te.main(out=out_path)

    out = pd.read_csv(out_path)
    assert list(zip(out["funds"], out["horizon_m"])) == [(7, 36), (7, 72), (9, 36), (9, 72)]
    numbers = json.loads((ROOT / "reports" / "report_numbers.json").read_text())
    assert np.allclose(out["tracking_error"], numbers["core"]["tracking_error"])
    assert np.allclose(out["tracking_error_corrected"],
                       out["tracking_error"] * np.exp(-out["active_risk_bias"]), rtol=1e-4)
