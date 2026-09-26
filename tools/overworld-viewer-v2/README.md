# Overworld Wild Tools V2

V2 is a shareable Pokédex Workshop application with optional overworld tools.
Its frontend is built from a clean DOM and purpose-built workflows;
it does not render or skin the legacy UI. Behind that frontend it reuses the
current compatibility parser, writers, build controls, ROM launcher, and audio
renderer to avoid duplicating source mutation logic. The existing viewer
remains unchanged.

The canonical system model and vocabulary live in
[`documentation/overworld-system/`](../../documentation/overworld-system/README.md)
and [`CONTEXT.md`](../../CONTEXT.md). `/api/v2/resolve` calls the same portable C
condition evaluator and resolver sources as the ROM. A `GET` previews saved
profile composition. A `POST` previews unsaved conditional-profile drafts with
observation facts, timer state, and candidate targets. Python prepares context
and presents provenance; it does not evaluate conditions or compose profiles.

## Run

From the repository root:

```bash
OPEN_PAGE=0 scripts/keyboard-maestro-start-overworld-viewer.sh
```

This installs and starts a per-user macOS LaunchAgent with `KeepAlive`, so V2
survives the terminal or Codex task that launched it and restarts after a crash.
Open <http://127.0.0.1:8766/>.

For foreground development and debugging, run:

```bash
python3 tools/overworld-viewer-v2/server.py
```

Use `--host` or `--port` to override the foreground server's local binding.

ROM builds run a bounded Docker readiness check before starting the container.
On macOS it starts Docker Desktop when the daemon is unavailable; an
unresponsive daemon fails promptly with restart guidance instead of leaving the
Workshop waiting indefinitely.

## Sharing and reduced mode

The application discovers workspace capabilities at runtime. A project does
not need the Overworld Behavior Profile system in order to open the Pokédex
Workshop. Missing optional source groups remove their corresponding deck from
navigation; they do not prevent the remaining decks from loading.

- **Pokédex Workshop** requires the standard species, personal-data,
  learnset, evolution, and asset sources used by the Pokémon data API.
- **Route Deck** is available when encounter sources can be parsed. Profile
  headers, override assignments, and spawn-setting sources are optional.
- **Profile Deck** appears only when the overworld behavior profile sources are
  present and readable.
- **Sound Deck and build utilities** remain capability-gated by their own
  source and tool requirements.

The server returns partial workspace data together with a `capabilities`
manifest. Consumers must use that manifest instead of assuming every deck is
installed. A stale URL or saved selection for an unavailable deck falls back to
the first available deck (normally Pokédex Workshop). Pokémon-only commits are
validated independently and do not require Profile Deck infrastructure.

Keep `scripts/overworld_behavior_profile_viewer.py` beside the shared V2 server:
it is still the compatibility adapter for route/profile source formats. Its
presence does not mean a project must contain the optional overworld profile
sources themselves.

## What V2 changes

- Replaces the legacy information architecture with focused Profile, Route,
  and Sound decks plus a compact Utilities menu.
- Shows one profile library. The complete root is marked as the root; every
  other named profile uses the same parent-and-local-fields model.
- Keeps drag handles and keyboard move controls for ordered profile
  applications.
- Keeps profile definitions separate from their uses. Selectors choose the
  initial profile. Each ordered application has one explicit member set and
  one shared target match.
- Lets an override profile be normal or conditional. A conditional profile
  owns an ordered list of independent conditions. The last active condition in
  that profile wins, while active profiles still compose in application order.
- Replaces the Alert editor with Conditions and removes the Active tab. Legacy
  attentive and Active values remain visible only in the migration report
  until catalog migration is complete.
- Adds member-set shortcuts for individual Pokémon, evolution families, types,
  and live encounter pools. These shortcuts materialize members in the same
  profile; they never create per-Pokémon backend rules. New override drafts
  start disabled until members or an all-Pokémon shared condition is selected.
- Documents the resolver contract in the UI: evaluation is top to bottom and
  the last matching application applies last.
- Adds a source-context resolution preview for Pokémon, terrain, level, and
  shiny state. Conditional preview also accepts current time, terrain and
  motion facts, player facts, timer state, and candidate actors. It shows
  application order, applied profiles, changed fields, the winning condition,
  and target source.
- Protects every source mutation with a deterministic content revision.
  Stale editors receive a conflict instead of silently overwriting newer work.
- Verifies the source revision before and after every full-data or resolver
  read, retrying instead of pairing stale parsed data with a newer revision.
- Loads only the active deck. Profile, route, Pokémon, and sound reads do not
  wait for one monolithic workspace payload.
- Refuses resolver reads when its loaded Python sources changed on disk; restart
  V2 to load the new parser before resolving another context.
- Replaces the legacy multi-request Save action with one all-or-nothing commit
  across profiles, memberships, overrides, encounters, and spawn settings.
- Rebuilds Route Deck around the proven encounter workflow: persisted
  per-source filters, semantic route/Pokémon/type search, method-grouped sprite
  actions, compact aggregate summaries, and contextual per-slot editing.
- Keeps route-only encounters as one reversible route operation. Manual source
  edits first restore the complete stored baseline, and conflicting external
  source changes block restoration instead of being overwritten.
- Blocks Save while shared profile conditions, slot values, forms, level ranges, or global
  spawn-distance relationships are invalid.
- Holds the same cross-process workspace lock for the full ROM build, so a
  second V2 process cannot rewrite source files mid-build.
- Snapshots every writable source and restores the complete snapshot if a
  write, validation pass, or full data parse fails.

## Architecture

The target authoring and diagnosis flow is defined in
[`authoring-debugging.md`](../../documentation/overworld-system/authoring-debugging.md).

Behavior profile saves now write named fields and explicit operators to
`data/overworld_behavior_profiles.json`. The expanded positional arrays in
`data/OverworldWildBehaviorData.c` are generated ROM compatibility output.
Use `python3 scripts/generate_overworld_behavior_catalog.py --check` to find
catalog/output drift. V2 is a client of the generated Behavior Schema and
portable resolver. Semantic trace and scenario work use the separate host
control surface described in the system documents.

- `server.py` serves the standalone V2 app, preserves the proven backend
  endpoints, and exposes the V2 APIs.
- `reliability.py` owns revisions, mutation locking, transactions, rollback,
  and projection of canonical resolver results into the editor response.
- `static/index.html` and `static/v2.css` define the new semantic UI and visual
  system.
- `static/v2.js` orchestrates navigation, atomic saves, builds, ROM launching,
  status, and utilities.
- `static/profiles.js`, `static/routes.js`, and `static/routes-sounds.js`
  implement the focused profile, route, and sound workflows without copying
  the legacy DOM.
- `lib/overworld/overworld_behavior_conditions.c` is the only condition policy,
  and `lib/overworld/overworld_behavior_resolver.c` is the only composition
  policy. The ROM actor service and Workshop native adapter compile those same
  files.

The V2-only API surface is:

- `GET /api/v2/health`
- `GET /api/v2/workspace-meta`
- `GET /api/v2/decks/profiles`
- `GET /api/v2/decks/routes`
- `GET /api/v2/resolve?species=...&terrain=...&level=...&shiny=...&conditionTerrainMask=...&forcedOverrideMask=...&behaviorClass=auto|...`
- `POST /api/v2/resolve` with a V3 draft catalog, subject, observation,
  candidates, and optional condition timer state
- `POST /api/v2/commit`

The health response includes `serverInstanceId` and `restartRequired`. The
restart endpoint is asynchronous; clients should poll health until a different
instance ID is ready before reloading.

If browser automation reports a stale or unowned tab handle, discard that
handle, verify `/api/v2/health`, and open a fresh local Workshop tab. Build and
status operations remain available through the documented HTTP endpoints; tab
ownership itself is controlled by the browser integration, not this server.

## Source and ROM state

“Saved” means the source transaction committed and the complete source model
parsed successfully. It does not mean a ROM was built. Build and Open NDS
remain explicit, separate actions in the header.

Open NDS uses the platform file opener by default. To launch a specific
emulator, set `NDS_OPEN_COMMAND`; include `{rom}` where the absolute ROM path
belongs, or omit it to append the path automatically. On macOS, launch the
installed melonDS app by bundle identifier:

```bash
NDS_OPEN_COMMAND='/usr/bin/open -b net.kuribo64.melonDS {rom}' \
  python3 tools/overworld-viewer-v2/server.py
```

Run one source-writing viewer process for a workspace at a time. V2 instances
coordinate with each other through an interprocess workspace lock; the legacy
V1 server predates that lock and should not be used to edit the same sources
concurrently.
