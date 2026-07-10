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
      "profileId", "spawnState", "spawnDestination", "spawnDestinationMinDistance",
      "spawnDestinationMaxDistance", "spawnHopTime", "overworldLimit", "jumpLevel",
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
  return `override:rules:${signature}`;
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
    version: 1,
    baseFields: mapOfMaps(),
    overrideFields: mapOfMaps(),
    memberships: new Map(),
    overrideNames: new Map(),
    overrideMatches: new Map(),
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

function matchesEqual(left, right) {
  return JSON.stringify(left.map(cloneRawMatch)) === JSON.stringify(right.map(cloneRawMatch));
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
  const drafts = state.profileDrafts?.version === 1 ? state.profileDrafts : newDraftStore();
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
      matches: draft.matches,
      speciesCount: 0,
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

  function matchesFor(profile) {
    if (profile?.draftId) return profile.matches;
    const key = profileKey(profile);
    if (drafts.overrideMatches.has(key)) return drafts.overrideMatches.get(key);
    const saved = Array.isArray(profile?.matches) && profile.matches.length ? profile.matches : [profile?.match].filter(Boolean);
    return saved.map(cloneRawMatch);
  }

  function setMatches(profile, matches) {
    const normalized = matches.map(cloneRawMatch);
    if (profile.draftId) {
      profile.matches = normalized;
      return;
    }
    const saved = (Array.isArray(profile.matches) && profile.matches.length ? profile.matches : [profile.match].filter(Boolean)).map(cloneRawMatch);
    if (matchesEqual(normalized, saved)) drafts.overrideMatches.delete(profileKey(profile));
    else drafts.overrideMatches.set(profileKey(profile), normalized);
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
      || drafts.overrideMatches.size
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
      + drafts.overrideMatches.size
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

  function fieldOptions(fieldKey, currentRaw = "") {
    const options = [...(data.editOptions?.[fieldKey] || [])];
    if (currentRaw && !options.some((option) => valueRaw(option) === currentRaw)) {
      options.push({ raw: currentRaw, label: humanizeRaw(currentRaw) });
    }
    return options;
  }

  function profileSearchText(profile) {
    const members = isOverrideProfile(profile) ? [] : membersFor(profile).map((item) => item.species?.name);
    const matches = isOverrideProfile(profile) ? matchesFor(profile).flatMap((match) => Object.values(match).map(humanizeRaw)) : [];
    return [nameFor(profile), profile.symbol, profile.summary, ...members, ...matches].filter(Boolean).join(" ").toLowerCase();
  }

  function visibleProfiles(profiles, kind) {
    const query = ui.search.trim().toLowerCase();
    if (ui.kind !== "all" && ui.kind !== kind) return [];
    return profiles.filter((profile) => !query || profileSearchText(profile).includes(query));
  }

  function filtered() {
    return Boolean(ui.search.trim() || ui.kind !== "all");
  }

  function renderProfileRow(profile, index, total, override = false) {
    const key = profileKey(profile);
    const selected = key === ui.selectedKey;
    const removed = drafts.removedOverrides.has(key);
    const changed = profile.draftId
      || fieldDraftMap(profile)?.size
      || drafts.overrideNames.has(key)
      || drafts.overrideMatches.has(key)
      || removed;
    const memberCount = isOverrideProfile(profile) ? (profile.speciesCount || 0) : membersFor(profile).length;
    const dragEnabled = override && !profile.draftId && !filtered() && !ui.busy;
    const orderControls = override ? `
      <span class="profile-row-order-controls pv2-order-controls" aria-label="Override order">
        <span class="profile-row-drag-handle" role="button" tabindex="${dragEnabled ? "0" : "-1"}" draggable="${dragEnabled}" data-reorder-handle data-profile-key="${escapeHtml(key)}" aria-label="Reorder ${escapeHtml(nameFor(profile))}" title="${dragEnabled ? "Drag or use arrow keys" : "Clear filters to reorder"}">⋮⋮</span>
        <button type="button" data-action="move-up" data-profile-key="${escapeHtml(key)}" ${!dragEnabled || index === 0 ? "disabled" : ""} aria-label="Move earlier">↑</button>
        <button type="button" data-action="move-down" data-profile-key="${escapeHtml(key)}" ${!dragEnabled || index === total - 1 ? "disabled" : ""} aria-label="Move later">↓</button>
      </span>` : "";
    return `
      <li class="profile-row pv2-profile-row${selected ? " is-active is-selected" : ""}${removed ? " is-removed" : ""}${changed ? " is-changed" : ""}${override ? " override-profile" : ""}" data-profile-row data-profile-key="${escapeHtml(key)}">
        ${orderControls}
        ${override ? `<span class="profile-index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>` : ""}
        <button class="profile-select pv2-profile-select" type="button" data-action="select-profile" data-profile-key="${escapeHtml(key)}" aria-current="${selected ? "true" : "false"}">
          <span class="profile-kind pv2-profile-kind">${override ? (profile.draftId ? "New override" : `Override ${index + 1}`) : (String(profile.index) === String(data.defaultClassIndex) ? "Default base" : "Base profile")}</span>
          <strong>${escapeHtml(nameFor(profile))}</strong>
          <small>${escapeHtml(profile.symbol || "Unsaved layer")} · ${memberCount} ${override ? "affected" : "members"}</small>
        </button>
        ${removed ? `<button type="button" data-action="delete-profile" data-profile-key="${escapeHtml(key)}">Undo removal</button>` : ""}
      </li>`;
  }

  function renderList() {
    const bases = visibleProfiles(baseProfiles(), "base");
    const overrides = visibleProfiles(overrideProfiles(), "override");
    const filterMessage = filtered() ? `<p class="order-help pv2-filter-note">Reordering is paused while the library is filtered.</p>` : `<p class="order-help">Drag the numbered grip or use its arrow keys. Later matching layers apply last.</p>`;
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
    const options = fieldOptions(fieldKey, raw);
    const contextBase = isOverrideProfile(profile) ? ui.contextResult?.baseProfile?.[fieldKey] : null;
    return `
      <label class="field-row profile-field pv2-field${changed ? " is-changed" : ""}${isOverrideProfile(profile) ? " is-overridden" : ""}" data-field-row="${escapeHtml(fieldKey)}" data-field-state="${changed ? "changed" : (isOverrideProfile(profile) ? "override" : "saved")}">
        <span class="field-copy pv2-field-copy">
          <strong>${escapeHtml(fieldLabel(fieldKey))}</strong>
          ${isOverrideProfile(profile) ? `<small class="field-base base-value">(${escapeHtml(valueLabel(contextBase || "Resolve a context below"))})</small>` : `<small>${escapeHtml(humanizeRaw(raw))}</small>`}
        </span>
        <select class="field-control" data-profile-value data-field-key="${escapeHtml(fieldKey)}" aria-label="${escapeHtml(fieldLabel(fieldKey))}">
          ${isOverrideProfile(profile) ? `<option value="">Not overridden</option>` : ""}
          ${options.map((option) => {
            const optionRaw = valueRaw(option);
            return `<option value="${escapeHtml(optionRaw)}" ${optionRaw === raw ? "selected" : ""}>${escapeHtml(valueLabel(option))}</option>`;
          }).join("")}
        </select>
        ${isOverrideProfile(profile) ? `<button type="button" data-action="remove-field" data-field="${escapeHtml(fieldKey)}" aria-label="Remove ${escapeHtml(fieldLabel(fieldKey))} override">Remove</button>` : ""}
      </label>`;
  }

  function sectionFields(section, profile) {
    const known = new Set(data.fields.map((field) => field.key));
    const fields = section.fields.filter((field) => known.has(field));
    if (!isOverrideProfile(profile)) return fields;
    return fields.filter((field) => fieldRaw(profile, field));
  }

  function unsectionedFields(profile) {
    const sectioned = new Set(FIELD_SECTIONS.flatMap((section) => section.fields));
    return data.fields
      .map((field) => field.key)
      .filter((field) => !sectioned.has(field) && (!isOverrideProfile(profile) || fieldRaw(profile, field)));
  }

  function renderFieldSections(profile) {
    const sections = FIELD_SECTIONS.map((section) => ({ ...section, activeFields: sectionFields(section, profile) }));
    const other = unsectionedFields(profile);
    if (other.length) sections.push({ id: "advanced", title: "Advanced", hint: "Additional engine-level controls.", activeFields: other });
    const rendered = sections
      .filter((section) => !isOverrideProfile(profile) || section.activeFields.length)
      .map((section) => `
        <details class="field-section pv2-field-section" data-section-id="${section.id}" ${ui.openSections.has(section.id) ? "open" : ""}>
          <summary><span><strong>${escapeHtml(section.title)}</strong><small>${escapeHtml(section.hint)}</small></span><em>${section.activeFields.length}</em></summary>
          <div class="field-grid profile-fields pv2-field-grid">${section.activeFields.map((field) => renderFieldControl(profile, field)).join("")}</div>
        </details>`).join("");
    if (!isOverrideProfile(profile)) return rendered;

    const allowed = new Set(data.overrideFieldKeys || []);
    const inactive = data.fields.filter((field) => allowed.has(field.key) && !fieldRaw(profile, field.key));
    return `
      <div class="add-field-control pv2-add-field">
        <label><span>Add an override field</span><select data-add-field-select><option value="">Choose field…</option>${inactive.map((field) => `<option value="${escapeHtml(field.key)}">${escapeHtml(field.label)}</option>`).join("")}</select></label>
        <button type="button" data-action="add-field" ${inactive.length ? "" : "disabled"}>Add field</button>
      </div>
      ${rendered || `<p class="empty-state empty-state--small">This layer has no fields yet. Add only the values it should replace.</p>`}`;
  }

  function matchSuggestions(field) {
    if (field === "species") return unique([DEFAULT_MATCH.species, ...data.assignments.map((item) => item?.species?.symbol)]);
    if (field === "terrain") return unique([DEFAULT_MATCH.terrain, ...Object.values(data.labels?.terrains || {}).map((item) => item.symbol)]);
    if (field === "groupMask") return unique([DEFAULT_MATCH.groupMask, ...Object.values(data.labels?.groups || {}).map((item) => item.symbol)]);
    if (field === "behaviorClass") return unique([DEFAULT_MATCH.behaviorClass, ...baseProfiles().map((profile) => profile.symbol)]);
    if (field === "shiny") return [DEFAULT_MATCH.shiny, "0", "1"];
    return [DEFAULT_MATCH[field], ...Array.from({ length: 101 }, (_, index) => String(index))];
  }

  function renderMatches(profile) {
    const matches = matchesFor(profile);
    const datalists = MATCH_FIELDS.map(([field]) => `
      <datalist id="pv2-match-${escapeHtml(field)}">${matchSuggestions(field).map((raw) => `<option value="${escapeHtml(raw)}">${escapeHtml(humanizeRaw(raw))}</option>`).join("")}</datalist>`).join("");
    return `
      <details class="match-section pv2-match-section" data-section-id="matches" ${ui.openSections.has("matches") ? "open" : ""}>
        <summary><span><strong>Match rules</strong><small>Each rule targets a context; all rules share this layer's fields.</small></span><em>${matches.length}</em></summary>
        <div class="match-list pv2-match-list">
          ${matches.map((match, matchIndex) => `
            <fieldset class="match-card pv2-match-card">
              <legend>Rule ${matchIndex + 1}</legend>
              <div class="match-grid pv2-match-grid">
                ${MATCH_FIELDS.map(([field, label]) => `
                  <label><span>${escapeHtml(label)}</span><input data-match-index="${matchIndex}" data-match-field="${field}" list="pv2-match-${field}" value="${escapeHtml(match[field])}" autocomplete="off"></label>`).join("")}
              </div>
              <div class="match-actions pv2-match-actions"><small>${escapeHtml(matchSummary(match))}</small><button type="button" data-action="remove-match" data-match-index="${matchIndex}" ${matches.length === 1 ? "disabled" : ""}>Remove rule</button></div>
            </fieldset>`).join("")}
          <button type="button" data-action="add-match">Add match rule</button>
        </div>
        ${datalists}
      </details>`;
  }

  function matchSummary(match) {
    const specific = MATCH_FIELDS
      .map(([field, label]) => [label, match[field]])
      .filter(([, raw]) => raw && !ANY_MATCH_PREFIXES.some((prefix) => raw === prefix || raw.startsWith(prefix)));
    return specific.length ? specific.map(([label, raw]) => `${label}: ${humanizeRaw(raw)}`).join(" · ") : "Matches every context (the backend will require at least one target)";
  }

  function renderMembership(profile) {
    const members = membersFor(profile);
    const memberSymbols = new Set(members.map((item) => item.species?.symbol));
    const available = data.assignments.filter((item) => !memberSymbols.has(item.species?.symbol));
    const isDefault = String(profile.index) === String(data.defaultClassIndex);
    const expanded = ui.openSections.has("membership");
    return `
      <details class="membership-section pv2-membership" data-section-id="membership" ${expanded ? "open" : ""}>
        <summary><span><strong>Membership</strong><small>Assign Pokémon to this base profile.</small></span><em>${members.length}</em></summary>
        ${expanded ? `<div class="member-add pv2-member-add">
          <select data-member-select aria-label="Pokémon to assign"><option value="">Choose Pokémon…</option>${available.map((assignment) => `<option value="${escapeHtml(assignment.species.symbol)}">${escapeHtml(assignment.species.name)}</option>`).join("")}</select>
          <button type="button" data-action="add-member" ${available.length ? "" : "disabled"}>Assign</button>
        </div>
        <ul class="member-list pv2-member-list">
          ${members.map((assignment) => `<li><span>${assignment.species?.iconUrl ? `<img src="${escapeHtml(assignment.species.iconUrl)}" alt="" loading="lazy">` : ""}<strong>${escapeHtml(assignment.species?.name)}</strong><small>${escapeHtml(assignment.species?.symbol)}</small></span><button type="button" data-action="remove-member" data-species="${escapeHtml(assignment.species?.symbol)}" ${isDefault ? "disabled title=\"Default members cannot be unassigned\"" : ""}>${isDefault ? "Default" : "Move to Default"}</button></li>`).join("") || `<li class="empty-state empty-state--small">No Pokémon currently use this profile.</li>`}
        </ul>
        ` : ""}
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
    const actions = `
      <button type="button" data-action="rename-profile" data-profile-key="${escapeHtml(key)}" ${profile.canRename === false ? "disabled" : ""}>Rename</button>
      <button type="button" data-action="duplicate-profile" data-profile-key="${escapeHtml(key)}">Duplicate</button>
      <button class="is-danger" type="button" data-action="delete-profile" data-profile-key="${escapeHtml(key)}" ${!override && profile.canDelete === false ? "disabled" : ""}>${removed ? "Undo removal" : "Delete"}</button>`;
    editorElement.innerHTML = `
      <header class="inspector-header v2-inspector-header pv2-editor-head">
        <div><p class="eyebrow">${override ? "Ordered override" : "Base profile"}</p><h2>${escapeHtml(nameFor(profile))}</h2><p>${escapeHtml(profile.symbol || "New unsaved override")}</p></div>
        <div class="inspector-actions pv2-editor-actions">${actions}</div>
      </header>
      ${removed ? `<div class="removal-note pv2-removal-note"><strong>Marked for removal.</strong><span>This profile remains visible until the transaction commits.</span></div>` : ""}
      ${override ? renderMatches(profile) : renderMembership(profile)}
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
    return `
      <div class="resolution-result">
        <header class="resolution-summary"><div><small>Resolved subject</small><strong>${escapeHtml(result.context?.species?.name || ui.context.species)} · Lv ${escapeHtml(result.context?.level || ui.context.level)}</strong></div><span class="result-chip">${matchedOverrideIndexes.length} matched</span></header>
        <section><h3>Applied layer order</h3><ol class="resolution-layers">${appliedLayers.map(renderLayer).join("")}</ol>
          ${skippedLayers.length ? `<details class="pv2-skipped-layers"><summary>Skipped layers <small>${skippedLayers.length}</small></summary><ol class="resolution-layers">${skippedLayers.map(renderLayer).join("")}</ol></details>` : ""}
        </section>
        <section><h3>Base → effective by field</h3><ul class="resolution-fields">
          ${changed.map((field) => `<li><strong>${escapeHtml(fieldLabel(field))}</strong><span class="base-value">(${escapeHtml(valueLabel(result.baseProfile?.[field]))})</span><i aria-hidden="true">→</i><b>${escapeHtml(valueLabel(result.resolvedProfile?.[field]))}</b></li>`).join("") || `<li class="pv2-empty">No field changes in this context.</li>`}
        </ul></section>
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

  function dropProfileDraft(key) {
    drafts.baseFields.delete(key);
    drafts.overrideFields.delete(key);
    drafts.overrideNames.delete(key);
    drafts.overrideMatches.delete(key);
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
      const result = await apiPost("/manage-profiles", payload);
      if (payload.action === "rename" && result?.symbol) rekeyBaseDraft(oldKey, `base:${result.symbol}`);
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
        const pokemon = String(formData.get("pokemon") || "").split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean);
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
        <p>Base profiles assign a complete behavior to Pokémon. Overrides replace selected fields only when their match rules apply.</p>`,
      onSubmit: (form) => {
        const kind = String(new FormData(form).get("kind") || "base");
        if (kind === "override") createOverrideDialog();
        else createBaseDialog();
      },
    });
  }

  function createOverrideDialog(source = null) {
    openDialog({
      title: source ? `Duplicate ${nameFor(source)}` : "Create override profile",
      submitLabel: source ? "Duplicate override" : "Create draft",
      fields: `<label><span>Name</span><input name="name" required maxlength="80" value="${escapeHtml(source ? `${nameFor(source)} copy` : "New override profile")}" autocomplete="off"></label>`,
      onSubmit: (form) => {
        const name = String(new FormData(form).get("name") || "").trim();
        const defaultSpecies = ui.context.species || data.assignments[0]?.species?.symbol || DEFAULT_MATCH.species;
        const draft = {
          draftId: createDraftId(),
          name,
          fields: source ? Object.fromEntries(data.fields.map((field) => [field.key, fieldRaw(source, field.key)]).filter(([, raw]) => raw)) : {},
          matches: source ? matchesFor(source).map(cloneRawMatch) : [{ ...DEFAULT_MATCH, species: defaultSpecies }],
        };
        drafts.newOverrides.push(draft);
        ui.selectedKey = `draft:${draft.draftId}`;
        ui.selectionHint = name;
        status("Override draft created. Add only the fields it should replace.", "warning");
        renderAll();
      },
    });
  }

  function renameDialog(profile) {
    openDialog({
      title: `Rename ${nameFor(profile)}`,
      fields: `<label><span>Name</span><input name="name" required maxlength="80" value="${escapeHtml(nameFor(profile))}" autocomplete="off"></label>`,
      onSubmit: (form) => {
        const name = String(new FormData(form).get("name") || "").trim();
        if (isOverrideProfile(profile)) {
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

  function addOverrideField(profile) {
    const select = editorElement.querySelector("[data-add-field-select]");
    const field = select?.value;
    if (!field) return;
    const defaultRaw = valueRaw(data.editOptions?.[field]?.[0]);
    if (!defaultRaw) {
      status(`${fieldLabel(field)} has no valid values.`, "error");
      return;
    }
    setField(profile, field, defaultRaw);
    ui.openSections.add(FIELD_SECTIONS.find((section) => section.fields.includes(field))?.id || "advanced");
    renderEditor();
    renderList();
    signalDirty();
  }

  function changeMatch(profile, index, field, raw) {
    const matches = matchesFor(profile).map(cloneRawMatch);
    if (!matches[index]) return;
    matches[index][field] = String(raw || DEFAULT_MATCH[field]);
    setMatches(profile, matches);
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
    else if (action === "rename-profile" && profile) renameDialog(profile);
    else if (action === "duplicate-profile" && profile) duplicateProfile(profile);
    else if (action === "delete-profile" && profile) deleteProfile(profile);
    else if (action === "close-dialog") closeDialog();
    else if (action === "add-field" && profile) addOverrideField(profile);
    else if (action === "remove-field" && profile) {
      setField(profile, target.dataset.field, "");
      renderEditor(); renderList(); signalDirty();
    } else if (action === "add-match" && profile) {
      const matches = matchesFor(profile).map(cloneRawMatch);
      matches.push(cloneRawMatch(matches.at(-1) || { ...DEFAULT_MATCH, species: ui.context.species }));
      setMatches(profile, matches); renderEditor(); renderList(); signalDirty();
    } else if (action === "remove-match" && profile) {
      const matches = matchesFor(profile).map(cloneRawMatch);
      if (matches.length > 1) matches.splice(Number(target.dataset.matchIndex), 1);
      setMatches(profile, matches); renderEditor(); renderList(); signalDirty();
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
    }
  }

  function onChange(event) {
    const profile = findProfile();
    if (event.target === elements.profileKindFilter) {
      ui.kind = event.target.value;
      renderList();
      return;
    }
    if (event.target.matches("[data-profile-value]") && profile) {
      setField(profile, event.target.dataset.fieldKey, event.target.value);
      renderEditor(); renderList(); signalDirty();
      return;
    }
    if (event.target.matches("[data-match-field]") && profile) {
      changeMatch(profile, Number(event.target.dataset.matchIndex), event.target.dataset.matchField, event.target.value);
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
    if (section.open) ui.openSections.add(section.dataset.sectionId);
    else ui.openSections.delete(section.dataset.sectionId);
    if (section.dataset.sectionId === "membership") requestAnimationFrame(renderEditor);
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
    const replaceMatches = {};
    const remove = new Set();

    for (const profile of savedOverrideProfiles()) {
      const key = profileKey(profile);
      const orders = ordersFor(profile);
      const replacingMatches = drafts.overrideMatches.has(key) && !drafts.removedOverrides.has(key);
      if (drafts.removedOverrides.has(key)) orders.forEach((order) => remove.add(order));
      if (drafts.removedOverrides.has(key)) continue;

      if (replacingMatches) {
        replaceMatches[orders[0]] = matchesFor(profile).map(cloneRawMatch);
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
      add.push({ name: draft.name, fields: { ...draft.fields }, matches: draft.matches.map(cloneRawMatch), match: cloneRawMatch(draft.matches[0]) });
    }

    const reorder = orderChanged() ? orderedSavedOverrides().map((profile) => ordersFor(profile)) : [];
    const payload = { add, edit, rename, replaceMatches, remove: [...remove], reorder };
    return add.length || Object.keys(edit).length || Object.keys(rename).length || Object.keys(replaceMatches).length || remove.size || reorder.length ? { changes: payload } : null;
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
      drafts.overrideMatches.clear();
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
    drafts.overrideMatches.clear();
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
    for (const store of [drafts.overrideFields, drafts.overrideNames, drafts.overrideMatches]) {
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
    commitPayload,
    clearCommitted,
    reset,
    refresh,
    destroy,
  });
}
