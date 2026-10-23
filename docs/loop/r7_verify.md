# Standing brief r7-verify — independently check another worker's report

**Read first:** `docs/loop/COMMON.md`, then the worker's brief and report that the planner names in
the message that sent you this file.
**Your worktree:** a fresh branch based on the branch under review. You only read and run; **do not edit
or commit anything** except your own `docs/loop/<thread>_verify.md`.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`. Your context is about 200K tokens: pipe long output through `tail`.

Another worker claims it met every acceptance criterion in its brief. Treat each claim as unverified.

## Tasks
1. List the brief's acceptance criteria. For each, run the command that proves or disproves it
   yourself and paste the decisive output line verbatim (pytest's final line, `git diff <base> --stat`,
   `git status --short reports/`, the script's printed numbers, the reproducer's output).
2. Check scope: `git diff improve --stat` touches only the files the brief let the worker own.
3. Check every number the worker's findings doc or report quotes against the output of the script it
   names. List any number you cannot reproduce.
4. Look for one thing the worker did not check that could make its result wrong (a default changed,
   a test that passes for the wrong reason, a number copied from an older run). Say what you tried.
5. Write `docs/loop/<thread>_verify.md`: one row per criterion (PASS / FAIL, evidence), the scope
   check, the numbers check, and your step-4 probe. Commit it. Report `done` if everything passes,
   `blocked` with the failures otherwise.
