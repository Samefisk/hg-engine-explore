# Map generator improvement loop

A loop that keeps making generated maps look more like vanilla without
anyone re-explaining the goal. It has three speeds, all writing to the same
memory:

| Loop | Who runs it | What it changes | Command / guide |
|---|---|---|---|
| Settings search | a script, unattended | `tools/maps/style/solver_config.json` | `python3 -B -m tools.maps.style.lab tune --trials 10` |
| Hypothesis iteration | an agent | solver/kit code, one idea at a time | [improve-map-generator skill](../../../.agents/skills/improve-map-generator/SKILL.md) |
| Review | the user | defects: places that look wrong in game | `lab defect add …`, screenshots on request |

## Memory (committed)

- `ledger.jsonl`: every accepted and rejected attempt: run id, code hash,
  scores per case, settings, the hypothesis and the lesson. Read the tail
  before proposing anything; do not retry a rejected idea without a new
  reason.
- `defects.jsonl`: user review notes with map and tile. Open defects outrank
  benchmark gains.
- `ideas.md`: the hypothesis backlog, best guess first.

Run files (`build/map-style/lab/*.json`) are local measurements, not memory.

## The judge and the player

The benchmark (`tools/maps/style/bench.json`) is the showcase layouts plus
held-out vanilla chunks: a vanilla chunk's own class layout, solved with that
chunk removed from the kit (no windows, no learned joins). Each case and seed
is scored by `score.py`. `quality` = mean `seamRate` minus 0.05 per failed
hard gate (route change, broken overhang, hole, exposed void, split region).

The judge (`seams.py`, `score.py`, `bench.json`) is separated from
the player (`quilt.py`, `kit.py`, `solver_config.json` with its tuning search space, …):

- `accept` takes a run only if it was measured on the current tree, beats the
  champion's quality by at least 0.002 (seed noise is about 0.001) with no
  more hard-gate failures, is at most 2.5× slower,
  and the judge is unchanged since the champion. Improving the score by
  loosening the judge is impossible by construction.
- Changing the judge is allowed only to close a metric gap (a defect the
  checks cannot see) or a false alarm on vanilla. `lab judge-check` must pass
  (every vanilla chunk scores perfectly with its full kit), then bench the
  unchanged player and `accept --rebaseline` with the defect id in the note.

## A user defect, end to end

1. The user says "the cliff at Mirrorlake (40, 12) floats".
   `lab defect add --map 542 --x 40 --z 12 --note "cliff floats"`.
2. `lab defect check` reports whether any metric flags that spot. If not, it
   is a METRIC GAP: extend the judge so it does (and stays clean on vanilla),
   rebaseline.
3. Improve the player until the bench improves; regenerate the map; the
   defect's spot is clean in `defect check`; the user confirms in game;
   `lab defect close`.

## Status

`python3 -B -m tools.maps.style.lab status` prints the champion, per-case
scores (worst first), open defects and the ledger tail.
