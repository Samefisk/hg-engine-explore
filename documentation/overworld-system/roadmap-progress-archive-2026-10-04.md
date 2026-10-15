# Historical delivery records — archived 2026-10-04

This is retained history, not a resume guide. Branch names, ROM identities,
“current” claims and next actions below were recorded at the time of each run.
Use [the current work table](roadmap-progress.md#current-work-table) for the
active checkout, latest candidate and next action. Recheck proof inputs before
using an older accepted result for a newer ROM.

## Player HP delivery records

Final acceptance is recorded in
[final-acceptance-3481.json](../../build/hit-crash-fit/final-acceptance-3481.json).
All ten required owner, spawn, contact, skid, wall, input and Ambush checks
passed with controller-owned accepted proof after the last host fixture
change. The current [skid-hit run](../../build/overworld-devtools/test-34724bb8586540469ffbf6f028452bb6/manifest.json)
proves immediate Crash at904, ground restoration at905, Crash completion at909,
one shared Jump at910–923, exact landing height and returned control.
Mount HP falls135→115 and saved rider HP100→80. The current
[collision run](../../build/overworld-devtools/test-009db5030f9f463da7ede5beb4f8949d/manifest.json)
proves real wild/party/rider HP, per-target protection and both shared Jump
landings. The required zero-stutter run covers2716 measured loops,1935 moving
frames and175 joined spawn-work witnesses with zero late loops or render
stalls. All private sessions are stopped and their owned ROM copies removed.
The source ROM, Delta copy and unchanged Continue save match the final receipt.
Work is uncommitted on `feature/player-hp`; no further source edit or game run
is queued. The next action is the user's playtest through the worktree UI's
Open NDS button. This contact/movement acceptance does not close the broader
home-rest, zero-HP, battle/capture or ordinary-Hop proof gaps below. The
prepared mode34 result remains diagnostic-only.

The user added a skid-hit rule after this proof: a hit during a due or active
skid must trigger the normal crash immediately, then apply knockback. It must
not wait for the remaining skid travel or silently cancel the skid. This order
was reproduced on ROM3476: native mounted HP fell 135→115 at frame902 during
an active skid. The old skid committed at frame904 and knockback began without
a Crash. The [measured failure](../../build/hp-skid-hit-baseline-3476/head2-measured-failure.json)
retains the actor identity, native HP, old motion, trace and ROM/save hashes.
The [ROM3479 repeat](../../build/overworld-devtools/test-307e579f56bc465ab12381b196e7d3c9/manifest.json)
now measures the required order: one hit at frame905, ground restoration at906,
Crash completion at910 and one forced Jump beginning at911. It removes the old
skid bounce; body/rider heights are exactly65536/98304 at landing. The old skid
does not emit END, commit or cancellation. Acceptance remains open because the
Jump stays `COMMIT_PENDING` through944. Final writes and Engine END are present,
but the Field adapter still waits for `STREAM_READY`. The private session is
closed, its owned ROM copy is removed and the source save is unchanged.
The [ROM3480 diagnostic](../../build/overworld-devtools/test-7c492d55e7594b82b07c93eb113cc62f/manifest.json)
measured an idle loader with an active old North axis, equal high/low values,
and zero remaining distance. Its last sample stayed at the rolled-back origin
while the new watcher reached the West landing. That empty old axis blocks
the next stock sample. BEGIN now retires only this exact empty axis at the
unchanged sampled X/Z, then binds the new watcher. It clears only E8/E0/E4;
POLL still requires a real stock sample. The stateless Field leaf occupies the
existing HP161 gap at `0x01FFD510`; public entries and stream state stay fixed.
The production-C check and independent review pass. GCC10 packages the leaf
in102 of112 bytes and the Field caller in470 of496 bytes. The package gate
checks exact linked/ROM bytes, the direct Thumb call and no mutable leaf state.
ROM3479 SHA-256 is
`ff971320d5fe78db01e6beb903c41d5752b46ef4f601ea0b8c8f397634cabc4f`.

The [ROM3481 repeat](../../build/overworld-devtools/test-10d3dfbd073a408cab01afc998a23206/manifest.json)
passed with controller-owned `acceptedProof: true` for `current.pokemon-skid-hit`.
Across64 completed frames, the hit at904 immediately publishes one Crash,
ground restoration follows at905, Crash ends at909, and one13-frame Jump starts
at910 and finishes at923 with control returned. The old skid emits no END,
commit or cancellation. Both heights restore and21 clean frames follow.
Real mount HP falls135→115 and saved rider HP100→80. The
[same-ROM basic collision run](../../build/overworld-devtools/test-43cccebf8e094c7c90039c934acd32b1/manifest.json)
also has accepted proof for `current.pokemon-combat`: Snorlax235→215,
party Cyndaquil101→81 and rider100→80 across57 completed frames, with both
shared Jump landings and height/control restoration. ROM3481 SHA-256 is
`0be72ee5a5b1d3a06af08bd317a3a0f2c9bd9910c899bd323ebd464200d6bfca`.
Both private sessions stopped and their ROM copies were removed. Source
`test.sav` remains byte-identical at the hash below. The same-ROM Skid and
Linear regression handoff is active; product, tools and build inputs are frozen.
The first-wall, newest-key and Ambush passes predate the final collector change;
controller rechecks must renew them before the stopped Linear handoff. The
new owner-reader control `test-1509c59a9d4748ecaf6d4439afa38b2f` is accepted.

The bounded gait-reader window is complete. The earlier later-wall records
lacked native gait and could not be repaired by replay. Fresh record
`test-070d657da03949d6890dfe391a2b6c52` exposed stale Mount input offsets:
reader session/mode used +60/+67, while current sealed GCC10 Apply reads
+68/+6F. Only those reads changed, with a guard for the four compiled load
instructions. The real paired poses remain unmodified. Eight focused reader
checks and independent review pass; there is no game-code or ROM change.

The [current single-key wall recheck](../../build/hit-crash-fit/gait-second-current-recheck.json)
accepts retained native run `test-c49e28ee3b1f42bcacbabe3e1ee6897f`:
43 completed frames, exact gait/seat across skid848..855, commit/control856,
and blocked Crash858. All17 copied controls reject their intended faults.
The [current two-key wall recheck](../../build/hit-crash-fit/gait-two-key-current-recheck.json)
accepts `test-e8a7e480f4b34e3f8625b141a2e2bc55`, also43 frames. It proves
idle Crash858 with zero speed/pending at(589,406), then one native-admitted
ordinary West Walk862 from still-held input. The canonical contract allows
that later recovery; final-held-frame idle was a checker error. All20 controls
reject wrong gait, seat/height, missing idle, wrong recovery and missing native
admission. Recipes, actions, wall bounds, skid commits and cancellation checks
stay exact. Eight focused checker tests pass, including copied premature-idle recovery. The original failed manifests
are retained unchanged; fresh-process controller rechecks grant current proof.
Both sessions are stopped and their private ROM copies removed.

The collector change made the two older HP results stale under current capture
checks. The [final skid-hit run](../../build/overworld-devtools/test-c278d16490e54e9f9c72e6b7b0d26595/manifest.json)
is accepted across64 frames, including a current retained recheck after the
last pure-checker repair. The [final collision run](../../build/overworld-devtools/test-c67db7ec088842a1adefe1f2e7b47a25/manifest.json)
is accepted across57 frames. Real wild/party/rider HP, hit protection, no
self-hit, immediate Crash, both shared Jump landings and restored seat/control
all pass. Sessions `session-zdns50j9` and `session-an648g6c` are stopped and
both private ROM copies removed. Source ROM3481 and Continue save still match
the hashes below. The [frozen handoff receipt](../../build/hit-crash-fit/final-source-handoff-3481.json)
binds the final files and ROM/save.

Skid completed the three remaining current-ROM gates with accepted proof:
`test-c6aaca8645524a8b90d28dbe4f4f13de` first-wall43frames,
`test-5d964fddfad74994804c02b9ba710fe5` newest-held49frames and
`test-7d40a293a87b408aa513d14d9b8eb43a` Ambush28frames. Each owned session
closed without errors and its private ROM copy was removed. All frozen file,
ROM and save hashes remain unchanged. Linear now owns stopped live control
for only its original mode34 diagnostic and required D1 gates. Root has no
game job or pending source edit. Product, observer, proof, recipe and
build inputs stayed frozen through the handoff. The original native mode34
16→8/80-moving-frame diagnostic passed with13 normal native36 Walk commits
and natural release. It remains diagnostic-only; its receipt is
[retained here](../../build/linear-final/diagnostic-receipt.json).

The two D1 attempts did not reach measurement: `test-aeb66a51ec3c4f34911e715972bf8b67`
and `test-ecf5d3edafc54844839d9556ac7ca42f` rejected the boot location with
zero observed frames. Source save65c loads Cherrygrove67(564,392), while arm
requires map33(585,406). This is a fixed-start fixture mismatch, not a pacing
pass or a measured game hitch. Both owned sessions closed and private ROM
copies were removed; all frozen hashes remain unchanged. No save substitution.
The [bounded natural route sample](../../build/linear-final/route2-receipt.json)
now reaches exactly map33(585,406) with settled stock coordinates, no field task
or dialogue, and the same source Mankey at15/15HP. RIGHT+B1tile, DOWN+B6,
RIGHT+B20 and DOWN+B8 plus neutral waits take169 completed navigation frames.
The source ROM/save are unchanged. Session `session-3zztvq8c` is stopped and
its private ROM removed. Unknown terrain cells were never labeled passable;
actual normal movement proves arrival. This diagnostic earns no D1 credit.

Linear owns one narrow fixture correction: add this exact natural setup before
the existing follower wait/bind, keep the map33(585,406) arm guard and all
measured route deltas, directions, endpoints, frame caps, minima, native work
and zero-late checks. Native step count is global since boot, so the measured
thresholds shift by the authenticated35 setup steps. There is no counter reset
or new reader. Only setup/overall budget accounts for those uncredited frames.
Owned scope is the two D1 recipes/scenario metadata, exact shared validator
seals, matching pure proof/tests and the two registry recipe hashes. Product,
reader, terrain guard, provenance classification, source save/ROM and build
remain frozen. No live run during edits. Review is within20minutes with one
Skid read-only check, then final freeze, current-ROM D1 and only the HP/movement
proofs whose honest capture checks reject the shared-validator change. No
reclassification or stale proof is permitted. Root remains integration owner.
The seven-file fixture correction is frozen and its one independent review is
clean. Hash/check receipt is [fixture-freeze.json](../../build/linear-final/fixture-freeze.json).
The exact35 native setup admissions, original live Mankey and stock controls
are required before arming. Population overall budget600 includes only setup;
its meter remains capped at360 observed frames. Zero-stutter keeps4000 overall,
2600 observed,1800 moving and zero late loops. The23 focused schema/pure-proof
checks and101 scenario validation pass. No product, reader, counter, terrain,
ROM/save or provenance change. The shared-validator change correctly stales the
prior current HP/movement captures; those are behavior evidence only until
required renewals pass. No old manifest or hash was changed.

Root restarted only the stopped worktree service. Current doctor/validation
pass. Owner-reader `test-1e07e4b4b73a41759b56f583e2d8f088` is accepted and
session `session-lzm617j7` stopped/private ROM removed. D1 population
`test-27b19d2c406f40b1ac9f11622332cb01` passed with accepted proof across256
measured frames. Its private session closed without errors and its ROM copy
was removed. Zero-stutter `test-6a35878055f044cfb1f603eded09eee1` stopped at
bind frame879 with zero measured frames. All35 normal admissions, source
Mankey, endpoint and released keys passed; the exact ready/centered player
guard correctly rejected native motion starting at879. Frames876–878 were
ready. The old unmeasured follower-IDLE wait delayed binding until that move.
Linear owns one bounded correction to wait for the verified existing actor,
as population already does. The zero-stutter meter permits a moving follower;
the centered/ready player, source identity,35 admissions, measured route and
all pacing thresholds remain required. The failed session closed without
errors and its ROM copy was removed. Product, readers, ROM/save and provenance
remain frozen. Review and final fixture freeze precede any new live run.
D1 stays open until both required registered gates have current accepted proof.
The five-file zero-only correction is frozen in
[zero-fixture-freeze.json](../../build/linear-final/zero-fixture-freeze.json).
Independent replay accepts the authentic centered frame873 with moving Mankey
and still rejects the offset player at879. Ten focused D1 controls and101
scenario validation pass; no game, reader, ROM/save or provenance input changed.
After the stopped service restart, current owner-reader
`test-d7c945edf0f94c28b0c5c21d77c7f271` and population
`test-b9246957753c4e8b969af99cf98706aa` pass with accepted proof across1/256
frames. Both private sessions closed without errors and their ROM copies were
removed. Zero-stutter `test-9efeb6cce77848ef93ef337793bf899d` passed with
current accepted proof:2716 measured loops,1935 moving frames,175 joined normal
spawn-work witnesses, zero late loops and zero render stalls. Its private
session closed without errors and its ROM copy was removed. The final
host/game inputs are frozen. All seven staled HP/movement captures have now
been renewed with current accepted proof: skid-hit
`test-34724bb8586540469ffbf6f028452bb6`64frames, collision
`test-009db5030f9f463da7ede5beb4f8949d`57frames, later wall
`test-43e6d83750684381a51141b87328ced0`43frames, two-key wall
`test-e559a819b08d409494ea5c48b239af5a`43frames, first wall
`test-6045c8d9a19c4c98beda5a4291116d5e`43frames, newest-held direction
`test-1bd54a543eb84f46aba0673a81c4cbe7`49frames and Ambush
`test-126e4c0c70dd42a6bb98730d96e41e80`28frames. Each private session closed
without errors and its ROM copy was removed. Root independently checked all
ten final manifests, the16-file freeze and ROM/save identity. Older results
remain historical; no old manifest, hash or provenance class was changed.
The earlier proposal to drain the skid before knockback is superseded. The
HP chat owns the stopped integration result. Skid and Linear returned clean
handoffs; neither has another source edit or live test queued.

The earlier
[collision/knockback run](../../build/overworld-devtools/test-04b31368e4944c8c9eca39784fc74bbb/manifest.json)
passed with controller-owned `acceptedProof: true` for `current.pokemon-combat`
on ROM3474, SHA-256
`5fdabe9ba749392434199f8033f808fe86ed64e25795742622f46f10f11b5a8a`.
Across 57 completed game frames, ordinary Weepinbell Ambush contact reduced
wild Snorlax HP from 227 to 207, real party Cyndaquil HP from 101 to 81, and
saved rider HP from 100 to 80. Both Pokémon completed the accepted one-tile
Jump, restored height and control, and retained per-target hit protection.
Rider and mount used one anchor. The attacker did not damage itself. All 15
copied-data rejection controls failed as required. The private session
`session-9a1luvhi` closed and its ROM copy was removed. Source `test.sav` stayed
byte-identical (SHA-256
`65c36abc15d442141a33cdffd682868514db6093890cb958964dd732a846eefb`).
Production-C checks cover party-backed Follower storage, caps and fainting;
this live run covers Wild and Mounted roles. It does not claim live battle,
capture or healing proof.

The earlier
[ROM3472 collision/knockback](../../build/overworld-devtools/test-0f353a9281264d96a29589d7da4a680c/manifest.json)
run confirmed full starting HP, but Pokémon contact failed because the
boot-resident Actor owner is absent from the SDK overlay list. Contact now
checks the fixed Actor entry identity instead. New wild encounters also use
the `0xFFFF` HP marker, so a reused slot starts full and numeric zero remains
fainted. The production-C checks pass. The live reader and meter check the
accepted forced motion plan after any current normal step finishes. The shared
ROM3473 build succeeded with the HP fixes and the new native Actor layout.
The reader now checks that exact layout, accepts the native reservation release
during a committed pause, and authenticates relocated resident code before
reading it. The
[owner reader calibration](../../build/overworld-devtools/test-04e93bc621824c42a3ea4a3fc42530f7/manifest.json)
passed with accepted proof on ROM3473. It proves mount setup and reader controls,
not Pokémon combat. ROM3474 built with the shared skid source and fixed direct
Thumb imports; independent ROM/ELF review checked HP capsules and Motion pins.
HP now owns game/build/source control for the measured skid-hit fix. It must
hand the accepted, stopped final ROM to Skid, then Linear for the current-ROM
D1 pacing checks. Those cross-feature gates
remain open. Any later relevant product or observer change requires current
HP proof again. The user-approved manual session and all HP-owned test
sessions are closed.

Status: implementation and acceptance active on `feature/player-hp`. The V2
Workshop built ROM3461 (SHA-256 `97b2530e…`) and copied it to Delta as
`test3461.nds`. One profile option byte selects None, Slide, or Jump knockback
and a distance of 1–7 tiles. Ram uses Jump 3; Throw Held Actor uses Slide 1;
active Ambush uses Jump 1 after a warned, 20-HP Hop hit. The one shared
player-health controller moves the player without a walking pose. Its path
checks let knockback pass through overworld Pokémon while walls, scripted
tiles, and non-Pokémon objects still block it. On ROM3455, the
[Ambush run](../../build/overworld-devtools/test-740da0fc70e54d45a6f932fe249b0c2a/manifest.json)
measured HP 100→80 and a one-tile south jump through Weepinbell. Accepted hits
now play the stock player-shove sound, flash the HP bar once, and tint the
outer edge of the screen red. User feedback favored the first tint but not a
second flash; ROM3461 removes the second bar pulse and clears the edge sprites
before restoring blend state. The final look still needs user playtesting.
The [mounted Ambush run](../../build/overworld-devtools/test-110b056ec3fd4e89b5c51a5b83c2afc8/manifest.json)
on ROM3461 measured two hits (HP 100→60) across 150 normal frames while the
rider stayed at (585,407) and both rider and mount kept their original height.
The resident mount does not appear in the SDK overlay load table; player health
now checks its fixed entry identity, field owner, and riding phase before
deciding whether on-foot knockback may start. Earlier
ROM3447 [Ram Jump/rest](../../build/overworld-devtools/test-cd2832335f8a4006b62791cffa189042/manifest.json)
and [Throw Slide/contact](../../build/overworld-devtools/test-1d5507d2d70f4ad8a313c68736e6e69b/manifest.json)
passed with accepted proof. Both extracted-C spawn-budget checks passed, then
[spawn work](../../build/overworld-devtools/test-089bf62cd7db4882af0271559e822252/manifest.json)
and [zero stutter](../../build/overworld-devtools/test-16aedf7414a946d3aa419a639263d64d/manifest.json)
passed on ROM3452 with the unchanged Route 30/Mankey Continue save. The
worktree save was restored byte for byte. User playtesting of the new motion,
hit sound, red edge tint, and bar appearance remain open. Zero-HP Continue,
ordinary attacking Hop, and home rest still lack final live acceptance for
the broader player-HP feature. The large center ring is retired.
Source review: 2026-09-28, branch
base `origin/main` at `02cc40566`, plus current worktree files. The user's
decisions below define this feature. Unproved behavior is labelled.


## Player HP implementation inventory recorded before ROM3510

The current implementation has these owners. A source path or successful build
is not a claim that the behavior passed in the game.

| Owner / interface | Implemented source and evidence | Exact remaining proof |
| --- | --- | --- |
| [HP reducer](../../lib/overworld/player_health_model.c), [public API](../../include/player_health_model.h) | 100 maximum HP, 33 Ram, 20 Throw, 60-frame protection, 300-frame rest wait, then 10 HP/second. Host tests use the production C. | Check timing and duplicate contacts with current-ROM attack scenarios. |
| [Save adapter](../../src/player_health_save.c), [save layout](../../include/save.h) | Versioned record occupies audited spare misc bytes at 0x2D5–0x2D7 and 0x2DD–0x2DF without changing the block size. Old records initialize lazily; valid zero remains zero. [ROM3409 injured Save/reload proof](../../build/overworld-devtools/test-1e71146996e04e649409fb3985056ed5/manifest.json) accepted a stock Save write and exact private cartridge reload: HP stayed 67 and bar fill 30. | Save/reload zero HP; prove legacy/bad record behavior and unrelated save data in game. |
| [Field owner](../../src/player_health.c), [field hook](../../src/field/map_teleport.c) | Resident field clock runs while no wild actor is active. [ROM3408 Ram/rest proof](../../build/overworld-devtools/test-9348e5aaecf246138914e2f171886077/manifest.json) accepted 300 still frames, then 10 HP in 60 frames and a movement reset. A live START-menu check froze HP and hid the bar, then restored it. | Prove battle/map/mount pause. |
| [Ground contact](../../src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c) | A blocked Walk step into the player checks the current profile's `attacking`, speed gate, and damage. Ram controls motion, not damage authority. [ROM3408 Ram/rest proof](../../build/overworld-devtools/test-9348e5aaecf246138914e2f171886077/manifest.json) accepted real Onix 100→67 under the old contact rule. | Prove the new speed gate, damage, turn lock, and no battle on the current ROM. |
| [Throw contact](../../src/player_health_contact.c) | Tracks a launched wild Pokémon by slot/generation/map and samples swept airborne motion; landing and cancellation end damage authority. [ROM3409 direct Throw proof](../../build/overworld-devtools/test-4605be3f6b0f449daad3715cdce673ec/manifest.json) accepted real contact 100→80. The same mounted Route 29 flight made a false hit on [ROM3408](../../build/overworld-devtools/session-l4azgzz6/recording-2c2c51c3e59c.json.gz) but no hit on [ROM3409](../../build/overworld-devtools/session-kl0r0pe8/recording-ca2f27ee2721.json.gz); both recordings have the same 240-frame rider and projectile path. [Registered mounted proof](../../build/overworld-devtools/test-c7d4d27a4bba4217a2bca4097ca15934/manifest.json) accepted a natural flight crossing the old hit box with HP100 and zero hits. Contact now samples the rider's X/Z offset. | Prove incidental flight, high arc, landing-only and repeat-contact checks. |
| [Recovery](../../src/player_health_recovery.c) | Closes the field before stock `Task_Blackout` and temporarily substitutes the HP healing spawn for its synchronous reads. On ROM3402, HP0 led to saved Center map 158, trainer/party full HP, an empty task chain and free player movement. | Register this as accepted proof; check money/bag, invalid destination, mounted collapse and zero-save reload. |
| [Center/home hooks](../../armips/scr_seq/scr_seq_00003_commonscript.s), [home script](../../armips/scr_seq/scr_seq_00845_home_rest.s) | Script markers follow completed party healing; resident service consumes them and records the healing spawn. On ROM3402, an Onix Ram left 67 saved HP, then the normal Violet nurse script and arrival returned live/saved HP to 100 with the field task idle. [Final HP receipt](../../build/overworld-devtools/session-gtyq8ioc/player-health-d2bbc7a0f95b.json). Both available saves have Elm's lab scene 3, which routes Mom's talk to the stock early dialogue; her regular Rest menu requires scene 4 and the completed savings question. | Complete Elm's rival-name/egg-return scene through normal input in a private copy, then play home rest and test checkpoint change, cancelled-flow and unrelated-heal controls. Register Center acceptance. |
| [Health bar renderer](../../src/player_health_presentation.c) | Draws one 64×32 main OBJ at (8,8), with a 44-pixel proportional fill, green/yellow/red HP colour and steady amber danger border. After the user's black-bar report on ROM3425, the palette moved from DMA-inaccessible ITCM to a retained heap buffer and the fill gained the stock party bar's light/body/shade bands. [ROM3427 bar proof](../../build/overworld-devtools/test-7bc945165acb442288ee63c0f2cfe131/manifest.json) accepted 44/44 full and 30/44 injured after Ram, with nonzero palette colors in main OBJ palette VRAM. [Earlier warning sample](../../build/overworld-devtools/session-8wije26u/player-health-aae2baba26ba.json) showed amber before Ram; START-menu samples showed hide and rebind. | Check final LCD appearance and UI conflicts in the user ROM. |
| [Observer](../../tools/overworld/devtools_player_health_observer.py), [descriptor](../../scripts/generate_player_health_debug.py) | Version 3 keeps the native bar receipt and now checks that its palette source is DMA-readable, contains colors, and matches main OBJ palette VRAM. The bar case rejects a copied black-palette fault. The build gate rejects both ARM/Thumb `memset` and `memcpy` veneers; the latter stalled ROM3426 startup. | Native memory data still do not prove final LCD pixels. |

The read-only vanilla reference confirms stock blackout sequencing in
`src/blackout.c`, Center/home arrival scripts in
`files/fielddata/script/scr_seq/scr_seq_0003.s`, and party HP/status/PP restore
in `src/use_item_on_mon.c`. Battle money loss is a separate battle command.
These source facts narrow the live check; they do not replace it. See the
validated revision in the original checkout's `.codex-reference/README.local.md`.
Never copy reference output into the product.

Direct Throw contact, the native bar, and injured Save/reload have current-ROM
accepted proof. Mounted Throw has a measured before/after fix and awaits a
registered check. Incidental flight, landing-only contact, repeat contact,
home rest, warning lifecycle and blackout acceptance remain open.


## Player HP delivery slices recorded before ROM3510

Keep one HP row in the [current work table](roadmap-progress.md#current-work-table).
Each slice below has a product result, dependency, completion check and proof
home. Source-complete means code exists; it does not mean the slice is accepted.

| Slice / dependency | Current result and next work | Completion criterion and proof home |
| --- | --- | --- |
| P0 — seam checks | Save range, frame clock, stock recovery path, Center/home hooks and OBJ resource owner are mapped in source. | Keep the map current when a source anchor changes; host layout and ROM package checks in [verification](verification.md). |
| P1 — P0 save/clock | Model, save, field tick and observer built; ROM3402 initial and Ram/rest checks accepted. | Save-reload and battle/map/mount pause checks; retain manifests under `build/overworld-devtools/`. |
| P2 — P1 + recovery | Blackout wrapper and heal markers built; ROM3402 diagnostic returned from HP0 to the saved Center with full trainer/party HP and free input. | Accepted blackout/healing checks for money/bag, real Center/home and zero-save/retry cases. |
| P3 — P2 | Ram impact built; ROM3402 Onix 100→67 and rest accepted, four-hit zero diagnostic passed. | Accept warned contact, protection, mounted hit, miss/follower and normal encounter controls. |
| P4 — P2 | Swept Throw contact built. ROM3403 commits Geodude's reserved approach Walk; a prepared Geodude/Weepinbell flight hit the player for 20 HP. | Accept direct/incidental/miss/high-arc/landing/cancel/mounted cases; attack warning precedes damaging flight. |
| P5 — P1 + graphics | Health bar renderer, v2 descriptor and bounded native receipt are source-ready; the old 14-sprite edge receipt is historical. | Build and check proportional fill, warning, hardware effect and suppression/restore in menu, map label, fade and battle. |
| P6 — P1–P5 | Freeze product, scenario and observer inputs; build through V2 Workshop; run only affected registered and regression checks. | Current ROM/save identity agrees with accepted manifests and feature map; report any exact open gap. |

Parallel work is safe only across owned files: save/model and rendering can be
investigated separately, while Ram/Throw and the shared frame path need one
integration owner. Freeze all inputs after review and before final proof.


## Player HP acceptance history — ROM3402 through ROM3427

Current state on 2026-09-26: the V2 Workshop built ROM3405 and copied it to
Delta without auto-opening it. The [initial-state](../../build/overworld-devtools/test-c08f9dedba3c4c91af4e899fc565bed2/manifest.json)
and [Ram/rest](../../build/overworld-devtools/test-1c8f92a164524d4fa4a9124ca668f88d/manifest.json)
scenarios passed with accepted proof on that ROM. A separate owned melonDS
diagnostic drove four Onix Ram hits to zero. The stock blackout returned to the
saved Center (map 158), restored player and party HP, ended its field task, and
released movement control. That diagnostic has not yet checked money or bag
and is not a registered blackout pass. At 67 HP, a native observer saw the
requested edge band and all 14 OAM sprite submissions from the old display;
the new bar still needs proof. A separate live Onix→Violet nurse path healed live/saved HP
from 67 to 100 after the complete normal script; home rest is still untested.
A [ROM3402 Route 29 diagnostic](../../build/overworld-devtools/session-p0j8142r/recording-b45d0dcf9bbc.json.gz)
kept Geodude's reserved approach Walk at `COMMIT_PENDING` 16/16 after its engine
command ended. ROM3403 lets that shared Walk reach the existing terminal commit
before the Throw reservation returns. In [the repeated prepared setup](../../build/overworld-devtools/session-9pe3uhe8/session.json),
Geodude reached commit sequence 11, launched Weepinbell, and the HP observer
recorded [100 HP](../../build/overworld-devtools/session-9pe3uhe8/player-health-7a13092d0587.json)
then [80 HP with one accepted hit](../../build/overworld-devtools/session-9pe3uhe8/player-health-88256244a026.json).
ROM3403 Route 29 has 40% Onix, 40% Geodude and 20% Snorlax in each time-of-day
table; [a separate session](../../build/overworld-devtools/session-klsiqr0k/session.json)
observed natural Geodude and Onix spawns. The user saw neither attack in play.
In owned session `session-llawsjpl`, Onix at (583,412), five tiles from the
stationary player at (585,407), had no Ram application (mask 1024) and HP
stayed 100 at frame 999; after another 720 frames HP was still 100. Source
inspection found the default notice range is three tiles. The current source
changes only Ram and Throw condition vision to five tiles, and changes the
Route 29 table to 40% Onix, 30% Geodude and 30% Weepinbell so Geodude has
a small target to throw. The custom notice range applies to the full Ram and
Throw species pools on every map; it keeps the forward cone and adjacent
awareness. ROM3404 built with this source and copied to Delta as
`test3404.nds`. In owned session `session-nxp1n7y2`, natural Onix on Route 29
activated Ram and HP/saved HP changed from 100 to 67 by frame 1600. The
[memory recording](../../build/overworld-devtools/session-nxp1n7y2/recording-db072e0c4d47.json.gz)
contains the stationary player and current Wild Onix. A natural Weepinbell
spawned, but no Throw occurred before normal field control ended at frame 1819.
In a second owned session on ROM3405, a natural Geodude threw Weepinbell across
the stationary player on Route 29. The flight lasted 16 recorded airborne
frames; HP and saved HP fell 100→80 with one accepted Throw hit and field
control intact. The [recording](../../build/overworld-devtools/session-gh90i7h0/recording-93ce3e974bce.json.gz)
has 182 consecutive snapshots with no drops. Both owned sessions are stopped.
These are diagnostics, not accepted proof.

The first registered `player-hp.throw-contact` run on ROM3404 reached a bound
flight and HP 80 but failed a frame-clock checker. ROM3405's fresh
[run](../../build/overworld-devtools/test-d9d1d8fd683645808274a28356190bbe/manifest.json)
completed all 10 actions, observed the flight and HP 100→80, then failed a
checker that assumed each native step yielded one frame. The corrected checker
replayed the retained run with `acceptedProof:true` and `passed:true` for
`current.player-health-throw-contact`; the immutable original manifest remains
failed. This proves the prepared direct-hit case, not the remaining Throw
boundaries or natural spawning.

On ROM3425, [moving-candidate selection, chase, and launch](../../build/overworld-devtools/test-749eb35701c7495fb92349476c9b7eaf/manifest.json)
and [direct Throw contact](../../build/overworld-devtools/test-d69b24779d474222a493e6b0d6c26fce/manifest.json)
passed with accepted proof. The first case does not observe the private
reservation frame or movement at pickup. The [spawn-work](../../build/overworld-devtools/test-cd8fe3a1cff64e579b4674366df7501d/manifest.json)
and [zero-stutter](../../build/overworld-devtools/test-04583799e4d14eaaac8d9810d3ba9d5b/manifest.json)
gates also passed on ROM3425 with an unchanged Route 30/Mankey Continue save;
the worktree's Stantler save was restored byte for byte after those runs.
After the Throw refactor, the current ROM3425 also passed
[the focused HP bar case](../../build/overworld-devtools/test-9f52c41edc164a95a43e15d8ef1a926b/manifest.json):
native fill was 44/44 at full HP and 30/44 after one real Onix Ram reduced HP
to 67. The user then reported that this bar appeared black. The old check
did not inspect palette memory. The decomp shows `GX_LoadOBJPltt` uses DMA for
this 32-byte palette, while the old palette source sat in ITCM. On ROM3427,
[the focused bar case](../../build/overworld-devtools/test-7bc945165acb442288ee63c0f2cfe131/manifest.json)
accepted the same 44→30 fill and checked a colored heap palette that matches
main OBJ palette VRAM. The new checker also rejects a copied black-palette
fault. This proves the palette transfer, not final LCD appearance.

**Next action:** finish zero-HP Save/reload, home rest and blackout acceptance.
Check the bar's final LCD appearance in the user ROM and remaining Throw
boundaries. Ask the user to check for a visible hitch on ROM3425. Keep proof
inputs frozen for each later current-ROM acceptance run.

| Open fact | Bounded next check | Independent work |
| --- | --- | --- |
| Blackout acceptance | Register the same four-hit Onix trigger; assert Center return, restored HP/party, money/bag unchanged and free movement | Source recovery path and completed ROM3402 diagnostic |
| Throw boundaries | Extend the accepted direct-hit setup to incidental contact, high arc, landing and cancel cases | ROM3409 direct and mounted Throw accepted; natural Route 29 diagnostic records 100→80 |
| Center/home checkpoint | Violet nurse healed live/saved 67→100 on ROM3402. At home map 63 use Mom's fifth menu item, Rest, while injured; inspect HP and saved spawn after the completed script. | Normal Center diagnostic; home, checkpoint change and cancelled-flow controls unproved |
| Health bar | Check final LCD appearance and remaining UI conflicts in the user ROM | ROM3427 native full/injured fill and colored palette VRAM accepted; earlier warning and menu hide/rebind observed |
| Save reload and zero-load | Save a zero record in a disposable game copy and Continue; inspect state and recovery | ROM3419 injured Save/reload accepted |
| Mounted parity and battle return | Reuse the same accepted HP observer across mount and battle transitions | Complete remaining unmounted paths |


## Previous roadmap ledger — ROM3500 checkpoint

## Overworld Roadmap — Current State

### Read this first

- [Roadmap](roadmap.md): scope and completion rules.
- This page: short resume state. Replace stale state; do not append run reports.
- Manifests own proof. Changed inputs can make older results stale.
- Detail indexes: [September 7](roadmap-progress-archive-2026-09-07.md),
  [Walk/September 8](roadmap-progress-archive-2026-09-08-walk.md),
  [timing matrix/September 9](roadmap-progress-archive-2026-09-09-matrix.md),
  [stomp/September 9](roadmap-progress-archive-2026-09-09-stomp.md), and
  [crash/September 9](roadmap-progress-archive-2026-09-09-crash.md).
- Missing evidence reopens its requirement. Some old artifacts were deleted.

### Current work table

Scope and exit criteria live in the [finite slices](roadmap.md#finite-delivery-slices).
One accepted contract does not close a whole slice.

| Slice | Owner | State | Evidence / remaining work | Next action |
| --- | --- | --- | --- | --- |
| D0 — proof workflow | root | verified | Shared checked jobs, retained evidence, failure records, and proof-input identity are in place | Reopen only for a concrete tool fault |
| D1 — reported faults | root | source-ready | Both extracted-C spawn-budget checks pass. Current ROM3500 has accepted [spawn-work](../../build/overworld-devtools/test-e26a19d2603b4669918bb7702ebf58c7/manifest.json) and [zero-stutter](../../build/overworld-devtools/test-1251857360554e29abb8a70ad459bd57/manifest.json) proof. One automatic attempt uses all240 queries, at most12 per update and exactly one profile/metadata/class preparation; maximum resumed finalizer44477 ticks is under50000. The long normal walk covers2652 measured loops and1935 moving frames with zero late loops or render stalls. Both use the unchanged Continue save (`65c36abc…`) and existing Mankey; setup earns no pacing credit | Finish scoped ticket acceptance; keep D1 open if the user reports a hitch on this ROM |
| D2 — schema/resolver/facade | root | source-ready | Conditional-profile resolver, evaluator, live controller, ABI, and packaged checks pass | Run the affected roadmap gate after the user check |
| D3 — Walk/chains/roles/Ram | root | source-ready | `NONE` and `PAUSE` are separate chain actions. A lone `PAUSE` now uses chain action chance for mounted and unmounted actors; extracted-C pass/reject checks pass. Rattata look-around converts chain ticks to its authored field-frame time; exact-C and ROM3145 memory checks pass | User checks normal bird and Rattata chain timing; a live lone-`PAUSE` chance below 100% remains unproved |
| D4 — Hop/Teleport/mount | root | active | Historical ROM3481: all three wall-skid cases, two-key recovery, newest-held direction and Ambush player-tile landing have accepted proof. The [final receipt](../../build/hit-crash-fit/final-acceptance-3481.json) binds exact runs and stopped cleanup. Earlier mounted blocker Hops are historical; Wild NPC chain-start, Pokémon-midpoint and long detach stress remain unaccepted | Keep user ride and rooftop checks open; finish only required missing Hop proof |
| D5 — world/transition/population | root | source-ready | Spawn-work and zero-stutter have current accepted proof on ROM3500 with the unchanged source save and Mankey. Current roof/signpost transition checks are part of the ticket batch; broader old transition and battle proofs remain historical | Finish the two affected surface-height checks; do not treat pacing as whole-slice closure |
| D6 — remove old paths | root | source-ready | Active, attentive, and the condition shadow bridge are removed; the linked deletion/build checks pass | Preserve through the affected roadmap gate |
| D7 — final acceptance | root | active | ROM3500 is the current player-HP candidate. The two pacing gates have current accepted proof; scoped TKT0008–0020 runtime checks are in progress. The broader ROM3481 contact/movement receipt is historical after the new profile and Query changes | Finish only required ticket gates and the user pulse appearance check; broader roadmap gaps stay open |
| Player HP — separate feature | root | active | Pokémon contact damage and shared knockback are implemented on `feature/player-hp`. Production-C storage, Actor-owner and empty-axis checks pass. The [ROM3481 contact/movement receipt](../../build/hit-crash-fit/final-acceptance-3481.json) remains historical. Current ROM3500 includes general Throw, moving HP healing, private damage/rest palettes and the Route29 allocation/rebind fixes. ROM/Delta identities match and source save is unchanged; work is uncommitted | Finish scoped current-ROM ticket acceptance. Sound/red-edge tint/bar, home rest, zero-HP, battle/capture and broader ordinary Hop roadmap checks remain outside this ticket batch |

States: queued, active, paused, source-ready, open, verified, blocked.
Verified means the whole slice has current evidence; source-ready does not.

### Active issue and next action

- D1's two required pacing gates passed on ROM3500 with the unchanged source Continue save and existing Mankey. A reported hitch on this ROM reopens the player-visible gate; zero late loops is the only tool pass.
- D3 and D4 still need the user's normal bird-chain and rooftop checks.
- The ROM3371 Wild NPC Hop proof needs a reviewed chain-start allowance; the observed primary Hop completed before a second chain Hop began.
- Next action: finish the scoped ticket cases on frozen ROM3500. Reuse accepted proof when its product, reader and recipe inputs remain unchanged.

### Current candidate and checks

- Workspace ROM: `test.nds`, SHA256
  `fe65b0c93cec5fb87a631ebf98d13a9a2fc1b66ee497ce5a6c46d26a658e3682`.
- Delta: `test3500.nds`, same SHA256. Saved Workshop open-after-build is off; the build did not open the ROM.
- The independent `test.sav` has SHA256
  `65c36abc15d442141a33cdffd682868514db6093890cb958964dd732a846eefb`;
  the untouched Delta original has SHA256
  `c98778b55bf6a018adece1457cb07de6b9fe074b69b93199d88df5a856360e91`.
- [Floaty Bounce Jigglypuff Hop pause](../../build/overworld-devtools/test-456c59a3ccab4e5a8f0d79dd039f1748/manifest.json)
  passed and was accepted on ROM3389: two complete normal Hops each retained
  10 landing-pause frames. The shared Igglybuff profile resolves the same pause;
  Igglybuff has no separate live cadence credit.
- [Mounted Stantler wall approach](../../build/overworld-devtools/test-4900d70c65264ff18e2c640568e6cc95/manifest.json)
  and its [repeat](../../build/overworld-devtools/test-a4bcc037bbee42cd89e0fa23bb7d2434/manifest.json)
  passed and were accepted on ROM3371: four cardinal Walks reach the last
  open tile (589,406), none targets the blocked wall (590,406), and an Up
  Walk commits at (589,405) with control returned.
- Historical [Mounted static Hop](../../build/overworld-devtools/test-eddfb5435e3e48dea31c012eb767fc4f/manifest.json),
  [Wild static Hop](../../build/overworld-devtools/test-664e8347ea194cd98578d3474549ca18/manifest.json),
  and [Mounted NPC Hop](../../build/overworld-devtools/test-d086df5f08e643d29867ce663b67e496/manifest.json)
  passed and were accepted. The [Wild NPC Hop](../../build/overworld-devtools/test-46907c993dd14da791517f33cc9fcf31/manifest.json)
  completed the first two-tile Hop but is not accepted: a second chain Hop
  started on the landing frame, while its proof requires exactly one start.
- The build passed Actor, Wild, Field terrain, mount, spawn identity, occupancy,
  move-history, conditional-profile, and packaged-ROM gates.
- ROM3365 diagnostic memory data: mounted Stantler jumped from (580,397) to
  (582,397) across blocked (581,397) in 16 frames, then resumed Walk and
  accelerated. Wild Stantler did the same from (573,395) to (573,397) across
  blocked (573,396). These recordings are not accepted proof.
- The following ROM3359 mounted results are history. Their changed Sprint
  profile and movement source inputs make them stale for ROM3365.
- The [mounted Stantler route](../../build/overworld-devtools/test-d4bbececeaed4ae8baa90b5ba70000b0/manifest.json)
  passed and was accepted on ROM3359: 840 route frames kept 9/9 nearby
  terrain cells loaded, followed by 25/25 recovery frames and more than
  eight tiles of movement. The earlier ROM lost terrain and faulted on Select.
- The [Stantler skid turn](../../build/overworld-devtools/test-8d421fb2b67b4565ae4c0b6b5ae7d738/manifest.json)
  passed and was accepted on ROM3359: eight east-travel skid frames kept
  the Down-facing turn before recovery. Old-facing and short-skid controls
  were rejected.
- The [Stantler Sprint proof](../../build/overworld-devtools/test-a4b42606976f4b3d8ed88252a0efaddc/manifest.json)
  passed and was accepted on ROM3359: acceleration to speed four, two
  forward chain Hops, and cardinal-only input.
- The [mounted map-crossing proof](../../build/overworld-devtools/test-b7a3c9ad1b5543f5bf234692395674a0/manifest.json)
  and [mid-run Select proof](../../build/overworld-devtools/test-2ede705e9e2b4eae9bd7a20955cc5c17/manifest.json)
  both passed and were accepted on ROM3359. The latter held Right through
  handoff and resumed the same Mankey mount after five frames.
- The [current owner-reader control](../../build/overworld-devtools/test-b1a09649cf9a4f18a3a1d09798622af9/manifest.json)
  passed and was accepted on ROM3359.
- The [long mounted control run](../../build/overworld-devtools/test-b69ca5d4af7540bcaeb7cbb015f7134a/manifest.json)
  on ROM3357 completed 24,032 observed frames without a freeze. It failed at
  Select: its fixed-profile check rejects the Follower policy restored in
  that frame, and its fixed route reached only 1,498 of the required 2,000
  motions. This is not accepted proof.
- The following spawn-work, zero-stutter, and conditional-profile results were
  accepted on ROM3287. They are not proof for the changed ROM3365.
- The [spawn-work proof](../../build/overworld-devtools/test-720a1d96329e4641a7d09f706364d1aa/manifest.json)
  passed and was accepted on ROM3287: 21 destination updates, 169 candidate
  queries, at most 12 per update, one profile/metadata/class preparation, one
  normal Hoothoot spawn Hop, 137 moving frames, and zero late loops or render
  stalls.
- The [zero-stutter proof](../../build/overworld-devtools/test-ec8c77e3840c4f89ae44ef8bfff56952/manifest.json)
  passed and was accepted on the same ROM and unchanged Continue save: 2,620
  observed frames, 1,935 moving frames, and zero late loops or render stalls.
- [Packaged resolver parity](../../build/overworld-devtools/test-706d2f9f2d9b4224bcc3b63afec00671/manifest.json),
  [packaged condition evaluation](../../build/overworld-devtools/test-b2c466b24fbd4df9806ef832282d27a0/manifest.json),
  and the [live Wild condition controller](../../build/overworld-devtools/test-d16169e8d70741088748bfcf026a99d9/manifest.json)
  passed and were accepted on ROM3287. The live controller proof includes
  trigger, held activation, and stale-target fail-close behavior.
- The ROM3143 [Hoothoot chain data](../../build/overworld-devtools/session-ml43dg3r/recording-ec49a9f3e111.json.gz)
  is memory evidence, not acceptance proof. The resolved Bird profile used
  action `PAUSE` (`6`); after its linked movement, the actor entered a 24-tick
  passive wait with no visual chain action.
- ROM3145 [Rattata look-around memory data](../../build/overworld-devtools/session-zf4z6i62/recording-36912f82eaaa.json.gz)
  measured 22, 26, and 28 chain ticks as 44, 52, and 56 field frames. The
  [pre-fix data](../../build/overworld-devtools/session-_lys0g_l/recording-1a9bc7c6901d.json.gz)
  measured a 20-tick action as only 20 field frames. These recordings are
  diagnostic memory evidence, not accepted proof.
- The extracted production reducer and Wild adapter pass separate `NONE`,
  `PAUSE`, and full-frame look-around cases. The current exact-Wild-Walk test
  is not accepted because its independent Wild-clear control is stale and its
  replacement control failed `wild Walk idle no-op clear differs`.

### Session and candidate ownership

- Root owns integration on `feature/conditional-profiles`; preserve
  dirty work.
- Use melonDS shared tools only. No images or video. Do not add a private driver.
- Inspect `dev status` and `dev test status` before live work. Do not take over
  another owner. Tests own a fresh private session.
- Preserve source ROMs, saves, the user's emulator, and the saved build-open
  preference.

### Completion

The roadmap is not complete. Recorded status is not final acceptance. The frozen
candidate must pass all required current proof and
`scripts/owctl verify roadmap --rom test.nds --json` must report `passed: true`.
