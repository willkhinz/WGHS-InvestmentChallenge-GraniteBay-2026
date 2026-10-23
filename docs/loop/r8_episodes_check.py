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
