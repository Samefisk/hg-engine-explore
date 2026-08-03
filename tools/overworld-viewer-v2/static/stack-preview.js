/* Deterministic, client-only OWBD V40 stack preview. */

import { materializeDraftGraph, validateStackInput, VALIDATION_CODES } from "./model-validation.js";

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
});

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
  let controllerRef = ref(model.controllers?.[0]) || "";
  let layers = [];
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
    ({ controllerRef, layers } = preserveStackPreviewSelection(current, controllerRef, layers));
  }

  function renderControls() {
    normalizeSelection();
    const current = activeModel();
    controls.innerHTML = `<label class="compact-field"><span>Source</span><select data-stack-mode><option value="saved" ${mode === "saved" ? "selected" : ""}>Saved</option><option value="draft" ${mode === "draft" ? "selected" : ""}>Draft</option><option value="compare" ${mode === "compare" ? "selected" : ""}>Saved ↔ Draft</option></select></label>
      <label class="compact-field"><span>Controller</span><select data-stack-controller>${options(current.controllers || [], controllerRef, (controller) => controller.name || `Controller ${ref(controller)}`)}</select></label>
      <div class="stack-preview-layers"><header><strong>Override layers</strong><small>${layers.length} / ${current.stackPreview?.capacity || 8}</small></header>${layers.map((layer, index) => `<div class="stack-preview-layer" data-stack-layer="${index}"><select data-stack-definition="${index}" aria-label="Definition">${options(current.overrideDefinitions || [], layer.definitionId, (definition) => `${definition.name || `Definition ${ref(definition)}`} · ${definition.channelLabel}`)}</select><select data-stack-owner="${index}" aria-label="Owner">${options(current.owners || [], layer.ownerId, (owner) => owner.name || `Owner ${ref(owner)}`)}</select><input type="number" min="0" max="65535" value="${layer.instanceKey}" data-stack-instance="${index}" aria-label="Instance key"><button type="button" data-stack-remove="${index}" aria-label="Remove layer">×</button></div>`).join("") || `<p>No overrides. The controller base state wins.</p>`}<button class="button" type="button" data-stack-add ${layers.length >= Number(current.stackPreview?.capacity || 8) ? "disabled" : ""}>Add layer</button></div>`;
  }

  function renderResult() {
    const preview = composeStackPreview({ model, draft: getDraft(), mode, controllerRef, layers });
    if (!preview.ok) {
      resolution.innerHTML = `<header class="panel-heading"><span><small>Deterministic preview</small><strong>Cannot compose</strong></span><span class="result-chip">${preview.errors.length} issue${preview.errors.length === 1 ? "" : "s"}</span></header><div class="stack-preview-errors">${preview.errors.map((error) => `<p><strong>${escapeHtml(error.code)}</strong><span>${escapeHtml(error.message)}</span></p>`).join("")}</div>`;
      return;
    }
    const result = preview.result;
    const layerRows = result.layers.map((layer) => `<tr><td>${escapeHtml(layer.definitionId)}</td><td>${escapeHtml(layer.ownerId)} / ${escapeHtml(layer.instanceKey)}</td><td><span class="stack-status stack-status--${escapeHtml(layer.visibility)}">${escapeHtml(layer.visibility)}</span></td><td>${escapeHtml(layer.timer.status)}</td><td>${escapeHtml(layer.lifetime.map.label || layer.lifetime.map.value)} / ${escapeHtml(layer.lifetime.battle.label || layer.lifetime.battle.value)}</td></tr>`).join("");
    const fieldRows = Object.entries(result.fields).map(([key, item]) => `<tr><td>${escapeHtml(key)}</td><td>${escapeHtml(item.value)}</td><td>${escapeHtml(item.provenance.kind)} · profile ${escapeHtml(item.provenance.profileId)}</td></tr>`).join("");
    resolution.innerHTML = `<header class="panel-heading"><span><small>Deterministic preview</small><strong>Effective state</strong></span><span class="result-chip">${preview.comparison ? (preview.comparison.changed ? "Changed" : "Same") : "Resolved"}</span></header><section class="stack-preview-result"><div class="stack-preview-identity"><span>Controller</span><strong>${escapeHtml(result.identity.controllerId)}</strong><span>Node / profile / role</span><strong>${escapeHtml(result.identity.nodeId)} / ${escapeHtml(result.identity.profileId)} / ${escapeHtml(result.identity.semanticRoleId)}</strong></div><h3>Layers</h3><table><thead><tr><th>Definition</th><th>Owner / key</th><th>Status</th><th>Timer</th><th>Map / battle</th></tr></thead><tbody>${layerRows || `<tr><td colspan="5">Base state only</td></tr>`}</tbody></table><details><summary>Complete field provenance (${Object.keys(result.fields).length})</summary><table><thead><tr><th>Field</th><th>Value</th><th>Source</th></tr></thead><tbody>${fieldRows}</tbody></table></details><details><summary>Controller and policy provenance</summary><pre>${escapeHtml(JSON.stringify({ scalars: result.controllerScalars, policies: result.policies }, null, 2))}</pre></details></section>`;
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
  }
  function onChange(event) {
    if (event.target.matches("[data-stack-mode]")) mode = event.target.value;
    else if (event.target.matches("[data-stack-controller]")) controllerRef = event.target.value;
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
    result: () => composeStackPreview({ model, draft: getDraft(), mode, controllerRef, layers: clone(layers) }),
    destroy: () => {
      if (destroyed) return;
      destroyed = true;
      workbench.removeEventListener("click", onClick);
      workbench.removeEventListener("change", onChange);
    },
  });
}
