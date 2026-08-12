# Overworld Wild Tools V2

V2 is a shareable Pokédex Workshop application with optional overworld tools.
Its frontend is built from a clean DOM and purpose-built workflows;
it does not render or skin the legacy UI. Behind that frontend it reuses the
proven parser, writers, build controls, ROM launcher, and audio renderer so data
semantics do not drift. The existing viewer remains unchanged.

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

- `server.py` serves the standalone V2 app, preserves the proven backend
  endpoints, and exposes the V2 APIs.
- `reliability.py` owns revisions, mutation locking, transactions, rollback,
  and context-accurate resolution.
- `static/index.html` and `static/v2.css` define the new semantic UI and visual
  system.
- `static/v2.js` orchestrates navigation, atomic saves, builds, ROM launching,
  status, and utilities.
- `static/profiles.js`, `static/routes.js`, and `static/routes-sounds.js`
  implement the focused profile, route, and sound workflows without copying
  the legacy DOM.
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` uses the
  same profile-first, apply-once resolution contract in the game runtime.

The V2-only API surface is:

- `GET /api/v2/health`
- `GET /api/v2/workspace-meta`
- `GET /api/v2/resolve?species=...&terrain=...&level=...&shiny=...`
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
