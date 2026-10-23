# Standing brief r7-integrate — merge verified branches and update the shared docs

**Read first:** `docs/loop/COMMON.md` (rule 3 does NOT apply to you: you are the one worker allowed to
edit `docs/MODEL.md`, `docs/VALIDATION.md`, `README.md`, `scripts/run_all.py` and
`scripts/doc_numbers.py`), then the planner's message, which lists the branches to merge and the exact
doc changes.
**Your worktree:** branch `r7-integrate`, based on `improve`. Already created for you.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`. Your context is about 200K tokens: pipe long output through `tail`.

## Rules
- Merge only the branches the planner names, with `git merge --no-ff <branch>`. If a merge conflicts,
  resolve it only when the resolution is obvious (both sides additive); otherwise abort and report
  `question` with the conflicting hunks.
- Make exactly the doc and script changes the planner specifies. Every figure you add to MODEL.md or
  VALIDATION.md gets a check in `scripts/doc_numbers.py` (`checks()`), built from the report that
  prints it, and that report must be written by a script in `run_all.py`'s ORDER.
- After each merge and after the doc edits: `PYTHONPATH=<wt>/src PY -m pytest -q` (paste the final line),
  `PY -m pyflakes src scripts tests`, `PYTHONPATH=<wt>/src PY scripts/run_all.py 2>&1 | tail -30`, and
  `PYTHONPATH=<wt>/src PY scripts/doc_numbers.py | tail -3`. Pre-existing reports must stay
  byte-identical unless the planner says a change is expected; list any that changed.
- Commit after each step. Never push. Never merge into `improve`: the planner does that.
