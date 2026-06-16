#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().with_name("route30_zero_waste_variants.html")
VIEWER = ROOT / "scripts" / "overworld_behavior_profile_viewer.py"
ICON_ORIGIN = "http://127.0.0.1:8765"


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def short_species(species: dict) -> str:
    return str(species.get("symbol", species.get("name", ""))).removeprefix("SPECIES_")


def icon(species: dict) -> str:
    url = species.get("iconUrl")
    if not url:
        return '<span class="mon-icon"></span>'
    return f'<img class="mon-icon" src="{ICON_ORIGIN}{esc(url)}" alt="{esc(species.get("name", ""))}" loading="lazy">'


def badge(text: str, cls: str = "") -> str:
    return f'<span class="badge {esc(cls)}">{esc(text)}</span>'


def species_chip(species: dict, form: int = 0, levels: tuple[int, int] | None = None) -> str:
    level_html = ""
    if levels is not None:
        lo, hi = levels
        level_html = f'<span class="level">{esc(lo if lo == hi else f"{lo}-{hi}")}</span>'
    form_html = "" if not form else f'<span class="form">f{esc(form)}</span>'
    return (
        '<span class="mon-chip">'
        f'{icon(species)}'
        f'<span class="mon-name">{esc(short_species(species))}</span>'
        f'{form_html}{level_html}'
        "</span>"
    )


def empty_cell() -> str:
    return '<span class="empty-cell"></span>'


def table_by_key(route: dict, key: str) -> dict:
    for table in route["pokemonTables"] + route["slotTables"]:
        if table["key"] == key:
            return table
    raise KeyError(key)


def rate(route: dict, key: str) -> int:
    return next(item["value"] for item in route["rates"] if item["key"] == key)


def top(route: dict, label: str) -> str:
    maps = ", ".join(map_item["symbol"] for map_item in route["maps"])
    return (
        '<header class="top">'
        f'<strong>{esc(label)}</strong>'
        f'<span class="route-name">{esc(route["name"])}</span>'
        f'<span class="meta">Encounter #{esc(route["id"])} · {esc(maps)} · {esc(route["speciesCount"])} Pokemon</span>'
        '<span class="source">Source</span>'
        "</header>"
    )


def rates_inline(route: dict) -> str:
    rate_keys = [
        ("W", "walkrate", "grass"),
        ("~", "surfrate", "water"),
        ("R", "rocksmashrate", "rock"),
        ("1", "oldrodrate", "rod"),
        ("2", "goodrodrate", "rod"),
        ("3", "superrodrate", "rod"),
    ]
    return '<div class="rates-inline">' + "".join(
        f'<span class="rate-pill {cls}">{label}<b>{esc(rate(route, key))}</b></span>'
        for label, key, cls in rate_keys
    ) + "</div>"


def unified_matrix(route: dict) -> str:
    morning = table_by_key(route, "morning")
    day = table_by_key(route, "day")
    night = table_by_key(route, "night")
    surf = table_by_key(route, "surf")
    rock = table_by_key(route, "rockSmash")
    old = table_by_key(route, "oldRod")
    good = table_by_key(route, "goodRod")
    super_rod = table_by_key(route, "superRod")
    hoenn = table_by_key(route, "hoenn")
    sinnoh = table_by_key(route, "sinnoh")
    swarms = route["swarms"]
    head = (
        '<div class="mega-head">'
        '<div>#</div><div>%</div><div>Lv</div>'
        '<div>AM</div><div>Day</div><div>Night</div>'
        '<div>Surf</div><div>Old</div><div>Good</div><div>Super</div>'
        '<div>Rock</div><div>Sound</div><div>Swarm</div>'
        "</div>"
    )
    rows = []
    for idx in range(12):
        level = route["grassLevels"][idx]
        sound = []
        if idx < len(hoenn["slots"]):
            sound.append(species_chip(hoenn["slots"][idx]["species"], hoenn["slots"][idx]["form"]))
        if idx < len(sinnoh["slots"]):
            sound.append(species_chip(sinnoh["slots"][idx]["species"], sinnoh["slots"][idx]["form"]))
        swarm = []
        if idx < len(swarms):
            label = swarms[idx]["label"].replace(" swarm", "").replace("Good rod", "Good").replace("Super rod", "Super")
            swarm.append(badge(label, "mini-label") + species_chip(swarms[idx]["species"], swarms[idx]["form"]))

        def slot_cell(table: dict) -> str:
            if idx >= len(table["slots"]):
                return empty_cell()
            slot = table["slots"][idx]
            levels = None
            if "minLevel" in slot:
                levels = (slot["minLevel"], slot["maxLevel"])
            return species_chip(slot["species"], slot.get("form", 0), levels)

        row = [
            f'<div class="idx">{esc(level["slot"])}</div>',
            f'<div class="pct">{esc(level["weight"])}%</div>',
            f'<div>{badge(level["value"], "level-badge")}</div>',
            f'<div>{species_chip(morning["slots"][idx]["species"], morning["slots"][idx]["form"])}</div>',
            f'<div>{species_chip(day["slots"][idx]["species"], day["slots"][idx]["form"])}</div>',
            f'<div>{species_chip(night["slots"][idx]["species"], night["slots"][idx]["form"])}</div>',
            f'<div>{slot_cell(surf)}</div>',
            f'<div>{slot_cell(old)}</div>',
            f'<div>{slot_cell(good)}</div>',
            f'<div>{slot_cell(super_rod)}</div>',
            f'<div>{slot_cell(rock)}</div>',
            f'<div>{"".join(sound) or empty_cell()}</div>',
            f'<div>{"".join(swarm) or empty_cell()}</div>',
        ]
        rows.append('<div class="mega-row">' + "".join(row) + "</div>")
    return '<section class="mega-board">' + head + "".join(rows) + "</section>"


def variant_e(route: dict) -> str:
    return '<main class="preview variant-e">' + top(route, "E Unified Matrix") + rates_inline(route) + unified_matrix(route) + "</main>"


def lane_table(title: str, cells: list[str], cls: str = "") -> str:
    return f'<section class="lane {esc(cls)}"><div class="lane-title">{esc(title)}</div><div class="lane-cells">{"".join(cells)}</div></section>'


def lane_variant(route: dict) -> str:
    cells = []
    morning = table_by_key(route, "morning")
    day = table_by_key(route, "day")
    night = table_by_key(route, "night")
    for idx, level in enumerate(route["grassLevels"]):
        cells.append(
            '<div class="grass-mini">'
            f'<span class="slotline">{esc(level["slot"])} · {esc(level["weight"])}% · Lv {esc(level["value"])}</span>'
            f'{species_chip(morning["slots"][idx]["species"], morning["slots"][idx]["form"])}'
            f'{species_chip(day["slots"][idx]["species"], day["slots"][idx]["form"])}'
            f'{species_chip(night["slots"][idx]["species"], night["slots"][idx]["form"])}'
            "</div>"
        )
    grass = lane_table("Grass 12 slots", cells, "grass-lane")

    lanes = [grass]
    for key in ["surf", "oldRod", "goodRod", "superRod", "rockSmash"]:
        table = table_by_key(route, key)
        row = []
        for slot in table["slots"]:
            levels = (slot["minLevel"], slot["maxLevel"])
            row.append(
                '<div class="mini-slot">'
                f'<span class="slotline">{esc(slot["slot"])} · {esc(slot["weight"])}%</span>'
                f'{species_chip(slot["species"], slot["form"], levels)}'
                "</div>"
            )
        lanes.append(lane_table(table["label"], row))
    sound_cells = []
    for key in ["hoenn", "sinnoh"]:
        table = table_by_key(route, key)
        for slot in table["slots"]:
            sound_cells.append(
                '<div class="mini-slot">'
                f'<span class="slotline">{esc(table["label"].split()[0])} {esc(slot["slot"])} · {esc(slot["weight"])}%</span>'
                f'{species_chip(slot["species"], slot["form"])}'
                "</div>"
            )
    lanes.append(lane_table("Sound", sound_cells, "low-lane"))
    swarm_cells = [
        '<div class="mini-slot">'
        f'<span class="slotline">{esc(swarm["label"].replace(" swarm", ""))}</span>'
        f'{species_chip(swarm["species"], swarm["form"])}'
        "</div>"
        for swarm in route["swarms"]
    ]
    lanes.append(lane_table("Swarms", swarm_cells, "low-lane"))
    return '<main class="preview variant-f">' + top(route, "F Type Lanes") + rates_inline(route) + '<section class="lanes">' + "".join(lanes) + "</section></main>"


def species_pivot(route: dict) -> str:
    seen: dict[str, dict] = {}
    hits: dict[str, list[str]] = defaultdict(list)

    def add(species: dict, text: str) -> None:
        if species["symbol"] == "SPECIES_NONE":
            return
        seen[species["symbol"]] = species
        hits[species["symbol"]].append(text)

    for key, label in [("morning", "AM"), ("day", "Day"), ("night", "Night"), ("hoenn", "Hoenn"), ("sinnoh", "Sinnoh")]:
        table = table_by_key(route, key)
        for slot in table["slots"]:
            add(slot["species"], f'{label} {slot["slot"]}:{slot["weight"]}%')
    for table in route["slotTables"]:
        for slot in table["slots"]:
            add(slot["species"], f'{table["label"]} {slot["slot"]}:{slot["weight"]}% L{slot["minLevel"]}-{slot["maxLevel"]}')
    for swarm in route["swarms"]:
        add(swarm["species"], swarm["label"].replace(" swarm", ""))

    species_rows = []
    for symbol, species in sorted(seen.items(), key=lambda item: item[1]["value"]):
        species_rows.append(
            '<div class="species-row">'
            f'<div>{species_chip(species)}</div>'
            f'<div>{"".join(badge(hit) for hit in hits[symbol])}</div>'
            "</div>"
        )
    return '<section class="pivot">' + "".join(species_rows) + "</section>"


def variant_g(route: dict) -> str:
    return (
        '<main class="preview variant-g">'
        + top(route, "G Slot Board + Species Pivot")
        + rates_inline(route)
        + '<section class="hybrid">'
        + unified_matrix(route)
        + species_pivot(route)
        + "</section></main>"
    )


CSS = r"""
  :root {
    --bg: #eef2f6;
    --panel: #fff;
    --line: #cad4e3;
    --soft: #e6edf5;
    --ink: #17202c;
    --muted: #60708a;
    --green: #0b7b68;
    --water: #0b6ea8;
    --gold: #9a650f;
    --violet: #5b32c8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font: 11px/1.15 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .preview {
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    padding: 7px;
    display: grid;
    gap: 5px;
    grid-template-rows: 32px 28px minmax(0, 1fr);
  }
  .preview:not(.active) { display: none; }
  .top {
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 8px;
    min-width: 0;
    padding: 4px 8px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 5px;
  }
  .top strong { font-size: 13px; }
  .route-name { font-size: 18px; font-weight: 900; }
  .meta {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--muted);
    font-weight: 700;
  }
  .source {
    color: #0d5b52;
    background: #d8f3ed;
    border-radius: 999px;
    padding: 4px 8px;
    font-weight: 900;
  }
  .rates-inline {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 5px;
  }
  .rate-pill {
    display: grid;
    grid-template-columns: 24px 1fr;
    align-items: center;
    gap: 5px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 5px;
    padding: 3px 5px;
    color: var(--muted);
    font-weight: 900;
  }
  .rate-pill b {
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 0 6px;
    background: #fff;
    font: 900 11px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .mega-board {
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-rows: 23px repeat(12, minmax(38px, 1fr));
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 5px;
    overflow: hidden;
  }
  .mega-head,
  .mega-row {
    display: grid;
    grid-template-columns: 25px 37px 38px repeat(3, minmax(118px, 1.05fr)) repeat(4, minmax(96px, .9fr)) minmax(78px, .72fr) minmax(126px, 1fr) minmax(126px, 1fr);
    min-width: 0;
  }
  .mega-head > div,
  .mega-row > div {
    min-width: 0;
    border-right: 1px solid var(--soft);
    border-bottom: 1px solid var(--soft);
    padding: 2px 4px;
    display: flex;
    align-items: center;
    gap: 3px;
    overflow: hidden;
  }
  .mega-head > div {
    background: #f8fbff;
    color: var(--muted);
    text-transform: uppercase;
    font-weight: 950;
    letter-spacing: .02em;
  }
  .mega-row:hover > div { background: #f7fffc; }
  .idx, .pct { justify-content: center; font-weight: 900; color: var(--muted); }
  .pct { color: var(--green); }
  .badge, .level-badge {
    min-width: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 18px;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: #f8fafc;
    color: var(--muted);
    padding: 0 5px;
    font: 900 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    white-space: nowrap;
  }
  .mini-label {
    font-size: 9px;
    width: 38px;
    padding: 0 2px;
    text-transform: uppercase;
  }
  .mon-chip {
    min-width: 0;
    width: 100%;
    display: grid;
    grid-template-columns: 20px minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 3px;
  }
  .mon-icon {
    width: 20px;
    height: 20px;
    object-fit: contain;
    image-rendering: pixelated;
  }
  .mon-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: clip;
    white-space: nowrap;
    border: 1px solid var(--line);
    border-radius: 4px;
    height: 21px;
    display: flex;
    align-items: center;
    padding: 0 5px;
    background: #fff;
    font: 950 11px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .form, .level {
    min-width: 24px;
    height: 20px;
    border: 1px solid var(--line);
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font: 900 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #fff;
  }
  .level { min-width: 34px; color: var(--water); }
  .empty-cell {
    width: 100%;
    height: 18px;
    border-radius: 4px;
    background: repeating-linear-gradient(90deg, transparent, transparent 5px, #eef2f7 5px, #eef2f7 6px);
    opacity: .65;
  }
  .variant-f {
    grid-template-rows: 32px 28px minmax(0, 1fr);
  }
  .lanes {
    min-height: 0;
    display: grid;
    grid-template-rows: minmax(278px, .46fr) repeat(2, minmax(84px, .13fr)) repeat(3, minmax(68px, .1fr));
    gap: 5px;
  }
  .lane {
    min-width: 0;
    display: grid;
    grid-template-columns: 76px minmax(0, 1fr);
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 5px;
    overflow: hidden;
  }
  .lane-title {
    display: flex;
    align-items: center;
    padding: 5px;
    background: #f8fbff;
    color: var(--muted);
    font-weight: 950;
    text-transform: uppercase;
    border-right: 1px solid var(--line);
  }
  .lane-cells {
    min-width: 0;
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    align-content: stretch;
  }
  .grass-lane .lane-cells {
    grid-template-columns: repeat(6, minmax(0, 1fr));
    grid-template-rows: repeat(2, minmax(0, 1fr));
  }
  .mini-slot,
  .grass-mini {
    min-width: 0;
    border-right: 1px solid var(--soft);
    border-bottom: 1px solid var(--soft);
    padding: 3px;
    display: grid;
    gap: 2px;
    align-content: center;
  }
  .grass-mini {
    grid-template-rows: auto repeat(3, 21px);
  }
  .slotline {
    color: var(--muted);
    font-weight: 900;
    font-size: 10px;
  }
  .variant-g {
    grid-template-rows: 32px 28px minmax(0, 1fr);
  }
  .hybrid {
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1.95fr) minmax(320px, .75fr);
    gap: 5px;
  }
  .hybrid .mega-head,
  .hybrid .mega-row {
    grid-template-columns: 22px 32px 34px repeat(3, minmax(88px, 1fr)) repeat(4, minmax(72px, .85fr)) minmax(58px, .62fr) minmax(82px, .7fr) minmax(82px, .7fr);
  }
  .hybrid .mon-name { font-size: 10px; padding: 0 3px; }
  .hybrid .level { display: none; }
  .pivot {
    min-height: 0;
    overflow: hidden;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 5px;
    display: grid;
    grid-auto-rows: minmax(31px, 1fr);
  }
  .species-row {
    min-width: 0;
    display: grid;
    grid-template-columns: 120px minmax(0, 1fr);
    gap: 4px;
    align-items: center;
    padding: 3px 4px;
    border-bottom: 1px solid var(--soft);
  }
  .species-row > div:last-child {
    min-width: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
    overflow: hidden;
    max-height: 28px;
  }
  @media (max-width: 760px) {
    .preview {
      height: auto;
      min-height: 100vh;
      overflow: auto;
      padding: 5px;
      grid-template-rows: auto auto auto;
    }
    .top {
      grid-template-columns: auto minmax(0, 1fr) auto;
    }
    .top strong { display: none; }
    .route-name { font-size: 16px; }
    .meta { grid-column: 1 / -1; }
    .rates-inline { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .mega-board {
      overflow-x: auto;
      grid-template-rows: 23px repeat(12, 38px);
    }
    .mega-head,
    .mega-row {
      min-width: 1120px;
    }
    .lanes {
      grid-template-rows: auto;
    }
    .lane {
      grid-template-columns: 1fr;
    }
    .lane-title {
      min-height: 24px;
      border-right: 0;
      border-bottom: 1px solid var(--line);
    }
    .lane-cells,
    .grass-lane .lane-cells {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      grid-template-rows: auto;
    }
    .hybrid {
      grid-template-columns: 1fr;
    }
    .pivot {
      grid-auto-rows: minmax(30px, auto);
    }
  }
"""


def build_html(route: dict) -> str:
    variants = [variant_e(route), lane_variant(route), variant_g(route)]
    script = """
      const key = (location.hash || '#e').slice(1).toLowerCase();
      document.querySelectorAll('.preview').forEach((node, index) => {
        const id = ['e','f','g'][index];
        node.classList.toggle('active', id === key);
      });
    """
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Route 30 Zero Waste Variants</title><style>'
        + CSS
        + '</style></head><body>'
        + "".join(variants)
        + '<script>'
        + script
        + '</script></body></html>'
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
