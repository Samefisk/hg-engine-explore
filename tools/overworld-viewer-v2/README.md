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

## Sharing and reduced mode

The application discovers workspace capabilities at runtime. A project does
not need the Overworld Behavior Profile system in order to open the Pokédex
Workshop. Missing optional source groups remove their corresponding deck from
navigation; they do not prevent the remaining decks from loading.

- **Pokédex Workshop** requires the standard species, personal-data,
  learnset, evolution, and asset sources used by the Pokémon data API.
- **Route Deck** is available when encounter sources can be parsed. Profile
  headers, override assignments, and spawn-setting sources are optional.
- **Profile Deck** loads the V51 authoring view of the canonical OWBD model and
  validates its V40 runtime representation. It is available only when that graph
  parses and validates successfully; it does not depend on the retired
  flattened-profile sources.
- **Sound Deck and build utilities** remain capability-gated by their own
  source and tool requirements.

The server returns partial workspace data together with a `capabilities`
manifest. Consumers must use that manifest instead of assuming every deck is
installed. A stale URL or saved selection for an unavailable deck falls back to
the first available deck (normally Pokédex Workshop). Pokémon-only commits are
validated independently and do not require Profile Deck infrastructure.

Keep `scripts/overworld_behavior_profile_viewer.py` beside the shared V2 server:
it still provides route, spawn-setting, shared Pokémon-data, build, launcher,
and audio services. Profile authoring uses the separate OWBD V51 endpoint and
writer over the V40 wire model; the shared backend no longer exposes the
flattened-profile editor.

## What V2 changes

- Replaces the legacy information architecture with focused Profile, Route,
  and Sound decks plus a compact Utilities menu.
- Splits Profile Deck into **State Profiles**, **Controllers**, and
  **Modifiers**. The `+` action creates the entity for the selected view, and
  new entities remain local drafts until Global Save.
- Treats every state profile as one complete, runnable behavior state. Calm,
  attentive, tired, carried, and custom meanings belong to controller-local
  nodes and semantic roles instead of sub-states inside a profile.
- Lets a controller bind complete profiles to a unique node roster with one
  required base node, typed scalar and policy defaults, and an authoritative
  transition roster.
- Makes state-body identity explicit. A shallow profile duplicate shares its
  body and exposes shared edits; a deep duplicate owns an independent body even
  when the initial values match. A body is retired only after its last profile
  reference disappears.
- Offers shallow and deep controller duplication with explicit closure rules.
  Deep copy remaps ordinary authored controller-local candidates and children;
  importer-owned backlinks and generated required-owner/tired-origin families
  are refused and must be regenerated, never silently omitted.
- Authors each transition together with its trigger, source-role mask, guards,
  atomic operations, actions, recovery actions, applicability, and override
  definition. An override definition is either a state candidate that selects
  one complete controller node or a modifier that changes typed values without
  changing state identity.
- Allows multiple independently owned override layers to be active at once.
  State candidates compete for the winning complete state; matching modifiers
  then fold over that state in deterministic order. Removing any owner-addressed
  layer recomposes from the base and all remaining layers instead of applying an
  inverse patch.
- Authors modifiers as first-class definitions with typed operations, explicit
  operation order, applicability, channel/priority, multiplicity, and map/battle
  lifetime policies. Modifier operations cannot change state identity.
- Adds a Stack preview that can compare saved and drafted graphs, resolve the
  controller for an entity context, apply event sequences, and show layer
  ownership, precedence, ordered modifier contributions, normalized effective
  values, and validation failures before Save.
- Adds controller-node mapping preview before changing a profile binding, and
  **Effective → state** promotion from a successful final preview. Promotion
  creates an independent deep state body and keeps bounded source/winner/field
  provenance in authoring JSON only; those annotations do not enter V40 runtime
  bytes.
- Protects every source mutation with a deterministic content revision.
  Stale editors receive a conflict instead of silently overwriting newer work.
- Verifies the source revision before and after workspace and behavior-model
  reads, retrying instead of pairing stale parsed data with a newer revision.
- Replaces the legacy multi-request Save action with one all-or-nothing commit
  across V51-authored state profiles, bodies, controllers, transitions,
  modifiers and their override graph, encounters, and spawn settings. The
  transaction validates and round-trips the generated V40 runtime model before
  replacing sources.
- Rebuilds Route Deck around the proven encounter workflow: persisted
  per-source filters, semantic route/Pokémon/type search, method-grouped sprite
  actions, compact aggregate summaries, and contextual per-slot editing.
- Keeps route-only encounters as one reversible route operation. Manual source
  edits first restore the complete stored baseline, and conflicting external
  source changes block restoration instead of being overwritten.
- Blocks Save while the behavior graph, shared-body edits, slot values, forms,
  level ranges, or global spawn-distance relationships are invalid.
- Holds the same cross-process workspace lock for the full ROM build, so a
  second V2 process cannot rewrite source files mid-build.
- Snapshots every writable source and restores the complete snapshot if a
  write, validation pass, or full data parse fails.

## Architecture

- `server.py` serves the standalone V2 app, preserves the proven backend
  endpoints, and exposes the V2 APIs.
- `reliability.py` owns revisions, mutation locking, transactions, and
  rollback.
- `static/index.html` and `static/v2.css` define the new semantic UI and visual
  system.
- `static/v2.js` orchestrates navigation, atomic saves, builds, ROM launching,
  status, and utilities.
- `static/profiles.js`, `static/stack-preview.js`, `static/routes.js`, and
  `static/routes-sounds.js` implement the focused profile, client-side stack
  preview, route, and sound workflows without copying the legacy DOM.
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` uses the
  same controller-base, state-candidate winner, ordered modifier fold, and
  owner-addressed recomposition contract in the game runtime.

V51 is an authoring/API format, not a second runtime format. Global Save emits
and validates the fixed V40 wire blob. Names, descriptive tags, duplication-mode
inputs, and promotion provenance remain outside runtime wire bytes; the resulting
stable profile/body identities and references are encoded in V40.

The V2-only API surface is:

- `GET /api/v2/health`
- `GET /api/v2/workspace-meta`
- `GET /api/v2/behavior-model`
- `POST /api/v2/commit`

## Source and ROM state

“Saved” means the source transaction committed and the complete source model
parsed successfully. It does not mean a ROM was built. Build and Open NDS
remain explicit, separate actions in the header.

Open NDS uses the platform file opener by default. To launch a specific
emulator, set `NDS_OPEN_COMMAND`; include `{rom}` where the absolute ROM path
belongs, or omit it to append the path automatically. For example:

```bash
NDS_OPEN_COMMAND='melonDS {rom}' python3 tools/overworld-viewer-v2/server.py
```

Run one source-writing viewer process for a workspace at a time. V2 instances
coordinate with each other through an interprocess workspace lock; the legacy
V1 server predates that lock and should not be used to edit the same sources
concurrently.
