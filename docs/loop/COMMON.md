# Standing rules for every worker brief (read this with your brief)

## The project in one paragraph
`lgm` is a liability-driven investment model. A client deposits $300k (Jan 2027) and $150k (Jan 2028),
must fund ten fixed $50,000 payments (Jan 2033-2042) with certainty, and wants the largest possible
"facility" fund left in January 2033. `src/lgm/curve.py` + `ladder.py` price a cash-flow-matched
Treasury ladder; `src/lgm/esg.py` simulates 20,000 monthly scenarios (Nelson-Siegel rates, equities with
Student-t shocks, inflation, USD/TWD, Taiwan building costs); `src/lgm/engine.py` applies a `Strategy`
(`src/lgm/strategies.py`) month by month; `src/lgm/growth/scoring.py` builds the parameters actually used
for headline numbers (`esg_params`). `docs/MODEL.md` and `docs/VALIDATION.md` describe the design and its
checks. Read `docs/MODEL.md` before you change anything.

## Environment (do not improvise this)
- Python: `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`. Call it `PY`.
- The virtualenv's editable install points at the MAIN checkout, not your worktree. Every command must
  put your worktree's `src` first, or you will be testing the main checkout's code:
  `PYTHONPATH=<your worktree>/src PY -m pytest -q`
  `PYTHONPATH=<your worktree>/src PY scripts/<script>.py`
- All data is cached in `data/raw/`; tests run offline. Do not re-download cached data unless your brief
  says so.
- The whole pipeline (`scripts/run_all.py`) takes about 100 s. One `engine.run` on 20,000 scenarios takes
  well under a second. Measure before you launch any grid search, and multiply out the cost.

## Discipline
1. **Commit after each task**, with a message that says what the commit does. An interrupted run loses
   everything that is not committed; committed work survives.
2. **Do not change default behaviour unless your brief says so.** New features are opt-in (a parameter
   whose default reproduces today's numbers). The test of this: after your changes,
   `PYTHONPATH=<worktree>/src PY scripts/run_all.py` must leave every pre-existing file in `reports/`
   byte-identical (`git status --short reports/` shows only new files you created). If it does not, you
   changed a default: find out why and fix it, or report `question`.
3. **Do not edit `docs/MODEL.md`, `docs/VALIDATION.md` or `README.md`.** Write your findings in the doc
   your brief names. The planner merges several workers' branches and these shared files would conflict.
4. **Only edit the files your brief says you own.** Small, additive edits elsewhere only if unavoidable,
   and list them in your report.
5. **Every number in your findings doc must be printed by a committed script** that you name next to
   it. No hand-typed results.
6. **Never invent data or sources.** If a source cannot be downloaded, say so. A downloaded file must be
   on disk under `data/raw/`, with its URL, download date and SHA-256 recorded. Reporting `blocked` with
   what you found is a correct and useful outcome; fabricated data is the only real failure.
7. **No polling.** Run scripts in the foreground. Do not launch background jobs and then repeatedly
   check on them.
8. **Report honestly, per item.** When you compare variants, give the numbers for every variant, not a
   range across them. Say plainly when a result goes against what the brief expected; breaking an
   assumption is the most useful thing you can do.
9. **Paste the final pytest line verbatim** in your report (e.g. `61 passed in 12.3s`). Do not retype it.
10. **Stop at the budget.** If you run out of time or compute, commit, then report `blocked` with
    partial results and what is left. That beats running into the 4-hour hard timeout, which delivers
    nothing.
11. **Keep memory low.** The machine runs several workers at once, and the bridge stops every
    worker if system memory pressure turns yellow. Estimate array sizes before you allocate them
    (20,000 scenarios x 75 months x 14 assets x 8 bytes is 168 MB per array). Keep peak memory under
    about 2 GB per script: process grids and inner simulations in chunks, keep summary statistics
    rather than full paths, and free large arrays you no longer need.
12. **Never run a command in the planner's main checkout**
    (`/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026`). Do not `cd` there and do
    not pass it to `git -C`. You may read files there. Run everything from your own worktree. A
    worker once ran `git checkout <rev> -- .` there and rolled back the day's merged work.
13. **Blocked git commands.** The bridge blocks `stash`, `checkout`, `switch`, `reset`, `clean`, `push`,
    `rebase`, `worktree`, `branch -d/-D/-f`, `restore --source` and `rm -rf`. You do not need them. To
    look at an older version, copy it out:
    `mkdir /tmp/<name> && git archive <rev> | tar -x -C /tmp/<name>`. To undo changes to reports, use
    `git restore reports/`.
14. **Count with commands, not by eye.** Any count in your report (scripts run, tests added, commits,
    files changed) comes from a command (`wc -l`, `grep -c`, `git log --oneline | wc -l`). Paste the
    command next to the count.
15. **Claims need numbers.** Do not write a sentence saying why something happens unless your brief
    asks for it and a number printed by a script backs it. If two of your numbers disagree with a
    sentence, the sentence is wrong.
16. **Write the report body to a file and pass `--body-file`.** In a double-quoted `--body` the shell
    deletes every `$` and backtick, so `$5,790` arrives as `,790`.
