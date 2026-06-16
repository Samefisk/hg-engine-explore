#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().with_name("route30_compact_variants.html")
VIEWER = ROOT / "scripts" / "overworld_behavior_profile_viewer.py"
ICON_ORIGIN = "http://127.0.0.1:8765"


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def short_species(species: dict) -> str:
    return str(species.get("symbol", species.get("name", ""))).removeprefix("SPECIES_")


def icon(species: dict, size: str = "mon-icon") -> str:
    url = species.get("iconUrl")
    if not url:
        return f'<span class="{size}" aria-hidden="true"></span>'
    return f'<img class="{size}" src="{ICON_ORIGIN}{esc(url)}" alt="{esc(species.get("name", ""))}" loading="lazy">'


def text_icon(kind: str, label: str) -> str:
    icons = {
        "walk": "W",
        "surf": "~",
        "rock": "R",
        "old": "1",
        "good": "2",
        "super": "3",
        "am": "AM",
        "day": "D",
        "night": "N",
        "sound": "S",
        "swarm": "*",
        "fish": "~",
    }
    return f'<span class="type-icon type-{esc(kind)}" title="{esc(label)}">{esc(icons.get(kind, label[:1]))}</span>'


def input_value(value, cls: str = "") -> str:
    return f'<input class="field {esc(cls)}" value="{esc(value)}" readonly>'


def number_value(value, cls: str = "") -> str:
    return f'<input class="field num-field {esc(cls)}" value="{esc(value)}" readonly>'


def species_cell(species: dict, form: int = 0, compact: bool = False) -> str:
    compact_class = " compact" if compact else ""
    return (
        f'<span class="species-edit{compact_class}">'
        f'{icon(species)}'
        f'{input_value(short_species(species), "species-field")}'
        f'{number_value(form, "form-field")}'
        "</span>"
    )


def panel(title: str, body: str, icon_kind: str | None = None, extra: str = "") -> str:
    icon_html = text_icon(icon_kind, title) if icon_kind else ""
    return (
        f'<section class="panel {esc(extra)}">'
        f'<div class="panel-head">{icon_html}<strong>{esc(title)}</strong></div>'
        f'{body}'
        "</section>"
    )


def route_title(route: dict, variant: str) -> str:
    map_text = ", ".join(item["symbol"] for item in route["maps"])
    return (
        '<header class="topbar">'
        f'<div><h1>{esc(variant)} <span>{esc(route["name"])}</span></h1>'
        f'<p>Encounter #{esc(route["id"])} · {esc(map_text)} · {esc(route["speciesCount"])} Pokemon</p></div>'
        '<span class="source-pill">Source</span>'
        "</header>"
    )


def rate_strip(route: dict, dense: bool = False) -> str:
    icon_by_key = {
        "walkrate": "walk",
        "surfrate": "surf",
        "rocksmashrate": "rock",
        "oldrodrate": "old",
        "goodrodrate": "good",
        "superrodrate": "super",
    }
    cells = []
    for rate in route["rates"]:
        label = rate["label"]
        cells.append(
            '<label class="rate-cell">'
            f'{text_icon(icon_by_key.get(rate["key"], "walk"), label)}'
            f'<span>{esc("" if dense else label)}</span>'
            f'{number_value(rate["value"], "rate-input")}'
            "</label>"
        )
    return '<section class="rate-strip">' + "".join(cells) + "</section>"


def grass_matrix(route: dict, mode: str = "sheet") -> str:
    tables = {table["key"]: table for table in route["pokemonTables"]}
    headings = [
        ("morning", "am", "Morning"),
        ("day", "day", "Day"),
        ("night", "night", "Night"),
    ]
    rows = []
    for idx, level in enumerate(route["grassLevels"]):
        row = [
            f'<div class="cell slot">{esc(level["slot"])}</div>',
            f'<div class="cell rate">{esc(level["weight"])}%</div>',
            f'<div class="cell level">{number_value(level["value"], "level-input")}</div>',
        ]
        for key, _icon_kind, _label in headings:
            slot = tables[key]["slots"][idx]
            row.append(f'<div class="cell time-cell">{species_cell(slot["species"], slot["form"], compact=True)}</div>')
        rows.append(f'<div class="matrix-row">{"".join(row)}</div>')
    head = (
        '<div class="matrix-head">'
        '<div>#</div><div>%</div><div>Lv</div>'
        + "".join(f'<div>{text_icon(kind, label)}<span>{esc(label if mode != "icons" else "")}</span></div>' for _key, kind, label in headings)
        + "</div>"
    )
    return panel("Grass", f'<div class="grass-matrix {esc(mode)}">{head}{"".join(rows)}</div>', "walk", "grass-panel")


def grass_matrix_split(route: dict) -> str:
    tables = {table["key"]: table for table in route["pokemonTables"]}
    headings = [("morning", "am", "AM"), ("day", "day", "Day"), ("night", "night", "Night")]

    def half(start: int, stop: int) -> str:
        rows = []
        for idx, level in enumerate(route["grassLevels"][start:stop], start):
            row = [
                f'<div class="cell slot">{esc(level["slot"])}</div>',
                f'<div class="cell rate">{esc(level["weight"])}%</div>',
                f'<div class="cell level">{number_value(level["value"], "level-input")}</div>',
            ]
            for key, _kind, _label in headings:
                slot = tables[key]["slots"][idx]
                row.append(f'<div class="cell time-cell">{species_cell(slot["species"], slot["form"], compact=True)}</div>')
            rows.append(f'<div class="matrix-row">{"".join(row)}</div>')
        head = (
            '<div class="matrix-head">'
            '<div>#</div><div>%</div><div>Lv</div>'
            + "".join(f'<div>{text_icon(kind, label)}<span>{esc(label)}</span></div>' for _key, kind, label in headings)
            + "</div>"
        )
        return f'<div class="grass-matrix split">{head}{"".join(rows)}</div>'

    return panel("Grass", f'<div class="split-grass">{half(0, 6)}{half(6, 12)}</div>', "walk", "grass-panel")


def compact_pokemon_table(table: dict, kind: str, with_levels: bool = False) -> str:
    header = '<div class="mini-head"><div>#</div><div>%</div><div>Pokemon</div>'
    header += '<div>Min</div><div>Max</div>' if with_levels else ""
    header += "</div>"
    rows = []
    for slot in table["slots"]:
        species = slot["species"]
        if with_levels:
            body = (
                f'<div>{esc(slot["slot"])}</div><div>{esc(slot.get("weight", ""))}</div>'
                f'<div>{species_cell(species, slot.get("form", 0), compact=True)}</div>'
                f'<div>{number_value(slot.get("minLevel", 0), "tiny-num")}</div>'
                f'<div>{number_value(slot.get("maxLevel", 0), "tiny-num")}</div>'
            )
        else:
            body = (
                f'<div>{esc(slot["slot"])}</div><div>{esc(slot.get("weight", ""))}</div>'
                f'<div>{species_cell(species, slot.get("form", 0), compact=True)}</div>'
            )
        rows.append(f'<div class="mini-row">{"".join(body)}</div>')
    cls = "with-levels" if with_levels else "sound-table"
    return panel(table["label"], f'<div class="mini-table {cls}">{header}{"".join(rows)}</div>', kind)


def swarms_panel(route: dict, compact: bool = True) -> str:
    rows = []
    for swarm in route["swarms"]:
        label = swarm["label"].replace(" swarm", "")
        rows.append(
            f'<div class="swarm-row"><span>{esc(label)}</span>{species_cell(swarm["species"], swarm["form"], compact=True)}</div>'
        )
    return panel("Swarms", '<div class="swarm-grid">' + "".join(rows) + "</div>", "swarm")


def secondary_panels(route: dict) -> str:
    sound = {table["key"]: table for table in route["pokemonTables"] if table["key"] in {"hoenn", "sinnoh"}}
    slot_kind = {
        "surf": "surf",
        "rockSmash": "rock",
        "oldRod": "old",
        "goodRod": "good",
        "superRod": "super",
    }
    panels = [compact_pokemon_table(table, slot_kind.get(table["key"], "fish"), with_levels=True) for table in route["slotTables"]]
    panels += [compact_pokemon_table(sound["hoenn"], "sound"), compact_pokemon_table(sound["sinnoh"], "sound"), swarms_panel(route)]
    return "".join(panels)


def variant_a(route: dict) -> str:
    return (
        '<main class="preview variant-a">'
        + route_title(route, "A")
        + rate_strip(route)
        + '<section class="sheet-layout">'
        + grass_matrix(route, "sheet")
        + '<div class="secondary-grid">'
        + secondary_panels(route)
        + "</div></section></main>"
    )


def variant_b(route: dict) -> str:
    return (
        '<main class="preview variant-b">'
        + route_title(route, "B")
        + '<div class="console-layout">'
        + '<div class="left-stack">'
        + rate_strip(route, dense=True)
        + grass_matrix(route, "icons")
        + "</div>"
        + '<div class="right-stack">'
        + secondary_panels(route)
        + "</div></div></main>"
    )


def variant_c(route: dict) -> str:
    return (
        '<main class="preview variant-c">'
        + route_title(route, "C")
        + '<section class="responsive-layout">'
        + rate_strip(route)
        + grass_matrix(route, "responsive")
        + '<div class="responsive-secondary">'
        + secondary_panels(route)
        + "</div></section></main>"
    )


def variant_d(route: dict) -> str:
    return (
        '<main class="preview variant-d">'
        + route_title(route, "D")
        + rate_strip(route, dense=True)
        + grass_matrix_split(route)
        + '<section class="workbench-secondary">'
        + secondary_panels(route)
        + "</section></main>"
    )


CSS = r"""
  :root {
    --bg: #eef2f7;
    --panel: #ffffff;
    --line: #cfd8e6;
    --line-soft: #e5eaf2;
    --ink: #151b23;
    --muted: #61708a;
    --green: #0f766e;
    --green-soft: #e7f7f2;
    --blue: #0b6ea8;
    --blue-soft: #e8f3fb;
    --gold: #b7791f;
    --violet: #6d28d9;
    --rose: #be123c;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font: 12px/1.25 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .preview {
    width: 100vw;
    height: 100vh;
    padding: 10px;
    overflow: hidden;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: 8px;
  }
  .preview:not(.active) { display: none; }
  .topbar {
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 8px 10px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
  }
  h1 { margin: 0; font-size: 18px; line-height: 1; letter-spacing: 0; }
  h1 span { font-size: 20px; }
  p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
  .source-pill {
    color: #0f5f59;
    background: #d9f4ee;
    border-radius: 999px;
    padding: 5px 10px;
    font-weight: 800;
  }
  .rate-strip {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 5px;
    min-height: 34px;
  }
  .rate-cell {
    display: grid;
    grid-template-columns: 23px minmax(0, 1fr) 46px;
    align-items: center;
    gap: 4px;
    min-width: 0;
    padding: 4px;
    border: 1px solid var(--line);
    border-radius: 7px;
    background: var(--panel);
  }
  .rate-cell span:not(.type-icon) {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--muted);
    text-transform: uppercase;
    font-weight: 800;
    letter-spacing: .02em;
  }
  .field {
    width: 100%;
    height: 24px;
    min-width: 0;
    border: 1px solid var(--line);
    border-radius: 5px;
    background: #fff;
    color: var(--ink);
    padding: 0 6px;
    font: 800 12px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .num-field {
    text-align: center;
    padding: 0 3px;
  }
  .rate-input { height: 24px; }
  .type-icon {
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 5px;
    border: 1px solid var(--line);
    background: #f7fafc;
    color: var(--muted);
    font: 900 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .type-walk, .type-am, .type-day, .type-night { color: #118044; background: #f0fdf4; }
  .type-surf, .type-old, .type-good, .type-super, .type-fish { color: var(--blue); background: var(--blue-soft); }
  .type-rock { color: #8a5b12; background: #fff8e6; }
  .type-sound { color: var(--violet); background: #f5f3ff; }
  .type-swarm { color: var(--rose); background: #fff1f2; }
  .type-am { color: #c2410c; background: #fff7ed; }
  .type-day { color: #b7791f; background: #fefce8; }
  .type-night { color: #4338ca; background: #eef2ff; }
  .panel {
    min-width: 0;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    overflow: hidden;
  }
  .panel-head {
    height: 28px;
    padding: 3px 6px;
    display: flex;
    align-items: center;
    gap: 5px;
    background: #f8fafc;
    border-bottom: 1px solid var(--line);
  }
  .panel-head strong {
    font-size: 12px;
    line-height: 1;
  }
  .grass-matrix {
    display: grid;
    grid-template-rows: 24px repeat(12, 26px);
  }
  .matrix-head,
  .matrix-row {
    display: grid;
    grid-template-columns: 30px 42px 50px repeat(3, minmax(130px, 1fr));
    min-width: 0;
  }
  .matrix-head > div,
  .cell {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 4px;
    border-bottom: 1px solid var(--line-soft);
    border-right: 1px solid var(--line-soft);
    padding: 2px 4px;
  }
  .matrix-head > div {
    color: var(--muted);
    background: #fbfdff;
    text-transform: uppercase;
    font-weight: 900;
    font-size: 10px;
    letter-spacing: .03em;
  }
  .matrix-row:hover .cell { background: #fbfffd; }
  .slot, .rate {
    justify-content: center;
    color: var(--muted);
    font-weight: 800;
  }
  .rate { color: var(--green); }
  .level-input { height: 22px; }
  .species-edit {
    display: grid;
    grid-template-columns: 22px minmax(58px, 1fr) 34px;
    align-items: center;
    gap: 4px;
    min-width: 0;
    width: 100%;
  }
  .species-edit.compact {
    grid-template-columns: 20px minmax(48px, 1fr) 30px;
  }
  .mon-icon {
    width: 22px;
    height: 22px;
    object-fit: contain;
    image-rendering: pixelated;
  }
  .species-edit.compact .mon-icon {
    width: 20px;
    height: 20px;
  }
  .form-field, .tiny-num { height: 22px; }
  .mini-table {
    display: grid;
    grid-template-rows: 21px;
  }
  .mini-head, .mini-row {
    display: grid;
    grid-template-columns: 24px 30px minmax(86px, 1fr);
    align-items: center;
  }
  .mini-table.with-levels .mini-head,
  .mini-table.with-levels .mini-row {
    grid-template-columns: 22px 28px minmax(96px, 1fr) 36px 36px;
  }
  .mini-head > div,
  .mini-row > div {
    min-width: 0;
    border-bottom: 1px solid var(--line-soft);
    border-right: 1px solid var(--line-soft);
    padding: 2px 4px;
    height: 26px;
    display: flex;
    align-items: center;
  }
  .mini-head > div {
    height: 21px;
    font-size: 9px;
    color: var(--muted);
    text-transform: uppercase;
    font-weight: 900;
    background: #fbfdff;
  }
  .mini-row > div:nth-child(1),
  .mini-row > div:nth-child(2) {
    justify-content: center;
    color: var(--muted);
    font-weight: 800;
  }
  .swarm-grid {
    display: grid;
    gap: 0;
  }
  .swarm-row {
    min-height: 28px;
    display: grid;
    grid-template-columns: 64px minmax(0, 1fr);
    gap: 4px;
    align-items: center;
    padding: 2px 5px;
    border-bottom: 1px solid var(--line-soft);
  }
  .swarm-row > span:first-child {
    color: var(--muted);
    font-weight: 800;
    font-size: 10px;
    text-transform: uppercase;
  }
  .variant-a {
    grid-template-rows: auto auto minmax(0, 1fr);
  }
  .sheet-layout {
    min-height: 0;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: 8px;
  }
  .variant-a .secondary-grid {
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
  }
  .variant-a .panel-head { height: 25px; }
  .variant-a .mini-head > div,
  .variant-a .mini-row > div { height: 23px; }
  .console-layout {
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1.55fr) minmax(360px, .85fr);
    gap: 8px;
  }
  .left-stack, .right-stack {
    min-height: 0;
    display: grid;
    gap: 6px;
    align-content: start;
  }
  .left-stack { grid-template-rows: auto auto; }
  .right-stack {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-content: start;
  }
  .variant-b .panel-head { background: #ecf7f4; }
  .responsive-layout {
    min-height: 0;
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr);
    gap: 7px;
  }
  .responsive-secondary {
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
  }
  .variant-c .panel {
    border-radius: 5px;
  }
  .variant-c .panel-head {
    height: 24px;
  }
  .variant-c .matrix-head,
  .variant-c .matrix-row {
    grid-template-columns: 28px 38px 46px repeat(3, minmax(120px, 1fr));
  }
  .variant-c .mini-head > div,
  .variant-c .mini-row > div {
    height: 23px;
  }
  .variant-d {
    grid-template-rows: auto auto auto minmax(0, 1fr);
  }
  .workbench-secondary {
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
    align-content: start;
  }
  .variant-d .topbar {
    min-height: 40px;
    border-radius: 3px;
  }
  .variant-d .panel {
    border-radius: 3px;
  }
  .variant-d .panel-head {
    height: 23px;
    border-left: 3px solid var(--green);
  }
  .variant-d .grass-matrix {
    grid-template-rows: 22px repeat(6, 25px);
  }
  .variant-d .mini-head > div,
  .variant-d .mini-row > div {
    height: 22px;
  }
  .split-grass {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0;
  }
  .split-grass .grass-matrix:first-child {
    border-right: 1px solid var(--line);
  }
  .split-grass .matrix-head,
  .split-grass .matrix-row {
    grid-template-columns: 26px 36px 42px repeat(3, minmax(88px, 1fr));
  }
  @media (max-width: 760px) {
    .preview {
      height: auto;
      min-height: 100vh;
      overflow: auto;
      padding: 6px;
    }
    .topbar {
      min-height: 40px;
      padding: 6px;
    }
    h1 { font-size: 14px; }
    h1 span { font-size: 16px; }
    .rate-strip {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .sheet-layout,
    .console-layout,
    .responsive-layout,
    .workbench { display: block; }
    .secondary-grid,
    .right-stack,
    .responsive-secondary,
    .workbench-secondary {
      grid-template-columns: 1fr 1fr;
    }
    .grass-panel {
      overflow-x: auto;
    }
    .grass-matrix {
      min-width: 740px;
    }
  }
"""


def build_html(route: dict) -> str:
    variants = {
        "a": variant_a(route),
        "b": variant_b(route),
        "c": variant_c(route),
        "d": variant_d(route),
    }
    script = """
      const key = (location.hash || '#a').slice(1).toLowerCase();
      document.querySelectorAll('.preview').forEach((node, index) => {
        const id = ['a','b','c','d'][index];
        node.classList.toggle('active', id === key);
      });
    """
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Route 30 Compact Variants</title><style>"
        + CSS
        + "</style></head><body>"
        + "".join(variants.values())
        + "<script>"
        + script
        + "</script></body></html>"
    )


def main() -> int:
    raw = subprocess.check_output([sys.executable, str(VIEWER), "--json"], cwd=ROOT)
    data = json.loads(raw)
    route = next(route for route in data["routes"] if route["id"] == 3)
    OUT.write_text(build_html(route), encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
