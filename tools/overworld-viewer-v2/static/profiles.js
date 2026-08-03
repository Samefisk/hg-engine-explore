/* Overworld Viewer V2 — OWBD v40 state-profile editor foundation. */

const GROUP_HELP = Object.freeze({
  behavior: "The single behavior represented by this complete state.",
  locomotion: "How the state moves. This profile has no hidden active or tired branch.",
  target: "What movement follows or avoids.",
  "tiles-surfaces": "Surfaces and jump permissions for this state.",
  "speed-range": "Movement cadence and distance limits.",
  hop: "Hop path and timing.",
  teleport: "Teleport timing.",
  "ram-chain": "RAM acceleration and chained-movement tuning.",
  battle: "Contact and battle behavior.",
  advanced: "Capabilities derived or consumed by specialized movement code.",
});

export function v40ProfileDeckCapability(data) {
  const source = data?.v40BehaviorModelCapability;
  if (source === undefined || source === null) return null;
  if (source === false) return { available: false, reason: "OWBD V40 behavior-model source is unavailable." };
  if (source === true) return { available: true, reason: "" };
  if (typeof source !== "object") return null;
  const available = source.available !== false
    && source.enabled !== false
    && source.readable !== false
    && Number(source.modelVersion || 40) === 40;
  return {
    available,
    reason: String(source.reason || source.message || (available ? "" : "OWBD V40 behavior-model source is unavailable.")),
  };
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function draftId() {
  const value = globalThis.crypto?.randomUUID?.()
    || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `draft:${value}`;
}

function fieldDefault(field) {
  if (field.type === "number" || field.type === "mask") return Number(field.minimum) || 0;
  return Number(field.options?.[0]?.value) || 0;
}

export function createCompleteStateDraft(fields, source = null, preferredName = "New state profile") {
  const values = Object.fromEntries(fields.map((field) => [
    field.key,
    source?.values?.[field.key] ?? fieldDefault(field),
  ]));
  return {
    draftId: draftId(),
    stableId: null,
    name: String(preferredName || "New state profile").trim() || "New state profile",
    descriptiveTags: [...(source?.descriptiveTags || [])],
    values,
    backlinks: [],
    created: true,
  };
}

export function validateCompleteStateProfile(profile, fields) {
  const errors = [];
  if (!String(profile?.name || "").trim()) errors.push({ path: "name", message: "Profile name is required." });
  for (const field of fields) {
    const raw = profile?.values?.[field.key];
    const value = Number(raw);
    if (!Number.isInteger(value)) {
      errors.push({ path: `values.${field.key}`, message: `${field.label} must be a whole number.` });
      continue;
    }
    if (field.type === "number" || field.type === "mask") {
      if (value < field.minimum || value > field.maximum) {
        errors.push({ path: `values.${field.key}`, message: `${field.label} must be ${field.minimum}–${field.maximum}.` });
      }
    } else if (!field.options.some((option) => Number(option.value) === value)) {
      errors.push({ path: `values.${field.key}`, message: `${field.label} has an invalid value.` });
    }
  }
  if (Number(profile?.values?.hopMaxDistance) < Number(profile?.values?.hopMinDistance)) {
    errors.push({ path: "values.hopMaxDistance", message: "Maximum hop distance cannot be below the minimum." });
  }
  return errors;
}

function requestJson(api, path, options = {}) {
  if (typeof api === "function") return api(path, options);
  if (typeof api?.request === "function") return api.request(path, options);
  if (typeof api?.fetch === "function") return api.fetch(path, options);
  if (typeof api?.get === "function") return api.get(path, options);
  throw new TypeError("Profile editor requires an injected read API");
}

export function createProfilesController({
  state = {}, api, elements = {}, setStatus = () => {},
  reportSelection = () => {},
} = {}) {
  const root = elements.profilesView;
  const list = elements.profileLibrary;
  const inspector = elements.profileInspector;
  if (!(root instanceof Element) || !(list instanceof Element) || !(inspector instanceof Element)) {
    throw new TypeError("Profile editor requires its view, library, and inspector elements");
  }

  let dataset = { modelVersion: 40, stateProfiles: [], stateProfileFields: [], groups: [] };
  let saved = [];
  let loading = true;
  let loadError = "";
  let selectedId = String(state.selectedProfileKey || "");
  let search = "";
  let filter = "all";
  let destroyed = false;
  const updates = new Map();
  const created = [];

  elements.profileKindFilter.innerHTML = `
    <option value="all">All states</option>
    <option value="saved">Saved states</option>
    <option value="draft">New drafts</option>`;
  elements.openProfileResolver.hidden = true;
  elements.profileResolverDrawer.hidden = true;
  root.classList.add("profile-controller-ready", "pv2", "v40-state-profiles");

  function idFor(profile) {
    return profile.draftId || `state:${profile.stableId}`;
  }

  function sourceProfile(profile) {
    if (profile?.created) return null;
    return saved.find((item) => item.stableId === profile.stableId) || null;
  }

  function editedSaved() {
    return saved.map((profile) => updates.get(profile.stableId) || profile);
  }

  function profiles() {
    return [...editedSaved(), ...created];
  }

  function selected() {
    return profiles().find((profile) => idFor(profile) === selectedId) || null;
  }

  function ensureUniqueName(preferred) {
    const names = new Set(profiles().map((profile) => profile.name.trim().toLowerCase()));
    const base = String(preferred || "New state profile").trim() || "New state profile";
    if (!names.has(base.toLowerCase())) return base;
    let suffix = 2;
    while (names.has(`${base} ${suffix}`.toLowerCase())) suffix += 1;
    return `${base} ${suffix}`;
  }

  function isChanged(profile) {
    return Boolean(profile?.created || updates.has(profile?.stableId));
  }

  function editable(profile) {
    if (!profile || profile.created) return profile;
    if (!updates.has(profile.stableId)) updates.set(profile.stableId, clone(profile));
    return updates.get(profile.stableId);
  }

  function validationErrors() {
    const errors = [];
    const names = new Map();
    for (const profile of profiles()) {
      errors.push(...validateCompleteStateProfile(profile, dataset.stateProfileFields)
        .map((error) => ({ ...error, profileId: idFor(profile) })));
      const name = profile.name.trim().toLowerCase();
      if (name && names.has(name)) errors.push({
        profileId: idFor(profile), path: "name", message: `Profile name duplicates ${names.get(name)}.`,
      });
      else if (name) names.set(name, profile.name);
    }
    return errors;
  }

  function syncDirty() {
    state.selectedProfileKey = selectedId;
    state.v40BehaviorModelDraft = {
      modelVersion: 40,
      stateProfiles: {
        create: created.map(clone),
        update: [...updates.values()].map(clone),
      },
    };
    // State-profile persistence is introduced with the atomic model writer.
    // Until then these drafts are deliberately local and must not enable the
    // shell's Global Save transaction.
    state.profileDirty = false;
  }

  function visibleProfiles() {
    const query = search.trim().toLowerCase();
    return profiles().filter((profile) => {
      if (filter === "saved" && profile.created) return false;
      if (filter === "draft" && !profile.created) return false;
      if (!query) return true;
      return [profile.name, profile.stableId, ...(profile.descriptiveTags || [])]
        .some((value) => String(value ?? "").toLowerCase().includes(query));
    });
  }

  function renderList() {
    if (loading) {
      list.innerHTML = `<div class="loading-card"><span></span><p>Loading V40 state profiles…</p></div>`;
      return;
    }
    if (loadError) {
      list.innerHTML = `<div class="shell-error-state" role="alert"><strong>State profiles unavailable</strong><p>${escapeHtml(loadError)}</p><button class="button" type="button" data-profile-action="retry">Retry</button></div>`;
      return;
    }
    const visible = visibleProfiles();
    list.innerHTML = `<section class="profile-group v40-profile-group" aria-labelledby="v40ProfilesTitle">
      <header><span><i aria-hidden="true">S</i><strong id="v40ProfilesTitle">Complete states</strong></span><small>${visible.length}</small></header>
      <ul class="profile-list">${visible.map((profile) => `
        <li class="pv2-profile-row ${selectedId === idFor(profile) ? "is-active" : ""} ${isChanged(profile) ? "is-changed" : ""}">
          <button class="pv2-profile-select" type="button" data-profile-id="${escapeHtml(idFor(profile))}">
            <strong>${escapeHtml(profile.name)}</strong>
            <small>${profile.created ? "Local, unpersisted draft" : `ID ${profile.stableId} · Body ${profile.bodyId}`}</small>
          </button>
        </li>`).join("") || `<li class="empty-state empty-state--small"><p>No state profiles match this filter.</p></li>`}
      </ul>
    </section>`;
  }

  function optionHtml(field, current) {
    return field.options.map((option) => `<option value="${option.value}" ${Number(option.value) === Number(current) ? "selected" : ""}>${escapeHtml(option.label)}</option>`).join("");
  }

  function fieldHtml(profile, field) {
    const value = profile.values[field.key];
    const error = validateCompleteStateProfile(profile, dataset.stateProfileFields)
      .find((item) => item.path === `values.${field.key}`);
    const control = field.type === "number" || field.type === "mask"
      ? `<input type="number" inputmode="numeric" min="${field.minimum}" max="${field.maximum}" value="${escapeHtml(value)}" data-state-field="${escapeHtml(field.key)}" ${error ? "aria-invalid=\"true\"" : ""}>`
      : `<select data-state-field="${escapeHtml(field.key)}" ${error ? "aria-invalid=\"true\"" : ""}>${optionHtml(field, value)}</select>`;
    return `<label class="v40-state-field" data-profile-field>
      <span><strong>${escapeHtml(field.label)}</strong>${field.type === "mask" ? `<small>Bit mask</small>` : ""}</span>
      ${control}${error ? `<small class="field-error">${escapeHtml(error.message)}</small>` : ""}
    </label>`;
  }

  function renderInspector() {
    const profile = selected();
    if (!profile) {
      inspector.innerHTML = `<div class="empty-state"><span class="empty-state__glyph" aria-hidden="true">◇</span><h2>Select a complete state</h2><p>Each profile is one runnable state. Create one or duplicate an existing state to begin.</p></div>`;
      return;
    }
    const nameError = validationErrors().find((error) => error.profileId === idFor(profile) && error.path === "name");
    const tagText = (profile.descriptiveTags || []).join(", ");
    const groups = dataset.groups.map((group, index) => {
      const fields = dataset.stateProfileFields.filter((field) => field.group === group.key);
      return `<details class="pv2-field-section v40-field-group" ${index < 4 ? "open" : ""}>
        <summary><span><strong>${escapeHtml(group.label)}</strong><small>${escapeHtml(GROUP_HELP[group.key] || "")}</small></span><b>${fields.length}</b></summary>
        <div class="profile-fields">${fields.map((field) => fieldHtml(profile, field)).join("")}</div>
      </details>`;
    }).join("");
    const hasLocalDrafts = created.length > 0 || updates.size > 0;
    inspector.innerHTML = `<article class="profile-field-editor v40-state-editor" data-selected-profile="${escapeHtml(idFor(profile))}">
      <header class="v40-state-editor__heading">
        <div><span class="eyebrow">One complete state</span><h2>${escapeHtml(profile.name)}</h2></div>
        <div class="v40-state-editor__actions">
          ${hasLocalDrafts ? `<button class="button" type="button" data-profile-action="reset-local">Discard local drafts</button>` : ""}
          <button class="button" type="button" data-profile-action="duplicate">Duplicate state</button>
        </div>
      </header>
      <section class="v40-state-identity" aria-labelledby="stateIdentityTitle">
        <div><span class="eyebrow" id="stateIdentityTitle">${profile.created ? "Local draft identity" : "Stable identity"}</span><strong>${profile.created ? escapeHtml(profile.draftId) : `ID ${profile.stableId}`}</strong><small>${profile.created ? "Local and unpersisted. Global Save does not include this draft yet." : escapeHtml(profile.registryKey || "Runtime catalog identity")}</small></div>
        <label><span>Name</span><input type="text" value="${escapeHtml(profile.name)}" data-state-identity="name" aria-invalid="${nameError ? "true" : "false"}">${nameError ? `<small class="field-error">${escapeHtml(nameError.message)}</small>` : ""}</label>
        <label class="v40-state-tags"><span>Descriptive tags</span><input type="text" value="${escapeHtml(tagText)}" data-state-identity="descriptiveTags" placeholder="bird, air, relaxed"><small>Search and documentation only. Tags never select runtime behavior.</small></label>
      </section>
      ${profile.backlinks?.length ? `<aside class="v40-backlinks"><strong>Used by ${profile.backlinks.length} controller node${profile.backlinks.length === 1 ? "" : "s"}</strong><span>${profile.backlinks.map((item) => `Controller ${item.controllerId} / Node ${item.nodeId}`).join(" · ")}</span></aside>` : ""}
      ${groups}
    </article>`;
  }

  function render() {
    renderList();
    renderInspector();
  }

  function selectProfile(id, { report = true } = {}) {
    if (!profiles().some((profile) => idFor(profile) === id)) return false;
    selectedId = id;
    state.selectedProfileKey = id;
    render();
    if (report) reportSelection({ view: "profiles", selection: id, label: selected()?.name || "" });
    return true;
  }

  function addProfile(source = null) {
    const preferred = source ? `${source.name} copy` : "New state profile";
    const draft = createCompleteStateDraft(dataset.stateProfileFields, source, ensureUniqueName(preferred));
    created.push(draft);
    selectedId = draft.draftId;
    syncDirty();
    render();
    requestAnimationFrame(() => inspector.querySelector("[data-state-identity='name']")?.select());
  }

  function updateIdentity(key, raw) {
    const profile = editable(selected());
    if (!profile) return;
    if (key === "descriptiveTags") {
      profile.descriptiveTags = [...new Set(String(raw).split(",").map((tag) => tag.trim()).filter(Boolean))];
    } else profile[key] = String(raw);
    syncDirty();
    renderList();
  }

  function updateField(key, raw) {
    const profile = editable(selected());
    if (!profile) return;
    profile.values[key] = Number(raw);
    syncDirty();
    renderList();
  }

  function resetLocalDrafts() {
    const previous = selected();
    const previousStableId = previous?.stableId;
    updates.clear();
    created.splice(0);
    selectedId = previousStableId && saved.some((profile) => profile.stableId === previousStableId)
      ? `state:${previousStableId}`
      : (saved[0] ? `state:${saved[0].stableId}` : "");
    syncDirty();
    render();
    setStatus("Local state-profile drafts discarded.", "info");
  }

  async function load() {
    loading = true;
    loadError = "";
    render();
    try {
      const response = await requestJson(api, `/api/v2/behavior-model?ts=${Date.now()}`);
      dataset = response?.data ?? response;
      if (dataset?.modelVersion !== 40 || !Array.isArray(dataset.stateProfiles) || !Array.isArray(dataset.stateProfileFields)) {
        throw new Error("The server did not return an OWBD v40 behavior model.");
      }
      saved = dataset.stateProfiles.map(clone);
      if (!selectedId || !profiles().some((profile) => idFor(profile) === selectedId)) {
        selectedId = profiles()[0] ? idFor(profiles()[0]) : "";
      }
      state.v40BehaviorModel = dataset;
      state.selectedProfileKey = selectedId;
      loading = false;
      render();
    } catch (error) {
      loading = false;
      loadError = String(error?.message || error);
      render();
    }
  }

  function onClick(event) {
    const select = event.target.closest("[data-profile-id]");
    if (select) return void selectProfile(select.dataset.profileId);
    const action = event.target.closest("[data-profile-action]")?.dataset.profileAction;
    if (action === "retry") return void load();
    if (action === "reset-local") return void resetLocalDrafts();
    if (action === "duplicate") return void addProfile(selected());
    if (event.target.closest("[data-action='new-profile']")) return void addProfile();
  }

  function onInput(event) {
    if (event.target === elements.profileSearch) {
      search = event.target.value;
      renderList();
      return;
    }
    if (event.target.matches("[data-state-identity]")) updateIdentity(event.target.dataset.stateIdentity, event.target.value);
    else if (event.target.matches("[data-state-field]")) updateField(event.target.dataset.stateField, event.target.value);
  }

  function onChange(event) {
    if (event.target === elements.profileKindFilter) {
      filter = event.target.value;
      renderList();
      return;
    }
    if (event.target.matches("[data-state-identity]")) {
      updateIdentity(event.target.dataset.stateIdentity, event.target.value);
      renderInspector();
    } else if (event.target.matches("[data-state-field]")) {
      updateField(event.target.dataset.stateField, event.target.value);
      renderInspector();
    }
  }

  root.addEventListener("click", onClick);
  root.addEventListener("input", onInput);
  root.addEventListener("change", onChange);
  load();

  return Object.freeze({
    hasChanges: () => false,
    changeCount: () => 0,
    hasInvalid: () => false,
    validationCount: () => 0,
    validationMessage: () => "",
    focusFirstInvalid: () => inspector.querySelector("[aria-invalid='true']")?.focus(),
    // Task 19 owns the atomic model-transaction writer. The typed draft graph
    // is already exposed on state.v40BehaviorModelDraft for that integration.
    commitPayload: () => ({}),
    clearCommitted: () => { updates.clear(); created.splice(0); syncDirty(); load(); },
    reset: resetLocalDrafts,
    refresh: () => { if (!loading && !created.length && !updates.size) load(); },
    refreshPreservingDrafts: () => load(),
    navigationContext: () => ({ selection: selectedId, label: selected()?.name || "" }),
    restoreSelection: (id) => selectProfile(id, { report: false }),
    behaviorModelDraft: () => clone(state.v40BehaviorModelDraft),
    localValidationErrors: () => clone(validationErrors()),
    destroy: () => {
      if (destroyed) return;
      destroyed = true;
      root.removeEventListener("click", onClick);
      root.removeEventListener("input", onInput);
      root.removeEventListener("change", onChange);
    },
  });
}
