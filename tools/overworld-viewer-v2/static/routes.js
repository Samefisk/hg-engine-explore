const ROUTE_SPECIES_LIST_ID = "v2-route-species-options";
const ROUTE_FILTER_STORAGE_KEY = "ow-v2-route-filters";
const ROUTE_SECTION_STORAGE_KEY = "ow-v2-route-sections";

const ROUTE_METHODS = [
  { key: "grass", label: "Grass", short: "G" },
  { key: "morning", label: "Grass AM", short: "AM" },
  { key: "day", label: "Grass Day", short: "D" },
  { key: "night", label: "Grass Night", short: "N" },
  { key: "surf", label: "Surf", short: "S" },
  { key: "rockSmash", label: "Rock smash", short: "R" },
  { key: "headbuttNormal", label: "Headbutt", short: "H" },
  { key: "headbuttSpecial", label: "Special trees", short: "H+" },
  { key: "oldRod", label: "Old rod", short: "1" },
  { key: "goodRod", label: "Good rod", short: "2" },
  { key: "superRod", label: "Super rod", short: "3" },
  { key: "hoenn", label: "Hoenn sound", short: "Ho" },
  { key: "sinnoh", label: "Sinnoh sound", short: "Si" },
  { key: "swarms", label: "Swarms", short: "Sw" },
];

const METHOD_META = new Map(ROUTE_METHODS.map((method) => [method.key, method]));
const DEFAULT_FILTERS = new Set([
  "grass", "morning", "day", "night", "surf", "rockSmash", "headbuttNormal", "headbuttSpecial",
  "oldRod", "goodRod", "superRod",
]);
const SOURCE_ORDER = [
  "morning", "day", "night", "surf", "oldRod", "goodRod", "superRod", "rockSmash",
  "headbuttNormal", "headbuttSpecial", "hoenn", "sinnoh", "swarms",
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function compact(value) {
  return String(value ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function shortSpeciesSymbol(symbol) {
  return String(symbol || "").replace(/^SPECIES_/, "");
}

function elementFrom(elements, key, id = key) {
  return elements?.[key] || document.getElementById(id);
}

function currentData(state, supplied) {
  if (supplied?.routes || supplied?.speciesOptions || supplied?.spawnSettings) return supplied;
  if (supplied?.data) return supplied.data;
  return state?.data || state?.appData || state?.workspaceData || state || {};
}

function icon(species, className = "v2-mon-icon", alt = "") {
  if (!species?.iconUrl) return `<span class="${escapeHtml(className)} v2-mon-icon--empty" aria-hidden="true"></span>`;
  return `<img class="${escapeHtml(className)}" src="${escapeHtml(species.iconUrl)}" alt="${escapeHtml(alt)}" loading="lazy">`;
}

function methodMark(key) {
  const common = 'viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"';
  const icons = {
    grass: `<svg ${common}><path d="M4 14c5 0 9-3 11-9-6 0-10 3-11 9Z"/><path d="M5 15c2-3 5-5 9-7"/></svg>`,
    morning: `<svg ${common}><path d="M3 15h14M5 12h10M7 9a3 3 0 0 1 6 0"/><path d="M10 3v2M4.5 6l1.5 1M15.5 6 14 7"/></svg>`,
    day: `<svg ${common}><circle cx="10" cy="10" r="3.2"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.4 1.4M14.3 14.3l1.4 1.4M15.7 4.3l-1.4 1.4M5.7 14.3l-1.4 1.4"/></svg>`,
    night: `<svg ${common}><path d="M14.5 14.7A6.5 6.5 0 0 1 8.2 4.1 6 6 0 1 0 14.5 14.7Z"/></svg>`,
    surf: `<svg ${common}><path d="M2 7c2-2 4 2 6 0s4 2 6 0 3 1 4 0M2 12c2-2 4 2 6 0s4 2 6 0 3 1 4 0"/></svg>`,
    rockSmash: `<svg ${common}><path d="m5 14 7-7 3 3-7 7H5v-3Z"/><path d="m11 6 2-2 3 3-2 2"/></svg>`,
    headbuttNormal: `<svg ${common}><path d="M10 17V9M6 17h8M4 10c-2-4 2-7 5-5 2-4 7-2 7 2 3 1 2 6-1 6H6c-3 0-4-2-2-3Z"/></svg>`,
    headbuttSpecial: `<svg ${common}><path d="M7 17V9M13 17v-6M3 10c-1-4 3-6 5-3 1-3 5-2 5 1 3 0 4 4 1 5H5c-2 0-3-2-2-3Z"/><path d="M11 5h5M13.5 2.5v5"/></svg>`,
    oldRod: `<svg ${common}><circle cx="10" cy="10" r="2.2"/></svg>`,
    goodRod: `<svg ${common}><circle cx="7" cy="10" r="2"/><circle cx="13" cy="10" r="2"/></svg>`,
    superRod: `<svg ${common}><circle cx="5" cy="10" r="1.7"/><circle cx="10" cy="10" r="1.7"/><circle cx="15" cy="10" r="1.7"/></svg>`,
    hoenn: `<svg ${common}><path d="M8 15V5l7-1v9"/><circle cx="6" cy="15" r="2"/><circle cx="13" cy="13" r="2"/></svg>`,
    sinnoh: `<svg ${common}><path d="M7 15V6l7 2v6"/><circle cx="5" cy="15" r="2"/><circle cx="12" cy="14" r="2"/></svg>`,
    swarms: `<svg ${common}><path d="M10 2v4M10 14v4M2 10h4M14 10h4M4.4 4.4l2.8 2.8M12.8 12.8l2.8 2.8M15.6 4.4l-2.8 2.8M7.2 12.8l-2.8 2.8"/></svg>`,
  };
  return `<span class="v2-method-mark" data-method="${escapeHtml(key)}" aria-hidden="true">${icons[key] || escapeHtml(METHOD_META.get(key)?.short || "•")}</span>`;
}

function mapLabel(route) {
  const maps = asArray(route?.maps);
  if (!maps.length) return "No mapped area";
  return maps.map((map) => map.symbol || map.name).filter(Boolean).join(", ");
}

function notify(setStatus, message, tone = "ready") {
  if (typeof setStatus === "function") setStatus(message, tone);
}

function numberIsValid(raw, min, max) {
  const value = Number(String(raw).trim());
  return String(raw).trim() !== ""
    && Number.isInteger(value)
    && (min == null || value >= Number(min))
    && (max == null || value <= Number(max));
}

function loadSet(key, fallback) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "null");
    if (Array.isArray(parsed)) return new Set(parsed);
  } catch (_error) {
    // A corrupt preference should never prevent the editor from loading.
  }
  return new Set(fallback);
}

function saveSet(key, values) {
  try {
    localStorage.setItem(key, JSON.stringify([...values]));
  } catch (_error) {
    // Private browsing and storage quotas are non-fatal for presentation state.
  }
}

async function ask(confirmAction, message) {
  if (typeof confirmAction === "function") {
    return Boolean(await Promise.resolve(confirmAction({
      title: "Turn off route-only encounter?",
      message,
      confirmLabel: "Turn off",
      danger: true,
    })));
  }
  if (typeof window !== "undefined" && typeof window.confirm === "function") return window.confirm(message);
  return true;
}

function baselineKey(routeId, path) {
  return `${routeId}\u0000${path}`;
}

function splitBaselineKey(key) {
  const separator = key.indexOf("\u0000");
  return [key.slice(0, separator), key.slice(separator + 1)];
}

export function createRoutesController({
  state: appState = {},
  api = null,
  elements = {},
  setStatus = null,
  markDirty = null,
  confirmAction = null,
  reportSelection = () => {},
  openPokemonRecord = () => false,
} = {}) {
  void api;
  const search = elementFrom(elements, "routeSearch");
  const filters = elementFrom(elements, "routeFilters");
  const library = elementFrom(elements, "routeLibrary");
  const inspector = elementFrom(elements, "routeInspector");
  const routeCount = elements?.routeCount
    || library?.closest(".library-panel")?.querySelector("[data-route-count]")
    || null;
  const abort = new AbortController();

  const model = {
    data: {},
    routes: [],
    routesById: new Map(),
    selectedRouteId: null,
    query: "",
    encounterDrafts: new Map(),
    overrideDrafts: new Map(),
    spawnDrafts: new Map(),
    baselines: new Map(),
    species: [],
    speciesByLookup: new Map(),
    speciesByBaseForm: new Map(),
    methodFilters: loadSet(ROUTE_FILTER_STORAGE_KEY, DEFAULT_FILTERS),
    openSections: loadSet(ROUTE_SECTION_STORAGE_KEY, ["grass", "sources"]),
    invalidInputs: new Map(),
    entryEditor: null,
    overrideEditor: false,
    spawnEditor: false,
  };

  function signalDirty() {
    if (typeof markDirty === "function") markDirty();
  }

  function invalidKey(kind, owner, path = "") {
    return `${kind}:${owner}:${path}`;
  }

  function markInvalid(key, message, invalid) {
    if (invalid) model.invalidInputs.set(key, message);
    else model.invalidInputs.delete(key);
    signalDirty();
  }

  function selectedRoute() {
    return model.routesById.get(String(model.selectedRouteId)) || model.routes[0] || null;
  }

  function baseline(routeId, path, fallback = "") {
    return model.baselines.get(baselineKey(routeId, path)) ?? String(fallback ?? "");
  }

  function effective(routeId, path, fallback = "") {
    const key = baselineKey(routeId, path);
    return model.encounterDrafts.has(key)
      ? model.encounterDrafts.get(key)
      : baseline(routeId, path, fallback);
  }

  function setEncounterDraft(routeId, path, value, fallback = "") {
    if (!path) return;
    const key = baselineKey(routeId, path);
    const normalized = String(value ?? "").trim();
    if (normalized === baseline(routeId, path, fallback)) model.encounterDrafts.delete(key);
    else model.encounterDrafts.set(key, normalized);
  }

  function setSpawnDraft(symbol, value, original) {
    const normalized = String(value ?? "").trim();
    if (normalized === String(original ?? "")) model.spawnDrafts.delete(symbol);
    else model.spawnDrafts.set(symbol, normalized);
  }

  function addBaseline(routeId, path, value) {
    if (path) model.baselines.set(baselineKey(routeId, path), String(value ?? ""));
  }

  function indexRoute(route) {
    const routeId = String(route.id);
    asArray(route.rates).forEach((item) => addBaseline(routeId, item.path, item.value));
    asArray(route.grassLevels).forEach((item) => addBaseline(routeId, item.path, item.value));
    asArray(route.pokemonTables).forEach((table) => asArray(table.slots).forEach((slot) => {
      addBaseline(routeId, slot.path, slot.species?.symbol);
      addBaseline(routeId, slot.formPath, slot.form || 0);
    }));
    [...asArray(route.slotTables), ...asArray(route.headbuttTables)].forEach((table) => {
      asArray(table.slots).forEach((slot) => {
        addBaseline(routeId, slot.paths?.species, slot.species?.symbol);
        addBaseline(routeId, slot.paths?.form, slot.form || 0);
        addBaseline(routeId, slot.paths?.minLevel, slot.minLevel);
        addBaseline(routeId, slot.paths?.maxLevel, slot.maxLevel);
      });
    });
    asArray(route.swarms).forEach((swarm) => {
      addBaseline(routeId, swarm.path, swarm.species?.symbol);
      addBaseline(routeId, swarm.formPath, swarm.form || 0);
    });
  }

  function registerSpecies(option) {
    const symbol = String(option?.symbol || "").toUpperCase();
    if (!symbol) return;
    [symbol, shortSpeciesSymbol(symbol), option.name, ...asArray(option.aliases)].forEach((name) => {
      if (!name) return;
      [String(name).toLowerCase(), compact(name)].forEach((key) => {
        if (!model.speciesByLookup.has(key)) model.speciesByLookup.set(key, option);
      });
    });
    const base = option.baseSymbol || option.symbol;
    model.speciesByBaseForm.set(`${base}|${Number(option.form || 0)}`, option);
  }

  function resolveSpecies(raw) {
    const value = String(raw || "").trim();
    if (!value) return null;
    return model.speciesByLookup.get(value.toLowerCase())
      || model.speciesByLookup.get(compact(value))
      || model.speciesByLookup.get(`species_${value}`.toLowerCase())
      || null;
  }

  function displaySpecies(symbol, form = 0) {
    return model.speciesByBaseForm.get(`${symbol}|${Number(form || 0)}`)
      || resolveSpecies(symbol)
      || { symbol, name: shortSpeciesSymbol(symbol) || "None", form: Number(form || 0) };
  }

  function speciesWrite(option) {
    return {
      symbol: option?.baseSymbol || option?.symbol || "SPECIES_NONE",
      form: String(option?.baseSymbol ? Number(option.form || 0) : 0),
    };
  }

  function speciesIdentity(symbol, form = 0) {
    return `${symbol || "SPECIES_NONE"}|${Number(form || 0)}`;
  }

  function routeChangeCount(routeId) {
    const routeKey = String(routeId);
    let count = model.overrideDrafts.has(routeKey) ? 1 : 0;
    for (const key of model.encounterDrafts.keys()) {
      if (splitBaselineKey(key)[0] === routeKey) count += 1;
    }
    return count;
  }

  function routeValidationCount(routeId) {
    const marker = `:${routeId}:`;
    return [...model.invalidInputs.keys()].filter((key) => key.includes(marker)).length;
  }

  function targetFromPokemon(route, table, slot, index) {
    const level = ["morning", "day", "night"].includes(table.key) ? route.grassLevels?.[index] : null;
    const symbol = effective(route.id, slot.path, slot.species?.symbol);
    const form = effective(route.id, slot.formPath, slot.form || 0);
    return {
      groupKey: table.key,
      groupLabel: table.label,
      slot: slot.slot,
      weight: slot.weight,
      path: slot.path,
      formPath: slot.formPath,
      originalSymbol: baseline(route.id, slot.path, slot.species?.symbol),
      originalForm: baseline(route.id, slot.formPath, slot.form || 0),
      symbol,
      form,
      option: displaySpecies(symbol, form),
      levelPath: level?.path || "",
      originalLevel: level ? baseline(route.id, level.path, level.value) : "",
      level: level ? effective(route.id, level.path, level.value) : "",
      enabled: !level || Number(effective(route.id, level.path, level.value)) !== 0,
      kind: "pokemon",
    };
  }

  function targetFromSlot(route, table, slot) {
    const symbol = effective(route.id, slot.paths?.species, slot.species?.symbol);
    const form = effective(route.id, slot.paths?.form, slot.form || 0);
    const minLevel = effective(route.id, slot.paths?.minLevel, slot.minLevel);
    const maxLevel = effective(route.id, slot.paths?.maxLevel, slot.maxLevel);
    return {
      groupKey: table.key,
      groupLabel: table.label,
      slot: slot.slot,
      weight: slot.weight,
      path: slot.paths?.species,
      formPath: slot.paths?.form,
      originalSymbol: baseline(route.id, slot.paths?.species, slot.species?.symbol),
      originalForm: baseline(route.id, slot.paths?.form, slot.form || 0),
      symbol,
      form,
      option: displaySpecies(symbol, form),
      minPath: slot.paths?.minLevel,
      maxPath: slot.paths?.maxLevel,
      originalMin: baseline(route.id, slot.paths?.minLevel, slot.minLevel),
      originalMax: baseline(route.id, slot.paths?.maxLevel, slot.maxLevel),
      minLevel,
      maxLevel,
      enabled: Number(minLevel) !== 0,
      kind: "slot",
    };
  }

  function sourceGroups(route) {
    const groups = new Map();
    asArray(route.pokemonTables).forEach((table) => {
      groups.set(table.key, {
        key: table.key,
        label: METHOD_META.get(table.key)?.label || table.label,
        targets: asArray(table.slots).map((slot, index) => targetFromPokemon(route, table, slot, index)),
      });
    });
    [...asArray(route.slotTables), ...asArray(route.headbuttTables)].forEach((table) => {
      groups.set(table.key, {
        key: table.key,
        label: METHOD_META.get(table.key)?.label || table.label,
        targets: asArray(table.slots).map((slot) => targetFromSlot(route, table, slot)),
        treeCount: table.treeCount,
      });
    });
    if (asArray(route.swarms).length) {
      groups.set("swarms", {
        key: "swarms",
        label: "Swarms",
        targets: asArray(route.swarms).map((swarm, index) => {
          const symbol = effective(route.id, swarm.path, swarm.species?.symbol);
          const form = effective(route.id, swarm.formPath, swarm.form || 0);
          return {
            groupKey: "swarms",
            groupLabel: swarm.label || "Swarms",
            swarmKey: swarm.key,
            slot: index + 1,
            weight: null,
            path: swarm.path,
            formPath: swarm.formPath,
            originalSymbol: baseline(route.id, swarm.path, swarm.species?.symbol),
            originalForm: baseline(route.id, swarm.formPath, swarm.form || 0),
            symbol,
            form,
            option: displaySpecies(symbol, form),
            levelLabel: String(swarm.label || "").replace(/ swarm$/i, ""),
            enabled: true,
            kind: "swarm",
          };
        }),
      });
    }
    return SOURCE_ORDER.map((key) => groups.get(key)).filter(Boolean);
  }

  function uniqueTargetSpecies(targets, allowed = null) {
    const seen = new Set();
    const result = [];
    targets.forEach((target) => {
      const identity = speciesIdentity(target.symbol, target.form);
      if (target.symbol === "SPECIES_NONE" || seen.has(identity) || (allowed && !allowed.has(identity))) return;
      seen.add(identity);
      result.push({ identity, option: target.option, symbol: target.symbol, form: target.form });
    });
    return result;
  }

  function sidebarGroups(route) {
    const groups = sourceGroups(route);
    const byKey = new Map(groups.map((group) => [group.key, group]));
    const grassGroups = ["morning", "day", "night"].map((key) => byKey.get(key));
    let common = new Set();
    if (grassGroups.every(Boolean)) {
      const sets = grassGroups.map((group) => new Set(uniqueTargetSpecies(group.targets).map((entry) => entry.identity)));
      common = new Set([...sets[0]].filter((identity) => sets.slice(1).every((set) => set.has(identity))));
    }
    const output = [];
    if (common.size) {
      output.push({
        key: "grass",
        label: METHOD_META.get("grass").label,
        species: uniqueTargetSpecies(grassGroups[0].targets, common),
      });
    }
    groups.forEach((group) => {
      let species = uniqueTargetSpecies(group.targets);
      if (["morning", "day", "night"].includes(group.key) && common.size) {
        species = species.filter((entry) => !common.has(entry.identity));
      }
      if (species.length) output.push({ key: group.key, label: group.label, species });
    });
    return output;
  }

  function speciesSearchText(entry) {
    const option = entry.option || displaySpecies(entry.symbol, entry.form);
    return [
      entry.symbol,
      option?.symbol,
      option?.name,
      ...asArray(option?.aliases),
      ...asArray(option?.types).flatMap((type) => [type?.name, type?.symbol]),
    ].join(" ").toLowerCase();
  }

  function routeFilterState(route) {
    const groups = sidebarGroups(route);
    const enabledGroups = groups.filter((group) => model.methodFilters.has(group.key));
    const identityText = [
      route.id,
      route.name,
      ...asArray(route.maps).flatMap((map) => [map.name, map.symbol]),
    ].join(" ").toLowerCase();
    const query = model.query;
    const identityMatch = Boolean(query && (identityText.includes(query) || compact(identityText).includes(compact(query))));
    const groupMatch = Boolean(query && enabledGroups.some((group) => {
      const text = [group.key, group.label, ...group.species.map(speciesSearchText)].join(" ").toLowerCase();
      return text.includes(query) || compact(text).includes(compact(query));
    }));
    return {
      groups,
      enabledGroups,
      identityMatch,
      visible: enabledGroups.length ? (!query || identityMatch || groupMatch) : identityMatch,
    };
  }

  function currentOverride(route) {
    const pending = model.overrideDrafts.get(String(route.id));
    if (pending?.action === "clear") return null;
    return pending?.action === "set" ? pending : route.encounterOverride || null;
  }

  function renderFilters() {
    if (!filters) return;
    filters.innerHTML = `
      <legend class="sr-only">Encounter method filters</legend>
      <button class="v2-route-settings-trigger" type="button" data-action="open-spawn-settings">Spawn settings</button>
      ${ROUTE_METHODS.map((method) => {
        const active = model.methodFilters.has(method.key);
        return `<button class="filter-chip v2-route-filter${active ? " is-active" : ""}" type="button"
          data-route-filter="${escapeHtml(method.key)}" aria-pressed="${active}" title="${escapeHtml(method.label)}">
          ${methodMark(method.key)}<span>${escapeHtml(method.label)}</span>
        </button>`;
      }).join("")}`;
  }

  function renderOverrideButton(route, compact = false) {
    const current = currentOverride(route);
    const option = current ? displaySpecies(current.species, current.form || 0) : null;
    const changed = model.overrideDrafts.has(String(route.id));
    const label = option ? `Only ${option.name || shortSpeciesSymbol(option.symbol)}` : "Set route-only encounter";
    return `<button class="v2-route-override-button${compact ? " is-compact" : ""}${current ? " is-active" : ""}${changed ? " is-dirty" : ""}"
      type="button" data-action="open-route-override" data-route-id="${escapeHtml(route.id)}" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">
      <span class="v2-method-mark" aria-hidden="true">◎</span>${option ? icon(option, "v2-route-sprite") : "<span aria-hidden=\"true\">+</span>"}
      ${compact ? "" : `<span>${escapeHtml(option ? `Only ${option.name}` : "Route-only")}</span>`}
    </button>`;
  }

  function renderSidebarGroup(route, group) {
    const meta = METHOD_META.get(group.key) || { short: group.label, label: group.label };
    const query = model.query;
    const methodText = `${group.key} ${group.label}`.toLowerCase();
    const groupMatch = Boolean(query && (methodText.includes(query) || compact(methodText).includes(compact(query)) || group.species.some((entry) => {
      const text = speciesSearchText(entry);
      return text.includes(query) || compact(text).includes(compact(query));
    })));
    return `<span class="v2-route-method-group${groupMatch ? " is-search-match" : ""}" data-group-key="${escapeHtml(group.key)}" title="${escapeHtml(group.label)}">
      ${methodMark(group.key)}
      <span class="v2-route-method-species">${group.species.map((entry) => {
        const option = entry.option;
        const match = Boolean(query && (speciesSearchText(entry).includes(query) || compact(speciesSearchText(entry)).includes(compact(query))));
        return `<span class="v2-route-species-chip${match ? " is-search-match" : ""}"><button class="v2-route-sprite-button" type="button"
          data-route-wide-edit="${escapeHtml(group.key)}" data-route-id="${escapeHtml(route.id)}"
          data-species-identity="${escapeHtml(entry.identity)}" aria-label="Edit ${escapeHtml(option?.name || shortSpeciesSymbol(entry.symbol))} across this route">
          ${icon(option, "v2-route-sprite")}
        </button></span>`;
      }).join("")}</span>
    </span>`;
  }

  function renderLibrary() {
    if (!library) return;
    const previousScroll = library.scrollTop;
    const visible = model.routes.map((route) => ({ route, state: routeFilterState(route) })).filter((entry) => entry.state.visible);
    if (routeCount) routeCount.textContent = `${visible.length}/${model.routes.length}`;
    library.innerHTML = visible.length ? visible.map(({ route, state }) => {
      const selected = String(route.id) === String(model.selectedRouteId);
      const edits = routeChangeCount(route.id);
      const speciesCount = new Set(sourceGroups(route).flatMap((group) => group.targets)
        .filter((target) => target.symbol !== "SPECIES_NONE")
        .map((target) => speciesIdentity(target.symbol, target.form))).size;
      const errors = routeValidationCount(route.id);
      return `<article class="v2-route-list-row${selected ? " is-selected" : ""}${edits ? " is-dirty" : ""}${errors ? " is-invalid" : ""}" data-route-row="${escapeHtml(route.id)}">
        <button class="v2-route-select" type="button" data-route-select="${escapeHtml(route.id)}" aria-pressed="${selected}">
          <span class="v2-route-list-id">#${escapeHtml(route.id)}</span>
          <span class="v2-route-list-copy"><strong>${escapeHtml(route.name)}</strong><small>${escapeHtml(mapLabel(route))} · ${speciesCount} species${edits ? ` · ${edits} changed` : ""}${errors ? ` · ${errors} error${errors === 1 ? "" : "s"}` : ""}</small></span>
        </button>
        <span class="v2-route-group-strip" aria-label="Encounter methods">
          ${renderOverrideButton(route, true)}
          ${state.enabledGroups.map((group) => renderSidebarGroup(route, group)).join("")}
        </span>
      </article>`;
    }).join("") : `<p class="v2-route-empty">No routes match the active methods and search.</p>`;
    library.scrollTop = previousScroll;
  }

  function sourceGroup(route, key) {
    return sourceGroups(route).find((group) => group.key === key) || null;
  }

  function encounterTargets(route, { includeDisabled = false } = {}) {
    return sourceGroups(route).flatMap((group) => group.targets).filter((target) => {
      if (!includeDisabled && !target.enabled) return false;
      return target.path && target.formPath && target.symbol !== "SPECIES_NONE";
    });
  }

  function levelText(target) {
    if (target.levelPath) return target.level === "" ? "" : `Lv ${target.level}`;
    if (target.minPath) return String(target.minLevel) === String(target.maxLevel)
      ? `Lv ${target.minLevel}`
      : `Lv ${target.minLevel}–${target.maxLevel}`;
    return target.levelLabel || "";
  }

  function aggregateTargets(targets) {
    const aggregates = new Map();
    targets.forEach((target, index) => {
      const identity = speciesIdentity(target.symbol, target.form);
      const current = aggregates.get(identity) || {
        identity,
        symbol: target.symbol,
        form: target.form,
        option: target.option,
        rate: 0,
        hasRate: false,
        levels: new Set(),
        targets: [],
        firstIndex: index,
      };
      const rate = Number(target.weight);
      if (target.weight !== null && target.weight !== undefined && target.weight !== "" && Number.isFinite(rate)) {
        current.rate += rate;
        current.hasRate = true;
      }
      const level = levelText(target);
      if (level) current.levels.add(level);
      current.targets.push(target);
      aggregates.set(identity, current);
    });
    return [...aggregates.values()].sort((left, right) => {
      if (left.hasRate || right.hasRate) return right.rate - left.rate || left.firstIndex - right.firstIndex;
      return left.firstIndex - right.firstIndex;
    });
  }

  function formatRate(value) {
    const rounded = Math.round(Number(value) * 10) / 10;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  }

  function summaryChip(route, group, aggregate, totalRate, aggregateCount) {
    const invalid = model.invalidInputs.has(invalidKey("summary", route.id, `${group.key}:${aggregate.identity}`));
    const levels = [...aggregate.levels].map((value) => value.replace(/^Lv\s*/, "")).slice(0, 4).join(", ");
    const share = aggregate.hasRate
      ? (totalRate > 0 ? aggregate.rate / totalRate : 1 / Math.max(1, aggregateCount))
      : 1;
    const normalizedRate = aggregate.hasRate && totalRate > 0 ? share * 100 : 0;
    const rate = aggregate.hasRate ? `${formatRate(normalizedRate)}%` : `${aggregate.targets.length}×`;
    const changed = aggregate.targets.some((target) => (
      effective(route.id, target.path, target.originalSymbol) !== target.originalSymbol
      || effective(route.id, target.formPath, target.originalForm) !== target.originalForm
    ));
    const searchText = speciesSearchText(aggregate);
    const searchMatch = Boolean(model.query && (searchText.includes(model.query) || compact(searchText).includes(compact(model.query))));
    const meter = aggregate.hasRate ? Math.max(0, Math.min(100, normalizedRate)) : 0;
    const rateClass = meter <= 8 ? "rate-tiny" : meter <= 18 ? "rate-small" : meter <= 34 ? "rate-medium" : "rate-large";
    const compactWidth = meter <= 0 ? 46 : Math.round(42 + (meter * 4));
    const speciesLabel = aggregate.option?.name || shortSpeciesSymbol(aggregate.symbol);
    return `<div class="v2-encounter-chip ${rateClass}${changed ? " is-dirty" : ""}${aggregate.symbol === "SPECIES_NONE" ? " is-empty" : ""}${searchMatch ? " is-search-match" : ""}" style="--summary-rate:${meter}%;--summary-compact-width:${compactWidth}px">
      <button class="v2-encounter-chip-visual" type="button" data-route-group-edit="${escapeHtml(group.key)}"
        data-route-id="${escapeHtml(route.id)}" data-species-identity="${escapeHtml(aggregate.identity)}"
        title="${escapeHtml(speciesLabel)}" aria-label="Edit ${escapeHtml(speciesLabel)} entries in ${escapeHtml(group.label)}">
        <strong>${escapeHtml(rate)}</strong>${icon(aggregate.option, "v2-summary-sprite")}<small>${escapeHtml(levels)}</small>
      </button>
      <input type="text" list="${ROUTE_SPECIES_LIST_ID}" value="${escapeHtml(shortSpeciesSymbol(aggregate.option?.symbol || aggregate.symbol))}"
        data-route-summary-species data-route-id="${escapeHtml(route.id)}" data-group-key="${escapeHtml(group.key)}"
        data-species-identity="${escapeHtml(aggregate.identity)}" autocomplete="off" title="${escapeHtml(speciesLabel)}"
        aria-label="Replace ${escapeHtml(speciesLabel)} in ${escapeHtml(group.label)}" aria-invalid="${invalid}">
      ${aggregate.symbol !== "SPECIES_NONE" ? `<button class="v2-pokemon-jump v2-pokemon-jump--chip" type="button" data-open-pokemon="${escapeHtml(aggregate.option?.symbol || aggregate.symbol)}" aria-label="Open ${escapeHtml(speciesLabel)} in Pokémon Editor" title="Open in Pokémon Editor">↗</button>` : ""}
    </div>`;
  }

  function summaryRow(route, group) {
    const aggregates = aggregateTargets(group.targets);
    const totalRate = aggregates.reduce((total, aggregate) => total + (aggregate.hasRate ? aggregate.rate : 0), 0);
    const methodText = `${group.key} ${group.label}`.toLowerCase();
    const searchMatch = Boolean(model.query && (methodText.includes(model.query) || compact(methodText).includes(compact(model.query))));
    return `<article class="v2-encounter-summary-row v2-source-${escapeHtml(group.key)}${searchMatch ? " is-search-match" : ""}">
      <header><button class="v2-encounter-group-edit" type="button" data-route-group-edit-all="${escapeHtml(group.key)}" data-route-id="${escapeHtml(route.id)}" aria-label="Edit all ${escapeHtml(group.label)} encounter slots">${methodMark(group.key)}<span><strong>${escapeHtml(group.label)}</strong><small>${group.targets.length} slots</small></span></button></header>
      <div class="v2-encounter-summary-chips">${aggregates.length
        ? aggregates.map((aggregate) => summaryChip(route, group, aggregate, totalRate, aggregates.length)).join("")
        : "<span class=\"v2-summary-empty\">No encounters</span>"}</div>
    </article>`;
  }

  function section(route, key, title, groups) {
    const open = model.openSections.has(key);
    const count = groups.reduce((total, group) => total + group.targets.length, 0);
    return `<details class="v2-route-summary-section" data-route-section="${escapeHtml(key)}"${open ? " open" : ""}>
      <summary><span>${escapeHtml(title)}</span><small>${count} source slots</small></summary>
      <div class="v2-route-summary-body">${groups.map((group) => summaryRow(route, group)).join("")}</div>
    </details>`;
  }

  function renderRateField(route, rate) {
    const raw = effective(route.id, rate.path, rate.value);
    const changed = raw !== String(rate.value ?? "");
    const invalid = model.invalidInputs.has(invalidKey("route", route.id, rate.path));
    const method = String(rate.key || "").replace(/rate$/i, "");
    const methodKey = method.includes("walk") ? "grass" : method.includes("surf") ? "surf" : method.includes("rock") ? "rockSmash" : method.includes("old") ? "oldRod" : method.includes("good") ? "goodRod" : "superRod";
    return `<label class="v2-route-rate${changed ? " is-dirty" : ""}" title="${escapeHtml(rate.label)}">
      ${methodMark(methodKey)}<input type="number" min="0" max="100" step="1" value="${escapeHtml(raw)}"
        data-route-number data-route-id="${escapeHtml(route.id)}" data-path="${escapeHtml(rate.path)}" data-original="${escapeHtml(rate.value)}"
        aria-label="${escapeHtml(rate.label)} rate" aria-invalid="${invalid}">
    </label>`;
  }

  function renderOverview(route) {
    return `<div class="v2-route-overview-strip" aria-label="Encounter overview">${sidebarGroups(route).map((group) => renderSidebarGroup(route, group)).join("")}</div>`;
  }

  function speciesOptions() {
    return `<datalist id="${ROUTE_SPECIES_LIST_ID}">${model.species.map((species) =>
      `<option value="${escapeHtml(shortSpeciesSymbol(species.symbol))}">${escapeHtml(species.name || species.symbol)}</option>`
    ).join("")}</datalist>`;
  }

  function inputNumber(routeId, path, value, label, min = 0, max = 100) {
    const raw = effective(routeId, path, value);
    const changed = raw !== String(value ?? "");
    const invalid = model.invalidInputs.has(invalidKey("route", routeId, path))
      || model.invalidInputs.has(invalidKey("level-range", routeId, String(path || "").replace(/\.(min|max)Level$/, "")));
    return `<label class="v2-entry-field${changed ? " is-dirty" : ""}"><span>${escapeHtml(label)}</span>
      <input type="number" min="${escapeHtml(min)}" max="${escapeHtml(max)}" step="1" value="${escapeHtml(raw)}"
        data-route-number data-route-id="${escapeHtml(routeId)}" data-path="${escapeHtml(path)}" data-original="${escapeHtml(value)}" aria-invalid="${invalid}">
    </label>`;
  }

  function speciesInput(routeId, target) {
    const option = displaySpecies(effective(routeId, target.path, target.originalSymbol), effective(routeId, target.formPath, target.originalForm));
    const changed = target.symbol !== target.originalSymbol || String(target.form) !== String(target.originalForm);
    const invalid = model.invalidInputs.has(invalidKey("species", routeId, target.path));
    return `<label class="v2-entry-species${changed ? " is-dirty" : ""}">
      ${icon(option, "v2-entry-sprite")}
      <span><small>Pokémon</small><input type="text" list="${ROUTE_SPECIES_LIST_ID}" value="${escapeHtml(shortSpeciesSymbol(option.symbol || target.symbol))}"
        data-route-species data-route-id="${escapeHtml(routeId)}" data-path="${escapeHtml(target.path)}" data-form-path="${escapeHtml(target.formPath)}"
        data-original="${escapeHtml(target.originalSymbol)}" data-form-original="${escapeHtml(target.originalForm)}" autocomplete="off" aria-invalid="${invalid}"></span>
      <span><small>Form</small><input type="number" min="0" max="31" step="1" value="${escapeHtml(target.form)}"
        data-route-number data-route-id="${escapeHtml(routeId)}" data-path="${escapeHtml(target.formPath)}" data-original="${escapeHtml(target.originalForm)}"
        aria-invalid="${model.invalidInputs.has(invalidKey("route", routeId, target.formPath))}"></span>
    </label>`;
  }

  function renderEntryEditor(route) {
    const editor = model.entryEditor;
    if (!editor || String(editor.routeId) !== String(route.id)) return "";
    const group = sourceGroup(route, editor.groupKey);
    const allTargets = sourceGroups(route).flatMap((source) => source.targets);
    const targets = editor.all
      ? (group?.targets || [])
      : (editor.wide ? allTargets : group?.targets || [])
        .filter((target) => speciesIdentity(target.symbol, target.form) === editor.identity);
    if (!targets.length) return "";
    const option = targets[0]?.option;
    const highlighted = targets.filter((target) => editor.groupKey === "grass"
      ? ["morning", "day", "night"].includes(target.groupKey)
      : target.groupKey === editor.groupKey);
    const contextLabel = editor.wide ? "Route-wide species swap" : (group?.label || targets[0]?.groupLabel || "Encounter source");
    const editorTitle = editor.all ? `Edit ${targets.length} encounter slots` : (option?.name || shortSpeciesSymbol(targets[0]?.symbol));
    return `<dialog class="v2-route-dialog v2-entry-dialog" data-route-entry-dialog aria-labelledby="v2EntryDialogTitle">
      <div class="v2-route-dialog-shell">
        <header><div><span class="v2-eyebrow">${escapeHtml(contextLabel)} · ${targets.length} ${editor.all ? "entries" : "matching entries"}</span><h2 id="v2EntryDialogTitle">${escapeHtml(editorTitle)}</h2></div>
          <button type="button" data-action="close-entry-editor" aria-label="Close entry editor">×</button></header>
        <div class="v2-entry-list">
          ${editor.wide ? `<div class="v2-entry-bulk">
            <label><span>Replace ${escapeHtml(option?.name || shortSpeciesSymbol(targets[0]?.symbol))} with</span><input type="text" list="${ROUTE_SPECIES_LIST_ID}" data-route-wide-species autocomplete="off" placeholder="Choose Pokémon"></label>
            <button type="button" data-action="swap-entry-highlighted">Swap ${highlighted.length} highlighted</button>
            <button type="button" data-action="swap-entry-all">Swap all ${targets.length}</button>
          </div>` : ""}
          ${targets.map((target) => {
            const isHighlighted = highlighted.includes(target);
            return `<article class="v2-entry-row${editor.wide && isHighlighted ? " is-highlighted" : ""}">
          <div class="v2-entry-meta">${methodMark(target.groupKey)}<strong>#${escapeHtml(target.slot)}</strong><span>${target.weight == null ? "overlay" : `${escapeHtml(formatRate(target.weight))}%`}</span>${editor.wide && isHighlighted ? '<span class="v2-entry-highlight-label" aria-hidden="true">Target</span><span class="sr-only">Highlighted for group swap.</span>' : ""}</div>
          ${speciesInput(route.id, target)}
          <div class="v2-entry-levels">${target.levelPath
            ? inputNumber(route.id, target.levelPath, target.originalLevel, "Level", 0, 100)
            : target.minPath
              ? `<fieldset class="v2-entry-range"><legend><span>Level range</span><small>levels</small></legend><span class="v2-entry-range-controls">${inputNumber(route.id, target.minPath, target.originalMin, "Min", 0, 100)}${inputNumber(route.id, target.maxPath, target.originalMax, "Max", 0, 100)}</span></fieldset>`
              : `<span>${escapeHtml(target.levelLabel || "No levels")}</span>`}</div>
        </article>`;
          }).join("")}</div>
        <footer><p>Changes are staged immediately and saved with the rest of the Route Deck.</p><button type="button" data-action="close-entry-editor">Done</button></footer>
      </div>
    </dialog>`;
  }

  function renderOverrideDialog(route) {
    if (!model.overrideEditor) return "";
    const current = currentOverride(route);
    const option = current ? displaySpecies(current.species, current.form || 0) : null;
    const invalid = model.invalidInputs.has(invalidKey("route-override", route.id));
    return `<dialog class="v2-route-dialog v2-override-dialog" data-route-override-dialog aria-labelledby="v2OverrideDialogTitle">
      <div class="v2-route-dialog-shell">
        <header><div><span class="v2-eyebrow">Single route layer</span><h2 id="v2OverrideDialogTitle">Route-only encounter</h2></div>
          <button type="button" data-action="close-route-override" aria-label="Close route-only editor">×</button></header>
        <div class="v2-override-editor">
          <div class="v2-override-copy"><strong>${escapeHtml(route.name)}</strong><p>Make one Pokémon the only enabled encounter on this route. The source entries are retained as one reversible baseline.</p></div>
          <label><span>Only encounter</span><input type="text" list="${ROUTE_SPECIES_LIST_ID}" value="${escapeHtml(option ? shortSpeciesSymbol(option.symbol) : "")}"
            data-route-override-input autocomplete="off" placeholder="Choose Pokémon" aria-invalid="${invalid}"></label>
        </div>
        <footer><button type="button" class="is-quiet" data-action="clear-route-override"${current ? "" : " disabled"}>Turn off</button><span></span>
          <button type="button" data-action="set-route-override">Apply to route</button></footer>
      </div>
    </dialog>`;
  }

  function spawnSettingRows(group) {
    const fields = asArray(group.settings).flatMap((setting) => (
      setting.kind === "testSpawn" ? asArray(setting.fields) : [setting]
    ));
    const bySymbol = new Map(fields.map((field) => [field.symbol, field]));
    const consumed = new Set();

    function fieldState(field) {
      const original = field.kind === "species" ? (field.symbolValue || field.raw) : field.value;
      const value = model.spawnDrafts.get(field.symbol) ?? String(original ?? "");
      const changed = model.spawnDrafts.has(field.symbol);
      const relationshipInvalid = (
        ["OW_WILD_SPAWN_MIN_DISTANCE", "OW_WILD_SPAWN_MAX_DISTANCE"].includes(field.symbol)
        && model.invalidInputs.has("spawn-range:min-max")
      ) || (field.symbol === "OW_WILD_DESPAWN_DISTANCE" && model.invalidInputs.has("spawn-range:despawn"));
      return {
        original,
        value,
        changed,
        invalid: model.invalidInputs.has(invalidKey("spawn", field.symbol)) || relationshipInvalid,
      };
    }

    function numberInput(field, label, state = fieldState(field)) {
      return `<label class="v2-spawn-range-control${state.changed ? " is-dirty" : ""}"><span>${escapeHtml(label)}</span>
        <input type="number" min="${escapeHtml(field.min)}" max="${escapeHtml(field.max)}" step="1" value="${escapeHtml(state.value)}"
          data-spawn-number data-symbol="${escapeHtml(field.symbol)}" data-original="${escapeHtml(state.original)}" aria-label="Spawn distance ${escapeHtml(label.toLowerCase())}" aria-invalid="${state.invalid}"></label>`;
    }

    return fields.flatMap((field) => {
      if (consumed.has(field.symbol)) return [];
      if (field.symbol === "OW_WILD_SPAWN_MAX_DISTANCE" && bySymbol.has("OW_WILD_SPAWN_MIN_DISTANCE")) return [];
      if (field.symbol === "OW_WILD_SPAWN_MIN_DISTANCE") {
        const maximum = bySymbol.get("OW_WILD_SPAWN_MAX_DISTANCE");
        if (maximum) {
          consumed.add(maximum.symbol);
          const minimumState = fieldState(field);
          const maximumState = fieldState(maximum);
          return [`<fieldset class="v2-spawn-range${minimumState.changed || maximumState.changed ? " is-dirty" : ""}"><legend><span>Spawn distance</span><small>tiles</small></legend><span class="v2-spawn-range-controls">${numberInput(field, "Min", minimumState)}${numberInput(maximum, "Max", maximumState)}</span></fieldset>`];
        }
      }

      const state = fieldState(field);
      if (field.kind === "species") {
        const option = displaySpecies(state.value, 0);
        return [`<label class="v2-spawn-field${state.changed ? " is-dirty" : ""}"><span>${escapeHtml(field.label)}</span>
          <input type="text" list="${ROUTE_SPECIES_LIST_ID}" value="${escapeHtml(shortSpeciesSymbol(option.symbol || state.value))}"
            data-spawn-species data-symbol="${escapeHtml(field.symbol)}" data-original="${escapeHtml(state.original)}" autocomplete="off" aria-invalid="${state.invalid}"></label>`];
      }
      return [`<label class="v2-spawn-field${state.changed ? " is-dirty" : ""}"><span>${escapeHtml(field.label)}${field.suffix ? ` (${escapeHtml(field.suffix)})` : ""}</span>
        <input type="number" min="${escapeHtml(field.min)}" max="${escapeHtml(field.max)}" step="1" value="${escapeHtml(state.value)}"
          data-spawn-number data-symbol="${escapeHtml(field.symbol)}" data-original="${escapeHtml(state.original)}" aria-invalid="${state.invalid}"></label>`];
    }).join("");
  }

  function renderSpawnDialog() {
    if (!model.spawnEditor) return "";
    return `<dialog class="v2-route-dialog v2-spawn-dialog" data-route-spawn-dialog aria-labelledby="v2SpawnDialogTitle">
      <div class="v2-route-dialog-shell">
        <header><div><span class="v2-eyebrow">Global configuration</span><h2 id="v2SpawnDialogTitle">Overworld spawn settings</h2></div>
          <button type="button" data-action="close-spawn-settings" aria-label="Close spawn settings">×</button></header>
        <div class="v2-spawn-groups">${asArray(model.data.spawnSettings).map((group) => `<section><h3>${escapeHtml(group.label)}</h3><div>${spawnSettingRows(group)}</div></section>`).join("")}</div>
        <footer><p>${model.spawnDrafts.size} setting${model.spawnDrafts.size === 1 ? "" : "s"} changed</p><button type="button" data-action="close-spawn-settings">Done</button></footer>
      </div>
    </dialog>`;
  }

  function showActiveDialog() {
    const dialog = inspector?.querySelector("dialog[data-route-entry-dialog], dialog[data-route-override-dialog], dialog[data-route-spawn-dialog]");
    if (dialog && !dialog.open && typeof dialog.showModal === "function") dialog.showModal();
  }

  function dialogInvalidInput(dialog) {
    return dialog?.querySelector('[aria-invalid="true"]') || null;
  }

  function closeDialogIfValid(dialog, onClose) {
    const invalid = dialogInvalidInput(dialog);
    if (invalid) {
      invalid.focus();
      notify(setStatus, "Fix or cancel the invalid value before closing this editor.", "error");
      return false;
    }
    onClose();
    dialog?.close();
    return true;
  }

  function renderInspector() {
    if (!inspector) return;
    const route = selectedRoute();
    if (!route) {
      inspector.innerHTML = `<p class="v2-route-empty">No route selected.</p>${speciesOptions()}${renderSpawnDialog()}`;
      showActiveDialog();
      return;
    }
    const edits = routeChangeCount(route.id);
    const groups = sourceGroups(route);
    const grass = ["morning", "day", "night"].map((key) => groups.find((group) => group.key === key)).filter(Boolean);
    const other = groups.filter((group) => !["morning", "day", "night"].includes(group.key)).filter((group) => {
      if (["headbuttNormal", "headbuttSpecial"].includes(group.key)) {
        return Number(group.treeCount || 0) > 0 || group.targets.some((target) => target.symbol !== "SPECIES_NONE");
      }
      return group.targets.length > 0;
    });
    inspector.innerHTML = `
      <header class="v2-route-detail-header">
        <div class="v2-route-title"><span class="v2-eyebrow">Encounter data #${escapeHtml(route.id)}</span><h2>${escapeHtml(route.name)}</h2><p>${escapeHtml(mapLabel(route))}</p></div>
        <div class="v2-route-head-tools"><div class="v2-route-header-rates" aria-label="Encounter rates">${asArray(route.rates).map((rate) => renderRateField(route, rate)).join("")}</div>
          ${renderOverrideButton(route)}<span class="v2-route-source-chip${edits ? " is-dirty" : ""}">${edits ? `${edits} changed` : "Source"}</span></div>
        ${renderOverview(route)}
      </header>
      <div class="v2-route-editor-layout">
        ${section(route, "grass", "Grass", grass)}
        ${section(route, "sources", "Other sources", other)}
      </div>
      ${renderEntryEditor(route)}${renderOverrideDialog(route)}${renderSpawnDialog()}${speciesOptions()}`;
    showActiveDialog();
  }

  function render() {
    renderFilters();
    renderLibrary();
    renderInspector();
  }

  function currentRouteById(routeId) {
    return model.routesById.get(String(routeId)) || null;
  }

  function updateSelectedRouteRows() {
    library?.querySelectorAll("[data-route-select]").forEach((button) => {
      const selected = String(button.dataset.routeSelect) === String(model.selectedRouteId);
      button.closest("[data-route-row]")?.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  }

  function selectRoute(routeId) {
    if (!model.routesById.has(String(routeId))) return false;
    if (String(model.selectedRouteId) === String(routeId)) return true;
    model.selectedRouteId = routeId;
    model.entryEditor = null;
    model.overrideEditor = false;
    updateSelectedRouteRows();
    renderInspector();
    if (inspector) inspector.scrollTop = 0;
    const route = currentRouteById(routeId);
    reportSelection("routes", String(routeId), route?.name || `Route ${routeId}`);
    return true;
  }

  function overrideEntries(route, state) {
    if (state?.entries?.length) return asArray(state.entries);
    return encounterTargets(route).map((target) => ({
      path: target.path,
      formPath: target.formPath,
      species: target.originalSymbol,
      form: String(target.originalForm || 0),
    }));
  }

  function overrideConflicts(route, state, entries) {
    const saved = route?.encounterOverride;
    if (!state || !saved) return [];
    return entries.filter((entry) => (
      baseline(route.id, entry.path, saved.species) !== String(saved.species)
      || baseline(route.id, entry.formPath, saved.form || 0) !== String(saved.form || 0)
    ));
  }

  function restoreOverrideEntries(route, entries) {
    entries.forEach((entry) => {
      setEncounterDraft(route.id, entry.path, entry.species, baseline(route.id, entry.path, entry.species));
      setEncounterDraft(route.id, entry.formPath, entry.form || 0, baseline(route.id, entry.formPath, entry.form || 0));
    });
  }

  function detachRouteOverride(route) {
    const state = currentOverride(route);
    if (!state) return true;
    const entries = overrideEntries(route, state);
    const conflicts = overrideConflicts(route, state, entries);
    if (conflicts.length) {
      notify(setStatus, `${conflicts.length} route source entr${conflicts.length === 1 ? "y has" : "ies have"} changed outside the override. Reload before editing this route.`, "error");
      return false;
    }
    restoreOverrideEntries(route, entries);
    if (route.encounterOverride) model.overrideDrafts.set(String(route.id), { action: "clear" });
    else model.overrideDrafts.delete(String(route.id));
    return true;
  }

  function overrideSensitiveNumber(route, path, nextValue) {
    if (String(path || "").endsWith(".form")) return true;
    const target = sourceGroups(route).flatMap((group) => group.targets)
      .find((candidate) => candidate.levelPath === path || candidate.minPath === path);
    if (!target) return false;
    const current = effective(route.id, path, target.levelPath ? target.originalLevel : target.originalMin);
    return Number(current) === 0 && Number(nextValue) !== 0;
  }

  function validateTargetRange(route, path) {
    const target = sourceGroups(route).flatMap((group) => group.targets)
      .find((candidate) => candidate.minPath === path || candidate.maxPath === path);
    if (!target) return true;
    const min = Number(effective(route.id, target.minPath, target.originalMin));
    const max = Number(effective(route.id, target.maxPath, target.originalMax));
    const key = invalidKey("level-range", route.id, target.minPath.replace(/\.minLevel$/, ""));
    const invalid = Number.isFinite(min) && Number.isFinite(max) && min > max;
    markInvalid(key, "Minimum level cannot exceed maximum level.", invalid);
    [target.minPath, target.maxPath].forEach((targetPath) => {
      [...(inspector?.querySelectorAll("[data-route-number]") || [])]
        .find((input) => String(input.dataset.routeId) === String(route.id) && input.dataset.path === targetPath)
        ?.setAttribute("aria-invalid", String(invalid));
    });
    return !invalid;
  }

  function updateChrome(route) {
    const chip = inspector?.querySelector(".v2-route-source-chip");
    const edits = routeChangeCount(route.id);
    if (chip) {
      chip.textContent = edits ? `${edits} changed` : "Source";
      chip.classList.toggle("is-dirty", Boolean(edits));
    }
  }

  function applyNumberInput(input) {
    const valid = numberIsValid(input.value, input.min || null, input.max || null);
    input.setAttribute("aria-invalid", String(!valid));
    const key = invalidKey("route", input.dataset.routeId, input.dataset.path);
    markInvalid(key, "Use a route value within the shown range.", !valid);
    if (!valid) return false;
    const route = currentRouteById(input.dataset.routeId);
    if (Number(input.value) === Number(effective(route.id, input.dataset.path, input.dataset.original))) {
      return true;
    }
    if (overrideSensitiveNumber(route, input.dataset.path, input.value) && !detachRouteOverride(route)) {
      renderInspector();
      return false;
    }
    setEncounterDraft(input.dataset.routeId, input.dataset.path, input.value, input.dataset.original);
    validateTargetRange(route, input.dataset.path);
    input.closest("label")?.classList.toggle("is-dirty", effective(input.dataset.routeId, input.dataset.path, input.dataset.original) !== String(input.dataset.original));
    signalDirty();
    renderLibrary();
    updateChrome(route);
    return true;
  }

  function applySpeciesInput(input) {
    const option = resolveSpecies(input.value);
    const valid = Boolean(option);
    input.setAttribute("aria-invalid", String(!valid));
    const key = invalidKey("species", input.dataset.routeId, input.dataset.path);
    markInvalid(key, "Choose a valid Pokémon.", !valid);
    if (!valid) {
      notify(setStatus, "Choose a valid Pokémon from the list.", "error");
      return false;
    }
    const route = currentRouteById(input.dataset.routeId);
    const write = speciesWrite(option);
    const currentSymbol = effective(route.id, input.dataset.path, input.dataset.original);
    const currentForm = effective(route.id, input.dataset.formPath, input.dataset.formOriginal || 0);
    if (write.symbol === currentSymbol && write.form === String(currentForm)) return true;
    if (!detachRouteOverride(route)) {
      renderInspector();
      return false;
    }
    setEncounterDraft(route.id, input.dataset.path, write.symbol, input.dataset.original);
    setEncounterDraft(route.id, input.dataset.formPath, write.form, input.dataset.formOriginal || 0);
    model.invalidInputs.delete(invalidKey("route", route.id, input.dataset.formPath));
    signalDirty();
    renderLibrary();
    renderInspector();
    return true;
  }

  function applySummarySpecies(input) {
    const route = currentRouteById(input.dataset.routeId);
    const group = sourceGroup(route, input.dataset.groupKey);
    const option = resolveSpecies(input.value);
    const key = invalidKey("summary", route.id, `${input.dataset.groupKey}:${input.dataset.speciesIdentity}`);
    input.setAttribute("aria-invalid", String(!option));
    markInvalid(key, "Choose a valid Pokémon for the source summary.", !option);
    if (!option || !group) return false;
    const write = speciesWrite(option);
    const targets = group.targets.filter((target) => speciesIdentity(target.symbol, target.form) === input.dataset.speciesIdentity);
    if (targets.every((target) => target.symbol === write.symbol && String(target.form) === write.form)) return true;
    if (!detachRouteOverride(route)) {
      renderInspector();
      return false;
    }
    targets.forEach((target) => {
      setEncounterDraft(route.id, target.path, write.symbol, target.originalSymbol);
      setEncounterDraft(route.id, target.formPath, write.form, target.originalForm);
      model.invalidInputs.delete(invalidKey("species", route.id, target.path));
    });
    signalDirty();
    renderLibrary();
    renderInspector();
    notify(setStatus, `${targets.length} ${group.label} entr${targets.length === 1 ? "y" : "ies"} now draft ${option.name || shortSpeciesSymbol(option.symbol)}.`, "success");
    return true;
  }

  function overrideBaselineEntries(route, targets) {
    const pending = model.overrideDrafts.get(String(route.id));
    if (pending?.action === "set" && asArray(pending.entries).length) return pending.entries;
    if (!pending && asArray(route.encounterOverride?.entries).length) return route.encounterOverride.entries;
    return targets.map((target) => ({
      path: target.path,
      formPath: target.formPath,
      species: effective(route.id, target.path, target.originalSymbol),
      form: String(effective(route.id, target.formPath, target.originalForm) || 0),
    }));
  }

  function setRouteOverride(route, option) {
    const targets = encounterTargets(route);
    if (!targets.length) {
      notify(setStatus, `${route.name} has no enabled encounter slots.`, "error");
      return false;
    }
    const write = speciesWrite(option);
    const current = currentOverride(route);
    if (current && String(current.species) === write.symbol && String(current.form || 0) === write.form) {
      model.overrideEditor = false;
      renderInspector();
      notify(setStatus, "That route-only encounter is already active.");
      return true;
    }
    const entries = overrideBaselineEntries(route, targets);
    targets.forEach((target) => {
      setEncounterDraft(route.id, target.path, write.symbol, target.originalSymbol);
      setEncounterDraft(route.id, target.formPath, write.form, target.originalForm);
    });
    model.overrideDrafts.set(String(route.id), { action: "set", species: write.symbol, form: write.form, entries });
    model.overrideEditor = false;
    signalDirty();
    renderLibrary();
    renderInspector();
    notify(setStatus, `${route.name} now drafts only ${option.name || shortSpeciesSymbol(option.symbol)}.`, "success");
    return true;
  }

  async function clearRouteOverride(route) {
    const state = currentOverride(route);
    if (!state) return false;
    if (!await ask(confirmAction, `Turn off the route-only encounter for ${route.name}?`)) return false;
    const entries = overrideEntries(route, state);
    const conflicts = overrideConflicts(route, state, entries);
    if (conflicts.length) {
      notify(setStatus, `${conflicts.length} source entr${conflicts.length === 1 ? "y conflicts" : "ies conflict"} with the stored baseline. Reload instead of overwriting external changes.`, "error");
      return false;
    }
    restoreOverrideEntries(route, entries);
    if (route.encounterOverride) model.overrideDrafts.set(String(route.id), { action: "clear" });
    else model.overrideDrafts.delete(String(route.id));
    model.overrideEditor = false;
    signalDirty();
    renderLibrary();
    renderInspector();
    notify(setStatus, `${route.name} route-only encounter is off.`, "success");
    return true;
  }

  function spawnNumericValue(symbol) {
    for (const group of asArray(model.data.spawnSettings)) {
      for (const setting of asArray(group.settings)) {
        const fields = setting.kind === "testSpawn" ? asArray(setting.fields) : [setting];
        const field = fields.find((candidate) => candidate.symbol === symbol);
        if (field) return Number(model.spawnDrafts.get(symbol) ?? field.value ?? field.raw);
      }
    }
    return NaN;
  }

  function validateSpawnRelationships() {
    const minimum = spawnNumericValue("OW_WILD_SPAWN_MIN_DISTANCE");
    const maximum = spawnNumericValue("OW_WILD_SPAWN_MAX_DISTANCE");
    const despawn = spawnNumericValue("OW_WILD_DESPAWN_DISTANCE");
    markInvalid("spawn-range:min-max", "Spawn minimum distance cannot exceed maximum distance.", Number.isFinite(minimum) && Number.isFinite(maximum) && minimum > maximum);
    markInvalid("spawn-range:despawn", "Despawn distance must be at least the spawn maximum distance.", Number.isFinite(maximum) && Number.isFinite(despawn) && despawn < maximum);
  }

  function applySpawnInput(input, species = false) {
    const original = input.dataset.original || "";
    let value = input.value;
    let valid = true;
    if (species) {
      const option = resolveSpecies(value);
      valid = Boolean(option);
      if (option) {
        value = option.symbol;
        input.value = shortSpeciesSymbol(option.symbol);
      }
    } else {
      valid = numberIsValid(value, input.min || null, input.max || null);
    }
    input.setAttribute("aria-invalid", String(!valid));
    markInvalid(invalidKey("spawn", input.dataset.symbol), species ? "Choose a valid Pokémon for the spawn setting." : "Use a spawn setting within the shown range.", !valid);
    if (!valid) return false;
    setSpawnDraft(input.dataset.symbol, value, original);
    validateSpawnRelationships();
    input.closest("label")?.classList.toggle("is-dirty", model.spawnDrafts.has(input.dataset.symbol));
    const dialog = input.closest("[data-route-spawn-dialog]");
    const range = input.closest(".v2-spawn-range");
    if (range) {
      const rangeDirty = [...range.querySelectorAll("[data-spawn-number]")]
        .some((control) => model.spawnDrafts.has(control.dataset.symbol));
      range.classList.toggle("is-dirty", rangeDirty);
    }
    const relationshipStates = [
      ["OW_WILD_SPAWN_MIN_DISTANCE", model.invalidInputs.has("spawn-range:min-max")],
      ["OW_WILD_SPAWN_MAX_DISTANCE", model.invalidInputs.has("spawn-range:min-max")],
      ["OW_WILD_DESPAWN_DISTANCE", model.invalidInputs.has("spawn-range:despawn")],
    ];
    relationshipStates.forEach(([symbol, relationshipInvalid]) => {
      const control = dialog?.querySelector(`[data-symbol="${symbol}"]`);
      if (!control) return;
      const ownInvalid = model.invalidInputs.has(invalidKey("spawn", symbol));
      control.setAttribute("aria-invalid", String(ownInvalid || relationshipInvalid));
    });
    signalDirty();
    return true;
  }

  function speciesSymbolsForPool(tableKeys = [], swarmKeys = []) {
    const tableSet = new Set(tableKeys);
    const swarmSet = new Set(swarmKeys);
    const symbols = new Set();
    model.routes.forEach((route) => {
      sourceGroups(route).forEach((group) => {
        const targets = group.key === "swarms"
          ? group.targets.filter((target) => swarmSet.has(target.swarmKey))
          : tableSet.has(group.key) ? group.targets : [];
        targets.forEach((target) => {
          if (target.option?.symbol && target.option.symbol !== "SPECIES_NONE") symbols.add(target.option.symbol);
        });
      });
    });
    return [...symbols];
  }

  function routePayload() {
    const changes = {};
    model.encounterDrafts.forEach((value, key) => {
      const [routeId, path] = splitBaselineKey(key);
      (changes[routeId] ||= {})[path] = value;
    });
    const overrides = {};
    model.overrideDrafts.forEach((operation, routeId) => {
      overrides[routeId] = operation.action === "clear" ? { action: "clear" } : {
        action: "set",
        species: operation.species,
        form: String(operation.form || 0),
        entries: asArray(operation.entries).map((entry) => ({
          path: entry.path,
          formPath: entry.formPath,
          species: entry.species,
          form: String(entry.form || 0),
        })),
      };
    });
    return { changes, overrides };
  }

  function commitPayload() {
    const payload = {};
    if (model.encounterDrafts.size || model.overrideDrafts.size) payload.encounters = routePayload();
    if (model.spawnDrafts.size) payload.spawnSettings = { changes: Object.fromEntries(model.spawnDrafts) };
    return payload;
  }

  function clearCommitted(scope = "all") {
    if (scope === "all" || scope === "encounters" || scope === "/save-encounters") {
      model.encounterDrafts.clear();
      model.overrideDrafts.clear();
    }
    if (scope === "all" || scope === "spawnSettings" || scope === "/save-spawn-settings") model.spawnDrafts.clear();
    if (scope === "all") model.invalidInputs.clear();
    model.entryEditor = null;
    model.overrideEditor = false;
    model.spawnEditor = false;
    signalDirty();
    render();
  }

  function reset(scope = "all") {
    clearCommitted(scope);
    notify(setStatus, "Route and spawn drafts reset.");
  }

  function refresh(nextData = null) {
    model.data = currentData(appState, nextData);
    model.routes = asArray(model.data.routes);
    model.routesById = new Map(model.routes.map((route) => [String(route.id), route]));
    model.baselines.clear();
    model.routes.forEach(indexRoute);
    model.species = asArray(model.data.speciesOptions);
    model.speciesByLookup.clear();
    model.speciesByBaseForm.clear();
    model.species.forEach(registerSpecies);
    if (!model.routesById.has(String(model.selectedRouteId))) model.selectedRouteId = model.routes[0]?.id ?? null;
    render();
    return controller;
  }

  function openEntryEditor(routeId, groupKey, identity) {
    selectRoute(routeId);
    model.entryEditor = { routeId, groupKey, identity, wide: false };
    model.overrideEditor = false;
    model.spawnEditor = false;
    renderInspector();
  }

  function openGroupEntryEditor(routeId, groupKey) {
    selectRoute(routeId);
    model.entryEditor = { routeId, groupKey, identity: null, wide: false, all: true };
    model.overrideEditor = false;
    model.spawnEditor = false;
    renderInspector();
  }

  function openWideEntryEditor(routeId, groupKey, identity) {
    selectRoute(routeId);
    model.entryEditor = { routeId, groupKey, identity, wide: true };
    model.overrideEditor = false;
    model.spawnEditor = false;
    renderInspector();
  }

  function applyWideSpecies(route, highlightedOnly) {
    const editor = model.entryEditor;
    const input = inspector?.querySelector("[data-route-wide-species]");
    const option = resolveSpecies(input?.value);
    const key = invalidKey("wide-swap", route.id, editor?.identity || "");
    input?.setAttribute("aria-invalid", String(!option));
    markInvalid(key, "Choose a valid Pokémon for the route-wide swap.", !option);
    if (!editor || !option) return false;
    const all = sourceGroups(route).flatMap((group) => group.targets)
      .filter((target) => speciesIdentity(target.symbol, target.form) === editor.identity);
    const targets = highlightedOnly ? all.filter((target) => editor.groupKey === "grass"
      ? ["morning", "day", "night"].includes(target.groupKey)
      : target.groupKey === editor.groupKey) : all;
    if (!targets.length) return false;
    const write = speciesWrite(option);
    if (targets.every((target) => target.symbol === write.symbol && String(target.form) === write.form)) {
      model.invalidInputs.delete(key);
      return true;
    }
    if (!detachRouteOverride(route)) return false;
    targets.forEach((target) => {
      setEncounterDraft(route.id, target.path, write.symbol, target.originalSymbol);
      setEncounterDraft(route.id, target.formPath, write.form, target.originalForm);
      model.invalidInputs.delete(invalidKey("species", route.id, target.path));
    });
    model.invalidInputs.delete(key);
    model.entryEditor = null;
    signalDirty();
    renderLibrary();
    renderInspector();
    notify(setStatus, `${targets.length} route entr${targets.length === 1 ? "y" : "ies"} now draft ${option.name || shortSpeciesSymbol(option.symbol)}.`, "success");
    return true;
  }

  search?.addEventListener("input", () => {
    model.query = search.value.trim().toLowerCase();
    renderLibrary();
    const scroll = inspector?.scrollTop || 0;
    renderInspector();
    if (inspector) inspector.scrollTop = scroll;
  }, { signal: abort.signal });

  filters?.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "open-spawn-settings") {
      model.spawnEditor = true;
      model.entryEditor = null;
      model.overrideEditor = false;
      renderInspector();
      return;
    }
    const button = event.target.closest("[data-route-filter]");
    if (!button) return;
    const key = button.dataset.routeFilter;
    if (model.methodFilters.has(key)) model.methodFilters.delete(key);
    else model.methodFilters.add(key);
    saveSet(ROUTE_FILTER_STORAGE_KEY, model.methodFilters);
    button.classList.toggle("is-active", model.methodFilters.has(key));
    button.setAttribute("aria-pressed", String(model.methodFilters.has(key)));
    renderLibrary();
  }, { signal: abort.signal });

  library?.addEventListener("click", (event) => {
    const pokemon = event.target.closest("[data-open-pokemon]");
    if (pokemon) {
      const route = currentRouteById(pokemon.closest("[data-route-row]")?.dataset.routeRow || model.selectedRouteId);
      openPokemonRecord(pokemon.dataset.openPokemon, {
        view: "routes",
        selection: String(route?.id ?? model.selectedRouteId ?? ""),
        label: route?.name || "Route deck",
      });
      return;
    }
    const override = event.target.closest('[data-action="open-route-override"]');
    if (override) {
      selectRoute(override.dataset.routeId);
      model.overrideEditor = true;
      model.entryEditor = null;
      renderInspector();
      return;
    }
    const wide = event.target.closest("[data-route-wide-edit]");
    if (wide) {
      openWideEntryEditor(wide.dataset.routeId, wide.dataset.routeWideEdit, wide.dataset.speciesIdentity);
      return;
    }
    const all = event.target.closest("[data-route-group-edit-all]");
    if (all) {
      openGroupEntryEditor(all.dataset.routeId, all.dataset.routeGroupEditAll);
      return;
    }
    const group = event.target.closest("[data-route-group-edit]");
    if (group) {
      openEntryEditor(group.dataset.routeId, group.dataset.routeGroupEdit, group.dataset.speciesIdentity);
      return;
    }
    const selector = event.target.closest("[data-route-select]");
    if (selector) {
      selectRoute(selector.dataset.routeSelect);
      return;
    }
    const row = event.target.closest("[data-route-row]");
    if (!row || event.target.closest('button, a[href], input, select, textarea, summary, label, [role="button"], [contenteditable="true"], [tabindex]:not([tabindex="-1"])')) return;
    selectRoute(row.dataset.routeRow);
  }, { signal: abort.signal });

  inspector?.addEventListener("input", (event) => {
    const input = event.target;
    if (input.matches("[data-route-number]")) applyNumberInput(input);
    else if (input.matches("[data-spawn-number]")) applySpawnInput(input);
  }, { signal: abort.signal });

  inspector?.addEventListener("change", (event) => {
    const input = event.target;
    if (input.matches("[data-route-species]")) applySpeciesInput(input);
    else if (input.matches("[data-route-summary-species]")) applySummarySpecies(input);
    else if (input.matches("[data-spawn-species]")) applySpawnInput(input, true);
  }, { signal: abort.signal });

  inspector?.addEventListener("keydown", (event) => {
    const input = event.target;
    if (!input.matches("[data-route-species], [data-route-summary-species], [data-route-override-input], [data-route-wide-species], [data-route-number], [data-spawn-number], [data-spawn-species]")) return;
    if (event.key === "Enter") {
      event.preventDefault();
      if (input.matches("[data-route-species]")) applySpeciesInput(input);
      else if (input.matches("[data-route-summary-species]")) applySummarySpecies(input);
      else if (input.matches("[data-route-wide-species]")) applyWideSpecies(selectedRoute(), false);
      else if (input.matches("[data-route-override-input]")) inspector.querySelector('[data-action="set-route-override"]')?.click();
      else input.blur();
    } else if (event.key === "Escape") {
      event.preventDefault();
      if (input.matches("[data-route-number]")) {
        model.invalidInputs.delete(invalidKey("route", input.dataset.routeId, input.dataset.path));
        validateTargetRange(currentRouteById(input.dataset.routeId), input.dataset.path);
      } else if (input.matches("[data-spawn-number], [data-spawn-species]")) {
        model.invalidInputs.delete(invalidKey("spawn", input.dataset.symbol));
        validateSpawnRelationships();
      } else if (input.matches("[data-route-species]")) {
        model.invalidInputs.delete(invalidKey("species", input.dataset.routeId, input.dataset.path));
      } else if (input.matches("[data-route-summary-species]")) {
        model.invalidInputs.delete(invalidKey("summary", input.dataset.routeId, `${input.dataset.groupKey}:${input.dataset.speciesIdentity}`));
      } else if (input.matches("[data-route-override-input]")) {
        model.invalidInputs.delete(invalidKey("route-override", selectedRoute()?.id));
      } else if (input.matches("[data-route-wide-species]")) {
        model.invalidInputs.delete(invalidKey("wide-swap", selectedRoute()?.id, model.entryEditor?.identity || ""));
      }
      signalDirty();
      renderInspector();
    }
  }, { signal: abort.signal });

  inspector?.addEventListener("toggle", (event) => {
    const details = event.target.closest("[data-route-section]");
    if (!details || event.target !== details) return;
    if (details.open) model.openSections.add(details.dataset.routeSection);
    else model.openSections.delete(details.dataset.routeSection);
    saveSet(ROUTE_SECTION_STORAGE_KEY, model.openSections);
  }, { signal: abort.signal, capture: true });

  inspector?.addEventListener("cancel", (event) => {
    const invalid = dialogInvalidInput(event.target);
    if (invalid) {
      event.preventDefault();
      invalid.focus();
      notify(setStatus, "Fix the invalid value or press Escape while editing it to restore the draft value.", "error");
      return;
    }
    if (event.target.matches("[data-route-entry-dialog]")) model.entryEditor = null;
    else if (event.target.matches("[data-route-override-dialog]")) model.overrideEditor = false;
    else if (event.target.matches("[data-route-spawn-dialog]")) model.spawnEditor = false;
  }, { signal: abort.signal, capture: true });

  inspector?.addEventListener("click", async (event) => {
    const pokemon = event.target.closest("[data-open-pokemon]");
    if (pokemon) {
      const route = selectedRoute();
      openPokemonRecord(pokemon.dataset.openPokemon, {
        view: "routes",
        selection: String(route?.id ?? ""),
        label: route?.name || "Route deck",
      });
      return;
    }
    const wide = event.target.closest("[data-route-wide-edit]");
    if (wide) {
      openWideEntryEditor(wide.dataset.routeId, wide.dataset.routeWideEdit, wide.dataset.speciesIdentity);
      return;
    }
    const all = event.target.closest("[data-route-group-edit-all]");
    if (all) {
      openGroupEntryEditor(all.dataset.routeId, all.dataset.routeGroupEditAll);
      return;
    }
    const group = event.target.closest("[data-route-group-edit]");
    if (group) {
      openEntryEditor(group.dataset.routeId, group.dataset.routeGroupEdit, group.dataset.speciesIdentity);
      return;
    }
    const actionButton = event.target.closest("[data-action]");
    const action = actionButton?.dataset.action;
    const route = selectedRoute();
    if (!action || !route) return;
    if (action === "open-route-override") {
      model.overrideEditor = true;
      model.entryEditor = null;
      model.spawnEditor = false;
      renderInspector();
    } else if (action === "close-entry-editor") {
      const dialog = inspector.querySelector("[data-route-entry-dialog]");
      closeDialogIfValid(dialog, () => { model.entryEditor = null; });
    } else if (action === "close-route-override") {
      const dialog = inspector.querySelector("[data-route-override-dialog]");
      closeDialogIfValid(dialog, () => { model.overrideEditor = false; });
    } else if (action === "close-spawn-settings") {
      const dialog = inspector.querySelector("[data-route-spawn-dialog]");
      closeDialogIfValid(dialog, () => { model.spawnEditor = false; });
    } else if (action === "set-route-override") {
      const input = inspector.querySelector("[data-route-override-input]");
      const option = resolveSpecies(input?.value);
      const invalid = !option || option.symbol === "SPECIES_NONE";
      input?.setAttribute("aria-invalid", String(invalid));
      markInvalid(invalidKey("route-override", route.id), "Choose a valid Pokémon for the route-only encounter.", invalid);
      if (invalid) notify(setStatus, "Choose a valid Pokémon for the route-only encounter.", "error");
      else setRouteOverride(route, option);
    } else if (action === "clear-route-override") {
      await clearRouteOverride(route);
    } else if (action === "swap-entry-highlighted") {
      applyWideSpecies(route, true);
    } else if (action === "swap-entry-all") {
      applyWideSpecies(route, false);
    }
  }, { signal: abort.signal });

  const controller = {
    state: model,
    hasChanges() {
      return model.encounterDrafts.size > 0 || model.overrideDrafts.size > 0 || model.spawnDrafts.size > 0;
    },
    changeCount() {
      return model.encounterDrafts.size + model.overrideDrafts.size + model.spawnDrafts.size;
    },
    hasInvalid() {
      return model.invalidInputs.size > 0;
    },
    validationCount() {
      return model.invalidInputs.size;
    },
    validationMessage() {
      return model.invalidInputs.values().next().value || "";
    },
    speciesSymbolsForPool,
    commitPayload,
    clearCommitted,
    reset,
    refresh,
    navigationContext() {
      const route = selectedRoute();
      return { selection: String(route?.id ?? ""), label: route?.name || "" };
    },
    restoreSelection(routeId, options = {}) {
      const selected = selectRoute(routeId);
      if (selected && options.focus) {
        inspector.tabIndex = -1;
        requestAnimationFrame(() => inspector.focus({ preventScroll: true }));
      }
      return selected;
    },
    destroy() {
      abort.abort();
    },
  };

  refresh();
  return controller;
}
