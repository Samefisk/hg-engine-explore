const directions = {
  studio: {
    number: "01",
    name: "Behavior Studio",
    description: "The balanced direction: distinct base/override libraries, lifecycle editing, and a persistent resolver inspector.",
  },
  resolver: {
    number: "02",
    name: "Resolver Control Room",
    description: "The correctness-first direction: every matching layer, field winner, skipped rule, and runtime fallback stays visible.",
  },
  notebook: {
    number: "03",
    name: "Field Research Notebook",
    description: "The approachable direction: plain-language behavior stories first, with implementation symbols available on demand.",
  },
  pokedex: {
    number: "04",
    name: "Pokédex Workshop",
    description: "The characterful direction: game-adjacent industrial graphics, sprite-led navigation, and a compact resolution scan.",
  },
  bench: {
    number: "05",
    name: "Data Bench",
    description: "The expert direction: dense comparison tables, bulk Include controls, keyboard workflows, and a provenance drawer.",
  },
};

const tabs = [...document.querySelectorAll("[data-direction]")];
const mockups = [...document.querySelectorAll("[data-mockup]")];
const footerDirection = document.getElementById("footerDirection");
const footerDescription = document.getElementById("footerDescription");
const preferenceLabel = document.getElementById("preferenceLabel");
const chooseButton = document.getElementById("chooseDirection");

let activeDirection = "studio";
let chosenDirection = window.localStorage.getItem("overworld-tools-v2-direction") || "";

function setDirection(direction, updateHash = true) {
  if (!directions[direction]) return;
  activeDirection = direction;
  const detail = directions[direction];

  tabs.forEach((tab) => {
    const active = tab.dataset.direction === direction;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-pressed", String(active));
  });

  mockups.forEach((mockup) => {
    const active = mockup.dataset.mockup === direction;
    mockup.hidden = !active;
    mockup.classList.toggle("is-active", active);
  });

  footerDirection.textContent = `${detail.number} · ${detail.name}`;
  footerDescription.textContent = detail.description;
  chooseButton.textContent = chosenDirection === direction ? `Selected: ${detail.name}` : `Choose ${detail.name}`;
  chooseButton.classList.toggle("is-chosen", chosenDirection === direction);

  if (updateHash) window.history.replaceState(null, "", `#${direction}`);
}

function chooseActiveDirection() {
  chosenDirection = activeDirection;
  window.localStorage.setItem("overworld-tools-v2-direction", chosenDirection);
  const detail = directions[chosenDirection];
  preferenceLabel.textContent = `${detail.number} · ${detail.name}`;
  chooseButton.textContent = `Selected: ${detail.name}`;
  chooseButton.classList.add("is-chosen");
}

function setupPokedexReorder() {
  const deck = document.getElementById("dexOverrideDeck");
  const resetButton = document.getElementById("dexResetOrder");
  const orderStatus = document.getElementById("dexOrderStatus");
  const selectedPriority = document.getElementById("dexSelectedPriority");
  const matchMeta = document.getElementById("dexMatchMeta");
  const scanOverrideMeta = document.getElementById("dexScanOverrideMeta");
  const scanOverrideResult = document.getElementById("dexScanOverrideResult");
  const laterOverridesMeta = document.getElementById("dexLaterOverridesMeta");
  const reviewCount = document.querySelector("[data-dex-review-count]");
  const draftCount = document.querySelector("[data-dex-draft-count]");
  if (!deck || !resetButton || !orderStatus || !selectedPriority || !matchMeta || !scanOverrideMeta || !scanOverrideResult || !laterOverridesMeta || !reviewCount || !draftCount) return;

  const orderStorageKey = "overworld-tools-v2-pokedex-order-v1";
  const contextMatches = [{ profileId: "OVR_42F8", rule: "#16" }];
  const baselineOrder = [...deck.querySelectorAll(".dex-profile-item")].map((item) => item.dataset.profileId);
  const itemById = new Map([...deck.querySelectorAll(".dex-profile-item")].map((item) => [item.dataset.profileId, item]));
  let draggedItem = null;
  let dropTarget = null;
  let dropAfter = false;
  let pointerDrag = null;

  const orderedItems = () => [...deck.querySelectorAll(".dex-profile-item")];
  const currentOrder = () => orderedItems().map((item) => item.dataset.profileId);
  const ordersMatch = (left, right) => left.length === right.length && left.every((id, index) => id === right[index]);

  function clearDropIndicators() {
    orderedItems().forEach((item) => item.classList.remove("is-drop-before", "is-drop-after"));
    dropTarget = null;
    dropAfter = false;
  }

  function updatePriorityLabels() {
    const items = orderedItems();
    items.forEach((item, index) => {
      const number = item.querySelector(".card-index b");
      if (number) number.textContent = String(index + 1).padStart(2, "0");
      item.setAttribute("aria-posinset", String(index + 1));
      item.setAttribute("aria-setsize", String(items.length));
      const handle = item.querySelector("[data-dex-drag-handle]");
      if (handle) handle.setAttribute("aria-label", `Move ${item.dataset.profileName || "override profile"}, resolver order ${index + 1} of ${items.length}`);
    });
    const selected = deck.querySelector(".dex-profile-item.is-selected");
    const selectedIndex = items.indexOf(selected);
    if (selectedIndex >= 0) selectedPriority.textContent = `OVERRIDE PROFILE · RESOLVER ORDER ${selectedIndex + 1} OF ${items.length}`;
  }

  function updateResolverOrderUI() {
    const items = orderedItems();
    items.forEach((item) => item.classList.remove("is-context-match", "is-final-match"));
    const matches = items
      .map((item) => ({ item, match: contextMatches.find((candidate) => candidate.profileId === item.dataset.profileId) }))
      .filter((entry) => entry.match);
    matches.forEach((entry) => entry.item.classList.add("is-context-match"));
    const finalMatch = matches.at(-1);
    if (!finalMatch) {
      matchMeta.innerHTML = "0 MATCHES<br>BASE ONLY";
      scanOverrideMeta.textContent = "NO MATCHING OVERRIDE";
      scanOverrideResult.textContent = "SKIPPED";
      laterOverridesMeta.textContent = "0 MATCHING OVERRIDES";
      return { lastMatchName: "NONE", lastMatchOrder: 0 };
    }
    finalMatch.item.classList.add("is-final-match");
    const finalIndex = items.indexOf(finalMatch.item);
    const laterMatchCount = matches.filter((entry) => items.indexOf(entry.item) > finalIndex).length;
    const lastMatchName = finalMatch.item.dataset.profileName || "Override profile";
    matchMeta.innerHTML = `${matches.length} MATCH · FINAL<br>RULE ${finalMatch.match.rule}`;
    scanOverrideMeta.textContent = `RULE ${finalMatch.match.rule} · ORDER ${finalIndex + 1} OF ${items.length}`;
    scanOverrideResult.textContent = "APPLIES LAST";
    laterOverridesMeta.textContent = `${laterMatchCount} MATCH AFTER ORDER ${finalIndex + 1}`;
    return { lastMatchName, lastMatchOrder: finalIndex + 1 };
  }

  function setDraftState(message) {
    const order = currentOrder();
    const dirty = !ordersMatch(order, baselineOrder);
    const resolverState = updateResolverOrderUI();
    deck.classList.toggle("has-order-draft", dirty);
    resetButton.disabled = !dirty;
    reviewCount.textContent = dirty ? "REVIEW ×4" : "REVIEW ×3";
    draftCount.textContent = dirty ? "DRAFT SLOT A · 3 FIELD CHANGES + 1 ORDER CHANGE" : "DRAFT SLOT A · 3 FIELD CHANGES";
    orderStatus.classList.toggle("is-dirty", dirty);
    orderStatus.textContent = typeof message === "function"
      ? message(resolverState)
      : message || (dirty
        ? `RESOLVER ORDER UPDATED · LAST MATCH: ${resolverState.lastMatchName.toUpperCase()} · EFFECTIVE RESULT UNCHANGED`
        : `RESOLVER ORDER ACTIVE · TOP → BOTTOM · LAST MATCH: ${resolverState.lastMatchName.toUpperCase()}`);
    if (dirty) window.localStorage.setItem(orderStorageKey, JSON.stringify(order));
    else window.localStorage.removeItem(orderStorageKey);
  }

  function finishMove(item, target, after, focusHandle = false) {
    if (!item || !target || item === target) return false;
    const beforeItems = orderedItems();
    const from = beforeItems.indexOf(item);
    const remaining = beforeItems.filter((candidate) => candidate !== item);
    const targetIndex = remaining.indexOf(target);
    if (targetIndex < 0) return false;
    const insertIndex = targetIndex + (after ? 1 : 0);
    const reference = remaining[insertIndex] || null;
    deck.insertBefore(item, reference);
    const to = orderedItems().indexOf(item);
    updatePriorityLabels();
    const name = item.dataset.profileName || "Override profile";
    setDraftState((resolverState) => `MOVED ${name.toUpperCase()} · APPLY ORDER ${from + 1} → ${to + 1} · RESOLVER UPDATED · LAST MATCH: ${resolverState.lastMatchName.toUpperCase()}`);
    if (focusHandle) item.querySelector("[data-dex-drag-handle]")?.focus();
    return from !== to;
  }

  function setDropTarget(target, after) {
    clearDropIndicators();
    if (!target || target === draggedItem || target === pointerDrag?.item) return;
    dropTarget = target;
    dropAfter = after;
    target.classList.add(after ? "is-drop-after" : "is-drop-before");
    const moving = draggedItem || pointerDrag?.item;
    const movingName = moving?.dataset.profileName || "PROFILE";
    const targetName = target.dataset.profileName || "PROFILE";
    orderStatus.textContent = `DROP TO APPLY ${movingName.toUpperCase()} ${after ? "AFTER" : "BEFORE"} ${targetName.toUpperCase()}`;
  }

  function updateDropFromPoint(clientX, clientY) {
    const candidate = document.elementFromPoint(clientX, clientY)?.closest(".dex-profile-item");
    if (!candidate || !deck.contains(candidate)) {
      clearDropIndicators();
      return;
    }
    const rect = candidate.getBoundingClientRect();
    setDropTarget(candidate, clientY >= rect.top + rect.height / 2);
    const deckRect = deck.getBoundingClientRect();
    if (clientY < deckRect.top + 28) deck.scrollTop -= 12;
    else if (clientY > deckRect.bottom - 28) deck.scrollTop += 12;
  }

  deck.addEventListener("dragstart", (event) => {
    const handle = event.target.closest("[data-dex-drag-handle]");
    if (!handle) {
      event.preventDefault();
      return;
    }
    draggedItem = handle.closest(".dex-profile-item");
    if (!draggedItem) return;
    event.dataTransfer?.setData("text/plain", draggedItem.dataset.profileId || "");
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
    draggedItem.classList.add("is-dragging");
    deck.classList.add("is-reordering");
    orderStatus.textContent = `MOVING ${(draggedItem.dataset.profileName || "PROFILE").toUpperCase()} · CHOOSE A NEW APPLY POSITION`;
  });

  deck.addEventListener("dragover", (event) => {
    if (!draggedItem) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
    updateDropFromPoint(event.clientX, event.clientY);
  });

  deck.addEventListener("drop", (event) => {
    if (!draggedItem) return;
    event.preventDefault();
    const moved = finishMove(draggedItem, dropTarget, dropAfter);
    if (!moved) setDraftState();
    clearDropIndicators();
  });

  deck.addEventListener("dragend", () => {
    draggedItem?.classList.remove("is-dragging");
    draggedItem = null;
    deck.classList.remove("is-reordering");
    clearDropIndicators();
  });

  deck.addEventListener("keydown", (event) => {
    const handle = event.target.closest("[data-dex-drag-handle]");
    if (!handle || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    const item = handle.closest(".dex-profile-item");
    const target = event.key === "ArrowUp" ? item?.previousElementSibling : item?.nextElementSibling;
    if (!item || !target) return;
    finishMove(item, target, event.key === "ArrowDown", true);
  });

  deck.addEventListener("pointerdown", (event) => {
    const handle = event.target.closest("[data-dex-drag-handle]");
    const item = handle?.closest(".dex-profile-item");
    if (!handle || !item) return;
    pointerDrag = { handle, item, pointerId: event.pointerId };
    handle.setPointerCapture?.(event.pointerId);
    item.classList.add("is-dragging");
    deck.classList.add("is-reordering");
    orderStatus.textContent = `MOVING ${(item.dataset.profileName || "PROFILE").toUpperCase()} · CHOOSE A NEW APPLY POSITION`;
    event.preventDefault();
  });

  deck.addEventListener("pointermove", (event) => {
    if (!pointerDrag || pointerDrag.pointerId !== event.pointerId) return;
    updateDropFromPoint(event.clientX, event.clientY);
    event.preventDefault();
  });

  function finishPointerDrag(event, canceled = false) {
    if (!pointerDrag || pointerDrag.pointerId !== event.pointerId) return;
    if (!canceled) finishMove(pointerDrag.item, dropTarget, dropAfter, true);
    pointerDrag.item.classList.remove("is-dragging");
    pointerDrag.handle.releasePointerCapture?.(event.pointerId);
    pointerDrag = null;
    deck.classList.remove("is-reordering");
    clearDropIndicators();
  }

  deck.addEventListener("pointerup", (event) => finishPointerDrag(event));
  deck.addEventListener("pointercancel", (event) => finishPointerDrag(event, true));

  resetButton.addEventListener("click", () => {
    baselineOrder.forEach((id) => deck.appendChild(itemById.get(id)));
    updatePriorityLabels();
    setDraftState((resolverState) => `RESOLVER ORDER RESET · LAST MATCH: ${resolverState.lastMatchName.toUpperCase()} · EFFECTIVE RESULT UNCHANGED`);
    deck.querySelector(".dex-profile-item.is-selected [data-dex-drag-handle]")?.focus();
  });

  try {
    const storedOrder = JSON.parse(window.localStorage.getItem(orderStorageKey) || "null");
    if (Array.isArray(storedOrder) && ordersMatch([...storedOrder].sort(), [...baselineOrder].sort())) {
      storedOrder.forEach((id) => deck.appendChild(itemById.get(id)));
    }
  } catch {
    window.localStorage.removeItem(orderStorageKey);
  }
  updatePriorityLabels();
  setDraftState(ordersMatch(currentOrder(), baselineOrder)
    ? undefined
    : (resolverState) => `DRAFT ORDER RESTORED · RESOLVER UPDATED · LAST MATCH: ${resolverState.lastMatchName.toUpperCase()}`);
}

tabs.forEach((tab) => tab.addEventListener("click", () => setDirection(tab.dataset.direction)));
chooseButton.addEventListener("click", chooseActiveDirection);

const hashDirection = window.location.hash.slice(1);
if (chosenDirection && directions[chosenDirection]) {
  const chosen = directions[chosenDirection];
  preferenceLabel.textContent = `${chosen.number} · ${chosen.name}`;
}
setDirection(directions[hashDirection] ? hashDirection : "studio", false);
setupPokedexReorder();
