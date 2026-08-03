import assert from "node:assert/strict";
import {
  createCompleteStateDraft,
  createControllerDraft,
  createProfilesController,
  validateCompleteStateProfile,
  validateControllerDraft,
  v40ProfileDeckCapability,
} from "../static/profiles.js";

const fields = [
  { key: "behaviorKind", label: "Behavior", type: "enum", options: [{ value: 1, label: "Idle" }] },
  { key: "hopMinDistance", label: "Minimum hop distance", type: "number", minimum: 0, maximum: 12 },
  { key: "hopMaxDistance", label: "Maximum hop distance", type: "number", minimum: 0, maximum: 12 },
];

const draft = createCompleteStateDraft(fields, null, "Bird calm");
assert.match(draft.draftId, /^draft:/);
assert.equal(draft.stableId, null);
assert.deepEqual(draft.values, { behaviorKind: 1, hopMinDistance: 0, hopMaxDistance: 0 });
assert.deepEqual(validateCompleteStateProfile(draft, fields), []);

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
    { value: 1, label: "Calm" }, { value: 2, label: "Active" },
    { value: 7, label: "Custom", custom: true },
  ],
  customRoles: [{ stableId: 37377, name: "Custom role 1" }],
  policyCatalog: {
    spawnPolicies: [{ stableId: 16385, name: "Spawn policy" }],
    populationPolicies: [{ stableId: 16641, name: "Population policy" }],
    hookSets: [{ stableId: 16897, name: "Hook set" }],
  },
  controllerScalarFields: [
    { key: "alertState", label: "Alert state", type: "enum", options: [{ value: 0, label: "None" }] },
  ],
  transitionGraph: { triggerOptions: [{ value: 1, label: "Detection" }] },
};
const controllerSource = {
  stableId: 12289,
  name: "Bird controller",
  nodes: [{ stableId: 12545, semanticRoleId: 1, profileStableId: 8705, base: true }],
  scalarDefaults: { alertState: 0 },
  policyIds: { spawnPolicyId: 16385, populationPolicyId: 16641, hookSetId: 16897 },
  transitionIds: [40961, 40962],
};
const transitionSource = {
  stableId: 40961,
  controllerIds: [12289],
  candidateDefinition: { stableId: 28673, controllerId: 12289, nodeId: 12545 },
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
  controllerIds: [12289],
  candidateDefinitionId: 28674,
  candidateDefinition: { stableId: 28674, controllerId: null, nodeId: null },
  guards: [{ stableId: 45058, kind: 1, referenceId: null }],
};
controllerModel.transitionGraph.transitions = [transitionSource, sharedTransitionSource];
const controllerCopy = createControllerDraft({
  source: controllerSource,
  profiles: controllerModel.stateProfiles,
  transitions: [transitionSource],
});
assert.match(controllerCopy.controller.draftId, /^draft:/);
assert.match(controllerCopy.controller.nodes[0].draftId, /^draft:/);
assert.equal(controllerCopy.controller.nodes[0].stableId, null);
assert.equal(controllerCopy.controller.nodes[0].base, true);
assert.match(controllerCopy.transitions[0].draftId, /^draft:/);
assert.equal(controllerCopy.transitions[0].candidateDefinition.nodeId, controllerCopy.controller.nodes[0].draftId);
assert.equal(controllerCopy.transitions[0].candidateDefinition.stableId, null);
assert.match(controllerCopy.transitions[0].candidateDefinition.draftId, /^draft:/);
assert.equal(controllerCopy.transitions[0].candidateDefinitionId, controllerCopy.transitions[0].candidateDefinition.draftId);
assert.deepEqual(controllerCopy.transitions[0].controllerIds, [controllerCopy.controller.draftId]);
assert.equal(controllerCopy.transitions[0].guards[0].referenceId, controllerCopy.controller.nodes[0].draftId);
assert.deepEqual(validateControllerDraft(controllerCopy.controller, controllerModel, controllerCopy.transitions), []);
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
        bodyProvenance: { kind: 1, label: "Calm" },
        values: { behaviorKind: 1, hopMinDistance: 0, hopMaxDistance: 0 },
        backlinks: [],
      }],
      stateProfileFields: fields,
      groups: [
        { key: "behavior", label: "Behavior" },
        { key: "hop", label: "Hop" },
      ],
      controllers: [controllerSource],
      owners: [{ stableId: 33025, name: "Owner 0" }],
      overrideDefinitions: [transitionSource.candidateDefinition],
      applicability: [{ stableId: transitionSource.candidateDefinition.applicabilityId || 61697 }],
      stackPreview: { capacity: 8 },
      controllerScalarFields: controllerModel.controllerScalarFields,
      semanticRoles: controllerModel.semanticRoles,
      customRoles: controllerModel.customRoles,
      policyCatalog: controllerModel.policyCatalog,
      transitionGraph: {
        transitions: [transitionSource, sharedTransitionSource],
        triggerOptions: controllerModel.transitionGraph.triggerOptions,
      },
    }),
  },
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
assert.equal(state.v40BehaviorModel.stateProfiles.length, 1);

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

assert.equal(controller.hasChanges(), false);
assert.equal(controller.changeCount(), 0);
assert.equal(shellMarkDirtyCalls, 0);
assert.deepEqual(controller.commitPayload(), {});
assert.equal(state.profileDirty, false);
assert.equal(state.v40BehaviorModelDraft.stateProfiles.create.length, 1);
assert.equal(state.v40BehaviorModelDraft.stateProfiles.create[0].name, "Bird relaxed");

root.dispatch("click", actionTarget("reset-local"));
assert.equal(state.v40BehaviorModelDraft.stateProfiles.create.length, 0);
assert.equal(state.v40BehaviorModelDraft.stateProfiles.update.length, 0);
assert.equal(shellMarkDirtyCalls, 0);
assert.deepEqual(controller.commitPayload(), {});

root.dispatch("click", {
  closest(selector) {
    return selector === "[data-profile-deck-mode]" ? { dataset: { profileDeckMode: "controllers" } } : null;
  },
});
assert.equal(state.profileDeckMode, "controllers");
root.dispatch("click", actionTarget("new"));
assert.equal(state.v40BehaviorModelDraft.controllers.create.length, 1);
assert.match(state.v40BehaviorModelDraft.controllers.create[0].draftId, /^draft:/);
assert.equal(state.v40BehaviorModelDraft.controllers.create[0].nodes.filter((node) => node.base).length, 1);
const firstControllerDraftId = state.v40BehaviorModelDraft.controllers.create[0].draftId;
const expandedShared = state.v40BehaviorModelDraft.transitions.update.find((transition) => transition.stableId === 40962);
assert.deepEqual(expandedShared.controllerIds, [12289, firstControllerDraftId]);
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
root.dispatch("input", {
  value: "28673",
  dataset: { transitionId: createdTransitionId, transitionField: "candidateDefinitionId" },
  matches: (selector) => selector === "[data-transition-field]",
});
assert.equal(state.v40BehaviorModelDraft.transitions.create[0].candidateDefinitionId, 28673);
assert.equal(state.v40BehaviorModelDraft.transitions.create[0].candidateDefinition.stableId, 28673);
assert.deepEqual(state.v40BehaviorModelDraft.transitions.create[0].controllerIds, [12289]);
root.dispatch("click", controllerActionTarget("duplicate"));
assert.equal(state.v40BehaviorModelDraft.controllers.create.length, 2);
assert.notEqual(
  state.v40BehaviorModelDraft.controllers.create[0].nodes[0].draftId,
  state.v40BehaviorModelDraft.controllers.create[1].nodes[0].draftId,
);
assert.equal(shellMarkDirtyCalls, 0);
assert.deepEqual(controller.commitPayload(), {});

controller.destroy();
console.log("V40 local-draft shell integration checks passed");
