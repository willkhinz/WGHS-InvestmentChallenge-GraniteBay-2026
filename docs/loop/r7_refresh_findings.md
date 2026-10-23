# r7-refresh findings: a refresh dry run on the 2026-10-22 curve

Run 2026-10-22 18:45-18:48 PDT on branch `r7-refresh` (from `improve`). `git status --short` was clean
before the run. Nothing under `src/` or `scripts/` was changed. The tree was restored afterwards; this
document is the only committed change.

## Dates set (`config/asof.yaml`, not committed)

- `curve_date: 2026-10-22`. The live 2026 Treasury par CSV had rows for both 2026-10-21 and 2026-10-22
  when fetched at 18:45 PDT; 2026-10-22 is the latest.
- `data_end: 2026-09-30` (unchanged). The September month-end is still the latest published: FRED CPI's
  last observation is 2026-09-01, so October is not out.
- `price_date: 2026-10-22`. Yahoo has daily closes through 2026-10-22.

## Sources

`scripts/run_all.py --refresh` printed:

    refreshed 57 of 57 sources

There is no `stale:` suffix, so no source failed. The 57 are Treasury nominal and real for 2025 and
2026 (4), FRED CPI (1), Fed H.10 USD/TWD (1), Fed Kim-Wright (1) and 50 Yahoo symbols (50). The 2026
Treasury files and H.10 changed; the 2025 Treasury files, CPI and Kim-Wright were byte-identical after
the re-download. The WInS and satellite scripts also refetched daily closes: 49 daily and 50 monthly
Yahoo files changed. All 102 rewritten files are listed with SHA-256 in the appendix.

## Scripts that exited non-zero

### `wins_ladder_check` (exit 1, non-fatal)

`scripts/run_all.py:27` marks this check non-fatal; `run_all.py` printed its last three lines:

    SHORTFALL in 2034, 2035, 2036, 2037, 2038, 2039; cheapest top-up:
      add $298 of IBTO (13 shares)
      add $4 of IBTP (1 shares)

The check itself (`scripts/wins_ladder_check.py`, no arguments) prints:

    cash waiting for a payment earns 0.0%
     payment  cash arriving  surplus after
        2033         40,261          6,927
        2034         25,987           -419  SHORT
        2035         33,328           -424  SHORT
        2036         33,340           -418  SHORT
        2037         33,362           -389  SHORT
        2038         33,631            -91  SHORT
        2039         33,314           -111  SHORT
        2040         33,661            217
        2041         33,349            233
        2042         34,031            931
    SHORTFALL in 2034, 2035, 2036, 2037, 2038, 2039; cheapest top-up:
      add $298 of IBTO (13 shares)
      add $4 of IBTP (1 shares)

**Cause.** The check values each ladder fund with `TermFund.growth_factor` at the current curve
(`src/lgm/instruments.py:153`), through `coverage()` at `scripts/wins_ladder_check.py:52`. The account it
reads is dated 2026-10-21 (`config/wins_account.yaml:2`): the holdings and fill prices are the Oct 21
trades. The Oct 22 curve is lower, so the same fund shares are projected to grow less and the 2034-2039
payments fall short. This is the documented workflow, not a code bug: `wins_rebalance.py` proposes
orders but places nothing (`scripts/wins_rebalance.py:38`), and the README says to update the account
after every trading session.

**Smallest fix (operational, no code change).** Execute the two ladder orders that
`scripts/wins_rebalance.py` prints first, then record them in `config/wins_account.yaml` (IBTO +13,
IBTP +1, cash -$329, `as_of: 2026-10-22`) and re-run `scripts/wins_ladder_check.py`. The rebalance
script's output (exit 0) is:

    closes of 2026-10-22; account as of 2026-10-21
    side symbol  shares  dollars
    Sell   ESGV     252  33980.0
    Sell   VSGX     290  22736.0
     Buy   IBTO      13    304.0
     Buy   IBTP       1     25.0
     Buy    VUG      98   8543.0
     Buy    VTV      74  16765.0
     Buy     VB      24   6928.0
     Buy    VGK     101   8767.0
     Buy   BBJP      47   3590.0
     Buy    EPP      28   1540.0
     Buy   BBCA      20   2101.0
     Buy   EMXC      46   4193.0
     Buy   MCHI      21   1029.0
     Buy   IBTM    1615  35619.0
    14 orders, $350 commissions, about $5,776 cash left

No `src/` or `scripts/` edit is needed. If the planner wants `run_all.py --refresh` to exit 0 without
trading, that is not possible: the check must compare the account it is given, and the account is one
day stale by construction.

### `doc_numbers` (exit 1, fatal)

The last 20 lines of its output:

    MISSING  MODEL      sensitivity row 2: '| Equity volatility | history since 2005 | x0.8 / x1.2 | +$5.5k / -$5.3k 5th pct |'
    MISSING  MODEL      sensitivity row 3: '| Equity correlations | shrunk toward zero | toward their average | -$80 median, -$1.1k 5th pct |'
    MISSING  MODEL      sensitivity row 4: '| Rates at the January 2027 lock | as today | 0.75 points lower / higher | -$36.2k / +$35.5k median |'
    MISSING  MODEL      sensitivity row 5: '| Cash awaiting a ladder payment | earns 3% | earns 0% (WInS pays none) | -$7.4k median |'
    MISSING  MODEL      sensitivity row 6: '| Expected rate path | unchanged | forwards less Kim-Wright term premium | -$289 median |'
    MISSING  MODEL      sensitivity row 7: '| Equity views | Black-Litterman posterior | equilibrium (views wrong) | -$727 median |'
    MISSING  MODEL      sensitivity row 8: '| Stock-rate correlation | -0.17 (2017-2026) | 2000-2021 regime (+0.28) | +$66 median, -$1.5k 5th pct |'
    MISSING  MODEL      sensitivity row 9: '| Ladder premium | constant 1.7% | moves with rates | +$60 median, +$598 5th pct |'
    MISSING  MODEL      sensitivity row 10: '| Stock satellite | none | 20% of equity, $25 trades | -$4.2k median |'
    MISSING  MODEL      sensitivity row 11: "| USD/TWD drift | none (random walk) | today's forward (-2.28% a year) | -$20.5k real median |"
    MISSING  MODEL      sensitivity row 12: '| Taiwan building-cost drift | 2.85% (1991-2026) | 3.78% (last ten years) | -$8.4k real median |'
    MISSING  MODEL      decision row 1: "| Growth mix and 2031 floor | 40% equity with a 100% floor instead of the IPS's 60% and 60%: median -$3.5k, 5th percentile +$7.8k, a 2031 floor worth $74.0k more at maturity; certainty equivalents within $0.4k at risk aversion 4 | How much the co-sponsors need promised in 2031 | Policy study |"
    MISSING  MODEL      decision row 2: '| Contribution share | 75%, 85% and 95% give typical contributions of $142k, $161k, $180k; Laura keeps $47k, $28k, $9k | Preference | Policy study |'
    MISSING  MODEL      decision row 3: '| Hedge USD/TWD | On the random walk every hedge lowers the real 5th percentile and median; if the forward were unbiased, at most +$3.6k on the 5th percentile | Evidence says do not hedge | USD/TWD |'
    MISSING  MODEL      decision row 4: '| Taiwan building-cost drift | The long-run average forecast six-year cost growth better in real time (RMSE 0.167 vs 0.222); the ten-year drift would mean -$8.4k of real median | Evidence supports the long-run average | Taiwan building costs |'
    MISSING  MODEL      decision row 5: '| Stock satellite | -$4.2k median at 20% with WInS commissions, +$0.5k without | A values choice, not a return one | Part 2b |'
    MISSING  MODEL      decision row 6: '| Reserve outside WInS | STRIPS need no reinvestment assumption and, at the retail ask, cost about what the WInS ladder costs assuming 3% (-0.10% vs +1.70% over zero-coupon value): $10.9k cheaper than making the WInS ladder certain, +$15.3k of median | Only if WInS rules do not bind | `scripts/strips_reserve.py` |'
    MISSING  MODEL      Taiwan drift effect: 'the real median by $8.4k (`scripts/fx_variants.py`'

    70 of 126 figures missing from the docs

**Cause.** The refresh moved 70 of the 126 figures that `docs/MODEL.md` and `docs/VALIDATION.md` quote
(59 MODEL and 11 VALIDATION lines, counted from the output above). The docs still quote the Oct 20
reports, so `scripts/doc_numbers.py` exits 1. This is the intended tripwire, not a bug.

**Smallest fix.** Run `scripts/doc_numbers.py --fix` (`scripts/doc_numbers.py:513-531`); it rewrites
every missing figure whose stale version occurs exactly once, then re-checks. I replayed its matcher
(`scripts/doc_numbers.py:507-521`) over the current docs: all 70 stale versions occur exactly once, so
one `--fix` pass places all 70 and the re-check should print `0 of 126 figures missing`. This edits the
two shared docs, which are the planner's to change (COMMON rule 3).

## New headline (refreshed `reports/report_numbers.json`, `plan` block)

| figure | refreshed | committed (HEAD) |
|---|---:|---:|
| median | $189,615.5 | $196,989.2 |
| 5th percentile | $140,106.8 | $146,101.9 |
| real median | $160,301.7 | $166,547.4 |

All six numbers are the `plan` block written by `scripts/report_numbers.py`; the committed column is
`git show HEAD:reports/report_numbers.json`.

## Doc figures stale

`scripts/doc_numbers.py` printed `70 of 126 figures missing from the docs`.

## Dry-run hygiene

- No file under `src/` or `scripts/` was modified.
- `git checkout -- .` restored `config/asof.yaml`, the 24 reports and the tracked data files;
  `git clean -fd data/ reports/` removed the untracked refresh files (including `IBTP_1d.csv`).
- After the restore, `scripts/doc_numbers.py` printed `0 of 126 figures missing from the docs` and
  `python -m pytest` printed `393 passed in 36.83s`.
- The only committed change is this document. The downloaded files are gone; their URLs, download date
  (2026-10-22) and SHA-256 are below.

## Appendix: downloaded-file manifest (2026-10-22, deleted by the restore)

URLs: Treasury nominal and real
`https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/<year>/all?type=daily_treasury_yield_curve` (real: `type=daily_treasury_real_yield_curve`);
FRED `https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS,CPILFENS`;
H.10 `https://www.federalreserve.gov/releases/h10/hist/dat00_ta.htm`;
Kim-Wright `https://www.federalreserve.gov/data/yield-curve-tables/feds200533.csv`;
Yahoo `https://query1.finance.yahoo.com/v8/finance/chart/<symbol>` (interval `1d` or `1mo`).

Re-downloaded but unchanged (not in `git status`):

    a4017970023f9c29284dd300dd85070923183b4b0160f9f8522fff62dfb0d607  data/raw/fred_cpi.csv
    f2fad3425132226f3ac2838b89314f5a192c395f06d8388dabe93c7cba6dca2b  data/raw/fed/kim_wright_feds200533.csv
    cf2fa3da7f160384b63d2ead698532b1d76cd9f789ce4911e2304db85b14e6d5  data/raw/treasury_par_2025.csv
    d3d3131c41e1f93f4661d227ce7079049d51888b395aaff863b6ad8e08838b64  data/raw/treasury_real_2025.csv

Changed (102 files):

    513d02c5e3afea6d411542dd1ed1624845d36ee75ac45c1ab090206992fbeb4b  data/raw/fed/h10_dat00_ta.htm
    973de534a24d9295249fa4bdfd455cc183c37ecfc9a52f3ed4df47b1507e01e6  data/raw/treasury_par_2026.csv
    e03348f5a7b495815acc9ffbfb8028cbf4edede6a79c7a029db435726f6895fb  data/raw/treasury_real_2026.csv
    337445c3ac6674411d0da47ba170530b1dfb59e964c11dc434f1e6787fed542b  data/raw/yahoo/AEP_1d.csv
    ffab8fdac0ab6bb5f1dea58fc9ba56dee6d8dee9439e76a5dd5632111287b609  data/raw/yahoo/AEP_1mo.csv
    027eddcf94cc913197b98f55bdb12a8a3dced051187e19a9751c1a7ae88a555e  data/raw/yahoo/AIZ_1d.csv
    ecb77659340b08620c9ec52ee82dc40827566ec955b3613ab18d3133cb32b6b0  data/raw/yahoo/AIZ_1mo.csv
    6a87bdbdf139a1c8aa4e892dab9871381d07dbfa09d86822f2c23114e77152de  data/raw/yahoo/APH_1d.csv
    4f4869dd69f5796b0c9f5bb6d88d024a64cd5a31fbeba8a19c825c4b0de4ae0b  data/raw/yahoo/APH_1mo.csv
    d916217b128402c498a2bf8af020f55dc715a63dfa1a6a502dc55de10d80a420  data/raw/yahoo/BAC_1d.csv
    396bee1b20a225777f2a5f2bc0132ff16bc55eed6223cb599dd2547d9365f314  data/raw/yahoo/BAC_1mo.csv
    086470a741360fb70deca7f33e1adcfe7c97e5b6206eb542547bd0c3760f0c38  data/raw/yahoo/BBCA_1d.csv
    373b1be6881d4be3c86deb27bf43acb4016972c2b2d74b9216a1359f17c747e2  data/raw/yahoo/BBJP_1d.csv
    7eec9c2dbb7cb6d190a2f7255c8a3dbc7347d11968d5a6c69d172e8a4e10b6e0  data/raw/yahoo/BNY_1d.csv
    c4fe031c9bc94635c76def24e3958d8d8fc287245678fd02e50294011b12dc2d  data/raw/yahoo/BNY_1mo.csv
    d8f3c637cf0f6b733c2fd14a49227cb529b965dea773b36868389a34d98403ee  data/raw/yahoo/CSCO_1d.csv
    b443ae335df58cf0c16c7c52d75e960fd9b4925146a88abeafa4b5ebf477d58f  data/raw/yahoo/CSCO_1mo.csv
    41321718280c80e764912bfc637174ea06358a5c351c11a8b97da567717b72ea  data/raw/yahoo/C_1d.csv
    e54099ef75202425122f57faa0b643e50b927f396fe12472f962fc22b8ab90bd  data/raw/yahoo/C_1mo.csv
    6c75d1fb86a4fbff5c3d4e5144c6438b5ba191fd7909c58582084d8a162d44e7  data/raw/yahoo/DGX_1d.csv
    9794d68378de36fc5ad4e17327c805435cb8e91283b526c32b3109ba50d6f0b5  data/raw/yahoo/DGX_1mo.csv
    b8ad1dea4dc8e00b2c2aaf1519081a5103a6a6eba887620dc5a2b6ac57503b97  data/raw/yahoo/EBAY_1d.csv
    fbeea3faedd5c9ec40d139ff48e44f4b9d34618d0cacf680901acb3375050822  data/raw/yahoo/EBAY_1mo.csv
    daeff1a1aa2715052d5bd63068812b011242db5e731f6ca2462c27c53392a44d  data/raw/yahoo/ECL_1d.csv
    2672657e3be6cf78685c1790dcbc0a80df9ef5c603426be87fdf5dc5ac49c96c  data/raw/yahoo/ECL_1mo.csv
    36ca35a8e0c517ec21d202772ed8b492de7eff4c106decb83b9e7722d433a689  data/raw/yahoo/EEM_1mo.csv
    e80adb090c0cb73469b3ce0e26823f9ba1e9406725afb21028eab2b8b1a2547d  data/raw/yahoo/EME_1d.csv
    87b5e1fc2309f45f04a4c22481c2a7ea349d158dd663bf4163dbb4ceacde4d87  data/raw/yahoo/EME_1mo.csv
    22c5d71820194b73890a5584a8ff3ddf4b78e478dd97cb0dafe5bfd7c3cc5959  data/raw/yahoo/EMXC_1d.csv
    401775cdad1c2b394b16e317023439c2254d3b113c20c88d8ba5d13da2a789d9  data/raw/yahoo/EMXC_1mo.csv
    cc32e96ef2adf4759e3b41f13327acd3ba20191498219e87000ea5d3955f2956  data/raw/yahoo/EPP_1d.csv
    4d4170d691e34969cd0613c3e13ac97ad0cb235e4bdfacd6aedc4f7017b39cbd  data/raw/yahoo/EPP_1mo.csv
    13d2dee22c20036c284f4ae8f222cb77d832146faec6b2296acc376a930be51b  data/raw/yahoo/ESGV_1d.csv
    a3bccdd51f9c89e6391d46a22b85da30f09963f8af00c457cd4fdf3a93eb8754  data/raw/yahoo/ETR_1d.csv
    a7f12b17fcf183795ccfb4739f9a112a649529ad1d4f3466efb609ad3b62b419  data/raw/yahoo/ETR_1mo.csv
    1d225c82248fc95f3260169ea3c04dea0e532dcaf1eabcefdccbb60d000b3902  data/raw/yahoo/EVRG_1d.csv
    de4b3626057ee97c7b9238e8db295589f89e89ca22af20f429332b04ae34a1b2  data/raw/yahoo/EVRG_1mo.csv
    177d59500973919d6c12c62120d43a95c513b6f99cc29da2758c138dfb068947  data/raw/yahoo/EWC_1mo.csv
    1ca114b23b63662ec0a78dd9867312294d9f5fcae19e8998dd6d680cf185f3da  data/raw/yahoo/EWJ_1mo.csv
    2b934c5d21e72fe9305f89e3e697741608dace8dd76635cf52ee22a3aa5d63ed  data/raw/yahoo/FFIV_1d.csv
    ca5f32807af4ae8933e169328091ee3763ca6bac78c243b6882a27455fd5b518  data/raw/yahoo/FFIV_1mo.csv
    b30077f5d0f86a3d8b83f738c2b239c6117ec127231c2a3fb2159d0d23311e65  data/raw/yahoo/FXI_1mo.csv
    a4e7e20a1eb2452be87044ef1b697ff79c6b0aa55981f33800da4faa2df84638  data/raw/yahoo/GE_1d.csv
    c102f6fb572350b858e11dc5ae14cd9a7a1e47425730afc74d450d7a7e93d4b5  data/raw/yahoo/GE_1mo.csv
    e6e8cc91766d5551dfede2e534b11d8bf7d00b329eccb2afeb295bf1203ee50b  data/raw/yahoo/GILD_1d.csv
    47db270236476403001baee8703af2ba82cb48090140cda30e3c965233083fa6  data/raw/yahoo/GILD_1mo.csv
    d4a56569e8914a63b931fa036917ff0369eba7922fe3dcb7847975a42530c495  data/raw/yahoo/GOOGL_1d.csv
    faa31f4d77c32135098ef2282e477dc531f128dcc0d7676bc9501f34f4b4541e  data/raw/yahoo/GOOGL_1mo.csv
    f1835cedb4032a10dafd7ac73c1eccf0b76d790e8c8475f899e142b29b8517bf  data/raw/yahoo/GWW_1d.csv
    0d5535b3083814bdc881099e9623db075118dd4ef7b0253d0f28c3406460ef54  data/raw/yahoo/GWW_1mo.csv
    758608f08f1a102327dc75ca591d5fd698b2eab28af63b704a969ed829bca98f  data/raw/yahoo/HLT_1d.csv
    faa4ade56124b53b3acd04c2c7a4b85c60e69a7373cd0b38b560e1dafc4d59eb  data/raw/yahoo/HLT_1mo.csv
    9cbf74556f39d767bbbba92d876a66fc86370df22b95c4e7f108de2fa364c532  data/raw/yahoo/HST_1d.csv
    0d256e5e8f78af5dc9d6a2152b46efc9407b9ac1b86b6df97024037c5d73a717  data/raw/yahoo/HST_1mo.csv
    c915cb5ad7d01351f097081d802d45f3d75f90961b2e0e2abeb194e8225f6f2d  data/raw/yahoo/HWM_1d.csv
    6c29aa1c6b8e3252d9524d3bd34f5d193e12e3ce120a43e1363b58adc6df95fa  data/raw/yahoo/HWM_1mo.csv
    591bd12c564be0984bf00741d66da1fa20b0ccb43223743506f77120a593903e  data/raw/yahoo/IBTM_1d.csv
    2fcbad05983dc3a81b8fd77b7db6f6cd6e2c7136d0bed5aed90a989a00c64a5e  data/raw/yahoo/IBTM_1mo.csv
    f63aba3f4de5834527558893e2f4ec767322e4046b8f51292410472411d94890  data/raw/yahoo/IBTO_1d.csv
    55f220d59d99f71741c649790ff5ac3a4a67a3a6b032e13001df413b14f8eb30  data/raw/yahoo/IBTP_1d.csv
    4199368f613010bc1e285abf71c51e666506d7c03a7e12d5448dc85c2bff48ed  data/raw/yahoo/INCY_1d.csv
    4eb0a4d8ebd13a6a3d9f0ec1ee186daa91033a0eba44c87b8aa1f41deac7079d  data/raw/yahoo/INCY_1mo.csv
    a5bf545a34156e1fb60c30ccfce335638cc1e0698e86b58f966d1c33f1fc4f6d  data/raw/yahoo/JCI_1d.csv
    cc31058b68c80675ef04933b9e13b95dae3eeb86829d502f3f7445b9343e7a52  data/raw/yahoo/JCI_1mo.csv
    dce691517f8ce9a98a9a5887ae4e08958244f4b567ed1a20540c6fdf9ba66d8d  data/raw/yahoo/JNJ_1d.csv
    eece7032aab29f94c4fd86fd27788df79f59bcbd0703ae9814c3ef43c4b30004  data/raw/yahoo/JNJ_1mo.csv
    62f374123642d9e190bc02fd886096c383c7217d1b8bcb7f5d3cbf27b89425d5  data/raw/yahoo/JPM_1d.csv
    4203ec96e4f934212ee8e971bd88e9bbd793fcf912dc44e8f464670c9fa5236d  data/raw/yahoo/JPM_1mo.csv
    7f51de375713e6d29b854688940b0cbcbe7aede3c9ea3d1569c17d7c902ab6f5  data/raw/yahoo/KEYS_1d.csv
    a21ff485bdac20b04104bc78838d0e947e3545a55644add1f979542c8a1a37b4  data/raw/yahoo/KEYS_1mo.csv
    fce05e907ef93ebb326289c909869d412653ece65c6d9e8bfa3bfc3d9c6c584f  data/raw/yahoo/MCHI_1d.csv
    11ec9b9fc3d96fe41da7a85d2d702b29663746ae8960d7a65efe489e94bcdda3  data/raw/yahoo/MCHI_1mo.csv
    e3fe59f647a823bc8dd43fe3c3bd9e24c08979914c4dc05e326124624219134f  data/raw/yahoo/MRK_1d.csv
    a69a4c86c0e40f3fe30d667cdf76c4968adc70e8644afb7cd58b1e5e1419dffd  data/raw/yahoo/MRK_1mo.csv
    b6ac0cdcdbe57d6326245c9daf2b6eea630161f21f067f8bd95a305429f9efa5  data/raw/yahoo/PH_1d.csv
    4a3a194bd152156416d658bd585b139842290f4a4762d8d9f581b74e786542d9  data/raw/yahoo/PH_1mo.csv
    fa0e7310673505d5498f3369a181a1b6976377c1e1012392119c430c2c06e4f6  data/raw/yahoo/ROST_1d.csv
    bbe50aecc1929896d048ea93c67a91d2fd50cb799640bd216efe1b0c126cb848  data/raw/yahoo/ROST_1mo.csv
    8e9119a08f7eefd15b70dfdf9c99f08ba4af8c2ac82fbf70e1e315de11434314  data/raw/yahoo/SPG_1d.csv
    124357692cbe1214ceb4aee57382bbbf114c3af61ee25a77ed7a1ae93762fa17  data/raw/yahoo/SPG_1mo.csv
    d50cb02117d8dd6f9206f4a9b750ef4c61d51c7b36f3ca1ead58ed13819afef9  data/raw/yahoo/STT_1d.csv
    4155212365a9e7af03090b8d7f6454c7ac1dfcbd64ae4f392d2c73f922f31a3a  data/raw/yahoo/STT_1mo.csv
    ca8d8163a365ca5c3d9444cf3009d75991986fd0e2cb8c44410bb8cf7409551c  data/raw/yahoo/TRV_1d.csv
    50e74c9063d26b555198043e26d216699f0fe10cdfb69efd2ac1c7611bd082e7  data/raw/yahoo/TRV_1mo.csv
    1adc45bb7daa6023bc9f16e40bb6f0e02cbb6d90481cf40477dd44d091fd68c3  data/raw/yahoo/VB_1d.csv
    35d7eee6da56fee58532248d3a558c9610931feb77a5f756cbe0b5b60a326096  data/raw/yahoo/VB_1mo.csv
    4dd437d47e282cb98851b173bcaadd0fcd3ee14b5a0fe225a5d08475c720a5a7  data/raw/yahoo/VEA_1mo.csv
    2099c6a9ffe92a7dbb50bdbbccdaa13b21ee6c1eedc523634d6eab927dbee904  data/raw/yahoo/VGK_1d.csv
    eaccfaac77f2752b2f24f589becc77d1dc0c12bfbdb8c2fdd3dfbd0aaec79d3f  data/raw/yahoo/VGK_1mo.csv
    6d33c602257ef4c139ea85c76ce686df44c00a1b5f8d18cde5c8ae491912e1c1  data/raw/yahoo/VSGX_1d.csv
    404d7facf0112950788849b68ed1897c74a80d39a622e4baaf97028504a879b3  data/raw/yahoo/VTI_1mo.csv
    c3e9a67373a400473e7e63ecb4504ccf9db6e15914eef80114fc206a35dced51  data/raw/yahoo/VTR_1d.csv
    4e87d71e1de955e1f7336e7530389d62b61e6b406a756aa651420325804297fe  data/raw/yahoo/VTR_1mo.csv
    4dd54e8df4a2ad758982359e3caac2a111dba6be8f8b61a019ad638ca68fdac2  data/raw/yahoo/VTV_1d.csv
    2c4840fe4b27e0a2ac771038f2876100523c059b830fc57fae68769000149db7  data/raw/yahoo/VTV_1mo.csv
    70fbf5d74101f06444b8fde53bd9b0f622c3ef62f743e00700e166cdd36736d9  data/raw/yahoo/VUG_1d.csv
    30476bcc16647372ef5f659ffdfc64e6065ce40489591245549db096af3cca01  data/raw/yahoo/VUG_1mo.csv
    04fd93e62860fb85612a673890fd55b8c7e690aec4b0ab6857aa42ad89dfaba6  data/raw/yahoo/VWO_1mo.csv
    39ced947b977621c85b7db160b5dc2a3271f0bc55798088dd3020ee4ffc78077  data/raw/yahoo/WAB_1d.csv
    a1a96f490735987d8022ee56d5bdb25065fe89958571aed4240f907f1bb77955  data/raw/yahoo/WAB_1mo.csv
    58f23e497bd8dcf1bfc4895912f1632212c90329f599537b6ba7a739c9cc4f02  data/raw/yahoo/WELL_1d.csv
    ab0f99691968229211b5a4b73d0b0ba73db97e0256ca49bb77ce61db208227ef  data/raw/yahoo/WELL_1mo.csv
