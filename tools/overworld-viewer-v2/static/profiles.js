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

function entityId(entity, prefix) {
  return entity?.draftId || `${prefix}:${entity?.stableId}`;
}

function localNodeId(node) {
  return entityId(node, "node");
}

function localTransitionId(transition) {
  return entityId(transition, "transition");
}

function nodeProfileRef(node) {
  return node?.profileRef ?? node?.profileStableId;
}

export function createControllerDraft({ source = null, profiles = [], transitions = [], policyDefaults = null } = {}) {
  const controllerDraftId = draftId();
  const profileId = profiles[0]?.stableId ?? null;
  const sourceNodes = source?.nodes?.length ? source.nodes : [{
    semanticRoleId: 1, customRoleId: null, profileStableId: profileId,
    base: true, optional: false, hidden: false,
  }];
  const nodeMap = new Map();
  const nodes = sourceNodes.map((node, order) => {
    const copy = { ...clone(node), stableId: null, draftId: draftId(), controllerId: controllerDraftId, order };
    [node.stableId, node.draftId, localNodeId(node)].filter(Boolean).forEach((id) => nodeMap.set(String(id), copy.draftId));
    return copy;
  });
  const transitionIdMap = new Map(transitions.map((transition) => [localTransitionId(transition), draftId()]));
  transitions.forEach((transition) => {
    if (transition.stableId) transitionIdMap.set(String(transition.stableId), transitionIdMap.get(localTransitionId(transition)));
    if (transition.draftId) transitionIdMap.set(String(transition.draftId), transitionIdMap.get(localTransitionId(transition)));
  });
  const definitionMap = new Map();
  for (const transition of transitions) {
    const sourceDefinition = transition.candidateDefinition || {};
    const definitionKey = String(transition.candidateDefinitionId ?? sourceDefinition.stableId ?? sourceDefinition.draftId);
    if (definitionMap.has(definitionKey)) continue;
    const definition = clone(sourceDefinition);
    definition.stableId = null;
    definition.draftId = draftId();
    definition.controllerId = controllerDraftId;
    const mappedNode = nodeMap.get(String(definition.nodeId)) || nodeMap.get(`node:${definition.nodeId}`);
    if (mappedNode) definition.nodeId = mappedNode;
    const mappedRecovery = transitionIdMap.get(String(definition.recoveryTransitionId));
    if (mappedRecovery) definition.recoveryTransitionId = mappedRecovery;
    definitionMap.set(definitionKey, definition);
  }
  const mapDefinitionId = (value) => definitionMap.get(String(value))?.draftId || value;
  const transitionCopies = transitions.map((transition, order) => {
    const copy = clone(transition);
    copy.stableId = null;
    copy.draftId = transitionIdMap.get(localTransitionId(transition));
    copy.order = order;
    const definitionKey = String(transition.candidateDefinitionId ?? transition.candidateDefinition?.stableId ?? transition.candidateDefinition?.draftId);
    copy.candidateDefinition = clone(definitionMap.get(definitionKey));
    copy.candidateDefinitionId = copy.candidateDefinition.draftId;
    copy.controllerIds = [controllerDraftId];
    copy.guards = (copy.guards || []).map((guard) => ({
      ...guard, stableId: null, draftId: draftId(),
      referenceId: nodeMap.get(String(guard.referenceId)) || guard.referenceId,
    }));
    copy.operations = (copy.operations || []).map((operation) => ({
      ...operation, stableId: null, draftId: draftId(),
      definitionId: mapDefinitionId(operation.definitionId),
      replacementDefinitionId: mapDefinitionId(operation.replacementDefinitionId),
      instanceKey: mapDefinitionId(operation.instanceKey),
    }));
    copy.actions = (copy.actions || []).map((action) => ({ ...action, stableId: null, draftId: draftId() }));
    copy.recoveryActions = (copy.recoveryActions || []).map((action) => ({ ...action, stableId: null, draftId: draftId() }));
    copy.created = true;
    return copy;
  });
  return {
    controller: {
      draftId: controllerDraftId,
      stableId: null,
      name: source ? `${source.name} copy` : "New controller",
      nodes,
      baseNodeId: localNodeId(nodes.find((node) => node.base)),
      scalarDefaults: clone(source?.scalarDefaults || Object.fromEntries([
        "alertState", "alertEmote", "alertTime", "alertness", "alertRange",
        "alertChance", "stamina", "restTime",
      ].map((key) => [key, 0]))),
      policyIds: clone(source?.policyIds || policyDefaults || {
        spawnPolicyId: 0, populationPolicyId: 0, hookSetId: 0,
      }),
      transitionIds: transitionCopies.map(localTransitionId),
      created: true,
    },
    transitions: transitionCopies,
  };
}

export function validateControllerDraft(controller, model, transitions = []) {
  const errors = [];
  if (!String(controller?.name || "").trim()) errors.push({ path: "name", message: "Controller name is required." });
  const nodes = controller?.nodes || [];
  if (!nodes.length) errors.push({ path: "nodes", message: "A controller requires at least one bound node." });
  const bases = nodes.filter((node) => node.base);
  if (bases.length !== 1) errors.push({ path: "nodes.base", message: "Exactly one bound node must be the base node." });
  const profileIds = new Set((model?.stateProfiles || []).flatMap((profile) => [profile.stableId, profile.draftId].filter((value) => value !== null && value !== undefined).map(String)));
  const semanticSelectors = new Map();
  const customSelectors = new Map();
  for (const node of nodes) {
    const id = localNodeId(node);
    if (!profileIds.has(String(nodeProfileRef(node)))) errors.push({ path: `nodes.${id}.profileRef`, message: "Select a bound state profile." });
    const role = Number(node.semanticRoleId);
    if (!(model?.semanticRoles || []).some((option) => Number(option.value) === role)) {
      errors.push({ path: `nodes.${id}.semanticRoleId`, message: "Select a semantic role." });
    } else if (role !== 7 && semanticSelectors.has(role)) {
      errors.push({ path: `nodes.${id}.semanticRoleId`, message: "Semantic selectors must be unique within a controller." });
    } else if (role !== 7) semanticSelectors.set(role, id);
    if (role === 7) {
      const customRole = Number(node.customRoleId);
      if (!(model?.customRoles || []).some((option) => Number(option.stableId) === customRole)) {
        errors.push({ path: `nodes.${id}.customRoleId`, message: "Custom nodes require a custom-role identity." });
      } else if (customSelectors.has(customRole)) {
        errors.push({ path: `nodes.${id}.customRoleId`, message: "Custom-role selectors must be unique within a controller." });
      } else customSelectors.set(customRole, id);
    }
  }
  for (const field of model?.controllerScalarFields || []) {
    const value = Number(controller?.scalarDefaults?.[field.key]);
    const valid = Number.isInteger(value) && (field.type === "number"
      ? value >= field.minimum && value <= field.maximum
      : field.options.some((option) => Number(option.value) === value));
    if (!valid) errors.push({ path: `scalarDefaults.${field.key}`, message: `${field.label} is outside its typed domain.` });
  }
  for (const key of ["spawnPolicyId", "populationPolicyId", "hookSetId"]) {
    const catalogKey = ({ spawnPolicyId: "spawnPolicies", populationPolicyId: "populationPolicies", hookSetId: "hookSets" })[key];
    if (!Number.isInteger(Number(controller?.policyIds?.[key]))
        || !(model?.policyCatalog?.[catalogKey] || []).some((policy) => Number(policy.stableId) === Number(controller.policyIds[key]))) {
      errors.push({ path: `policyIds.${key}`, message: `${key} must reference an existing policy.` });
    }
  }
  for (const transition of transitions) {
    const id = localTransitionId(transition);
    if (!(model?.transitionGraph?.triggerOptions || []).some((option) => Number(option.value) === Number(transition.trigger))) {
      errors.push({ path: `transitions.${id}.trigger`, message: "Select a typed transition event." });
    }
    const candidateDefinitions = [
      ...(model?.transitionGraph?.transitions || []).map((item) => item.candidateDefinition),
      ...transitions.map((item) => item.candidateDefinition),
    ];
    if (!candidateDefinitions.some((definition) => String(definition?.stableId) === String(transition.candidateDefinitionId))) {
      if (!candidateDefinitions.some((definition) => String(definition?.draftId) === String(transition.candidateDefinitionId))) {
        errors.push({ path: `transitions.${id}.candidateDefinitionId`, message: "Select an existing typed candidate definition." });
      }
    }
    if (!Number.isInteger(Number(transition.fromRoleMask)) || Number(transition.fromRoleMask) < 1 || Number(transition.fromRoleMask) > 127) {
      errors.push({ path: `transitions.${id}.fromRoleMask`, message: "From-role mask must select at least one semantic role." });
    }
    if (!Number.isInteger(Number(transition.dispatchPriority)) || Number(transition.dispatchPriority) < 1 || Number(transition.dispatchPriority) > 65535) {
      errors.push({ path: `transitions.${id}.dispatchPriority`, message: "Dispatch priority must be 1–65535." });
    }
    const exactNodeId = transition.candidateDefinition?.nodeId;
    if (exactNodeId && !new Set(nodes.flatMap((node) => [node.stableId, node.draftId].filter(Boolean).map(String))).has(String(exactNodeId))) {
      errors.push({ path: `transitions.${id}.candidateDefinition.nodeId`, message: "Exact transition selector references a node outside this controller." });
    }
    const definitionController = transition.candidateDefinition?.controllerId;
    const expectedScope = definitionController
      ? [String(definitionController)]
      : (model?.controllers || []).map((item) => String(item.draftId || item.stableId));
    const actualScope = (transition.controllerIds || []).map(String);
    if (expectedScope.length !== actualScope.length || expectedScope.some((value) => !actualScope.includes(value))) {
      errors.push({ path: `transitions.${id}.controllerIds`, message: "Transition membership must match its candidate-definition controller scope." });
    }
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

  let dataset = { modelVersion: 40, stateProfiles: [], stateProfileFields: [], controllers: [], transitionGraph: { transitions: [] }, groups: [] };
  let saved = [];
  let savedControllers = [];
  let savedTransitions = [];
  let loading = true;
  let loadError = "";
  let selectedId = String(state.selectedProfileKey || "");
  let search = "";
  let filter = "all";
  let mode = state.profileDeckMode === "controllers" ? "controllers" : "states";
  let destroyed = false;
  const updates = new Map();
  const created = [];
  const controllerUpdates = new Map();
  const createdControllers = [];
  const transitionUpdates = new Map();
  const createdTransitions = [];
  const removedTransitionIds = new Set();
  let selectedControllerId = String(state.selectedControllerKey || "");

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

  function controllerIdFor(controller) {
    return entityId(controller, "controller");
  }

  function controllers() {
    return [...savedControllers.map((controller) => controllerUpdates.get(controller.stableId) || controller), ...createdControllers];
  }

  function selectedController() {
    return controllers().find((controller) => controllerIdFor(controller) === selectedControllerId) || null;
  }

  function editableController(controller) {
    if (!controller || controller.created) return controller;
    if (!controllerUpdates.has(controller.stableId)) controllerUpdates.set(controller.stableId, clone(controller));
    return controllerUpdates.get(controller.stableId);
  }

  function transitions() {
    return [
      ...savedTransitions.filter((transition) => !removedTransitionIds.has(transition.stableId))
        .map((transition) => transitionUpdates.get(transition.stableId) || transition),
      ...createdTransitions,
    ];
  }

  function controllerTransitions(controller = selectedController()) {
    if (!controller) return [];
    const id = controllerIdFor(controller);
    return transitions().filter((transition) => (transition.controllerIds || []).map(String).includes(String(controller.stableId || id)))
      .sort((left, right) => Number(left.order) - Number(right.order));
  }

  function editableTransition(transition) {
    if (!transition || transition.created || transition.draftId) return transition;
    if (!transitionUpdates.has(transition.stableId)) transitionUpdates.set(transition.stableId, clone(transition));
    return transitionUpdates.get(transition.stableId);
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
    state.selectedControllerKey = selectedControllerId;
    state.profileDeckMode = mode;
    state.v40BehaviorModelDraft = {
      ...(state.v40BehaviorModelDraft || {}),
      modelVersion: 40,
      stateProfiles: {
        create: created.map(clone),
        update: [...updates.values()].map(clone),
      },
      controllers: {
        create: createdControllers.map(clone),
        update: [...controllerUpdates.values()].map(clone),
      },
      transitions: {
        create: createdTransitions.map(clone),
        update: [...transitionUpdates.values()].map(clone),
        remove: [...removedTransitionIds],
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
    if (mode === "controllers") return void renderControllerList();
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

  function renderControllerList() {
    if (loading) {
      list.innerHTML = `<div class="loading-card"><span></span><p>Loading V40 controllers…</p></div>`;
      return;
    }
    if (loadError) {
      list.innerHTML = `<div class="shell-error-state" role="alert"><strong>Controllers unavailable</strong><p>${escapeHtml(loadError)}</p><button class="button" type="button" data-profile-action="retry">Retry</button></div>`;
      return;
    }
    const query = search.trim().toLowerCase();
    const visible = controllers().filter((controller) => {
      if (filter === "saved" && controller.created) return false;
      if (filter === "draft" && !controller.created) return false;
      return !query || [controller.name, controller.stableId, controller.registryKey]
        .some((value) => String(value ?? "").toLowerCase().includes(query));
    });
    list.innerHTML = `<section class="profile-group v40-profile-group" aria-labelledby="v40ControllersTitle">
      <header><span><i aria-hidden="true">C</i><strong id="v40ControllersTitle">Controllers</strong></span><small>${visible.length}</small></header>
      <ul class="profile-list">${visible.map((controller) => `
        <li class="pv2-profile-row ${selectedControllerId === controllerIdFor(controller) ? "is-active" : ""} ${controller.created || controllerUpdates.has(controller.stableId) ? "is-changed" : ""}">
          <button class="pv2-profile-select" type="button" data-controller-id="${escapeHtml(controllerIdFor(controller))}">
            <strong>${escapeHtml(controller.name)}</strong>
            <small>${controller.created ? "Local, unpersisted draft" : `ID ${controller.stableId}`} · ${controller.nodes.length} nodes</small>
          </button>
        </li>`).join("") || `<li class="empty-state empty-state--small"><p>No controllers match this filter.</p></li>`}
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
    if (mode === "controllers") return void renderControllerInspector();
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

  function selectOptions(options, current, valueKey = "value", labelKey = "label") {
    return options.map((option) => `<option value="${escapeHtml(option[valueKey])}" ${String(option[valueKey]) === String(current) ? "selected" : ""}>${escapeHtml(option[labelKey])}</option>`).join("");
  }

  function nodeRoleOptions(node, controller) {
    const used = new Set(controller.nodes.filter((other) => other !== node && Number(other.semanticRoleId) !== 7).map((other) => Number(other.semanticRoleId)));
    return (dataset.semanticRoles || []).map((option) => `<option value="${option.value}" ${Number(option.value) === Number(node.semanticRoleId) ? "selected" : ""} ${Number(option.value) !== 7 && used.has(Number(option.value)) ? "disabled" : ""}>${escapeHtml(option.label)}</option>`).join("");
  }

  function customRoleOptions(node, controller) {
    const used = new Set(controller.nodes.filter((other) => other !== node && Number(other.semanticRoleId) === 7).map((other) => Number(other.customRoleId)));
    return (dataset.customRoles || []).map((option) => `<option value="${option.stableId}" ${Number(option.stableId) === Number(node.customRoleId) ? "selected" : ""} ${used.has(Number(option.stableId)) ? "disabled" : ""}>${escapeHtml(option.name)}</option>`).join("");
  }

  function renderControllerInspector() {
    const controller = selectedController();
    if (!controller) {
      inspector.innerHTML = `<div class="empty-state"><span class="empty-state__glyph" aria-hidden="true">◇</span><h2>Select a controller</h2><p>Controllers bind complete state profiles to unique semantic nodes and own their transition roster.</p></div>`;
      return;
    }
    const localTransitions = controllerTransitions(controller);
    const errors = validateControllerDraft(controller, { ...dataset, stateProfiles: profiles(), controllers: controllers() }, localTransitions);
    const profileOptions = profiles().map((profile) => ({
      value: profile.draftId || profile.stableId,
      label: `${profile.name} · ${profile.draftId ? "draft" : profile.stableId}`,
    }));
    const definitionOptions = [...new Map((dataset.transitionGraph?.transitions || []).map((transition) => [
      transition.candidateDefinitionId,
      { value: transition.candidateDefinitionId, label: `Definition ${transition.candidateDefinitionId} · role ${transition.candidateDefinition?.semanticRoleId || "exact"}` },
    ]).concat(localTransitions.map((transition) => [
      transition.candidateDefinitionId,
      { value: transition.candidateDefinitionId, label: `${String(transition.candidateDefinitionId).startsWith("draft:") ? "Draft" : "Definition"} ${transition.candidateDefinitionId}` },
    ]))).values()];
    const ownerOptions = [...new Set((dataset.transitionGraph?.transitions || []).map((transition) => transition.ownerId))]
      .map((ownerId) => ({ value: ownerId, label: `Owner ${ownerId}` }));
    const scalarFields = (dataset.controllerScalarFields || []).map((field) => {
      const value = controller.scalarDefaults[field.key];
      const control = field.type === "number"
        ? `<input type="number" min="${field.minimum}" max="${field.maximum}" value="${value}" data-controller-scalar="${field.key}">`
        : `<select data-controller-scalar="${field.key}">${selectOptions(field.options, value)}</select>`;
      return `<label class="v40-state-field"><span><strong>${escapeHtml(field.label)}</strong></span>${control}</label>`;
    }).join("");
    const policyControls = Object.entries({
      spawnPolicyId: "spawnPolicies", populationPolicyId: "populationPolicies", hookSetId: "hookSets",
    }).map(([key, catalogKey]) => `<label class="v40-state-field"><span><strong>${escapeHtml(key.replace(/Id$/, " ID"))}</strong></span><select data-controller-policy="${key}">${selectOptions(dataset.policyCatalog?.[catalogKey] || [], controller.policyIds[key], "stableId", "name")}</select></label>`).join("");
    const nodeRows = controller.nodes.map((node, index) => {
      const nodeId = localNodeId(node);
      const usageCount = localTransitions.filter((transition) => String(transition.candidateDefinition?.nodeId || "") === String(node.stableId || nodeId)).length;
      return `<tr data-controller-node="${escapeHtml(nodeId)}">
        <td><input type="radio" name="controller-base-node" data-node-field="base" data-node-id="${escapeHtml(nodeId)}" ${node.base ? "checked" : ""} aria-label="Use node ${index + 1} as base"></td>
        <td><strong>${node.draftId ? escapeHtml(node.draftId) : node.stableId}</strong><small>${usageCount} transition backlink${usageCount === 1 ? "" : "s"}</small></td>
        <td><select data-node-field="semanticRoleId" data-node-id="${escapeHtml(nodeId)}">${nodeRoleOptions(node, controller)}</select>${Number(node.semanticRoleId) === 7 ? `<select data-node-field="customRoleId" data-node-id="${escapeHtml(nodeId)}" aria-label="Custom role">${customRoleOptions(node, controller)}</select>` : ""}</td>
        <td><select data-node-field="profileRef" data-node-id="${escapeHtml(nodeId)}">${selectOptions(profileOptions, nodeProfileRef(node))}</select></td>
        <td class="v40-row-actions"><button type="button" data-node-action="up" data-node-id="${escapeHtml(nodeId)}" ${index === 0 ? "disabled" : ""} aria-label="Move node up">↑</button><button type="button" data-node-action="down" data-node-id="${escapeHtml(nodeId)}" ${index === controller.nodes.length - 1 ? "disabled" : ""} aria-label="Move node down">↓</button><button type="button" data-node-action="remove" data-node-id="${escapeHtml(nodeId)}" ${controller.nodes.length === 1 ? "disabled" : ""}>Remove</button></td>
      </tr>`;
    }).join("");
    const transitionRows = localTransitions.map((transition, index) => {
      const transitionId = localTransitionId(transition);
      return `<tr data-controller-transition="${escapeHtml(transitionId)}">
        <td><strong>${transition.draftId ? escapeHtml(transition.draftId) : transition.stableId}</strong></td>
        <td><select data-transition-field="trigger" data-transition-id="${escapeHtml(transitionId)}">${selectOptions(dataset.transitionGraph.triggerOptions || [], transition.trigger)}</select></td>
        <td><fieldset class="v40-role-mask"><legend class="sr-only">Allowed source roles</legend>${(dataset.semanticRoles || []).map((role) => `<label title="${escapeHtml(role.label)}"><input type="checkbox" data-transition-role="${role.value}" data-transition-id="${escapeHtml(transitionId)}" ${Number(transition.fromRoleMask) & (1 << (Number(role.value) - 1)) ? "checked" : ""}><span>${escapeHtml(role.label.slice(0, 1))}</span></label>`).join("")}</fieldset></td>
        <td><select data-transition-field="candidateDefinitionId" data-transition-id="${escapeHtml(transitionId)}" aria-label="Candidate definition">${selectOptions(definitionOptions, transition.candidateDefinitionId)}</select></td>
        <td><select data-transition-field="ownerId" data-transition-id="${escapeHtml(transitionId)}" aria-label="Owner">${selectOptions(ownerOptions, transition.ownerId)}</select></td>
        <td><input type="number" min="1" max="65535" value="${transition.dispatchPriority}" data-transition-field="dispatchPriority" data-transition-id="${escapeHtml(transitionId)}"></td>
        <td class="v40-row-actions"><button type="button" data-transition-action="up" data-transition-id="${escapeHtml(transitionId)}" ${index === 0 ? "disabled" : ""} aria-label="Move transition up">↑</button><button type="button" data-transition-action="down" data-transition-id="${escapeHtml(transitionId)}" ${index === localTransitions.length - 1 ? "disabled" : ""} aria-label="Move transition down">↓</button><button type="button" data-transition-action="remove" data-transition-id="${escapeHtml(transitionId)}">Remove</button></td>
      </tr>`;
    }).join("");
    inspector.innerHTML = `<article class="profile-field-editor v40-controller-editor" data-selected-controller="${escapeHtml(controllerIdFor(controller))}">
      <header class="v40-state-editor__heading"><div><span class="eyebrow">Typed controller</span><h2>${escapeHtml(controller.name)}</h2><small>${controller.created ? escapeHtml(controller.draftId) : `Stable ID ${controller.stableId}`}</small></div><div class="v40-state-editor__actions"><button class="button" type="button" data-controller-action="duplicate">Duplicate controller</button></div></header>
      ${errors.length ? `<aside class="v40-validation" role="status"><strong>${errors.length} draft issue${errors.length === 1 ? "" : "s"}</strong><span>${escapeHtml(errors[0].message)}</span></aside>` : ""}
      <section class="v40-controller-identity"><label><span>Name</span><input type="text" value="${escapeHtml(controller.name)}" data-controller-identity="name"></label><div><span>Identity</span><strong>${controller.created ? escapeHtml(controller.draftId) : controller.stableId}</strong><small>${controller.created ? "Local and unpersisted" : escapeHtml(controller.registryKey)}</small></div></section>
      <details class="pv2-field-section" open><summary><span><strong>Controller defaults</strong><small>Typed scalar defaults and stable policy references.</small></span></summary><div class="profile-fields">${scalarFields}${policyControls}</div></details>
      <section class="v40-controller-section"><header><div><span class="eyebrow">State roster</span><h3>Bound nodes</h3></div><button type="button" data-controller-action="add-node">Add node</button></header><div class="v40-table-scroll"><table class="v40-controller-table"><thead><tr><th>Base</th><th>Node ID</th><th>Semantic role</th><th>Bound profile</th><th>Order</th></tr></thead><tbody>${nodeRows}</tbody></table></div></section>
      <section class="v40-controller-section"><header><div><span class="eyebrow">Authoritative graph</span><h3>Transitions</h3></div><button type="button" data-controller-action="add-transition">Add transition</button></header><div class="v40-table-scroll"><table class="v40-controller-table v40-transition-table"><thead><tr><th>Row ID</th><th>Event</th><th>From roles</th><th>Definition</th><th>Owner</th><th>Priority</th><th>Order</th></tr></thead><tbody>${transitionRows || `<tr><td colspan="7">No transitions.</td></tr>`}</tbody></table></div></section>
    </article>`;
  }

  function render() {
    root.classList.toggle?.("v40-controller-mode", mode === "controllers");
    root.querySelectorAll?.("[data-profile-deck-mode]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.profileDeckMode === mode)));
    const title = root.querySelector?.("#profileLibraryTitle");
    if (title) title.textContent = mode === "controllers" ? "Controllers" : "State profiles";
    const createButton = root.querySelector?.("[data-action='new-profile']");
    if (createButton) createButton.setAttribute("aria-label", mode === "controllers" ? "Create controller" : "Create state profile");
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

  function selectController(id, { report = true } = {}) {
    if (!controllers().some((controller) => controllerIdFor(controller) === id)) return false;
    selectedControllerId = id;
    state.selectedControllerKey = id;
    render();
    if (report) reportSelection({ view: "profiles", selection: id, label: selectedController()?.name || "" });
    return true;
  }

  function uniqueControllerName(preferred) {
    const names = new Set(controllers().map((controller) => String(controller.name).trim().toLowerCase()));
    const base = String(preferred || "New controller").trim() || "New controller";
    if (!names.has(base.toLowerCase())) return base;
    let suffix = 2;
    while (names.has(`${base} ${suffix}`.toLowerCase())) suffix += 1;
    return `${base} ${suffix}`;
  }

  function addController(source = null) {
    const sourceTransitions = source ? controllerTransitions(source) : [];
    const draft = createControllerDraft({
      source, profiles: profiles(), transitions: sourceTransitions,
      policyDefaults: dataset.controllers?.[0]?.policyIds,
    });
    draft.controller.name = uniqueControllerName(source ? `${source.name} copy` : "New controller");
    createdControllers.push(draft.controller);
    createdTransitions.push(...draft.transitions);
    const allControllerIds = controllers().map((controller) => controller.draftId || controller.stableId);
    transitions().filter((transition) => !transition.candidateDefinition?.controllerId).forEach((transition) => {
      editableTransition(transition).controllerIds = [...allControllerIds];
    });
    selectedControllerId = draft.controller.draftId;
    syncDirty();
    render();
    requestAnimationFrame(() => inspector.querySelector("[data-controller-identity='name']")?.select());
  }

  function updateControllerValue(domain, key, raw) {
    const controller = editableController(selectedController());
    if (!controller) return;
    if (domain === "identity") controller[key] = String(raw);
    else controller[domain][key] = Number(raw);
    syncDirty();
    renderList();
  }

  function addNode() {
    const controller = editableController(selectedController());
    if (!controller) return;
    const used = new Set(controller.nodes.map((node) => Number(node.semanticRoleId)));
    const unusedOrdinary = (dataset.semanticRoles || []).find((option) => Number(option.value) !== 7 && !used.has(Number(option.value)))?.value;
    const usedCustom = new Set(controller.nodes.filter((node) => Number(node.semanticRoleId) === 7).map((node) => Number(node.customRoleId)));
    const unusedCustom = (dataset.customRoles || []).find((option) => !usedCustom.has(Number(option.stableId)))?.stableId;
    const role = unusedOrdinary || (unusedCustom ? 7 : dataset.semanticRoles?.[0]?.value || 1);
    const node = {
      stableId: null, draftId: draftId(), controllerId: controller.draftId || controller.stableId,
      order: controller.nodes.length, semanticRoleId: Number(role),
      semanticRole: dataset.semanticRoles?.find((option) => Number(option.value) === Number(role))?.label || "",
      customRoleId: Number(role) === 7 ? unusedCustom || null : null,
      profileRef: profiles()[0]?.draftId || profiles()[0]?.stableId || null,
      base: controller.nodes.length === 0, optional: false, hidden: false,
    };
    controller.nodes.push(node);
    if (node.base) controller.baseNodeId = node.draftId;
    syncDirty();
    render();
  }

  function updateNode(nodeId, key, raw) {
    const controller = editableController(selectedController());
    const node = controller?.nodes.find((item) => localNodeId(item) === nodeId);
    if (!node) return;
    if (key === "base") {
      controller.nodes.forEach((item) => { item.base = item === node; });
      controller.baseNodeId = nodeId;
    } else {
      node[key] = key === "profileRef" && String(raw).startsWith("draft:") ? String(raw) : Number(raw);
      if (key === "semanticRoleId") {
        node.semanticRole = dataset.semanticRoles?.find((option) => Number(option.value) === Number(raw))?.label || "";
        if (Number(raw) === 7) {
          const usedCustom = new Set(controller.nodes
            .filter((other) => other !== node && Number(other.semanticRoleId) === 7)
            .map((other) => Number(other.customRoleId)));
          node.customRoleId = node.customRoleId && !usedCustom.has(Number(node.customRoleId))
            ? node.customRoleId
            : dataset.customRoles?.find((role) => !usedCustom.has(Number(role.stableId)))?.stableId || null;
        } else node.customRoleId = null;
      }
    }
    syncDirty();
  }

  function nodeAction(nodeId, action) {
    const controller = editableController(selectedController());
    const index = controller?.nodes.findIndex((node) => localNodeId(node) === nodeId) ?? -1;
    if (!controller || index < 0) return;
    if (action === "remove" && controller.nodes.length > 1) {
      const [removed] = controller.nodes.splice(index, 1);
      if (removed.base) {
        controller.nodes[0].base = true;
        controller.baseNodeId = localNodeId(controller.nodes[0]);
      }
    } else if (action === "up" && index > 0) {
      [controller.nodes[index - 1], controller.nodes[index]] = [controller.nodes[index], controller.nodes[index - 1]];
    } else if (action === "down" && index < controller.nodes.length - 1) {
      [controller.nodes[index], controller.nodes[index + 1]] = [controller.nodes[index + 1], controller.nodes[index]];
    }
    controller.nodes.forEach((node, order) => { node.order = order; });
    syncDirty();
    render();
  }

  function addTransition() {
    const controller = selectedController();
    if (!controller) return;
    const source = controllerTransitions(controller)[0] || savedTransitions[0];
    const transition = source ? clone(source) : {
      candidateDefinitionId: 1, candidateDefinition: {}, ownerId: 1,
      trigger: 1, fromRoleMask: 1, dispatchPriority: 1,
      guards: [], operations: [], actions: [], recoveryActions: [],
    };
    transition.stableId = null;
    transition.draftId = draftId();
    transition.name = "New transition";
    transition.order = controllerTransitions(controller).length;
    const controllerId = controller.draftId || controller.stableId;
    const definition = clone(transition.candidateDefinition || {});
    definition.stableId = null;
    definition.draftId = draftId();
    definition.controllerId = controllerId;
    if (definition.nodeId) definition.nodeId = controller.baseNodeId;
    transition.candidateDefinition = definition;
    transition.candidateDefinitionId = definition.draftId;
    transition.controllerIds = [controllerId];
    transition.guards = (transition.guards || []).map((guard) => ({
      ...guard, stableId: null, draftId: draftId(),
      referenceId: guard.kind === 3 ? controller.baseNodeId : guard.referenceId,
    }));
    transition.operations = (transition.operations || []).map((operation) => ({ ...operation, stableId: null, draftId: draftId() }));
    transition.actions = (transition.actions || []).map((action) => ({ ...action, stableId: null, draftId: draftId() }));
    transition.recoveryActions = (transition.recoveryActions || []).map((action) => ({ ...action, stableId: null, draftId: draftId() }));
    transition.created = true;
    createdTransitions.push(transition);
    const editable = editableController(controller);
    editable.transitionIds = [...(editable.transitionIds || []), transition.draftId];
    syncDirty();
    render();
  }

  function findTransition(id) {
    return transitions().find((transition) => localTransitionId(transition) === id) || null;
  }

  function updateTransition(id, key, raw) {
    const transition = editableTransition(findTransition(id));
    if (!transition) return;
    transition[key] = key === "candidateDefinitionId" && String(raw).startsWith("draft:") ? String(raw) : Number(raw);
    if (key === "candidateDefinitionId") {
      const source = transitions().find((item) => String(item.candidateDefinitionId) === String(raw))
        || (dataset.transitionGraph?.transitions || []).find((item) => String(item.candidateDefinitionId) === String(raw));
      transition.candidateDefinition = clone(source?.candidateDefinition || null);
      transition.controllerIds = transition.candidateDefinition?.controllerId
        ? [transition.candidateDefinition.controllerId]
        : controllers().map((controller) => controller.draftId || controller.stableId);
    }
    syncDirty();
  }

  function updateTransitionRole(id, role, checked) {
    const transition = editableTransition(findTransition(id));
    if (!transition) return;
    const bit = 1 << (Number(role) - 1);
    transition.fromRoleMask = checked ? Number(transition.fromRoleMask) | bit : Number(transition.fromRoleMask) & ~bit;
    transition.fromSemanticRoleIds = (dataset.semanticRoles || []).map((item) => Number(item.value)).filter((value) => transition.fromRoleMask & (1 << (value - 1)));
    syncDirty();
  }

  function transitionAction(id, action) {
    const controller = selectedController();
    const local = controllerTransitions(controller);
    const index = local.findIndex((transition) => localTransitionId(transition) === id);
    if (!controller || index < 0) return;
    const transition = local[index];
    if (action === "remove") {
      if (transition.draftId) createdTransitions.splice(createdTransitions.indexOf(transition), 1);
      else {
        transitionUpdates.delete(transition.stableId);
        removedTransitionIds.add(transition.stableId);
      }
      controllers().forEach((item) => {
        if (!(item.transitionIds || []).some((reference) => String(reference) === String(transition.stableId) || String(reference) === id)) return;
        const editable = editableController(item);
        editable.transitionIds = editable.transitionIds.filter((reference) => String(reference) !== String(transition.stableId) && String(reference) !== id);
      });
    } else {
      const otherIndex = action === "up" ? index - 1 : index + 1;
      if (otherIndex >= 0 && otherIndex < local.length) {
        const first = editableTransition(transition);
        const second = editableTransition(local[otherIndex]);
        [first.order, second.order] = [second.order, first.order];
      }
    }
    syncDirty();
    render();
  }

  function setMode(nextMode) {
    if (!["states", "controllers"].includes(nextMode) || mode === nextMode) return;
    mode = nextMode;
    filter = "all";
    elements.profileKindFilter.innerHTML = nextMode === "controllers" ? `
      <option value="all">All controllers</option>
      <option value="saved">Saved controllers</option>
      <option value="draft">New drafts</option>` : `
      <option value="all">All states</option>
      <option value="saved">Saved states</option>
      <option value="draft">New drafts</option>`;
    elements.profileKindFilter.value = filter;
    syncDirty();
    render();
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
    controllerUpdates.clear();
    createdControllers.splice(0);
    transitionUpdates.clear();
    createdTransitions.splice(0);
    removedTransitionIds.clear();
    selectedId = previousStableId && saved.some((profile) => profile.stableId === previousStableId)
      ? `state:${previousStableId}`
      : (saved[0] ? `state:${saved[0].stableId}` : "");
    selectedControllerId = savedControllers[0] ? `controller:${savedControllers[0].stableId}` : "";
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
      if (dataset?.modelVersion !== 40 || !Array.isArray(dataset.stateProfiles) || !Array.isArray(dataset.stateProfileFields)
          || !Array.isArray(dataset.controllers) || !Array.isArray(dataset.transitionGraph?.transitions)) {
        throw new Error("The server did not return an OWBD v40 behavior model.");
      }
      saved = dataset.stateProfiles.map(clone);
      savedControllers = dataset.controllers.map(clone);
      savedTransitions = dataset.transitionGraph.transitions.map(clone);
      if (!selectedId || !profiles().some((profile) => idFor(profile) === selectedId)) {
        selectedId = profiles()[0] ? idFor(profiles()[0]) : "";
      }
      if (!selectedControllerId || !controllers().some((controller) => controllerIdFor(controller) === selectedControllerId)) {
        selectedControllerId = controllers()[0] ? controllerIdFor(controllers()[0]) : "";
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
    const modeButton = event.target.closest("[data-profile-deck-mode]");
    if (modeButton) return void setMode(modeButton.dataset.profileDeckMode);
    const controllerSelect = event.target.closest("[data-controller-id]");
    if (controllerSelect) return void selectController(controllerSelect.dataset.controllerId);
    const select = event.target.closest("[data-profile-id]");
    if (select) return void selectProfile(select.dataset.profileId);
    const action = event.target.closest("[data-profile-action]")?.dataset.profileAction;
    if (action === "retry") return void load();
    if (action === "reset-local") return void resetLocalDrafts();
    if (action === "duplicate") return void addProfile(selected());
    const controllerActionName = event.target.closest("[data-controller-action]")?.dataset.controllerAction;
    if (controllerActionName === "duplicate") return void addController(selectedController());
    if (controllerActionName === "add-node") return void addNode();
    if (controllerActionName === "add-transition") return void addTransition();
    const nodeButton = event.target.closest("[data-node-action]");
    if (nodeButton) return void nodeAction(nodeButton.dataset.nodeId, nodeButton.dataset.nodeAction);
    const transitionButton = event.target.closest("[data-transition-action]");
    if (transitionButton) return void transitionAction(transitionButton.dataset.transitionId, transitionButton.dataset.transitionAction);
    if (event.target.closest("[data-action='new-profile']")) return void (mode === "controllers" ? addController() : addProfile());
  }

  function onInput(event) {
    if (event.target === elements.profileSearch) {
      search = event.target.value;
      renderList();
      return;
    }
    if (event.target.matches("[data-controller-identity]")) updateControllerValue("identity", event.target.dataset.controllerIdentity, event.target.value);
    else if (event.target.matches("[data-controller-scalar]")) updateControllerValue("scalarDefaults", event.target.dataset.controllerScalar, event.target.value);
    else if (event.target.matches("[data-controller-policy]")) updateControllerValue("policyIds", event.target.dataset.controllerPolicy, event.target.value);
    else if (event.target.matches("[data-node-field]") && event.target.dataset.nodeField !== "base") updateNode(event.target.dataset.nodeId, event.target.dataset.nodeField, event.target.value);
    else if (event.target.matches("[data-transition-field]")) updateTransition(event.target.dataset.transitionId, event.target.dataset.transitionField, event.target.value);
    else if (event.target.matches("[data-state-identity]")) updateIdentity(event.target.dataset.stateIdentity, event.target.value);
    else if (event.target.matches("[data-state-field]")) updateField(event.target.dataset.stateField, event.target.value);
  }

  function onChange(event) {
    if (event.target === elements.profileKindFilter) {
      filter = event.target.value;
      renderList();
      return;
    }
    if (event.target.matches("[data-node-field]")) {
      updateNode(event.target.dataset.nodeId, event.target.dataset.nodeField, event.target.value);
      renderInspector();
      return;
    }
    if (event.target.matches("[data-transition-role]")) {
      updateTransitionRole(event.target.dataset.transitionId, event.target.dataset.transitionRole, event.target.checked);
      renderInspector();
      return;
    }
    if (event.target.matches("[data-controller-identity]")) {
      updateControllerValue("identity", event.target.dataset.controllerIdentity, event.target.value);
      renderInspector();
      return;
    }
    if (event.target.matches("[data-controller-scalar]")) {
      updateControllerValue("scalarDefaults", event.target.dataset.controllerScalar, event.target.value);
      renderInspector();
      return;
    }
    if (event.target.matches("[data-controller-policy]")) {
      updateControllerValue("policyIds", event.target.dataset.controllerPolicy, event.target.value);
      renderInspector();
      return;
    }
    if (event.target.matches("[data-transition-field]")) {
      updateTransition(event.target.dataset.transitionId, event.target.dataset.transitionField, event.target.value);
      renderInspector();
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
    clearCommitted: () => {
      updates.clear(); created.splice(0);
      controllerUpdates.clear(); createdControllers.splice(0);
      transitionUpdates.clear(); createdTransitions.splice(0); removedTransitionIds.clear();
      syncDirty(); load();
    },
    reset: resetLocalDrafts,
    refresh: () => { if (!loading && !created.length && !updates.size) load(); },
    refreshPreservingDrafts: () => load(),
    navigationContext: () => mode === "controllers"
      ? ({ selection: selectedControllerId, label: selectedController()?.name || "" })
      : ({ selection: selectedId, label: selected()?.name || "" }),
    restoreSelection: (id) => String(id).startsWith("controller:") || String(id).startsWith("draft:") && controllers().some((controller) => controllerIdFor(controller) === id)
      ? (setMode("controllers"), selectController(id, { report: false }))
      : (setMode("states"), selectProfile(id, { report: false })),
    behaviorModelDraft: () => clone(state.v40BehaviorModelDraft),
    localValidationErrors: () => clone([
      ...validationErrors(),
      ...controllers().flatMap((controller) => validateControllerDraft(controller, { ...dataset, stateProfiles: profiles(), controllers: controllers() }, controllerTransitions(controller))
        .map((error) => ({ ...error, controllerId: controllerIdFor(controller) }))),
    ]),
    destroy: () => {
      if (destroyed) return;
      destroyed = true;
      root.removeEventListener("click", onClick);
      root.removeEventListener("input", onInput);
      root.removeEventListener("change", onChange);
    },
  });
}
