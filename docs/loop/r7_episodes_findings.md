# r7-episodes findings: named historical starts just after the lock

Numbers come from `scripts/episode_stress.py` (`reports/episode_stress.csv`); the CSV is the
machine-readable version of the table below. The table rounds to one decimal and shows the funded
share as a percentage; the CSV has the full precision and the raw share. The script builds the core
and the IPS exactly as
`scripts/report_numbers.py` does, and the history paths exactly as `validate_model.backtest()` does:
both as they happened (`recentre=None`) and re-centred on the BL expected returns
(`recentre=core["table"]["bl_geo_total"].values`).

For each named episode the start is chosen so the episode's first bad month lands at model month 3
(February 2027), one month after the January 2027 lock. The table does not pick the worst start for an
episode; it picks the start that puts the episode just after the lock. The 2022 sell-off has no full
six-year path, so it is reported as unavailable and then tested with a 12-month splice. Run
`PYTHONPATH=src $PY scripts/episode_stress.py` to regenerate the CSV and print the table.

## The table

| Path set | Episode | Start | First bad month | Facility (Jan 2033) | 85% contribution | Floor (Jan 2031) | Funded | Real facility (2027 TWD) | 6y core equity | Worst 12m |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Simulated (20,000, seed 11) | Median | — | — | $196,989.2 | $167,440.8 | $117,578.8 | 100.0% | $166,547.4 | +44.2% | −18.0% |
| Simulated (20,000, seed 11) | 5th percentile | — | — | $146,101.9 | $124,186.6 | $88,273.7 | 100.0% | $110,678.1 | −22.6% | −32.3% |
| History as it happened | 2008 financial crisis | 2008-05-31 | 2008-09-30 | $207,882.5 | $176,700.1 | $115,308.0 | 100.0% | $216,285.3 | +51.0% | −19.6% |
| History as it happened | 2011 euro crisis | 2011-04-30 | 2011-08-31 | $216,473.0 | $184,002.0 | $129,383.2 | 100.0% | $230,814.6 | +63.9% | −12.4% |
| History as it happened | 2015-16 China and oil sell-off | 2015-04-30 | 2015-08-31 | $240,088.3 | $204,075.1 | $137,051.5 | 100.0% | $180,048.5 | +87.3% | −14.1% |
| History as it happened | COVID | 2019-10-31 | 2020-02-29 | $213,890.7 | $181,807.1 | $123,523.8 | 100.0% | $177,362.1 | +83.7% | −19.7% |
| History as it happened | Worst path | 2008-10-31 | 2009-02-28 | $136,195.1 | $115,765.8 | $77,833.0 | 100.0% | $123,083.2 | +120.9% | −10.7% |
| History re-centred on BL expected returns | 2008 financial crisis | 2008-05-31 | 2008-09-30 | $196,935.1 | $167,394.8 | $110,550.7 | 100.0% | $204,895.5 | +34.2% | −21.1% |
| History re-centred on BL expected returns | 2011 euro crisis | 2011-04-30 | 2011-08-31 | $206,033.9 | $175,128.8 | $124,384.1 | 100.0% | $219,683.9 | +45.7% | −14.1% |
| History re-centred on BL expected returns | 2015-16 China and oil sell-off | 2015-04-30 | 2015-08-31 | $227,946.8 | $193,754.8 | $131,558.6 | 100.0% | $170,943.3 | +66.5% | −15.8% |
| History re-centred on BL expected returns | COVID | 2019-10-31 | 2020-02-29 | $203,858.3 | $173,279.5 | $118,975.3 | 100.0% | $169,043.1 | +63.3% | −21.3% |
| History re-centred on BL expected returns | Worst path | 2008-10-31 | 2009-02-28 | $129,359.3 | $109,955.4 | $74,908.3 | 100.0% | $116,905.5 | +96.3% | −12.4% |
| History paths | 2022 stock-and-bond sell-off | — | 2022-01-31 | — | — | — | — | — | — | — |
| Simulated with 2022 spliced | 2022 sell-off, median | 2021-09-30 | 2022-01-31 | $207,397.8 | $176,288.2 | $125,846.0 | 100.0% | $194,263.7 | +14.7% | −18.3% |

All rows are available except the 2022 full path (`available=0`, `n_paths=0`). The simulated rows use
20,000 scenarios; each historical row is one path. `Funded` is the share of paths in which every
payment is funded. For the simulated rows, the equity columns are the median (or 5th percentile) of
the per-path six-year cumulative return and the per-path worst 12-month return. The worst path is the
lowest January 2033 facility among the 184 historical starts in each path set, not the lowest equity
return. The 2022 full path is unavailable because the last start with 74 months of history is
2020-07-31; the table does not substitute another date. `zero5_jan2027` and `zero5_jan2031` in the CSV are each path's 5-year zero rate at the two lock dates.

## 2008 financial crisis

The start is 2008-05-31, so the lock is struck just before the crisis and the first bad month is
2008-09-30. As it happened, the facility is $207,882.5, the contribution is $176,700.1, the floor is
$115,308.0, the real facility is $216,285.3, six-year core equity is +51.0%, and the worst 12 months
are −19.6%; all payments are funded. Re-centred, the facility is $196,935.1, the contribution is
$167,394.8, the floor is $110,550.7, the real facility is $204,895.5, six-year equity is +34.2%, and
the worst 12 months are −21.1%. The facility is above the simulated median as it happened and
essentially at the median after recentring, even though the worst 12 months are worse than the
simulated median's −18.0%. The lock is affordable because it is struck before the crash. The first
deposit locks 98.8% of the ladder's present value (vs a 99.9% median across paths), so the January 2031
top-up takes more from the growth sleeve than on the median path. The as-it-happened facility is high
because the six-year window includes the post-crash recovery; recentring removes the unusually strong
US mean and brings the facility back to the median.

## 2011 euro crisis

The start is 2011-04-30, so the first bad month is 2011-08-31. As it happened, the facility is
$216,473.0, the contribution is $184,002.0, the floor is $129,383.2, the real facility is $230,814.6,
six-year core equity is +63.9%, and the worst 12 months are −12.4%; all payments are funded.
Re-centred, the facility is $206,033.9, the contribution is $175,128.8, the floor is $124,384.1, the
real facility is $219,683.9, six-year equity is +45.7%, and the worst 12 months are −14.1%. The euro
crisis is a sharp but short drawdown: the worst 12 months are the mildest among the named episodes as
it happened, and the six-year window captures the subsequent US recovery. The facility is above the
simulated median in both path sets. The real facility is the highest in the table, even though the
nominal facility is below the 2015 path's: the real facility also depends on the path's Taiwan cost
index and FX, and those pieces are more favourable over this window than over the 2015-2021 window.

## 2015-16 China and oil sell-off

The start is 2015-04-30, so the first bad month is 2015-08-31. As it happened, the facility is
$240,088.3, the contribution is $204,075.1, the floor is $137,051.5, the real facility is $180,048.5,
six-year core equity is +87.3%, and the worst 12 months are −14.1%; all payments are funded.
Re-centred, the facility is $227,946.8, the contribution is $193,754.8, the floor is $131,558.6, the
real facility is $170,943.3, six-year equity is +66.5%, and the worst 12 months are −15.8%. This is
the highest nominal facility in the table, but not the highest real facility: the six-year window
runs through the long US bull market and the COVID rebound, and ends before the 2022 sell-off, while
the real deflator is less favourable over the same window. The sell-off itself is short, and the facility
is above the simulated median in both path sets. The as-it-happened equity return is the highest
among the four named episodes, and recentring lowers it without changing the ranking of the facility.

## COVID

The start is 2019-10-31, so the first bad month is 2020-02-29. As it happened, the facility is
$213,890.7, the contribution is $181,807.1, the floor is $123,523.8, the real facility is $177,362.1,
six-year core equity is +83.7%, and the worst 12 months are −19.7%; all payments are funded.
Re-centred, the facility is $203,858.3, the contribution is $173,279.5, the floor is $118,975.3, the
real facility is $169,043.1, six-year equity is +63.3%, and the worst 12 months are −21.3%. The COVID
crash is sharp and fast, and its worst 12 months are close to the 2008 episode's; the
re-centred worst 12 months are the worst among the named episodes. The recovery is strong enough that
the six-year equity return and the facility are above the simulated median in both path sets, even
though the window includes the 2022 sell-off.

## The worst path

The worst path starts 2008-10-31; the first bad month is 2009-02-28. As it happened, the facility is
$136,195.1, the contribution is $115,765.8, the floor is $77,833.0, the real facility is $123,083.2,
six-year core equity is +120.9%, and the worst 12 months are −10.7%; all payments are funded.
Re-centred, the facility is $129,359.3, the contribution is $109,955.4, the floor is $74,908.3, the
real facility is $116,905.5, six-year equity is +96.3%, and the worst 12 months are −12.4%. This is
the lowest facility in each path set, and it is below the simulated 5th percentile ($146,101.9), so
the simulated percentile table does not bound the historical lock risk. It is not the worst equity
path: the six-year window starts near the market bottom, so the equity return is the highest in the
table and the worst 12 months are the mildest. The facility is low because the January 2027 lock is
struck after the crash, when rates are low: the first deposit locks a smaller share of the payments,
and the January 2031 top-up takes more from the growth sleeve. The facility and the equity
drawdown rank differently.

## 2022: unavailable full path, and the 12-month splice

The 2022 stock-and-bond sell-off has no full six-year path: the last start with 74 months of history
is 2020-07-31, so a start that puts January 2022 at model month 3 would need history beyond the data.
The table reports it as unavailable and does not substitute another date.

The splice adds one row. It takes the simulated scenarios and replaces their months 3-14 shocks with
the actual January-December 2022 equity, rate, and FX moves, leaving the post-2022 simulated months
unchanged. The implementation uses a historical segment from 2021-09-30 to 2022-12-31.
Because `eq_log[k]` is the return from month `k` to month `k+1`, `seg.eq_log[0, 3:15]` is exactly
January-December 2022. For the curve, the script sets each month's level from the previous month plus
the historical change, then shifts the post-splice path by the cumulative difference at the splice
boundary, so the simulated future shape is preserved. The FX path uses the same difference-in-differences
construction. The inflation and Taiwan-cost paths are unchanged.

The spliced median facility is $207,397.8, the contribution is $176,288.2, the floor is $125,846.0,
the real facility is $194,263.7, six-year core equity is +14.7%, and the worst 12 months are −18.3%;
all payments are funded. This is the one row where the facility is above the unspliced simulated
median ($196,989.2) while six-year equity is far below the unspliced median (+44.2%). The nominal
gain is a rate effect: rate-only adds +$16,534.1, partly offset by equity-only −$5,790.3; FX-only
adds +$0.0 to the nominal facility but moves the real facility to $184,699.3 (vs the unspliced
median $166,547.4). The splice is a counterfactual, not a historical six-year path: it replaces only
the first 12 months' shocks and keeps the simulated post-2022 months, so it should not be read as a
fifth episode.

## 2022 splice decomposition

To isolate the drivers of the facility gain, the script also tests splicing each component separately.
Splicing only the 2022 equity moves gives a median facility of $191,198.9 (−$5,790.3 vs the unspliced
median), only the rate moves gives $213,523.3 (+$16,534.1), and only the FX moves gives $196,989.2
(+$0.0). The rate-only splice reproduces nearly the full facility gain, while the equity-only splice
reduces the facility and the FX-only splice has no effect on the nominal facility (it only affects the
real facility through TWD depreciation). The ladder is about 99.95% locked in January 2027, so the
2022 rise in rates after that makes the January 2031 floor and the bond sleeve cheaper rather than
hurting the reserve. The equity loss is real, but the liability-side gain from cheaper floor purchases
dominates.

## What the table says

- Every named episode, the worst path, and the spliced 2022 row fund every payment. The lowest
  facility in the table is the recentred worst path at $129,359.3; the as-it-happened worst is
  $136,195.1, and the simulated 5th percentile is $146,101.9.
- The four named episodes are above the simulated median as it happened; after recentring, 2008 is
  essentially at the median ($196,935.1 vs $196,989.2) and the other three are above. A named crisis
  is not, by itself, a facility tail.
- The worst facility is the October 2008 start, not because of the equity crash but because rates fell
  after that start: the path's 5-year zero rate is already 3.65% at the January 2027 lock (4.95% on the
  median simulated path), so the first deposit locks only 84.95% of the ladder's present value (99.95%
  on the median), and the rate is 3.03% at the January 2031 top-up. A fall in rates after a well-funded
  lock is not enough on its own: the 2008 crisis path's rate falls from 4.85% to 2.29% with 98.78%
  locked, and its facility is above the median. Its six-year
  equity return is the highest in the table, and its worst 12 months are the mildest: facility and
  equity drawdown rank differently.
- The 2022 splice nominal gain is a rate effect: rate-only adds +$16,534.1 of the +$10,408.6 total,
  partly offset by equity-only −$5,790.3; FX-only adds +$0.0 to the nominal facility but moves the
  real facility to $184,699.3 (vs the unspliced median $166,547.4). It is the clearest reminder that
  the facility is a liability-side metric, not a return metric.
- The episodes are four single historical paths, not a probability distribution; the re-centred set
  is a counterfactual with the BL mean returns; the 2022 splice is a 12-month stress, not a full
  path; and the strategy is held fixed throughout. The table is a set of named stresses, not a
  forecast.
