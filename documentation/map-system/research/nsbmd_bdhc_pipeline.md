# Nintendo DS 3D model and terrain toolchain for HGSS maps (NSBMD / NSBTX / NSBTA / IMD / BDHC), headless macOS view (researched 2026-10-15)

Repo activity data below came from the GitHub API (`gh api repos/...`) on 2026-10-15. "pushed_at" is the last push to any branch.

| Repo | Last push | License (GitHub SPDX) | Language |
|---|---|---|---|
| scurest/apicula | 2025-01-21 | 0BSD | Rust |
| magcius/noclip.website | 2026-10-06 (src/nns_g3d last commit 2026-05-26) | NOASSERTION (custom) | TypeScript |
| Trifindo/Pokemon-DS-Map-Studio (original) | 2024-03-26 | none detected | Java |
| AdAstra-LD/Pokemon-DS-Map-Studio (active fork, v2.4 released 2026-09-24) | 2026-09-24 | none detected | Java |
| Trinsic64/Pokemon-DS-Map-Studio (fork merged into AdAstra v2.4) | 2026-10-10 | none detected | Java |
| DS-Pokemon-Rom-Editor/DSPRE (v2.3.4.0 released 2026-10-13) | 2026-10-14 | AGPL-3.0 | C# |
| jellees/nns-blender-plugin | 2026-09-19 | none detected | Python |
| Ermelber/nitro-g3d-tools | 2020-08-17 | none detected | C# |
| Garhoogin/NitroPaint (v2.10.1.0 released 2026-10-07) | 2026-10-07 | BSD-2-Clause | C |
| Garhoogin/ptexconv | 2026-09-11 | BSD-2-Clause | C |
| TheGameratorT/NitroModel_ConverterGUI | 2019-11-23 | none detected | C++ |

## Do open-source NSBMD writers or encoders exist?

### Takeaway
I found only one open-source program that writes NSBMD: Ermelber's **nitro-g3d-tools** `BinaryConverter`, a C#/.NET Framework 4.7 tool that converts IMD to NSBMD. Its last push was in 2020, it has no license file, and nobody appears to use it in the Pokémon toolchain. Everything else is either a reader (apicula, noclip, DSPRE's viewer), an IMD writer that still needs Nintendo's g3dcvtr (Pokemon DS Map Studio (PDSMS), the NNS Blender plugin), or closed-source Windows software (MKDS Course Modifier). The usual pipeline is: generate IMD, run g3dcvtr, get NSBMD/NSBTX.

### Cited Findings
- **apicula** reads NSBMD, NSBTX, NSBCA, NSBTP and NSBTA (the last marked experimental). It outputs COLLADA (.dae) or glTF (.glb) through `apicula convert -f=glb <files> -o <dir>`, and also has `extract` (scans a ROM or file for Nitro files), `view` and `info` commands. The README does not mention writing Nitro files. The license is 0BSD and it builds from source with Rust 1.34+. Only the prebuilt binary is Windows-only, so building with `cargo` on macOS is the expected route. Pattern and material animations work in the viewer but not in the converter. — [apicula README](https://github.com/scurest/apicula)
- apicula's "continuous" release asset is `apicula-latest-windows.zip`, published 2021-03-08. The last push to the repo was 2025-01-21. — GitHub API, [apicula releases](https://github.com/scurest/apicula/releases)
- **nitro-g3d-tools** (Ermelber) contains the folders BinaryConverter, BinaryTexConverter, IntermediateConverter, LibNitro.Intermediate and LibNitroG3DTools, and depends on AssimpNet 4.1.0. Its README says to build with Visual Studio and .NET Framework v4.7. — [nitro-g3d-tools](https://github.com/Ermelber/nitro-g3d-tools)
- `BinaryConverter/Program.cs` prints "Nitro G3D Binary Converter — A CLI tool capable of converting Nitro G3D Intermediates (IMD and such) into Binaries (NSBMD and such)". Usage is `binconv INPUT [OPTIONS]`, and `-t/--etex` writes the NSBTX separately. It calls `new NsbmdConverter(path).Write(outPath)`. — [BinaryConverter/Program.cs](https://github.com/Ermelber/nitro-g3d-tools/blob/master/BinaryConverter/Program.cs)
- **MKDS Course Modifier** is the tool forum users usually recommend for OBJ to NSBMD (File > New > NSBMD, pick the OBJ, save NSBMD + NSBTX). One user reported that an older build had no NSBMD option. I found no license or source for it. — [Project Pokemon thread "Obj to Nsbmd?"](https://projectpokemon.org/home/forums/topic/29590-obj-to-nsbmd-import-obj-to-sdsme/), [gbatemp "Help Converting .obj to .nsbmd"](https://gbatemp.net/threads/help-converting-obj-to-nsbmd.362093/), [NSMBHD NSBMD Creation Tutorial](https://nsmbhd.net/thread/431-tutorial-nsbmd-creation-tutorials-and-hacking/)
- The other official route is Maya 5–7 with the Nitro plugins: scale by 1/16 and export with the emdl option, which produces an NSBMD without textures. — [NSMBHD NSBMD Creation Tutorial](https://nsmbhd.net/thread/431-tutorial-nsbmd-creation-tutorials-and-hacking/)
- **NNS Blender plugin** (jellees; authors Ermelber and Jelle): "able to export intermediate model format (.imd)" as well as `.ica` (bone/joint animation) and `.ita` (texture animation). The repo also has export_ima.py and export_itp.py. It does not write NSBMD. Textures must be Nitro TGA, generated with Optpix or NitroPaint. All documented workflows go through the Blender GUI. — [nns-blender-plugin](https://github.com/jellees/nns-blender-plugin), [DSHack: NNS Blender Plugins](https://wiki.dshack.org/Wiki.jsp?page=NNS+Blender+Plugins)
- The DSHack MKDS custom-track tutorial says the NNS Blender Plugin works with Blender 2.8 through 4.0. It exports via File > Export > Nitro Intermediate, then converts the IMD with g3dcvtr's bundled `mdltex.bat`. It warns that "Compress nodes" set to Unite / Unite and combine polygon breaks animations. — [DSHack: Making a Custom Track](https://wiki.dshack.org/Wiki.jsp?page=Making+a+Custom+Track)
- **NitroModel_ConverterGUI** (TheGameratorT, C++, 2019) is a GUI wrapper around `ass2imd` and `imd2nsbmd`. It does not replace them. A sibling repo, NSBMD-NSBTX_Converter, ships the original g3dcvtr executable in its bin folder. — [NitroModel_ConverterGUI](https://github.com/TheGameratorT/NitroModel_ConverterGUI), [NSMBHD "NSBMD and NSBTX Converter"](https://nsmbhd.net/thread/4951-nsbmd-and-nsbtx-converter/)
- **NitroPaint** (BSD-2-Clause, C, Win32 GUI; v2.10.1.0 on 2026-10-07) lists "Texture Archive: NSBMD/NSBTX, BMD (SM64DS)" among its supported formats, so it can edit and convert textures inside NSBTX/NSBMD. Past release notes mention fixes for incorrect NSBTX output. — [NitroPaint README](https://github.com/Garhoogin/NitroPaint/blob/main/README.md), [NitroPaint releases](https://github.com/Garhoogin/NitroPaint/releases)
- **ptexconv** (Garhoogin, BSD-2-Clause, C) is "the command line version of the background and texture conversion functionality of NitroPaint". It supports all DS texture formats (palette4/16/256, a3i5, a5i3, tex4x4, direct) and outputs binary, C header, GRF, NNS TGA (`-onns`) or NCLR. The README does not mention NSBTX output. Main flags: `-gt` (texture), `-f` (format), `-cm` (palette color limit), `-o`, `-d` (dither). — [ptexconv](https://github.com/Garhoogin/ptexconv)
- `unnsbtx` (packaged in Ubuntu) lists and extracts NSBTX images to TGA (`unnsbtx l|e file.nsbtx`). It is read-only. — [Ubuntu manpage unnsbtx](https://manpages.ubuntu.com/manpages/focal/man1/unnsbtx.1.html)
- **DSPRE** can import and export map NSBMD and map BIN, export map models as DAE/GLB/NSBMD, import and export NSBTX and AreaData, and export 512 px map screenshots. Its README says that creating new maps from scratch needs PDSMS. — [DSPRE README](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)

### Inferences
- Because nitro-g3d-tools is C# with AssimpNet, it might build with modern .NET or Mono on macOS. That is untested, and AssimpNet needs a native libassimp for macOS. It is the only candidate I found for a fully open IMD→NSBMD step, but its fidelity to g3dcvtr is unproven, it has had no maintenance since 2020, and it has no license, so redistributing it is legally unclear.
- A from-scratch NSBMD writer for map chunks is feasible and probably the cleanest long-term headless option. Map models are static: one node, no skinning, a few materials. apicula's parser (0BSD Rust) and noclip's `NNS_G3D.ts` are detailed readable specs of the binary layout, and apicula can serve as a round-trip validator (write → `apicula info/convert` → compare). This is an inference; I found no existing project that has done it.
- For textures, ptexconv covers headless palette conversion on any OS. Something still has to pack the TEX0/NSBTX container, using g3dcvtr, nitro-g3d-tools `BinaryTexConverter`, or a custom writer.

### Gaps
- I could not confirm whether nitro-g3d-tools' NsbmdConverter supports all IMD features (multiple materials, texture SRT, vertex colors, polygon strips) or produces game-loadable files for HGSS. I found no test reports.
- I could not find authoritative source, license or current download for MKDS Course Modifier or Every File Explorer (Gericom). Whether either writes NSBMD headlessly is unknown, and both are presumed Windows/.NET GUI tools.
- I did not find "obj2nsbmd", "nsbmd-converter", "NitroBlender", "io_scene_nsbmd" or "blender-nds" projects that write NSBMD. Searches returned only the tools above, which suggests none are prominent, though they may exist in obscure repos.
- melonDS has no model-export tooling that I found.

## Nintendo g3dcvtr / NITRO-System IMD converter: availability, macOS use, legality

### Takeaway
g3dcvtr is a leaked or redistributed Nintendo NITRO-System SDK Windows command-line binary. It needs `xerces-c` DLLs and converts IMD (XML) to NSBMD/NSBTX. Hobbyists download it from Project Pokemon or similar sites. Tools such as PDSMS deliberately do not bundle it because they cannot redistribute it. It runs under Wine on Linux and, with a recent Wine (9.15 reported), on macOS. That makes a headless `wine g3dcvtr.exe in.imd -o out.nsbmd` step practical but legally grey.

### Cited Findings
- Project Pokemon hosts a "G3DCVTR" file listing that describes it as converting an imd file to an nsbmd file. It is a Windows executable with `--help` output. — [Project Pokemon: G3DCVTR](https://projectpokemon.org/home/files/file/3819-g3dcvtr/)
- PDSMS README (original): "If you wish to export .nsbmd files, g3dcvtr.exe and xerces-c_2_5_0.dll must be placed into the bin/converter folder." — [Trifindo PDSMS](https://github.com/Trifindo/Pokemon-DS-Map-Studio)
- The AdAstra-LD PDSMS fork README says to "place your legally obtained `g3dcvtr.exe` in the release's `converter` folder. The release creates this folder and includes the supporting DLL … but cannot redistribute `g3dcvtr.exe`." The repo ships `converter/xerces-c_2_8.dll` and a placeholder "Paste g3dcvtr in this folder.txt". Its `ConverterLocator.java` looks for the hard-coded name `g3dcvtr.exe` under `converter/`. — [AdAstra-LD PDSMS](https://github.com/AdAstra-LD/Pokemon-DS-Map-Studio), repository tree via GitHub API
- The newer PDSMS forks add one-click chains "OBJ -> IMD -> NSBMD -> NSBTX" for all maps or the active map. — [Trinsic64 PDSMS fork](https://github.com/Trinsic64/Pokemon-DS-Map-Studio), summarized in search results
- The DSHack guide for Linux uses Wine (5.0+ recommended): put IMD/ICA/ITA next to g3dcvtr and run through `wine cmd`. — [DSHack: How to use mkds tools on a linux distribution](https://wiki.dshack.org/Wiki.jsp?page=How+to+use+mkds+tools+on+a+linux+distribution)
- In a PDSMS forum thread, a user reports that NSBMD export works on Linux by calling g3dcvtr through Wine. The author said the integration "wasn't fully patched". — [PokéCommunity PDSMS thread p.2](https://pokecommunity.com/showthread.php?p=10130197)
- A macOS user running Wine Staging got a startup error launching G3DCVTR. The reported fix was upgrading to Wine 9.15. — [gbatemp: I cannot open G3DCVTR using Wine Staging on Mac](https://gbatemp.net/threads/i-cannot-open-g3dcvtr-using-wine-staging-on-mac-help.660311/)
- Multiple IMDs can be merged into one NSBMD by passing several inputs plus an output name to g3dcvtr in a batch command. — [NSMBHD: merge IMD models with G3DCVTR](https://nsmbhd.net/thread/5708-i-don-t-know-how-to-merge-imd-models-together-with-c3dcvtr/)
- g3dcvtr ships with `mdltex.bat`, which builds both NSBMD and NSBTX from an IMD. — [DSHack: Making a Custom Track](https://wiki.dshack.org/Wiki.jsp?page=Making+a+Custom+Track)

### Inferences
- On Apple Silicon macOS, g3dcvtr likely needs a recent Wine build (Homebrew `wine-stable`/Gcenx builds, which run under Rosetta 2) to handle a 32-bit Windows exe. The gbatemp report suggests Wine ≥ 9.15 works. This is unverified locally.
- Legality: g3dcvtr is proprietary Nintendo SDK code. The community treats it as "bring your own legally obtained copy" and does not redistribute it. A distributable or CI pipeline should not vendor it. Keep it as an optional, user-supplied local dependency, or replace it with an open writer.

### Gaps
- I found no explicit list of g3dcvtr CLI flags from a primary source, beyond `--help` existing and the `-emdl`/`-etex` style split implied by mdltex.bat. Run `wine g3dcvtr.exe --help` locally to capture them.
- I did not establish whether g3dcvtr is 32-bit or 64-bit PE, or which xerces DLL version it needs. Sources say 2_5_0 (original PDSMS) and 2_8 (AdAstra fork).

## IMD and NSBMD format documentation

### Takeaway
No formal public spec exists for IMD or NSBMD. The best references are code: apicula (Rust, 0BSD), noclip.website `src/nns_g3d/NNS_G3D.ts` (TypeScript), the PDSMS `formats/imd/*.java` IMD writer, the nns-blender-plugin `export_nitro.py` IMD writer, and nitro-g3d-tools' LibNitro.Intermediate and Binary converter. GBATEK documents the hardware GX command stream that NSBMD display lists contain.

### Cited Findings
- IMD is described as an XML-based intermediate format that G3DCVTR converts into NSBMD. — [MKDS wiki: NSMBD](http://mkds.wikidot.com/nsmbd)
- PDSMS has an IMD writer in `src/main/java/formats/imd/` (ImdModel, ImdNode, ImdTexture, ImdTextureIndexed, ImdPaletteArray, ImdTileset, ExportImdDialog…). — [AdAstra-LD PDSMS repo tree](https://github.com/AdAstra-LD/Pokemon-DS-Map-Studio)
- The IMD exporter in the NNS Blender plugin is `export_nitro.py`. — [nns-blender-plugin/export_nitro.py](https://github.com/jellees/nns-blender-plugin/blob/master/export_nitro.py)
- noclip.website's `src/nns_g3d/` contains `NNS_G3D.ts` (`parseNSBMD`, `parseNSBTX`, `BTX0`, `fx32`), `narc.ts`, `render.ts`, `Scenes_PokemonHGSS.ts`, `Scenes_PokemonPlatinum.ts`, `Scenes_MarioKartDS.ts` and `nsmbds_scenes.ts`. — [noclip.website src/nns_g3d](https://github.com/magcius/noclip.website/tree/main/src/nns_g3d)
- GBATEK's DS 3D section documents the geometry commands (POLYGON_ATTR, TEXIMAGE_PARAM, PLTT_BASE, DIF_AMB, …) that NSBMD display lists contain. It says "3D is more or less (about 92%) understood and described." — [GBATEK](https://problemkaputt.de/gbatek.htm) (DS 3D Video chapter)
- `necco-atsume/nsbmd-texture-tool` is an extractor and importer for NSBMD-embedded textures. — [nsbmd-texture-tool](https://github.com/necco-atsume/nsbmd-texture-tool)

### Inferences
- For a custom writer, the most efficient spec is apicula's `src/nitro/` parsers combined with noclip's NNS_G3D.ts. Both are complete enough to render HGSS maps, so they encode every field a map chunk uses.

### Gaps
- I did not locate Kiwi.ds or Lowlines NSBMD wiki pages during this session. They are historically cited but may be offline.
- I found no IMD XML schema document. The schema has to be inferred from the PDSMS and Blender-plugin writers or from sample IMDs.

## BDHC format (HGSS/Platinum terrain heights): documentation, generators, constraints

### Takeaway
BDHC is now well documented by the pret/pokeplatinum decompilation (`docs/maps/bdhc.md` plus `src/overlay005/bdhc.c`). It is a list of axis-aligned 2D rectangular "plates", each a plane (unit normal + constant), indexed by Z-scanline "strips". PDSMS has open Java BDHC readers and writers for both DP and HGSS variants (`BdhcWriterDP.java`, `BdhcWriterHGSS.java`, `BdhcLoaderHGSS.java`). That is a solid basis for a small headless generator from a tile-height grid.

### Cited Findings
- A plate is a 2D top-left corner, a 2D bottom-right corner, a unit normal and a constant. Height is `P_y = -(n_x*P_x + n_z*P_z + d) / n_y`. Plates may overlap at different heights (for example, bridges). The engine computes all candidate heights and picks the one closest to the object's current height. "If the map object is not within the bounds of any plate, collision detection and height calculation will behave erratically." — [pokeplatinum docs/maps/bdhc.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/bdhc.md)
- Strips are lists of plates that intersect a given Z "scanline". There is one strip per distinct plate Z-boundary except the minimum. The engine binary-searches strips by Z, then tests that strip's plates. "Some complex map can reach over 100 plates." The doc also gives formulas for deriving the normal (cross product of AB and AC) and `d = -n̂·A`. — [pokeplatinum docs/maps/bdhc.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/bdhc.md)
- Binary layout from the decomp loader: 4-byte magic, then u16 counts in order points, normals, constants, plates, strips, accessList. Arrays follow in the same order. `BDHCPoint {fx32 x, z}`, normals are `VecFx32`, constants `fx32`, `BDHCPlate {u16 firstPointIndex, secondPointIndex, normalIndex, constantIndex}`, `BDHCStrip {fx32 scanline; u16 accessListElementCount; u16 accessListStartIndex}`, access list `u16[]`. — [pokeplatinum src/overlay005/bdhc.c](https://github.com/pret/pokeplatinum/blob/main/src/overlay005/bdhc.c), [include/overlay005/bdhc.h](https://github.com/pret/pokeplatinum/blob/main/include/overlay005/bdhc.h)
- `#define BDHC_BUFFER_SIZE 0x9000` (36,864 bytes) in Platinum. This is the maximum BDHC size per loaded map buffer. — [pokeplatinum include/constants/field/bdhc.h](https://github.com/pret/pokeplatinum/blob/main/include/constants/field/bdhc.h)
- A map is 32×32 tiles or 512×512 world units (1 unit = 1/16 tile). Map data holds per-tile terrain attributes (collision and behavior), the base NSBMD model, BDHC, and map-prop instances. Map matrices place maps on a grid with per-map altitude. "Areas" own the prop models and textures, the map-model textures (map_tex_set NSBTX) and the lighting config. At most 4 maps are loaded at once. — [pokeplatinum docs/maps/maps.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/maps.md), [docs/maps/loading_maps.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/loading_maps.md)
- PDSMS `BdhcWriterHGSS.java` writes the "BDHC" magic, then u16 counts (points, slopes, zCoords, plates, stripes, plate-index count), then points, slopes, Z coords, plates (point indices, slope index, z index), stripes (u16 0, u16 y, u16 count, u16 offset) and indices. The HGSS strip entry appears to store the scanline as a 16-bit integer with a zero fractional half. — [AdAstra-LD PDSMS formats/bdhc/BdhcWriterHGSS.java](https://github.com/AdAstra-LD/Pokemon-DS-Map-Studio/blob/master/src/main/java/formats/bdhc/BdhcWriterHGSS.java)
- PDSMS also has BDHCAM (camera-plate) read/write, editing of collisions (`.per`) and BDHC terrain, and exports maps as OBJ, IMD and NSBMD. — [Project Pokemon PDSMS file page](https://projectpokemon.org/home/files/file/4237-pokemon-ds-map-studio/), [AdAstra-LD PDSMS repo tree](https://github.com/AdAstra-LD/Pokemon-DS-Map-Studio)
- DSPRE handles BDHCAM import/export, collision and permission editing, and map BIN import/export, which packages the permissions, model and BDHC into one land_data file. — [DSPRE README](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)
- HGSS land_data container layout as parsed by noclip: `u32@0x00` permissions size, `u32@0x04` props size, `u32@0x08` NSBMD size, `u16@0x12` extra HGSS header-section size, and the first section starts at 0x14. Props are 0x30-byte records (u32 modelID, fx32 x/y/z…). The embedded NSBMD follows the props, and BDHC comes after the model. — [noclip Scenes_PokemonHGSS.ts](https://github.com/magcius/noclip.website/blob/main/src/nns_g3d/Scenes_PokemonHGSS.ts)

### Inferences
- A tile-grid → BDHC generator is straightforward. Merge runs of equal-height or equal-slope tiles into rectangles (greedy meshing), compute normals and constants per the decomp formula, dedupe points, normals and constants into index tables, then build sorted strips from distinct Z-edges. Keep total size under 0x9000 bytes; the HGSS limit needs confirming. Port the PDSMS HGSS writer, or write a ~200-line Python equivalent, for byte-exact compatibility.
- HGSS and DP BDHC differ at least in strip encoding (PDSMS keeps separate DP and HGSS writers). Use the HGSS variant and validate against vanilla `land_data` files from the local ROM by round-tripping.

### Gaps
- I did not confirm the HGSS-specific BDHC buffer size or full format differences from the pokeheartgold decomp. The local `.codex-reference/pokeheartgold` has no named BDHC file, so the loader is likely still in unnamed overlay assembly (for example `asm/overlay_01_*`).
- I did not find community documentation of the meaning of HGSS land_data's extra header section (`u16@0x12`).

## Practical DS limits relevant to map chunks

### Takeaway
Hardware caps per frame are 2048 polygons and 6144 vertices in the geometry buffers. Texture VRAM is up to 4×128 KB slots (A–D) and texture palette VRAM is up to 96 KB (0x18000 addressable). The game typically allocates far less to map textures, because 4 map chunks plus props, overworld sprites and followers share these budgets.

### Cited Findings
- GBATEK RAM_COUNT register: "Number of Polygons currently stored in Polygon List RAM (0..2048)", "Number of Vertices currently stored in Vertex RAM (0..6144)". Internal 3D memory is 104 KB Polygon RAM and 144 KB Vertex RAM, double-buffered (52 KB×2 and 72 KB×2). — [GBATEK](https://problemkaputt.de/gbatek.htm)
- VRAM banks A, B, C, D (128 KB each) can be mapped as texture image slots 0–3. Bank E (64 KB) or banks F and G (16 KB) can be mapped as texture palette. Up to 6 palette slots address 0x18000 bytes. — [GBATEK](https://problemkaputt.de/gbatek.htm) (Memory Control / Texture Palette)
- Texture formats: 1 A3I5 (8bpp translucent), 2 4-color (2bpp), 3 16-color (4bpp), 4 256-color (8bpp), 5 4×4-texel compressed, 6 A5I3, 7 direct color (16bpp). The 4-color format uses an 8-byte palette-base step; the others use 16-byte steps. — [GBATEK](https://problemkaputt.de/gbatek.htm) (DS 3D Texture Formats)
- The DS supports 4 hardware lights. Platinum uses light 0 for map models and sprites, light 2 for building windows and light 3 for lamps and glass doors. The lighting config is per area. — [pokeplatinum docs/maps/maps.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/maps.md)
- Map-model textures come from the area's `map_tex_set` NSBTX, not from the map's NSBMD. noclip falls back to a default tileset when a model fails to bind to its area NSBTX. — [noclip Scenes_PokemonHGSS.ts](https://github.com/magcius/noclip.website/blob/main/src/nns_g3d/Scenes_PokemonHGSS.ts), [pokeplatinum docs/maps/maps.md](https://github.com/pret/pokeplatinum/blob/main/docs/maps/maps.md)

### Inferences
- New map NSBMDs should be built with textures external (NSBMD without TEX0), so materials bind by name to the area NSBTX. Every texture or palette name the model references must exist in the area's `map_tex_set` entry. This matches the PDSMS "OBJ → IMD → NSBMD → NSBTX" split and DSPRE's separate NSBTX editor.
- Polygon budget per chunk: with up to 4 chunks visible plus props and sprites, a few hundred quads per chunk is a safe target. Strip and quad output from the converter matters, since quads count as one polygon.

### Gaps
- I found no authoritative HGSS-specific numbers for the texture VRAM allocated to map tilesets, the per-chunk NSBMD size buffer, or documented crash thresholds for oversized maps. These should be measured from the decomp or ROM (FIELD heap layout; see the project memory on field heap budget).

## Tools that render HGSS maps offline (top-down / orthographic)

### Takeaway
noclip.website has dedicated HGSS and Platinum scene loaders (TypeScript, browser, WebGL/WebGPU). It parses `land_data.narc`, `map_tex_set.narc`, `build_model.narc`, `map_matrix.narc` and `bm_room.narc` and renders full matrices with props, which makes it the best reference renderer. For headless macOS, the most scriptable route is apicula `convert -f=glb` per map chunk (feeding the area NSBTX alongside), then Blender `--background` or a three.js/headless-GL script for orthographic top-down renders. DSPRE (Windows GUI) can export 512 px map screenshots and GLB/DAE.

### Cited Findings
- `Scenes_PokemonHGSS.ts` mounts land_data, map_tex_set, build_model, map_matrix and bm_room NARCs plus `maps.bin` headers. It iterates the matrix, slices the embedded NSBMD out of each land_data file, binds it to the area tileset NSBTX (falling back to a default), and places it at `(x*512, height*8, y*512)`. Props are parsed from 0x30-byte records and loaded from build_model. — [noclip Scenes_PokemonHGSS.ts](https://github.com/magcius/noclip.website/blob/main/src/nns_g3d/Scenes_PokemonHGSS.ts)
- noclip's repo license is reported by GitHub as NOASSERTION (a custom license file), and noclip is a browser app. The nns_g3d directory was last changed 2026-05-26. — GitHub API
- apicula's CLI converts NSBMD + NSBTX inputs together into DAE or GLB. It is 0BSD and builds with Rust. — [apicula](https://github.com/scurest/apicula)
- DSPRE: 3D OpenGL map visualization, DAE/GLB/NSBMD model export, 512 px map screenshot export. It needs Windows 7+ and .NET Framework 4.8. HGSS English has "Full Support"; hg-engine ROMs have "partial support, some editors disabled". — [DSPRE README](https://github.com/DS-Pokemon-Rom-Editor/DSPRE)
- DSPRE publishes an experimental cross-platform Avalonia build ("canary-avalonia", 2026-10-14) for Windows and Linux x64, self-contained. Its notes say "expect missing features, rough edges, and instability". No macOS asset is provided. — [DSPRE releases](https://github.com/DS-Pokemon-Rom-Editor/DSPRE/releases)
- PDSMS is Java 8, "tested under Windows, Linux and MacOS", and GUI-only (launched as a jar). The README documents no CLI or headless mode. — [Trifindo PDSMS](https://github.com/Trifindo/Pokemon-DS-Map-Studio), [AdAstra-LD PDSMS](https://github.com/AdAstra-LD/Pokemon-DS-Map-Studio)
- Rust crate `uxie` lists Platinum and HGSS ROM support. Later versions describe Platinum as primary and HGSS as partial. I did not verify whether it includes map or model handling. — [docs.rs uxie 0.4.0](https://docs.rs/crate/uxie/0.4.0)

### Inferences — recommended headless macOS pipeline
- **Read/render:** extract NARCs with an existing NDS/NARC tool (for example `ndstool` plus a small NARC unpacker, or apicula's `extract`). Slice land_data into permissions, props, NSBMD and BDHC using the noclip offsets. Run `apicula convert -f=glb chunk.nsbmd area.nsbtx`, then render orthographically with `blender --background --python render.py`, or with a Node three.js plus headless-gl script. A port of noclip's loader is the alternative if exact DS material and lighting fidelity matters.
- **Generate:** tile grid → mesh (Python) → IMD XML (port the PDSMS ImdModel writer) → NSBMD via (a) `wine g3dcvtr.exe` (best fidelity, user-supplied binary, legal grey), (b) nitro-g3d-tools BinaryConverter under .NET/Mono (open but unproven and unmaintained), or (c) a custom open NSBMD writer validated by apicula round-trip. Textures go through ptexconv to NNS TGA or raw data, then into the area NSBTX. BDHC uses a custom Python writer modeled on PDSMS `BdhcWriterHGSS.java` and the pokeplatinum docs. Validate in melonDS with memory-backed checks.
- For OBJ/glTF input, Blender plus the NNS plugin can produce IMD, but only interactively. Scripting it headlessly through `blender --background --python` calling the exporter operator is plausible but undocumented.

### Gaps
- I did not test whether apicula correctly applies HGSS area NSBTX textures to external-texture map NSBMDs. noclip's fallback logic hints that some maps fail to bind.
- I found no standalone "pokemon-map-viewer" or three.js HGSS viewer beyond noclip.
- Kodewerx and other older format pages were not reached in this session.
