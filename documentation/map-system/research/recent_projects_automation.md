# Recent Gen 4 (HGSS/Platinum) projects, automation, and AI/agent tooling for map work (2023–2026)

Research date: 2026-10-15. I used about 20 web searches and fetches. Several primary pages, mainly GitHub landing pages, did not show dates or licenses in the fetched text. Those gaps are marked below.

## Libraries (Python/Rust/JS/Java) that parse or write Gen 4 maps, events, and matrices

### Takeaway
The most agent-friendly library found is **uxie**, a Rust crate and CLI with `--json` output. It reads map headers, events, encounters, and scripts from DSPRE project folders or from the pokeplatinum/pokeheartgold decomps. It is read-oriented, and its HGSS support is partial. No mature Python or JS library that writes Gen 4 maps, events, or matrices was found. Writing still means generic NARC tooling (ndspy, nitroarc) plus your own codecs built from the format documentation.

### Cited Findings
- **uxie 0.9.5** (published 2026-10-04) is a "data fetching library for Pokemon Gen 4 romhacking." It is MIT-licensed. The bundled `nitroarc` submodule is LGPL-3.0-or-later, and the page recommends shipping `nitroarc_ffi` as a separate shared library. The repo is github.com/kalaay/uxie (also KalaayPT/uxie). — [docs.rs uxie](https://docs.rs/crate/uxie/latest)
- uxie CLI commands: `header`, `map`, `event`, `encounter`, `symbols`, `personal`, `move`, `item`, `trainer`, `evolution`, `learnset`, `egg-moves`. Most accept `--json` and `-p/--project`. `-d/--decomp` sets a decomp path for symbol resolution. It handles script mappings, a global script table for `CallCommonScript` resolution, and bidirectional constant/value resolution from C headers. — [docs.rs uxie](https://docs.rs/crate/uxie/latest)
- uxie auto-detects DSPRE projects (`arm9.bin` + `unpacked/`) and decomp sources (pokeplatinum, pokeheartgold). Platinum support is the most complete; HGSS is "improved but partial." The page does not mention matrices or write support. — [docs.rs uxie](https://docs.rs/crate/uxie/latest)
- Earlier uxie versions (0.4.0, 0.5.x, 0.7.0) are on docs.rs, which shows active iteration. — [uxie 0.4.0](https://docs.rs/crate/uxie/0.4.0), [uxie 0.7.0](https://docs.rs/crate/uxie/0.7.0)
- ndspy is a general Python library that "reads, modifies, and creates many types of files used in Nintendo DS games." I found no Gen 4 map-specific module. — [ecosyste.ms ndspy usage](https://repos.ecosyste.ms/usage/pypi/ndspy)
- Project Pokémon documents the Gen 4 binary map structure. For example, D/P maps are stored under `fielddata/landdata`. — [Project Pokémon: Map Structure](https://projectpokemon.org/home/docs/gen-4/map-structure-r29/)
- Gen IV matrix files lay out how maps are situated in the world and connect, and the game uses them to pair headers with maps. HGSS stores them at a different numbered NARC path than DPPt. — [PokéCommunity: Map matrix files Gen IV](https://www.pokecommunity.com/threads/map-matrix-files-gen-iv.353897/)
- **PokEditor** (turtleisaac) is a Java, OS-agnostic Gen 4 data editor that requires Java 20. Its backend, **PokEditor-Core**, is a separate library for "reading and writing various forms of game data for the Gen 4 Pokémon games." Its listed editors cover personal data, learnsets, evolutions, moves, and sprites, not maps. — [PokEditor mirror](https://identichosting.duckdns.org/turtleisaac/PokEditor), [PokEditor-Core mirror](https://identichosting.duckdns.org/turtleisaac/PokEditor-Core)
- **Pokémon Sinjoh Editor** (GreyLily3) is a Gen 4 ROM hacking tool for DPPt and HGSS. Its source is at github.com/GreyLily3/Pokemon_Sinjoh_Editor. — [Project Pokémon file page](https://projectpokemon.org/home/files/file/5751-pokemon-sinjoh-editor/)
- pret/pokeplatinum uses custom compilers in `tools/dataproc` that turn plain-text data (mainly JSON) into binaries and NARCs via libnitroarc. Its tooling includes the nitroarc C library and CLI and NitroBTX for NSBTX textures. This comes from a third-party indexer summary. — [Algolia DocSearch summary of pret/pokeplatinum](https://docsearch.algolia.com/mcp/docs/repo/pret/pokeplatinum)

### Inferences
- For a headless HGSS map pipeline, uxie fits as a **read and validation oracle** (dump headers and events as JSON, then resolve script and constant names). Writes would still need a custom encoder for event files, matrix files, and map containers (`land_data`: permissions, BDHC, NSBMD), using ndspy or nitroarc for NARC packing.
- The nitroarc CLI from the pokeplatinum ecosystem is a likely candidate for deterministic NARC pack/unpack in CI, but check its license (LGPL) and HGSS compatibility.
- hg-engine already builds from source with `make`. A source-of-truth format such as JSON or YAML for events, headers, and matrices, compiled to NARCs at build time, would mirror pokeplatinum's dataproc approach and suit agent edits better than binary patching.

### Gaps
- No "Hotpot" Gen 4 library was found under that name. The closest matches were PokEditor/PokEditor-Core.
- No JS/TypeScript Gen 4 map library was found.
- I could not confirm whether uxie writes data or parses matrices. Its docs page lists only reads.
- I could not confirm PokEditor-Core's license or last-release date from the mirror.

## Randomizers and map-shuffle tools that rewrite warps

### Takeaway
The only HGSS warp randomizer found is **adrienntindall/hgss-map-randomizer** (C++, Windows exe) and its 2026 clean-room Kotlin port **kotlinds/pokemon-map-randomizer** (Apache-2.0, GUI+CLI, HG/SS/B2/W2). They rewrite warp destinations programmatically and keep the game beatable. Their warp data and block constraint files are reusable references for HGSS warp graphs. UPR ZX/FVX do not randomize warps.

### Cited Findings
- kotlinds/pokemon-map-randomizer: Apache License 2.0. It is a "clean-room Kotlin/Multiplatform rewrite" of adrienntindall/hgss-map-randomizer. It credits that project for the algorithm, block constraint files, and warp data. Release 1.0.2 came out about 7 months before the fetch (around March 2026), with no activity since. It has 1 star. — [klibs.io project page](https://klibs.io/project/kotlinds/pokemon-map-randomizer)
- CLI: `./app <rom> <game> [seed|-] [season] <outputDir>`, with games `hg`, `ss`, `b2`, `w2`. It outputs `<name>_map_randomized.nds` and a `.log` of warp connections and the seed. It requires JDK 17+, and `./gradlew :core:jvmTest` runs its tests. — [klibs.io](https://klibs.io/project/kotlinds/pokemon-map-randomizer)
- It keeps beatability: every gym, story event, and progression gate is reachable from the start. It supports EN/FR/DE/ES HGSS ROMs. — [klibs.io](https://klibs.io/project/kotlinds/pokemon-map-randomizer)
- The original C++ repo "Randomizes warps in Pokemon Heart Gold and Soul Silver." It has 65 commits, ships `map_randomizer.exe`, `HGSSMiscInfo.txt`, `HowToUse.txt`, and `src/`, `tools/`, `files/`, and shows no visible LICENSE file. — [adrienntindall/hgss-map-randomizer](https://github.com/adrienntindall/hgss-map-randomizer)
- UPR ZX (Ajarmar) and the UPR FVX fork (foxoftheasterisk + voliol) randomize Pokémon, trainers, items, and similar data across Gens 1–7. No warp or map randomization was found. — [UPR ZX](https://github.com/Ajarmar/universal-pokemon-randomizer-zx), [UPR FVX](https://github.com/upr-fvx/universal-pokemon-randomizer-fvx)
- A Pokémon Crystal map randomizer (Gen 2) exists as a similar reference design. — [choatix/pokemon-crystal-map-randomizer](https://github.com/choatix/pokemon-crystal-map-randomizer)

### Inferences
- The Kotlin core (Apache-2.0, with JVM tests) is the most reusable code here for reading and writing HGSS warp tables and modeling the progression graph. An agent could use it as a reference warp codec and for its HGSS block/gate constraint data. Those data files are licensed through the original author, so check the license before copying.
- A beatability or reachability checker over the warp graph would serve as a static "map test" for new maps, for example "every new warp has a matching return warp and every map is reachable." It would complement in-emulator tests.

### Gaps
- I did not verify which NARCs the randomizers edit. They are probably zone event files (`a/0/3/2` in HGSS), but no fetched source confirmed this.
- The C++ original's language, license, and last-commit date were not visible on the fetched page.
- No Platinum warp randomizer was found in this pass.

## hg-engine community: map features, tooling, and hacks with new maps

### Takeaway
Upstream hg-engine (BluRosie) is a battle and engine overhaul. Its README describes no map features, map editor, or map docs, only `data/Encounters.c` and `data/Trainers.c`. DSPRE explicitly marks hg-engine ROMs as "partial support, some editors disabled," so mainstream map tooling and hg-engine conflict. No public hg-engine hack documenting a large new-map workflow was found.

### Cited Findings
- hg-engine is "an engine overhaul for English Pokémon HeartGold," with 373 stars, 418 forks, and about 4,771 commits. Features include a Pokédex expanded through Gen 6, abilities up to 512, Megas, Fairy type, and 30 PC boxes. The README describes no map features. — [BluRosie/hg-engine](https://github.com/BluRosie/hg-engine)
- Its build is `make` and produces `test.nds` from `rom.nds`. It needs gcc-arm-none-eabi, libpng, and rustup, with Docker supported. It runs on Linux, macOS (Rosetta may be needed on Apple Silicon), and Windows via WSL/MSYS2. Instead of a formal license it has community terms: no money, derived hacks stay free, credits carried over. — [BluRosie/hg-engine](https://github.com/BluRosie/hg-engine)
- DSPRE's README lists hg-engine ROMs as "Partial Support … Some editors disabled." — [DSPRE GitHub](https://github.com/DS-Pokemon-Rom-Editor/DSPRE) (as summarized in search results)

### Inferences
- In this repository, the Samefisk fork includes a scripted battle tester (`AUTO_TEST=Y`, `data/battle_tests`, `scripts/run_tests.sh`). This comes from the local `hg-engine-battle-tester` skill description, not a web source. It is the closest existing precedent for an automated in-ROM test harness and could be extended to map and warp tests.
- Because DSPRE only partly supports hg-engine ROMs, an agent pipeline should edit unpacked NARC sources in the build tree, or a JSON source-of-truth, rather than round-trip through DSPRE on `test.nds`.

### Gaps
- The search for "hg-engine new maps hack" returned nothing relevant. I found no named hg-engine-based hack with many new maps and no documented workflow. The hg-engine Discord, which I could not access, is the likely source.
- I could not see what `.github/workflows` in upstream hg-engine runs.

## Notable HGSS/Platinum hacks with many new maps, and their toolchains

### Takeaway
I found little dated, primary documentation on how major Gen 4 hacks built new maps. The documented community workflow is still **Pokémon DS Map Studio (PDSMS) for creating maps → DSPRE (formerly SDSME) for importing them and editing headers, matrices, and events**. All of it is GUI-only and Windows-centric.

### Cited Findings
- PDSMS is "a tool for creating gen 4 and gen 5 Pokémon games' maps." It cannot import or modify the original games' maps, and it was designed for use alongside SDSME. — [Trifindo/Pokemon-DS-Map-Studio](https://github.com/Trifindo/Pokemon-DS-Map-Studio)
- PDSMS needs G3DCVTR for model conversion, ships predesigned tilesets, and supports custom tiles. — [Project Pokémon PDSMS file page](https://projectpokemon.org/home/files/file/4237-pokemon-ds-map-studio/)
- SDSME is no longer in development, and users are told to use DSPRE. — [SDSME source mirror](https://github-redirect.dependabot.com/BuffelSaft/SDSME)
- A community tip for recreating HGSS routes: make a new map at width 120 and height 61, and check alignment against cartridge play with a walk-through-walls cheat. — PokéCommunity thread summarized in search results ([pokecommunity showthread](https://www.pokecommunity.com/showthread.php?p=9989991))
- A 2025 PokéCommunity thread reverse-engineered Platinum's town-map block layout (data starts at offset 04 in `tmap_block`). — [Editing the town map in Platinum](https://www.pokecommunity.com/threads/editing-the-town-map-in-platinum.415931)

### Inferences
- Renegade Platinum, Sacred Gold/Storm Silver, and similar hacks are known mainly for data rebalancing rather than many new maps. I found no web source documenting their map toolchains, so I have not made specific claims about them.

### Gaps
- No primary source was found for map workflows of Renegade Platinum, Sacred Gold, Storm Silver, Platinum Redux, Following Platinum, or fan-region Gen 4 hacks. These are probably in Discord or YouTube devlogs that I could not reach.

## Decomp-based map editing and a "porymap for Gen 4"

### Takeaway
No porymap-equivalent for Gen 4 decomps was found. Porymap remains Gen 3-only. pokeplatinum has the most mature text-to-binary data pipeline, and uxie already reads decomp sources. For HGSS, DSPRE (Windows, .NET 4.8, GUI) remains the de facto map, event, and matrix editor, and it has no documented CLI or automation API.

### Cited Findings
- Porymap is a map editor for the Gen 3 decomps (pokeruby, pokeemerald, pokefirered). It reads and writes decomp files, not ROMs. — [porymap mirror](https://code.heni.lol/decomp/porymap), [Flathub porymap](https://flathub.org/de/apps/io.github.huderlem.porymap)
- DSPRE ("Reloaded") has moved to the central repo DS-Pokemon-Rom-Editor/DSPRE. v1.14.0 was the final release from the Mixone-FinallyHere/AdAstra-LD repos and added an auto-updater, externalized editors, and in-game trade and overworld editors. A 1.12.3 beta (May 2024) added overlay and level-script editors. — [DSPRE GitHub](https://github.com/DS-Pokemon-Rom-Editor/DSPRE), [PokéCommunity DSPRE v1.14.0](https://www.pokecommunity.com/threads/dspre-v1-14-0.538822/), [r/PokemonROMhacks DSPRE 1.12.3 beta, May 2024](https://lr.sudovanilla.org/r/PokemonROMhacks/comments/1cquose/dspre_reloaded_1123_beta)
- DSPRE requires Windows 7+ and .NET Framework 4.8 (WinForms). Its map editor provides OpenGL 3D, building placement, collision/permission and BGS editing, BDHCAM, NSBMD import/export, DAE/GLB export, and 512px screenshots. Its event editor places NPCs, warps, triggers, and spawnables with warp navigation. Its matrix editor handles layout, connections, and resizing. The README describes no CLI or automation API, though scripts can be edited externally in VS Code. It has 82 stars and 19 forks. — [DSPRE GitHub](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)
- DSPRE's README defers to the DS Pokémon Hacking Wiki for documentation and to PDSMS for creating maps from scratch. — [DSPRE GitHub](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)
- pokeplatinum's documented map subsystems and dataproc JSON pipeline come from an indexer summary. — [Algolia summary](https://docsearch.algolia.com/mcp/docs/repo/pret/pokeplatinum)

### Inferences
- DSPRE's C# source is still the best reference implementation for HGSS event, header, matrix, and BDHC serialization. Porting its codecs into a small CLI would be the shortest path to headless writes. It is Windows/.NET Framework, so it will not run natively on macOS headless; Mono or Wine is unverified.
- The local `.codex-reference/pokeheartgold` checkout can serve as the structural authority for event and header structs when writing such a codec.

### Gaps
- No search found "porymap-ds," a web DSPRE, or Godot/Unity Gen 4 editors. If they exist, they are not indexed.
- I could not confirm the pokeheartgold decomp's current map-data format (JSON vs binary) or whether it has map tooling.
- The DSPRE license text was not shown on the fetched page.

## Emulator automation (melonDS, DeSmuME, BizHawk) for in-game map tests

### Takeaway
Standalone melonDS (1.0 in July 2024, 1.1 in November 2025, based on the release page's ordering) has a **GDB stub** and in-process multi-instance support, but **no merged Lua scripting** and no official headless mode. A melonDS Lua PR was dropped over macOS CI problems. BizHawk's melonDS core has Lua with memory domains (including TCM). DeSmuME has mature Lua and a CLI, but development is slow. No existing Gen 4 "map test" harness was found publicly.

### Cited Findings
- melonDS releases: 1.1 (18 Nov), 1.0 (08 Jul), 1.0 RC (21 Nov), 0.9.5 (03 Nov). 1.0 fixed the GDB stub not activating until reset, and 1.1 fixed vCont packet handling. 1.0 RC refactored the core to support multiple instances in one process. 0.9.5 improved command-line parameter handling. The release notes do not mention Lua or headless mode. — [melonDS releases](https://github.com/melonDS-emu/melonDS/releases)
- A melonDS Lua scripting PR was "nearly finished" but dropped because of macOS CI problems. A developer suggested reviving it and splitting the core from the Qt frontend to allow headless automated tests. This was in a BlocksDS issue about automated testing. — [codeberg blocksds/sdk #142](https://codeberg.org/blocksds/sdk/issues/142)
- BizHawk added an NDS (melonDS) core around 2.7, and later added TCM memory areas for melonDS (#3420). — [TASVideos BizHawk release history](https://tasvideos.org/Bizhawk/PreviousReleaseHistory), [TASVideos forum](https://tasvideos.org/Forum/Posts/510064)
- A "Universal DS Lua Script" repo manages NDS Lua scripts for both DeSmuME and BizHawk's melonDS core, and auto-detects the ROM. — [GitHub topic: desmume](https://github.com/topics/desmume)
- DeSmuME supports Lua and TAS tools. Its last numbered release was 0.9.13 (May 2022), with nightly builds since. — [tech-insider melonDS overview](https://tech-insider.org/melonds-emulateur-nintendo-ds-installer-configurer-2026/) (secondary source)
- Archipelago ships a generic BizHawk Lua connector (socket bridge), a reusable pattern for external control of BizHawk. — [Archipelago connector_bizhawk_generic.lua](https://git.hollymcfarland.com/monorail/Archipelago/src/commit/1312884fa2deb33546a500fe743e371492b67806/data/lua/connector_bizhawk_generic.lua)
- melonDS DS is a libretro core port of melonDS, which makes RetroArch-style frontends possible. — [JesseTG/melonds-ds](https://github.com/JesseTG/melonds-ds), [libretro docs](https://docs.libretro.com/library/melonds/)

### Inferences
- For a macOS headless agent pipeline, the options are: (a) the melonDS 1.x GDB stub driven from `arm-none-eabi-gdb` or a Python RSP client, for memory reads and breakpoints at warp or map-load functions; (b) a custom melonDS core harness that links the multi-instance core without Qt; or (c) BizHawk (.NET/Mono; BizHawk on macOS is not officially supported). Option (b) matches this repo's existing melonDS-only rule.
- A map test harness could assert, through memory reads, the current map ID, player X/Z, and the event-load result after scripted inputs, much like this repo's "memory-backed proof" approach.

### Gaps
- I could not confirm whether melonDS has merged Lua since the BlocksDS discussion, or the exact year of the 1.1 release (the page omits years). Context suggests 1.0 was July 2024 and 1.1 was November 2025.
- No public Gen 4 warp-walk or map-test harness was found.

## MCP servers and AI tooling for ROM hacking or NDS

### Takeaway
Emulator MCP servers exist for mGBA (GB/GBA) and BizHawk, but none were found with documented Nintendo DS support. No Pokémon Gen 4 ROM-hacking MCP server was found. The closest AI-adjacent asset is uxie's `--json` CLI, which could be wrapped as an MCP tool.

### Cited Findings
- **mcp-bizhawk** (dmang-dev): MIT-licensed, npm `mcp-bizhawk`. It offers 20 tools: memory read/write (8/16/32-bit and ranges), pause, frame advance, reset, joypad input, screenshots, save/load state, and batched input sequences. It requires BizHawk 2.6.2+ and Node 22+, and was tested on BizHawk 2.11.1 with SNES. Its system list does not mention the Nintendo DS. One tool description says it was verified in May 2026. — [glama: mcp-bizhawk](https://glama.ai/mcp/servers/igddve8klv)
- **mGBA MCP Server**: MIT-licensed. It supports memory reads, screenshots at any frame, and OAM dumps for GB/GBC/GBA, and includes a Claude Code config example. — [glama: mGBA MCP](https://glama.ai/mcp/servers/pd4ytd6jgs)
- A Gearboy (Game Boy) emulator with an embedded MCP server is listed, but I did not verify it independently. — [The Daily Workflow list of gaming MCP servers 2026](https://thedailyworkflow.com/mcp/tutorial/best-gaming-mcp-servers-2026) (aggregator)
- Algolia DocSearch exposes an MCP endpoint over pret/pokeplatinum docs. — [docsearch.algolia.com/mcp/docs/repo/pret/pokeplatinum](https://docsearch.algolia.com/mcp/docs/repo/pret/pokeplatinum)

### Inferences
- mcp-bizhawk might work with BizHawk's melonDS core, since it uses generic memory domains, but that is untested. A purpose-built MCP over the melonDS GDB stub or a headless melonDS core, plus a uxie- or DSPRE-codec-based "map data" MCP, would be new work.

### Gaps
- No NDS-specific or Pokémon-Gen-4-specific MCP server was found.
- I did not check whether mcp-bizhawk's memory-domain tools work with melonDS core domain names (Main RAM, ARM9 TCM, and others).
