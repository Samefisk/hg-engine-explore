# Overworld Wild Tools V2 — direction mockups

These five read-only mockups compare different information architectures for the same profile-override workflow. Open `index.html` through a local web server and switch directions with the numbered tabs.

## Selected direction

**Pokédex Workshop (04)** is the selected direction. Its override deck now
supports direct drag-to-reorder, keyboard arrow reordering from each grip,
stable-ID draft persistence, resolver-order renumbering, and reset. Profiles are
applied from top to bottom; the last matching override applies last. Each override
is one layer whose targeting rows are OR conditions, not separate per-Pokémon
layers. Field rows show the resolved base value in parentheses before the override
and effective value.

```bash
python3 -m http.server 8787 --bind 127.0.0.1
```

Run that command from the repository root, then open
<http://127.0.0.1:8787/design_previews/overworld-tools-v2/>.

## Shared requirements

Every direction keeps the same functional commitments:

- Profiles, route encounters, sound effects, build, and open-ROM workspaces.
- Base profiles and override profiles are distinct entities.
- Preview context always includes species, terrain, level, and shiny state.
- The resolver shows base, matching rules, overrides, and runtime normalization.
- Each override field uses an explicit Include/Custom versus Inherit choice.
- Pending changes live in one durable draft with an impact preview.
- The final save is presented as one revision-checked atomic changeset.

The profile screen is the only workflow drawn in detail in this first direction
study. The selected direction must also preserve the current app's full scope:

| Area | V2 parity scope |
| --- | --- |
| Profile management | Base/override CRUD, Pokémon/type/family/spawn-pool membership, ordered rules, field editing, and effective-value inspection |
| Route encounters | Search and method filters, rates, slots, levels/forms, route swaps and overrides, and global spawn settings |
| Sound effects | Search, metadata, rendered/raw/approximate playback, imported-audio comparison, and waveforms |
| Build and run | Save, build-after-save, auto-run, build log, open `test.nds`, and server restart |
| Debug utilities | Shiny counter, reserved shiny controls, source revision, resolver diagnostics, and validation errors |

## Directions

1. **Behavior Studio** — lifecycle-first and balanced; the recommended all-round direction.
2. **Resolver Control Room** — provenance-first and optimized for correctness/debugging.
3. **Field Research Notebook** — plain-language and approachable, with advanced details available on demand.
4. **Pokédex Workshop** — game-adjacent visual identity with an industrial cartridge/deck metaphor.
5. **Data Bench** — table-first, keyboard-friendly, and optimized for expert throughput.

The prototypes are intentionally static. They are a direction-selection tool, not a replacement for the current viewer yet.
