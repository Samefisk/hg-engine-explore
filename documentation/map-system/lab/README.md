# Map generator improvement loop

A loop that keeps making generated maps look more like vanilla without
anyone re-explaining the goal. It has three speeds, all writing to the same
memory:

| Loop | Who runs it | What it changes | Command / guide |
|---|---|---|---|
| Settings search | a script, unattended | `tools/maps/style/solver_config.json` | `python3 -B -m tools.maps.style.lab tune --trials 10` |
| Hypothesis iteration | an agent | solver/kit code, one idea at a time | [improve-map-generator skill](../../../.agents/skills/improve-map-generator/SKILL.md) |
| Review | the user | defects: places that look wrong in game | `lab defect add …`, screenshots on request |
| Scan | an agent, every iteration and hand-off | defects found before the user sees them | `lab scan --write` |
| Retro | an agent, every iteration | the process: skills, tools, backlog | `lab retro --write` |

The last two close the loop the way "The road to self-improving software"
(Ben Holmes, 2026) describes for software factories: agents fill the backlog
themselves from monitoring, and score their own past work to fix the process.

### Scan: find defects before anyone reports them

`lab scan [--map M] [--write]` takes every generated map (lands with a written
generate report) and compares two independent looks at it: the offline
renderer (`render.voids`, textures and props included) and the judge
(`score.py` checks on the report grid).

- Render void with no judge check within 2 tiles: a **METRIC GAP candidate**,
  one defect per 8x8 area. These come first: the judge is blind there.
- Judge-flagged areas (seams alone excepted): one **detected** defect per map
  and set of checks, at the worst area, listing the others. One solver
  weakness shows up everywhere; filing every area would bury the backlog.
- A finding within 4 tiles of an open defect belongs to that defect.
- At most 5 new defects per map and scan.

Scan defects carry `source: scan` and `evidence`; with `--write` the scan
closes them when nothing flags their spot any more. Defects from people are
never closed by a scan: when no check flags their spot it asks for a re-look.

### Retro: score the loop itself

`lab retro [--write]` reads only the loop's records (ledger, run files,
defects, the papercut log; never conversation transcripts) and scores a
fixed rubric:

| Rubric item | Miss means |
|---|---|
| benches per accepted change ≤ 4 | measuring instead of thinking: quick/case benches first |
| every full bench decided | a lesson was lost: accept or reject every full run |
| no idea rejected twice | the ledger was not read: mark the idea dead |
| rejections carry a lesson | the next agent cannot learn from it |
| most defects found before the user | review/scan before hand-off failed: add the missing check |
| no open defect older than 3 days | the backlog is not worked |
| champion measured on the current tree | the next comparison is meaningless |
| no open map-tool papercuts | tool friction is not fixed |

Each miss carries a proposed change. `--write` appends the result to
`retro.md`; the next iteration acts on it (improve-map-generator step 1).

## Memory (committed)

- `ledger.jsonl`: every accepted and rejected attempt: run id, code hash,
  scores per case, settings, the hypothesis and the lesson. Read the tail
  before proposing anything; do not retry a rejected idea without a new
  reason.
- `defects.jsonl`: user review notes with map and tile. Open defects outrank
  benchmark gains.
- `ideas.md`: the hypothesis backlog, best guess first.
- `retro.md`: rubric results from `lab retro --write`, with proposals.

Run files (`build/map-style/lab/*.json`) are local measurements, not memory.

## The judge and the player

The benchmark (`tools/maps/style/bench.json`) is the showcase layouts plus
held-out vanilla chunks: a vanilla chunk's own class layout, solved with that
chunk removed from the kit (no windows, no learned joins). Each case and seed
is scored by `score.py`. `quality` = mean `seamRate` minus 0.05 per failed
hard gate (route change, broken overhang, hole, exposed void, render void, split region).

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
