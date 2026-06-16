#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().with_name("route30_visual_compact_variants.html")
VIEWER = ROOT / "scripts" / "overworld_behavior_profile_viewer.py"
ICON_ORIGIN = "http://127.0.0.1:8765"


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def short_species(species: dict) -> str:
    return str(species.get("symbol", species.get("name", ""))).removeprefix("SPECIES_")


def mon_icon(species: dict) -> str:
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


def level_range(slot: dict) -> str:
    low = slot.get("minLevel", "")
    high = slot.get("maxLevel", "")
    return str(low) if low == high else f"{low}-{high}"


SOURCE = {
    "grass": ("G", "Grass"),
    "am": ("AM", "Morning"),
    "day": ("D", "Day"),
    "night": ("N", "Night"),
    "surf": ("~", "Surf"),
    "old": ("1", "Old rod"),
    "good": ("2", "Good rod"),
    "super": ("3", "Super rod"),
    "rock": ("R", "Rock smash"),
    "hoenn": ("H", "Hoenn sound"),
    "sinnoh": ("S", "Sinnoh sound"),
    "radio": ("H/S", "Radio"),
    "swarm": ("!", "Swarms"),
}


def glyph(kind: str, label: str | None = None) -> str:
    text, title = SOURCE[kind]
    return f'<span class="glyph {esc(kind)}" title="{esc(label or title)}">{esc(text)}</span>'


def tiny_value(value, cls: str = "") -> str:
    return f'<span class="tiny-value {esc(cls)}">{esc(value)}</span>'


def mon_chip(species: dict, form: int = 0, label: str = "", level: str | None = None, cls: str = "") -> str:
    form_html = "" if not form else f'<span class="mini-tag">f{esc(form)}</span>'
    level_html = "" if level in (None, "", "0", 0) else f'<span class="mini-tag level-tag">L{esc(level)}</span>'
    label_html = "" if not label else f'<span class="chip-label">{esc(label)}</span>'
    none = " none" if species.get("symbol") == "SPECIES_NONE" else ""
    return (
        f'<span class="mon-chip {esc(cls)}{none}">'
        f'{label_html}{mon_icon(species)}'
        f'<span class="mon-name">{esc(short_species(species))}</span>'
        f'{form_html}{level_html}</span>'
    )


def topbar(route: dict, label: str) -> str:
    maps = ", ".join(map_item["symbol"] for map_item in route["maps"])
    rates = [
        ("grass", "walkrate"),
        ("surf", "surfrate"),
        ("rock", "rocksmashrate"),
        ("old", "oldrodrate"),
        ("good", "goodrodrate"),
        ("super", "superrodrate"),
    ]
    rate_html = "".join(
        f'<span class="rate-pill">{glyph(kind)}{tiny_value(rate_by_key(route, key), "rate")}</span>'
        for kind, key in rates
    )
    return (
        '<header class="topbar">'
        f'<strong>{esc(label)}</strong>'
        f'<span class="route-name">{esc(route["name"])}</span>'
        f'<span class="meta">#{esc(route["id"])} {esc(maps)} {esc(route["speciesCount"])} Pokemon</span>'
        f'<span class="rate-row">{rate_html}</span>'
        '<span class="source">Source</span>'
        "</header>"
    )


def panel(title: str, kind: str, body: str, cls: str = "") -> str:
    return (
        f'<section class="panel {esc(kind)} {esc(cls)}">'
        f'<div class="panel-title">{glyph(kind, title)}<strong>{esc(title)}</strong></div>'
        f'{body}</section>'
    )


def grass_time_groups(route: dict, idx: int) -> list[tuple[str, dict, int]]:
    groups: dict[tuple[str, int], dict] = {}
    order = [
        ("am", "AM", table_by_key(route, "morning")["slots"][idx]),
        ("day", "D", table_by_key(route, "day")["slots"][idx]),
        ("night", "N", table_by_key(route, "night")["slots"][idx]),
    ]
    for kind, label, slot in order:
        key = (slot["species"]["symbol"], slot.get("form", 0))
        groups.setdefault(key, {"labels": [], "species": slot["species"], "form": slot.get("form", 0)})
        groups[key]["labels"].append(label)
    result = []
    for group in groups.values():
        labels = group["labels"]
        if len(labels) == 3:
            label = "All"
        elif labels == ["AM", "D"]:
            label = "AM+D"
        else:
            label = "+".join(labels)
        result.append((label, group["species"], group["form"]))
    return result


def grass_flow(route: dict, mode: str = "flow") -> str:
    rows = []
    for idx, level in enumerate(route["grassLevels"]):
        chips = "".join(
            mon_chip(species, form, label, cls="time-chip")
            for label, species, form in grass_time_groups(route, idx)
        )
        rows.append(
            '<div class="grass-slot" style="--rate: {rate}">'
            '<span class="rate-fill"></span>'
            '<span class="slot-meta">'
            f'{tiny_value("#" + str(level["slot"]), "slot")}'
            f'{tiny_value(str(level["weight"]) + "%", "pct")}'
            f'{tiny_value("L" + str(level["value"]), "lvl")}'
            '</span>'
            f'<span class="time-cluster">{chips}</span>'
            "</div>".format(rate=esc(level["weight"]))
        )
    return '<div class="grass-flow ' + esc(mode) + '">' + "".join(rows) + "</div>"


def grass_mosaic(route: dict) -> str:
    tiles = []
    for idx, level in enumerate(route["grassLevels"]):
        chips = "".join(
            mon_chip(species, form, label, cls="tile-chip")
            for label, species, form in grass_time_groups(route, idx)
        )
        tiles.append(
            f'<div class="grass-tile" style="--rate:{esc(level["weight"])}">'
            '<span class="tile-rate"></span>'
            f'<span class="tile-meta">{tiny_value("#" + str(level["slot"]), "slot")}{tiny_value(str(level["weight"]) + "%", "pct")}{tiny_value("L" + str(level["value"]), "lvl")}</span>'
            f'<span class="tile-mons">{chips}</span>'
            "</div>"
        )
    return '<div class="grass-mosaic">' + "".join(tiles) + "</div>"


def slot_deck(route: dict, key: str, kind: str) -> str:
    table = table_by_key(route, key)
    chips = []
    for slot in table["slots"]:
        chips.append(
            '<span class="source-chip">'
            f'{tiny_value("#" + str(slot["slot"]), "slot")}'
            f'{tiny_value(str(slot["weight"]) + "%", "pct")}'
            f'{mon_chip(slot["species"], slot.get("form", 0), level=level_range(slot), cls="deck-mon")}'
            "</span>"
        )
    return panel(table["label"], kind, '<div class="source-chip-grid">' + "".join(chips) + "</div>", "deck")


def radio_deck(route: dict) -> str:
    chips = []
    for key, kind in [("hoenn", "hoenn"), ("sinnoh", "sinnoh")]:
        table = table_by_key(route, key)
        for slot in table["slots"]:
            chips.append(
                '<span class="source-chip">'
                f'{glyph(kind)}{tiny_value(str(slot["weight"]) + "%", "pct")}'
                f'{mon_chip(slot["species"], slot.get("form", 0), cls="deck-mon")}'
                "</span>"
            )
    return panel("Radio sounds", "radio", '<div class="source-chip-grid">' + "".join(chips) + "</div>", "deck")


def swarm_deck(route: dict) -> str:
    chips = []
    for swarm in route["swarms"]:
        label = swarm["label"].replace(" swarm", "").replace("Good rod", "Good").replace("Super rod", "Super")
        chips.append(
            '<span class="source-chip swarm-chip">'
            f'{tiny_value(label, "source-label")}'
            f'{mon_chip(swarm["species"], swarm.get("form", 0), cls="deck-mon")}'
            "</span>"
        )
    return panel("Swarms", "swarm", '<div class="source-chip-grid">' + "".join(chips) + "</div>", "deck")


def method_decks(route: dict) -> str:
    return (
        '<div class="method-decks">'
        + slot_deck(route, "surf", "surf")
        + slot_deck(route, "oldRod", "old")
        + slot_deck(route, "goodRod", "good")
        + slot_deck(route, "superRod", "super")
        + slot_deck(route, "rockSmash", "rock")
        + radio_deck(route)
        + swarm_deck(route)
        + "</div>"
    )


def add_hit(seen: dict, hits: dict, species: dict, label: str) -> None:
    if species.get("symbol") == "SPECIES_NONE":
        return
    symbol = species["symbol"]
    seen[symbol] = species
    hits[symbol].append(label)


def cast_data(route: dict) -> list[tuple[dict, list[str]]]:
    seen: dict[str, dict] = {}
    hits: dict[str, list[str]] = defaultdict(list)
    for key, label in [("morning", "AM"), ("day", "D"), ("night", "N"), ("hoenn", "H"), ("sinnoh", "S")]:
        for slot in table_by_key(route, key)["slots"]:
            add_hit(seen, hits, slot["species"], f'{label}{slot["slot"]}:{slot["weight"]}')
    for key, label in [("surf", "~"), ("oldRod", "1"), ("goodRod", "2"), ("superRod", "3"), ("rockSmash", "R")]:
        for slot in table_by_key(route, key)["slots"]:
            add_hit(seen, hits, slot["species"], f'{label}{slot["slot"]}:{slot["weight"]}L{level_range(slot)}')
    for swarm in route["swarms"]:
        add_hit(seen, hits, swarm["species"], swarm["label"].replace(" swarm", ""))
    return sorted(((species, hits[symbol]) for symbol, species in seen.items()), key=lambda item: (-len(item[1]), item[0]["value"]))


def cast_cloud(route: dict, compact: bool = False) -> str:
    nodes = []
    max_hits = max(len(hits) for _species, hits in cast_data(route))
    for species, hits in cast_data(route):
        chips = "".join(tiny_value(hit, "hit") for hit in hits[:6 if compact else 8])
        nodes.append(
            f'<div class="cast-node" style="--weight:{len(hits) / max_hits:.2f}">'
            f'{mon_chip(species, cls="cast-mon")}'
            f'<span class="cast-hits">{chips}</span>'
            "</div>"
        )
    return panel("Route cast", "grass", '<div class="cast-cloud">' + "".join(nodes) + "</div>", "cast-panel")


def source_rail(route: dict, key: str, kind: str) -> str:
    table = table_by_key(route, key)
    chips = []
    for slot in table["slots"]:
        chips.append(
            '<span class="rail-token">'
            f'{tiny_value(slot["slot"], "slot")}'
            f'{tiny_value(str(slot["weight"]) + "%", "pct")}'
            f'{mon_chip(slot["species"], slot.get("form", 0), level=level_range(slot), cls="rail-mon")}'
            "</span>"
        )
    return f'<div class="rail {esc(kind)}"><span class="rail-label">{glyph(kind)}<strong>{esc(table["label"])}</strong></span><span class="rail-items">{"".join(chips)}</span></div>'


def grass_source_rails(route: dict) -> str:
    rows = []
    for source_key, kind, label in [("morning", "am", "Morning"), ("day", "day", "Day"), ("night", "night", "Night")]:
        table = table_by_key(route, source_key)
        chips = []
        for idx, slot in enumerate(table["slots"]):
            level = route["grassLevels"][idx]
            chips.append(
                '<span class="rail-token">'
                f'{tiny_value(level["slot"], "slot")}'
                f'{tiny_value(str(level["weight"]) + "%", "pct")}'
                f'{tiny_value("L" + str(level["value"]), "lvl")}'
                f'{mon_chip(slot["species"], slot.get("form", 0), cls="rail-mon")}'
                "</span>"
            )
        rows.append(f'<div class="rail grass-rail {esc(kind)}"><span class="rail-label">{glyph(kind)}<strong>{esc(label)}</strong></span><span class="rail-items">{"".join(chips)}</span></div>')
    return "".join(rows)


def radio_rail(route: dict) -> str:
    chips = []
    for key, kind in [("hoenn", "hoenn"), ("sinnoh", "sinnoh")]:
        table = table_by_key(route, key)
        for slot in table["slots"]:
            chips.append(
                '<span class="rail-token">'
                f'{glyph(kind)}{tiny_value(str(slot["weight"]) + "%", "pct")}'
                f'{mon_chip(slot["species"], slot.get("form", 0), cls="rail-mon")}'
                "</span>"
            )
    return f'<div class="rail radio"><span class="rail-label">{glyph("radio")}<strong>Radio</strong></span><span class="rail-items">{"".join(chips)}</span></div>'


def swarm_rail(route: dict) -> str:
    chips = []
    for swarm in route["swarms"]:
        label = swarm["label"].replace(" swarm", "").replace("Good rod", "Good").replace("Super rod", "Super")
        chips.append(
            '<span class="rail-token">'
            f'{tiny_value(label, "source-label")}'
            f'{mon_chip(swarm["species"], swarm.get("form", 0), cls="rail-mon")}'
            "</span>"
        )
    return f'<div class="rail swarm"><span class="rail-label">{glyph("swarm")}<strong>Swarms</strong></span><span class="rail-items">{"".join(chips)}</span></div>'


def variant_k(route: dict) -> str:
    return (
        '<main class="preview variant-k">'
        + topbar(route, "K Habitat Flow")
        + '<div class="body flow-layout">'
        + panel("Grass rhythm", "grass", grass_flow(route), "grass-panel")
        + method_decks(route)
        + cast_cloud(route, compact=True)
        + "</div></main>"
    )


def variant_l(route: dict) -> str:
    return (
        '<main class="preview variant-l">'
        + topbar(route, "L Encounter Mosaic")
        + '<div class="body mosaic-layout">'
        + panel("Grass mosaic", "grass", grass_mosaic(route), "mosaic-grass")
        + cast_cloud(route, compact=True)
        + method_decks(route)
        + "</div></main>"
    )


def variant_m(route: dict) -> str:
    return (
        '<main class="preview variant-m">'
        + topbar(route, "M Source Rails")
        + '<div class="body rails-layout">'
        + '<section class="rail-board">'
        + grass_source_rails(route)
        + source_rail(route, "surf", "surf")
        + source_rail(route, "oldRod", "old")
        + source_rail(route, "goodRod", "good")
        + source_rail(route, "superRod", "super")
        + source_rail(route, "rockSmash", "rock")
        + radio_rail(route)
        + swarm_rail(route)
        + "</section>"
        + cast_cloud(route, compact=True)
        + "</div></main>"
    )


CSS = r"""
  :root {
    --bg: #eef2f6;
    --panel: #fff;
    --line: #cad5e4;
    --soft: #e4ebf4;
    --ink: #15202c;
    --muted: #60708a;
    --grass: #0c865c;
    --water: #0879bd;
    --rod: #a76610;
    --rock: #6d665c;
    --radio: #6042ce;
    --swarm: #cf376b;
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
    display: none;
    grid-template-rows: 32px minmax(0, 1fr);
    gap: 5px;
    padding: 5px;
    overflow: clip;
  }
  .preview.active { display: grid; }
  .topbar {
    display: grid;
    grid-template-columns: auto auto auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 8px;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: var(--panel);
    padding: 3px 6px;
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
  .meta {
    color: var(--muted);
    font-weight: 850;
    white-space: nowrap;
  }
  .source {
    height: 22px;
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    background: #d9f4ee;
    color: #0b5f52;
    padding: 0 8px;
    font-weight: 950;
  }
  .rate-row {
    display: flex;
    justify-content: flex-end;
    gap: 3px;
    overflow: hidden;
  }
  .rate-pill {
    display: inline-grid;
    grid-template-columns: 21px 34px;
    gap: 2px;
    align-items: center;
  }
  .body {
    min-height: 0;
    overflow: clip;
  }
  .glyph {
    width: 21px;
    height: 20px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 5px;
    border: 1px solid var(--line);
    background: #fff;
    color: var(--muted);
    font: 950 9px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    flex: 0 0 auto;
  }
  .glyph.grass,
  .glyph.am,
  .glyph.day,
  .glyph.night { color: var(--grass); background: #effbf5; border-color: #a8dac4; }
  .glyph.surf { color: var(--water); background: #edf8ff; border-color: #a9d8f4; }
  .glyph.old,
  .glyph.good,
  .glyph.super { color: var(--rod); background: #fff6e7; border-color: #e8ca96; }
  .glyph.rock { color: var(--rock); background: #f7f4ef; border-color: #d9d1c4; }
  .glyph.radio,
  .glyph.hoenn,
  .glyph.sinnoh { color: var(--radio); background: #f4f1ff; border-color: #cabdff; }
  .glyph.swarm { color: var(--swarm); background: #fff0f5; border-color: #f1b4cf; }
  .tiny-value {
    min-width: 0;
    height: 19px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--line);
    border-radius: 5px;
    background: #fff;
    padding: 0 4px;
    color: var(--muted);
    font: 950 9px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    white-space: nowrap;
  }
  .slot,
  .lvl,
  .rate { color: var(--ink); }
  .pct { color: var(--grass); }
  .panel {
    min-height: 0;
    display: grid;
    grid-template-rows: 25px minmax(0, 1fr);
    border: 1px solid var(--line);
    border-radius: 7px;
    background: var(--panel);
    overflow: hidden;
  }
  .panel-title {
    display: flex;
    align-items: center;
    gap: 5px;
    border-bottom: 1px solid var(--line);
    background: #f8fbff;
    padding: 2px 5px;
    color: var(--muted);
    text-transform: uppercase;
    font-weight: 950;
    letter-spacing: .02em;
  }
  .panel-title strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mon-chip {
    min-width: 0;
    display: inline-grid;
    grid-template-columns: auto 18px minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 3px;
  }
  .mon-icon {
    width: 18px;
    height: 18px;
    object-fit: contain;
    image-rendering: pixelated;
  }
  .mon-name {
    min-width: 0;
    height: 19px;
    display: flex;
    align-items: center;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    border: 1px solid var(--line);
    border-radius: 5px;
    background: #fff;
    padding: 0 5px;
    font: 950 9px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .mon-chip.none .mon-name {
    color: #8995a8;
    background: #f7f9fc;
  }
  .chip-label,
  .mini-tag {
    height: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--line);
    border-radius: 5px;
    background: #f9fbfe;
    color: var(--muted);
    padding: 0 4px;
    font: 950 8px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    white-space: nowrap;
  }
  .time-chip {
    height: 26px;
    grid-template-columns: 36px 18px minmax(56px, 1fr) auto;
    border: 1px solid var(--soft);
    border-radius: 7px;
    background: #fff;
    padding: 2px 3px;
  }
  .time-chip .chip-label {
    background: #effbf5;
    color: var(--grass);
    border-color: #acd8c2;
  }
  .time-chip .mon-name {
    height: 19px;
    font-size: 9px;
  }
  .flow-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(460px, .86fr);
    grid-template-rows: auto minmax(0, 1fr);
    gap: 5px;
  }
  .flow-layout .grass-panel {
    grid-column: 1;
    grid-row: 1;
  }
  .flow-layout .method-decks {
    grid-column: 2;
    grid-row: 1 / 3;
  }
  .flow-layout .cast-panel {
    grid-column: 1;
    grid-row: 2;
  }
  .grass-flow {
    min-height: 0;
    padding: 5px;
    display: grid;
    grid-template-rows: repeat(12, 44px);
    gap: 4px;
  }
  .grass-slot {
    position: relative;
    min-height: 0;
    display: grid;
    grid-template-columns: 116px minmax(0, 1fr);
    align-items: center;
    gap: 5px;
    border: 1px solid var(--soft);
    border-radius: 8px;
    background:
      linear-gradient(90deg, rgba(12, 134, 92, .08), transparent 42%),
      #fff;
    overflow: hidden;
  }
  .grass-slot::before {
    content: "";
    position: absolute;
    inset-block: 0;
    inset-inline-start: 0;
    width: 4px;
    background: var(--grass);
  }
  .rate-fill {
    position: absolute;
    inset-block-start: 0;
    inset-inline-start: 4px;
    height: 3px;
    inline-size: calc(var(--rate) * 1%);
    min-inline-size: 8px;
    max-inline-size: calc(100% - 4px);
    background: var(--grass);
    opacity: .85;
  }
  .slot-meta {
    z-index: 1;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 3px;
    padding-inline-start: 8px;
  }
  .time-cluster {
    z-index: 1;
    display: flex;
    gap: 4px;
    overflow: hidden;
  }
  .method-decks {
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: repeat(4, minmax(0, 1fr));
    gap: 5px;
  }
  .method-decks .panel {
    grid-template-rows: 24px minmax(0, 1fr);
  }
  .method-decks .swarm {
    grid-column: span 2;
  }
  .source-chip-grid {
    min-height: 0;
    padding: 4px;
    display: grid;
    grid-template-columns: 1fr;
    gap: 3px;
    overflow: hidden;
  }
  .source-chip {
    min-height: 0;
    display: grid;
    grid-template-columns: 28px 36px minmax(0, 1fr);
    align-items: center;
    gap: 3px;
    border: 1px solid var(--soft);
    border-radius: 6px;
    background: #fff;
    padding: 2px;
  }
  .source-chip .glyph {
    width: 20px;
    height: 18px;
  }
  .deck-mon {
    grid-template-columns: 18px minmax(0, 1fr) auto;
  }
  .deck-mon .chip-label {
    display: none;
  }
  .deck-mon .mon-name {
    height: 18px;
  }
  .swarm-chip {
    grid-template-columns: 58px minmax(0, 1fr);
  }
  .source-label {
    width: 100%;
    justify-content: flex-start;
  }
  .cast-panel {
    grid-template-rows: 24px minmax(0, 1fr);
  }
  .cast-cloud {
    min-height: 0;
    padding: 5px;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 4px;
    overflow: hidden;
  }
  .flow-layout .cast-cloud {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-auto-rows: minmax(26px, 1fr);
  }
  .cast-node {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(82px, .7fr) minmax(0, 1fr);
    align-items: center;
    gap: 3px;
    border: 1px solid var(--soft);
    border-radius: 7px;
    background:
      linear-gradient(90deg, rgba(8, 121, 189, calc(var(--weight) * .10)), transparent 62%),
      #fff;
    padding: 2px;
  }
  .cast-mon {
    grid-template-columns: 18px minmax(0, 1fr);
  }
  .cast-mon .chip-label {
    display: none;
  }
  .cast-hits {
    display: flex;
    gap: 2px;
    overflow: hidden;
  }
  .hit {
    height: 17px;
    padding: 0 3px;
    font-size: 8px;
  }
  .mosaic-layout {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    grid-template-rows: minmax(0, .66fr) minmax(0, .34fr);
    gap: 5px;
  }
  .mosaic-grass {
    grid-column: 1 / 4;
    grid-row: 1;
  }
  .mosaic-layout .cast-panel {
    grid-column: 4;
    grid-row: 1 / 3;
  }
  .mosaic-layout .method-decks {
    grid-column: 1 / 4;
    grid-row: 2;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    grid-template-rows: 1fr;
  }
  .mosaic-layout .method-decks .swarm {
    grid-column: auto;
  }
  .mosaic-layout .source-chip {
    grid-template-columns: 24px minmax(0, 1fr);
  }
  .mosaic-layout .source-chip > .pct {
    display: none;
  }
  .mosaic-layout .cast-cloud {
    grid-template-columns: 1fr;
  }
  .grass-mosaic {
    min-height: 0;
    padding: 6px;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    grid-template-rows: repeat(3, minmax(0, 1fr));
    gap: 5px;
  }
  .grass-tile {
    position: relative;
    min-width: 0;
    display: grid;
    grid-template-rows: 22px minmax(0, 1fr);
    border: 1px solid var(--soft);
    border-radius: 9px;
    background: #fff;
    overflow: hidden;
  }
  .tile-rate {
    position: absolute;
    inset-inline: 0;
    inset-block-start: 0;
    height: 4px;
    inline-size: calc(var(--rate) * 3%);
    min-inline-size: 14px;
    max-inline-size: 100%;
    background: var(--grass);
  }
  .tile-meta {
    display: flex;
    gap: 3px;
    padding: 5px 5px 0;
  }
  .tile-mons {
    min-height: 0;
    padding: 3px 5px 5px;
    display: grid;
    gap: 3px;
    align-content: center;
  }
  .tile-chip {
    grid-template-columns: 36px 18px minmax(0, 1fr);
  }
  .tile-chip .mini-tag {
    display: none;
  }
  .rails-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.58fr) minmax(340px, .58fr);
    gap: 5px;
  }
  .rails-layout .cast-panel {
    min-height: 0;
  }
  .rails-layout .cast-cloud {
    grid-template-columns: 1fr;
    grid-auto-rows: 32px;
    align-content: start;
  }
  .rails-layout .cast-node {
    min-height: 0;
  }
  .rail-board {
    min-height: 0;
    display: grid;
    grid-template-rows: repeat(3, minmax(80px, 1.25fr)) repeat(7, minmax(52px, .72fr));
    gap: 5px;
    overflow: hidden;
  }
  .rail {
    min-width: 0;
    display: grid;
    grid-template-columns: 96px minmax(0, 1fr);
    gap: 5px;
    align-items: stretch;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    overflow: hidden;
  }
  .rail-label {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 5px;
    background: #f8fbff;
    color: var(--muted);
    font-weight: 950;
    text-transform: uppercase;
    border-right: 1px solid var(--line);
  }
  .rail-label strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rail-items {
    min-height: 0;
    display: flex;
    flex-wrap: wrap;
    align-content: center;
    gap: 4px;
    padding: 4px;
    overflow: hidden;
  }
  .rail-token {
    min-width: 0;
    display: inline-grid;
    grid-template-columns: auto auto auto minmax(76px, 1fr);
    align-items: center;
    gap: 3px;
    border: 1px solid var(--soft);
    border-radius: 7px;
    background: #fff;
    padding: 2px;
  }
  .rail-mon {
    grid-template-columns: 18px minmax(0, 1fr) auto;
  }
  .rail-mon .chip-label {
    display: none;
  }
  @media (max-width: 1180px) {
    .topbar {
      grid-template-columns: auto auto minmax(0, 1fr) auto;
    }
    .meta { display: none; }
    .flow-layout,
    .mosaic-layout,
    .rails-layout {
      overflow: auto;
      grid-template-columns: 1fr;
      grid-template-rows: auto auto auto;
      scrollbar-gutter: stable;
    }
    .flow-layout .grass-panel,
    .flow-layout .method-decks,
    .flow-layout .cast-panel,
    .mosaic-grass,
    .mosaic-layout .cast-panel,
    .mosaic-layout .method-decks {
      grid-column: auto;
      grid-row: auto;
    }
    .method-decks,
    .mosaic-layout .method-decks {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      grid-template-rows: none;
      grid-auto-rows: auto;
    }
  }
  @media (max-width: 760px) {
    .preview {
      block-size: 100dvh;
      grid-template-rows: auto minmax(0, 1fr);
      padding: 4px;
    }
    .topbar {
      grid-template-columns: auto minmax(0, 1fr) auto;
      grid-auto-rows: auto;
    }
    .topbar strong { display: none; }
    .route-name { font-size: 16px; }
    .rate-row {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
    }
    .body {
      overflow: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable;
    }
    .grass-flow,
    .grass-mosaic {
      grid-template-columns: 1fr;
      grid-template-rows: none;
      grid-auto-rows: auto;
    }
    .grass-slot {
      min-height: 42px;
      grid-template-columns: 106px minmax(0, 1fr);
    }
    .time-cluster {
      flex-wrap: wrap;
      padding-block: 4px;
    }
    .method-decks,
    .mosaic-layout .method-decks {
      grid-template-columns: 1fr;
    }
    .cast-cloud {
      grid-template-columns: 1fr;
      overflow: visible;
    }
    .rail-board {
      grid-template-rows: none;
      grid-auto-rows: auto;
    }
    .rail {
      grid-template-columns: 1fr;
    }
    .rail-label {
      min-height: 24px;
      border-right: 0;
      border-bottom: 1px solid var(--line);
    }
  }
"""


def build_html(route: dict) -> str:
    script = r"""
      const ids = ['k', 'l', 'm'];
      function activate() {
        const candidate = (location.hash || '#k').slice(1).toLowerCase();
        const id = ids.includes(candidate) ? candidate : 'k';
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
        '<title>Route 30 Visual Compact Variants</title><style>'
        + CSS
        + '</style></head><body>'
        + variant_k(route)
        + variant_l(route)
        + variant_m(route)
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
