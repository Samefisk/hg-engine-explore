---
name: improve-map-generator
description: Run one iteration of the map-generator improvement loop - measure, try one hypothesis on the solver, keep it only if the benchmark improves, and record the lesson. Use when asked to improve how generated maps look, to work the map lab, or on a scheduled map-improvement run.
---

# Improve the map generator (one iteration)

Design truth: [lab/README.md](../../../documentation/map-system/lab/README.md)
and [style-system.md](../../../documentation/map-system/style-system.md).
One iteration = one hypothesis, measured, decided, recorded. Leave the tree
clean either way.

## 1. Orient (read, do not change anything)

```bash
python3 -B -m tools.maps.style.lab status
python3 -B -m tools.maps.style.lab defect check
```

Read the ledger tail (`documentation/map-system/lab/ledger.jsonl`) and
`ideas.md`. Priority:

1. An open defect that `defect check` reports as a METRIC GAP: fix the judge
   first (step 3b).
2. An open detected defect: pick a player change likely to clear it.
3. The worst benchmark cases in `status`: pick the top untried idea, or a new
   one backed by evidence from those cases (break their bad joins down by
   cause before guessing).

Never retry a rejected ledger entry without a new reason stated in the note.
If `status` says the champion code differs from the tree, find out why
before measuring anything.

## 2. Measure the baseline if needed

If the champion's code hash matches the tree, its ledger numbers are the
baseline. Otherwise run `lab bench --label baseline` on the unchanged tree.

## 3a. Change the player (normal case)

Edit only player files: `tools/maps/style/quilt.py`, `kit.py`, `layout.py`,
`bdhc_gen.py`, `solver_config.json`. Keep the change to one idea. Then:

```bash
python3 -B -m unittest tools.maps.style.test_solver tools.maps.style.test_kit tools.maps.style.test_seams
python3 -B -m tools.maps.style.lab bench --label <short-idea-name>
```

Use `--quick` or `--case NAME` while iterating; only a full bench of the
final tree can be accepted. Then either:

- `lab accept --run <id> --note "<idea>: <what changed>; <numbers>"`. It
  refuses unless the run beats the champion. If refused, treat it as rejected.
- `lab reject --run <id> --note "<idea>: <result>; lesson: <why it failed>"`,
  then revert the player change (`git checkout -- <files>`).

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

When the champion has improved since the showcase maps were generated
(ledger), regenerate them with the commands in
[showcase.md](../../../documentation/map-system/showcase.md), run lint, build
with `hg-engine-delta-build`, and prove with `tools.maps.showcase probe`.
Capture the sheets (`tools.maps.showcase shots`) and review them yourself
first (AGENTS.md Maps); every visual problem becomes a defect (`lab defect
add`). Then tell the user what changed. Their notes become defects too.
Scheduled runs skip this step (no builds or sessions unattended).

## Report

Hypothesis, decision, quality before → after, per-case changes worth
noting, defects touched, commit hash, and the next idea you would try.
