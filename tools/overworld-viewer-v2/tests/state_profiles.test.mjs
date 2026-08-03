import assert from "node:assert/strict";
import {
  createCompleteStateDraft,
  createProfilesController,
  validateCompleteStateProfile,
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

controller.destroy();
console.log("V40 local-draft shell integration checks passed");
