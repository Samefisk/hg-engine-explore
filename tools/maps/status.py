"""Is the map work in a consistent state? Every stale piece with the command that fixes it.

  python3 -B -m tools.maps.status [--map M] [--json]
  python3 -B -m tools.maps.status --refresh-hashes    # only when a finding names it

Checks (read-only; a few seconds, lint is most of it):
  reports   build/map-style/report-NNNN.json: each land's model.nsbmd on disk
            matches the report (its modelHashes, else the re-composed grid, as
            `style resolve --write` requires), and the report stores `layout`.
            Stored hashes that only predate a compose change (the re-composed
            grid matches disk) are refreshed with --refresh-hashes.
  showcase  `showcase write` run on a temp copy of data/maps changes nothing.
  lint      `tools.maps lint` errors (warnings are informational).
  rom       test.nds (where `make` and the delta build put the ROM) is newer
            than every file under data/maps/.
  lab       the champion's code and judge hashes match the tree (else the
            next `lab accept` needs a fresh bench); open defects (informational).

--map M limits the report check to reports holding M's lands and skips the
showcase check unless M is a showcase map or Cherrygrove. Exit 0 when nothing
needs action, 1 when a finding is listed.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from .cli import REPO

OVERRIDES = REPO / "data/maps"
REPORT_DIR = REPO / "build/map-style"
ROM = REPO / "test.nds"
STATUS = "python3 -B -m tools.maps.status"
SHOWCASE_WRITE = "python3 -B -m tools.maps.showcase write"


def finding(name: str, stale: str, fix: str) -> dict:
    return {"name": name, "stale": stale, "fix": fix}


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def report_lands(report: dict) -> list[int]:
    from .style.edit import report_lands as lands
    return lands(report)


def disk_hashes(overrides: Path, lands: list[int]) -> dict[str, str | None]:
    """SHA-256 of each land's model.nsbmd in the override tree (None when missing)."""
    return {str(n): _sha(overrides / "land" / f"{n:04d}" / "model.nsbmd") for n in lands}


def _layout_file(overrides: Path, maps: list[int]) -> str:
    for map_id in maps:
        found = sorted((overrides / "layouts").glob(f"{map_id}-*.txt"))
        if found:
            return str(found[0].relative_to(REPO) if found[0].is_relative_to(REPO) else found[0])
    return "LAYOUT.txt"


def _generate_cmd(report: dict, layout_path: str) -> str:
    return (f"python3 -B -m tools.maps.style generate --layout {layout_path} --map {report['map']} "
            f"--land {report['land']} --relax {report.get('relax', 0)} --seeds {report.get('seedsTried', 16)}"
            f" && {SHOWCASE_WRITE}")


def check_report(path: Path, report: dict, overrides: Path, recompose: Callable[[dict], dict],
                 land_maps: dict[int, list[int]]) -> tuple[dict, list[dict]]:
    """(check entry, findings) for one generate report.

    recompose(report) -> {land: sha} of the report grid composed now (cli.write_lands write=False).
    """
    lands = report_lands(report) if "grid" in report or report.get("lands") else []
    entry = {"report": path.name, "lands": lands, "state": "ok", "storedHashes": bool(report.get("modelHashes")),
             "layout": "layout" in report}
    if "grid" not in report or not report.get("written"):
        entry["state"] = "never-written"  # resolve refuses it; the lands on disk come from elsewhere
        return entry, []
    tag = path.stem
    maps = sorted({m for n in lands for m in land_maps.get(n, [])})
    entry["maps"] = maps
    layout_path = _layout_file(overrides, maps)
    out = []
    disk = disk_hashes(overrides, lands)
    stored = report.get("modelHashes") or {}
    expected, recomposed = (stored, None) if stored else (None, recompose(report))
    expected = expected or recomposed
    bad = [n for n in lands if disk[str(n)] is None or disk[str(n)] != expected.get(str(n))]
    if bad and stored:
        recomposed = recompose(report)
        if all(disk[str(n)] is not None and disk[str(n)] == recomposed.get(str(n)) for n in lands):
            entry["state"] = "hashes-stale"
            out.append(finding(f"{tag}-hashes",
                               f"{path.name} modelHashes for lands {bad} predate the current compose; the lands on "
                               "disk are this grid re-composed, but `style resolve --write` refuses them",
                               f"{STATUS} --refresh-hashes"))
            bad = []
    if bad:
        entry["state"] = "lands-differ"
        missing = [n for n in bad if disk[str(n)] is None]
        out.append(finding(f"{tag}-lands",
                           f"lands {bad} model.nsbmd on disk " + (f"(missing: {missing}) " if missing else "")
                           + f"differ from {path.name}'s grid (regenerated or hand-edited since); "
                           "`style resolve --write` refuses them. Regenerate (or delete the report if disk wins)",
                           _generate_cmd(report, layout_path)))
    if "layout" not in report:
        out.append(finding(f"{tag}-layout",
                           f"{path.name} has no stored `layout`; `style resolve` needs "
                           f"--layout {layout_path} --relax N on every call",
                           _generate_cmd(report, layout_path)))
    return entry, out


def check_reports(report_dir: Path, overrides: Path, recompose: Callable[[dict], dict],
                  land_maps: dict[int, list[int]], only_lands: set[int] | None = None) -> tuple[list, list]:
    entries, out = [], []
    for path in sorted(report_dir.glob("report-*.json")):
        report = json.loads(path.read_text())
        if only_lands is not None and not only_lands & set(report_lands(report) if "grid" in report else []):
            continue
        entry, found = check_report(path, report, overrides, recompose, land_maps)
        entries.append(entry)
        out += found
    return entries, out


def refresh_hashes(report_dir: Path, overrides: Path, recompose: Callable[[dict], dict]) -> list[str]:
    """Store the re-composed hashes in reports whose grid, composed now, is exactly the lands on disk."""
    done = []
    for path in sorted(report_dir.glob("report-*.json")):
        report = json.loads(path.read_text())
        if "grid" not in report or not report.get("written"):
            continue
        lands = report_lands(report)
        disk = disk_hashes(overrides, lands)
        if report.get("modelHashes") and all(disk[str(n)] == report["modelHashes"].get(str(n)) for n in lands):
            continue
        fresh = recompose(report)
        if any(disk[str(n)] is None or disk[str(n)] != fresh.get(str(n)) for n in lands):
            continue  # disk is not this grid: refreshing would hide a real mismatch
        report["modelHashes"] = {str(n): fresh[str(n)] for n in lands}
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(report, indent=1) + "\n")
        tmp.replace(path)
        done.append(path.name)
    return done


BUILD_KINDS = ("events", "headers", "land", "matrix", "area")  # what `apply` packs; layouts/waivers are not


def newest_file(root: Path) -> tuple[Path | None, float]:
    files = [p for kind in BUILD_KINDS for p in (root / kind).rglob("*")
             if p.is_file() and p.name != ".DS_Store" and not p.name.endswith(".tmp")]
    if not files:
        return None, 0.0
    newest = max(files, key=lambda p: p.stat().st_mtime)
    return newest, newest.stat().st_mtime


def _stamp(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def check_rom(rom: Path, overrides: Path) -> tuple[dict, list[dict]]:
    newest, newest_t = newest_file(overrides)
    entry = {"rom": str(rom.relative_to(REPO) if rom.is_relative_to(REPO) else rom),
             "romTime": _stamp(rom.stat().st_mtime) if rom.exists() else None,
             "newestOverride": str(newest.relative_to(overrides)) if newest else None,
             "newestTime": _stamp(newest_t) if newest else None}
    fix = "build with the hg-engine-delta-build skill (writes test.nds)"
    if not rom.exists():
        entry["fresh"] = False
        return entry, [finding("rom-missing", f"{entry['rom']} does not exist", fix)]
    entry["fresh"] = newest is None or rom.stat().st_mtime >= newest_t
    if entry["fresh"]:
        return entry, []
    return entry, [finding("rom-stale", f"{entry['rom']} ({entry['romTime']}) is older than data/maps/"
                           f"{entry['newestOverride']} ({entry['newestTime']})", fix)]


def check_showcase(overrides: Path) -> tuple[dict, list[dict]]:
    """Run `showcase write` on a temp copy of the override tree; list the files it would change."""
    from . import showcase
    with tempfile.TemporaryDirectory(prefix="map-status-") as tmp:
        copy = Path(tmp) / "maps"
        shutil.copytree(overrides, copy)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                showcase.write(copy)
        except (SystemExit, Exception) as error:  # noqa: BLE001 - any failure is the finding
            return ({"state": "write-fails", "error": str(error)},
                    [finding("showcase-write-fails", f"`showcase write` fails on the current tree: {error}",
                             SHOWCASE_WRITE)])
        before = {p.relative_to(overrides): p for p in overrides.rglob("*") if p.is_file()}
        after = {p.relative_to(copy): p for p in copy.rglob("*") if p.is_file()}
        changed = sorted(str(k) for k in before.keys() | after.keys()
                         if k not in before or k not in after or before[k].read_bytes() != after[k].read_bytes())
    if not changed:
        return {"state": "ok", "changes": []}, []
    return ({"state": "stale", "changes": changed},
            [finding("showcase", f"showcase panels/events not restored; `showcase write` would change {changed}",
                     SHOWCASE_WRITE)])


def check_lint(base, edited, overrides: Path) -> tuple[dict, list[dict]]:
    from . import lint
    try:
        result = lint.lint(edited, base, lint.load_waivers(overrides))
    except (ValueError, KeyError) as error:
        return ({"errors": None, "error": str(error)},
                [finding("lint-waivers", f"data/maps/lint_waivers.json is invalid: {error}",
                         "fix the waiver file, then python3 -B -m tools.maps lint")])
    entry = {"errors": len(result[lint.ERROR]), "warnings": len(result[lint.WARNING]),
             "waived": len(result["waived"]), "firstErrors": result[lint.ERROR][:5]}
    if not result[lint.ERROR]:
        return entry, []
    return entry, [finding("lint", f"{entry['errors']} lint error(s) block the build, e.g. {result[lint.ERROR][0]}",
                           "python3 -B -m tools.maps lint   # fix each, or waive in data/maps/lint_waivers.json")]


def check_lab() -> tuple[dict, list[dict]]:
    from .style import lab
    champ, code, judge = lab.champion(), lab.code_hash(), lab.judge_hash()
    defects = [d["id"] for d in lab._read_jsonl(lab.DEFECTS) if d.get("status") == "open"]
    decided = {e["run"] for e in lab._read_jsonl(lab.LEDGER)}
    pending = []
    for path in sorted(lab.RUNS.glob("*.json")):
        try:
            run = json.loads(path.read_text())
        except ValueError:
            continue
        if run.get("codeHash") == code and not run.get("quick") and run.get("id") not in decided:
            pending.append(run["id"])
    entry = {"codeHash": code, "judgeHash": judge, "champion": champ and champ["run"],
             "codeMatches": bool(champ) and champ["codeHash"] == code,
             "judgeMatches": bool(champ) and champ.get("judgeHash") == judge,
             "openDefects": defects, "pendingRuns": pending}
    lab_cmd = "python3 -B -m tools.maps.style.lab"
    if not champ:
        return entry, [finding("lab-no-champion", "the lab ledger has no accepted champion",
                               f"{lab_cmd} bench --label baseline && {lab_cmd} accept --rebaseline --run R --note N")]
    if not entry["judgeMatches"]:
        return entry, [finding("lab-judge-changed", f"judge (seams.py, score.py, bench) hash {judge} differs from "
                               f"champion {champ['run']}'s {champ.get('judgeHash')}; accept needs --rebaseline",
                               f"{lab_cmd} judge-check && {lab_cmd} bench --label L   # then accept --rebaseline")]
    if entry["codeMatches"]:
        return entry, []
    if pending:
        return entry, [finding("lab-decide", f"run(s) {pending} measured the current tree but are not in the ledger",
                               f"{lab_cmd} accept --run {pending[-1]} --note N   # or: reject --run ... --note N")]
    return entry, [finding("lab-bench", f"code hash {code} differs from champion {champ['run']}'s "
                           f"{champ['codeHash']}; the next accept needs a full bench (~25 min)",
                           f"{lab_cmd} bench --label L")]


def _land_maps(edited) -> dict[int, list[int]]:
    where: dict[int, list[int]] = {}
    for map_id, header in enumerate(edited.headers):
        if header.get("alias"):
            continue
        try:
            matrix = edited.matrix_for(map_id)
        except (IndexError, KeyError):
            continue
        for cz, row in enumerate(matrix["landData"]):
            for cx, land in enumerate(row):
                if matrix["headers"] is None or matrix["headers"][cz][cx] == map_id:
                    where.setdefault(land, []).append(map_id)
    return where


def run(map_id: int | None = None, overrides: Path = OVERRIDES, report_dir: Path = REPORT_DIR,
        rom: Path = ROM) -> dict:
    from . import world
    from .style import edit
    started = time.time()
    base = edit._base_world()  # one ROM load, shared with the re-compose
    edited = world.apply_overrides(base, overrides)
    land_maps = _land_maps(edited)
    checks, findings = {}, []

    def recompose(report: dict) -> dict:
        from .style.cli import write_lands
        return write_lands(base, edit.kit_for(report["tileset"]), report["grid"], report["map"],
                           report["land"], overrides, write=False)["modelHashes"]

    def guarded(name: str, fn, command: str):
        try:
            entry, found = fn()
        except Exception as error:  # noqa: BLE001 - a crashed check is itself a finding
            entry, found = {"error": f"{type(error).__name__}: {error}"}, [
                finding(f"{name}-check-failed", f"the {name} check crashed: {type(error).__name__}: {error}",
                        command)]
        checks[name] = entry
        findings.extend(found)

    only = {n for n, maps in land_maps.items() if map_id in maps} if map_id is not None else None
    if only is not None and not only:
        findings.append(finding("map-unknown", f"map {map_id} has no land in the edited tree; nothing to check",
                                f"{STATUS}  # without --map, or a map id with land"))
    guarded("reports", lambda: check_reports(report_dir, overrides, recompose, land_maps, only),
            f"{STATUS} --json")
    from .showcase import CHERRYGROVE, SHOWCASE
    if map_id is None or map_id in {CHERRYGROVE, *(e["map"] for e in SHOWCASE)}:
        guarded("showcase", lambda: check_showcase(overrides), SHOWCASE_WRITE)
    guarded("lint", lambda: check_lint(base, edited, overrides), "python3 -B -m tools.maps lint")
    if overrides.resolve() == OVERRIDES.resolve():  # test.nds is built from data/maps, not from a copy
        guarded("rom", lambda: check_rom(rom, overrides), f"{STATUS} --json")
    guarded("lab", check_lab, "python3 -B -m tools.maps.style.lab status")
    return {"ok": not findings, "map": map_id, "findings": findings, "checks": checks,
            "seconds": round(time.time() - started, 1)}


def render(result: dict) -> str:
    count = len(result["findings"])
    lines = [f"map status: {'nothing to do' if result['ok'] else f'{count} action(s)'}"]
    for f in result["findings"]:
        lines += [f"  [{f['name']}] {f['stale']}", f"      fix: {f['fix']}"]
    c = result["checks"]
    lines.append("checks:")
    if "reports" in c:
        reports = c["reports"]
        lines.append("  reports: " + (reports["error"] if isinstance(reports, dict) else "; ".join(
            f"{r['report']} {r['state']} lands {r['lands']}" for r in reports) or "none"))
    if "showcase" in c:
        lines.append(f"  showcase: {c['showcase'].get('state', c['showcase'].get('error'))}")
    if "lint" in c:
        lint = c["lint"]
        lines.append(f"  lint: {lint.get('errors')} error(s), {lint.get('warnings')} warning(s), "
                     f"{lint.get('waived')} waived" if "error" not in lint else f"  lint: {lint['error']}")
    if "rom" in c:
        rom = c["rom"]
        lines.append(f"  rom: {rom.get('rom')} {rom.get('romTime')}, newest override {rom.get('newestOverride')} "
                     f"{rom.get('newestTime')}" if "error" not in rom else f"  rom: {rom['error']}")
    if "lab" in c:
        lab = c["lab"]
        lines.append(f"  lab: champion {lab.get('champion')}, code {'matches' if lab.get('codeMatches') else 'differs'}, "
                     f"judge {'unchanged' if lab.get('judgeMatches') else 'changed'}, "
                     f"{len(lab.get('openDefects', []))} open defect(s) {lab.get('openDefects', [])}, "
                     f"pending runs {lab.get('pendingRuns', [])}" if "error" not in lab else f"  lab: {lab['error']}")
    lines.append(f"({result['seconds']} s)")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.status", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--map", type=int, help="limit report checks to this map's lands")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--refresh-hashes", action="store_true",
                        help="store re-composed modelHashes in reports whose grid is exactly the lands on disk")
    parser.add_argument("--overrides", type=Path, default=OVERRIDES)
    args = parser.parse_args(argv)
    if args.refresh_hashes:
        if args.overrides.resolve() != OVERRIDES.resolve():
            print("refused: --refresh-hashes updates build/map-style reports, which describe data/maps only",
                  file=sys.stderr)
            return 2
        from .style import edit
        from .style.cli import write_lands
        base = edit._base_world()
        done = refresh_hashes(REPORT_DIR, args.overrides, lambda r: write_lands(
            base, edit.kit_for(r["tileset"]), r["grid"], r["map"], r["land"], args.overrides,
            write=False)["modelHashes"])
        print(f"refreshed modelHashes: {done or 'none'}")
    result = run(args.map, args.overrides)
    print(json.dumps(result, indent=1) if args.json else render(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
