# Overworld Wild Tools V2

V2 is a separate Pokédex Workshop application for the overworld behavior
toolchain. Its frontend is built from a clean DOM and purpose-built workflows;
it does not render or skin the legacy UI. Behind that frontend it reuses the
proven parser, writers, build controls, ROM launcher, and audio renderer so data
semantics do not drift. The existing viewer remains unchanged.

## Run

From the repository root:

```bash
python3 tools/overworld-viewer-v2/server.py
```

Open <http://127.0.0.1:8766/>. Use `--host` or `--port` to override the local
binding.

## What V2 changes

- Replaces the legacy information architecture with focused Profile, Route,
  and Sound decks plus a compact Utilities menu.
- Keeps base profiles and override profiles visually distinct.
- Keeps drag handles and keyboard move controls for override ordering.
- Treats each override profile as one runtime layer with one explicit member
  set and one optional shared condition. The profile is evaluated and applied
  at most once for a Pokémon context.
- Adds member-set shortcuts for individual Pokémon, evolution families, types,
  and live encounter pools. These shortcuts materialize members in the same
  profile; they never create per-Pokémon backend rules. New override drafts
  start disabled until members or an all-Pokémon shared condition is selected.
- Documents the resolver contract in the UI: evaluation is top to bottom and
  the last matching override applies last.
- Adds an exact context resolver for Pokémon, terrain, level, and shiny state.
  It shows matched layers, skipped-layer count, effective values, and base
  values in parentheses.
- Protects every source mutation with a deterministic content revision.
  Stale editors receive a conflict instead of silently overwriting newer work.
- Verifies the source revision before and after every full-data or resolver
  read, retrying instead of pairing stale parsed data with a newer revision.
- Replaces the legacy multi-request Save action with one all-or-nothing commit
  across profiles, memberships, overrides, encounters, and spawn settings.
- Adds a Route Deck roster, encounter-method filters, form-safe bulk species
  swaps, route-only layers, and live summaries derived from the current draft.
- Blocks Save while shared profile conditions, slot values, forms, level ranges, or global
  spawn-distance relationships are invalid.
- Holds the same cross-process workspace lock for the full ROM build, so a
  second V2 process cannot rewrite source files mid-build.
- Snapshots every writable source and restores the complete snapshot if a
  write, validation pass, or full data parse fails.

## Architecture

- `server.py` serves the standalone V2 app, preserves the proven backend
  endpoints, and exposes the V2 APIs.
- `reliability.py` owns revisions, mutation locking, transactions, rollback,
  and context-accurate resolution.
- `static/index.html` and `static/v2.css` define the new semantic UI and visual
  system.
- `static/v2.js` orchestrates navigation, atomic saves, builds, ROM launching,
  status, and utilities.
- `static/profiles.js` and `static/routes-sounds.js` implement the focused
  domain workflows without copying the legacy DOM.
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` uses the
  same profile-first, apply-once resolution contract in the game runtime.

The V2-only API surface is:

- `GET /api/v2/health`
- `GET /api/v2/workspace-meta`
- `GET /api/v2/resolve?species=...&terrain=...&level=...&shiny=...`
- `POST /api/v2/commit`

## Source and ROM state

“Saved” means the source transaction committed and the complete source model
parsed successfully. It does not mean a ROM was built. Build and Open NDS
remain explicit, separate actions in the header.

Run one source-writing viewer process for a workspace at a time. V2 instances
coordinate with each other through an interprocess workspace lock; the legacy
V1 server predates that lock and should not be used to edit the same sources
concurrently.
