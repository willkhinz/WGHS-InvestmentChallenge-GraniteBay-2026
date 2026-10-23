"""Apply the r8 episodes edits: a doc_numbers check, a run_all entry and a VALIDATION bullet.

Run once, from the worktree root: PYTHONPATH=<worktree>/src PY docs/loop/r8_apply_episodes.py
It refuses to run twice. Written and dry-run by the planner; do not edit it. The check function it
inserts is docs/loop/r8_episodes_check.py.
"""
import sys
from pathlib import Path

FN = Path("docs/loop/r8_episodes_check.py").read_text().rstrip()

p = Path("scripts/doc_numbers.py")
s = p.read_text()
if "def episodes_bullet" in s:
    sys.exit("already applied")
head = "\n\ndef checks() -> list[tuple[str, str, str]]:"
assert head in s, "doc_numbers checks() not found"
s = s.replace(head, "\n\n" + FN + "\n\n" + head, 1)
anchor = "                f\"{k(ips['p5'])} against {k(plan['p5'])} simulated\"))\n"
assert anchor in s, "doc_numbers replay anchor not found"
s = s.replace(anchor, anchor + '    out.append(("VALIDATION", "named crises after the lock", episodes_bullet()))\n', 1)
p.write_text(s)

r = Path("scripts/run_all.py")
t = r.read_text()
a = '    ("policy_robust", False, True),'
assert a in t, "run_all anchor not found"
j = t.index("\n", t.index(a)) + 1
t = t[:j] + '    ("episode_stress", False, True),        # named crises after the lock (docs/VALIDATION.md section 7)\n' + t[j:]
r.write_text(t)

sys.path[:0] = ["scripts", "src"]
import doc_numbers  # noqa: E402

v = Path("docs/VALIDATION.md")
u = v.read_text()
anc = "  cautious. All-stock funds every payment in 89.1% of real paths against 86.7% simulated.\n"
assert anc in u, "VALIDATION anchor not found"
v.write_text(u.replace(anc, anc + doc_numbers.episodes_bullet() + "\n", 1))
print("applied: scripts/doc_numbers.py, scripts/run_all.py, docs/VALIDATION.md")
