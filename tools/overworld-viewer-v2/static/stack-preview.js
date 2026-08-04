/* Deterministic, client-only OWBD V40 stack preview. */

import {
  materializeDraftGraph,
  validateBehaviorModel,
  validateStackInput,
  VALIDATION_CODES,
} from "./model-validation.js";

export const STACK_PREVIEW_CODES = Object.freeze({
  CAPACITY: "STACK_CAPACITY_EXCEEDED",
  OWNER: "OWNER_NOT_FOUND",
  REQUIRED_OWNER: "OWNER_REQUIRED_MISMATCH",
  MULTIPLE_OWNERS: "OWNER_MULTIPLICITY_CONFLICT",
  MULTIPLE_INSTANCES: "INSTANCE_MULTIPLICITY_CONFLICT",
  INSTANCE_KEY: "INSTANCE_KEY_INVALID",
  DUPLICATE_IDENTITY: "LAYER_IDENTITY_DUPLICATE",
  DANGLING: "REFERENCE_DANGLING",
  AMBIGUOUS: "SELECTOR_AMBIGUOUS",
  MODIFIER: "MODIFIER_PREVIEW_UNSUPPORTED",
  DRAFT: "DRAFT_REFERENCE_INVALID",
  GRAPH: "EVENT_GRAPH_INVALID",
  STEP: "EVENT_STEP_INVALID",
  LIMIT: "EVENT_SEQUENCE_LIMIT_EXCEEDED",
  TRANSITION: "TRANSITION_NOT_FOUND",
  TRANSITION_AMBIGUOUS: "TRANSITION_DISPATCH_AMBIGUOUS",
  OPERATION: "TRANSITION_OPERATION_FAILED",
  TIMER: "TIMER_RECOVERY_INVALID",
});

export const STACK_SEQUENCE_LIMITS = Object.freeze({ steps: 128, ticksPerStep: 255 });

const clone = (value) => JSON.parse(JSON.stringify(value));
const ref = (entity) => entity?.draftId ?? entity?.stableId;
const same = (left, right) => String(left) === String(right);

function issue(code, message, path = "") {
  return { code, message, path };
}

export function materializePreviewModel(savedModel, draft = null) {
  return materializeDraftGraph(savedModel, draft);
}

export function comparePrecedence(left, right) {
  for (const key of ["channel", "priority", "definitionStableId", "ownerId", "instanceKey"]) {
    const difference = Number(left[key]) - Number(right[key]);
    if (difference) return difference < 0 ? -1 : 1;
  }
  return 0;
}

function selectedController(model, controllerRef) {
  return (model.controllers || []).find((controller) => same(ref(controller), controllerRef));
}

function selectedProfile(model, profileRef) {
  return (model.stateProfiles || []).find((profile) => same(ref(profile), profileRef));
}

function resolvedNode(model, controller, definition, errors, path) {
  const nodes = controller.nodes || [];
  let matches = [];
  if (Number(definition.selectorKind) === 1) {
    matches = nodes.filter((node) => same(ref(node), definition.nodeId));
  } else if (Number(definition.selectorKind) === 2) {
    matches = nodes.filter((node) => Number(node.semanticRoleId) === Number(definition.semanticRoleId));
  } else {
    errors.push(issue(STACK_PREVIEW_CODES.DANGLING, "Definition has an unknown selector kind.", `${path}.selectorKind`));
    return null;
  }
  if (matches.length > 1) {
    errors.push(issue(STACK_PREVIEW_CODES.AMBIGUOUS, "Definition selector matches more than one controller node.", `${path}.selector`));
    return null;
  }
  if (!matches.length) {
    if (Number(definition.selectorKind) === 1) {
      errors.push(issue(STACK_PREVIEW_CODES.DANGLING, "Exact selector references a controller node that does not exist.", `${path}.selector`));
    }
    return null;
  }
  const node = matches[0];
  const profile = selectedProfile(model, node.profileRef ?? node.profileStableId);
  if (!profile) {
    errors.push(issue(
      String(node.profileRef ?? "").startsWith("draft:") ? STACK_PREVIEW_CODES.DRAFT : STACK_PREVIEW_CODES.DANGLING,
      "Controller node references a state profile that does not exist.",
      `${path}.profile`,
    ));
    return null;
  }
  return { node, profile };
}

function timerStatus(definition, isWinner) {
  if (!Number(definition.timerClock)) return "inactive";
  if (isWinner) return "running";
  return ({ 1: "paused-while-hidden", 2: "running-while-hidden", 3: "expires-on-hide" })[
    Number(definition.hiddenTimerPolicy)
  ] || "inactive-while-hidden";
}

function composeOne(model, { controllerRef, layers = [], immutableContextMask = 0xFFFFFFFF } = {}) {
  const validationErrors = validateStackInput(model, { controllerRef, layers, immutableContextMask });
  if (validationErrors.length) {
    const mapped = validationErrors.map((error) => {
      let code = error.code;
      if (code === VALIDATION_CODES.DRAFT_REFERENCE) code = STACK_PREVIEW_CODES.DRAFT;
      else if (code === VALIDATION_CODES.REFERENCE) code = error.path.endsWith("ownerId") ? STACK_PREVIEW_CODES.OWNER : STACK_PREVIEW_CODES.DANGLING;
      else if (code === VALIDATION_CODES.SELECTOR_DUPLICATE) code = STACK_PREVIEW_CODES.AMBIGUOUS;
      else if (code === VALIDATION_CODES.BASE_NODE || code === VALIDATION_CODES.PROFILE_FIELDS) code = STACK_PREVIEW_CODES.DRAFT;
      return issue(code, error.message, error.path);
    });
    return { ok: false, errors: mapped, result: null };
  }
  const errors = [];
  const capacity = Number(model.stackPreview?.capacity || 8);
  if (layers.length > capacity) {
    errors.push(issue(STACK_PREVIEW_CODES.CAPACITY, `A runtime stack can contain at most ${capacity} override layers.`, "layers"));
  }
  const controller = selectedController(model, controllerRef);
  if (!controller) {
    errors.push(issue(
      String(controllerRef || "").startsWith("draft:") ? STACK_PREVIEW_CODES.DRAFT : STACK_PREVIEW_CODES.DANGLING,
      "Selected controller does not exist.", "controllerRef",
    ));
    return { ok: false, errors, result: null };
  }
  const baseNodes = (controller.nodes || []).filter((node) => node.base);
  if (baseNodes.length !== 1) {
    errors.push(issue(STACK_PREVIEW_CODES.DRAFT, "Selected controller must have exactly one base node.", "controller.nodes.base"));
    return { ok: false, errors, result: null };
  }
  const baseNode = baseNodes[0];
  const baseProfile = selectedProfile(model, baseNode.profileRef ?? baseNode.profileStableId);
  if (!baseProfile) {
    errors.push(issue(
      String(baseNode.profileRef ?? "").startsWith("draft:") ? STACK_PREVIEW_CODES.DRAFT : STACK_PREVIEW_CODES.DANGLING,
      "The base node references a state profile that does not exist.", "controller.base.profile",
    ));
    return { ok: false, errors, result: null };
  }

  const definitions = new Map((model.overrideDefinitions || []).map((definition) => [String(ref(definition)), definition]));
  const owners = new Map((model.owners || []).map((owner) => [String(ref(owner)), owner]));
  const applicability = new Map((model.applicability || []).map((rule) => [String(ref(rule)), rule]));
  const normalized = [];
  const layerIdentities = new Set();
  const layersByDefinition = new Map();

  layers.forEach((source, index) => {
    const path = `layers.${index}`;
    if (String(source.definitionId || "").startsWith("draft:")) {
      errors.push(issue(STACK_PREVIEW_CODES.DRAFT, "Unallocated draft definitions have no runtime precedence key.", `${path}.definitionId`));
      return;
    }
    const definition = definitions.get(String(source.definitionId));
    if (!definition) {
      errors.push(issue(
        String(source.definitionId || "").startsWith("draft:") ? STACK_PREVIEW_CODES.DRAFT : STACK_PREVIEW_CODES.DANGLING,
        "Layer references a definition that does not exist.", `${path}.definitionId`,
      ));
      return;
    }
    if (String(source.ownerId || "").startsWith("draft:")) {
      errors.push(issue(STACK_PREVIEW_CODES.DRAFT, "Unallocated draft owners have no runtime precedence key.", `${path}.ownerId`));
      return;
    }
    const owner = owners.get(String(source.ownerId));
    if (!owner) {
      errors.push(issue(STACK_PREVIEW_CODES.OWNER, "Layer references an owner that does not exist.", `${path}.ownerId`));
      return;
    }
    const rawInstanceKey = source.instanceKey;
    const instanceKey = Number(rawInstanceKey);
    const numericShape = typeof rawInstanceKey === "number"
      || (typeof rawInstanceKey === "string" && /^\d+$/.test(rawInstanceKey));
    if (!numericShape || !Number.isInteger(instanceKey) || instanceKey < 0 || instanceKey > 0xFFFF) {
      errors.push(issue(STACK_PREVIEW_CODES.INSTANCE_KEY, "Instance key must be an unsigned 16-bit integer.", `${path}.instanceKey`));
    } else if (!definition.allowMultipleInstancesPerOwner && instanceKey !== 0) {
      errors.push(issue(STACK_PREVIEW_CODES.INSTANCE_KEY, "Single-instance definitions require instance key 0.", `${path}.instanceKey`));
    }
    const identity = `${source.ownerId}:${instanceKey}`;
    if (layerIdentities.has(identity)) {
      errors.push(issue(STACK_PREVIEW_CODES.DUPLICATE_IDENTITY, "Owner and instance key must identify one layer.", path));
    }
    layerIdentities.add(identity);
    if (definition.hasRequiredOwnerId && !same(definition.requiredOwnerId, source.ownerId)) {
      errors.push(issue(STACK_PREVIEW_CODES.REQUIRED_OWNER, "Layer owner does not match the definition's required owner.", `${path}.ownerId`));
    }
    const siblings = layersByDefinition.get(String(ref(definition))) || [];
    if (!definition.allowMultipleOwners && siblings.some((layer) => !same(layer.ownerId, source.ownerId))) {
      errors.push(issue(STACK_PREVIEW_CODES.MULTIPLE_OWNERS, "Definition does not allow multiple owners.", path));
    }
    if (!definition.allowMultipleInstancesPerOwner
        && siblings.some((layer) => same(layer.ownerId, source.ownerId) && Number(layer.instanceKey) !== instanceKey)) {
      errors.push(issue(STACK_PREVIEW_CODES.MULTIPLE_INSTANCES, "Definition does not allow multiple instances for one owner.", path));
    }
    siblings.push({ ownerId: source.ownerId, instanceKey });
    layersByDefinition.set(String(ref(definition)), siblings);
    if (Number(definition.kind) === 2) {
      errors.push(issue(STACK_PREVIEW_CODES.MODIFIER, "Modifier definitions require the runtime modifier engine and are not approximated by this preview.", `${path}.definitionId`));
      return;
    }
    const rule = applicability.get(String(definition.applicabilityId));
    if (!rule) {
      errors.push(issue(STACK_PREVIEW_CODES.DANGLING, "Definition references an applicability rule that does not exist.", `${path}.applicabilityId`));
      return;
    }
    const scopedController = definition.controllerId ?? rule.controllerId;
    let applicable = !scopedController || same(scopedController, ref(controller));
    const requiredMask = Number(rule.immutableContextMask) >>> 0;
    const actualMask = Number(immutableContextMask) >>> 0;
    applicable = applicable && (requiredMask === 0xFFFFFFFF || (actualMask & requiredMask) === requiredMask);
    const resolved = applicable ? resolvedNode(model, controller, definition, errors, path) : null;
    if (applicable && !resolved && !errors.some((error) => error.path.startsWith(path))) applicable = false;
    normalized.push({
      definitionStableId: ref(definition), definition, ownerId: ref(owner), owner,
      instanceKey, applicable, node: resolved?.node || null, profile: resolved?.profile || null,
      precedence: {
        channel: Number(definition.channel), priority: Number(definition.priority),
        definitionStableId: Number(ref(definition)), ownerId: Number(ref(owner)), instanceKey,
      },
    });
  });

  if (errors.length) return { ok: false, errors, result: null };
  const applicable = normalized.filter((layer) => layer.applicable).sort((left, right) => comparePrecedence(left.precedence, right.precedence));
  const winner = applicable.at(-1) || null;
  const effectiveNode = winner?.node || baseNode;
  const effectiveProfile = winner?.profile || baseProfile;
  const identity = {
    controllerId: ref(controller), nodeId: ref(effectiveNode), profileId: ref(effectiveProfile),
    semanticRoleId: Number(effectiveNode.semanticRoleId),
  };
  const source = winner ? {
    kind: "override", definitionId: winner.definitionStableId, ownerId: winner.ownerId,
    instanceKey: winner.instanceKey, nodeId: ref(effectiveNode), profileId: ref(effectiveProfile),
  } : { kind: "base", nodeId: ref(baseNode), profileId: ref(baseProfile) };
  const fields = Object.fromEntries((model.stateProfileFields || []).map((field) => [
    field.key, { value: effectiveProfile.values?.[field.key], provenance: clone(source) },
  ]));
  const controllerScalars = Object.fromEntries((model.controllerScalarFields || []).map((field) => [
    field.key, { value: controller.scalarDefaults?.[field.key], provenance: { kind: "controller-base", controllerId: ref(controller) } },
  ]));
  const policies = Object.fromEntries(Object.entries(controller.policyIds || {}).map(([key, value]) => [
    key, { value, provenance: { kind: "controller-base", controllerId: ref(controller) } },
  ]));
  const layerResults = normalized.map((layer) => {
    const isWinner = winner === layer;
    return {
      definitionId: layer.definitionStableId, ownerId: layer.ownerId, instanceKey: layer.instanceKey,
      identity: layer.node && layer.profile ? {
        controllerId: ref(controller), nodeId: ref(layer.node), profileId: ref(layer.profile),
        semanticRoleId: Number(layer.node.semanticRoleId),
      } : null,
      applicable: layer.applicable, winner: isWinner,
      visibility: !layer.applicable ? "not-applicable" : isWinner ? "winner" : "hidden",
      precedence: clone(layer.precedence),
      lifetime: {
        map: { value: Number(layer.definition.mapLifetime), label: layer.definition.mapLifetimeLabel },
        battle: { value: Number(layer.definition.battleLifetime), label: layer.definition.battleLifetimeLabel },
      },
      timer: {
        status: timerStatus(layer.definition, isWinner),
        clock: Number(layer.definition.timerClock), clockLabel: layer.definition.timerClockLabel,
        source: Number(layer.definition.timerSource), sourceLabel: layer.definition.timerSourceLabel,
        value: Number(layer.definition.timerValue), hiddenPolicy: Number(layer.definition.hiddenTimerPolicy),
      },
      recovery: {
        policy: Number(layer.definition.recoveryPolicy), label: layer.definition.recoveryPolicyLabel,
        transitionId: layer.definition.recoveryTransitionId || null,
      },
    };
  });
  return {
    ok: true, errors: [], result: {
      identity, baseIdentity: {
        controllerId: ref(controller), nodeId: ref(baseNode), profileId: ref(baseProfile),
        semanticRoleId: Number(baseNode.semanticRoleId),
      },
      fields, controllerScalars, policies, layers: layerResults,
      canonicalOrder: applicable.map((layer) => ({
        definitionId: layer.definitionStableId, ownerId: layer.ownerId, instanceKey: layer.instanceKey,
      })),
      winningLayer: winner ? { definitionId: winner.definitionStableId, ownerId: winner.ownerId, instanceKey: winner.instanceKey } : null,
    },
  };
}

export function composeStackPreview({ model, draft = null, mode = "saved", ...input } = {}) {
  if (!model) return { ok: false, errors: [issue(STACK_PREVIEW_CODES.DANGLING, "A saved behavior model is required.", "model")], result: null };
  if (mode === "saved") return { mode, ...composeOne(materializePreviewModel(model), input) };
  if (mode === "draft") return { mode, ...composeOne(materializePreviewModel(model, draft), input) };
  if (mode === "compare") {
    const saved = composeOne(materializePreviewModel(model), input);
    const drafted = composeOne(materializePreviewModel(model, draft), input);
    if (!saved.ok || !drafted.ok) return {
      mode, ok: false, errors: [...saved.errors, ...drafted.errors], result: null, comparison: null,
    };
    return {
      mode, ok: true, errors: [], result: drafted.result,
      comparison: { saved: saved.result, draft: drafted.result, changed: JSON.stringify(saved.result) !== JSON.stringify(drafted.result) },
    };
  }
  return { mode, ok: false, errors: [issue(STACK_PREVIEW_CODES.DANGLING, "Unknown preview mode.", "mode")], result: null };
}

export function preserveStackPreviewSelection(model, controllerRef, layers = []) {
  return {
    controllerRef: controllerRef || ref(model.controllers?.[0]) || "",
    layers: clone(layers),
  };
}

function numberOr(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function contextMatch(match = {}, context = {}) {
  const species = numberOr(context.species, 0);
  const groupMask = numberOr(context.groupMask ?? context.immutableContextMask, 0xFFFFFFFF) >>> 0;
  const terrain = numberOr(context.terrain, 0);
  const level = numberOr(context.level, 1);
  const shiny = context.shiny ? 1 : 0;
  const behaviorClass = numberOr(context.behaviorClass, 0);
  return (!Number(match.species) || Number(match.species) === species)
    && (!Number(match.groupMask) || (Number(match.groupMask) & groupMask) !== 0)
    && (Number(match.terrain ?? 0xFF) === 0xFF || Number(match.terrain) === terrain)
    && (!Number(match.minimumLevel ?? match.minLevel) || level >= Number(match.minimumLevel ?? match.minLevel))
    && (!Number(match.maximumLevel ?? match.maxLevel) || level <= Number(match.maximumLevel ?? match.maxLevel))
    && (Number(match.shiny ?? 0xFF) === 0xFF || Number(match.shiny) === shiny)
    && (Number(match.behaviorClass ?? 0xFF) === 0xFF || Number(match.behaviorClass) === behaviorClass);
}

function assignmentController(model, assignment) {
  if (assignment?.controllerId != null) return assignment.controllerId;
  const actionRef = assignment?.controllerIndex;
  const action = String(actionRef).startsWith("draft:")
    ? (model.assignmentActions || []).find((item) => String(ref(item)) === String(actionRef))
    : model.assignmentActions?.[Number(actionRef)];
  if (action?.payload && !Array.isArray(action.payload)) return action.payload.controllerRef ?? null;
  return Array.isArray(action?.payload) && action.payload.length >= 2
    ? Number(action.payload[0]) | (Number(action.payload[1]) << 8)
    : null;
}

/** Resolve the immutable entity selection exactly once before sequence replay. */
export function resolveStackPreviewContext(model, source = {}) {
  const context = {
    species: Math.max(0, numberOr(source.species, 0)),
    terrain: Math.max(0, numberOr(source.terrain, 0)),
    level: Math.max(1, Math.min(100, numberOr(source.level, 20))),
    shiny: Boolean(source.shiny),
    groupMask: numberOr(source.groupMask ?? source.immutableContextMask, 0xFFFFFFFF) >>> 0,
    immutableContextMask: numberOr(source.immutableContextMask ?? source.groupMask, 0xFFFFFFFF) >>> 0,
    behaviorClass: Math.max(0, numberOr(source.behaviorClass, 0)),
    systemRoute: Math.max(0, numberOr(source.systemRoute, 0)),
    chanceRoll: Math.max(0, Math.min(99, numberOr(source.chanceRoll, 0))),
    presentationGate: Boolean(source.presentationGate),
    candidateTimerDurations: clone(source.candidateTimerDurations || {}),
  };
  let controllerRef = source.controllerRef ?? null;
  let dispatch = { kind: "explicit", assignmentId: null, priority: null };
  if (controllerRef == null || controllerRef === "") {
    controllerRef = ref(model.controllers?.[context.behaviorClass]) ?? null;
    dispatch = { kind: "behavior-class", assignmentId: null, priority: null };
    if (controllerRef == null) return {
      ...context,
      controllerRef: null,
      dispatch: { kind: "invalid-behavior-class", assignmentId: null, priority: null },
    };
    const candidates = [];
    for (const assignment of model.genericAssignments || model.contextDispatch?.genericAssignments || []) {
      if (contextMatch(assignment.match, context)) candidates.push({ ...assignment, dispatchKind: "generic" });
    }
    for (const assignment of model.speciesAssignments || model.contextDispatch?.speciesAssignments || []) {
      if (Number(assignment.species) === Number(context.species)) candidates.push({ ...assignment, dispatchKind: "species" });
    }
    candidates.sort((left, right) => Number(left.dispatchPriority ?? left.priority) - Number(right.dispatchPriority ?? right.priority)
      || Number(ref(left)) - Number(ref(right)));
    const winner = candidates.at(-1);
    if (winner) {
      controllerRef = assignmentController(model, winner);
      dispatch = {
        kind: winner.dispatchKind,
        assignmentId: ref(winner),
        priority: Number(winner.dispatchPriority ?? winner.priority),
      };
    }
  }
  return { ...context, controllerRef, dispatch };
}

function sequenceGraphErrors(model) {
  const errors = [];
  if (model.validationSchema) {
    for (const diagnostic of validateBehaviorModel(model)) {
      errors.push(issue(diagnostic.code || STACK_PREVIEW_CODES.GRAPH, diagnostic.message, diagnostic.path));
    }
    if (errors.length) return errors;
  }
  const definitions = new Set((model.overrideDefinitions || []).map((item) => String(ref(item))));
  const owners = new Set((model.owners || []).map((item) => String(ref(item))));
  const transitions = model.transitionGraph?.transitions;
  if (!Array.isArray(transitions)) return [issue(STACK_PREVIEW_CODES.GRAPH, "The behavior model has no authored transition graph.", "transitionGraph.transitions")];
  const transitionIds = new Set(transitions.map((item) => String(ref(item))));
  transitions.forEach((transition, index) => {
    const path = `transitionGraph.transitions.${index}`;
    if (String(ref(transition) || "").startsWith("draft:")) errors.push(issue(STACK_PREVIEW_CODES.DRAFT, "Unallocated draft transitions cannot be dispatched by the runtime preview.", path));
    if (!definitions.has(String(transition.candidateDefinitionId))) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Transition candidate definition does not exist.", `${path}.candidateDefinitionId`));
    if (!owners.has(String(transition.ownerId))) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Transition owner does not exist.", `${path}.ownerId`));
    if (!Number.isInteger(Number(transition.trigger)) || Number(transition.trigger) < 1 || Number(transition.trigger) > 13) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Transition trigger is outside the V40 event domain.", `${path}.trigger`));
    if (!Number.isInteger(Number(transition.fromRoleMask)) || Number(transition.fromRoleMask) < 1 || Number(transition.fromRoleMask) > 0x7F) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Transition role mask is invalid.", `${path}.fromRoleMask`));
    for (const [childIndex, guard] of (transition.guards || []).entries()) {
      if (![1, 2, 3, 4, 5, 6, 7, 8].includes(Number(guard.kind))) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Transition has an unsupported guard kind.", `${path}.guards.${childIndex}.kind`));
      if ([4, 5].includes(Number(guard.kind)) && !owners.has(String(guard.referenceId))) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Owner guard references an owner that does not exist.", `${path}.guards.${childIndex}.referenceId`));
    }
    for (const [childIndex, operation] of (transition.operations || []).entries()) {
      if (![1, 2, 3, 4, 5, 6].includes(Number(operation.kind))) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Transition has an unsupported operation kind.", `${path}.operations.${childIndex}.kind`));
      if ([1, 2, 3, 4].includes(Number(operation.kind)) && !definitions.has(String(operation.definitionId))) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Transition operation references a definition that does not exist.", `${path}.operations.${childIndex}.definitionId`));
      if ([1, 2, 3, 4, 5].includes(Number(operation.kind)) && !owners.has(String(operation.ownerId))) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Transition operation references an owner that does not exist.", `${path}.operations.${childIndex}.ownerId`));
      if (Number(operation.kind) === 2 && !definitions.has(String(operation.replacementDefinitionId))) errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Replace operation references a definition that does not exist.", `${path}.operations.${childIndex}.replacementDefinitionId`));
    }
  });
  for (const [index, definition] of (model.overrideDefinitions || []).entries()) {
    if (Number(definition.recoveryPolicy) === 1 && !transitionIds.has(String(definition.recoveryTransitionId))) {
      errors.push(issue(STACK_PREVIEW_CODES.GRAPH, "Timed definition recovery transition does not exist.", `overrideDefinitions.${index}.recoveryTransitionId`));
    }
  }
  return errors;
}

function layerInput(layer) {
  return { definitionId: layer.definitionId, ownerId: layer.ownerId, instanceKey: Number(layer.instanceKey) };
}

function definitionById(model, definitionId) {
  return (model.overrideDefinitions || []).find((item) => same(ref(item), definitionId));
}

function timerDuration(model, definition, controller, context) {
  let duration = Number(definition.timerValue || 0);
  if (Number(definition.timerSource) === 2) duration = Number(controller.scalarDefaults?.stamina || 0);
  if (Number(definition.timerSource) === 3 && context.candidateTimerDurations?.[String(ref(definition))] != null) {
    duration = Number(context.candidateTimerDurations[String(ref(definition))]);
  }
  if (Number(definition.semanticRoleId) === 4 && duration === 0) return 255;
  if (Number(definition.semanticRoleId) === 3 && duration === 0) return 1;
  return Math.max(0, Math.min(254, duration));
}

function armLayerTimer(model, controller, context, layer) {
  const definition = definitionById(model, layer.definitionId);
  if (!definition || !Number(definition.timerClock)) return { ...layer, timer: null };
  const duration = timerDuration(model, definition, controller, context);
  return {
    ...layer,
    timer: {
      clock: Number(definition.timerClock), hiddenPolicy: Number(definition.hiddenTimerPolicy),
      recoveryPolicy: Number(definition.recoveryPolicy), recoveryTransitionId: definition.recoveryTransitionId,
      armedDuration: duration, remainingTicks: duration, zeroPending: duration === 0,
    },
  };
}

function snapshotSequence(model, context, layers) {
  const composed = composeOne(model, {
    controllerRef: context.controllerRef,
    immutableContextMask: context.immutableContextMask,
    layers: layers.map(layerInput),
  });
  if (!composed.ok) return composed;
  const timers = new Map(layers.map((layer) => [`${layer.ownerId}:${layer.instanceKey}`, layer.timer]));
  composed.result.layers.forEach((layer) => {
    const timer = timers.get(`${layer.ownerId}:${layer.instanceKey}`);
    layer.timer.remainingTicks = timer?.remainingTicks ?? null;
    layer.timer.armedDuration = timer?.armedDuration ?? null;
    layer.timer.zeroPending = Boolean(timer?.zeroPending);
  });
  return composed;
}

function expireHiddenTimers(layers, snapshot, presentationGate) {
  if (presentationGate) return { layers, changed: false };
  const winner = snapshot.result.winningLayer;
  let changed = false;
  const next = layers.map((layer) => {
    const wins = winner && same(winner.ownerId, layer.ownerId) && Number(winner.instanceKey) === Number(layer.instanceKey);
    if (!wins && layer.timer && layer.timer.hiddenPolicy === 3 && !layer.timer.zeroPending) {
      changed = true;
      return { ...layer, timer: { ...layer.timer, remainingTicks: 0, zeroPending: true } };
    }
    return layer;
  });
  return { layers: next, changed };
}

function guardMatches(guard, event, snapshot, layers) {
  const effective = snapshot.result.identity;
  let matches = false;
  if (Number(guard.kind) === 1) matches = true;
  else if (Number(guard.kind) === 2) matches = Number(effective.semanticRoleId) === Number(guard.payload);
  else if (Number(guard.kind) === 3) matches = same(effective.nodeId, guard.referenceId);
  else if ([4, 5].includes(Number(guard.kind))) {
    matches = layers.some((layer) => same(layer.ownerId, guard.referenceId));
    if (Number(guard.kind) === 5) matches = !matches;
  } else if (Number(guard.kind) === 6) {
    matches = Boolean(event.replay) && event.replay.recoveryTransitionId && event.replay.definitionId
      && event.replay.ownerId && Number(event.trigger) === Number(guard.payload);
  } else if (Number(guard.kind) === 7) matches = Number(event.chanceRoll) < Number(guard.payload);
  else if (Number(guard.kind) === 8) matches = Number(event.systemRoute) === Number(guard.payload);
  return guard.negate ? !matches : matches;
}

function selectTransition(model, context, event, snapshot) {
  const transitions = model.transitionGraph?.transitions || [];
  const roleBit = 1 << (Number(snapshot.result.identity.semanticRoleId) - 1);
  if (event.replay) {
    const exact = transitions.find((item) => same(ref(item), event.replay.recoveryTransitionId));
    if (exact && Number(exact.trigger) === Number(event.trigger)
        && (Number(exact.fromRoleMask) & roleBit)
        && (!(exact.controllerIds || []).length || exact.controllerIds.some((id) => same(id, context.controllerRef)))) {
      return { transition: exact, errors: [] };
    }
    return exact ? { transition: null, errors: [] } : {
      transition: null,
      errors: [issue(STACK_PREVIEW_CODES.TRANSITION, "Timer recovery transition does not exist.", "step.replay.recoveryTransitionId")],
    };
  }
  const candidates = transitions.filter((transition) => Number(transition.trigger) === Number(event.trigger)
    && (Number(transition.fromRoleMask) & roleBit)
    && (!(transition.controllerIds || []).length || transition.controllerIds.some((id) => same(id, context.controllerRef))));
  if (!candidates.length) return { transition: null, errors: [] };
  const priority = Math.max(...candidates.map((item) => Number(item.dispatchPriority)));
  const winners = candidates.filter((item) => Number(item.dispatchPriority) === priority);
  if (winners.length !== 1) return {
    transition: null,
    errors: [issue(STACK_PREVIEW_CODES.TRANSITION_AMBIGUOUS, "More than one transition owns the highest dispatch priority.", "transitionGraph.transitions")],
  };
  return { transition: winners[0], errors: [] };
}

function operationInstanceKey(event, operation, transition) {
  if (event.replay && same(operation.definitionId, transition.candidateDefinitionId) && same(operation.ownerId, transition.ownerId)) {
    return Number(event.replay.instanceKey);
  }
  return Number(event.trigger) === 11 ? Number(operation.instanceKey) : 0;
}

function operationAddressesLayer(model, operation, layer) {
  if (operation.kind <= 4) return same(operation.ownerId, layer.ownerId)
    && Number(operation.instanceKey) === Number(layer.instanceKey);
  if (operation.kind === 5) return same(operation.ownerId, layer.ownerId);
  if (operation.kind === 6) {
    const definition = definitionById(model, layer.definitionId);
    return definition && Number(definition.mapLifetime) === Number(operation.policyId);
  }
  return false;
}

function preflightTransitionOperations(model, layers, transition, event) {
  const reports = [];
  const operations = (transition.operations || []).map((source) => ({
    source,
    operationId: Number(ref(source)),
    kind: Number(source.kind),
    definitionId: source.definitionId,
    replacementDefinitionId: source.replacementDefinitionId,
    ownerId: source.ownerId,
    policyId: source.policyId,
    instanceKey: operationInstanceKey(event, source, transition),
  })).sort((left, right) => left.operationId - right.operationId);
  for (let index = 0; index < operations.length; index += 1) {
    const operation = operations[index];
    if (!Number.isInteger(operation.operationId) || operation.operationId <= 0) {
      return { ok: false, errors: [issue(STACK_PREVIEW_CODES.OPERATION, "Operation stable ID must be a non-zero integer.", `transition.${ref(transition)}.operations`)] };
    }
    if (index && operation.operationId === operations[index - 1].operationId) {
      return { ok: false, errors: [issue(STACK_PREVIEW_CODES.OPERATION, "Transition delta contains duplicate operation stable IDs.", `transition.${ref(transition)}.operations`)] };
    }
    if (operation.kind === 6 && ![1, 2, 3].includes(Number(operation.policyId))) {
      return { ok: false, errors: [issue(STACK_PREVIEW_CODES.OPERATION, "Map-lifetime removal requires authored policy 1, 2, or 3.", `transition.${ref(transition)}.operation.${operation.operationId}.policyId`)] };
    }
    if (operation.kind === 3 || operation.kind === 4) {
      const target = layers.find((layer) => same(layer.definitionId, operation.definitionId)
        && same(layer.ownerId, operation.ownerId) && Number(layer.instanceKey) === operation.instanceKey);
      if (!target && operation.kind === 3) {
        return { ok: false, errors: [issue(STACK_PREVIEW_CODES.OPERATION, "Required layer is not present.", `transition.${ref(transition)}.operation.${operation.operationId}`)] };
      }
      if (!target) {
        reports.push({
          operationId: operation.operationId, kind: operation.kind, status: "not-present",
          definitionId: operation.definitionId, ownerId: operation.ownerId, instanceKey: operation.instanceKey,
        });
        operations.splice(index, 1);
        index -= 1;
      }
    }
  }
  const syntheticLayer = (operation) => operation.kind <= 4 ? {
    definitionId: operation.kind <= 2 ? (operation.kind === 2 ? operation.replacementDefinitionId : operation.definitionId) : null,
    ownerId: operation.ownerId, instanceKey: operation.instanceKey,
  } : null;
  for (let leftIndex = 0; leftIndex < operations.length; leftIndex += 1) {
    const left = operations[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < operations.length; rightIndex += 1) {
      const right = operations[rightIndex];
      let ambiguous = left.kind === 5 && right.kind === 5 && same(left.ownerId, right.ownerId);
      ambiguous ||= left.kind === 6 && right.kind === 6 && Number(left.policyId) === Number(right.policyId);
      const leftSynthetic = syntheticLayer(left);
      const rightSynthetic = syntheticLayer(right);
      if (leftSynthetic && right.kind !== 6) ambiguous ||= operationAddressesLayer(model, right, leftSynthetic);
      if (rightSynthetic && left.kind !== 6) ambiguous ||= operationAddressesLayer(model, left, rightSynthetic);
      ambiguous ||= layers.some((layer) => operationAddressesLayer(model, left, layer)
        && operationAddressesLayer(model, right, layer));
      if (ambiguous) return {
        ok: false,
        errors: [issue(STACK_PREVIEW_CODES.OPERATION, "Transition delta contains operations that address the same layer.", `transition.${ref(transition)}.operations`)],
      };
    }
  }
  return { ok: true, operations, reports, errors: [] };
}

function replacementFamilyCompatible(current, replacement) {
  return Boolean(current) && Boolean(replacement)
    && Boolean(Number(current.hasTiredOriginKind)) === Boolean(Number(replacement.hasTiredOriginKind))
    && Number(current.tiredOriginKind || 0) === Number(replacement.tiredOriginKind || 0)
    && Boolean(Number(current.hasRequiredOwnerId)) === Boolean(Number(replacement.hasRequiredOwnerId))
    && same(current.requiredOwnerId || 0, replacement.requiredOwnerId || 0);
}

function applyTransitionOperations(model, controller, context, layers, transition, event) {
  let next = clone(layers);
  const preflight = preflightTransitionOperations(model, layers, transition, event);
  if (!preflight.ok) return { ok: false, layers, errors: preflight.errors, reports: [] };
  const reports = [...preflight.reports];
  const fail = (operation, message) => ({
    ok: false, layers,
    errors: [issue(STACK_PREVIEW_CODES.OPERATION, message, `transition.${ref(transition)}.operation.${operation.operationId}`)],
    reports,
  });
  for (const operation of preflight.operations) {
    const kind = operation.kind;
    const instanceKey = operation.instanceKey;
    const identityIndex = next.findIndex((layer) => same(layer.ownerId, operation.ownerId) && Number(layer.instanceKey) === instanceKey);
    if (kind === 1) {
      if (identityIndex >= 0 && !same(next[identityIndex].definitionId, operation.definitionId)) return fail(operation, "Apply identity is already owned by a different definition.");
      if (identityIndex < 0) next.push(armLayerTimer(model, controller, context, {
        definitionId: operation.definitionId, ownerId: operation.ownerId, instanceKey,
      }));
      reports.push({ operationId: operation.operationId, kind, status: identityIndex < 0 ? "applied" : "idempotent", definitionId: operation.definitionId, ownerId: operation.ownerId, instanceKey });
    } else if (kind === 2) {
      if (identityIndex < 0) return fail(operation, "Replace target identity is not present.");
      const currentDefinition = definitionById(model, next[identityIndex].definitionId);
      const replacementDefinition = definitionById(model, operation.replacementDefinitionId);
      if (!replacementFamilyCompatible(currentDefinition, replacementDefinition)) return fail(operation, "Replace target belongs to an incompatible generated-wrapper family.");
      next[identityIndex] = armLayerTimer(model, controller, context, {
        definitionId: operation.replacementDefinitionId, ownerId: operation.ownerId, instanceKey,
      });
      reports.push({ operationId: operation.operationId, kind, status: "replaced", definitionId: operation.replacementDefinitionId, ownerId: operation.ownerId, instanceKey });
    } else if (kind === 3 || kind === 4) {
      const index = next.findIndex((layer) => same(layer.definitionId, operation.definitionId)
        && same(layer.ownerId, operation.ownerId) && Number(layer.instanceKey) === instanceKey);
      if (index < 0) return fail(operation, "Preflighted removal target changed before atomic commit.");
      next.splice(index, 1);
      reports.push({ operationId: operation.operationId, kind, status: "removed", definitionId: operation.definitionId, ownerId: operation.ownerId, instanceKey });
    } else if (kind === 5) {
      const before = next.length;
      next = next.filter((layer) => !same(layer.ownerId, operation.ownerId));
      reports.push({ operationId: operation.operationId, kind, status: before === next.length ? "not-present" : "removed-owner", definitionId: null, ownerId: operation.ownerId, instanceKey: null });
    } else if (kind === 6) {
      const before = next.length;
      next = next.filter((layer) => Number(definitionById(model, layer.definitionId)?.mapLifetime) !== Number(operation.policyId));
      reports.push({ operationId: operation.operationId, kind, status: before === next.length ? "not-present" : "removed-policy", definitionId: null, ownerId: null, instanceKey: null, policyId: Number(operation.policyId), boundary: "map" });
    } else return fail(operation, "Operation kind is not supported by V40.");
  }
  const composed = snapshotSequence(model, context, next);
  if (!composed.ok) return { ok: false, layers, errors: composed.errors, reports };
  reports.sort((left, right) => Number(left.operationId) - Number(right.operationId));
  return { ok: true, layers: next, errors: [], reports };
}

function dispatchSequenceEvent(model, controller, context, layers, sourceEvent, presentationGate) {
  const event = {
    trigger: Number(sourceEvent.trigger), systemRoute: Number(sourceEvent.systemRoute ?? context.systemRoute),
    chanceRoll: Number(sourceEvent.chanceRoll ?? context.chanceRoll), replay: sourceEvent.replay || null,
  };
  if (!Number.isInteger(event.trigger) || event.trigger < 1 || event.trigger > 13
      || !Number.isInteger(event.systemRoute) || event.systemRoute < 0 || event.systemRoute > 0xFF
      || !Number.isInteger(event.chanceRoll) || event.chanceRoll < 0 || event.chanceRoll > 99) {
    return { ok: false, layers, errors: [issue(STACK_PREVIEW_CODES.STEP, "Event step fields are outside the V40 runtime domain.", "step")], report: null };
  }
  const before = snapshotSequence(model, context, layers);
  if (!before.ok) return { ok: false, layers, errors: before.errors, report: null };
  const selected = selectTransition(model, context, event, before);
  if (selected.errors.length) return { ok: false, layers, errors: selected.errors, report: null };
  if (!selected.transition) return { ok: true, layers, errors: [], report: { kind: "event", event, status: "no-transition", guards: [] } };
  const transition = selected.transition;
  if (event.replay && (!same(transition.candidateDefinitionId, event.replay.definitionId) || !same(transition.ownerId, event.replay.ownerId))) {
    return { ok: true, layers, errors: [], report: { kind: "event", event, transitionId: ref(transition), status: "stale-recovery", guards: [] } };
  }
  const guards = [];
  for (const guard of transition.guards || []) {
    const passed = guardMatches(guard, event, before, layers);
    guards.push({ guardId: ref(guard), kind: Number(guard.kind), passed });
    if (!passed) return {
      ok: true, layers, errors: [],
      report: { kind: "event", event, transitionId: ref(transition), status: "guard-failed", guards },
    };
  }
  const applied = applyTransitionOperations(model, controller, context, layers, transition, event);
  if (!applied.ok) return { ok: false, layers, errors: applied.errors, report: null };
  let after = snapshotSequence(model, context, applied.layers);
  let normalized = applied.layers;
  if (after.ok) {
    const hidden = expireHiddenTimers(normalized, after, presentationGate);
    normalized = hidden.layers;
    if (hidden.changed) after = snapshotSequence(model, context, normalized);
  }
  return {
    ok: after.ok, layers: normalized, errors: after.errors,
    presentationGate,
    report: {
      kind: "event", event, transitionId: ref(transition), status: "dispatched", guards,
      operations: applied.reports, actions: (transition.actions || []).map((action) => ref(action)),
    },
  };
}

function tickSequenceTimers(model, controller, context, layers, step, presentationGate) {
  const clock = Number(step.clock);
  const ticks = Number(step.ticks ?? 1);
  if (![1, 2].includes(clock) || !Number.isInteger(ticks) || ticks < 1 || ticks > STACK_SEQUENCE_LIMITS.ticksPerStep) {
    return { ok: false, layers, errors: [issue(STACK_PREVIEW_CODES.STEP, "Timer step requires clock 1 or 2 and 1-255 ticks.", "step")], report: null };
  }
  if (step.presentationGate !== undefined && typeof step.presentationGate !== "boolean") {
    return { ok: false, layers, presentationGate, errors: [issue(STACK_PREVIEW_CODES.STEP, "Presentation gate must be boolean when a tick changes it.", "step.presentationGate")], report: null };
  }
  const nextPresentationGate = step.presentationGate ?? presentationGate;
  let snapshot = snapshotSequence(model, context, layers);
  if (!snapshot.ok) return { ok: false, layers, errors: snapshot.errors, report: null };
  let next = clone(layers);
  const changed = [];
  if (!nextPresentationGate) {
    const hidden = expireHiddenTimers(next, snapshot, nextPresentationGate);
    next = hidden.layers;
    snapshot = snapshotSequence(model, context, next);
    const winner = snapshot.result.winningLayer;
    next = next.map((layer) => {
      const timer = layer.timer;
      const wins = winner && same(winner.ownerId, layer.ownerId) && Number(winner.instanceKey) === Number(layer.instanceKey);
      if (!timer || timer.clock !== clock || timer.zeroPending || timer.remainingTicks === 255
          || (!wins && timer.hiddenPolicy !== 2)) return layer;
      const remainingTicks = Math.max(0, timer.remainingTicks - ticks);
      if (remainingTicks === timer.remainingTicks) return layer;
      changed.push({ definitionId: layer.definitionId, ownerId: layer.ownerId, instanceKey: layer.instanceKey, before: timer.remainingTicks, after: remainingTicks });
      return { ...layer, timer: { ...timer, remainingTicks, zeroPending: remainingTicks === 0 } };
    });
  }
  const recoveries = [];
  const pending = next.filter((layer) => layer.timer?.zeroPending).sort((left, right) => Number(left.ownerId) - Number(right.ownerId) || Number(left.instanceKey) - Number(right.instanceKey));
  for (const expired of pending) {
    const stillPending = next.some((layer) => same(layer.definitionId, expired.definitionId)
      && same(layer.ownerId, expired.ownerId) && Number(layer.instanceKey) === Number(expired.instanceKey)
      && layer.timer?.zeroPending);
    if (!stillPending) {
      recoveries.push({ kind: "event", status: "stale-recovery", transitionId: expired.timer.recoveryTransitionId });
      continue;
    }
    if (Number(expired.timer.recoveryPolicy) !== 1 || !expired.timer.recoveryTransitionId) {
      return { ok: false, layers, errors: [issue(STACK_PREVIEW_CODES.TIMER, "Expired timer has no route-transition recovery.", `layers.${expired.ownerId}:${expired.instanceKey}.timer`)], report: null };
    }
    const transition = (model.transitionGraph?.transitions || []).find((item) => same(ref(item), expired.timer.recoveryTransitionId));
    if (!transition) return { ok: false, layers, errors: [issue(STACK_PREVIEW_CODES.TIMER, "Expired timer recovery transition does not exist.", "timer.recoveryTransitionId")], report: null };
    const recovery = dispatchSequenceEvent(model, controller, context, next, {
      trigger: transition.trigger, systemRoute: context.systemRoute, chanceRoll: context.chanceRoll,
      replay: {
        recoveryTransitionId: expired.timer.recoveryTransitionId, definitionId: expired.definitionId,
        ownerId: expired.ownerId, instanceKey: expired.instanceKey,
      },
    }, nextPresentationGate);
    if (!recovery.ok) return recovery;
    next = recovery.layers;
    recoveries.push(recovery.report);
  }
  return { ok: true, layers: next, presentationGate: nextPresentationGate, errors: [], report: { kind: "tick", clock, ticks, presentationGate: nextPresentationGate, changed, recoveries } };
}

function runOneSequence(model, sourceContext, initialLayers, steps) {
  if (sourceContext.presentationGate !== undefined && typeof sourceContext.presentationGate !== "boolean") {
    return { ok: false, errors: [issue(STACK_PREVIEW_CODES.STEP, "Initial presentation gate must be boolean.", "context.presentationGate")], context: null, history: [], result: null };
  }
  const context = resolveStackPreviewContext(model, sourceContext);
  const graphErrors = sequenceGraphErrors(model);
  if (graphErrors.length) return { ok: false, errors: graphErrors, context, history: [], result: null };
  const controller = selectedController(model, context.controllerRef);
  if (!controller) return { ok: false, errors: [issue(STACK_PREVIEW_CODES.DANGLING, "Context did not resolve an existing controller.", "context.controllerRef")], context, history: [], result: null };
  let presentationGate = context.presentationGate;
  let layers = initialLayers.map((layer) => armLayerTimer(model, controller, context, layerInput(layer)));
  let snapshot = snapshotSequence(model, context, layers);
  if (!snapshot.ok) return { ok: false, errors: snapshot.errors, context, history: [], result: null };
  ({ layers } = expireHiddenTimers(layers, snapshot, presentationGate));
  snapshot = snapshotSequence(model, context, layers);
  const history = [{ index: 0, step: { kind: "initial" }, report: null, presentationGate, snapshot: snapshot.result }];
  for (const [index, step] of steps.entries()) {
    const advanced = step?.kind === "event"
      ? dispatchSequenceEvent(model, controller, context, layers, step, presentationGate)
      : step?.kind === "tick"
        ? tickSequenceTimers(model, controller, context, layers, step, presentationGate)
        : { ok: false, layers, errors: [issue(STACK_PREVIEW_CODES.STEP, "Sequence step kind must be event or tick.", `steps.${index}.kind`)], report: null };
    if (!advanced.ok) return { ok: false, errors: advanced.errors, context, history, result: null };
    layers = advanced.layers;
    presentationGate = advanced.presentationGate ?? presentationGate;
    snapshot = snapshotSequence(model, context, layers);
    if (!snapshot.ok) return { ok: false, errors: snapshot.errors, context, history, result: null };
    history.push({ index: index + 1, step: clone(step), report: advanced.report, presentationGate, snapshot: snapshot.result });
  }
  return { ok: true, errors: [], context, history, presentationGate, result: history.at(-1).snapshot, layers: clone(layers) };
}

/** Replay a bounded event/timer sequence without mutating either saved or draft data. */
export function runStackEventSequence({ model, draft = null, mode = "saved", context = {}, initialLayers = [], steps = [] } = {}) {
  if (!model) return { mode, ok: false, errors: [issue(STACK_PREVIEW_CODES.DANGLING, "A saved behavior model is required.", "model")], result: null };
  if (!Array.isArray(steps) || steps.length > STACK_SEQUENCE_LIMITS.steps) return {
    mode, ok: false, errors: [issue(STACK_PREVIEW_CODES.LIMIT, `A preview sequence may contain at most ${STACK_SEQUENCE_LIMITS.steps} steps.`, "steps")], result: null,
  };
  if (mode === "saved" || mode === "draft") {
    const resolved = runOneSequence(materializePreviewModel(model, mode === "draft" ? draft : null), context, initialLayers, steps);
    return { mode, ...resolved };
  }
  if (mode === "compare") {
    const saved = runOneSequence(materializePreviewModel(model), context, initialLayers, steps);
    const drafted = runOneSequence(materializePreviewModel(model, draft), context, initialLayers, steps);
    if (!saved.ok || !drafted.ok) return { mode, ok: false, errors: [...saved.errors, ...drafted.errors], result: null, comparison: { saved, draft: drafted, changed: null } };
    return {
      mode, ok: true, errors: [], result: drafted.result, context: drafted.context, history: drafted.history, layers: drafted.layers,
      comparison: { saved, draft: drafted, changed: JSON.stringify(saved.history) !== JSON.stringify(drafted.history) },
    };
  }
  return { mode, ok: false, errors: [issue(STACK_PREVIEW_CODES.STEP, "Unknown preview mode.", "mode")], result: null };
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

export function createStackPreviewController({ model, getDraft = () => null, elements = {}, setStatus = () => {} } = {}) {
  const drawer = elements.profileResolverDrawer;
  const workbench = elements.profileWorkbench;
  const open = elements.openProfileResolver;
  const close = elements.closeProfileResolver;
  const resolution = elements.profileResolution;
  const controls = drawer?.querySelector?.(".resolver-drawer-controls");
  if (!drawer || !workbench || !open || !close || !resolution || !controls) return null;
  let mode = "saved";
  let controllerRef = "";
  let layers = [];
  let steps = [];
  let context = {
    species: 0, terrain: 0, level: 20, shiny: false, groupMask: 0xFFFFFFFF,
    immutableContextMask: 0xFFFFFFFF, behaviorClass: 0, systemRoute: 0, chanceRoll: 0,
    presentationGate: false,
  };
  let selectedTrigger = Number(model.transitionGraph?.triggerOptions?.[0]?.value || 1);
  let tickCount = 1;
  let tickPresentationGate = false;
  let destroyed = false;

  function activeModel() {
    return mode === "saved" ? materializePreviewModel(model) : materializePreviewModel(model, getDraft());
  }

  function options(items, selected, label) {
    const known = items.some((item) => same(ref(item), selected));
    const retained = selected !== "" && selected !== null && selected !== undefined && !known
      ? `<option value="${escapeHtml(selected)}" selected>Missing reference ${escapeHtml(selected)}</option>`
      : "";
    return retained + items.map((item) => `<option value="${escapeHtml(ref(item))}" ${same(ref(item), selected) ? "selected" : ""}>${escapeHtml(label(item))}</option>`).join("");
  }

  function normalizeSelection() {
    const current = activeModel();
    ({ layers } = preserveStackPreviewSelection(current, controllerRef, layers));
  }

  function renderControls() {
    normalizeSelection();
    const current = activeModel();
    controls.innerHTML = `<label class="compact-field"><span>Source</span><select data-stack-mode><option value="saved" ${mode === "saved" ? "selected" : ""}>Saved</option><option value="draft" ${mode === "draft" ? "selected" : ""}>Draft</option><option value="compare" ${mode === "compare" ? "selected" : ""}>Saved ↔ Draft</option></select></label>
      <fieldset class="stack-preview-context"><legend>Entity context</legend>
        <label class="compact-field"><span>Controller</span><select data-stack-controller><option value="" ${controllerRef === "" ? "selected" : ""}>Resolve from context</option>${options(current.controllers || [], controllerRef, (controller) => controller.name || `Controller ${ref(controller)}`)}</select></label>
        <label class="compact-field"><span>Species ID</span><input type="number" min="0" max="65535" value="${context.species}" data-sequence-context="species"></label>
        <label class="compact-field"><span>Terrain</span><input type="number" min="0" max="255" value="${context.terrain}" data-sequence-context="terrain"></label>
        <label class="compact-field"><span>Level</span><input type="number" min="1" max="100" value="${context.level}" data-sequence-context="level"></label>
        <label class="compact-field"><span>Behavior class</span><input type="number" min="0" max="255" value="${context.behaviorClass}" data-sequence-context="behaviorClass"></label>
        <label class="compact-field"><span>Group / immutable mask</span><input type="number" min="0" max="4294967295" value="${context.groupMask}" data-sequence-context="groupMask"></label>
        <label class="check-control"><input type="checkbox" data-sequence-context="shiny" ${context.shiny ? "checked" : ""}><span>Shiny</span></label>
        <label class="check-control"><input type="checkbox" data-sequence-context="presentationGate" ${context.presentationGate ? "checked" : ""}><span>Initial presentation gate</span></label>
      </fieldset>
      <div class="stack-preview-layers"><header><strong>Override layers</strong><small>${layers.length} / ${current.stackPreview?.capacity || 8}</small></header>${layers.map((layer, index) => `<div class="stack-preview-layer" data-stack-layer="${index}"><select data-stack-definition="${index}" aria-label="Definition">${options(current.overrideDefinitions || [], layer.definitionId, (definition) => `${definition.name || `Definition ${ref(definition)}`} · ${definition.channelLabel}`)}</select><select data-stack-owner="${index}" aria-label="Owner">${options(current.owners || [], layer.ownerId, (owner) => owner.name || `Owner ${ref(owner)}`)}</select><input type="number" min="0" max="65535" value="${layer.instanceKey}" data-stack-instance="${index}" aria-label="Instance key"><button type="button" data-stack-remove="${index}" aria-label="Remove layer">×</button></div>`).join("") || `<p>No overrides. The controller base state wins.</p>`}<button class="button" type="button" data-stack-add ${layers.length >= Number(current.stackPreview?.capacity || 8) ? "disabled" : ""}>Add layer</button></div>
      <fieldset class="stack-preview-sequence"><legend>Event sequence</legend>
        <label class="compact-field"><span>Event</span><select data-sequence-trigger>${(current.transitionGraph?.triggerOptions || []).map((option) => `<option value="${option.value}" ${Number(option.value) === selectedTrigger ? "selected" : ""}>${escapeHtml(option.label)}</option>`).join("")}</select></label>
        <label class="compact-field"><span>System route</span><input type="number" min="0" max="255" value="${context.systemRoute}" data-sequence-context="systemRoute"></label>
        <label class="compact-field"><span>Chance roll</span><input type="number" min="0" max="99" value="${context.chanceRoll}" data-sequence-context="chanceRoll"></label>
        <button class="button" type="button" data-sequence-add-event>Step event</button>
        <label class="compact-field"><span>Ticks</span><input type="number" min="1" max="255" value="${tickCount}" data-sequence-ticks></label>
        <label class="check-control"><input type="checkbox" data-sequence-tick-gate ${tickPresentationGate ? "checked" : ""}><span>Gate during tick</span></label>
        <button class="button" type="button" data-sequence-add-tick="1">Tick frames</button>
        <button class="button" type="button" data-sequence-add-tick="2">Tick movement</button>
        <button class="button" type="button" data-sequence-reset ${steps.length ? "" : "disabled"}>Reset sequence</button>
        <small>${steps.length} / ${STACK_SEQUENCE_LIMITS.steps} steps</small>
      </fieldset>`;
  }

  function renderResult() {
    const preview = runStackEventSequence({
      model, draft: getDraft(), mode,
      context: { ...context, controllerRef }, initialLayers: layers, steps,
    });
    if (!preview.ok) {
      resolution.innerHTML = `<header class="panel-heading"><span><small>Deterministic preview</small><strong>Cannot compose</strong></span><span class="result-chip">${preview.errors.length} issue${preview.errors.length === 1 ? "" : "s"}</span></header><div class="stack-preview-errors">${preview.errors.map((error) => `<p><strong>${escapeHtml(error.code)}</strong><span>${escapeHtml(error.message)}</span></p>`).join("")}</div>`;
      return;
    }
    const result = preview.result;
    const layerRows = result.layers.map((layer) => `<tr><td>${escapeHtml(layer.definitionId)}</td><td>${escapeHtml(layer.ownerId)} / ${escapeHtml(layer.instanceKey)}</td><td><span class="stack-status stack-status--${escapeHtml(layer.visibility)}">${escapeHtml(layer.visibility)}</span></td><td>${escapeHtml(layer.timer.status)}${layer.timer.remainingTicks == null ? "" : ` · ${escapeHtml(layer.timer.remainingTicks)} / ${escapeHtml(layer.timer.armedDuration)}`}</td><td>${escapeHtml(layer.lifetime.map.label || layer.lifetime.map.value)} / ${escapeHtml(layer.lifetime.battle.label || layer.lifetime.battle.value)}</td></tr>`).join("");
    const fieldRows = Object.entries(result.fields).map(([key, item]) => `<tr><td>${escapeHtml(key)}</td><td>${escapeHtml(item.value)}</td><td>${escapeHtml(item.provenance.kind)} · profile ${escapeHtml(item.provenance.profileId)}</td></tr>`).join("");
    const draftHistory = preview.history || [];
    const savedHistory = preview.comparison?.saved?.history || [];
    const stateSummary = (snapshot) => {
      if (!snapshot) return "Unavailable";
      const identity = snapshot.identity;
      const source = snapshot.winningLayer
        ? `definition ${snapshot.winningLayer.definitionId} · owner ${snapshot.winningLayer.ownerId}:${snapshot.winningLayer.instanceKey}`
        : `base profile ${snapshot.baseIdentity.profileId}`;
      return `${identity.nodeId} / ${identity.profileId} / role ${identity.semanticRoleId} · ${source}`;
    };
    const timeline = draftHistory.map((entry, index) => {
      const label = entry.step.kind === "initial" ? "Initial" : entry.step.kind === "event" ? `Event ${entry.step.trigger}` : `${entry.step.ticks || 1} tick(s), clock ${entry.step.clock}`;
      return `<tr><td>${entry.index}</td><td>${escapeHtml(label)}</td><td>${escapeHtml(stateSummary(entry.snapshot))}</td>${savedHistory[index] ? `<td>${escapeHtml(stateSummary(savedHistory[index].snapshot))}</td>` : ""}<td>${escapeHtml(entry.report?.status || entry.report?.kind || "resolved")}</td></tr>`;
    }).join("");
    const dispatch = preview.context?.dispatch;
    resolution.innerHTML = `<header class="panel-heading"><span><small>Deterministic preview</small><strong>Effective state</strong></span><span class="result-chip">${preview.comparison ? (preview.comparison.changed ? "Changed" : "Same") : "Resolved"}</span></header><section class="stack-preview-result"><div class="stack-preview-identity"><span>Controller</span><strong>${escapeHtml(result.identity.controllerId)} · ${escapeHtml(dispatch?.kind || "explicit")}</strong><span>Node / profile / role</span><strong>${escapeHtml(result.identity.nodeId)} / ${escapeHtml(result.identity.profileId)} / ${escapeHtml(result.identity.semanticRoleId)}</strong></div><h3>Sequence</h3><table><thead><tr><th>#</th><th>Step</th><th>${preview.comparison ? "Draft" : "Effective"}</th>${preview.comparison ? "<th>Saved</th>" : ""}<th>Result</th></tr></thead><tbody>${timeline}</tbody></table><h3>Layers</h3><table><thead><tr><th>Definition</th><th>Owner / key</th><th>Status</th><th>Timer</th><th>Map / battle</th></tr></thead><tbody>${layerRows || `<tr><td colspan="5">Base state only</td></tr>`}</tbody></table><details><summary>Complete field provenance (${Object.keys(result.fields).length})</summary><table><thead><tr><th>Field</th><th>Value</th><th>Source</th></tr></thead><tbody>${fieldRows}</tbody></table></details><details><summary>Controller and policy provenance</summary><pre>${escapeHtml(JSON.stringify({ scalars: result.controllerScalars, policies: result.policies }, null, 2))}</pre></details></section>`;
  }

  function render() { renderControls(); renderResult(); }
  function openDrawer() { drawer.hidden = false; workbench.classList.add("is-resolver-open"); open.setAttribute("aria-expanded", "true"); render(); }
  function closeDrawer() { drawer.hidden = true; workbench.classList.remove("is-resolver-open"); open.setAttribute("aria-expanded", "false"); }
  function addLayer() {
    const current = activeModel();
    if (layers.length >= Number(current.stackPreview?.capacity || 8)) return;
    const definition = current.overrideDefinitions?.[0];
    const owner = current.owners?.find((item) => same(ref(item), definition?.requiredOwnerId)) || current.owners?.[0];
    if (!definition || !owner) return;
    layers.push({ definitionId: ref(definition), ownerId: ref(owner), instanceKey: 0 });
    render();
  }
  function onClick(event) {
    if (event.target === open) return void openDrawer();
    if (event.target === close) return void closeDrawer();
    if (event.target.matches("[data-stack-add]")) return void addLayer();
    if (event.target.matches("[data-stack-remove]")) { layers.splice(Number(event.target.dataset.stackRemove), 1); render(); }
    if (event.target.matches("[data-sequence-add-event]")) {
      if (steps.length < STACK_SEQUENCE_LIMITS.steps) steps.push({ kind: "event", trigger: selectedTrigger, systemRoute: context.systemRoute, chanceRoll: context.chanceRoll });
      render();
    }
    if (event.target.matches("[data-sequence-add-tick]")) {
      if (steps.length < STACK_SEQUENCE_LIMITS.steps) steps.push({ kind: "tick", clock: Number(event.target.dataset.sequenceAddTick), ticks: tickCount, presentationGate: tickPresentationGate });
      render();
    }
    if (event.target.matches("[data-sequence-reset]")) { steps = []; render(); }
  }
  function onChange(event) {
    if (event.target.matches("[data-stack-mode]")) mode = event.target.value;
    else if (event.target.matches("[data-stack-controller]")) controllerRef = event.target.value;
    else if (event.target.matches("[data-sequence-trigger]")) selectedTrigger = Number(event.target.value);
    else if (event.target.matches("[data-sequence-ticks]")) tickCount = Math.max(1, Math.min(255, Number(event.target.value) || 1));
    else if (event.target.matches("[data-sequence-tick-gate]")) tickPresentationGate = event.target.checked;
    else if (event.target.matches("[data-sequence-context]")) {
      const key = event.target.dataset.sequenceContext;
      const value = event.target.type === "checkbox" ? event.target.checked : Number(event.target.value);
      context[key] = value;
      if (key === "groupMask") context.immutableContextMask = Number(value) >>> 0;
      steps = [];
    }
    else if (event.target.matches("[data-stack-definition]")) {
      const layer = layers[Number(event.target.dataset.stackDefinition)];
      const definition = activeModel().overrideDefinitions?.find((item) => same(ref(item), event.target.value));
      layer.definitionId = event.target.value;
      layer.instanceKey = 0;
      if (definition?.requiredOwnerId) layer.ownerId = definition.requiredOwnerId;
    }
    else if (event.target.matches("[data-stack-owner]")) layers[Number(event.target.dataset.stackOwner)].ownerId = event.target.value;
    else if (event.target.matches("[data-stack-instance]")) layers[Number(event.target.dataset.stackInstance)].instanceKey = Number(event.target.value);
    else return;
    render();
  }
  open.hidden = false;
  open.closest("details")?.removeAttribute("hidden");
  workbench.addEventListener("click", onClick);
  workbench.addEventListener("change", onChange);
  render();
  return Object.freeze({
    refresh: render,
    result: () => runStackEventSequence({ model, draft: getDraft(), mode, context: { ...context, controllerRef }, initialLayers: clone(layers), steps: clone(steps) }),
    destroy: () => {
      if (destroyed) return;
      destroyed = true;
      workbench.removeEventListener("click", onClick);
      workbench.removeEventListener("change", onChange);
    },
  });
}
