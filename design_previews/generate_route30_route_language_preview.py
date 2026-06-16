#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().with_name("route30_route_language_preview.html")
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


def table_by_key(route: dict, key: str) -> dict:
    for table in route["pokemonTables"] + route["slotTables"]:
        if table["key"] == key:
            return table
    raise KeyError(key)


def rate_by_key(route: dict, key: str) -> int:
    return next(rate["value"] for rate in route["rates"] if rate["key"] == key)


TYPES = {
    "grass": "Grass",
    "am": "Morning",
    "day": "Day",
    "night": "Night",
    "surf": "Surf",
    "rock": "Rock smash",
    "old": "Old rod",
    "good": "Good rod",
    "super": "Super rod",
    "hoenn": "Hoenn sound",
    "sinnoh": "Sinnoh sound",
    "swarm": "Swarms",
}


def svg_icon(kind: str) -> str:
    attrs = 'class="tile-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"'
    icons = {
        "grass": '<path d="M11 20A7 7 0 0 1 4 13c0-6 8-10 16-10-1 8-5 16-12 16Z"/><path d="M4 20c4-4 8-8 12-12"/>',
        "am": '<path d="M4 18h16"/><path d="M6 15a6 6 0 0 1 12 0"/><path d="M12 3v5"/><path d="m4.2 7.2 2.1 2.1"/><path d="m19.8 7.2-2.1 2.1"/>',
        "day": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.9 4.9 1.4 1.4"/><path d="m17.7 17.7 1.4 1.4"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m4.9 19.1 1.4-1.4"/><path d="m17.7 6.3 1.4-1.4"/>',
        "night": '<path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5 7.5 7.5 0 1 0 20.5 14.5Z"/>',
        "surf": '<path d="M2 8c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2"/><path d="M2 14c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2"/><path d="M2 20c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2"/>',
        "rock": '<path d="m15 12 5-5-3-3-5 5"/><path d="M9 15 4 20"/><path d="m14 13-3 3-3-3 3-3Z"/>',
        "hoenn": '<path d="M9 18V5l10-2v13"/><circle cx="7" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
        "sinnoh": '<path d="M8 18V6l9-2v12"/><path d="M8 10l9-2"/><circle cx="6" cy="18" r="2.5"/><circle cx="15" cy="16" r="2.5"/>',
        "swarm": '<path d="M12 3l1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7Z"/><path d="M5 15l.9 2.1L8 18l-2.1.9L5 21l-.9-2.1L2 18l2.1-.9Z"/><path d="M19 14l.7 1.7L21.5 16.5l-1.8.8L19 19l-.7-1.7-1.8-.8 1.8-.8Z"/>',
    }
    if kind in {"old", "good", "super"}:
        count = {"old": 1, "good": 2, "super": 3}[kind]
        xs = {1: [12], 2: [9, 15], 3: [7, 12, 17]}[count]
        circles = "".join(f'<circle cx="{x}" cy="12" r="2.8" fill="currentColor" stroke="none"/>' for x in xs)
        return f'<svg {attrs}>{circles}</svg>'
    return f'<svg {attrs}>{icons[kind]}</svg>'


def type_tile(kind: str, label: str | None = None) -> str:
    return f'<span class="type-tile {esc(kind)}" title="{esc(label or TYPES[kind])}">{svg_icon(kind)}</span>'


def value_chip(value, cls: str = "") -> str:
    return f'<span class="value-chip {esc(cls)}">{esc(value)}</span>'


def mon_chip(species: dict, form: int = 0, cls: str = "") -> str:
    form_html = "" if not form else f'<span class="form-chip">f{esc(form)}</span>'
    none = " none" if species.get("symbol") == "SPECIES_NONE" else ""
    return (
        f'<span class="mon-chip {esc(cls)}{none}">'
        f'{icon(species)}'
        f'<span class="mon-name">{esc(short_species(species))}</span>'
        f'{form_html}</span>'
    )


def route_maps(route: dict) -> str:
    return ", ".join(map_item["symbol"] for map_item in route["maps"])


def level_range(slot: dict) -> str:
    low = slot.get("minLevel", "")
    high = slot.get("maxLevel", "")
    return str(low) if low == high else f"{low}-{high}"


def unique_species_icons(slots: list[dict], limit: int = 8) -> str:
    seen = set()
    icons = []
    for slot in slots:
        species = slot["species"]
        symbol = species.get("symbol")
        if symbol == "SPECIES_NONE" or symbol in seen:
            continue
        seen.add(symbol)
        icons.append(icon(species))
        if len(icons) >= limit:
            break
    return "".join(icons)


def unique_species_icons_for_symbols(slots: list[dict], symbols: set[str], limit: int = 8) -> str:
    seen = set()
    icons = []
    for slot in slots:
        species = slot["species"]
        symbol = species.get("symbol")
        if symbol == "SPECIES_NONE" or symbol in seen or symbol not in symbols:
            continue
        seen.add(symbol)
        icons.append(icon(species))
        if len(icons) >= limit:
            break
    return "".join(icons)


def overview_pill(kind: str, body: str, label: str | None = None) -> str:
    return f'<span class="overview-pill {esc(kind)}">{type_tile(kind, label)}<span class="overview-icons">{body}</span></span>'


def overview_strip(route: dict) -> str:
    morning_slots = table_by_key(route, "morning")["slots"]
    day_slots = table_by_key(route, "day")["slots"]
    night_slots = table_by_key(route, "night")["slots"]
    morning_symbols = {slot["species"]["symbol"] for slot in morning_slots if slot["species"]["symbol"] != "SPECIES_NONE"}
    day_symbols = {slot["species"]["symbol"] for slot in day_slots if slot["species"]["symbol"] != "SPECIES_NONE"}
    night_symbols = {slot["species"]["symbol"] for slot in night_slots if slot["species"]["symbol"] != "SPECIES_NONE"}
    all_day_symbols = morning_symbols & day_symbols & night_symbols
    pills = []
    all_day_icons = unique_species_icons_for_symbols(morning_slots + day_slots + night_slots, all_day_symbols, 8)
    if all_day_icons:
        pills.append(overview_pill("grass", all_day_icons, "Grass"))
    for kind, slots, symbols, label in [
        ("am", morning_slots, morning_symbols - all_day_symbols, "Morning"),
        ("day", day_slots, day_symbols - all_day_symbols, "Day"),
        ("night", night_slots, night_symbols - all_day_symbols, "Night"),
    ]:
        body = unique_species_icons_for_symbols(slots, symbols, 7)
        if body:
            pills.append(overview_pill(kind, body, label))
    for key, kind in [("surf", "surf"), ("oldRod", "old"), ("goodRod", "good"), ("superRod", "super")]:
        pills.append(overview_pill(kind, unique_species_icons(table_by_key(route, key)["slots"], 7), table_by_key(route, key)["label"]))
    radio_slots = table_by_key(route, "hoenn")["slots"] + table_by_key(route, "sinnoh")["slots"]
    pills.append(overview_pill("hoenn", unique_species_icons(radio_slots, 7), "Radio sounds"))
    swarm_slots = [{"species": swarm["species"]} for swarm in route["swarms"]]
    pills.append(overview_pill("swarm", unique_species_icons(swarm_slots, 7), "Swarms"))
    return '<div class="route-overview">' + "".join(pills) + "</div>"


def top(route: dict) -> str:
    filters = [
        "grass",
        "am",
        "day",
        "night",
        "surf",
        "rock",
        "old",
        "good",
        "super",
        "hoenn",
        "sinnoh",
        "swarm",
    ]
    rate_keys = [
        ("grass", "walkrate"),
        ("surf", "surfrate"),
        ("rock", "rocksmashrate"),
        ("old", "oldrodrate"),
        ("good", "goodrodrate"),
        ("super", "superrodrate"),
    ]
    return (
        '<header class="routes-head">'
        '<div class="head-line">'
        f'<h1>{esc(route["name"])} <span>{esc(route_maps(route))}</span></h1>'
        f'<strong>{esc(route["speciesCount"])} Pokemon</strong>'
        "</div>"
        '<div class="filter-row">'
        + "".join(f'<button class="filter-button" type="button">{type_tile(kind)}</button>' for kind in filters)
        + '<span class="rate-strip">'
        + "".join(
            f'<span class="rate-pill">{type_tile(kind)}{value_chip(rate_by_key(route, key), "rate")}</span>'
            for kind, key in rate_keys
        )
        + "</span></div>"
        + overview_strip(route)
        + "</header>"
    )


def grass_groups(route: dict, idx: int) -> list[tuple[str, str, dict, int]]:
    slots = [
        ("am", "AM", table_by_key(route, "morning")["slots"][idx]),
        ("day", "D", table_by_key(route, "day")["slots"][idx]),
        ("night", "N", table_by_key(route, "night")["slots"][idx]),
    ]
    grouped: dict[tuple[str, int], dict] = {}
    for kind, label, slot in slots:
        key = (slot["species"]["symbol"], slot.get("form", 0))
        grouped.setdefault(key, {"kinds": [], "labels": [], "species": slot["species"], "form": slot.get("form", 0)})
        grouped[key]["kinds"].append(kind)
        grouped[key]["labels"].append(label)

    result = []
    for group in grouped.values():
        labels = group["labels"]
        if labels == ["AM", "D", "N"]:
            label = "All"
            kind = "grass"
        elif labels == ["AM", "D"]:
            label = "AM+D"
            kind = "am"
        else:
            label = "+".join(labels)
            kind = group["kinds"][0]
        result.append((kind, label, group["species"], group["form"]))
    return result


def pill_group(kind: str, label: str, body: str, cls: str = "") -> str:
    return f'<span class="pill-group {esc(kind)} {esc(cls)}">{type_tile(kind, label)}<span class="pill-body">{body}</span></span>'


def grass_panel(route: dict) -> str:
    rows = []
    time_tables = [
        ("am", "Morning", table_by_key(route, "morning")),
        ("day", "Day", table_by_key(route, "day")),
        ("night", "Night", table_by_key(route, "night")),
    ]
    for idx, level in enumerate(route["grassLevels"]):
        group_html = "".join(
            pill_group(kind, label, mon_chip(table["slots"][idx]["species"], table["slots"][idx].get("form", 0)), "time-group")
            for kind, label, table in time_tables
        )
        rows.append(
            '<div class="flat-row grass-row">'
            f'<div class="row-index">#{esc(level["slot"])}</div>'
            f'<div class="row-title compact-stats"><strong>{esc(level["weight"])}%</strong><span>Lv {esc(level["value"])}</span></div>'
            f'<div class="row-groups">{group_html}</div>'
            "</div>"
        )
    return (
        '<section class="list-panel grass-list">'
        '<div class="panel-head"><h2>Grass Slots</h2><span>12 slots</span></div>'
        + "".join(rows)
        + "</section>"
    )


def slot_group(slot: dict) -> str:
    level = level_range(slot)
    return (
        '<span class="slot-chip">'
        f'{value_chip("#" + str(slot["slot"]), "slot")}'
        f'{value_chip(str(slot["weight"]) + "%", "pct")}'
        f'{mon_chip(slot["species"], slot.get("form", 0))}'
        f'{value_chip("L" + level, "level")}'
        "</span>"
    )


def source_row(route: dict, key: str, kind: str) -> str:
    table = table_by_key(route, key)
    body = "".join(
        pill_group(kind, table["label"], slot_group(slot), "slot-group")
        for slot in table["slots"]
    )
    return (
        f'<div class="flat-row source-row source-{esc(kind)}">'
        f'<div class="row-groups">{body}</div>'
        "</div>"
    )


def radio_row(route: dict) -> str:
    chips = []
    for key, kind in [("hoenn", "hoenn"), ("sinnoh", "sinnoh")]:
        table = table_by_key(route, key)
        for slot in table["slots"]:
            chips.append(
                pill_group(
                    kind,
                    table["label"],
                    '<span class="slot-chip radio-chip">'
                    f'{value_chip(str(slot["weight"]) + "%", "pct")}'
                    f'{mon_chip(slot["species"], slot.get("form", 0))}'
                    "</span>",
                    "slot-group",
                )
            )
    return (
        '<div class="flat-row source-row source-radio">'
        f'<div class="row-groups">{"".join(chips)}</div>'
        "</div>"
    )


def swarm_row(route: dict) -> str:
    chips = []
    for swarm in route["swarms"]:
        label = swarm["label"].replace(" swarm", "").replace("Good rod", "Good").replace("Super rod", "Super")
        chips.append(
            pill_group(
                "swarm",
                label,
                '<span class="slot-chip swarm-slot">'
                f'{value_chip(label, "source-label")}'
                f'{mon_chip(swarm["species"], swarm.get("form", 0))}'
                "</span>",
                "slot-group",
            )
        )
    return (
        '<div class="flat-row source-row source-swarm">'
        f'<div class="row-groups">{"".join(chips)}</div>'
        "</div>"
    )


def sources_panel(route: dict) -> str:
    rows = [
        source_row(route, "surf", "surf"),
        source_row(route, "oldRod", "old"),
        source_row(route, "goodRod", "good"),
        source_row(route, "superRod", "super"),
        source_row(route, "rockSmash", "rock"),
        radio_row(route),
        swarm_row(route),
    ]
    return (
        '<section class="list-panel source-list">'
        '<div class="panel-head"><h2>Other Sources</h2><span>Surf, rods, sounds, swarms</span></div>'
        + "".join(rows)
        + "</section>"
    )


CSS = r"""
  :root {
    --bg: #f7f9fc;
    --panel: #fff;
    --line: #d2dce9;
    --soft: #e8eef6;
    --ink: #17202d;
    --muted: #63728c;
    --green: #0b8063;
    --green-bg: #eaf8f1;
    --blue: #0875b7;
    --blue-bg: #e9f5fd;
    --gold: #a26012;
    --gold-bg: #fff5e4;
    --violet: #7548d6;
    --violet-bg: #f4efff;
    --pink: #d63a76;
    --pink-bg: #fff0f6;
    --stone: #6e675f;
    --stone-bg: #f6f3ef;
  }
  * { box-sizing: border-box; min-width: 0; }
  html,
  body {
    width: 100%;
    height: 100%;
    margin: 0;
    overflow: hidden;
    background: var(--bg);
    color: var(--ink);
    font: 15px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .preview {
    width: 100%;
    height: 100dvh;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    overflow: clip;
  }
  .routes-head {
    background: var(--panel);
    border-bottom: 1px solid var(--line);
    box-shadow: 0 1px 0 rgba(20, 30, 44, .03);
  }
  .head-line {
    height: 42px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 0 13px;
    border-bottom: 1px solid var(--line);
  }
  h1 {
    margin: 0;
    font-size: 23px;
    font-weight: 950;
    letter-spacing: 0;
  }
  h1 span {
    color: var(--muted);
    font-weight: 650;
  }
  .head-line strong {
    color: var(--muted);
    font-size: 22px;
    font-weight: 650;
  }
  .filter-row {
    min-height: 48px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px;
    overflow: hidden;
  }
  .filter-button {
    width: 48px;
    height: 48px;
    border: 2px solid var(--line);
    border-radius: 10px;
    background: #fff;
    padding: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .filter-button:nth-child(-n+9) {
    border-color: var(--line);
    background: #fff;
  }
  .rate-strip {
    margin-left: auto;
    display: flex;
    gap: 7px;
    overflow: hidden;
  }
  .rate-pill {
    height: 34px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 0 7px 0 5px;
    border: 2px solid var(--line);
    border-radius: 10px;
    background: #fff;
  }
  .search-like {
    display: none;
  }
  .route-overview {
    min-height: 48px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 7px 9px;
    overflow: hidden;
  }
  .overview-pill {
    min-width: 0;
    min-height: 39px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 0 1 auto;
    border: 2px solid var(--line);
    border-radius: 10px;
    background: #fff;
    padding: 4px 9px 4px 5px;
  }
  .overview-icons {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 5px;
    overflow: hidden;
  }
  .overview-icons .mon-icon {
    width: 28px;
    height: 28px;
    flex: 0 0 auto;
  }
  .type-tile {
    width: 37px;
    height: 37px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    border: 2px solid var(--line);
    border-radius: 9px;
    background: #fff;
    color: var(--muted);
    font: 950 13px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .tile-svg {
    width: 22px;
    height: 22px;
    display: block;
  }
  .grass,
  .am,
  .day,
  .night {
    color: var(--green);
    background: var(--green-bg);
    border-color: #b7dccc;
  }
  .surf {
    color: var(--blue);
    background: var(--blue-bg);
    border-color: #c1ddf1;
  }
  .old,
  .good,
  .super {
    color: var(--blue);
    background: var(--blue-bg);
    border-color: #c1ddf1;
  }
  .rock {
    color: var(--stone);
    background: var(--stone-bg);
    border-color: #d8d1c7;
  }
  .hoenn,
  .sinnoh {
    color: var(--violet);
    background: var(--violet-bg);
    border-color: #cfc1fa;
  }
  .swarm {
    color: var(--pink);
    background: var(--pink-bg);
    border-color: #f2bfd4;
  }
  .route-body {
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, .96fr) minmax(640px, 1.04fr);
    grid-template-rows: minmax(0, 1fr);
    gap: 0;
    overflow: hidden;
    background: var(--panel);
  }
  .list-panel {
    min-height: 0;
    min-width: 0;
    background: var(--panel);
    border-right: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
    overflow: hidden;
  }
  .grass-list {
    grid-column: 1;
    grid-row: 1;
  }
  .source-list {
    grid-column: 2;
    grid-row: 1 / 3;
  }
  .cast-list {
    display: none;
  }
  .panel-head {
    height: 34px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 0 12px;
    border-bottom: 1px solid var(--line);
    background: #fbfcff;
  }
  .panel-head h2 {
    margin: 0;
    font-size: 17px;
    font-weight: 950;
  }
  .panel-head span {
    color: var(--muted);
    font-size: 15px;
    font-weight: 650;
  }
  .flat-row {
    min-width: 0;
    display: grid;
    grid-template-columns: 56px 148px minmax(0, 1fr);
    align-items: center;
    min-height: 38px;
    padding: 3px 7px;
    border-bottom: 1px solid var(--line);
    background: #fff;
  }
  .source-surf,
  .source-old,
  .source-good,
  .source-super {
    background: linear-gradient(90deg, rgba(8, 117, 183, .07), #fff 48%);
  }
  .source-surf .pill-group,
  .source-old .pill-group,
  .source-good .pill-group,
  .source-super .pill-group {
    background: #f3faff;
    border-color: #c6e0f4;
  }
  .grass-row {
    min-height: 45px;
  }
  .source-row {
    grid-template-columns: minmax(0, 1fr);
    min-height: 0;
    padding: 4px 7px;
  }
  .row-index {
    color: var(--muted);
    font-size: 18px;
    font-weight: 850;
  }
  .row-title {
    min-width: 0;
    display: flex;
    align-items: baseline;
    gap: 6px;
    overflow: hidden;
  }
  .compact-stats {
    display: inline-flex;
    align-items: baseline;
    gap: 5px;
  }
  .compact-stats strong {
    color: var(--ink);
  }
  .source-row .row-title {
    display: grid;
    gap: 2px;
    align-items: center;
  }
  .row-title strong {
    font-size: 16px;
    font-weight: 950;
    white-space: nowrap;
  }
  .row-title span {
    min-width: 0;
    color: var(--muted);
    font-size: 11px;
    font-weight: 750;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .row-groups {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 7px;
    overflow: hidden;
  }
  .pill-group {
    min-width: 0;
    min-height: 33px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex: 0 1 auto;
    border: 2px solid var(--line);
    border-radius: 10px;
    background: #fff;
    padding: 3px 6px 3px 4px;
  }
  .time-group {
    min-height: 37px;
  }
  .pill-group > .type-tile {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    font-size: 11px;
  }
  .pill-body {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    overflow: hidden;
  }
  .value-chip {
    height: 20px;
    min-width: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: #fff;
    color: var(--muted);
    padding: 0 6px;
    font: 950 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    white-space: nowrap;
  }
  .slot,
  .level,
  .rate {
    color: var(--ink);
  }
  .pct {
    color: var(--green);
  }
  .mon-chip {
    min-width: 0;
    display: inline-grid;
    grid-template-columns: 26px minmax(0, 1fr) auto;
    align-items: center;
    gap: 4px;
  }
  .mon-icon {
    width: 26px;
    height: 26px;
    object-fit: contain;
    image-rendering: pixelated;
  }
  .mon-name {
    min-width: 0;
    height: 23px;
    display: flex;
    align-items: center;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: #fff;
    padding: 0 7px;
    font: 950 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .mon-chip.none .mon-name {
    color: #8c97a8;
    background: #f7f9fc;
  }
  .form-chip {
    height: 20px;
    min-width: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: #fff;
    color: var(--muted);
    font: 950 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .slot-chip {
    min-width: 0;
    display: inline-grid;
    grid-template-columns: auto auto minmax(58px, 1fr) auto;
    align-items: center;
    gap: 5px;
    flex: 0 1 auto;
  }
  .radio-chip {
    grid-template-columns: auto auto minmax(78px, 1fr);
  }
  .swarm-slot {
    grid-template-columns: 56px minmax(86px, 1fr);
  }
  .source-list .pill-group {
    width: auto;
    min-height: 30px;
    flex: 0 1 auto;
  }
  .source-list .row-groups {
    flex-wrap: wrap;
    align-content: center;
    gap: 5px;
    row-gap: 4px;
  }
  .source-list .pill-body {
    flex-wrap: nowrap;
  }
  .source-list .slot-group {
    padding: 2px 4px 2px 3px;
  }
  .source-list .slot-group > .type-tile {
    width: 28px;
    height: 28px;
    border-radius: 8px;
  }
  .source-list .slot-group > .type-tile .tile-svg {
    width: 18px;
    height: 18px;
  }
  .source-list .value-chip {
    height: 18px;
    padding: 0 4px;
    font-size: 9px;
  }
  .source-list .slot-chip {
    grid-template-columns: auto auto minmax(58px, 1fr) auto;
    flex: 0 1 auto;
    min-width: 0;
    gap: 3px;
  }
  .source-list .radio-chip {
    grid-template-columns: auto minmax(62px, 1fr);
  }
  .source-list .swarm-slot {
    grid-template-columns: auto minmax(68px, 1fr);
  }
  .source-list .mon-icon {
    width: 24px;
    height: 24px;
  }
  .source-list .mon-name {
    height: 18px;
    padding: 0 5px;
    font-size: 9px;
    max-width: 74px;
  }
  .source-list .form-chip {
    height: 18px;
    min-width: 20px;
    font-size: 9px;
  }
  @media (max-width: 1120px) {
    .route-body {
      grid-template-columns: 1fr;
      grid-template-rows: auto auto auto;
      overflow: auto;
      scrollbar-gutter: stable;
    }
    .grass-list,
    .source-list,
    .cast-list {
      grid-column: auto;
      grid-row: auto;
      overflow: visible;
    }
  }
  @media (max-width: 760px) {
    .preview {
      height: 100dvh;
    }
    .head-line {
      height: 42px;
    }
    h1 {
      font-size: 19px;
    }
    .head-line strong {
      font-size: 17px;
    }
    .filter-row {
      min-height: 48px;
      gap: 6px;
      padding: 7px;
    }
    .filter-button {
      width: 42px;
      height: 42px;
    }
    .filter-button .type-tile,
    .rate-pill .type-tile {
      width: 29px;
      height: 29px;
    }
    .rate-strip {
      display: none;
    }
    .route-overview {
      min-height: 42px;
      overflow-x: auto;
      overscroll-behavior-x: contain;
      padding-bottom: 6px;
    }
    .route-body {
      overflow: auto;
      overscroll-behavior: contain;
    }
    .flat-row,
    .source-row {
      grid-template-columns: 48px minmax(0, 1fr);
      gap: 4px;
    }
    .row-groups {
      grid-column: 1 / -1;
      flex-wrap: wrap;
      overflow: visible;
    }
    .pill-group {
      width: 100%;
    }
  }
"""


def build_html(route: dict) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Route 30 Route Language Preview</title><style>'
        + CSS
        + '</style></head><body><main class="preview">'
        + top(route)
        + '<section class="route-body">'
        + grass_panel(route)
        + sources_panel(route)
        + "</section></main></body></html>"
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
