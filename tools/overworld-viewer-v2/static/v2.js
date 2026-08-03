import { createProfilesController, v40ProfileDeckCapability } from "/v2-assets/profiles.js";
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
  conflictRevision: "",
  busy: false,
  commitInert: false,
  activeView: localStorage.getItem("ow-v2-view") || "pokemon",
  controllers: {},
  availableViews: new Set(WORKSPACE_VIEWS),
  controllerAvailability: Object.fromEntries(WORKSPACE_VIEWS.map((name) => [name, {
    available: true,
    status: name === "pokemon" ? "loading" : "pending",
    reason: "",
  }])),
  workspaceDataError: "",
  navigationContext: null,
  applyingLocation: false,
  buildServerAvailable: false,
  latestBuildStatus: null,
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
  "/api/v2/commit",
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
  "commitStatusHeading", "commitStatusDetail", "commitStatusElapsed", "commitStatusAction",
  "saveAllLabel",
].forEach((id) => { elements[id] = byId(id); });

function capabilitySource(data, name) {
  const capabilities = data?.capabilities;
  const candidates = [
    capabilities?.views?.[name],
    capabilities?.[name],
    data?.[`${name}Capability`],
    data?.[`${name}Available`],
  ];
  if (name === "profiles") candidates.push(data?.profilesAvailable);
  return candidates.find((value) => value !== undefined && value !== null);
}

function normalizedViewCapability(data, name) {
  if (name === "profiles") {
    const v40Capability = v40ProfileDeckCapability(data);
    if (v40Capability) return v40Capability;
  }
  const source = capabilitySource(data, name);
  const label = {
    pokemon: "Pokémon Editor",
    profiles: "Profile Deck",
    routes: "Route Deck",
    sounds: "Sound Deck",
  }[name] || name;
  const fallbackReason = name === "profiles"
    ? data?.profileError?.message
    : data?.[`${name}Error`]?.message || data?.[`${name}Error`];
  if (source === false) return { available: false, reason: String(fallbackReason || `${label} sources are not available in this project.`) };
  if (source && typeof source === "object") {
    const available = source.available !== false && source.enabled !== false && source.readable !== false;
    return {
      available,
      reason: String(source.reason || source.message || fallbackReason || (available ? "" : `${label} sources are not available in this project.`)),
    };
  }
  return { available: true, reason: "" };
}

function firstAvailableView(preferred = "pokemon") {
  if (state.availableViews.has(preferred)) return preferred;
  return WORKSPACE_VIEWS.find((name) => state.availableViews.has(name)) || "";
}

function viewIsAvailable(name) {
  return state.availableViews.has(name);
}

function destroyUnavailableController(name) {
  const controller = state.controllers[name];
  if (!controller) return;
  controller.destroy?.();
  delete state.controllers[name];
}

function applyWorkspaceCapabilities(data, { failed = false } = {}) {
  const next = {};
  WORKSPACE_VIEWS.forEach((name) => {
    let capability = normalizedViewCapability(data, name);
    if (failed && ["profiles", "routes"].includes(name)) {
      capability = { available: false, reason: state.workspaceDataError || "Workspace data could not be loaded." };
    }
    const previous = state.controllerAvailability[name] || {};
    next[name] = {
      ...capability,
      status: capability.available ? previous.status || "pending" : "unavailable",
    };
  });
  state.controllerAvailability = next;
  state.availableViews = new Set(WORKSPACE_VIEWS.filter((name) => next[name].available));
  elements.workspaceNav.style.setProperty("--workspace-view-count", String(Math.max(1, state.availableViews.size)));

  WORKSPACE_VIEWS.forEach((name) => {
    const available = state.availableViews.has(name);
    const tab = elements.workspaceNav.querySelector(`[data-view="${name}"]`);
    if (tab) {
      tab.hidden = !available;
      tab.disabled = !available;
      tab.setAttribute("aria-disabled", String(!available));
      if (!available && next[name].reason) tab.title = next[name].reason;
      else tab.removeAttribute("title");
    }
    elements[`${name}View`]?.toggleAttribute("data-view-unavailable", !available);
    if (!available) destroyUnavailableController(name);
  });
  state.controllers.pokemon?.refreshContext?.();

  if (!viewIsAvailable(state.activeView)) {
    const fallback = firstAvailableView();
    if (fallback) {
      activateView(fallback);
      writeLocation(fallback, fallback === "pokemon" ? state.selectedPokemonKey : "", "replace");
    }
  }
}

function messageFromResult(result, response) {
  return result?.error || result?.message || `HTTP ${response.status}`;
}

function offlineRequestError(error) {
  const wrapped = new Error("V2 server is offline. Restart it, then reload this page.", { cause: error });
  wrapped.isConnectionFailure = true;
  return wrapped;
}

const API_TIMEOUT_MS = 60000;

async function timedJsonRequest(path, options = {}, timeoutMs = API_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal });
    const result = await response.json();
    return { response, result };
  } catch (error) {
    if (error?.name === "AbortError") {
      const wrapped = new Error(`The server did not respond within ${Math.round(timeoutMs / 1000)} seconds.`, { cause: error });
      wrapped.isTimeout = true;
      throw wrapped;
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

const api = {
  async get(path, options = {}) {
    let response;
    let result;
    try {
      ({ response, result } = await timedJsonRequest(path, { cache: "no-store", ...options }));
    } catch (error) {
      if (error?.isTimeout) throw error;
      if (error instanceof SyntaxError) throw new Error("The V2 server returned an unreadable response.", { cause: error });
      throw offlineRequestError(error);
    }
    if (!response.ok) throw new Error(messageFromResult(result, response));
    return result;
  },

  async post(path, payload = {}, options = {}) {
    const headers = new Headers({ "Content-Type": "application/json", ...(options.headers || {}) });
    if (MUTATION_PATHS.has(path)) {
      if (state.conflict) throw new Error("Sources changed. Your draft is preserved and must be applied to the latest revision.");
      if (!state.revision) throw new Error("The workspace revision is not loaded yet.");
      headers.set("If-Match", state.revision);
    }
    let response;
    let result;
    try {
      ({ response, result } = await timedJsonRequest(path, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      }));
    } catch (error) {
      const wrapped = error?.isTimeout
        ? error
        : error instanceof SyntaxError
          ? new Error("The V2 server response ended before save confirmation.", { cause: error })
          : offlineRequestError(error);
      if (MUTATION_PATHS.has(path)) wrapped.isOutcomeUnknown = true;
      throw wrapped;
    }
    const recoverableConflict = response.status === 409
      && ["revision_conflict", "asset_revision_conflict"].includes(result?.code);
    if (recoverableConflict) {
      state.conflict = true;
      state.conflictRevision = String(result.sourceRevision || state.revision || "");
      setStatus("Sources changed outside this editor. Your draft is preserved.", "error");
    }
    if (!response.ok) {
      const error = new Error(messageFromResult(result, response));
      error.status = response.status;
      error.code = result?.code || "";
      error.isConflict = recoverableConflict;
      error.currentRevision = String(result?.sourceRevision || "");
      error.currentAssetRevision = String(result?.assetRevision || "");
      throw error;
    }
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
let commitElapsedTimer = 0;
let commitStartedAt = 0;
let commitRecoveryAction = null;

function formatElapsed(milliseconds) {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
}

function updateCommitElapsed() {
  if (!commitStartedAt) return;
  const elapsed = formatElapsed(performance.now() - commitStartedAt);
  elements.commitStatusElapsed.value = elapsed;
  elements.pendingCount.textContent = elapsed;
  elements.pendingCount.setAttribute("aria-label", `Save running for ${elapsed}`);
}

function startCommitElapsed() {
  window.clearInterval(commitElapsedTimer);
  commitStartedAt = performance.now();
  elements.saveAll.classList.add("is-saving");
  elements.saveAll.setAttribute("aria-busy", "true");
  elements.saveAllLabel.textContent = "Saving";
  elements.pendingCount.hidden = false;
  elements.pendingCount.classList.add("is-elapsed");
  updateCommitElapsed();
  commitElapsedTimer = window.setInterval(updateCommitElapsed, 1000);
}

function stopCommitElapsed() {
  window.clearInterval(commitElapsedTimer);
  commitElapsedTimer = 0;
  commitStartedAt = 0;
  elements.saveAll.classList.remove("is-saving");
  elements.saveAll.removeAttribute("aria-busy");
  elements.saveAllLabel.textContent = "Save";
  elements.pendingCount.classList.remove("is-elapsed");
}

function setCommitRecovery(label = "", action = null) {
  commitRecoveryAction = typeof action === "function" ? action : null;
  elements.commitStatusAction.textContent = label;
  elements.commitStatusAction.hidden = !commitRecoveryAction;
  elements.commitStatus.classList.toggle("has-action", Boolean(commitRecoveryAction));
}

function showCommitStatus(message, detail, kind = "busy", { dismissAfter = 0, phase = "", actionLabel = "", action = null } = {}) {
  window.clearTimeout(commitStatusTimer);
  commitStatusTimer = 0;
  elements.commitStatus.dataset.kind = kind;
  elements.commitStatus.dataset.phase = phase;
  elements.commitStatus.classList.add("is-visible");
  elements.commitStatusHeading.textContent = message;
  elements.commitStatusDetail.textContent = detail;
  setCommitRecovery(actionLabel, action);
  if (kind === "error" && commitRecoveryAction) {
    requestAnimationFrame(() => elements.commitStatusAction.focus({ preventScroll: true }));
  }
  if (dismissAfter > 0) {
    commitStatusTimer = window.setTimeout(() => {
      elements.commitStatus.classList.remove("is-visible");
      elements.commitStatusHeading.textContent = "";
      elements.commitStatusDetail.textContent = "";
      elements.commitStatusElapsed.value = "";
      setCommitRecovery();
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
  [elements.saveAll, elements.resetDraft]
    .forEach((control) => { control.disabled = busy; });
  updateBuildControls();
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
  const nextView = WORKSPACE_VIEWS.includes(view) && viewIsAvailable(view)
    ? view
    : firstAvailableView();
  if (!nextView) return state.activeView;
  state.activeView = nextView;
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
  return state.activeView;
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
    const tabs = [...elements.workspaceNav.querySelectorAll("[data-view]:not([hidden]):not(:disabled)")];
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
  if (!viewIsAvailable("pokemon")) return null;
  if (!state.controllers.pokemon) {
    state.controllers.pokemon = createPokemonController(controllerContext());
  }
  return state.controllers.pokemon;
}

function rebuildPokemonController(symbol) {
  if (!viewIsAvailable("pokemon")) return null;
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
  if (!viewIsAvailable("pokemon")) {
    setStatus(state.controllerAvailability.pokemon?.reason || "Pokémon Editor is not available in this project.", "error");
    return false;
  }
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
  const active = activateView(originView, { selection: originSelection, focus: true });
  writeLocation(active, active === originView ? originSelection : "", "push");
}

function applyLocation(descriptor) {
  if (!descriptor) return;
  let redirected = false;
  state.applyingLocation = true;
  try {
    if (!viewIsAvailable(descriptor.view)) {
      const fallback = firstAvailableView();
      if (fallback) {
        activateView(fallback);
        redirected = true;
      }
      return;
    }
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
    if (redirected) {
      writeLocation(state.activeView, state.activeView === "pokemon" ? state.selectedPokemonKey : controllerSelection(state.activeView).selection, "replace");
    }
  }
}

function ensureWorkspaceController(name) {
  if (!viewIsAvailable(name)) return null;
  if (state.controllers[name]) return state.controllers[name];
  const factories = {
    profiles: createProfilesController,
    routes: createRoutesController,
    sounds: createSoundsController,
  };
  const factory = factories[name];
  if (!factory) return null;
  state.controllers[name] = factory(controllerContext());
  state.controllerAvailability[name] = {
    ...state.controllerAvailability[name],
    status: "ready",
  };
  return state.controllers[name];
}

function ensureAvailableWorkspaceControllers(data, refreshOnly = null, { preserveDrafts = false } = {}) {
  const requested = refreshOnly ? new Set(refreshOnly) : null;
  ["profiles", "routes", "sounds"].forEach((name) => {
    const existed = Boolean(state.controllers[name]);
    const controller = ensureWorkspaceController(name);
    if (!requested || requested.has(name) || !existed) {
      const refresh = preserveDrafts && existed && controller?.refreshPreservingDrafts
        ? controller.refreshPreservingDrafts
        : controller?.refresh;
      refresh?.call(controller, data);
    }
    if (controller) {
      state.controllerAvailability[name] = {
        ...state.controllerAvailability[name],
        status: "ready",
      };
    }
  });
}

async function loadData({
  keepStatus = false,
  refreshOnly = null,
  throwOnControllerRefreshError = false,
  allowDraftRebase = false,
  preserveDraftCapabilities = false,
} = {}) {
  if (!keepStatus) setStatus("Loading workspace…", "busy");
  const data = await api.get(`/data.json?ts=${Date.now()}`);
  if (!data.sourceRevision) throw new Error("V2 data did not include a source revision.");

  if (!allowDraftRebase && state.revision && data.sourceRevision !== state.revision && totalChangeCount() > 0) {
    state.conflict = true;
    state.conflictRevision = data.sourceRevision;
    throw new Error("Sources changed while this draft was open. Your draft is still preserved.");
  }
  state.data = data;
  state.revision = data.sourceRevision;
  state.conflict = false;
  state.conflictRevision = "";
  state.workspaceDataError = "";

  if (!preserveDraftCapabilities) applyWorkspaceCapabilities(data);
  ensureAvailableWorkspaceControllers(data, refreshOnly, { preserveDrafts: preserveDraftCapabilities });
  const refreshPokemon = !refreshOnly || new Set(refreshOnly).has("pokemon");
  const pokemonController = ensurePokemonController();
  if (refreshPokemon) {
    try {
      const refresh = throwOnControllerRefreshError && pokemonController?.refreshStrict
        ? pokemonController.refreshStrict(data)
        : pokemonController?.refresh?.(data);
      await Promise.resolve(refresh);
    } catch (error) {
      setStatus(`Pokémon Editor failed to refresh: ${error.message}`, "error");
      if (throwOnControllerRefreshError) throw error;
    }
  } else {
    pokemonController?.syncWorkspaceRevision?.(data.sourceRevision, data.assetRevision);
  }
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

const COMMIT_DOMAIN_CONTROLLERS = Object.freeze({
  behaviorModel: "profiles",
  profiles: "profiles",
  profileMemberships: "profiles",
  profileOverrides: "profiles",
  encounters: "routes",
  spawnSettings: "routes",
  pokemonUpdates: "pokemon",
  pokemonEvolutionUpdates: "pokemon",
  pokemonLearnsetUpdates: "pokemon",
  pokemonFormUpdates: "pokemon",
  pokemonAssetUpdates: "pokemon",
});

function commitControllerNames(domains) {
  const domainNames = Array.isArray(domains) ? domains : Object.keys(domains || {});
  return [...new Set(domainNames.map((domain) => COMMIT_DOMAIN_CONTROLLERS[domain]).filter(Boolean))];
}

function controllerDisplayName(name) {
  return ({ profiles: "Profile Deck", routes: "Route Deck", sounds: "Sound Deck", pokemon: "Pokémon Editor" })[name] || name;
}

function clearCommittedControllers(controllerNames, result, requestedDomains = []) {
  controllerNames.forEach((name) => {
    const controller = state.controllers[name];
    if (!controller?.clearCommitted) return;
    controller.clearCommitted(
      name === "pokemon" ? { ...result, requestedDomains }
        : name === "profiles" ? result
          : undefined,
    );
  });
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

async function retryCommittedRefresh(result, controllerNames) {
  setBusy(true, { inert: true });
  startCommitElapsed();
  setStatus("Source saved · refreshing affected decks…", "busy");
  showCommitStatus(
    "Source is already saved",
    `Refreshing ${controllerNames.map(controllerDisplayName).join(" and ")}.`,
    "busy",
    { phase: "refresh" },
  );
  let feedback = null;
  try {
    await loadData({ keepStatus: true, refreshOnly: controllerNames, throwOnControllerRefreshError: true });
    feedback = commitFeedback(result);
  } catch (error) {
    feedback = {
      message: `Source saved · refresh failed: ${error.message}`,
      detail: `${error.message} Your source changes are safe. Retry only refreshes the editor view.`,
      kind: "error",
      actionLabel: "Retry refresh",
      action: () => retryCommittedRefresh(result, controllerNames),
    };
  } finally {
    stopCommitElapsed();
    setBusy(false, { inert: true });
  }
  setStatus(feedback.message, feedback.kind);
  showCommitStatus(
    feedback.message,
    feedback.detail || "Affected decks are synchronized and editing is unlocked.",
    feedback.kind,
    feedback.action ? { actionLabel: feedback.actionLabel, action: feedback.action } : { dismissAfter: 6200 },
  );
}

async function checkUnknownSaveOutcome(originalRevision) {
  setBusy(true, { inert: true });
  startCommitElapsed();
  setStatus("Checking the workspace revision…", "busy");
  showCommitStatus("Checking save status", "No source files will be written during this check.", "busy", { phase: "verify" });
  let feedback;
  try {
    const data = await api.get(`/data.json?ts=${Date.now()}`);
    if (data.sourceRevision === originalRevision) {
      state.conflict = false;
      feedback = {
        message: "No source change detected",
        detail: "The draft is still here and it is safe to retry the save.",
        kind: "ready",
        actionLabel: "Retry save",
        action: saveAllChanges,
      };
    } else {
      state.conflict = true;
      state.conflictRevision = data.sourceRevision;
      feedback = {
        message: "The source revision changed",
        detail: "The earlier save may already have completed. Review the latest source underneath your preserved draft before deciding whether to save it again.",
        kind: "error",
        actionLabel: "Review latest",
        action: () => applyDraftToLatestRevision(data.sourceRevision, { reviewOnly: true }),
      };
    }
  } catch (error) {
    feedback = {
      message: `Status check failed: ${error.message}`,
      detail: "The draft is preserved. Check the server before trying to save again.",
      kind: "error",
      actionLabel: "Check again",
      action: () => checkUnknownSaveOutcome(originalRevision),
    };
  } finally {
    stopCommitElapsed();
    setBusy(false, { inert: true });
  }
  setStatus(feedback.message, feedback.kind);
  showCommitStatus(
    feedback.message,
    feedback.detail,
    feedback.kind,
    feedback.action ? { actionLabel: feedback.actionLabel, action: feedback.action } : {},
  );
}

async function applyDraftToLatestRevision(revision = state.conflictRevision, { reviewOnly = false } = {}) {
  const latestRevision = String(revision || "");
  if (!latestRevision) {
    showCommitStatus(
      "Latest revision unavailable",
      "Your draft is still preserved. Check the server, then try saving again.",
      "error",
      { actionLabel: "Check status", action: () => checkUnknownSaveOutcome(state.revision) },
    );
    return;
  }
  const changeCount = totalChangeCount();
  if (!reviewOnly) {
    const confirmed = await confirmAction({
      title: "Apply your draft to the latest source?",
      message: `All ${changeCount} pending change${changeCount === 1 ? "" : "s"} stay intact. The editor will first refresh the latest source underneath them, then save your draft; where the same value changed elsewhere, your drafted value takes precedence.`,
      confirmLabel: "Apply my draft",
    });
    if (!confirmed) return;
  }
  let controllerNames;
  try {
    controllerNames = commitControllerNames(collectCommitDomains());
  } catch (error) {
    setStatus(`Draft could not be prepared: ${error.message}`, "error");
    toast("Your draft is still preserved.", "error");
    return;
  }

  setBusy(true, { inert: true });
  startCommitElapsed();
  const refreshControllerNames = controllerNames;
  setStatus("Refreshing the latest source beneath your draft…", "busy");
  showCommitStatus(
    "Rebasing preserved draft",
    "Refreshing current source data while keeping every pending edit in memory.",
    "busy",
    { phase: "refresh" },
  );
  try {
    await loadData({
      keepStatus: true,
      refreshOnly: refreshControllerNames,
      throwOnControllerRefreshError: true,
      allowDraftRebase: true,
      preserveDraftCapabilities: true,
    });
  } catch (error) {
    state.conflict = true;
    state.conflictRevision = latestRevision;
    setStatus(`Latest source could not be loaded: ${error.message}`, "error");
    showCommitStatus(
      "Draft still preserved",
      `${error.message} No pending edit was discarded or written.`,
      "error",
      { actionLabel: "Try again", action: () => applyDraftToLatestRevision(state.conflictRevision) },
    );
    return;
  } finally {
    stopCommitElapsed();
    setBusy(false, { inert: true });
  }

  if (totalValidationCount() > 0) {
    const message = firstValidationMessage();
    setStatus(`Draft needs review · ${message}`, "error");
    showCommitStatus(
      "Draft preserved on the latest source",
      `${message}. The incompatible item remains preserved and has not been written; review the owning deck or reset the draft when you no longer need it.`,
      "error",
    );
    const [owner, controller] = firstValidationOwner() || [];
    if (owner && WORKSPACE_VIEWS.includes(owner)) {
      activateView(owner, { historyMode: "push", focus: true });
      controller?.focusFirstInvalid?.();
    }
    return;
  }
  if (reviewOnly) {
    setStatus(`Latest source loaded · ${changeCount} draft change${changeCount === 1 ? "" : "s"} still pending`, "pending");
    showCommitStatus(
      "Latest source loaded beneath your draft",
      "Nothing was written or discarded. Review the pending values, then save only if they still need to be applied.",
      "pending",
      { actionLabel: "Save draft", action: saveAllChanges },
    );
    return;
  }
  setStatus("Draft rebased · saving…", "busy");
  await saveAllChanges();
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
    setStatus("Source changed; your draft is preserved.", "error");
    showCommitStatus(
      "Source changed; draft preserved",
      "Apply the same pending edits to the latest source without reloading or discarding anything.",
      "error",
      { actionLabel: "Apply to latest", action: () => applyDraftToLatestRevision() },
    );
    return;
  }

  let finalFeedback = null;
  let committedResult = null;
  let shouldBuild = false;
  const submittedControllerNames = commitControllerNames(domains);
  let refreshControllerNames = submittedControllerNames;
  const originalRevision = state.revision;
  const changeCount = totalChangeCount();
  setBusy(true, { inert: true });
  startCommitElapsed();
  setStatus(`Saving ${changeCount} change${changeCount === 1 ? "" : "s"}…`, "busy");
  showCommitStatus(
    `Saving ${changeCount} change${changeCount === 1 ? "" : "s"}`,
    "Validating the current revision and writing one atomic source transaction.",
    "busy",
    { phase: "commit" },
  );
  try {
    const result = await api.post("/api/v2/commit", {
      sourceRevision: state.revision,
      ...domains,
    });
    committedResult = result;
    state.revision = result.sourceRevision;
    clearCommittedControllers(submittedControllerNames, result, Object.keys(domains));
    refreshControllerNames = commitControllerNames(result.changedDomains || []);
    shouldBuild = result.saved && elements.autoBuild.checked;
    if (result.saved) {
      setStatus("Source committed · refreshing affected decks…", "busy");
      showCommitStatus(
        "Source files saved",
        `Refreshing ${refreshControllerNames.map(controllerDisplayName).join(" and ")} only.`,
        "busy",
        { phase: "refresh" },
      );
      await loadData({ keepStatus: true, refreshOnly: refreshControllerNames, throwOnControllerRefreshError: true });
    }
    finalFeedback = commitFeedback(result);
  } catch (error) {
    if (committedResult) {
      finalFeedback = {
        message: `Source saved · view refresh failed: ${error.message}`,
        toastMessage: "Source saved, but the editor view needs to refresh.",
        kind: "error",
        toastKind: "error",
        saved: true,
        refreshFailed: true,
      };
    } else {
      finalFeedback = {
        message: error.isOutcomeUnknown
          ? "Save result not confirmed"
          : error.isConflict
            ? `Source changed; ${changeCount} pending change${changeCount === 1 ? " is" : "s are"} preserved`
            : `Save failed: ${error.message}`,
        toastMessage: error.isConflict ? "Source changed; nothing in your draft was discarded." : error.message,
        kind: "error",
        toastKind: "error",
        saved: false,
        outcomeUnknown: Boolean(error.isOutcomeUnknown),
        conflict: Boolean(error.isConflict || state.conflict),
      };
    }
  } finally {
    stopCommitElapsed();
    setBusy(false, { inert: true });
    if (finalFeedback) {
      setStatus(finalFeedback.message, finalFeedback.kind);
      toast(finalFeedback.toastMessage, finalFeedback.toastKind);
      const retryAction = finalFeedback.refreshFailed
        ? () => retryCommittedRefresh(committedResult, refreshControllerNames)
        : finalFeedback.outcomeUnknown
          ? () => checkUnknownSaveOutcome(originalRevision)
        : finalFeedback.conflict
            ? () => applyDraftToLatestRevision(state.conflictRevision)
            : (!committedResult ? saveAllChanges : null);
      showCommitStatus(
        finalFeedback.outcomeUnknown ? "Save result not confirmed" : finalFeedback.message,
        finalFeedback.outcomeUnknown
          ? "The connection ended before confirmation. Your draft is preserved; check the workspace revision before saving again."
          : finalFeedback.refreshFailed
          ? "The source transaction completed. Retry to synchronize the editor without saving again."
          : finalFeedback.conflict
            ? "Nothing was discarded. Apply your pending edits on top of the latest source when you are ready; your edited values will take precedence on overlap."
          : finalFeedback.kind === "error"
            ? "Save stopped before confirmation. Your draft remains in the workspace."
          : finalFeedback.saved
            ? "Source verification completed and the workspace is unlocked."
            : "The draft was cleared; source files were unchanged.",
        finalFeedback.kind,
        retryAction
          ? { actionLabel: finalFeedback.refreshFailed ? "Retry refresh" : finalFeedback.outcomeUnknown ? "Check status" : finalFeedback.conflict ? "Apply to latest" : "Retry save", action: retryAction }
          : { dismissAfter: 6200 },
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
  state.buildServerAvailable = true;
  state.latestBuildStatus = status || {};
  const running = Boolean(status?.running);
  const output = status?.output || status?.error || "";
  elements.buildOutput.textContent = output;
  elements.buildPanel.hidden = !elements.showBuildLog.checked;
  elements.buildRom.textContent = running ? "Building…" : "Build ROM";
  updateBuildControls();
  if (running) setStatus(status.latestLine || "Building ROM…", "busy");
  if (!running && status?.ok === true) setStatus("ROM build complete", "success");
  if (!running && status?.ok === false) setStatus("ROM build failed", "error");
  return running;
}

function updateBuildControls() {
  const running = Boolean(state.latestBuildStatus?.running);
  const hasRom = state.latestBuildStatus?.testNdsExists === true;
  elements.buildRom.disabled = state.busy || running;
  elements.openNds.disabled = state.busy || running || !state.buildServerAvailable || !hasRom;

  if (!state.buildServerAvailable) {
    elements.openNds.title = "V2 server is offline or has not responded. Reload after restarting it.";
  } else if (running) {
    elements.openNds.title = "Open NDS is unavailable while the ROM is building.";
  } else if (!hasRom) {
    elements.openNds.title = "Build the ROM first; test.nds does not exist yet.";
  } else {
    elements.openNds.removeAttribute("title");
  }
}

async function pollBuild() {
  try {
    const status = await api.get(`/build-status?ts=${Date.now()}`);
    if (applyBuildStatus(status)) window.setTimeout(pollBuild, 900);
  } catch (error) {
    state.buildServerAvailable = false;
    updateBuildControls();
    if (error.isConnectionFailure) {
      setStatus("V2 server is offline. Restart it, then reload this page.", "error");
    } else {
      setStatus(`Build status unavailable: ${error.message}`, "error");
    }
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
    if (error.isConnectionFailure) {
      state.buildServerAvailable = false;
      updateBuildControls();
      setStatus("V2 server is offline. Restart it, then reload this page.", "error");
    } else {
      setStatus(`Build failed to start: ${error.message}`, "error");
    }
  }
}

async function openNds() {
  setBusy(true);
  setStatus("Opening test.nds…", "busy");
  try {
    const result = await api.post("/open-test-nds", {});
    setStatus(result.message || "Opened test.nds", "success");
    toast(result.message || "Opened test.nds", "success");
  } catch (error) {
    if (error.isConnectionFailure) {
      state.buildServerAvailable = false;
      setStatus("V2 server is offline. Restart it, then reload this page.", "error");
    } else {
      setStatus(`Open failed: ${error.message}`, "error");
    }
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
  elements.commitStatusAction.addEventListener("click", () => {
    const action = commitRecoveryAction;
    if (!action || state.busy) return;
    void action();
  });
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
  updateBuildControls();
  if (initialLocation) applyLocation(initialLocation);
  else {
    activateView(state.activeView);
    writeLocation(state.activeView, controllerSelection(state.activeView).selection, "replace");
  }
  try {
    Promise.resolve(ensurePokemonController()?.refresh?.()).catch((error) => {
      setStatus(`Pokémon Editor failed to load: ${error.message}`, "error");
    });
  } catch (error) {
    setStatus(`Pokémon Editor failed to initialize: ${error.message}`, "error");
  }
  const [workspaceResult] = await Promise.allSettled([loadData(), loadShiny(), pollBuild()]);
  if (workspaceResult.status === "rejected") {
    const error = workspaceResult.reason;
    state.workspaceDataError = String(error?.message || error || "Workspace data unavailable");
    applyWorkspaceCapabilities({
      profilesAvailable: false,
      routesAvailable: false,
      profileError: { message: state.workspaceDataError },
      routeError: { message: state.workspaceDataError },
    }, { failed: true });
    try {
      await Promise.resolve(ensureWorkspaceController("sounds")?.refresh?.());
    } catch (soundError) {
      applyWorkspaceCapabilities({
        profilesAvailable: false,
        capabilities: {
          pokemon: state.controllerAvailability.pokemon,
          profiles: { available: false, reason: state.workspaceDataError },
          routes: { available: false, reason: state.workspaceDataError },
          sounds: { available: false, reason: String(soundError?.message || soundError || "Sound data unavailable") },
        },
      }, { failed: true });
    }
    renderShellLoadError(error);
    if (state.activeView === "pokemon" && viewIsAvailable("pokemon")) {
      setStatus("Pokémon Editor available · optional workspace decks unavailable", "ready");
    }
  } else if (initialLocation && initialLocation.view !== "pokemon" && initialLocation.selection && viewIsAvailable(initialLocation.view)) {
    state.controllers[initialLocation.view]?.restoreSelection?.(initialLocation.selection);
  }
  const activeSelection = state.activeView === "pokemon"
    ? state.selectedPokemonKey
    : controllerSelection(state.activeView).selection;
  writeLocation(state.activeView, activeSelection, "replace");
}

state.reloadData = loadData;
state.markDirty = markDirty;
state.toast = toast;
state.openPokemonRecord = openPokemonRecord;
state.reportSelection = reportSelection;

boot();
