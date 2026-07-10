import { createProfilesController } from "/v2-assets/profiles.js";
import { createRoutesController, createSoundsController } from "/v2-assets/routes-sounds.js";

const state = {
  data: null,
  revision: "",
  conflict: false,
  busy: false,
  activeView: localStorage.getItem("ow-v2-view") || "profiles",
  controllers: {},
};

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

const elements = {};
[
  "app", "appHeader", "workspaceNav", "globalStatus", "pendingCount",
  "saveAll", "resetDraft", "buildRom", "openNds", "restartServer",
  "autoBuild", "autoRun", "showBuildLog", "buildPanel", "buildOutput",
  "profilesView", "profileSearch", "profileKindFilter", "profileLibrary",
  "profileContextSpecies", "profileContextTerrain", "profileContextLevel",
  "profileContextShiny", "resolveContext", "profileResolution", "profileInspector",
  "routesView", "routeSearch", "routeLibrary", "routeInspector",
  "soundsView", "soundSearch", "soundFilters", "soundLibrary", "soundInspector",
  "soundStatus", "shinyCounter", "refreshShiny", "resetShiny", "maxShiny",
  "reservedShinies", "toastRegion", "confirmDialog",
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

function markDirty() {
  const count = totalChangeCount();
  elements.pendingCount.textContent = String(count);
  elements.pendingCount.hidden = count === 0;
  elements.saveAll.disabled = state.busy || state.conflict || count === 0;
  elements.resetDraft.disabled = state.busy || count === 0;
  if (count > 0 && !state.busy) setStatus(`${count} draft change${count === 1 ? "" : "s"}`, "pending");
  if (count === 0 && !state.busy && !state.conflict) setStatus("Source ready", "ready");
}

function setBusy(busy) {
  state.busy = busy;
  elements.app.toggleAttribute("aria-busy", busy);
  [elements.saveAll, elements.resetDraft, elements.buildRom, elements.openNds]
    .forEach((control) => { control.disabled = busy; });
  markDirty();
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

function activateView(view) {
  state.activeView = ["profiles", "routes", "sounds"].includes(view) ? view : "profiles";
  localStorage.setItem("ow-v2-view", state.activeView);
  elements.app.dataset.view = state.activeView;
  elements.workspaceNav.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === state.activeView;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
  });
  ["profiles", "routes", "sounds"].forEach((name) => {
    const viewElement = elements[`${name}View`];
    viewElement.hidden = name !== state.activeView;
    viewElement.classList.toggle("is-active", name === state.activeView);
  });
}

function bindNavigation() {
  elements.workspaceNav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-view]");
    if (button) activateView(button.dataset.view);
  });
  elements.workspaceNav.addEventListener("keydown", (event) => {
    if (!new Set(["ArrowLeft", "ArrowRight"]).has(event.key)) return;
    const tabs = [...elements.workspaceNav.querySelectorAll("[data-view]")];
    const current = tabs.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    const offset = event.key === "ArrowRight" ? 1 : -1;
    const next = tabs[(current + offset + tabs.length) % tabs.length];
    activateView(next.dataset.view);
    next.focus();
  });
}

function controllerContext() {
  return { state, api, elements, setStatus, markDirty, confirmAction, toast };
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

  if (!state.controllers.profiles) {
    state.controllers.profiles = createProfilesController(controllerContext());
    state.controllers.routes = createRoutesController(controllerContext());
    state.controllers.sounds = createSoundsController(controllerContext());
  }
  Object.values(state.controllers).forEach((controller) => controller.refresh?.(data));
  markDirty();
}

function compactPayload(payload) {
  return Object.fromEntries(Object.entries(payload || {}).filter(([, value]) => value != null));
}

async function saveAllChanges() {
  const profilePayload = state.controllers.profiles?.commitPayload?.() || {};
  const routePayload = state.controllers.routes?.commitPayload?.() || {};
  const domains = compactPayload({ ...profilePayload, ...routePayload });
  if (!Object.keys(domains).length) return;
  if (state.conflict) {
    setStatus("Reload required before this draft can be saved.", "error");
    return;
  }

  setBusy(true);
  setStatus("Validating and saving one transaction…", "busy");
  try {
    const result = await api.post("/api/v2/commit", {
      sourceRevision: state.revision,
      ...domains,
    });
    state.revision = result.sourceRevision;
    state.controllers.profiles?.clearCommitted?.();
    state.controllers.routes?.clearCommitted?.();
    await loadData({ keepStatus: true });
    setStatus("Saved and source-verified", "success");
    toast("All draft changes were committed together.", "success");
    if (elements.autoBuild.checked) await startBuild();
  } catch (error) {
    setStatus(`Save failed: ${error.message}`, "error");
    toast(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function resetAllDrafts() {
  if (!totalChangeCount()) return;
  const confirmed = await confirmAction({
    title: "Discard every draft change?",
    message: "This clears unsaved profile, override, route, and spawn-setting edits.",
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
  elements.buildPanel.hidden = !elements.showBuildLog.checked && !running && !output;
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
  elements.buildPanel.hidden = false;
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
}

async function boot() {
  elements.showBuildLog.checked = localStorage.getItem("ow-v2-show-build-log") === "true";
  elements.autoBuild.checked = localStorage.getItem("ow-v2-auto-build") === "true";
  elements.autoRun.checked = localStorage.getItem("ow-v2-auto-run") === "true";
  elements.buildPanel.hidden = !elements.showBuildLog.checked;
  bindNavigation();
  bindGlobalActions();
  activateView(state.activeView);
  try {
    await Promise.all([loadData(), loadShiny(), pollBuild()]);
  } catch (error) {
    setStatus(`Workspace failed to load: ${error.message}`, "error");
  }
}

state.reloadData = loadData;
state.markDirty = markDirty;
state.toast = toast;

boot();
