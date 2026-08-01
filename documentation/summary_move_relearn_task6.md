# Summary Move Relearn Task 6: unusual ownership paths

Task 6 audits permanent learned/forgotten-move history outside the ordinary
script setter, level-up, evolution, Move Reminder, tutor, and party/PC Summary
paths already covered by tasks 1–5. The named vanilla HeartGold source under
`.codex-reference/pokeheartgold/` is the behavioral authority. All task-6
hooks call task-3 history APIs; there is no second history store.

## Path matrix

| Path | Identity class | Canonical owner / commit | Existing task-3 observation | Task-6 handling |
| --- | --- | --- | --- | --- |
| Script `SetMonMove`, tutors, Move Deleter, battle EXP and evolution selection | Existing mutation | Player `PartyPokemon`; confirmed setter return | Yes | Unchanged; task-3 replace/delete/record hooks remain the sole owner. |
| `GiveMon`, starter, script gifts, Mystery Gift, NPC loan | New identity creation/import | Successful `PokeParty_Add` into the live player party | No first-observation baseline | The sole success tail advances party count, verifies the canonical player party, then seeds its committed slot. Full-party/failure and enemy/temporary parties do not observe. |
| Script-created eggs and Togepi egg | New identity creation | Successful player-party add while still an egg | Deliberately rejected | Eggs remain fail-closed. No parent or pre-slot history is allocated. |
| Hatch completion | Same new identity becoming usable | Hatch task clears `MON_DATA_IS_EGG` on the canonical party owner | Save-time fallback only | Path-specific wrapper performs the retail clear first, then seeds the inherited/current permanent moves as the first baseline. |
| NPC in-game trade | Existing outgoing plus new incoming identity | `NPCTrade_ReceiveMonToSlot` canonical slot copy after the animation | Neither side at this boundary | Capture outgoing snapshot without dirtying; after the infallible slot copy, record it and seed the received identity. Cancel never reaches the call. |
| Local/wireless party trade | Existing outgoing plus new incoming identity | Overlay 65 successful live party-slot replacement after communication/animation | Save-time fallback only | The success commit uses the same resident transaction as NPC trade: snapshot outgoing, perform the retail slot copy, record outgoing, then seed the canonical received owner. Disconnect/cancel never reaches the commit. |
| GTS deposit/export | Existing outgoing identity | Overlay 70 canonical box or party removal after a successful offer/paired exchange | No | Capture the selected canonical owner before removal, execute retail deletion, and record the snapshot only after the box delete or successful party remove. Failure/cancel states never reach these commits. |
| GTS receive with party space | New incoming identity | Successful `Party_AddMon` | Yes | The player-party success tail seeds the committed arrival; full/failure paths do not observe. |
| GTS receive with a full party | New incoming identity | Overlay 70 successful first-empty PC placement | No | Both receive variants resolve the exact empty slot before the retail placement, then seed only its canonical destination after success. Failure/cancel remains history-clean. |
| GTS trade-triggered evolution copy-back | Existing identity species mutation plus pure relocation | Named retail `ov70_022418A4` after the evolution scene | Existing evolution/move hooks; deliberately no copy-back hook | The prior receive seed establishes the PID/OTID record. Any permanent evolution-scene move mutation is recorded against that same identity. Party copy-back and boxed delete/first-empty replacement only relocate the evolved canonical owner and do not count as learning; current species/form drives candidates. Failure before copy-back leaves the save owner unchanged. |
| Ordinary party/PC box transfer | Pure transfer | Existing tasks 3–4 canonical transfer ownership | Yes | Unchanged; identity key and acquisition order survive without treating transfer as learning. |
| Rotom appliance/form rewrite | Existing mutation and form change | `Mon_UpdateRotomForm` on a persistent owner | Direct setters were missed | Reject form indices outside 0–5 before table access; route each replacement/deletion through task-3 APIs. Current-form Summary policy admits only that form's proved special move. |
| DNA Splicer Kyurem rewrite | Existing mutation and form change | Permanent party-menu fuse/separate commit | Direct helper setter was missed | `SwapPartyPokemonMove` receives an explicit permanent-history flag. Splicer and permanent form callers use task-3 replace; battle copies use retail transient writes. |
| Evolution with explicit target form zero | Existing identity species/form change | Evolution scene canonical species/form setters | History identity already stable; form-zero presence was lost | Evolution data carries a separate explicit-form marker, so form zero is written rather than inheriting an old form. Candidate rebuilding always uses the resulting canonical form. |
| Wormadam Sandy/Trash lineage | Existing species/form candidate semantics | Read-only candidate build | Parent generator omitted derived cloak species | Both derived cloak species resolve to Burmy for legal historical move filtering. |
| Daycare deposit | Pure transfer of existing identity | Retail daycare copy/remove function | No boundary observation | Call the retail commit, then seed the canonical deposited `DaycareMon`. Party cancellation before the commit is history-clean. |
| Daycare level-up with empty slot | Existing mutation | `MonTryLearnMoveOnLevelUp` append | Yes | Existing task-3 successful append hook remains authoritative. |
| Daycare level-up with full set | Existing replacement | The one daycare call to `DeleteMonFirstMoveAndAppend` | No | Resident wrapper observes the owner, executes the infallible retail shift, and records the appended move once. Egg-construction calls to the same retail helper are untouched. |
| Scripted daycare sanitizer / Mirror Herb inheritance | Existing mutation of either owner | Successful canonical move+PP write to the selected party `PartyPokemon` or deposited `DaycareMon` | Direct setters were missed | Each owner filters its own legal egg-move buffer/current set, then records through the resident task-3 transaction. Both callers compute max PP from the incoming move with zero PP Ups before mutation. The resident helper atomically writes the move, resets PP Ups, writes PP, then records. Party and deposited histories never share donor or scratch-buffer state. |
| Daycare withdrawal | Pure transfer | Successful `PokeParty_Add` | No explicit withdrawal hook | The canonical party-add success hook seeds the same PID/OTID record after withdrawal; it does not allocate a second identity. |
| Egg generation/inheritance | New identity construction | Temporary egg construction, then party add as egg | Intentionally none | Construction buffers and parent moves never observe. The accepted inherited/current set becomes baseline only at hatch completion. |
| Pokéwalker export | Pure transfer | Canonical PC lookup immediately before serialization/delete, followed by either IR status-15 acknowledgement | No | The lookup captures a non-dirty resident pending snapshot. The two distinct status-15 call sites enter separately pinned resident stubs at `0x023BD480` and `0x023BD488`; both advance retail first and then share one consume-once commit. Preparation, serialization, deletion, and forced-save steps do not allocate, touch, or evict history. |
| Pokéwalker successful return/catch placements | Existing transfer or new import | Three successful `PCStorage_PlaceMonInBoxByIndexPair` calls | No | Place first, resolve the canonical destination, then seed. Existing PID/OTID resumes one record; a new arrival receives one baseline. |
| Pokéwalker recovery/cancel | Failed transfer recovery | Complete retail recovery helper `ov112_021EC134` | None | A wrapper at `0x023BD490` runs retail restoration first and then discards pending history unconditionally, including a missing/corrupt Walker copy that skips the internal placement at `0x021EC182`. Named overlay-112 instructions prove the retail caller passes its live non-null application owner. A `NULL` argument is therefore reserved for sealed direct-ROM acceptance and skips only the unmapped overlay helper while executing the same real resident discard boundary. No history image, access sequence, revision, dirty flag, or unrelated record may change. |
| Castform/Cherrim battle forms, battle Kyurem/Zacian/Zamazenta, `NEEDS_REVERSION` extended forms | Temporary/battle-only | Battle copies, not save owners | Not applicable | Rejected by the canonical permanent-owner gate or explicitly routed through transient setters. They never enter permanent history or Summary relearn. |

## Integrity and ownership rules

- `IsCanonicalPermanentBoxPokemon` is shared by capture, candidate building,
  and Summary entry. It rejects null, empty, egg, Bad Egg, checksum-failed,
  out-of-range species/form, transient classic forms, unregistered extended
  forms, and extended forms marked `NEEDS_REVERSION`.
- Every successful mutation continues to use encrypted `GetBoxMonData` /
  `SetBoxMonData` accessors or a retail canonical copy routine; task 6 never
  edits encrypted substructures directly.
- History is keyed only by personality and OT ID. Transfer and species/form
  changes retain the record and deterministic acquisition order. New identity
  baselines are created only from the committed canonical owner.
- History dirty/revision changes follow task-3 APIs. Preview, animation,
  communication failure, full-party failure, egg construction, and temporary
  transit buffers do not allocate or dirty records.
- Pokéwalker export pending state is transient overlay-155 memory, not a
  second history store. The sealed emulator harness sends monotonic,
  task-6-only requests through the zero-initialized mailbox at `0x023BD4A8`.
  The source-linked boot-resident field-ready SysTask call at `0x023D9ABC`
  enters the wrapper at `0x023BD4A0`, which preserves the original overlay-131 poll
  and returns immediately unless the exact magic/version/sequence tuple is
  armed. The dispatcher resolves `SaveBlock2_get` and save array 41 in-ROM,
  owns its `0x134`-byte Walker buffer, and calls the packaged stage, both ACK,
  and recovery entries at `0x023BD420`, `0x023BD480`, `0x023BD488`, and
  `0x023BD490`. Read-only execution callbacks authenticate those exact hits;
  the host never rewrites ARM9 PC, CPSR, or prefetched instruction state.
  Missing-record
  and full-319-record cancellation fixtures compare the real task-3 store,
  complete metadata, oldest record, access sequence, revision, dirty flag,
  and unrelated records byte-exact. Each ACK entry is invoked twice; only the
  first call after staging may allocate/record and advance history revision.
  The host model remains a non-probative oracle rather than execution proof.
- Save ownership is unchanged: the primary save/box/daycare/Pokéwalker code
  marks its ordinary owner dirty and task-3 prepare/finish/cancel publishes the
  sidecar transaction. Task 6 adds no independent save or commit path.
- Summary special-move admission is fail-closed and species/form scoped to
  proved Rotom and Kyurem rewrites. Persisted presence alone is never legality.

## Runtime evidence boundaries

- Actual retail/script evidence uses the Route 34 daycare lady's script 9501.
  The authenticated fixture walks through the real door, proves the script
  callback at map 331 `(3,7)`, and exercises both chooser cancel and slot-2
  STORE/confirm. The success path proves reciprocal party/deposited-owner move
  rewrites, nonzero max PP with zero PP Ups, exactly one append per PID/OTID,
  unrelated records and all 900 PC slots unchanged, and retail save/reload.
- Trade, Rotom form, egg/hatch, and Pokéwalker serialization evidence uses real encrypted
  `0x88` BoxPokemon records, both authenticated PC save generations, and both
  sealed task-3 history mirrors. Trade cancel is byte-exact; form 32 rejects
  before mutation; eggs remain history-free until the egg bit is canonically
  cleared; and Pokéwalker recovery restores the complete save byte-for-byte.
  The unavailable peripheral serialization leg alone is labelled a
  source-exact surrogate. Transaction-boundary evidence is ROM-executed:
  the harness arms the fixed resident mailbox and lets the game-native
  field-ready poll call the fixed entries, uses a real canonical PC owner and
  the live task-3 save pointer, and supplies a private real RAM
  `POKEWALKER`-shaped buffer to the retail ACK routine
  (named `sub_02032644`, whose only mutation is the `u16` at offset `0x124`).
  It authenticates every entry hit and the completion release word without
  interrupting CPU context. The consumed magic prevents crash/retry replay;
  completion sequence is published last, and the zero-magic retail path only
  performs the unchanged original poll plus an inert comparison. The surrogate
  separately verifies exact export/import records,
  PC CRC ownership, round-trip identity/history, new-arrival baseline, reparse
  persistence, and all 900 boxed checksums.
- Candidate ordering and known-move exclusion remain proven by the task-2
  builder/source-static gate; the serialization surrogate does not model or
  claim execution of that builder.
- Screenshots and exported saves are evidence artifacts, not path-only
  claims. Every emulator process writes them by sibling-file atomic replace,
  freezes the regular file by canonical path and inode, and publishes each
  reference as `{path,size,sha256}`. ROM, manifest, result, preserved DSV, and
  controlled fixture paths are protected against output aliasing. Child
  results authenticate canonical JSON and their complete artifact set; the
  parent verifies the records against the live files before embedding them.
  Paths, descriptors, sizes, hashes, result bytes, and the sealed runtime
  closure are reauthenticated after atomic publication or a stdout-only child
  flush. Mutation, substitution, hard-link/symlink aliasing, and stale-result
  reuse therefore fail closed.

## Sealed emulator runtime closure

- The container build publishes the ROM/build pair with an explicit unbound
  runtime slot. After that managed build succeeds, and before Delta receives a
  copy, the managed wrapper compiles the sealed native trust anchor without a
  random Mach-O UUID (`-Wl,-no_uuid`) and ad-hoc signs it without a timestamp
  with the exact hardened-runtime, restrict, library-validation, hard, and kill
  CodeDirectory policy,
  then invokes the host runtime binder through that anchor. This makes repeated
  verifier and Workshop compilations byte-reproducible instead of replacing a
  published bootstrap with a semantically equivalent, differently hashed
  binary. The binder
  atomically records the bootstrap binary, committed inventory, source,
  build/link command, compiler identity, code-directory hash, and sole linked
  image before verifying the bound manifest again. An unbound or partially
  replaced manifest cannot launch acceptance.
- The native bootstrap runs before CPython. It contains an internal SHA-256
  implementation and links only Apple-protected `libSystem`; it does not load
  OpenSSL, CommonCrypto, Python, or repository code in its own pre-main closure.
  Its committed inventory individually records the exact repository venv
  symlink chain and `pyvenv.cfg`, canonical Python executable/framework,
  complete pycache-excluding standard library, required-absent
  `python310.zip`, all retained runtime sources, complete DeSmuME and Pillow
  trees, `libssl`, `libcrypto`, and the remaining mutable native closure.
  Regular leaves are opened without following symlinks. Symlink hops and their
  parent directories are retained separately, and the exact alias chain must
  resolve to the canonical executable.
- The inventory also seals the exact canonical directory graph for every
  importable standard-library, DeSmuME, Pillow, retained-source, and mutable
  native closure directory. Each membership record hashes a domain-separated,
  raw-byte-sorted sequence of length-prefixed entry names and regular,
  directory, or symlink types from a retained `O_NOFOLLOW` directory
  descriptor. Unsupported filesystem types and all tree symlinks except the
  two reviewed framework `libpython3.10` links fail inventory generation.
  `__pycache__` and framework `site-packages` descendants are named by their
  sealed parent membership but deliberately not traversed: exact `-S`, `-B`,
  `/dev/null` pycache, normalized `sys.path`, and the source/extension-only
  loader make them non-importable. Any new package shadow, direct bytecode,
  extension, archive, link, rename, or entry-type substitution changes a
  monitored membership digest before Python can run.
  Every sealed regular or executable leaf also requires an `M` record for its
  immediate parent. This includes the framework `bin` directory and
  `Python.app/Contents/MacOS`, so a sibling executable, extension, or package
  cannot appear beside an otherwise exact leaf. The final graph contains 150
  membership directories.
- Every retained descriptor is hashed before fork and watched with
  `EVFILT_VNODE` for write, extension, delete, rename, link, revoke, and
  topology changes. The bootstrap sanitizes the entire child environment and
  executes only the authenticated `.venv/bin/python3` alias. Before fork it
  validates the exact argv prefix `-I -S -B -X pycache_prefix=/dev/null` and
  an individually authenticated approved entry path (runtime launcher or
  publication binder); dropped, reordered, or extra interpreter flags fail
  closed before CPython. Python must publish the exact READY
  message; the native parent then rehashes every descriptor and canonical path
  before returning GO. Monitoring continues until child exit, followed by one
  final complete descriptor/path reauthentication. The event queue is drained
  in 64-event batches to empty, retries interruption, and fails closed on any
  data/topology event or a bounded continuous backlog; attribute-only events
  require immediate exact record reauthentication. A sealed native self-test
  consumes and authenticates the first 64 non-decisive events from the same
  production kqueue, then proves the production drain rejects the later write.
  Native stale-result targets are collected before strict argv parsing and
  unlinked without following the final node. Regular files, symlinks, FIFOs,
  and sockets are removed; directories, permission failures, and every error
  other than `ENOENT` fail closed. Malformed and overflowing argv therefore
  cannot preserve a prior passing result. Child ownership and saved wait status
  are centralized: stopped/pre-GO/EPIPE failures close the protocol, signal
  only an unreaped owned PID, and reap within a five-second bound. A one-second
  hostile READY fixture proves bounded cleanup for stopped, exited, and
  closed-pipe children with no surviving process group.
- The dropped-`-S` regression uses a real temporary `.pth` in the canonical
  venv `site-packages`: direct isolated Python without `-S` first proves that
  the marker runs before the script, then the native anchor proves the same
  argv is rejected without a marker or stale result. The fixture is removed in
  a `finally` boundary; the exact flag set skips it.
- This closes the former six-module pre-script gap. A canonical `abc.py`
  fixture writes a marker, atomically restores its original sealed bytes, and
  then executes the original module; direct Python proves that payload runs and
  defeats a later Python hash, while the native launch rejects it before the
  marker exists. A separately compiled `libssl.1.1.dylib` wrapper uses a real
  constructor, restores the original canonical dylib, and re-exports its
  symbols; direct `_hashlib` loading proves constructor execution, while the
  native launch again rejects it before the marker. Both negative runs also
  prove stale-result removal. Existing calibrated `PYTHONPATH`, `.whl`,
  arbitrary archive, direct `.pyc`, `.pth`, `sitecustomize`, `__pycache__`,
  flag-drop, environment-drop, and child-propagation fixtures remain.
- A deterministic package-before-module fixture adds
  `hashlib/__init__.py` beside sealed `hashlib.py`, proves direct exact-flag
  Python executes the package first and self-removes it, then proves the native
  directory closure rejects the same membership before fork with no marker or
  stale result. Separate direct-`.pyc` and new-symlink negatives cover entry
  names/types, and the authoring generator is required to reject the symlink.
- The root of trust is stated narrowly. The managed external caller supplies
  reviewed native-bootstrap SHA-256 and CDHash constants. The build helper
  independently authenticates the signed temporary candidate, atomically moves
  it into place, and repeats full-file hash, CDHash, strict CodeDirectory,
  entitlement, linkage, and no-UUID checks on the published path. It never
  executes the published file to derive identity; an after-`mv` substitution
  fixture calibrates a valid self-reporting ad-hoc replacement and proves final
  publication fails. Darwin AMFI enforces
  the ad-hoc code-directory page hashes plus hardened/restricted/library
  validation before `main`, and the bootstrap verifies that same
  external digest from its own retained canonical descriptor. Pre-main trust is
  limited to the kernel, dyld shared cache, and Apple-protected `libSystem`.
  The signature superblob is parsed structurally and must contain exactly the
  CodeDirectory, requirements, and CMS-wrapper slots; XML and DER entitlement
  slots are absent, `codesign` emits an empty dictionary, and the manifest
  records the exact empty key set plus full CodeDirectory and superblob hashes.
  Re-signed `get-task-allow` and `allow-unsigned-executable-memory` fixtures
  retain the old hardened flag string yet are rejected. A real constructor fixture first
  calibrates `DYLD_INSERT_LIBRARIES` and `DYLD_PRINT_TO_FILE` against an
  intentionally unprotected copy, then proves the exact published bootstrap
  creates neither constructor marker nor dyld log while still invalidating
  stale evidence. Ad-hoc identity by itself is explicitly not claimed as an
  identity root, and
  macOS has no usable unprivileged `fexecve`/`execveat` equivalent. The retained
  alias/canonical descriptors, vnode monitoring, READY/GO barrier, and repeated
  identity/hash checks bracket that unavoidable path-based `execve` handoff.
- After GO, Python still requires `isolated=1`, `ignore_environment=1`, no site,
  no bytecode, the `/dev/null` pycache sink, the normalized source/extension-only
  path hook, and the manifest-recorded native-bootstrap environment. It then
  authenticates the publication manifest, ROM, loaded module origins/loaders,
  and runtime closure before any retained helper runs. This inner validation is
  defense in depth and publication authentication; it is no longer the
  pre-Python trust anchor.
  The bound manifest records and revalidates the exact policy. The host binding
  content-addresses the canonical Python entry and resolved
  executable, the linked Python shared runtime, `pyvenv.cfg`, and a
  pycache-excluding tree of standard-library source/native modules. It also
  seals the complete DeSmuME and Pillow package trees, the exact
  `desmume.__init__`, `i18n_util`, `controls`, and `emulator` sources, the
  canonical `libdesmume`, and every allowed mutable native image.
- Before any retained helper or manifest-helper code executes, the launcher
  independently recomputes that primitive closure. DeSmuME Python modules are
  compiled directly from the retained authenticated buffers. Pillow Python
  modules are served only from retained source buffers through the already
  loaded frozen import bootstrap; timestamp-valid `.pyc` files and ordinary
  source loaders are not consulted. The exact canonical `libdesmume` path is
  hashed before load, loaded explicitly, and rehashed with stable file
  identity immediately afterward.
- At both the pre-helper and final reauthentication boundaries, every loaded
  Python module is enumerated. Builtin and frozen origins are accepted; source
  and extension origins must resolve canonically inside the content-addressed
  standard-library, native, package, or retained-source closure with the exact
  expected loader. `zipimporter`, `SourcelessFileLoader`, path/finder mutation,
  module-origin aliasing, and an unsealed loader fail closed. Hostile bootstrap
  fixtures calibrate and then reject `PYTHONPATH` source, `.whl`, an archive
  with an arbitrary suffix, direct `module.pyc`, user `.pth`, `sitecustomize`,
  standard `__pycache__`, missing interpreter flags, and environment leakage.
  A calibrated canonical-stdlib poison fixture separately proves the payload is
  executable through an ordinary source loader, then proves stage zero detects
  the changed tree, removes stale evidence, and never executes the payload.
- Native image enumeration uses dyld's in-process image list on macOS and
  `/proc/self/maps` on Linux. Every loaded image outside the documented
  OS-owned roots must be present in the manifest's mutable closure. The trust
  boundary is limited to `/System/Library`, `/usr/lib`, and the OS Cryptex
  equivalents on macOS, or `/lib*` and `/usr/lib*` on Linux. In particular,
  the Python framework/runtime, Pillow extensions, `libdesmume`, SDL2, GLib,
  Intl, and PCRE2 remain content-addressed rather than delegated to that OS
  boundary.
- The complete runtime trees, retained buffers, mutable native image set,
  ROM, publication manifest, helpers, and evidence artifacts are rehashed at
  the end. The same version-3 authentication object is compared by every
  isolated parent/child process, so environment substitution cannot be hidden
  behind a successful child result.

Task 7's all-compatible testing mode is deliberately excluded.
