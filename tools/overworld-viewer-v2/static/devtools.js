// UI and owctl share the same service. No emulator state is owned by this page.
const API = "/api/v2/devtools";
const byId = (id) => document.getElementById(id);
const state = { session: null, snapshot: {}, busy: false, polling: false,
  result: {}, actorDetail: null, events: [], pressed: new Set(), keyboardRunning: false,
  pendingControl: null, currentControl: null, unknownOutcomes: [],
  test: null, testRunId: null, testPolling: false, testBusy: false, testCanceling: false,
  currentTest: null, testPinned: null, testInspecting: false,
  testGeneration: 0, testErrors: [],
  explanation: null, eventTail: null,
  lastScreen: "", selectedHandle: null, selectedSubject: null, statusGeneration: 0 };
const KEY_MAP = { ArrowUp: "UP", ArrowDown: "DOWN", ArrowLeft: "LEFT", ArrowRight: "RIGHT",
  KeyZ: "A", KeyX: "B", KeyA: "Y", KeyS: "X", KeyQ: "L", KeyW: "R",
  Enter: "START", ShiftLeft: "SELECT", ShiftRight: "SELECT" };
const NUMERIC_FIELDS = new Set(["map", "x", "z", "facing", "species", "form", "level", "slot", "hp", "status"]);

function json(value) {
  return JSON.stringify(value, (key, item) => key === "url" && typeof item === "string" && item.startsWith("data:image/")
    ? "[PNG image shown above]" : item, 2);
}

function message(text, error = false) {
  byId("message").textContent = text;
  byId("message").classList.toggle("error", error);
}

function connection(ok, text) {
  byId("connection").textContent = text;
  byId("connection").dataset.ok = String(ok);
}

function formValues(form) {
  const values = {};
  for (const [key, value] of new FormData(form)) {
    const text = String(value).trim();
    if (!text) continue;
    if (NUMERIC_FIELDS.has(key)) {
      if (!/^-?\d+$/.test(text)) throw new Error(`${key} must be a whole number.`);
      values[key] = Number(text);
    } else if (key === "moves") {
      const parts = text.split(/[\s,]+/);
      if (parts.length !== 4 || parts.some((part) => !/^\d+$/.test(part))) {
        throw new Error("Moves must contain four numeric IDs. Use 0 for an empty slot.");
      }
      values[key] = parts.map(Number);
    } else values[key] = text;
  }
  return values;
}

function safeArtifactUrl(value, image = false) {
  if (typeof value !== "string") return null;
  if (image && /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(value)) return value;
  try {
    const url = new URL(value, location.origin);
    if (url.origin === location.origin && url.pathname.startsWith(API + "/artifacts/")
        && !url.username && !url.password) return url.href;
  } catch (_error) { /* The service must supply an explicit, safe artifact URL. */ }
  return null;
}

function showArtifact(artifact) {
  const url = safeArtifactUrl(artifact?.url);
  if (!url) return;
  const link = document.createElement("a");
  link.href = url;
  link.textContent = url.split("/").at(-1);
  link.download = "";
  byId("downloads").prepend(link);
  while (byId("downloads").children.length > 12) byId("downloads").lastElementChild.remove();
}

function actorHandle(actor) {
  const handle = typeof actor.handle === "object" ? actor.handle?.value : actor.handle;
  return Number.isInteger(handle) && handle > 0 ? handle : null;
}

function actorIdentityLabel(actor) {
  if (actor.identityVerified === true) return "identity verified";
  const failures = Array.isArray(actor.identityFailures) ? actor.identityFailures.join(", ") : "";
  return `WARNING: identity not verified${failures ? " · " + failures : ""}`;
}

function actorSubject(actor) {
  return {
    handle: Object.fromEntries(["value", "slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration"]
      .map((key) => [key, actor.handle?.[key]])),
    ...Object.fromEntries(["subjectIdentity", "species", "role", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"]
      .map((key) => [key, actor[key]])),
  };
}

function sameSubject(left, right) {
  return left !== null && right !== null && JSON.stringify(left) === JSON.stringify(right);
}

function verifiedDraftSubject(snapshot, selected) {
  const actors = Array.isArray(snapshot?.actors) ? snapshot.actors : [];
  const matches = actors.filter((actor) => sameSubject(actorSubject(actor), selected));
  const actor = matches.length === 1 ? matches[0] : null;
  const handle = selected?.handle || {};
  const uint = (value, minimum, maximum) => Number.isInteger(value) && minimum <= value && value <= maximum;
  if (!actor || actor.active !== true || actor.identityVerified !== true || actor.presentationAttached !== true
      || !uint(handle.slot, 0, 9) || !uint(handle.value, 1, 0xffffffff)
      || ["generation", "fieldEpoch", "mapGeneration", "encounterGeneration"].some((key) => !uint(handle[key], 1, 65535))
      || handle.value !== handle.generation * 65536 + handle.slot
      || ["subjectIdentity", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"].some((key) => !uint(selected[key], 1, 0xffffffff))
      || snapshot.context?.fieldEpoch !== handle.fieldEpoch || snapshot.context?.mapGeneration !== handle.mapGeneration) {
    throw new Error("The selected actor is missing, changed, stale, or unverified. Inspect and select it again before creating a draft.");
  }
  return actorSubject(actor);
}

function hideActorDetail() {
  state.actorDetail = null;
  state.explanation = null;
  byId("explanationSummary").textContent = "";
  byId("explanationDetail").textContent = "";
  byId("actorInspector").hidden = true;
  byId("actorRaw").open = false;
  byId("actorDetail").textContent = "";
}

function showActorDetail(actor) {
  if (state.explanation && !sameSubject(actorSubject(actor), actorSubject(state.explanation.subject || {}))) {
    state.explanation = null;
    byId("explanationSummary").textContent = "";
    byId("explanationDetail").textContent = "";
  }
  state.actorDetail = actor;
  byId("actorInspector").hidden = false;
  const handle = actorHandle(actor);
  const position = actor.logical || {};
  byId("actorSummary").textContent = `Species ${actor.species ?? "?"} · ${actor.role ?? "?"} · ${handle === null ? "no handle" : "0x" + handle.toString(16)} · ${actorIdentityLabel(actor)} · ${actor.motionKind ?? "?"}/${actor.motionPhase ?? "?"} · tile ${position.x ?? "?"}, ${position.z ?? position.y ?? "?"} · commits ${actor.commitSequence ?? "?"}.`;
  byId("actorDetail").textContent = byId("actorRaw").open ? json(actor) : "";
}

function showResult(body, op) {
  state.result = body;
  const data = body.result || {};
  const parts = [body.ok ? `${op} ${data.started ? "started" : "completed"}`
    : `${op} failed: ${body.error?.code ?? "error"} · ${body.error?.message ?? "No result"}`];
  if (data.frame !== undefined) parts.push(`frame ${data.frame}`);
  if (Array.isArray(data.actors)) parts.push(`${data.actors.length} actors`);
  if (Array.isArray(data.party)) parts.push(`${data.party.length} party entries`);
  if (data.screenshot) parts.push(`screen captured at frame ${data.screenshot.frame ?? "?"}`);
  if (data.artifact) parts.push("export ready below Recent commands");
  const summary = parts.join(" · ");
  byId("resultSummary").textContent = summary.length > 450 ? summary.slice(0, 447) + "…" : summary;
  byId("result").textContent = byId("resultRaw").open ? json(body) : "";
}

function renderActors(actors) {
  if (!Array.isArray(actors)) actors = [];
  const list = byId("actors");
  list.replaceChildren();
  if (!actors.some((actor) => actorHandle(actor) === state.selectedHandle
      && sameSubject(actorSubject(actor), state.selectedSubject))) {
    state.selectedHandle = null;
    state.selectedSubject = null;
    hideActorDetail();
  }
  if (!actors.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No active actors in this snapshot.";
    list.append(empty);
    hideActorDetail();
    return;
  }
  for (const actor of actors) {
    const handle = actorHandle(actor);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "actor";
    button.disabled = state.session?.state !== "ready" || handle === null || actor.active !== true;
    button.classList.toggle("identity-warning", actor.identityVerified !== true);
    const copy = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = actor.name || `Species ${actor.species ?? "unknown"}`;
    const detail = document.createElement("code");
    const logical = actor.logical || {};
    const coordinate = Array.isArray(logical) ? logical.join(", ")
      : `${logical.x ?? "?"}, ${logical.z ?? logical.y ?? "?"}`;
    detail.textContent = `${handle === null ? "No usable handle" : "0x" + handle.toString(16).padStart(8, "0")} · ${actorIdentityLabel(actor)} · tile ${coordinate} · ${actor.motionKind ?? "?"}/${actor.motionPhase ?? "?"}`;
    copy.append(title, detail);
    const role = document.createElement("span");
    role.className = "role";
    role.textContent = actor.role ?? "unknown role";
    button.append(copy, role);
    button.addEventListener("click", () => {
      state.selectedHandle = handle;
      state.selectedSubject = actorSubject(actor);
      showActorDetail(actor);
      command("inspect", { handle });
    });
    list.append(button);
    if (handle === state.selectedHandle) {
      showActorDetail(actor);
    }
  }
}

function renderTerrain(terrain) {
  if (!terrain) return;
  const wrapper = byId("terrainGrid");
  wrapper.replaceChildren();
  const cells = Array.isArray(terrain) ? terrain : terrain.cells;
  if (!Array.isArray(cells) || !cells.length) {
    const raw = document.createElement("pre");
    raw.className = "data";
    raw.textContent = json(terrain);
    wrapper.append(raw);
    return;
  }
  const usable = cells.filter((cell) => Number.isInteger(cell.x) && Number.isInteger(cell.z ?? cell.y));
  if (!usable.length) {
    const text = document.createElement("p");
    text.textContent = "The terrain response has no coordinate grid. See the raw result below.";
    wrapper.append(text);
    return;
  }
  const xs = [...new Set(usable.map((cell) => cell.x))].sort((a, b) => a - b);
  const zs = [...new Set(usable.map((cell) => cell.z ?? cell.y))].sort((a, b) => a - b);
  if (xs.length > 33 || zs.length > 33) {
    wrapper.textContent = "Terrain grid is too large. Use a smaller radius.";
    return;
  }
  const lookup = new Map(usable.map((cell) => [`${cell.x},${cell.z ?? cell.y}`, cell]));
  const observation = terrain.observation || {};
  // `center` is the player read in this terrain capture, not a later actor
  // snapshot. Never combine the two clocks to infer a player marker.
  const player = observation.player || observation.center;
  const playerKey = player && Number.isInteger(player.x) && Number.isInteger(player.z ?? player.y)
    ? `${player.x},${player.z ?? player.y}` : null;
  const warps = new Map();
  for (const warp of Array.isArray(terrain.warps) ? terrain.warps : []) {
    if (Number.isInteger(warp.x) && Number.isInteger(warp.z ?? warp.y)) {
      warps.set(`${warp.x},${warp.z ?? warp.y}`, warp);
    }
  }
  const caption = document.createElement("p");
  caption.className = "muted";
  caption.textContent = `${playerKey ? "P = player at this terrain sample" : "Player position not supplied by this terrain sample"} · W = loaded warp coordinate · ${observation.boundary || "sample boundary not supplied"}${observation.nativeCycle !== undefined ? ` · native cycle ${observation.nativeCycle}` : ""}${observation.lastCompletedGameFrame !== undefined ? ` · last completed game frame ${observation.lastCompletedGameFrame}` : ""}.`;
  wrapper.append(caption);
  const table = document.createElement("table");
  table.className = "terrain";
  table.setAttribute("aria-label", "Loaded terrain by world tile X and Z");
  const header = document.createElement("tr");
  header.append(document.createElement("th"));
  for (const x of xs) {
    const label = document.createElement("th");
    label.textContent = x;
    label.scope = "col";
    header.append(label);
  }
  table.append(header);
  for (const z of zs) {
    const row = document.createElement("tr");
    const label = document.createElement("th");
    label.textContent = z;
    label.scope = "row";
    row.append(label);
    for (const x of xs) {
      const cell = lookup.get(`${x},${z}`);
      const key = `${x},${z}`;
      const warp = warps.get(key);
      const isPlayer = key === playerKey;
      const tile = document.createElement("td");
      const unknown = !cell || cell.loaded === false || cell.known === false;
      tile.classList.toggle("unknown", unknown);
      tile.classList.toggle("blocked", !unknown && (cell.blocked === true || cell.collision === true));
      tile.classList.toggle("player", isPlayer);
      tile.classList.toggle("warp", Boolean(warp));
      tile.title = cell ? json({ ...cell, ...(warp ? { warp } : {}), ...(isPlayer ? { playerAtTerrainSample: true } : {}) }) : `No tile data at ${x}, ${z}`;
      const markers = [isPlayer ? "P" : "", warp ? "W" : ""].filter(Boolean).join(" ");
      tile.textContent = `${markers ? markers + " · " : ""}${unknown ? "?" : String(cell.surface ?? cell.terrain ?? cell.behavior ?? "loaded")}`;
      row.append(tile);
    }
    table.append(row);
  }
  wrapper.append(table);
}

function renderCatalog(result, kind) {
  const list = byId("catalogResults");
  list.replaceChildren();
  if (!Array.isArray(result.items)) {
    const raw = document.createElement("pre");
    raw.className = "data";
    raw.textContent = json(result);
    list.append(raw);
    return;
  }
  if (!result.items.length) list.textContent = "No matching IDs.";
  for (const item of result.items) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "actor";
    row.disabled = !Number.isInteger(item.id);
    row.textContent = `${item.id ?? "?"} · ${item.name || item.symbol || "Unnamed"}`;
    row.addEventListener("click", () => {
      if (kind === "species") {
        byId("spawnForm").elements.species.value = item.id;
        byId("partyForm").elements.species.value = item.id;
        message(`Species ${item.id} filled in the spawn and party forms. No game change was made.`);
      } else if (kind === "maps") {
        byId("teleportForm").elements.map.value = item.id;
        message(`Map ${item.id} filled in the warp form. Set X and Z before using it.`);
      } else {
        const input = byId("partyForm").elements.moves;
        const current = input.value.trim() ? input.value.split(/[\s,]+/) : ["0", "0", "0", "0"];
        if (current.length !== 4 || current.some((id) => !/^\d+$/.test(id))) {
          message(`Move ID ${item.id}. The current move list is not four IDs; correct it before adding a move.`, true);
          return;
        }
        const empty = current.findIndex((id) => Number(id) === 0);
        if (empty < 0) { message(`Move ID ${item.id}. The move list is full; choose a slot to replace in the form.`); return; }
        current[empty] = String(item.id);
        input.value = current.join(", ");
        message(`Move ${item.id} added to the party form. No game change was made.`);
      }
    });
    list.append(row);
  }
}

function renderEvents() {
  const serviceEvents = Array.isArray(state.snapshot.events) ? state.snapshot.events : [];
  const events = serviceEvents.length ? serviceEvents.slice(-40).reverse() : state.events;
  const list = byId("events");
  list.replaceChildren();
  for (const event of events) {
    const row = document.createElement("li");
    const stamp = document.createElement("time");
    stamp.textContent = event.time || `frame ${event.frame ?? "?"}`;
    const data = event.data || {};
    const failed = event.ok === false || event.kind === "error" || data.ok === false;
    row.classList.toggle("failed", failed);
    row.append(stamp, document.createTextNode(event.op || `${event.kind ?? "event"}${data.op ? ": " + data.op : ""}${data.message ? " · " + data.message : ""}`));
    list.append(row);
  }
  if (!events.length) list.textContent = "No commands yet.";
}

function render() {
  const session = state.session;
  const snapshot = state.snapshot;
  byId("sessionState").textContent = session?.state || "No session";
  byId("sessionMode").textContent = session ? `${session.mode} · ${snapshot.playing ? "playing" : "paused"}${snapshot.recording ? " · recording data" : ""}` : "—";
  byId("sessionIdentity").textContent = session ? `${session.id} / ${snapshot.frame ?? "not observed"}` : "—";
  const player = snapshot.player;
  byId("playerPosition").textContent = player
    ? `${snapshot.context?.mapId ?? snapshot.map ?? snapshot.mapId ?? player.map ?? "?"} / ${player.x ?? "?"}, ${player.z ?? player.y ?? "?"}`
    : "Not observed";
  byId("identity").textContent = session ? json(session.identity || session) : "Not loaded.";
  const recipe = session?.recipe;
  byId("recipeProgress").hidden = !recipe;
  if (recipe) {
    byId("recipeProgress").textContent = `${recipe.name}: ${recipe.state}. ${recipe.completedActions ?? 0}/${recipe.totalActions ?? "?"} actions completed${recipe.state === "running" ? ` · current action ${recipe.currentAction ?? 0}` : ""}${recipe.error?.message ? " · " + recipe.error.message : ""}.`;
  }
  for (const fieldset of document.querySelectorAll("[data-prepared]")) {
    fieldset.disabled = state.busy || Boolean(state.pendingControl || state.currentControl) || testActive() || session?.state !== "ready";
  }
  const control = state.pendingControl || state.currentControl;
  byId("controlStatus").hidden = !control;
  byId("controlStatus").textContent = control
    ? `${control.op}: ${state.pendingControl ? "queued; waiting for the current request" : "waiting for its result"}. Extra captures and key input are paused. Stop takes priority.` : "";
  byId("unknownOutcomes").hidden = !state.unknownOutcomes.length;
  byId("unknownOutcomes").textContent = state.unknownOutcomes.length
    ? `Unconfirmed requests: ${state.unknownOutcomes.map((item) => `${item.op} · ${item.requestId}: ${item.message}`).join("; ")}. Check status before retrying. None was sent again automatically.` : "";
  renderActors(snapshot.actors);
  renderEvents();
  renderTest();
  const shot = snapshot.screenshot;
  const url = safeArtifactUrl(shot?.url, true);
  if (url && url !== state.lastScreen) {
    state.lastScreen = url;
    byId("screen").src = url;
    byId("screen").hidden = false;
    byId("screenEmpty").hidden = true;
  }
  if (url) {
    const observed = snapshot.frame;
    const order = Number.isInteger(shot.frame) && Number.isInteger(observed)
      ? shot.frame === observed ? "same as the last observed frame"
        : shot.frame > observed ? "capture is newer than the last observed state" : "capture is earlier than the last observed state"
      : "frame order is not known";
    byId("screenCaption").textContent = `Captured frame ${shot.frame ?? "?"}${observed !== undefined ? ` · last observed frame ${observed}` : ""} · ${order}. Optional human view; never test proof.`;
  }
}

function applyResponse(response, { partial = false } = {}) {
  if (Object.hasOwn(response, "session")) {
    const oldId = state.session?.id;
    state.session = response.session;
    if (oldId !== state.session?.id) {
      state.snapshot = {};
      state.selectedHandle = null;
      state.selectedSubject = null;
      state.events = [];
      state.unknownOutcomes = [];
      state.result = {};
      byId("resultRaw").open = false;
      byId("result").textContent = "";
      byId("resultSummary").textContent = "No command result for this session.";
      // CLI or another tab can replace the session. A previous command's
      // frame, copied JSON, and error banner must not describe the new one.
      const error = response.error || response.result?.lastError || state.session?.lastError;
      if (error) {
        state.result = response; // Keep the new error's actual status/command envelope.
        const summary = `Session error: ${error.code || "error"} · ${error.message || "No error detail"}`;
        byId("resultSummary").textContent = summary;
        message(summary, true);
      } else {
        message(state.session?.id ? `Session ${state.session.id}. No command result for this session.`
          : "No active session. Previous command result cleared.");
      }
      state.lastScreen = "";
      byId("screen").removeAttribute("src");
      byId("screen").hidden = true;
      byId("screenEmpty").hidden = false;
      byId("screenCaption").textContent = "Images are off by default. Capture is an optional human view, never test proof.";
      byId("partyDetail").hidden = true;
      byId("partyDetail").textContent = "";
      hideActorDetail();
      byId("terrainGrid").textContent = "No terrain capture for this session.";
      state.eventTail = null;
      byId("eventTail").textContent = "";
      byId("eventTailRaw").open = false;
    }
  }
  if (response.ok && response.result && typeof response.result === "object") {
    const result = response.result;
    if (!partial) state.snapshot = { ...state.snapshot, ...result };
    else if (result.screenshot) state.snapshot.screenshot = result.screenshot;
    if (result.terrain) renderTerrain(result.terrain);
    if (result.recipes) {
      byId("recipes").hidden = false;
      byId("recipes").textContent = json(result.recipes);
    }
    showArtifact(result.artifact);
  }
  render();
}

function testActive() {
  return state.testBusy || ["starting", "running", "canceling"].includes(state.currentTest?.state);
}

function historicalTest() {
  return state.test?.historical === true || Boolean(state.testPinned
    && state.currentTest?.runId !== state.test?.runId);
}

function canCancelTest() {
  return !historicalTest() && state.testRunId === state.currentTest?.runId
    && ["starting", "running", "canceling"].includes(state.test?.state);
}

function rememberTest(runId) {
  state.testRunId = runId || null;
  byId("testRunId").value = runId || "";
  try {
    if (runId) sessionStorage.setItem("overworld-devtools-run", runId);
    else sessionStorage.removeItem("overworld-devtools-run");
  } catch (_error) { /* The current page still retains the exact ID. */ }
}

function renderTest() {
  const run = state.test;
  const active = ["starting", "running", "canceling"].includes(run?.state);
  byId("testStart").disabled = state.busy || testActive();
  byId("testCancel").disabled = !canCancelTest() || state.testCanceling;
  byId("testExport").disabled = !state.testRunId || active || state.testBusy;
  byId("testTransport").hidden = !state.testErrors.length;
  byId("testTransport").textContent = state.testErrors.join("\n");
  if (!run) return;
  const accepted = run.acceptedProof === true ? "Accepted proof" : "Not accepted proof";
  const view = historicalTest()
    ? `History — no control of this run. Current job: ${state.currentTest?.runId || "none"} (${state.currentTest?.state || "not observed"}). Use Refresh test status to follow the current job. `
    : state.testPinned ? "Selected current run. " : "Following current job. ";
  byId("testProgress").textContent = `${view}${run.test || "Checked test"}: ${run.state || "unknown"} · ${accepted}${run.runId ? " · " + run.runId : ""}. ${run.phase || ""}${run.action ? " / " + run.action : ""} · ${run.completedActions ?? 0}/${run.totalActions ?? "?"} actions · ${run.observedFrames ?? 0} observed frames · ${run.nativeCycles ?? 0} native cycles. ${run.nextAction || ""}`;
  const budget = run.budgets || {};
  byId("testLimits").textContent = `Elapsed ${run.elapsedSeconds ?? "?"}s / ${budget.maxSeconds ?? "?"}s · game frame cap ${budget.maxFrames ?? "?"} · no-progress cap ${budget.noProgressFrames ?? "?"} frames · last progress frame ${run.lastProgressFrame ?? "?"}.`;
  const subjects = run.subjects || run.evaluation?.subjects || [];
  byId("testSubject").textContent = `Subjects: ${json(subjects)}${run.lastObservation ? "\nLast observation: " + json(run.lastObservation) : ""}`;
  const failures = run.evaluation?.failures || run.failures || [];
  byId("testFailure").hidden = !failures.length && !run.failureArtifact;
  byId("testFailure").textContent = `${failures.length ? json(failures) : ""}${run.failureArtifact ? "\nFailure evidence: " + json(run.failureArtifact) : ""}`;
  byId("testManifest").textContent = run.manifest ? `Manifest: ${run.manifest}` : "No terminal manifest supplied yet.";
  byId("testDetail").textContent = byId("testRaw").open ? json(run) : "";
}

function receiveTest(run, expectedRunId = null, source = "current") {
  if (!run || typeof run !== "object" || typeof run.state !== "string") {
    throw new Error("The server did not return a checked-test state.");
  }
  if (expectedRunId && run.runId !== expectedRunId) throw new Error("Test run identity changed. The old run was not replaced; inspect the exact run ID.");
  if (source === "current") {
    state.currentTest = run;
    if (!state.testPinned || state.testPinned === run.runId) {
      state.test = run;
      rememberTest(run.runId);
    }
  } else {
    state.testPinned = expectedRunId;
    state.test = run;
    rememberTest(run.runId);
  }
  if (["starting", "running", "canceling"].includes(run.state)) {
    releaseKeyboard();
    byId("keyboard").checked = false;
  }
  renderTest();
}

async function testCommand(op, args = {}, { poll = false } = {}) {
  const readStatus = op === "test.status";
  const inspectRun = readStatus && Boolean(args.runId);
  const cancel = op === "test.cancel";
  // Status and cancel have separate slots: neither waits for a game command,
  // a start receipt, or the other request. Mutations are never auto-retried.
  if (readStatus && (inspectRun ? state.testInspecting : state.testPolling) || cancel && state.testCanceling
      || !readStatus && !cancel && state.testBusy) return null;
  if (inspectRun) state.testInspecting = true;
  else if (readStatus) state.testPolling = true;
  else if (cancel) state.testCanceling = true;
  else state.testBusy = true;
  if (!readStatus || inspectRun) state.testGeneration += 1;
  const generation = state.testGeneration;
  const requestId = crypto.randomUUID();
  if (op === "test.start") {
    releaseKeyboard();
    byId("keyboard").checked = false;
    rememberTest(null);
    state.test = null;
    state.currentTest = null;
    state.testPinned = null;
  }
  renderTest();
  let body;
  try {
    const response = await fetch(API, { method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({op, args, requestId}), signal: AbortSignal.timeout(readStatus || cancel ? 8000 : 120000) });
    body = await response.json();
    if (typeof body.ok !== "boolean") throw new Error("The server did not return a devtools result.");
    if (readStatus && generation !== state.testGeneration) return body; // Older poll cannot undo a cancel/start receipt.
    if (!body.ok) throw new Error(`${body.error?.code || "error"}: ${body.error?.message || "Test request failed."}`);
    const result = body.result || {};
    if (op === "test.list") {
      const list = byId("testName");
      const previous = list.value;
      list.replaceChildren();
      for (const test of result.tests || []) {
        const option = document.createElement("option");
        option.value = test.id;
        option.disabled = test.valid !== true;
        option.textContent = `${test.id} · ${test.valid ? test.title || test.mode : "INVALID: " + test.error}`;
        list.append(option);
      }
      if ((result.tests || []).some((test) => test.id === previous)) list.value = previous;
      byId("testCatalog").textContent = `${result.tests?.length ?? 0} saved tests. Invalid tests cannot start. Declared limits are shown in API list output and during a run.`;
    } else if (op === "test.cancel") {
      // Keep the exact receipt, but a delayed old cancel reply must not replace
      // a newer current run already observed by an independent status poll.
      if (!state.currentTest?.runId || state.currentTest.runId === args.runId) receiveTest(result, args.runId);
    } else if (["test.start", "test.status"].includes(op)) receiveTest(result, args.runId, inspectRun ? "selected" : "current");
    else if (op === "test.export") {
      if (result.run?.runId !== args.runId) throw new Error("Export returned a different test run.");
      if (state.testPinned === args.runId) receiveTest(result.run, args.runId, "selected");
      else if (state.currentTest?.runId === args.runId) receiveTest(result.run, args.runId);
      showArtifact(result.artifact);
    } else byId("testFileResult").textContent = `${op} completed. This did not run the game or grant accepted proof.`;
    if (!poll) showResult(body, op);
  } catch (error) {
    const text = body?.ok === false ? `${op}: ${error.message}`
      : `${op}: no confirmed result. Request ${requestId}. ${error.message}. Check status; no automatic retry.`;
    // Keep uncertain mutation receipts even after a successful status poll.
    if (!poll || !state.testErrors.includes(text)) state.testErrors = [...state.testErrors, text].slice(-6);
    if (!poll) showResult(body?.ok === false ? body : {ok:false,error:{code:"response-unknown",message:text,requestId}}, op);
    if (op === "test.validate" || op === "test.save") byId("testFileResult").textContent = text;
  } finally {
    if (inspectRun) state.testInspecting = false;
    else if (readStatus) state.testPolling = false;
    else if (cancel) state.testCanceling = false;
    else state.testBusy = false;
    renderTest();
  }
  return body;
}

function testStatus() {
  if (document.hidden) return;
  return testCommand("test.status", {}, {poll:true});
}

function refreshCurrentTest() {
  state.testPinned = null;
  state.testGeneration += 1;
  return testStatus();
}

async function status() {
  if (state.polling || document.hidden) return;
  state.polling = true;
  const generation = state.statusGeneration;
  try {
    const response = await fetch(API + "/status", { cache: "no-store", signal: AbortSignal.timeout(8000) });
    const body = await response.json();
    if (!response.ok || body.ok !== true) throw new Error(body.error?.message || "Status is not available.");
    connection(true, "Workshop connected");
    if (generation === state.statusGeneration) applyResponse(body);
  } catch (error) {
    connection(false, "Workshop not connected");
  } finally { state.polling = false; }
}

function controlWaiting() { return Boolean(state.pendingControl || state.currentControl); }

function queueControl(op) {
  releaseKeyboard();
  if (op === "stop") byId("keyboard").checked = false;
  // One pending control, not a mutation queue. Repeated clicks share a receipt.
  // Stop replaces a pending Pause; a later Pause must never replace Stop.
  if (state.pendingControl) {
    if (op === "stop") state.pendingControl.op = "stop";
    render();
    return state.pendingControl.promise;
  }
  if (state.currentControl && (state.currentControl.op === "stop" || state.currentControl.op === op)) {
    return state.currentControl.promise;
  }
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  state.pendingControl = {op, promise, resolve, sessionId: state.session?.id};
  drainControl();
  render();
  return promise;
}

async function drainControl() {
  if (state.busy || state.currentControl || !state.pendingControl) return;
  const control = state.pendingControl;
  state.pendingControl = null;
  state.currentControl = control;
  let result;
  try {
    if (control.sessionId !== state.session?.id) {
      result = {ok:false, error:{code:"control-session-changed", message:"The session changed while the control was queued. Check state and choose the control again."}};
      showResult(result, control.op);
      message(result.error.message, true);
    } else result = await runCommand(control.op, {}, {priority:true});
  } finally {
    state.currentControl = null;
    control.resolve(result);
    render();
    drainControl();
  }
}

function command(op, args = {}, options = {}) {
  if (op.startsWith("test.")) return testCommand(op, args);
  if (testActive()) {
    message("A checked test owns the session. Use its status or Cancel this run.", true);
    return Promise.resolve(null);
  }
  if ((op === "pause" || op === "stop") && Object.keys(args).length === 0) return queueControl(op);
  return runCommand(op, args, options);
}

async function runCommand(op, args = {}, { quiet = false, priority = false } = {}) {
  if (state.busy || (!priority && controlWaiting())) {
    if (!quiet) message("A command is still running. Wait for its result.", true);
    return null;
  }
  state.busy = true;
  state.statusGeneration += 1;
  render();
  const requestId = crypto.randomUUID();
  if (!quiet) message(`${op} is running…`);
  if (op === "capture" && byId("screen").hidden) byId("screenEmpty").textContent = "Capture is running…";
  let body;
  try {
    const response = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op, args, requestId }), signal: AbortSignal.timeout(120000) });
    body = await response.json();
    if (typeof body.ok !== "boolean") throw new Error("The server did not return a devtools result.");
    connection(true, "Workshop connected");
    // A filtered inspect must not replace the full current actor inventory.
    applyResponse(body, { partial: op === "inspect" && args.handle !== undefined
      || ["explain", "compare", "checkpoint", "events", "diagnostics", "catalog"].includes(op) });
    if (op === "inspect" && args.handle !== undefined && body.ok) {
      const actor = body.result?.actors?.find((item) => actorHandle(item) === args.handle);
      if (actor) showActorDetail(actor);
    }
    if (!quiet || !body.ok) {
      showResult(body, op);
      const success = body.result?.started
        ? `${op} started. Watch its progress; it has not completed yet.`
        : op === "capture" && body.result?.screenshot ? `Capture completed at frame ${body.result.screenshot.frame}.` : `${op} completed.`;
      message(body.ok ? success : `${body.error?.code || "error"}: ${body.error?.message || "Command failed."}`, !body.ok);
    }
    state.events.unshift({ op, ok: body.ok, time: new Date().toLocaleTimeString() });
    state.events.length = Math.min(state.events.length, 40);
    if (!body.ok) releaseKeyboard();
  } catch (error) {
    releaseKeyboard();
    body = { ok: false, error: { code: "response-unknown", message: String(error), requestId } };
    // A later confirmed Pause must not erase the uncertain preceding receipt.
    state.unknownOutcomes.push({op, requestId, message:String(error)});
    state.unknownOutcomes = state.unknownOutcomes.slice(-4);
    showResult(body, op);
    message(`No confirmed result. Request ${requestId}. Check status before retrying; this request is not sent again automatically.`, true);
  } finally {
    state.statusGeneration += 1;
    state.busy = false;
    if (op === "capture" && byId("screen").hidden) byId("screenEmpty").textContent = "No capture available. Check the command result.";
    render();
    drainControl();
  }
  return body;
}

async function capture() {
  if (state.busy || controlWaiting() || testActive() || document.hidden || state.session?.state !== "ready") return;
  return command("capture");
}

function releaseKeyboard() { state.pressed.clear(); }

async function keyboardPump() {
  if (state.keyboardRunning) return;
  state.keyboardRunning = true;
  try {
    while (byId("keyboard").checked && state.pressed.size && !controlWaiting() && !testActive() && !document.hidden && document.hasFocus()) {
      if (!state.busy) {
        const keys = [...state.pressed];
        // Opposed directions are not guessed. Wait until one is released.
        if (!(keys.includes("UP") && keys.includes("DOWN")) && !(keys.includes("LEFT") && keys.includes("RIGHT"))) {
          const result = await command("step", { frames: 8, keys }, { quiet: true });
          if (result && !result.ok) break;
        }
      }
      await new Promise((resolve) => setTimeout(resolve, 30));
    }
  } finally { state.keyboardRunning = false; }
}

document.addEventListener("keydown", (event) => {
  if (!byId("keyboard").checked || controlWaiting() || testActive() || event.ctrlKey || event.metaKey || event.altKey
      || event.target.closest("input, textarea, select, [contenteditable=true]")) return;
  const key = KEY_MAP[event.code];
  if (!key) return;
  event.preventDefault();
  state.pressed.add(key);
  keyboardPump();
});
document.addEventListener("keyup", (event) => { state.pressed.delete(KEY_MAP[event.code]); });
window.addEventListener("blur", releaseKeyboard);
document.addEventListener("visibilitychange", () => { if (document.hidden) releaseKeyboard(); else status(); });
byId("keyboard").addEventListener("change", async () => {
  releaseKeyboard();
  if (byId("keyboard").checked) {
    const paused = await command("pause");
    if (!paused?.ok) byId("keyboard").checked = false;
  }
});

function wireForm(id, op) {
  byId(id).addEventListener("submit", async (event) => {
    event.preventDefault();
    releaseKeyboard();
    try { await command(op, formValues(event.currentTarget)); }
    catch (error) { message(error.message, true); }
  });
}
wireForm("startForm", "start");
wireForm("teleportForm", "teleport");
wireForm("spawnForm", "spawn");
wireForm("partyForm", "party");
byId("draftForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  releaseKeyboard();
  try {
    const values = formValues(event.currentTarget);
    const selected = state.selectedSubject;
    const sessionId = state.session?.id;
    if (!selected || state.session?.state !== "ready") throw new Error("Select a current verified actor before creating a draft.");
    // Validate the selection the user made, then re-read that exact handle.
    // Never substitute a new actor merely because it occupies the same slot.
    verifiedDraftSubject(state.snapshot, selected);
    const observed = await command("inspect", { handle: selected.handle.value });
    if (!observed?.ok || observed.session?.id !== sessionId || state.session?.id !== sessionId
        || !sameSubject(selected, state.selectedSubject)) {
      throw new Error("The selected actor or session changed during inspection. Select it again.");
    }
    const subject = verifiedDraftSubject(observed.result, selected);
    await command("scenario.draft", { ...values, subject });
  } catch (error) { message(error.message, true); }
});
byId("catalogForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = formValues(event.currentTarget);
  const response = await command("catalog", { ...values, limit: 20 });
  if (response?.ok) renderCatalog(response.result, values.kind);
});
byId("partyRead").addEventListener("click", async () => {
  const response = await command("inspect");
  if (response?.ok) {
    byId("partyDetail").hidden = false;
    byId("partyDetail").textContent = response.result.party
      ? json(response.result.party) : "No party summary is available in this snapshot. The complete inspect result is below.";
  }
});
byId("recipeForm").addEventListener("submit", (event) => {
  event.preventDefault();
  releaseKeyboard();
  const action = event.submitter?.value;
  if (!["save", "load"].includes(action)) return;
  command("recipe." + action, formValues(event.currentTarget));
});
byId("recipeList").addEventListener("click", () => command("recipe.list"));
byId("commandForm").addEventListener("submit", (event) => {
  event.preventDefault();
  releaseKeyboard();
  try {
    const values = new FormData(event.currentTarget);
    const args = JSON.parse(values.get("args") || "{}");
    if (!args || Array.isArray(args) || typeof args !== "object") throw new Error("Arguments must be a JSON object.");
    command(String(values.get("op")).trim(), args);
  } catch (error) { message(error.message, true); }
});
for (const button of document.querySelectorAll("[data-op]")) {
  button.addEventListener("click", () => {
    releaseKeyboard();
    if (button.dataset.op === "play") byId("keyboard").checked = false;
    command(button.dataset.op);
  });
}
byId("step").addEventListener("click", () => {
  releaseKeyboard();
  const keys = byId("stepKeys").value.toUpperCase().split(/[\s,+]+/).filter(Boolean);
  command("step", { frames: Number(byId("stepFrames").value), keys });
});
byId("capture").addEventListener("click", capture);
byId("terrain").addEventListener("click", () => command("terrain", { radius: Number(byId("terrainRadius").value) }));
byId("refresh").addEventListener("click", status);
byId("help").addEventListener("click", () => command("help"));
byId("copyResult").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(JSON.stringify(state.result, null, 2)); message("Result JSON copied."); }
  catch (_error) { message("Clipboard is not available. Select and copy the result below.", true); }
});
byId("resultRaw").addEventListener("toggle", () => {
  byId("result").textContent = byId("resultRaw").open ? json(state.result) : "";
});
byId("actorRaw").addEventListener("toggle", () => {
  byId("actorDetail").textContent = byId("actorRaw").open && state.actorDetail ? json(state.actorDetail) : "";
});
byId("actorExplain").addEventListener("click", async () => {
  const selected = state.selectedSubject;
  const sessionId = state.session?.id;
  if (!selected) return;
  const body = await command("explain", {handle:selected.handle.value});
  if (!body?.ok) return;
  if (sessionId !== state.session?.id || !sameSubject(selected, state.selectedSubject)
      || !sameSubject(selected, actorSubject(body.result?.subject || {}))) {
    message("The selected actor changed during Explain. Select the current actor again.", true);
    return;
  }
  state.explanation = body.result;
  byId("explanationSummary").textContent = `Observed frame ${body.result.frame ?? "?"} · ${actorIdentityLabel(body.result.subject)} · profile ${body.result.profileStatus} · decision ${body.result.decision?.lastDecisionName ?? "unknown"}. ${body.result.scope || ""}`;
  byId("explanationDetail").textContent = byId("explanationRaw").open ? json(state.explanation) : "";
});
byId("explanationRaw").addEventListener("toggle", () => {
  byId("explanationDetail").textContent = byId("explanationRaw").open && state.explanation ? json(state.explanation) : "";
});
byId("checkpoint").addEventListener("click", async () => {
  const body = await command("checkpoint");
  const url = safeArtifactUrl(body?.result?.artifact?.url);
  if (!body?.ok || !url) return;
  const relative = new URL(url).pathname.slice((API + "/artifacts/").length);
  const input = byId("compareLeft").value.trim() ? byId("compareRight") : byId("compareLeft");
  input.value = relative;
  byId("compareResult").textContent = `Saved ${relative}. The game was not changed.`;
});
byId("compareForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = await command("compare", formValues(event.currentTarget));
  if (body?.ok) byId("compareResult").textContent = `${body.result.equal ? "Exact JSON values match." : "First JSON difference: " + json(body.result.firstDifference)} ${body.result.scope || "Diagnostic only."}`;
});
byId("readEvents").addEventListener("click", async () => {
  const body = await command("events", {limit:30});
  if (!body?.ok) return;
  state.eventTail = body.result;
  byId("eventTailRaw").open = true;
  byId("eventTail").textContent = json(state.eventTail);
});
byId("eventTailRaw").addEventListener("toggle", () => {
  byId("eventTail").textContent = byId("eventTailRaw").open && state.eventTail ? json(state.eventTail) : "";
});
byId("testList").addEventListener("click", () => testCommand("test.list"));
byId("testRefresh").addEventListener("click", refreshCurrentTest);
byId("testStartForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const name = byId("testName").value;
  if (name) return testCommand("test.start", {name});
  message("List tests and choose a saved test first.", true);
});
byId("testRunForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const runId = byId("testRunId").value.trim();
  return runId ? testCommand("test.status", {runId}) : refreshCurrentTest();
});
byId("testCancel").addEventListener("click", () => {
  if (canCancelTest()) return testCommand("test.cancel", {runId:state.testRunId});
});
byId("testExport").addEventListener("click", () => {
  if (state.testRunId) return testCommand("test.export", {runId:state.testRunId});
});
byId("testRaw").addEventListener("toggle", renderTest);
byId("testFileForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const action = event.submitter?.value;
    if (!["validate", "save"].includes(action)) return;
    const file = byId("testFile").files?.[0];
    if (!file || file.size > 262144) throw new Error("Choose a UTF-8 JSON test file of at most 256 KiB.");
    const test = JSON.parse(await file.text());
    if (!test || Array.isArray(test) || typeof test !== "object") throw new Error("The test file must contain a JSON object.");
    const args = {test};
    if (action === "save") args.name = byId("testSaveName").value.trim();
    return await testCommand("test." + action, args);
  } catch (error) { byId("testFileResult").textContent = error.message; }
});
try { rememberTest(sessionStorage.getItem("overworld-devtools-run")); }
catch (_error) { /* Storage is optional; status discovers the current run. */ }

// Poll cached state only. Images require an explicit Capture click; data
// recording and play never request screenshots or video.
setInterval(async () => {
  if (!testActive()) await status();
}, 500);
// Deliberately separate from cached session status: the game worker may be
// inside a bounded call while the job status/cancel lock remains available.
setInterval(testStatus, 500);
testStatus();
status();
