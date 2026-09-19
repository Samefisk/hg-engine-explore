// Host DOM binding checks only. This does not render a browser or run a ROM.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

class Element {
  constructor() {
    this.hidden = false; this.open = false; this.disabled = false;
    this.children = []; this.dataset = {}; this.listeners = {};
    this.textContent = "";
    const classes = new Set();
    this.classList = { toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); },
      contains(name) { return classes.has(name); } };
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...nodes) { this.children.push(...nodes); }
  prepend(node) { this.children.unshift(node); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
  get lastElementChild() { return this.children.at(-1); }
}

async function run() {
  const source = fs.readFileSync(process.argv[2], "utf8");
  const html = fs.readFileSync(process.argv[3], "utf8");
  const mode = process.argv[4];
  const elements = new Map();
  for (const tag of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
    const element = new Element();
    element.hidden = /\bhidden\b/.test(tag[0]);
    elements.set(tag[1], element);
  }
  const element = (id) => {
    assert(elements.has(id), `Actual HTML lacks #${id}`);
    return elements.get(id);
  };
  const fields = [new Element(), new Element(), new Element()];
  const buttons = [...html.matchAll(/<button\b[^>]*\bdata-op="([^"]+)"[^>]*>/g)].map((tag) => {
    const button = new Element(); button.dataset.op = tag[1]; return button;
  });
  const documentListeners = {};
  const intervals = [];
  let requestSequence = 0;
  const png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB";
  let capture = { ok: true, session: { id: "session-host", state: "ready", mode: "normal" },
    result: { screenshot: { url: png, frame: 20, sha256: "host-only" } } };
  if (process.argv[5]) capture = JSON.parse(fs.readFileSync(process.argv[5], "utf8"));
  let session = capture.session;
  let snapshot = { frame: capture.result.screenshot.frame, actors: [], player: { x: 1, z: 2 } };
  const sent = [];
  let commandResult = capture;
  let commandHandler = null;
  const storage = new Map();
  const context = vm.createContext({
    console, URL, Promise, setTimeout, clearTimeout,
    setInterval(callback) { intervals.push(callback); return intervals.length; },
    crypto: { randomUUID: () => `host-request-${++requestSequence}` },
    performance: { now: () => 1000 },
    AbortSignal: { timeout: () => null },
    location: { origin: "http://127.0.0.1:8766" },
    navigator: {},
    sessionStorage: {getItem: (key) => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key)},
    FormData: class {
      constructor(form) { this.values = form.formValues || []; }
      [Symbol.iterator]() { return this.values[Symbol.iterator](); }
      get(key) { return this.values.find(([name]) => name === key)?.[1]; }
    },
    window: { addEventListener() {} },
    document: { hidden: false, hasFocus: () => true, getElementById: element,
      addEventListener(name, callback) { documentListeners[name] = callback; },
      querySelectorAll: (selector) => selector === "[data-prepared]" ? fields : selector === "[data-op]" ? buttons : [],
      createElement: () => new Element(), createTextNode: (text) => ({ textContent: text }) },
    fetch: async (url, options = {}) => {
      if (options.method === "POST") {
        const request = JSON.parse(options.body);
        sent.push(request);
        return { ok: true, json: async () => commandHandler ? commandHandler(request)
          : request.op === "test.status" ? {ok:true,result:{state:"idle",acceptedProof:false}} : commandResult };
      }
      return { ok: true, json: async () => ({ ok: true, session, result: snapshot }) };
    },
  });
  vm.runInContext(source + "\nglobalThis.ui = {state, status, command, applyResponse, testStatus};", context);
  await new Promise(setImmediate); // Complete the real script's initial status poll.
  const startupRequests = sent.map((request) => request.op);
  sent.length = 0; // The implicit startup test-status discovery is read-only.

  if (mode === "manual-capture-only" || mode === "no-timer-capture") {
    // Execute real DOM handlers and installed timers. Assert requests only;
    // no pixels, image decoding, screenshots, video or emulator are used.
    const flush = () => new Promise(setImmediate);
    const click = (op) => buttons.find((button) => button.dataset.op === op).listeners.click();
    const noCapture = (trigger) => assert(!sent.some((request) => request.op === "capture"),
      `${trigger} must not request an image without a Capture click`);
    assert(!startupRequests.includes("capture"), "page load must not request an image");
    assert(html.includes("Recording saves native memory and trace events, not images or video."));
    for (const label of ["Start data recording", "Stop data recording", "Export data recording"])
      assert(html.includes(`>${label}</button>`), `recording label must describe data: ${label}`);
    assert(element("screenCaption").textContent.includes("never test proof"));
    commandHandler = (request) => {
      if (request.op === "test.status") return {ok:true,result:{state:"idle",acceptedProof:false}};
      if (request.op === "play") snapshot = {...snapshot, playing:true};
      if (request.op === "step") documentListeners.keyup({code:"ArrowRight"});
      return {ok:true,session,result:snapshot};
    };
    if (mode === "manual-capture-only") {
      for (const [id, op] of [["startForm","start"], ["teleportForm","teleport"], ["spawnForm","spawn"], ["partyForm","party"]]) {
        const form = element(id);
        await form.listeners.submit({preventDefault(){},currentTarget:form});
        await flush();
        assert(sent.some((request) => request.op === op), `${id} must still send ${op}`);
        noCapture(op);
      }
      const recipe = element("recipeForm"); recipe.formValues = [["name","host-route"]];
      recipe.listeners.submit({preventDefault(){},currentTarget:recipe,submitter:{value:"load"}});
      await flush();
      assert.equal(sent.at(-1).op, "recipe.load"); noCapture("recipe load");
      for (const op of ["reset", "record.start", "record.stop", "recording.export"]) {
        click(op); await flush();
        assert.equal(sent.at(-1).op, op); noCapture(op);
      }
      context.ui.applyResponse({ok:true,session,result:{...snapshot,recording:true}});
      assert(element("sessionMode").textContent.includes("recording data"));
      element("stepFrames").value = "1"; element("stepKeys").value = "RIGHT";
      element("step").listeners.click(); await flush();
      assert.equal(sent.at(-1).op, "step"); noCapture("step button");
      const beforeKeyboard = sent.length;
      element("keyboard").checked = true;
      documentListeners.keydown({code:"ArrowRight",target:{closest:()=>false},preventDefault(){}});
      await flush();
      assert.equal(sent.length, beforeKeyboard + 1); assert.equal(sent.at(-1).op, "step");
      noCapture("keyboard step");
      element("keyboard").checked = false;
    }
    click("play"); await flush();
    assert.equal(sent.at(-1).op, "play"); noCapture("play");
    for (let i = 0; i < 3; i += 1) {
      await context.ui.status();
      documentListeners.visibilitychange(); await flush();
      for (const timer of intervals) { await timer(); await flush(); }
      noCapture("status, visibility and playing timers");
    }
    await element("capture").listeners.click();
    assert.equal(sent.filter((request) => request.op === "capture").length, 1,
      "the explicit Capture click must still request exactly one image");
  } else if (mode === "capture") {
    assert.equal(element("screen").hidden, true);
    await element("capture").listeners.click();
    assert.equal(sent.at(-1).op, "capture");
    assert.equal(element("screen").hidden, false);
    assert.equal(element("screen").src, capture.result.screenshot.url);
    assert.equal(element("screenEmpty").hidden, true);
    assert(element("screenCaption").textContent.includes(String(capture.result.screenshot.frame)));
    context.ui.applyResponse({ ok: true, session: { ...session, id: "new-session" }, result: {} });
    assert.equal(element("screen").hidden, true);
    // A capture created by the CLI appears through cached status while paused.
    snapshot = { ...snapshot, screenshot: capture.result.screenshot };
    await context.ui.status();
    assert.equal(element("screen").src, capture.result.screenshot.url);
    assert.equal(element("screen").hidden, false);
    assert.equal(sent.length, 1, "status must not ask the emulator to capture again");
  } else if (mode === "priority-controls") {
    const flush = () => new Promise(setImmediate);
    const click = (op) => buttons.find((button) => button.dataset.op === op).listeners.click();
    function deferred() {
      let resolve, reject;
      const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
      return {promise, resolve, reject};
    }
    async function heldCapture(id) {
      session = {...session, id, state:"ready"};
      snapshot = {frame:20, actors:[], playing:true};
      context.ui.applyResponse({ok:true, session, result:snapshot});
      const pending = deferred();
      commandHandler = (request) => {
        if (request.op === "capture") return pending.promise;
        snapshot = {...snapshot, playing:false};
        if (request.op === "stop") session = {...session, state:"stopped"};
        return {ok:true, session, result:snapshot};
      };
      const start = sent.length;
      element("capture").listeners.click(); // Only an explicit user action starts capture.
      await flush();
      assert.deepEqual(sent.slice(start).map((request) => request.op), ["capture"]);
      return {pending, start};
    }
    let run = await heldCapture("pause-after-capture");
    click("pause"); click("pause");
    assert.equal(context.ui.state.pendingControl?.op, "pause", "Pause must be queued, not dropped while capture is unresolved");
    assert(element("controlStatus").textContent.includes("pause"));
    element("keyboard").checked = true;
    documentListeners.keydown({code:"ArrowRight",target:{closest:()=>false},preventDefault(){}});
    await intervals[0]();
    assert.equal(context.ui.state.pressed.size, 0, "pending Pause must discard key input, not defer it until after Pause");
    assert.deepEqual(sent.slice(run.start).map((request) => request.op), ["capture"]);
    run.pending.resolve({ok:true, session, result:{screenshot:{url:png,frame:23}}});
    await flush();
    assert.deepEqual(sent.slice(run.start).map((request) => request.op), ["capture","pause"]);
    assert.equal(context.ui.state.snapshot.playing, false);
    assert.equal(context.ui.state.pendingControl, null);
    assert.equal(context.ui.state.currentControl, null);

    run = await heldCapture("stop-wins");
    click("pause"); click("stop"); click("pause"); click("stop");
    assert.equal(context.ui.state.pendingControl.op, "stop", "one pending Stop replaces Pause and cannot be downgraded");
    run.pending.resolve({ok:true, session, result:{screenshot:{url:png,frame:23}}});
    await flush();
    assert.deepEqual(sent.slice(run.start).map((request) => request.op), ["capture","stop"]);
    assert.equal(context.ui.state.session.state, "stopped");

    run = await heldCapture("unknown-capture-result");
    click("pause");
    const unknownId = sent[run.start].requestId;
    run.pending.reject(new Error("Synthetic connection ended before the capture receipt"));
    await flush();
    assert.deepEqual(sent.slice(run.start).map((request) => request.op), ["capture","pause"], "an unknown result must not retry capture");
    assert.equal(context.ui.state.snapshot.playing, false);
    assert.equal(element("unknownOutcomes").hidden, false);
    assert(element("unknownOutcomes").textContent.includes(unknownId), "successful Pause must not hide the preceding unknown request ID");
    assert(element("unknownOutcomes").textContent.includes("capture"));

    // Repeated clicks during the control's own unresolved request also coalesce.
    session = {...session, id:"pause-in-flight", state:"ready"};
    context.ui.applyResponse({ok:true, session, result:{frame:30, actors:[], playing:true}});
    const pause = deferred();
    commandHandler = (request) => request.op === "pause" ? pause.promise
      : {ok:true, session:{...session,state:"stopped"}, result:{playing:false}};
    const start = sent.length;
    click("pause"); click("pause"); click("stop"); click("pause"); click("stop");
    assert.deepEqual(sent.slice(start).map((request) => request.op), ["pause"]);
    pause.resolve({ok:true, session, result:{playing:false}});
    await flush();
    assert.deepEqual(sent.slice(start).map((request) => request.op), ["pause","stop"]);
    assert.equal(new Set(sent.map((request) => request.requestId)).size, sent.length);
  } else if (mode === "caption-order") {
    for (const [captured, observed, expected, forbidden] of [
      [2683,2464,"newer than the last observed state","earlier"],
      [2464,2683,"earlier than the last observed state","newer"],
      [2464,2464,"same as the last observed frame","earlier"],
      [2683,undefined,"frame order is not known","earlier"],
      [undefined,2464,"frame order is not known","newer"],
    ]) {
      context.ui.applyResponse({ok:true,session,result:{frame:observed,screenshot:{url:png,frame:captured}}});
      const caption = element("screenCaption").textContent;
      assert(caption.includes(expected), caption);
      assert(!caption.includes(forbidden), caption);
      assert(!caption.includes("current frame"), "a cached snapshot is not the current emulator frame");
    }
  } else if (mode === "session-change") {
    // A real manual command belongs to the old session, even when another
    // client later replaces the session and publishes a newer cached image.
    commandResult = {ok:true, session, result:{screenshot:{url:png, frame:2814}}};
    await context.ui.command("capture");
    assert(element("message").textContent.includes("2814"));
    assert(element("resultSummary").textContent.includes("2814"));
    element("resultRaw").open = true;
    element("resultRaw").listeners.toggle();
    element("partyDetail").hidden = false;
    element("partyDetail").textContent = "Old party at frame 2814";
    await context.ui.status();
    assert(element("resultSummary").textContent.includes("2814"), "same-session polls retain the last command");

    session = {...session, id:"session-replaced-by-cli"};
    snapshot = {frame:757, actors:[], events:[], screenshot:{url:png, frame:729}};
    await context.ui.status();
    assert(!element("message").textContent.includes("2814"), "old command banner must not name the new session");
    assert(element("message").textContent.includes(session.id));
    assert(!element("resultSummary").textContent.includes("2814"));
    assert(element("resultSummary").textContent.includes("No command result"));
    assert.equal(element("resultRaw").open, false);
    assert.equal(element("result").textContent, "");
    assert.equal(JSON.stringify(context.ui.state.result), "{}", "Copy JSON must not copy the previous session result");
    assert.equal(context.ui.state.events.length, 0, "old local commands must not fill an empty new history");
    assert.equal(element("partyDetail").hidden, true);
    assert.equal(element("partyDetail").textContent, "");
    assert(element("screenCaption").textContent.includes("Captured frame 729"));
    assert(element("screenCaption").textContent.includes("last observed frame 757"));
    assert.equal(sent.length, 1, "session replacement must not issue a command");

    for (const source of ["result", "session"]) {
      const error = {code:"new-session-failure", message:"New subject was not present", details:{frame:9}};
      session = {id:`session-with-${source}-error`, state:"ready", mode:"prepared"};
      snapshot = {frame:9, actors:[], events:[]};
      if (source === "result") snapshot.lastError = error;
      else session.lastError = error;
      await context.ui.status();
      assert(element("message").classList.contains("error"));
      assert(element("message").textContent.includes(error.code));
      assert(element("message").textContent.includes(error.message));
      assert(element("resultSummary").textContent.includes(error.code));
      assert.equal(context.ui.state.result[source].lastError.code, error.code,
        "new error remains available in the original status response");
      element("resultRaw").open = true;
      element("resultRaw").listeners.toggle();
      assert(element("result").textContent.includes(error.code));
    }
    // Service loss is also a context change. It must clear the old error.
    session = null;
    snapshot = {};
    await context.ui.status();
    assert(!element("message").classList.contains("error"));
    assert(!element("message").textContent.includes("new-session-failure"));
    assert.equal(JSON.stringify(context.ui.state.result), "{}");
  } else if (mode === "compact") {
    commandResult = { ok: true, session, result: { frame: 30, actors: [],
      hugeRawInspector: Array(10000).fill("diagnostic data") } };
    await context.ui.command("inspect");
    assert.equal(element("resultRaw").open, false);
    assert.equal(element("result").textContent, "", "closed raw JSON must not remain in the DOM");
    assert(element("resultSummary").textContent.length < 500);
    element("resultRaw").open = true;
    element("resultRaw").listeners.toggle();
    assert(element("result").textContent.includes("hugeRawInspector"));
    element("resultRaw").open = false;
    element("resultRaw").listeners.toggle();
    assert.equal(element("result").textContent, "");
  } else if (mode === "invalid-actor") {
    const actor = {handle:{value:131072}, active:true, identityVerified:false,
      identityFailures:["presentation-attached", "engine-in-manager"], role:"WILD", species:165,
      logical:{x:550,y:376}, motionKind:"NONE", motionPhase:"IDLE"};
    commandResult = {ok:true, session, result:{actors:[actor]}};
    context.ui.applyResponse(commandResult);
    const button = element("actors").children[0];
    assert.equal(button.disabled, false, "bad identity must remain inspectable");
    assert(button.classList.contains("identity-warning"));
    button.listeners.click();
    await new Promise(setImmediate);
    assert.equal(sent.at(-1).op, "inspect");
    assert.equal(sent.at(-1).args.handle, actor.handle.value);
    assert.equal(context.ui.state.actorDetail.identityVerified, false);
    assert(element("actorSummary").textContent.includes("engine-in-manager"));
    context.ui.applyResponse({ok:true, session, result:{actors:[{...actor, active:false}]}});
    assert.equal(element("actors").children[0].disabled, true);
  } else if (mode === "draft-subject") {
    const actor = {handle:{value:131072,slot:0,generation:2,fieldEpoch:4,mapGeneration:5,encounterGeneration:6},
      active:true,identityVerified:true,presentationAttached:true,subjectIdentity:0xf0000001,
      role:"WILD",species:165,authorityGeneration:3,engineAnchorGeneration:4,presentationGeneration:5,
      logical:{x:550,y:376},motionKind:"NONE",motionPhase:"IDLE"};
    const owner = {fieldEpoch:4,mapGeneration:5};
    element("draftForm").formValues = [["name","selected-ledyba"],["expectation","Completes its chain pause"]];
    let observed = actor;
    let observedContext = owner;
    commandHandler = (request) => request.op === "inspect"
      ? {ok:true,session,result:{frame:31,context:observedContext,actors:observed ? [observed] : []}}
      : {ok:true,session,result:{draft:{subject:request.args.subject,status:"planned",acceptedProof:false}}};
    async function choose() {
      observed = structuredClone(actor); observedContext = structuredClone(owner);
      context.ui.applyResponse({ok:true,session,result:{frame:30,context:owner,actors:[actor]}});
      element("actors").children[0].listeners.click();
      await new Promise(setImmediate);
    }
    async function submit() {
      await element("draftForm").listeners.submit({preventDefault(){},currentTarget:element("draftForm")});
      await new Promise(setImmediate);
    }
    await choose();
    const before = sent.length;
    await submit();
    assert.deepEqual(sent.slice(before).map((request) => request.op), ["inspect","scenario.draft"],
      "the installed draft form must refresh the chosen actor before sending a draft");
    const subject = sent.at(-1).args.subject;
    for (const field of ["handle","subjectIdentity","species","role","authorityGeneration","engineAnchorGeneration","presentationGeneration"]) {
      assert.deepEqual(subject[field], actor[field], `draft must retain exact ${field}`);
    }
    const mutations = [
      () => { observed = null; },
      () => { observed.identityVerified = false; },
      () => { observed.presentationAttached = false; },
      () => { observed.active = false; },
      () => { observed.subjectIdentity++; },
      () => { observed.species++; },
      () => { observed.role = "FOLLOWER"; },
      () => { observed.handle.mapGeneration++; },
      () => { observed.authorityGeneration++; },
      () => { observed.engineAnchorGeneration++; },
      () => { observed.presentationGeneration++; },
      () => { observedContext.fieldEpoch++; },
      () => { observedContext.mapGeneration++; },
    ];
    for (const mutate of mutations) {
      await choose();
      mutate();
      const count = sent.filter((request) => request.op === "scenario.draft").length;
      await submit();
      assert.equal(sent.filter((request) => request.op === "scenario.draft").length, count,
        "stale/unverified selection must never be silently replaced in a draft");
      assert(element("message").classList.contains("error"));
    }
    await choose();
    session = {...session,id:"different-session"};
    context.ui.applyResponse({ok:true,session,result:{frame:3,context:owner,actors:[actor]}});
    const count = sent.length;
    await submit();
    assert.equal(sent.length, count, "session replacement clears draft selection even with the same numeric handle");
  } else if (mode === "checked-tests") {
    const flush = () => new Promise(setImmediate);
    let resolveCapture;
    const pendingCapture = new Promise((resolve) => { resolveCapture = resolve; });
    let run = {runId:"test-exact",test:"ledyba",state:"starting",phase:"boot",acceptedProof:false,
      budgets:{maxFrames:5000,maxSeconds:120,noProgressFrames:100},observedFrames:0,nativeCycles:4,
      totalActions:3,completedActions:0,nextAction:"Booting",manifest:"build/test-exact/manifest.json"};
    let pendingStatus = null;
    commandHandler = (request) => {
      if (request.op === "capture") return pendingCapture;
      if (request.op === "test.status") return pendingStatus || {ok:true,result:run};
      if (request.op === "test.cancel") return {ok:true,result:{...run,state:"canceling"}};
      if (request.op === "test.export") return {ok:true,result:{run,artifact:{url:"/api/v2/devtools/artifacts/test-exact/manifest.json"}}};
      return {ok:true,result:run};
    };
    const capturePromise = element("capture").listeners.click();
    await flush();
    assert.equal(context.ui.state.busy, true);
    await intervals[1](); // Installed test poll is independent of blocked capture/boot.
    assert.equal(context.ui.state.testRunId, "test-exact");
    assert.equal(element("testRunId").value, "test-exact");
    assert.equal(storage.get("overworld-devtools-run"), "test-exact");
    assert.equal(element("testCancel").disabled, false);
    assert(element("testProgress").textContent.includes("Not accepted proof"));
    assert(element("testLimits").textContent.includes("5000"));
    let resolveStatus;
    pendingStatus = new Promise((resolve) => { resolveStatus = resolve; });
    const statusPromise = element("testRefresh").listeners.click();
    await flush();
    await element("testCancel").listeners.click();
    assert.deepEqual(sent.map((request) => request.op), ["capture","test.status","test.status","test.cancel"]);
    assert.deepEqual(sent.at(-1).args, {runId:"test-exact"});
    assert.equal(context.ui.state.test.state, "canceling");
    resolveStatus({ok:true,result:run});
    await statusPromise;
    assert.equal(context.ui.state.test.state, "canceling", "older poll must not undo a newer cancel receipt");
    assert.equal(context.ui.state.busy, true, "Cancel did not wait for or complete the game request");
    resolveCapture(capture);
    await capturePromise;
    const before = sent.length;
    element("keyboard").checked = true;
    documentListeners.keydown({code:"ArrowRight",target:{closest:()=>false},preventDefault(){}});
    await element("capture").listeners.click();
    await context.ui.command("step", {frames:1,keys:[]});
    await intervals[0]();
    assert.equal(sent.length, before, "active checked test must suppress manual input and manual capture");
    assert.equal(context.ui.state.pressed.size, 0);
    pendingStatus = null;
    run = {...run,state:"completed",passed:true,observedFrames:900,subjects:[{name:"subject",species:165,handle:65536}],
      evaluation:{failures:[]},acceptedProof:false};
    await element("testRefresh").listeners.click();
    assert(element("testProgress").textContent.includes("Not accepted proof"), "passing observation is not acceptedProof");
    assert(element("testSubject").textContent.includes("165"));
    assert.equal(element("testDetail").textContent, "", "raw test JSON is lazy");
    run = {...run,acceptedProof:true};
    await element("testExport").listeners.click();
    assert(element("testProgress").textContent.includes("Accepted proof"));
    assert.equal(element("downloads").children.length, 1);
    assert.deepEqual(sent.at(-1).args, {runId:"test-exact"});
    run = {...run,runId:"test-other"};
    element("testRunId").value = "test-exact";
    await element("testRunForm").listeners.submit({preventDefault(){}});
    assert.equal(context.ui.state.testRunId, "test-exact", "never silently replace exact saved run identity");
    assert(element("testTransport").textContent.includes("identity changed"));
    run = {...run,runId:"test-exact",state:"failed",acceptedProof:false,evaluation:{failures:[{code:"missing-subject"}]},failureArtifact:{path:"failure.json"}};
    await element("testRefresh").listeners.click();
    assert(element("testFailure").textContent.includes("missing-subject"));
    assert(element("testFailure").textContent.includes("failure.json"));
  } else if (mode === "checked-current-history") {
    const historical = {runId:"test-old",test:"old-idle",state:"completed",acceptedProof:false};
    let current = historical;
    commandHandler = (request) => {
      if (request.op === "test.status") return {ok:true,result:request.args.runId === "test-old" ? {...historical,historical:true} : current};
      if (request.op === "test.cancel") return {ok:false,error:{code:"invalid-command",message:"exact run is no longer current"}};
      throw new Error("Unexpected command " + request.op);
    };
    await intervals[1]();
    assert.equal(context.ui.state.testRunId,"test-old");
    current = {runId:"test-new",test:"absent-subject",state:"running",acceptedProof:false,observedFrames:0};
    await intervals[1]();
    assert.deepEqual(sent.at(-1).args,{},"automatic polling must request CURRENT status, not its cached run ID");
    assert.equal(context.ui.state.testRunId,"test-new","a CLI-started job must replace the old completed display");
    assert(element("testProgress").textContent.includes("absent-subject"));
    assert.equal(element("testCancel").disabled,false);
    element("testRunId").value="test-old";
    await element("testRunForm").listeners.submit({preventDefault(){}});
    assert.deepEqual(sent.at(-1).args,{runId:"test-old"});
    assert.equal(context.ui.state.testRunId,"test-old");
    assert(element("testProgress").textContent.includes("History"));
    assert(element("testProgress").textContent.includes("test-new"),"history view must disclose the current job separately");
    assert.equal(element("testCancel").disabled,true,"history view may not cancel a different current job");
    const before=sent.length;
    await element("testCancel").listeners.click();
    await context.ui.command("step",{frames:1,keys:[]});
    assert.equal(sent.length,before,"history must not grant manual input or cancel authority over current job");
    current={...current,observedFrames:8};
    await intervals[1]();
    assert.deepEqual(sent.at(-1).args,{});
    assert.equal(context.ui.state.testRunId,"test-old","auto polling must not replace explicit history view");
    await element("testRefresh").listeners.click();
    assert.deepEqual(sent.at(-1).args,{});
    assert.equal(context.ui.state.testRunId,"test-new");
    assert(!element("testProgress").textContent.includes("History"));
    // A newer server run can start before the next poll. The stale button must
    // send the displayed exact ID, never discover-and-cancel the new one.
    current={...current,runId:"test-newer"};
    await element("testCancel").listeners.click();
    assert.deepEqual(sent.at(-1).args,{runId:"test-new"});
    assert.equal(sent.filter((request)=>request.op==="test.cancel").length,1);
    assert(element("testTransport").textContent.includes("no longer current"));
    await intervals[1]();
    assert.equal(context.ui.state.testRunId,"test-newer");
    // A slow current poll cannot overwrite a deliberate history inspection;
    // the explicit read is not dropped behind the poll's request slot.
    let resolveCurrent;
    const delayedCurrent = new Promise((resolve)=>{resolveCurrent=resolve;});
    commandHandler = (request) => request.args.runId
      ? {ok:true,result:{...historical,historical:true}} : delayedCurrent;
    const slowPoll = intervals[1]();
    await new Promise(setImmediate);
    element("testRunId").value="test-old";
    await element("testRunForm").listeners.submit({preventDefault(){}});
    assert.equal(context.ui.state.testRunId,"test-old");
    resolveCurrent({ok:true,result:current});
    await slowPoll;
    assert.equal(context.ui.state.testRunId,"test-old","earlier current poll cannot undo explicit history selection");
  } else if (mode === "checked-test-files") {
    commandHandler = (request) => request.op === "test.list"
      ? {ok:true,result:{tests:[{id:"valid",title:"Valid",valid:true},{id:"invalid",valid:false,error:"missing expectation"}]}}
      : {ok:true,result:{acceptedProof:false}};
    await element("testList").listeners.click();
    assert.equal(element("testName").children[1].disabled, true);
    const test = {id:"checked",title:"Reviewed expectation",actions:[]};
    element("testFile").files = [{size:100,text:async()=>JSON.stringify(test)}];
    element("testSaveName").value = "checked";
    const submit = (value) => element("testFileForm").listeners.submit({preventDefault(){},submitter:{value}});
    await submit("validate");
    assert.deepEqual(sent.at(-1).args, {test});
    await submit("save");
    assert.deepEqual(sent.at(-1).args, {name:"checked",test});
    assert(element("testFileResult").textContent.includes("did not run the game"));
    const before = sent.length;
    for (const file of [null,{size:262145,text:async()=>"{}"},{size:10,text:async()=>"[]"},{size:10,text:async()=>"{"}]) {
      element("testFile").files = file ? [file] : [];
      await submit("validate");
      assert.equal(sent.length, before, "invalid file must not be sent");
    }
    commandHandler = () => { throw new Error("Synthetic lost start response"); };
    element("testName").value = "checked";
    await element("testStartForm").listeners.submit({preventDefault(){}});
    const start = sent.at(-1);
    assert.equal(start.op, "test.start");
    assert(element("testTransport").textContent.includes(start.requestId));
    commandHandler = () => ({ok:true,result:{runId:"test-after-lost-reply",state:"running",acceptedProof:false}});
    await intervals[1]();
    assert.equal(sent.filter((request) => request.op === "test.start").length, 1, "unknown start must never be retried by polling");
    assert.equal(context.ui.state.testRunId, "test-after-lost-reply");
    assert(element("testTransport").textContent.includes(start.requestId), "later status must not erase the uncertain receipt");
  } else if (mode === "insight-controls") {
    const actor = {handle:{value:131072,generation:2},active:true,identityVerified:false,
      identityFailures:["engine-in-manager"],role:"WILD",species:165,subjectIdentity:123};
    let explained = actor;
    let checkpoint = 0;
    commandHandler = (request) => {
      const base = {ok:true,session};
      if (request.op === "inspect") return {...base,result:{frame:20,actors:[actor]}};
      if (request.op === "explain") return {...base,result:{frame:21,subject:explained,profileStatus:"unknown: no resolver receipt",decision:{lastDecisionName:"ENGINE_BUSY"},scope:"Observed only"}};
      if (request.op === "checkpoint") return {...base,result:{artifact:{url:`/api/v2/devtools/artifacts/session-host/checkpoint-${++checkpoint}.json`}}};
      if (request.op === "compare") return {...base,result:{equal:false,firstDifference:{path:["frame"],left:20,right:21},scope:"Exact saved observations; not gameplay proof"}};
      if (request.op === "events") return {...base,result:{events:[{frame:21,kind:"native-observation"}],completeHistory:false,scope:"bounded recent event tail"}};
      throw new Error("Unexpected operation " + request.op);
    };
    context.ui.applyResponse({ok:true,session,result:{frame:20,actors:[actor]}});
    element("actors").children[0].listeners.click();
    await new Promise(setImmediate);
    await element("actorExplain").listeners.click();
    assert.deepEqual(sent.at(-1).args,{handle:131072});
    assert(element("explanationSummary").textContent.includes("unknown"));
    assert(element("explanationSummary").textContent.includes("engine-in-manager"));
    assert.equal(context.ui.state.snapshot.frame,20,"explanation clock must not relabel previous actor inventory");
    assert.equal(element("explanationDetail").textContent,"");
    element("explanationRaw").open = true;
    element("explanationRaw").listeners.toggle();
    assert(element("explanationDetail").textContent.includes("ENGINE_BUSY"));
    explained = {...actor,subjectIdentity:124};
    await element("actorExplain").listeners.click();
    assert(element("message").textContent.includes("changed during Explain"));
    assert.equal(context.ui.state.explanation.subject.subjectIdentity,123,"replacement subject must not silently overwrite selection");
    element("compareLeft").value = "";
    await element("checkpoint").listeners.click();
    await element("checkpoint").listeners.click();
    assert.equal(element("compareLeft").value,"session-host/checkpoint-1.json");
    assert.equal(element("compareRight").value,"session-host/checkpoint-2.json");
    element("compareForm").formValues = [["left",element("compareLeft").value],["right",element("compareRight").value]];
    await element("compareForm").listeners.submit({preventDefault(){},currentTarget:element("compareForm")});
    assert(element("compareResult").textContent.includes("not gameplay proof"));
    await element("readEvents").listeners.click();
    assert.deepEqual(sent.at(-1).args,{limit:30});
    assert(element("eventTail").textContent.includes('"completeHistory": false'));
    assert.equal(context.ui.state.snapshot.frame,20);
    assert.equal(context.ui.state.snapshot.events,undefined,"a filtered tail must not replace the full cached event inventory");
  } else if (mode === "terrain-markers") {
    const terrain = {cells:[{x:1,z:2,loaded:true},{x:2,z:2,loaded:true}],
      warps:[{x:2,y:2,index:4}], observation:{center:{x:1,z:2}, boundary:"paused-native-cycle-end",
        nativeCycle:50,lastCompletedGameFrame:40}};
    context.ui.applyResponse({ok:true, session, result:{frame:999,player:{x:2,y:2},terrain}});
    let table = element("terrainGrid").children.find((child) => child.className === "terrain");
    let tiles = table.children[1].children.slice(1);
    assert(tiles[0].classList.contains("player"));
    assert(!tiles[1].classList.contains("player"), "do not borrow later snapshot player");
    assert(tiles[1].classList.contains("warp"));
    assert(tiles[1].textContent.includes("W"));
    assert(element("terrainGrid").children[0].textContent.includes("native cycle 50"));
    context.ui.applyResponse({ok:true, session, result:{terrain:{...terrain,observation:{},warps:[{x:"2",y:2}]}}});
    table = element("terrainGrid").children.find((child) => child.className === "terrain");
    tiles = table.children[1].children.slice(1);
    assert(tiles.every((tile) => !tile.classList.contains("player") && !tile.classList.contains("warp")));
  } else throw new Error("unknown UI test mode");
  console.log(`${mode}: actual page bindings passed`);
}
run().catch((error) => { console.error(error); process.exitCode = 1; });
