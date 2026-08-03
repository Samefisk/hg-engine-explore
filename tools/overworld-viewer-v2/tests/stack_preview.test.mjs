import assert from "node:assert/strict";
import {
  STACK_PREVIEW_CODES,
  comparePrecedence,
  composeStackPreview,
  materializePreviewModel,
  preserveStackPreviewSelection,
} from "../static/stack-preview.js";

const fields = ["behaviorKind", "speed", "movementRange"].map((key) => ({ key }));
const profile = (stableId, value) => ({ stableId, name: `Profile ${stableId}`, values: Object.fromEntries(fields.map((field) => [field.key, value])) });
const node = (stableId, profileStableId, semanticRoleId, base = false) => ({ stableId, profileStableId, semanticRoleId, base });
const applicability = (stableId) => ({ stableId, immutableContextMask: 0xFFFFFFFF, controllerId: null, effectiveProfileId: null, semanticRoleId: null });
const definition = (stableId, nodeId, overrides = {}) => ({
  stableId, applicabilityId: stableId + 1000, kind: 1, channel: 2, priority: 10,
  selectorKind: 1, nodeId, semanticRoleId: 0, controllerId: null,
  hasRequiredOwnerId: 0, requiredOwnerId: null,
  allowMultipleOwners: 1, allowMultipleInstancesPerOwner: 1,
  mapLifetime: 1, mapLifetimeLabel: "Clear", battleLifetime: 2, battleLifetimeLabel: "Preserve logical",
  timerClock: 0, timerClockLabel: "None", timerSource: 0, timerSourceLabel: "None",
  timerValue: 0, hiddenTimerPolicy: 0, recoveryPolicy: 0, recoveryPolicyLabel: "None",
  recoveryTransitionId: null, ...overrides,
});

function fixture() {
  const definitions = [definition(101, 12), definition(102, 13), definition(103, 14)];
  return {
    modelVersion: 40,
    stateProfileFields: fields,
    controllerScalarFields: [{ key: "stamina" }],
    stateProfiles: [profile(20, 1), profile(21, 2), profile(22, 3), profile(23, 4)],
    controllers: [{
      stableId: 1, name: "Bird", scalarDefaults: { stamina: 20 }, policyIds: { spawnPolicyId: 7 },
      nodes: [node(11, 20, 1, true), node(12, 21, 2), node(13, 22, 3), node(14, 23, 4)],
    }],
    owners: [{ stableId: 201 }, { stableId: 202 }, { stableId: 203 }],
    applicability: definitions.map((item) => applicability(item.applicabilityId)),
    overrideDefinitions: definitions,
    stackPreview: { capacity: 8 },
  };
}

const layer = (definitionId, ownerId = 201, instanceKey = 0) => ({ definitionId, ownerId, instanceKey });
const compose = (model, layers, extra = {}) => composeStackPreview({ model, controllerRef: 1, layers, ...extra });

// Canonical composition is independent of input order and exposes complete provenance.
{
  const model = fixture();
  const forward = compose(model, [layer(101), layer(102, 202), layer(103, 203)]);
  const reverse = compose(model, [layer(103, 203), layer(101), layer(102, 202)]);
  assert.equal(forward.ok, true);
  assert.deepEqual(forward.result.identity, { controllerId: 1, nodeId: 14, profileId: 23, semanticRoleId: 4 });
  assert.deepEqual(forward.result.canonicalOrder, reverse.result.canonicalOrder);
  assert.deepEqual(forward.result.winningLayer, reverse.result.winningLayer);
  assert.equal(Object.keys(forward.result.fields).length, fields.length);
  assert.equal(forward.result.fields.speed.provenance.definitionId, 103);
  assert.deepEqual(forward.result.controllerScalars.stamina.provenance, { kind: "controller-base", controllerId: 1 });
  assert.deepEqual(forward.result.policies.spawnPolicyId.provenance, { kind: "controller-base", controllerId: 1 });
}

// Every precedence component is deterministic and higher wins.
{
  assert.equal(comparePrecedence({ channel: 1, priority: 99, definitionStableId: 9, ownerId: 9, instanceKey: 9 }, { channel: 2, priority: 0, definitionStableId: 0, ownerId: 0, instanceKey: 0 }), -1);
  assert.equal(comparePrecedence({ channel: 2, priority: 9, definitionStableId: 9, ownerId: 9, instanceKey: 9 }, { channel: 2, priority: 10, definitionStableId: 0, ownerId: 0, instanceKey: 0 }), -1);
  assert.equal(comparePrecedence({ channel: 2, priority: 10, definitionStableId: 101, ownerId: 9, instanceKey: 9 }, { channel: 2, priority: 10, definitionStableId: 102, ownerId: 0, instanceKey: 0 }), -1);
  assert.equal(comparePrecedence({ channel: 2, priority: 10, definitionStableId: 101, ownerId: 201, instanceKey: 9 }, { channel: 2, priority: 10, definitionStableId: 101, ownerId: 202, instanceKey: 0 }), -1);
  assert.equal(comparePrecedence({ channel: 2, priority: 10, definitionStableId: 101, ownerId: 201, instanceKey: 1 }, { channel: 2, priority: 10, definitionStableId: 101, ownerId: 201, instanceKey: 2 }), -1);
  const model = fixture();
  model.overrideDefinitions[0].channel = 5;
  model.overrideDefinitions[1].priority = 255;
  assert.equal(compose(model, [layer(101), layer(102, 202)]).result.winningLayer.definitionId, 101);
  model.overrideDefinitions[0].channel = 2;
  assert.equal(compose(model, [layer(101), layer(102, 202)]).result.winningLayer.definitionId, 102);
  model.overrideDefinitions[1].priority = 10;
  assert.equal(compose(model, [layer(101), layer(102, 202)]).result.winningLayer.definitionId, 102);
  assert.deepEqual(compose(model, [layer(101, 201, 1), layer(101, 202, 1)]).result.winningLayer, { definitionId: 101, ownerId: 202, instanceKey: 1 });
  assert.deepEqual(compose(model, [layer(101, 201, 1), layer(101, 201, 2)]).result.winningLayer, { definitionId: 101, ownerId: 201, instanceKey: 2 });
}

// Removing a middle layer is inert; removing the winner reveals the next canonical candidate.
{
  const model = fixture();
  const all = compose(model, [layer(101), layer(102, 202), layer(103, 203)]).result;
  const withoutMiddle = compose(model, [layer(101), layer(103, 203)]).result;
  const withoutWinner = compose(model, [layer(101), layer(102, 202)]).result;
  assert.deepEqual(withoutMiddle.winningLayer, all.winningLayer);
  assert.equal(withoutWinner.winningLayer.definitionId, 102);
}

// Saved, draft, and compare modes are isolated and invalid draft references clear the result.
{
  const model = fixture();
  const draft = { stateProfiles: { update: [{ ...profile(20, 9) }] } };
  const saved = composeStackPreview({ model, draft, mode: "saved", controllerRef: 1, layers: [] });
  const drafted = composeStackPreview({ model, draft, mode: "draft", controllerRef: 1, layers: [] });
  const compared = composeStackPreview({ model, draft, mode: "compare", controllerRef: 1, layers: [] });
  assert.equal(saved.result.fields.speed.value, 1);
  assert.equal(drafted.result.fields.speed.value, 9);
  assert.equal(compared.comparison.changed, true);
  assert.equal(model.stateProfiles[0].values.speed, 1);
  const invalid = composeStackPreview({
    model, mode: "draft", controllerRef: "draft:controller",
    draft: { controllers: { create: [{ draftId: "draft:controller", name: "Broken", nodes: [{ draftId: "draft:node", profileRef: "draft:missing", semanticRoleId: 1, base: true }], scalarDefaults: {}, policyIds: {} }] } },
    layers: [],
  });
  assert.equal(invalid.result, null);
  assert.equal(invalid.errors[0].code, STACK_PREVIEW_CODES.DRAFT);
}

// Exact and semantic selectors both preserve the four-part runtime identity.
{
  const model = fixture();
  model.overrideDefinitions[0].selectorKind = 2;
  model.overrideDefinitions[0].semanticRoleId = 3;
  assert.deepEqual(compose(model, [layer(101)]).result.identity, { controllerId: 1, nodeId: 13, profileId: 22, semanticRoleId: 3 });
  model.controllers[0].nodes.push(node(15, 23, 3));
  const ambiguous = compose(model, [layer(101)]);
  assert.equal(ambiguous.result, null);
  assert.equal(ambiguous.errors[0].code, STACK_PREVIEW_CODES.AMBIGUOUS);
}

// Stable validation codes cover ownership, multiplicity, capacity, and dangling references.
{
  const model = fixture();
  assert.equal(compose(model, [layer(101, 999)]).errors[0].code, STACK_PREVIEW_CODES.OWNER);
  model.overrideDefinitions[0].hasRequiredOwnerId = 1;
  model.overrideDefinitions[0].requiredOwnerId = 202;
  assert.equal(compose(model, [layer(101, 201)]).errors[0].code, STACK_PREVIEW_CODES.REQUIRED_OWNER);
  model.overrideDefinitions[0].hasRequiredOwnerId = 0;
  model.overrideDefinitions[0].allowMultipleOwners = 0;
  assert.equal(compose(model, [layer(101, 201), layer(101, 202)]).errors[0].code, STACK_PREVIEW_CODES.MULTIPLE_OWNERS);
  model.overrideDefinitions[0].allowMultipleOwners = 1;
  model.overrideDefinitions[0].allowMultipleInstancesPerOwner = 0;
  assert.equal(compose(model, [layer(101, 201, 1)]).errors[0].code, STACK_PREVIEW_CODES.INSTANCE_KEY);
  assert.equal(compose(model, [layer(101, 201, 0.5)]).errors[0].code, STACK_PREVIEW_CODES.INSTANCE_KEY);
  assert.equal(compose(model, [layer(101, 201, 65536)]).errors[0].code, STACK_PREVIEW_CODES.INSTANCE_KEY);
  assert.equal(compose(model, [layer(101, 201, null)]).errors[0].code, STACK_PREVIEW_CODES.INSTANCE_KEY);
  assert.equal(compose(model, Array.from({ length: 9 }, (_, index) => layer(102, 201, index))).errors[0].code, STACK_PREVIEW_CODES.CAPACITY);
  assert.equal(compose(model, [layer(999)]).errors[0].code, STACK_PREVIEW_CODES.DANGLING);
  model.overrideDefinitions[0].nodeId = 999;
  assert.equal(compose(model, [layer(101)]).errors[0].code, STACK_PREVIEW_CODES.DANGLING);
  model.overrideDefinitions[0].nodeId = 12;
  model.overrideDefinitions[0].kind = 2;
  assert.equal(compose(model, [layer(101)]).errors[0].code, STACK_PREVIEW_CODES.MODIFIER);
}

// Timer, hidden, recovery, and lifetime statuses follow the winning candidate.
{
  const model = fixture();
  Object.assign(model.overrideDefinitions[0], { timerClock: 1, timerClockLabel: "Frame", timerSource: 1, timerSourceLabel: "Fixed", timerValue: 12, hiddenTimerPolicy: 1, recoveryPolicy: 1, recoveryPolicyLabel: "Route transition", recoveryTransitionId: 501 });
  Object.assign(model.overrideDefinitions[1], { timerClock: 2, timerClockLabel: "Completed movement", timerSource: 2, timerSourceLabel: "Controller stamina", hiddenTimerPolicy: 2 });
  const result = compose(model, [layer(101), layer(102, 202)]).result;
  assert.equal(result.layers.find((item) => item.definitionId === 101).timer.status, "paused-while-hidden");
  assert.equal(result.layers.find((item) => item.definitionId === 102).timer.status, "running");
  assert.deepEqual(result.layers.find((item) => item.definitionId === 101).recovery, { policy: 1, label: "Route transition", transitionId: 501 });
  assert.deepEqual(result.layers.find((item) => item.definitionId === 101).lifetime, { map: { value: 1, label: "Clear" }, battle: { value: 2, label: "Preserve logical" } });

  model.overrideDefinitions[0].controllerId = 999;
  model.overrideDefinitions[0].hiddenTimerPolicy = 3;
  const retained = compose(model, [layer(101)]).result.layers[0];
  assert.equal(retained.visibility, "not-applicable");
  assert.equal(retained.timer.status, "expires-on-hide");
}

// Draft definitions and owners are never converted to NaN precedence keys.
{
  const model = fixture();
  const draftDefinition = { ...definition(0, 12), stableId: null, draftId: "draft:def" };
  const draftOwner = { stableId: null, draftId: "draft:owner" };
  const draft = {
    overrideDefinitions: { create: [draftDefinition] },
    owners: { create: [draftOwner] },
    applicability: { create: [applicability(draftDefinition.applicabilityId)] },
  };
  const left = composeStackPreview({ model, draft, mode: "draft", controllerRef: 1, layers: [layer("draft:def"), layer(101, 202)] });
  const right = composeStackPreview({ model, draft, mode: "draft", controllerRef: 1, layers: [layer(101, 202), layer("draft:def")] });
  assert.equal(left.result, null);
  assert.equal(right.result, null);
  assert.equal(left.errors.find((error) => error.code === STACK_PREVIEW_CODES.DRAFT).code, STACK_PREVIEW_CODES.DRAFT);
  assert.equal(right.errors.find((error) => error.code === STACK_PREVIEW_CODES.DRAFT).code, STACK_PREVIEW_CODES.DRAFT);
  assert.equal(composeStackPreview({ model, draft, mode: "draft", controllerRef: 1, layers: [layer(101, "draft:owner")] }).errors[0].code, STACK_PREVIEW_CODES.DRAFT);
}

// Draft/compare mode retains removed selections so composition reports and clears them.
{
  const model = fixture();
  const layers = [layer(101)];
  const withoutDefinition = materializePreviewModel(model, { overrideDefinitions: { remove: [101] } });
  assert.deepEqual(preserveStackPreviewSelection(withoutDefinition, 1, layers), { controllerRef: 1, layers });
  const missingDefinition = composeStackPreview({ model, draft: { overrideDefinitions: { remove: [101] } }, mode: "draft", controllerRef: 1, layers });
  assert.equal(missingDefinition.result, null);
  assert.equal(missingDefinition.errors[0].code, STACK_PREVIEW_CODES.DANGLING);
  const missingController = composeStackPreview({ model, draft: { controllers: { remove: [1] } }, mode: "compare", controllerRef: 1, layers: [] });
  assert.equal(missingController.result, null);
  assert.equal(missingController.errors.at(-1).code, STACK_PREVIEW_CODES.DANGLING);
}

// Materialization is a copy, never an edit of saved state.
{
  const model = fixture();
  const result = materializePreviewModel(model, { stateProfiles: { update: [profile(20, 7)] } });
  result.stateProfiles[0].values.speed = 99;
  assert.equal(model.stateProfiles[0].values.speed, 1);
}

console.log("stack preview tests passed");
