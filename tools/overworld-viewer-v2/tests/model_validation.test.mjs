import assert from "node:assert/strict";
import {
  indexDiagnostics,
  materializeDraftGraph,
  validateBehaviorDraft,
  validateBehaviorModel,
  validateStackInput,
  VALIDATION_CODES,
} from "../static/model-validation.js";

const copy = (value) => structuredClone(value);
const fields = Array.from({ length: 28 }, (_, index) => ({
  key: index === 0 ? "hopMinDistance" : index === 1 ? "hopMaxDistance" : `field${index}`,
  label: `Field ${index}`, type: "number", minimum: 0, maximum: 255,
}));
const values = Object.fromEntries(fields.map((field) => [field.key, 0]));

function fixture() {
  const definition = {
    stableId: 50, applicabilityId: 61, priority: 100, kind: 1, channel: 2,
    selectorKind: 2, semanticRoleId: 1, controllerId: null, nodeId: null,
    mapLifetime: 2, battleLifetime: 1, timerClock: 1, timerSource: 1,
    timerValue: 4, hiddenTimerPolicy: 1, recoveryPolicy: 0,
    recoveryTransitionId: null, hasRequiredOwnerId: 1, requiredOwnerId: 60,
    hasTiredOriginKind: 0, tiredOriginKind: 0, allowMultipleOwners: 0,
    allowMultipleInstancesPerOwner: 0, authoredTiredBound: 0, flags: 0,
    reserved0: 0, reserved1: 0,
  };
  const transition = {
    stableId: 70, name: "Become active", order: 0, controllerIds: [20],
    candidateDefinitionId: 50, candidateDefinition: copy(definition), ownerId: 60,
    trigger: 1, fromRoleMask: 1, dispatchPriority: 8192,
    guards: [{ stableId: 71, kind: 1, negate: false, payload: 0, referenceId: null }],
    operations: [{ stableId: 72, definitionId: 50, ownerId: 60, replacementDefinitionId: null, policyId: null, instanceKey: 50, kind: 1, busyPolicy: 1, required: false }],
    actions: [{ stableId: 73, phase: 1, kind: 1, referenceId: null, payload: 0 }],
    recoveryActions: [{ stableId: 74, ownerId: 60, kind: 1, required: true }],
  };
  return {
    modelVersion: 40,
    validationSchema: {
      stateFieldCount: 28, stackCapacity: 8,
      unsigned: { byte: 255, short: 65535, word: 4294967295 },
      childCountMaximums: { guards: 65535, operations: 65535, actions: 65535, recoveryActions: 255 },
    },
    stateProfileFields: fields,
    stateProfiles: [{
      stableId: 10, bodyId: 11, bodyRegistryKey: "state-body:calm",
      bodyProvenance: { kind: 1, label: "Calm" }, name: "Calm",
      descriptiveTags: ["bird"], values: copy(values),
    }],
    semanticRoles: Array.from({ length: 7 }, (_, index) => ({ value: index + 1, label: `Role ${index + 1}` })),
    customRoles: [{ stableId: 40, value: 1, name: "Perch" }],
    controllerScalarFields: [{ key: "stamina", label: "Stamina", type: "number", minimum: 0, maximum: 64 }],
    controllers: [{
      stableId: 20, name: "Bird", baseNodeId: 30,
      nodes: [{ stableId: 30, controllerId: 20, profileStableId: 10, order: 0, semanticRoleId: 1, customRoleId: null, base: true, optional: false, hidden: false }],
      scalarDefaults: { stamina: 20 },
      policyIds: { spawnPolicyId: 80, populationPolicyId: 81, hookSetId: 82 },
      transitionIds: [70],
    }],
    owners: [{ stableId: 60, name: "System", systemOwned: true, flags: 0 }],
    applicability: [{ stableId: 61, name: "Everywhere", flags: 1, immutableContextMask: 0xFFFFFFFF, controllerId: null, effectiveProfileId: null, semanticRoleId: null }],
    overrideDefinitions: [definition],
    policyCatalog: {
      spawnPolicies: [{ stableId: 80, name: "Spawn" }],
      populationPolicies: [{ stableId: 81, name: "Population" }],
      hookSets: [{ stableId: 82, name: "Hooks" }],
    },
    transitionGraph: { triggerOptions: [{ value: 1, label: "Alert" }], transitions: [transition] },
    stackPreview: { capacity: 8 },
  };
}

function codes(diagnostics) {
  return new Set(diagnostics.map((item) => item.code));
}

function expectCode(mutate, code) {
  const model = fixture();
  mutate(model);
  const diagnostics = validateBehaviorModel(model);
  assert.equal(codes(diagnostics).has(code), true, `${code} missing from ${JSON.stringify(diagnostics, null, 2)}`);
}

// The complete saved V40 shape is clean and names/tags remain role-independent metadata.
assert.deepEqual(validateBehaviorModel(fixture()), []);

// Identity and complete, role-independent profile families.
expectCode((model) => { model.owners[0].stableId = 10; }, VALIDATION_CODES.IDENTITY_DUPLICATE);
{
  const model = fixture();
  model.stateProfiles.push({ ...copy(model.stateProfiles[0]), stableId: 12, name: "Shared calm" });
  assert.deepEqual(validateBehaviorModel(model), []);
}
expectCode((model) => {
  model.stateProfiles.push({ ...copy(model.stateProfiles[0]), stableId: 12, name: "Conflicting body", values: { ...copy(model.stateProfiles[0].values), field2: 1 } });
}, VALIDATION_CODES.IDENTITY_DUPLICATE);
expectCode((model) => {
  model.stateProfiles.push({ ...copy(model.stateProfiles[0]), stableId: 12, name: "Conflicting provenance", bodyProvenance: { kind: 2, label: "Active" } });
}, VALIDATION_CODES.IDENTITY_DUPLICATE);
expectCode((model) => {
  model.stateProfiles.push({ ...copy(model.stateProfiles[0]), stableId: 12, name: "Conflicting registry", bodyRegistryKey: "state-body:other" });
}, VALIDATION_CODES.IDENTITY_DUPLICATE);
expectCode((model) => { delete model.stateProfiles[0].values.field2; }, VALIDATION_CODES.PROFILE_FIELDS);
expectCode((model) => { model.stateProfiles[0].semanticRoleId = 1; }, VALIDATION_CODES.PROFILE_ROLE);
expectCode((model) => { model.stateProfiles[0].values.field2 = 256; }, VALIDATION_CODES.FIELD_DOMAIN);

// Controller base, binding, owner, selector, scalar, and policy families.
expectCode((model) => { model.controllers[0].nodes[0].base = false; }, VALIDATION_CODES.BASE_NODE);
expectCode((model) => { model.controllers[0].nodes[0].controllerId = 21; }, VALIDATION_CODES.NODE_OWNER);
expectCode((model) => { model.controllers[0].nodes[0].profileStableId = 999; }, VALIDATION_CODES.REFERENCE);
expectCode((model) => { model.controllers[0].nodes.push({ stableId: 31, controllerId: 20, profileStableId: 10, order: 1, semanticRoleId: 1, customRoleId: null, base: false }); }, VALIDATION_CODES.SELECTOR_DUPLICATE);
expectCode((model) => { model.controllers[0].scalarDefaults.stamina = 65; }, VALIDATION_CODES.FIELD_DOMAIN);
expectCode((model) => { model.controllers[0].policyIds.spawnPolicyId = 999; }, VALIDATION_CODES.CONTROLLER_POLICY);

// Definition, selector, owner, lifetime, timer, recovery, and cross-reference families.
expectCode((model) => { model.overrideDefinitions[0].selectorKind = 1; }, VALIDATION_CODES.DEFINITION_SELECTOR);
expectCode((model) => { model.overrideDefinitions[0].flags = 1; }, VALIDATION_CODES.DEFINITION_SELECTOR);
expectCode((model) => { model.overrideDefinitions[0].hasTiredOriginKind = 0; model.overrideDefinitions[0].tiredOriginKind = 2; }, VALIDATION_CODES.DEFINITION_DOMAIN);
expectCode((model) => { model.overrideDefinitions[0].hasTiredOriginKind = 1; model.overrideDefinitions[0].tiredOriginKind = 0; }, VALIDATION_CODES.DEFINITION_DOMAIN);
expectCode((model) => { model.overrideDefinitions[0].applicabilityId = 999; }, VALIDATION_CODES.REFERENCE);
expectCode((model) => { model.overrideDefinitions[0].requiredOwnerId = 999; }, VALIDATION_CODES.REFERENCE);
expectCode((model) => { model.overrideDefinitions[0].mapLifetime = 9; }, VALIDATION_CODES.LIFETIME);
expectCode((model) => { model.overrideDefinitions[0].timerClock = 0; }, VALIDATION_CODES.TIMER);
expectCode((model) => { model.overrideDefinitions[0].timerValue = 0; }, VALIDATION_CODES.TIMER);
expectCode((model) => { model.overrideDefinitions[0].recoveryPolicy = 1; model.overrideDefinitions[0].recoveryTransitionId = 999; }, VALIDATION_CODES.REFERENCE);
expectCode((model) => {
  const definition = { ...copy(model.overrideDefinitions[0]), stableId: 51, recoveryPolicy: 0, recoveryTransitionId: null };
  const transition = copy(model.transitionGraph.transitions[0]);
  transition.stableId = 75;
  transition.candidateDefinitionId = 51;
  transition.candidateDefinition = copy(definition);
  transition.guards[0].stableId = 76;
  transition.operations[0].stableId = 77;
  transition.operations[0].definitionId = 51;
  transition.operations[0].instanceKey = 51;
  transition.actions[0].stableId = 78;
  transition.recoveryActions[0].stableId = 79;
  model.overrideDefinitions.push(definition);
  model.transitionGraph.transitions.push(transition);
  model.controllers[0].transitionIds.push(75);
  model.overrideDefinitions[0].recoveryPolicy = 1;
  model.overrideDefinitions[0].recoveryTransitionId = 75;
}, VALIDATION_CODES.RECOVERY);

// Transition scope, child domain/count, reference, and wire-width families.
expectCode((model) => { model.transitionGraph.transitions[0].controllerIds = []; }, VALIDATION_CODES.TRANSITION_SCOPE);
expectCode((model) => { model.transitionGraph.transitions[0].guards[0].kind = 99; }, VALIDATION_CODES.CHILD_DOMAIN);
expectCode((model) => { model.transitionGraph.transitions[0].operations[0].definitionId = 999; }, VALIDATION_CODES.REFERENCE);
expectCode((model) => { model.transitionGraph.transitions[0].operations[0].instanceKey = 51; }, VALIDATION_CODES.CHILD_DOMAIN);
expectCode((model) => { model.transitionGraph.transitions[0].operations[0].replacementDefinitionId = 50; }, VALIDATION_CODES.CHILD_DOMAIN);
expectCode((model) => {
  model.owners.push({ stableId: 62, name: "Other system" });
  model.overrideDefinitions.push({ ...copy(model.overrideDefinitions[0]), stableId: 51, requiredOwnerId: 62 });
  const operation = model.transitionGraph.transitions[0].operations[0];
  operation.kind = 2;
  operation.replacementDefinitionId = 51;
}, VALIDATION_CODES.OWNER_REQUIRED);
expectCode((model) => { const operation = model.transitionGraph.transitions[0].operations[0]; operation.kind = 5; }, VALIDATION_CODES.CHILD_DOMAIN);
expectCode((model) => { model.transitionGraph.transitions[0].actions[0].kind = 0; }, VALIDATION_CODES.CHILD_DOMAIN);
expectCode((model) => {
  model.owners.push({ stableId: 62, name: "Other system" });
  model.transitionGraph.transitions[0].ownerId = 62;
  model.transitionGraph.transitions[0].operations[0].ownerId = 62;
}, VALIDATION_CODES.OWNER_REQUIRED);
expectCode((model) => { model.transitionGraph.transitions[0].operations[0].definitionId = 50; model.transitionGraph.transitions[0].candidateDefinitionId = 51; }, VALIDATION_CODES.CHILD_DOMAIN);
expectCode((model) => { model.transitionGraph.transitions[0].dispatchPriority = 65536; }, VALIDATION_CODES.WIRE_RANGE);
expectCode((model) => { model.validationSchema.childCountMaximums.guards = 0; }, VALIDATION_CODES.CHILD_COUNT);

function addTransitionCopy(model, { controllerId, definitionId, applicabilityId = 61 }) {
  const source = model.transitionGraph.transitions[0];
  const definition = { ...copy(model.overrideDefinitions[0]), stableId: definitionId, controllerId, applicabilityId };
  const transition = copy(source);
  Object.assign(transition, {
    stableId: 75, name: "Parallel dispatch", order: 1, controllerIds: [controllerId],
    candidateDefinitionId: definitionId, candidateDefinition: copy(definition),
  });
  transition.guards[0].stableId = 76;
  Object.assign(transition.operations[0], { stableId: 77, definitionId, instanceKey: definitionId });
  transition.actions[0].stableId = 78;
  transition.recoveryActions[0].stableId = 79;
  model.overrideDefinitions.push(definition);
  model.transitionGraph.transitions.push(transition);
  return transition;
}

// Equal-priority dispatch is rejected only when event, role, and effective
// controller scopes overlap.
{
  const model = fixture();
  const duplicate = addTransitionCopy(model, { controllerId: 20, definitionId: 51 });
  model.overrideDefinitions[0].controllerId = 20;
  model.transitionGraph.transitions[0].candidateDefinition.controllerId = 20;
  model.controllers[0].transitionIds.push(duplicate.stableId);
  assert.equal(codes(validateBehaviorModel(model)).has(VALIDATION_CODES.TRANSITION_AMBIGUOUS), true);
}
{
  const model = fixture();
  model.overrideDefinitions[0].controllerId = 20;
  model.transitionGraph.transitions[0].candidateDefinition.controllerId = 20;
  model.controllers.push({
    ...copy(model.controllers[0]), stableId: 21, name: "Other", baseNodeId: 31,
    nodes: [{ ...copy(model.controllers[0].nodes[0]), stableId: 31, controllerId: 21 }], transitionIds: [75],
  });
  addTransitionCopy(model, { controllerId: 21, definitionId: 51 });
  assert.deepEqual(validateBehaviorModel(model), []);
}
{
  const model = fixture();
  Object.assign(model.applicability[0], { controllerId: 20, flags: 3 });
  model.controllers.push({
    ...copy(model.controllers[0]), stableId: 21, name: "Other", baseNodeId: 31,
    nodes: [{ ...copy(model.controllers[0].nodes[0]), stableId: 31, controllerId: 21 }], transitionIds: [75],
  });
  model.applicability.push({ ...copy(model.applicability[0]), stableId: 62, controllerId: 21 });
  addTransitionCopy(model, { controllerId: null, definitionId: 51, applicabilityId: 62 });
  model.transitionGraph.transitions[1].controllerIds = [21];
  assert.deepEqual(validateBehaviorModel(model), []);
}

// Draft transactions are isolated copies and unsupported domains are explicit.
{
  const saved = fixture();
  const draft = { modelVersion: 40, stateProfiles: { update: [{ ...copy(saved.stateProfiles[0]), name: "Relaxed" }] } };
  const materialized = materializeDraftGraph(saved, draft);
  materialized.stateProfiles[0].values.field2 = 99;
  assert.equal(saved.stateProfiles[0].values.field2, 0);
  assert.equal(draft.stateProfiles.update[0].values.field2, 0);
  assert.equal(validateBehaviorDraft(saved, draft).length, 0);
  const invalid = { stateProfiles: { create: [{ stableId: 90, name: "Bad", values: copy(values) }] } };
  assert.equal(codes(validateBehaviorDraft(saved, invalid)).has(VALIDATION_CODES.DRAFT_TRANSACTION), true);
  assert.deepEqual(validateBehaviorDraft(saved, { owners: { create: [] } }), []);
  assert.equal(codes(validateBehaviorDraft(saved, { owners: { create: [{ draftId: "draft:owner" }] } })).has(VALIDATION_CODES.REPRESENTATION), true);
  assert.equal(codes(validateBehaviorDraft(saved, { importRecipes: { remove: [1] } })).has(VALIDATION_CODES.REPRESENTATION), true);
  assert.equal(codes(validateBehaviorDraft(saved, { tiredTranslations: { remove: [1] } })).has(VALIDATION_CODES.REPRESENTATION), true);
}

// Direct writer domains used by Complete Behavior Set materialize and validate
// in the same client-side graph as profiles/controllers/transitions.
{
  const saved = fixture();
  const draft = {
    modelVersion: 40,
    spawnPolicies: { create: [{
      draftId: "draft:spawn", stableId: null, provenanceId: 90,
      spawnState: 3, destination: 0, minimumDistance: 1,
      maximumDistance: 5, spawnHopTime: 4, flags: 0,
    }] },
    populationPolicies: { create: [{
      draftId: "draft:population", stableId: null, populationGroupId: 91,
      provenanceId: 90, limit: 4, flags: 0,
    }] },
    assignmentActions: { create: [{
      draftId: "draft:assignment-action", stableId: null,
      kind: 1, flags: 0, payload: { controllerRef: 20 },
    }] },
    genericAssignments: { create: [{
      draftId: "draft:generic", stableId: null, controllerIndex: "draft:assignment-action",
      dispatchPriority: 7,
      match: { groupMask: 1, species: 0, terrain: 255, minimumLevel: 0, maximumLevel: 0, shiny: 255, behaviorClass: 255 },
    }] },
    speciesAssignments: { create: [{
      draftId: "draft:species", stableId: null, controllerIndex: "draft:assignment-action",
      dispatchPriority: 8, species: 25,
    }] },
  };
  assert.deepEqual(validateBehaviorDraft(saved, draft), []);
  const materialized = materializeDraftGraph(saved, draft);
  assert.equal(materialized.policyCatalog.spawnPolicies.at(-1).draftId, "draft:spawn");
  assert.equal(materialized.policyCatalog.populationPolicies.at(-1).draftId, "draft:population");
  assert.equal(materialized.assignmentActions.at(-1).payload.controllerRef, 20);
  assert.equal(materialized.genericAssignments.at(-1).controllerIndex, "draft:assignment-action");
  assert.equal(materialized.speciesAssignments.at(-1).species, 25);
}

// Transition-owned definition and applicability edits replace their canonical
// validation records, so the exact graph submitted to the writer is checked.
{
  const saved = fixture();
  const transition = copy(saved.transitionGraph.transitions[0]);
  transition.candidateDefinition.priority = 255;
  transition.candidateDefinition.applicability = {
    stableId: 61, name: "Everywhere", kind: 1, groupMask: 0xFFFFFFFF,
    controllerId: null, profileId: null, minimum: 0, maximum: 0, flags: 0,
  };
  const valid = { modelVersion: 40, transitions: { update: [transition] } };
  assert.deepEqual(validateBehaviorDraft(saved, valid), []);
  transition.candidateDefinition.priority = 256;
  assert.equal(codes(validateBehaviorDraft(saved, valid)).has(VALIDATION_CODES.WIRE_RANGE), true);
  transition.candidateDefinition.priority = 255;
  transition.candidateDefinition.requiredOwnerId = 999;
  assert.equal(codes(validateBehaviorDraft(saved, valid)).has(VALIDATION_CODES.REFERENCE), true);
  const conflict = copy(transition);
  conflict.stableId = null;
  conflict.draftId = "draft:conflicting-transition";
  conflict.candidateDefinition.requiredOwnerId = 60;
  assert.equal(codes(validateBehaviorDraft(saved, {
    transitions: { update: [transition], create: [conflict] },
  })).has(VALIDATION_CODES.DRAFT_TRANSACTION), true);
}

// An authored shared definition/applicability update wins over every untouched
// saved transition that still embeds the prior display record.
{
  const saved = fixture();
  const sibling = copy(saved.transitionGraph.transitions[0]);
  sibling.stableId = 75;
  sibling.name = "Shared sibling";
  sibling.order = 1;
  sibling.dispatchPriority -= 1;
  sibling.guards[0].stableId = 76;
  sibling.operations[0].stableId = 77;
  sibling.actions[0].stableId = 78;
  sibling.recoveryActions[0].stableId = 79;
  saved.transitionGraph.transitions.push(sibling);
  saved.controllers[0].transitionIds.push(75);
  const update = copy(saved.transitionGraph.transitions[0]);
  update.candidateDefinition.priority = 254;
  update.candidateDefinition.applicability = {
    stableId: 61, name: "Edited shared rule", kind: 1, groupMask: 255,
    controllerId: null, profileId: null, minimum: 0, maximum: 0, flags: 0,
  };
  const materialized = materializeDraftGraph(saved, { transitions: { update: [update] } });
  assert.equal(materialized.overrideDefinitions.find((item) => item.stableId === 50).priority, 254);
  assert.equal(materialized.applicability.find((item) => item.stableId === 61).immutableContextMask, 255);
  assert.deepEqual(validateBehaviorDraft(saved, { transitions: { update: [update] } }), []);
}

// Stack keys, capacity, ownership, multiplicity, and selectors are deterministic.
{
  const model = fixture();
  const valid = [{ definitionId: 50, ownerId: 60, instanceKey: 0 }];
  assert.deepEqual(validateStackInput(model, { controllerRef: 20, layers: valid }), []);
  assert.equal(codes(validateStackInput(model, { controllerRef: 20, layers: Array.from({ length: 9 }, () => ({ definitionId: 50, ownerId: 60, instanceKey: 0 })) })).has(VALIDATION_CODES.STACK_CAPACITY), true);
  assert.equal(codes(validateStackInput(model, { controllerRef: 20, layers: [{ definitionId: 50, ownerId: 60, instanceKey: 65536 }] })).has(VALIDATION_CODES.STACK_INSTANCE), true);
  assert.equal(codes(validateStackInput(model, { controllerRef: 20, layers: [...valid, ...valid] })).has(VALIDATION_CODES.STACK_IDENTITY), true);
  model.owners.push({ stableId: 62, name: "Other" });
  assert.equal(codes(validateStackInput(model, { controllerRef: 20, layers: [{ definitionId: 50, ownerId: 62, instanceKey: 0 }] })).has(VALIDATION_CODES.OWNER_REQUIRED), true);
  model.overrideDefinitions[0].hasRequiredOwnerId = 0;
  model.overrideDefinitions[0].requiredOwnerId = null;
  assert.equal(codes(validateStackInput(model, { controllerRef: 20, layers: [{ definitionId: 50, ownerId: 60, instanceKey: 0 }, { definitionId: 50, ownerId: 62, instanceKey: 0 }] })).has(VALIDATION_CODES.OWNER_MULTIPLICITY), true);
}

// Stable sorting, deduplication, and entity indexing do not depend on mutation order.
{
  const left = fixture();
  left.controllers[0].nodes[0].profileStableId = 999;
  left.controllers[0].policyIds.spawnPolicyId = 999;
  const right = fixture();
  right.controllers[0].policyIds.spawnPolicyId = 999;
  right.controllers[0].nodes[0].profileStableId = 999;
  const a = validateBehaviorModel(left);
  const b = validateBehaviorModel(right);
  assert.deepEqual(a, b);
  const indexed = indexDiagnostics(a);
  assert.equal(indexed["controller:20"].some((item) => item.code === VALIDATION_CODES.CONTROLLER_POLICY), true);
  assert.equal(indexed["controllerNode:30"].some((item) => item.code === VALIDATION_CODES.REFERENCE), true);
}

console.log("OWBD V40 whole-graph validation tests passed");
