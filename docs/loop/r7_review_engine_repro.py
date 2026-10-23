"""Reproducer for docs/loop/r7_review_engine_findings.md (review of f6e0613..b8c0036).

Run from the worktree root, with the repo's virtualenv:

    PYTHONPATH=$PWD/src /Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python \
        docs/loop/r7_review_engine_repro.py

Prints one line per finding: `F<k> REPRO|pass -- claim -- expected vs actual`.
F1/F3/F4 are behaviour changes for valid input; F2 is a misleading error message.
"""
import dataclasses as dc

import numpy as np

from lgm import engine
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS

r = build_core()
p = esg_params(r["cal"], r["table"]["bl_geo_total"].values)
st = dc.replace(IPS, region_weights=tuple(r["w_bl"]))
er = tuple(g.expense_ratio for g in CORE)
sc = simulate(p, n=40, seed=7)
cfg = engine.EngineConfig(eq_er=er)
res = engine.run(st, sc, cfg, snapshot_2031=True)

# F1: conditional_2031_band validates `percentiles` as tuple(...) (engine.py:673) but loops
# over the original (engine.py:687), so a one-shot iterator is exhausted by validation.
# Expected: the same percentile keys for any iterable. Old code (f6e0613) looped only once.
want = {"p5", "p50", "p95"}
gen = engine.conditional_2031_band(st, sc, res, p, k=3, n_inner=50, cfg=engine.EngineConfig(eq_er=er),
                                   percentiles=(x for x in (5, 50, 95)))
lst = engine.conditional_2031_band(st, sc, res, p, k=3, n_inner=50, cfg=engine.EngineConfig(eq_er=er),
                                   percentiles=[5, 50, 95])
gen_keys, lst_keys = set(gen), set(lst)
ok = not want <= gen_keys and want <= lst_keys and {"p5", "p50", "p95"} <= lst_keys
print(f"F1 {'REPRO' if ok else 'pass'} -- band percentile iterator exhausted by validation -- "
      f"expected {sorted(want)} for both, got generator {sorted(gen_keys)} / list {sorted(lst_keys)}")

# F2: a 2-D eq_log is rejected by _finite_path with the placeholder shape (n, None, None); the
# explicit check at engine.py:374-375 (which would say "(n, months, equities)") is unreachable.
bad2d = dc.replace(sc, eq_log=sc.eq_log[:, :, 0])
try:
    engine.run(st, bad2d, engine.EngineConfig(eq_er=er))
    msg = "no error"
except ValueError as exc:
    msg = str(exc)
ok = "None" in msg and "months" not in msg
print(f"F2 {'REPRO' if ok else 'pass'} -- 2-D eq_log error names placeholder axes -- "
      f"expected an error naming (n, months, equities), got: {msg}")

# F3: run() assigns cfg.eq_er in place (engine.py:390) without copying the caller's config,
# so a list input becomes a tuple of numpy floats. Expected: caller's config unchanged.
cfg3 = engine.EngineConfig(eq_er=list(er))
before = (type(cfg3.eq_er).__name__, type(cfg3.eq_er[0]).__name__)
engine.run(st, sc, cfg3)
after = (type(cfg3.eq_er).__name__, type(cfg3.eq_er[0]).__name__)
ok = before == ("list", "float") and after != before
print(f"F3 {'REPRO' if ok else 'pass'} -- run() mutates caller cfg.eq_er -- "
      f"expected (list, float) unchanged, got {before} -> {after}")

# F4: _finite_path converts array-likes but run() keeps using sc.<field>, so a list-valued
# fx_log / tw_cost_log passes validation and crashes later with a raw TypeError
# (engine.py:399-400). Expected: reject with scenarios.<field> ValueError, as ndarrays are.
for field in ("fx_log", "tw_cost_log"):
    bad = dc.replace(sc, **{field: getattr(sc, field).tolist()})
    try:
        engine.run(st, bad, engine.EngineConfig(eq_er=er))
        msg = "no error"
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
    ok = msg.startswith("TypeError")
    print(f"F4 {'REPRO' if ok else 'pass'} -- list {field} passes validation then crashes -- "
          f"expected ValueError 'scenarios.{field}...', got {msg}")

# Control: `resid` is also converted-and-discarded, but nothing reads it after validation,
# so the same input shape is accepted there. Expected: valid input runs either way.
resid_list = dc.replace(sc, resid=sc.resid.tolist())
engine.run(st, resid_list, engine.EngineConfig(eq_er=er))
print("F4 note -- same list input for `resid` runs fine: it is validated but never used by run()")
