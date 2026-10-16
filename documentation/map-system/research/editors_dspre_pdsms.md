# Gen 4 map editors for HeartGold/SoulSilver: DSPRE and PDSMS (state as of 2026-10-15)

Method note: Repository facts below (licenses, releases, branches, file lists, code excerpts) came from the GitHub API through `gh` on 2026-10-15. The "Source" links point at the matching GitHub pages. Code-level claims cite the file path in the linked repository.

## DSPRE: data coverage, HGSS header extension, runtime, macOS viability, license, activity and reusable parsers

### Takeaway
DSPRE (now the "DSPRE Reloaded" lineage, centralized at `DS-Pokemon-Rom-Editor/DSPRE`) is very active, with v2.3.4 released on 2026-10-13. It is AGPL-3.0 C#. The stable app is a Windows-only .NET Framework 4.8 WinForms program. An in-progress Avalonia port splits out a `net8.0` class library (`DSPRE.Core`) and ships Windows and Linux canary builds, but no macOS build. It also has an hg-engine integration layer. It edits nearly all HGSS map-related data. Adding headers requires its "Dynamic Header Allocation" patch. There is no CLI. Headless use would mean calling `DSPRE.Core` from your own .NET 8 program, or porting its parsers.

### Cited Findings
**Lineage and activity**
- The original DSPRE was by Nomura. "DSPRE Reloaded" was continued by AdAstra-LD and Mixone-FinallyHere. v1.14.0 (2025-11-04) was announced as the FINAL release from the Mixone-FinallyHere and AdAstra-LD repos, and development moved to the centralized `DS-Pokemon-Rom-Editor/DSPRE` repo. — [PokeCommunity DSPRE v1.14.0 thread](https://www.pokecommunity.com/threads/dspre-v1-14-0.538822/); [Mixone fork releases (archived)](https://github.com/Mixone-FinallyHere/DS-Pokemon-Rom-Editor/releases)
- `DS-Pokemon-Rom-Editor/DSPRE` metadata: license AGPL-3.0, language C#, last push 2026-10-14, 82 stars. Recent releases: v2.3.3.0 (2026-10-04), v2.3.4.0 (2026-10-13), a rolling `canary` tag, and a `canary-avalonia` tag (2026-10-14). — [DSPRE releases](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/releases)
- The v2.3.4 notes say it fixed an Event Editor crash on Spanish SoulSilver caused by looking up the overworld sprite table at the wrong place. This shows HGSS localization-specific offsets are still being fixed. — [DSPRE v2.3.4 release](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/releases/tag/v2.3.4.0)
- The AdAstra-LD fork (`AdAstra-LD/DS-Pokemon-Rom-Editor`, 239 stars) has older "DSPRE Reloaded" releases up to v1.11.1 (2023-12-13) and a canary from 2025-11-26. It is no longer the main line. — [AdAstra-LD/DS-Pokemon-Rom-Editor](https://github.com/AdAstra-LD/DS-Pokemon-Rom-Editor)
- Branches in the main repo include `feature/avalonia`, `dotnet-8`, `dsrom-CI`, `dsrom-ffi`, `feature/DecompPartialSupport`, `feature/offsetDB` and `uxie`. — [DSPRE branches](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/branches)

**Editable data, per the README**
- Supported games: Diamond, Pearl, Platinum, HeartGold, SoulSilver, and hg-engine ROMs (partial).
- Editors listed:
  - Header Editor: properties, weather, music, camera. Also copy/paste, import/export, add/remove headers "if relevant patch applied", and WorldMap Coordinates (HGSS).
  - Matrix Editor.
  - Map Editor: collision/permissions, buildings, NSBMD and BIN import/export, texture preview.
  - Event Editor: NPCs/overworlds, warps, triggers, spawnables.
  - Script Editor: binary and plaintext formats.
  - Text Editor.
  - Wild Encounters Editor, plus HGSS Safari Zone and Headbutt editors.
  - NSBTX Editor: texture packs and AreaData.
  - Patch Toolbox.
  - The README says to use PDSMS to create new maps from scratch.
  — [DSPRE README](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)
- Adding new headers requires the **Dynamic Header Allocation** patch in DSPRE's Patch Toolbox. — [DS Pokémon Hacking wiki, Mapping FAQs](https://github.com/ds-pokemon-hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/mapping/mapping_faqs.mdx)
- The `MapHeader.cs` comments document both the DPPt and HGSS header layouts. The HGSS layout is:

  | Offset | Field |
  | --- | --- |
  | 0x0 | Wild Pokémon file (byte) |
  | 0x1 | Area data (byte) |
  | 0x4 | Matrix (ushort) |
  | 0x6 | Script file |
  | 0x8 | Level script file |
  | 0xA | Text archive |
  | 0xC / 0xE | Day / night music |
  | 0x10 | Event file |
  | 0x12 | Map name index |

  — [DSPRE DS_Map/ROMFiles/MapHeader.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/ROMFiles/MapHeader.cs)

**Runtime and platform**
- The stable app targets .NET Framework 4.8 with `OutputType WinExe`. It depends on System.Windows.Forms, WPF/WindowsFormsIntegration, HelixToolkit, OpenTK, Tao.OpenGl, Tao.Platform.Windows and ScintillaNET. — [DSPRE DS_Map/DSPRE.csproj](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/DSPRE.csproj)
- The README lists the requirements as Windows 7 or later and .NET Framework 4.8, with no macOS or Linux support. — [DSPRE README](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)
- It bundles Windows executables in `DS_Map/Tools/`: `ndstool.exe`, `blz.exe`, `apicula.exe`, `chatot.exe` and `dsrom.exe`. — [DSPRE repo tree](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/tree/main/DS_Map/Tools)
- The `canary-avalonia` release describes a "pure Avalonia DSPRE shell (no WinForms)" from `feature/avalonia`, for "Windows and Linux, both self-contained", with "missing features, rough edges, and instability". Its assets are `DSPRE-Avalonia-linux-x64-canary.tar.gz` and `DSPRE-Avalonia-win-x64-canary.zip`. There is no macOS asset. — [DSPRE canary-avalonia release](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/releases/tag/canary-avalonia)
- PR #212 changed resources because "linux is case-sensitive". PR #280 added a building-replacement confirmation "when someone apply a PDSMS Map". — [DSPRE PR #212](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/pull/212); [DSPRE PR #280](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/pull/280)
- On `feature/avalonia`, the solution has `DSPRE.Core` (a `net8.0` Library), `DSPRE.Avalonia` (`net8.0`, RuntimeIdentifier `linux-x64`), `DSPRE.Tests`, and the legacy `DS_Map`. `DSPRE.Core` references System.Drawing.Common 8.0, Newtonsoft.Json, YamlDotNet and LibGit2Sharp. — [DSPRE feature/avalonia DSPRE.Core.csproj](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/feature/avalonia/DSPRE.Core/DSPRE.Core.csproj)
- `DSPRE.Core` contains about 166 files under `ROMFiles/` and 87 under `HgEngine/`. The `HgEngine/` files include `HgEngineHeaderEditor.cs`, `HgEngineOverworlds.cs`, `HgEngineSyntheticOverlay.cs`, `HgEngineHeadbutt.cs`, `HgEngineProject.cs`, `HgEngineBuild.cs`, `HgEngineWriteGuard.cs` and `HgEngineBattleTests.cs`. — [DSPRE feature/avalonia tree](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/tree/feature/avalonia/DSPRE.Core)
- No CLI, batch or headless mode appears in the README. In the trees, the only entry points are GUI `Program.cs` files (`DS_Map/Program.cs`, `DSPRE.Avalonia/Program.cs`). — [DSPRE README](https://github.com/DS-Pokemon-Rom-Editor/DSPRE); [repo tree](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)

**Reusable parsers and writers in the source**
- `DS_Map/ROMFiles/` includes:
  - Map data: `MapFile.cs`, `MapHeader.cs`, `GameMatrix.cs`, `EventFile.cs`, `AreaData.cs`.
  - Scripts and text: `ScriptFile.cs`, `LevelScriptFile.cs`, `TextArchive.cs`.
  - Encounters: `EncounterFile.cs`, `HeadbuttEncounterFile.cs`, `SafariZoneEncounterFile.cs`, `BugContestEncounterFile.cs`.
  - Others: trainer, personal and move data.
  — [DSPRE ROMFiles](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/tree/main/DS_Map/ROMFiles)
- `DS_Map/LibNDSFormats/` contains:
  - NSBMD, NSBTX, NSBCA, NSBTA and NSBTP loaders.
  - An NSBMD OpenGL renderer.
  - An OBJ writer (`Export3DTools/OBJWriter.cs`).
  — [DSPRE LibNDSFormats](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/tree/main/DS_Map/LibNDSFormats)
- `MapFile.cs` documents the land_data container as a 16-byte header with lengths for permissions (always 2048), buildings, NSBMD and BDHC sections. Buildings are 48-byte records: model ID, fixed-point x/y/z, rotations, and width/height/length.
  - It exposes `BuildingsToByteArray` and `CollisionsToByteArray`, plus import/export filters for `.per`, `.bld`, `.bdhc`, `.bdhcam` and `.bgs`.
  - It stores BDHC as raw bytes (`public byte[] bdhc`). It does not generate or edit BDHC structurally.
  - Its constructors use Windows-style path joining (`unpackedDir + "\\" + ...`).
  — [DSPRE MapFile.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/ROMFiles/MapFile.cs)

**Related library**
- `uxie` (KalaayPT; MIT, with a bundled LGPL-3.0-or-later `nitroarc` submodule) is a Rust library and CLI for Gen 4 data. Version 0.9.5 is dated 2026-10-04.
  - It reads ROM data from DSPRE projects and decompilation sources.
  - CLI commands include `header`, `map`, `event`, `encounter`, `symbols` and `personal`.
  - Platinum is the primary target. HGSS support is described as "partial in some workflows". Matrices, land data and BDHC are not mentioned.
  - A `uxie` branch exists in the DSPRE repo.
  — [docs.rs uxie](https://docs.rs/crate/uxie/latest); [KalaayPT/uxie](https://github.com/KalaayPT/uxie)

### Inferences
- Running the stable DSPRE on macOS would require Wine or a Windows VM, because it uses WinForms, WPF and Windows-only Tao.Platform. Avalonia canaries exist only for Linux and Windows. A macOS build may be feasible later, since Avalonia and net8 are cross-platform, but none is published.
- The most practical scripted route on macOS is likely a small .NET 8 console program that references `DSPRE.Core` from `feature/avalonia`, or reimplementing the documented layouts (header, matrix, land_data container, 48-byte building records, permissions) in Python. Caveats for the `DSPRE.Core` route:
  - It is AGPL-3.0, which matters if the result is redistributed or linked.
  - System.Drawing.Common is Windows-only at runtime from .NET 7 onward, so image paths may fail on macOS.
  - `DSPRE.Core` may still depend on global ROM-state singletons (`RomInfo.gameDirs`) and on the bundled Windows `ndstool.exe`/`dsrom.exe`. I did not verify this.
- Because DSPRE has an `HgEngine` layer, a project built on hg-engine can expect DSPRE to read and write hg-engine sources/overrides directly (header editor, overworlds, synthetic overlay). Its writes could therefore touch this repository's files, not just a ROM.

### Gaps
- I did not confirm whether `DSPRE.Core` builds or runs on macOS, or whether it can be driven without GUI initialization.
- I did not inspect what the Dynamic Header Allocation patch changes for HGSS, such as the ARM9 or overlay relocation of the header table.
- I did not verify whether DSPRE's NSBMD import requires external tools. `apicula.exe` is bundled, most likely for NSBMD→DAE export (inference).
- No `LICENSE` file content was read for the AdAstra-LD fork. The API returned no SPDX ID for it.

## PDSMS: map construction, NSBMD/BDHC/permission generation, Java portability, CLI, file format, license and HGSS caveats

### Takeaway
PDSMS builds a map from a tile grid of user-supplied `.obj`/`.mtl` tiles, using 8 layers (9 in the AdAstra fork) and per-cell heights. It generates IMD, OBJ, NSBTX, BDHC/BDHCAM, collisions, backsound and buildings, and packs an HGSS map `.bin`. NSBMD output requires Nintendo's proprietary `g3dcvtr.exe` (IMD→NSBMD), which cannot be redistributed. On non-Windows systems PDSMS runs it through `wine`. It is a Java Swing GUI. The only command-line feature is opening a file passed as an argument. The upstream repository has no license, so all rights are reserved by default. The upstream was last updated in 2021 (v2.2). The active continuation is the AdAstra-LD fork (v2.4, 2026-09-24), whose `.pdsmap` files do not work in vanilla PDSMS.

### Cited Findings
**Upstream status and fork**
- Upstream `Trifindo/Pokemon-DS-Map-Studio` is Java, with 272 stars and no license file (the API license field is null). Its last release is "Release 2.2" (2021-06-23), and its last code commits are from June–July 2021. — [Trifindo/Pokemon-DS-Map-Studio](https://github.com/Trifindo/Pokemon-DS-Map-Studio); [releases](https://github.com/Trifindo/Pokemon-DS-Map-Studio/releases)
- Supported games are DP, Pt, HGSS, BW and B2W2. The README says the tool is "designed to be used alongside SDSME" and "DOES NOT allow modification of maps from official games". It is "tested under Windows, macOS and Linux", requires Java 8 for upstream, and runs with `java -jar PokemonDSMapStudio.jar`. Exporting `.nsbmd` needs `g3dcvtr.exe` and a xerces-c DLL in the `converter` folder. — [PDSMS README](https://github.com/Trifindo/Pokemon-DS-Map-Studio)
- The AdAstra-LD fork, described as "Fork of Trifindo's PDSMS 2.1 with a bunch of new features":
  - Releases: v2.2 (2023-11-27), v2.2.1 (2024-03-26), v2.2.2 (2026-05-15) and v2.4 (2026-09-24). v2.4 merges Trinsic64's fork.
  - Maps resaved with it are "incompatible with vanilla PDSMS" because of an extra 3D layer and Export Group metadata (`exportgroup`/`egcenter` keywords). Tile folders are stored in a `.meta` sidecar.
  - It adds selection, copy/paste and fill tools, per-tile collision defaults with "Auto Coll.", "Split PDSMAP by Area", and area export dialogs. July 2026 commits include "Overhaul move permission labels for all supported games … HGSS".
  - Its Windows release bundles a Java runtime. The portable release requires Java 11 or newer.
  - It "cannot redistribute `g3dcvtr.exe`", so users must supply a "legally obtained" copy.
  — [AdAstra-LD/Pokemon-DS-Map-Studio](https://github.com/AdAstra-LD/Pokemon-DS-Map-Studio); [v2.4 release](https://github.com/AdAstra-LD/Pokemon-DS-Map-Studio/releases/tag/v2.4)

**NSBMD pipeline**
- `MainFrame.java` builds the command for `converter/g3dcvtr.exe` with the arguments `<imd> -eboth|-emdl -o <file>`. On Windows it runs the program directly. On other systems it prefixes the command with `wine`, with the comment "wine call works only with relative path". It runs the converter through `ProcessBuilder`. — [PDSMS src/main/java/editor/MainFrame.java](https://github.com/Trifindo/Pokemon-DS-Map-Studio/blob/master/src/main/java/editor/MainFrame.java)
- PDSMS writes the intermediate `.imd` itself. The `formats/imd/` package contains `ImdModel` and the triangle and stripe calculators. NSBTX is written natively (`nsbtx2/NsbtxWriter.java`). OBJ export uses `obj/ObjWriter.java`, and DAE is read with `dae/DaeReader.java`. — [PDSMS formats source](https://github.com/Trifindo/Pokemon-DS-Map-Studio/tree/master/src/main/java/formats)
- Flow described by the wiki: PDSMS exports maps as `.obj`, which are converted to `.nsbmd` through an intermediate `.imd`. Alternatively, it exports all map files (permissions, terrain, background sounds) packaged as a `.bin`. — [DS Pokémon Hacking wiki, Models](https://github.com/ds-pokemon-hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/mapping/models.md)
- I found no open-source IMD→NSBMD replacement for g3dcvtr. apicula (0BSD) converts NSBMD to COLLADA/glTF, the opposite direction. — [scurest/apicula](https://github.com/scurest/apicula)

**BDHC, permissions and the HGSS map bin**
- Game-specific writers exist:
  - Terrain: `formats/bdhc/BdhcWriterHGSS.java` and `BdhcLoaderHGSS.java`, with plates, slopes and stripes.
  - Camera terrain: `formats/bdhcam/BdhcamWriter.java`.
  - Collisions: `formats/collisions/Collisions.java` (and BW 3D collisions).
  - Background sound: `formats/backsound/Backsound.java`.
  - Buildings: `editor/buildingeditor2/BuildHandlerHGSS.java` and `AreaDataHGSS.java`.
  - Map bin: `formats/mapbin/MapBinHGSS.java`.
  — [PDSMS formats source](https://github.com/Trifindo/Pokemon-DS-Map-Studio/tree/master/src/main/java/formats)
- `MapBinHGSS` reads `<map>.bgs`, `.per`, `.bld`, `.nsbmd` and `.bdhc` from a folder.
  - It strips textures from the NSBMD (`NsbmdUtils.nsbmdTexToNsbmdOnly`).
  - It substitutes `.bdhcam` for `.bdhc` when the BDHCAM file contains data.
  - It writes a 16-byte header with the lengths of the per, bld, nsbmd and bdhc sections.
  - This is the same container DSPRE's `MapFile.cs` reads, which is why a PDSMS `.bin` can be imported into DSPRE.
  — [MapBinHGSS.java](https://github.com/Trifindo/Pokemon-DS-Map-Studio/blob/master/src/main/java/formats/mapbin/MapBinHGSS.java); [DSPRE MapFile.cs](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/blob/main/DS_Map/ROMFiles/MapFile.cs)

**Project file format**
- `.pdsmap` is a line-based plain-text format written with `PrintWriter`:
  - A game-index tag and value.
  - A tileset tag followed by a `.pdsts` filename.
  - For each map: a map tag, `x y` coordinates, an area index, tile-grid and height-grid blocks, then a map-end tag.
  - Tilesets use the `.pdsts` extension and are handled by `tileset/TilesetIO.java`.
  — [MapMatrix.java](https://github.com/Trifindo/Pokemon-DS-Map-Studio/blob/master/src/main/java/editor/mapmatrix/MapMatrix.java)

**Command-line use**
- `main(String[] args)` only opens a `.pdsmap` or `.pdsts` passed as `args[0]`. There are no batch or export flags. — [MainFrame.java](https://github.com/Trifindo/Pokemon-DS-Map-Studio/blob/master/src/main/java/editor/MainFrame.java)

**Map conventions**
- Each map is a 32×32 grid, with 512 m per side in game units. PDSMS uses a 0.0625 scale.
- Tiles are `.obj` + `.mtl` files. Each must have no unused material slots and at most one material per image texture.
- There are 8 layers (9 in the AdAstra fork) with per-cell, per-layer heights. A Z-offset tile property exists only in the AdAstra fork.
- Some vanilla maps are hard to recreate faithfully with tiles.
- Suggested limits: under ~1,000 polygons per map, and no more than 2,000 polygons in total for maps, buildings and sprites.
- `.bgs` (background sound) is an HGSS-only map attribute. In HGSS, collision `0x80` blocks movement, and type `0x02` marks tall grass.
— [DS Pokémon Hacking wiki, Mapping overview](https://github.com/ds-pokemon-hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/mapping/mapping.md)

### Inferences
- PDSMS can be scripted headlessly on macOS in two ways, both requiring development work:
  - Java code that calls its classes (`MapMatrix` load, `ImdModel` export, `BdhcWriterHGSS`, `MapBinHGSS.toByteArray`). Many paths are tied to Swing handlers and dialogs.
  - Generating `.pdsmap`/`.pdsts` text and driving the export code.
- The NSBMD step has no clean open-source route. It needs `g3dcvtr.exe` under Wine on macOS, which is proprietary and must come from the user. Alternatives are an existing NSBMD reused as-is, or a custom NSBMD writer.
- No license on the upstream repository means reusing its code in this project is legally unclear. The AdAstra fork also shows no SPDX license.

### Gaps
- I did not verify whether g3dcvtr runs reliably under current macOS Wine builds (CrossOver or Wine on Apple Silicon).
- I did not confirm whether PDSMS's BDHC generation from tile heights is automatic or needs manual plate editing. Code exists for both the editor dialog and the writer.
- I did not read the exact `.pdsts` tileset format.

## Combined PDSMS + DSPRE workflow for new HGSS maps, and its pain points

### Takeaway
The community-standard workflow is to build the map in PDSMS, export the IMD and convert it to NSBMD with g3dcvtr, then export the HGSS map `.bin`. In DSPRE, you apply the Dynamic Header Allocation patch if adding a header, import the `.bin` into a land_data slot, then set the matrix, header, area data, events and scripts. Pain points:
- proprietary g3dcvtr
- tileset and version incompatibility between PDSMS forks
- texture and polygon budgets
- HGSS header association quirks
- Windows-centric tooling

### Cited Findings
- The DSPRE README says the Map Editor imports and exports NSBMD and BIN, and that new maps should come from PDSMS. — [DSPRE README](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)
- The wiki FAQ says to import custom maps by following the written tutorial (Models page, import/export section) and a video tutorial. Adding headers needs the Dynamic Header Allocation patch. Tilesets made with the AdAstra fork fail silently in base PDSMS. — [Mapping FAQs](https://github.com/ds-pokemon-hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/mapping/mapping_faqs.mdx)
- Data hierarchy, per the wiki:
  - Header
    - Area Data: map NSBTX, building NSBTX, global NSBTA (HGSS-only)
    - Matrix
    - Map NSBMD
      - BDHC
      - PER
      - BGS (HGSS-only)
      - BLD
  - Ripping vanilla maps uses DSPRE to export DAE, then Blender to OBJ with a 0.0625 scale and swapped Y/Z axes, then PDSMS.
  - Recommended Blender versions are 2.78–2.83 and 4.2.
  - Other tools named: the NNS Blender plugin for NSBCA, apicula, NitroPaint, and Tinke.
  — [Mapping overview](https://github.com/ds-pokemon-hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/mapping/mapping.md)
- Tutorials: Trifindo's PDSMS video series, JaySan's beginner PDSMS series, and SauceyaTTa's HGSS mapping introduction. Support is mainly the Kingdom of DS ROM Hacking Discord (#g4-mapping-support, #tile-sharing). — [Mapping overview](https://github.com/ds-pokemon-hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/mapping/mapping.md)
- An older developer comment (DSPRE/Spiky thread) says GameFreak probably changed header association in HGSS, and that it works fine in DPPt. It may be outdated. — [PokeCommunity Spiky's DS Map Editor thread](https://www.pokecommunity.com/threads/spikys-ds-map-editor-now-open-source.288625/post-7432157)
- A Project Pokémon research thread documents the HGSS map file as a section header followed by permissions, 3D objects (buildings), NSBMD and BDHC. It was surfaced by search, and I did not read it in full. — [Project Pokémon search result, profile content](https://projectpokemon.org/home/profile/127833-ravends/content/)
- DSPRE PR #280 adds a building-replacement confirmation when applying a PDSMS map. This suggests importing a PDSMS `.bin` replaces the buildings already on that map. — [DSPRE PR #280](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/pull/280)

### Inferences
- An agent could do most of the DSPRE side headlessly by writing the documented binary layouts itself (matrix, header table, land_data container, events) inside the hg-engine build. This bypasses both GUIs. The hard part remains producing a new NSBMD and a matching BDHC.

### Gaps
- No step-by-step written HGSS-only "new map" tutorial was fully read. The wiki Models import/export section and the videos were not transcribed.

## Other HGSS map-capable editors

### Takeaway
SDSME (Spiky's DS Map Editor) is the older predecessor, and its source is mirrored. CDSRE was a GPL-3.0 "spiritual successor" that has been dormant since 2024. PokEditor and Pokémon Sinjoh Editor are GPL-3.0 data editors, not map-geometry editors. Tinke and NitroPaint are generic NDS file and graphics tools. apicula converts NSBMD to DAE/glTF. None of these replaces PDSMS for map geometry or DSPRE for headers and events.

### Cited Findings
- `Skareeg/SDSME`: "Source code from Spiky's DS Map Editor", 45 stars, updated 2026-06-24, no license listed. — [Skareeg/SDSME](https://github.com/Skareeg/SDSME)
- `team-cosmic/cdsre`: "Cosmic DS ROM Editor, the spiritual successor to SDSME", GPL-3.0, last updated 2024-09-11. — [team-cosmic/cdsre](https://github.com/team-cosmic/cdsre)
- `turtleisaac/PokEditor` (GPL-3.0, updated 2026-09-17) is a "Multifunctional in-depth editor for Pokémon Gen 4 game data". There are also PokEditor-v2 and PokEditor-Core (v3 backend). — [turtleisaac/PokEditor](https://github.com/turtleisaac/PokEditor)
- `GreyLily3/Pokemon_Sinjoh_Editor` (GPL-3.0, updated 2026-09-13) edits stats and other data for the Gen 4 games, including HGSS. — [Pokemon_Sinjoh_Editor](https://github.com/GreyLily3/Pokemon_Sinjoh_Editor)
- `pleonex/tinke` (GPL-3.0, updated 2026-10-12) is a viewer and editor for NDS game files. — [pleonex/tinke](https://github.com/pleonex/tinke)
- NitroPaint (Garhoogin) is listed for textures. apicula (0BSD) converts Nitro models to COLLADA/glTF, but its converter does not handle pattern and material animations. — [Mapping overview](https://github.com/ds-pokemon-hacking/ds-pokemon-hacking.github.io/blob/main/docs/generation-iv/guides/mapping/mapping.md); [apicula](https://github.com/scurest/apicula)

### Inferences
- For an agent on macOS, the only realistic map-geometry pipeline is still PDSMS logic plus g3dcvtr under Wine, unless a custom NSBMD writer is built. For header, matrix, event and land_data plumbing, DSPRE's documented layouts or `DSPRE.Core`/`uxie` code are the best references.

### Gaps
- I did not check the SDSME source for license or HGSS support details, or whether CDSRE handles maps.
- I did not check Pokémon Sinjoh Editor's or PokEditor's exact HGSS feature lists for any map data.
