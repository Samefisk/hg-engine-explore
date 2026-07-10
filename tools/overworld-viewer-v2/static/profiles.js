/*
 * Overworld Viewer V2 — profile workspace
 *
 * This module owns its DOM and draft state. It intentionally depends only on
 * the documented data.json model and injected API/callbacks, so the profile
 * editor can evolve independently from the legacy viewer implementation.
 */

const DEFAULT_MATCH = Object.freeze({
  groupMask: "OW_WILD_BEHAVIOR_GROUP_NONE",
  species: "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES",
  terrain: "OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN",
  minLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
  maxLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
  shiny: "OW_WILD_BEHAVIOR_MATCH_ANY_SHINY",
  behaviorClass: "OW_WILD_BEHAVIOR_MATCH_ANY_CLASS",
});

const TARGET_KINDS = Object.freeze([
  ["pokemon", "Pokémon"],
  ["family", "Evolution family"],
  ["type", "Typing"],
  ["spawnPool", "Spawn pool"],
]);

const SPAWN_POOLS = Object.freeze([
  { key: "land", label: "Land", raw: "OW_WILD_SPAWN_TERRAIN_LAND", tableKeys: ["morning", "day", "night", "hoenn", "sinnoh"], swarmKeys: ["landSwarm"] },
  { key: "surf", label: "Surf", raw: "OW_WILD_SPAWN_TERRAIN_SURF", tableKeys: ["surf"], swarmKeys: ["surfSwarm"] },
  { key: "fish", label: "Fishing", raw: "OW_WILD_SPAWN_TERRAIN_FISHING", tableKeys: ["oldRod", "goodRod", "superRod"], swarmKeys: ["nightFish", "fishSwarm"] },
  { key: "headbutt", label: "Headbutt", raw: "OW_WILD_SPAWN_TERRAIN_HEADBUTT", tableKeys: ["headbuttNormal", "headbuttSpecial"], swarmKeys: [] },
]);

const MATCH_FIELDS = Object.freeze([
  ["species", "Pokémon"],
  ["groupMask", "Group mask"],
  ["terrain", "Terrain"],
  ["minLevel", "Minimum level"],
  ["maxLevel", "Maximum level"],
  ["shiny", "Shiny"],
  ["behaviorClass", "Base profile"],
]);

const FIELD_SECTIONS = Object.freeze([
  {
    id: "identity",
    title: "Identity & spawning",
    hint: "Behavior family, spawn state, destination, and population limits.",
    fields: [
      "profileId", "spawnState", "spawnDestination", "spawnHopTime",
      "spawnDestinationMinDistance", "spawnDestinationMaxDistance", "overworldLimit", "jumpLevel",
    ],
  },
  {
    id: "calm",
    title: "Calm state",
    hint: "Default roaming behavior before the Pokémon becomes alert.",
    fields: [
      "chillState", "chillAction", "chillTarget", "chillSpeed", "chillCooldown",
      "range", "chillAllowedTile", "chillAllowedTile2", "specialAction",
    ],
  },
  {
    id: "alert",
    title: "Alert & active state",
    hint: "Detection, reaction, targeting, chase, and active movement.",
    fields: [
      "alertState", "alertEmote", "alertTime", "alertness", "alertRange", "alertChance",
      "alertSpecialAction", "attentiveState", "attentiveAction", "attentiveSpeed",
      "attentiveBattle", "targetSelector", "movementStyle", "attentiveAllowedTile",
      "attentiveAllowedTile2", "attentiveChaseBoostDistance", "attentiveChaseBoostSpeed",
      "attentiveCircleRadius", "attentiveContinueWhenArrived", "attentiveAvoidPreviousTile",
    ],
  },
  {
    id: "tired",
    title: "Tired state",
    hint: "Stamina, recovery timing, and movement after exertion.",
    fields: [
      "stamina", "tiredState", "restTime", "tiredSpeed", "tiredAllowedTile",
      "tiredAllowedTile2",
    ],
  },
  {
    id: "motion",
    title: "Motion mechanics",
    hint: "Hop, teleport, ram, and movement-chain tuning.",
    fields: [
      "hopAllowNonCardinal", "hopMinDistance", "hopMaxDistance", "hopPause", "hopTime",
      "hopSpinSpeed", "teleportTime", "teleportPause", "ramAccelerationSteps", "ramMaxSpeed",
      "chainPauseAction", "attentiveHopAllowNonCardinal", "attentiveHopMinDistance",
      "attentiveHopMaxDistance", "attentiveHopPause", "attentiveHopSpinSpeed",
      "attentiveTeleportTime", "attentiveTeleportPause", "attentiveRamAccelerationSteps",
      "attentiveRamMaxSpeed", "tiredHopAllowNonCardinal", "tiredHopMinDistance",
      "tiredHopMaxDistance", "tiredHopPause", "tiredTeleportTime", "tiredTeleportPause",
      "tiredRamAccelerationSteps", "tiredRamMaxSpeed",
    ],
  },
]);

const ANY_MATCH_PREFIXES = Object.freeze([
  "OW_WILD_BEHAVIOR_MATCH_ANY_",
  "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
  "OW_WILD_BEHAVIOR_GROUP_NONE",
]);

const RAM_LOCOMOTION = "OW_WILD_BEHAVIOR_LOCOMOTION_RAM";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function humanizeRaw(value) {
  const raw = String(value ?? "");
  if (!raw) return "Not set";
  return raw
    .replace(/^OW_WILD_BEHAVIOR_/, "")
    .replace(/^OW_WILD_SPAWNER_/, "")
    .replace(/^OW_WILD_SPAWN_/, "")
    .replace(/^SPECIES_/, "")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function valueRaw(value) {
  if (value && typeof value === "object") return String(value.raw ?? value.symbol ?? value.value ?? "");
  return String(value ?? "");
}

function valueLabel(value) {
  if (value && typeof value === "object") {
    return String(value.label ?? value.name ?? humanizeRaw(value.raw ?? value.symbol ?? value.value));
  }
  return humanizeRaw(value);
}

function unique(values) {
  return [...new Set(values.filter((value) => value !== undefined && value !== null && value !== ""))];
}

function isOverrideProfile(profile) {
  return Boolean(profile?.isOverrideProfile || profile?.kind === "override" || String(profile?.index ?? "").startsWith("override:"));
}

function ordersFor(profile) {
  if (Array.isArray(profile?.orders) && profile.orders.length) return profile.orders.map(Number);
  if (profile?.order !== undefined && profile?.order !== null) return [Number(profile.order)];
  const fromIndex = String(profile?.index ?? "").replace(/^override:/, "");
  return fromIndex && Number.isFinite(Number(fromIndex)) ? [Number(fromIndex)] : [];
}

function baseProfileKey(profile) {
  return `base:${profile?.symbol || profile?.name || profile?.index}`;
}

function overrideProfileKey(profile) {
  const named = String(profile?.customName || "").trim();
  if (named) return `override:name:${named}`;
  const signature = ordersFor(profile).join(",") || profile?.symbol || profile?.index;
  return `override:profile:${signature}`;
}

function profileKey(profile) {
  return profile?.draftId ? `draft:${profile.draftId}` : (isOverrideProfile(profile) ? overrideProfileKey(profile) : baseProfileKey(profile));
}

function normalizeData(input) {
  const data = input && typeof input === "object" ? input : {};
  return {
    fields: [],
    overrideFieldKeys: [],
    editOptions: {},
    labels: {},
    classes: [],
    assignments: [],
    speciesOptions: [],
    typeOptions: [],
    defaultClassIndex: 0,
    profilesAvailable: true,
    profileError: null,
    ...data,
  };
}

function mapOfMaps() {
  return new Map();
}

function newDraftStore() {
  return {
    version: 2,
    baseFields: mapOfMaps(),
    overrideFields: mapOfMaps(),
    memberships: new Map(),
    overrideNames: new Map(),
    overrideTargets: new Map(),
    removedOverrides: new Set(),
    newOverrides: [],
    overrideOrder: [],
  };
}

function cloneRawMatch(match) {
  const result = { ...DEFAULT_MATCH };
  for (const [field] of MATCH_FIELDS) result[field] = valueRaw(match?.[field]) || result[field];
  return result;
}

function cloneTarget(target = {}) {
  return {
    members: unique((target.members || []).map((member) => valueRaw(member?.symbol || member)).filter(Boolean)),
    match: cloneRawMatch(target.match),
    targetMode: ["disabled", "members", "all"].includes(target.targetMode) ? target.targetMode : "disabled",
  };
}

function createDraftId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

/**
 * Create the standalone profiles workspace.
 *
 * `api` may be a function or expose request/fetch/get/post methods. All source
 * access remains behind that injected boundary; this module never calls the
 * global fetch implementation directly.
 */
export function createProfilesController({
  state = {},
  api,
  elements = {},
  setStatus = () => {},
  markDirty = () => {},
  confirmAction,
} = {}) {
  const root = elements.profilesView || elements.root || elements.container || elements.profiles;
  if (!(root instanceof Element)) throw new TypeError("createProfilesController requires elements.profilesView");
  if (!api) throw new TypeError("createProfilesController requires an injected api");

  let data = normalizeData(state.profileData || state.data || state.appData);
  const drafts = state.profileDrafts?.version === 2 ? state.profileDrafts : newDraftStore();
  state.profileDrafts = drafts;

  const ui = {
    search: "",
    kind: "all",
    selectedKey: state.selectedProfileKey || "",
    openSections: new Set(["identity"]),
    context: {
      species: "",
      terrain: "",
      level: "20",
      shiny: false,
    },
    contextResult: null,
    contextError: "",
    contextBusy: false,
    targetKind: "pokemon",
    targetValue: "",
    memberQuery: "",
    draggedKey: "",
    selectionHint: "",
    busy: false,
    destroyed: false,
  };
  let contextAbortController = null;
  let dialogSubmit = null;

  const listElement = elements.profileLibrary;
  const editorElement = elements.profileInspector;
  const contextElement = elements.profileResolution;
  if (![listElement, editorElement, contextElement].every((element) => element instanceof Element)) {
    throw new TypeError("Profile controller requires profileLibrary, profileInspector, and profileResolution elements");
  }
  root.classList.add("profile-controller-ready", "pv2");
  listElement.classList.add("pv2-profile-list");
  editorElement.classList.add("pv2-editor");
  contextElement.classList.add("pv2-context");
  elements.resolveContext.dataset.action = "resolve-context";
  const announcerElement = document.createElement("p");
  announcerElement.className = "sr-only profile-position-announcer";
  announcerElement.setAttribute("aria-live", "polite");
  announcerElement.setAttribute("aria-atomic", "true");
  root.append(announcerElement);
  const dialogElement = document.createElement("dialog");
  dialogElement.className = "profile-dialog pv2-dialog";
  dialogElement.dataset.profileDialog = "";
  root.append(dialogElement);

  function status(message, kind = "info") {
    setStatus(String(message || ""), kind);
  }

  function announce(message) {
    announcerElement.textContent = "";
    requestAnimationFrame(() => { announcerElement.textContent = String(message || ""); });
  }

  async function requestJson(path, options = {}) {
    const method = String(options.method || "GET").toUpperCase();
    let result;
    if (typeof api === "function") {
      result = await api(path, options);
    } else if (typeof api.request === "function") {
      result = await api.request(path, options);
    } else if (typeof api.fetch === "function") {
      result = await api.fetch(path, options);
    } else if (method === "GET" && typeof api.get === "function") {
      result = await api.get(path, options);
    } else if (method === "POST" && typeof api.post === "function") {
      const payload = typeof options.body === "string" ? JSON.parse(options.body || "{}") : options.body;
      result = await api.post(path, payload, options);
    } else {
      throw new TypeError(`Injected api cannot ${method} ${path}`);
    }

    if (result instanceof Response) {
      const body = await result.json();
      if (!result.ok) throw new Error(body?.error || `HTTP ${result.status}`);
      return body;
    }
    if (result?.ok === false && result?.error) throw new Error(result.error);
    return result?.data !== undefined && result?.response !== undefined ? result.data : result;
  }

  function apiGet(path, options = {}) {
    return requestJson(path, { ...options, method: "GET" });
  }

  function apiPost(path, payload, options = {}) {
    return requestJson(path, {
      ...options,
      method: "POST",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      body: JSON.stringify(payload),
    });
  }

  function baseProfiles() {
    return data.classes.filter((profile) => !isOverrideProfile(profile));
  }

  function savedOverrideProfiles() {
    return data.classes.filter(isOverrideProfile);
  }

  function newOverrideProfiles() {
    return drafts.newOverrides.map((draft) => ({
      ...draft,
      index: `draft:${draft.draftId}`,
      kind: "override",
      isOverrideProfile: true,
      symbol: `DRAFT_OVERRIDE_${draft.draftId}`,
      orders: [],
      profile: Object.fromEntries(Object.entries(draft.fields).map(([field, raw]) => [field, { raw }])),
      editProfile: Object.fromEntries(Object.entries(draft.fields).map(([field, raw]) => [field, { raw }])),
      target: cloneTarget(draft.target),
      memberSymbols: [...draft.target.members],
      members: speciesEntries().filter((species) => draft.target.members.includes(species.symbol)),
      speciesCount: draft.target.targetMode === "members" ? draft.target.members.length : 0,
    }));
  }

  function orderedSavedOverrides() {
    const saved = savedOverrideProfiles();
    if (!drafts.overrideOrder.length) return saved;
    const byKey = new Map(saved.map((profile) => [profileKey(profile), profile]));
    const ordered = drafts.overrideOrder.map((key) => byKey.get(key)).filter(Boolean);
    for (const profile of saved) if (!ordered.includes(profile)) ordered.push(profile);
    return ordered;
  }

  function overrideProfiles() {
    return [...orderedSavedOverrides(), ...newOverrideProfiles()];
  }

  function allProfiles() {
    return [...baseProfiles(), ...overrideProfiles()];
  }

  function findProfile(key = ui.selectedKey) {
    return allProfiles().find((profile) => profileKey(profile) === key) || null;
  }

  function nameFor(profile) {
    if (!profile) return "";
    if (profile.draftId) return profile.name;
    return drafts.overrideNames.get(profileKey(profile)) ?? profile.name ?? profile.symbol ?? "Profile";
  }

  function overrideNameAvailable(name, excludedProfile = null) {
    const normalized = String(name || "").trim().toLowerCase();
    if (!normalized) return false;
    const excludedKey = excludedProfile ? profileKey(excludedProfile) : "";
    return !overrideProfiles().some((profile) => profile !== excludedProfile
      && (!excludedKey || profileKey(profile) !== excludedKey)
      && nameFor(profile).trim().toLowerCase() === normalized
      && !drafts.removedOverrides.has(profileKey(profile)));
  }

  function uniqueOverrideName(preferred) {
    const base = String(preferred || "New override profile").trim() || "New override profile";
    if (overrideNameAvailable(base)) return base;
    let suffix = 2;
    while (!overrideNameAvailable(`${base} ${suffix}`)) suffix += 1;
    return `${base} ${suffix}`;
  }

  function rawFieldMap(profile) {
    const result = {};
    for (const field of data.fields) {
      const raw = valueRaw(profile?.editProfile?.[field.key] ?? profile?.profile?.[field.key]);
      if (raw) result[field.key] = raw;
    }
    return result;
  }

  function fieldDraftMap(profile, create = false) {
    const store = isOverrideProfile(profile) ? drafts.overrideFields : drafts.baseFields;
    const key = profileKey(profile);
    if (!store.has(key) && create) store.set(key, new Map());
    return store.get(key) || null;
  }

  function fieldRaw(profile, fieldKey) {
    if (profile?.draftId) return String(profile.fields?.[fieldKey] ?? "");
    const pending = fieldDraftMap(profile);
    if (pending?.has(fieldKey)) return pending.get(fieldKey);
    return valueRaw(profile?.editProfile?.[fieldKey] ?? profile?.profile?.[fieldKey]);
  }

  function originalFieldRaw(profile, fieldKey) {
    return valueRaw(profile?.editProfile?.[fieldKey] ?? profile?.profile?.[fieldKey]);
  }

  function setField(profile, fieldKey, raw) {
    const next = String(raw ?? "");
    if (profile.draftId) {
      if (next) profile.fields[fieldKey] = next;
      else delete profile.fields[fieldKey];
      return;
    }
    const map = fieldDraftMap(profile, true);
    if (next === originalFieldRaw(profile, fieldKey)) map.delete(fieldKey);
    else map.set(fieldKey, next);
    if (!map.size) (isOverrideProfile(profile) ? drafts.overrideFields : drafts.baseFields).delete(profileKey(profile));
  }

  function sourceTarget(profile) {
    if (profile?.draftId) return cloneTarget(profile.target);
    const modeValue = Number(profile?.targetMode?.value);
    const modeRaw = valueRaw(profile?.targetMode);
    const targetMode = modeValue === 1 || modeRaw.includes("MEMBERS")
      ? "members"
      : (modeValue === 2 || modeRaw.includes("ALL") ? "all" : "disabled");
    return cloneTarget({
      members: profile?.memberSymbols || (profile?.members || []).map((member) => member.symbol),
      match: profile?.match,
      targetMode,
    });
  }

  function targetFor(profile) {
    if (profile?.draftId) return cloneTarget(profile.target);
    return cloneTarget(drafts.overrideTargets.get(profileKey(profile)) || sourceTarget(profile));
  }

  function setTarget(profile, target) {
    const normalized = cloneTarget(target);
    normalized.match.species = DEFAULT_MATCH.species;
    if (normalized.targetMode === "members" && !normalized.members.length) normalized.targetMode = "disabled";
    if (profile.draftId) {
      profile.target = normalized;
      return;
    }
    const saved = sourceTarget(profile);
    if (JSON.stringify(normalized) === JSON.stringify(saved)) drafts.overrideTargets.delete(profileKey(profile));
    else drafts.overrideTargets.set(profileKey(profile), normalized);
  }

  function baseByIndex(index) {
    return baseProfiles().find((profile) => String(profile.index) === String(index)) || null;
  }

  function originalBaseForSpecies(symbol) {
    const assignment = data.assignments.find((item) => item?.species?.symbol === symbol);
    return baseByIndex(assignment?.behaviorClass?.value);
  }

  function pendingBaseKeyForSpecies(symbol) {
    return drafts.memberships.get(symbol) || profileKey(originalBaseForSpecies(symbol));
  }

  function membersFor(profile) {
    const key = profileKey(profile);
    return data.assignments.filter((assignment) => pendingBaseKeyForSpecies(assignment?.species?.symbol) === key);
  }

  function setMembership(symbol, targetProfile) {
    const original = originalBaseForSpecies(symbol);
    const targetKey = profileKey(targetProfile);
    if (original && profileKey(original) === targetKey) drafts.memberships.delete(symbol);
    else drafts.memberships.set(symbol, targetKey);
  }

  function speciesEntries() {
    return data.assignments
      .map((assignment) => assignment?.species)
      .filter((species) => species?.symbol && species.symbol !== "SPECIES_NONE");
  }

  function compactLookup(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
  }

  function speciesForInput(value) {
    const needle = compactLookup(value);
    if (!needle) return null;
    const options = [...speciesEntries(), ...(data.speciesOptions || [])];
    return options.find((species) => unique([
      species.symbol,
      species.name,
      ...(species.aliases || []),
    ]).some((candidate) => compactLookup(candidate) === needle)) || null;
  }

  function typeGroupSymbol(typeSymbol) {
    return `OW_WILD_BEHAVIOR_GROUP_TYPE_${String(typeSymbol || "").replace(/^TYPE_/, "")}`;
  }

  function routeSpeciesForPool(pool) {
    if (!pool) return [];
    const liveSymbols = state.controllers?.routes?.speciesSymbolsForPool?.(pool.tableKeys, pool.swarmKeys);
    if (Array.isArray(liveSymbols)) {
      const symbols = new Set(liveSymbols);
      return speciesEntries().filter((species) => symbols.has(species.symbol));
    }
    const symbols = new Set();
    const add = (species, form = 0) => {
      const base = species?.baseSymbol || species?.symbol;
      const option = (data.speciesOptions || []).find((candidate) =>
        (candidate.baseSymbol || candidate.symbol) === base && Number(candidate.form || 0) === Number(form || 0));
      const symbol = option?.symbol || species?.symbol;
      if (symbol && symbol !== "SPECIES_NONE") symbols.add(symbol);
    };
    (data.routes || []).forEach((route) => {
      [...(route.pokemonTables || []), ...(route.slotTables || []), ...(route.headbuttTables || [])]
        .filter((table) => pool.tableKeys.includes(table.key))
        .forEach((table) => (table.slots || []).forEach((slot) => add(slot.species, slot.form)));
      (route.swarms || [])
        .filter((swarm) => pool.swarmKeys.includes(swarm.key))
        .forEach((swarm) => add(swarm.species, swarm.form));
    });
    return speciesEntries().filter((species) => symbols.has(species.symbol));
  }

  function familyEntries() {
    const byBase = new Map();
    speciesEntries().forEach((species) => {
      const base = species.familyBaseSymbol || species.symbol;
      if (!byBase.has(base)) byBase.set(base, []);
      byBase.get(base).push(species);
    });
    return [...byBase.entries()].map(([symbol, members]) => ({
      symbol,
      name: members.find((species) => species.symbol === symbol)?.name || members[0]?.familyBaseName || humanizeRaw(symbol),
      members,
    }));
  }

  function targetOptions(kind) {
    if (kind === "type") return (data.typeOptions || []).map((type) => ({ value: type.symbol, label: type.name }));
    if (kind === "spawnPool") return SPAWN_POOLS.map((pool) => ({ value: pool.raw, label: pool.label }));
    if (kind === "family") return familyEntries().map((family) => ({ value: family.symbol, label: `${family.name} family` }));
    return speciesEntries().map((species) => ({ value: species.symbol, label: species.name }));
  }

  function normalizedTargetValue(kind = ui.targetKind) {
    const options = targetOptions(kind);
    if (options.some((option) => option.value === ui.targetValue)) return ui.targetValue;
    return options[0]?.value || "";
  }

  function targetCandidates(kind = ui.targetKind, value = normalizedTargetValue(kind)) {
    if (kind === "type") {
      return speciesEntries().filter((species) => (species.types || []).some((type) => type.symbol === value));
    }
    if (kind === "spawnPool") {
      return routeSpeciesForPool(SPAWN_POOLS.find((pool) => pool.raw === value));
    }
    if (kind === "family") {
      return familyEntries().find((family) => family.symbol === value)?.members || [];
    }
    const species = speciesEntries().find((entry) => entry.symbol === value);
    return species ? [species] : [];
  }

  function matchCanTargetAssignment(match, assignment) {
    if (!match) return false;
    const pendingBase = findProfile(pendingBaseKeyForSpecies(assignment.species?.symbol));
    const baseSymbol = pendingBase?.symbol || assignment.behaviorClass?.symbol;
    if (match.behaviorClass !== DEFAULT_MATCH.behaviorClass && match.behaviorClass !== baseSymbol) return false;
    if (match.groupMask && match.groupMask !== DEFAULT_MATCH.groupMask && match.groupMask !== "OW_WILD_BEHAVIOR_GROUP_NONE") {
      const dynamicType = (data.typeOptions || []).find((type) => typeGroupSymbol(type.symbol) === match.groupMask);
      if (dynamicType) {
        if (!(assignment.species?.types || []).some((type) => type.symbol === dynamicType.symbol)) return false;
        return true;
      }
      const group = (data.groups || []).find((entry) => entry.group?.symbol === match.groupMask);
      if (!group?.species?.some((species) => species.symbol === assignment.species?.symbol)) return false;
    }
    return true;
  }

  function potentialAssignmentsFor(profile) {
    if (!isOverrideProfile(profile)) return [];
    const target = targetFor(profile);
    if (target.targetMode === "disabled") return [];
    const memberSet = new Set(target.members);
    return data.assignments.filter((assignment) =>
      (target.targetMode === "all" || memberSet.has(assignment.species?.symbol))
      && matchCanTargetAssignment(target.match, assignment));
  }

  function matchingContextFor(profile, assignment) {
    const target = targetFor(profile);
    const match = target.match;
    if (target.targetMode === "disabled" || !matchCanTargetAssignment(match, assignment)) return null;
    const currentLevel = Number(ui.context.level || 1);
    const minimum = match.minLevel === DEFAULT_MATCH.minLevel ? 1 : Number(match.minLevel);
    const maximum = match.maxLevel === DEFAULT_MATCH.maxLevel ? 100 : Number(match.maxLevel);
    return {
      species: assignment.species?.symbol,
      terrain: match.terrain === DEFAULT_MATCH.terrain ? ui.context.terrain : match.terrain,
      level: String(Math.min(maximum, Math.max(minimum, currentLevel))),
      shiny: match.shiny === DEFAULT_MATCH.shiny ? ui.context.shiny : String(match.shiny) === "1",
    };
  }

  function savedOrderKeys() {
    return savedOverrideProfiles().map(profileKey);
  }

  function currentOrderKeys() {
    return orderedSavedOverrides().map(profileKey);
  }

  function orderChanged() {
    return JSON.stringify(currentOrderKeys()) !== JSON.stringify(savedOrderKeys());
  }

  function hasChanges() {
    return Boolean(
      drafts.baseFields.size
      || drafts.overrideFields.size
      || drafts.memberships.size
      || drafts.overrideNames.size
      || drafts.overrideTargets.size
      || drafts.removedOverrides.size
      || drafts.newOverrides.length
      || orderChanged()
    );
  }

  function changeCount() {
    const nestedSize = (store) => [...store.values()].reduce((total, fields) => total + fields.size, 0);
    return nestedSize(drafts.baseFields)
      + nestedSize(drafts.overrideFields)
      + drafts.memberships.size
      + drafts.overrideNames.size
      + drafts.overrideTargets.size
      + drafts.removedOverrides.size
      + drafts.newOverrides.length
      + (orderChanged() ? 1 : 0);
  }

  function signalDirty() {
    const dirty = hasChanges();
    state.profileDirty = dirty;
    state.selectedProfileKey = ui.selectedKey;
    markDirty();
  }

  function fieldLabel(fieldKey) {
    return data.fields.find((field) => field.key === fieldKey)?.label || humanizeRaw(fieldKey);
  }

  function effectiveFieldCandidates(profile, fieldKey) {
    const ownValue = fieldRaw(profile, fieldKey);
    if (ownValue || !isOverrideProfile(profile)) return ownValue ? [ownValue] : [];
    const baseKeys = new Set(potentialAssignmentsFor(profile)
      .map((assignment) => pendingBaseKeyForSpecies(assignment?.species?.symbol))
      .filter(Boolean));
    return unique([...baseKeys].map((key) => fieldRaw(findProfile(key), fieldKey)).filter(Boolean));
  }

  function canUseRamLocomotion(profile) {
    return effectiveFieldCandidates(profile, "chillAction").includes(RAM_LOCOMOTION);
  }

  function fieldLabelForProfile(profile, fieldKey) {
    if (fieldKey !== "ramMaxSpeed") return fieldLabel(fieldKey);
    const locomotion = effectiveFieldCandidates(profile, "chillAction");
    const usesRam = locomotion.includes(RAM_LOCOMOTION);
    const usesChain = locomotion.some((raw) => raw !== RAM_LOCOMOTION);
    if (usesRam && usesChain) return "RAM speed / chain pause";
    return usesRam ? "RAM max speed" : "Chain pause";
  }

  function fieldOptions(fieldKey, currentRaw = "", profile = null) {
    const options = [...(data.editOptions?.[fieldKey] || [])];
    const usesRam = profile && canUseRamLocomotion(profile);
    if (fieldKey === "ramMaxSpeed" && !usesRam) {
      for (let value = 0; value <= 255; value += 1) {
        const raw = String(value);
        if (!options.some((option) => valueRaw(option) === raw)) options.push({ raw, label: raw, value });
      }
    }
    if (currentRaw && !options.some((option) => valueRaw(option) === currentRaw)) {
      options.push({ raw: currentRaw, label: humanizeRaw(currentRaw) });
    }
    return options;
  }

  function profileSearchText(profile) {
    const assignments = isOverrideProfile(profile) ? potentialAssignmentsFor(profile) : membersFor(profile);
    const members = assignments.flatMap((item) => [
      item.species?.name,
      item.species?.symbol,
      item.species?.familyBaseName,
      ...(item.species?.types || []).flatMap((type) => [type.name, type.symbol]),
      ...(item.groups || []),
    ]);
    const targetValues = isOverrideProfile(profile) ? Object.values(targetFor(profile).match).map(humanizeRaw) : [];
    const fields = data.fields.flatMap((field) => [field.label, fieldRaw(profile, field.key), valueLabel(profile?.profile?.[field.key])]);
    const rules = (profile.classRules || []).flatMap((rule) => [rule.summary, rule.className]);
    const primitives = Object.values(profile.primitives || {}).flatMap((primitive) => [valueRaw(primitive), valueLabel(primitive)]);
    return [nameFor(profile), profile.symbol, profile.summary, ...members, ...targetValues, ...fields, ...rules, ...primitives]
      .filter(Boolean).join(" ").toLowerCase();
  }

  function visibleProfiles(profiles, kind) {
    const query = ui.search.trim().toLowerCase();
    if (ui.kind !== "all" && ui.kind !== kind) return [];
    return profiles.filter((profile) => !query || profileSearchText(profile).includes(query));
  }

  function filtered() {
    return Boolean(ui.search.trim() || ui.kind !== "all");
  }

  function profilePreviewSpecies(profile, override = false, limit = 20) {
    let candidates;
    if (override) {
      const target = targetFor(profile);
      if (target.targetMode === "disabled") {
        candidates = [];
      } else if (target.targetMode === "all") {
        candidates = potentialAssignmentsFor(profile).map((assignment) => assignment.species).filter(Boolean);
      } else {
        const bySymbol = new Map(speciesEntries().map((species) => [species.symbol, species]));
        candidates = target.members.map((symbol) => bySymbol.get(symbol)).filter(Boolean);
      }
    } else {
      candidates = membersFor(profile).map((assignment) => assignment.species).filter(Boolean);
    }
    return [...new Map(candidates.map((species) => [species.symbol, species])).values()]
      .filter((species) => species.iconUrl)
      .slice(0, limit);
  }

  function renderProfileRow(profile, index, total, override = false) {
    const key = profileKey(profile);
    const selected = key === ui.selectedKey;
    const removed = drafts.removedOverrides.has(key);
    const changed = profile.draftId
      || fieldDraftMap(profile)?.size
      || drafts.overrideNames.has(key)
      || drafts.overrideTargets.has(key)
      || removed;
    const overrideTarget = override ? targetFor(profile) : null;
    const membershipLabel = override
      ? (overrideTarget.targetMode === "all" ? "all matching Pokémon" : `${overrideTarget.members.length} members`)
      : `${membersFor(profile).length} members`;
    const dragEnabled = override && !profile.draftId && !filtered() && !ui.busy;
    const orderControls = override
      ? `<span class="profile-row-drag-handle" role="button" tabindex="${dragEnabled ? "0" : "-1"}" draggable="${dragEnabled}" data-reorder-handle data-profile-key="${escapeHtml(key)}" aria-label="Reorder ${escapeHtml(nameFor(profile))}" title="${dragEnabled ? "Drag or use keyboard controls" : "Clear filters to reorder"}">⋮⋮</span>`
      : "";
    const previewSpecies = profilePreviewSpecies(profile, override);
    const previewIcons = previewSpecies.length ? `
      <span class="pv2-profile-icons" aria-hidden="true">
        ${previewSpecies.map((species) => `<img src="${escapeHtml(species.iconUrl)}" alt="" width="16" height="16" loading="lazy" decoding="async" draggable="false">`).join("")}
      </span>` : "";
    return `
      <li class="profile-row pv2-profile-row${selected ? " is-active is-selected" : ""}${removed ? " is-removed" : ""}${changed ? " is-changed" : ""}${override ? " override-profile" : ""}" data-profile-row data-profile-key="${escapeHtml(key)}">
        ${orderControls}
        <button class="profile-select pv2-profile-select" type="button" data-action="select-profile" data-profile-key="${escapeHtml(key)}" aria-current="${selected ? "true" : "false"}">
          <span class="pv2-profile-heading">
            ${override ? `<span class="profile-index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>` : ""}
            <span class="pv2-profile-copy">
              <span class="profile-kind pv2-profile-kind">${override ? (profile.draftId ? "New override" : `Override ${index + 1}`) : (String(profile.index) === String(data.defaultClassIndex) ? "Default base" : "Base profile")}</span>
              <strong>${escapeHtml(nameFor(profile))}</strong>
              <small>${escapeHtml(profile.symbol || "Unsaved layer")} · ${escapeHtml(membershipLabel)}</small>
            </span>
          </span>
          ${previewIcons}
        </button>
        ${removed ? `<button type="button" data-action="delete-profile" data-profile-key="${escapeHtml(key)}">Undo removal</button>` : ""}
      </li>`;
  }

  function renderList() {
    const bases = visibleProfiles(baseProfiles(), "base");
    const overrides = visibleProfiles(overrideProfiles(), "override");
    const filterMessage = filtered() ? `<p class="order-help pv2-filter-note">Reordering is paused while the library is filtered.</p>` : `<p class="order-help">Drag the dotted grip; keyboard reordering is also supported. Later matching layers apply last.</p>`;
    listElement.innerHTML = `
      ${ui.kind !== "override" ? `
        <section class="profile-group profile-group--base pv2-library-group" data-profile-group="base" aria-labelledby="pv2-base-heading">
          <header><span><i aria-hidden="true">B</i><strong id="pv2-base-heading">Base profiles</strong></span><small>${bases.length}</small></header>
          <ul class="profile-list" data-profile-list="base">${bases.map((profile, index) => renderProfileRow(profile, index, bases.length)).join("") || `<li class="empty-state empty-state--small">No base profiles match this filter.</li>`}</ul>
        </section>` : ""}
      ${ui.kind !== "base" ? `
        <section class="profile-group profile-group--overrides pv2-library-group" data-profile-group="overrides" aria-labelledby="pv2-override-heading">
          <header><span><i aria-hidden="true">O</i><strong id="pv2-override-heading">Ordered overrides</strong></span><small>${overrides.length}</small></header>
          ${filterMessage}
          <ol class="profile-list override-deck" data-profile-list="overrides">${overrides.map((profile, index) => renderProfileRow(profile, index, overrides.length, true)).join("") || `<li class="empty-state empty-state--small">No override profiles match this filter.</li>`}</ol>
        </section>` : ""}
    `;
  }

  function renderFieldControl(profile, fieldKey) {
    const raw = fieldRaw(profile, fieldKey);
    const original = originalFieldRaw(profile, fieldKey);
    const changed = profile.draftId ? Boolean(raw) : raw !== original;
    const options = fieldOptions(fieldKey, raw, profile);
    const label = fieldLabelForProfile(profile, fieldKey);
    const override = isOverrideProfile(profile);
    const contextBase = override ? ui.contextResult?.baseProfile?.[fieldKey] : null;
    const hasContextBase = contextBase !== null && contextBase !== undefined && valueRaw(contextBase) !== "";
    const hasOverride = Boolean(raw);
    const state = override
      ? (changed ? "changed" : (hasOverride ? "override" : "inherited"))
      : (changed ? "changed" : "saved");
    const stateLabel = changed
      ? (hasOverride ? "Edited override" : "Will inherit")
      : (hasOverride ? "Overrides base" : "Inherited");
    return `
      <label class="field-row profile-field pv2-field${changed ? " is-changed" : ""}${override && hasOverride ? " is-overridden" : ""}${override && !hasOverride ? " is-inherited" : ""}" data-field-row="${escapeHtml(fieldKey)}" data-field-state="${state}">
        <span class="field-copy pv2-field-copy">
          <strong>${escapeHtml(label)}</strong>
          ${override ? `<small class="pv2-field-meta"><span class="pv2-field-state">${escapeHtml(stateLabel)}</span>${hasContextBase ? `<span class="field-base base-value pv2-field-base">(${escapeHtml(valueLabel(contextBase))})</span>` : ""}</small>` : ""}
        </span>
        <select class="field-control" data-profile-value data-field-key="${escapeHtml(fieldKey)}" aria-label="${escapeHtml(label)}">
          ${override ? `<option value="" ${raw ? "" : "selected"}>Inherit</option>` : ""}
          ${options.map((option) => {
            const optionRaw = valueRaw(option);
            return `<option value="${escapeHtml(optionRaw)}" ${optionRaw === raw ? "selected" : ""}>${escapeHtml(valueLabel(option))}</option>`;
          }).join("")}
        </select>
      </label>`;
  }

  function sectionFields(section, profile) {
    const known = new Set(data.fields.map((field) => field.key));
    const allowed = new Set(data.overrideFieldKeys || []);
    return section.fields.filter((field) => known.has(field) && (!isOverrideProfile(profile) || allowed.has(field)));
  }

  function unsectionedFields(profile) {
    const sectioned = new Set(FIELD_SECTIONS.flatMap((section) => section.fields));
    const allowed = new Set(data.overrideFieldKeys || []);
    return data.fields
      .map((field) => field.key)
      .filter((field) => !sectioned.has(field) && (!isOverrideProfile(profile) || allowed.has(field)));
  }

  function renderFieldSections(profile) {
    const override = isOverrideProfile(profile);
    const sections = FIELD_SECTIONS.map((section) => {
      const fields = sectionFields(section, profile);
      return { ...section, fields, overrideCount: fields.filter((field) => fieldRaw(profile, field)).length };
    });
    const other = unsectionedFields(profile);
    if (other.length) sections.push({
      id: "advanced",
      title: "Advanced",
      hint: "Additional engine-level controls.",
      fields: other,
      overrideCount: other.filter((field) => fieldRaw(profile, field)).length,
    });
    const rendered = sections
      .filter((section) => section.fields.length)
      .map((section) => `
        <details class="field-section pv2-field-section" data-section-id="${section.id}" ${ui.openSections.has(section.id) ? "open" : ""}>
          <summary>
            <span><strong>${escapeHtml(section.title)}</strong><small>${escapeHtml(section.hint)}</small></span>
            <em><span aria-hidden="true">${override ? `${section.overrideCount} / ${section.fields.length}` : section.fields.length}</span><span class="sr-only">${override ? `${section.overrideCount} of ${section.fields.length} fields overridden` : `${section.fields.length} fields`}</span></em>
          </summary>
          ${override && ui.openSections.has(section.id) ? `<div class="pv2-section-toolbar"><span>Only set values override; the rest inherit.</span><button class="pv2-section-inherit" type="button" data-action="clear-section" data-section="${escapeHtml(section.id)}" aria-label="Make all ${escapeHtml(section.title)} values inherit" ${section.overrideCount ? "" : "disabled"}>Inherit all</button></div>` : ""}
          ${ui.openSections.has(section.id) ? `<div class="field-grid profile-fields pv2-field-grid">${section.fields.map((field) => renderFieldControl(profile, field)).join("")}</div>` : ""}
        </details>`).join("");
    return rendered || `<p class="empty-state empty-state--small">No editable fields are available for this profile.</p>`;
  }

  function matchSuggestions(field) {
    const existing = data.classes.map((profile) => valueRaw(profile.match?.[field])).filter(Boolean);
    if (field === "species") return unique([DEFAULT_MATCH.species, ...data.assignments.map((item) => item?.species?.symbol), ...existing]);
    if (field === "terrain") return unique([DEFAULT_MATCH.terrain, ...Object.values(data.labels?.terrains || {}).map((item) => item.symbol), ...existing]);
    if (field === "groupMask") return unique([
      DEFAULT_MATCH.groupMask,
      ...Object.values(data.labels?.groups || {}).map((item) => item.symbol),
      ...(data.typeOptions || []).map((type) => typeGroupSymbol(type.symbol)),
      ...existing,
    ]);
    if (field === "behaviorClass") return unique([DEFAULT_MATCH.behaviorClass, ...baseProfiles().map((profile) => profile.symbol), ...existing]);
    if (field === "shiny") return unique([DEFAULT_MATCH.shiny, "0", "1", ...existing]);
    return unique([DEFAULT_MATCH[field], ...Array.from({ length: 101 }, (_, index) => String(index)), ...existing]);
  }

  function isAnyMatchValue(field, raw) {
    return raw === DEFAULT_MATCH[field]
      || (["minLevel", "maxLevel"].includes(field) && String(raw) === "0")
      || (field === "groupMask" && raw === "OW_WILD_BEHAVIOR_GROUP_NONE");
  }

  function matchErrors(match, allowGlobal = false) {
    const errors = [];
    const allowed = new Map(MATCH_FIELDS.map(([field]) => [field, new Set(matchSuggestions(field))]));
    MATCH_FIELDS.forEach(([field, label]) => {
      const raw = String(match?.[field] || "");
      const numeric = ["minLevel", "maxLevel"].includes(field) && /^\d+$/.test(raw);
      if (!raw || (!allowed.get(field).has(raw) && !numeric)) errors.push(`${label} has an unknown value`);
      if (numeric && Number(raw) > 100) errors.push(`${label} must be between 0 and 100`);
    });
    const min = isAnyMatchValue("minLevel", match.minLevel) ? null : Number(match.minLevel);
    const max = isAnyMatchValue("maxLevel", match.maxLevel) ? null : Number(match.maxLevel);
    if (Number.isFinite(min) && Number.isFinite(max) && min > max) errors.push("Minimum level is greater than maximum level");
    if (!allowGlobal && MATCH_FIELDS.every(([field]) => isAnyMatchValue(field, match[field]))) {
      errors.push("All-Pokémon targeting requires at least one shared condition");
    }
    return errors;
  }

  function profileValidationErrors() {
    const errors = [];
    allProfiles().forEach((profile) => {
      if (!profile.draftId && !fieldDraftMap(profile)?.size) return;
      if (!canUseRamLocomotion(profile)) return;
      const raw = fieldRaw(profile, "ramMaxSpeed");
      const option = (data.editOptions?.ramMaxSpeed || []).find((candidate) => valueRaw(candidate) === raw);
      const numeric = Number(option?.value ?? raw);
      if (Number.isFinite(numeric) && numeric > 4) errors.push(`${nameFor(profile)} RAM max speed must be between 0 and 4`);
    });
    const seenNames = new Set();
    const activeOverrides = overrideProfiles().filter((profile) => !drafts.removedOverrides.has(profileKey(profile)));
    if (!activeOverrides.length) errors.push("Create a replacement before removing the last override profile");
    activeOverrides.forEach((profile) => {
      const name = nameFor(profile).trim().toLowerCase();
      if (!name || seenNames.has(name)) errors.push("Override profile names must be unique");
      seenNames.add(name);
      const shouldValidateTarget = profile.draftId || drafts.overrideTargets.has(profileKey(profile));
      if (!shouldValidateTarget) return;
      const target = targetFor(profile);
      if (target.targetMode === "members" && !target.members.length) errors.push(`${nameFor(profile)} needs at least one member`);
      const knownSpecies = new Set(speciesEntries().map((species) => species.symbol));
      if (target.members.some((symbol) => !knownSpecies.has(symbol))) errors.push(`${nameFor(profile)} contains an unknown Pokémon member`);
      errors.push(...matchErrors(target.match, target.targetMode !== "all"));
    });
    return unique(errors);
  }

  function renderTargetBuilder(profile, mode = "override") {
    const kind = ui.targetKind;
    const value = normalizedTargetValue(kind);
    ui.targetValue = value;
    const candidates = targetCandidates(kind, value);
    const targetOptionsHtml = targetOptions(kind).map((option) => `
      <option value="${escapeHtml(option.value)}" ${option.value === value ? "selected" : ""}>${escapeHtml(option.label)}</option>`).join("");
    const assignable = mode === "base"
      ? candidates.filter((species) => pendingBaseKeyForSpecies(species.symbol) !== profileKey(profile))
      : candidates.filter((species) => !targetFor(profile).members.includes(species.symbol));
    const canApply = assignable.length > 0;
    const preview = candidates.slice(0, 14).map((species) => species.iconUrl
      ? `<img src="${escapeHtml(species.iconUrl)}" alt="${escapeHtml(species.name)}" loading="lazy">`
      : `<span>${escapeHtml(species.name?.slice(0, 1) || "?")}</span>`).join("");
    return `
      <section class="pv2-target-builder" aria-label="${mode === "base" ? "Assign profile members" : "Add override members"}">
        <header><div><strong>${mode === "base" ? "Assign a target set" : "Add Pokémon to this profile"}</strong><small>${mode === "base" ? "Move matching Pokémon into this base profile." : "Shortcuts expand to explicit members of this single override layer."}</small></div><em>${assignable.length} available</em></header>
        <div class="pv2-target-controls">
          <label><span>Target kind</span><select data-target-kind>${TARGET_KINDS.map(([key, label]) => `<option value="${key}" ${key === kind ? "selected" : ""}>${label}</option>`).join("")}</select></label>
          <label><span>Target</span><select data-target-value>${targetOptionsHtml}</select></label>
          <button type="button" data-action="add-target" ${canApply ? "" : "disabled"}>${mode === "base" ? `Assign ${assignable.length}` : `Add ${assignable.length}`}</button>
        </div>
        <div class="pv2-target-preview" aria-label="Target preview">${preview || `<small>No Pokémon match this target.</small>`}${candidates.length > 14 ? `<b>+${candidates.length - 14}</b>` : ""}</div>
      </section>`;
  }

  function addTarget(profile) {
    const kind = ui.targetKind;
    const value = normalizedTargetValue(kind);
    if (!value) return;
    if (isOverrideProfile(profile)) {
      const target = targetFor(profile);
      const additions = targetCandidates(kind, value).map((species) => species.symbol);
      const previousCount = target.members.length;
      target.members = unique([...target.members, ...additions]);
      if (target.targetMode === "disabled" && target.members.length) target.targetMode = "members";
      setTarget(profile, target);
      ui.openSections.add("override-target");
      status(`Added ${target.members.length - previousCount} member${target.members.length - previousCount === 1 ? "" : "s"} to ${nameFor(profile)}.`, "warning");
    } else {
      const candidates = targetCandidates(kind, value)
        .filter((species) => pendingBaseKeyForSpecies(species.symbol) !== profileKey(profile));
      candidates.forEach((species) => setMembership(species.symbol, profile));
      status(`Assigned ${candidates.length} Pokémon to ${nameFor(profile)}.`, "warning");
    }
    renderEditor();
    renderList();
    signalDirty();
  }

  function renderOverrideTarget(profile) {
    const target = targetFor(profile);
    const expanded = ui.openSections.has("override-target");
    const conditionFields = MATCH_FIELDS.filter(([field]) => field !== "species");
    const datalists = conditionFields.map(([field]) => `
      <datalist id="pv2-match-${escapeHtml(field)}">${matchSuggestions(field).map((raw) => `<option value="${escapeHtml(raw)}">${escapeHtml(humanizeRaw(raw))}</option>`).join("")}</datalist>`).join("");
    const query = ui.memberQuery.trim().toLowerCase();
    const bySymbol = new Map(speciesEntries().map((species) => [species.symbol, species]));
    const members = target.members.map((symbol) => bySymbol.get(symbol) || { symbol, name: humanizeRaw(symbol) });
    const visibleMembers = members.filter((species) => !query || [
      species.name,
      species.symbol,
      species.familyBaseName,
      ...(species.types || []).flatMap((type) => [type.name, type.symbol]),
    ].filter(Boolean).join(" ").toLowerCase().includes(query)).slice(0, 160);
    const modeLabel = target.targetMode === "all" ? "All matching Pokémon" : (target.targetMode === "disabled" ? "Disabled" : `${members.length} members`);
    const conditionErrors = matchErrors(target.match, target.targetMode !== "all");
    return `
      <details class="membership-section pv2-membership pv2-override-target" data-section-id="override-target" ${expanded ? "open" : ""}>
        <summary><span><strong>Members</strong><small>One member set, evaluated as one override layer.</small></span><em>${escapeHtml(modeLabel)}</em></summary>
        ${expanded ? `<div class="pv2-override-target-body">
          ${renderTargetBuilder(profile, "override")}
          <div class="pv2-target-mode">
            <label><span>Target mode</span><select data-target-mode>
              <option value="disabled" ${target.targetMode === "disabled" ? "selected" : ""}>Disabled</option>
              <option value="members" ${target.targetMode === "members" ? "selected" : ""}>Explicit members</option>
              <option value="all" ${target.targetMode === "all" ? "selected" : ""}>All Pokémon matching shared conditions</option>
            </select></label>
            <small>Changing modes never creates additional backend rules.</small>
          </div>
          ${target.targetMode === "all" ? `<p class="pv2-member-note">This profile targets every Pokémon that passes the shared conditions below. Saved members are retained if you switch back.</p>` : `
            <label class="pv2-member-search"><span>Find current members</span><input type="search" value="${escapeHtml(ui.memberQuery)}" data-member-search placeholder="Name, symbol, family, or type"></label>
            <ul class="member-list pv2-member-list">
              ${visibleMembers.map((species) => `<li><span>${species.iconUrl ? `<img src="${escapeHtml(species.iconUrl)}" alt="" loading="lazy">` : ""}<strong>${escapeHtml(species.name)}</strong><small>${escapeHtml(species.symbol)}</small></span><button type="button" data-action="remove-override-member" data-species="${escapeHtml(species.symbol)}">Remove</button></li>`).join("") || `<li class="empty-state empty-state--small">${members.length ? "No members match this search." : "No members yet. Add Pokémon above to activate member targeting."}</li>`}
            </ul>
            ${members.length > visibleMembers.length ? `<p class="pv2-member-note">Showing ${visibleMembers.length} of ${members.length}. Search to narrow this list.</p>` : ""}
          `}
          <details class="pv2-shared-conditions${conditionErrors.length ? " is-invalid" : ""}" data-section-id="override-conditions" ${ui.openSections.has("override-conditions") || conditionErrors.length ? "open" : ""}>
            <summary><span><strong>Shared conditions</strong><small>These conditions are checked once, together with membership.</small></span><em>${conditionErrors.length ? "Needs attention" : "Optional"}</em></summary>
            <div class="match-grid pv2-match-grid">
              ${conditionFields.map(([field, label]) => `<label><span>${escapeHtml(label)}</span><input data-target-condition="${field}" list="pv2-match-${field}" value="${escapeHtml(target.match[field])}" autocomplete="off"></label>`).join("")}
            </div>
            ${conditionErrors.length ? `<p class="pv2-condition-error">${escapeHtml(conditionErrors[0])}</p>` : `<p class="pv2-member-note">Conditions use AND logic. They narrow this one profile; they do not become separate rules.</p>`}
          </details>
          ${datalists}
        </div>` : ""}
      </details>`;
  }

  function renderMembership(profile) {
    const members = membersFor(profile);
    const isDefault = String(profile.index) === String(data.defaultClassIndex);
    const expanded = ui.openSections.has("membership");
    const query = ui.memberQuery.trim().toLowerCase();
    const visibleMembers = members.filter((assignment) => !query || [
      assignment.species?.name,
      assignment.species?.symbol,
      assignment.species?.familyBaseName,
      ...(assignment.species?.types || []).flatMap((type) => [type.name, type.symbol]),
    ].filter(Boolean).join(" ").toLowerCase().includes(query)).slice(0, 160);
    return `
      <details class="membership-section pv2-membership" data-section-id="membership" ${expanded ? "open" : ""}>
        <summary><span><strong>Membership</strong><small>Assign Pokémon to this base profile.</small></span><em>${members.length}</em></summary>
        ${expanded ? `${renderTargetBuilder(profile, "base")}
        <label class="pv2-member-search"><span>Find current members</span><input type="search" value="${escapeHtml(ui.memberQuery)}" data-member-search placeholder="Name, symbol, family, or type"></label>
        <ul class="member-list pv2-member-list">
          ${visibleMembers.map((assignment) => `<li><span>${assignment.species?.iconUrl ? `<img src="${escapeHtml(assignment.species.iconUrl)}" alt="" loading="lazy">` : ""}<strong>${escapeHtml(assignment.species?.name)}</strong><small>${escapeHtml(assignment.species?.symbol)}</small></span><button type="button" data-action="remove-member" data-species="${escapeHtml(assignment.species?.symbol)}" ${isDefault ? "disabled title=\"Default members cannot be unassigned\"" : ""}>${isDefault ? "Default" : "Move to Default"}</button></li>`).join("") || `<li class="empty-state empty-state--small">No members match this search.</li>`}
        </ul>
        ${members.length > visibleMembers.length ? `<p class="pv2-member-note">Showing ${visibleMembers.length} of ${members.length}. Search to narrow this list.</p>` : ""}
        ` : ""}
      </details>`;
  }

  function renderAffected(profile) {
    const affected = potentialAssignmentsFor(profile);
    const expanded = ui.openSections.has("affected");
    return `
      <details class="membership-section pv2-affected" data-section-id="affected" ${expanded ? "open" : ""}>
        <summary><span><strong>Potential coverage</strong><small>Pokémon that can match this one layer in at least one valid context.</small></span><em>${affected.length}</em></summary>
        ${expanded ? `<ul class="member-list pv2-member-list">
          ${affected.slice(0, 160).map((assignment) => `<li><span>${assignment.species?.iconUrl ? `<img src="${escapeHtml(assignment.species.iconUrl)}" alt="" loading="lazy">` : ""}<strong>${escapeHtml(assignment.species?.name)}</strong><small>${escapeHtml(assignment.species?.symbol)}</small></span><button type="button" data-action="inspect-species" data-species="${escapeHtml(assignment.species?.symbol)}">Resolve match</button></li>`).join("") || `<li class="empty-state empty-state--small">No Pokémon can currently match this layer.</li>`}
        </ul>${affected.length > 160 ? `<p class="pv2-member-note">Showing the first 160 of ${affected.length} possible Pokémon.</p>` : ""}` : ""}
      </details>`;
  }

  function renderEditor() {
    const profile = findProfile();
    if (!profile) {
      editorElement.innerHTML = `<div class="empty-state"><span class="empty-state__glyph" aria-hidden="true">◇</span><h2>Select a profile</h2><p>Choose a base or override profile from the library.</p></div>`;
      return;
    }
    const key = profileKey(profile);
    const override = isOverrideProfile(profile);
    const removed = drafts.removedOverrides.has(key);
    const headerSpecies = profilePreviewSpecies(profile, override, 20);
    const headerIcons = headerSpecies.length ? `
      <span class="pv2-editor-icons" aria-hidden="true">
        ${headerSpecies.map((species) => `<img src="${escapeHtml(species.iconUrl)}" alt="" width="20" height="20" decoding="async" draggable="false">`).join("")}
      </span>` : "";
    const actions = `
      ${!override && String(profile.index) !== String(data.defaultClassIndex) ? `<button type="button" data-action="convert-base-to-override" data-profile-key="${escapeHtml(key)}">Make override</button>` : ""}
      <button type="button" data-action="rename-profile" data-profile-key="${escapeHtml(key)}" ${profile.canRename === false ? "disabled" : ""}>Rename</button>
      <button type="button" data-action="duplicate-profile" data-profile-key="${escapeHtml(key)}">Duplicate</button>
      <button class="is-danger" type="button" data-action="delete-profile" data-profile-key="${escapeHtml(key)}" ${!override && profile.canDelete === false ? "disabled" : ""}>${removed ? "Undo removal" : "Delete"}</button>`;
    editorElement.innerHTML = `
      <header class="inspector-header v2-inspector-header pv2-editor-head">
        <div class="pv2-editor-identity">
          <div class="pv2-editor-title-copy"><p class="eyebrow">${override ? "Ordered override" : "Base profile"}</p><h2>${escapeHtml(nameFor(profile))}</h2><p>${escapeHtml(profile.symbol || "New unsaved override")}</p></div>
          ${headerIcons}
        </div>
        <div class="inspector-actions pv2-editor-actions">${actions}</div>
      </header>
      ${removed ? `<div class="removal-note pv2-removal-note"><strong>Marked for removal.</strong><span>This profile remains visible until the transaction commits.</span></div>` : ""}
      ${override ? `${renderOverrideTarget(profile)}${renderAffected(profile)}` : renderMembership(profile)}
      <section class="profile-field-editor pv2-fields" aria-labelledby="pv2-fields-title">
        <header><div><p class="eyebrow pv2-eyebrow">Focused field editor</p><h3 id="pv2-fields-title">${override ? "Overridden values" : "Profile values"}</h3></div><span>${data.fields.length} available fields</span></header>
        ${renderFieldSections(profile)}
      </section>`;
  }

  function ensureContextDefaults() {
    const symbols = new Set(data.assignments.map((item) => item?.species?.symbol));
    if (!symbols.has(ui.context.species)) ui.context.species = data.assignments[0]?.species?.symbol || "";
    const terrains = Object.values(data.labels?.terrains || {});
    const terrainSymbols = new Set(terrains.map((item) => item.symbol));
    if (!terrainSymbols.has(ui.context.terrain)) {
      ui.context.terrain = terrains.find((item) => /_LAND$/.test(item.symbol))?.symbol || terrains[0]?.symbol || "";
    }
  }

  function renderContextResult() {
    if (ui.contextBusy) return `<div class="empty-state empty-state--small"><h2>Resolving…</h2><p>Reading the saved source layers.</p></div>`;
    if (ui.contextError) return `<div class="empty-state empty-state--small is-error"><h2>Resolution unavailable</h2><p>${escapeHtml(ui.contextError)}</p></div>`;
    const result = ui.contextResult;
    if (!result) return `<div class="empty-state empty-state--small"><span class="scan-grid" aria-hidden="true"></span><h2>Choose a subject</h2><p>Resolve a Pokémon and terrain to preview exact saved order and field provenance.</p></div>`;
    const layers = result.resolverLayers || [];
    const matchedOverrideIndexes = layers
      .map((layer, index) => (layer.kind === "override" && layer.matched ? index : -1))
      .filter((index) => index >= 0);
    const finalMatchedOverrideIndex = matchedOverrideIndexes.at(-1);
    const indexedLayers = layers.map((layer, index) => ({ layer, index }));
    const appliedLayers = indexedLayers.filter(({ layer }) => layer.kind === "base" || layer.matched);
    const skippedLayers = indexedLayers.filter(({ layer }) => layer.kind === "override" && !layer.matched);
    const renderLayer = ({ layer, index }) => `<li class="resolution-layer ${layer.matched ? "is-matched" : "is-skipped"}${index === finalMatchedOverrideIndex ? " is-applied-last" : ""}"><span>${String(index + 1).padStart(2, "0")}</span><div><strong>${escapeHtml(layer.name)}</strong><small>${escapeHtml(layer.summary || layer.kind)}</small></div><em>${index === finalMatchedOverrideIndex ? "applied last" : (layer.matched ? "applied" : "skipped")}</em></li>`;
    const allFields = unique([...Object.keys(result.baseProfile || {}), ...Object.keys(result.resolvedProfile || {})]);
    const changed = allFields.filter((field) => valueRaw(result.baseProfile?.[field]) !== valueRaw(result.resolvedProfile?.[field]));
    const classHits = result.classRuleHits || [];
    const runtimeLayers = result.runtimeLayers || [];
    const normalizations = result.normalizations || [];
    const primitives = Object.entries(result.resolvedPrimitives || {});
    const runtimeChangeCount = runtimeLayers.reduce((total, layer) => total + (layer.changes || []).length, 0);
    return `
      <div class="resolution-result">
        <header class="resolution-summary"><div><small>Resolved subject</small><strong>${escapeHtml(result.context?.species?.name || ui.context.species)} · Lv ${escapeHtml(result.context?.level || ui.context.level)}</strong></div><span class="result-chip">${matchedOverrideIndexes.length} matched</span></header>
        <section><h3>Applied layer order</h3><ol class="resolution-layers">${appliedLayers.map(renderLayer).join("")}</ol>
          ${skippedLayers.length ? `<details class="pv2-skipped-layers"><summary>Skipped layers <small>${skippedLayers.length}</small></summary><ol class="resolution-layers">${skippedLayers.map(renderLayer).join("")}</ol></details>` : ""}
        </section>
        <section><h3>Base → effective by field</h3><ul class="resolution-fields">
          ${changed.map((field) => `<li><strong>${escapeHtml(fieldLabel(field))}</strong><span class="base-value">(${escapeHtml(valueLabel(result.baseProfile?.[field]))})</span><i aria-hidden="true">→</i><b>${escapeHtml(valueLabel(result.resolvedProfile?.[field]))}</b></li>`).join("") || `<li class="pv2-empty">No field changes in this context.</li>`}
        </ul></section>
        <details class="pv2-diagnostics">
          <summary><span>Runtime diagnostics</span><small>${runtimeChangeCount} field writes · ${classHits.length} class match${classHits.length === 1 ? "" : "es"}</small></summary>
          <div class="pv2-diagnostic-stack">
            <section><h4>Class selection</h4><ul class="pv2-diagnostic-list">
              ${classHits.map((hit) => `<li><span>#${escapeHtml(hit.order)}</span><strong>${escapeHtml(hit.summary)}</strong><small>${escapeHtml(hit.className)}</small></li>`).join("") || `<li class="pv2-empty">No class rules matched.</li>`}
            </ul></section>
            <section><h4>Runtime layer writes</h4><ol class="pv2-runtime-layers">
              ${runtimeLayers.map((layer, index) => `<li><header><span>${String(index + 1).padStart(2, "0")}</span><strong>${escapeHtml(layer.label)}</strong><small>${(layer.changes || []).length} fields</small></header>${(layer.changes || []).length ? `<ul>${layer.changes.map((change) => `<li><strong>${escapeHtml(change.label || fieldLabel(change.field))}</strong><span class="base-value">(${escapeHtml(valueLabel(change.before))})</span><i aria-hidden="true">→</i><b>${escapeHtml(valueLabel(change.after))}</b></li>`).join("")}</ul>` : `<p>No runtime writes.</p>`}</li>`).join("") || `<li class="pv2-empty">No runtime layers returned.</li>`}
            </ol></section>
            ${normalizations.length ? `<section><h4>Normalizations</h4><ul class="pv2-diagnostic-list">${normalizations.map((item) => `<li><strong>${escapeHtml(item.label || fieldLabel(item.field))}</strong><small>${escapeHtml(item.reason || item.summary || `${valueLabel(item.before)} → ${valueLabel(item.after)}`)}</small></li>`).join("")}</ul></section>` : ""}
            ${primitives.length ? `<section><h4>Resolved engine primitives</h4><dl class="pv2-primitives">${primitives.map(([key, value]) => `<div><dt>${escapeHtml(humanizeRaw(String(key).replace(/([a-z])([A-Z])/g, "$1_$2")))}</dt><dd>${escapeHtml(valueLabel(value))}</dd></div>`).join("")}</dl></section>` : ""}
          </div>
        </details>
        <details class="pv2-full-profile">
          <summary><span>Full effective profile</span><small>${allFields.length} fields</small></summary>
          <dl>${allFields.map((field) => `<div><dt>${escapeHtml(fieldLabel(field))}</dt><dd>${escapeHtml(valueLabel(result.resolvedProfile?.[field]))}<small>(${escapeHtml(valueLabel(result.baseProfile?.[field]))})</small></dd></div>`).join("")}</dl>
        </details>
      </div>`;
  }

  function renderContextControls() {
    ensureContextDefaults();
    const terrains = Object.values(data.labels?.terrains || {}).sort((left, right) => Number(left.value) - Number(right.value));
    elements.profileContextSpecies.innerHTML = data.assignments.map((assignment) => `<option value="${escapeHtml(assignment.species?.symbol)}" ${assignment.species?.symbol === ui.context.species ? "selected" : ""}>${escapeHtml(assignment.species?.name)}</option>`).join("");
    elements.profileContextTerrain.innerHTML = terrains.map((terrain) => `<option value="${escapeHtml(terrain.symbol)}" ${terrain.symbol === ui.context.terrain ? "selected" : ""}>${escapeHtml(terrain.name)}</option>`).join("");
    elements.profileContextLevel.value = ui.context.level;
    elements.profileContextShiny.checked = ui.context.shiny;
    elements.resolveContext.disabled = ui.contextBusy || !ui.context.species || !ui.context.terrain;
  }

  function renderContext() {
    renderContextControls();
    contextElement.innerHTML = `
      <header class="panel-heading"><span><small>Context scan</small><strong>Resolution</strong></span><span class="result-chip">${ui.contextResult ? "Saved source" : "Not run"}</span></header>
      ${renderContextResult()}`;
  }

  function renderAll() {
    if (ui.destroyed) return;
    if (!ui.selectedKey || !findProfile(ui.selectedKey)) {
      const hinted = allProfiles().find((profile) => nameFor(profile) === ui.selectionHint);
      ui.selectedKey = profileKey(hinted || baseProfiles().find((profile) => String(profile.index) === String(data.defaultClassIndex)) || allProfiles()[0] || {});
    }
    renderList();
    renderEditor();
    renderContext();
    signalDirty();
  }

  function setSelected(key) {
    if (!findProfile(key)) return;
    ui.selectedKey = key;
    ui.selectionHint = nameFor(findProfile(key));
    renderList();
    renderEditor();
    signalDirty();
  }

  function moveOverride(key, delta) {
    if (filtered()) {
      status("Clear search and kind filters before reordering overrides.", "warning");
      return;
    }
    const ordered = orderedSavedOverrides();
    const index = ordered.findIndex((profile) => profileKey(profile) === key);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    const [moved] = ordered.splice(index, 1);
    ordered.splice(target, 0, moved);
    drafts.overrideOrder = ordered.map(profileKey);
    renderList();
    signalDirty();
    announce(`${nameFor(moved)} moved to position ${target + 1} of ${ordered.length}.`);
  }

  function moveOverrideTo(sourceKey, targetKey, after) {
    if (filtered() || sourceKey === targetKey) return;
    const ordered = orderedSavedOverrides();
    const sourceIndex = ordered.findIndex((profile) => profileKey(profile) === sourceKey);
    const targetIndex = ordered.findIndex((profile) => profileKey(profile) === targetKey);
    if (sourceIndex < 0 || targetIndex < 0) return;
    const [moved] = ordered.splice(sourceIndex, 1);
    let insertion = ordered.findIndex((profile) => profileKey(profile) === targetKey);
    if (after) insertion += 1;
    ordered.splice(insertion, 0, moved);
    drafts.overrideOrder = ordered.map(profileKey);
    renderList();
    signalDirty();
    announce(`${nameFor(moved)} moved to position ${insertion + 1} of ${ordered.length}.`);
  }

  async function askConfirmation(message, options = {}) {
    if (typeof confirmAction === "function") {
      return Boolean(await confirmAction({ message, danger: Boolean(options.dangerous), ...options }));
    }
    return globalThis.confirm(message);
  }

  function openDialog({ title, submitLabel = "Save", fields, onSubmit, danger = false }) {
    dialogSubmit = onSubmit;
    dialogElement.innerHTML = `
      <form method="dialog" data-dialog-form>
        <header><p class="pv2-eyebrow">Profile action</p><h2>${escapeHtml(title)}</h2></header>
        <div class="pv2-dialog-fields">${fields}</div>
        <footer><button type="button" data-action="close-dialog">Cancel</button><button class="${danger ? "is-danger" : "is-primary"}" type="submit">${escapeHtml(submitLabel)}</button></footer>
      </form>`;
    if (typeof dialogElement.showModal === "function") dialogElement.showModal();
    else dialogElement.setAttribute("open", "");
    requestAnimationFrame(() => dialogElement.querySelector("input, textarea, select")?.focus());
  }

  function closeDialog() {
    dialogSubmit = null;
    if (typeof dialogElement.close === "function") dialogElement.close();
    else dialogElement.removeAttribute("open");
  }

  function rekeyBaseDraft(oldKey, newKey) {
    if (oldKey === newKey) return;
    if (drafts.baseFields.has(oldKey)) {
      drafts.baseFields.set(newKey, drafts.baseFields.get(oldKey));
      drafts.baseFields.delete(oldKey);
    }
    for (const [species, target] of drafts.memberships) if (target === oldKey) drafts.memberships.set(species, newKey);
    if (ui.selectedKey === oldKey) ui.selectedKey = newKey;
  }

  function rewriteDraftBehaviorClass(oldSymbol, newSymbol) {
    if (!oldSymbol || !newSymbol || oldSymbol === newSymbol) return;
    drafts.overrideTargets.forEach((target, key) => {
      const rewritten = cloneTarget(target);
      if (rewritten.match.behaviorClass === oldSymbol) rewritten.match.behaviorClass = newSymbol;
      drafts.overrideTargets.set(key, rewritten);
    });
    drafts.newOverrides.forEach((draft) => {
      if (draft.target.match.behaviorClass === oldSymbol) draft.target.match.behaviorClass = newSymbol;
    });
  }

  function dropProfileDraft(key) {
    drafts.baseFields.delete(key);
    drafts.overrideFields.delete(key);
    drafts.overrideNames.delete(key);
    drafts.overrideTargets.delete(key);
    drafts.removedOverrides.delete(key);
    drafts.overrideOrder = drafts.overrideOrder.filter((item) => item !== key);
    for (const [species, target] of drafts.memberships) if (target === key) drafts.memberships.delete(species);
  }

  async function manageBaseProfile(payload, currentProfile = null) {
    if (ui.busy) return;
    ui.busy = true;
    status(`${humanizeRaw(payload.action)} profile…`, "busy");
    renderList();
    try {
      const oldKey = currentProfile ? profileKey(currentProfile) : "";
      const oldSymbol = currentProfile?.symbol || "";
      const fallbackSymbol = baseByIndex(data.defaultClassIndex)?.symbol || "OW_WILD_BEHAVIOR_CLASS_DEFAULT";
      const result = await apiPost("/manage-profiles", payload);
      if (payload.action === "rename" && result?.symbol) {
        rekeyBaseDraft(oldKey, `base:${result.symbol}`);
        rewriteDraftBehaviorClass(oldSymbol, result.symbol);
      }
      if (payload.action === "delete") rewriteDraftBehaviorClass(oldSymbol, fallbackSymbol);
      if (payload.action === "delete") dropProfileDraft(oldKey);
      if (typeof state.reloadData === "function") await state.reloadData({ keepStatus: true });
      else refresh(await apiGet("/data.json", { cache: "no-store" }));
      if (result?.symbol) setSelected(`base:${result.symbol}`);
      status(result?.message || "Profile structure saved.", "success");
    } catch (error) {
      status(`Profile action failed: ${error.message}`, "error");
    } finally {
      ui.busy = false;
      renderAll();
    }
  }

  function createBaseDialog() {
    openDialog({
      title: "Create base profile",
      submitLabel: "Create profile",
      fields: `
        <label><span>Name</span><input name="name" required maxlength="80" autocomplete="off"></label>
        <label><span>Initial Pokémon (optional)</span><textarea name="pokemon" rows="4" placeholder="Mankey, Primeape"></textarea><small>Comma or line separated species names/symbols.</small></label>`,
      onSubmit: (form) => {
        const formData = new FormData(form);
        const name = String(formData.get("name") || "").trim();
        const rawPokemon = String(formData.get("pokemon") || "").split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean);
        const resolved = rawPokemon.map(speciesForInput);
        const invalid = rawPokemon.filter((_, index) => !resolved[index]);
        if (invalid.length) {
          status(`Unknown Pokémon: ${invalid.join(", ")}`, "error");
          return;
        }
        const pokemon = unique(resolved.map((species) => species.symbol));
        return manageBaseProfile({ action: "create", name, pokemon });
      },
    });
  }

  function createProfileDialog() {
    openDialog({
      title: "Create profile",
      submitLabel: "Continue",
      fields: `
        <label><span>Profile kind</span><select name="kind"><option value="base">Base profile</option><option value="override">Ordered override</option></select></label>
        <p>Base profiles assign a complete behavior to Pokémon. Each ordered override is one layer with one member set and optional shared conditions.</p>`,
      onSubmit: (form) => {
        const kind = String(new FormData(form).get("kind") || "base");
        if (kind === "override") createOverrideDialog();
        else createBaseDialog();
      },
    });
  }

  function createOverrideDialog(source = null) {
    const suggestedName = uniqueOverrideName(source ? `${nameFor(source)} copy` : "New override profile");
    openDialog({
      title: source ? `Duplicate ${nameFor(source)}` : "Create override profile",
      submitLabel: source ? "Duplicate override" : "Create draft",
      fields: `<label><span>Name</span><input name="name" required maxlength="80" value="${escapeHtml(suggestedName)}" autocomplete="off"></label>`,
      onSubmit: (form) => {
        const name = String(new FormData(form).get("name") || "").trim();
        if (!overrideNameAvailable(name)) {
          status(`An override named ${name} already exists. Names identify layers and must be unique.`, "error");
          return;
        }
        const draft = {
          draftId: createDraftId(),
          name,
          fields: source ? Object.fromEntries(data.fields.map((field) => [field.key, fieldRaw(source, field.key)]).filter(([, raw]) => raw)) : {},
          target: source ? targetFor(source) : { members: [], match: { ...DEFAULT_MATCH }, targetMode: "disabled" },
        };
        drafts.newOverrides.push(draft);
        ui.selectedKey = `draft:${draft.draftId}`;
        ui.selectionHint = name;
        status("Override draft created. Add only the fields it should replace.", "warning");
        renderAll();
      },
    });
  }

  function createOverrideFromBase(profile) {
    if (!profile || isOverrideProfile(profile) || String(profile.index) === String(data.defaultClassIndex)) return;
    const members = membersFor(profile);
    if (!members.length) {
      status(`${nameFor(profile)} has no Pokémon to target.`, "error");
      return;
    }
    const name = uniqueOverrideName(`${nameFor(profile)} override`);
    const fields = {};
    const allowed = new Set(data.overrideFieldKeys || []);
    data.fields.forEach((field) => {
      const raw = fieldRaw(profile, field.key);
      if (allowed.has(field.key) && raw) fields[field.key] = raw;
    });
    const draft = {
      draftId: createDraftId(),
      name,
      fields,
      target: {
        members: members.map((assignment) => assignment.species.symbol),
        match: { ...DEFAULT_MATCH },
        targetMode: "members",
      },
    };
    drafts.newOverrides.push(draft);
    ui.selectedKey = `draft:${draft.draftId}`;
    ui.selectionHint = name;
    ui.openSections.add("override-target");
    renderAll();
    status(`Created ${name} with ${members.length} member targets. The base profile is unchanged.`, "warning");
  }

  function renameDialog(profile) {
    openDialog({
      title: `Rename ${nameFor(profile)}`,
      fields: `<label><span>Name</span><input name="name" required maxlength="80" value="${escapeHtml(nameFor(profile))}" autocomplete="off"></label>`,
      onSubmit: (form) => {
        const name = String(new FormData(form).get("name") || "").trim();
        if (isOverrideProfile(profile)) {
          if (!overrideNameAvailable(name, profile)) {
            status(`An override named ${name} already exists. Names identify layers and must be unique.`, "error");
            return;
          }
          if (profile.draftId) profile.name = name;
          else if (name === profile.name) drafts.overrideNames.delete(profileKey(profile));
          else drafts.overrideNames.set(profileKey(profile), name);
          ui.selectionHint = name;
          renderAll();
          status("Override rename added to the draft transaction.", "warning");
          return;
        }
        return manageBaseProfile({ action: "rename", classIndex: profile.index, name }, profile);
      },
    });
  }

  function duplicateProfile(profile) {
    if (isOverrideProfile(profile)) {
      createOverrideDialog(profile);
      return;
    }
    openDialog({
      title: `Duplicate ${nameFor(profile)}`,
      submitLabel: "Duplicate profile",
      fields: `<label><span>Name</span><input name="name" required maxlength="80" value="${escapeHtml(`${nameFor(profile)} copy`)}" autocomplete="off"></label>`,
      onSubmit: (form) => manageBaseProfile({ action: "duplicate", classIndex: profile.index, name: String(new FormData(form).get("name") || "").trim() }, profile),
    });
  }

  async function deleteProfile(profile) {
    const key = profileKey(profile);
    if (profile.draftId) {
      drafts.newOverrides = drafts.newOverrides.filter((item) => item.draftId !== profile.draftId);
      if (ui.selectedKey === key) ui.selectedKey = "";
      renderAll();
      return;
    }
    if (isOverrideProfile(profile)) {
      if (drafts.removedOverrides.has(key)) drafts.removedOverrides.delete(key);
      else if (await askConfirmation(`Remove ${nameFor(profile)} when changes are saved?`, { dangerous: true, confirmLabel: "Remove override" })) drafts.removedOverrides.add(key);
      renderAll();
      return;
    }
    if (String(profile.index) === String(data.defaultClassIndex) || profile.canDelete === false) return;
    const count = membersFor(profile).length;
    const confirmed = await askConfirmation(`Delete ${nameFor(profile)}? ${count} Pokémon will fall back to Default.`, { dangerous: true, confirmLabel: "Delete profile" });
    if (confirmed) await manageBaseProfile({ action: "delete", classIndex: profile.index }, profile);
  }

  function changeTargetCondition(profile, field, raw) {
    const target = targetFor(profile);
    if (!Object.hasOwn(DEFAULT_MATCH, field) || field === "species") return;
    target.match[field] = String(raw || DEFAULT_MATCH[field]);
    setTarget(profile, target);
    renderList();
    signalDirty();
  }

  async function resolveContext() {
    if (!ui.context.species || !ui.context.terrain || ui.contextBusy) return;
    contextAbortController?.abort();
    contextAbortController = new AbortController();
    ui.contextBusy = true;
    ui.contextError = "";
    renderContext();
    try {
      const query = new URLSearchParams({
        species: ui.context.species,
        terrain: ui.context.terrain,
        level: ui.context.level,
        shiny: ui.context.shiny ? "1" : "0",
      });
      ui.contextResult = typeof api.resolve === "function"
        ? await api.resolve(Object.fromEntries(query), { signal: contextAbortController.signal })
        : await apiGet(`/api/v2/resolve?${query}`, { cache: "no-store", signal: contextAbortController.signal });
      ui.contextError = "";
      renderEditor();
    } catch (error) {
      if (error.name !== "AbortError") ui.contextError = `Could not resolve this context: ${error.message}`;
    } finally {
      ui.contextBusy = false;
      contextAbortController = null;
      renderContext();
    }
  }

  function onClick(event) {
    const target = event.target.closest("[data-action]");
    if (!target || !root.contains(target)) return;
    const action = target.dataset.action;
    const key = target.dataset.profileKey || ui.selectedKey;
    const profile = findProfile(key);
    if (action === "select-profile") setSelected(key);
    else if (action === "move-up") moveOverride(key, -1);
    else if (action === "move-down") moveOverride(key, 1);
    else if (action === "create-base") createBaseDialog();
    else if (action === "create-override") createOverrideDialog();
    else if (action === "new-profile") createProfileDialog();
    else if (action === "convert-base-to-override" && profile) createOverrideFromBase(profile);
    else if (action === "rename-profile" && profile) renameDialog(profile);
    else if (action === "duplicate-profile" && profile) duplicateProfile(profile);
    else if (action === "delete-profile" && profile) deleteProfile(profile);
    else if (action === "close-dialog") closeDialog();
    else if (action === "add-target" && profile) addTarget(profile);
    else if (action === "inspect-species") {
      const assignment = data.assignments.find((item) => item.species?.symbol === target.dataset.species);
      const context = assignment && profile ? matchingContextFor(profile, assignment) : null;
      if (context) Object.assign(ui.context, context);
      else ui.context.species = target.dataset.species;
      renderContextControls();
      resolveContext();
    }
    else if (action === "clear-section" && profile) {
      event.preventDefault();
      event.stopPropagation();
      const section = FIELD_SECTIONS.find((candidate) => candidate.id === target.dataset.section);
      const fields = section ? sectionFields(section, profile) : (target.dataset.section === "advanced" ? unsectionedFields(profile) : []);
      const clearedCount = fields.filter((field) => fieldRaw(profile, field)).length;
      fields.forEach((field) => setField(profile, field, ""));
      renderEditor(); renderList(); signalDirty();
      editorElement.querySelector(`[data-section-id="${CSS.escape(target.dataset.section)}"] > summary`)?.focus({ preventScroll: true });
      announce(`${section?.title || "Advanced"}: ${clearedCount} override value${clearedCount === 1 ? "" : "s"} will inherit after saving.`);
    }
    else if (action === "remove-override-member" && profile) {
      const overrideTarget = targetFor(profile);
      overrideTarget.members = overrideTarget.members.filter((symbol) => symbol !== target.dataset.species);
      if (!overrideTarget.members.length && overrideTarget.targetMode === "members") overrideTarget.targetMode = "disabled";
      setTarget(profile, overrideTarget); renderEditor(); renderList(); signalDirty();
    } else if (action === "add-member" && profile) {
      const symbol = editorElement.querySelector("[data-member-select]")?.value;
      if (symbol) setMembership(symbol, profile);
      renderEditor(); renderList(); signalDirty();
    } else if (action === "remove-member" && profile) {
      const fallback = baseByIndex(data.defaultClassIndex);
      if (fallback) setMembership(target.dataset.species, fallback);
      renderEditor(); renderList(); signalDirty();
    } else if (action === "resolve-context") resolveContext();
  }

  function onInput(event) {
    if (event.target === elements.profileSearch) {
      ui.search = event.target.value;
      renderList();
    } else if (event.target.matches("[data-member-search]")) {
      ui.memberQuery = event.target.value;
      const profile = findProfile();
      if (profile) {
        renderEditor();
        const input = editorElement.querySelector("[data-member-search]");
        input?.focus();
        input?.setSelectionRange(ui.memberQuery.length, ui.memberQuery.length);
      }
    }
  }

  function onChange(event) {
    const profile = findProfile();
    if (event.target === elements.profileKindFilter) {
      ui.kind = event.target.value;
      renderList();
      return;
    }
    if (event.target.matches("[data-target-kind]")) {
      ui.targetKind = event.target.value;
      ui.targetValue = "";
      renderEditor();
      return;
    }
    if (event.target.matches("[data-target-value]")) {
      ui.targetValue = event.target.value;
      renderEditor();
      return;
    }
    if (event.target.matches("[data-profile-value]") && profile) {
      const fieldKey = event.target.dataset.fieldKey;
      setField(profile, fieldKey, event.target.value);
      renderEditor(); renderList(); signalDirty();
      editorElement.querySelector(`[data-profile-value][data-field-key="${CSS.escape(fieldKey)}"]`)?.focus({ preventScroll: true });
      return;
    }
    if (event.target.matches("[data-target-mode]") && profile) {
      const target = targetFor(profile);
      target.targetMode = event.target.value;
      setTarget(profile, target);
      renderEditor(); renderList(); signalDirty();
      return;
    }
    if (event.target.matches("[data-target-condition]") && profile) {
      changeTargetCondition(profile, event.target.dataset.targetCondition, event.target.value);
      renderEditor();
      return;
    }
    if (event.target === elements.profileContextSpecies) ui.context.species = event.target.value;
    else if (event.target === elements.profileContextTerrain) ui.context.terrain = event.target.value;
    else if (event.target === elements.profileContextLevel) ui.context.level = event.target.value;
    else if (event.target === elements.profileContextShiny) ui.context.shiny = event.target.checked;
  }

  function onToggle(event) {
    const section = event.target.closest("[data-section-id]");
    if (!section) return;
    const wasOpen = ui.openSections.has(section.dataset.sectionId);
    if (section.open) {
      ui.openSections.add(section.dataset.sectionId);
      const rendersOnOpen = ["membership", "affected", "override-target", "advanced"].includes(section.dataset.sectionId)
        || FIELD_SECTIONS.some((candidate) => candidate.id === section.dataset.sectionId);
      if (!wasOpen && rendersOnOpen) {
        const sectionId = section.dataset.sectionId;
        requestAnimationFrame(() => {
          renderEditor();
          editorElement.querySelector(`[data-section-id="${CSS.escape(sectionId)}"] > summary`)?.focus({ preventScroll: true });
        });
      }
    } else {
      ui.openSections.delete(section.dataset.sectionId);
    }
  }

  async function onSubmit(event) {
    if (!event.target.matches("[data-dialog-form]")) return;
    event.preventDefault();
    const submit = dialogSubmit;
    closeDialog();
    if (submit) await submit(event.target);
  }

  function onKeyDown(event) {
    const handle = event.target.closest("[data-reorder-handle]");
    if (!handle || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    moveOverride(handle.dataset.profileKey, event.key === "ArrowUp" ? -1 : 1);
    listElement.querySelector(`[data-reorder-handle][data-profile-key="${CSS.escape(handle.dataset.profileKey)}"]`)?.focus();
  }

  function onDragStart(event) {
    const handle = event.target.closest("[data-reorder-handle]");
    if (!handle || filtered()) return;
    ui.draggedKey = handle.dataset.profileKey;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", ui.draggedKey);
    handle.closest("[data-profile-row]")?.classList.add("is-dragging");
  }

  function onDragOver(event) {
    const row = event.target.closest("[data-profile-row]");
    if (!row?.classList.contains("override-profile") || !ui.draggedKey || row.dataset.profileKey === ui.draggedKey) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    listElement.querySelectorAll(".is-drop-before, .is-drop-after").forEach((item) => item.classList.remove("is-drop-before", "is-drop-after"));
    const rect = row.getBoundingClientRect();
    row.classList.add(event.clientY < rect.top + rect.height / 2 ? "is-drop-before" : "is-drop-after");
  }

  function onDrop(event) {
    const row = event.target.closest("[data-profile-row]");
    if (!row?.classList.contains("override-profile") || !ui.draggedKey) return;
    event.preventDefault();
    const rect = row.getBoundingClientRect();
    moveOverrideTo(ui.draggedKey, row.dataset.profileKey, event.clientY >= rect.top + rect.height / 2);
    onDragEnd();
  }

  function onDragEnd() {
    ui.draggedKey = "";
    listElement.querySelectorAll(".is-dragging, .is-drop-before, .is-drop-after").forEach((item) => item.classList.remove("is-dragging", "is-drop-before", "is-drop-after"));
  }

  root.addEventListener("click", onClick);
  root.addEventListener("input", onInput);
  root.addEventListener("change", onChange);
  root.addEventListener("toggle", onToggle, true);
  root.addEventListener("submit", onSubmit);
  root.addEventListener("keydown", onKeyDown);
  root.addEventListener("dragstart", onDragStart);
  root.addEventListener("dragover", onDragOver);
  root.addEventListener("drop", onDrop);
  root.addEventListener("dragend", onDragEnd);

  function overridePayload() {
    const add = [];
    const edit = {};
    const rename = {};
    const replaceTargets = {};
    const remove = new Set();

    for (const profile of savedOverrideProfiles()) {
      const key = profileKey(profile);
      const orders = ordersFor(profile);
      const replacingTarget = drafts.overrideTargets.has(key) && !drafts.removedOverrides.has(key);
      if (drafts.removedOverrides.has(key)) orders.forEach((order) => remove.add(order));
      if (drafts.removedOverrides.has(key)) continue;

      if (replacingTarget) {
        replaceTargets[orders[0]] = targetFor(profile);
      }

      const fieldEdits = drafts.overrideFields.get(key);
      if (fieldEdits?.size) {
        for (const order of orders) edit[order] = Object.fromEntries(fieldEdits);
      }
      if (drafts.overrideNames.has(key)) {
        for (const order of orders) rename[order] = drafts.overrideNames.get(key);
      }
    }

    for (const draft of drafts.newOverrides) {
      add.push({ name: draft.name, fields: { ...draft.fields }, target: cloneTarget(draft.target) });
    }

    const reorder = orderChanged() ? orderedSavedOverrides().map((profile) => ordersFor(profile)) : [];
    const payload = { add, edit, rename, replaceTargets, remove: [...remove], reorder };
    return add.length || Object.keys(edit).length || Object.keys(rename).length || Object.keys(replaceTargets).length || remove.size || reorder.length ? { changes: payload } : null;
  }

  function commitPayload() {
    const profileChanges = {};
    for (const [key, fields] of drafts.baseFields) {
      const profile = baseProfiles().find((item) => profileKey(item) === key);
      if (profile && fields.size) profileChanges[profile.index] = Object.fromEntries(fields);
    }

    const membershipChanges = {};
    for (const [symbol, targetKey] of drafts.memberships) {
      const target = baseProfiles().find((profile) => profileKey(profile) === targetKey);
      const original = originalBaseForSpecies(symbol);
      if (target && (!original || String(target.index) !== String(original.index))) membershipChanges[symbol] = target.index;
    }

    return {
      profiles: Object.keys(profileChanges).length ? { changes: profileChanges } : null,
      profileMemberships: Object.keys(membershipChanges).length ? { changes: membershipChanges } : null,
      profileOverrides: overridePayload(),
    };
  }

  function committedDomains(value) {
    if (!value) return new Set(["profiles", "profileMemberships", "profileOverrides"]);
    if (Array.isArray(value)) return new Set(value);
    if (Array.isArray(value.changedDomains)) return new Set(value.changedDomains);
    if (typeof value === "string") return new Set([value]);
    return new Set(Object.keys(value).filter((key) => value[key]));
  }

  function clearCommitted(committed = null) {
    const domains = committedDomains(committed);
    ui.selectionHint = nameFor(findProfile());
    if (domains.has("profiles")) drafts.baseFields.clear();
    if (domains.has("profileMemberships")) drafts.memberships.clear();
    if (domains.has("profileOverrides")) {
      drafts.overrideFields.clear();
      drafts.overrideNames.clear();
      drafts.overrideTargets.clear();
      drafts.removedOverrides.clear();
      drafts.newOverrides = [];
      drafts.overrideOrder = [];
    }
    renderAll();
  }

  function reset() {
    ui.selectionHint = nameFor(findProfile());
    drafts.baseFields.clear();
    drafts.overrideFields.clear();
    drafts.memberships.clear();
    drafts.overrideNames.clear();
    drafts.overrideTargets.clear();
    drafts.removedOverrides.clear();
    drafts.newOverrides = [];
    drafts.overrideOrder = [];
    status("Profile drafts reset.", "info");
    renderAll();
  }

  function pruneDrafts() {
    const baseKeys = new Set(baseProfiles().map(profileKey));
    const overrideKeys = new Set(savedOverrideProfiles().map(profileKey));
    for (const key of drafts.baseFields.keys()) if (!baseKeys.has(key)) drafts.baseFields.delete(key);
    for (const store of [drafts.overrideFields, drafts.overrideNames, drafts.overrideTargets]) {
      for (const key of store.keys()) if (!overrideKeys.has(key)) store.delete(key);
    }
    for (const key of drafts.removedOverrides) if (!overrideKeys.has(key)) drafts.removedOverrides.delete(key);
    for (const [species, target] of drafts.memberships) {
      if (!baseKeys.has(target) || !data.assignments.some((item) => item.species?.symbol === species)) drafts.memberships.delete(species);
    }
    drafts.overrideOrder = drafts.overrideOrder.filter((key) => overrideKeys.has(key));
  }

  function refresh(nextData) {
    if (!nextData || typeof nextData !== "object") return;
    ui.selectionHint = ui.selectionHint || nameFor(findProfile());
    data = normalizeData(nextData);
    state.profileData = data;
    pruneDrafts();
    ui.contextResult = null;
    ui.contextError = data.profilesAvailable === false ? (data.profileError?.message || "Profiles are unavailable in this source state.") : "";
    renderAll();
  }

  function destroy() {
    if (ui.destroyed) return;
    ui.destroyed = true;
    contextAbortController?.abort();
    root.removeEventListener("click", onClick);
    root.removeEventListener("input", onInput);
    root.removeEventListener("change", onChange);
    root.removeEventListener("toggle", onToggle, true);
    root.removeEventListener("submit", onSubmit);
    root.removeEventListener("keydown", onKeyDown);
    root.removeEventListener("dragstart", onDragStart);
    root.removeEventListener("dragover", onDragOver);
    root.removeEventListener("drop", onDrop);
    root.removeEventListener("dragend", onDragEnd);
    root.classList.remove("profile-controller-ready", "pv2");
    listElement.classList.remove("pv2-profile-list");
    editorElement.classList.remove("pv2-editor");
    contextElement.classList.remove("pv2-context");
    announcerElement.remove();
    dialogElement.remove();
    listElement.replaceChildren();
    editorElement.replaceChildren();
    contextElement.replaceChildren();
  }

  if (data.profilesAvailable === false) {
    ui.contextError = data.profileError?.message || "Profiles are unavailable in this source state.";
  }
  renderAll();

  return Object.freeze({
    hasChanges,
    changeCount,
    hasInvalid: () => profileValidationErrors().length > 0,
    validationCount: () => profileValidationErrors().length,
    validationMessage: () => profileValidationErrors()[0] || "",
    commitPayload,
    clearCommitted,
    reset,
    refresh,
    destroy,
  });
}
