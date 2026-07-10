const ROUTE_SPECIES_LIST_ID = "v2-route-species-options";

const SOUND_FILTERS = [
  ["all", "All"],
  ["effects", "Sound effects"],
  ["moves", "Moves"],
  ["field", "Field"],
  ["battle", "Battle"],
  ["tester", "Tester"],
  ["extra", "Extra sequences"],
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

function shortSpeciesSymbol(symbol) {
  return String(symbol || "").replace(/^SPECIES_/, "");
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function elementFrom(elements, key, id = key) {
  return elements?.[key] || document.getElementById(id);
}

function currentData(state, supplied) {
  if (supplied?.routes || supplied?.speciesOptions || supplied?.spawnSettings) return supplied;
  if (supplied?.data) return supplied.data;
  return state?.data || state?.appData || state?.workspaceData || state || {};
}

function icon(species, className = "v2-mon-icon") {
  if (!species?.iconUrl) return "";
  return `<img class="${escapeHtml(className)}" src="${escapeHtml(species.iconUrl)}" alt="" loading="lazy">`;
}

function mapLabel(route) {
  const maps = asArray(route?.maps);
  if (!maps.length) return "No linked map";
  return maps.map((map) => map.name || map.symbol).filter(Boolean).join(", ");
}

function notify(setStatus, message, tone = "ready") {
  if (typeof setStatus === "function") setStatus(message, tone);
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

async function getJson(api, path, options = {}) {
  let response;
  if (typeof api?.getJson === "function") response = await api.getJson(path, options);
  else if (typeof api?.get === "function") response = await api.get(path, options);
  else if (typeof api?.request === "function") response = await api.request(path, { method: "GET", ...options });
  else response = await fetch(path, { cache: "no-store", ...options });

  if (response && typeof response.json === "function") {
    const payload = await response.json();
    if (response.ok === false || payload?.error) {
      throw new Error(payload?.error || `Request failed (${response.status})`);
    }
    return payload;
  }
  if (response?.error) throw new Error(response.error);
  return response;
}

function baselineKey(routeId, path) {
  return `${routeId}\u0000${path}`;
}

function splitBaselineKey(key) {
  const separator = key.indexOf("\u0000");
  return [key.slice(0, separator), key.slice(separator + 1)];
}

function numberIsValid(raw, min, max) {
  const value = Number(String(raw).trim());
  return String(raw).trim() !== ""
    && Number.isInteger(value)
    && (min == null || value >= Number(min))
    && (max == null || value <= Number(max));
}

export function createRoutesController({
  state: appState = {},
  api = null,
  elements = {},
  setStatus = null,
  markDirty = null,
  confirmAction = null,
} = {}) {
  void api;
  const search = elementFrom(elements, "routeSearch");
  const library = elementFrom(elements, "routeLibrary");
  const inspector = elementFrom(elements, "routeInspector");
  const routeCount = elements?.routeCount
    || library?.closest(".library-panel")?.querySelector("[data-route-count]")
    || null;
  const abort = new AbortController();

  const model = {
    data: {},
    routes: [],
    selectedRouteId: null,
    query: "",
    encounterDrafts: new Map(),
    overrideDrafts: new Map(),
    spawnDrafts: new Map(),
    baselines: new Map(),
    routesById: new Map(),
    species: [],
    speciesByLookup: new Map(),
    speciesByBaseForm: new Map(),
  };

  function signalDirty() {
    if (typeof markDirty === "function") markDirty();
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

  function routeChangeCount(routeId) {
    const routeKey = String(routeId);
    let count = model.overrideDrafts.has(routeKey) ? 1 : 0;
    for (const key of model.encounterDrafts.keys()) {
      if (splitBaselineKey(key)[0] === routeKey) count += 1;
    }
    return count;
  }

  function registerSpecies(option) {
    const symbol = String(option?.symbol || "").toUpperCase();
    if (!symbol) return;
    const names = [
      symbol,
      shortSpeciesSymbol(symbol),
      option.name,
      option.baseSymbol,
      shortSpeciesSymbol(option.baseSymbol),
    ];
    names.forEach((name) => {
      if (!name) return;
      model.speciesByLookup.set(String(name).toLowerCase(), option);
      model.speciesByLookup.set(compact(name), option);
    });
    const base = option.baseSymbol || option.symbol;
    model.speciesByBaseForm.set(`${base}:${Number(option.form || 0)}`, option);
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
    return model.speciesByBaseForm.get(`${symbol}:${Number(form || 0)}`)
      || resolveSpecies(symbol)
      || { symbol, name: shortSpeciesSymbol(symbol) || "None", form: Number(form || 0) };
  }

  function speciesWrite(option) {
    return {
      symbol: option?.baseSymbol || option?.symbol || "SPECIES_NONE",
      form: String(option?.baseSymbol ? Number(option.form || 0) : 0),
    };
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

  function routeMatches(route) {
    const query = model.query;
    if (!query) return true;
    const text = [
      route.id,
      route.name,
      ...asArray(route.maps).flatMap((map) => [map.name, map.symbol]),
      ...asArray(route.species).flatMap((species) => [species.name, species.symbol]),
    ].join(" ").toLowerCase();
    return text.includes(query);
  }

  function renderLibrary() {
    if (!library) return;
    const visible = model.routes.filter(routeMatches);
    if (routeCount) routeCount.textContent = model.query ? `${visible.length}/${model.routes.length}` : String(model.routes.length);
    library.innerHTML = visible.length ? visible.map((route) => {
      const selected = String(route.id) === String(model.selectedRouteId);
      const edits = routeChangeCount(route.id);
      const sample = asArray(route.species).slice(0, 4);
      return `
        <button class="v2-library-row v2-route-row${selected ? " is-selected" : ""}${edits ? " is-dirty" : ""}" type="button"
          data-route-select="${escapeHtml(route.id)}" aria-pressed="${selected}">
          <span class="v2-library-id">#${escapeHtml(route.id)}</span>
          <span class="v2-library-copy">
            <strong>${escapeHtml(route.name)}</strong>
            <small>${escapeHtml(mapLabel(route))}${edits ? ` · ${edits} change${edits === 1 ? "" : "s"}` : ""}</small>
          </span>
          <span class="v2-icon-stack" aria-hidden="true">${sample.map((species) => icon(species)).join("")}</span>
        </button>`;
    }).join("") : `<p class="v2-empty">No routes match “${escapeHtml(model.query)}”.</p>`;
  }

  function inputNumber(routeId, path, value, label, min = 0, max = 100, extraClass = "") {
    const raw = effective(routeId, path, value);
    const changed = raw !== String(value ?? "");
    return `
      <label class="v2-field ${extraClass}${changed ? " is-dirty" : ""}">
        <span>${escapeHtml(label)}</span>
        <input type="number" min="${escapeHtml(min)}" max="${escapeHtml(max)}" step="1" value="${escapeHtml(raw)}"
          data-route-number data-route-id="${escapeHtml(routeId)}" data-path="${escapeHtml(path)}"
          data-original="${escapeHtml(value)}">
      </label>`;
  }

  function speciesInput(routeId, path, species, formPath, form, label = "Pokémon") {
    const rawSymbol = effective(routeId, path, species?.symbol);
    const rawForm = effective(routeId, formPath, form || 0);
    const option = displaySpecies(rawSymbol, rawForm);
    const changed = rawSymbol !== String(species?.symbol || "") || rawForm !== String(form || 0);
    return `
      <label class="v2-field v2-species-field${changed ? " is-dirty" : ""}">
        <span>${escapeHtml(label)}</span>
        <span class="v2-species-control">
          ${icon(option)}
          <input type="text" list="${ROUTE_SPECIES_LIST_ID}" value="${escapeHtml(shortSpeciesSymbol(option.symbol || rawSymbol))}"
            autocomplete="off" data-route-species data-route-id="${escapeHtml(routeId)}"
            data-path="${escapeHtml(path)}" data-form-path="${escapeHtml(formPath)}"
            data-original="${escapeHtml(species?.symbol)}" data-form-original="${escapeHtml(form || 0)}">
          <input class="v2-form-input" type="number" min="0" max="31" step="1" value="${escapeHtml(rawForm)}"
            aria-label="Form" title="Form" data-route-number data-route-id="${escapeHtml(routeId)}"
            data-path="${escapeHtml(formPath)}" data-original="${escapeHtml(form || 0)}">
        </span>
      </label>`;
  }

  function ratesSection(route) {
    if (!asArray(route.rates).length) return "";
    return `
      <details class="v2-disclosure" open>
        <summary><span>Encounter rates</span><small>0–100%</small></summary>
        <div class="v2-compact-grid">
          ${route.rates.map((rate) => inputNumber(route.id, rate.path, rate.value, rate.label, 0, 100)).join("")}
        </div>
      </details>`;
  }

  function grassSection(route) {
    if (!asArray(route.grassLevels).length) return "";
    return `
      <details class="v2-disclosure">
        <summary><span>Grass levels</span><small>${route.grassLevels.length} weighted slots</small></summary>
        <div class="v2-slot-grid">
          ${route.grassLevels.map((level) => inputNumber(
            route.id,
            level.path,
            level.value,
            `Slot ${level.slot} · ${level.weight}%`,
            0,
            100,
          )).join("")}
        </div>
      </details>`;
  }

  function pokemonTable(route, table) {
    return `
      <details class="v2-disclosure">
        <summary><span>${escapeHtml(table.label)}</span><small>${asArray(table.slots).length} slots</small></summary>
        <div class="v2-slot-list">
          ${asArray(table.slots).map((slot) => `
            <div class="v2-slot-row">
              <span class="v2-slot-weight">${escapeHtml(slot.weight)}%</span>
              ${speciesInput(route.id, slot.path, slot.species, slot.formPath, slot.form, `Slot ${slot.slot}`)}
            </div>`).join("")}
        </div>
      </details>`;
  }

  function levelTable(route, table) {
    return `
      <details class="v2-disclosure">
        <summary><span>${escapeHtml(table.label)}</span><small>${asArray(table.slots).length} slots</small></summary>
        <div class="v2-slot-list">
          ${asArray(table.slots).map((slot) => `
            <div class="v2-slot-row v2-level-slot">
              <span class="v2-slot-weight">${escapeHtml(slot.weight)}%</span>
              ${speciesInput(route.id, slot.paths?.species, slot.species, slot.paths?.form, slot.form, `Slot ${slot.slot}`)}
              <span class="v2-level-range">
                ${inputNumber(route.id, slot.paths?.minLevel, slot.minLevel, "Min", 0, 100)}
                ${inputNumber(route.id, slot.paths?.maxLevel, slot.maxLevel, "Max", 0, 100)}
              </span>
            </div>`).join("")}
        </div>
      </details>`;
  }

  function swarmsSection(route) {
    if (!asArray(route.swarms).length) return "";
    return `
      <details class="v2-disclosure">
        <summary><span>Swarms</span><small>${route.swarms.length}</small></summary>
        <div class="v2-compact-grid">
          ${route.swarms.map((swarm) => speciesInput(
            route.id,
            swarm.path,
            swarm.species,
            swarm.formPath,
            swarm.form,
            swarm.label,
          )).join("")}
        </div>
      </details>`;
  }

  function encounterTargets(route) {
    const targets = [];
    const add = (path, formPath, species, form, enabled = true) => {
      if (!enabled || !path || !formPath || species?.symbol === "SPECIES_NONE") return;
      targets.push({
        path,
        formPath,
        originalSymbol: baseline(route.id, path, species?.symbol),
        originalForm: baseline(route.id, formPath, form || 0),
      });
    };
    asArray(route.pokemonTables).forEach((table) => asArray(table.slots).forEach((slot, index) => {
      const grassLevel = ["morning", "day", "night"].includes(table.key) ? route.grassLevels?.[index] : null;
      const enabled = !grassLevel || Number(effective(route.id, grassLevel.path, grassLevel.value)) !== 0;
      add(slot.path, slot.formPath, slot.species, slot.form, enabled);
    }));
    [...asArray(route.slotTables), ...asArray(route.headbuttTables)].forEach((table) => {
      asArray(table.slots).forEach((slot) => {
        const enabled = Number(effective(route.id, slot.paths?.minLevel, slot.minLevel)) !== 0;
        add(slot.paths?.species, slot.paths?.form, slot.species, slot.form, enabled);
      });
    });
    asArray(route.swarms).forEach((swarm) => add(swarm.path, swarm.formPath, swarm.species, swarm.form));
    return targets;
  }

  function currentOverride(route) {
    const pending = model.overrideDrafts.get(String(route.id));
    if (pending?.action === "clear") return null;
    return pending?.action === "set" ? pending : route.encounterOverride || null;
  }

  function overrideSection(route) {
    const current = currentOverride(route);
    const option = current ? displaySpecies(current.species, current.form || 0) : null;
    const changed = model.overrideDrafts.has(String(route.id));
    return `
      <details class="v2-disclosure v2-route-override${changed ? " is-dirty" : ""}">
        <summary>
          <span>Route-only encounter</span>
          <small>${option ? `Only ${escapeHtml(option.name || shortSpeciesSymbol(option.symbol))}` : "Off"}</small>
        </summary>
        <div class="v2-inline-editor">
          <label class="v2-field v2-species-field">
            <span>Only encounter</span>
            <input type="text" list="${ROUTE_SPECIES_LIST_ID}" value="${escapeHtml(option ? shortSpeciesSymbol(option.symbol) : "")}"
              data-route-override-input autocomplete="off" placeholder="Pokémon">
          </label>
          <button type="button" data-action="set-route-override">Apply</button>
          <button type="button" data-action="clear-route-override"${current ? "" : " disabled"}>Turn off</button>
        </div>
        <p class="v2-help">Temporarily makes one Pokémon the only encounter on this route while retaining the original entries for restoration.</p>
      </details>`;
  }

  function spawnSettingRows(group) {
    return asArray(group.settings).map((setting) => {
      const fields = setting.kind === "testSpawn" ? asArray(setting.fields) : [setting];
      return fields.map((field) => {
        const original = field.kind === "species" ? (field.symbolValue || field.raw) : field.value;
        const value = model.spawnDrafts.get(field.symbol) ?? String(original ?? "");
        const changed = model.spawnDrafts.has(field.symbol);
        if (field.kind === "species") {
          const option = displaySpecies(value, 0);
          return `
            <label class="v2-field v2-species-field${changed ? " is-dirty" : ""}">
              <span>${escapeHtml(field.label)}</span>
              <input type="text" list="${ROUTE_SPECIES_LIST_ID}" value="${escapeHtml(shortSpeciesSymbol(option.symbol || value))}"
                data-spawn-species data-symbol="${escapeHtml(field.symbol)}" data-original="${escapeHtml(original)}" autocomplete="off">
            </label>`;
        }
        return `
          <label class="v2-field${changed ? " is-dirty" : ""}">
            <span>${escapeHtml(field.label)}${field.suffix ? ` (${escapeHtml(field.suffix)})` : ""}</span>
            <input type="number" min="${escapeHtml(field.min)}" max="${escapeHtml(field.max)}" step="1" value="${escapeHtml(value)}"
              data-spawn-number data-symbol="${escapeHtml(field.symbol)}" data-original="${escapeHtml(original)}">
          </label>`;
      }).join("");
    }).join("");
  }

  function spawnSettingsSection() {
    const groups = asArray(model.data.spawnSettings);
    if (!groups.length) return "";
    return `
      <details class="v2-disclosure v2-global-settings">
        <summary><span>Global spawn settings</span><small>${model.spawnDrafts.size} changed</small></summary>
        ${groups.map((group) => `
          <details class="v2-nested-disclosure">
            <summary>${escapeHtml(group.label)}</summary>
            <div class="v2-compact-grid">${spawnSettingRows(group)}</div>
          </details>`).join("")}
      </details>`;
  }

  function speciesOptions() {
    return `<datalist id="${ROUTE_SPECIES_LIST_ID}">${model.species.map((species) =>
      `<option value="${escapeHtml(shortSpeciesSymbol(species.symbol))}">${escapeHtml(species.name || species.symbol)}</option>`
    ).join("")}</datalist>`;
  }

  function renderInspector() {
    if (!inspector) return;
    const route = selectedRoute();
    if (!route) {
      inspector.innerHTML = `<p class="v2-empty">No route selected.</p>${spawnSettingsSection()}${speciesOptions()}`;
      return;
    }
    const edits = routeChangeCount(route.id);
    inspector.innerHTML = `
      <header class="v2-inspector-header">
        <div>
          <span class="v2-eyebrow">Encounter data #${escapeHtml(route.id)}</span>
          <h2>${escapeHtml(route.name)}</h2>
          <p>${escapeHtml(mapLabel(route))} · ${escapeHtml(route.speciesCount ?? asArray(route.species).length)} species</p>
        </div>
        <span class="v2-change-chip${edits ? " is-dirty" : ""}">${edits ? `${edits} changed` : "Source"}</span>
      </header>
      ${ratesSection(route)}
      ${overrideSection(route)}
      ${grassSection(route)}
      <section class="v2-disclosure-stack" aria-label="Encounter tables">
        ${asArray(route.pokemonTables).map((table) => pokemonTable(route, table)).join("")}
        ${asArray(route.slotTables).map((table) => levelTable(route, table)).join("")}
        ${asArray(route.headbuttTables).map((table) => levelTable(route, table)).join("")}
        ${swarmsSection(route)}
      </section>
      ${spawnSettingsSection()}
      ${speciesOptions()}`;
  }

  function render() {
    renderLibrary();
    renderInspector();
  }

  function applyNumberInput(input) {
    const valid = numberIsValid(input.value, input.min || null, input.max || null);
    input.setAttribute("aria-invalid", String(!valid));
    if (!valid) return false;
    setEncounterDraft(input.dataset.routeId, input.dataset.path, input.value, input.dataset.original);
    input.closest(".v2-field")?.classList.toggle(
      "is-dirty",
      effective(input.dataset.routeId, input.dataset.path, input.dataset.original) !== String(input.dataset.original),
    );
    signalDirty();
    renderLibrary();
    return true;
  }

  function applySpeciesInput(input) {
    const option = resolveSpecies(input.value);
    input.setAttribute("aria-invalid", String(!option));
    if (!option) {
      notify(setStatus, "Choose a valid Pokémon.", "error");
      return false;
    }
    const write = speciesWrite(option);
    setEncounterDraft(input.dataset.routeId, input.dataset.path, write.symbol, input.dataset.original);
    setEncounterDraft(input.dataset.routeId, input.dataset.formPath, write.form, input.dataset.formOriginal || 0);
    input.value = shortSpeciesSymbol(option.symbol);
    const formInput = Array.from(input.parentElement?.querySelectorAll("[data-path]") || [])
      .find((candidate) => candidate.dataset.path === input.dataset.formPath);
    if (formInput) formInput.value = write.form;
    input.closest(".v2-field")?.classList.toggle(
      "is-dirty",
      effective(input.dataset.routeId, input.dataset.path, input.dataset.original) !== String(input.dataset.original)
        || effective(input.dataset.routeId, input.dataset.formPath, input.dataset.formOriginal || 0) !== String(input.dataset.formOriginal || 0),
    );
    signalDirty();
    renderLibrary();
    return true;
  }

  function applySpawnInput(input, species = false) {
    const original = input.dataset.original || "";
    let value = input.value;
    let valid = true;
    if (species) {
      const option = resolveSpecies(value);
      valid = Boolean(option);
      if (option) {
        value = speciesWrite(option).symbol;
        input.value = shortSpeciesSymbol(option.symbol);
      }
    } else {
      valid = numberIsValid(value, input.min || null, input.max || null);
    }
    input.setAttribute("aria-invalid", String(!valid));
    if (!valid) {
      notify(setStatus, species ? "Choose a valid Pokémon." : "Use a value within the shown range.", "error");
      return false;
    }
    setSpawnDraft(input.dataset.symbol, value, original);
    input.closest(".v2-field")?.classList.toggle("is-dirty", model.spawnDrafts.has(input.dataset.symbol));
    signalDirty();
    return true;
  }

  function overrideBaselineEntries(route, targets) {
    const pending = model.overrideDrafts.get(String(route.id));
    if (pending?.action === "set" && asArray(pending.entries).length) return pending.entries;
    if (asArray(route.encounterOverride?.entries).length) return route.encounterOverride.entries;
    return targets.map((target) => ({
      path: target.path,
      formPath: target.formPath,
      species: target.originalSymbol,
      form: String(target.originalForm || 0),
    }));
  }

  function setRouteOverride(route, option) {
    const targets = encounterTargets(route);
    if (!targets.length) {
      notify(setStatus, `${route.name} has no enabled encounter slots.`, "error");
      return false;
    }
    const write = speciesWrite(option);
    const saved = route.encounterOverride;
    if (!model.overrideDrafts.has(String(route.id))
        && saved
        && String(saved.species) === write.symbol
        && String(saved.form || 0) === write.form) {
      notify(setStatus, "That route-only encounter is already active.");
      return false;
    }
    const entries = overrideBaselineEntries(route, targets);
    targets.forEach((target) => {
      setEncounterDraft(route.id, target.path, write.symbol, target.originalSymbol);
      setEncounterDraft(route.id, target.formPath, write.form, target.originalForm);
    });
    model.overrideDrafts.set(String(route.id), {
      action: "set",
      species: write.symbol,
      form: write.form,
      entries,
    });
    signalDirty();
    render();
    notify(setStatus, `${route.name} now drafts only ${option.name || shortSpeciesSymbol(option.symbol)}.`, "success");
    return true;
  }

  async function clearRouteOverride(route) {
    const pending = model.overrideDrafts.get(String(route.id));
    const saved = route.encounterOverride;
    if (!pending && !saved) return false;
    if (!await ask(confirmAction, `Turn off the route-only encounter for ${route.name}?`)) return false;

    const entries = pending?.action === "set" && asArray(pending.entries).length
      ? pending.entries
      : asArray(saved?.entries);
    entries.forEach((entry) => {
      setEncounterDraft(route.id, entry.path, entry.species, baseline(route.id, entry.path, entry.species));
      setEncounterDraft(route.id, entry.formPath, entry.form || 0, baseline(route.id, entry.formPath, entry.form || 0));
    });
    if (saved) model.overrideDrafts.set(String(route.id), { action: "clear" });
    else model.overrideDrafts.delete(String(route.id));
    signalDirty();
    render();
    notify(setStatus, `${route.name} route-only encounter is off.`, "success");
    return true;
  }

  function routePayload() {
    const changes = {};
    model.encounterDrafts.forEach((value, key) => {
      const [routeId, path] = splitBaselineKey(key);
      (changes[routeId] ||= {})[path] = value;
    });
    const overrides = {};
    model.overrideDrafts.forEach((operation, routeId) => {
      if (operation.action === "clear") {
        overrides[routeId] = { action: "clear" };
      } else {
        overrides[routeId] = {
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
      }
    });
    return { changes, overrides };
  }

  function commitPayload() {
    const payload = {};
    if (model.encounterDrafts.size || model.overrideDrafts.size) {
      payload.encounters = routePayload();
    }
    if (model.spawnDrafts.size) {
      payload.spawnSettings = { changes: Object.fromEntries(model.spawnDrafts) };
    }
    return payload;
  }

  function clearCommitted(scope = "all") {
    if (scope === "all" || scope === "encounters" || scope === "/save-encounters") {
      model.encounterDrafts.clear();
      model.overrideDrafts.clear();
    }
    if (scope === "all" || scope === "spawnSettings" || scope === "/save-spawn-settings") {
      model.spawnDrafts.clear();
    }
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

    if (!model.routesById.has(String(model.selectedRouteId))) {
      model.selectedRouteId = model.routes[0]?.id ?? null;
    }
    render();
    return controller;
  }

  function destroy() {
    abort.abort();
  }

  if (search) {
    search.addEventListener("input", () => {
      model.query = search.value.trim().toLowerCase();
      renderLibrary();
    }, { signal: abort.signal });
  }
  library?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-route-select]");
    if (!button) return;
    model.selectedRouteId = button.dataset.routeSelect;
    render();
  }, { signal: abort.signal });
  inspector?.addEventListener("input", (event) => {
    const input = event.target;
    if (input.matches("[data-route-number]")) applyNumberInput(input);
    else if (input.matches("[data-spawn-number]")) applySpawnInput(input);
  }, { signal: abort.signal });
  inspector?.addEventListener("change", (event) => {
    const input = event.target;
    if (input.matches("[data-route-species]")) applySpeciesInput(input);
    else if (input.matches("[data-spawn-species]")) applySpawnInput(input, true);
  }, { signal: abort.signal });
  inspector?.addEventListener("click", async (event) => {
    const action = event.target.closest("[data-action]")?.dataset.action;
    const route = selectedRoute();
    if (!route || !action) return;
    if (action === "set-route-override") {
      const input = inspector.querySelector("[data-route-override-input]");
      const option = resolveSpecies(input?.value);
      input?.setAttribute("aria-invalid", String(!option || option.symbol === "SPECIES_NONE"));
      if (!option || option.symbol === "SPECIES_NONE") {
        notify(setStatus, "Choose a valid Pokémon for the route-only encounter.", "error");
        return;
      }
      setRouteOverride(route, option);
    } else if (action === "clear-route-override") {
      await clearRouteOverride(route);
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
    commitPayload,
    clearCommitted,
    reset,
    refresh,
    destroy,
  };

  refresh();
  return controller;
}

export function createSoundsController({
  state: appState = {},
  api = null,
  elements = {},
  setStatus = null,
  markDirty = null,
  confirmAction = null,
} = {}) {
  void markDirty;
  void confirmAction;
  const search = elementFrom(elements, "soundSearch");
  const filters = elementFrom(elements, "soundFilters");
  const library = elementFrom(elements, "soundLibrary");
  const inspector = elementFrom(elements, "soundInspector");
  const statusElement = elementFrom(elements, "soundStatus");
  const abort = new AbortController();

  const model = {
    payload: null,
    effects: [],
    selectedId: null,
    query: "",
    filter: "all",
    importedAudio: new Map(),
    audio: null,
    objectUrl: null,
    fetchAbort: null,
    audioContext: null,
    playbackNodes: [],
    loadGeneration: 0,
  };

  function setSoundStatus(message, tone = "ready") {
    if (statusElement) {
      statusElement.textContent = message || "";
      statusElement.dataset.tone = tone;
    }
  }

  function effectById(id) {
    return model.effects.find((effect) => Number(effect.id) === Number(id)) || null;
  }

  function selectedEffect() {
    return effectById(model.selectedId) || model.effects[0] || null;
  }

  function groupLabel(effect) {
    const bank = String(effect.bank || "");
    const groups = asArray(effect.groups);
    if (effect.isMoveSoundEffect) return "Move";
    if (!effect.isSoundEffect && String(effect.name || "").startsWith("SEQ_ME_")) return "ME";
    if (bank === "BANK_BASIC") return "Basic";
    if (groups.some((group) => group.includes("FIELD"))) return "Field";
    if (groups.some((group) => group.includes("BATTLE"))) return "Battle";
    return groups[0]?.replace(/^GROUP_SE_/, "") || bank.replace(/^BANK_SE_/, "") || "Sequence";
  }

  function matchesFilter(effect) {
    const bank = String(effect.bank || "").toUpperCase();
    const groups = asArray(effect.groups).join(" ").toUpperCase();
    if (model.filter === "effects") return Boolean(effect.isSoundEffect);
    if (model.filter === "moves") return Boolean(effect.isMoveSoundEffect || asArray(effect.moveAliases).length);
    if (model.filter === "field") return bank.includes("FIELD") || groups.includes("FIELD");
    if (model.filter === "battle") return bank.includes("BATTLE") || groups.includes("BATTLE");
    if (model.filter === "tester") return Boolean(effect.inTesterRange);
    if (model.filter === "extra") return !effect.isSoundEffect;
    return true;
  }

  function soundSearchText(effect) {
    return [
      effect.id,
      effect.name,
      effect.shortName,
      effect.fileName,
      effect.bank,
      effect.player,
      ...asArray(effect.groups),
      ...asArray(effect.moveAliases).flatMap((alias) => [
        alias.moveName,
        alias.moveSymbol,
        alias.command,
        alias.commandText,
      ]),
    ].join(" ").toLowerCase();
  }

  function visibleEffects() {
    return model.effects.filter((effect) => matchesFilter(effect)
      && (!model.query || soundSearchText(effect).includes(model.query)));
  }

  function renderFilters() {
    if (!filters) return;
    filters.innerHTML = `<legend class="sr-only">Sound effect filters</legend>${SOUND_FILTERS.map(([key, label]) => `
      <button type="button" class="filter-chip v2-filter-chip${model.filter === key ? " is-active" : ""}"
        data-sound-filter="${key}" aria-pressed="${model.filter === key}">${label}</button>`).join("")}`;
  }

  function displaySoundName(effect) {
    const aliases = [];
    asArray(effect.moveAliases).forEach((alias) => {
      if (alias.moveName && !aliases.includes(alias.moveName)) aliases.push(alias.moveName);
    });
    return aliases.slice(0, 2).join(", ") || effect.shortName || effect.name;
  }

  function renderLibrary() {
    if (!library) return;
    const visible = visibleEffects();
    if (!visible.some((effect) => Number(effect.id) === Number(model.selectedId))) {
      model.selectedId = visible[0]?.id ?? model.effects[0]?.id ?? null;
    }
    library.innerHTML = visible.length ? visible.map((effect) => `
      <button class="v2-library-row v2-sound-row${Number(effect.id) === Number(model.selectedId) ? " is-selected" : ""}"
        type="button" data-sound-select="${escapeHtml(effect.id)}">
        <span class="v2-library-id">${escapeHtml(effect.id)}</span>
        <span class="v2-library-copy">
          <strong>${escapeHtml(displaySoundName(effect))}</strong>
          <small>${escapeHtml([effect.bank, effect.player].filter(Boolean).join(" · ") || effect.fileName)}</small>
        </span>
        <span class="v2-library-tag">${escapeHtml(groupLabel(effect))}</span>
      </button>`).join("") : `<p class="v2-empty">No sounds match the current filters.</p>`;
  }

  function importedAudioFor(effect) {
    if (!effect) return null;
    const keys = [
      effect.id,
      String(effect.id).padStart(4, "0"),
      effect.name,
      effect.shortName,
      String(effect.fileName || "").replace(/\.[^.]+$/, ""),
    ].map((value) => String(value || "").toUpperCase());
    return keys.map((key) => model.importedAudio.get(key)).find(Boolean) || null;
  }

  function detailField(label, value) {
    return `<div class="v2-readonly-field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "—")}</strong></div>`;
  }

  function renderInspector() {
    if (!inspector) return;
    const effect = selectedEffect();
    if (!effect) {
      inspector.innerHTML = `<p class="v2-empty">Select a sound effect.</p>`;
      return;
    }
    const aliases = asArray(effect.moveAliases);
    const local = importedAudioFor(effect);
    inspector.innerHTML = `
      <header class="v2-inspector-header">
        <div>
          <span class="v2-eyebrow">Sequence ${escapeHtml(effect.id)}</span>
          <h2>${escapeHtml(displaySoundName(effect))}</h2>
          <p>${escapeHtml(effect.name)} · ${escapeHtml(effect.fileName || "No SSEQ file")}</p>
        </div>
        <span class="v2-change-chip">${escapeHtml(groupLabel(effect))}</span>
      </header>
      <div class="v2-sound-actions">
        <button type="button" data-sound-action="real"${effect.hasSseq ? "" : " disabled"}>Play real</button>
        <button type="button" data-sound-action="raw"${effect.hasSseq ? "" : " disabled"}>Play raw SEQ</button>
        <button type="button" data-sound-action="approx">Approximate</button>
        <button type="button" data-sound-action="local"${local ? "" : " disabled"}>Play imported</button>
        <button type="button" data-sound-action="stop">Stop</button>
      </div>
      <canvas class="v2-waveform" data-sound-waveform width="720" height="112" aria-label="Sound waveform"></canvas>
      <div class="v2-readonly-grid">
        ${detailField("Bank", effect.bank)}
        ${detailField("Player", effect.player)}
        ${detailField("Volume", effect.volume)}
        ${detailField("Priority", [effect.channelPriority, effect.playerPriority].filter((value) => value != null).join(" / "))}
        ${detailField("SSEQ", effect.hasSseq ? `${effect.sseqBytes} bytes` : "Missing")}
      </div>
      ${aliases.length ? `
        <details class="v2-disclosure" open>
          <summary><span>Move uses</span><small>${aliases.length}</small></summary>
          <div class="v2-chip-list">${aliases.map((alias) => `
            <button type="button" data-move-preview="${escapeHtml(alias.moveId || "")}"${alias.moveId ? "" : " disabled"}
              title="${escapeHtml(alias.commandText || alias.command || "Move sequence")}">${escapeHtml(alias.moveName || alias.moveSymbol)}</button>`).join("")}</div>
        </details>` : ""}
      <details class="v2-disclosure">
        <summary><span>Local reference audio</span><small>${model.importedAudio.size ? `${model.importedAudio.size} loaded` : "Optional"}</small></summary>
        <label class="v2-file-picker">
          <span>Import audio files</span>
          <input type="file" accept="audio/*,.wav,.ogg,.mp3" multiple data-sound-import>
        </label>
        <p class="v2-help">Names are matched against sequence ID, symbol, short name, or SSEQ filename. Files remain local to this page.</p>
      </details>`;
    drawPlaceholder(effect);
  }

  function render() {
    renderFilters();
    renderLibrary();
    renderInspector();
  }

  function waveformCanvas() {
    return inspector?.querySelector("[data-sound-waveform]") || null;
  }

  function drawBars(values, color = "#3b82f6") {
    const canvas = waveformCanvas();
    const context = canvas?.getContext?.("2d");
    if (!canvas || !context) return;
    const { width, height } = canvas;
    context.clearRect(0, 0, width, height);
    context.fillStyle = "rgba(148, 163, 184, .08)";
    context.fillRect(0, 0, width, height);
    context.strokeStyle = "rgba(148, 163, 184, .45)";
    context.beginPath();
    context.moveTo(0, height / 2);
    context.lineTo(width, height / 2);
    context.stroke();
    if (!values.length) return;
    const step = width / values.length;
    context.fillStyle = color;
    values.forEach((value, index) => {
      const barHeight = Math.max(2, Math.min(1, value) * height * 0.86);
      context.fillRect(index * step, (height - barHeight) / 2, Math.max(1, step - 1), barHeight);
    });
  }

  function drawPlaceholder(effect) {
    if (!effect) return drawBars([]);
    const name = String(effect.name || "");
    const values = Array.from({ length: 64 }, (_, index) => {
      const char = name.charCodeAt(index % Math.max(1, name.length)) || 1;
      return 0.12 + ((Number(effect.id || 0) * 17 + char * 7 + index * 29) % 83) / 100;
    });
    drawBars(values, "#64748b");
  }

  async function ensureAudioContext() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) throw new Error("Web Audio is unavailable in this browser");
    if (!model.audioContext) model.audioContext = new AudioContextClass();
    if (model.audioContext.state === "suspended") await model.audioContext.resume();
    return model.audioContext;
  }

  async function drawBlobWaveform(blob) {
    try {
      const context = await ensureAudioContext();
      const buffer = await context.decodeAudioData(await blob.arrayBuffer());
      const samples = buffer.getChannelData(0);
      const bucketCount = 128;
      const bucketSize = Math.max(1, Math.floor(samples.length / bucketCount));
      const values = Array.from({ length: bucketCount }, (_, bucket) => {
        let peak = 0;
        const start = bucket * bucketSize;
        const end = Math.min(samples.length, start + bucketSize);
        for (let index = start; index < end; index += 1) peak = Math.max(peak, Math.abs(samples[index]));
        return peak;
      });
      drawBars(values);
    } catch (_error) {
      drawPlaceholder(selectedEffect());
    }
  }

  function stop() {
    model.fetchAbort?.abort();
    model.fetchAbort = null;
    if (model.audio) {
      model.audio.pause();
      model.audio.currentTime = 0;
      model.audio = null;
    }
    if (model.objectUrl) {
      URL.revokeObjectURL(model.objectUrl);
      model.objectUrl = null;
    }
    model.playbackNodes.forEach((node) => {
      try {
        node.stop?.();
        node.disconnect?.();
      } catch (_error) {
        // A stopped Web Audio node throws if stopped again.
      }
    });
    model.playbackNodes = [];
    setSoundStatus("Stopped.");
  }

  async function playBlob(blob, label) {
    stop();
    model.objectUrl = URL.createObjectURL(blob);
    if (typeof Audio !== "function") throw new Error("HTML audio playback is unavailable");
    model.audio = new Audio(model.objectUrl);
    model.audio.preload = "auto";
    model.audio.addEventListener("ended", () => setSoundStatus(`Finished ${label}.`), { once: true });
    const [, playback] = await Promise.allSettled([drawBlobWaveform(blob), model.audio.play()]);
    if (playback.status === "rejected") throw playback.reason;
    setSoundStatus(`Playing ${label}.`, "success");
  }

  async function playUrl(url, label) {
    stop();
    const controller = new AbortController();
    model.fetchAbort = controller;
    const timeout = setTimeout(() => controller.abort(), 20000);
    setSoundStatus(`Rendering ${label}…`);
    try {
      const response = await fetch(url, { cache: "no-store", signal: controller.signal });
      if (!response.ok) {
        let message = `Sound render failed (${response.status})`;
        try {
          const payload = await response.json();
          if (payload.error) message = payload.error;
        } catch (_error) {
          // The legacy audio route may return plain text for an error.
        }
        throw new Error(message);
      }
      await playBlob(await response.blob(), label);
    } catch (error) {
      const message = error.name === "AbortError" ? "Sound rendering timed out." : error.message;
      setSoundStatus(message, "error");
    } finally {
      clearTimeout(timeout);
      if (model.fetchAbort === controller) model.fetchAbort = null;
    }
  }

  async function playReal(effect) {
    const alias = asArray(effect?.moveAliases).find((item) => item.moveId);
    if (alias) {
      await playUrl(
        `/move-sound-effects/${encodeURIComponent(alias.moveId)}.wav`,
        `${alias.moveName || effect.name} move preview`,
      );
    } else if (effect?.hasSseq) {
      await playUrl(`/sound-effects/${encodeURIComponent(effect.id)}.wav`, effect.name);
    }
  }

  async function playApproximate(effect) {
    try {
      stop();
      const context = await ensureAudioContext();
      const master = context.createGain();
      master.gain.value = Math.min(0.35, Math.max(0.06, Number(effect.volume || 90) / 300));
      master.connect(context.destination);
      model.playbackNodes.push(master);
      const start = context.currentTime + 0.015;
      const base = 170 + (Number(effect.id || 0) % 38) * 17;
      const pulses = String(effect.name || "").includes("KIRAKIRA") ? 5 : 3;
      const duration = 0.42;
      for (let index = 0; index < pulses; index += 1) {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        const pulseStart = start + index * (duration / pulses);
        oscillator.type = String(effect.bank || "").includes("FIELD") ? "triangle" : "square";
        oscillator.frequency.setValueAtTime(base * (1 + index * 0.12), pulseStart);
        gain.gain.setValueAtTime(0.001, pulseStart);
        gain.gain.exponentialRampToValueAtTime(0.8, pulseStart + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.001, pulseStart + duration / pulses);
        oscillator.connect(gain);
        gain.connect(master);
        oscillator.start(pulseStart);
        oscillator.stop(pulseStart + duration / pulses + 0.02);
        model.playbackNodes.push(oscillator, gain);
      }
      setSoundStatus(`Approximate preview for ${effect.name}; not the DS render.`);
    } catch (error) {
      setSoundStatus(error.message, "error");
    }
  }

  function importFiles(files) {
    let count = 0;
    Array.from(files || []).forEach((file) => {
      const key = String(file.name || "").replace(/\.[^.]+$/, "").toUpperCase();
      if (!key) return;
      model.importedAudio.set(key, file);
      count += 1;
    });
    renderInspector();
    setSoundStatus(`${count} local audio file${count === 1 ? "" : "s"} loaded.`, "success");
  }

  async function refresh(payload = null) {
    const generation = ++model.loadGeneration;
    setSoundStatus("Loading sound effects…");
    try {
      const statePayload = payload?.effects
        ? payload
        : appState?.soundEffectsPayload || appState?.sounds || null;
      const next = statePayload || await getJson(api, "/sound-effects", { cache: "no-store" });
      if (generation !== model.loadGeneration) return controller;
      model.payload = next || {};
      model.effects = asArray(next?.effects);
      if (!effectById(model.selectedId)) {
        model.selectedId = next?.tester?.initial || model.effects[0]?.id || null;
      }
      render();
      setSoundStatus(`${model.effects.length} sound sequences loaded.`, "success");
    } catch (error) {
      if (generation !== model.loadGeneration) return controller;
      model.effects = [];
      render();
      setSoundStatus(`Could not load sounds: ${error.message}`, "error");
    }
    return controller;
  }

  function clearCommitted() {}

  function reset() {
    stop();
    model.query = "";
    model.filter = "all";
    if (search) search.value = "";
    render();
  }

  function destroy() {
    abort.abort();
    model.loadGeneration += 1;
    stop();
    model.audioContext?.close?.();
    model.audioContext = null;
    model.importedAudio.clear();
  }

  search?.addEventListener("input", () => {
    model.query = search.value.trim().toLowerCase();
    renderLibrary();
    renderInspector();
  }, { signal: abort.signal });
  filters?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-sound-filter]");
    if (!button) return;
    model.filter = button.dataset.soundFilter;
    render();
  }, { signal: abort.signal });
  library?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-sound-select]");
    if (!button) return;
    model.selectedId = Number(button.dataset.soundSelect);
    render();
  }, { signal: abort.signal });
  inspector?.addEventListener("change", (event) => {
    if (event.target.matches("[data-sound-import]")) importFiles(event.target.files);
  }, { signal: abort.signal });
  inspector?.addEventListener("click", async (event) => {
    const effect = selectedEffect();
    if (!effect) return;
    try {
      const move = event.target.closest("[data-move-preview]");
      if (move?.dataset.movePreview) {
        const alias = asArray(effect.moveAliases).find((item) => String(item.moveId) === move.dataset.movePreview);
        await playUrl(
          `/move-sound-effects/${encodeURIComponent(move.dataset.movePreview)}.wav`,
          `${alias?.moveName || effect.name} move preview`,
        );
        return;
      }
      const action = event.target.closest("[data-sound-action]")?.dataset.soundAction;
      if (action === "real") await playReal(effect);
      else if (action === "raw") await playUrl(`/sound-effects/${encodeURIComponent(effect.id)}.wav`, `${effect.name} raw sequence`);
      else if (action === "approx") await playApproximate(effect);
      else if (action === "local") {
        const file = importedAudioFor(effect);
        if (file) await playBlob(file, file.name);
      } else if (action === "stop") stop();
    } catch (error) {
      setSoundStatus(`Could not play sound: ${error.message}`, "error");
    }
  }, { signal: abort.signal });

  const controller = {
    state: model,
    hasChanges() { return false; },
    changeCount() { return 0; },
    commitPayload() { return {}; },
    clearCommitted,
    reset,
    refresh,
    stop,
    destroy,
    ready: Promise.resolve(),
  };
  return controller;
}
