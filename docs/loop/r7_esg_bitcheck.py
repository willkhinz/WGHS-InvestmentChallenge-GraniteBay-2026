"""Fingerprint the ESG output under three configurations, for comparing two versions of esg.py.

Run with PYTHONPATH=<tree>/src from inside <tree>. Prints one line per configuration and field:
`<config> <field> <sha256 of the array bytes>`. Two trees whose esg.py differ only in validation
print identical lines. The configs: the headline parameters; the same with GARCH(1,1) on; the same
with the Taiwan cost innovations correlated with US CPI instead of USD/TWD (the two correlation
options are exclusive). 2,000 scenarios, seed 11.
"""
import dataclasses as dc
import hashlib

import numpy as np

from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params

r = build_core()
base = esg_params(r["cal"], r["table"]["bl_geo_total"].values)
configs = {
    "headline": base,
    "garch": dc.replace(base, eq_garch=(0.08, 0.90)),
    "cost_cpi_corr": dc.replace(base, tw_cost_fx_corr=None, tw_cost_corr=0.3),
}
for name, p in configs.items():
    sc = simulate(p, n=2000, seed=11)
    for f in dc.fields(sc):
        v = getattr(sc, f.name)
        if isinstance(v, np.ndarray):
            print(name, f.name, hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest()[:16])
