import assert from "node:assert/strict";
import {
  createCompleteStateDraft,
  createCompleteBehaviorSetDraft,
  createControllerDraft,
  createProfilesController,
  compactBehaviorModelDraft,
  behaviorModelChangeCount,
  validateCompleteStateProfile,
  validateControllerDraft,
  v40ProfileDeckCapability,
} from "../static/profiles.js";

const fields = [
  { key: "behaviorKind", label: "Behavior", type: "enum", options: [
    { value: 1, label: "Idle" }, { value: 2, label: "Chase" }, { value: 10, label: "Tired Emote" },
  ] },
  { key: "hopMinDistance", label: "Minimum hop distance", type: "number", minimum: 0, maximum: 12 },
  { key: "hopMaxDistance", label: "Maximum hop distance", type: "number", minimum: 0, maximum: 12 },
];

const draft = createCompleteStateDraft(fields, null, "Bird calm");
assert.match(draft.draftId, /^draft:/);
assert.equal(draft.stableId, null);
assert.deepEqual(draft.values, { behaviorKind: 1, hopMinDistance: 0, hopMaxDistance: 0 });
assert.deepEqual(validateCompleteStateProfile(draft, fields), []);
draft.templateProvenance = { kind: 1, provenanceId: 36865 };
const compactDraft = compactBehaviorModelDraft({ stateProfiles: { create: [draft] } }, {
  stateProfiles: [], controllers: [], transitionGraph: { transitions: [] },
});
assert.equal(behaviorModelChangeCount(compactDraft), 1);
assert.deepEqual(Object.keys(compactDraft.stateProfiles.create[0]).sort(), [
  "descriptiveTags", "draftId", "name", "templateProvenance", "values",
].sort());

const copy = createCompleteStateDraft(fields, {
  name: "Bird active",
  descriptiveTags: ["bird", "air"],
  values: { behaviorKind: 1, hopMinDistance: 2, hopMaxDistance: 5 },
}, "Bird active copy");
assert.equal(copy.name, "Bird active copy");
assert.equal("semanticRole" in copy, false);
assert.deepEqual(copy.descriptiveTags, ["bird", "air"]);
assert.deepEqual(copy.values, { behaviorKind: 1, hopMinDistance: 2, hopMaxDistance: 5 });

copy.values.hopMaxDistance = 1;
assert.equal(validateCompleteStateProfile(copy, fields).at(-1).path, "values.hopMaxDistance");

console.log("V40 state-profile editor unit checks passed");

const controllerModel = {
  stateProfiles: [{ stableId: 8705, name: "Bird calm" }],
  semanticRoles: [
    { value: 1, label: "Calm" }, { value: 2, label: "Active" }, { value: 3, label: "Tired" },
    { value: 7, label: "Custom", custom: true },
  ],
  customRoles: [{ stableId: 37377, name: "Custom role 1" }],
  policyCatalog: {
    spawnPolicies: [{
      stableId: 16380, name: "Decoy spawn policy", provenanceId: 1,
      spawnState: 0, destination: 0, minimumDistance: 0, maximumDistance: 0,
      spawnHopTime: 0, flags: 0,
    }, {
      stableId: 16385, name: "Spawn policy", provenanceId: 36865,
      spawnState: 3, destination: 0, minimumDistance: 1, maximumDistance: 5,
      spawnHopTime: 4, flags: 0,
    }],
    populationPolicies: [{
      stableId: 16640, name: "Decoy population policy", populationGroupId: 1,
      provenanceId: 1, limit: 1, flags: 0,
    }, {
      stableId: 16641, name: "Population policy", populationGroupId: 17665,
      provenanceId: 36865, limit: 0, flags: 0,
    }],
    hookSets: [{
      stableId: 16896, name: "Decoy hook set", helpCallInvocation: 9,
      pickupThrowEntry: 9, pickupThrowActiveLoop: 9, flags: 0,
    }, {
      stableId: 16897, name: "Hook set", helpCallInvocation: 0,
      pickupThrowEntry: 0, pickupThrowActiveLoop: 0, flags: 0,
    }],
  },
  controllerScalarFields: [
    { key: "alertState", label: "Alert state", type: "number", minimum: 0, maximum: 255 },
    { key: "stamina", label: "Stamina", type: "number", minimum: 0, maximum: 64 },
    { key: "restTime", label: "Rest time", type: "number", minimum: 0, maximum: 255 },
  ],
  transitionGraph: { triggerOptions: [{ value: 1, label: "Detection" }] },
};
const behaviorSetDraft = createCompleteBehaviorSetDraft({
  fields,
  templateProfile: copy,
  roleTemplates: {
    calm: copy,
    active: { ...copy, stableId: 8706, values: { ...copy.values, behaviorKind: 2 } },
    tired: { ...copy, stableId: 8707, values: { ...copy.values, behaviorKind: 10 } },
  },
  policyDefaults: { spawnPolicyId: 16385, populationPolicyId: 16641, hookSetId: 16897 },
  controllerTemplate: {
    scalarDefaults: { alertState: 1, stamina: 24, restTime: 32 },
    policyIds: { spawnPolicyId: 16385, populationPolicyId: 16641, hookSetId: 16897 },
  },
  spawnPolicyTemplate: {
    provenanceId: 36865, spawnState: 3, destination: 0,
    minimumDistance: 1, maximumDistance: 5, spawnHopTime: 4, flags: 0,
  },
  populationPolicyTemplate: {
    populationGroupId: 17665, provenanceId: 36865, limit: 0, flags: 0,
  },
  hookSetTemplate: {
    helpCallInvocation: 0, pickupThrowEntry: 0, pickupThrowActiveLoop: 0, flags: 0,
  },
  awarenessOwnerId: 33026,
  exhaustionOwnerId: 33029,
  triggerIds: [1, 2, 3],
  existingTransitions: [1, 2, 3].map((event, index) => ({
    stableId: 40000 + index, trigger: event, fromRoleMask: 0x7F,
    dispatchPriority: 8192, controllerIds: [12289],
    candidateDefinition: { controllerId: null },
  })),
  transitionOrderStart: 20,
  stateName: "Bird behavior",
  controllerName: "Bird behavior controller",
  assignment: { kind: "species", species: 25, dispatchPriority: 7 },
});
assert.equal(behaviorSetDraft.profiles.length, 3);
assert.deepEqual(behaviorSetDraft.profiles.map((profile) => profile.values.behaviorKind), [1, 2, 10]);
assert.deepEqual(behaviorSetDraft.profiles.map((profile) => profile.name), [
  "Bird behavior · Calm", "Bird behavior · Active", "Bird behavior · Tired",
]);
assert.equal(new Set(behaviorSetDraft.profiles.map((profile) => profile.draftId)).size, 3);
assert.deepEqual(behaviorSetDraft.controller.nodes.map((node) => node.semanticRoleId), [1, 2, 3]);
assert.deepEqual(behaviorSetDraft.controller.scalarDefaults, { alertState: 1, stamina: 24, restTime: 32 });
assert.deepEqual(behaviorSetDraft.transitions.map((transition) => transition.dispatchPriority), [8193, 8193, 8193]);
assert.equal(behaviorSetDraft.priorityAllocationError, "");
assert.deepEqual(
  behaviorSetDraft.controller.nodes.map((node) => node.profileRef),
  behaviorSetDraft.profiles.map((profile) => profile.draftId),
);
assert.equal(behaviorSetDraft.transitions.length, 3);
assert.deepEqual(behaviorSetDraft.transitions.map((transition) => transition.order), [20, 21, 22]);
assert.equal(new Set(behaviorSetDraft.transitions.map((transition) => transition.candidateDefinitionId)).size, 2);
assert.equal(
  behaviorSetDraft.transitions[1].candidateDefinition.recoveryTransitionId,
  behaviorSetDraft.transitions[2].draftId,
);
assert.deepEqual([
  behaviorSetDraft.transitions[1].candidateDefinition.hasRequiredOwnerId,
  behaviorSetDraft.transitions[1].candidateDefinition.requiredOwnerId,
  behaviorSetDraft.transitions[1].candidateDefinition.hasTiredOriginKind,
  behaviorSetDraft.transitions[1].candidateDefinition.tiredOriginKind,
], [0, null, 0, 0]);
assert.match(behaviorSetDraft.spawnPolicy.draftId, /^draft:/);
assert.match(behaviorSetDraft.populationPolicy.draftId, /^draft:/);
assert.deepEqual(
  [behaviorSetDraft.assignment.kind, behaviorSetDraft.assignment.species, behaviorSetDraft.assignment.controllerIndex],
  ["species", 25, behaviorSetDraft.assignmentAction.draftId],
);
assert.deepEqual(behaviorSetDraft.assignmentAction.payload, { controllerRef: behaviorSetDraft.controller.draftId });
assert.equal(behaviorSetDraft.controller.policyIds.hookSetId, behaviorSetDraft.hookSet.draftId);
const controllerSource = {
  stableId: 12289,
  name: "Bird controller",
  nodes: [{ stableId: 12545, semanticRoleId: 1, profileStableId: 8705, base: true }],
  scalarDefaults: { alertState: 3, stamina: 24, restTime: 32 },
  policyIds: { spawnPolicyId: 16385, populationPolicyId: 16641, hookSetId: 16897 },
  transitionIds: [40961, 40962],
};
const transitionSource = {
  stableId: 40961,
  order: 0,
  controllerIds: [12289],
  candidateDefinition: {
    stableId: 28673, controllerId: 12289, nodeId: 12545, applicabilityId: 61697,
    kind: 1, channel: 1, priority: 200,
    selectorKind: 1, semanticRoleId: 0,
    hasTiredOriginKind: 0, tiredOriginKind: 0,
    hasRequiredOwnerId: 0, requiredOwnerId: 0,
    authoredTiredBound: 0,
    applicability: { stableId: 61697, name: "Controller scope", flags: 2, immutableContextMask: 0xFFFFFFFF, controllerId: 12289, effectiveProfileId: null, semanticRoleId: null },
  },
  candidateDefinitionId: 28673,
  ownerId: 33026,
  trigger: 1,
  fromRoleMask: 1,
  dispatchPriority: 8192,
  guards: [{ stableId: 45057, kind: 3, referenceId: 12545 }],
  operations: [], actions: [], recoveryActions: [],
};
const sharedTransitionSource = {
  ...structuredClone(transitionSource),
  stableId: 40962,
  order: 1,
  dispatchPriority: 8191,
  controllerIds: [12289],
  candidateDefinitionId: 28674,
  candidateDefinition: {
    ...structuredClone(transitionSource.candidateDefinition),
    stableId: 28674, controllerId: null, nodeId: null, applicabilityId: 61698,
    applicability: { stableId: 61698, name: "Global scope", controllerId: null },
  },
  guards: [{ stableId: 45058, kind: 1, referenceId: null }],
};
const secondScopedTransitionSource = {
  ...structuredClone(transitionSource), stableId: 40963, order: 2,
};
const generatedTransitionSource = {
  ...structuredClone(transitionSource), stableId: 40964, order: 2,
  dispatchPriority: 8190, ownerId: 33025,
  candidateDefinitionId: 28675,
  candidateDefinition: {
    ...structuredClone(transitionSource.candidateDefinition),
    stableId: 28675, applicabilityId: 61699, hasRequiredOwnerId: 1,
    requiredOwnerId: 33025, flags: 1,
    applicability: { stableId: 61699, name: "Generated controller scope", controllerId: 12289 },
  },
  guards: [{ stableId: 45060, kind: 1, negate: false, payload: 0, referenceId: null }],
  operations: [{
    stableId: 45061, definitionId: 28675, ownerId: 33025,
    replacementDefinitionId: null, policyId: null, instanceKey: 28675,
    kind: 1, busyPolicy: 1, required: false,
  }],
  actions: [], recoveryActions: [],
};
controllerModel.transitionGraph.transitions = [transitionSource, sharedTransitionSource];
controllerModel.behaviorModelAuthoring = { applicability: [
  { stableId: 61697, kind: 1, groupMask: 0xFFFFFFFF, controllerId: 12289, profileId: 0, minimum: 0, maximum: 0, flags: 2 },
  { stableId: 61698, kind: 1, groupMask: 0xFFFFFFFF, controllerId: null, profileId: 0, minimum: 0, maximum: 0, flags: 0 },
  { stableId: 61699, kind: 3, groupMask: 0xFFFFFFFF, controllerId: 12289, profileId: 0, minimum: 0, maximum: 0, flags: 0 },
], profileDeleteBlockers: { 8705: [{ domain: "importRecipes", stableId: 60001 }] } };
const reordered = [structuredClone(transitionSource), structuredClone(sharedTransitionSource)];
[reordered[0].order, reordered[1].order] = [reordered[1].order, reordered[0].order];
const reorderPayload = compactBehaviorModelDraft({ transitions: { update: reordered } }, {
  ...controllerModel, controllers: [controllerSource], transitionGraph: { ...controllerModel.transitionGraph, transitions: [transitionSource, sharedTransitionSource] },
});
assert.equal(behaviorModelChangeCount(reorderPayload), 2);
assert.deepEqual(reorderPayload.transitions.update.map((item) => item.order), [1, 0]);
const controllerCopy = createControllerDraft({
  source: controllerSource,
  profiles: controllerModel.stateProfiles,
  transitions: [transitionSource, secondScopedTransitionSource],
  transitionOrderStart: 20,
  behaviorModelAuthoring: controllerModel.behaviorModelAuthoring,
});
assert.match(controllerCopy.controller.draftId, /^draft:/);
assert.match(controllerCopy.controller.nodes[0].draftId, /^draft:/);
assert.equal(controllerCopy.controller.nodes[0].stableId, null);
assert.equal(controllerCopy.controller.nodes[0].base, true);
assert.match(controllerCopy.transitions[0].draftId, /^draft:/);
assert.equal(controllerCopy.transitions[0].candidateDefinition.nodeId, controllerCopy.controller.nodes[0].draftId);
assert.equal(controllerCopy.transitions[0].candidateDefinition.stableId, null);
assert.match(controllerCopy.transitions[0].candidateDefinition.draftId, /^draft:/);
assert.match(controllerCopy.transitions[0].candidateDefinition.applicability.draftId, /^draft:/);
assert.equal(controllerCopy.transitions[0].candidateDefinition.applicabilityId, controllerCopy.transitions[0].candidateDefinition.applicability.draftId);
assert.equal(controllerCopy.transitions[0].candidateDefinition.applicability.controllerId, controllerCopy.controller.draftId);
assert.deepEqual(
  Object.fromEntries(["kind", "groupMask", "profileId", "minimum", "maximum"].map((key) => [key, controllerCopy.transitions[0].candidateDefinition.applicability[key]])),
  { kind: 1, groupMask: 0xFFFFFFFF, profileId: 0, minimum: 0, maximum: 0 },
);
assert.equal(controllerCopy.transitions[1].candidateDefinition.applicability.draftId, controllerCopy.transitions[0].candidateDefinition.applicability.draftId);
assert.equal(transitionSource.candidateDefinition.applicability.stableId, 61697);
assert.equal(transitionSource.candidateDefinition.applicability.controllerId, 12289);
assert.equal("kind" in transitionSource.candidateDefinition.applicability, false);
assert.deepEqual(controllerCopy.transitions.map((item) => item.order), [20, 21]);
assert.equal(controllerCopy.transitions[0].candidateDefinitionId, controllerCopy.transitions[0].candidateDefinition.draftId);
assert.deepEqual(controllerCopy.transitions[0].controllerIds, [controllerCopy.controller.draftId]);
assert.equal(controllerCopy.transitions[0].guards[0].referenceId, controllerCopy.controller.nodes[0].draftId);
assert.deepEqual(validateControllerDraft(controllerCopy.controller, controllerModel, controllerCopy.transitions), []);
const generatedClone = createControllerDraft({
  source: controllerSource,
  profiles: controllerModel.stateProfiles,
  transitions: [{
    ...structuredClone(transitionSource),
    candidateDefinition: {
      ...structuredClone(transitionSource.candidateDefinition),
      hasRequiredOwnerId: 1, requiredOwnerId: 33029,
    },
  }],
});
assert.equal(generatedClone.transitions.length, 0);
assert.equal(generatedClone.omittedGeneratedTransitionCount, 1);
const unsupportedClone = createControllerDraft({
  source: controllerSource,
  profiles: controllerModel.stateProfiles,
  transitions: [{
    ...structuredClone(transitionSource),
    candidateDefinition: { ...structuredClone(transitionSource.candidateDefinition), kind: 2 },
  }],
});
assert.equal(unsupportedClone.transitions.length, 0);
assert.equal(unsupportedClone.omittedGeneratedTransitionCount, 1);
controllerCopy.controller.nodes.push({
  draftId: "draft:duplicate", semanticRoleId: 1, profileStableId: 8705, base: false,
});
assert.match(validateControllerDraft(controllerCopy.controller, controllerModel, controllerCopy.transitions).at(-1).message, /unique/i);
controllerCopy.controller.nodes[1].semanticRoleId = 2;
controllerCopy.controller.nodes[1].base = true;
assert.match(validateControllerDraft(controllerCopy.controller, controllerModel, controllerCopy.transitions)[0].message, /Exactly one/i);
controllerCopy.controller.nodes[1].base = false;
controllerCopy.controller.nodes.push({
  draftId: "draft:custom-a", semanticRoleId: 7, customRoleId: 37377,
  profileStableId: 8705, base: false,
});
controllerModel.customRoles.push({ stableId: 37378, name: "Custom role 2" });
controllerCopy.controller.nodes.push({
  draftId: "draft:custom-b", semanticRoleId: 7, customRoleId: 37378,
  profileStableId: 8705, base: false,
});
assert.equal(validateControllerDraft(controllerCopy.controller, controllerModel, controllerCopy.transitions).some((error) => /Custom-role selectors/.test(error.message)), false);
controllerCopy.controller.nodes.at(-1).customRoleId = 37377;
assert.equal(validateControllerDraft(controllerCopy.controller, controllerModel, controllerCopy.transitions).some((error) => /Custom-role selectors/.test(error.message)), true);
console.log("V40 controller draft and invariant checks passed");

const mixedCapability = v40ProfileDeckCapability({
  profilesAvailable: false,
  capabilities: { profiles: { available: false, reason: "Legacy V39 table is absent" } },
  v40BehaviorModelCapability: { available: true, modelVersion: 40, stateProfileCount: 58 },
});
assert.deepEqual(mixedCapability, { available: true, reason: "" });
assert.deepEqual(
  v40ProfileDeckCapability({
    v40BehaviorModelCapability: { available: false, reason: "V40 catalog missing" },
  }),
  { available: false, reason: "V40 catalog missing" },
);
console.log("V40 Profile Deck capability override checks passed");

class FakeElement {
  constructor() {
    this.innerHTML = "";
    this.hidden = false;
    this.value = "";
    this.dataset = {};
    this.listeners = new Map();
    this.classList = { add() {}, remove() {} };
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  removeEventListener(type) {
    this.listeners.delete(type);
  }

  querySelector() {
    return null;
  }

  dispatch(type, target) {
    this.listeners.get(type)?.({ target });
  }
}

globalThis.Element = FakeElement;
globalThis.requestAnimationFrame = (callback) => callback();

const root = new FakeElement();
const profileSearch = new FakeElement();
const profileKindFilter = new FakeElement();
const inspector = new FakeElement();
const state = {};
let shellMarkDirtyCalls = 0;
const statuses = [];
const controller = createProfilesController({
  state,
  api: {
    get: async () => ({
      modelVersion: 40,
      stateProfiles: [{
        stableId: 8705,
        bodyId: 4609,
        name: "Bird calm",
        descriptiveTags: ["bird"],
        registryKey: "authored-profile:class-0:chill",
        provenanceId: 36865,
        bodyProvenance: { kind: 1, label: "Calm" },
        values: { behaviorKind: 1, hopMinDistance: 0, hopMaxDistance: 0 },
        backlinks: [],
      }, {
        stableId: 8707,
        bodyId: 4611,
        name: "Bird active",
        descriptiveTags: ["bird", "active"],
        registryKey: "authored-profile:class-0:active",
        provenanceId: 36865,
        bodyProvenance: { kind: 1, label: "Active" },
        values: { behaviorKind: 2, hopMinDistance: 0, hopMaxDistance: 0 },
        backlinks: [],
      }, {
        stableId: 8708,
        bodyId: 4612,
        name: "Bird tired",
        descriptiveTags: ["bird", "tired"],
        registryKey: "authored-profile:class-0:tired",
        provenanceId: 36865,
        bodyProvenance: { kind: 1, label: "Tired" },
        values: { behaviorKind: 10, hopMinDistance: 0, hopMaxDistance: 0 },
        backlinks: [],
      }, {
        stableId: 8706,
        bodyId: 4610,
        name: "Unused state",
        descriptiveTags: [],
        registryKey: "authored-profile:unused",
        provenanceId: 36865,
        bodyProvenance: { kind: 1, label: "Calm" },
        values: { behaviorKind: 1, hopMinDistance: 0, hopMaxDistance: 0 },
        backlinks: [],
      }],
      stateProfileFields: fields,
      groups: [
        { key: "behavior", label: "Behavior" },
        { key: "hop", label: "Hop" },
      ],
      controllers: [{
        ...controllerSource,
        transitionIds: [40961, 40962, 40964],
        nodes: [
          ...controllerSource.nodes,
          { stableId: 12546, semanticRoleId: 2, profileStableId: 8707, base: false },
          { stableId: 12547, semanticRoleId: 3, profileStableId: 8708, base: false },
        ],
      }],
      owners: [{ stableId: 33025, name: "Owner 0" }],
      overrideDefinitions: [transitionSource.candidateDefinition, sharedTransitionSource.candidateDefinition, generatedTransitionSource.candidateDefinition],
      applicability: [{
        stableId: 61697, flags: 3, immutableContextMask: 0xFFFFFFFF,
        controllerId: 12289, effectiveProfileId: null, semanticRoleId: null,
      }, {
        stableId: 61698, flags: 1, immutableContextMask: 0xFFFFFFFF,
        controllerId: null, effectiveProfileId: null, semanticRoleId: null,
      }, {
        stableId: 61699, flags: 3, immutableContextMask: 0xFFFFFFFF,
        controllerId: 12289, effectiveProfileId: null, semanticRoleId: null,
      }],
      stackPreview: { capacity: 8 },
      controllerScalarFields: controllerModel.controllerScalarFields,
      semanticRoles: controllerModel.semanticRoles,
      customRoles: controllerModel.customRoles,
      policyCatalog: controllerModel.policyCatalog,
      assignmentActions: [{
        stableId: 21505, kind: 1, flags: 0,
        payload: [1, 48, 0, 0, 0, 0, 0, 0],
      }],
      genericAssignments: [{
        stableId: 21249, controllerIndex: 0, dispatchPriority: 10,
        match: { groupMask: 1, species: 0, terrain: 255, minimumLevel: 0, maximumLevel: 0, shiny: 255, behaviorClass: 255 },
      }],
      speciesAssignments: [{ stableId: 21250, species: 25, controllerIndex: 0, dispatchPriority: 11 }],
      transitionGraph: {
        transitions: [transitionSource, sharedTransitionSource, generatedTransitionSource],
        triggerOptions: controllerModel.transitionGraph.triggerOptions,
      },
      behaviorModelAuthoring: controllerModel.behaviorModelAuthoring,
    }),
  },
  setStatus: (message, kind) => { statuses.push({ message, kind }); },
  elements: {
    profilesView: root,
    profileLibrary: new FakeElement(),
    profileInspector: inspector,
    profileKindFilter,
    openProfileResolver: new FakeElement(),
    profileResolverDrawer: new FakeElement(),
    profileSearch,
  },
  markDirty: () => { shellMarkDirtyCalls += 1; },
});

await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(state.v40BehaviorModel.stateProfiles.length, 4);

const actionTarget = (action) => ({
  closest(selector) {
    if (selector === "[data-profile-action]") return action ? { dataset: { profileAction: action } } : null;
    if (selector === "[data-action='new-profile']") return action === "new" ? {} : null;
    return null;
  },
});
root.dispatch("click", actionTarget("new"));
root.dispatch("input", {
  value: "Bird relaxed",
  dataset: { stateIdentity: "name" },
  matches: (selector) => selector === "[data-state-identity]",
});

assert.equal(controller.hasChanges(), true);
assert.equal(controller.changeCount(), 1);
assert.equal(shellMarkDirtyCalls, 2);
assert.equal(controller.commitPayload().behaviorModel.stateProfiles.create.length, 1);
assert.equal(state.profileDirty, true);
assert.equal(state.v40BehaviorModelDraft.stateProfiles.create.length, 1);
assert.equal(state.v40BehaviorModelDraft.stateProfiles.create[0].name, "Bird relaxed");

root.dispatch("click", actionTarget("delete"));
assert.equal(state.v40BehaviorModelDraft.stateProfiles.create.length, 0);
assert.deepEqual(controller.commitPayload(), {});
root.dispatch("click", actionTarget("new"));

root.dispatch("click", actionTarget("reset-local"));
assert.equal(state.v40BehaviorModelDraft.stateProfiles.create.length, 0);
assert.equal(state.v40BehaviorModelDraft.stateProfiles.update.length, 0);
assert.equal(shellMarkDirtyCalls, 5);
assert.deepEqual(controller.commitPayload(), {});

root.dispatch("click", actionTarget("delete"));
assert.deepEqual(state.v40BehaviorModelDraft.stateProfiles.remove, []);
assert.match(statuses.at(-1).message, /controller node/);
root.dispatch("click", {
  closest(selector) {
    return selector === "[data-profile-id]" ? { dataset: { profileId: "state:8706" } } : null;
  },
});
root.dispatch("click", actionTarget("delete"));
assert.deepEqual(state.v40BehaviorModelDraft.stateProfiles.remove, [8706]);
root.dispatch("click", actionTarget("reset-local"));
assert.deepEqual(state.v40BehaviorModelDraft.stateProfiles.remove, []);

const behaviorSetActionTarget = (behaviorSetAction) => ({
  closest(selector) {
    return selector === "[data-behavior-set-action]" ? { dataset: { behaviorSetAction } } : null;
  },
});
const behaviorSetInput = (field, value) => root.dispatch("input", {
  value,
  dataset: { behaviorSetField: field },
  matches: (selector) => selector === "[data-behavior-set-field]",
});
root.dispatch("click", behaviorSetActionTarget("open"));
assert.match(inspector.innerHTML, /Calm complete state/);
assert.match(inspector.innerHTML, /Active · Tired/);
assert.match(inspector.innerHTML, /Awareness · Exhaustion · Recovery/);
assert.match(inspector.innerHTML, /No assignment will be created/);
behaviorSetInput("assignmentKind", "species");
assert.match(inspector.innerHTML, /Assignment priority must be explicitly set/);
behaviorSetInput("assignmentPriority", "7");
behaviorSetInput("species", "25");
assert.match(inspector.innerHTML, /already has an explicit controller assignment/);
behaviorSetInput("species", "26");
root.dispatch("click", behaviorSetActionTarget("confirm"));
assert.equal(state.v40BehaviorModelDraft.stateProfiles.create.length, 3);
assert.equal(state.v40BehaviorModelDraft.controllers.create.length, 1);
assert.equal(state.v40BehaviorModelDraft.controllers.create[0].nodes.length, 3);
assert.equal(state.v40BehaviorModelDraft.transitions.create.length, 3);
assert.equal(state.v40BehaviorModelDraft.spawnPolicies.create.length, 1);
assert.equal(state.v40BehaviorModelDraft.populationPolicies.create.length, 1);
assert.equal(state.v40BehaviorModelDraft.hookSets.create.length, 1);
assert.equal(state.v40BehaviorModelDraft.assignmentActions.create.length, 1);
assert.equal(state.v40BehaviorModelDraft.speciesAssignments.create.length, 1);
assert.equal(state.v40BehaviorModelDraft.genericAssignments.create.length, 0);
const completeSetPayload = controller.commitPayload().behaviorModel;
assert.deepEqual(completeSetPayload.controllers.create[0].scalarDefaults, { alertState: 3, stamina: 24, restTime: 32 });
assert.equal(completeSetPayload.spawnPolicies.create[0].spawnState, 3);
assert.equal(completeSetPayload.populationPolicies.create[0].populationGroupId, 17665);
assert.equal(completeSetPayload.hookSets.create[0].helpCallInvocation, 0);
assert.equal(completeSetPayload.transitions.update, undefined);
assert.equal(behaviorModelChangeCount(completeSetPayload), 12);
assert.equal(completeSetPayload.speciesAssignments.create[0].controllerIndex, completeSetPayload.assignmentActions.create[0].draftId);
assert.deepEqual(completeSetPayload.assignmentActions.create[0].payload, {
  controllerRef: completeSetPayload.controllers.create[0].draftId,
});
assert.equal("controllerId" in completeSetPayload.speciesAssignments.create[0], false);
const tiredPayloadDefinitions = completeSetPayload.transitions.create
  .map((transition) => transition.candidateDefinition)
  .filter((definition) => Number(definition.channel) === 2);
assert.equal(tiredPayloadDefinitions.length, 2);
assert.equal(tiredPayloadDefinitions.every((definition) => Number(definition.hasRequiredOwnerId) === 0
  && definition.requiredOwnerId === null && Number(definition.hasTiredOriginKind) === 0
  && Number(definition.tiredOriginKind) === 0), true);
for (const policyRef of Object.values(completeSetPayload.controllers.create[0].policyIds)) {
  assert.match(inspector.innerHTML, new RegExp(`option value="${policyRef}" selected`));
}
assert.deepEqual(
  controller.wholeGraphDiagnostics().filter((item) => String(item.entityId).startsWith("draft:")),
  [],
);
root.dispatch("click", actionTarget("reset-local"));
assert.deepEqual(controller.commitPayload(), {});

root.dispatch("click", {
  closest(selector) {
    return selector === "[data-profile-deck-mode]" ? { dataset: { profileDeckMode: "controllers" } } : null;
  },
});
assert.equal(state.profileDeckMode, "controllers");
root.dispatch("click", {
  closest(selector) {
    return selector === "[data-controller-id]" ? { dataset: { controllerId: "controller:12289" } } : null;
  },
});
root.dispatch("click", {
  closest(selector) {
    return selector === "[data-transition-action]"
      ? { dataset: { transitionAction: "author", transitionId: "transition:40964" } }
      : null;
  },
});
assert.match(inspector.innerHTML, /Read-only transition row/);
const generatedBefore = structuredClone(state.v40BehaviorModelDraft.transitions);
root.dispatch("input", {
  value: "2", dataset: { transitionId: "transition:40964", transitionField: "trigger" },
  matches: (selector) => selector === "[data-transition-field]",
});
root.dispatch("input", {
  value: "99", dataset: { transitionId: "transition:40964", definitionField: "priority" },
  matches: (selector) => selector === "[data-definition-field]",
});
root.dispatch("input", {
  value: "255", dataset: { transitionId: "transition:40964", applicabilityField: "groupMask" },
  matches: (selector) => selector === "[data-applicability-field]",
});
root.dispatch("input", {
  value: "2", dataset: { transitionId: "transition:40964", childKind: "guards", childId: "guard:45060", childField: "kind" },
  matches: (selector) => selector === "[data-child-field]",
});
root.dispatch("click", {
  closest(selector) {
    return selector === "[data-transition-action]"
      ? { dataset: { transitionAction: "remove", transitionId: "transition:40964" } }
      : null;
  },
});
assert.deepEqual(state.v40BehaviorModelDraft.transitions, generatedBefore);
assert.match(statuses.at(-1).message, /wholly read-only/);
root.dispatch("click", {
  closest(selector) {
    return selector === "[data-transition-action]"
      ? { dataset: { transitionAction: "down", transitionId: "transition:40962" } }
      : null;
  },
});
assert.deepEqual(state.v40BehaviorModelDraft.transitions, generatedBefore);
root.dispatch("click", {
  closest(selector) {
    return selector === "[data-transition-action]"
      ? { dataset: { transitionAction: "remove", transitionId: "transition:40961" } }
      : null;
  },
});
assert.deepEqual(state.v40BehaviorModelDraft.transitions.remove, [40961]);
assert.equal(state.v40BehaviorModelDraft.transitions.update.some((item) => item.stableId === 40964), false);
assert.equal(controller.commitPayload().behaviorModel.transitions.update?.some((item) => item.stableId === 40964) || false, false);
root.dispatch("click", actionTarget("reset-local"));
root.dispatch("click", actionTarget("new"));
assert.equal(state.v40BehaviorModelDraft.controllers.create.length, 1);
assert.match(state.v40BehaviorModelDraft.controllers.create[0].draftId, /^draft:/);
assert.equal(state.v40BehaviorModelDraft.controllers.create[0].nodes.filter((node) => node.base).length, 1);
const firstControllerDraftId = state.v40BehaviorModelDraft.controllers.create[0].draftId;
assert.equal(state.v40BehaviorModelDraft.transitions.update.some((transition) => transition.stableId === 40962), false);
root.dispatch("input", {
  value: "Bird controller draft",
  dataset: { controllerIdentity: "name" },
  matches: (selector) => selector === "[data-controller-identity]",
});
assert.equal(state.v40BehaviorModelDraft.controllers.create[0].name, "Bird controller draft");
const controllerActionTarget = (controllerAction) => ({
  closest(selector) {
    if (selector === "[data-controller-action]") return { dataset: { controllerAction } };
    return null;
  },
});
root.dispatch("click", controllerActionTarget("add-node"));
assert.equal(state.v40BehaviorModelDraft.controllers.create[0].nodes.length, 2);
assert.deepEqual(state.v40BehaviorModelDraft.controllers.create[0].nodes.map((node) => node.semanticRoleId), [1, 2]);
const changeNodeRole = (nodeId) => root.dispatch("change", {
  value: "7",
  dataset: { nodeId, nodeField: "semanticRoleId" },
  matches: (selector) => selector === "[data-node-field]",
});
changeNodeRole(state.v40BehaviorModelDraft.controllers.create[0].nodes[1].draftId);
root.dispatch("click", controllerActionTarget("add-node"));
changeNodeRole(state.v40BehaviorModelDraft.controllers.create[0].nodes[2].draftId);
assert.deepEqual(
  state.v40BehaviorModelDraft.controllers.create[0].nodes.slice(1).map((node) => [node.semanticRoleId, node.customRoleId]),
  [[7, 37377], [7, 37378]],
);
root.dispatch("click", {
  closest(selector) {
    return selector === "[data-transition-action]"
      ? { dataset: { transitionAction: "remove", transitionId: "transition:40962" } }
      : null;
  },
});
assert.deepEqual(state.v40BehaviorModelDraft.transitions.remove, [40962]);
assert.equal(state.v40BehaviorModelDraft.transitions.update.some((transition) => transition.stableId === 40962), false);
root.dispatch("click", controllerActionTarget("add-transition"));
assert.equal(state.v40BehaviorModelDraft.transitions.create.length, 1);
assert.match(state.v40BehaviorModelDraft.transitions.create[0].draftId, /^draft:/);
const createdTransitionId = state.v40BehaviorModelDraft.transitions.create[0].draftId;
assert.deepEqual([
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.selectorKind,
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.flags,
], [1, 0]);
const definitionInput = (field, value, checked = false) => root.dispatch("input", {
  value, checked,
  dataset: { transitionId: createdTransitionId, definitionField: field },
  matches: (selector) => selector === "[data-definition-field]",
});
const applicabilityInput = (field, value) => root.dispatch("input", {
  value,
  dataset: { transitionId: createdTransitionId, applicabilityField: field },
  matches: (selector) => selector === "[data-applicability-field]",
});
for (const [field, value, checked] of [
  ["name", "Authored candidate"], ["channel", "3"], ["priority", "255"], ["controllerId", firstControllerDraftId],
  ["selectorKind", "2"], ["semanticRoleId", "2"], ["selectorKind", "1"],
  ["nodeId", state.v40BehaviorModelDraft.controllers.create[0].nodes[0].draftId],
  ["mapLifetime", "1"], ["battleLifetime", "2"],
  ["timerClock", "1"], ["timerSource", "2"], ["timerValue", "5"],
  ["hiddenTimerPolicy", "2"], ["recoveryPolicy", "1"],
  ["recoveryTransitionId", createdTransitionId], ["recoveryPolicy", "0"],
  ["allowMultipleOwners", "on", true], ["allowMultipleInstancesPerOwner", "on", true],
]) definitionInput(field, value, checked);
definitionInput("kind", "2");
assert.equal(state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.kind, 1);
assert.match(statuses.at(-1).message, /Modifier/);
definitionInput("channel", "5");
assert.equal(state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.channel, 3);
assert.match(statuses.at(-1).message, /System Safety/);
definitionInput("priority", "256");
assert.equal(state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.priority, 255);
assert.match(statuses.at(-1).message, /0–255/);
definitionInput("requiredOwnerId", "33026");
definitionInput("tiredOriginKind", "2");
definitionInput("hasTiredOriginKind", "on", true);
definitionInput("authoredTiredBound", "on", true);
assert.deepEqual([
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.requiredOwnerId,
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.hasTiredOriginKind,
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.tiredOriginKind,
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.authoredTiredBound,
], [0, 0, 0, 0]);
assert.match(statuses.at(-1).message, /read-only/);
definitionInput("selectorKind", "2");
assert.deepEqual([
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.nodeId,
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.flags,
], [null, 0]);
definitionInput("selectorKind", "1");
assert.deepEqual([
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.semanticRoleId,
  state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.flags,
], [0, 0]);
for (const [field, value] of [
  ["name", "Authored applicability"], ["kind", "3"], ["groupMask", "255"],
  ["controllerId", firstControllerDraftId], ["profileId", "8705"],
  ["minimum", "0"], ["maximum", "8"], ["flags", "9"],
]) applicabilityInput(field, value);
const childActionTarget = (kind) => ({
  closest(selector) {
    return selector === "[data-child-action]" ? {
      dataset: { childAction: "add", childKind: kind, transitionId: createdTransitionId },
    } : null;
  },
});
for (const kind of ["guards", "operations", "actions", "recoveryActions"]) root.dispatch("click", childActionTarget(kind));
const authoredTransition = state.v40BehaviorModelDraft.transitions.create[0];
const childInput = (kind, child, field, value, checked = false) => root.dispatch("input", {
  value, checked,
  dataset: {
    transitionId: createdTransitionId, childKind: kind,
    childId: child.draftId, childField: field,
  },
  matches: (selector) => selector === "[data-child-field]",
});
const authoredGuard = authoredTransition.guards.at(-1);
for (const [field, value, checked] of [
  ["kind", "3"], ["negate", "on", true], ["payload", "2"],
  ["referenceId", state.v40BehaviorModelDraft.controllers.create[0].nodes[0].draftId],
]) childInput("guards", authoredGuard, field, value, checked);
const authoredOperation = authoredTransition.operations.at(-1);
for (const [field, value, checked] of [
  ["kind", "2"], ["definitionId", authoredTransition.candidateDefinitionId],
  ["ownerId", "33026"], ["replacementDefinitionId", "28673"],
  ["policyId", "1"], ["instanceKey", authoredTransition.candidateDefinitionId],
  ["busyPolicy", "2"], ["required", "on", true], ["required", "on", false],
  ["kind", "1"],
]) childInput("operations", authoredOperation, field, value, checked);
const authoredAction = authoredTransition.actions.at(-1);
childInput("actions", authoredAction, "phase", "2");
childInput("actions", authoredAction, "kind", "4");
const authoredRecovery = authoredTransition.recoveryActions.at(-1);
childInput("recoveryActions", authoredRecovery, "ownerId", "33026");
childInput("recoveryActions", authoredRecovery, "kind", "2");
childInput("recoveryActions", authoredRecovery, "required", "on", false);
childInput("recoveryActions", authoredRecovery, "required", "on", true);
assert.equal(authoredTransition.candidateDefinition.channel, 3);
assert.equal(authoredTransition.candidateDefinition.priority, 255);
assert.deepEqual(
  [authoredTransition.candidateDefinition.timerClock, authoredTransition.candidateDefinition.timerSource,
    authoredTransition.candidateDefinition.timerValue, authoredTransition.candidateDefinition.hiddenTimerPolicy],
  [1, 2, 5, 2],
);
assert.equal(authoredTransition.candidateDefinition.allowMultipleOwners, 1);
assert.equal(authoredTransition.candidateDefinition.flags, 0);
assert.deepEqual([authoredTransition.candidateDefinition.hasTiredOriginKind, authoredTransition.candidateDefinition.tiredOriginKind], [0, 0]);
assert.equal(authoredTransition.candidateDefinition.applicability.groupMask, 255);
assert.deepEqual(["guards", "operations", "actions", "recoveryActions"].map((kind) => authoredTransition[kind].at(-1).draftId.startsWith("draft:")), [true, true, true, true]);
const authoredIds = [authoredTransition.draftId, authoredTransition.candidateDefinition.draftId,
  authoredTransition.candidateDefinition.applicability.draftId,
  ...["guards", "operations", "actions", "recoveryActions"].flatMap((kind) => authoredTransition[kind].map((item) => item.draftId))];
assert.equal(new Set(authoredIds).size, authoredIds.length);
assert.equal(authoredIds.every((id) => id?.startsWith("draft:")), true);
const authoredPayload = controller.commitPayload().behaviorModel.transitions.create
  .find((item) => item.draftId === createdTransitionId);
assert.equal(authoredPayload.candidateDefinition.channel, 3);
assert.equal(authoredPayload.candidateDefinition.applicability.groupMask, 255);
assert.equal(authoredPayload.recoveryActions.at(-1).kind, 2);
definitionInput("selectorKind", "2");
definitionInput("nodeId", state.v40BehaviorModelDraft.controllers.create[0].nodes[0].draftId);
assert.equal(controller.wholeGraphDiagnostics().some((item) => item.code === "DEFINITION_SELECTOR_INVALID"), true);
assert.equal(controller.hasInvalid(), true);
definitionInput("selectorKind", "1");
root.dispatch("click", controllerActionTarget("duplicate"));
assert.equal(state.v40BehaviorModelDraft.controllers.create.length, 2);
assert.notEqual(
  state.v40BehaviorModelDraft.controllers.create[0].nodes[0].draftId,
  state.v40BehaviorModelDraft.controllers.create[1].nodes[0].draftId,
);
const callsBeforeRefresh = shellMarkDirtyCalls;
assert.equal(controller.hasInvalid(), true);
assert.ok(controller.commitPayload().behaviorModel);

const preservedControllerDraftId = controller.navigationContext().selection;
const preservedPayload = structuredClone(controller.commitPayload());
assert.equal(controller.hasChanges(), true);
assert.equal(state.v40BehaviorModelDraft.controllers.create.some((item) => item.draftId === preservedControllerDraftId), true);
assert.deepEqual(controller.commitPayload(), preservedPayload);
await controller.refreshPreservingDrafts();
assert.equal(state.v40BehaviorModelDraft.controllers.create.some((item) => item.draftId === preservedControllerDraftId), true);
assert.deepEqual(controller.commitPayload(), preservedPayload);
assert.equal(shellMarkDirtyCalls, callsBeforeRefresh);

controller.clearCommitted({
  domains: { behaviorModel: { draftIdMap: { [preservedControllerDraftId]: 62001 } } },
});
assert.equal(controller.hasChanges(), false);
assert.deepEqual(controller.commitPayload(), {});
assert.equal(controller.navigationContext().selection, "controller:62001");
assert.equal(shellMarkDirtyCalls, callsBeforeRefresh + 1);

root.dispatch("click", {
  closest(selector) {
    return selector === "[data-controller-id]" ? { dataset: { controllerId: "controller:12289" } } : null;
  },
});
root.dispatch("click", controllerActionTarget("delete"));
assert.deepEqual(state.v40BehaviorModelDraft.controllers.remove, []);
assert.match(inspector.innerHTML, /No draft changes have been made yet/);
assert.match(inspector.innerHTML, /explicitly removes 2 assignment backlinks/);
root.dispatch("click", {
  closest(selector) {
    return selector === "[data-controller-delete-action]"
      ? { dataset: { controllerDeleteAction: "confirm" } }
      : null;
  },
});
assert.deepEqual(state.v40BehaviorModelDraft.controllers.remove, [12289]);
assert.deepEqual(state.v40BehaviorModelDraft.genericAssignments.remove, [21249]);
assert.deepEqual(state.v40BehaviorModelDraft.speciesAssignments.remove, [21250]);
assert.deepEqual(state.v40BehaviorModelDraft.assignmentActions.remove, [21505]);
assert.equal(state.v40BehaviorModelDraft.transitions.remove.includes(40961), true);

// Duplicate checks use the materialized transaction, so removing a saved
// species assignment and replacing it atomically is valid.
root.dispatch("click", behaviorSetActionTarget("open"));
behaviorSetInput("assignmentKind", "species");
behaviorSetInput("assignmentPriority", "7");
behaviorSetInput("species", "25");
assert.doesNotMatch(inspector.innerHTML, /already has an explicit controller assignment/);
root.dispatch("click", behaviorSetActionTarget("confirm"));
assert.equal(state.v40BehaviorModelDraft.speciesAssignments.create.at(-1).species, 25);
assert.deepEqual(state.v40BehaviorModelDraft.speciesAssignments.remove, [21250]);

controller.destroy();
console.log("V40 local-draft shell integration checks passed");
