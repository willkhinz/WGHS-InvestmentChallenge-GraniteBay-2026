# r7-te findings: the core's 1.30% tracking error, corrected out of sample

`scripts/corr_shrink_oos.py` (`reports/corr_shrink_oos.csv`) finds that the generator's zero-target
correlation estimate understates the core's active risk against the market out of sample: the mean log
error, forecast over realised, is -10.2% over the next 36 months and -19.0% over 72 months on the
7-fund panel, and -10.8% and -19.0% on the 9-fund panel. `scripts/tracking_error_oos.py` applies the
inverse of that bias, `exp(-active_risk_bias)`, to the core's headline tracking error (1.30%) and
volatility (15.18%) in `reports/report_numbers.json`, and writes `reports/tracking_error_oos.csv`.
Bias is a mean log error, so a negative value means the forecast was too low.

| Funds | Horizon | Active-risk bias | Tracking error | Corrected | Market-vol bias | Core volatility | Corrected |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 36 m | -10.2% | 1.30% | 1.44% | +0.3% | 15.18% | 15.13% |
| 7 | 72 m | -19.0% | 1.30% | 1.57% | -0.4% | 15.18% | 15.24% |
| 9 | 36 m | -10.8% | 1.30% | 1.45% | +1.1% | 15.18% | 15.01% |
| 9 | 72 m | -19.0% | 1.30% | 1.57% | +0.7% | 15.18% | 15.08% |

All numbers in the table are printed by `scripts/tracking_error_oos.py`; the CSV carries the same figures
at six decimals. The market-volatility bias is applied to the core's volatility only as a comparison: it
is the error the same out-of-sample test found in the market's volatility, not in the core's, so it
shows what a volatility correction of that size would do, not a correction the core needs.

The 1.30% should be quoted as a point estimate conditional on the generator's correlation estimate, with
the out-of-sample correction alongside: about 1.4-1.45% if the relevant horizon is three years and 1.6%
if it is six. The market-volatility correction moves the core's 15.18% volatility by less than 0.2
percentage points in either direction, so the tracking-error correction, not a volatility rescaling, is
the one that matters.
