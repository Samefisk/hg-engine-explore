# Shiny Overworld Pokemon Effect

This note tracks a visual effect discovered during the long-hop shadow
investigation. It did not fix shadows, but it may be useful later for shiny
overworld Pokemon presentation.

## Discovery

- During shadow attempt S41, `ov01_0220329C(object, 0)` was called from the
  active canopy long-hop render path.
- Runtime result from user verification: the Pokemon displayed a shiny-style
  effect, not a floor shadow.
- Build used for verification: `test1508.nds`, copied to Delta from the
  Overworld Behavior Profile Viewer build.

## Useful Symbols

- Declaration:
  `void *LONG_CALL ov01_0220329C(LocalMapObject *mapObject, int variant);`
- Declared in `include/map_events_internal.h`.
- Linked at `0x0220329C | 1` in `rom.ld`.

## Notes

- This effect should not be used as a shadow payload.
- It may be a candidate for a future shiny overworld spawn sparkle/attention
  effect.
- The S41 use spawned it repeatedly on odd long-hop frames. A real shiny
  implementation should likely trigger it once at spawn or during a deliberate
  reveal beat, not every movement frame.
