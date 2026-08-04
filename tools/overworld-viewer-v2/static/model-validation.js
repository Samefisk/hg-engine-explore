/* Pure, deterministic OWBD V40 authoring validation. */

const clone = (value) => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const ref = (entity) => entity?.draftId ?? entity?.stableId;
const same = (left, right) => String(left) === String(right);
const present = (value) => value !== null && value !== undefined && value !== "";
const nonzeroRef = (value) => present(value) && Number(value) !== 0;
const asArray = (value) => Array.isArray(value) ? value : [];

export const VALIDATION_CODES = Object.freeze({
  MODEL_VERSION: "MODEL_VERSION_INVALID",
  DRAFT_TRANSACTION: "DRAFT_TRANSACTION_INVALID",
  DRAFT_REFERENCE: "DRAFT_REFERENCE_INVALID",
  REPRESENTATION: "REPRESENTATION_UNSUPPORTED",
  IDENTITY: "IDENTITY_INVALID",
  IDENTITY_DUPLICATE: "IDENTITY_DUPLICATE",
  NAME: "NAME_REQUIRED",
  PROFILE_FIELDS: "PROFILE_FIELD_SET_INVALID",
  PROFILE_ROLE: "PROFILE_ROLE_OWNERSHIP_INVALID",
  FIELD_DOMAIN: "FIELD_DOMAIN_INVALID",
  WIRE_RANGE: "WIRE_RANGE_INVALID",
  BASE_NODE: "CONTROLLER_BASE_INVALID",
  NODE_OWNER: "NODE_OWNER_MISMATCH",
  REFERENCE: "REFERENCE_DANGLING",
  SEMANTIC_ROLE: "SEMANTIC_ROLE_INVALID",
  SELECTOR_DUPLICATE: "SELECTOR_DUPLICATE",
  CONTROLLER_POLICY: "CONTROLLER_POLICY_INVALID",
  TRANSITION_SCOPE: "TRANSITION_SCOPE_INVALID",
  TRANSITION_AMBIGUOUS: "TRANSITION_DISPATCH_AMBIGUOUS",
  CHILD_COUNT: "TRANSITION_CHILD_COUNT_INVALID",
  CHILD_DOMAIN: "TRANSITION_CHILD_INVALID",
  DEFINITION_SELECTOR: "DEFINITION_SELECTOR_INVALID",
  DEFINITION_DOMAIN: "DEFINITION_DOMAIN_INVALID",
  LIFETIME: "LIFETIME_INVALID",
  TIMER: "TIMER_CONTRACT_INVALID",
  RECOVERY: "RECOVERY_CONTRACT_INVALID",
  STACK_CAPACITY: "STACK_CAPACITY_EXCEEDED",
  STACK_INSTANCE: "INSTANCE_KEY_INVALID",
  STACK_IDENTITY: "LAYER_IDENTITY_DUPLICATE",
  OWNER_REQUIRED: "OWNER_REQUIRED_MISMATCH",
  OWNER_MULTIPLICITY: "OWNER_MULTIPLICITY_CONFLICT",
  INSTANCE_MULTIPLICITY: "INSTANCE_MULTIPLICITY_CONFLICT",
  MODIFIER_DOMAIN: "MODIFIER_OPERATION_INVALID",
  MODIFIER_COUNT: "MODIFIER_OPERATION_COUNT_INVALID",
  MODIFIER_OWNERSHIP: "MODIFIER_OPERATION_OWNERSHIP_INVALID",
  MODIFIER_CONFLICT: "MODIFIER_FIELD_PRECEDENCE_CONFLICT",
});

const DEFAULT_SCHEMA = Object.freeze({
  stateFieldCount: 28,
  stackCapacity: 8,
  unsigned: { byte: 0xFF, short: 0xFFFF, word: 0xFFFFFFFF },
  childCountMaximums: { guards: 0xFFFF, operations: 0xFFFF, actions: 0xFFFF, recoveryActions: 0xFF },
  domains: {
    semanticRole: [1, 2, 3, 4, 5, 6, 7], definitionKind: [1, 2],
    selectorKind: [1, 2], channel: [0, 1, 2, 3, 4, 5], lifetime: [1, 2, 3],
    timerClock: [0, 1, 2], timerSource: [0, 1, 2, 3], hiddenTimerPolicy: [0, 1, 2, 3],
    recoveryPolicy: [0, 1], guardKind: [1, 2, 3, 4, 5, 6, 7, 8],
    operationKind: [1, 2, 3, 4, 5, 6], busyPolicy: [1, 2],
    actionPhase: [1, 2, 3, 4], actionKind: [1, 2, 3, 4, 5, 6, 7, 8],
    recoveryActionKind: [1, 2, 3, 4],
  },
});

function schemaFor(model) {
  const supplied = model?.validationSchema || {};
  return {
    ...DEFAULT_SCHEMA,
    ...supplied,
    unsigned: { ...DEFAULT_SCHEMA.unsigned, ...(supplied.unsigned || {}) },
    childCountMaximums: { ...DEFAULT_SCHEMA.childCountMaximums, ...(supplied.childCountMaximums || {}) },
    domains: { ...DEFAULT_SCHEMA.domains, ...(supplied.domains || {}) },
  };
}

const MODIFIER_NUMERIC_FIELDS = Object.freeze({
  1: new Set([3, 4, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 24, 25]),
  2: new Set([3, 4, 6, 7]),
});

function modifierField(model, namespace, fieldId) {
  if (namespace === 1 && fieldId >= 1 && fieldId <= 27) {
    return asArray(model?.stateProfileFields)[fieldId] || null;
  }
  if (namespace === 2 && fieldId >= 1 && fieldId <= 7) {
    return asArray(model?.controllerScalarFields)[fieldId - 1] || null;
  }
  return null;
}

function modifierScalarValid(field, value) {
  return Number.isInteger(value) && Boolean(field) && validateTypedValue(value, field);
}

function modifierProjection(model) {
  const rules = new Map(asArray(model?.applicability).map((item) => [String(ref(item)), item]));
  const operations = new Map();
  asArray(model?.modifierOperations).forEach((operation) => {
    const key = String(operation?.definitionId);
    (operations.get(key) || operations.set(key, []).get(key)).push(clone(operation));
  });
  return asArray(model?.overrideDefinitions)
    .filter((definition) => Number(definition?.kind) === 2)
    .map((definition) => ({
      ...clone(definition),
      applicability: clone(rules.get(String(definition?.applicabilityId))),
      operations: (operations.get(String(ref(definition))) || [])
        .sort((left, right) => Number(left?.order) - Number(right?.order)),
    }));
}

function diagnostic(code, path, message, entityType = "model", entityId = "model", severity = "error") {
  return { code, severity, path, entityType, entityId: String(entityId ?? "model"), message };
}

function stableDiagnostics(source) {
  const unique = new Map();
  for (const item of source) {
    const normalized = diagnostic(
      String(item.code), String(item.path || ""), String(item.message || ""),
      String(item.entityType || "model"), item.entityId ?? "model", String(item.severity || "error"),
    );
    const key = [normalized.code, normalized.severity, normalized.path, normalized.entityType, normalized.entityId, normalized.message].join("\0");
    unique.set(key, normalized);
  }
  return [...unique.values()].sort((left, right) => {
    for (const key of ["severity", "code", "entityType", "entityId", "path", "message"]) {
      const compared = left[key].localeCompare(right[key], "en", { numeric: true });
      if (compared) return compared;
    }
    return 0;
  });
}

export function indexDiagnostics(diagnostics) {
  const index = {};
  for (const item of stableDiagnostics(diagnostics || [])) {
    const key = `${item.entityType}:${item.entityId}`;
    (index[key] ||= []).push(item);
  }
  return index;
}

function mergedEntities(saved, delta = {}) {
  const removed = new Set(asArray(delta?.remove).map(String));
  const updates = new Map(asArray(delta?.update).map((item) => [String(item?.stableId), clone(item)]));
  return [
    ...asArray(saved).filter((item) => !removed.has(String(item?.stableId)))
      .map((item) => updates.get(String(item?.stableId)) || clone(item)),
    ...asArray(delta?.create).map(clone),
  ];
}

/** Materialize one isolated graph snapshot. The saved model and draft are never mutated. */
export function materializeDraftGraph(savedModel, draft = null) {
  const model = clone(savedModel || {});
  if (!draft || typeof draft !== "object") return model;
  for (const key of ["stateProfiles", "controllers", "owners", "overrideDefinitions", "applicability", "customRoles", "semanticRoles"]) {
    if (draft[key]) model[key] = mergedEntities(model[key], draft[key]);
  }
  if (draft.transitions) {
    model.transitionGraph ||= {};
    model.transitionGraph.transitions = mergedEntities(model.transitionGraph.transitions, draft.transitions);
    // Definitions and applicability are authored through their owning transition.
    // Materialize those embedded records into the canonical validation domains so
    // edits to saved identities and newly-created draft identities are validated
    // by the same whole-graph contracts as persisted records.
    const definitions = new Map(asArray(model.overrideDefinitions).map((item) => [String(ref(item)), item]));
    const applicability = new Map(asArray(model.applicability).map((item) => [String(ref(item)), item]));
    // Only authored rows may override the canonical definition tables. Untouched
    // saved transitions can share those identities and still carry the old
    // embedded display copy.
    const authoredTransitions = [
      ...asArray(draft.transitions.update),
      ...asArray(draft.transitions.create),
    ];
    authoredTransitions.forEach((transition) => {
      const definition = transition?.candidateDefinition;
      if (!definition || !present(ref(definition))) return;
      definitions.set(String(ref(definition)), clone(definition));
      const authored = definition.applicability;
      if (!authored || !present(ref(authored))) return;
      const validationShape = "kind" in authored ? {
        ...clone(authored),
        flags: Number(authored.kind),
        immutableContextMask: Number(authored.groupMask),
        effectiveProfileId: authored.profileId || null,
        semanticRoleId: authored.minimum || null,
      } : clone(authored);
      applicability.set(String(ref(authored)), validationShape);
    });
    model.overrideDefinitions = [...definitions.values()];
    model.applicability = [...applicability.values()];
  }
  if (draft.modifiers) {
    const merged = mergedEntities(modifierProjection(model), draft.modifiers);
    const retiredDefinitionIds = new Set(
      asArray(model.overrideDefinitions)
        .filter((definition) => Number(definition?.kind) === 2)
        .map((definition) => String(ref(definition))),
    );
    const retiredApplicabilityIds = new Set(
      asArray(model.overrideDefinitions)
        .filter((definition) => Number(definition?.kind) === 2)
        .map((definition) => String(definition?.applicabilityId)),
    );
    model.overrideDefinitions = asArray(model.overrideDefinitions)
      .filter((definition) => !retiredDefinitionIds.has(String(ref(definition))));
    model.applicability = asArray(model.applicability)
      .filter((rule) => !retiredApplicabilityIds.has(String(ref(rule))));
    model.modifierOperations = asArray(model.modifierOperations)
      .filter((operation) => !retiredDefinitionIds.has(String(operation?.definitionId)));
    for (const modifier of merged) {
      const definition = clone(modifier);
      const authoredRule = definition.applicability;
      const authoredOperations = asArray(definition.operations);
      delete definition.applicability;
      delete definition.operations;
      model.overrideDefinitions.push(definition);
      if (authoredRule) model.applicability.push("kind" in authoredRule ? {
        ...clone(authoredRule),
        flags: Number(authoredRule.kind),
        immutableContextMask: Number(authoredRule.groupMask),
        effectiveProfileId: authoredRule.profileId || null,
        semanticRoleId: authoredRule.minimum || null,
      } : clone(authoredRule));
      model.modifierOperations.push(...authoredOperations.map((operation, order) => ({
        ...clone(operation), definitionId: ref(definition), order,
      })));
    }
  }
  if (draft.policyCatalog && typeof draft.policyCatalog === "object") {
    model.policyCatalog ||= {};
    for (const key of ["spawnPolicies", "populationPolicies", "hookSets"]) {
      if (draft.policyCatalog[key]) model.policyCatalog[key] = mergedEntities(model.policyCatalog[key], draft.policyCatalog[key]);
    }
  }
  for (const key of ["spawnPolicies", "populationPolicies", "hookSets"]) {
    if (!draft[key]) continue;
    model.policyCatalog ||= {};
    model.policyCatalog[key] = mergedEntities(model.policyCatalog[key], draft[key]);
  }
  for (const key of ["genericAssignments", "speciesAssignments", "assignmentActions", "overrides", "importRecipes", "tiredTranslations"]) {
    if (draft[key]) model[key] = mergedEntities(model[key], draft[key]);
  }
  // Controller membership is a projection of candidate scope, not authored
  // transaction state. Rebuild it after every draft merge so adding/removing a
  // controller does not require rewriting every global transition row.
  const controllerRefs = asArray(model.controllers).map(ref);
  const materializedTransitions = asArray(model.transitionGraph?.transitions);
  const applicabilityById = new Map(asArray(model.applicability).map((rule) => [String(ref(rule)), rule]));
  materializedTransitions.sort((left, right) => Number(left?.order) - Number(right?.order));
  materializedTransitions.forEach((transition, order) => { transition.order = order; });
  materializedTransitions.forEach((transition) => {
    const definition = transition?.candidateDefinition;
    const scopedController = definition?.controllerId
      ?? definition?.applicability?.controllerId
      ?? applicabilityById.get(String(definition?.applicabilityId))?.controllerId;
    transition.controllerIds = present(scopedController)
      ? [scopedController]
      : [...controllerRefs];
  });
  asArray(model.controllers).forEach((controller) => {
    controller.transitionIds = materializedTransitions
      .filter((transition) => asArray(transition.controllerIds).some((value) => same(value, ref(controller))))
      .map(ref);
  });
  return model;
}

function validateDelta(savedModel, draft) {
  const errors = [];
  if (draft === null || draft === undefined) return errors;
  if (typeof draft !== "object" || Array.isArray(draft)) {
    return [diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, "draft", "Draft transaction must be an object.", "draft", "draft")];
  }
  if (present(draft.modelVersion) && Number(draft.modelVersion) !== 40) {
    errors.push(diagnostic(VALIDATION_CODES.MODEL_VERSION, "draft.modelVersion", "Draft modelVersion must remain 40.", "draft", "draft"));
  }
  const supported = new Set([
    "stateProfiles", "controllers", "transitions", "modifiers",
    "spawnPolicies", "populationPolicies", "hookSets",
    "genericAssignments", "speciesAssignments", "assignmentActions",
    "overrides",
  ]);
  const recognized = new Set([...supported, "owners", "importRecipes", "tiredTranslations", "overrideDefinitions", "modifierOperations", "applicability", "customRoles", "semanticRoles", "policyCatalog"]);
  for (const key of Object.keys(draft).filter((key) => key !== "modelVersion")) {
    if (!recognized.has(key)) {
      errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, `draft.${key}`, `Unknown draft transaction domain ${key}.`, "draft", "draft"));
    } else if (!supported.has(key) && ["create", "update", "remove"].some((operation) => asArray(draft[key]?.[operation]).length)) {
      errors.push(diagnostic(VALIDATION_CODES.REPRESENTATION, `draft.${key}`, `${key} authoring is not supported by the current atomic writer.`, "draft", "draft"));
    }
  }
  const savedDomains = {
    stateProfiles: asArray(savedModel?.stateProfiles), controllers: asArray(savedModel?.controllers),
    transitions: asArray(savedModel?.transitionGraph?.transitions), owners: asArray(savedModel?.owners),
    modifiers: modifierProjection(savedModel),
    spawnPolicies: asArray(savedModel?.policyCatalog?.spawnPolicies),
    populationPolicies: asArray(savedModel?.policyCatalog?.populationPolicies),
    hookSets: asArray(savedModel?.policyCatalog?.hookSets),
    genericAssignments: asArray(savedModel?.genericAssignments),
    speciesAssignments: asArray(savedModel?.speciesAssignments),
    assignmentActions: asArray(savedModel?.assignmentActions),
    overrides: asArray(savedModel?.overrides),
    importRecipes: asArray(savedModel?.importRecipes),
    tiredTranslations: asArray(savedModel?.tiredTranslations),
    overrideDefinitions: asArray(savedModel?.overrideDefinitions), modifierOperations: asArray(savedModel?.modifierOperations), applicability: asArray(savedModel?.applicability),
    customRoles: asArray(savedModel?.customRoles), semanticRoles: asArray(savedModel?.semanticRoles),
  };
  for (const key of Object.keys(savedDomains)) {
    const delta = draft[key];
    if (delta === undefined) continue;
    if (!delta || typeof delta !== "object" || Array.isArray(delta)) {
      errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, `draft.${key}`, `${key} draft must contain create, update, and/or remove arrays.`, "draft", key));
      continue;
    }
    const savedIds = new Set(savedDomains[key].map((item) => String(item?.stableId)));
    const touched = new Set();
    for (const operation of ["create", "update", "remove"]) {
      if (delta[operation] !== undefined && !Array.isArray(delta[operation])) {
        errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, `draft.${key}.${operation}`, `${operation} must be an array.`, "draft", key));
        continue;
      }
      asArray(delta[operation]).forEach((item, index) => {
        const value = operation === "remove" ? item : operation === "create" ? item?.draftId : item?.stableId;
        const path = `draft.${key}.${operation}.${index}`;
        if (operation === "create" && (!String(item?.draftId || "").startsWith("draft:") || present(item?.stableId))) {
          errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, path, "Created entities require one draft: identity and no stableId.", key, value || index));
        }
        if (operation === "update" && (!Number.isInteger(item?.stableId) || !savedIds.has(String(item.stableId)))) {
          errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, path, "Updated entities must reference one saved stableId.", key, value || index));
        }
        if (operation === "remove" && !savedIds.has(String(item))) {
          errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, path, "Removed entities must reference one saved stableId.", key, value || index));
        }
        const identity = `${operation === "create" ? "draft" : "stable"}:${String(value)}`;
        if (touched.has(identity)) errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, path, "An entity may occur only once in a draft transaction.", key, value || index));
        touched.add(identity);
      });
    }
  }
  const authoredDefinitions = new Map();
  const authoredApplicability = new Map();
  for (const operation of ["create", "update"]) {
    asArray(draft?.transitions?.[operation]).forEach((transition, index) => {
      const definition = transition?.candidateDefinition;
      const definitionId = ref(definition);
      const path = `draft.transitions.${operation}.${index}.candidateDefinition`;
      if (present(definitionId)) {
        const serialized = JSON.stringify(definition);
        if (authoredDefinitions.has(String(definitionId)) && authoredDefinitions.get(String(definitionId)) !== serialized) {
          errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, path, "Shared candidate definition has conflicting authored values.", "overrideDefinition", definitionId));
        } else authoredDefinitions.set(String(definitionId), serialized);
      }
      const rule = definition?.applicability;
      const ruleId = ref(rule);
      if (present(ruleId)) {
        const serialized = JSON.stringify(rule);
        if (authoredApplicability.has(String(ruleId)) && authoredApplicability.get(String(ruleId)) !== serialized) {
          errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, `${path}.applicability`, "Shared applicability has conflicting authored values.", "applicability", ruleId));
        } else authoredApplicability.set(String(ruleId), serialized);
      }
    });
  }
  return errors;
}

function entityIdentity(entity) {
  if (Number.isInteger(entity?.stableId) && entity.stableId > 0) return { kind: "stable", value: entity.stableId };
  if (!present(entity?.stableId) && /^draft:[^\s]+$/.test(String(entity?.draftId || ""))) return { kind: "draft", value: entity.draftId };
  return null;
}

function validateTypedValue(value, field) {
  if (!Number.isInteger(value)) return false;
  if (field?.type === "number" || field?.type === "mask") return value >= Number(field.minimum) && value <= Number(field.maximum);
  return asArray(field?.options).some((option) => Number(option.value) === value);
}

function modelDiagnostics(model) {
  const errors = [];
  const schema = schemaFor(model);
  const shortMax = Number(schema.unsigned.short);
  const byteMax = Number(schema.unsigned.byte);
  const wordMax = Number(schema.unsigned.word);
  if (Number(model?.modelVersion) !== 40) errors.push(diagnostic(VALIDATION_CODES.MODEL_VERSION, "modelVersion", "Behavior model version must be 40."));

  const fields = asArray(model?.stateProfileFields);
  const fieldKeys = fields.map((field) => String(field?.key || ""));
  if (fields.length !== Number(schema.stateFieldCount) || new Set(fieldKeys).size !== fields.length || fieldKeys.some((key) => !key)) {
    errors.push(diagnostic(VALIDATION_CODES.PROFILE_FIELDS, "stateProfileFields", `V40 requires exactly ${schema.stateFieldCount} unique state fields.`));
  }

  const globalIds = new Map();
  function identity(entity, type, path, { globalStable = true } = {}) {
    const found = entityIdentity(entity);
    const label = found?.value ?? path;
    if (!found || (found.kind === "stable" && found.value > shortMax)) {
      errors.push(diagnostic(VALIDATION_CODES.IDENTITY, `${path}.${found?.kind === "draft" ? "draftId" : "stableId"}`, "Entity identity must be a non-zero unsigned 16-bit stableId or a draft: identity.", type, label));
      return null;
    }
    const key = `${found.kind}:${found.value}`;
    if (globalStable || found.kind === "draft") {
      if (globalIds.has(key)) errors.push(diagnostic(VALIDATION_CODES.IDENTITY_DUPLICATE, path, `Identity ${found.value} is already owned by ${globalIds.get(key)}.`, type, found.value));
      else globalIds.set(key, `${type} at ${path}`);
    }
    return found.value;
  }
  function unsigned(value, maximum, path, type, id, { optional = false, allowDraft = false } = {}) {
    if (optional && !present(value)) return true;
    if (allowDraft && /^draft:[^\s]+$/.test(String(value || ""))) return true;
    if (!Number.isInteger(value) || value < 0 || value > maximum) {
      errors.push(diagnostic(VALIDATION_CODES.WIRE_RANGE, path, `Value must fit the V40 unsigned ${maximum === byteMax ? "8" : maximum === shortMax ? "16" : "32"}-bit wire field.`, type, id));
      return false;
    }
    return true;
  }
  function domain(value, values, path, type, id, code = VALIDATION_CODES.FIELD_DOMAIN) {
    if (!asArray(values).map(Number).includes(Number(value))) {
      errors.push(diagnostic(code, path, "Value is outside the typed V40 domain.", type, id));
      return false;
    }
    return true;
  }
  function requireRef(value, known, path, type, id, label) {
    if (!present(value) || !known.has(String(value))) {
      errors.push(diagnostic(VALIDATION_CODES.REFERENCE, path, `${label} reference does not resolve.`, type, id));
      return false;
    }
    return true;
  }
  const zero = (value) => !present(value) || Number(value) === 0;
  function requireBoolean(value, path, type, id) {
    if (typeof value !== "boolean") errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, path, "Value must be a boolean.", type, id));
  }

  const profiles = asArray(model?.stateProfiles);
  const profileIds = new Set();
  const profileNames = new Set();
  const stateBodies = new Map();
  profiles.forEach((profile, index) => {
    const path = `stateProfiles.${index}`;
    const id = identity(profile, "stateProfile", path);
    if (id !== null) profileIds.add(String(id));
    if (!String(profile?.name || "").trim()) errors.push(diagnostic(VALIDATION_CODES.NAME, `${path}.name`, "State profile name is required.", "stateProfile", id));
    const normalizedName = String(profile?.name || "").trim().toLocaleLowerCase("en");
    if (normalizedName && profileNames.has(normalizedName)) errors.push(diagnostic(VALIDATION_CODES.IDENTITY_DUPLICATE, `${path}.name`, "State profile names must be unique.", "stateProfile", id));
    profileNames.add(normalizedName);
    if ("semanticRole" in (profile || {}) || "semanticRoleId" in (profile || {}) || "customRoleId" in (profile || {})) {
      errors.push(diagnostic(VALIDATION_CODES.PROFILE_ROLE, path, "Semantic roles belong to controller nodes, never state profiles.", "stateProfile", id));
    }
    const valueKeys = Object.keys(profile?.values || {});
    if (valueKeys.length !== fields.length || valueKeys.some((key) => !fieldKeys.includes(key)) || fieldKeys.some((key) => !valueKeys.includes(key))) {
      errors.push(diagnostic(VALIDATION_CODES.PROFILE_FIELDS, `${path}.values`, "Profile must contain every typed state field exactly once.", "stateProfile", id));
    }
    fields.forEach((field) => {
      if (!validateTypedValue(profile?.values?.[field.key], field)) errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${path}.values.${field.key}`, `${field.label || field.key} is outside its typed domain.`, "stateProfile", id));
    });
    if (Number(profile?.values?.hopMaxDistance) < Number(profile?.values?.hopMinDistance)) errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${path}.values.hopMaxDistance`, "Maximum hop distance cannot be below the minimum.", "stateProfile", id));
    if (present(profile?.bodyId)) {
      unsigned(profile.bodyId, shortMax, `${path}.bodyId`, "stateProfile", id);
      if (Number(profile.bodyId) === 0) errors.push(diagnostic(VALIDATION_CODES.IDENTITY, `${path}.bodyId`, "State body identity zero is reserved.", "stateProfile", id));
      const bodyKey = `stable:${profile.bodyId}`;
      const bodyRegistryKey = String(profile?.bodyRegistryKey || "");
      const provenanceKind = Number(profile?.bodyProvenance?.kind);
      if (!bodyRegistryKey || !Number.isInteger(provenanceKind) || provenanceKind < 1 || provenanceKind > 7) {
        errors.push(diagnostic(VALIDATION_CODES.IDENTITY, `${path}.bodyId`, "Persisted state bodies require immutable registry and provenance metadata.", "stateProfile", id));
      }
      const signature = JSON.stringify([
        bodyRegistryKey,
        provenanceKind,
        fieldKeys.map((key) => profile?.values?.[key]),
      ]);
      if (stateBodies.has(bodyKey)) {
        if (stateBodies.get(bodyKey) !== signature) errors.push(diagnostic(VALIDATION_CODES.IDENTITY_DUPLICATE, `${path}.bodyId`, `State body identity ${profile.bodyId} has conflicting immutable data.`, "stateProfile", id));
      } else if (globalIds.has(bodyKey)) {
        errors.push(diagnostic(VALIDATION_CODES.IDENTITY_DUPLICATE, `${path}.bodyId`, `State body identity ${profile.bodyId} collides with ${globalIds.get(bodyKey)}.`, "stateProfile", id));
      } else {
        stateBodies.set(bodyKey, signature);
        globalIds.set(bodyKey, `state body at ${path}`);
      }
    }
  });

  const semanticRoles = new Set(asArray(model?.semanticRoles).map((item) => String(item?.value)));
  const customRoleIds = new Set();
  asArray(model?.customRoles).forEach((role, index) => {
    const id = identity(role, "customRole", `customRoles.${index}`);
    if (id !== null) customRoleIds.add(String(id));
  });

  const policyIds = new Set();
  const policyKinds = { spawnPolicyId: "spawnPolicies", populationPolicyId: "populationPolicies", hookSetId: "hookSets" };
  Object.values(policyKinds).forEach((key) => asArray(model?.policyCatalog?.[key]).forEach((policy, index) => {
    const path = `policyCatalog.${key}.${index}`;
    const id = identity(policy, key, path);
    if (id !== null) policyIds.add(String(id));
    if (key === "spawnPolicies" && (present(policy?.draftId) || "spawnState" in (policy || {}))) {
      unsigned(policy?.provenanceId, shortMax, `${path}.provenanceId`, key, id);
      for (const field of ["spawnState", "destination", "minimumDistance", "maximumDistance", "spawnHopTime", "flags"]) unsigned(policy?.[field], byteMax, `${path}.${field}`, key, id);
      if (Number(policy?.maximumDistance) < Number(policy?.minimumDistance)) errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${path}.maximumDistance`, "Maximum spawn distance cannot be below the minimum.", key, id));
    } else if (key === "populationPolicies" && (present(policy?.draftId) || "populationGroupId" in (policy || {}))) {
      unsigned(policy?.populationGroupId, shortMax, `${path}.populationGroupId`, key, id);
      unsigned(policy?.provenanceId, shortMax, `${path}.provenanceId`, key, id);
      unsigned(policy?.limit, byteMax, `${path}.limit`, key, id);
      unsigned(policy?.flags, byteMax, `${path}.flags`, key, id);
    } else if (key === "hookSets" && (present(policy?.draftId) || "helpCallInvocation" in (policy || {}))) {
      for (const field of ["helpCallInvocation", "pickupThrowEntry", "pickupThrowActiveLoop", "flags"]) unsigned(policy?.[field], byteMax, `${path}.${field}`, key, id);
    }
  }));

  const controllers = asArray(model?.controllers);
  const controllerIds = new Set();
  const nodeIds = new Set();
  const nodesById = new Map();
  const controllerNames = new Set();
  controllers.forEach((controller, controllerIndex) => {
    const path = `controllers.${controllerIndex}`;
    const id = identity(controller, "controller", path);
    if (id !== null) controllerIds.add(String(id));
    if (!String(controller?.name || "").trim()) errors.push(diagnostic(VALIDATION_CODES.NAME, `${path}.name`, "Controller name is required.", "controller", id));
    const name = String(controller?.name || "").trim().toLocaleLowerCase("en");
    if (name && controllerNames.has(name)) errors.push(diagnostic(VALIDATION_CODES.IDENTITY_DUPLICATE, `${path}.name`, "Controller names must be unique.", "controller", id));
    controllerNames.add(name);
    const nodes = asArray(controller?.nodes);
    if (!nodes.length || nodes.length > shortMax) errors.push(diagnostic(VALIDATION_CODES.CHILD_COUNT, `${path}.nodes`, "Controller must contain 1–65535 ordered nodes.", "controller", id));
    const baseNodes = nodes.filter((node) => node?.base === true);
    if (baseNodes.length !== 1) errors.push(diagnostic(VALIDATION_CODES.BASE_NODE, `${path}.nodes`, "Controller must have exactly one base node.", "controller", id));
    const baseRef = ref(baseNodes[0]);
    if (baseNodes.length === 1 && !same(controller?.baseNodeId, baseRef)) errors.push(diagnostic(VALIDATION_CODES.BASE_NODE, `${path}.baseNodeId`, "baseNodeId must identify the single base node.", "controller", id));
    const selectors = new Set();
    const orders = new Set();
    nodes.forEach((node, nodeIndex) => {
      const nodePath = `${path}.nodes.${nodeIndex}`;
      const nodeId = identity(node, "controllerNode", nodePath);
      if (nodeId !== null) { nodeIds.add(String(nodeId)); nodesById.set(String(nodeId), { node, controllerId: id }); }
      if (!same(node?.controllerId, id)) errors.push(diagnostic(VALIDATION_CODES.NODE_OWNER, `${nodePath}.controllerId`, "Node owner must match its containing controller.", "controllerNode", nodeId));
      requireRef(node?.profileRef ?? node?.profileStableId, profileIds, `${nodePath}.profileRef`, "controllerNode", nodeId, "State profile");
      domain(node?.semanticRoleId, semanticRoles.size ? [...semanticRoles] : schema.domains.semanticRole, `${nodePath}.semanticRoleId`, "controllerNode", nodeId, VALIDATION_CODES.SEMANTIC_ROLE);
      const role = Number(node?.semanticRoleId);
      let selector = `role:${role}`;
      if (role === 7) {
        requireRef(node?.customRoleId, customRoleIds, `${nodePath}.customRoleId`, "controllerNode", nodeId, "Custom role");
        selector = `custom:${String(node?.customRoleId)}`;
      } else if (present(node?.customRoleId)) {
        errors.push(diagnostic(VALIDATION_CODES.SEMANTIC_ROLE, `${nodePath}.customRoleId`, "Ordinary semantic nodes cannot own a custom-role identity.", "controllerNode", nodeId));
      }
      if (selectors.has(selector)) errors.push(diagnostic(VALIDATION_CODES.SELECTOR_DUPLICATE, nodePath, "Semantic selectors must be unique within a controller.", "controllerNode", nodeId));
      selectors.add(selector);
      if (!Number.isInteger(node?.order) || node.order < 0 || node.order >= nodes.length || orders.has(node.order)) errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${nodePath}.order`, "Node order must be a unique contiguous index.", "controllerNode", nodeId));
      orders.add(node?.order);
    });
    asArray(model?.controllerScalarFields).forEach((field) => {
      if (!validateTypedValue(controller?.scalarDefaults?.[field.key], field)) errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${path}.scalarDefaults.${field.key}`, `${field.label || field.key} is outside its typed domain.`, "controller", id));
    });
    Object.entries(policyKinds).forEach(([field, catalog]) => {
      const known = new Set(asArray(model?.policyCatalog?.[catalog]).map((item) => String(ref(item))));
      if (!known.has(String(controller?.policyIds?.[field]))) errors.push(diagnostic(VALIDATION_CODES.CONTROLLER_POLICY, `${path}.policyIds.${field}`, `${field} must reference an existing typed policy.`, "controller", id));
    });
  });

  const owners = asArray(model?.owners);
  const ownerIds = new Set();
  owners.forEach((owner, index) => { const id = identity(owner, "owner", `owners.${index}`); if (id !== null) ownerIds.add(String(id)); });
  const applicability = asArray(model?.applicability);
  const applicabilityIds = new Set();
  const applicabilityById = new Map();
  applicability.forEach((rule, index) => {
    const path = `applicability.${index}`;
    const id = identity(rule, "applicability", path);
    if (id !== null) { applicabilityIds.add(String(id)); applicabilityById.set(String(id), rule); }
    unsigned(rule?.flags, shortMax, `${path}.flags`, "applicability", id);
    unsigned(rule?.immutableContextMask, wordMax, `${path}.immutableContextMask`, "applicability", id);
    if (present(rule?.controllerId)) requireRef(rule.controllerId, controllerIds, `${path}.controllerId`, "applicability", id, "Controller");
    if (present(rule?.effectiveProfileId)) requireRef(rule.effectiveProfileId, profileIds, `${path}.effectiveProfileId`, "applicability", id, "Effective profile");
    if (present(rule?.semanticRoleId)) domain(rule.semanticRoleId, semanticRoles.size ? [...semanticRoles] : schema.domains.semanticRole, `${path}.semanticRoleId`, "applicability", id, VALIDATION_CODES.SEMANTIC_ROLE);
    const flagRefs = [[2, rule?.controllerId, "controllerId"], [4, rule?.effectiveProfileId, "effectiveProfileId"], [8, rule?.semanticRoleId, "semanticRoleId"]];
    flagRefs.forEach(([bit, value, key]) => {
      if (Boolean(Number(rule?.flags) & bit) !== present(value)) errors.push(diagnostic(VALIDATION_CODES.DEFINITION_DOMAIN, `${path}.${key}`, `${key} presence must match its applicability flag.`, "applicability", id));
    });
  });

  const rootDefinitions = asArray(model?.overrideDefinitions);
  const embeddedDefinitions = asArray(model?.transitionGraph?.transitions).map((item) => item?.candidateDefinition).filter(Boolean);
  const definitions = [...rootDefinitions];
  const knownDefinitionRefs = new Set(rootDefinitions.map((item) => String(ref(item))));
  embeddedDefinitions.forEach((item) => { if (!knownDefinitionRefs.has(String(ref(item)))) { definitions.push(item); knownDefinitionRefs.add(String(ref(item))); } });
  const definitionIds = new Set();
  definitions.forEach((definition, index) => {
    const isRoot = index < rootDefinitions.length;
    const path = `${isRoot ? "overrideDefinitions" : "embeddedDefinitions"}.${isRoot ? index : index - rootDefinitions.length}`;
    const id = identity(definition, "overrideDefinition", path, { globalStable: isRoot || !rootDefinitions.some((item) => same(ref(item), ref(definition))) });
    if (id !== null) definitionIds.add(String(id));
    requireRef(definition?.applicabilityId, applicabilityIds, `${path}.applicabilityId`, "overrideDefinition", id, "Applicability");
    domain(definition?.kind, schema.domains.definitionKind, `${path}.kind`, "overrideDefinition", id, VALIDATION_CODES.DEFINITION_DOMAIN);
    domain(definition?.channel, schema.domains.channel, `${path}.channel`, "overrideDefinition", id, VALIDATION_CODES.DEFINITION_DOMAIN);
    const modifier = Number(definition?.kind) === 2;
    if (!modifier) domain(definition?.selectorKind, schema.domains.selectorKind, `${path}.selectorKind`, "overrideDefinition", id, VALIDATION_CODES.DEFINITION_SELECTOR);
    unsigned(definition?.priority, byteMax, `${path}.priority`, "overrideDefinition", id);
    for (const key of ["timerValue", "hasTiredOriginKind", "tiredOriginKind", "hasRequiredOwnerId", "allowMultipleOwners", "allowMultipleInstancesPerOwner", "authoredTiredBound", "flags", "reserved0", "reserved1"]) unsigned(definition?.[key] ?? 0, byteMax, `${path}.${key}`, "overrideDefinition", id);
    if (modifier) {
      if (![1, 2, 3, 4].includes(Number(definition?.channel))) errors.push(diagnostic(VALIDATION_CODES.DEFINITION_DOMAIN, `${path}.channel`, "Ordinary runtime modifiers must use Controller State, Temporary Effect, Scripted Force, or Possession.", "overrideDefinition", id));
      for (const key of ["controllerId", "nodeId", "selectorKind", "semanticRoleId", "requiredOwnerId", "recoveryTransitionId", "timerClock", "timerSource", "hiddenTimerPolicy", "recoveryPolicy", "timerValue", "hasTiredOriginKind", "tiredOriginKind", "hasRequiredOwnerId", "authoredTiredBound", "flags", "reserved0", "reserved1"]) {
        if (!zero(definition?.[key])) errors.push(diagnostic(VALIDATION_CODES.DEFINITION_DOMAIN, `${path}.${key}`, "Modifier definitions cannot carry candidate, timer, recovery, or generated-wrapper metadata.", "overrideDefinition", id));
      }
    } else if (Number(definition?.selectorKind) === 1) {
      requireRef(definition?.nodeId, nodeIds, `${path}.nodeId`, "overrideDefinition", id, "Exact node");
      if (Number(definition?.semanticRoleId || 0) !== 0) errors.push(diagnostic(VALIDATION_CODES.DEFINITION_SELECTOR, `${path}.semanticRoleId`, "Exact selectors must not also select a semantic role.", "overrideDefinition", id));
      const node = nodesById.get(String(definition?.nodeId));
      const scopedController = definition?.controllerId
        ?? definition?.applicability?.controllerId
        ?? applicabilityById.get(String(definition?.applicabilityId))?.controllerId;
      if (present(scopedController) && node && !same(scopedController, node.controllerId)) errors.push(diagnostic(VALIDATION_CODES.DEFINITION_SELECTOR, `${path}.controllerId`, "Exact selector controller and node ownership disagree.", "overrideDefinition", id));
    } else if (Number(definition?.selectorKind) === 2) {
      if (present(definition?.nodeId)) errors.push(diagnostic(VALIDATION_CODES.DEFINITION_SELECTOR, `${path}.nodeId`, "Semantic selectors cannot also select an exact node.", "overrideDefinition", id));
      domain(definition?.semanticRoleId, semanticRoles.size ? [...semanticRoles] : schema.domains.semanticRole, `${path}.semanticRoleId`, "overrideDefinition", id, VALIDATION_CODES.DEFINITION_SELECTOR);
    }
    const generatedDefinition = !modifier && (Number(definition?.hasTiredOriginKind) !== 0 || Number(definition?.hasRequiredOwnerId) !== 0);
    const expectedSelectorFlags = generatedDefinition && Number(definition?.selectorKind) === 1 ? 1 : 0;
    if (Number(definition?.flags) !== expectedSelectorFlags) errors.push(diagnostic(VALIDATION_CODES.DEFINITION_SELECTOR, `${path}.flags`, `Definition flags must be ${expectedSelectorFlags} for this selector kind.`, "overrideDefinition", id));
    if (![0, 1].includes(Number(definition?.hasTiredOriginKind))
        || (!Number(definition?.hasTiredOriginKind) && Number(definition?.tiredOriginKind) !== 0)
        || (Number(definition?.hasTiredOriginKind) && ![1, 2, 3].includes(Number(definition?.tiredOriginKind)))) {
      errors.push(diagnostic(VALIDATION_CODES.DEFINITION_DOMAIN, `${path}.tiredOriginKind`, "Tired-origin presence and kind must agree; enabled kinds are 1–3.", "overrideDefinition", id));
    }
    const scopedController = definition?.controllerId
      ?? definition?.applicability?.controllerId
      ?? applicabilityById.get(String(definition?.applicabilityId))?.controllerId;
    if (nonzeroRef(scopedController)) requireRef(scopedController, controllerIds, `${path}.controllerId`, "overrideDefinition", id, "Controller");
    domain(definition?.mapLifetime, schema.domains.lifetime, `${path}.mapLifetime`, "overrideDefinition", id, VALIDATION_CODES.LIFETIME);
    domain(definition?.battleLifetime, schema.domains.lifetime, `${path}.battleLifetime`, "overrideDefinition", id, VALIDATION_CODES.LIFETIME);
    domain(definition?.timerClock ?? 0, schema.domains.timerClock, `${path}.timerClock`, "overrideDefinition", id, VALIDATION_CODES.TIMER);
    domain(definition?.timerSource ?? 0, schema.domains.timerSource, `${path}.timerSource`, "overrideDefinition", id, VALIDATION_CODES.TIMER);
    domain(definition?.hiddenTimerPolicy ?? 0, schema.domains.hiddenTimerPolicy, `${path}.hiddenTimerPolicy`, "overrideDefinition", id, VALIDATION_CODES.TIMER);
    domain(definition?.recoveryPolicy ?? 0, schema.domains.recoveryPolicy, `${path}.recoveryPolicy`, "overrideDefinition", id, VALIDATION_CODES.RECOVERY);
    if (Number(definition?.timerClock) === 0 && (Number(definition?.timerSource) !== 0 || Number(definition?.timerValue) !== 0 || Number(definition?.hiddenTimerPolicy) !== 0)) errors.push(diagnostic(VALIDATION_CODES.TIMER, path, "A definition without a timer clock must clear timer source, value, and hidden policy.", "overrideDefinition", id));
    if (Number(definition?.timerClock) !== 0 && (Number(definition?.timerSource) === 0 || Number(definition?.timerValue) === 0 || Number(definition?.hiddenTimerPolicy) === 0)) errors.push(diagnostic(VALIDATION_CODES.TIMER, path, "An active timer requires a non-zero source, value, and hidden-state policy.", "overrideDefinition", id));
    if (Boolean(Number(definition?.hasRequiredOwnerId)) !== nonzeroRef(definition?.requiredOwnerId)) errors.push(diagnostic(VALIDATION_CODES.OWNER_REQUIRED, `${path}.requiredOwnerId`, "Required-owner flag and reference must agree.", "overrideDefinition", id));
    if (nonzeroRef(definition?.requiredOwnerId)) requireRef(definition.requiredOwnerId, ownerIds, `${path}.requiredOwnerId`, "overrideDefinition", id, "Required owner");
  });

  const definitionsById = new Map(definitions.map((definition) => [String(ref(definition)), definition]));
  const modifierOperationsByDefinition = new Map();
  asArray(model?.modifierOperations).forEach((operation, index) => {
    const path = `modifierOperations.${index}`;
    const id = identity(operation, "modifierOperation", path);
    const definitionId = operation?.definitionId;
    const definition = definitionsById.get(String(definitionId));
    requireRef(definitionId, definitionIds, `${path}.definitionId`, "modifierOperation", id, "Modifier definition");
    if (definition && Number(definition.kind) !== 2) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_OWNERSHIP, `${path}.definitionId`, "Only a modifier definition may own modifier operations.", "modifierOperation", id));
    const namespace = Number(operation?.fieldNamespace);
    const fieldId = Number(operation?.fieldId);
    const operator = Number(operation?.operatorKind);
    const field = modifierField(model, namespace, fieldId);
    if (![1, 2].includes(namespace) || !field) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_DOMAIN, `${path}.fieldId`, "Modifier target must be one runtime-addressable state or controller field; behaviorKind is not addressable.", "modifierOperation", id));
    domain(operator, [1, 2, 3, 4, 5, 6], `${path}.operatorKind`, "modifierOperation", id, VALIDATION_CODES.MODIFIER_DOMAIN);
    const numeric = Boolean(MODIFIER_NUMERIC_FIELDS[namespace]?.has(fieldId));
    if (!numeric && operator !== 1) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_DOMAIN, `${path}.operatorKind`, "Enum, boolean, mask, and ID fields support SET only.", "modifierOperation", id));
    const operand = operation?.operand;
    if (!Number.isInteger(operand) || operand < -0x8000 || operand > 0x7FFF) {
      errors.push(diagnostic(VALIDATION_CODES.MODIFIER_DOMAIN, `${path}.operand`, "Modifier operand must be a signed 16-bit integer.", "modifierOperation", id));
    } else if (![2, 5, 6].includes(operator) && !modifierScalarValid(field, operand)) {
      errors.push(diagnostic(VALIDATION_CODES.MODIFIER_DOMAIN, `${path}.operand`, "Exact modifier operands must be members of the target field's typed domain.", "modifierOperation", id));
    }
    unsigned(operation?.bound, byteMax, `${path}.bound`, "modifierOperation", id);
    if (operator < 5 && Number(operation?.bound) !== 0) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_DOMAIN, `${path}.bound`, "Only compound relative operators may carry a bound.", "modifierOperation", id));
    if (operator >= 5 && !modifierScalarValid(field, Number(operation?.bound))) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_DOMAIN, `${path}.bound`, "Compound modifier bounds must be members of the target field's typed domain.", "modifierOperation", id));
    if (!Number.isInteger(operation?.order) || operation.order < 0 || operation.order > 15) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_DOMAIN, `${path}.order`, "Modifier operation order must fit 0..15.", "modifierOperation", id));
    const owned = modifierOperationsByDefinition.get(String(definitionId)) || [];
    owned.push(operation);
    modifierOperationsByDefinition.set(String(definitionId), owned);
  });
  definitions.forEach((definition, index) => {
    const operations = modifierOperationsByDefinition.get(String(ref(definition))) || [];
    const path = `${index < rootDefinitions.length ? "overrideDefinitions" : "embeddedDefinitions"}.${index < rootDefinitions.length ? index : index - rootDefinitions.length}`;
    if (Number(definition?.kind) !== 2) {
      if (operations.length) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_OWNERSHIP, path, "State-candidate definitions cannot own modifier operations.", "overrideDefinition", ref(definition)));
      return;
    }
    if (operations.length < 1 || operations.length > 16) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_COUNT, `${path}.operations`, "A modifier definition must own 1..16 operations.", "overrideDefinition", ref(definition)));
    const orders = operations.map((operation) => Number(operation?.order)).sort((left, right) => left - right);
    if (orders.length && orders.some((value, order) => value !== order)) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_DOMAIN, `${path}.operations`, "Modifier operation order must be one unique contiguous 0-based sequence.", "overrideDefinition", ref(definition)));
    const lower = new Set(operations.filter((operation) => Number(operation?.operatorKind) === 3).map((operation) => `${operation.fieldNamespace}:${operation.fieldId}`));
    const upper = new Set(operations.filter((operation) => Number(operation?.operatorKind) === 4).map((operation) => `${operation.fieldNamespace}:${operation.fieldId}`));
    for (const fieldKey of lower) if (upper.has(fieldKey)) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_DOMAIN, `${path}.operations`, `One modifier cannot combine AT_LEAST and AT_MOST for field ${fieldKey}.`, "overrideDefinition", ref(definition)));
  });
  const modifierDefinitions = definitions.filter((definition) => Number(definition?.kind) === 2);
  modifierDefinitions.forEach((right, rightIndex) => {
    const rightFields = new Set((modifierOperationsByDefinition.get(String(ref(right))) || []).map((operation) => `${operation.fieldNamespace}:${operation.fieldId}`));
    for (let leftIndex = 0; leftIndex < rightIndex; leftIndex += 1) {
      const left = modifierDefinitions[leftIndex];
      if (Number(left?.channel) !== Number(right?.channel) || Number(left?.priority) !== Number(right?.priority)) continue;
      const overlap = (modifierOperationsByDefinition.get(String(ref(left))) || []).find((operation) => rightFields.has(`${operation.fieldNamespace}:${operation.fieldId}`));
      if (overlap) errors.push(diagnostic(VALIDATION_CODES.MODIFIER_CONFLICT, `overrideDefinitions.${rootDefinitions.indexOf(right)}.priority`, `Modifier ${String(ref(right))} shares channel, priority, and field ${overlap.fieldNamespace}:${overlap.fieldId} with modifier ${String(ref(left))}; stable IDs decide write order.`, "overrideDefinition", ref(right), "warning"));
    }
  });

  const transitions = asArray(model?.transitionGraph?.transitions);
  const transitionIds = new Set();
  const transitionOrders = new Set();
  transitions.forEach((transition, index) => { const id = identity(transition, "transition", `transitionGraph.transitions.${index}`); if (id !== null) transitionIds.add(String(id)); });
  const transitionsById = new Map(transitions.map((transition) => [String(ref(transition)), transition]));
  const ownerAuthorized = (definitionRef, ownerRef) => {
    const definition = definitionsById.get(String(definitionRef));
    return Boolean(definition) && (!Number(definition.hasRequiredOwnerId) || same(definition.requiredOwnerId, ownerRef));
  };
  definitions.forEach((definition, index) => {
    const id = ref(definition); const path = `${index < rootDefinitions.length ? "overrideDefinitions" : "embeddedDefinitions"}.${index < rootDefinitions.length ? index : index - rootDefinitions.length}`;
    if (Number(definition?.recoveryPolicy) === 1) {
      const resolves = requireRef(definition?.recoveryTransitionId, transitionIds, `${path}.recoveryTransitionId`, "overrideDefinition", id, "Recovery transition");
      const recovery = resolves ? transitionsById.get(String(definition.recoveryTransitionId)) : null;
      if (recovery && !same(recovery.candidateDefinitionId, id)) errors.push(diagnostic(VALIDATION_CODES.RECOVERY, `${path}.recoveryTransitionId`, "Recovery transition must route the same candidate definition.", "overrideDefinition", id));
      if (recovery && nonzeroRef(definition?.requiredOwnerId) && !same(recovery.ownerId, definition.requiredOwnerId)) errors.push(diagnostic(VALIDATION_CODES.RECOVERY, `${path}.recoveryTransitionId`, "Recovery transition owner must match the definition's required owner.", "overrideDefinition", id));
      if (recovery && !asArray(recovery.operations).some((operation) => [3, 4].includes(Number(operation.kind)) && same(operation.definitionId, id) && same(operation.ownerId, recovery.ownerId))) errors.push(diagnostic(VALIDATION_CODES.RECOVERY, `${path}.recoveryTransitionId`, "Recovery transition must remove the same candidate and owner.", "overrideDefinition", id));
    }
    else if (nonzeroRef(definition?.recoveryTransitionId)) errors.push(diagnostic(VALIDATION_CODES.RECOVERY, `${path}.recoveryTransitionId`, "Recovery transition requires route-transition policy.", "overrideDefinition", id));
  });

  const childGlobalIds = new Set();
  transitions.forEach((transition, index) => {
    const path = `transitionGraph.transitions.${index}`;
    const id = ref(transition);
    if (!Number.isInteger(transition?.order) || transition.order < 0 || transition.order >= transitions.length || transitionOrders.has(transition.order)) {
      errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${path}.order`, "Transition order must be a unique contiguous index.", "transition", id));
    }
    transitionOrders.add(transition?.order);
    const definition = definitions.find((item) => same(ref(item), transition?.candidateDefinitionId));
    requireRef(transition?.candidateDefinitionId, definitionIds, `${path}.candidateDefinitionId`, "transition", id, "Candidate definition");
    if (transition?.candidateDefinition && !same(ref(transition.candidateDefinition), transition.candidateDefinitionId)) errors.push(diagnostic(VALIDATION_CODES.REFERENCE, `${path}.candidateDefinition`, "Embedded candidate definition identity must match candidateDefinitionId.", "transition", id));
    requireRef(transition?.ownerId, ownerIds, `${path}.ownerId`, "transition", id, "Owner");
    if (definition && !ownerAuthorized(ref(definition), transition?.ownerId)) errors.push(diagnostic(VALIDATION_CODES.OWNER_REQUIRED, `${path}.ownerId`, "Transition owner is not authorized by its candidate definition.", "transition", id));
    const triggerDomain = asArray(model?.transitionGraph?.triggerOptions).map((item) => item.value);
    domain(transition?.trigger, triggerDomain, `${path}.trigger`, "transition", id, VALIDATION_CODES.CHILD_DOMAIN);
    if (!Number.isInteger(transition?.fromRoleMask) || transition.fromRoleMask < 1 || transition.fromRoleMask > 0x7F) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${path}.fromRoleMask`, "Transition from-role mask must select roles 1–7.", "transition", id));
    unsigned(transition?.dispatchPriority, shortMax, `${path}.dispatchPriority`, "transition", id);
    const scopedController = definition?.controllerId
      ?? definition?.applicability?.controllerId
      ?? applicabilityById.get(String(definition?.applicabilityId))?.controllerId;
    const expectedScope = scopedController ? [String(scopedController)] : [...controllerIds].sort((a, b) => a.localeCompare(b, "en", { numeric: true }));
    const actualScope = [...new Set(asArray(transition?.controllerIds).map(String))].sort((a, b) => a.localeCompare(b, "en", { numeric: true }));
    if (expectedScope.length !== actualScope.length || expectedScope.some((value, scopeIndex) => value !== actualScope[scopeIndex])) errors.push(diagnostic(VALIDATION_CODES.TRANSITION_SCOPE, `${path}.controllerIds`, "Transition membership must exactly match candidate-definition scope.", "transition", id));
    if (definition?.nodeId && !actualScope.includes(String(nodesById.get(String(definition.nodeId))?.controllerId))) errors.push(diagnostic(VALIDATION_CODES.TRANSITION_SCOPE, `${path}.candidateDefinition.nodeId`, "Exact selector node is outside the transition controller scope.", "transition", id));
    for (const childKey of ["guards", "operations", "actions", "recoveryActions"]) {
      const children = asArray(transition?.[childKey]);
      if (children.length > Number(schema.childCountMaximums[childKey])) errors.push(diagnostic(VALIDATION_CODES.CHILD_COUNT, `${path}.${childKey}`, `${childKey} exceeds its V40 child-count wire field.`, "transition", id));
      children.forEach((child, childIndex) => {
        const childPath = `${path}.${childKey}.${childIndex}`;
        const childId = identity(child, childKey, childPath);
        if (childId !== null) {
          const childKeyValue = String(childId);
          if (childGlobalIds.has(childKeyValue)) errors.push(diagnostic(VALIDATION_CODES.IDENTITY_DUPLICATE, childPath, "Transition child identities must be globally unique.", childKey, childId));
          childGlobalIds.add(childKeyValue);
        }
        if (childKey === "guards") {
          domain(child?.kind, schema.domains.guardKind, `${childPath}.kind`, childKey, childId, VALIDATION_CODES.CHILD_DOMAIN);
          unsigned(child?.payload, byteMax, `${childPath}.payload`, childKey, childId);
          if (Number(child?.kind) === 3) requireRef(child?.referenceId, nodeIds, `${childPath}.referenceId`, childKey, childId, "Effective node");
          if ([4, 5].includes(Number(child?.kind))) requireRef(child?.referenceId, ownerIds, `${childPath}.referenceId`, childKey, childId, "Owner");
          requireBoolean(child?.negate, `${childPath}.negate`, childKey, childId);
        } else if (childKey === "operations") {
          const operationKind = Number(child?.kind);
          domain(operationKind, schema.domains.operationKind, `${childPath}.kind`, childKey, childId, VALIDATION_CODES.CHILD_DOMAIN);
          domain(child?.busyPolicy, schema.domains.busyPolicy, `${childPath}.busyPolicy`, childKey, childId, VALIDATION_CODES.CHILD_DOMAIN);
          if (present(child?.definitionId)) requireRef(child.definitionId, definitionIds, `${childPath}.definitionId`, childKey, childId, "Definition");
          if (present(child?.replacementDefinitionId)) requireRef(child.replacementDefinitionId, definitionIds, `${childPath}.replacementDefinitionId`, childKey, childId, "Replacement definition");
          if (present(child?.ownerId)) requireRef(child.ownerId, ownerIds, `${childPath}.ownerId`, childKey, childId, "Owner");
          unsigned(child?.instanceKey, shortMax, `${childPath}.instanceKey`, childKey, childId, { optional: true, allowDraft: true });
          requireBoolean(child?.required, `${childPath}.required`, childKey, childId);
          if (!zero(child?.flags)) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.flags`, "Operation flags are reserved and must be zero.", childKey, childId));
          const requiredFields = (fieldsToRequire) => fieldsToRequire.forEach((key) => {
            if (zero(child?.[key])) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.${key}`, `${key} is required for this operation kind.`, childKey, childId));
          });
          const zeroFields = (fieldsToClear) => fieldsToClear.forEach((key) => {
            if (!zero(child?.[key])) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.${key}`, `${key} must be zero for this operation kind.`, childKey, childId));
          });
          if (operationKind === 1) {
            requiredFields(["definitionId", "ownerId", "instanceKey"]);
            zeroFields(["replacementDefinitionId", "policyId"]);
          } else if (operationKind === 2) {
            requiredFields(["definitionId", "ownerId", "replacementDefinitionId", "instanceKey"]);
            zeroFields(["policyId"]);
          } else if ([3, 4].includes(operationKind)) {
            requiredFields(["definitionId", "ownerId"]);
            zeroFields(["replacementDefinitionId", "policyId", "instanceKey"]);
          } else if (operationKind === 5) {
            requiredFields(["ownerId"]);
            zeroFields(["definitionId", "replacementDefinitionId", "policyId", "instanceKey"]);
          } else if (operationKind === 6) {
            zeroFields(["definitionId", "ownerId", "replacementDefinitionId", "instanceKey"]);
            if (![1, 2, 3].includes(Number(child?.policyId))) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.policyId`, "Apply-policy operations require lifetime policy 1–3.", childKey, childId));
          }
          if ([1, 2].includes(operationKind) && !same(child?.instanceKey, child?.definitionId)) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.instanceKey`, "Apply/replace instanceKey must equal the source definition identity.", childKey, childId));
          if ([1, 2].includes(operationKind) && !same(child?.ownerId, transition?.ownerId)) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.ownerId`, "Apply/replace operations must use their transition owner.", childKey, childId));
          if ([1, 2].includes(operationKind) && !ownerAuthorized(child?.definitionId, child?.ownerId)) errors.push(diagnostic(VALIDATION_CODES.OWNER_REQUIRED, `${childPath}.ownerId`, "Source definition does not authorize this operation owner.", childKey, childId));
          if (operationKind === 2 && !ownerAuthorized(child?.replacementDefinitionId, child?.ownerId)) errors.push(diagnostic(VALIDATION_CODES.OWNER_REQUIRED, `${childPath}.replacementDefinitionId`, "Replacement definition does not authorize the same operation owner.", childKey, childId));
          const expectedRequired = operationKind === 3;
          if (typeof child?.required === "boolean" && child.required !== expectedRequired) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.required`, `${operationKind === 3 ? "Required removal" : "This operation"} requires required=${expectedRequired}.`, childKey, childId));
          if ([1, 3, 4].includes(operationKind) && !same(child?.definitionId, transition?.candidateDefinitionId)) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.definitionId`, "Apply/remove operations must target their transition candidate definition.", childKey, childId));
          if ([1, 3, 4].includes(operationKind) && !same(child?.ownerId, transition?.ownerId)) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.ownerId`, "Apply/remove operations must use their transition owner.", childKey, childId));
        } else if (childKey === "actions") {
          domain(child?.phase, schema.domains.actionPhase, `${childPath}.phase`, childKey, childId, VALIDATION_CODES.CHILD_DOMAIN);
          domain(child?.kind, schema.domains.actionKind, `${childPath}.kind`, childKey, childId, VALIDATION_CODES.CHILD_DOMAIN);
          unsigned(child?.payload, shortMax, `${childPath}.payload`, childKey, childId);
          if (!zero(child?.referenceId)) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.referenceId`, "Typed action referenceId is reserved and must be zero.", childKey, childId));
          if (!zero(child?.payload)) errors.push(diagnostic(VALIDATION_CODES.CHILD_DOMAIN, `${childPath}.payload`, "Typed action payload is reserved and must be zero.", childKey, childId));
        } else {
          domain(child?.kind, schema.domains.recoveryActionKind, `${childPath}.kind`, childKey, childId, VALIDATION_CODES.CHILD_DOMAIN);
          requireRef(child?.ownerId, ownerIds, `${childPath}.ownerId`, childKey, childId, "Recovery owner");
          requireBoolean(child?.required, `${childPath}.required`, childKey, childId);
        }
      });
    }
  });

  // Dispatch is unique within every controller/role/event scope. Equal
  // priorities are valid only when controller scopes or source-role masks are
  // truly disjoint.
  for (let rightIndex = 0; rightIndex < transitions.length; rightIndex += 1) {
    const right = transitions[rightIndex];
    const rightScope = asArray(right?.controllerIds).map(String);
    for (let leftIndex = 0; leftIndex < rightIndex; leftIndex += 1) {
      const left = transitions[leftIndex];
      if (Number(left?.trigger) !== Number(right?.trigger)
          || Number(left?.dispatchPriority) !== Number(right?.dispatchPriority)
          || !(Number(left?.fromRoleMask) & Number(right?.fromRoleMask))) continue;
      const leftScope = asArray(left?.controllerIds).map(String);
      const scopesOverlap = !leftScope.length || !rightScope.length
        || leftScope.some((value) => rightScope.includes(value));
      if (!scopesOverlap) continue;
      errors.push(diagnostic(
        VALIDATION_CODES.TRANSITION_AMBIGUOUS,
        `transitionGraph.transitions.${rightIndex}.dispatchPriority`,
        `Transition dispatch overlaps ${String(ref(left))} at the same event, role, controller, and priority.`,
        "transition", ref(right),
      ));
    }
  }

  controllers.forEach((controller, index) => {
    const expected = transitions.filter((transition) => asArray(transition?.controllerIds).some((value) => same(value, ref(controller)))).map((transition) => String(ref(transition))).sort();
    const actual = [...new Set(asArray(controller?.transitionIds).map(String))].sort();
    if (expected.length !== actual.length || expected.some((value, itemIndex) => value !== actual[itemIndex])) errors.push(diagnostic(VALIDATION_CODES.TRANSITION_SCOPE, `controllers.${index}.transitionIds`, "Controller transition roster must match graph membership.", "controller", ref(controller)));
  });

  const assignmentActions = asArray(model?.assignmentActions);
  const assignmentActionRefs = new Set();
  assignmentActions.forEach((action, index) => {
    const path = `assignmentActions.${index}`;
    const id = identity(action, "assignmentActions", path);
    if (id !== null) assignmentActionRefs.add(String(id));
    if (Number(action?.kind) !== 1) errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${path}.kind`, "Complete-set assignment actions must use ASSIGN_CONTROLLER kind 1.", "assignmentActions", id));
    if (Number(action?.flags) !== 0) errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${path}.flags`, "Assignment action flags are reserved and must be zero.", "assignmentActions", id));
    const controllerRef = Array.isArray(action?.payload) && action.payload.length >= 2
      ? Number(action.payload[0]) | (Number(action.payload[1]) << 8)
      : action?.payload?.controllerRef;
    requireRef(controllerRef, controllerIds, `${path}.payload.controllerRef`, "assignmentActions", id, "Controller");
  });
  const validateAssignment = (assignment, index, kind) => {
    const path = `${kind}.${index}`;
    const id = identity(assignment, kind, path);
    const actionRef = assignment?.controllerIndex;
    const numericIndex = Number(actionRef);
    const resolves = String(actionRef).startsWith("draft:")
      ? assignmentActionRefs.has(String(actionRef))
      : Number.isInteger(numericIndex) && numericIndex >= 0 && numericIndex < assignmentActions.length;
    if (!resolves) errors.push(diagnostic(VALIDATION_CODES.REFERENCE, `${path}.controllerIndex`, "Assignment action reference does not resolve.", kind, id));
    unsigned(assignment?.dispatchPriority, shortMax, `${path}.dispatchPriority`, kind, id);
    if (kind === "speciesAssignments") {
      if (!Number.isInteger(assignment?.species) || assignment.species < 1 || assignment.species > shortMax) errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${path}.species`, "Species assignment requires species 1–65535.", kind, id));
      return;
    }
    const match = assignment?.match || {};
    unsigned(match.groupMask, wordMax, `${path}.match.groupMask`, kind, id);
    unsigned(match.species, shortMax, `${path}.match.species`, kind, id);
    for (const field of ["terrain", "minimumLevel", "maximumLevel", "shiny", "behaviorClass"]) unsigned(match[field], byteMax, `${path}.match.${field}`, kind, id);
    if (Number(match.maximumLevel) && Number(match.maximumLevel) < Number(match.minimumLevel)) errors.push(diagnostic(VALIDATION_CODES.FIELD_DOMAIN, `${path}.match.maximumLevel`, "Maximum assignment level cannot be below the minimum.", kind, id));
  };
  asArray(model?.genericAssignments).forEach((assignment, index) => validateAssignment(assignment, index, "genericAssignments"));
  asArray(model?.speciesAssignments).forEach((assignment, index) => validateAssignment(assignment, index, "speciesAssignments"));

  return errors;
}

export function validateBehaviorModel(model) {
  return stableDiagnostics(modelDiagnostics(model || {}));
}

export function validateBehaviorDraft(savedModel, draft) {
  return stableDiagnostics([
    ...validateDelta(savedModel || {}, draft),
    ...modelDiagnostics(materializeDraftGraph(savedModel || {}, draft)),
  ]);
}

/** Validate only graph entities referenced by one stack-preview request. */
export function validateStackInput(model, { controllerRef, layers = [], immutableContextMask = 0xFFFFFFFF } = {}) {
  const errors = [];
  const referencedGraphEntities = new Set();
  const schema = schemaFor(model);
  const controller = asArray(model?.controllers).find((item) => same(ref(item), controllerRef));
  if (!controller) errors.push(diagnostic(String(controllerRef).startsWith("draft:") ? VALIDATION_CODES.DRAFT_REFERENCE : VALIDATION_CODES.REFERENCE, "controllerRef", "Selected controller does not exist.", "stack", controllerRef));
  const fields = asArray(model?.stateProfileFields);
  const profiles = new Map(asArray(model?.stateProfiles).map((item) => [String(ref(item)), item]));
  if (controller) {
    const bases = asArray(controller.nodes).filter((node) => node?.base);
    if (bases.length !== 1) errors.push(diagnostic(VALIDATION_CODES.BASE_NODE, "controller.nodes", "Selected controller must have exactly one base node.", "controller", ref(controller)));
    asArray(controller.nodes).forEach((node, index) => {
      const profile = profiles.get(String(node?.profileRef ?? node?.profileStableId));
      if (!profile) errors.push(diagnostic(String(node?.profileRef ?? node?.profileStableId).startsWith("draft:") ? VALIDATION_CODES.DRAFT_REFERENCE : VALIDATION_CODES.REFERENCE, `controller.nodes.${index}.profileRef`, "Referenced state profile does not exist.", "controllerNode", ref(node)));
      else {
        referencedGraphEntities.add(`stateProfile:${String(ref(profile))}`);
        const keys = Object.keys(profile.values || {});
        if (keys.length !== fields.length || fields.some((field) => !keys.includes(field.key))) errors.push(diagnostic(VALIDATION_CODES.PROFILE_FIELDS, `controller.nodes.${index}.profile.values`, "Referenced profile is not one complete typed state.", "stateProfile", ref(profile)));
      }
    });
  }
  if (!Array.isArray(layers)) errors.push(diagnostic(VALIDATION_CODES.DRAFT_TRANSACTION, "layers", "Preview layers must be an array.", "stack", "stack"));
  if (asArray(layers).length > Number(model?.stackPreview?.capacity ?? schema.stackCapacity)) errors.push(diagnostic(VALIDATION_CODES.STACK_CAPACITY, "layers", `Runtime stack capacity is ${model?.stackPreview?.capacity ?? schema.stackCapacity}.`, "stack", "stack"));
  if (!Number.isInteger(immutableContextMask) || immutableContextMask < 0 || immutableContextMask > Number(schema.unsigned.word)) errors.push(diagnostic(VALIDATION_CODES.WIRE_RANGE, "immutableContextMask", "Immutable context mask must be an unsigned 32-bit integer.", "stack", "stack"));
  const definitions = new Map(asArray(model?.overrideDefinitions).map((item) => [String(ref(item)), item]));
  const owners = new Map(asArray(model?.owners).map((item) => [String(ref(item)), item]));
  const applicability = new Map(asArray(model?.applicability).map((item) => [String(ref(item)), item]));
  const layerIdentities = new Set();
  const perDefinition = new Map();
  asArray(layers).forEach((layer, index) => {
    const path = `layers.${index}`;
    const definition = definitions.get(String(layer?.definitionId));
    const owner = owners.get(String(layer?.ownerId));
    if (String(layer?.definitionId || "").startsWith("draft:")) errors.push(diagnostic(VALIDATION_CODES.DRAFT_REFERENCE, `${path}.definitionId`, "Unallocated draft definitions have no runtime precedence key.", "stackLayer", index));
    if (String(layer?.ownerId || "").startsWith("draft:")) errors.push(diagnostic(VALIDATION_CODES.DRAFT_REFERENCE, `${path}.ownerId`, "Unallocated draft owners have no runtime precedence key.", "stackLayer", index));
    if (definition) referencedGraphEntities.add(`overrideDefinition:${String(ref(definition))}`);
    if (Number(definition?.kind) === 2) asArray(model?.modifierOperations)
      .filter((operation) => same(operation?.definitionId, ref(definition)))
      .forEach((operation) => referencedGraphEntities.add(`modifierOperation:${String(ref(operation))}`));
    if (!definition) errors.push(diagnostic(String(layer?.definitionId).startsWith("draft:") ? VALIDATION_CODES.DRAFT_REFERENCE : VALIDATION_CODES.REFERENCE, `${path}.definitionId`, "Layer definition does not exist.", "stackLayer", index));
    if (!owner) errors.push(diagnostic(String(layer?.ownerId).startsWith("draft:") ? VALIDATION_CODES.DRAFT_REFERENCE : VALIDATION_CODES.REFERENCE, `${path}.ownerId`, "Layer owner does not exist.", "stackLayer", index));
    if (definition && !applicability.has(String(definition.applicabilityId))) errors.push(diagnostic(VALIDATION_CODES.REFERENCE, `${path}.applicabilityId`, "Definition applicability does not exist.", "stackLayer", index));
    const instanceKey = Number(layer?.instanceKey);
    const numericShape = typeof layer?.instanceKey === "number" || (typeof layer?.instanceKey === "string" && /^\d+$/.test(layer.instanceKey));
    if (!numericShape || !Number.isInteger(instanceKey) || instanceKey < 0 || instanceKey > Number(schema.unsigned.short)) errors.push(diagnostic(VALIDATION_CODES.STACK_INSTANCE, `${path}.instanceKey`, "Instance key must be an unsigned 16-bit integer.", "stackLayer", index));
    if (definition && !definition.allowMultipleInstancesPerOwner && instanceKey !== 0) errors.push(diagnostic(VALIDATION_CODES.STACK_INSTANCE, `${path}.instanceKey`, "Single-instance definitions require instance key 0.", "stackLayer", index));
    const identityKey = `${String(layer?.ownerId)}:${instanceKey}`;
    if (layerIdentities.has(identityKey)) errors.push(diagnostic(VALIDATION_CODES.STACK_IDENTITY, path, "Owner and instance key must identify one layer.", "stackLayer", index));
    layerIdentities.add(identityKey);
    if (definition?.hasRequiredOwnerId && !same(definition.requiredOwnerId, layer?.ownerId)) errors.push(diagnostic(VALIDATION_CODES.OWNER_REQUIRED, `${path}.ownerId`, "Layer owner does not match the required owner.", "stackLayer", index));
    const siblings = perDefinition.get(String(layer?.definitionId)) || [];
    if (definition && !definition.allowMultipleOwners && siblings.some((item) => !same(item.ownerId, layer?.ownerId))) errors.push(diagnostic(VALIDATION_CODES.OWNER_MULTIPLICITY, path, "Definition does not allow multiple owners.", "stackLayer", index));
    if (definition && !definition.allowMultipleInstancesPerOwner && siblings.some((item) => same(item.ownerId, layer?.ownerId) && item.instanceKey !== instanceKey)) errors.push(diagnostic(VALIDATION_CODES.INSTANCE_MULTIPLICITY, path, "Definition does not allow multiple instances for one owner.", "stackLayer", index));
    siblings.push({ ownerId: layer?.ownerId, instanceKey });
    perDefinition.set(String(layer?.definitionId), siblings);
    const scopedController = definition?.controllerId ?? applicability.get(String(definition?.applicabilityId))?.controllerId;
    if (definition && controller && nonzeroRef(scopedController) && !same(scopedController, ref(controller))) return;
    if (definition && Number(definition.kind) === 1 && controller && Number(definition.selectorKind) === 1 && !asArray(controller.nodes).some((node) => same(ref(node), definition.nodeId))) errors.push(diagnostic(VALIDATION_CODES.REFERENCE, `${path}.selector`, "Exact selector does not resolve in the selected controller.", "stackLayer", index));
    if (definition && Number(definition.kind) === 1 && controller && Number(definition.selectorKind) === 2) {
      const matches = asArray(controller.nodes).filter((node) => Number(node.semanticRoleId) === Number(definition.semanticRoleId));
      if (matches.length !== 1) errors.push(diagnostic(matches.length ? VALIDATION_CODES.SELECTOR_DUPLICATE : VALIDATION_CODES.REFERENCE, `${path}.selector`, "Semantic selector must resolve exactly once in the selected controller.", "stackLayer", index));
    }
  });
  // Reuse the authoritative whole-graph contracts for the saved/draft
  // entities that this preview can actually resolve. The validator is pure,
  // so this never changes the preview model or its caller's draft.
  for (const item of modelDiagnostics(model || {})) {
    if (item.severity !== "warning" && referencedGraphEntities.has(`${item.entityType}:${item.entityId}`)) errors.push(item);
  }
  return stableDiagnostics(errors);
}
