/*
 * Overworld Viewer V2 — Pokédex Index
 *
 * The Pokémon workspace exposes source-backed Entry and Battle draft editors
 * when the endpoint advertises those write domains. All other domains remain
 * reference views, and persistence stays behind the shared commit boundary.
 */

const DOMAIN_TABS = Object.freeze([
  ["entry", "Entry"],
  ["battle", "Battle"],
  ["growth", "Growth"],
  ["moves", "Moves"],
  ["evolution", "Evolution"],
  ["forms", "Forms"],
  ["assets", "Assets"],
]);

const LIST_ROW_HEIGHT = 58;
const LIST_OVERSCAN = 7;
const COMBOBOX_WINDOW_SIZE = 12;
const COMBOBOX_LIST_ID = "pv2-pokemon-shared-combobox-list";
const MOVE_ROW_HEIGHT = 60;
const MOVE_WINDOW_SIZE = 28;
const MOVE_GROUPS = Object.freeze([
  ["levelMoves", "Level"],
  ["machineMoves", "Machines"],
  ["tutorMoves", "Tutors"],
  ["eggMoves", "Egg"],
]);
const ASSET_SLOTS = Object.freeze([
  ["icon", "Menu icon"],
  ["follower", "Overworld follower"],
  ["maleFront", "Front"],
  ["femaleFront", "Female front"],
  ["maleBack", "Back"],
  ["femaleBack", "Female back"],
]);
const STORAGE_SELECTION_KEY = "ow-v2-pokemon-selection";
const STORAGE_SECTIONS_KEY = "ow-v2-pokemon-sections";
const STORAGE_SEARCH_KEY = "ow-v2-pokemon-search";
const STORAGE_TYPE_KEY = "ow-v2-pokemon-type";
const STORAGE_SCOPE_KEY = "ow-v2-pokemon-scope";

const ENTRY_ROOT_KEYS = new Set([
  "category", "classification", "description", "dexEntry", "flavorText", "height",
  "weight", "genderRatio", "eggGroups", "habitat", "color", "shape", "footprint",
  "generation", "region", "isLegendary", "isMythical", "isBaby",
]);

const BATTLE_ROOT_KEYS = new Set([
  "types", "type1", "type2", "abilities", "ability1", "ability2", "hiddenAbility",
  "baseStats", "stats", "evYield", "evYields", "catchRate", "baseExperience", "baseExp",
  "personalBaseExperience", "heldItems", "heldItem", "runChance", "escapeRate",
  "bodyColor", "flipSprite",
]);

const DOMAIN_ROOT_KEYS = Object.freeze({
  entry: ENTRY_ROOT_KEYS,
  battle: BATTLE_ROOT_KEYS,
  growth: new Set(["growthRate", "eggCycles", "baseFriendship", "genderRatio", "eggGroups"]),
  moves: new Set(["learnset", "learnsetSummary", "moves"]),
  evolution: new Set(["evolutions", "evolution"]),
  forms: new Set(["forms", "baseSymbol", "baseValue", "isForm", "formIndex"]),
  assets: new Set(["assets", "graphics", "sprites"]),
  technical: new Set(["id", "symbol", "value", "order", "sourceOrder", "source"]),
});

const DOMAIN_ALIASES = Object.freeze({
  entry: ["entry", "dex", "pokedex", "encyclopedia", "identity"],
  battle: ["battle", "combat", "battleData"],
  growth: ["growth", "breeding", "training"],
  moves: ["moves", "learnset", "moveData"],
  evolution: ["evolution", "evolutions", "evolutionData"],
  forms: ["forms", "variants", "formData"],
  assets: ["assets", "graphics", "sprites", "spriteData"],
  technical: ["technical", "source", "rawValues"],
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined || value === "") return [];
  if (typeof value === "object") {
    return Object.entries(value).map(([key, entry]) => (
      entry && typeof entry === "object" ? { key, ...entry } : { key, value: entry }
    ));
  }
  return [value];
}

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function firstDefined(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== "");
}

function textValue(...values) {
  const value = firstDefined(...values);
  return value === undefined || value === null ? "" : String(value);
}

function humanize(value) {
  return String(value ?? "")
    .replace(/^SPECIES_/, "")
    .replace(/^TYPE_/, "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function compact(value) {
  return String(value ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function valueLabel(value) {
  if (value === null || value === undefined || value === "") return "Not provided";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map(valueLabel).join(", ");
  if (isRecord(value)) {
    const label = firstDefined(value.label, value.name, value.displayName, value.text);
    const raw = firstDefined(value.raw, value.symbol, value.key);
    const numeric = firstDefined(value.value, value.id, value.index);
    if (label && raw && String(label) !== String(raw)) return `${label} · ${raw}`;
    const chosen = firstDefined(label, raw, numeric, JSON.stringify(value));
    return chosen === undefined ? "Not provided" : String(chosen);
  }
  return String(value);
}

function optionKey(value) {
  return compact(firstDefined(value?.symbol, value?.key, value?.raw, value?.name, value?.label, value));
}

function optionLabel(value) {
  const chosen = firstDefined(value?.name, value?.label, value?.displayName, humanize(firstDefined(value?.symbol, value?.key, value?.raw, value)));
  return chosen === undefined ? "Not provided" : String(chosen);
}

function normalizeTypes(entry) {
  const source = firstDefined(
    entry.types,
    entry.battle?.types,
    entry.type,
    [entry.type1, entry.type2].filter(Boolean),
  );
  const seen = new Set();
  return asArray(source).map((type) => {
    const key = optionKey(type);
    return { key, label: optionLabel(type), raw: firstDefined(type?.symbol, type?.raw, type?.key, type) };
  }).filter((type) => type.key && !seen.has(type.key) && seen.add(type.key));
}

function isReservedSpecies(entry, symbol, name) {
  if (entry.reserved === true || entry.sentinel === true || entry.hidden === true || entry.isReserved === true) return true;
  if (!name || /^-+$/.test(name.trim())) return true;
  return /(?:^SPECIES_NONE$|^SPECIES_EGG$|BAD_EGG|FILLER|UNUSED|RESERVED|_START$|_END$)/.test(symbol);
}

function urlValue(value) {
  return textValue(value?.url, value?.href, value?.path, typeof value === "string" ? value : "");
}

function normalizeSpriteUrls(entry) {
  const sprites = isRecord(entry.sprites) ? entry.sprites : {};
  const assets = isRecord(entry.assets) ? entry.assets : {};
  const iconUrl = textValue(
    entry.iconUrl,
    urlValue(entry.icon),
    urlValue(sprites.icon),
    urlValue(assets.icon),
    assets.iconUrl,
    "",
  );
  const frontUrl = textValue(
    entry.frontSpriteUrl,
    entry.spriteUrl,
    urlValue(entry.frontSprite),
    urlValue(entry.sprite),
    urlValue(sprites.front),
    urlValue(sprites.frontDefault),
    urlValue(sprites.maleFront),
    urlValue(assets["male-front"]),
    urlValue(assets["female-front"]),
    urlValue(assets.front),
    assets.spriteUrl,
    "",
  );
  return { iconUrl, frontUrl };
}

function normalizeSpeciesEntry(rawEntry, fallbackKey, index) {
  const entry = isRecord(rawEntry) ? rawEntry : { name: rawEntry };
  const symbol = textValue(entry.symbol, entry.speciesSymbol, entry.key, fallbackKey, `SPECIES_${index}`);
  const dexNumber = firstDefined(
    entry.nationalDex,
    entry.nationalDexNumber,
    entry.dexNumber,
    entry.dex?.number,
    entry.dex?.national,
    entry.dex?.id,
    entry.pokedexNumber,
    entry.number,
    entry.id,
    entry.value,
  );
  const name = textValue(entry.name, entry.displayName, entry.label, humanize(symbol), "Unknown Pokémon");
  const formName = textValue(entry.formName, entry.form?.name, entry.form?.label, entry.formLabel, entry.formDisplayName, "");
  const types = normalizeTypes(entry);
  const spriteUrls = normalizeSpriteUrls(entry);
  const baseSymbol = textValue(entry.baseSymbol, entry.baseSpecies?.symbol, entry.baseSpecies, symbol);
  const formIndex = Number(firstDefined(entry.formIndex, entry.form?.index, entry.formId));
  const isForm = entry.isForm === true
    || entry.form?.isForm === true
    || (Number.isFinite(formIndex) && formIndex > 0)
    || Boolean(baseSymbol && symbol && baseSymbol !== symbol)
    || Boolean(formName);
  const aliases = asArray(firstDefined(entry.aliases, entry.searchAliases, [])).map(valueLabel);
  const dexNumeric = Number(dexNumber);
  const dexTokens = Number.isFinite(dexNumeric)
    ? [String(dexNumeric), String(dexNumeric).padStart(3, "0"), String(dexNumeric).padStart(4, "0")]
      .flatMap((token) => [token, `#${token}`])
    : [dexNumber].filter(Boolean).flatMap((token) => [String(token), `#${token}`]);
  const searchText = [name, symbol, formName, ...dexTokens, ...aliases, ...types.flatMap((type) => [type.key, type.label])]
    .filter((value) => value !== undefined && value !== null && value !== "").join(" ").toLowerCase();
  return {
    ...entry,
    __key: symbol || `${name}:${formName}:${index}`,
    __symbol: symbol,
    __name: name,
    __dexNumber: dexNumber,
    __formName: formName,
    __types: types,
    __isForm: isForm,
    __isReserved: isReservedSpecies(entry, symbol, name),
    __iconUrl: spriteUrls.iconUrl,
    __frontSpriteUrl: spriteUrls.frontUrl,
    __search: searchText,
    __searchCompact: compact(searchText),
  };
}

function unwrapPayload(payload) {
  const root = payload?.pokemonData || payload?.data || payload?.result || payload || {};
  const source = firstDefined(root.species, root.pokemon, root.entries, root.speciesOptions, []);
  const entries = Array.isArray(source)
    ? source.map((entry, index) => normalizeSpeciesEntry(entry, "", index))
    : Object.entries(source || {}).map(([key, entry], index) => normalizeSpeciesEntry(entry, key, index));
  const enums = root.enums || root.options || root.lookups || {};
  const capabilities = root.capabilities || {};
  return {
    species: entries.sort((left, right) => {
      const leftNumber = Number(left.__dexNumber);
      const rightNumber = Number(right.__dexNumber);
      if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber) && leftNumber !== rightNumber) return leftNumber - rightNumber;
      return left.__name.localeCompare(right.__name, undefined, { numeric: true });
    }),
    enums,
    sourceRevision: textValue(root.sourceRevision, payload?.sourceRevision, ""),
    assetRevision: textValue(root.assetRevision, payload?.assetRevision, ""),
    readOnly: root.readOnly !== false,
    summary: root.summary || {},
    capabilities,
    writeDomains: asArray(firstDefined(capabilities.writeDomains, capabilities.writableGroups, root.writeDomains, root.writableGroups, [])).map((domain) => textValue(domain).toLowerCase()),
    fieldRegistry: normalizeFieldRegistry(firstDefined(root.fieldRegistry, capabilities.fieldRegistry, {})),
    validationRules: asArray(firstDefined(capabilities.validationRules, root.validationRules, [])),
  };
}

function looksLikePokemonPayload(value) {
  const root = value?.pokemonData || value?.data || value;
  return Boolean(root && (root.species || root.pokemon || root.entries));
}

function commonAncestor(elements) {
  const candidates = [];
  let cursor = elements[0];
  while (cursor) {
    candidates.push(cursor);
    cursor = cursor.parentElement;
  }
  return candidates.find((candidate) => elements.every((element) => candidate.contains(element))) || document.body;
}

function readStorage(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value === null ? fallback : JSON.parse(value);
  } catch (_error) {
    return fallback;
  }
}

function writeStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (_error) {
    // Persistence is optional when storage is unavailable or restricted.
  }
}

function pathParts(path) {
  return String(path || "").replace(/\[(\d+)\]/g, ".$1").split(".").filter(Boolean);
}

function valueAtPath(source, path) {
  return pathParts(path).reduce((value, key) => value?.[key], source);
}

function fieldValueRaw(value) {
  if (isRecord(value)) return firstDefined(value.raw, value.symbol, value.value, value.id, value.name, "");
  return value ?? "";
}

function normalizeFieldRegistry(registry) {
  const result = [];
  const seen = new Set();
  const descriptorKeys = new Set(["path", "label", "type", "kind", "component", "control", "inputType", "enum", "enumKey", "options", "min", "max", "required", "nullable", "writable"]);
  const visit = (value, domain = "", pathHint = "") => {
    if (Array.isArray(value)) {
      value.forEach((item) => visit(item, domain, ""));
      return;
    }
    if (!isRecord(value)) return;
    const explicitPath = textValue(value.path, value.key, value.field, pathHint);
    const looksLikeDescriptor = Boolean(explicitPath && Object.keys(value).some((key) => descriptorKeys.has(key)));
    if (looksLikeDescriptor) {
      const normalizedDomain = textValue(value.domain, domain, explicitPath.split(".")[0]).toLowerCase();
      const id = `${normalizedDomain}:${explicitPath}`;
      if (!seen.has(id)) {
        seen.add(id);
        result.push({ ...value, path: explicitPath, domain: normalizedDomain });
      }
      return;
    }
    Object.entries(value).forEach(([key, item]) => {
      if (["fields", "descriptors", "registry"].includes(key)) visit(item, domain, "");
      else if (["entry", "battle"].includes(key.toLowerCase())) visit(item, key.toLowerCase(), "");
      else visit(item, domain, key);
    });
  };
  visit(registry);
  return result.sort((left, right) => Number(left.order || 0) - Number(right.order || 0));
}

function canonical(value) {
  return JSON.stringify(value === undefined ? null : value);
}

function domainSource(species, domain) {
  const aliases = DOMAIN_ALIASES[domain] || [domain];
  const direct = {};
  aliases.forEach((key) => {
    if (species[key] !== undefined && species[key] !== null) direct[key] = species[key];
  });
  const rootKeys = DOMAIN_ROOT_KEYS[domain];
  if (rootKeys) {
    rootKeys.forEach((key) => {
      if (species[key] !== undefined && species[key] !== null && direct[key] === undefined) direct[key] = species[key];
    });
  }
  return direct;
}

function leafRows(value, path = [], depth = 0) {
  if (depth > 7) return [{ label: path.map(humanize).join(" / "), value: JSON.stringify(value) }];
  if (Array.isArray(value)) {
    if (!value.length) return [];
    if (value.every((item) => !isRecord(item) && !Array.isArray(item))) {
      return [{ label: path.map(humanize).join(" / "), value }];
    }
    return value.flatMap((item, index) => leafRows(item, [...path, String(index + 1)], depth + 1));
  }
  if (isRecord(value)) {
    const entries = Object.entries(value).filter(([key, item]) => !key.startsWith("__") && item !== undefined && item !== null);
    if (!entries.length) return [];
    return entries.flatMap(([key, item]) => leafRows(item, [...path, key], depth + 1));
  }
  return [{ label: path.map(humanize).join(" / ") || "Value", value }];
}

function visualTypeKey(value) {
  return textValue(value, "unknown").toLowerCase().replace(/^type[_-]?/, "").replace(/[^a-z0-9]+/g, "-");
}

function renderTypePills(types) {
  return types.map((type) => `<span class="pv2-pokemon-type" data-type="${escapeHtml(visualTypeKey(type.key))}">${escapeHtml(type.label)}</span>`).join("");
}

function renderValue(value) {
  const label = valueLabel(value);
  const isPath = typeof value === "string" && (/[/\\]/.test(value) || /\.(?:png|gif|json|c|h|s|bin|narc)$/i.test(value));
  return `<span${isPath ? ' class="is-technical-value"' : ""}>${escapeHtml(label)}</span>`;
}

function renderReadOnlyDomain(species, domain) {
  const rows = leafRows(domainSource(species, domain));
  const title = domain === "entry" ? "Pokédex entry" : "Battle specification";
  const description = domain === "entry"
    ? "Identity, classification, physical data, and catalog metadata supplied by the source model."
    : "Typing, abilities, battle statistics, yields, and encounter-facing constants supplied by the source model.";
  return `<section class="pv2-pokemon-domain">
    <header><div><span class="pv2-pokemon-eyebrow">Read-only source view</span><h3>${title}</h3></div><small>${rows.length} values</small></header>
    <p class="pv2-pokemon-domain-intro">${description}</p>
    ${rows.length ? `<dl class="pv2-pokemon-data-grid">${rows.map((row) => `<div><dt>${escapeHtml(row.label)}</dt><dd>${renderValue(row.value)}</dd></div>`).join("")}</dl>` : `<div class="pv2-pokemon-empty"><strong>No ${escapeHtml(domain)} data was returned.</strong><span>The index will populate this section when the source endpoint exposes it.</span></div>`}
  </section>`;
}

function countDomainItems(source) {
  if (source === null || source === undefined || source === "") return 0;
  if (Array.isArray(source)) return source.length;
  if (isRecord(source)) return Object.keys(source).length;
  return 1;
}

function domainSummary(species, domain) {
  const source = domainSource(species, domain);
  const values = Object.values(source);
  const count = values.reduce((total, value) => total + countDomainItems(value), 0);
  if (domain === "growth") {
    const rate = firstDefined(species.growthRate, species.growth?.rate, species.growth?.growthRate);
    const friendship = firstDefined(species.baseFriendship, species.friendship, species.growth?.baseFriendship);
    return {
      kicker: "Training profile",
      title: rate ? valueLabel(rate) : "Growth model",
      summary: friendship !== undefined ? `Base friendship ${valueLabel(friendship)} · ${count} supplied values` : `${count} supplied growth and breeding values`,
    };
  }
  if (domain === "moves") {
    const learnsetSummary = species.learnsetSummary || species.learnset?.summary || species.learnset || {};
    const counts = learnsetSummary.counts || species.learnset?.counts || {};
    const moveCount = Object.values(counts).reduce((total, value) => total + (Number(value) || 0), 0);
    const provenance = firstDefined(learnsetSummary.provenance, species.learnset?.provenance, "not supplied");
    return {
      kicker: "Learnset index",
      title: `${moveCount || count} move references`,
      summary: `Source provenance: ${valueLabel(provenance)} · ${Object.keys(counts).length} learnset groups`,
    };
  }
  if (domain === "evolution") {
    const evolutions = firstDefined(species.evolutions, species.evolution, []);
    const paths = countDomainItems(evolutions);
    return { kicker: "Family graph", title: paths ? `${paths} evolution path${paths === 1 ? "" : "s"}` : "No evolution paths supplied", summary: paths ? `${count} source values describe evolution methods, parameters, and targets.` : "This record has no source evolution entries." };
  }
  if (domain === "forms") {
    const forms = firstDefined(species.forms, species.variants, species.formData, []);
    const formCount = countDomainItems(forms);
    return { kicker: "Variant registry", title: formCount ? `${formCount} related form${formCount === 1 ? "" : "s"}` : (species.__formName || "Base form"), summary: `${count} source values describe base identity, form index, and related variants.` };
  }
  const assets = firstDefined(species.assets, species.graphics, species.sprites, {});
  const assetCount = countDomainItems(assets);
  return { kicker: "Asset manifest", title: `${assetCount} linked asset${assetCount === 1 ? "" : "s"}`, summary: `${count} source values report availability and resolved asset locations.` };
}

function renderFoundationDomain(species, domain) {
  const summary = domainSummary(species, domain);
  const previewRows = leafRows(domainSource(species, domain)).slice(0, 6);
  return `<section class="pv2-pokemon-domain pv2-pokemon-domain--foundation">
    <header><div><span class="pv2-pokemon-eyebrow">${escapeHtml(summary.kicker)}</span><h3>${escapeHtml(summary.title)}</h3></div><small>Reference preview</small></header>
    <p class="pv2-pokemon-domain-intro">${escapeHtml(summary.summary)}</p>
    ${previewRows.length ? `<dl class="pv2-pokemon-preview-values">${previewRows.map((row) => `<div><dt>${escapeHtml(row.label)}</dt><dd>${renderValue(row.value)}</dd></div>`).join("")}</dl>` : `<p class="pv2-pokemon-future-note">No source values were returned for this domain. Editing is not available in this reference view.</p>`}
  </section>`;
}

export function createPokemonController({
  state = {},
  api,
  elements = {},
  setStatus = () => {},
  markDirty = () => {},
} = {}) {
  const element = (name) => elements[name] || document.getElementById(name);
  const searchElement = element("pokemonSearch");
  const typeFilterElement = element("pokemonTypeFilter");
  const stateFilterElement = element("pokemonStateFilter");
  const countElement = element("pokemonLibraryCount");
  const libraryElement = element("pokemonLibrary");
  const inspectorElement = element("pokemonInspector");
  const required = [searchElement, typeFilterElement, stateFilterElement, libraryElement, inspectorElement];
  if (!required.every((candidate) => candidate instanceof Element)) {
    throw new TypeError("Pokémon controller requires search, filters, library, and inspector elements");
  }
  if (!api) throw new TypeError("Pokémon controller requires an injected api");

  const root = commonAncestor(required);
  const libraryPanel = libraryElement.closest(".panel") || libraryElement.parentElement;
  const inspectorPanel = inspectorElement.closest(".panel") || inspectorElement.parentElement;
  root.classList.add("pv2-pokemon-workbench");
  libraryPanel?.classList.add("pv2-pokemon-library-panel");
  inspectorPanel?.classList.add("pv2-pokemon-inspector-panel");
  libraryElement.classList.add("pv2-pokemon-library");
  inspectorElement.classList.add("pv2-pokemon-inspector");

  const storedSections = readStorage(STORAGE_SECTIONS_KEY, {});
  const sectionBySpecies = state.pokemonSections instanceof Map
    ? state.pokemonSections
    : new Map(Object.entries(isRecord(storedSections) ? storedSections : {}));
  state.pokemonSections = sectionBySpecies;
  const drafts = state.pokemonDrafts instanceof Map ? state.pokemonDrafts : new Map();
  state.pokemonDrafts = drafts;
  const learnsetDrafts = state.pokemonLearnsetDrafts instanceof Map ? state.pokemonLearnsetDrafts : new Map();
  const evolutionDrafts = state.pokemonEvolutionDrafts instanceof Map ? state.pokemonEvolutionDrafts : new Map();
  const formDrafts = state.pokemonFormDrafts instanceof Map ? state.pokemonFormDrafts : new Map();
  const assetDrafts = state.pokemonAssetDrafts instanceof Map ? state.pokemonAssetDrafts : new Map();
  const learnsetDetails = state.pokemonLearnsetDetails instanceof Map ? state.pokemonLearnsetDetails : new Map();
  const editorOptionsByRevision = state.pokemonEditorOptionsByRevision instanceof Map ? state.pokemonEditorOptionsByRevision : new Map();
  state.pokemonLearnsetDrafts = learnsetDrafts;
  state.pokemonEvolutionDrafts = evolutionDrafts;
  state.pokemonFormDrafts = formDrafts;
  state.pokemonAssetDrafts = assetDrafts;
  state.pokemonLearnsetDetails = learnsetDetails;
  state.pokemonEditorOptionsByRevision = editorOptionsByRevision;
  const moveTabBySpecies = new Map();
  const moveSearchBySpecies = new Map();
  const moveWindowBySpecies = new Map();
  const familyStageSummaries = new Map();
  let projectedFamilyGraphCache = null;
  const storedSelection = readStorage(STORAGE_SELECTION_KEY, "");
  const storedSearch = readStorage(STORAGE_SEARCH_KEY, "");
  const storedType = readStorage(STORAGE_TYPE_KEY, "all");
  const storedScope = readStorage(STORAGE_SCOPE_KEY, "all");
  const ui = {
    search: typeof storedSearch === "string" ? storedSearch : "",
    pendingSearch: typeof storedSearch === "string" ? storedSearch : "",
    type: typeof storedType === "string" ? storedType : "all",
    scope: ["all", "base", "forms"].includes(storedScope) ? storedScope : "all",
    selectedKey: state.selectedPokemonKey || (typeof storedSelection === "string" ? storedSelection : ""),
    rovingKey: "",
    filtered: [],
    busy: false,
    error: "",
    destroyed: false,
  };
  let model = { species: [], enums: {}, sourceRevision: "", assetRevision: "", readOnly: true, summary: {}, capabilities: {}, writeDomains: [], fieldRegistry: [], validationRules: [] };
  let loadPromise = null;
  let loadGeneration = 0;
  let lastWorkspaceRevision = "";
  let lastWorkspaceAssetRevision = "";
  let pendingCommittedAssetRevision = "";
  let searchTimer = 0;
  let scrollFrame = 0;
  const resultAnnouncer = document.createElement("p");
  resultAnnouncer.className = "sr-only";
  resultAnnouncer.setAttribute("role", "status");
  resultAnnouncer.setAttribute("aria-live", "polite");
  resultAnnouncer.setAttribute("aria-atomic", "true");
  root.append(resultAnnouncer);
  const comboboxPopup = document.createElement("div");
  comboboxPopup.id = COMBOBOX_LIST_ID;
  comboboxPopup.className = "pv2-pokemon-combobox-popup";
  comboboxPopup.setAttribute("role", "listbox");
  comboboxPopup.setAttribute("aria-label", "Source enum suggestions");
  comboboxPopup.hidden = true;
  root.append(comboboxPopup);
  const comboboxState = {
    control: null,
    species: null,
    descriptor: null,
    structured: null,
    selectedLabel: "",
    options: [],
    filtered: [],
    activeIndex: -1,
    renderToken: 0,
  };
  const comboboxOptionCache = new WeakMap();
  libraryElement.removeAttribute("aria-live");
  libraryElement.setAttribute("role", "listbox");
  libraryElement.setAttribute("aria-label", "Pokémon index");
  libraryElement.tabIndex = -1;

  async function requestJson(path) {
    let result;
    if (typeof api === "function") result = await api(path, { method: "GET", cache: "no-store" });
    else if (typeof api.get === "function") result = await api.get(path, { cache: "no-store" });
    else if (typeof api.request === "function") result = await api.request(path, { method: "GET", cache: "no-store" });
    else if (typeof api.fetch === "function") result = await api.fetch(path, { method: "GET", cache: "no-store" });
    else throw new TypeError("Injected api cannot GET /api/v2/pokemon-data");
    if (result instanceof Response) {
      const body = await result.json();
      if (!result.ok) throw new Error(body?.error || `HTTP ${result.status}`);
      return body;
    }
    if (result?.ok === false) throw new Error(result.error || "Pokémon data request failed");
    return result;
  }

  function descriptorsFor(domain) {
    return model.fieldRegistry.filter((descriptor) => descriptor.domain === domain);
  }

  function recordFieldAccess(species, descriptor) {
    if (descriptor.writable === false) return { writable: false, reason: textValue(descriptor.readOnlyReason, descriptor.reason, "This field is reference-only.") };
    const recordGroups = asArray(firstDefined(species?.writableGroups, species?.writeDomains, model.writeDomains)).map((group) => textValue(group).toLowerCase());
    if (!recordGroups.includes(descriptor.domain)) {
      return { writable: false, reason: textValue(species?.writeReason, species?.readOnlyReason, `${humanize(descriptor.domain)} is not writable for this record.`) };
    }
    const accessRoots = [species?.fieldAccess, species?.writeAccess?.fields, species?.access?.fields, species?.editableAccess];
    const access = accessRoots.map((rootValue) => firstDefined(rootValue?.[descriptor.path], valueAtPath(rootValue, descriptor.path))).find((value) => value !== undefined);
    if (access === false) return { writable: false, reason: "This source field is not writable for this record." };
    if (typeof access === "string" && !["write", "writable", "read-write", "readwrite"].includes(access.toLowerCase())) {
      return { writable: false, reason: access };
    }
    if (isRecord(access) && (access.writable === false || access.allowed === false || ["read", "readonly", "read-only", "blocked"].includes(textValue(access.mode, access.access).toLowerCase()))) {
      return { writable: false, reason: textValue(access.reason, access.message, "This source field is not writable for this record.") };
    }
    return { writable: true, reason: "" };
  }

  function writableDescriptorsFor(species, domain) {
    return descriptorsFor(domain).filter((descriptor) => recordFieldAccess(species, descriptor).writable);
  }

  function domainWritable(domain, species = selectedSpecies()) {
    return Boolean(species) && model.writeDomains.includes(domain) && writableDescriptorsFor(species, domain).length > 0;
  }

  function structuredDomainWritable(domain, species = selectedSpecies()) {
    if (!species || !model.writeDomains.includes(domain)) return false;
    const recordGroups = asArray(firstDefined(species.writableGroups, species.writeDomains, model.writeDomains)).map((group) => textValue(group).toLowerCase());
    const groupAccess = firstDefined(species.groupAccess?.[domain], species.access?.groups?.[domain]);
    if (isRecord(groupAccess) && (groupAccess.writable === false || groupAccess.allowed === false)) return false;
    return recordGroups.includes(domain);
  }

  function learnsetWritable(species) {
    return model.writeDomains.includes("moves") && species?.learnsetAccess?.writable !== false && structuredDomainWritable("moves", species);
  }

  function learnsetRowsEditable(species) {
    const source = learnsetDetailFor(species);
    return learnsetWritable(species) && (source?.provenance !== "inherited" || learnsetDrafts.get(species.__symbol)?.materializeInherited === true);
  }

  function edgeWritable(species) {
    return model.writeDomains.includes("evolution") && species?.evolutionAccess?.writable === true;
  }

  function babyWritable(species) {
    return model.writeDomains.includes("evolution") && species?.babyAccess?.writable === true;
  }

  function sourceFieldValue(species, descriptor) {
    let value = valueAtPath(species.editable, descriptor.path);
    if (value === undefined) value = valueAtPath(species, descriptor.path);
    const parts = pathParts(descriptor.path);
    if (value === undefined && ["entry", "battle", "growth"].includes(parts[0])) {
      value = valueAtPath(species, parts.slice(1).join("."));
    }
    return fieldValueRaw(value);
  }

  function controlKind(descriptor, species = null) {
    const declared = textValue(descriptor.control, descriptor.inputType, descriptor.component, descriptor.kind, descriptor.type).toLowerCase();
    const path = descriptor.path.toLowerCase();
    if (["boolean", "bool", "checkbox", "toggle"].includes(declared) || /flip|is[A-Z]/.test(descriptor.path)) return "boolean";
    if (["combobox", "autocomplete"].includes(declared) || (/abilit|helditem|held_item/.test(path) && enumOptionsFor(descriptor).length > COMBOBOX_WINDOW_SIZE)) return "combobox";
    if (enumOptionsFor(descriptor).length) return "enum";
    if (["number", "integer", "int", "uint8", "u8", "range"].includes(declared) || /(?:^|-)number$/.test(declared)) return "number";
    if (["textarea", "multiline", "longtext"].includes(declared) || /dexentry|dex_entry|description|flavor/.test(path)) return "textarea";
    const source = species ? sourceFieldValue(species, descriptor) : null;
    return typeof source === "number" ? "number" : "text";
  }

  function enumKeyFor(descriptor) {
    const explicit = textValue(descriptor.enumKey, descriptor.enum, descriptor.enumSource, descriptor.optionsKey, descriptor.valuesFrom);
    if (explicit) return explicit.replace(/^enums\./, "");
    const path = descriptor.path.toLowerCase();
    if (path.includes("type")) return "types";
    if (path.includes("abilit")) return "abilities";
    if (path.includes("item")) return "items";
    if (path.includes("bodycolor") || path.includes("body_color")) return "bodyColors";
    return "";
  }

  function enumOptionsFor(descriptor) {
    const direct = asArray(descriptor.options || descriptor.values);
    if (direct.length) return direct;
    const key = enumKeyFor(descriptor);
    return key ? asArray(model.enums[key] || model.enums[key.toLowerCase()]) : [];
  }

  function normalizeControlValue(value, descriptor, species = null) {
    const kind = controlKind(descriptor, species);
    const raw = fieldValueRaw(value);
    if (kind === "boolean") return value === true || raw === true || ["1", "true", "yes"].includes(String(raw).toLowerCase());
    if (kind === "number") {
      if (raw === "" || raw === null || raw === undefined) return "";
      const numeric = Number(raw);
      return Number.isFinite(numeric) ? numeric : raw;
    }
    return textValue(raw);
  }

  function draftMapFor(species, create = false) {
    if (!species) return null;
    if (!drafts.has(species.__symbol) && create) drafts.set(species.__symbol, new Map());
    return drafts.get(species.__symbol) || null;
  }

  function fieldValue(species, descriptor) {
    const pending = draftMapFor(species);
    if (pending?.has(descriptor.path)) return pending.get(descriptor.path);
    return normalizeControlValue(sourceFieldValue(species, descriptor), descriptor, species);
  }

  function fieldChanged(species, descriptor) {
    return Boolean(draftMapFor(species)?.has(descriptor.path));
  }

  function setDraftField(species, descriptor, value) {
    const normalized = normalizeControlValue(value, descriptor, species);
    const original = normalizeControlValue(sourceFieldValue(species, descriptor), descriptor, species);
    const pending = draftMapFor(species, true);
    if (canonical(normalized) === canonical(original)) pending.delete(descriptor.path);
    else pending.set(descriptor.path, normalized);
    if (!pending.size) drafts.delete(species.__symbol);
  }

  function numberBounds(descriptor) {
    const path = descriptor.path.toLowerCase();
    let minimum = descriptor.min;
    let maximum = descriptor.max;
    if (minimum === undefined && path.includes("basestats")) minimum = 1;
    if (maximum === undefined && path.includes("basestats")) maximum = 255;
    if (minimum === undefined && /evyield|ev_yield/.test(path)) minimum = 0;
    if (maximum === undefined && /evyield|ev_yield/.test(path)) maximum = 3;
    return { minimum: minimum === undefined ? null : Number(minimum), maximum: maximum === undefined ? null : Number(maximum) };
  }

  function stringBounds(descriptor) {
    const minimum = firstDefined(descriptor.minLength, descriptor.minlength, descriptor.min);
    const maximum = firstDefined(descriptor.maxLength, descriptor.maxlength, descriptor.max);
    return {
      minimum: minimum === undefined ? null : Number(minimum),
      maximum: maximum === undefined ? null : Number(maximum),
    };
  }

  function validationRuleFor(descriptor, property) {
    return model.validationRules.find((rule) => rule.path === descriptor.path && rule[property] !== undefined);
  }

  function lineLimitFor(descriptor) {
    const rule = validationRuleFor(descriptor, "maximumLines");
    const value = firstDefined(descriptor.maximumLines, descriptor.maxLines, rule?.maximumLines);
    return value === undefined ? null : Number(value);
  }

  function fieldError(species, descriptor) {
    const value = fieldValue(species, descriptor);
    const kind = controlKind(descriptor, species);
    const empty = value === "" || value === null || value === undefined;
    if (descriptor.required && empty) return `${descriptor.label || humanize(descriptor.path)} is required.`;
    if (empty && descriptor.nullable === true) return "";
    if (empty && ["number", "enum", "combobox"].includes(kind)) return `${descriptor.label || humanize(descriptor.path)} requires a source value.`;
    if (empty && /(^|\.)name$/i.test(descriptor.path)) return "Name cannot be empty.";
    if (empty) return "";
    if (kind === "number") {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return `${descriptor.label || humanize(descriptor.path)} must be a number.`;
      if (descriptor.integer !== false && !Number.isInteger(numeric)) return `${descriptor.label || humanize(descriptor.path)} must be a whole number.`;
      const { minimum, maximum } = numberBounds(descriptor);
      if (Number.isFinite(minimum) && numeric < minimum) return `Minimum value is ${minimum}.`;
      if (Number.isFinite(maximum) && numeric > maximum) return `Maximum value is ${maximum}.`;
    }
    if (["text", "textarea"].includes(kind)) {
      const { minimum, maximum } = stringBounds(descriptor);
      if (Number.isFinite(minimum) && String(value).length < minimum) return `Minimum length is ${minimum} character${minimum === 1 ? "" : "s"}.`;
      if (Number.isFinite(maximum) && String(value).length > maximum) return `Maximum length is ${maximum} characters.`;
      const maximumLines = lineLimitFor(descriptor);
      const lines = String(value).split(/\r?\n/).length;
      if (Number.isFinite(maximumLines) && lines > maximumLines) {
        return textValue(validationRuleFor(descriptor, "maximumLines")?.message, `Maximum line count is ${maximumLines}.`);
      }
    }
    if (["enum", "combobox"].includes(kind)) {
      const allowed = new Set(enumOptionsFor(descriptor).flatMap((option) => [textValue(option?.symbol, option?.raw, option?.key), textValue(option?.value)]).filter(Boolean));
      if (allowed.size && !allowed.has(String(value))) return "Choose a value from the source enum.";
    }
    return "";
  }

  function speciesValidationErrors(species) {
    const errors = model.fieldRegistry
      .filter((descriptor) => fieldChanged(species, descriptor) && recordFieldAccess(species, descriptor).writable)
      .map((descriptor) => ({ path: descriptor.path, message: fieldError(species, descriptor) }))
      .filter((error) => error.message);
    return [...new Map(errors.map((error) => [`${error.path}:${error.message}`, error])).values()];
  }

  function speciesGroupValidationErrors(species) {
    const errors = [];
    const evDescriptors = descriptorsFor("battle").filter((descriptor) => /evyield|ev_yield/i.test(descriptor.path));
    if (evDescriptors.some((descriptor) => fieldChanged(species, descriptor))) {
      const componentErrors = evDescriptors.map((descriptor) => fieldError(species, descriptor)).filter(Boolean);
      const rule = model.validationRules.find((candidate) => candidate.id === "ev-yield-total" || candidate.pathPrefix?.startsWith("battle.evYields"));
      const maximumTotal = Number(firstDefined(rule?.maximumTotal, 3));
      const total = evDescriptors.reduce((sum, descriptor) => sum + (Number(fieldValue(species, descriptor)) || 0), 0);
      if (!componentErrors.length && total > maximumTotal) {
        errors.push({ path: "battle.evYields", group: "ev", message: textValue(rule?.message, `EV yield total cannot exceed ${maximumTotal}.`) });
      }
    }
    return errors;
  }

  function moveSymbol(value) {
    return textValue(value?.move?.symbol, value?.moveSymbol, value?.symbol, value?.raw, value);
  }

  function normalizeLearnset(detail = {}) {
    return {
      provenance: textValue(detail.provenance, "missing"),
      sourceSymbol: textValue(detail.sourceSymbol),
      levelMoves: asArray(detail.levelMoves).map((entry) => ({ level: normalizeMoveLevel(entry?.level ?? entry?.Level ?? 1), move: moveSymbol(entry) })),
      machineMoves: asArray(detail.machineMoves).map(moveSymbol).filter(Boolean),
      tutorMoves: asArray(detail.tutorMoves).map(moveSymbol).filter(Boolean),
      eggMoves: asArray(detail.eggMoves).map(moveSymbol).filter(Boolean),
    };
  }

  function normalizeMoveLevel(value) {
    const text = String(value ?? "").trim();
    if (!text) return "";
    const numeric = Number(text);
    return Number.isInteger(numeric) && numeric >= 0 && numeric <= 100 ? numeric : text;
  }

  function detailCacheKey(sourceRevision, assetRevision, symbol) {
    return `${sourceRevision}:${assetRevision}:${symbol}`;
  }

  function learnsetDetailFor(species) {
    return learnsetDetails.get(detailCacheKey(model.sourceRevision, model.assetRevision, species.__symbol))?.data || null;
  }

  function editorDetailFor(species) {
    const detail = learnsetDetails.get(detailCacheKey(model.sourceRevision, model.assetRevision, species.__symbol)) || null;
    const options = editorOptionsByRevision.get(model.sourceRevision);
    return detail ? { ...detail, moveOptions: options?.moveOptions || [], evolutionOptions: options?.evolutionOptions || {}, optionRevision: options?.optionRevision || detail.optionRevision } : null;
  }

  function formBaseRecord(species) {
    const baseSymbol = baseSymbolFor(species);
    return model.species.find((candidate) => candidate.__symbol === baseSymbol && !candidate.__isForm) || species;
  }

  function normalizeFormRow(row, fallbackRecord = null, index = 0) {
    const symbol = textValue(row?.symbol, row?.identity, fallbackRecord?.__symbol);
    const declaredFormIndex = Number(firstDefined(row?.declaredFormIndex, row?.formIndex, fallbackRecord?.formIndex, fallbackRecord?.form?.index, index + 1));
    return {
      symbol,
      identity: textValue(row?.identity, symbol),
      label: textValue(row?.label, row?.name, fallbackRecord?.__name, humanize(symbol)),
      declaredFormIndex,
      adjustedRecord: Boolean(firstDefined(row?.adjustedRecord, fallbackRecord?.adjustedRecord, true)),
      enabled: firstDefined(row?.enabled, fallbackRecord?.enabled, true) !== false,
      needsReversion: Boolean(firstDefined(row?.needsReversion, fallbackRecord?.needsReversion, false)),
      aliases: asArray(firstDefined(row?.aliases, fallbackRecord?.aliases, [])),
      flags: firstDefined(row?.flags, fallbackRecord?.formFlags, {}),
      source: firstDefined(row?.source, fallbackRecord?.formSource, {}),
      access: isRecord(row?.access) ? row.access : {},
    };
  }

  function formEditorFor(species) {
    const detail = editorDetailFor(species);
    const contract = detail?.formEditor;
    const base = formBaseRecord(species);
    if (contract) {
      return {
        ...contract,
        baseSymbol: textValue(contract.baseSymbol, base.__symbol),
        forms: asArray(contract.forms).map((row, index) => normalizeFormRow(row, model.species.find((candidate) => candidate.__symbol === row?.symbol), index)),
        rules: contract.rules || {},
        access: contract.access || {},
      };
    }
    const records = model.species.filter((candidate) => candidate.__isForm && baseSymbolFor(candidate) === base.__symbol);
    const rows = asArray(firstDefined(base.forms, base.variants, [])).map((row, index) => normalizeFormRow(row, records.find((candidate) => candidate.__symbol === row?.symbol), index));
    const seen = new Set(rows.map((row) => row.symbol));
    records.forEach((record, index) => { if (!seen.has(record.__symbol)) rows.push(normalizeFormRow({}, record, rows.length + index)); });
    return { baseSymbol: base.__symbol, forms: rows, rules: {}, access: { writable: false, reason: "The source did not expose a writable semantic form contract." } };
  }

  function formFieldWritable(editor, row, field) {
    return row.access?.[field]?.writable === true || editor.access?.fields?.[field]?.writable === true || editor.access?.writable === true && row.access?.[field]?.writable !== false;
  }

  function formComparable(editor) {
    return { baseSymbol: editor.baseSymbol, forms: editor.forms.map((row) => ({ symbol: row.symbol, declaredFormIndex: Number(row.declaredFormIndex), enabled: Boolean(row.enabled), needsReversion: Boolean(row.needsReversion) })) };
  }

  function formWritableComparable(editor) {
    return { baseSymbol: editor.baseSymbol, forms: editor.forms.map((row) => ({ symbol: row.symbol, needsReversion: Boolean(row.needsReversion) })) };
  }

  function formValueFor(species) {
    const editor = formEditorFor(species);
    return formDrafts.get(editor.baseSymbol) || editor;
  }

  function ensureFormDraft(species) {
    const source = formEditorFor(species);
    if (!formDrafts.has(source.baseSymbol)) formDrafts.set(source.baseSymbol, { ...source, forms: source.forms.map((row) => ({ ...row, access: { ...row.access } })), sourceSnapshot: formComparable(source) });
    return formDrafts.get(source.baseSymbol);
  }

  function reconcileFormDraft(species) {
    const source = formEditorFor(species);
    const draft = formDrafts.get(source.baseSymbol);
    if (draft && canonical(formWritableComparable(draft)) === canonical(formWritableComparable(draft.sourceSnapshot || source))) formDrafts.delete(source.baseSymbol);
  }

  function formAffectedSymbols(species) {
    const source = formEditorFor(species);
    const draft = formDrafts.get(source.baseSymbol);
    if (!draft) return [];
    const snapshot = draft.sourceSnapshot || formComparable(source);
    const before = new Map(snapshot.forms.map((row) => [row.symbol, Boolean(row.needsReversion)]));
    return draft.forms.filter((row) => before.get(row.symbol) !== Boolean(row.needsReversion)).map((row) => row.symbol);
  }

  function formValidationErrors() {
    return [...formDrafts.values()].flatMap((draft) => {
      const base = model.species.find((candidate) => candidate.__symbol === draft.baseSymbol) || model.species.find((candidate) => baseSymbolFor(candidate) === draft.baseSymbol);
      if (!base) return [];
      const errors = [];
      draft.forms.forEach((row, index) => {
        const prefix = `forms.rows.${index}`;
        if (typeof row.needsReversion !== "boolean") errors.push({ species: base, path: `${prefix}.needsReversion`, message: "Needs reversion must be a boolean." });
      });
      return errors;
    });
  }

  function assetEditorFor(species) {
    const detail = editorDetailFor(species);
    const contract = detail?.assetEditor;
    if (contract) return { ...contract, slots: contract.slots || {}, rules: contract.rules || {}, access: contract.access || {} };
    const source = isRecord(species.assets) ? species.assets : isRecord(species.sprites) ? species.sprites : {};
    const slots = {};
    ASSET_SLOTS.forEach(([slot, label]) => {
      const kebab = slot.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
      const raw = firstDefined(source[slot], source[kebab], slot === "maleFront" ? source.front : undefined, slot === "icon" ? species.__iconUrl : undefined);
      slots[slot] = { label, url: urlValue(raw), status: raw ? "available" : "missing", provenance: "resolved source", access: { writable: false, reason: "The source did not expose an upload contract for this asset." } };
    });
    return { slots, rules: {}, access: { writable: false, reason: "Asset uploads are unavailable for this record." } };
  }

  function assetSlotWritable(editor, slot) {
    return editor.slots?.[slot]?.access?.writable === true || editor.access?.slots?.[slot]?.writable === true || editor.access?.writable === true && editor.slots?.[slot]?.access?.writable !== false;
  }

  function assetRuleFor(editor, slot) {
    return { ...(editor.rules || {}), ...(editor.rules?.slots?.[slot] || {}), ...(editor.slots?.[slot]?.rules || {}) };
  }

  function assetProvenanceLabel(source) {
    return ({
      "source-png": "Direct source PNG",
      "empty-source-placeholder": "Writable fallback placeholder",
      "generated-manifest": "Generated manifest asset",
      "generated-fallback": "Generated counterpart fallback",
    })[source?.provenance] || humanize(source?.provenance || (source?.generated ? "generated asset" : "source managed"));
  }

  function assetSourceDiagnostic(editor, slot) {
    const source = editor.slots?.[slot] || {};
    const diagnostics = asArray(source.diagnostics).map(valueLabel).filter(Boolean).map((message) => String(message).replace(/\bSPECIES_[A-Z0-9_]+\b/g, (symbol) => humanize(symbol)).replace(/\b(?:maleFront|femaleFront|maleBack|femaleBack)\b/g, (value) => humanize(value)));
    const writable = assetSlotWritable(editor, slot);
    if (source.status === "invalid-source") return `Source PNG validation failed${diagnostics.length ? `: ${diagnostics.join("; ")}` : ". Replace it with a valid PNG before Save."}`;
    if (writable && (["empty-source-placeholder", "generated-fallback"].includes(source.provenance) || source.status === "generated-fallback")) return `This slot currently mirrors its counterpart through the engine fallback. Global Save creates an explicit source PNG for this slot.${diagnostics.length ? ` ${diagnostics.join("; ")}.` : ""}`;
    if (!writable && (source.generated || source.status === "unavailable")) return `No direct source PNG replacement is available for this generated asset${source.access?.reason ? `: ${humanize(source.access.reason)}` : "."}${diagnostics.length ? ` ${diagnostics.join("; ")}.` : ""}`;
    if (writable && source.status === "missing") return "A direct source slot exists but has no PNG yet. Global Save creates the explicit source PNG.";
    if (writable) return diagnostics.length ? `Source diagnostics: ${diagnostics.join("; ")}` : "This preview resolves from a direct, writable source PNG.";
    return textValue(source.access?.reason, diagnostics.join("; "), "This source asset is read-only.");
  }

  function assetDraftFor(species, slot) {
    return assetDrafts.get(species.__symbol)?.assets?.[slot] || null;
  }

  function assetDraftState(entry) {
    if (!entry) return null;
    const expired = Number(entry.expiresAt) && Date.now() >= Number(entry.expiresAt) * 1000;
    const stale = Boolean(entry.sourceRevision && entry.sourceRevision !== model.sourceRevision || entry.assetRevision && model.assetRevision && entry.assetRevision !== model.assetRevision);
    if (expired) return { status: "expired", invalid: true, message: "The staged asset expired. Choose the file again or revert this replacement." };
    if (stale) return { status: "stale", invalid: true, message: "The staged asset belongs to an older source or asset revision. Choose the file again." };
    if (entry.error || entry.status === "error") return { status: "error", invalid: true, busy: false, message: entry.error || "Asset validation failed. Choose the file again or revert." };
    if (entry.status === "validating") return { status: "validating", invalid: false, busy: true, message: "Validating file type, size, and dimensions…" };
    if (entry.status === "staging") return { status: "staging", invalid: false, busy: true, message: "Uploading to the revision-scoped staging area…" };
    if (entry.status === "ready" && entry.stagingToken) return { status: "ready", invalid: false, message: "Validated and staged for Global Save." };
    return { status: "incomplete", invalid: true, message: "Asset requires a valid staging token. Choose the file again or revert." };
  }

  function revokeAssetPreview(entry) {
    if (entry?.objectUrl) URL.revokeObjectURL(entry.objectUrl);
  }

  function discardAssetStage(entry) {
    const token = textValue(entry?.stagingToken);
    if (!token) return;
    entry.stagingToken = "";
    const headers = {};
    if (model.sourceRevision) headers["If-Match"] = model.sourceRevision;
    if (model.assetRevision) headers["X-Asset-Revision"] = model.assetRevision;
    fetch(`/api/v2/pokemon-assets/staged/${encodeURIComponent(token)}`, { method: "DELETE", headers }).catch(() => {});
  }

  function refreshAssetsEditor(species, fallbackSlot = "") {
    if (ui.destroyed || selectedSpecies()?.__symbol !== species.__symbol || activeDomain(species) !== "assets") return;
    const active = document.activeElement;
    const activeCard = active?.closest?.("[data-asset-card]");
    const slot = activeCard?.dataset.assetCard || fallbackSlot;
    const control = active?.matches?.("[data-asset-revert]") ? "revert" : active?.matches?.("[data-asset-file]") ? "file" : "drop";
    renderInspector();
    if (!slot) return;
    requestAnimationFrame(() => {
      const selector = control === "revert" ? `[data-asset-revert="${CSS.escape(slot)}"]` : control === "file" ? `[data-asset-file="${CSS.escape(slot)}"]` : `[data-asset-drop-slot="${CSS.escape(slot)}"]`;
      inspectorElement.querySelector(selector)?.focus({ preventScroll: true });
    });
  }

  function removeAssetDraft(species, slot, { discard = true } = {}) {
    const record = assetDrafts.get(species.__symbol);
    if (!record?.assets?.[slot]) return;
    if (discard) discardAssetStage(record.assets[slot]);
    revokeAssetPreview(record.assets[slot]);
    delete record.assets[slot];
    if (!Object.keys(record.assets).length) assetDrafts.delete(species.__symbol);
  }

  function assetValidationErrors() {
    return [...assetDrafts.entries()].flatMap(([symbol, draft]) => {
      const species = model.species.find((candidate) => candidate.__symbol === symbol);
      if (!species) return [];
      return Object.entries(draft.assets).flatMap(([slot, entry]) => {
        const state = assetDraftState(entry);
        return state?.invalid ? [{ species, path: `assets.${slot}`, message: state.message }] : [];
      });
    });
  }

  function assetBusyIssues() {
    return [...assetDrafts.entries()].flatMap(([symbol, draft]) => {
      const species = model.species.find((candidate) => candidate.__symbol === symbol);
      if (!species) return [];
      return Object.entries(draft.assets).flatMap(([slot, entry]) => {
        const state = assetDraftState(entry);
        return state?.busy ? [{ species, path: `assets.${slot}`, message: state.message, busy: true }] : [];
      });
    });
  }

  async function imageDimensions(file) {
    if (typeof createImageBitmap === "function") {
      const bitmap = await createImageBitmap(file);
      const dimensions = { width: bitmap.width, height: bitmap.height };
      bitmap.close();
      return dimensions;
    }
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const image = new Image();
      image.onload = () => { const result = { width: image.naturalWidth, height: image.naturalHeight }; URL.revokeObjectURL(url); resolve(result); };
      image.onerror = () => { URL.revokeObjectURL(url); reject(new Error("The selected file is not a readable image.")); };
      image.src = url;
    });
  }

  async function uploadAssetStage(species, slot, file) {
    const editor = assetEditorFor(species);
    const endpoint = textValue(editor.stagingEndpoint, "/api/v2/pokemon-assets/stage");
    const form = new FormData();
    form.append("symbol", species.__symbol);
    form.append("slot", slot);
    form.append("file", file, file.name);
    if (typeof api.upload === "function") return api.upload(endpoint, form);
    const headers = {};
    if (model.sourceRevision) headers["If-Match"] = model.sourceRevision;
    if (model.assetRevision) headers["X-Asset-Revision"] = model.assetRevision;
    const response = await fetch(endpoint, { method: "POST", body: form, headers });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload?.error || `Asset staging failed with HTTP ${response.status}.`);
    return payload;
  }

  async function stageAssetFile(species, slot, file) {
    const editor = assetEditorFor(species);
    if (!assetSlotWritable(editor, slot) || !(file instanceof File)) return;
    if (assetDraftState(assetDraftFor(species, slot))?.busy) {
      setStatus("Asset validation or staging is already in progress for this slot.", "busy");
      return;
    }
    removeAssetDraft(species, slot);
    const entry = { file, objectUrl: URL.createObjectURL(file), fileName: file.name, mimeType: file.type, bytes: file.size, status: "validating", stagingToken: "", error: "" };
    const record = assetDrafts.get(species.__symbol) || { symbol: species.__symbol, assets: {} };
    record.assets[slot] = entry;
    assetDrafts.set(species.__symbol, record);
    if (!ui.destroyed) {
      refreshAssetsEditor(species, slot);
      renderLibraryWindow();
      signalDirty();
    }
    try {
      const rule = assetRuleFor(editor, slot);
      const allowed = asArray(firstDefined(rule.allowedMimeTypes, ["image/png"]));
      const maximumBytes = Number(firstDefined(rule.maxBytes, 2 * 1024 * 1024));
      if (allowed.length && !allowed.includes(file.type)) throw new Error(`Use ${allowed.join(" or ")}.`);
      if (file.size > maximumBytes) throw new Error(`Asset must be ${Math.round(maximumBytes / 1024)} KB or smaller.`);
      const dimensions = await imageDimensions(file);
      entry.width = dimensions.width;
      entry.height = dimensions.height;
      const expectedWidth = Number(firstDefined(rule.width, rule.expectedWidth));
      const expectedHeight = Number(firstDefined(rule.height, rule.expectedHeight));
      if (Number.isFinite(expectedWidth) && dimensions.width !== expectedWidth || Number.isFinite(expectedHeight) && dimensions.height !== expectedHeight) throw new Error(`Expected ${expectedWidth || "any"}×${expectedHeight || "any"} px; received ${dimensions.width}×${dimensions.height} px.`);
      entry.status = "staging";
      refreshAssetsEditor(species, slot);
      const staged = await uploadAssetStage(species, slot, file);
      const returnedToken = textValue(staged?.stagingToken, staged?.token);
      if (assetDraftFor(species, slot) !== entry) {
        discardAssetStage({ stagingToken: returnedToken });
        return;
      }
      entry.stagingToken = returnedToken;
      entry.sourceRevision = textValue(staged?.sourceRevision);
      entry.assetRevision = textValue(staged?.assetRevision);
      if (!entry.stagingToken) throw new Error("Asset staging did not return an opaque staging token.");
      if (textValue(staged?.sourceRevision) !== model.sourceRevision || model.assetRevision && textValue(staged?.assetRevision) !== model.assetRevision) throw new Error("Asset staging returned a stale source or asset revision.");
      entry.previewUrl = textValue(staged?.previewUrl);
      entry.status = "ready";
      entry.error = "";
      entry.expiresAt = staged?.expiresAt;
      setStatus(`${ASSET_SLOTS.find(([key]) => key === slot)?.[1] || humanize(slot)} staged for Global Save.`, "info");
    } catch (error) {
      if (assetDraftFor(species, slot) !== entry) return;
      discardAssetStage(entry);
      entry.status = "error";
      entry.error = textValue(error?.message, error, "Asset validation failed.");
      setStatus(entry.error, "error");
    }
    if (!ui.destroyed) {
      refreshAssetsEditor(species, slot);
      renderLibraryWindow();
      signalDirty();
    }
  }

  function learnsetValueFor(species) {
    return learnsetDrafts.get(species.__symbol) || learnsetDetailFor(species);
  }

  function ensureLearnsetDraft(species, { materialize = false } = {}) {
    if (!learnsetDrafts.has(species.__symbol)) {
      const source = normalizeLearnset(learnsetDetailFor(species) || {});
      const sourceSnapshot = Object.freeze({
        levelMoves: Object.freeze(source.levelMoves.map((entry) => Object.freeze({ ...entry }))),
        machineMoves: Object.freeze([...source.machineMoves]),
        tutorMoves: Object.freeze([...source.tutorMoves]),
        eggMoves: Object.freeze([...source.eggMoves]),
      });
      learnsetDrafts.set(species.__symbol, {
        symbol: species.__symbol,
        levelMoves: source.levelMoves.map((entry) => ({ ...entry })),
        machineMoves: [...source.machineMoves],
        tutorMoves: [...source.tutorMoves],
        eggMoves: [...source.eggMoves],
        materializeInherited: materialize || source.provenance === "inherited",
        sourceSnapshot,
      });
    } else if (materialize) learnsetDrafts.get(species.__symbol).materializeInherited = true;
    return learnsetDrafts.get(species.__symbol);
  }

  async function ensureEditorOptions(revision, expectedOptionRevision = "", force = false, endpoint = "/api/v2/pokemon-editor-options") {
    const existing = editorOptionsByRevision.get(revision);
    if (!force && existing?.status === "ready" && (!expectedOptionRevision || existing.optionRevision === expectedOptionRevision)) return existing;
    if (!force && existing?.status === "loading") return existing.promise;
    const promise = requestJson(endpoint).then((payload) => {
      const sourceRevision = textValue(payload?.sourceRevision);
      const optionRevision = textValue(payload?.optionRevision);
      if (sourceRevision !== revision || model.sourceRevision !== revision) throw new Error("Pokémon editor options are stale for the current source revision.");
      if (expectedOptionRevision && optionRevision !== expectedOptionRevision) throw new Error("Pokémon detail and editor options revisions disagree.");
      const ready = { status: "ready", sourceRevision, optionRevision, assetRevision: payload?.assetRevision, moveOptions: asArray(payload?.moveOptions), evolutionOptions: payload?.evolutionOptions || {}, promise: null };
      editorOptionsByRevision.set(revision, ready);
      return ready;
    }).catch((error) => {
      editorOptionsByRevision.delete(revision);
      throw error;
    });
    editorOptionsByRevision.set(revision, { status: "loading", optionRevision: expectedOptionRevision, promise });
    return promise;
  }

  async function ensureLearnsetDetail(species, force = false) {
    const requestedRevision = model.sourceRevision;
    const requestedAssetRevision = model.assetRevision;
    const detailKey = detailCacheKey(requestedRevision, requestedAssetRevision, species.__symbol);
    const existing = learnsetDetails.get(detailKey);
    if (existing?.status === "loading" && !force) return existing.promise;
    if (existing?.status === "ready" && !force) return existing.data;
    const record = { status: "loading", data: existing?.data || null, error: "", promise: null };
    const promise = requestJson(`/api/v2/pokemon-data/${encodeURIComponent(species.__symbol)}`)
      .then(async (payload) => {
        const responseRevision = textValue(payload?.sourceRevision, requestedRevision);
        const responseAssetRevision = textValue(payload?.assetRevision, requestedAssetRevision);
        if (model.sourceRevision !== requestedRevision || responseRevision !== requestedRevision || model.assetRevision !== requestedAssetRevision || responseAssetRevision !== requestedAssetRevision) {
          learnsetDetails.delete(detailKey);
          if (model.sourceRevision !== requestedRevision || model.assetRevision !== requestedAssetRevision) return ensureLearnsetDetail(species, true);
          throw new Error("Pokémon detail source or asset revision changed; reload the editor detail.");
        }
        const detail = normalizeLearnset(firstDefined(payload?.learnset, payload?.pokemon?.learnset, payload?.data?.learnset, {}));
        if (payload?.moveOptions || payload?.evolutionOptions) {
          editorOptionsByRevision.set(responseRevision, { status: "ready", sourceRevision: responseRevision, optionRevision: textValue(payload?.optionRevision), moveOptions: asArray(payload?.moveOptions), evolutionOptions: payload?.evolutionOptions || {} });
        } else await ensureEditorOptions(responseRevision, textValue(payload?.optionRevision), force, textValue(payload?.editorOptionsEndpoint, "/api/v2/pokemon-editor-options"));
        learnsetDetails.set(detailKey, { status: "ready", revision: responseRevision, assetRevision: textValue(payload?.assetRevision, model.assetRevision), optionRevision: textValue(payload?.optionRevision), data: detail, formEditor: firstDefined(payload?.formEditor, payload?.pokemon?.formEditor, payload?.data?.formEditor), assetEditor: firstDefined(payload?.assetEditor, payload?.pokemon?.assetEditor, payload?.data?.assetEditor), error: "", promise: null });
        if (!ui.destroyed && selectedSpecies()?.__symbol === species.__symbol) renderInspector();
        return detail;
      })
      .catch((error) => {
        learnsetDetails.set(detailKey, { status: "error", revision: requestedRevision, assetRevision: requestedAssetRevision, data: null, error: textValue(error?.message, error, "Learnset detail unavailable"), promise: null });
        if (!ui.destroyed && selectedSpecies()?.__symbol === species.__symbol) renderInspector();
        return null;
      });
    record.promise = promise;
    learnsetDetails.set(detailKey, record);
    return promise;
  }

  function normalizeEvolutionEdge(edge = {}) {
    const targetFormIndex = firstDefined(edge.targetFormIndex, edge.logicalTarget?.formIndex);
    return {
      method: textValue(edge.method?.symbol, edge.methodSymbol, edge.method),
      parameter: textValue(edge.parameter?.raw, edge.parameter?.symbol, edge.parameter, edge.parameterValue, "0"),
      targetSymbol: targetFormIndex !== undefined ? textValue(edge.targetBaseSymbol, edge.logicalTarget?.baseSymbol, edge.targetSymbol) : textValue(edge.targetSymbol, edge.logicalTarget?.alias, edge.targetBaseSymbol),
      ...(targetFormIndex !== undefined ? { targetFormIndex } : {}),
    };
  }

  function sourceBabySymbol(species) {
    return textValue(species.babySymbol, species.evolution?.babySymbol, species.evolutionFamily?.babySymbol, species.evolutionFamily?.rootSymbols?.[0], species.__symbol);
  }

  function evolutionValueFor(species) {
    return evolutionDrafts.get(species.__symbol) || {
      symbol: species.__symbol,
      edges: asArray(firstDefined(species.evolutions, species.evolution?.edges, [])).map(normalizeEvolutionEdge),
      babySymbol: sourceBabySymbol(species),
    };
  }

  function ensureEvolutionDraft(species) {
    if (!evolutionDrafts.has(species.__symbol)) {
      const source = evolutionValueFor(species);
      evolutionDrafts.set(species.__symbol, { symbol: species.__symbol, edges: source.edges.map((edge) => ({ ...edge })), babySymbol: source.babySymbol, edgesTouched: false, babyTouched: false });
    }
    return evolutionDrafts.get(species.__symbol);
  }

  function baseSymbolFor(species) {
    return textValue(species?.baseSymbol, species?.form?.baseSymbol, species?.formMetadata?.baseSymbol, species?.__symbol);
  }

  function projectedEdgesFor(species) {
    const draft = evolutionDrafts.get(species.__symbol);
    return draft?.edgesTouched ? draft.edges : asArray(firstDefined(species.evolutions, species.evolution?.edges, [])).map(normalizeEvolutionEdge);
  }

  function projectedFamilyGraph() {
    if (projectedFamilyGraphCache) return projectedFamilyGraphCache;
    const baseSymbols = [...new Set(model.species.map(baseSymbolFor).filter(Boolean))];
    const adjacency = new Map(baseSymbols.map((symbol) => [symbol, new Set()]));
    const incoming = new Map(baseSymbols.map((symbol) => [symbol, 0]));
    model.species.forEach((species) => projectedEdgesFor(species).forEach((edge) => {
      const source = baseSymbolFor(species);
      const targetRecord = model.species.find((candidate) => candidate.__symbol === edge.targetSymbol);
      const target = targetRecord ? baseSymbolFor(targetRecord) : edge.targetSymbol;
      if (!source || !target || !adjacency.has(source) || !adjacency.has(target)) return;
      adjacency.get(source).add(target);
      adjacency.get(target).add(source);
      incoming.set(target, 1);
    }));
    projectedFamilyGraphCache = { adjacency, incoming };
    return projectedFamilyGraphCache;
  }

  function projectedFamilyFor(species) {
    const start = baseSymbolFor(species);
    const { adjacency, incoming } = projectedFamilyGraph();
    const members = new Set();
    const stack = [start];
    while (stack.length) {
      const symbol = stack.pop();
      if (!symbol || members.has(symbol)) continue;
      members.add(symbol);
      adjacency.get(symbol)?.forEach((neighbor) => stack.push(neighbor));
    }
    const roots = [...members].filter((symbol) => (incoming.get(symbol) || 0) === 0);
    return { members: [...members], roots };
  }

  function stageFamilyBabyMappings(species, requestedRoot = "", { append = false } = {}) {
    const summaryKey = species.__symbol;
    const previous = familyStageSummaries.get(summaryKey);
    if (!append) previous?.affected.forEach((symbol) => {
      const draft = evolutionDrafts.get(symbol);
      const record = model.species.find((candidate) => candidate.__symbol === symbol);
      if (!draft || !record) return;
      draft.babySymbol = sourceBabySymbol(record);
      draft.babyTouched = false;
      if (!draft.edgesTouched) evolutionDrafts.delete(symbol);
    });
    const currentFamily = projectedFamilyFor(species);
    const seeds = requestedRoot ? currentFamily.members : [...new Set([...currentFamily.members, ...asArray(species.evolutionFamily?.baseSymbols)])];
    const families = [];
    const covered = new Set();
    seeds.forEach((symbol) => {
      if (covered.has(symbol)) return;
      const record = model.species.find((candidate) => candidate.__symbol === symbol && !candidate.__isForm);
      if (!record) return;
      const family = projectedFamilyFor(record);
      family.members.forEach((member) => covered.add(member));
      families.push(family);
    });
    const affected = [];
    const blocked = [];
    families.forEach((family) => {
      const rootSymbol = requestedRoot || (family.roots.length === 1 ? family.roots[0] : "");
      if (!rootSymbol) return;
      model.species.filter((candidate) => !candidate.__isForm && family.members.includes(baseSymbolFor(candidate))).forEach((candidate) => {
        if (!babyWritable(candidate)) {
          if (sourceBabySymbol(candidate) !== rootSymbol) blocked.push({ symbol: candidate.__symbol, reason: candidate.babyAccess?.reason || "baby mapping is read-only" });
          return;
        }
        if (sourceBabySymbol(candidate) === rootSymbol && !evolutionDrafts.get(candidate.__symbol)?.babyTouched) return;
        const draft = ensureEvolutionDraft(candidate);
        draft.babySymbol = rootSymbol;
        draft.babyTouched = draft.babySymbol !== sourceBabySymbol(candidate);
        if (draft.babyTouched) affected.push(candidate.__symbol);
        if (!draft.edgesTouched && !draft.babyTouched) evolutionDrafts.delete(candidate.__symbol);
      });
    });
    const roots = families.flatMap((family) => family.roots);
    const members = [...new Set(families.flatMap((family) => family.members))];
    const combinedFamilies = append && previous ? [...previous.families, ...families] : families;
    const distinctFamilies = [...new Map(combinedFamilies.map((family) => [canonical([...family.members].sort()), family])).values()];
    const combinedMembers = append && previous ? [...previous.members, ...members] : members;
    const combinedRoots = append && previous ? [...previous.roots, ...roots] : roots;
    const combinedAffected = append && previous ? [...previous.affected, ...affected] : affected;
    const combinedBlocked = append && previous ? [...previous.blocked, ...blocked] : blocked;
    familyStageSummaries.set(summaryKey, { initiatorSymbol: species.__symbol, members: [...new Set(combinedMembers)], roots: [...new Set(combinedRoots)], families: distinctFamilies, invalidRootCounts: distinctFamilies.filter((family) => family.roots.length !== 1).map((family) => family.roots.length), rootSymbol: requestedRoot || previous?.rootSymbol || (combinedRoots.length === 1 ? combinedRoots[0] : ""), affected: [...new Set(combinedAffected)], blocked: [...new Map(combinedBlocked.map((entry) => [`${entry.symbol}:${entry.reason}`, entry])).values()] });
    return familyStageSummaries.get(summaryKey);
  }

  function clearAutoStagedBabyMappings() {
    const staged = new Set([...familyStageSummaries.values()].flatMap((summary) => summary.affected));
    staged.forEach((symbol) => {
      const draft = evolutionDrafts.get(symbol);
      const record = model.species.find((candidate) => candidate.__symbol === symbol);
      if (!draft || !record) return;
      draft.babySymbol = sourceBabySymbol(record);
      draft.babyTouched = false;
      if (!draft.edgesTouched) evolutionDrafts.delete(symbol);
    });
    familyStageSummaries.clear();
  }

  function recomputeFamilyStaging(initiator = null, requestedRoot = "") {
    clearAutoStagedBabyMappings();
    const topologyRecords = [...evolutionDrafts.entries()].filter(([, draft]) => draft.edgesTouched).map(([symbol]) => model.species.find((species) => species.__symbol === symbol)).filter(Boolean);
    const coveredBases = new Set();
    topologyRecords.forEach((record) => {
      if (coveredBases.has(baseSymbolFor(record))) return;
      const summary = stageFamilyBabyMappings(record);
      summary.members.forEach((member) => coveredBases.add(member));
    });
    if (requestedRoot && initiator) stageFamilyBabyMappings(initiator, requestedRoot, { append: familyStageSummaries.has(initiator.__symbol) });
  }

  function topologyTargetSignature(edges) {
    return canonical([...new Set(asArray(edges).map((edge) => {
      const targetRecord = model.species.find((candidate) => candidate.__symbol === edge.targetSymbol);
      return targetRecord ? baseSymbolFor(targetRecord) : edge.targetSymbol;
    }).filter(Boolean))].sort());
  }

  function evolutionMaxSlots(species = selectedSpecies()) {
    const rule = model.validationRules.find((candidate) => candidate.id === "evolution-max-slots" || candidate.group === "evolution" && candidate.maximumSlots !== undefined);
    return Number(firstDefined(species?.evolutionAccess?.capacity, editorDetailFor(species)?.evolutionOptions?.maxEvolutionEdges, species?.groupAccess?.evolution?.capacity, rule?.maximumSlots, model.capabilities?.evolution?.maximumSlots, model.capabilities?.evolutionMaxSlots, 9));
  }

  function learnsetValidationErrors() {
    const bySymbol = new Map(model.species.map((species) => [species.__symbol, species]));
    return [...learnsetDrafts.entries()].flatMap(([symbol, draft]) => {
      const species = bySymbol.get(symbol);
      if (!species) return [];
      const errors = [];
      MOVE_GROUPS.forEach(([key]) => {
        const sourceRows = asArray(draft.sourceSnapshot?.[key] ?? learnsetDetailFor(species)?.[key]);
        const sourceCounts = new Map();
        const draftCounts = new Map();
        const firstRows = new Map();
        const identityFor = (entry) => {
          const move = key === "levelMoves" ? entry?.move : entry;
          return key === "levelMoves" ? `${normalizeMoveLevel(entry?.level)}:${move}` : String(move);
        };
        sourceRows.forEach((entry) => {
          const identity = identityFor(entry);
          sourceCounts.set(identity, (sourceCounts.get(identity) || 0) + 1);
        });
        draft[key].forEach((entry, index) => {
          const move = key === "levelMoves" ? entry.move : entry;
          const path = `moves.${key}.${index}`;
          if (!/^MOVE_[A-Z0-9_]+$/.test(String(move))) errors.push({ species, path: `${path}.move`, message: "Choose a valid move from the source options." });
          const levelText = String(entry.level ?? "").trim();
          if (key === "levelMoves" && !levelText) errors.push({ species, path: `${path}.level`, message: "Level is required." });
          else if (key === "levelMoves" && (!Number.isInteger(Number(levelText)) || Number(levelText) < 0 || Number(levelText) > 100)) errors.push({ species, path: `${path}.level`, message: "Level must be a whole number from 0 to 100." });
          if (key === "levelMoves" && levelText && index > 0 && String(draft.levelMoves[index - 1].level ?? "").trim() && Number(levelText) < Number(draft.levelMoves[index - 1].level)) errors.push({ species, path: `${path}.level`, message: "Levels must be nondecreasing; equal-level row order is preserved." });
          const identity = identityFor(entry);
          const occurrence = (draftCounts.get(identity) || 0) + 1;
          draftCounts.set(identity, occurrence);
          if (!firstRows.has(identity)) firstRows.set(identity, index);
          const allowedOccurrences = Math.max(1, sourceCounts.get(identity) || 0);
          if (occurrence > allowedOccurrences) errors.push({ species, path: `${path}.move`, message: `Duplicate of row ${firstRows.get(identity) + 1}.` });
        });
      });
      return [...new Map(errors.map((error) => [`${error.path}:${error.message}`, error])).values()];
    });
  }

  function evolutionValidationErrors() {
    const bySymbol = new Map(model.species.map((species) => [species.__symbol, species]));
    const errors = [...evolutionDrafts.entries()].flatMap(([symbol, draft]) => {
      const species = bySymbol.get(symbol);
      if (!species) return [];
      const maximum = evolutionMaxSlots(species);
      const errors = [];
      if (draft.edgesTouched && draft.edges.length > maximum) errors.push({ species, path: "evolution.edges", message: `Evolution data supports at most ${maximum} outgoing edges.` });
      if (draft.babyTouched && !/^SPECIES_[A-Z0-9_]+$/.test(draft.babySymbol)) errors.push({ species, path: "evolution.babySymbol", message: "Baby species must use a SPECIES_* symbol." });
      const seenEdges = new Map();
      if (draft.edgesTouched) draft.edges.forEach((edge, index) => {
        const method = evolutionMethodOptions().find((option) => enumOptionValue(option) === edge.method);
        if (!method) errors.push({ species, path: `evolution.edges.${index}.method`, message: `Evolution ${index + 1} requires a supported method.` });
        const schema = method?.parameter || {};
        const parameterKind = evolutionParameterKind(edge.method);
        const parameterText = String(edge.parameter ?? "").trim();
        if (!parameterText) errors.push({ species, path: `evolution.edges.${index}.parameter`, message: `Evolution ${index + 1} requires a method parameter.` });
        else if (["fixed", "zero"].includes(parameterKind) && Number(parameterText) !== 0) {
          errors.push({ species, path: `evolution.edges.${index}.parameter`, message: "This evolution method requires a fixed parameter of 0." });
        }
        else if (["integer", "level", "number", "numeric"].includes(parameterKind)) {
          const numeric = Number(parameterText);
          const minimum = schema.min === undefined || schema.min === null || schema.min === "" ? Number.NaN : Number(schema.min);
          const maximum = schema.max === undefined || schema.max === null || schema.max === "" ? Number.NaN : Number(schema.max);
          const wholeRequired = !["number", "numeric"].includes(parameterKind) || schema.integer !== false;
          if (!Number.isFinite(numeric) || wholeRequired && !Number.isInteger(numeric) || Number.isFinite(minimum) && numeric < minimum || Number.isFinite(maximum) && numeric > maximum) {
            const range = Number.isFinite(minimum) && Number.isFinite(maximum) ? ` from ${minimum} to ${maximum}` : "";
            errors.push({ species, path: `evolution.edges.${index}.parameter`, message: `Parameter must be ${wholeRequired ? "a whole number" : "a number"}${range}.` });
          }
        }
        else if (asArray(schema.optionSymbols).length && !asArray(schema.optionSymbols).includes(parameterText)) {
          errors.push({ species, path: `evolution.edges.${index}.parameter`, message: `Choose a parameter supported by ${optionLabel(method)}.` });
        }
        if (!model.species.some((candidate) => candidate.__symbol === edge.targetSymbol) && !editorDetailFor(species)?.evolutionOptions?.species?.some((candidate) => candidate.symbol === edge.targetSymbol)) errors.push({ species, path: `evolution.edges.${index}.targetSymbol`, message: `Evolution ${index + 1} requires a known species target.` });
        const identity = canonical([edge.method, edge.parameter, edge.targetSymbol, edge.targetFormIndex ?? null]);
        if (seenEdges.has(identity)) errors.push({ species, path: `evolution.edges.${index}.targetSymbol`, message: `Duplicate of evolution ${seenEdges.get(identity) + 1}.` });
        else seenEdges.set(identity, index);
      });
      return errors;
    });
    familyStageSummaries.forEach((summary) => {
      const species = bySymbol.get(summary.initiatorSymbol) || bySymbol.get(summary.members[0]);
      if (!species) return;
      if (summary.invalidRootCounts?.length) errors.push({ species, path: "evolution.family", message: "Every projected family component must have exactly one root." });
      if (summary.blocked.length) errors.push({ species, path: "evolution.family", message: `${summary.blocked.length} required baby mapping update${summary.blocked.length === 1 ? " is" : "s are"} not writable.` });
      let inconsistentMappings = 0;
      asArray(summary.families).filter((family) => family.roots.length === 1).forEach((family) => family.members.forEach((baseSymbol) => {
        const rootSymbol = family.roots[0];
        model.species.filter((candidate) => !candidate.__isForm && baseSymbolFor(candidate) === baseSymbol).forEach((candidate) => {
          const projectedBaby = evolutionDrafts.get(candidate.__symbol)?.babyTouched ? evolutionDrafts.get(candidate.__symbol).babySymbol : sourceBabySymbol(candidate);
          if (projectedBaby !== rootSymbol) inconsistentMappings += 1;
        });
      }));
      if (inconsistentMappings) errors.push({ species, path: "evolution.family", message: `${inconsistentMappings} projected baby mapping${inconsistentMappings === 1 ? " is" : "s are"} inconsistent with the family root.` });
    });
    return errors;
  }

  function validationErrors() {
    const bySymbol = new Map(model.species.map((species) => [species.__symbol, species]));
    const fieldErrors = [...drafts.keys()].flatMap((symbol) => {
      const species = bySymbol.get(symbol);
      return species ? speciesValidationErrors(species).concat(speciesGroupValidationErrors(species)).map((error) => ({ ...error, species })) : [];
    });
    return fieldErrors.concat(learnsetValidationErrors(), evolutionValidationErrors(), formValidationErrors(), assetValidationErrors());
  }

  function signalDirty() {
    state.pokemonDirty = drafts.size > 0 || learnsetDrafts.size > 0 || evolutionDrafts.size > 0 || formDrafts.size > 0 || assetDrafts.size > 0;
    markDirty();
  }

  function selectedSpecies() {
    return model.species.find((species) => species.__key === ui.selectedKey) || null;
  }

  function descriptorMatching(domain, pattern) {
    return descriptorsFor(domain).find((descriptor) => pattern.test(descriptor.path));
  }

  function effectiveName(species) {
    const descriptor = descriptorMatching("entry", /(^|\.)name$/i);
    const pending = descriptor ? draftMapFor(species) : null;
    if (descriptor && pending?.has(descriptor.path)) {
      const draftName = String(pending.get(descriptor.path) ?? "").trim();
      return draftName || "Unnamed Pokémon";
    }
    if (!descriptor || !species.__isForm) return species.__name;
    const baseSymbol = textValue(species.baseSymbol, species.form?.baseSymbol, species.formMetadata?.baseSymbol, species.__baseSymbol);
    const base = model.species.find((candidate) => candidate.__symbol === baseSymbol && !candidate.__isForm);
    const baseDrafts = base ? draftMapFor(base) : null;
    if (!base || !baseDrafts?.has(descriptor.path)) return species.__name;
    const draftedBaseName = String(baseDrafts.get(descriptor.path) ?? "").trim() || "Unnamed Pokémon";
    const savedBaseName = base.__name;
    const publicFormName = species.__name;
    if (savedBaseName && publicFormName.toLowerCase().startsWith(savedBaseName.toLowerCase())) {
      const suffix = publicFormName.slice(savedBaseName.length);
      if (suffix.trim()) return `${draftedBaseName}${suffix}`;
    }
    return species.__formName ? `${draftedBaseName} · ${species.__formName}` : draftedBaseName;
  }

  function displayIncludesFormLabel(displayName, formName) {
    const simplifiedForm = compact(String(formName || "").replace(/\bforms?e?\b/gi, ""));
    return Boolean(simplifiedForm && compact(displayName).includes(simplifiedForm));
  }

  function enumLabelFor(descriptor, rawValue) {
    const raw = String(rawValue ?? "");
    const option = enumOptionsFor(descriptor).find((candidate) => enumOptionValue(candidate) === raw);
    return option ? optionLabel(option) : humanize(raw);
  }

  function effectiveTypes(species) {
    const descriptors = descriptorsFor("battle").filter((descriptor) => /battle\.types\./i.test(descriptor.path));
    const pending = draftMapFor(species);
    if (!descriptors.length || !descriptors.some((descriptor) => pending?.has(descriptor.path))) return species.__types;
    const values = descriptors.map((descriptor) => fieldValue(species, descriptor)).filter((value) => value !== "" && value !== null && value !== undefined);
    return values.map((raw) => ({ key: optionKey(raw), label: enumLabelFor(descriptors[0], raw), raw })).filter((type, index, all) => type.key && all.findIndex((candidate) => candidate.key === type.key) === index);
  }

  function speciesInvalid(species) {
    if (!species) return false;
    const fieldInvalid = Boolean(draftMapFor(species)?.size && (speciesValidationErrors(species).length || speciesGroupValidationErrors(species).length));
    const formBase = baseSymbolFor(species);
    return fieldInvalid || learnsetValidationErrors().some((error) => error.species.__symbol === species.__symbol) || evolutionValidationErrors().some((error) => error.species.__symbol === species.__symbol) || formValidationErrors().some((error) => baseSymbolFor(error.species) === formBase) || assetValidationErrors().some((error) => error.species.__symbol === species.__symbol);
  }

  function effectiveSearch(species) {
    const projectedName = effectiveName(species);
    const projectedTypes = effectiveTypes(species);
    if (!draftMapFor(species)?.size && projectedName === species.__name && projectedTypes === species.__types) return species.__search;
    const numeric = Number(species.__dexNumber);
    const dexTokens = Number.isFinite(numeric)
      ? [String(numeric), String(numeric).padStart(3, "0"), String(numeric).padStart(4, "0")].flatMap((token) => [token, `#${token}`])
      : [species.__dexNumber].filter(Boolean).flatMap((token) => [String(token), `#${token}`]);
    const aliases = asArray(firstDefined(species.aliases, species.searchAliases, [])).map(valueLabel);
    return [projectedName, species.__symbol, species.__formName, ...dexTokens, ...aliases, ...projectedTypes.flatMap((type) => [type.key, type.label])]
      .filter(Boolean).join(" ").toLowerCase();
  }

  function domainState(species, domain) {
    if (domain === "moves") {
      return { changed: learnsetDrafts.has(species.__symbol) ? 1 : 0, errors: learnsetValidationErrors().filter((error) => error.species.__symbol === species.__symbol).length };
    }
    if (domain === "evolution") {
      return { changed: evolutionDrafts.has(species.__symbol) ? 1 : 0, errors: evolutionValidationErrors().filter((error) => error.species.__symbol === species.__symbol).length };
    }
    if (domain === "forms") {
      const baseSymbol = baseSymbolFor(species);
      return { changed: formDrafts.has(baseSymbol) ? formAffectedSymbols(species).length : 0, errors: formValidationErrors().filter((error) => baseSymbolFor(error.species) === baseSymbol).length };
    }
    if (domain === "assets") {
      return { changed: Object.keys(assetDrafts.get(species.__symbol)?.assets || {}).length, errors: assetValidationErrors().filter((error) => error.species.__symbol === species.__symbol).length };
    }
    const descriptors = descriptorsFor(domain);
    const changed = descriptors.filter((descriptor) => fieldChanged(species, descriptor)).length;
    const fieldErrors = speciesValidationErrors(species).filter((error) => error.path.startsWith(`${domain}.`));
    const groupErrors = speciesGroupValidationErrors(species).filter((error) => error.path.startsWith(`${domain}.`));
    return { changed, errors: fieldErrors.length + groupErrors.length };
  }

  function activeDomain(species) {
    const stored = sectionBySpecies.get(species.__key);
    return DOMAIN_TABS.some(([key]) => key === stored) ? stored : "entry";
  }

  function filterOptions() {
    const enumTypes = asArray(firstDefined(model.enums.types, model.enums.typeOptions, []));
    const discoveredTypes = model.species.flatMap((species) => species.__types);
    const types = new Map([...enumTypes, ...discoveredTypes].map((type) => [optionKey(type), optionLabel(type)]).filter(([key]) => key));
    return { types: [...types].sort((a, b) => a[1].localeCompare(b[1])) };
  }

  function renderFilterControls() {
    const options = filterOptions();
    if (!["all", ...options.types.map(([key]) => key)].includes(ui.type)) ui.type = "all";
    if (!["all", "base", "forms"].includes(ui.scope)) ui.scope = "all";
    searchElement.value = ui.pendingSearch;
    typeFilterElement.innerHTML = `<option value="all">All types</option>${options.types.map(([key, label]) => `<option value="${escapeHtml(key)}" ${key === ui.type ? "selected" : ""}>${escapeHtml(label)}</option>`).join("")}`;
    stateFilterElement.innerHTML = `<option value="all" ${ui.scope === "all" ? "selected" : ""}>All records</option><option value="base" ${ui.scope === "base" ? "selected" : ""}>Base species</option><option value="forms" ${ui.scope === "forms" ? "selected" : ""}>Forms</option>`;
    stateFilterElement.hidden = false;
    stateFilterElement.closest("label")?.removeAttribute("hidden");
  }

  function visibleSpecies() {
    const needle = ui.search.trim().toLowerCase();
    const compactNeedle = compact(needle);
    return model.species.filter((species) => {
      if (species.__isReserved && !needle) return false;
      const search = effectiveSearch(species);
      const compactSearch = search === species.__search ? species.__searchCompact : compact(search);
      if (needle && !search.includes(needle) && !(compactNeedle && compactSearch.includes(compactNeedle))) return false;
      if (ui.type !== "all" && !effectiveTypes(species).some((type) => type.key === ui.type)) return false;
      if (ui.scope === "base" && species.__isForm) return false;
      if (ui.scope === "forms" && !species.__isForm) return false;
      return true;
    });
  }

  function dexLabel(species) {
    const numeric = Number(species.__dexNumber);
    if (Number.isFinite(numeric)) return `#${String(numeric).padStart(3, "0")}`;
    return species.__dexNumber ? `#${species.__dexNumber}` : "#—";
  }

  function renderSprite(species, size = "small") {
    const url = size === "large" ? species.__frontSpriteUrl : species.__iconUrl;
    if (!url) return `<span class="pv2-pokemon-sprite pv2-pokemon-sprite--${size} is-empty" aria-hidden="true">◇</span>`;
    const alt = size === "large" ? `${species.__name} front sprite` : "";
    return `<span class="pv2-pokemon-sprite pv2-pokemon-sprite--${size}"><img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" loading="lazy" decoding="async" draggable="false"></span>`;
  }

  function announceResults() {
    resultAnnouncer.textContent = `${ui.filtered.length} Pokémon in the filtered index.`;
  }

  function renderLibraryRow(species) {
    const selected = species.__key === ui.selectedKey;
    const changed = Boolean(draftMapFor(species)?.size || learnsetDrafts.has(species.__symbol) || evolutionDrafts.has(species.__symbol) || formDrafts.has(baseSymbolFor(species)) || assetDrafts.has(species.__symbol));
    const invalid = speciesInvalid(species);
    const name = effectiveName(species);
    const types = effectiveTypes(species);
    const displayAlreadyNamesForm = /\([^()]+\)/.test(name) || /\([^()]+\)/.test(species.__name);
    const candidateFormCopy = species.__formName || (species.__isForm && !displayAlreadyNamesForm ? humanize(species.__symbol.replace(`${species.baseSymbol || ""}_`, "")) : "");
    const formCopy = displayIncludesFormLabel(name, candidateFormCopy) ? "" : candidateFormCopy;
    const optionId = `pv2-pokemon-option-${species.__key.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
    return `<li><button id="${escapeHtml(optionId)}" role="option" aria-selected="${selected}" class="pv2-pokemon-row${selected ? " is-selected" : ""}${changed ? " is-changed" : ""}${invalid ? " is-invalid" : ""}" type="button" tabindex="${species.__key === ui.rovingKey ? "0" : "-1"}" data-pokemon-select="${escapeHtml(species.__key)}" aria-current="${selected ? "true" : "false"}">
      <span class="pv2-pokemon-row-number">${escapeHtml(dexLabel(species))}</span>
      ${renderSprite(species)}
      <span class="pv2-pokemon-row-copy"><strong>${escapeHtml(name)}</strong>${formCopy ? `<small>${escapeHtml(formCopy)}</small>` : ""}</span>
      <span class="pv2-pokemon-row-types">${invalid ? `<b class="pv2-pokemon-row-error" title="Draft has validation errors" aria-label="Draft has validation errors">!</b>` : ""}${renderTypePills(types)}</span>
    </button></li>`;
  }

  function libraryListOffset() {
    const toolbarHeight = libraryElement.querySelector(".pv2-pokemon-mobile-toolbar")?.offsetHeight || 0;
    const metaHeight = libraryElement.querySelector(".pv2-pokemon-list-meta")?.offsetHeight || 0;
    return toolbarHeight + metaHeight;
  }

  function filtersActive() {
    return Boolean(ui.search || ui.type !== "all" || ui.scope !== "all");
  }

  function renderMobileLibraryToolbar() {
    const selected = selectedSpecies();
    if (!selected) return "";
    const name = effectiveName(selected);
    const currentLabel = `${dexLabel(selected)} ${name}`;
    return `<div class="pv2-pokemon-mobile-toolbar" role="toolbar" aria-label="Pokémon picker controls">
      <button type="button" data-pokemon-library-close aria-label="Close Pokémon picker and return to ${escapeHtml(name)}">Back</button>
      <span><small>Current Pokémon</small><strong>${escapeHtml(currentLabel)}</strong></span>
      <button type="button" data-pokemon-current>Current</button>
      ${filtersActive() ? `<button type="button" data-pokemon-clear-filters>Clear</button>` : ""}
    </div>`;
  }

  function updateMobileLibraryToolbar() {
    const toolbar = libraryElement.querySelector(".pv2-pokemon-mobile-toolbar");
    if (toolbar) toolbar.outerHTML = renderMobileLibraryToolbar();
  }

  function renderLibraryWindow({ focusKey = "" } = {}) {
    const list = libraryElement.querySelector(".pv2-pokemon-list");
    if (!list) return;
    const activeRow = document.activeElement?.closest?.("[data-pokemon-select]");
    const restoreKey = focusKey || (activeRow && libraryElement.contains(activeRow) ? activeRow.dataset.pokemonSelect : "");
    if (!ui.filtered.length) {
      libraryElement.removeAttribute("aria-activedescendant");
      list.innerHTML = `<li><div class="pv2-pokemon-empty"><strong>No Pokémon match these filters.</strong><span>Try another name, type, or record scope.</span></div></li>`;
      return;
    }
    const listTop = libraryListOffset();
    const viewportRows = Math.min(26, Math.max(10, Math.ceil((libraryElement.clientHeight || 580) / LIST_ROW_HEIGHT)));
    const firstVisible = Math.floor(Math.max(0, libraryElement.scrollTop - listTop) / LIST_ROW_HEIGHT);
    const start = Math.max(0, firstVisible - LIST_OVERSCAN);
    const end = Math.min(ui.filtered.length, firstVisible + viewportRows + LIST_OVERSCAN);
    const focusedIndex = restoreKey ? ui.filtered.findIndex((species) => species.__key === restoreKey) : -1;
    const switchesToActiveDescendant = focusedIndex >= 0 && (focusedIndex < start || focusedIndex >= end);
    if (switchesToActiveDescendant) {
      ui.rovingKey = ui.filtered[Math.min(firstVisible, ui.filtered.length - 1)]?.__key || "";
      libraryElement.tabIndex = 0;
      libraryElement.focus({ preventScroll: true });
    }
    const topSpace = start * LIST_ROW_HEIGHT;
    const bottomSpace = (ui.filtered.length - end) * LIST_ROW_HEIGHT;
    list.innerHTML = `${topSpace ? `<li class="pv2-pokemon-window-space" style="height:${topSpace}px" aria-hidden="true"></li>` : ""}${ui.filtered.slice(start, end).map(renderLibraryRow).join("")}${bottomSpace ? `<li class="pv2-pokemon-window-space" style="height:${bottomSpace}px" aria-hidden="true"></li>` : ""}`;
    const restored = restoreKey ? list.querySelector(`[data-pokemon-select="${CSS.escape(restoreKey)}"]`) : null;
    if (restored) {
      libraryElement.removeAttribute("aria-activedescendant");
      libraryElement.tabIndex = -1;
      restored.focus({ preventScroll: true });
    } else if (document.activeElement === libraryElement && ui.rovingKey) {
      const activeOption = list.querySelector(`[data-pokemon-select="${CSS.escape(ui.rovingKey)}"]`);
      if (activeOption?.id) libraryElement.setAttribute("aria-activedescendant", activeOption.id);
    }
  }

  function renderLibrary({ resetScroll = false, announce = false } = {}) {
    root.toggleAttribute("aria-busy", ui.busy);
    libraryElement.toggleAttribute("aria-busy", ui.busy);
    inspectorElement.toggleAttribute("aria-busy", ui.busy);
    if (ui.busy && !model.species.length) {
      if (countElement) {
        countElement.textContent = "…";
        countElement.setAttribute("aria-label", "Loading Pokémon record count");
      }
      libraryElement.innerHTML = `<div class="pv2-pokemon-loading"><span aria-hidden="true"></span><strong>Reading Pokédex index…</strong></div>`;
      return;
    }
    if (ui.error && !model.species.length) {
      if (countElement) {
        countElement.textContent = "0";
        countElement.setAttribute("aria-label", "0 visible Pokémon records");
      }
      libraryElement.innerHTML = `<div class="pv2-pokemon-empty is-error"><strong>Pokédex index unavailable</strong><span>${escapeHtml(ui.error)}</span><button type="button" data-pokemon-retry>Retry</button></div>`;
      return;
    }
    ui.filtered = visibleSpecies();
    if (!ui.filtered.some((species) => species.__key === ui.rovingKey)) {
      ui.rovingKey = ui.filtered.find((species) => species.__key === ui.selectedKey)?.__key || ui.filtered[0]?.__key || "";
    }
    if (resetScroll) libraryElement.scrollTop = 0;
    const realCount = model.species.filter((species) => !species.__isReserved).length;
    const draftedSymbols = new Set([...drafts.keys(), ...learnsetDrafts.keys(), ...evolutionDrafts.keys(), ...assetDrafts.keys(), ...[...formDrafts.values()].flatMap((draft) => [draft.baseSymbol, ...draft.forms.map((row) => row.symbol)])]);
    const invalidCount = [...draftedSymbols].reduce((count, symbol) => count + (speciesInvalid(model.species.find((species) => species.__symbol === symbol)) ? 1 : 0), 0);
    if (countElement) {
      countElement.textContent = String(ui.filtered.length);
      countElement.setAttribute("aria-label", `${ui.filtered.length} visible of ${realCount} Pokémon records`);
    }
    libraryElement.innerHTML = `${renderMobileLibraryToolbar()}<div class="pv2-pokemon-list-meta"><strong>${ui.filtered.length}</strong><span>of ${realCount} indexed</span>${invalidCount ? `<b class="pv2-pokemon-invalid-count">${invalidCount} invalid</b>` : ""}${ui.error ? `<button type="button" data-pokemon-retry title="${escapeHtml(ui.error)}">Retry refresh</button>` : ""}</div><ul class="pv2-pokemon-list" role="presentation"></ul>`;
    renderLibraryWindow();
    if (announce) announceResults();
  }

  function renderIdentityAssetGallery(species) {
    const editor = assetEditorFor(species);
    const assets = [
      ["maleFront", "Front", "is-primary"],
      ["femaleFront", "Front ♀", ""],
      ["maleBack", "Back", ""],
      ["femaleBack", "Back ♀", ""],
      ["follower", "Follower", "is-follower"],
      ["icon", "Menu icon", "is-icon"],
    ];
    return `<div class="pv2-pokemon-asset-showcase" aria-label="${escapeHtml(effectiveName(species))} visual assets">${assets.map(([slot, label, className]) => {
      const source = editor.slots?.[slot] || {};
      const draft = assetDraftFor(species, slot);
      const previewUrl = textValue(
        draft?.objectUrl,
        draft?.previewUrl,
        source.url,
        source.previewUrl,
        slot === "maleFront" ? species.__frontSpriteUrl : "",
        slot === "icon" ? species.__iconUrl : "",
      );
      const unavailable = !previewUrl;
      const visual = previewUrl
        ? slot === "follower"
          ? renderFollowerFrames(previewUrl, effectiveName(species), true)
          : ["maleFront", "femaleFront", "maleBack", "femaleBack"].includes(slot)
            ? renderBattleSpriteFrame(previewUrl, effectiveName(species), label, slot.endsWith("Back") ? 1 : 0)
            : `<img src="${escapeHtml(previewUrl)}" alt="${escapeHtml(`${effectiveName(species)} ${label}`)}" decoding="async">`
        : `<span aria-hidden="true">◇</span>`;
      return `<figure class="pv2-pokemon-asset-tile ${className}${unavailable ? " is-empty" : ""}" data-identity-asset="${slot}" title="${escapeHtml(`${label}${draft ? " · staged replacement" : ""}`)}">${visual}<figcaption>${escapeHtml(label)}${draft ? `<i aria-label="Staged replacement"></i>` : ""}</figcaption></figure>`;
    }).join("")}</div>`;
  }

  function renderFollowerFrames(url, name, compact = false) {
    const frames = [0, 2, 4, 6];
    return `<span class="pv2-pokemon-follower-frames${compact ? " is-compact" : ""}" aria-label="${escapeHtml(`${name} overworld follower directions`)}">${frames.map((frame, index) => `<span class="pv2-pokemon-follower-frame" style="--follower-frame:${frame}" aria-hidden="${index ? "true" : "false"}"><img src="${escapeHtml(url)}" alt="${index ? "" : escapeHtml(`${name} overworld follower sprite`)}" decoding="async"></span>`).join("")}</span>`;
  }

  function renderBattleSpriteFrame(url, name, label, frame) {
    return `<span class="pv2-pokemon-battle-frame" data-battle-frame="${frame}"><img src="${escapeHtml(url)}" alt="${escapeHtml(`${name} ${label}`)}" decoding="async"></span>`;
  }

  function renderIdentity(species) {
    const referenceState = model.writeDomains.length ? "Draft editor" : (model.readOnly ? "Reference" : "Index");
    const name = effectiveName(species);
    const types = effectiveTypes(species);
    return `<header class="pv2-pokemon-identity">
      <div class="pv2-pokemon-identity-copy">
        <span class="pv2-pokemon-eyebrow">${escapeHtml(dexLabel(species))} · Pokédex record</span>
        <h2>${escapeHtml(name)}</h2>
        ${species.__formName && !displayIncludesFormLabel(name, species.__formName) ? `<p>${escapeHtml(species.__formName)}</p>` : ""}
        <div class="pv2-pokemon-identity-types">${renderTypePills(types) || `<span class="pv2-pokemon-type" data-type="unknown">Type not supplied</span>`}</div>
        <span class="pv2-pokemon-identity-state"><i aria-hidden="true"></i>${referenceState}</span>
      </div>
      ${renderIdentityAssetGallery(species)}
      <button class="pv2-pokemon-browse-button" type="button" data-pokemon-library-toggle>Browse Pokémon</button>
    </header>`;
  }

  function renderTechnical(species) {
    const rows = leafRows(domainSource(species, "technical"));
    return `<details class="pv2-pokemon-technical">
      <summary><span><strong>Technical values</strong><small>Symbols, source-facing constants, and raw endpoint record</small></span><em>${rows.length || Object.keys(species).filter((key) => !key.startsWith("__")).length}</em></summary>
      <div class="pv2-pokemon-technical-body">
        ${rows.length ? `<dl>${rows.map((row) => `<div><dt>${escapeHtml(row.label)}</dt><dd>${renderValue(row.value)}</dd></div>`).join("")}</dl>` : ""}
        <details><summary>Raw endpoint record</summary><pre tabindex="0">${escapeHtml(JSON.stringify(Object.fromEntries(Object.entries(species).filter(([key]) => !key.startsWith("__"))), null, 2))}</pre></details>
      </div>
    </details>`;
  }

  function descriptorLabel(descriptor) {
    return textValue(descriptor.label, descriptor.name, humanize(pathParts(descriptor.path).at(-1)));
  }

  function descriptorGroup(descriptor, domain) {
    const path = descriptor.path.toLowerCase();
    if (domain === "entry") {
      if (/gender|bodycolor|body_color|flip/.test(path)) return "appearance";
      if (/dex|classification|category|height|weight|entry|description|flavor/.test(path)) return "dex";
      return "identity";
    }
    if (domain === "growth") {
      if (/egggroup|egg_group|eggcycles|egg_cycles/.test(path)) return "breeding";
      if (/growthrate|growth_rate/.test(path)) return "curve";
      return "training";
    }
    if (/basestats|base_stats|\.stats\./.test(path)) return "stats";
    if (/evyield|ev_yield/.test(path)) return "ev";
    if (/abilit/.test(path)) return "abilities";
    if (/type/.test(path)) return "types";
    if (/helditem|held_item|items?\[/.test(path)) return "items";
    if (/catch|baseexp|base_experience|runchance|run_chance|escape/.test(path)) return "encounter";
    return "other";
  }

  function editorGroups(domain, descriptors) {
    const definitions = domain === "entry"
      ? [["identity", "Identity"], ["dex", "Pokédex text & dimensions"], ["appearance", "Sex & appearance"]]
      : domain === "growth"
        ? [["curve", "Experience Curve"], ["training", "Training & Friendship"], ["breeding", "Breeding & Hatching"]]
        : [["stats", "Base stats"], ["types", "Type Pair"], ["abilities", "Ability Slots"], ["ev", "EV Yield"], ["encounter", "Battle rewards & capture"], ["items", "Held Items"], ["other", "Other battle values"]];
    return definitions.map(([key, label]) => ({ key, label, fields: descriptors.filter((descriptor) => descriptorGroup(descriptor, domain) === key) })).filter((group) => group.fields.length);
  }

  function enumOptionValue(option) {
    return textValue(option?.symbol, option?.raw, option?.key, option?.value);
  }

  function genderPresetOptions() {
    return [
      [0, "Male only"],
      [31, "87.5% male · 12.5% female"],
      [63, "75% male · 25% female"],
      [127, "50% male · 50% female"],
      [191, "25% male · 75% female"],
      [225, "12.5% male · 87.5% female"],
      [254, "Female only"],
      [255, "Genderless"],
    ];
  }

  function renderEnumOptions(descriptor, value) {
    const empty = descriptor.nullable === true ? `<option value="">Not set</option>` : "";
    const options = enumOptionsFor(descriptor);
    const fallback = value !== "" && !options.some((option) => enumOptionValue(option) === String(value))
      ? `<option value="${escapeHtml(value)}" selected>${escapeHtml(humanize(value))}</option>`
      : "";
    return `${empty}${fallback}${options.map((option) => {
      const raw = enumOptionValue(option);
      return `<option value="${escapeHtml(raw)}" ${String(value) === raw ? "selected" : ""}>${escapeHtml(optionLabel(option))}</option>`;
    }).join("")}`;
  }

  function comboboxOptions(descriptor) {
    if (comboboxOptionCache.has(descriptor)) return comboboxOptionCache.get(descriptor);
    const normalized = enumOptionsFor(descriptor).map((option, index) => {
      const symbol = enumOptionValue(option);
      const label = optionLabel(option);
      const aliases = asArray(firstDefined(option?.aliases, option?.searchAliases, option?.alias, [])).map(valueLabel);
      const search = [label, symbol, ...aliases].filter(Boolean).join(" ").toLowerCase();
      return {
        index,
        symbol,
        label,
        search,
        searchCompact: compact(search),
      };
    }).filter((option) => option.symbol);
    comboboxOptionCache.set(descriptor, normalized);
    return normalized;
  }

  function normalizedStructuredOptions(rawOptions, kind) {
    const expanded = kind === "species" ? asArray(rawOptions).flatMap((option) => [option, ...asArray(option?.forms).map((form) => ({ ...form, baseSymbol: option.symbol, nationalDexNumber: option.nationalDexNumber }))]) : asArray(rawOptions);
    return expanded.map((option, index) => {
      const symbol = kind === "species" ? textValue(option?.symbol, option?.baseSymbol) : enumOptionValue(option);
      const label = textValue(option?.label, option?.name, humanize(symbol));
      const form = option?.baseSymbol ? `Form ${firstDefined(option?.formIndex, "variant")}` : textValue(option?.formName, option?.formLabel);
      const dex = firstDefined(option?.nationalDexNumber, option?.dexNumber);
      const aliases = asArray(firstDefined(option?.aliases, option?.searchAliases, [])).map(valueLabel);
      const search = [label, symbol, form, dex, ...aliases].filter(Boolean).join(" ").toLowerCase();
      const adjustedSymbol = textValue(option?.adjustedSymbol, option?.adjustedRecord?.symbol, option?.symbol, option?.baseSymbol);
      const pokemon = model.species.find((candidate) => candidate.__symbol === adjustedSymbol);
      const identity = textValue(option?.identity, option?.logicalAlias, option?.baseSymbol && option?.formIndex !== undefined ? `${option.baseSymbol}@FORM_${option.formIndex}` : symbol);
      return { index, identity, symbol, label, form, dex, baseSymbol: option?.baseSymbol, formIndex: option?.formIndex, adjustedSymbol, adjustedRecord: option?.adjustedRecord, logicalAlias: option?.logicalAlias, enabled: option?.enabled, sprite: pokemon?.__iconUrl || "", search: `${search} ${identity}`.toLowerCase(), searchCompact: compact(`${search} ${identity}`) };
    }).filter((option) => option.symbol && option?.enabled !== false);
  }

  function structuredComboboxConfig(control, species) {
    const kind = control.dataset.structuredCombobox;
    const detail = editorDetailFor(species);
    if (!kind || !detail) return null;
    let rawOptions = [];
    let optionKind = kind;
    let parameterOptionSymbols = null;
    if (kind === "move") rawOptions = detail.moveOptions;
    else if (kind === "evolution-method") rawOptions = detail.evolutionOptions?.evolutionMethods;
    else if (kind === "evolution-target") rawOptions = [...asArray(detail.evolutionOptions?.species), ...asArray(detail.evolutionOptions?.forms)];
    else if (kind === "baby") {
      const roots = new Set(projectedFamilyFor(species).roots);
      rawOptions = asArray(firstDefined(detail.evolutionOptions?.babySpecies, detail.evolutionOptions?.species, [])).filter((option) => roots.has(option.symbol)).map((option) => ({ ...option, forms: [] }));
      optionKind = "baby-roots";
    }
    else if (kind === "evolution-parameter") {
      const edge = evolutionValueFor(species).edges[Number(control.dataset.evolutionParameter)];
      const schema = evolutionParameterSchema(edge?.method) || {};
      const source = textValue(schema.enumSource).split(".").at(-1);
      rawOptions = detail.evolutionOptions?.[source];
      parameterOptionSymbols = new Set(asArray(schema.optionSymbols));
      if (source === "species") optionKind = "species";
    }
    let options = normalizedStructuredOptions(rawOptions, kind === "evolution-target" ? "species" : optionKind);
    if (parameterOptionSymbols?.size) options = options.filter((option) => {
      if (optionKind !== "species" || !Number(option.formIndex)) return parameterOptionSymbols.has(option.symbol) || parameterOptionSymbols.has(option.identity);
      return parameterOptionSymbols.has(option.identity) || option.adjustedSymbol !== option.baseSymbol && parameterOptionSymbols.has(option.adjustedSymbol);
    });
    return { kind, options, selectedSymbol: textValue(control.dataset.structuredSymbol), selectedLabel: control.value };
  }

  function positionComboboxPopup() {
    const control = comboboxState.control;
    if (!control?.isConnected || comboboxPopup.hidden) return;
    const bounds = control.getBoundingClientRect();
    const availableBelow = Math.max(0, window.innerHeight - bounds.bottom - 10);
    const availableAbove = Math.max(0, bounds.top - 10);
    const opensAbove = availableBelow < 220 && availableAbove > availableBelow;
    const available = opensAbove ? availableAbove : availableBelow;
    const popupHeight = Math.min(360, Math.max(120, available));
    comboboxPopup.style.left = `${Math.max(8, Math.min(bounds.left, window.innerWidth - Math.max(bounds.width, 260) - 8))}px`;
    comboboxPopup.style.width = `${Math.max(bounds.width, 260)}px`;
    comboboxPopup.style.maxHeight = `${popupHeight}px`;
    const renderedHeight = Math.min(popupHeight, comboboxPopup.scrollHeight || popupHeight);
    comboboxPopup.style.top = `${opensAbove ? Math.max(8, bounds.top - renderedHeight - 3) : bounds.bottom + 3}px`;
    comboboxPopup.classList.toggle("is-above", opensAbove);
  }

  function renderComboboxPopup() {
    const { control, filtered, activeIndex } = comboboxState;
    if (!control) return;
    const maximumStart = Math.max(0, filtered.length - COMBOBOX_WINDOW_SIZE);
    const start = Math.max(0, Math.min(maximumStart, activeIndex - Math.floor(COMBOBOX_WINDOW_SIZE / 2)));
    const visible = filtered.slice(start, start + COMBOBOX_WINDOW_SIZE);
    const token = ++comboboxState.renderToken;
    const resultCopy = filtered.length > COMBOBOX_WINDOW_SIZE
      ? `Type to narrow ${filtered.length} values · showing ${start + 1}–${start + visible.length}`
      : `${filtered.length} match${filtered.length === 1 ? "" : "es"}`;
    comboboxPopup.innerHTML = `<div class="pv2-pokemon-combobox-meta" role="presentation">${resultCopy}</div>${visible.length ? visible.map((option, offset) => {
      const filteredIndex = start + offset;
      const active = filteredIndex === activeIndex;
      const id = `pv2-pokemon-combobox-option-${token}-${filteredIndex}`;
      return `<button id="${id}" type="button" role="option" tabindex="-1" aria-selected="${option.identity === control.dataset.pokemonComboboxSymbol || option.symbol === control.dataset.pokemonComboboxSymbol}" aria-setsize="${filtered.length}" aria-posinset="${filteredIndex + 1}" class="${active ? "is-active" : ""}" data-pokemon-combobox-option="${filteredIndex}">${option.sprite ? `<img src="${escapeHtml(option.sprite)}" alt="" loading="lazy">` : ""}<span><strong>${escapeHtml(option.label)}</strong>${option.dex || option.form ? `<small>${option.dex ? `#${String(option.dex).padStart(3, "0")}` : ""}${option.form ? ` · ${escapeHtml(option.form)}` : ""}</small>` : ""}</span><code>${escapeHtml(option.symbol)}${option.formIndex !== undefined ? ` · form ${escapeHtml(option.formIndex)}` : ""}</code></button>`;
    }).join("") : `<div class="pv2-pokemon-combobox-empty" role="presentation">No matching source values</div>`}`;
    const active = comboboxPopup.querySelector("[role=option].is-active");
    if (active) control.setAttribute("aria-activedescendant", active.id);
    else control.removeAttribute("aria-activedescendant");
    positionComboboxPopup();
  }

  function filterCombobox(query, { preserveActive = false } = {}) {
    const needle = String(query || "").trim().toLowerCase();
    const compactNeedle = compact(needle);
    comboboxState.filtered = comboboxState.options.filter((option) => !needle || option.search.includes(needle) || (compactNeedle && option.searchCompact.includes(compactNeedle)));
    if (!preserveActive || comboboxState.activeIndex >= comboboxState.filtered.length) comboboxState.activeIndex = comboboxState.filtered.length ? 0 : -1;
    renderComboboxPopup();
  }

  function openCombobox(control, query = "") {
    const species = selectedSpecies();
    if (!species) return;
    const structured = structuredComboboxConfig(control, species);
    const descriptor = structured ? null : descriptorsFor(activeDomain(species)).find((candidate) => candidate.path === control.dataset.pokemonCombobox);
    if (!structured && (!descriptor || !recordFieldAccess(species, descriptor).writable)) return;
    comboboxState.control = control;
    comboboxState.species = species;
    comboboxState.descriptor = descriptor;
    comboboxState.structured = structured;
    comboboxState.selectedLabel = structured?.selectedLabel || enumLabelFor(descriptor, fieldValue(species, descriptor));
    comboboxState.options = structured?.options || comboboxOptions(descriptor);
    comboboxPopup.hidden = false;
    control.setAttribute("aria-expanded", "true");
    filterCombobox(query);
    if (!String(query).trim()) {
      const selectedIndex = comboboxState.filtered.findIndex((option) => (option.identity || option.symbol) === control.dataset.pokemonComboboxSymbol);
      if (selectedIndex >= 0) {
        comboboxState.activeIndex = selectedIndex;
        renderComboboxPopup();
      }
    }
  }

  function closeCombobox({ restore = true } = {}) {
    const { control, species, descriptor, structured } = comboboxState;
    if (restore && control?.isConnected && species) {
      if (descriptor) {
        const symbol = fieldValue(species, descriptor);
        control.value = enumLabelFor(descriptor, symbol);
        control.dataset.pokemonComboboxSymbol = String(symbol ?? "");
      } else if (structured) control.value = comboboxState.selectedLabel;
    }
    control?.setAttribute("aria-expanded", "false");
    control?.removeAttribute("aria-activedescendant");
    comboboxPopup.hidden = true;
    comboboxPopup.innerHTML = "";
    comboboxState.control = null;
    comboboxState.species = null;
    comboboxState.descriptor = null;
    comboboxState.structured = null;
    comboboxState.selectedLabel = "";
    comboboxState.options = [];
    comboboxState.filtered = [];
    comboboxState.activeIndex = -1;
  }

  function selectComboboxOption(index) {
    const option = comboboxState.filtered[index];
    const { control, species, descriptor, structured } = comboboxState;
    if (!option || !control || !species || (!descriptor && !structured)) return;
    control.value = option.label;
    control.dataset.pokemonComboboxSymbol = option.symbol;
    if (descriptor) applyFieldValue(species, descriptor, option.symbol);
    else applyStructuredComboboxValue(species, control, option);
    closeCombobox({ restore: false });
    control.focus({ preventScroll: true });
  }

  function applyStructuredComboboxValue(species, control, option) {
    const kind = control.dataset.structuredCombobox;
    const focusSelector = kind === "move" ? `[data-move-symbol="${control.dataset.moveSymbol}"]` : kind === "baby" ? "[data-evolution-baby]" : kind === "evolution-method" ? `[data-evolution-method="${control.dataset.evolutionMethod}"]` : kind === "evolution-parameter" ? `[data-evolution-parameter="${control.dataset.evolutionParameter}"]` : `[data-evolution-target="${control.dataset.evolutionTarget}"]`;
    if (kind === "move") {
      const index = Number(control.dataset.moveSymbol);
      mutateLearnset(species, (draft) => {
        const group = activeMoveGroup(species);
        if (group === "levelMoves") draft.levelMoves[index].move = option.symbol;
        else draft[group][index] = option.symbol;
      });
    } else if (kind === "baby") {
      recomputeFamilyStaging(species, option.symbol);
      renderInspector();
      refreshStructuredChrome(species);
    }
    else {
      const index = Number(firstDefined(control.dataset.evolutionMethod, control.dataset.evolutionTarget, control.dataset.evolutionParameter));
      mutateEvolution(species, (draft) => {
        if (kind === "evolution-method") {
          draft.edges[index].method = option.symbol;
          const parameterKind = evolutionParameterKind(option.symbol);
          draft.edges[index].parameter = ["fixed", "zero"].includes(parameterKind) ? "0" : ["integer", "number", "numeric", "level"].includes(parameterKind) ? "1" : "";
        } else if (kind === "evolution-parameter") draft.edges[index].parameter = option.symbol;
        else {
          draft.edges[index].targetSymbol = option.baseSymbol || option.symbol;
          if (option.baseSymbol && Number(option.formIndex) > 0) draft.edges[index].targetFormIndex = Number(option.formIndex);
          else delete draft.edges[index].targetFormIndex;
        }
      });
    }
    setStatus(`${option.label} selected.`, "info");
    requestAnimationFrame(() => inspectorElement.querySelector(focusSelector)?.focus({ preventScroll: true }));
  }

  function fieldCounter(descriptor, value, species = null) {
    const kind = controlKind(descriptor, species);
    if (!["text", "textarea"].includes(kind)) return "";
    const maximumLines = lineLimitFor(descriptor);
    const { maximum } = stringBounds(descriptor);
    if (!Number.isFinite(maximum) && !Number.isFinite(maximumLines)) return "";
    const characters = String(value ?? "").length;
    const lines = String(value ?? "").split(/\r?\n/).length;
    return [Number.isFinite(maximum) ? `${characters}/${maximum} chars` : "", Number.isFinite(maximumLines) ? `${lines}/${maximumLines} lines` : ""].filter(Boolean).join(" · ");
  }

  function renderEditorField(species, descriptor, { aggregateErrorId = "" } = {}) {
    const kind = controlKind(descriptor, species);
    const value = fieldValue(species, descriptor);
    const changed = fieldChanged(species, descriptor);
    const access = recordFieldAccess(species, descriptor);
    const validation = changed ? (speciesValidationErrors(species).find((error) => error.path === descriptor.path)?.message || fieldError(species, descriptor)) : "";
    const label = descriptorLabel(descriptor);
    const id = `pv2-pokemon-field-${species.__symbol}-${descriptor.path}`.replace(/[^a-zA-Z0-9_-]/g, "-");
    const errorId = `${id}-error`;
    const helpId = `${id}-help`;
    const counterId = `${id}-counter`;
    const help = /genderratio|gender_ratio/i.test(descriptor.path)
      ? "Choose a named ratio preset. The source byte remains visible under Technical values."
      : textValue(access.writable ? "" : access.reason, descriptor.help, descriptor.description);
    const counter = fieldCounter(descriptor, value, species);
    const aggregateInvalid = Boolean(aggregateErrorId);
    const describedIds = [help ? helpId : "", counter ? counterId : "", validation ? errorId : "", aggregateErrorId].filter(Boolean).join(" ");
    const describedBy = describedIds ? ` aria-describedby="${describedIds}"` : "";
    const dataAttribute = kind === "combobox" ? "data-pokemon-combobox" : "data-pokemon-field";
    const common = `id="${id}" ${dataAttribute}="${escapeHtml(descriptor.path)}" aria-label="${escapeHtml(label)}" aria-invalid="${Boolean(validation || aggregateInvalid)}"${describedBy}${access.writable ? "" : " disabled"}`;
    let control;
    if (/genderratio|gender_ratio/i.test(descriptor.path)) {
      const presets = genderPresetOptions();
      const custom = presets.some(([raw]) => Number(value) === raw) ? "" : `<option value="${escapeHtml(value)}" selected>Custom source ratio</option>`;
      control = `<select ${common}>${custom}${presets.map(([raw, display]) => `<option value="${raw}" ${Number(value) === raw ? "selected" : ""}>${escapeHtml(display)}</option>`).join("")}</select>`;
    } else if (kind === "boolean") {
      control = `<label class="pv2-pokemon-switch"><input type="checkbox" ${common} ${value ? "checked" : ""}><span>${value ? "Yes" : "No"}</span></label>`;
    } else if (kind === "enum") {
      control = `<select ${common}>${renderEnumOptions(descriptor, value)}</select>`;
    } else if (kind === "combobox") {
      control = `<input type="text" ${common} role="combobox" aria-autocomplete="list" aria-haspopup="listbox" aria-controls="${COMBOBOX_LIST_ID}" aria-expanded="false" autocomplete="off" spellcheck="false" data-pokemon-combobox-symbol="${escapeHtml(value)}" value="${escapeHtml(enumLabelFor(descriptor, value))}">`;
    } else if (kind === "textarea") {
      const { minimum, maximum } = stringBounds(descriptor);
      control = `<textarea ${common} rows="${Number(descriptor.rows) || 3}"${Number.isFinite(minimum) ? ` minlength="${minimum}"` : ""}${Number.isFinite(maximum) ? ` maxlength="${maximum}"` : ""}>${escapeHtml(value)}</textarea>`;
    } else if (kind === "number") {
      const { minimum, maximum } = numberBounds(descriptor);
      control = `<input type="number" ${common} value="${escapeHtml(value)}"${Number.isFinite(minimum) ? ` min="${minimum}"` : ""}${Number.isFinite(maximum) ? ` max="${maximum}"` : ""} step="${descriptor.integer === false ? "any" : "1"}">`;
    } else {
      const { minimum, maximum } = stringBounds(descriptor);
      control = `<input type="text" ${common} value="${escapeHtml(value)}"${Number.isFinite(minimum) ? ` minlength="${minimum}"` : ""}${Number.isFinite(maximum) ? ` maxlength="${maximum}"` : ""}>`;
    }
    return `<div class="pv2-pokemon-edit-field${changed ? " is-changed" : ""}${validation ? " is-invalid" : ""}${aggregateInvalid ? " is-aggregate-invalid" : ""}${access.writable ? "" : " is-readonly"}" data-pokemon-field-shell="${escapeHtml(descriptor.path)}">
      <div class="pv2-pokemon-field-heading"><label for="${id}"><strong>${escapeHtml(label)}</strong>${descriptor.unit && !/genderratio|gender_ratio/i.test(descriptor.path) ? `<small>${escapeHtml(descriptor.unit)}</small>` : ""}</label><button type="button" data-pokemon-revert-field="${escapeHtml(descriptor.path)}" ${changed ? "" : "hidden"}>Revert</button></div>
      ${control}
      <p id="${errorId}" class="pv2-pokemon-field-error" ${validation ? "" : "hidden"}>${escapeHtml(validation)}</p>
      ${counter ? `<small id="${counterId}" class="pv2-pokemon-field-counter" data-field-counter>${escapeHtml(counter)}</small>` : ""}
      ${help ? `<small id="${helpId}" class="pv2-pokemon-field-help">${escapeHtml(help)}</small>` : ""}
    </div>`;
  }

  function fieldByPattern(species, domain, pattern, fallbackPaths = []) {
    const descriptor = descriptorsFor(domain).find((candidate) => pattern.test(candidate.path));
    if (descriptor) return fieldValue(species, descriptor);
    return fieldValueRaw(fallbackPaths.map((path) => valueAtPath(species, path)).find((value) => value !== undefined));
  }

  function renderEntryPreview(species) {
    const name = effectiveName(species);
    const classification = textValue(fieldByPattern(species, "entry", /classification|category/i, ["dex.classification", "classification"]), "Classification not supplied");
    const entry = textValue(fieldByPattern(species, "entry", /dex.*entry|entry$|description|flavor/i, ["dex.entry", "dexEntry", "description"]), "No Pokédex text supplied.");
    const height = textValue(fieldByPattern(species, "entry", /height/i, ["dex.height", "height"]));
    const weight = textValue(fieldByPattern(species, "entry", /weight/i, ["dex.weight", "weight"]));
    const details = [classification, height && `Height ${height}`, weight && `Weight ${weight}`].filter(Boolean).join(" · ");
    return `<div class="pv2-pokemon-entry-preview-line"><strong>${escapeHtml(dexLabel(species))} · ${escapeHtml(name)}</strong></div><div class="pv2-pokemon-entry-preview-line"><span>${escapeHtml(details)}</span></div><div class="pv2-pokemon-entry-preview-line"><p>${escapeHtml(entry)}</p></div>`;
  }

  function statDescriptors() {
    return descriptorsFor("battle").filter((descriptor) => /basestats|base_stats|\.stats\./i.test(descriptor.path));
  }

  function renderBattleMetrics(species) {
    const stats = statDescriptors();
    const values = stats.map((descriptor) => Number(fieldValue(species, descriptor)) || 0);
    const total = values.reduce((sum, value) => sum + value, 0);
    const evFields = descriptorsFor("battle").filter((descriptor) => /evyield|ev_yield/i.test(descriptor.path));
    const evTotal = evFields.reduce((sum, descriptor) => sum + (Number(fieldValue(species, descriptor)) || 0), 0);
    const evInvalid = speciesGroupValidationErrors(species).some((error) => error.group === "ev");
    return `<div class="pv2-pokemon-stat-summary"><div class="pv2-pokemon-stat-total"><small>Base stat total</small><strong>${total}</strong></div><div class="pv2-pokemon-stat-bars">${stats.map((descriptor, index) => {
      const percent = Math.max(0, Math.min(100, values[index] / 255 * 100));
      return `<div><span>${escapeHtml(descriptorLabel(descriptor))}</span><i><b style="--pv2-stat-width:${percent}%"></b></i><strong>${values[index]}</strong></div>`;
    }).join("") || `<p>No base-stat fields are registered.</p>`}</div><div class="pv2-pokemon-ev-total"><small>EV yield total</small><strong class="${evInvalid ? "is-invalid" : ""}">${evTotal}</strong></div></div>`;
  }

  function renderGrowthMetrics(species) {
    const value = (pattern, fallback) => textValue(fieldByPattern(species, "growth", pattern, fallback), "Not supplied");
    return `<div class="pv2-pokemon-growth-summary"><div><small>Growth rate</small><strong>${escapeHtml(humanize(value(/growthrate|growth_rate/i, ["growthRate.symbol", "growthRate"])))}</strong></div><div><small>Egg cycles</small><strong>${escapeHtml(value(/eggcycles|egg_cycles/i, ["eggCycles"]))}</strong></div><div><small>Base friendship</small><strong>${escapeHtml(value(/basefriendship|base_friendship/i, ["baseFriendship"]))}</strong></div></div>`;
  }

  function renderWritableDomain(species, domain) {
    const descriptors = descriptorsFor(domain);
    const changed = descriptors.filter((descriptor) => fieldChanged(species, descriptor)).length;
    const anyWritable = writableDescriptorsFor(species, domain).length > 0;
    const groups = editorGroups(domain, descriptors);
    return `<section class="pv2-pokemon-domain pv2-pokemon-domain--editor" data-pokemon-editor-domain="${domain}">
      <header><div><span class="pv2-pokemon-eyebrow">${anyWritable ? "Source draft editor" : "Source reference"}</span><h3>${domain === "entry" ? "Pokédex entry" : domain === "growth" ? "Growth & breeding" : "Battle specification"}</h3></div><div class="pv2-pokemon-domain-actions"><small data-editor-change-count>${anyWritable ? `${changed} changed · Global Save` : "Reference-only for this record"}</small><button type="button" data-pokemon-revert-domain="${domain}" ${changed ? "" : "hidden"}>Revert domain</button></div></header>
      ${domain === "entry" ? `<div class="pv2-pokemon-entry-preview" data-entry-preview>${renderEntryPreview(species)}</div>` : domain === "growth" ? `<div data-growth-metrics>${renderGrowthMetrics(species)}</div>` : `<div data-battle-metrics>${renderBattleMetrics(species)}</div>`}
      <div class="pv2-pokemon-editor-groups">${groups.map((group) => {
        const groupChanged = group.fields.filter((descriptor) => fieldChanged(species, descriptor)).length;
        const fieldErrors = speciesValidationErrors(species).filter((error) => group.fields.some((descriptor) => descriptor.path === error.path));
        const compositeErrors = speciesGroupValidationErrors(species).filter((error) => error.group === group.key);
        const errorCount = fieldErrors.length + compositeErrors.length;
        const stateCopy = [groupChanged ? `${groupChanged} changed` : "", errorCount ? `${errorCount} error${errorCount === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ");
        const composite = ["types", "abilities", "ev", "items", "breeding"].includes(group.key);
        const groupId = `pv2-pokemon-group-${species.__symbol}-${group.key}`.replace(/[^a-zA-Z0-9_-]/g, "-");
        const groupErrorId = `${groupId}-error`;
        return `<section class="pv2-pokemon-editor-group${composite ? " is-composite" : ""}${groupChanged ? " is-changed" : ""}${errorCount ? " is-invalid" : ""}" data-editor-group="${group.key}" role="group" tabindex="-1" aria-labelledby="${groupId}-label" aria-invalid="${Boolean(errorCount)}"${compositeErrors.length ? ` aria-describedby="${groupErrorId}"` : ""}><header><h4 id="${groupId}-label">${escapeHtml(group.label)}</h4><div><small data-group-state>${escapeHtml(stateCopy)}</small><button type="button" data-pokemon-revert-group="${group.key}" ${groupChanged ? "" : "hidden"}>Revert group</button></div></header><div class="pv2-pokemon-edit-grid">${group.fields.map((descriptor) => renderEditorField(species, descriptor, { aggregateErrorId: group.key === "ev" && compositeErrors.length ? groupErrorId : "" })).join("")}</div><p id="${groupErrorId}" class="pv2-pokemon-group-error" data-group-error ${compositeErrors.length ? "" : "hidden"}>${escapeHtml(compositeErrors[0]?.message || "")}</p></section>`;
      }).join("")}</div>
      <p class="pv2-pokemon-save-note">Changes remain in the workspace draft until the global Save action commits them.</p>
    </section>`;
  }

  function activeMoveGroup(species) {
    const stored = moveTabBySpecies.get(species.__symbol);
    return MOVE_GROUPS.some(([key]) => key === stored) ? stored : "levelMoves";
  }

  function moveRowHeight() {
    return globalThis.matchMedia?.("(max-width: 600px)").matches ? 148 : MOVE_ROW_HEIGHT;
  }

  function moveDisplayName(symbol) {
    const option = moveOption(symbol);
    return option ? optionLabel(option) : humanize(symbol);
  }

  function moveOption(symbol) {
    return asArray(firstDefined(editorDetailFor(selectedSpecies())?.moveOptions, model.enums.moves, model.enums.moveOptions, [])).find((candidate) => enumOptionValue(candidate) === symbol);
  }

  function moveTypeInfo(symbol) {
    const option = moveOption(symbol);
    const typeSymbol = textValue(option?.typeSymbol, option?.type?.symbol, option?.type, "TYPE_NORMAL");
    return { key: visualTypeKey(typeSymbol), label: textValue(typeof option?.type === "string" ? option.type : option?.type?.label, humanize(typeSymbol)) };
  }

  function structuredComboboxInput(kind, symbol, label, dataAttributes, disabled = false, identity = symbol) {
    return `<input type="text" role="combobox" data-structured-combobox="${kind}" data-structured-symbol="${escapeHtml(symbol)}" data-pokemon-combobox-symbol="${escapeHtml(identity)}" ${dataAttributes} value="${escapeHtml(label)}" aria-autocomplete="list" aria-haspopup="listbox" aria-controls="${COMBOBOX_LIST_ID}" aria-expanded="false" autocomplete="off" spellcheck="false" ${disabled ? "disabled" : ""}>`;
  }

  function renderMoveWindow(species, groupKey, values) {
    const query = textValue(moveSearchBySpecies.get(species.__symbol)).trim().toLowerCase();
    const indexed = values.map((value, index) => ({ value, index })).filter(({ value }) => {
      const symbol = groupKey === "levelMoves" ? value.move : value;
      return !query || `${symbol} ${moveDisplayName(symbol)} ${groupKey === "levelMoves" ? value.level : ""}`.toLowerCase().includes(query);
    });
    const windowKey = `${species.__symbol}:${groupKey}`;
    const start = Math.max(0, Math.min(Number(moveWindowBySpecies.get(windowKey)) || 0, Math.max(0, indexed.length - MOVE_WINDOW_SIZE)));
    const visible = indexed.slice(start, start + MOVE_WINDOW_SIZE);
    const source = learnsetDetailFor(species);
    const writable = learnsetWritable(species) && (source?.provenance !== "inherited" || learnsetDrafts.get(species.__symbol)?.materializeInherited === true);
    const reorderDisabled = !writable || Boolean(query);
    const rows = visible.map(({ value, index }) => {
      const symbol = groupKey === "levelMoves" ? value.move : value;
      const rowErrors = learnsetValidationErrors().filter((error) => error.species.__symbol === species.__symbol && error.path.startsWith(`moves.${groupKey}.${index}.`));
      const levelError = rowErrors.find((error) => error.path.endsWith(".level"));
      const moveError = rowErrors.find((error) => error.path.endsWith(".move"));
      const errorId = `pv2-move-error-${species.__symbol}-${groupKey}-${index}`.replace(/[^a-zA-Z0-9_-]/g, "-");
      const levelErrorId = `${errorId}-level`;
      const moveErrorId = `${errorId}-move`;
      const rowErrorIds = [levelError && levelErrorId, moveError && moveErrorId].filter(Boolean).join(" ");
      const visibleErrors = [...new Set([levelError?.message, moveError?.message].filter(Boolean))].join(" · ");
      const moveType = moveTypeInfo(symbol);
      return `<div class="pv2-pokemon-move-row${groupKey === "levelMoves" ? " has-level" : " is-level-free"}${rowErrors.length ? " is-invalid" : ""}" role="listitem" data-move-row="${index}" data-move-type="${escapeHtml(moveType.key)}" tabindex="0" aria-invalid="${Boolean(rowErrors.length)}"${rowErrorIds ? ` aria-describedby="${rowErrorIds}"` : ""}><span class="pv2-pokemon-move-order" aria-hidden="true">${index + 1}</span>${groupKey === "levelMoves" ? `<label><span class="sr-only">Level</span><input type="number" min="0" max="100" step="1" required value="${escapeHtml(value.level)}" data-move-level="${index}" aria-invalid="${Boolean(levelError)}"${levelError ? ` aria-describedby="${levelErrorId}"` : ""} ${writable ? "" : "disabled"}></label>` : ""}<label class="pv2-pokemon-move-symbol"><span class="pv2-pokemon-move-label"><b>${escapeHtml(moveDisplayName(symbol) || "Choose move")}</b><small class="pv2-pokemon-type" data-type="${escapeHtml(moveType.key)}">${escapeHtml(moveType.label)}</small></span>${structuredComboboxInput("move", symbol, moveDisplayName(symbol), `data-move-symbol="${index}" aria-invalid="${Boolean(moveError)}"${moveError ? ` aria-describedby="${moveErrorId}"` : ""}`, !writable)}</label><div class="pv2-pokemon-row-actions"><button type="button" data-move-up="${index}" ${reorderDisabled || index === 0 ? "disabled" : ""} aria-label="Move ${escapeHtml(moveDisplayName(symbol))} up">↑</button><button type="button" data-move-down="${index}" ${reorderDisabled || index === values.length - 1 ? "disabled" : ""} aria-label="Move ${escapeHtml(moveDisplayName(symbol))} down">↓</button><button type="button" data-move-remove="${index}" ${writable ? "" : "disabled"} aria-label="Remove ${escapeHtml(moveDisplayName(symbol))}">Remove</button></div>${levelError ? `<p id="${levelErrorId}" class="sr-only" data-move-error-field="level">${escapeHtml(levelError.message)}</p>` : ""}${moveError ? `<p id="${moveErrorId}" class="sr-only" data-move-error-field="move">${escapeHtml(moveError.message)}</p>` : ""}${visibleErrors ? `<p class="pv2-pokemon-row-error-copy" data-move-error-summary aria-hidden="true">${escapeHtml(visibleErrors)}</p>` : ""}</div>`;
    }).join("");
    const rowHeight = moveRowHeight();
    return `${query ? `<p class="pv2-pokemon-reorder-note">Reordering is disabled while this section is filtered. Clear the filter to preserve source order.</p>` : ""}<div class="pv2-pokemon-move-list" role="list" tabindex="0" aria-label="${escapeHtml(humanize(groupKey))}" data-move-list data-move-group="${groupKey}" style="--pv2-move-total:${indexed.length * rowHeight}px"><div role="presentation" aria-hidden="true" style="height:${start * rowHeight}px"></div>${rows || `<div class="pv2-pokemon-move-empty" role="listitem">No moves match this view.</div>`}<div role="presentation" aria-hidden="true" style="height:${Math.max(0, indexed.length - start - visible.length) * rowHeight}px"></div></div>`;
  }

  function renderMovesEditor(species) {
    const stateRecord = editorDetailFor(species);
    if (!stateRecord || stateRecord.status === "loading") return `<section class="pv2-pokemon-domain pv2-pokemon-domain--editor"><div class="pv2-pokemon-loading"><span aria-hidden="true"></span><strong>Loading source learnset…</strong></div></section>`;
    if (stateRecord.status === "error") return `<section class="pv2-pokemon-domain pv2-pokemon-domain--editor"><div class="pv2-pokemon-empty is-error"><strong>Learnset unavailable</strong><span>${escapeHtml(stateRecord.error)}</span><button type="button" data-move-retry>Retry</button></div></section>`;
    const source = stateRecord.data;
    const value = learnsetValueFor(species) || source;
    const groupKey = activeMoveGroup(species);
    const writable = learnsetWritable(species);
    const inherited = source.provenance === "inherited" && !learnsetDrafts.has(species.__symbol);
    const customizing = source.provenance === "inherited" && learnsetDrafts.get(species.__symbol)?.materializeInherited === true;
    const editable = writable && (!inherited || customizing);
    const values = asArray(value[groupKey]);
    const query = textValue(moveSearchBySpecies.get(species.__symbol));
    return `<section class="pv2-pokemon-domain pv2-pokemon-moves-editor"><header><div><span class="pv2-pokemon-eyebrow">Learnset source</span><h3>Moves</h3></div><div class="pv2-pokemon-domain-actions"><small>${learnsetDrafts.has(species.__symbol) ? "1 learnset record pending · Global Save" : `${humanize(source.provenance)} provenance`}</small>${learnsetDrafts.has(species.__symbol) ? `<button type="button" data-move-revert>Revert domain</button>` : ""}</div></header>${!writable ? `<div class="pv2-pokemon-access-reasons"><p><strong>Moves are read-only.</strong> ${escapeHtml(species.learnsetAccess?.reason || "No writable learnset record.")}</p></div>` : ""}<div class="pv2-pokemon-provenance${inherited || customizing ? " is-inherited" : ""}"><span><strong>${inherited || customizing ? `Inherited from ${humanize(source.sourceSymbol)}` : "Explicit learnset"}</strong><small>${inherited ? "This form reads its base learnset. Customize creates a permanent independent source record when saved." : customizing ? "Customization is pending. Saving permanently materializes an independent form learnset." : "Row order is source order; equal-level ordering is preserved."}</small></span>${inherited && writable ? `<button type="button" data-move-customize>Customize form</button>` : customizing ? `<button type="button" data-move-cancel-customize>Cancel customization</button>` : ""}</div><div class="pv2-pokemon-move-tabs" role="group" aria-label="Learnset sections">${MOVE_GROUPS.map(([key, label]) => `<button type="button" aria-pressed="${key === groupKey}" data-move-tab="${key}">${escapeHtml(label)}<b>${asArray(value[key]).length}</b></button>`).join("")}</div><div class="pv2-pokemon-structured-tools"><label><span>Filter this learnset</span><input type="search" value="${escapeHtml(query)}" data-move-search placeholder="Move name or symbol"></label><button type="button" data-move-add ${editable ? "" : "disabled"}>Add ${groupKey === "levelMoves" ? "level move" : "move"}</button></div>${renderMoveWindow(species, groupKey, values)}<p class="pv2-pokemon-save-note">Use the arrow controls or Alt+Arrow keys to reorder without sorting equal-level rows.</p></section>`;
  }

  function evolutionMethodOptions() {
    return asArray(firstDefined(editorDetailFor(selectedSpecies())?.evolutionOptions?.evolutionMethods, model.enums.evolutionMethods, model.enums.evolutionMethodOptions, []));
  }

  function evolutionParameterSchema(method) {
    return evolutionMethodOptions().find((candidate) => enumOptionValue(candidate) === method)?.parameter || null;
  }

  function evolutionParameterKind(method) {
    const option = evolutionMethodOptions().find((candidate) => enumOptionValue(candidate) === method);
    const declared = textValue(option?.parameterKind, option?.parameter?.kind, option?.kind).toLowerCase();
    if (declared) return declared;
    if (["EVO_FRIENDSHIP", "EVO_FRIENDSHIP_DAY", "EVO_FRIENDSHIP_NIGHT", "EVO_TRADE", "EVO_LEVEL_ELECTRIC_FIELD", "EVO_LEVEL_MOSSY_STONE", "EVO_LEVEL_ICY_STONE"].includes(method)) return "zero";
    if (["EVO_TRADE_ITEM", "EVO_STONE", "EVO_STONE_MALE", "EVO_STONE_FEMALE", "EVO_ITEM_DAY", "EVO_ITEM_NIGHT"].includes(method)) return "item";
    if (method === "EVO_HAS_MOVE") return "move";
    if (method === "EVO_HAS_MOVE_TYPE") return "type";
    if (["EVO_OTHER_PARTY_MON", "EVO_TRADE_SPECIFIC_MON"].includes(method)) return "species";
    if (/ITEM|STONE|TRADE_ITEM|HOLD/.test(method)) return "item";
    if (/MOVE/.test(method)) return "move";
    if (/TYPE/.test(method)) return "type";
    if (/SPECIES/.test(method)) return "species";
    if (/LEVEL|FRIENDSHIP|BEAUTY|AFFECTION|TIME/.test(method)) return "number";
    return "expression";
  }

  function evolutionCommitParameter(edge) {
    const kind = evolutionParameterKind(edge.method);
    if (["fixed", "zero"].includes(kind)) return 0;
    if (["integer", "level", "number", "numeric"].includes(kind)) return Number(edge.parameter);
    return String(edge.parameter);
  }

  function renderEvolutionParameter(edge, index, writable, errorId = "", invalid = false) {
    const kind = evolutionParameterKind(edge.method);
    const schema = evolutionParameterSchema(edge.method) || {};
    if (["zero", "fixed"].includes(kind)) return `<label><span>Method parameter</span><input type="text" value="Fixed at 0" disabled><small>This method has no configurable condition value.</small></label>`;
    if (kind === "type") {
      const allowed = new Set(asArray(schema.optionSymbols));
      const options = asArray(model.enums.types).filter((option) => !allowed.size || allowed.has(enumOptionValue(option)));
      const fallback = edge.parameter && !options.some((option) => enumOptionValue(option) === edge.parameter) ? `<option value="${escapeHtml(edge.parameter)}" selected>${escapeHtml(humanize(edge.parameter))} · unsupported</option>` : "";
      return `<label><span>Required type</span><select data-evolution-parameter="${index}" aria-invalid="${invalid}"${invalid ? ` aria-describedby="${errorId}"` : ""} ${writable ? "" : "disabled"}>${fallback}${options.map((option) => `<option value="${escapeHtml(enumOptionValue(option))}" ${enumOptionValue(option) === edge.parameter ? "selected" : ""}>${escapeHtml(optionLabel(option))}</option>`).join("")}</select></label>`;
    }
    if (["number", "numeric", "level", "integer"].includes(kind)) return `<label><span>${schema.unit === "level" || /LEVEL/.test(edge.method) ? "Required level" : "Numeric parameter"}</span><input type="number" min="${Number(firstDefined(schema.min, 0))}" max="${Number(firstDefined(schema.max, 65535))}" step="${["number", "numeric"].includes(kind) && schema.integer === false ? "any" : "1"}" required value="${escapeHtml(edge.parameter)}" data-evolution-parameter="${index}" aria-invalid="${invalid}"${invalid ? ` aria-describedby="${errorId}"` : ""} ${writable ? "" : "disabled"}></label>`;
    return `<label><span>${kind === "item" ? "Required item" : kind === "move" ? "Required move" : kind === "species" ? "Required species" : "Method parameter"}</span>${structuredComboboxInput("evolution-parameter", edge.parameter, humanize(edge.parameter), `data-evolution-parameter="${index}" aria-invalid="${invalid}"${invalid ? ` aria-describedby="${errorId}"` : ""}`, !writable)}<small>${escapeHtml(edge.parameter)}</small></label>`;
  }

  function evolutionMethodInput(edge, index, writable, errorId = "", invalid = false) {
    const option = evolutionMethodOptions().find((candidate) => enumOptionValue(candidate) === edge.method);
    return structuredComboboxInput("evolution-method", edge.method, option ? optionLabel(option) : humanize(edge.method), `data-evolution-method="${index}" aria-invalid="${invalid}"${invalid ? ` aria-describedby="${errorId}"` : ""}`, !writable);
  }

  function evolutionSpeciesInput(kind, selectedSymbol, index, writable, errorId = "", invalid = false, identity = selectedSymbol) {
    const species = model.species.find((candidate) => candidate.__symbol === selectedSymbol);
    const options = editorDetailFor(selectedSpecies())?.evolutionOptions;
    const option = normalizedStructuredOptions([...asArray(options?.species), ...asArray(options?.forms)], "species").find((candidate) => candidate.identity === identity);
    const attribute = kind === "baby" ? "data-evolution-baby" : `data-evolution-target="${index}"`;
    return structuredComboboxInput(kind, selectedSymbol, option?.label || (species ? effectiveName(species) : humanize(selectedSymbol)), `${attribute} aria-invalid="${invalid}"${invalid ? ` aria-describedby="${errorId}"` : ""}`, !writable, identity);
  }

  function edgeTargetDisplaySymbol(edge) {
    if (edge.targetFormIndex === undefined || Number(edge.targetFormIndex) === 0) return edge.targetSymbol;
    const form = model.species.find((candidate) => textValue(candidate.baseSymbol, candidate.form?.baseSymbol, candidate.formMetadata?.baseSymbol) === edge.targetSymbol && Number(firstDefined(candidate.formIndex, candidate.form?.index, candidate.formMetadata?.formIndex)) === Number(edge.targetFormIndex));
    return form?.__symbol || edge.targetSymbol;
  }

  function edgeTargetIdentity(edge) {
    return edge.targetFormIndex !== undefined ? `${edge.targetSymbol}@FORM_${edge.targetFormIndex}` : edge.targetSymbol;
  }

  function evolutionTargetPresentation(species, edge) {
    const options = editorDetailFor(species)?.evolutionOptions;
    const option = normalizedStructuredOptions([...asArray(options?.species), ...asArray(options?.forms)], "species").find((candidate) => candidate.identity === edgeTargetIdentity(edge));
    const record = model.species.find((candidate) => candidate.__symbol === textValue(option?.adjustedSymbol, edgeTargetDisplaySymbol(edge), edge.targetSymbol));
    return { option, record, label: option?.label || (record ? effectiveName(record) : humanize(edge.targetSymbol || "Choose target")) };
  }

  function renderEvolutionFamilyOverview(species) {
    const projected = projectedFamilyFor(species);
    const symbols = projected.members;
    const members = symbols.map((symbol) => model.species.find((candidate) => candidate.__symbol === symbol)).filter(Boolean);
    const saved = new Set(asArray(species.evolutionFamily?.baseSymbols));
    const removed = [...saved].filter((symbol) => !projected.members.includes(symbol)).map((symbol) => model.species.find((candidate) => candidate.__symbol === symbol)).filter(Boolean);
    const relationship = (source, edge) => {
      const sourceFormIndex = Number(firstDefined(source.formIndex, source.form?.index, source.formMetadata?.formIndex));
      const sourceIdentity = source.__isForm && Number.isFinite(sourceFormIndex) && sourceFormIndex > 0 ? `${baseSymbolFor(source)}@FORM_${sourceFormIndex}` : baseSymbolFor(source);
      return { directiveIdentity: canonical([sourceIdentity, edge.method, String(edge.parameter ?? ""), edge.targetSymbol, edge.targetFormIndex ?? null]), sourceIdentity, source, edge };
    };
    const comparisonBases = new Set([...saved, ...projected.members]);
    let comparisonExpanded = true;
    while (comparisonExpanded) {
      comparisonExpanded = false;
      [...comparisonBases].forEach((symbol) => {
        const record = model.species.find((candidate) => candidate.__symbol === symbol && !candidate.__isForm);
        if (!record) return;
        [...asArray(record.evolutionFamily?.baseSymbols), ...projectedFamilyFor(record).members].forEach((member) => {
          if (comparisonBases.has(member)) return;
          comparisonBases.add(member);
          comparisonExpanded = true;
        });
      });
    }
    const comparisonSources = model.species.filter((candidate) => comparisonBases.has(baseSymbolFor(candidate)));
    const savedRelationshipRows = comparisonSources.flatMap((source) => asArray(firstDefined(source.evolutions, source.evolution?.edges, [])).map(normalizeEvolutionEdge).filter((edge) => edge.targetSymbol).map((edge) => relationship(source, edge)));
    const projectedRelationshipRows = comparisonSources.flatMap((source) => projectedEdgesFor(source).filter((edge) => edge.targetSymbol).map((edge) => relationship(source, edge)));
    const indexRelationships = (rows) => {
      const occurrences = new Map();
      return new Map(rows.map((row) => {
        const occurrence = occurrences.get(row.directiveIdentity) || 0;
        occurrences.set(row.directiveIdentity, occurrence + 1);
        return [`${row.directiveIdentity}#${occurrence}`, row];
      }));
    };
    const savedRelationships = indexRelationships(savedRelationshipRows);
    const projectedRelationships = indexRelationships(projectedRelationshipRows);
    const relationshipRows = [...new Set([...savedRelationships.keys(), ...projectedRelationships.keys()])].map((key) => ({ ...(projectedRelationships.get(key) || savedRelationships.get(key)), state: !savedRelationships.has(key) ? "is-added" : !projectedRelationships.has(key) ? "is-removed" : "" }));
    const relationshipHtml = relationshipRows.map((row) => {
      const targetLabel = evolutionTargetPresentation(species, row.edge).label;
      const rawTarget = row.edge.targetFormIndex !== undefined ? `${row.edge.targetSymbol}@FORM_${row.edge.targetFormIndex}` : row.edge.targetSymbol;
      const method = evolutionMethodOptions().find((option) => enumOptionValue(option) === row.edge.method);
      const parameterKind = evolutionParameterKind(row.edge.method);
      const condition = ["zero", "fixed"].includes(parameterKind) ? "" : ` · ${humanize(row.edge.parameter)}`;
      return `<li class="${row.state}"><strong>${escapeHtml(effectiveName(row.source))} → ${escapeHtml(targetLabel)}</strong><small>${escapeHtml(method ? optionLabel(method) : humanize(row.edge.method))}${escapeHtml(condition)}</small><code>${escapeHtml(row.sourceIdentity)} · ${escapeHtml(row.edge.method)}(${escapeHtml(row.edge.parameter)}) → ${escapeHtml(rawTarget)}</code></li>`;
    }).join("");
    return `<section class="pv2-pokemon-family-overview" aria-label="Evolution family overview"><span><small>Projected family overview</small><strong>${members.length} base member${members.length === 1 ? "" : "s"} · ${projected.roots.length} root${projected.roots.length === 1 ? "" : "s"}</strong></span><ul>${members.map((member) => `<li class="${saved.has(member.__symbol) ? "" : "is-added"}"><button type="button" data-family-evolution-select="${escapeHtml(member.__key)}">${renderSprite(member)}<span>${escapeHtml(effectiveName(member))}</span></button></li>`).join("")}${removed.map((member) => `<li class="is-removed"><button type="button" data-family-evolution-select="${escapeHtml(member.__key)}">${renderSprite(member)}<span>${escapeHtml(effectiveName(member))}</span></button></li>`).join("")}</ul><ol class="pv2-pokemon-family-relationships">${relationshipHtml}</ol></section>${renderFamilyStageSummary(species)}`;
  }

  function renderFamilyStageSummary(species) {
    const summary = familyStageSummaries.get(species.__symbol) || [...familyStageSummaries.values()].find((candidate) => candidate.members.includes(baseSymbolFor(species)));
    if (!summary || (!summary.affected.length && !summary.blocked.length && !summary.invalidRootCounts?.length)) return "";
    const familyError = Boolean(summary.blocked.length || summary.invalidRootCounts?.length);
    return `<div class="pv2-pokemon-family-stage-summary${familyError ? " is-invalid" : ""}" data-evolution-family-summary tabindex="-1" aria-invalid="${familyError}"><strong>${summary.affected.length} baby mapping${summary.affected.length === 1 ? "" : "s"} staged across this family</strong>${summary.affected.length ? `<small>${summary.affected.map(humanize).join(", ")}</small>` : ""}${summary.invalidRootCounts?.length ? `<p>Every projected family component must have exactly one root.</p>` : ""}${summary.blocked.length ? `<p>${summary.blocked.length} required mapping${summary.blocked.length === 1 ? " is" : "s are"} blocked: ${escapeHtml(summary.blocked.map((entry) => `${humanize(entry.symbol)} — ${entry.reason}`).join("; "))}</p>` : ""}</div>`;
  }

  function renderEvolutionEditor(species) {
    const detail = editorDetailFor(species);
    if (!detail || detail.status === "loading") return `<section class="pv2-pokemon-domain pv2-pokemon-domain--editor"><div class="pv2-pokemon-loading"><span aria-hidden="true"></span><strong>Loading evolution editor contract…</strong></div></section>`;
    if (detail.status === "error") return `<section class="pv2-pokemon-domain pv2-pokemon-domain--editor"><div class="pv2-pokemon-empty is-error"><strong>Evolution detail unavailable</strong><span>${escapeHtml(detail.error)}</span><button type="button" data-move-retry>Retry</button></div></section>`;
    const value = evolutionValueFor(species);
    const writable = edgeWritable(species);
    const canEditBaby = babyWritable(species);
    const maximum = evolutionMaxSlots(species);
    const errors = evolutionValidationErrors().filter((error) => error.species.__symbol === species.__symbol);
    const baby = model.species.find((candidate) => candidate.__symbol === value.babySymbol);
    const familyBases = new Set([...projectedFamilyFor(species).members, ...asArray(species.evolutionFamily?.baseSymbols), ...asArray(familyStageSummaries.get(species.__symbol)?.members)]);
    const affectedEvolutionCount = [...evolutionDrafts.keys()].filter((symbol) => {
      const record = model.species.find((candidate) => candidate.__symbol === symbol);
      return record && familyBases.has(baseSymbolFor(record));
    }).length;
    return `<section class="pv2-pokemon-domain pv2-pokemon-evolution-editor"><header><div><span class="pv2-pokemon-eyebrow">Family graph editor</span><h3>Evolution</h3></div><div class="pv2-pokemon-domain-actions"><small>${affectedEvolutionCount ? `${affectedEvolutionCount} evolution record${affectedEvolutionCount === 1 ? "" : "s"} pending · Global Save` : `${value.edges.length}/${maximum} outgoing slots`}</small><button type="button" data-evolution-revert ${evolutionDrafts.has(species.__symbol) ? "" : "hidden"}>Revert domain</button></div></header>${!writable || !canEditBaby ? `<div class="pv2-pokemon-access-reasons">${!writable ? `<p><strong>Evolution edges are read-only.</strong> ${escapeHtml(species.evolutionAccess?.reason || "No writable evolution block.")}</p>` : ""}${!canEditBaby ? `<p><strong>Baby mapping is read-only.</strong> ${escapeHtml(species.babyAccess?.reason || "No writable baby row.")}</p>` : ""}</div>` : ""}${renderEvolutionFamilyOverview(species)}<section class="pv2-pokemon-baby-composite" role="group" aria-label="Baby species"><div class="pv2-pokemon-evolution-node">${baby ? renderSprite(baby) : "◇"}<span><small>Family baby</small><strong>${escapeHtml(baby ? effectiveName(baby) : humanize(value.babySymbol))}</strong></span></div><label><span>Baby species</span>${evolutionSpeciesInput("baby", value.babySymbol, 0, canEditBaby)}</label></section><div class="pv2-pokemon-evolution-edges">${value.edges.map((edge, index) => {
      const targetDisplaySymbol = edgeTargetDisplaySymbol(edge);
      const targetPresentation = evolutionTargetPresentation(species, edge);
      const target = targetPresentation.record;
      const edgeErrors = errors.filter((error) => error.path.startsWith(`evolution.edges.${index}`));
      const errorId = `pv2-evolution-error-${species.__symbol}-${index}`.replace(/[^a-zA-Z0-9_-]/g, "-");
      const methodError = edgeErrors.find((error) => error.path.endsWith(".method"));
      const parameterError = edgeErrors.find((error) => error.path.endsWith(".parameter"));
      const targetError = edgeErrors.find((error) => error.path.endsWith(".targetSymbol"));
      const methodErrorId = `${errorId}-method`;
      const parameterErrorId = `${errorId}-parameter`;
      const targetErrorId = `${errorId}-target`;
      const edgeErrorIds = [methodError && methodErrorId, parameterError && parameterErrorId, targetError && targetErrorId].filter(Boolean).join(" ");
      const visibleErrors = [...new Set([methodError?.message, parameterError?.message, targetError?.message].filter(Boolean))].join(" · ");
      return `<article class="pv2-pokemon-evolution-edge${edgeErrors.length ? " is-invalid" : ""}" data-evolution-edge="${index}" tabindex="-1" aria-invalid="${Boolean(edgeErrors.length)}"${edgeErrorIds ? ` aria-describedby="${edgeErrorIds}"` : ""}><div class="pv2-pokemon-evolution-graph"><div class="pv2-pokemon-evolution-node">${renderSprite(species)}<strong>${escapeHtml(effectiveName(species))}</strong></div><span aria-hidden="true">→</span><div class="pv2-pokemon-evolution-node">${target ? renderSprite(target) : "◇"}<strong>${escapeHtml(targetPresentation.label)}</strong></div></div><div class="pv2-pokemon-evolution-fields"><label><span>Method</span>${evolutionMethodInput(edge, index, writable, methodErrorId, Boolean(methodError))}</label>${renderEvolutionParameter(edge, index, writable, parameterErrorId, Boolean(parameterError))}<label><span>Target species / form</span>${evolutionSpeciesInput("evolution-target", targetDisplaySymbol, index, writable, targetErrorId, Boolean(targetError), edgeTargetIdentity(edge))}</label></div><div class="pv2-pokemon-row-actions"><button type="button" data-evolution-up="${index}" ${!writable || index === 0 ? "disabled" : ""} aria-label="Move evolution ${index + 1} up">↑</button><button type="button" data-evolution-down="${index}" ${!writable || index === value.edges.length - 1 ? "disabled" : ""} aria-label="Move evolution ${index + 1} down">↓</button><button type="button" data-evolution-remove="${index}" ${writable ? "" : "disabled"}>Remove</button></div>${methodError ? `<p id="${methodErrorId}" class="sr-only" data-evolution-error-field="method">${escapeHtml(methodError.message)}</p>` : ""}${parameterError ? `<p id="${parameterErrorId}" class="sr-only" data-evolution-error-field="parameter">${escapeHtml(parameterError.message)}</p>` : ""}${targetError ? `<p id="${targetErrorId}" class="sr-only" data-evolution-error-field="target">${escapeHtml(targetError.message)}</p>` : ""}${visibleErrors ? `<p class="pv2-pokemon-row-error-copy" data-evolution-error-summary aria-hidden="true">${escapeHtml(visibleErrors)}</p>` : ""}</article>`;
    }).join("") || `<div class="pv2-pokemon-move-empty">This species has no outgoing evolutions.</div>`}</div>${errors.length ? `<div class="pv2-pokemon-structured-errors" role="alert">${errors.map((error) => `<p>${escapeHtml(error.message)}</p>`).join("")}</div>` : ""}<div class="pv2-pokemon-structured-footer"><button type="button" data-evolution-add ${!writable || value.edges.length >= maximum ? "disabled" : ""}>Add evolution</button><small>${value.edges.length}/${maximum} source slots used</small></div></section>`;
  }

  function renderFormsEditor(species) {
    const detail = editorDetailFor(species);
    if (!detail || detail.status === "loading") return `<section class="pv2-pokemon-domain pv2-pokemon-domain--editor"><div class="pv2-pokemon-loading"><span aria-hidden="true"></span><strong>Loading semantic form registry…</strong></div></section>`;
    if (detail.status === "error") return `<section class="pv2-pokemon-domain pv2-pokemon-domain--editor"><div class="pv2-pokemon-empty is-error"><strong>Form registry unavailable</strong><span>${escapeHtml(detail.error)}</span><button type="button" data-move-retry>Retry</button></div></section>`;
    const editor = formEditorFor(species);
    const value = formValueFor(species);
    const changed = formDrafts.has(editor.baseSymbol);
    const affected = formAffectedSymbols(species);
    const base = formBaseRecord(species);
    const canonicalBaseSelected = species.__symbol === editor.baseSymbol && !species.__isForm;
    const errors = formValidationErrors().filter((error) => error.species.__symbol === base.__symbol);
    const minimumIndex = Number(firstDefined(value.rules?.minFormIndex, 1));
    const maximumIndex = Number(firstDefined(value.rules?.maxFormIndex, 255));
    const indexOptions = Array.from({ length: Math.max(0, maximumIndex - minimumIndex + 1) }, (_, offset) => minimumIndex + offset);
    const writable = canonicalBaseSelected && value.forms.some((row) => formFieldWritable(value, row, "needsReversion"));
    const rows = value.forms.map((row, index) => {
      const rowErrors = errors.filter((error) => error.path.startsWith(`forms.rows.${index}.`));
      const indexError = rowErrors.find((error) => error.path.endsWith(".declaredFormIndex"));
      const symbolError = rowErrors.find((error) => error.path.endsWith(".symbol"));
      const errorId = `pv2-form-error-${editor.baseSymbol}-${index}`.replace(/[^a-zA-Z0-9_-]/g, "-");
      const indexWritable = formFieldWritable(value, row, "declaredFormIndex");
      const enabledWritable = formFieldWritable(value, row, "enabled");
      const reversionWritable = canonicalBaseSelected && formFieldWritable(value, row, "needsReversion");
      const aliases = asArray(row.aliases).map(valueLabel);
      const flags = isRecord(row.flags) ? Object.entries(row.flags).filter(([, enabled]) => enabled).map(([flag]) => humanize(flag)) : asArray(row.flags).map(valueLabel);
      const record = model.species.find((candidate) => candidate.__symbol === row.symbol);
      return `<article class="pv2-pokemon-form-row${rowErrors.length ? " is-invalid" : ""}" data-form-row="${index}" tabindex="-1" aria-invalid="${Boolean(rowErrors.length)}"${rowErrors.length ? ` aria-describedby="${errorId}"` : ""}><div class="pv2-pokemon-form-identity">${record ? renderSprite(record) : `<span class="pv2-pokemon-sprite pv2-pokemon-sprite--small is-empty" aria-hidden="true">◇</span>`}<span><small>Form identity</small><strong>${escapeHtml(row.label)}</strong><code>${escapeHtml(row.symbol)}</code></span></div><label><span>Declared index</span><select data-form-index="${index}" aria-invalid="${Boolean(indexError)}"${indexError ? ` aria-describedby="${errorId}"` : ""} ${indexWritable ? "" : "disabled"}>${indexOptions.map((option) => `<option value="${option}" ${Number(row.declaredFormIndex) === option ? "selected" : ""}>${option}</option>`).join("")}</select></label><div class="pv2-pokemon-form-switches"><label><input type="checkbox" data-form-enabled="${index}" ${row.enabled ? "checked" : ""} ${enabledWritable ? "" : "disabled"}><span>Enabled</span></label><label><input type="checkbox" data-form-reversion="${index}" ${row.needsReversion ? "checked" : ""} ${reversionWritable ? "" : "disabled"}><span>Needs reversion</span></label></div><div class="pv2-pokemon-form-metadata"><span>${row.adjustedRecord ? "Adjusted personal record" : "Logical alias"}</span>${flags.map((flag) => `<span>${escapeHtml(flag)}</span>`).join("")}${aliases.map((alias) => `<span>${escapeHtml(alias)}</span>`).join("") || `<span>No aliases</span>`}</div><div class="pv2-pokemon-row-actions"><button type="button" data-form-up="${index}" ${index <= 0 || !indexWritable || !formFieldWritable(value, value.forms[index - 1], "declaredFormIndex") ? "disabled" : ""} aria-label="Move ${escapeHtml(row.label)} earlier">↑</button><button type="button" data-form-down="${index}" ${index >= value.forms.length - 1 || !indexWritable || !formFieldWritable(value, value.forms[index + 1], "declaredFormIndex") ? "disabled" : ""} aria-label="Move ${escapeHtml(row.label)} later">↓</button>${record ? `<button type="button" data-form-select="${escapeHtml(record.__key)}">Open record</button>` : ""}</div>${rowErrors.length ? `<p id="${errorId}" class="pv2-pokemon-row-error-copy">${escapeHtml((indexError || symbolError || rowErrors[0]).message)}</p>` : ""}</article>`;
    }).join("");
    const reason = canonicalBaseSelected ? textValue(value.access?.reason, "This registry is reference-only.") : `Edit form metadata from the canonical base record ${editor.baseSymbol}.`;
    return `<section class="pv2-pokemon-domain pv2-pokemon-forms-editor"><header><div><span class="pv2-pokemon-eyebrow">Semantic family registry</span><h3>Forms</h3></div><div class="pv2-pokemon-domain-actions"><small>${changed ? `${affected.length} affected record${affected.length === 1 ? "" : "s"} · Global Save` : `${value.forms.length} declared form${value.forms.length === 1 ? "" : "s"}`}</small><button type="button" data-form-revert ${changed ? "" : "hidden"}>Revert domain</button></div></header><div class="pv2-pokemon-form-base">${renderSprite(base, "large")}<span><small>Canonical base identity</small><strong>${escapeHtml(effectiveName(base))}</strong><code>${escapeHtml(editor.baseSymbol)}</code></span><dl><div><dt>Declared forms</dt><dd>${value.forms.length}</dd></div><div><dt>Adjusted records</dt><dd>${value.forms.filter((row) => row.adjustedRecord).length}</dd></div><div><dt>Logical aliases</dt><dd>${value.forms.filter((row) => !row.adjustedRecord).length}</dd></div></dl></div>${!writable ? `<div class="pv2-pokemon-access-reasons"><p><strong>Form registry is read-only.</strong> ${escapeHtml(reason)}</p></div>` : ""}${affected.length ? `<div class="pv2-pokemon-family-stage-summary"><strong>${affected.length} form record${affected.length === 1 ? "" : "s"} affected</strong><small>${escapeHtml(affected.map(humanize).join(", "))}</small></div>` : ""}<div class="pv2-pokemon-form-list" role="list">${rows || `<div class="pv2-pokemon-empty"><strong>No alternate forms are declared.</strong><span>The canonical base identity remains visible above.</span></div>`}</div>${errors.length ? `<div class="pv2-pokemon-structured-errors" role="alert">${errors.map((error) => `<p>${escapeHtml(error.message)}</p>`).join("")}</div>` : ""}<p class="pv2-pokemon-save-note">Form symbols, aliases, source flags, and unsupported values remain visible. Only explicitly writable registry fields join Global Save.</p></section>`;
  }

  function renderAssetsEditor(species) {
    const detail = editorDetailFor(species);
    if (!detail || detail.status === "loading") return `<section class="pv2-pokemon-domain pv2-pokemon-domain--editor"><div class="pv2-pokemon-loading"><span aria-hidden="true"></span><strong>Loading visual asset manifest…</strong></div></section>`;
    if (detail.status === "error") return `<section class="pv2-pokemon-domain pv2-pokemon-domain--editor"><div class="pv2-pokemon-empty is-error"><strong>Asset manifest unavailable</strong><span>${escapeHtml(detail.error)}</span><button type="button" data-move-retry>Retry</button></div></section>`;
    const editor = assetEditorFor(species);
    const record = assetDrafts.get(species.__symbol);
    const errors = assetValidationErrors().filter((error) => error.species.__symbol === species.__symbol);
    const changed = Object.keys(record?.assets || {}).length;
    const cards = ASSET_SLOTS.map(([slot, fallbackLabel]) => {
      const source = editor.slots?.[slot] || {};
      const draft = assetDraftFor(species, slot);
      const rule = assetRuleFor(editor, slot);
      const writable = assetSlotWritable(editor, slot);
      const previewUrl = textValue(draft?.objectUrl, draft?.previewUrl, source.url, source.previewUrl);
      const label = textValue(source.label, fallbackLabel);
      const width = firstDefined(draft?.width, source.width);
      const height = firstDefined(draft?.height, source.height);
      const bytes = firstDefined(draft?.bytes, source.bytes);
      const draftState = assetDraftState(draft);
      const status = textValue(draftState?.status, source.status, previewUrl ? "available" : "missing");
      const error = errors.find((candidate) => candidate.path === `assets.${slot}`);
      const inputId = `pv2-asset-file-${species.__symbol}-${slot}`.replace(/[^a-zA-Z0-9_-]/g, "-");
      const accept = asArray(firstDefined(rule.allowedMimeTypes, ["image/png"])).join(",");
      const reason = textValue(source.access?.reason, editor.access?.reason, source.generated ? "Generated assets remain source-managed." : "This asset is reference-only.");
      const previewVisual = previewUrl
        ? slot === "follower"
          ? renderFollowerFrames(previewUrl, effectiveName(species))
          : `<img src="${escapeHtml(previewUrl)}" alt="${escapeHtml(effectiveName(species))} ${escapeHtml(label)} preview" decoding="async">`
        : `<span aria-hidden="true">◇</span><small>No preview</small>`;
      return `<article class="pv2-pokemon-asset-card${draft ? " is-changed" : ""}${error ? " is-invalid" : ""}" data-asset-card="${slot}" aria-invalid="${Boolean(error)}"><div class="pv2-pokemon-asset-preview${slot === "follower" ? " is-follower" : ""}${previewUrl ? "" : " is-empty"}" data-asset-drop-slot="${slot}" tabindex="${writable ? "0" : "-1"}" ${writable ? `role="button" aria-label="Drop or choose a replacement ${escapeHtml(label)} asset"` : ""}>${previewVisual}${draft ? `<b>Local preview</b>` : ""}</div><header><span><small>${escapeHtml(label)}</small><strong>${escapeHtml(status)}</strong></span><em class="is-${escapeHtml(status)}">${draft ? "Pending" : source.generated ? "Generated" : "Source"}</em></header><dl><div><dt>Dimensions</dt><dd>${width && height ? `${escapeHtml(width)}×${escapeHtml(height)} px` : "Not reported"}</dd></div><div><dt>Format</dt><dd>${escapeHtml(textValue(draft?.mimeType, source.mimeType, "Unknown"))}</dd></div><div><dt>Size</dt><dd>${Number(bytes) ? `${Math.ceil(Number(bytes) / 1024)} KB` : "Not reported"}</dd></div><div><dt>Provenance</dt><dd>${escapeHtml(textValue(source.provenance, source.generated ? "Generated" : "Source-managed"))}</dd></div></dl>${writable ? `<div class="pv2-pokemon-asset-actions"><label for="${inputId}">${draft ? "Replace file" : "Choose file"}</label><input class="sr-only" id="${inputId}" type="file" accept="${escapeHtml(accept)}" data-asset-file="${slot}"><button type="button" data-asset-revert="${slot}" ${draft ? "" : "hidden"}>Revert</button></div><small class="pv2-pokemon-asset-rule">${escapeHtml([accept || "Image", Number(firstDefined(rule.maxBytes)) ? `≤ ${Math.round(Number(rule.maxBytes) / 1024)} KB` : "", firstDefined(rule.width) && firstDefined(rule.height) ? `${rule.width}×${rule.height} px` : ""].filter(Boolean).join(" · "))}</small>` : `<p class="pv2-pokemon-asset-reason"><strong>Read-only.</strong> ${escapeHtml(reason)}</p>`}${draft ? `<p class="pv2-pokemon-asset-status" aria-live="polite">${draft.status === "error" ? escapeHtml(draft.error) : draft.status === "ready" ? "Validated and staged for Global Save." : draft.status === "staging" ? "Uploading to the revision-scoped staging area…" : "Validating file type, size, and dimensions…"}</p>` : ""}</article>`;
    }).join("");
    return `<section class="pv2-pokemon-domain pv2-pokemon-assets-editor"><header><div><span class="pv2-pokemon-eyebrow">Visual asset studio</span><h3>Assets</h3></div><div class="pv2-pokemon-domain-actions"><small>${changed ? `${changed} replacement${changed === 1 ? "" : "s"} pending · Global Save` : "Source manifest"}</small><button type="button" data-assets-revert ${changed ? "" : "hidden"}>Revert all</button></div></header><p class="pv2-pokemon-domain-intro">Preview battle, menu, and overworld follower assets without exposing source paths. Writable slots accept revision-scoped staged replacements.</p><div class="pv2-pokemon-asset-grid">${cards}</div>${errors.length ? `<div class="pv2-pokemon-structured-errors" role="alert">${errors.map((error) => `<p>${escapeHtml(error.message)}</p>`).join("")}</div>` : ""}</section>`;
  }

  function refreshEditorDerived(species) {
    const errorByPath = new Map(speciesValidationErrors(species).map((error) => [error.path, error.message]));
    const aggregateEvError = speciesGroupValidationErrors(species).find((error) => error.group === "ev");
    const changeCountElement = inspectorElement.querySelector("[data-editor-change-count]");
    if (changeCountElement) {
      const count = descriptorsFor(activeDomain(species)).filter((descriptor) => fieldChanged(species, descriptor)).length;
      changeCountElement.textContent = domainWritable(activeDomain(species), species) ? `${count} changed · Global Save` : "Reference-only for this record";
      const domainRevert = inspectorElement.querySelector("[data-pokemon-revert-domain]");
      if (domainRevert) domainRevert.hidden = !count;
    }
    const preview = inspectorElement.querySelector("[data-entry-preview]");
    if (preview) preview.innerHTML = renderEntryPreview(species);
    const metrics = inspectorElement.querySelector("[data-battle-metrics]");
    if (metrics) metrics.innerHTML = renderBattleMetrics(species);
    const growthMetrics = inspectorElement.querySelector("[data-growth-metrics]");
    if (growthMetrics) growthMetrics.innerHTML = renderGrowthMetrics(species);
    descriptorsFor(activeDomain(species)).forEach((descriptor) => {
      const shell = inspectorElement.querySelector(`[data-pokemon-field-shell="${CSS.escape(descriptor.path)}"]`);
      if (!shell) return;
      const changed = fieldChanged(species, descriptor);
      const validation = changed ? (errorByPath.get(descriptor.path) || fieldError(species, descriptor)) : "";
      const aggregateInvalid = /evyield|ev_yield/i.test(descriptor.path) && Boolean(aggregateEvError);
      const aggregateErrorId = aggregateInvalid ? inspectorElement.querySelector('[data-editor-group="ev"] [data-group-error]')?.id : "";
      shell.classList.toggle("is-changed", changed);
      shell.classList.toggle("is-invalid", Boolean(validation));
      shell.classList.toggle("is-aggregate-invalid", Boolean(aggregateInvalid));
      const control = shell.querySelector("[data-pokemon-field], [data-pokemon-combobox]");
      control?.setAttribute("aria-invalid", String(Boolean(validation || aggregateInvalid)));
      const error = shell.querySelector(".pv2-pokemon-field-error");
      if (error) {
        error.textContent = validation;
        error.hidden = !validation;
        const descriptions = [shell.querySelector(".pv2-pokemon-field-help")?.id, shell.querySelector("[data-field-counter]")?.id, validation ? error.id : "", aggregateErrorId].filter(Boolean);
        if (descriptions.length) control?.setAttribute("aria-describedby", descriptions.join(" "));
        else control?.removeAttribute("aria-describedby");
      }
      if (control?.type === "checkbox") shell.querySelector(".pv2-pokemon-switch span").textContent = control.checked ? "Yes" : "No";
      const revert = shell.querySelector("[data-pokemon-revert-field]");
      if (revert) revert.hidden = !changed;
      const counter = shell.querySelector("[data-field-counter]");
      if (counter) counter.textContent = fieldCounter(descriptor, fieldValue(species, descriptor), species);
      if (control?.matches("[data-pokemon-combobox]")) {
        const symbol = fieldValue(species, descriptor);
        control.dataset.pokemonComboboxSymbol = String(symbol ?? "");
        control.value = enumLabelFor(descriptor, symbol);
      }
    });
    editorGroups(activeDomain(species), descriptorsFor(activeDomain(species))).forEach((group) => {
      const groupElement = inspectorElement.querySelector(`[data-editor-group="${CSS.escape(group.key)}"]`);
      if (!groupElement) return;
      const changed = group.fields.filter((descriptor) => fieldChanged(species, descriptor)).length;
      const fieldErrors = speciesValidationErrors(species).filter((error) => group.fields.some((descriptor) => descriptor.path === error.path));
      const compositeErrors = speciesGroupValidationErrors(species).filter((error) => error.group === group.key);
      const errorCount = fieldErrors.length + compositeErrors.length;
      groupElement.classList.toggle("is-changed", changed > 0);
      groupElement.classList.toggle("is-invalid", errorCount > 0);
      const stateElement = groupElement.querySelector("[data-group-state]");
      if (stateElement) stateElement.textContent = [changed ? `${changed} changed` : "", errorCount ? `${errorCount} error${errorCount === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ");
      const revert = groupElement.querySelector("[data-pokemon-revert-group]");
      if (revert) revert.hidden = !changed;
      const groupError = groupElement.querySelector("[data-group-error]");
      if (groupError) {
        groupError.textContent = compositeErrors[0]?.message || "";
        groupError.hidden = !compositeErrors.length;
      }
      groupElement.setAttribute("aria-invalid", String(Boolean(errorCount)));
      if (compositeErrors.length && groupError?.id) groupElement.setAttribute("aria-describedby", groupError.id);
      else groupElement.removeAttribute("aria-describedby");
    });
    const identity = inspectorElement.querySelector(".pv2-pokemon-identity");
    if (identity) identity.outerHTML = renderIdentity(species);
    const bannerMarkup = renderInspectorDraftBanner(species);
    const banner = inspectorElement.querySelector(".pv2-pokemon-draft-banner");
    if (bannerMarkup && banner) banner.outerHTML = bannerMarkup;
    else if (bannerMarkup && !banner) inspectorElement.querySelector(".pv2-pokemon-identity")?.insertAdjacentHTML("afterend", bannerMarkup);
    else banner?.remove();
    inspectorElement.querySelectorAll("[data-pokemon-tab]").forEach((tab) => {
      const domain = tab.dataset.pokemonTab;
      tab.innerHTML = renderTabContent(species, domain, DOMAIN_TABS.find(([key]) => key === domain)?.[1] || humanize(domain));
    });
    const sectionSelect = inspectorElement.querySelector("[data-pokemon-section-select]");
    if (sectionSelect) [...sectionSelect.options].forEach((option) => {
      const label = DOMAIN_TABS.find(([key]) => key === option.value)?.[1] || humanize(option.value);
      option.textContent = sectionOptionLabel(species, option.value, label);
    });
  }

  function renderTabContent(species, domain, label) {
    const stateCopy = domainState(species, domain);
    return `<span>${escapeHtml(label)}</span>${stateCopy.changed ? `<b class="pv2-pokemon-tab-change" aria-label="${stateCopy.changed} changed">${stateCopy.changed}</b>` : ""}${stateCopy.errors ? `<b class="pv2-pokemon-tab-error" aria-label="${stateCopy.errors} validation errors">${stateCopy.errors}</b>` : ""}`;
  }

  function sectionOptionLabel(species, domain, label) {
    const stateCopy = domainState(species, domain);
    const suffix = [stateCopy.changed ? `${stateCopy.changed} changed` : "", stateCopy.errors ? `${stateCopy.errors} errors` : ""].filter(Boolean).join(", ");
    return suffix ? `${label} — ${suffix}` : label;
  }

  function renderInspectorDraftBanner(species) {
    const totalChanges = changeCount();
    if (!totalChanges) return "";
    const invalid = validationErrors();
    const busy = assetBusyIssues();
    const currentChanges = (draftMapFor(species)?.size || 0) + (learnsetDrafts.has(species.__symbol) ? 1 : 0) + (evolutionDrafts.has(species.__symbol) ? 1 : 0) + (formDrafts.has(baseSymbolFor(species)) ? formAffectedSymbols(species).length : 0) + Object.keys(assetDrafts.get(species.__symbol)?.assets || {}).length;
    return `<aside class="pv2-pokemon-draft-banner${invalid.length ? " is-invalid" : busy.length ? " is-busy" : ""}" aria-label="Pokémon draft status"><span><strong>${totalChanges} pending Pokémon change${totalChanges === 1 ? "" : "s"}</strong><small>${currentChanges ? `${currentChanges} pending on this record` : "This record is unchanged"}</small></span>${invalid.length ? `<button type="button" data-pokemon-first-invalid><strong>${invalid.length} invalid</strong><small>Go to first invalid field</small></button>` : busy.length ? `<em>${busy.length} asset stage${busy.length === 1 ? "" : "s"} in progress · Save blocked</em>` : `<em>Ready for global Save</em>`}</aside>`;
  }

  function renderInspector() {
    closeCombobox();
    const species = selectedSpecies();
    if (!species) {
      inspectorElement.innerHTML = `<div class="pv2-pokemon-empty pv2-pokemon-empty--center"><span aria-hidden="true">◇</span><strong>Select a Pokémon</strong><small>Choose a full row from the index to inspect its source-backed record.</small></div>`;
      return;
    }
    const active = activeDomain(species);
    const domainMarkup = active === "moves"
      ? renderMovesEditor(species)
      : active === "evolution"
        ? renderEvolutionEditor(species)
        : active === "forms"
          ? renderFormsEditor(species)
          : active === "assets"
            ? renderAssetsEditor(species)
        : model.writeDomains.includes(active) && descriptorsFor(active).length
          ? renderWritableDomain(species, active)
          : ["entry", "battle"].includes(active)
            ? renderReadOnlyDomain(species, active)
            : renderFoundationDomain(species, active);
    inspectorElement.innerHTML = `${renderIdentity(species)}
      ${renderInspectorDraftBanner(species)}
      <div class="pv2-pokemon-tabs" role="tablist" aria-label="Pokémon data domains">
        ${DOMAIN_TABS.map(([key, label]) => `<button type="button" role="tab" id="pv2-pokemon-tab-${key}" aria-controls="pv2-pokemon-panel-${key}" aria-selected="${key === active}" tabindex="${key === active ? "0" : "-1"}" data-pokemon-tab="${key}">${renderTabContent(species, key, label)}</button>`).join("")}
      </div>
      <label class="pv2-pokemon-section-select"><span>Data section</span><select data-pokemon-section-select>${DOMAIN_TABS.map(([key, label]) => `<option value="${key}" ${key === active ? "selected" : ""}>${escapeHtml(sectionOptionLabel(species, key, label))}</option>`).join("")}</select></label>
      <section class="pv2-pokemon-tabpanel" id="pv2-pokemon-panel-${active}" role="tabpanel" aria-labelledby="pv2-pokemon-tab-${active}">
        ${domainMarkup}
      </section>
      ${renderTechnical(species)}`;
    const renderedFormValue = active === "forms" ? formValueFor(species) : null;
    if (renderedFormValue && (species.__isForm || species.__symbol !== renderedFormValue.baseSymbol)) {
      inspectorElement.querySelector("[data-form-revert]")?.remove();
      inspectorElement.querySelectorAll("[data-form-select]").forEach((control) => control.remove());
      const action = document.createElement("button");
      action.type = "button";
      action.dataset.formOpenBase = renderedFormValue.baseSymbol;
      action.textContent = "Open canonical base to edit";
      inspectorElement.querySelector(".pv2-pokemon-access-reasons")?.append(action);
    }
    if (renderedFormValue && asArray(renderedFormValue.aliases).length) {
      const aliases = document.createElement("section");
      aliases.className = "pv2-pokemon-form-aliases";
      const heading = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = "Logical runtime aliases";
      const count = document.createElement("small");
      count.textContent = `${renderedFormValue.aliases.length} read-only alias${renderedFormValue.aliases.length === 1 ? "" : "es"}`;
      heading.append(title, count);
      const list = document.createElement("ul");
      asArray(renderedFormValue.aliases).forEach((alias) => {
        const item = document.createElement("li");
        const label = document.createElement("strong");
        label.textContent = textValue(alias.label, humanize(alias.identity));
        const identity = document.createElement("code");
        identity.textContent = textValue(alias.identity, `${alias.baseSymbol}@FORM_${alias.formIndex}`);
        const reason = document.createElement("small");
        reason.textContent = textValue(alias.access?.reason, "Logical runtime aliases are read-only and are not form registry rows.");
        item.append(label, identity, reason);
        list.append(item);
      });
      aliases.append(heading, list);
      inspectorElement.querySelector(".pv2-pokemon-form-base")?.after(aliases);
    }
    inspectorElement.querySelectorAll(".pv2-pokemon-form-row").forEach((row) => {
      row.setAttribute("role", "listitem");
      const form = renderedFormValue?.forms?.[Number(row.dataset.formRow)];
      if (!form) return;
      row.querySelectorAll("[data-form-up], [data-form-down]").forEach((control) => control.remove());
      const indexControl = row.querySelector("[data-form-index]");
      if (indexControl) {
        const label = indexControl.closest("label");
        const metadata = document.createElement("div");
        metadata.className = "pv2-pokemon-form-index-metadata";
        const caption = document.createElement("small");
        caption.textContent = "Runtime form index";
        const value = document.createElement("strong");
        value.textContent = String(form.declaredFormIndex);
        const reason = document.createElement("span");
        reason.textContent = textValue(form.access?.declaredFormIndex?.reason, "Runtime form indexes are referenced cross-record; registry ordering is preserved.");
        metadata.append(caption, value, reason);
        label?.replaceWith(metadata);
      }
      const reasons = [...new Set(["enabled", "needsReversion"].filter((field) => !formFieldWritable(renderedFormValue, form, field)).map((field) => textValue(form.access?.[field]?.reason, renderedFormValue.access?.fields?.[field]?.reason)).filter(Boolean))];
      const reversion = row.querySelector(`[data-form-reversion="${row.dataset.formRow}"]`);
      if (reversion) {
        const label = reversion.closest("label");
        const copy = label?.querySelector("span");
        if (copy) copy.textContent = "Revert after battle";
        const help = document.createElement("small");
        help.className = "pv2-pokemon-form-reversion-help";
        help.textContent = "When enabled, this temporary battle form returns to its mapped normal or base form when battle ends.";
        label?.append(help);
      }
      if (reasons.length) {
        const note = document.createElement("span");
        note.textContent = `Read-only: ${reasons.join("; ")}`;
        note.title = reasons.join("; ");
        row.querySelector(".pv2-pokemon-form-metadata")?.append(note);
      }
    });
    const formSummary = renderedFormValue ? inspectorElement.querySelector(".pv2-pokemon-forms-editor .pv2-pokemon-family-stage-summary") : null;
    const formDraft = renderedFormValue ? formDrafts.get(renderedFormValue.baseSymbol) : null;
    if (formSummary && formDraft) {
      const source = new Map(asArray(formDraft.sourceSnapshot?.forms).map((row) => [row.symbol, row]));
      const affected = formDraft.forms.filter((row) => Boolean(source.get(row.symbol)?.needsReversion) !== Boolean(row.needsReversion));
      const heading = document.createElement("strong");
      heading.textContent = `${affected.length} form record${affected.length === 1 ? "" : "s"} affected`;
      const list = document.createElement("ul");
      affected.forEach((row) => {
        const item = document.createElement("li");
        item.textContent = `${row.label}: Revert after battle ${source.get(row.symbol)?.needsReversion ? "On" : "Off"} → ${row.needsReversion ? "On" : "Off"}`;
        list.append(item);
      });
      formSummary.replaceChildren(heading, list);
    }
    inspectorElement.querySelectorAll(".pv2-pokemon-asset-card.is-invalid").forEach((card) => {
      const status = card.querySelector(".pv2-pokemon-asset-status");
      if (!status) return;
      status.id = `pv2-asset-error-${species.__symbol}-${card.dataset.assetCard}`.replace(/[^a-zA-Z0-9_-]/g, "-");
      card.setAttribute("aria-describedby", status.id);
      card.querySelector("[data-asset-drop-slot]")?.setAttribute("aria-describedby", status.id);
    });
    const renderedAssetEditor = active === "assets" ? assetEditorFor(species) : null;
    if (renderedAssetEditor) inspectorElement.querySelectorAll(".pv2-pokemon-asset-card").forEach((card) => {
      const slot = card.dataset.assetCard;
      const entry = assetDraftFor(species, slot);
      const computed = assetDraftState(entry);
      const source = renderedAssetEditor.slots?.[slot] || {};
      const provenance = card.querySelector("dl div:last-child dd");
      if (provenance) provenance.textContent = assetProvenanceLabel(source);
      const diagnostic = document.createElement("p");
      diagnostic.className = "pv2-pokemon-asset-diagnostic";
      diagnostic.textContent = assetSourceDiagnostic(renderedAssetEditor, slot);
      if (source.status === "invalid-source") {
        diagnostic.id = `pv2-asset-source-error-${species.__symbol}-${slot}`.replace(/[^a-zA-Z0-9_-]/g, "-");
        diagnostic.setAttribute("role", "alert");
        card.classList.add("is-source-invalid");
        card.setAttribute("aria-invalid", "true");
        card.setAttribute("aria-describedby", diagnostic.id);
      }
      card.append(diagnostic);
      if (!computed) return;
      const statusCopy = card.querySelector("header strong");
      if (statusCopy) statusCopy.textContent = computed.status;
      const badge = card.querySelector("header em");
      if (badge) {
        badge.className = `is-${computed.status}`;
        badge.textContent = computed.invalid ? "Action required" : "Pending";
      }
      if (computed.busy) {
        card.classList.add("is-busy");
        const input = card.querySelector("[data-asset-file]");
        if (input) input.disabled = true;
        const drop = card.querySelector("[data-asset-drop-slot]");
        drop?.removeAttribute("role");
        drop?.setAttribute("tabindex", "-1");
        drop?.setAttribute("aria-disabled", "true");
        card.querySelector(".pv2-pokemon-asset-actions label")?.setAttribute("aria-disabled", "true");
      }
      const live = card.querySelector(".pv2-pokemon-asset-status");
      if (live) live.textContent = computed.message;
      const preview = card.querySelector(".pv2-pokemon-asset-preview");
      if (preview) {
        const compare = document.createElement("div");
        compare.className = "pv2-pokemon-asset-compare";
        const comparison = (title, url, metadata, pending = false) => {
          const figure = document.createElement("figure");
          if (pending) figure.className = "is-pending";
          const caption = document.createElement("figcaption");
          caption.textContent = title;
          if (url) {
            const image = document.createElement("img");
            image.src = url;
            image.alt = `${effectiveName(species)} ${title.toLowerCase()}`;
            image.decoding = "async";
            figure.append(image);
          } else {
            const empty = document.createElement("span");
            empty.textContent = "No source preview";
            figure.append(empty);
          }
          const details = document.createElement("small");
          details.textContent = metadata;
          figure.prepend(caption);
          figure.append(details);
          return figure;
        };
        const sourceFileName = textValue(source.fileName, textValue(source.source).split(/[\\/]/).at(-1), "Source asset");
        const sourceMeta = [sourceFileName, source.width && source.height ? `${source.width}×${source.height} px` : "Dimensions not reported", Number(source.bytes) ? `${Math.ceil(Number(source.bytes) / 1024)} KB` : "Size not reported"].join(" · ");
        const pendingMeta = [entry.fileName || "Selected file", entry.width && entry.height ? `${entry.width}×${entry.height} px` : "Checking dimensions", Number(entry.bytes) ? `${Math.ceil(Number(entry.bytes) / 1024)} KB` : "Size not reported"].join(" · ");
        compare.append(comparison("Current source", textValue(source.url, source.previewUrl), sourceMeta), comparison("Pending replacement", textValue(entry.objectUrl, entry.previewUrl), pendingMeta, true));
        preview.replaceChildren(compare);
        preview.classList.add("has-comparison");
        card.classList.add("has-comparison");
      }
      const boundary = document.createElement("p");
      boundary.className = "pv2-pokemon-asset-stage-boundary";
      boundary.textContent = computed.busy ? "Local staging in progress — Global Save remains blocked." : computed.invalid ? "Local draft only — fix or reselect before Global Save." : "Staged only — Global Save writes source.";
      card.append(boundary);
      if (computed.invalid && entry.file) {
        const retry = document.createElement("button");
        retry.type = "button";
        retry.dataset.assetRetry = slot;
        retry.textContent = "Retry staging";
        card.querySelector(".pv2-pokemon-asset-actions")?.append(retry);
      }
    });
    if (!editorDetailFor(species)) queueMicrotask(() => ensureLearnsetDetail(species));
  }

  function ensureSelection() {
    const selected = model.species.find((species) => species.__key === ui.selectedKey);
    if (!selected || (selected.__isReserved && !ui.search)) {
      ui.selectedKey = model.species.find((species) => !species.__isReserved)?.__key || "";
    }
    state.selectedPokemonKey = ui.selectedKey;
    if (ui.selectedKey) writeStorage(STORAGE_SELECTION_KEY, ui.selectedKey);
  }

  function renderAll() {
    if (ui.destroyed) return;
    ensureSelection();
    root.classList.toggle("has-pokemon-selection", Boolean(ui.selectedKey));
    renderFilterControls();
    renderLibrary({ announce: Boolean(model.species.length) });
    renderInspector();
  }

  function selectSpecies(key, { focus = false } = {}) {
    if (!model.species.some((species) => species.__key === key)) return;
    ui.selectedKey = key;
    ui.rovingKey = key;
    state.selectedPokemonKey = key;
    writeStorage(STORAGE_SELECTION_KEY, key);
    updateMobileLibraryToolbar();
    const wasMobileLibraryOpen = root.classList.contains("is-mobile-library-open");
    root.classList.remove("is-mobile-library-open");
    renderLibraryWindow({ focusKey: focus ? key : "" });
    renderInspector();
    if ((wasMobileLibraryOpen || !focus) && globalThis.matchMedia?.("(max-width: 820px)").matches) {
      requestAnimationFrame(() => inspectorElement.querySelector("[data-pokemon-library-toggle]")?.focus({ preventScroll: true }));
    }
  }

  function openRecord(symbol, origin = {}) {
    const species = model.species.find((candidate) => candidate.__symbol === symbol || candidate.__key === symbol);
    if (!species) return false;
    const options = isRecord(origin) ? origin : { origin };
    selectSpecies(species.__key, { focus: true });
    scrollCurrentIntoView();
    if (options.focus !== false) requestAnimationFrame(() => {
      const panel = inspectorElement.querySelector(".pv2-pokemon-tabpanel");
      if (!panel) return;
      panel.tabIndex = -1;
      panel.focus({ preventScroll: true });
    });
    return true;
  }

  function navigationContext() {
    const species = selectedSpecies();
    return { selection: species?.__symbol || "", label: species ? effectiveName(species) : "" };
  }

  function selectDomain(key, { focus = false } = {}) {
    const species = selectedSpecies();
    if (!species || !DOMAIN_TABS.some(([tabKey]) => tabKey === key)) return;
    sectionBySpecies.set(species.__key, key);
    writeStorage(STORAGE_SECTIONS_KEY, Object.fromEntries(sectionBySpecies));
    renderInspector();
    if (focus) inspectorElement.querySelector(`[data-pokemon-tab="${CSS.escape(key)}"]`)?.focus({ preventScroll: true });
  }

  function navigateToFirstInvalid() {
    const first = validationErrors()[0];
    if (!first) return;
    ui.selectedKey = first.species.__key;
    ui.rovingKey = first.species.__key;
    state.selectedPokemonKey = first.species.__key;
    writeStorage(STORAGE_SELECTION_KEY, first.species.__key);
    const domain = first.path.split(".")[0];
    sectionBySpecies.set(first.species.__key, domain);
    const movePath = first.path.match(/^moves\.(levelMoves|machineMoves|tutorMoves|eggMoves)\.(\d+)\.(move|level)$/);
    if (movePath) {
      moveTabBySpecies.set(first.species.__symbol, movePath[1]);
      moveSearchBySpecies.set(first.species.__symbol, "");
      moveWindowBySpecies.set(`${first.species.__symbol}:${movePath[1]}`, Math.max(0, Number(movePath[2]) - 5));
    }
    writeStorage(STORAGE_SECTIONS_KEY, Object.fromEntries(sectionBySpecies));
    root.classList.remove("is-mobile-library-open");
    renderLibrary();
    renderInspector();
    requestAnimationFrame(() => {
      const aggregateGroup = first.path === "battle.evYields" ? inspectorElement.querySelector('[data-editor-group="ev"]') : null;
      const evolutionIndex = first.path.match(/^evolution\.edges\.(\d+)/)?.[1];
      const formIndex = first.path.match(/^forms\.rows\.(\d+)/)?.[1];
      const assetSlot = first.path.match(/^assets\.([^.]+)/)?.[1];
      const structured = movePath
        ? inspectorElement.querySelector(movePath[3] === "level" ? `[data-move-level="${movePath[2]}"]` : `[data-move-symbol="${movePath[2]}"]`)
        : first.path.startsWith("moves.") || first.path === "moves"
          ? inspectorElement.querySelector("[data-move-list]")
        : evolutionIndex !== undefined
          ? inspectorElement.querySelector(first.path.endsWith(".method") ? `[data-evolution-method="${evolutionIndex}"]` : first.path.endsWith(".parameter") ? `[data-evolution-parameter="${evolutionIndex}"]` : `[data-evolution-target="${evolutionIndex}"]`)
          : first.path === "evolution.babySymbol"
            ? inspectorElement.querySelector("[data-evolution-baby]")
            : first.path === "evolution.family"
              ? inspectorElement.querySelector("[data-evolution-family-summary]")
            : formIndex !== undefined
              ? inspectorElement.querySelector(first.path.endsWith(".declaredFormIndex") ? `[data-form-index="${formIndex}"]` : `[data-form-row="${formIndex}"]`)
            : first.path === "forms.family"
              ? inspectorElement.querySelector(".pv2-pokemon-form-list")
            : assetSlot
              ? inspectorElement.querySelector(`[data-asset-card="${CSS.escape(assetSlot)}"] [data-asset-drop-slot]`)
            : null;
      const field = aggregateGroup || structured ? null : inspectorElement.querySelector(`[data-pokemon-field="${CSS.escape(first.path)}"], [data-pokemon-combobox="${CSS.escape(first.path)}"]`);
      const target = aggregateGroup || structured || field;
      target?.focus?.({ preventScroll: true });
      target?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  }

  function focusFirstBlocking() {
    const first = assetBusyIssues()[0];
    if (!first) return;
    ui.selectedKey = first.species.__key;
    ui.rovingKey = first.species.__key;
    state.selectedPokemonKey = first.species.__key;
    sectionBySpecies.set(first.species.__key, "assets");
    writeStorage(STORAGE_SELECTION_KEY, first.species.__key);
    writeStorage(STORAGE_SECTIONS_KEY, Object.fromEntries(sectionBySpecies));
    renderLibrary();
    renderInspector();
    const slot = first.path.split(".")[1];
    requestAnimationFrame(() => inspectorElement.querySelector(`[data-asset-card="${CSS.escape(slot)}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" }));
  }

  function ensureRowVisible(index) {
    const listTop = libraryListOffset();
    const top = listTop + index * LIST_ROW_HEIGHT;
    const bottom = top + LIST_ROW_HEIGHT;
    const viewportTop = libraryElement.scrollTop;
    const viewportBottom = viewportTop + libraryElement.clientHeight;
    if (top < viewportTop + listTop) libraryElement.scrollTop = Math.max(0, top - listTop);
    else if (bottom > viewportBottom) libraryElement.scrollTop = bottom - libraryElement.clientHeight;
  }

  function focusBrowseControl() {
    requestAnimationFrame(() => inspectorElement.querySelector("[data-pokemon-library-toggle]")?.focus({ preventScroll: true }));
  }

  function scrollCurrentIntoView({ focus = false } = {}) {
    const index = ui.filtered.findIndex((species) => species.__key === ui.selectedKey);
    if (index < 0) return false;
    ui.rovingKey = ui.selectedKey;
    ensureRowVisible(index);
    renderLibraryWindow({ focusKey: focus ? ui.selectedKey : "" });
    return true;
  }

  function clearLibraryFilters() {
    ui.search = "";
    ui.pendingSearch = "";
    ui.type = "all";
    ui.scope = "all";
    writeStorage(STORAGE_SEARCH_KEY, "");
    writeStorage(STORAGE_TYPE_KEY, "all");
    writeStorage(STORAGE_SCOPE_KEY, "all");
    renderFilterControls();
    renderLibrary({ resetScroll: true, announce: true });
  }

  function applyFieldValue(species, descriptor, value) {
    setDraftField(species, descriptor, value);
    refreshEditorDerived(species);
    if (/(^|\.)name$|battle\.types\./i.test(descriptor.path)) renderLibrary();
    else renderLibraryWindow();
    signalDirty();
  }

  function refreshStructuredChrome(species) {
    refreshEditorDerived(species);
    renderLibraryWindow();
    signalDirty();
  }

  function setStructuredControlError(control, invalid, errorId) {
    if (!control) return;
    control.setAttribute("aria-invalid", String(Boolean(invalid)));
    if (invalid) control.setAttribute("aria-describedby", errorId);
    else control.removeAttribute("aria-describedby");
  }

  function syncStructuredFieldError(container, control, error, errorId, fieldAttribute, fieldName) {
    setStructuredControlError(control, Boolean(error), errorId);
    let copy = container.querySelector(`#${CSS.escape(errorId)}`);
    if (error) {
      if (!copy) {
        copy = document.createElement("p");
        copy.id = errorId;
        copy.className = "sr-only";
        copy.setAttribute(fieldAttribute, fieldName);
        container.append(copy);
      }
      copy.textContent = error.message;
    } else copy?.remove();
  }

  function syncVisibleErrorSummary(container, selector, errors) {
    const messages = [...new Set(errors.map((error) => error?.message).filter(Boolean))];
    let summary = container.querySelector(selector);
    if (messages.length) {
      if (!summary) {
        summary = document.createElement("p");
        summary.className = "pv2-pokemon-row-error-copy";
        summary.setAttribute(selector.slice(1, -1), "");
        summary.setAttribute("aria-hidden", "true");
        container.append(summary);
      }
      summary.textContent = messages.join(" · ");
    } else summary?.remove();
  }

  function syncMoveRowValidation(species, group, index, validation = learnsetValidationErrors()) {
    const row = inspectorElement.querySelector(`[data-move-list][data-move-group="${CSS.escape(group)}"] [data-move-row="${index}"]`);
    if (!row) return;
    const errors = validation.filter((error) => error.species.__symbol === species.__symbol && error.path.startsWith(`moves.${group}.${index}.`));
    const errorId = `pv2-move-error-${species.__symbol}-${group}-${index}`.replace(/[^a-zA-Z0-9_-]/g, "-");
    const levelError = errors.find((error) => error.path.endsWith(".level"));
    const moveError = errors.find((error) => error.path.endsWith(".move"));
    const levelErrorId = `${errorId}-level`;
    const moveErrorId = `${errorId}-move`;
    const rowErrorIds = [levelError && levelErrorId, moveError && moveErrorId].filter(Boolean).join(" ");
    row.classList.toggle("is-invalid", Boolean(errors.length));
    row.setAttribute("aria-invalid", String(Boolean(errors.length)));
    if (rowErrorIds) row.setAttribute("aria-describedby", rowErrorIds);
    else row.removeAttribute("aria-describedby");
    syncStructuredFieldError(row, row.querySelector(`[data-move-level="${index}"]`), levelError, levelErrorId, "data-move-error-field", "level");
    syncStructuredFieldError(row, row.querySelector(`[data-move-symbol="${index}"]`), moveError, moveErrorId, "data-move-error-field", "move");
    syncVisibleErrorSummary(row, "[data-move-error-summary]", [levelError, moveError]);
  }

  function syncEvolutionEdgeValidation(species, index, validation = evolutionValidationErrors()) {
    const edge = inspectorElement.querySelector(`[data-evolution-edge="${index}"]`);
    if (!edge) return;
    const errors = validation.filter((error) => error.species.__symbol === species.__symbol && error.path.startsWith(`evolution.edges.${index}.`));
    const errorId = `pv2-evolution-error-${species.__symbol}-${index}`.replace(/[^a-zA-Z0-9_-]/g, "-");
    const methodError = errors.find((error) => error.path.endsWith(".method"));
    const parameterError = errors.find((error) => error.path.endsWith(".parameter"));
    const targetError = errors.find((error) => error.path.endsWith(".targetSymbol"));
    const methodErrorId = `${errorId}-method`;
    const parameterErrorId = `${errorId}-parameter`;
    const targetErrorId = `${errorId}-target`;
    const edgeErrorIds = [methodError && methodErrorId, parameterError && parameterErrorId, targetError && targetErrorId].filter(Boolean).join(" ");
    edge.classList.toggle("is-invalid", Boolean(errors.length));
    edge.setAttribute("aria-invalid", String(Boolean(errors.length)));
    if (edgeErrorIds) edge.setAttribute("aria-describedby", edgeErrorIds);
    else edge.removeAttribute("aria-describedby");
    syncStructuredFieldError(edge, edge.querySelector(`[data-evolution-method="${index}"]`), methodError, methodErrorId, "data-evolution-error-field", "method");
    syncStructuredFieldError(edge, edge.querySelector(`[data-evolution-parameter="${index}"]`), parameterError, parameterErrorId, "data-evolution-error-field", "parameter");
    syncStructuredFieldError(edge, edge.querySelector(`[data-evolution-target="${index}"]`), targetError, targetErrorId, "data-evolution-error-field", "target");
    syncVisibleErrorSummary(edge, "[data-evolution-error-summary]", [methodError, parameterError, targetError]);
  }

  function syncRenderedMoveValidation(species, group = activeMoveGroup(species)) {
    const validation = learnsetValidationErrors();
    inspectorElement.querySelectorAll(`[data-move-list][data-move-group="${CSS.escape(group)}"] [data-move-row]`).forEach((row) => syncMoveRowValidation(species, group, Number(row.dataset.moveRow), validation));
  }

  function syncRenderedEvolutionValidation(species) {
    const validation = evolutionValidationErrors();
    inspectorElement.querySelectorAll("[data-evolution-edge]").forEach((edge) => syncEvolutionEdgeValidation(species, Number(edge.dataset.evolutionEdge), validation));
  }

  function refreshMoveList(species, scrollTop = 0) {
    const list = inspectorElement.querySelector("[data-move-list]");
    const value = learnsetValueFor(species);
    if (!list || !value) return;
    const group = activeMoveGroup(species);
    list.outerHTML = renderMoveWindow(species, group, asArray(value[group]));
    const replacement = inspectorElement.querySelector("[data-move-list]");
    if (replacement) replacement.scrollTop = scrollTop;
  }

  function mutateLearnset(species, callback, { rerender = true } = {}) {
    if (!learnsetRowsEditable(species) || !learnsetDetailFor(species)) return;
    const draft = ensureLearnsetDraft(species);
    callback(draft);
    const source = learnsetDetailFor(species);
    const sourceComparable = source ? { levelMoves: source.levelMoves.map((entry) => ({ ...entry, level: normalizeMoveLevel(entry.level) })), machineMoves: source.machineMoves, tutorMoves: source.tutorMoves, eggMoves: source.eggMoves } : null;
    const draftComparable = { levelMoves: draft.levelMoves.map((entry) => ({ ...entry, level: normalizeMoveLevel(entry.level) })), machineMoves: draft.machineMoves, tutorMoves: draft.tutorMoves, eggMoves: draft.eggMoves };
    if (source?.provenance === "explicit" && canonical(sourceComparable) === canonical(draftComparable)) learnsetDrafts.delete(species.__symbol);
    if (rerender) renderInspector();
    else {
      refreshStructuredChrome(species);
      syncRenderedMoveValidation(species);
    }
    signalDirty();
  }

  function moveLearnsetRow(species, group, index, offset) {
    const values = asArray(learnsetValueFor(species)?.[group]);
    const targetIndex = Math.max(0, Math.min(values.length - 1, index + offset));
    if (targetIndex === index) return false;
    mutateLearnset(species, (draft) => {
      const [row] = draft[group].splice(index, 1);
      draft[group].splice(targetIndex, 0, row);
    });
    requestAnimationFrame(() => inspectorElement.querySelector(`[data-move-row="${targetIndex}"]`)?.focus({ preventScroll: true }));
    setStatus(`Move row moved to position ${targetIndex + 1}.`, "info");
    return true;
  }

  function mutateEvolution(species, callback, { rerender = true, babyOnly = false } = {}) {
    if (!edgeWritable(species) && !babyWritable(species)) return;
    const draft = ensureEvolutionDraft(species);
    const topologyBefore = topologyTargetSignature(draft.edges);
    callback(draft);
    if (!babyOnly) draft.edgesTouched = true;
    const source = { edges: asArray(firstDefined(species.evolutions, species.evolution?.edges, [])).map(normalizeEvolutionEdge), babySymbol: sourceBabySymbol(species) };
    if (canonical(source.edges) === canonical(draft.edges)) draft.edgesTouched = false;
    if (draft.babySymbol === source.babySymbol) draft.babyTouched = false;
    if (!draft.edgesTouched && !draft.babyTouched) evolutionDrafts.delete(species.__symbol);
    const topologyChanged = !babyOnly && topologyBefore !== topologyTargetSignature(draft.edges);
    if (topologyChanged) {
      projectedFamilyGraphCache = null;
      recomputeFamilyStaging(species);
    }
    if (rerender) renderInspector();
    else {
      refreshStructuredChrome(species);
      syncRenderedEvolutionValidation(species);
    }
    signalDirty();
  }

  function mutateForms(species, callback, focusSelector = "") {
    const draft = ensureFormDraft(species);
    callback(draft);
    reconcileFormDraft(species);
    renderInspector();
    renderLibraryWindow();
    signalDirty();
    if (focusSelector) requestAnimationFrame(() => inspectorElement.querySelector(focusSelector)?.focus({ preventScroll: true }));
  }

  function revertAllAssets(species) {
    const record = assetDrafts.get(species.__symbol);
    if (!record) return;
    Object.values(record.assets).forEach((entry) => { discardAssetStage(entry); revokeAssetPreview(entry); });
    assetDrafts.delete(species.__symbol);
    renderInspector();
    renderLibraryWindow();
    signalDirty();
  }

  function editField(control) {
    const species = selectedSpecies();
    if (!species) return;
    const path = control.dataset.pokemonField;
    const descriptor = model.fieldRegistry.find((candidate) => candidate.path === path && candidate.domain === activeDomain(species));
    if (!descriptor || !domainWritable(descriptor.domain, species) || !recordFieldAccess(species, descriptor).writable) return;
    applyFieldValue(species, descriptor, control.type === "checkbox" ? control.checked : control.value);
  }

  function revertDescriptors(species, descriptors, focusPath = "", focusGroup = "") {
    const pending = draftMapFor(species);
    if (!pending) return;
    descriptors.forEach((descriptor) => pending.delete(descriptor.path));
    if (!pending.size) drafts.delete(species.__symbol);
    renderLibrary();
    renderInspector();
    signalDirty();
    requestAnimationFrame(() => {
      const control = focusPath ? inspectorElement.querySelector(`[data-pokemon-field="${CSS.escape(focusPath)}"]:not(:disabled), [data-pokemon-combobox="${CSS.escape(focusPath)}"]:not(:disabled)`) : null;
      const group = focusGroup ? inspectorElement.querySelector(`[data-editor-group="${CSS.escape(focusGroup)}"]`) : null;
      (control || group)?.focus({ preventScroll: true });
    });
  }

  function onClick(event) {
    const comboboxOption = event.target.closest("[data-pokemon-combobox-option]");
    if (comboboxOption && comboboxPopup.contains(comboboxOption)) {
      selectComboboxOption(Number(comboboxOption.dataset.pokemonComboboxOption));
      return;
    }
    const combobox = event.target.closest("[data-pokemon-combobox], [data-structured-combobox]");
    if (combobox && root.contains(combobox)) {
      if (comboboxState.control !== combobox) openCombobox(combobox);
      return;
    }
    const formBase = event.target.closest("[data-form-open-base]");
    if (formBase && root.contains(formBase)) {
      const target = model.species.find((candidate) => candidate.__symbol === formBase.dataset.formOpenBase && !candidate.__isForm);
      if (target) {
        sectionBySpecies.set(target.__key, "forms");
        writeStorage(STORAGE_SECTIONS_KEY, Object.fromEntries(sectionBySpecies));
        selectSpecies(target.__key);
        requestAnimationFrame(() => inspectorElement.querySelector("[data-form-reversion]:not(:disabled)")?.focus({ preventScroll: true }));
      }
      return;
    }
    const formRecord = event.target.closest("[data-form-select]");
    if (formRecord && root.contains(formRecord)) {
      const target = model.species.find((candidate) => candidate.__key === formRecord.dataset.formSelect);
      if (target) {
        sectionBySpecies.set(target.__key, "forms");
        writeStorage(STORAGE_SECTIONS_KEY, Object.fromEntries(sectionBySpecies));
        selectSpecies(target.__key, { focus: true });
      }
      return;
    }
    const formRevert = event.target.closest("[data-form-revert]");
    if (formRevert && root.contains(formRevert)) {
      const species = selectedSpecies();
      if (species && !species.__isForm && species.__symbol === baseSymbolFor(species)) {
        formDrafts.delete(baseSymbolFor(species));
        renderInspector();
        renderLibraryWindow();
        signalDirty();
        requestAnimationFrame(() => inspectorElement.querySelector("[data-form-reversion]:not(:disabled)")?.focus({ preventScroll: true }));
        setStatus("Form registry draft reverted.", "info");
      }
      return;
    }
    const assetRetry = event.target.closest("[data-asset-retry]");
    if (assetRetry && root.contains(assetRetry)) {
      const species = selectedSpecies();
      const entry = species ? assetDraftFor(species, assetRetry.dataset.assetRetry) : null;
      if (species && entry?.file) stageAssetFile(species, assetRetry.dataset.assetRetry, entry.file);
      return;
    }
    const assetRevert = event.target.closest("[data-asset-revert]");
    if (assetRevert && root.contains(assetRevert)) {
      const species = selectedSpecies();
      if (species) {
        const slot = assetRevert.dataset.assetRevert;
        removeAssetDraft(species, slot);
        renderInspector();
        renderLibraryWindow();
        signalDirty();
        requestAnimationFrame(() => inspectorElement.querySelector(`[data-asset-drop-slot="${CSS.escape(slot)}"]`)?.focus({ preventScroll: true }));
      }
      return;
    }
    const assetsRevert = event.target.closest("[data-assets-revert]");
    if (assetsRevert && root.contains(assetsRevert)) {
      const species = selectedSpecies();
      if (species) {
        revertAllAssets(species);
        requestAnimationFrame(() => inspectorElement.querySelector("[data-asset-drop-slot][role=button]")?.focus({ preventScroll: true }));
        setStatus("Asset replacements reverted.", "info");
      }
      return;
    }
    const assetDrop = event.target.closest("[data-asset-drop-slot]");
    if (assetDrop && root.contains(assetDrop) && assetDrop.getAttribute("role") === "button") {
      inspectorElement.querySelector(`[data-asset-file="${CSS.escape(assetDrop.dataset.assetDropSlot)}"]`)?.click();
      return;
    }
    const familyMember = event.target.closest("[data-family-evolution-select]");
    if (familyMember && root.contains(familyMember)) {
      const key = familyMember.dataset.familyEvolutionSelect;
      const target = model.species.find((candidate) => candidate.__key === key);
      if (target) {
        sectionBySpecies.set(target.__key, "evolution");
        writeStorage(STORAGE_SECTIONS_KEY, Object.fromEntries(sectionBySpecies));
        selectSpecies(target.__key, { focus: true });
      }
      return;
    }
    const moveTab = event.target.closest("[data-move-tab]");
    if (moveTab && root.contains(moveTab)) {
      const species = selectedSpecies();
      if (species) {
        moveTabBySpecies.set(species.__symbol, moveTab.dataset.moveTab);
        moveWindowBySpecies.set(`${species.__symbol}:${moveTab.dataset.moveTab}`, 0);
        renderInspector();
        requestAnimationFrame(() => inspectorElement.querySelector(`[data-move-tab="${CSS.escape(moveTab.dataset.moveTab)}"]`)?.focus({ preventScroll: true }));
      }
      return;
    }
    const moveRetry = event.target.closest("[data-move-retry]");
    if (moveRetry && root.contains(moveRetry)) {
      const species = selectedSpecies();
      if (species) ensureLearnsetDetail(species, true);
      return;
    }
    const moveCustomize = event.target.closest("[data-move-customize]");
    if (moveCustomize && root.contains(moveCustomize)) {
      const species = selectedSpecies();
      if (species && learnsetWritable(species)) {
        ensureLearnsetDraft(species, { materialize: true });
        renderInspector();
        refreshStructuredChrome(species);
        requestAnimationFrame(() => inspectorElement.querySelector("[data-move-symbol]")?.focus({ preventScroll: true }));
        setStatus("Independent form learnset customization started. This becomes permanent only after global Save.", "info");
      }
      return;
    }
    const moveCancel = event.target.closest("[data-move-cancel-customize], [data-move-revert]");
    if (moveCancel && root.contains(moveCancel)) {
      const species = selectedSpecies();
      if (species) {
        learnsetDrafts.delete(species.__symbol);
        renderInspector();
        refreshStructuredChrome(species);
        requestAnimationFrame(() => inspectorElement.querySelector(moveCancel.matches("[data-move-cancel-customize]") ? "[data-move-customize]" : "[data-move-search]")?.focus({ preventScroll: true }));
        setStatus("Learnset draft reverted.", "info");
      }
      return;
    }
    const moveAdd = event.target.closest("[data-move-add]");
    if (moveAdd && root.contains(moveAdd)) {
      const species = selectedSpecies();
      if (species) {
        const group = activeMoveGroup(species);
        moveSearchBySpecies.set(species.__symbol, "");
        mutateLearnset(species, (draft) => {
          draft[group].push(group === "levelMoves" ? { level: 1, move: "" } : "");
          moveWindowBySpecies.set(`${species.__symbol}:${group}`, Math.max(0, draft[group].length - MOVE_WINDOW_SIZE));
        });
        requestAnimationFrame(() => {
          const controls = [...inspectorElement.querySelectorAll("[data-move-symbol]")];
          controls.at(-1)?.focus({ preventScroll: true });
        });
        setStatus(`Added a ${humanize(group)} row. Choose a move.`, "info");
      }
      return;
    }
    const moveRemove = event.target.closest("[data-move-remove]");
    if (moveRemove && root.contains(moveRemove)) {
      const species = selectedSpecies();
      if (species) {
        const removedIndex = Number(moveRemove.dataset.moveRemove);
        mutateLearnset(species, (draft) => draft[activeMoveGroup(species)].splice(removedIndex, 1));
        requestAnimationFrame(() => inspectorElement.querySelector(`[data-move-row="${Math.max(0, removedIndex - 1)}"]`)?.focus({ preventScroll: true }));
        setStatus("Move row removed.", "info");
      }
      return;
    }
    const moveUp = event.target.closest("[data-move-up]");
    const moveDown = event.target.closest("[data-move-down]");
    if ((moveUp || moveDown) && root.contains(moveUp || moveDown)) {
      const species = selectedSpecies();
      const control = moveUp || moveDown;
      if (species) moveLearnsetRow(species, activeMoveGroup(species), Number(moveUp ? control.dataset.moveUp : control.dataset.moveDown), moveUp ? -1 : 1);
      return;
    }
    const evolutionAdd = event.target.closest("[data-evolution-add]");
    if (evolutionAdd && root.contains(evolutionAdd)) {
      const species = selectedSpecies();
      if (species) mutateEvolution(species, (draft) => {
        const method = enumOptionValue(evolutionMethodOptions()[0]) || "EVO_LEVEL";
        const kind = evolutionParameterKind(method);
        draft.edges.push({ method, parameter: ["fixed", "zero"].includes(kind) ? "0" : ["integer", "number", "numeric", "level"].includes(kind) ? "1" : "", targetSymbol: "" });
      });
      requestAnimationFrame(() => {
        const target = [...inspectorElement.querySelectorAll("[data-evolution-target]")].at(-1);
        target?.focus({ preventScroll: true });
        if (target) openCombobox(target);
      });
      setStatus("Incomplete evolution edge added. Choose a target before saving.", "warning");
      return;
    }
    const evolutionRevert = event.target.closest("[data-evolution-revert]");
    if (evolutionRevert && root.contains(evolutionRevert)) {
      const species = selectedSpecies();
      if (species) {
        evolutionDrafts.delete(species.__symbol);
        projectedFamilyGraphCache = null;
        recomputeFamilyStaging();
        renderInspector();
        refreshStructuredChrome(species);
        requestAnimationFrame(() => inspectorElement.querySelector("[data-evolution-add]")?.focus({ preventScroll: true }));
        setStatus("Evolution draft reverted.", "info");
      }
      return;
    }
    const revertDomain = event.target.closest("[data-pokemon-revert-domain]");
    if (revertDomain && root.contains(revertDomain)) {
      const species = selectedSpecies();
      if (species) revertDescriptors(species, descriptorsFor(revertDomain.dataset.pokemonRevertDomain), "", descriptorGroup(descriptorsFor(revertDomain.dataset.pokemonRevertDomain)[0] || {}, revertDomain.dataset.pokemonRevertDomain));
      return;
    }
    const evolutionRemove = event.target.closest("[data-evolution-remove]");
    if (evolutionRemove && root.contains(evolutionRemove)) {
      const species = selectedSpecies();
      if (species) {
        const removedIndex = Number(evolutionRemove.dataset.evolutionRemove);
        mutateEvolution(species, (draft) => draft.edges.splice(removedIndex, 1));
        requestAnimationFrame(() => inspectorElement.querySelector(`[data-evolution-edge="${Math.max(0, removedIndex - 1)}"]`)?.focus({ preventScroll: true }));
        setStatus("Evolution edge removed.", "info");
      }
      return;
    }
    const evolutionUp = event.target.closest("[data-evolution-up]");
    const evolutionDown = event.target.closest("[data-evolution-down]");
    if ((evolutionUp || evolutionDown) && root.contains(evolutionUp || evolutionDown)) {
      const species = selectedSpecies();
      const control = evolutionUp || evolutionDown;
      const index = Number(evolutionUp ? control.dataset.evolutionUp : control.dataset.evolutionDown);
      if (species) mutateEvolution(species, (draft) => {
        const target = Math.max(0, Math.min(draft.edges.length - 1, index + (evolutionUp ? -1 : 1)));
        const [edge] = draft.edges.splice(index, 1);
        draft.edges.splice(target, 0, edge);
      });
      requestAnimationFrame(() => inspectorElement.querySelector(`[data-evolution-edge="${Math.max(0, index + (evolutionUp ? -1 : 1))}"]`)?.focus({ preventScroll: true }));
      setStatus("Evolution edge reordered.", "info");
      return;
    }
    const firstInvalid = event.target.closest("[data-pokemon-first-invalid]");
    if (firstInvalid && root.contains(firstInvalid)) {
      navigateToFirstInvalid();
      return;
    }
    const revertField = event.target.closest("[data-pokemon-revert-field]");
    if (revertField && root.contains(revertField)) {
      const species = selectedSpecies();
      const descriptor = species ? descriptorsFor(activeDomain(species)).find((candidate) => candidate.path === revertField.dataset.pokemonRevertField) : null;
      if (species && descriptor) revertDescriptors(species, [descriptor], descriptor.path);
      return;
    }
    const revertGroup = event.target.closest("[data-pokemon-revert-group]");
    if (revertGroup && root.contains(revertGroup)) {
      const species = selectedSpecies();
      const group = species ? editorGroups(activeDomain(species), descriptorsFor(activeDomain(species))).find((candidate) => candidate.key === revertGroup.dataset.pokemonRevertGroup) : null;
      const firstWritable = species && group ? group.fields.find((descriptor) => recordFieldAccess(species, descriptor).writable) : null;
      if (species && group) revertDescriptors(species, group.fields, firstWritable?.path || "", group.key);
      return;
    }
    const selection = event.target.closest("[data-pokemon-select]");
    if (selection && root.contains(selection)) {
      ui.rovingKey = selection.dataset.pokemonSelect;
      selectSpecies(selection.dataset.pokemonSelect);
      return;
    }
    const retry = event.target.closest("[data-pokemon-retry]");
    if (retry && root.contains(retry)) {
      ensureLoad(true);
      return;
    }
    const libraryToggle = event.target.closest("[data-pokemon-library-toggle]");
    if (libraryToggle && root.contains(libraryToggle)) {
      root.classList.add("is-mobile-library-open");
      requestAnimationFrame(() => {
        scrollCurrentIntoView();
        requestAnimationFrame(() => searchElement.focus({ preventScroll: true }));
      });
      return;
    }
    const libraryClose = event.target.closest("[data-pokemon-library-close]");
    if (libraryClose && root.contains(libraryClose)) {
      root.classList.remove("is-mobile-library-open");
      focusBrowseControl();
      return;
    }
    const currentPokemon = event.target.closest("[data-pokemon-current]");
    if (currentPokemon && root.contains(currentPokemon)) {
      if (!scrollCurrentIntoView({ focus: true })) {
        clearLibraryFilters();
        requestAnimationFrame(() => scrollCurrentIntoView({ focus: true }));
      }
      return;
    }
    const clearFilters = event.target.closest("[data-pokemon-clear-filters]");
    if (clearFilters && root.contains(clearFilters)) {
      clearLibraryFilters();
      requestAnimationFrame(() => searchElement.focus({ preventScroll: true }));
      return;
    }
    const tab = event.target.closest("[data-pokemon-tab]");
    if (tab && root.contains(tab)) {
      selectDomain(tab.dataset.pokemonTab, { focus: true });
      return;
    }
  }

  function onInput(event) {
    if (event.target.matches("[data-move-search]")) {
      const species = selectedSpecies();
      if (species) {
        moveSearchBySpecies.set(species.__symbol, event.target.value);
        moveWindowBySpecies.set(`${species.__symbol}:${activeMoveGroup(species)}`, 0);
        refreshMoveList(species);
      }
      return;
    }
    if (event.target.matches("[data-move-level], [data-move-symbol]:not([data-structured-combobox])")) {
      const species = selectedSpecies();
      const index = Number(firstDefined(event.target.dataset.moveSymbol, event.target.dataset.moveLevel));
      if (species) {
        const group = activeMoveGroup(species);
        mutateLearnset(species, (draft) => {
          if (group === "levelMoves") {
            if (event.target.matches("[data-move-level]")) {
              const level = normalizeMoveLevel(event.target.value);
              draft.levelMoves[index].level = level;
              if (typeof level === "number") event.target.value = String(level);
            }
            else draft.levelMoves[index].move = event.target.value.trim().toUpperCase();
          } else draft[group][index] = event.target.value.trim().toUpperCase();
        }, { rerender: false });
      }
      return;
    }
    if (event.target.matches("[data-evolution-parameter]:not([data-structured-combobox])")) {
      const species = selectedSpecies();
      const index = Number(event.target.dataset.evolutionParameter);
      if (species) {
        mutateEvolution(species, (draft) => { draft.edges[index].parameter = event.target.value; }, { rerender: false });
      }
      return;
    }
    if (event.target.matches("[data-pokemon-combobox], [data-structured-combobox]")) {
      if (comboboxState.control !== event.target) openCombobox(event.target, event.target.value);
      else filterCombobox(event.target.value);
      return;
    }
    if (event.target.matches("[data-pokemon-field]") && !["checkbox", "select-one"].includes(event.target.type)) {
      editField(event.target);
      return;
    }
    if (event.target !== searchElement) return;
    ui.pendingSearch = searchElement.value;
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      ui.search = ui.pendingSearch;
      writeStorage(STORAGE_SEARCH_KEY, ui.search);
      renderLibrary({ resetScroll: true, announce: true });
    }, 140);
  }

  function onChange(event) {
    if (event.target.matches("[data-form-reversion]")) {
      const species = selectedSpecies();
      if (!species) return;
      const index = Number(event.target.dataset.formReversion);
      const editor = formValueFor(species);
      if (species.__isForm || species.__symbol !== editor.baseSymbol || !editor.forms[index] || !formFieldWritable(editor, editor.forms[index], "needsReversion")) return;
      const selector = `[data-form-reversion="${index}"]`;
      mutateForms(species, (draft) => {
        draft.forms[index].needsReversion = event.target.checked;
      }, selector);
      return;
    }
    if (event.target.matches("[data-asset-file]")) {
      const species = selectedSpecies();
      const file = event.target.files?.[0];
      if (species && file) stageAssetFile(species, event.target.dataset.assetFile, file);
      event.target.value = "";
      return;
    }
    if (event.target.matches('[data-evolution-parameter][type="number"]')) {
      const species = selectedSpecies();
      if (species) syncRenderedEvolutionValidation(species);
      return;
    }
    if (event.target.matches("[data-move-level]")) {
      const species = selectedSpecies();
      if (species) syncRenderedMoveValidation(species);
      return;
    }
    if (event.target.matches("[data-evolution-method], [data-evolution-target], [data-evolution-baby], [data-evolution-parameter]") && !event.target.matches("[data-structured-combobox]")) {
      const species = selectedSpecies();
      if (!species) return;
      if (event.target.matches("[data-evolution-baby]")) {
        recomputeFamilyStaging(species, event.target.value);
        renderInspector();
        refreshStructuredChrome(species);
        return;
      }
      mutateEvolution(species, (draft) => {
        const index = Number(firstDefined(event.target.dataset.evolutionMethod, event.target.dataset.evolutionTarget, event.target.dataset.evolutionParameter));
        if (event.target.matches("[data-evolution-method]")) {
          draft.edges[index].method = event.target.value;
          const kind = evolutionParameterKind(event.target.value);
          draft.edges[index].parameter = ["zero", "fixed"].includes(kind) ? "0" : ["number", "numeric", "level", "integer"].includes(kind) ? "1" : "";
        } else if (event.target.matches("[data-evolution-target]")) {
          const target = model.species.find((candidate) => candidate.__symbol === event.target.value);
          const baseSymbol = textValue(target?.baseSymbol, target?.form?.baseSymbol, target?.formMetadata?.baseSymbol, target?.__symbol);
          const formIndex = Number(firstDefined(target?.formIndex, target?.form?.index, target?.formMetadata?.formIndex));
          draft.edges[index].targetSymbol = target?.__isForm && baseSymbol ? baseSymbol : event.target.value;
          if (target?.__isForm && Number.isFinite(formIndex) && formIndex > 0) draft.edges[index].targetFormIndex = formIndex;
          else delete draft.edges[index].targetFormIndex;
        }
        else draft.edges[index].parameter = event.target.value;
      });
      const focusSelector = event.target.matches("[data-evolution-method]") ? `[data-evolution-method="${event.target.dataset.evolutionMethod}"]` : event.target.matches("[data-evolution-target]") ? `[data-evolution-target="${event.target.dataset.evolutionTarget}"]` : `[data-evolution-parameter="${event.target.dataset.evolutionParameter}"]`;
      requestAnimationFrame(() => inspectorElement.querySelector(focusSelector)?.focus({ preventScroll: true }));
      return;
    }
    if (event.target.matches("[data-move-symbol]:not([data-structured-combobox])")) {
      const focusSelector = `[data-move-symbol="${event.target.dataset.moveSymbol}"]`;
      renderInspector();
      requestAnimationFrame(() => inspectorElement.querySelector(focusSelector)?.focus({ preventScroll: true }));
      return;
    }
    if (event.target.matches("[data-pokemon-field]")) {
      editField(event.target);
      return;
    }
    if (event.target === typeFilterElement) {
      ui.type = typeFilterElement.value;
      writeStorage(STORAGE_TYPE_KEY, ui.type);
    }
    else if (event.target === stateFilterElement) {
      ui.scope = stateFilterElement.value;
      writeStorage(STORAGE_SCOPE_KEY, ui.scope);
    }
    else if (event.target.matches("[data-pokemon-section-select]")) {
      selectDomain(event.target.value);
      return;
    }
    else return;
    renderLibrary({ resetScroll: true, announce: true });
  }

  function onKeyDown(event) {
    const assetDrop = event.target.closest?.("[data-asset-drop-slot][role=button]");
    if (assetDrop && ["Enter", " "].includes(event.key)) {
      event.preventDefault();
      inspectorElement.querySelector(`[data-asset-file="${CSS.escape(assetDrop.dataset.assetDropSlot)}"]`)?.click();
      return;
    }
    const moveRow = event.target.closest?.("[data-move-row]");
    if (moveRow && event.altKey && ["ArrowUp", "ArrowDown"].includes(event.key)) {
      const species = selectedSpecies();
      const filtered = species ? Boolean(textValue(moveSearchBySpecies.get(species.__symbol)).trim()) : false;
      if (species && learnsetRowsEditable(species) && !filtered) {
        event.preventDefault();
        moveLearnsetRow(species, activeMoveGroup(species), Number(moveRow.dataset.moveRow), event.key === "ArrowUp" ? -1 : 1);
      }
      return;
    }
    const combobox = event.target.closest?.("[data-pokemon-combobox], [data-structured-combobox]");
    if (combobox) {
      const open = comboboxState.control === combobox && !comboboxPopup.hidden;
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key) && (open || ["ArrowDown", "ArrowUp"].includes(event.key))) {
        event.preventDefault();
        if (!open) openCombobox(combobox);
        if (!comboboxState.filtered.length) return;
        if (event.key === "Home") comboboxState.activeIndex = 0;
        else if (event.key === "End") comboboxState.activeIndex = comboboxState.filtered.length - 1;
        else comboboxState.activeIndex = Math.max(0, Math.min(comboboxState.filtered.length - 1, comboboxState.activeIndex + (event.key === "ArrowDown" ? 1 : -1)));
        renderComboboxPopup();
        return;
      }
      if (event.key === "Enter" && open) {
        event.preventDefault();
        if (comboboxState.activeIndex >= 0) selectComboboxOption(comboboxState.activeIndex);
        return;
      }
      if (event.key === "Escape" && open) {
        event.preventDefault();
        closeCombobox();
        return;
      }
      if (event.key === "Tab" && open) closeCombobox();
    }
    const tab = event.target.closest("[data-pokemon-tab]");
    if (tab && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      const tabs = [...inspectorElement.querySelectorAll("[data-pokemon-tab]")];
      const index = tabs.indexOf(tab);
      if (index < 0) return;
      event.preventDefault();
      const nextIndex = event.key === "Home" ? 0 : (event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length);
      selectDomain(tabs[nextIndex].dataset.pokemonTab, { focus: true });
      return;
    }
    const row = event.target.closest?.("[data-pokemon-select]");
    const navigationKey = row?.dataset.pokemonSelect || (event.target === libraryElement ? ui.rovingKey : "");
    if (navigationKey && ["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) {
      const index = ui.filtered.findIndex((species) => species.__key === navigationKey);
      if (index < 0) return;
      event.preventDefault();
      const nextIndex = event.key === "Home" ? 0 : (event.key === "End" ? ui.filtered.length - 1 : Math.max(0, Math.min(ui.filtered.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))));
      const nextKey = ui.filtered[nextIndex]?.__key;
      if (!nextKey) return;
      ui.rovingKey = nextKey;
      ensureRowVisible(nextIndex);
      renderLibraryWindow();
      selectSpecies(nextKey, { focus: true });
      return;
    }
    if (event.target === searchElement && event.key === "ArrowDown") {
      const firstKey = ui.filtered[0]?.__key;
      if (firstKey) {
        event.preventDefault();
        ui.rovingKey = firstKey;
        ensureRowVisible(0);
        renderLibraryWindow({ focusKey: firstKey });
      }
    }
  }

  function onLibraryScroll() {
    if (scrollFrame) return;
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = 0;
      renderLibraryWindow();
    });
  }

  function onFocusIn(event) {
    const combobox = event.target.closest?.("[data-pokemon-combobox], [data-structured-combobox]");
    if (!combobox) return;
    openCombobox(combobox);
    requestAnimationFrame(() => combobox.select());
  }

  function onFocusOut(event) {
    if (!event.target.matches?.("[data-pokemon-combobox], [data-structured-combobox]")) return;
    requestAnimationFrame(() => {
      if (document.activeElement !== comboboxState.control && !comboboxPopup.contains(document.activeElement)) closeCombobox();
    });
  }

  function onPointerDown(event) {
    if (event.target.closest?.("[data-pokemon-combobox-option]")) event.preventDefault();
  }

  function onAssetDragOver(event) {
    const target = event.target.closest?.("[data-asset-drop-slot][role=button]");
    if (!target) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }

  function onAssetDrop(event) {
    const target = event.target.closest?.("[data-asset-drop-slot][role=button]");
    if (!target) return;
    event.preventDefault();
    const species = selectedSpecies();
    const file = event.dataTransfer?.files?.[0];
    if (species && file) stageAssetFile(species, target.dataset.assetDropSlot, file);
  }

  function onWorkspaceScroll(event) {
    const list = event.target.closest?.("[data-move-list]");
    if (!list) return;
    const species = selectedSpecies();
    if (!species) return;
    const group = activeMoveGroup(species);
    const key = `${species.__symbol}:${group}`;
    const next = Math.max(0, Math.floor(list.scrollTop / moveRowHeight()) - 5);
    if (next === (Number(moveWindowBySpecies.get(key)) || 0)) return;
    moveWindowBySpecies.set(key, next);
    const scrollTop = list.scrollTop;
    requestAnimationFrame(() => refreshMoveList(species, scrollTop));
  }

  root.addEventListener("click", onClick);
  root.addEventListener("input", onInput);
  root.addEventListener("change", onChange);
  root.addEventListener("keydown", onKeyDown);
  root.addEventListener("focusin", onFocusIn);
  root.addEventListener("focusout", onFocusOut);
  root.addEventListener("pointerdown", onPointerDown);
  root.addEventListener("dragover", onAssetDragOver);
  root.addEventListener("drop", onAssetDrop);
  root.addEventListener("scroll", onWorkspaceScroll, true);
  libraryElement.addEventListener("scroll", onLibraryScroll, { passive: true });
  inspectorElement.addEventListener("scroll", positionComboboxPopup, { passive: true });
  window.addEventListener("resize", positionComboboxPopup);
  const resizeObserver = typeof ResizeObserver === "function"
    ? new ResizeObserver(() => renderLibraryWindow())
    : null;
  resizeObserver?.observe(libraryElement);

  function applyPayload(payload) {
    model = unwrapPayload(payload);
    projectedFamilyGraphCache = null;
    for (const revision of editorOptionsByRevision.keys()) if (revision !== model.sourceRevision) editorOptionsByRevision.delete(revision);
    const currentDetailPrefix = `${model.sourceRevision}:${model.assetRevision}:`;
    for (const key of learnsetDetails.keys()) if (!key.startsWith(currentDetailPrefix)) learnsetDetails.delete(key);
    if (model.sourceRevision) lastWorkspaceRevision = model.sourceRevision;
    if (model.assetRevision) lastWorkspaceAssetRevision = model.assetRevision;
    if (pendingCommittedAssetRevision === model.assetRevision) pendingCommittedAssetRevision = "";
    ui.error = "";
    ui.busy = false;
    renderAll();
    signalDirty();
  }

  function ensureLoad(force = false) {
    if (loadPromise && !force) return loadPromise;
    const generation = ++loadGeneration;
    ui.busy = true;
    ui.error = "";
    renderAll();
    loadPromise = requestJson("/api/v2/pokemon-data")
      .then((payload) => {
        if (!ui.destroyed && generation === loadGeneration) applyPayload(payload);
        return payload;
      })
      .catch((error) => {
        if (!ui.destroyed && generation === loadGeneration) {
          ui.busy = false;
          ui.error = textValue(error?.message, error, "Unknown Pokémon data request failure");
          loadPromise = null;
          setStatus(`Pokédex index unavailable: ${ui.error}`, "error");
          renderAll();
        }
        return null;
      });
    return loadPromise;
  }

  function refresh(payload) {
    if (looksLikePokemonPayload(payload)) {
      if (!loadPromise) loadPromise = Promise.resolve(payload);
      applyPayload(payload);
      return loadPromise;
    }
    const nextRevision = textValue(payload?.sourceRevision, "");
    const nextAssetRevision = textValue(payload?.assetRevision, pendingCommittedAssetRevision, "");
    const sourceChanged = Boolean(nextRevision && (lastWorkspaceRevision || model.sourceRevision) && nextRevision !== (lastWorkspaceRevision || model.sourceRevision));
    const assetChanged = Boolean(nextAssetRevision && (lastWorkspaceAssetRevision || model.assetRevision) && nextAssetRevision !== (lastWorkspaceAssetRevision || model.assetRevision));
    if (sourceChanged || assetChanged) {
      if (nextRevision) lastWorkspaceRevision = nextRevision;
      if (nextAssetRevision) lastWorkspaceAssetRevision = nextAssetRevision;
      return ensureLoad(true).then(async (result) => {
        const species = selectedSpecies();
        if (species && ["moves", "evolution", "forms", "assets"].includes(activeDomain(species))) await ensureLearnsetDetail(species);
        return result;
      });
    }
    if (nextRevision) lastWorkspaceRevision = nextRevision;
    if (nextAssetRevision) lastWorkspaceAssetRevision = nextAssetRevision;
    return ensureLoad();
  }

  function destroy() {
    if (ui.destroyed) return;
    ui.destroyed = true;
    root.removeEventListener("click", onClick);
    root.removeEventListener("input", onInput);
    root.removeEventListener("change", onChange);
    root.removeEventListener("keydown", onKeyDown);
    root.removeEventListener("focusin", onFocusIn);
    root.removeEventListener("focusout", onFocusOut);
    root.removeEventListener("pointerdown", onPointerDown);
    root.removeEventListener("dragover", onAssetDragOver);
    root.removeEventListener("drop", onAssetDrop);
    root.removeEventListener("scroll", onWorkspaceScroll, true);
    libraryElement.removeEventListener("scroll", onLibraryScroll);
    inspectorElement.removeEventListener("scroll", positionComboboxPopup);
    window.removeEventListener("resize", positionComboboxPopup);
    resizeObserver?.disconnect();
    window.clearTimeout(searchTimer);
    if (scrollFrame) cancelAnimationFrame(scrollFrame);
    resultAnnouncer.remove();
    comboboxPopup.remove();
    root.removeAttribute("aria-busy");
    libraryElement.removeAttribute("aria-busy");
    root.classList.remove("pv2-pokemon-workbench");
    libraryPanel?.classList.remove("pv2-pokemon-library-panel");
    inspectorPanel?.classList.remove("pv2-pokemon-inspector-panel");
  }

  function changeCount() {
    return [...drafts.values()].reduce((total, fields) => total + fields.size, 0) + learnsetDrafts.size + evolutionDrafts.size + [...formDrafts.values()].reduce((total, draft) => total + formAffectedSymbols(model.species.find((species) => baseSymbolFor(species) === draft.baseSymbol) || {}).length, 0) + [...assetDrafts.values()].reduce((total, draft) => total + Object.keys(draft.assets || {}).length, 0);
  }

  function commitPayload() {
    const records = [...drafts.entries()]
      .filter(([, fields]) => fields.size)
      .map(([symbol, fields]) => ({ symbol, fields: Object.fromEntries(fields) }));
    const payload = records.length ? { pokemonUpdates: { records } } : {};
    if (learnsetDrafts.size) {
      payload.pokemonLearnsetUpdates = { records: [...learnsetDrafts.values()].map((draft) => ({
        symbol: draft.symbol,
        levelMoves: draft.levelMoves.map((entry) => ({ level: Number(entry.level), move: entry.move })),
        machineMoves: [...draft.machineMoves],
        tutorMoves: [...draft.tutorMoves],
        eggMoves: [...draft.eggMoves],
        materializeInherited: Boolean(draft.materializeInherited),
      })) };
    }
    if (evolutionDrafts.size) {
      payload.pokemonEvolutionUpdates = { records: [...evolutionDrafts.values()].map((draft) => ({
        symbol: draft.symbol,
        ...(draft.edgesTouched ? { edges: draft.edges.map((edge) => ({ method: edge.method, parameter: evolutionCommitParameter(edge), targetSymbol: edge.targetSymbol, ...(edge.targetFormIndex !== undefined ? { targetFormIndex: edge.targetFormIndex } : {}) })) } : {}),
        ...(draft.babyTouched ? { babySymbol: draft.babySymbol } : {}),
      })) };
    }
    if (formDrafts.size) {
      payload.pokemonFormUpdates = { records: [...formDrafts.values()].map((draft) => ({
        baseSymbol: draft.baseSymbol,
        forms: draft.forms.map((row) => ({ symbol: row.symbol, declaredFormIndex: Number(row.declaredFormIndex), enabled: Boolean(row.enabled), needsReversion: Boolean(row.needsReversion) })),
      })) };
    }
    if (assetDrafts.size) {
      const assetRecords = [...assetDrafts.values()].map((draft) => ({
        symbol: draft.symbol,
        assets: Object.fromEntries(Object.entries(draft.assets).filter(([, entry]) => entry.stagingToken).map(([slot, entry]) => [slot, { stagingToken: entry.stagingToken }])),
      })).filter((record) => Object.keys(record.assets).length);
      if (assetRecords.length) {
        payload.assetRevision = model.assetRevision;
        payload.pokemonAssetUpdates = { records: assetRecords };
      }
    }
    return payload;
  }

  function clearDrafts(domains = ["pokemonUpdates", "pokemonLearnsetUpdates", "pokemonEvolutionUpdates", "pokemonFormUpdates", "pokemonAssetUpdates"], { discardAssets = true } = {}) {
    if (domains.includes("pokemonUpdates")) drafts.clear();
    if (domains.includes("pokemonLearnsetUpdates")) learnsetDrafts.clear();
    if (domains.includes("pokemonEvolutionUpdates")) {
      evolutionDrafts.clear();
      familyStageSummaries.clear();
      projectedFamilyGraphCache = null;
    }
    if (domains.includes("pokemonFormUpdates")) formDrafts.clear();
    if (domains.includes("pokemonAssetUpdates")) {
      assetDrafts.forEach((draft) => Object.values(draft.assets || {}).forEach((entry) => { if (discardAssets) discardAssetStage(entry); revokeAssetPreview(entry); }));
      assetDrafts.clear();
    }
    renderAll();
    signalDirty();
  }

  function clearCommitted(committed = null) {
    const transaction = isRecord(committed) && isRecord(committed.domains) ? committed : null;
    const committedAssetRevision = textValue(transaction?.assetRevision);
    if (committedAssetRevision && committedAssetRevision !== model.assetRevision) pendingCommittedAssetRevision = committedAssetRevision;
    const domains = committed ? (Array.isArray(committed) ? committed : (committed.changedDomains || Object.keys(committed))) : ["pokemonUpdates", "pokemonLearnsetUpdates", "pokemonEvolutionUpdates", "pokemonFormUpdates", "pokemonAssetUpdates"];
    const assetResult = transaction?.domains?.pokemonAssetUpdates;
    clearDrafts(assetResult ? domains.filter((domain) => domain !== "pokemonAssetUpdates") : domains, { discardAssets: false });
    if (!assetResult) return;
    const retained = new Set(asArray(assetResult.retainedStagingTokens));
    assetDrafts.forEach((draft, symbol) => {
      Object.entries(draft.assets || {}).forEach(([slot, entry]) => {
        if (retained.has(entry.stagingToken)) {
          removeAssetDraft({ __symbol: symbol }, slot, { discard: true });
          return;
        }
        removeAssetDraft({ __symbol: symbol }, slot, { discard: false });
      });
    });
    renderAll();
    signalDirty();
  }

  function reset() {
    clearDrafts();
    setStatus("Pokémon drafts reset.", "info");
  }

  renderAll();

  return Object.freeze({
    hasChanges: () => changeCount() > 0,
    changeCount,
    hasInvalid: () => validationErrors().length > 0,
    validationCount: () => validationErrors().length,
    validationMessage: () => {
      const first = validationErrors()[0];
      return first ? `${effectiveName(first.species)} — ${first.message}` : "";
    },
    blockingCount: () => assetBusyIssues().length,
    blockingMessage: () => assetBusyIssues()[0]?.message || "",
    isBlocking: () => assetBusyIssues().length > 0,
    commitPayload,
    clearCommitted,
    reset,
    refresh,
    openRecord,
    navigationContext,
    focusFirstInvalid: navigateToFirstInvalid,
    focusFirstBlocking,
    destroy,
  });
}
