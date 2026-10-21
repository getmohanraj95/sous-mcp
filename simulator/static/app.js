"use strict";

const els = {
  status: document.getElementById("status"),
  transcript: document.getElementById("transcript"),
  emptyState: document.getElementById("empty-state"),
  input: document.getElementById("utterance"),
  send: document.getElementById("send"),
  mic: document.getElementById("mic"),
  speak: document.getElementById("speak"),
  slot: document.getElementById("ticket-slot"),
  server: document.getElementById("fact-server"),
  protocol: document.getElementById("fact-protocol"),
  session: document.getElementById("fact-session"),
  tools: document.getElementById("tool-list"),
  trace: document.getElementById("trace"),
  reset: document.getElementById("reset"),
  suggestions: document.getElementById("suggestions"),
};

function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = options.text;
  for (const child of children) node.append(child);
  return node;
}

/* ---------- state panel ---------- */

function renderState(state) {
  if (state.connected) {
    els.status.textContent = `Connected to ${state.server_name} over MCP ${state.protocol_version}`;
    els.status.className = "status is-live";
  } else {
    els.status.textContent = "Sous server isn't running. Start it with: python server.py";
    els.status.className = "status is-down";
  }
  els.server.textContent = state.connected ? `${state.server_name} at ${state.server_url}` : "Not connected";
  els.protocol.textContent = state.protocol_version || "Not connected";
  els.session.textContent = state.session_id || "Not connected";

  els.tools.replaceChildren(
    ...state.tools.map((tool) =>
      el("li", {}, [el("code", { text: tool.name }), " ", el("span", { className: "ro", text: tool.read_only ? "read-only" : "updates state" })])
    )
  );
  els.trace.replaceChildren(
    ...state.trace.slice().reverse().map((event) =>
      el("li", { className: event.ok ? "" : "fail" }, [
        el("code", { text: event.method }),
        el("span", { text: event.detail }),
        el("span", { className: "ms", text: `${event.elapsed_ms} ms` }),
      ])
    )
  );
}

/* ---------- transcript ---------- */

function addLine(who, text, tool) {
  els.emptyState?.remove();
  const line = el("li", { className: `line ${who}` }, [
    el("span", { className: "who", text: who === "user" ? "You" : "Sous" }),
    el("p", { text }),
  ]);
  if (tool) {
    const args = JSON.stringify(tool.arguments);
    line.append(el("code", { className: `tool-call${tool.is_error ? " is-error" : ""}`, text: `tools/call ${tool.name} ${args}` }));
  }
  els.transcript.append(line);
  els.transcript.scrollTop = els.transcript.scrollHeight;
}

/* ---------- tickets ---------- */

function itemRow(name, have) {
  return el("li", {}, [
    el("span", { text: name }),
    el("span", { className: have ? "mark-have" : "mark-need", text: have ? "have" : "need" }),
  ]);
}

function ticketFor(card) {
  const ticket = el("article", { className: "ticket is-new" });
  switch (card.type) {
    case "pantry": {
      ticket.append(el("h2", { text: "Pantry" }));
      const notes = [];
      if (card.restrictions.length) notes.push(`Only: ${card.restrictions.join(", ")}`);
      if (card.allergies.length) notes.push(`Avoid: ${card.allergies.join(", ")}`);
      ticket.append(el("p", { className: "meta", text: notes.join(". ") || "No dietary rules set" }));
      ticket.append(card.items.length ? el("ul", {}, card.items.map((i) => itemRow(i, true))) : el("p", { text: "Empty" }));
      break;
    }
    case "recipes": {
      ticket.append(el("h2", { text: "What you can cook" }));
      ticket.append(el("p", { className: "meta", text: `For ${card.servings}. Ranked by ${card.backend}.` }));
      if (!card.items.length) ticket.append(el("p", { text: "No recipe fits your restrictions." }));
      for (const recipe of card.items) {
        const block = el("section", { className: "recipe" }, [
          el("h3", { text: recipe.title }),
          el("p", { className: "score", text: `${recipe.have.length} of ${recipe.have.length + recipe.missing.length} ingredients on hand` }),
          el("ul", {}, [...recipe.have.map((i) => itemRow(i, true)), ...recipe.missing.map((i) => itemRow(i, false))]),
        ]);
        if (recipe === card.items[0]) {
          block.append(el("p", { className: "section", text: "Method" }), el("ol", { className: "steps" }, recipe.steps.map((s) => el("li", { text: s }))));
        }
        block.append(el("p", { className: "tags", text: recipe.tags.join(", ") }));
        ticket.append(block);
      }
      break;
    }
    case "shopping_list": {
      ticket.append(el("h2", { text: `Shopping list` }));
      ticket.append(el("p", { className: "meta", text: card.title }));
      ticket.append(card.missing.length ? el("ul", {}, card.missing.map((i) => itemRow(i, false))) : el("p", { text: "Nothing to buy." }));
      break;
    }
    case "meal_plan": {
      ticket.append(el("h2", { text: "Meal plan" }));
      ticket.append(el("ul", {}, card.upcoming.map((m) =>
        el("li", {}, [el("span", { text: m.title }), el("span", { text: `${m.when}, serves ${m.servings}` })])
      )));
      break;
    }
    case "error": {
      ticket.append(el("h2", { text: "Couldn't do that" }), el("p", { text: card.message }));
      break;
    }
    default:
      return null;
  }
  return ticket;
}

function hangTicket(card) {
  if (!card) return;
  const ticket = ticketFor(card);
  if (ticket) els.slot.replaceChildren(ticket);
}

/* ---------- talking ---------- */

function say(text) {
  if (!els.speak.checked || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed with status ${response.status}`);
  return data;
}

async function send(text) {
  const utterance = text.trim();
  if (!utterance) return;
  els.input.value = "";
  els.send.disabled = true;
  addLine("user", utterance);
  try {
    const { turn, state } = await api("/api/turn", { utterance });
    addLine("sous", turn.speech, turn.tool);
    hangTicket(turn.card);
    renderState(state);
    say(turn.speech);
  } catch (error) {
    addLine("sous", error.message);
    refresh();
  } finally {
    els.send.disabled = false;
    els.input.focus();
  }
}

async function refresh() {
  try {
    renderState(await api("/api/state"));
  } catch (error) {
    els.status.textContent = error.message;
    els.status.className = "status is-down";
  }
}

els.send.addEventListener("click", () => send(els.input.value));
els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter") send(els.input.value);
});
els.suggestions.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-say]");
  if (button) send(button.dataset.say);
});
els.reset.addEventListener("click", async () => {
  try {
    const state = await api("/api/reset", {});
    els.transcript.replaceChildren();
    els.slot.replaceChildren(el("p", { className: "pass-empty", text: "New session started. Your pantry is empty." }));
    renderState(state);
  } catch (error) {
    addLine("sous", error.message);
  }
});

/* Optional voice input where the browser supports it (Chrome, Edge). */
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (Recognition) {
  const recognizer = new Recognition();
  recognizer.lang = "en-US";
  recognizer.interimResults = false;
  els.mic.hidden = false;
  els.mic.addEventListener("click", () => {
    els.mic.setAttribute("aria-pressed", "true");
    recognizer.start();
  });
  recognizer.addEventListener("result", (event) => send(event.results[0][0].transcript));
  recognizer.addEventListener("end", () => els.mic.setAttribute("aria-pressed", "false"));
}

refresh();
