"""Tests for Taiwan official price and construction cost data adapters."""
from __future__ import annotations

import numpy as np
import pandas as pd

from lgm.data import taiwan


def test_taiwan_cci_shape_and_no_gaps():
    s = taiwan.cci()
    assert isinstance(s, pd.Series)
    assert s.name == "TW_CCI"
    assert len(s) == 429
    assert s.index[0] == pd.Timestamp("1991-01-31")
    assert s.index[-1] == pd.Timestamp("2026-09-30")
    assert not s.isna().any()

    # Verify no missing months: exactly one observation per month-end
    full_idx = pd.date_range(s.index[0], s.index[-1], freq="ME")
    assert len(s) == len(full_idx)
    assert (s.index == full_idx).all()


def test_taiwan_cci_cross_check_values():
    s = taiwan.cci()

    # 1. New Taipei City official report & DGBAS spliced table cross-checks (year-end levels)
    assert np.isclose(s.loc["2021-12-31"], 103.25)
    assert np.isclose(s.loc["2022-12-31"], 107.92)
    assert np.isclose(s.loc["2023-12-31"], 109.88)
    assert np.isclose(s.loc["2024-12-31"], 111.84)
    assert np.isclose(s.loc["2025-12-31"], 112.86)

    # 2. Latest reading from September 2026 release
    assert np.isclose(s.loc["2026-09-30"], 120.26)

    # 3. Base year definition: 2021 (ROC 110) annual average equals exactly 100.00
    s_2021 = s.loc["2021-01-31":"2021-12-31"]
    assert len(s_2021) == 12
    assert np.isclose(s_2021.mean(), 100.00, atol=1e-3)


def test_taiwan_cpi_shape_and_values():
    cpi = taiwan.cpi()
    assert isinstance(cpi, pd.Series)
    assert cpi.name == "TW_CPI"
    assert len(cpi) == 813
    assert cpi.index[0] == pd.Timestamp("1959-01-31")
    assert cpi.index[-1] == pd.Timestamp("2026-09-30")
    assert not cpi.isna().any()

    # No gaps
    full_idx = pd.date_range(cpi.index[0], cpi.index[-1], freq="ME")
    assert len(cpi) == len(full_idx)
    assert (cpi.index == full_idx).all()

    # Base year check
    cpi_2021 = cpi.loc["2021-01-31":"2021-12-31"]
    assert len(cpi_2021) == 12
    assert np.isclose(cpi_2021.mean(), 100.00, atol=1e-3)

    # Cross-check recent points
    assert np.isclose(cpi.loc["2025-12-31"], 110.24)
    assert np.isclose(cpi.loc["2026-09-30"], 112.82)


def test_taiwan_sub_indices():
    mat = taiwan.materials()
    srv = taiwan.services()
    assert len(mat) == 429
    assert len(srv) == 429
    assert mat.index[0] == srv.index[0] == pd.Timestamp("1991-01-31")
    assert mat.index[-1] == srv.index[-1] == pd.Timestamp("2026-09-30")

    # Both sub-indices use base year 2021 = 100
    assert np.isclose(mat.loc["2021-01-31":"2021-12-31"].mean(), 100.00, atol=1e-3)
    assert np.isclose(srv.loc["2021-01-31":"2021-12-31"].mean(), 100.00, atol=1e-3)


def test_taiwan_costs_proposal_does_not_overwrite_live_config():
    """The r1 calibration writes a proposal; it must not replace config/taiwan.yaml."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "taiwan_costs.py"
    spec = importlib.util.spec_from_file_location("_taiwan_costs_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.CONFIG_PATH == mod.ROOT / "config" / "taiwan_costs_proposal.yaml"
    assert mod.CONFIG_PATH != mod.ROOT / "config" / "taiwan.yaml"
