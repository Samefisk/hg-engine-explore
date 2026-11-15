# Three emote slots

Run `scripts/owctl scenario run presentation.emote-three-slots --json` on the current ROM.
This one prepared case binds four fresh Wild Cyndaquil and uses six fixed native quiet calls:
A0,A1,B1,C2,D3,C3. Actual Admit returns must be yes,no,yes,yes,no,no.
After teleport, eight neutral setup frames let the current Field and Query
owners load. These frames do not count toward the240 observed frames.

The exact148-byte native owner must hold three distinct active effects, models,
texture keys and palette keys. Native104-byte effect data and each borrowed
model bind every frame destination to its own slot. Native update and visible
draw calls on all three occur during240 ordinary completed neutral updates.
All six quiet requests make no PlaySE or StopSE call. Normal script bubbles
still play their sound once; the native host checks cover that separate path.
No screenshot or dry-run capacity result receives credit.

All three native effects retire, then VWait frees each key and source exactly
once with the transfer queue empty. Each owned slot is cleared. Other actors
may use those slots later; whole-field model counts and VRAM totals are
diagnostics. The final read can run while the follower moves. It must keep the
same Field, heap, effect context and four full actor identities, with no active
native call. The read advances no frames. The runner must close its private
session. Unknown identity or missing evidence fails.
