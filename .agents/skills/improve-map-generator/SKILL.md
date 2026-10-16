---
name: improve-map-generator
description: Run one iteration of the map-generator improvement loop - measure, try one hypothesis on the solver, keep it only if the benchmark improves, and record the lesson. Use when asked to improve how generated maps look, to work the map lab, or on a scheduled map-improvement run.
---

# Improve the map generator (one iteration)

Design truth: [lab/README.md](../../../documentation/map-system/lab/README.md)
and [style-system.md](../../../documentation/map-system/style-system.md).
One iteration = one hypothesis, measured, decided, recorded. Leave the tree
clean either way.

The headline benchmark is the **rebuild bench** (`tools.maps.style.rebuild`,
style-system.md "Semantic pipeline"): six held-out vanilla chunks rebuilt
from their own semantic maps and compared with vanilla as rendered images.
Void must not grow, `tileMatch` should rise. Look at its side-by-side PNGs
before and after every change: they show what the numbers mean. The old
`lab bench` (walk-class quilt solver, score.py gates) is kept only for that
old generator; new maps never use it.

## 1. Orient (read, do not change anything)

```bash
python3 -B -m tools.maps.style.rebuild status     # rebuild champion, and whether it is this tree
python3 -B -m tools.maps.style.lab status
python3 -B -m tools.maps.style.lab scan --write    # find defects before anyone reports them
python3 -B -m tools.maps.style.lab defect check
python3 -B -m tools.maps.style.lab retro           # how the loop itself is doing
```

`scan` compares the renderer with the judge on every generated map and files
what it finds (`source: scan`): a METRIC GAP candidate where the render shows
void no check sees, one detected defect per map and set of checks otherwise.
It closes its own defects once they no longer reproduce, never the user's
(it lists those for a re-look instead). Read the ledger tail (`documentation/map-system/lab/ledger.jsonl`) and
`ideas.md`. Priority:

1. An open defect that `defect check` reports as a METRIC GAP: fix the judge
   first (step 3b).
2. An open detected defect: pick a player change likely to clear it.
3. The worst benchmark cases in `status`: pick the top untried idea, or a new
   one backed by evidence from those cases (break their bad joins down by
   cause before guessing).

If `retro` reports a MISS, its proposal is a process fix (a skill step, a
tool, the backlog): do it in this iteration when it is small, otherwise add
it to `ideas.md`, so the same failure does not repeat.

Never retry a rejected ledger entry without a new reason stated in the note.
If `status` says the champion code differs from the tree, find out why
before measuring anything.

## 2. Measure the baseline if needed

If the rebuild champion's code hash is this tree, its ledger numbers
(`documentation/map-system/lab/rebuild-ledger.jsonl`) are the baseline.
Otherwise run `python3 -B -m tools.maps.style.rebuild --label baseline` on the
unchanged tree and accept it (first champion) or compare with it.

## 3a. Change the player (normal case)

Player files: `tools/maps/style/semantic.py` (what tiles are), `paint.py`
(the painter), `design.py` (shapes and refine), `kit.py`, `bdhc_gen.py`.
Keep the change to one idea; find it in the rebuild PNGs (a pond without its
bank, a sliced tree, a notch at a wall corner), and break the case's defects
down first (`Painter.report()`: walk/kind/level mismatches, bad seams,
overhang violations, bare tiles, void tiles). Then:

```bash
python3 -B -m unittest tools.maps.style.test_semantic tools.maps.style.test_kit tools.maps.style.test_seams
python3 -B -m tools.maps.style.rebuild --label <short-idea-name> [--case NAME]
```

Use `--case` while iterating; only a full run of the final tree can be
accepted. Then either:

- `python3 -B -m tools.maps.style.rebuild accept --run <dir> --note "<idea>: <what changed>; <numbers>"`.
  It refuses unless the run beats the champion. If refused, treat it as rejected.
- `python3 -B -m tools.maps.style.rebuild reject --run <dir> --note "<idea>: <result>; lesson: <why it failed>"`,
  then revert the player change (`git checkout -- <files>`).

A semantic change (a new kind, a layer, a level step) changes every target:
the rebuild bench handles that (targets are re-extracted), but committed
designs (`data/maps/designs/*.semantic.txt`) must be redesigned with
`showcase design` before they are painted again.

## 3b. Change the judge (metric gap or vanilla false alarm only)

Judge files: `seams.py`, `score.py`, `bench.json`. Make the check
see the defect, then:

```bash
python3 -B -m tools.maps.style.lab judge-check     # vanilla must still score perfectly
python3 -B -m tools.maps.style.lab defect check    # the defect is now detected
python3 -B -m tools.maps.style.lab bench --label judge-<defect>
python3 -B -m tools.maps.style.lab accept --run <id> --rebaseline --note "judge: <defect id> ..."
```

Never loosen the judge to raise the score. A judge change without a defect
id or a vanilla false alarm is out of scope.

## 4. Commit an accepted iteration

Commit the change, the ledger line and any `ideas.md` update together, on
the current branch, following the repository Git rules. A rejected iteration
commits only the ledger line and the idea's new status.

## 5. Refresh the user's view (only after real gains)

When the rebuild champion has improved since the showcase maps were painted,
redesign and repaint them (`python3 -B -m tools.maps.showcase design`, then
`showcase write`), run lint, build
with `hg-engine-delta-build`, and prove with `tools.maps.showcase probe`.
Capture the sheets (`tools.maps.showcase shots`) and review them yourself
first (AGENTS.md Maps); every visual problem becomes a defect (`lab defect
add`). Then tell the user what changed. Their notes become defects too.
Scheduled runs skip this step (no builds or sessions unattended).

## 6. Retro (every iteration)

`python3 -B -m tools.maps.style.lab retro --write` appends the rubric result
to `documentation/map-system/lab/retro.md`; commit it with the ledger line.

## Report

Retro score and any process fix made, hypothesis, decision, quality before → after, per-case changes worth
noting, defects touched, commit hash, and the next idea you would try.
