import { createProfilesController } from "/v2-assets/profiles.js";
import { createRoutesController } from "/v2-assets/routes.js";
import { createSoundsController } from "/v2-assets/routes-sounds.js";
import { createPokemonController } from "/v2-assets/pokemon.js";

const WORKSPACE_VIEWS = ["pokemon", "profiles", "routes", "sounds"];
const NAVIGATION_CONTEXT_KEY = "ow-v2-navigation-context";
const POKEMON_SELECTION_KEY = "ow-v2-pokemon-selection";

const state = {
  data: null,
  revision: "",
  conflict: false,
  busy: false,
  commitInert: false,
  activeView: localStorage.getItem("ow-v2-view") || "profiles",
  controllers: {},
  navigationContext: null,
  applyingLocation: false,
};

let pokemonSelectionKey = (() => {
  const stored = localStorage.getItem(POKEMON_SELECTION_KEY);
  if (!stored) return "";
  try { return String(JSON.parse(stored) || ""); } catch (_error) { return stored; }
})();
Object.defineProperty(state, "selectedPokemonKey", {
  enumerable: true,
  get: () => pokemonSelectionKey,
  set(value) {
    const next = String(value || "");
    if (next === pokemonSelectionKey) return;
    pokemonSelectionKey = next;
    if (next) localStorage.setItem(POKEMON_SELECTION_KEY, JSON.stringify(next));
    if (state.activeView === "pokemon" && !state.applyingLocation) {
      reportSelection("pokemon", next, humanizeSpecies(next));
    }
  },
});

const MUTATION_PATHS = new Set([
  "/save-profiles",
  "/save-profile-memberships",
  "/manage-profiles",
  "/save-profile-overrides",
  "/save-encounters",
  "/save-spawn-settings",
]);

function byId(id) {
  const element = document.getElementById(id);
  if (!element) throw new Error(`V2 shell is missing #${id}`);
  return element;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

const elements = {};
[
  "app", "appHeader", "workspaceNav", "globalStatus", "pendingCount",
  "saveAll", "resetDraft", "buildRom", "openNds", "restartServer",
  "autoBuild", "autoRun", "showBuildLog", "buildPanel", "buildOutput",
  "pokemonView", "pokemonSearch", "pokemonTypeFilter", "pokemonStateFilter",
  "pokemonLibrary", "pokemonLibraryCount", "pokemonInspector",
  "profilesView", "profileSearch", "profileKindFilter", "profileLibrary",
  "profileContextSpecies", "profileContextTerrain", "profileContextLevel",
  "profileContextShiny", "resolveContext", "profileResolution", "profileInspector",
  "profileWorkbench", "profileResolverDrawer", "openProfileResolver", "closeProfileResolver",
  "routesView", "routeSearch", "routeFilters", "routeLibrary", "routeInspector",
  "soundsView", "soundSearch", "soundFilters", "soundLibrary", "soundInspector",
  "soundStatus", "shinyCounter", "refreshShiny", "resetShiny", "maxShiny",
  "reservedShinies", "toastRegion", "confirmDialog", "deckContextBar",
  "returnToDeck", "clearDeckContext", "deckContextLabel", "commitStatus",
  "commitStatusHeading", "commitStatusDetail",
].forEach((id) => { elements[id] = byId(id); });

function messageFromResult(result, response) {
  return result?.error || result?.message || `HTTP ${response.status}`;
}

const api = {
  async get(path, options = {}) {
    const response = await fetch(path, { cache: "no-store", ...options });
    const result = await response.json();
    if (!response.ok) throw new Error(messageFromResult(result, response));
    return result;
  },

  async post(path, payload = {}, options = {}) {
    const headers = new Headers({ "Content-Type": "application/json", ...(options.headers || {}) });
    if (MUTATION_PATHS.has(path)) {
      if (state.conflict) throw new Error("Sources changed. Reload before saving this draft.");
      if (!state.revision) throw new Error("The workspace revision is not loaded yet.");
      headers.set("If-Match", state.revision);
    }
    const response = await fetch(path, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (response.status === 409) {
      state.conflict = true;
      setStatus("Sources changed outside this editor. Reload before saving.", "error");
    }
    if (!response.ok) throw new Error(messageFromResult(result, response));
    if (result.sourceRevision) state.revision = result.sourceRevision;
    return result;
  },

  resolve(params) {
    return this.get(`/api/v2/resolve?${new URLSearchParams(params)}`);
  },
};

function setStatus(message, kind = "ready") {
  const heading = elements.globalStatus.querySelector("strong");
  const detail = elements.globalStatus.querySelector("small");
  if (heading) heading.textContent = message || "Source ready";
  else elements.globalStatus.textContent = message || "Source ready";
  if (detail) {
    const details = {
      ready: "Revision checking on",
      pending: "Review before save",
      busy: "Keep this window open",
      success: "Workspace synchronized",
      error: "Draft preserved; action required",
    };
    detail.textContent = details[kind] || "Workspace status";
  }
  elements.globalStatus.dataset.kind = kind;
  elements.app.dataset.status = kind;
}

function toast(message, kind = "info") {
  const item = document.createElement("div");
  item.className = "toast";
  item.dataset.kind = kind;
  item.textContent = message;
  elements.toastRegion.append(item);
  window.setTimeout(() => item.remove(), 4200);
}

let commitStatusTimer = 0;

function showCommitStatus(message, detail, kind = "busy", { dismissAfter = 0 } = {}) {
  window.clearTimeout(commitStatusTimer);
  commitStatusTimer = 0;
  elements.commitStatus.dataset.kind = kind;
  elements.commitStatus.classList.add("is-visible");
  elements.commitStatusHeading.textContent = message;
  elements.commitStatusDetail.textContent = detail;
  if (dismissAfter > 0) {
    commitStatusTimer = window.setTimeout(() => {
      elements.commitStatus.classList.remove("is-visible");
      elements.commitStatusHeading.textContent = "";
      elements.commitStatusDetail.textContent = "";
      commitStatusTimer = 0;
    }, dismissAfter);
  }
}

function totalChangeCount() {
  return Object.values(state.controllers).reduce(
    (total, controller) => {
      const count = typeof controller?.changeCount === "function"
        ? controller.changeCount()
        : controller?.changeCount;
      return total + (Number(count) || 0);
    },
    0
  );
}

function totalValidationCount() {
  return Object.values(state.controllers).reduce((total, controller) => {
    const count = typeof controller?.validationCount === "function"
      ? controller.validationCount()
      : (typeof controller?.hasInvalid === "function" && controller.hasInvalid() ? 1 : 0);
    return total + (Number(count) || 0);
  }, 0);
}

function firstValidationMessage() {
  for (const controller of Object.values(state.controllers)) {
    if (typeof controller?.validationMessage !== "function") continue;
    const message = controller.validationMessage();
    if (message) return message;
  }
  return "Fix invalid draft values before saving.";
}

function firstValidationOwner() {
  return Object.entries(state.controllers).find(([, controller]) => {
    const count = typeof controller?.validationCount === "function"
      ? controller.validationCount()
      : (typeof controller?.hasInvalid === "function" && controller.hasInvalid() ? 1 : 0);
    return Number(count) > 0;
  }) || null;
}

function totalBlockingCount() {
  return Object.values(state.controllers).reduce((total, controller) => {
    const count = typeof controller?.blockingCount === "function"
      ? controller.blockingCount()
      : (typeof controller?.isBlocking === "function" && controller.isBlocking() ? 1 : 0);
    return total + (Number(count) || 0);
  }, 0);
}

function firstBlockingMessage() {
  for (const controller of Object.values(state.controllers)) {
    if (typeof controller?.blockingMessage !== "function") continue;
    const message = controller.blockingMessage();
    if (message) return message;
  }
  return "Wait for pending validation or upload work to finish before saving.";
}

function firstBlockingOwner() {
  return Object.entries(state.controllers).find(([, controller]) => {
    const count = typeof controller?.blockingCount === "function"
      ? controller.blockingCount()
      : (typeof controller?.isBlocking === "function" && controller.isBlocking() ? 1 : 0);
    return Number(count) > 0;
  }) || null;
}

function markDirty() {
  const count = totalChangeCount();
  const validationCount = totalValidationCount();
  const blockingCount = totalBlockingCount();
  elements.pendingCount.textContent = String(count);
  elements.pendingCount.setAttribute(
    "aria-label",
    `${count} pending change${count === 1 ? "" : "s"}`
  );
  elements.pendingCount.hidden = count === 0;
  elements.saveAll.disabled = state.busy || state.conflict || count === 0 || validationCount > 0 || blockingCount > 0;
  if (blockingCount > 0 && !validationCount) elements.saveAll.title = firstBlockingMessage();
  else elements.saveAll.removeAttribute("title");
  elements.resetDraft.disabled = state.busy || (count === 0 && validationCount === 0);
  if (validationCount > 0 && !state.busy) {
    setStatus(`${validationCount} invalid draft value${validationCount === 1 ? "" : "s"} · ${firstValidationMessage()}`, "error");
  } else if (blockingCount > 0 && !state.busy) {
    setStatus(`${blockingCount} pending asset operation${blockingCount === 1 ? "" : "s"} · ${firstBlockingMessage()}`, "busy");
  } else if (count > 0 && !state.busy) {
    setStatus(`${count} draft change${count === 1 ? "" : "s"}`, "pending");
  }
  if (count === 0 && validationCount === 0 && blockingCount === 0 && !state.busy && !state.conflict) setStatus("Source ready", "ready");
}

const COMMIT_GUARDED_EVENTS = ["click", "pointerdown", "keydown", "input", "change", "drop", "dragover", "submit", "focusin"];
let commitFocusReturn = null;

function commitFocusDescriptor(element) {
  if (!(element instanceof HTMLElement) || !elements.app.contains(element)) return null;
  let selector = "";
  if (element.id) selector = `#${CSS.escape(element.id)}`;
  else {
    const attribute = [
      "data-pokemon-field", "data-pokemon-combobox", "data-asset-file",
      "data-asset-drop-slot", "data-asset-revert", "data-view",
    ].find((name) => element.hasAttribute(name));
    if (attribute) selector = `[${attribute}="${CSS.escape(element.getAttribute(attribute))}"]`;
  }
  return { element, selector };
}

function guardCommitInteraction(event) {
  if (!state.commitInert) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  if (event.type === "focusin" && event.target instanceof HTMLElement) event.target.blur();
}

function visibleEnabledFocusTarget(element) {
  if (!(element instanceof HTMLElement) || !element.isConnected || element.matches(":disabled")) return null;
  if (element.closest("[hidden], [aria-hidden='true'], [inert]")) return null;
  const style = getComputedStyle(element);
  if (style.display === "none" || style.visibility === "hidden" || element.getClientRects().length === 0) return null;
  return element;
}

function activeWorkspaceFocusTarget() {
  const view = elements[`${state.activeView}View`];
  const target = visibleEnabledFocusTarget(view);
  if (target) target.tabIndex = -1;
  return target;
}

function setWorkspaceInert(inert) {
  if (inert === state.commitInert) return;
  if (inert) {
    commitFocusReturn = commitFocusDescriptor(document.activeElement);
    state.commitInert = true;
    elements.app.inert = true;
    elements.app.setAttribute("inert", "");
    elements.app.setAttribute("aria-busy", "true");
    elements.app.classList.add("is-commit-inert");
    COMMIT_GUARDED_EVENTS.forEach((type) => document.addEventListener(type, guardCommitInteraction, true));
    return;
  }
  state.commitInert = false;
  elements.app.inert = false;
  elements.app.removeAttribute("inert");
  elements.app.classList.remove("is-commit-inert");
  COMMIT_GUARDED_EVENTS.forEach((type) => document.removeEventListener(type, guardCommitInteraction, true));
  const descriptor = commitFocusReturn;
  commitFocusReturn = null;
  requestAnimationFrame(() => {
    const original = visibleEnabledFocusTarget(descriptor?.element);
    const remounted = !original && descriptor?.selector
      ? visibleEnabledFocusTarget(elements.app.querySelector(descriptor.selector))
      : null;
    const focusTarget = original || remounted || activeWorkspaceFocusTarget();
    focusTarget?.focus?.({ preventScroll: true });
  });
}

function setBusy(busy, { inert = false } = {}) {
  if (busy && inert) setWorkspaceInert(true);
  state.busy = busy;
  elements.app.toggleAttribute("aria-busy", busy);
  [elements.saveAll, elements.resetDraft, elements.buildRom, elements.openNds]
    .forEach((control) => { control.disabled = busy; });
  markDirty();
  if (!busy && state.commitInert) setWorkspaceInert(false);
}

function confirmAction(config = {}) {
  const normalized = typeof config === "string" ? { message: config } : config;
  const {
    title = "Confirm action",
    message = "Continue?",
    confirmLabel = "Continue",
    danger = false,
  } = normalized;
  const dialog = elements.confirmDialog;
  dialog.querySelector("#confirmTitle").textContent = title;
  dialog.querySelector("#confirmMessage").textContent = message;
  const accept = dialog.querySelector("[data-confirm-accept]");
  accept.textContent = confirmLabel;
  accept.classList.toggle("button--danger", danger);
  accept.classList.toggle("button--primary", !danger);
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true });
    dialog.showModal();
  });
}

function humanizeSpecies(symbol) {
  return String(symbol || "Pokémon")
    .replace(/^SPECIES_/, "")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function validPokemonSymbol(symbol) {
  const value = String(symbol || "");
  return /^SPECIES_[A-Z0-9_]+$/.test(value)
    && !["SPECIES_NONE", "SPECIES_EGG", "SPECIES_BAD_EGG"].includes(value)
    && !/^SPECIES_\d+$/.test(value);
}

function readNavigationContext() {
  try {
    const context = JSON.parse(sessionStorage.getItem(NAVIGATION_CONTEXT_KEY) || "null");
    return context && WORKSPACE_VIEWS.includes(context.originView) ? context : null;
  } catch (_error) {
    return null;
  }
}

function storeNavigationContext(context) {
  state.navigationContext = context;
  try {
    if (context) sessionStorage.setItem(NAVIGATION_CONTEXT_KEY, JSON.stringify(context));
    else sessionStorage.removeItem(NAVIGATION_CONTEXT_KEY);
  } catch (_error) {
    // Cross-deck context is helpful, but storage restrictions are non-fatal.
  }
  renderNavigationContext();
}

function renderNavigationContext() {
  const context = state.navigationContext;
  const visible = state.activeView === "pokemon" && context?.originView && context.originView !== "pokemon";
  elements.deckContextBar.hidden = !visible;
  if (!visible) return;
  const originName = `${context.originView[0].toUpperCase()}${context.originView.slice(1)}`;
  elements.deckContextLabel.textContent = context.originLabel
    ? `${originName} · ${context.originLabel}`
    : `${originName} deck`;
  elements.returnToDeck.setAttribute("aria-label", `Return to ${elements.deckContextLabel.textContent}`);
}

function locationDescriptor() {
  const raw = location.hash.replace(/^#/, "");
  if (!raw) return null;
  const [path, query = ""] = raw.split("?", 2);
  const [view, encodedSelection = ""] = path.split("/", 2);
  if (!WORKSPACE_VIEWS.includes(view)) return null;
  const params = new URLSearchParams(query);
  try {
    return {
      view,
      selection: encodedSelection ? decodeURIComponent(encodedSelection) : "",
      originView: params.get("from") || "",
      originSelection: params.get("origin") || "",
      originLabel: params.get("label") || "",
    };
  } catch (_error) {
    return null;
  }
}

function hashFor(view, selection = "") {
  const path = `#${view}${selection ? `/${encodeURIComponent(selection)}` : ""}`;
  if (view !== "pokemon" || !state.navigationContext) return path;
  const params = new URLSearchParams();
  params.set("from", state.navigationContext.originView);
  if (state.navigationContext.originSelection) params.set("origin", state.navigationContext.originSelection);
  if (state.navigationContext.originLabel) params.set("label", state.navigationContext.originLabel);
  return `${path}?${params}`;
}

function writeLocation(view, selection = "", mode = "replace") {
  if (state.applyingLocation) return;
  const hash = hashFor(view, selection);
  if (location.hash === hash) return;
  history[mode === "push" ? "pushState" : "replaceState"]({ view, selection }, "", hash);
}

function reportSelection(view, selection = "", label = "") {
  if (!WORKSPACE_VIEWS.includes(view)) return;
  state.deckSelections ||= {};
  state.deckSelections[view] = { selection: String(selection || ""), label: String(label || "") };
  if (state.activeView === view) writeLocation(view, selection, "replace");
}

function controllerSelection(view) {
  const controller = state.controllers[view];
  const selection = controller?.navigationContext?.();
  if (selection) return selection;
  return state.deckSelections?.[view] || { selection: "", label: "" };
}

function activateView(view, { historyMode = "none", selection = "", focus = false } = {}) {
  state.activeView = WORKSPACE_VIEWS.includes(view) ? view : "profiles";
  localStorage.setItem("ow-v2-view", state.activeView);
  elements.app.dataset.view = state.activeView;
  elements.workspaceNav.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === state.activeView;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
  });
  WORKSPACE_VIEWS.forEach((name) => {
    const viewElement = elements[`${name}View`];
    viewElement.hidden = name !== state.activeView;
    viewElement.classList.toggle("is-active", name === state.activeView);
  });
  renderNavigationContext();
  if (selection && state.activeView !== "pokemon") {
    state.controllers[state.activeView]?.restoreSelection?.(selection, { focus });
  }
  if (historyMode !== "none") {
    const current = state.activeView === "pokemon"
      ? state.selectedPokemonKey
      : controllerSelection(state.activeView).selection;
    writeLocation(state.activeView, current, historyMode);
  }
  if (focus) {
    const viewElement = elements[`${state.activeView}View`];
    viewElement.tabIndex = -1;
    requestAnimationFrame(() => viewElement.focus({ preventScroll: true }));
  }
}

function bindNavigation() {
  elements.workspaceNav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-view]");
    if (button) {
      if (button.dataset.view !== "pokemon") storeNavigationContext(null);
      activateView(button.dataset.view, { historyMode: "push", focus: true });
    }
  });
  elements.workspaceNav.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = [...elements.workspaceNav.querySelectorAll("[data-view]")];
    const current = tabs.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? tabs.length - 1
        : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    const next = tabs[nextIndex];
    if (next.dataset.view !== "pokemon") storeNavigationContext(null);
    activateView(next.dataset.view, { historyMode: "push" });
    next.focus();
  });
  elements.returnToDeck.addEventListener("click", returnToOrigin);
  elements.clearDeckContext.addEventListener("click", () => {
    storeNavigationContext(null);
    writeLocation("pokemon", state.selectedPokemonKey, "replace");
  });
  window.addEventListener("hashchange", () => applyLocation(locationDescriptor()));
}

function controllerContext() {
  return {
    state,
    api,
    elements,
    setStatus,
    markDirty,
    confirmAction,
    toast,
    reportSelection,
    openPokemonRecord,
  };
}

function ensurePokemonController() {
  if (!state.controllers.pokemon) {
    state.controllers.pokemon = createPokemonController(controllerContext());
  }
  return state.controllers.pokemon;
}

function rebuildPokemonController(symbol) {
  state.selectedPokemonKey = symbol;
  localStorage.setItem(POKEMON_SELECTION_KEY, JSON.stringify(symbol));
  const current = state.controllers.pokemon;
  if (typeof current?.openRecord === "function") {
    current.openRecord(symbol, { focus: true });
    return current;
  }
  current?.destroy?.();
  delete state.controllers.pokemon;
  const controller = ensurePokemonController();
  Promise.resolve(controller.refresh?.(state.data)).catch((error) => {
    setStatus(`Pokémon Editor could not open ${humanizeSpecies(symbol)}: ${error.message}`, "error");
  });
  return controller;
}

function openPokemonRecord(symbol, origin = {}) {
  const normalized = String(symbol || "").trim().toUpperCase();
  if (!validPokemonSymbol(normalized)) {
    setStatus("That Pokémon record does not have a source symbol.", "error");
    return false;
  }
  const sourceView = WORKSPACE_VIEWS.includes(origin.view) ? origin.view : state.activeView;
  const snapshot = controllerSelection(sourceView);
  if (sourceView !== "pokemon") {
    storeNavigationContext({
      originView: sourceView,
      originSelection: String(origin.selection ?? snapshot.selection ?? ""),
      originLabel: String(origin.label ?? snapshot.label ?? ""),
      pokemonSymbol: normalized,
    });
  }
  rebuildPokemonController(normalized);
  activateView("pokemon");
  writeLocation("pokemon", normalized, "push");
  setStatus(`Opened ${humanizeSpecies(normalized)} in Pokémon Editor`, "ready");
  return true;
}

function returnToOrigin() {
  const context = state.navigationContext;
  if (!context?.originView) return;
  const { originView, originSelection } = context;
  storeNavigationContext(null);
  activateView(originView, { selection: originSelection, focus: true });
  writeLocation(originView, originSelection, "push");
}

function applyLocation(descriptor) {
  if (!descriptor) return;
  state.applyingLocation = true;
  try {
    if (descriptor.view === "pokemon") {
      if (descriptor.originView && descriptor.originView !== "pokemon") {
        storeNavigationContext({
          originView: descriptor.originView,
          originSelection: descriptor.originSelection,
          originLabel: descriptor.originLabel,
          pokemonSymbol: descriptor.selection,
        });
      } else {
        storeNavigationContext(null);
      }
      if (validPokemonSymbol(descriptor.selection) && descriptor.selection !== state.selectedPokemonKey) {
        rebuildPokemonController(descriptor.selection);
      }
      activateView("pokemon");
    } else {
      storeNavigationContext(null);
      activateView(descriptor.view, { selection: descriptor.selection });
    }
  } finally {
    state.applyingLocation = false;
  }
}

function ensureLegacyControllers() {
  if (!state.controllers.profiles) {
    state.controllers.profiles = createProfilesController(controllerContext());
    state.controllers.routes = createRoutesController(controllerContext());
    state.controllers.sounds = createSoundsController(controllerContext());
  }
}

async function loadData({ keepStatus = false } = {}) {
  if (!keepStatus) setStatus("Loading workspace…", "busy");
  const data = await api.get(`/data.json?ts=${Date.now()}`);
  if (!data.sourceRevision) throw new Error("V2 data did not include a source revision.");

  if (state.revision && data.sourceRevision !== state.revision && totalChangeCount() > 0) {
    state.conflict = true;
    throw new Error("Sources changed while this draft was open. Reload before saving.");
  }
  state.data = data;
  state.revision = data.sourceRevision;
  state.conflict = false;

  ensureLegacyControllers();
  await Promise.resolve(ensurePokemonController().refresh?.(data)).catch((error) => {
    setStatus(`Pokémon Editor failed to refresh: ${error.message}`, "error");
  });
  ["profiles", "routes", "sounds"].forEach((name) => state.controllers[name]?.refresh?.(data));
  markDirty();
}

function renderShellLoadError(error) {
  const message = String(error?.message || error || "Unknown workspace request failure");
  [elements.profileLibrary, elements.routeLibrary, elements.soundLibrary].forEach((container) => {
    if (!container?.querySelector(".loading-card, .loading-row")) return;
    container.innerHTML = `<div class="shell-error-state" role="alert"><strong>Workspace data unavailable</strong><p>${escapeHtml(message)}</p><button class="button" type="button" data-shell-retry>Retry</button></div>`;
  });
}

function collectCommitDomains() {
  const domains = {};
  const owners = new Map();
  Object.entries(state.controllers).forEach(([controllerName, controller]) => {
    const payload = controller?.commitPayload?.() || {};
    if (typeof payload !== "object" || Array.isArray(payload)) {
      throw new TypeError(`${controllerName} returned an invalid commit payload.`);
    }
    Object.entries(payload).forEach(([domain, value]) => {
      if (value == null) return;
      if (Object.prototype.hasOwnProperty.call(domains, domain)) {
        throw new Error(`Commit domain "${domain}" is owned by both ${owners.get(domain)} and ${controllerName}.`);
      }
      domains[domain] = value;
      owners.set(domain, controllerName);
    });
  });
  return domains;
}

function commitFeedback(result) {
  const assetResult = result?.domains?.pokemonAssetUpdates || {};
  const changedAssets = Number(assetResult.changedAssets) || 0;
  const identicalAssets = Number(assetResult.unchangedAssets) || 0;
  const changedDomains = Array.isArray(result?.changedDomains) ? result.changedDomains : [];
  if (!result?.saved) {
    const message = identicalAssets > 0
      ? `No source changes — ${identicalAssets === 1 ? "identical asset" : `${identicalAssets} identical assets`} skipped`
      : "No source changes";
    return { message, toastMessage: message, kind: "ready", toastKind: "info", saved: false };
  }

  const clauses = [];
  const nonAssetDomains = changedDomains.filter((domain) => domain !== "pokemonAssetUpdates").length;
  if (nonAssetDomains > 0) clauses.push(`${nonAssetDomains} source domain${nonAssetDomains === 1 ? "" : "s"} changed`);
  if (changedAssets > 0) clauses.push(`${changedAssets} asset${changedAssets === 1 ? "" : "s"} changed`);
  if (identicalAssets > 0) clauses.push(`${identicalAssets} identical asset${identicalAssets === 1 ? "" : "s"} skipped`);
  if (!clauses.length) clauses.push(`${changedDomains.length || 1} source domain${changedDomains.length === 1 ? "" : "s"} changed`);
  const summary = clauses.join("; ");
  return {
    message: `Saved and source-verified — ${summary}`,
    toastMessage: summary[0].toUpperCase() + summary.slice(1),
    kind: "success",
    toastKind: "success",
    saved: true,
  };
}

async function saveAllChanges() {
  if (totalValidationCount() > 0) {
    const message = firstValidationMessage();
    setStatus(message, "error");
    toast(message, "error");
    const [owner, controller] = firstValidationOwner() || [];
    if (owner && WORKSPACE_VIEWS.includes(owner)) {
      activateView(owner, { historyMode: "push", focus: true });
      controller?.focusFirstInvalid?.();
    }
    return;
  }
  if (totalBlockingCount() > 0) {
    const message = firstBlockingMessage();
    setStatus(`Save waiting · ${message}`, "busy");
    toast(message, "info");
    const [owner, controller] = firstBlockingOwner() || [];
    if (owner && WORKSPACE_VIEWS.includes(owner)) {
      activateView(owner, { historyMode: "push", focus: true });
      controller?.focusFirstBlocking?.();
    }
    return;
  }
  let domains;
  try {
    domains = collectCommitDomains();
  } catch (error) {
    setStatus(`Save blocked: ${error.message}`, "error");
    toast(error.message, "error");
    return;
  }
  if (!Object.keys(domains).length) return;
  if (state.conflict) {
    setStatus("Reload required before this draft can be saved.", "error");
    return;
  }

  let finalFeedback = null;
  let shouldBuild = false;
  setBusy(true, { inert: true });
  setStatus("Validating and saving one transaction…", "busy");
  showCommitStatus("Saving changes…", "Validating revisions and committing one source transaction.", "busy");
  try {
    const result = await api.post("/api/v2/commit", {
      sourceRevision: state.revision,
      ...domains,
    });
    state.revision = result.sourceRevision;
    Object.entries(state.controllers).forEach(([name, controller]) => controller?.clearCommitted?.(name === "pokemon" ? result : undefined));
    await loadData({ keepStatus: true });
    finalFeedback = commitFeedback(result);
    shouldBuild = finalFeedback.saved && elements.autoBuild.checked;
  } catch (error) {
    finalFeedback = {
      message: `Save failed: ${error.message}`,
      toastMessage: error.message,
      kind: "error",
      toastKind: "error",
      saved: false,
    };
  } finally {
    setBusy(false, { inert: true });
    if (finalFeedback) {
      setStatus(finalFeedback.message, finalFeedback.kind);
      toast(finalFeedback.toastMessage, finalFeedback.toastKind);
      showCommitStatus(
        finalFeedback.message,
        finalFeedback.kind === "error"
          ? "Save stopped. Your draft is preserved and the workspace is unlocked."
          : finalFeedback.saved
            ? "Source verification completed and the workspace is unlocked."
            : "The draft was cleared; source files were unchanged.",
        finalFeedback.kind,
        { dismissAfter: 6200 }
      );
    }
  }
  if (shouldBuild) await startBuild();
}

async function resetAllDrafts() {
  if (!totalChangeCount() && !totalValidationCount()) return;
  const confirmed = await confirmAction({
    title: "Discard every draft change?",
    message: "This clears every unsaved change across the Pokédex Workshop.",
    confirmLabel: "Discard drafts",
    danger: true,
  });
  if (!confirmed) return;
  Object.values(state.controllers).forEach((controller) => controller.reset?.());
  markDirty();
  toast("Drafts discarded.");
}

function applyBuildStatus(status) {
  const running = Boolean(status?.running);
  const output = status?.output || status?.error || "";
  elements.buildOutput.textContent = output;
  elements.buildPanel.hidden = !elements.showBuildLog.checked;
  elements.buildRom.disabled = running || state.busy;
  elements.buildRom.textContent = running ? "Building…" : "Build ROM";
  if (running) setStatus(status.latestLine || "Building ROM…", "busy");
  if (!running && status?.ok === true) setStatus("ROM build complete", "success");
  if (!running && status?.ok === false) setStatus("ROM build failed", "error");
  return running;
}

async function pollBuild() {
  try {
    const status = await api.get(`/build-status?ts=${Date.now()}`);
    if (applyBuildStatus(status)) window.setTimeout(pollBuild, 900);
  } catch (error) {
    setStatus(`Build status unavailable: ${error.message}`, "error");
  }
}

async function startBuild() {
  setStatus("Starting ROM build…", "busy");
  elements.buildPanel.hidden = !elements.showBuildLog.checked;
  try {
    const status = await api.post("/build", { runAfter: elements.autoRun.checked });
    applyBuildStatus(status);
    window.setTimeout(pollBuild, 700);
  } catch (error) {
    setStatus(`Build failed to start: ${error.message}`, "error");
  }
}

async function openNds() {
  setBusy(true);
  setStatus("Opening test.nds…", "busy");
  try {
    const result = await api.post("/open-test-nds", {});
    setStatus(result.message || "Opened test.nds", "success");
  } catch (error) {
    setStatus(`Open failed: ${error.message}`, "error");
  } finally {
    setBusy(false);
  }
}

function renderShiny(payload) {
  const counter = Number(payload?.counter ?? 0);
  const denominator = Number(payload?.denominator ?? Math.max(1, 8192 - counter));
  elements.shinyCounter.textContent = String(counter);
  elements.shinyCounter.setAttribute("aria-label", `Saved shiny counter ${counter}; pity chance one in ${denominator}`);
  const reserved = payload?.reservedShinies || payload?.savedShinies || [];
  elements.reservedShinies.innerHTML = "";
  reserved.forEach((item) => {
    const chip = document.createElement("span");
    chip.className = "reserved-shiny";
    const species = item.species?.name || item.speciesName || item.symbol || "Reserved shiny";
    chip.textContent = `${species}${item.level ? ` · Lv ${item.level}` : ""}`;
    elements.reservedShinies.append(chip);
  });
}

async function loadShiny() {
  try {
    renderShiny(await api.get(`/shiny-counter?ts=${Date.now()}`));
  } catch (error) {
    elements.shinyCounter.textContent = "—";
  }
}

async function setShiny(counter) {
  try {
    renderShiny(await api.post("/shiny-counter", { counter }));
    toast(`Shiny counter set to ${counter}.`, "success");
  } catch (error) {
    setStatus(`Shiny counter failed: ${error.message}`, "error");
  }
}

function bindGlobalActions() {
  elements.saveAll.addEventListener("click", saveAllChanges);
  elements.resetDraft.addEventListener("click", resetAllDrafts);
  elements.buildRom.addEventListener("click", startBuild);
  elements.openNds.addEventListener("click", openNds);
  elements.restartServer.addEventListener("click", async () => {
    const confirmed = await confirmAction({
      title: "Restart the V2 server?",
      message: "Any unsaved draft remains only in this browser and may be lost.",
      confirmLabel: "Restart server",
    });
    if (!confirmed) return;
    setStatus("Restarting server…", "busy");
    try {
      await api.post("/restart-server", {});
      window.setTimeout(() => location.reload(), 1100);
    } catch (error) {
      setStatus(`Restart failed: ${error.message}`, "error");
    }
  });
  elements.showBuildLog.addEventListener("change", () => {
    elements.buildPanel.hidden = !elements.showBuildLog.checked;
    localStorage.setItem("ow-v2-show-build-log", String(elements.showBuildLog.checked));
  });
  elements.autoBuild.addEventListener("change", () => localStorage.setItem("ow-v2-auto-build", String(elements.autoBuild.checked)));
  elements.autoRun.addEventListener("change", () => localStorage.setItem("ow-v2-auto-run", String(elements.autoRun.checked)));
  elements.refreshShiny.addEventListener("click", loadShiny);
  elements.resetShiny.addEventListener("click", () => setShiny(0));
  elements.maxShiny.addEventListener("click", () => setShiny(8191));
  elements.buildPanel.querySelector("[data-action='close-build-panel']")?.addEventListener("click", () => {
    elements.buildPanel.hidden = true;
    elements.showBuildLog.checked = false;
    localStorage.setItem("ow-v2-show-build-log", "false");
  });
  elements.app.addEventListener("click", (event) => {
    if (event.target.closest("[data-shell-retry]")) location.reload();
  });
  window.addEventListener("keydown", (event) => {
    if (!(event.metaKey || event.ctrlKey) || event.altKey || event.key.toLowerCase() !== "s") return;
    event.preventDefault();
    if (!state.busy && totalBlockingCount() > 0) saveAllChanges();
    else if (!elements.saveAll.disabled) elements.saveAll.click();
  });
  window.addEventListener("beforeunload", (event) => {
    if (!totalChangeCount()) return;
    event.preventDefault();
    event.returnValue = "";
  });
}

async function boot() {
  const initialLocation = locationDescriptor();
  state.navigationContext = readNavigationContext();
  if (initialLocation?.view === "pokemon" && validPokemonSymbol(initialLocation.selection)) {
    pokemonSelectionKey = initialLocation.selection;
  }
  elements.showBuildLog.checked = localStorage.getItem("ow-v2-show-build-log") === "true";
  elements.autoBuild.checked = localStorage.getItem("ow-v2-auto-build") === "true";
  elements.autoRun.checked = localStorage.getItem("ow-v2-auto-run") === "true";
  elements.buildPanel.hidden = !elements.showBuildLog.checked;
  bindNavigation();
  bindGlobalActions();
  if (initialLocation) applyLocation(initialLocation);
  else {
    activateView(state.activeView);
    writeLocation(state.activeView, controllerSelection(state.activeView).selection, "replace");
  }
  try {
    Promise.resolve(ensurePokemonController().refresh?.()).catch((error) => {
      setStatus(`Pokémon Editor failed to load: ${error.message}`, "error");
    });
  } catch (error) {
    setStatus(`Pokémon Editor failed to initialize: ${error.message}`, "error");
  }
  try {
    await Promise.all([loadData(), loadShiny(), pollBuild()]);
    if (initialLocation && initialLocation.view !== "pokemon" && initialLocation.selection) {
      state.controllers[initialLocation.view]?.restoreSelection?.(initialLocation.selection);
    }
    const activeSelection = state.activeView === "pokemon"
      ? state.selectedPokemonKey
      : controllerSelection(state.activeView).selection;
    writeLocation(state.activeView, activeSelection, "replace");
  } catch (error) {
    setStatus(`Profile and route workspace failed to load: ${error.message}`, "error");
    renderShellLoadError(error);
  }
}

state.reloadData = loadData;
state.markDirty = markDirty;
state.toast = toast;
state.openPokemonRecord = openPokemonRecord;
state.reportSelection = reportSelection;

boot();
