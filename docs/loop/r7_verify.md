# Standing brief r7-verify — independently check another worker's report

Follow these steps in order. Do every step. Do not skip a step because an earlier one passed, and do
not add work the steps do not ask for.

## Fixed facts (do not work these out yourself)
- `WT` = your current directory (the bridge put you in your worktree). Run `pwd` once and use that
  absolute path wherever this brief says `WT`. **Run every command from WT.** Never `cd` into
  `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026` (the planner's main checkout)
  and never pass it to `git -C`. You may *read* files there; you may not run commands there.
- `PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`.
- Every Python command starts with `PYTHONPATH=WT/src`. Without it you test the main checkout instead.
- `BASE` = the branch under review, named in the planner's message. `improve` is the main branch.
- `NOTES` = `docs/loop/<your thread name>_verify.md`, for example `docs/loop/r7-verify-esg2_verify.md`.
  It is NOT `docs/loop/r7_verify.md`: that file is this brief, and you must not edit it.
- `scripts/run_all.py` runs **27 scripts** and prints one line per script in the form
  `<name>   exit <code>   <seconds>s`. `wins_ladder_check` exiting 1 is known and non-fatal. Any
  other non-zero exit is a FAIL.
- The IPS headline on `improve` is plan median **196989.2** and plan 5th percentile **146101.9**: the
  keys `plan.median` and `plan.p5` in `reports/report_numbers.json`.
- These git commands are blocked for you and will fail: `stash`, `checkout`, `switch`, `reset`,
  `clean`, `push`, `rebase`, `worktree`, `branch -d/-D/-f`, `restore --source`. You do not need any of
  them. To look at old code, copy it out of git (step 4). To undo report changes, use
  `git restore reports/`.
- Your context is about 200K tokens. Pipe every long output through `tail -n 40`.

## What you may change
Only `NOTES`. Do not edit or commit any other file. If a check fails, record it; do not fix it.

## Steps
1. Read `docs/loop/COMMON.md`, the worker's brief and the worker's report (the planner's message
   names both and quotes the report).
2. Write down, as a numbered list in `NOTES`, every claim in the report: each commit, each test it says
   it added, each number, and each "passes" or "unchanged". One line per claim.
3. **Counts.** Count with commands, never by eye:
   - commits: `git log --oneline improve..BASE | wc -l`
   - tests added: `git diff improve...BASE -- tests/ | grep -cE '^\+\s*def test_'`
   Compare each with the count the report gives. A mismatch is a FAIL row.
4. **Make a full copy of the repository as it was before the fix**, outside your worktree (`OLD`
   below means `/tmp/<thread>-base`):
   `mkdir /tmp/<thread>-base && git archive $(git merge-base improve BASE) | tar -x -C /tmp/<thread>-base`
   If `mkdir` says the directory exists, use `/tmp/<thread>-base2` (then `-base3`) instead; do not delete anything.
   It is about 21 MB and takes under a second. It writes only into OLD and touches no checkout.
   OLD is the one place outside WT where you may `cd`.
5. **Tests.** From WT, run `PYTHONPATH=WT/src PY -m pytest -q tests 2>&1 | tail -n 3` and paste the
   summary line (`N passed in Xs`) exactly as printed. Then the old tests on the old code:
   `cd OLD && PYTHONPATH=OLD/src PY -m pytest -q tests 2>&1 | tail -n 3; cd WT`
   and paste that line too. The difference in passed tests must equal the count from step 3.
6. **Each new test fails before the fix.** For each test file that gained tests in step 3, copy the
   NEW file over the old one in OLD, then run each new test there against the OLD source:
   `cp WT/tests/<file>.py OLD/tests/<file>.py`
   `cd OLD && PYTHONPATH=OLD/src PY -m pytest -q tests/<file>.py::<test> 2>&1 | tail -n 3; cd WT`
   It must FAIL (or error). Then from WT run `PYTHONPATH=WT/src PY -m pytest -q tests/<file>.py::<test> 2>&1 | tail -n 3`;
   it must pass. Paste both lines for every test. A new test that passes on the old source is a FAIL
   row: it does not test the fix.
7. **Reports unchanged.** Run `PYTHONPATH=WT/src PY scripts/run_all.py 2>&1 | grep ' exit '` and
   paste every line. Count them with `| wc -l` (must be 27). Then `git status --short reports/` and
   paste its output (empty is a pass). Then `git restore reports/`.
8. **Headline.** Run
   `PY -c "import json;d=json.load(open('reports/report_numbers.json'));print(d['plan']['median'], d['plan']['p5'])"`
   from WT after step 7. It must print `196989.2 146101.9`.
9. **Scope.** Run `git diff improve...BASE --stat`. Every file listed must be in the set the
   planner's message allows. Any other file is a FAIL row.
10. **The planner's probes.** The planner's message lists extra probes. Do each one exactly as
    written, and give each its own row.
11. **Write `NOTES`** with this template, filling every `<...>`:

```
# <thread> verification of <BASE>

| # | Claim or check | Command | Output (verbatim) | PASS/FAIL |
|---|---|---|---|---|
| 1 | <claim> | `<command>` | `<decisive line>` | PASS |
...

## Failures
<one paragraph per FAIL row: what was claimed, what you saw. "None." if none.>

## What I did not check
<anything in the report you could not test, and why. "Nothing." if nothing.>
```

    Do not write sentences explaining why the model behaves as it does. Report what the commands
    printed.
12. Commit only `NOTES`: `git add NOTES && git commit -m "<thread>: verification notes"`.
13. Report. Use `kind=done` only if every row is PASS. Otherwise `kind=blocked`, and list the FAIL
    rows in the report body. Write the body to a file with a quoted heredoc and pass `--body-file`
    (the bridge's instructions show the command), so dollar signs survive.
