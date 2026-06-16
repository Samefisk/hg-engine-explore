#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().with_name("route30_ultra_dense_variants.html")
VIEWER = ROOT / "scripts" / "overworld_behavior_profile_viewer.py"
ICON_ORIGIN = "http://127.0.0.1:8765"


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def table_by_key(route: dict, key: str) -> dict:
    for table in route["pokemonTables"] + route["slotTables"]:
        if table["key"] == key:
            return table
    raise KeyError(key)


def rate_by_key(route: dict, key: str) -> int:
    return next(rate["value"] for rate in route["rates"] if rate["key"] == key)


def short_species(species: dict) -> str:
    return str(species.get("symbol", species.get("name", ""))).removeprefix("SPECIES_")


def mon_icon(species: dict) -> str:
    url = species.get("iconUrl")
    if not url:
        return '<span class="mon-icon"></span>'
    return f'<img class="mon-icon" src="{ICON_ORIGIN}{esc(url)}" alt="{esc(species.get("name", ""))}" loading="lazy">'


def method_icon(kind: str, label: str) -> str:
    text = {
        "grass": "G",
        "am": "AM",
        "day": "D",
        "night": "N",
        "surf": "~",
        "old": "1",
        "good": "2",
        "super": "3",
        "rock": "R",
        "hoenn": "H",
        "sinnoh": "S",
        "sound": "H/S",
        "swarm": "!",
    }[kind]
    return f'<span class="method-icon {esc(kind)}" title="{esc(label)}">{esc(text)}</span>'


def value_box(value, cls: str = "") -> str:
    return f'<span class="value-box {esc(cls)}">{esc(value)}</span>'


def mon_cell(species: dict, form: int = 0, level: str | int | None = None, tiny: bool = False) -> str:
    if species.get("symbol") == "SPECIES_NONE":
        name = '<span class="mon-name none">NONE</span>'
    else:
        name = f'<span class="mon-name">{esc(short_species(species))}</span>'
    form_html = "" if not form else f'<span class="mini-pill">f{esc(form)}</span>'
    level_html = "" if level in (None, "", 0, "0") else f'<span class="mini-pill level-pill">L{esc(level)}</span>'
    cls = "mon-cell tiny" if tiny else "mon-cell"
    return f'<span class="{cls}">{mon_icon(species)}{name}{form_html}{level_html}</span>'


def empty() -> str:
    return '<span class="empty"></span>'


def level_range(slot: dict) -> str:
    low = slot.get("minLevel", "")
    high = slot.get("maxLevel", "")
    if low == high:
        return esc(low)
    return f'{esc(low)}-{esc(high)}'


def topbar(route: dict, title: str) -> str:
    maps = ", ".join(map_item["symbol"] for map_item in route["maps"])
    rates = [
        ("grass", "walking", "walkrate"),
        ("surf", "surf", "surfrate"),
        ("rock", "rock smash", "rocksmashrate"),
        ("old", "old rod", "oldrodrate"),
        ("good", "good rod", "goodrodrate"),
        ("super", "super rod", "superrodrate"),
    ]
    rate_html = "".join(
        f'<span class="top-rate">{method_icon(kind, label)}{value_box(rate_by_key(route, key), "rate-value")}</span>'
        for kind, label, key in rates
    )
    return (
        '<header class="topbar">'
        f'<strong>{esc(title)}</strong>'
        f'<span class="route-name">{esc(route["name"])}</span>'
        f'<span class="route-meta">#{esc(route["id"])} {esc(maps)} {esc(route["speciesCount"])} Pokemon</span>'
        f'<span class="rates">{rate_html}</span>'
        '<span class="source">Source</span>'
        "</header>"
    )


def section(title: str, icon_kind: str, body: str, cls: str = "") -> str:
    return (
        f'<section class="section {esc(cls)}">'
        f'<div class="section-head">{method_icon(icon_kind, title)}<strong>{esc(title)}</strong></div>'
        f'{body}</section>'
    )


def grass_rows(route: dict) -> str:
    morning = table_by_key(route, "morning")
    day = table_by_key(route, "day")
    night = table_by_key(route, "night")
    rows = [
        '<div class="grass-head">'
        '<span>#</span><span>%</span><span>Lv</span>'
        f'<span>{method_icon("am", "morning")}</span>'
        f'<span>{method_icon("day", "day")}</span>'
        f'<span>{method_icon("night", "night")}</span>'
        "</div>"
    ]
    for idx, level in enumerate(route["grassLevels"]):
        rows.append(
            '<div class="grass-row">'
            f'{value_box(level["slot"], "slot")}'
            f'{value_box(str(level["weight"]) + "%", "pct")}'
            f'{value_box(level["value"], "level")}'
            f'{mon_cell(morning["slots"][idx]["species"], morning["slots"][idx]["form"])}'
            f'{mon_cell(day["slots"][idx]["species"], day["slots"][idx]["form"])}'
            f'{mon_cell(night["slots"][idx]["species"], night["slots"][idx]["form"])}'
            "</div>"
        )
    return '<div class="grass-ledger">' + "".join(rows) + "</div>"


def collect_species_hits(route: dict) -> list[tuple[dict, list[str]]]:
    seen: dict[str, dict] = {}
    hits: dict[str, list[str]] = defaultdict(list)

    def add(species: dict, label: str) -> None:
        if species.get("symbol") == "SPECIES_NONE":
            return
        symbol = species["symbol"]
        seen[symbol] = species
        hits[symbol].append(label)

    for key, label in [("morning", "AM"), ("day", "D"), ("night", "N"), ("hoenn", "H"), ("sinnoh", "S")]:
        table = table_by_key(route, key)
        for slot in table["slots"]:
            add(slot["species"], f'{label}{slot["slot"]}:{slot["weight"]}')
    for table in route["slotTables"]:
        prefix = {"surf": "~", "oldRod": "1", "goodRod": "2", "superRod": "3", "rockSmash": "R"}[table["key"]]
        for slot in table["slots"]:
            add(slot["species"], f'{prefix}{slot["slot"]}:{slot["weight"]} L{level_range(slot)}')
    for swarm in route["swarms"]:
        label = swarm["label"].replace(" swarm", "").replace("Good rod", "Gd").replace("Super rod", "Sp")
        add(swarm["species"], label)

    return sorted(((species, hits[symbol]) for symbol, species in seen.items()), key=lambda item: item[0]["value"])


def species_strip(route: dict) -> str:
    rows = []
    for species, hits in collect_species_hits(route):
        rows.append(
            '<div class="species-hit">'
            f'{mon_cell(species, tiny=True)}'
            f'<span class="hit-list">{"".join(value_box(hit, "hit") for hit in hits[:8])}</span>'
            "</div>"
        )
    return section("Species coverage", "grass", '<div class="species-strip">' + "".join(rows) + "</div>", "coverage")


def slot_table(table: dict, icon_kind: str, include_levels: bool = True) -> str:
    rows = [
        '<div class="method-row method-head">'
        '<span>#</span><span>%</span><span>Pokemon</span>'
        + ("<span>Lv</span>" if include_levels else "<span></span>")
        + "</div>"
    ]
    for slot in table["slots"]:
        rows.append(
            '<div class="method-row">'
            f'{value_box(slot["slot"], "slot")}'
            f'{value_box(str(slot["weight"]) + "%", "pct")}'
            f'{mon_cell(slot["species"], slot.get("form", 0), tiny=True)}'
            f'{value_box(level_range(slot), "level") if include_levels else ""}'
            "</div>"
        )
    return section(table["label"], icon_kind, '<div class="method-table">' + "".join(rows) + "</div>")


def sound_table(route: dict) -> str:
    rows = []
    for key, icon_kind in [("hoenn", "hoenn"), ("sinnoh", "sinnoh")]:
        table = table_by_key(route, key)
        for slot in table["slots"]:
            rows.append(
                '<div class="method-row">'
                f'{method_icon(icon_kind, table["label"])}'
                f'{value_box(str(slot["weight"]) + "%", "pct")}'
                f'{mon_cell(slot["species"], slot.get("form", 0), tiny=True)}'
                "</div>"
            )
    return section("Radio", "sound", '<div class="method-table no-levels">' + "".join(rows) + "</div>")


def swarm_table(route: dict) -> str:
    rows = []
    for swarm in route["swarms"]:
        label = swarm["label"].replace(" swarm", "").replace("Good rod", "Good").replace("Super rod", "Super")
        rows.append(
            '<div class="method-row">'
            f'{value_box(label, "swarm-label")}'
            '<span></span>'
            f'{mon_cell(swarm["species"], swarm.get("form", 0), tiny=True)}'
            "</div>"
        )
    return section("Swarms", "swarm", '<div class="method-table no-levels">' + "".join(rows) + "</div>")


def method_stack(route: dict) -> str:
    parts = [
        slot_table(table_by_key(route, "surf"), "surf"),
        slot_table(table_by_key(route, "oldRod"), "old"),
        slot_table(table_by_key(route, "goodRod"), "good"),
        slot_table(table_by_key(route, "superRod"), "super"),
        slot_table(table_by_key(route, "rockSmash"), "rock"),
        sound_table(route),
        swarm_table(route),
    ]
    return '<div class="method-stack">' + "".join(parts) + "</div>"


def variant_h(route: dict) -> str:
    return (
        '<main class="preview variant-h">'
        + topbar(route, "H Slot Ledger")
        + '<div class="body slot-ledger">'
        + '<div class="left-stack">'
        + section("Grass", "grass", grass_rows(route), "grass-section")
        + species_strip(route)
        + "</div>"
        + method_stack(route)
        + "</div></main>"
    )


def sheet_group_rows(route: dict, key: str, group: str, icon_kind: str) -> str:
    table = table_by_key(route, key)
    rows = []
    for slot in table["slots"]:
        rows.append(
            '<div class="sheet-row non-grass-row">'
            f'<span class="type-cell">{method_icon(icon_kind, group)}<b>{esc(group)}</b></span>'
            f'{value_box(slot["slot"], "slot")}'
            f'{value_box(str(slot["weight"]) + "%", "pct")}'
            f'{value_box(level_range(slot), "level")}'
            f'{mon_cell(slot["species"], slot.get("form", 0), tiny=True)}'
            "</div>"
        )
    return "".join(rows)


def variant_i(route: dict) -> str:
    return (
        '<main class="preview variant-i">'
        + topbar(route, "I Wall Board")
        + '<div class="body wall-board">'
        + section("Grass", "grass", grass_rows(route), "grass-section")
        + species_strip(route)
        + slot_table(table_by_key(route, "surf"), "surf")
        + slot_table(table_by_key(route, "oldRod"), "old")
        + slot_table(table_by_key(route, "goodRod"), "good")
        + slot_table(table_by_key(route, "superRod"), "super")
        + slot_table(table_by_key(route, "rockSmash"), "rock")
        + sound_table(route)
        + swarm_table(route)
        + "</div></main>"
    )


def hit_for_species(route: dict, species_symbol: str, source_key: str) -> list[str]:
    hits = []
    if source_key in {"morning", "day", "night", "hoenn", "sinnoh"}:
        table = table_by_key(route, source_key)
        for slot in table["slots"]:
            if slot["species"]["symbol"] == species_symbol:
                hits.append(f'{slot["slot"]}:{slot["weight"]}')
    elif source_key == "swarms":
        for swarm in route["swarms"]:
            if swarm["species"]["symbol"] == species_symbol:
                label = swarm["label"].replace(" swarm", "").replace("Good rod", "Good").replace("Super rod", "Super")
                hits.append(label)
    else:
        table = table_by_key(route, source_key)
        for slot in table["slots"]:
            if slot["species"]["symbol"] == species_symbol:
                hits.append(f'{slot["slot"]}:{slot["weight"]} L{level_range(slot)}')
    return hits


def variant_j(route: dict) -> str:
    columns = [
        ("morning", "am", "AM"),
        ("day", "day", "Day"),
        ("night", "night", "Night"),
        ("surf", "surf", "Surf"),
        ("oldRod", "old", "Old"),
        ("goodRod", "good", "Good"),
        ("superRod", "super", "Super"),
        ("rockSmash", "rock", "Rock"),
        ("hoenn", "hoenn", "Hoenn"),
        ("sinnoh", "sinnoh", "Sinnoh"),
        ("swarms", "swarm", "Swarm"),
    ]
    rows = [
        '<div class="pivot-head"><span>Pokemon</span>'
        + "".join(f'<span>{method_icon(kind, label)}</span>' for _key, kind, label in columns)
        + "</div>"
    ]
    for species, _hits in collect_species_hits(route):
        cells = []
        for key, _kind, _label in columns:
            source_hits = hit_for_species(route, species["symbol"], key)
            cells.append(
                '<span class="pivot-cell">'
                + ("".join(value_box(hit, "hit") for hit in source_hits) if source_hits else "")
                + "</span>"
            )
        rows.append(
            '<div class="pivot-row">'
            f'{mon_cell(species)}'
            + "".join(cells)
            + "</div>"
        )
    return (
        '<main class="preview variant-j">'
        + topbar(route, "J Species Matrix")
        + '<div class="body pivot-layout">'
        + '<section class="species-matrix">' + "".join(rows) + "</section>"
        + '<div class="bottom-ledgers">'
        + section("Grass", "grass", grass_rows(route), "grass-section")
        + method_stack(route)
        + "</div></div></main>"
    )


CSS = r"""
  :root {
    --bg: #eef2f6;
    --panel: #fff;
    --line: #cbd6e5;
    --soft: #e5ebf4;
    --ink: #151c27;
    --muted: #5f6f89;
    --grass: #0a7d54;
    --water: #0876b5;
    --rod: #94600e;
    --rock: #6b665d;
    --sound: #6241c7;
    --swarm: #c93668;
  }
  * { box-sizing: border-box; min-width: 0; }
  html,
  body {
    inline-size: 100%;
    block-size: 100%;
    margin: 0;
    overflow: hidden;
    background: var(--bg);
    color: var(--ink);
    font: 11px/1.15 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .preview {
    inline-size: 100%;
    max-inline-size: 100%;
    block-size: 100dvh;
    padding: 5px;
    overflow: clip;
    display: none;
    grid-template-rows: 31px minmax(0, 1fr);
    gap: 5px;
  }
  .preview.active { display: grid; }
  .topbar {
    min-height: 0;
    display: grid;
    grid-template-columns: auto auto auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 7px;
    padding: 3px 6px;
    border: 1px solid var(--line);
    border-radius: 5px;
    background: var(--panel);
    overflow: hidden;
  }
  .topbar strong {
    color: var(--muted);
    font-weight: 950;
    white-space: nowrap;
  }
  .route-name {
    font-size: 18px;
    font-weight: 950;
    white-space: nowrap;
  }
  .route-meta {
    color: var(--muted);
    font-weight: 800;
    white-space: nowrap;
  }
  .rates {
    display: flex;
    justify-content: flex-end;
    gap: 3px;
    overflow: hidden;
  }
  .top-rate {
    display: inline-grid;
    grid-template-columns: 21px 34px;
    align-items: center;
    gap: 2px;
  }
  .source {
    height: 22px;
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    background: #d9f4ee;
    color: #0b5b50;
    padding: 0 8px;
    font-weight: 950;
  }
  .body {
    min-height: 0;
    overflow: clip;
  }
  .slot-ledger {
    display: grid;
    grid-template-columns: minmax(0, 1.52fr) minmax(370px, .78fr);
    gap: 5px;
  }
  .left-stack {
    min-height: 0;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: 5px;
  }
  .section {
    min-height: 0;
    display: grid;
    grid-template-rows: 24px minmax(0, 1fr);
    border: 1px solid var(--line);
    border-radius: 5px;
    background: var(--panel);
    overflow: hidden;
  }
  .section-head {
    min-height: 0;
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 2px 5px;
    border-bottom: 1px solid var(--line);
    background: #f8fbff;
    color: var(--muted);
    text-transform: uppercase;
    font-weight: 950;
    letter-spacing: .02em;
  }
  .section-head strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .method-icon {
    width: 21px;
    height: 20px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    border: 1px solid var(--line);
    background: #fff;
    font: 950 9px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--muted);
    flex: 0 0 auto;
  }
  .method-icon.grass,
  .method-icon.am,
  .method-icon.day,
  .method-icon.night { color: var(--grass); background: #effbf4; border-color: #a7d8c0; }
  .method-icon.surf { color: var(--water); background: #edf8ff; border-color: #add8f2; }
  .method-icon.old,
  .method-icon.good,
  .method-icon.super { color: var(--rod); background: #fff7e9; border-color: #ebcd9a; }
  .method-icon.rock { color: var(--rock); background: #f7f5f0; border-color: #d9d2c5; }
  .method-icon.hoenn,
  .method-icon.sinnoh,
  .method-icon.sound { color: var(--sound); background: #f4f1ff; border-color: #c9bcff; }
  .method-icon.swarm { color: var(--swarm); background: #fff0f6; border-color: #f2b4cf; }
  .value-box {
    height: 20px;
    min-width: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: #fff;
    padding: 0 4px;
    color: var(--muted);
    font: 950 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    white-space: nowrap;
  }
  .rate-value,
  .slot,
  .level { color: var(--ink); }
  .pct { color: var(--grass); }
  .grass-ledger,
  .grass-head,
  .grass-row {
    min-width: 0;
  }
  .grass-ledger {
    display: grid;
    grid-template-rows: 22px repeat(12, 32px);
    align-content: start;
  }
  .grass-head,
  .grass-row {
    display: grid;
    grid-template-columns: 28px 38px 36px repeat(3, minmax(0, 1fr));
  }
  .grass-head > span,
  .grass-row > span {
    min-width: 0;
    border-right: 1px solid var(--soft);
    border-bottom: 1px solid var(--soft);
    padding: 2px 4px;
    display: flex;
    align-items: center;
    overflow: hidden;
  }
  .grass-head > span {
    color: var(--muted);
    background: #f8fbff;
    font-weight: 950;
    text-transform: uppercase;
  }
  .grass-row:hover > span,
  .sheet-row:hover > span,
  .method-row:hover > span,
  .pivot-row:hover > span { background: #f8fffc; }
  .mon-cell {
    width: 100%;
    min-width: 0;
    display: grid;
    grid-template-columns: 19px minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 3px;
  }
  .mon-cell.tiny {
    grid-template-columns: 18px minmax(0, 1fr) auto auto;
    gap: 2px;
  }
  .mon-icon {
    width: 19px;
    height: 19px;
    object-fit: contain;
    image-rendering: pixelated;
  }
  .tiny .mon-icon {
    width: 18px;
    height: 18px;
  }
  .mon-name {
    height: 20px;
    min-width: 0;
    display: flex;
    align-items: center;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: #fff;
    padding: 0 5px;
    font: 950 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .mon-name.none {
    color: #8b98aa;
    background: #f7f9fc;
  }
  .mini-pill {
    height: 18px;
    min-width: 20px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: #fff;
    color: var(--muted);
    font: 950 9px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .method-stack {
    min-height: 0;
    display: grid;
    grid-template-rows: repeat(4, minmax(94px, .96fr)) minmax(58px, .58fr) minmax(74px, .74fr) minmax(82px, .82fr);
    gap: 5px;
  }
  .method-table {
    display: grid;
    grid-auto-rows: 21px;
    align-content: start;
  }
  .method-row {
    display: grid;
    grid-template-columns: 28px 42px minmax(0, 1fr) 47px;
    align-items: center;
    min-width: 0;
  }
  .method-table.no-levels .method-row {
    grid-template-columns: 45px 42px minmax(0, 1fr);
  }
  .method-row > span {
    min-height: 21px;
    min-width: 0;
    padding: 1px 3px;
    border-right: 1px solid var(--soft);
    border-bottom: 1px solid var(--soft);
    display: flex;
    align-items: center;
    overflow: hidden;
  }
  .method-head > span {
    color: var(--muted);
    background: #fbfdff;
    font-weight: 950;
    text-transform: uppercase;
  }
  .swarm-label {
    width: 100%;
    justify-content: flex-start;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .coverage {
    grid-template-rows: 24px auto;
  }
  .species-strip {
    min-height: 0;
    padding: 4px;
    display: grid;
    grid-template-columns: 1fr;
    grid-auto-rows: minmax(24px, 1fr);
    gap: 3px 5px;
    overflow: hidden;
  }
  .species-hit {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(92px, .55fr) minmax(0, 1fr);
    gap: 3px;
    align-items: center;
    border: 1px solid var(--soft);
    border-radius: 4px;
    padding: 2px;
    background: #fff;
  }
  .hit-list {
    min-width: 0;
    display: flex;
    gap: 2px;
    overflow: hidden;
  }
  .hit {
    height: 18px;
    font-size: 9px;
    padding: 0 3px;
  }
  .single-sheet {
    min-height: 0;
    display: grid;
    grid-template-rows: 20px repeat(42, minmax(0, 1fr));
    border: 1px solid var(--line);
    border-radius: 5px;
    background: var(--panel);
    overflow: hidden;
  }
  .wall-board {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    grid-template-rows: minmax(420px, .54fr) minmax(0, .23fr) minmax(0, .23fr);
    gap: 5px;
  }
  .wall-board .grass-section {
    grid-column: 1 / 4;
    grid-row: 1;
  }
  .wall-board .coverage {
    grid-column: 4;
    grid-row: 1;
  }
  .wall-board .species-strip {
    grid-template-columns: 1fr;
  }
  .wall-board .method-table {
    block-size: 100%;
    grid-auto-rows: minmax(19px, 1fr);
  }
  .sheet-head,
  .sheet-row {
    display: grid;
    grid-template-columns: 72px 28px 38px 46px repeat(3, minmax(0, 1fr)) minmax(0, 1.12fr);
    align-items: center;
  }
  .sheet-row.grass-sheet-row {
    grid-template-columns: 72px 28px 38px 46px repeat(3, minmax(0, 1fr));
  }
  .sheet-row.non-grass-row {
    grid-template-columns: 72px 28px 38px 46px minmax(0, 1fr);
  }
  .sheet-head > span,
  .sheet-row > span {
    min-height: 0;
    height: 100%;
    min-width: 0;
    padding: 0 3px;
    border-right: 1px solid var(--soft);
    border-bottom: 1px solid var(--soft);
    display: flex;
    align-items: center;
    overflow: hidden;
  }
  .sheet-head > span {
    background: #f8fbff;
    color: var(--muted);
    font-weight: 950;
    text-transform: uppercase;
  }
  .variant-i .method-icon {
    width: 18px;
    height: 16px;
    font-size: 8px;
    border-radius: 3px;
  }
  .variant-i .value-box {
    height: 16px;
    font-size: 9px;
    border-radius: 3px;
  }
  .variant-i .mon-cell.tiny {
    grid-template-columns: 15px minmax(0, 1fr) auto auto;
  }
  .variant-i .mon-icon {
    width: 15px;
    height: 15px;
  }
  .variant-i .mon-name {
    height: 16px;
    font-size: 9px;
    border-radius: 3px;
    padding: 0 4px;
  }
  .type-cell {
    gap: 3px;
    color: var(--muted);
    font-weight: 950;
  }
  .type-cell b {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .empty {
    inline-size: 100%;
    block-size: 14px;
    opacity: .55;
    background: repeating-linear-gradient(90deg, transparent, transparent 6px, #eef2f7 6px, #eef2f7 7px);
    border-radius: 3px;
  }
  .pivot-layout {
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: 5px;
  }
  .species-matrix {
    min-height: 0;
    display: grid;
    grid-template-rows: 24px;
    grid-auto-rows: 27px;
    border: 1px solid var(--line);
    border-radius: 5px;
    background: var(--panel);
    overflow: hidden;
  }
  .pivot-head,
  .pivot-row {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(130px, .85fr) repeat(11, minmax(0, 1fr));
  }
  .pivot-head > span,
  .pivot-row > span {
    min-width: 0;
    border-right: 1px solid var(--soft);
    border-bottom: 1px solid var(--soft);
    padding: 2px 3px;
    display: flex;
    align-items: center;
    overflow: hidden;
  }
  .pivot-head > span {
    background: #f8fbff;
    color: var(--muted);
    font-weight: 950;
    text-transform: uppercase;
  }
  .pivot-cell {
    gap: 2px;
    flex-wrap: wrap;
    align-content: center;
  }
  .bottom-ledgers {
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(360px, .85fr);
    gap: 5px;
    overflow: hidden;
  }
  .bottom-ledgers .grass-ledger {
    grid-template-rows: 22px repeat(12, 22px);
  }
  .bottom-ledgers .grass-row .mon-name,
  .bottom-ledgers .mon-name {
    height: 18px;
    font-size: 9px;
  }
  .bottom-ledgers .method-stack {
    grid-template-rows: repeat(4, minmax(58px, 1fr)) minmax(46px, .8fr) minmax(52px, .9fr) minmax(58px, 1fr);
    gap: 3px;
  }
  .bottom-ledgers .section {
    grid-template-rows: 20px minmax(0, 1fr);
  }
  .bottom-ledgers .section-head {
    padding: 1px 4px;
  }
  .bottom-ledgers .method-table {
    grid-auto-rows: 17px;
  }
  .bottom-ledgers .method-row > span {
    min-height: 17px;
  }
  @media (max-width: 1180px) {
    .topbar {
      grid-template-columns: auto auto minmax(0, 1fr) auto;
    }
    .route-meta { display: none; }
    .slot-ledger,
    .bottom-ledgers {
      grid-template-columns: 1fr;
      overflow: auto;
      scrollbar-gutter: stable;
    }
    .method-stack {
      grid-template-rows: none;
      grid-auto-rows: auto;
    }
  }
  @media (max-width: 760px) {
    body { overflow: hidden; }
    .preview {
      block-size: 100dvh;
      grid-template-rows: auto minmax(0, 1fr);
      padding: 4px;
    }
    .topbar {
      grid-template-columns: auto minmax(0, 1fr) auto;
      grid-auto-rows: minmax(24px, auto);
    }
    .topbar strong { display: none; }
    .route-name { font-size: 16px; }
    .rates {
      grid-column: 1 / -1;
      justify-content: stretch;
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
    }
    .top-rate {
      grid-template-columns: 21px minmax(0, 1fr);
    }
    .body {
      overflow: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable;
    }
    .left-stack {
      grid-template-rows: auto auto;
    }
    .grass-section,
    .coverage,
    .section {
      overflow: visible;
    }
    .grass-ledger {
      min-width: 700px;
    }
    .grass-section {
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }
    .species-strip {
      grid-template-columns: 1fr;
      overflow: visible;
    }
    .single-sheet,
    .species-matrix {
      min-width: 920px;
    }
    .variant-i .body,
    .variant-j .body {
      overflow: auto;
    }
    .pivot-layout {
      grid-template-rows: auto auto;
    }
  }
"""


def build_html(route: dict) -> str:
    script = r"""
      const ids = ['h', 'i', 'j'];
      function activate() {
        const id = ids.includes((location.hash || '#h').slice(1).toLowerCase())
          ? (location.hash || '#h').slice(1).toLowerCase()
          : 'h';
        document.querySelectorAll('.preview').forEach((node, index) => {
          node.classList.toggle('active', ids[index] === id);
        });
      }
      addEventListener('hashchange', activate);
      activate();
    """
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Route 30 Ultra Dense Variants</title><style>'
        + CSS
        + '</style></head><body>'
        + variant_h(route)
        + variant_i(route)
        + variant_j(route)
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
