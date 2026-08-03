/* Overworld Viewer V2 — OWBD v40 state-profile editor foundation. */

import { createStackPreviewController } from "./stack-preview.js";
import { indexDiagnostics, validateBehaviorDraft, validateBehaviorModel } from "./model-validation.js";

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
  const templateProvenance = source?.templateProvenance || (
    source?.bodyProvenance?.kind && source?.provenanceId
      ? { kind: Number(source.bodyProvenance.kind), provenanceId: Number(source.provenanceId) }
      : null
  );
  return {
    draftId: draftId(),
    stableId: null,
    name: String(preferredName || "New state profile").trim() || "New state profile",
    descriptiveTags: [...(source?.descriptiveTags || [])],
    values,
    backlinks: [],
    ...(templateProvenance ? { templateProvenance: clone(templateProvenance) } : {}),
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

export function createControllerDraft({
  source = null, profiles = [], transitions = [], policyDefaults = null,
  transitionOrderStart = 0, behaviorModelAuthoring = null,
} = {}) {
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
  const applicabilityMap = new Map();
  const sourceControllerId = source?.draftId ?? source?.stableId ?? null;
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
    const displayedApplicability = sourceDefinition.applicability;
    const authoredApplicability = (behaviorModelAuthoring?.applicability || []).find(
      (item) => String(item.stableId) === String(displayedApplicability?.stableId ?? sourceDefinition.applicabilityId),
    );
    const sourceApplicability = displayedApplicability
      ? { ...clone(displayedApplicability), ...clone(authoredApplicability || {}) }
      : clone(authoredApplicability || null);
    const applicabilityKey = sourceApplicability?.draftId ?? sourceApplicability?.stableId;
    if (sourceApplicability && applicabilityKey != null
        && sourceDefinition.controllerId != null
        && String(sourceApplicability.controllerId) === String(sourceControllerId)) {
      if (!applicabilityMap.has(String(applicabilityKey))) {
        const applicability = clone(sourceApplicability);
        applicability.stableId = null;
        applicability.draftId = draftId();
        applicability.controllerId = controllerDraftId;
        applicabilityMap.set(String(applicabilityKey), applicability);
      }
      definition.applicability = clone(applicabilityMap.get(String(applicabilityKey)));
      definition.applicabilityId = definition.applicability.draftId;
    }
    definitionMap.set(definitionKey, definition);
  }
  const mapDefinitionId = (value) => definitionMap.get(String(value))?.draftId || value;
  const transitionCopies = transitions.map((transition, order) => {
    const copy = clone(transition);
    copy.stableId = null;
    copy.draftId = transitionIdMap.get(localTransitionId(transition));
    copy.order = Number(transitionOrderStart) + order;
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

const DEFINITION_AUTHORED_FIELDS = Object.freeze([
  "controllerId", "nodeId", "requiredOwnerId", "recoveryTransitionId",
  "applicabilityId", "priority", "kind", "channel", "selectorKind",
  "semanticRoleId", "mapLifetime", "battleLifetime", "timerClock",
  "timerSource", "hiddenTimerPolicy", "recoveryPolicy", "timerValue",
  "hasTiredOriginKind", "tiredOriginKind", "hasRequiredOwnerId",
  "allowMultipleOwners", "allowMultipleInstancesPerOwner",
  "authoredTiredBound", "flags", "reserved0", "reserved1",
]);

const CHILD_FIELDS = Object.freeze({
  guards: ["kind", "negate", "payload", "referenceId"],
  operations: ["definitionId", "ownerId", "replacementDefinitionId", "policyId", "instanceKey", "kind", "busyPolicy", "required"],
  actions: ["phase", "kind", "referenceId", "payload"],
  recoveryActions: ["ownerId", "kind", "required"],
});

const AUTHORING_OPTIONS = Object.freeze({
  definitionKind: [[1, "State candidate"], [2, "Modifier"]],
  channel: [[0, "Static context"], [1, "Controller state"], [2, "Temporary effect"], [3, "Scripted force"], [4, "Possession"], [5, "System safety"]],
  selectorKind: [[1, "Exact node"], [2, "Semantic role"]],
  lifetime: [[1, "Clear"], [2, "Preserve logical"], [3, "System"]],
  timerClock: [[0, "None"], [1, "Frame"], [2, "Completed movement"]],
  timerSource: [[0, "None"], [1, "Fixed"], [2, "Controller stamina"], [3, "Candidate fold"]],
  hiddenTimerPolicy: [[0, "None"], [1, "Pause while hidden"], [2, "Continue while hidden"], [3, "Expire on hide"]],
  recoveryPolicy: [[0, "None"], [1, "Route transition"]],
  guardKind: [[1, "Always"], [2, "Effective role"], [3, "Effective node"], [4, "Owner present"], [5, "Owner absent"], [6, "Candidate timer expired"], [7, "Alert chance roll"], [8, "System route"]],
  operationKind: [[1, "Apply"], [2, "Replace"], [3, "Remove required"], [4, "Remove if present"], [5, "Remove owner if present"], [6, "Apply lifetime policy"]],
  busyPolicy: [[1, "Reject while busy"], [2, "Queue exact"]],
  actionPhase: [[1, "Entry"], [2, "Exit"], [3, "Presentation"], [4, "Invocation"]],
  actionKind: [[1, "Reset active steps"], [2, "Reset tired counter"], [3, "Clear movement chain"], [4, "Start post-tired cooldown"], [5, "Start alert presentation"], [6, "Try pickup/throw"], [7, "Alert complete"], [8, "Canopy pickup/throw hook"]],
  recoveryActionKind: [[1, "Remove self"], [2, "Remove owner if present"], [3, "Reset tired counter"], [4, "Start flee cooldown"]],
});

function optionRecords(key) {
  return (AUTHORING_OPTIONS[key] || []).map(([value, label]) => ({ value, label }));
}

function authoredIdentity(entity) {
  return entity?.draftId
    ? { draftId: entity.draftId }
    : { stableId: Number(entity?.stableId) };
}

function pickFields(source, fields) {
  return Object.fromEntries(fields.map((key) => [key, source?.[key] ?? null]));
}

function compactProfile(profile, creating) {
  return {
    ...authoredIdentity(profile),
    name: String(profile.name),
    descriptiveTags: [...(profile.descriptiveTags || [])],
    values: clone(profile.values || {}),
    ...(creating ? { templateProvenance: clone(profile.templateProvenance) } : {}),
  };
}

function compactNode(node) {
  return {
    ...authoredIdentity(node),
    profileRef: node.profileRef ?? node.profileStableId,
    semanticRoleId: Number(node.semanticRoleId),
    customRoleId: node.customRoleId ?? null,
    base: Boolean(node.base),
    optional: Boolean(node.optional),
    hidden: Boolean(node.hidden),
  };
}

function compactController(controller) {
  return {
    ...authoredIdentity(controller),
    name: String(controller.name),
    nodes: (controller.nodes || []).map(compactNode),
    scalarDefaults: clone(controller.scalarDefaults || {}),
    policyIds: clone(controller.policyIds || {}),
  };
}

function compactApplicability(definition, model) {
  const embedded = definition?.applicability;
  const stableId = embedded?.stableId ?? definition?.applicabilityId;
  const authored = embedded?.kind !== undefined
    ? embedded
    : (model?.behaviorModelAuthoring?.applicability || []).find((item) => String(item.stableId) === String(stableId));
  if (!authored) throw new Error(`Applicability ${stableId ?? ""} is not representable by the V40 writer.`);
  return {
    ...authoredIdentity(authored),
    ...pickFields(authored, ["name", "kind", "groupMask", "controllerId", "profileId", "minimum", "maximum", "flags"]),
  };
}

function compactDefinition(definition, model) {
  if (!definition) throw new Error("A transition candidate definition is required.");
  return {
    ...authoredIdentity(definition),
    ...(definition.name ? { name: String(definition.name) } : {}),
    ...pickFields(definition, DEFINITION_AUTHORED_FIELDS),
    applicability: compactApplicability(definition, model),
  };
}

function compactChild(child, kind) {
  return {
    ...authoredIdentity(child),
    ...pickFields(child, CHILD_FIELDS[kind]),
  };
}

function compactTransition(transition, model) {
  return {
    ...authoredIdentity(transition),
    name: String(transition.name),
    controllerIds: [...(transition.controllerIds || [])],
    candidateDefinitionId: transition.candidateDefinitionId,
    candidateDefinition: compactDefinition(transition.candidateDefinition, model),
    ownerId: transition.ownerId,
    trigger: Number(transition.trigger),
    fromRoleMask: Number(transition.fromRoleMask),
    dispatchPriority: Number(transition.dispatchPriority),
    order: Number(transition.order),
    ...Object.fromEntries(Object.keys(CHILD_FIELDS).map((kind) => [
      kind, (transition[kind] || []).map((child) => compactChild(child, kind)),
    ])),
  };
}

function sameAuthored(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

/** Return the writer's compact delta; display-only and derived fields never cross the API. */
export function compactBehaviorModelDraft(draft, model) {
  const transaction = { modelVersion: 40 };
  const specifications = {
    stateProfiles: [(item, creating) => compactProfile(item, creating), model?.stateProfiles || []],
    controllers: [(item) => compactController(item), model?.controllers || []],
    transitions: [(item) => compactTransition(item, model), model?.transitionGraph?.transitions || []],
  };
  for (const [domain, [compact, saved]] of Object.entries(specifications)) {
    const delta = draft?.[domain] || {};
    const create = (delta.create || []).map((item) => compact(item, true, model));
    const update = (delta.update || []).map((item) => compact(item, false, model)).filter((item) => {
      const source = saved.find((candidate) => Number(candidate.stableId) === Number(item.stableId));
      return !source || !sameAuthored(item, compact(source, false, model));
    });
    const remove = [...(delta.remove || [])];
    const authored = Object.fromEntries(Object.entries({ create, update, remove }).filter(([, values]) => values.length));
    if (Object.keys(authored).length) transaction[domain] = authored;
  }
  return transaction;
}

export function behaviorModelChangeCount(transaction) {
  return ["stateProfiles", "controllers", "transitions"].reduce(
    (total, domain) => total + ["create", "update", "remove"].reduce(
      (domainTotal, operation) => domainTotal + (transaction?.[domain]?.[operation]?.length || 0), 0,
    ), 0,
  );
}

export function createProfilesController({
  state = {}, api, elements = {}, setStatus = () => {},
  reportSelection = () => {}, markDirty = () => {},
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
  let stackPreviewController = null;
  let graphDiagnostics = [];
  let graphDiagnosticIndex = {};
  let writerValidationError = "";
  const updates = new Map();
  const created = [];
  const removedProfileIds = new Set();
  const controllerUpdates = new Map();
  const createdControllers = [];
  const transitionUpdates = new Map();
  const createdTransitions = [];
  const removedTransitionIds = new Set();
  let selectedControllerId = String(state.selectedControllerKey || "");
  let selectedTransitionId = String(state.selectedTransitionKey || "");

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
    return saved.filter((profile) => !removedProfileIds.has(profile.stableId))
      .map((profile) => updates.get(profile.stableId) || profile);
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

  function recomputeGraphDiagnostics() {
    if (loading || !dataset?.stateProfiles) return;
    graphDiagnostics = state.v40BehaviorModelDraft
      ? validateBehaviorDraft(dataset, state.v40BehaviorModelDraft)
      : validateBehaviorModel(dataset);
    graphDiagnosticIndex = indexDiagnostics(graphDiagnostics);
    state.v40BehaviorModelDiagnostics = clone(graphDiagnostics);
  }

  function diagnosticsFor(type, entity) {
    return graphDiagnosticIndex[`${type}:${String(entity?.draftId ?? entity?.stableId)}`] || [];
  }

  function currentCommit() {
    try {
      const transaction = compactBehaviorModelDraft(state.v40BehaviorModelDraft, dataset);
      writerValidationError = "";
      return { transaction, count: behaviorModelChangeCount(transaction) };
    } catch (error) {
      writerValidationError = String(error?.message || error);
      const draft = state.v40BehaviorModelDraft || {};
      const count = ["stateProfiles", "controllers", "transitions"].reduce(
        (total, domain) => total + ["create", "update", "remove"].reduce(
          (subtotal, operation) => subtotal + (draft?.[domain]?.[operation]?.length || 0), 0,
        ), 0,
      );
      return { transaction: null, count };
    }
  }

  function blockingDiagnostics() {
    const diagnostics = graphDiagnostics.filter((item) => item.severity !== "warning");
    return writerValidationError
      ? [{ code: "REPRESENTATION_UNSUPPORTED", message: writerValidationError, entityType: "draft", entityId: "draft" }, ...diagnostics]
      : diagnostics;
  }

  function syncDirty({ notify = true } = {}) {
    state.selectedProfileKey = selectedId;
    state.selectedControllerKey = selectedControllerId;
    state.selectedTransitionKey = selectedTransitionId;
    state.profileDeckMode = mode;
    state.v40BehaviorModelDraft = {
      ...(state.v40BehaviorModelDraft || {}),
      modelVersion: 40,
      stateProfiles: {
        create: created.map(clone),
        update: [...updates.values()].map(clone),
        remove: [...removedProfileIds],
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
    recomputeGraphDiagnostics();
    state.profileDirty = currentCommit().count > 0;
    stackPreviewController?.refresh();
    if (notify) markDirty();
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
            <strong>${escapeHtml(profile.name)}${diagnosticsFor("stateProfile", profile).length ? `<span class="v40-diagnostic-badge" aria-label="${diagnosticsFor("stateProfile", profile).length} validation issues">${diagnosticsFor("stateProfile", profile).length}</span>` : ""}</strong>
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
            <strong>${escapeHtml(controller.name)}${diagnosticsFor("controller", controller).length ? `<span class="v40-diagnostic-badge" aria-label="${diagnosticsFor("controller", controller).length} validation issues">${diagnosticsFor("controller", controller).length}</span>` : ""}</strong>
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
    const entityDiagnostics = diagnosticsFor("stateProfile", profile);
    const tagText = (profile.descriptiveTags || []).join(", ");
    const groups = dataset.groups.map((group, index) => {
      const fields = dataset.stateProfileFields.filter((field) => field.group === group.key);
      return `<details class="pv2-field-section v40-field-group" ${index < 4 ? "open" : ""}>
        <summary><span><strong>${escapeHtml(group.label)}</strong><small>${escapeHtml(GROUP_HELP[group.key] || "")}</small></span><b>${fields.length}</b></summary>
        <div class="profile-fields">${fields.map((field) => fieldHtml(profile, field)).join("")}</div>
      </details>`;
    }).join("");
    const hasLocalDrafts = created.length > 0 || updates.size > 0 || removedProfileIds.size > 0;
    inspector.innerHTML = `<article class="profile-field-editor v40-state-editor" data-selected-profile="${escapeHtml(idFor(profile))}">
      <header class="v40-state-editor__heading">
        <div><span class="eyebrow">One complete state</span><h2>${escapeHtml(profile.name)}</h2></div>
        <div class="v40-state-editor__actions">
          ${hasLocalDrafts ? `<button class="button" type="button" data-profile-action="reset-local">Discard local drafts</button>` : ""}
          <button class="button" type="button" data-profile-action="duplicate">Duplicate state</button>
          <button class="button button--danger" type="button" data-profile-action="delete">Delete state</button>
        </div>
      </header>
      <section class="v40-state-identity" aria-labelledby="stateIdentityTitle">
        <div><span class="eyebrow" id="stateIdentityTitle">${profile.created ? "Draft identity" : "Stable identity"}</span><strong>${profile.created ? escapeHtml(profile.draftId) : `ID ${profile.stableId}`}</strong><small>${profile.created ? "Pending Global Save." : escapeHtml(profile.registryKey || "Runtime catalog identity")}</small></div>
        <label><span>Name</span><input type="text" value="${escapeHtml(profile.name)}" data-state-identity="name" aria-invalid="${nameError ? "true" : "false"}">${nameError ? `<small class="field-error">${escapeHtml(nameError.message)}</small>` : ""}</label>
        <label class="v40-state-tags"><span>Descriptive tags</span><input type="text" value="${escapeHtml(tagText)}" data-state-identity="descriptiveTags" placeholder="bird, air, relaxed"><small>Search and documentation only. Tags never select runtime behavior.</small></label>
      </section>
      ${entityDiagnostics.length ? `<aside class="v40-validation" role="status"><strong>${entityDiagnostics.length} model issue${entityDiagnostics.length === 1 ? "" : "s"}</strong><span>${escapeHtml(entityDiagnostics[0].message)}</span></aside>` : ""}
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

  function nullableOptions(options, current, label = "None", valueKey = "value", labelKey = "label") {
    return `<option value="0" ${current === null || current === undefined || Number(current) === 0 ? "selected" : ""}>${escapeHtml(label)}</option>${selectOptions(options, current, valueKey, labelKey)}`;
  }

  function referenceOptions(items, current, label, name = "name") {
    const options = items.map((item) => ({
      value: item.draftId || item.stableId,
      label: item[name] || `${label} ${item.draftId || item.stableId}`,
    }));
    return nullableOptions(options, current, `No ${label.toLowerCase()}`);
  }

  function authoredApplicabilityFor(definition) {
    if (definition?.applicability?.kind !== undefined) return definition.applicability;
    const stableId = definition?.applicability?.stableId ?? definition?.applicabilityId;
    const authored = (dataset.behaviorModelAuthoring?.applicability || [])
      .find((item) => String(item.stableId) === String(stableId));
    return authored ? { ...clone(authored), name: definition?.applicability?.name || authored.name } : (definition?.applicability || {});
  }

  function transitionAuthoringDiagnostics(transition) {
    const identities = new Set([
      ["transition", transition], ["overrideDefinition", transition?.candidateDefinition],
      ["applicability", transition?.candidateDefinition?.applicability],
      ...(transition?.guards || []).map((item) => ["guards", item]),
      ...(transition?.operations || []).map((item) => ["operations", item]),
      ...(transition?.actions || []).map((item) => ["actions", item]),
      ...(transition?.recoveryActions || []).map((item) => ["recoveryActions", item]),
    ].map(([kind, item]) => `${kind}:${String(item?.draftId ?? item?.stableId)}`));
    return graphDiagnostics.filter((item) => identities.has(`${item.entityType}:${item.entityId}`));
  }

  function childRows(transition, kind, controller) {
    const definitionItems = [...new Map(transitions().map((item) => [String(item.candidateDefinitionId), item.candidateDefinition])).values()];
    const ownerHtml = (value) => referenceOptions(dataset.owners || [], value, "Owner");
    const definitionHtml = (value, nullable = true) => {
      const options = definitionItems.map((item) => ({ value: item.draftId || item.stableId, label: item.name || `Definition ${item.draftId || item.stableId}` }));
      return nullable ? nullableOptions(options, value, "No definition") : selectOptions(options, value);
    };
    const rows = (transition[kind] || []).map((child) => {
      const childId = entityId(child, kind.slice(0, -1));
      const common = `data-transition-id="${escapeHtml(localTransitionId(transition))}" data-child-kind="${kind}" data-child-id="${escapeHtml(childId)}"`;
      if (kind === "guards") {
        const reference = [4, 5].includes(Number(child.kind))
          ? `<select data-child-field="referenceId" ${common}>${ownerHtml(child.referenceId)}</select>`
          : Number(child.kind) === 3
            ? `<select data-child-field="referenceId" ${common}>${referenceOptions(controller.nodes || [], child.referenceId, "Node", "semanticRole")}</select>`
            : `<input type="number" min="0" max="65535" value="${Number(child.referenceId) || 0}" data-child-field="referenceId" ${common}>`;
        return `<div class="v40-author-row"><select data-child-field="kind" ${common}>${selectOptions(optionRecords("guardKind"), child.kind)}</select><label>Negate <input type="checkbox" data-child-field="negate" ${common} ${child.negate ? "checked" : ""}></label><label>Payload <input type="number" min="0" max="255" value="${child.payload}" data-child-field="payload" ${common}></label><label>Reference ${reference}</label><button type="button" data-child-action="remove" ${common}>Remove</button></div>`;
      }
      if (kind === "operations") {
        return `<div class="v40-author-row v40-author-row--wide"><select data-child-field="kind" ${common}>${selectOptions(optionRecords("operationKind"), child.kind)}</select><label>Definition <select data-child-field="definitionId" ${common}>${definitionHtml(child.definitionId)}</select></label><label>Owner <select data-child-field="ownerId" ${common}>${ownerHtml(child.ownerId)}</select></label><label>Replacement <select data-child-field="replacementDefinitionId" ${common}>${definitionHtml(child.replacementDefinitionId)}</select></label><label>Lifetime policy <select data-child-field="policyId" ${common}>${nullableOptions(optionRecords("lifetime"), child.policyId, "None")}</select></label><label>Instance <select data-child-field="instanceKey" ${common}>${definitionHtml(child.instanceKey)}</select></label><label>Busy <select data-child-field="busyPolicy" ${common}>${selectOptions(optionRecords("busyPolicy"), child.busyPolicy)}</select></label><label>Required <input type="checkbox" data-child-field="required" ${common} ${child.required ? "checked" : ""}></label><button type="button" data-child-action="remove" ${common}>Remove</button></div>`;
      }
      if (kind === "actions") {
        return `<div class="v40-author-row"><select data-child-field="phase" ${common}>${selectOptions(optionRecords("actionPhase"), child.phase)}</select><select data-child-field="kind" ${common}>${selectOptions(optionRecords("actionKind"), child.kind)}</select><small>Typed action payload and reference are reserved.</small><button type="button" data-child-action="remove" ${common}>Remove</button></div>`;
      }
      return `<div class="v40-author-row"><select data-child-field="kind" ${common}>${selectOptions(optionRecords("recoveryActionKind"), child.kind)}</select><label>Owner <select data-child-field="ownerId" ${common}>${ownerHtml(child.ownerId)}</select></label><label>Required <input type="checkbox" data-child-field="required" ${common} ${child.required ? "checked" : ""}></label><button type="button" data-child-action="remove" ${common}>Remove</button></div>`;
    }).join("");
    return rows || `<p class="v40-author-empty">No ${escapeHtml(kind.replace(/([A-Z])/g, " $1").toLowerCase())}.</p>`;
  }

  function renderTransitionAuthoring(transition, controller) {
    if (!transition) return "";
    const id = localTransitionId(transition);
    const definition = transition.candidateDefinition || {};
    const applicability = authoredApplicabilityFor(definition);
    const diagnostics = transitionAuthoringDiagnostics(transition);
    const controllerOptions = controllers().map((item) => ({ value: item.draftId || item.stableId, label: item.name }));
    const allNodes = controllers().flatMap((item) => (item.nodes || []).map((node) => ({
      value: node.draftId || node.stableId,
      label: `${item.name} · ${node.semanticRole || `role ${node.semanticRoleId}`}`,
    })));
    const transitionOptions = transitions().map((item) => ({ value: item.draftId || item.stableId, label: item.name || `Transition ${item.draftId || item.stableId}` }));
    const profileOptions = profiles().map((item) => ({ value: item.draftId || item.stableId, label: item.name }));
    const field = (label, control) => `<label class="v40-author-field"><span>${escapeHtml(label)}</span>${control}</label>`;
    const definitionField = (label, key, control) => field(label, control.replace(/^(<[^ >]+)/, `$1 data-definition-field="${key}" data-transition-id="${escapeHtml(id)}"`));
    const applicabilityField = (label, key, control) => field(label, control.replace(/^(<[^ >]+)/, `$1 data-applicability-field="${key}" data-transition-id="${escapeHtml(id)}"`));
    return `<details class="v40-transition-author" open data-transition-author="${escapeHtml(id)}"><summary><span><strong>Author transition and candidate</strong><small>${escapeHtml(transition.name || id)}</small></span></summary>
      ${diagnostics.length ? `<aside class="v40-validation"><strong>${diagnostics.length} authoring issue${diagnostics.length === 1 ? "" : "s"}</strong><ul>${diagnostics.slice(0, 8).map((item) => `<li>${escapeHtml(item.message)}</li>`).join("")}</ul></aside>` : ""}
      <div class="v40-author-grid">
        ${field("Transition name", `<input type="text" value="${escapeHtml(transition.name)}" data-transition-field="name" data-transition-id="${escapeHtml(id)}">`)}
        ${field("Transition owner", `<select data-transition-field="ownerId" data-transition-id="${escapeHtml(id)}">${referenceOptions(dataset.owners || [], transition.ownerId, "Owner")}</select>`)}
        ${definitionField("Definition name", "name", `<input type="text" value="${escapeHtml(definition.name || "New definition")}">`)}
        ${definitionField("Kind", "kind", `<select>${selectOptions(optionRecords("definitionKind"), definition.kind)}</select>`)}
        ${definitionField("Channel", "channel", `<select>${selectOptions(optionRecords("channel"), definition.channel)}</select>`)}
        ${definitionField("Priority", "priority", `<input type="number" min="0" max="65535" value="${definition.priority}">`)}
        ${definitionField("Controller scope", "controllerId", `<select>${nullableOptions(controllerOptions, definition.controllerId, "All controllers")}</select>`)}
        ${definitionField("Selector", "selectorKind", `<select>${selectOptions(optionRecords("selectorKind"), definition.selectorKind)}</select>`)}
        ${Number(definition.selectorKind) === 1
          ? definitionField("Exact node", "nodeId", `<select>${nullableOptions(allNodes, definition.nodeId, "Select node")}</select>`)
          : definitionField("Semantic role", "semanticRoleId", `<select>${selectOptions(dataset.semanticRoles || [], definition.semanticRoleId)}</select>`)}
        ${definitionField("Required owner", "requiredOwnerId", `<select>${referenceOptions(dataset.owners || [], definition.requiredOwnerId, "Owner")}</select>`)}
        ${definitionField("Map lifetime", "mapLifetime", `<select>${selectOptions(optionRecords("lifetime"), definition.mapLifetime)}</select>`)}
        ${definitionField("Battle lifetime", "battleLifetime", `<select>${selectOptions(optionRecords("lifetime"), definition.battleLifetime)}</select>`)}
        ${definitionField("Timer clock", "timerClock", `<select>${selectOptions(optionRecords("timerClock"), definition.timerClock)}</select>`)}
        ${definitionField("Timer source", "timerSource", `<select>${selectOptions(optionRecords("timerSource"), definition.timerSource)}</select>`)}
        ${definitionField("Timer value", "timerValue", `<input type="number" min="0" max="255" value="${definition.timerValue}">`)}
        ${definitionField("Hidden timer", "hiddenTimerPolicy", `<select>${selectOptions(optionRecords("hiddenTimerPolicy"), definition.hiddenTimerPolicy)}</select>`)}
        ${definitionField("Recovery policy", "recoveryPolicy", `<select>${selectOptions(optionRecords("recoveryPolicy"), definition.recoveryPolicy)}</select>`)}
        ${definitionField("Recovery transition", "recoveryTransitionId", `<select>${nullableOptions(transitionOptions, definition.recoveryTransitionId, "No recovery route")}</select>`)}
        ${definitionField("Tired origin", "tiredOriginKind", `<input type="number" min="0" max="3" value="${definition.tiredOriginKind}">`)}
      </div>
      <fieldset class="v40-author-checks"><legend>Ownership and lifecycle flags</legend>
        ${[["allowMultipleOwners", "Allow multiple owners"], ["allowMultipleInstancesPerOwner", "Allow multiple instances per owner"], ["authoredTiredBound", "Authored tired bound"], ["hasTiredOriginKind", "Use tired origin"]].map(([key, label]) => `<label><input type="checkbox" data-definition-field="${key}" data-transition-id="${escapeHtml(id)}" ${Number(definition[key]) ? "checked" : ""}> ${label}</label>`).join("")}
      </fieldset>
      <details class="v40-author-subsection" open><summary><strong>Applicability</strong></summary><div class="v40-author-grid">
        ${applicabilityField("Name", "name", `<input type="text" value="${escapeHtml(applicability.name || "New applicability")}">`)}
        ${applicabilityField("Kind", "kind", `<input type="number" min="0" max="65535" value="${applicability.kind}">`)}
        ${applicabilityField("Group mask", "groupMask", `<input type="number" min="0" max="4294967295" value="${applicability.groupMask}">`)}
        ${applicabilityField("Controller", "controllerId", `<select>${nullableOptions(controllerOptions, applicability.controllerId, "Any controller")}</select>`)}
        ${applicabilityField("Profile", "profileId", `<select>${nullableOptions(profileOptions, applicability.profileId, "Any profile")}</select>`)}
        ${applicabilityField("Minimum", "minimum", `<input type="number" min="0" max="255" value="${applicability.minimum}">`)}
        ${applicabilityField("Maximum", "maximum", `<input type="number" min="0" max="255" value="${applicability.maximum}">`)}
        ${applicabilityField("Flags", "flags", `<input type="number" min="0" max="65535" value="${applicability.flags}">`)}
      </div></details>
      ${[["guards", "Guards"], ["operations", "Operations"], ["actions", "Transition actions"], ["recoveryActions", "Recovery actions"]].map(([kind, label]) => `<details class="v40-author-subsection" open><summary><span><strong>${label}</strong><small>${(transition[kind] || []).length} rows</small></span></summary><div class="v40-author-rows">${childRows(transition, kind, controller)}</div><button type="button" data-child-action="add" data-child-kind="${kind}" data-transition-id="${escapeHtml(id)}">Add ${label.toLowerCase().replace(/s$/, "")}</button></details>`).join("")}
    </details>`;
  }

  function renderControllerInspector() {
    const controller = selectedController();
    if (!controller) {
      inspector.innerHTML = `<div class="empty-state"><span class="empty-state__glyph" aria-hidden="true">◇</span><h2>Select a controller</h2><p>Controllers bind complete state profiles to unique semantic nodes and own their transition roster.</p></div>`;
      return;
    }
    const localTransitions = controllerTransitions(controller);
    if (!localTransitions.some((transition) => localTransitionId(transition) === selectedTransitionId)) {
      selectedTransitionId = localTransitions[0] ? localTransitionId(localTransitions[0]) : "";
    }
    const errors = validateControllerDraft(controller, { ...dataset, stateProfiles: profiles(), controllers: controllers() }, localTransitions);
    const entityDiagnostics = diagnosticsFor("controller", controller);
    const profileOptions = profiles().map((profile) => ({
      value: profile.draftId || profile.stableId,
      label: `${profile.name} · ${profile.draftId ? "draft" : profile.stableId}`,
    }));
    const ownerOptions = (dataset.owners || []).map((owner) => ({ value: owner.stableId, label: owner.name || `Owner ${owner.stableId}` }));
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
      const nodeDiagnostics = diagnosticsFor("controllerNode", node);
      return `<tr data-controller-node="${escapeHtml(nodeId)}">
        <td><input type="radio" name="controller-base-node" data-node-field="base" data-node-id="${escapeHtml(nodeId)}" ${node.base ? "checked" : ""} aria-label="Use node ${index + 1} as base"></td>
        <td><strong>${node.draftId ? escapeHtml(node.draftId) : node.stableId}${nodeDiagnostics.length ? `<span class="v40-diagnostic-badge" aria-label="${nodeDiagnostics.length} validation issues">${nodeDiagnostics.length}</span>` : ""}</strong><small>${usageCount} transition backlink${usageCount === 1 ? "" : "s"}</small></td>
        <td><select data-node-field="semanticRoleId" data-node-id="${escapeHtml(nodeId)}">${nodeRoleOptions(node, controller)}</select>${Number(node.semanticRoleId) === 7 ? `<select data-node-field="customRoleId" data-node-id="${escapeHtml(nodeId)}" aria-label="Custom role">${customRoleOptions(node, controller)}</select>` : ""}</td>
        <td><select data-node-field="profileRef" data-node-id="${escapeHtml(nodeId)}">${selectOptions(profileOptions, nodeProfileRef(node))}</select></td>
        <td class="v40-row-actions"><button type="button" data-node-action="up" data-node-id="${escapeHtml(nodeId)}" ${index === 0 ? "disabled" : ""} aria-label="Move node up">↑</button><button type="button" data-node-action="down" data-node-id="${escapeHtml(nodeId)}" ${index === controller.nodes.length - 1 ? "disabled" : ""} aria-label="Move node down">↓</button><button type="button" data-node-action="remove" data-node-id="${escapeHtml(nodeId)}" ${controller.nodes.length === 1 ? "disabled" : ""}>Remove</button></td>
      </tr>`;
    }).join("");
    const transitionRows = localTransitions.map((transition, index) => {
      const transitionId = localTransitionId(transition);
      const transitionDiagnostics = diagnosticsFor("transition", transition);
      return `<tr data-controller-transition="${escapeHtml(transitionId)}">
        <td><strong>${transition.draftId ? escapeHtml(transition.draftId) : transition.stableId}${transitionDiagnostics.length ? `<span class="v40-diagnostic-badge" aria-label="${transitionDiagnostics.length} validation issues">${transitionDiagnostics.length}</span>` : ""}</strong></td>
        <td><select data-transition-field="trigger" data-transition-id="${escapeHtml(transitionId)}">${selectOptions(dataset.transitionGraph.triggerOptions || [], transition.trigger)}</select></td>
        <td><fieldset class="v40-role-mask"><legend class="sr-only">Allowed source roles</legend>${(dataset.semanticRoles || []).map((role) => `<label title="${escapeHtml(role.label)}"><input type="checkbox" data-transition-role="${role.value}" data-transition-id="${escapeHtml(transitionId)}" ${Number(transition.fromRoleMask) & (1 << (Number(role.value) - 1)) ? "checked" : ""}><span>${escapeHtml(role.label.slice(0, 1))}</span></label>`).join("")}</fieldset></td>
        <td><button type="button" data-transition-action="author" data-transition-id="${escapeHtml(transitionId)}" aria-pressed="${transitionId === selectedTransitionId}">${escapeHtml(String(transition.candidateDefinitionId))}</button></td>
        <td><select data-transition-field="ownerId" data-transition-id="${escapeHtml(transitionId)}" aria-label="Owner">${selectOptions(ownerOptions, transition.ownerId)}</select></td>
        <td><input type="number" min="1" max="65535" value="${transition.dispatchPriority}" data-transition-field="dispatchPriority" data-transition-id="${escapeHtml(transitionId)}"></td>
        <td class="v40-row-actions"><button type="button" data-transition-action="up" data-transition-id="${escapeHtml(transitionId)}" ${index === 0 ? "disabled" : ""} aria-label="Move transition up">↑</button><button type="button" data-transition-action="down" data-transition-id="${escapeHtml(transitionId)}" ${index === localTransitions.length - 1 ? "disabled" : ""} aria-label="Move transition down">↓</button><button type="button" data-transition-action="remove" data-transition-id="${escapeHtml(transitionId)}">Remove</button></td>
      </tr>`;
    }).join("");
    inspector.innerHTML = `<article class="profile-field-editor v40-controller-editor" data-selected-controller="${escapeHtml(controllerIdFor(controller))}">
      <header class="v40-state-editor__heading"><div><span class="eyebrow">Typed controller</span><h2>${escapeHtml(controller.name)}</h2><small>${controller.created ? escapeHtml(controller.draftId) : `Stable ID ${controller.stableId}`}</small></div><div class="v40-state-editor__actions"><button class="button" type="button" data-controller-action="duplicate">Duplicate controller</button></div></header>
      ${errors.length || entityDiagnostics.length ? `<aside class="v40-validation" role="status"><strong>${errors.length + entityDiagnostics.length} model issue${errors.length + entityDiagnostics.length === 1 ? "" : "s"}</strong><span>${escapeHtml(entityDiagnostics[0]?.message || errors[0]?.message)}</span></aside>` : ""}
      <section class="v40-controller-identity"><label><span>Name</span><input type="text" value="${escapeHtml(controller.name)}" data-controller-identity="name"></label><div><span>Identity</span><strong>${controller.created ? escapeHtml(controller.draftId) : controller.stableId}</strong><small>${controller.created ? "Pending Global Save" : escapeHtml(controller.registryKey)}</small></div></section>
      <details class="pv2-field-section" open><summary><span><strong>Controller defaults</strong><small>Typed scalar defaults and stable policy references.</small></span></summary><div class="profile-fields">${scalarFields}${policyControls}</div></details>
      <section class="v40-controller-section"><header><div><span class="eyebrow">State roster</span><h3>Bound nodes</h3></div><button type="button" data-controller-action="add-node">Add node</button></header><div class="v40-table-scroll"><table class="v40-controller-table"><thead><tr><th>Base</th><th>Node ID</th><th>Semantic role</th><th>Bound profile</th><th>Order</th></tr></thead><tbody>${nodeRows}</tbody></table></div></section>
      <section class="v40-controller-section"><header><div><span class="eyebrow">Authoritative graph</span><h3>Transitions</h3></div><button type="button" data-controller-action="add-transition">Add transition</button></header><div class="v40-table-scroll"><table class="v40-controller-table v40-transition-table"><thead><tr><th>Row ID</th><th>Event</th><th>From roles</th><th>Definition</th><th>Owner</th><th>Priority</th><th>Order</th></tr></thead><tbody>${transitionRows || `<tr><td colspan="7">No transitions.</td></tr>`}</tbody></table></div></section>
      ${renderTransitionAuthoring(localTransitions.find((transition) => localTransitionId(transition) === selectedTransitionId), controller)}
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
    const draft = createCompleteStateDraft(
      dataset.stateProfileFields, source || saved[0], ensureUniqueName(preferred),
    );
    if (!source) {
      draft.name = ensureUniqueName(preferred);
      draft.descriptiveTags = [];
    }
    created.push(draft);
    selectedId = draft.draftId;
    syncDirty();
    render();
    requestAnimationFrame(() => inspector.querySelector("[data-state-identity='name']")?.select());
  }

  function deleteSelectedProfile() {
    const profile = selected();
    if (!profile) return;
    if (!profile.created) {
      const blockerIndex = dataset.behaviorModelAuthoring?.profileDeleteBlockers;
      if (!blockerIndex || typeof blockerIndex !== "object") {
        setStatus("State deletion is unavailable because authoritative backlink data is missing.", "error");
        return;
      }
      const blockers = blockerIndex[String(profile.stableId)] || [];
      if (blockers.length) {
        const domains = [...new Set(blockers.map((item) => item.domain))].join(" and ");
        setStatus(`Cannot delete ${profile.name}: it is referenced by ${domains}.`, "error");
        return;
      }
    }
    if (profile.created) created.splice(created.indexOf(profile), 1);
    else {
      updates.delete(profile.stableId);
      removedProfileIds.add(profile.stableId);
    }
    selectedId = profiles()[0] ? idFor(profiles()[0]) : "";
    syncDirty();
    render();
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
    // Shared transitions remain shared and gain the new controller through
    // membership. Only controller-scoped rows need an independent copy.
    const sourceTransitions = source
      ? controllerTransitions(source).filter((transition) => transition.candidateDefinition?.controllerId)
      : [];
    const draft = createControllerDraft({
      source, profiles: profiles(), transitions: sourceTransitions,
      policyDefaults: dataset.controllers?.[0]?.policyIds,
      transitionOrderStart: transitions().length,
      behaviorModelAuthoring: dataset.behaviorModelAuthoring,
    });
    draft.controller.name = uniqueControllerName(source ? `${source.name} copy` : "New controller");
    createdControllers.push(draft.controller);
    createdTransitions.push(...draft.transitions);
    const allControllerIds = controllers().map((controller) => controller.draftId || controller.stableId);
    const sharedTransitions = transitions().filter((transition) => !transition.candidateDefinition?.controllerId);
    sharedTransitions.forEach((transition) => {
      editableTransition(transition).controllerIds = [...allControllerIds];
    });
    draft.controller.transitionIds = [
      ...draft.controller.transitionIds,
      ...sharedTransitions.map((transition) => transition.draftId || transition.stableId),
    ];
    selectedControllerId = draft.controller.draftId;
    syncDirty();
    render();
    requestAnimationFrame(() => inspector.querySelector("[data-controller-identity='name']")?.select());
  }

  function updateControllerValue(domain, key, raw) {
    const selectedValue = selectedController();
    if (!selectedValue) return;
    const value = domain === "identity" ? String(raw) : Number(raw);
    const previous = domain === "identity" ? selectedValue[key] : selectedValue[domain]?.[key];
    if (previous === value) return;
    const controller = editableController(selectedValue);
    if (domain === "identity") controller[key] = value;
    else controller[domain][key] = value;
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
    const selectedValue = selectedController();
    const current = selectedValue?.nodes.find((item) => localNodeId(item) === nodeId);
    if (!current) return;
    const value = key === "base" ? Boolean(raw)
      : key === "profileRef" && String(raw).startsWith("draft:") ? String(raw) : Number(raw);
    if (key === "base" && current.base && value) return;
    if (key !== "base" && current[key] === value) return;
    const controller = editableController(selectedValue);
    const node = controller?.nodes.find((item) => localNodeId(item) === nodeId);
    if (!node) return;
    if (key === "base") {
      controller.nodes.forEach((item) => { item.base = item === node; });
      controller.baseNodeId = nodeId;
    } else {
      node[key] = value;
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
    if ((action === "remove" && controller.nodes.length <= 1)
        || (action === "up" && index === 0)
        || (action === "down" && index === controller.nodes.length - 1)) return;
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
    transition.order = transitions().length;
    const controllerId = controller.draftId || controller.stableId;
    const definition = clone(transition.candidateDefinition || {});
    const sourceDefinitionId = transition.candidateDefinitionId ?? definition.stableId ?? definition.draftId;
    definition.stableId = null;
    definition.draftId = draftId();
    definition.controllerId = controllerId;
    definition.selectorKind = 1;
    definition.nodeId = controller.baseNodeId || localNodeId(controller.nodes?.[0]);
    definition.semanticRoleId = 0;
    definition.flags = 1;
    if (!Number(definition.hasTiredOriginKind)) definition.tiredOriginKind = 0;
    const sourceApplicabilityId = definition.applicabilityId ?? definition.applicability?.stableId;
    const authoredApplicability = (dataset.behaviorModelAuthoring?.applicability || [])
      .find((item) => String(item.stableId) === String(sourceApplicabilityId));
    const applicability = clone(authoredApplicability || {
      name: "New applicability", kind: 1, groupMask: 0xFFFFFFFF,
      controllerId, profileId: 0, minimum: 0, maximum: 0, flags: 0,
    });
    applicability.stableId = null;
    applicability.draftId = draftId();
    applicability.controllerId = controllerId;
    applicability.kind = Number(applicability.kind || 1) | 2;
    definition.applicability = applicability;
    definition.applicabilityId = applicability.draftId;
    transition.candidateDefinition = definition;
    transition.candidateDefinitionId = definition.draftId;
    transition.controllerIds = [controllerId];
    transition.guards = (transition.guards || []).map((guard) => ({
      ...guard, stableId: null, draftId: draftId(),
      referenceId: guard.kind === 3 ? controller.baseNodeId : guard.referenceId,
    }));
    transition.operations = (transition.operations || []).map((operation) => ({
      ...operation, stableId: null, draftId: draftId(),
      definitionId: String(operation.definitionId) === String(sourceDefinitionId) ? definition.draftId : operation.definitionId,
      replacementDefinitionId: String(operation.replacementDefinitionId) === String(sourceDefinitionId) ? definition.draftId : operation.replacementDefinitionId,
      instanceKey: String(operation.instanceKey) === String(sourceDefinitionId) ? definition.draftId : operation.instanceKey,
    }));
    transition.actions = (transition.actions || []).map((action) => ({ ...action, stableId: null, draftId: draftId() }));
    transition.recoveryActions = (transition.recoveryActions || []).map((action) => ({ ...action, stableId: null, draftId: draftId() }));
    transition.created = true;
    createdTransitions.push(transition);
    selectedTransitionId = transition.draftId;
    const editable = editableController(controller);
    editable.transitionIds = [...(editable.transitionIds || []), transition.draftId];
    syncDirty();
    render();
  }

  function findTransition(id) {
    return transitions().find((transition) => localTransitionId(transition) === id) || null;
  }

  function updateTransition(id, key, raw) {
    const found = findTransition(id);
    const value = key === "name" ? String(raw)
      : key === "candidateDefinitionId" && String(raw).startsWith("draft:") ? String(raw)
        : Number(raw);
    if (!found || found[key] === value) return;
    const transition = editableTransition(found);
    if (!transition) return;
    const previousCandidateId = transition.candidateDefinitionId;
    transition[key] = value;
    if (key === "candidateDefinitionId") {
      const source = transitions().find((item) => String(item.candidateDefinitionId) === String(raw))
        || (dataset.transitionGraph?.transitions || []).find((item) => String(item.candidateDefinitionId) === String(raw));
      transition.candidateDefinition = clone(source?.candidateDefinition || null);
      transition.controllerIds = transition.candidateDefinition?.controllerId
        ? [transition.candidateDefinition.controllerId]
        : controllers().map((controller) => controller.draftId || controller.stableId);
      transition.operations = (transition.operations || []).map((operation) => ({
        ...operation,
        definitionId: String(operation.definitionId) === String(previousCandidateId) ? transition.candidateDefinitionId : operation.definitionId,
        replacementDefinitionId: String(operation.replacementDefinitionId) === String(previousCandidateId) ? transition.candidateDefinitionId : operation.replacementDefinitionId,
        instanceKey: String(operation.instanceKey) === String(previousCandidateId) ? transition.candidateDefinitionId : operation.instanceKey,
      }));
      const transitionRef = transition.draftId || transition.stableId;
      const scope = new Set((transition.controllerIds || []).map(String));
      controllers().forEach((controller) => {
        const controllerRef = controller.draftId || controller.stableId;
        const references = (controller.transitionIds || []).map(String);
        const contains = references.includes(String(transitionRef));
        if (scope.has(String(controllerRef)) === contains) return;
        const editableOwner = editableController(controller);
        editableOwner.transitionIds = scope.has(String(controllerRef))
          ? [...editableOwner.transitionIds, transitionRef]
          : editableOwner.transitionIds.filter((value) => String(value) !== String(transitionRef));
      });
    } else if (key === "ownerId") {
      if (Number(transition.candidateDefinition?.hasRequiredOwnerId)) transition.candidateDefinition.requiredOwnerId = value;
      transition.operations = (transition.operations || []).map((operation) => [1, 2, 3, 4].includes(Number(operation.kind))
        ? { ...operation, ownerId: value } : operation);
    }
    syncDirty();
  }

  function updateTransitionMembership(transition) {
    const scope = transition.candidateDefinition?.controllerId
      ? [transition.candidateDefinition.controllerId]
      : controllers().map((item) => item.draftId || item.stableId);
    transition.controllerIds = scope;
    const transitionRef = transition.draftId || transition.stableId;
    const wanted = new Set(scope.map(String));
    controllers().forEach((controller) => {
      const controllerRef = controller.draftId || controller.stableId;
      const contains = (controller.transitionIds || []).some((item) => String(item) === String(transitionRef));
      if (wanted.has(String(controllerRef)) === contains) return;
      const owner = editableController(controller);
      owner.transitionIds = wanted.has(String(controllerRef))
        ? [...owner.transitionIds, transitionRef]
        : owner.transitionIds.filter((item) => String(item) !== String(transitionRef));
    });
  }

  function definitionValue(key, raw, checked) {
    const booleanFields = new Set(["allowMultipleOwners", "allowMultipleInstancesPerOwner", "authoredTiredBound", "hasTiredOriginKind"]);
    const referenceFields = new Set(["controllerId", "nodeId", "requiredOwnerId", "recoveryTransitionId"]);
    if (key === "name") return String(raw);
    if (booleanFields.has(key)) return checked ? 1 : 0;
    if (referenceFields.has(key) && (String(raw) === "0" || raw === "")) return null;
    if ((referenceFields.has(key) || key === "semanticRoleId") && String(raw).startsWith("draft:")) return String(raw);
    return Number(raw);
  }

  function updateDefinition(id, key, raw, checked = false) {
    const source = findTransition(id);
    if (!source?.candidateDefinition) return;
    const definitionId = String(source.candidateDefinitionId);
    const value = definitionValue(key, raw, checked);
    const affected = transitions().filter((item) => String(item.candidateDefinitionId) === definitionId);
    affected.forEach((item) => {
      const transition = editableTransition(item);
      const definition = transition.candidateDefinition;
      definition.applicability = clone(authoredApplicabilityFor(definition));
      definition[key] = value;
      if (key === "requiredOwnerId") definition.hasRequiredOwnerId = value ? 1 : 0;
      if (key === "selectorKind") {
        if (value === 1) {
          definition.nodeId = selectedController()?.baseNodeId || localNodeId(selectedController()?.nodes?.[0]);
          definition.semanticRoleId = 0;
          definition.flags = 1;
        } else {
          definition.nodeId = null;
          definition.semanticRoleId = Number(selectedController()?.nodes?.[0]?.semanticRoleId) || 1;
          definition.flags = 0;
        }
      }
      if (key === "hasTiredOriginKind" && !value) definition.tiredOriginKind = 0;
      if (key === "tiredOriginKind") definition.hasTiredOriginKind = value ? 1 : 0;
      if (key === "timerClock") {
        if (value === 0) Object.assign(definition, { timerSource: 0, timerValue: 0, hiddenTimerPolicy: 0 });
        else {
          if (!Number(definition.timerSource)) definition.timerSource = 1;
          if (!Number(definition.timerValue)) definition.timerValue = 1;
          if (!Number(definition.hiddenTimerPolicy)) definition.hiddenTimerPolicy = 1;
        }
      }
      if (key === "recoveryPolicy" && value === 0) definition.recoveryTransitionId = null;
      if (key === "controllerId") updateTransitionMembership(transition);
    });
    syncDirty();
  }

  function updateApplicability(id, key, raw) {
    const source = findTransition(id);
    const sourceRule = authoredApplicabilityFor(source?.candidateDefinition);
    if (!source || !sourceRule) return;
    const applicabilityId = String(sourceRule.draftId ?? sourceRule.stableId);
    const referenceFields = new Set(["controllerId", "profileId"]);
    const value = key === "name" ? String(raw)
      : referenceFields.has(key) && (String(raw) === "0" || raw === "") ? null
        : referenceFields.has(key) && String(raw).startsWith("draft:") ? String(raw)
          : Number(raw);
    transitions().filter((item) => String(authoredApplicabilityFor(item.candidateDefinition)?.draftId
      ?? authoredApplicabilityFor(item.candidateDefinition)?.stableId) === applicabilityId).forEach((item) => {
      const transition = editableTransition(item);
      transition.candidateDefinition.applicability = clone(authoredApplicabilityFor(transition.candidateDefinition));
      transition.candidateDefinition.applicability[key] = value;
      if (["controllerId", "profileId", "minimum"].includes(key)) {
        const rule = transition.candidateDefinition.applicability;
        rule.kind = (Number(rule.kind) | 1) & ~14;
        if (rule.controllerId) rule.kind |= 2;
        if (rule.profileId) rule.kind |= 4;
        if (rule.minimum) rule.kind |= 8;
      }
      transition.candidateDefinition.applicabilityId = transition.candidateDefinition.applicability.draftId
        || transition.candidateDefinition.applicability.stableId;
    });
    syncDirty();
  }

  function normalizeOperation(operation, transition) {
    const definitionId = transition.candidateDefinitionId;
    const ownerId = transition.ownerId;
    const kind = Number(operation.kind);
    Object.assign(operation, { busyPolicy: Number(operation.busyPolicy) || 1, required: kind === 3 });
    if (kind === 1) Object.assign(operation, { definitionId, ownerId, replacementDefinitionId: null, policyId: null, instanceKey: definitionId });
    else if (kind === 2) Object.assign(operation, { definitionId, ownerId, replacementDefinitionId: operation.replacementDefinitionId || definitionId, policyId: null, instanceKey: definitionId });
    else if ([3, 4].includes(kind)) Object.assign(operation, { definitionId, ownerId, replacementDefinitionId: null, policyId: null, instanceKey: null });
    else if (kind === 5) Object.assign(operation, { definitionId: null, ownerId, replacementDefinitionId: null, policyId: null, instanceKey: null, required: false });
    else Object.assign(operation, { definitionId: null, ownerId: null, replacementDefinitionId: null, policyId: Number(operation.policyId) || 1, instanceKey: null, required: false });
  }

  function findChild(transition, kind, childId) {
    return (transition?.[kind] || []).find((item) => entityId(item, kind.slice(0, -1)) === childId);
  }

  function updateChild(transitionId, kind, childId, key, raw, checked = false) {
    const source = findTransition(transitionId);
    if (!source || !CHILD_FIELDS[kind]) return;
    const transition = editableTransition(source);
    const child = findChild(transition, kind, childId);
    if (!child) return;
    const booleanFields = new Set(["negate", "required"]);
    const optionalRefs = new Set(["referenceId", "definitionId", "ownerId", "replacementDefinitionId", "policyId", "instanceKey"]);
    child[key] = booleanFields.has(key) ? Boolean(checked)
      : optionalRefs.has(key) && (String(raw) === "0" || raw === "") ? null
        : optionalRefs.has(key) && String(raw).startsWith("draft:") ? String(raw)
          : Number(raw);
    if (kind === "operations" && key === "kind") normalizeOperation(child, transition);
    syncDirty();
  }

  function childAction(transitionId, kind, childId, action) {
    const source = findTransition(transitionId || selectedTransitionId);
    if (!source || !CHILD_FIELDS[kind]) return;
    const transition = editableTransition(source);
    if (action === "remove") {
      const index = transition[kind].findIndex((item) => entityId(item, kind.slice(0, -1)) === childId);
      if (index >= 0) transition[kind].splice(index, 1);
    } else if (action === "add") {
      const identity = { stableId: null, draftId: draftId() };
      if (kind === "guards") transition.guards.push({ ...identity, kind: 1, negate: false, payload: 0, referenceId: null });
      else if (kind === "operations") {
        const operation = { ...identity, definitionId: transition.candidateDefinitionId, ownerId: transition.ownerId, replacementDefinitionId: null, policyId: null, instanceKey: transition.candidateDefinitionId, kind: 1, busyPolicy: 1, required: false };
        normalizeOperation(operation, transition);
        transition.operations.push(operation);
      } else if (kind === "actions") transition.actions.push({ ...identity, phase: 1, kind: 1, referenceId: null, payload: 0 });
      else transition.recoveryActions.push({ ...identity, ownerId: transition.ownerId, kind: 1, required: true });
    }
    syncDirty();
    renderInspector();
  }

  function updateTransitionRole(id, role, checked) {
    const found = findTransition(id);
    if (!found) return;
    const bit = 1 << (Number(role) - 1);
    const value = checked ? Number(found.fromRoleMask) | bit : Number(found.fromRoleMask) & ~bit;
    if (value === Number(found.fromRoleMask)) return;
    const transition = editableTransition(found);
    transition.fromRoleMask = value;
    transition.fromSemanticRoleIds = (dataset.semanticRoles || []).map((item) => Number(item.value)).filter((value) => transition.fromRoleMask & (1 << (value - 1)));
    syncDirty();
  }

  function transitionAction(id, action) {
    const controller = selectedController();
    const local = controllerTransitions(controller);
    const index = local.findIndex((transition) => localTransitionId(transition) === id);
    if (!controller || index < 0) return;
    const transition = local[index];
    if (action === "author") {
      selectedTransitionId = id;
      state.selectedTransitionKey = id;
      renderInspector();
      return;
    }
    if (action === "remove") {
      const removedOrder = Number(transition.order);
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
      transitions().filter((item) => Number(item.order) > removedOrder).forEach((item) => {
        editableTransition(item).order = Number(item.order) - 1;
      });
      if (selectedTransitionId === id) selectedTransitionId = "";
    } else {
      const otherIndex = action === "up" ? index - 1 : index + 1;
      if (otherIndex < 0 || otherIndex >= local.length) return;
      const first = editableTransition(transition);
      const second = editableTransition(local[otherIndex]);
      [first.order, second.order] = [second.order, first.order];
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
    state.profileDeckMode = mode;
    render();
  }

  function updateIdentity(key, raw) {
    const selectedValue = selected();
    if (!selectedValue) return;
    const value = key === "descriptiveTags"
      ? [...new Set(String(raw).split(",").map((tag) => tag.trim()).filter(Boolean))]
      : String(raw);
    if (JSON.stringify(selectedValue[key]) === JSON.stringify(value)) return;
    const profile = editable(selectedValue);
    if (key === "descriptiveTags") {
      profile.descriptiveTags = value;
    } else profile[key] = value;
    syncDirty();
    renderList();
  }

  function updateField(key, raw) {
    const selectedValue = selected();
    const value = Number(raw);
    if (!selectedValue || selectedValue.values[key] === value) return;
    const profile = editable(selectedValue);
    profile.values[key] = value;
    syncDirty();
    renderList();
  }

  function resetLocalDrafts() {
    const hadChanges = currentCommit().count > 0;
    const previous = selected();
    const previousStableId = previous?.stableId;
    updates.clear();
    created.splice(0);
    removedProfileIds.clear();
    controllerUpdates.clear();
    createdControllers.splice(0);
    transitionUpdates.clear();
    createdTransitions.splice(0);
    removedTransitionIds.clear();
    selectedId = previousStableId && saved.some((profile) => profile.stableId === previousStableId)
      ? `state:${previousStableId}`
      : (saved[0] ? `state:${saved[0].stableId}` : "");
    selectedControllerId = savedControllers[0] ? `controller:${savedControllers[0].stableId}` : "";
    selectedTransitionId = "";
    syncDirty({ notify: hadChanges });
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
          || !Array.isArray(dataset.controllers) || !Array.isArray(dataset.transitionGraph?.transitions)
          || !Array.isArray(dataset.owners) || !Array.isArray(dataset.overrideDefinitions)
          || !Array.isArray(dataset.applicability) || Number(dataset.stackPreview?.capacity) !== 8) {
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
      syncDirty({ notify: false });
      stackPreviewController?.destroy();
      stackPreviewController = createStackPreviewController({
        model: dataset,
        getDraft: () => state.v40BehaviorModelDraft,
        elements,
        setStatus,
      });
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
    if (action === "delete") return void deleteSelectedProfile();
    const controllerActionName = event.target.closest("[data-controller-action]")?.dataset.controllerAction;
    if (controllerActionName === "duplicate") return void addController(selectedController());
    if (controllerActionName === "add-node") return void addNode();
    if (controllerActionName === "add-transition") return void addTransition();
    const nodeButton = event.target.closest("[data-node-action]");
    if (nodeButton) return void nodeAction(nodeButton.dataset.nodeId, nodeButton.dataset.nodeAction);
    const transitionButton = event.target.closest("[data-transition-action]");
    if (transitionButton) return void transitionAction(transitionButton.dataset.transitionId, transitionButton.dataset.transitionAction);
    const childButton = event.target.closest("[data-child-action]");
    if (childButton) return void childAction(childButton.dataset.transitionId, childButton.dataset.childKind, childButton.dataset.childId, childButton.dataset.childAction);
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
    else if (event.target.matches("[data-definition-field]")) updateDefinition(event.target.dataset.transitionId, event.target.dataset.definitionField, event.target.value, event.target.checked);
    else if (event.target.matches("[data-applicability-field]")) updateApplicability(event.target.dataset.transitionId, event.target.dataset.applicabilityField, event.target.value);
    else if (event.target.matches("[data-child-field]")) updateChild(event.target.dataset.transitionId || selectedTransitionId, event.target.dataset.childKind, event.target.dataset.childId, event.target.dataset.childField, event.target.value, event.target.checked);
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
    if (event.target.matches("[data-definition-field]")) {
      updateDefinition(event.target.dataset.transitionId, event.target.dataset.definitionField, event.target.value, event.target.checked);
      renderInspector();
      return;
    }
    if (event.target.matches("[data-applicability-field]")) {
      updateApplicability(event.target.dataset.transitionId, event.target.dataset.applicabilityField, event.target.value);
      renderInspector();
      return;
    }
    if (event.target.matches("[data-child-field]")) {
      updateChild(event.target.dataset.transitionId || selectedTransitionId, event.target.dataset.childKind, event.target.dataset.childId, event.target.dataset.childField, event.target.value, event.target.checked);
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
    hasChanges: () => currentCommit().count > 0,
    changeCount: () => currentCommit().count,
    hasInvalid: () => blockingDiagnostics().length > 0,
    validationCount: () => blockingDiagnostics().length,
    validationMessage: () => blockingDiagnostics()[0]?.message || "",
    focusFirstInvalid: () => inspector.querySelector("[aria-invalid='true']")?.focus(),
    commitPayload: () => {
      const commit = currentCommit();
      return commit.count && commit.transaction ? { behaviorModel: commit.transaction } : {};
    },
    clearCommitted: (result = {}) => {
      const mapping = result?.domains?.behaviorModel?.draftIdMap || result?.draftIdMap || {};
      if (mapping[selectedId]) selectedId = `state:${mapping[selectedId]}`;
      if (mapping[selectedControllerId]) selectedControllerId = `controller:${mapping[selectedControllerId]}`;
      if (mapping[selectedTransitionId]) selectedTransitionId = `transition:${mapping[selectedTransitionId]}`;
      updates.clear(); created.splice(0); removedProfileIds.clear();
      controllerUpdates.clear(); createdControllers.splice(0);
      transitionUpdates.clear(); createdTransitions.splice(0); removedTransitionIds.clear();
      state.selectedProfileKey = selectedId;
      state.selectedControllerKey = selectedControllerId;
      syncDirty();
    },
    reset: resetLocalDrafts,
    refresh: () => (!loading && currentCommit().count === 0 ? load() : undefined),
    refreshPreservingDrafts: () => load(),
    navigationContext: () => mode === "controllers"
      ? ({ selection: selectedControllerId, label: selectedController()?.name || "" })
      : ({ selection: selectedId, label: selected()?.name || "" }),
    restoreSelection: (id) => String(id).startsWith("controller:") || String(id).startsWith("draft:") && controllers().some((controller) => controllerIdFor(controller) === id)
      ? (setMode("controllers"), selectController(id, { report: false }))
      : (setMode("states"), selectProfile(id, { report: false })),
    behaviorModelDraft: () => clone(state.v40BehaviorModelDraft),
    wholeGraphDiagnostics: () => clone(graphDiagnostics),
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
      stackPreviewController?.destroy();
    },
  });
}
