"use strict";
const $ = (id) => document.getElementById(id);
const state = { documents: [], sources: [], run: null, busy: false, controller: null, liveAvailable: false, modelsLoaded: false };
const labels = { workbench: "Agent workbench", knowledge: "Knowledge base", evaluation: "Evaluation lab", activity: "Runs & tickets" };
let errorTimer;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...options.headers } });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { const data = await response.json(); if (typeof data.detail === "string") detail = data.detail; } catch {}
    throw new Error(detail);
  }
  return response.json();
}

function error(message) {
  $("error-banner").textContent = message;
  $("error-banner").hidden = false;
  clearTimeout(errorTimer);
  errorTimer = setTimeout(() => { $("error-banner").hidden = true; }, 11000);
}

function view(name) {
  document.querySelectorAll(".view").forEach((node) => { node.hidden = node.id !== `${name}-view`; });
  document.querySelectorAll(".nav-item").forEach((node) => {
    node.classList.toggle("active", node.dataset.view === name);
    node.setAttribute("aria-current", node.dataset.view === name ? "page" : "false");
  });
  $("page-label").textContent = labels[name];
  if (name === "knowledge") loadDocuments().catch((e) => error(e.message));
  if (name === "activity") loadActivity().catch((e) => error(e.message));
}

async function loadHealth() {
  const health = await api("/api/health");
  $("connection-label").textContent = "Local server connected";
  $("document-count").textContent = health.documents;
  $("chunk-count").textContent = health.chunks;
  $("nav-doc-count").textContent = health.documents;
  state.liveAvailable = health.live_available;
  const selected = $("model").value;
  $("model").replaceChildren(...health.models.map((model) => {
    const option = element("option", "", model); option.value = model; return option;
  }));
  $("model").value = state.modelsLoaded && health.models.includes(selected) ? selected : health.model;
  state.modelsLoaded = true;
  setMode();
}

function setMode() {
  const live = $("mode").value === "live";
  const needsKey = live && !state.liveAvailable;
  $("mode-badge").textContent = needsKey ? "API KEY REQUIRED" : live ? "LIVE OPENAI AGENT" : "OFFLINE DEMO";
  $("live-setup").hidden = !needsKey;
  $("setup-status").textContent = "";
  if (!state.busy) {
    $("run-button").disabled = needsKey;
    $("run-button").textContent = needsKey ? "API key required" : "Run agent ↗";
  }
  $("retrieval-label").textContent = live ? "Hybrid BM25 + embeddings" : "BM25 retrieval";
  $("mode-explainer").textContent = live
    ? `Live model: ${$("model").value}. ${needsKey ? "Add your server API key to enable live runs." : "Questions and evidence are sent to OpenAI; API usage is billed to your key. Model access depends on your API account."}`
    : `Offline demo selects source excerpts without a model or API key. Your selected live model (${$("model").value}) is used only in Live OpenAI agent mode.`;
}

function addTrace(item) {
  if (["answer_delta", "done"].includes(item.type)) return;
  if (!$("trace").querySelector(".trace-event")) $("trace").replaceChildren();
  const row = element("div", "trace-event");
  row.append(element("span", "trace-dot"));
  const body = element("div");
  let label = item.label || item.name?.replaceAll("_", " ") || item.type;
  if (item.type === "tool_call") label = `Tool → ${item.name}`;
  body.append(element("div", "label", label));
  if (item.detail || item.arguments) body.append(element("div", "detail", item.detail || JSON.stringify(item.arguments)));
  body.append(element("div", "trace-time", `${item.elapsed_ms ?? 0} ms · ${item.type}`));
  row.append(body);
  $("trace").append(row);
  $("trace").scrollTop = $("trace").scrollHeight;
  $("trace-count").textContent = `${$("trace").children.length} events`;
}

function renderSources(sources) {
  state.sources = sources;
  $("sources").replaceChildren();
  $("source-count").textContent = sources.length;
  sources.forEach((source, index) => {
    const row = element("div", "source-item");
    row.id = `source-${source.id}`;
    const title = element("div", "source-title");
    title.append(element("span", "source-number", index + 1), document.createTextNode(source.title));
    row.append(title, element("p", "", source.content.slice(0, 310) + (source.content.length > 310 ? "…" : "")),
      element("div", "source-meta", `${source.retrieval} · score ${source.score} · ${source.section}`));
    const button = element("button", "text-button", "Read document ↗");
    button.addEventListener("click", () => openDocument(source.document_id));
    row.append(button);
    $("sources").append(row);
  });
  if (!sources.length) $("sources").append(element("p", "side-empty", "No relevant evidence was found."));
}

function renderAnswer(text) {
  $("answer").replaceChildren();
  const parts = text.split(/(\[[a-zA-Z0-9_-]+\])/g);
  parts.forEach((part) => {
    const id = part.slice(1, -1);
    const index = state.sources.findIndex((source) => source.id === id);
    if (part.startsWith("[") && index >= 0) {
      const button = element("button", "citation", index + 1);
      button.title = state.sources[index].title;
      button.setAttribute("aria-label", `Show source ${index + 1}: ${button.title}`);
      button.addEventListener("click", () => {
        const row = $(`source-${id}`);
        row?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        row?.classList.add("highlight");
        setTimeout(() => row?.classList.remove("highlight"), 1800);
      });
      $("answer").append(button);
    } else $("answer").append(document.createTextNode(part));
  });
}

function finishRun(result) {
  state.run = result;
  renderSources(result.sources || []);
  renderAnswer(result.answer);
  $("answer").hidden = false;
  $("answer-empty").hidden = true;
  $("answer-status").textContent = result.outcome === "validation_failed" ? "RESPONSE VALIDATION FAILED"
    : result.outcome === "refused" ? "MODEL DECLINED" : result.abstained ? "INSUFFICIENT EVIDENCE" : "SOURCE IDS VERIFIED";
  $("last-latency").textContent = `${(result.latency_ms / 1000).toFixed(2)}s`;
  $("run-summary").hidden = false;
  const metrics = [`${result.mode === "demo" ? "DEMO / EXTRACTIVE" : "LIVE / MODEL"}`, `${result.latency_ms} MS`, `${result.sources.length} SOURCES`];
  if (result.model) metrics.push(result.model);
  if (result.usage) metrics.push(`${result.usage.input_tokens + result.usage.output_tokens} MODEL TOKENS`, `${result.usage.embedding_tokens} EMBEDDING TOKENS`);
  $("run-summary").replaceChildren(...metrics.map((m) => element("span", "", m)));
  const download = element("button", "text-button", "Export run ↓");
  download.addEventListener("click", () => {
    const { approval_token, ...safe } = result;
    const url = URL.createObjectURL(new Blob([JSON.stringify(safe, null, 2)], { type: "application/json" }));
    const link = element("a"); link.href = url; link.download = `atlas-run-${result.run_id.slice(0, 8)}.json`; link.click(); URL.revokeObjectURL(url);
  });
  $("run-summary").append(download);
  $("draft-card").hidden = !result.draft;
  if (result.draft) {
    $("draft-title").textContent = result.draft.title;
    $("draft-summary").textContent = result.draft.summary;
    $("draft-priority").textContent = `${result.draft.priority.toUpperCase()} PRIORITY`;
    if (result.approval_token) sessionStorage.setItem(`atlas-approval-${result.run_id}`, result.approval_token);
    $("approve-button").disabled = !sessionStorage.getItem(`atlas-approval-${result.run_id}`);
    $("approve-button").textContent = $("approve-button").disabled ? "Approval is available in the original browser session" : "Approve & create local ticket ✓";
    $("ticket-result").textContent = "";
  }
}

async function runQuestion(event) {
  event.preventDefault();
  if (state.busy) { state.controller.abort(); return; }
  if ($("mode").value === "live" && !state.liveAvailable) { setMode(); return; }
  const question = $("question").value.trim();
  if (question.length < 3) { error("Enter a question with at least three characters."); return; }
  state.busy = true;
  state.controller = new AbortController();
  state.run = null;
  $("error-banner").hidden = true;
  $("run-button").textContent = "Stop run ■";
  $("answer-empty").hidden = true;
  $("answer").hidden = false;
  $("answer").textContent = "Searching the knowledge base…";
  $("answer-status").textContent = "RUNNING";
  $("run-summary").hidden = true;
  $("draft-card").hidden = true;
  $("trace").replaceChildren();
  $("trace-count").textContent = "0 events";
  renderSources([]);
  let answer = "", completed = false;
  try {
    const response = await fetch("/api/runs/stream", { method: "POST", signal: state.controller.signal,
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, mode: $("mode").value, model: $("model").value, allow_draft: $("task").value === "draft" }) });
    if (!response.ok) { const detail = await response.json(); throw new Error(typeof detail.detail === "string" ? detail.detail : "The question was rejected."); }
    const reader = response.body.getReader(), decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        if (!frame.startsWith("data: ")) continue;
        const item = JSON.parse(frame.slice(6));
        if (item.type === "error") throw new Error(item.message);
        addTrace(item);
        if (item.sources && item.type === "tool_result") {
          const merged = new Map(state.sources.map((s) => [s.id, s]));
          item.sources.forEach((s) => merged.set(s.id, s)); renderSources([...merged.values()]);
        }
        if (item.type === "answer_delta") { answer += item.text; renderAnswer(answer); }
        if (item.type === "done") { finishRun(item); completed = true; }
      }
      if (done) break;
    }
    if (!completed) throw new Error("The connection closed before the run finished. Check recent runs before retrying.");
  } catch (e) {
    $("answer-status").textContent = e.name === "AbortError" ? "STOPPED" : "FAILED";
    $("answer").textContent = e.name === "AbortError" ? "Run stopped. Any in-flight provider request may finish before cancellation is recorded." : "This run did not complete. Your documents are still available; check the message below.";
    if (e.name !== "AbortError") error(e.message);
  } finally { state.busy = false; setMode(); }
}

async function approve() {
  if (!state.run) return;
  const token = sessionStorage.getItem(`atlas-approval-${state.run.run_id}`);
  $("approve-button").disabled = true;
  try {
    const ticket = await api(`/api/runs/${state.run.run_id}/approve`, { method: "POST", body: JSON.stringify({ token }) });
    $("ticket-result").textContent = `${ticket.id} created in the local sandbox. Nothing was sent externally.`;
    $("approve-button").textContent = "Approved ✓";
  } catch (e) { error(e.message); $("approve-button").disabled = false; }
}

async function openDocument(id) {
  try {
    const doc = await api(`/api/documents/${encodeURIComponent(id)}`);
    $("dialog-title").textContent = doc.title;
    $("dialog-content").textContent = doc.content;
    $("document-dialog").showModal();
  } catch (e) { error(e.message); }
}

function renderDocuments() {
  const filter = $("doc-filter").value.toLowerCase();
  const rows = state.documents.filter((d) => d.title.toLowerCase().includes(filter));
  $("document-list").replaceChildren();
  rows.forEach((doc) => {
    const row = element("div", "document-row"), body = element("div");
    body.append(element("strong", "", doc.title), element("small", "", `${doc.chunks} CHUNKS · ${doc.id.startsWith("custom-") ? "CUSTOM DOCUMENT" : "DEMO CORPUS"}`));
    const button = element("button", "text-button", "Read ↗");
    button.addEventListener("click", () => openDocument(doc.id));
    row.append(element("span", "doc-icon", "▤"), body, button); $("document-list").append(row);
  });
  if (!rows.length) $("document-list").append(element("div", "empty-panel", "No documents match your filter."));
}

async function loadDocuments() { state.documents = await api("/api/documents"); renderDocuments(); }

async function addDocument(event) {
  event.preventDefault();
  const button = $("document-form").querySelector("button"); button.disabled = true;
  try {
    const result = await api("/api/documents", { method: "POST", body: JSON.stringify({ title: $("doc-title").value, content: $("doc-content").value }) });
    $("document-result").textContent = `${result.changed ? "Indexed" : "Already indexed"} · ${result.chunks} chunks. Available to the next run.`;
    await Promise.all([loadDocuments(), loadHealth()]);
  } catch (e) { error(e.message); } finally { button.disabled = false; }
}

async function evaluate() {
  $("evaluate-button").disabled = true;
  try {
    const report = await api("/api/evaluation");
    const metrics = element("div", "eval-metrics");
    [["Hit rate @ 4", `${(report.hit_rate_at_4 * 100).toFixed(1)}%`, `${report.answerable_cases} ANSWERABLE CASES`],
     ["Mean reciprocal rank @ 4", report.mrr_at_4.toFixed(3), "HIGHER IS BETTER"],
     ["No-evidence accuracy", `${(report.no_evidence_accuracy * 100).toFixed(1)}%`, `${report.unanswerable_cases} OUT-OF-SCOPE CASES`]].forEach(([label, value, foot]) => {
      const card = element("div", "card eval-metric"); card.append(element("span", "", label), element("strong", "", value), element("small", "", foot)); metrics.append(card);
    });
    const wrap = element("div", "card table-wrap"), table = element("table"), head = element("thead"), header = element("tr");
    ["QUESTION", "EXPECTED SOURCE", "FIRST RELEVANT RANK", "RESULT"].forEach((text) => header.append(element("th", "", text))); head.append(header); table.append(head);
    const body = element("tbody");
    report.results.forEach((result) => {
      const row = element("tr");
      row.append(element("td", "", result.question), element("td", "", result.relevant.join(", ") || "No evidence"),
        element("td", "", result.reciprocal_rank ? Math.round(1 / result.reciprocal_rank) : "—"), element("td", result.hit ? "pass" : "fail", result.hit ? "✓ PASS" : "× MISS")); body.append(row);
    });
    table.append(body); wrap.append(table);
    $("evaluation-output").replaceChildren(metrics, wrap, element("p", "eval-scope", report.scope + " Results use the current local corpus. The CLI report uses a clean seeded corpus."));
  } catch (e) { error(e.message); } finally { $("evaluate-button").disabled = false; }
}

async function loadActivity() {
  const [runs, tickets] = await Promise.all([api("/api/runs"), api("/api/tickets")]);
  $("runs-list").replaceChildren(); $("tickets-list").replaceChildren();
  runs.forEach((run) => {
    const row = element("div", "activity-row");
    row.append(element("strong", "", run.question), element("small", "", `${run.mode.toUpperCase()} · ${run.status.toUpperCase()} · ${new Date(run.created_at).toLocaleString()}`));
    if (run.result?.answer) {
      const button = element("button", "text-button", "Inspect run ↗");
      button.addEventListener("click", () => {
        view("workbench"); $("trace").replaceChildren(); (run.result.events || []).forEach(addTrace); finishRun(run.result);
        $("question").value = run.question; $("mode").value = run.mode; setMode();
        if (run.result.model) { $("model").value = run.result.model; setMode(); }
      }); row.append(button);
    }
    $("runs-list").append(row);
  });
  tickets.forEach((ticket) => {
    const row = element("div", "activity-row");
    row.append(element("small", "", `${ticket.id} · ${ticket.priority.toUpperCase()}`), element("strong", "", ticket.title), element("p", "", ticket.summary));
    $("tickets-list").append(row);
  });
  if (!runs.length) $("runs-list").append(element("div", "empty-panel", "No runs yet. Start in the agent workbench."));
  if (!tickets.length) $("tickets-list").append(element("div", "empty-panel", "No tickets created. An explicit approval is required."));
}

document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => view(button.dataset.view)));
document.querySelectorAll(".example").forEach((button) => button.addEventListener("click", () => { $("question").value = button.dataset.question; $("task").value = button.dataset.task || "answer"; $("question").focus(); }));
$("query-form").addEventListener("submit", runQuestion);
$("mode").addEventListener("change", setMode);
$("model").addEventListener("change", setMode);
$("recheck-setup").addEventListener("click", async () => {
  $("recheck-setup").disabled = true;
  try {
    await loadHealth();
    $("setup-status").textContent = state.liveAvailable ? "API key detected. Live mode is ready." : "No API key detected. Save .env and restart the server first.";
  } catch (e) { error(e.message); } finally { $("recheck-setup").disabled = false; }
});
$("approve-button").addEventListener("click", approve);
$("document-form").addEventListener("submit", addDocument);
$("doc-filter").addEventListener("input", renderDocuments);
$("evaluate-button").addEventListener("click", evaluate);
$("refresh-activity").addEventListener("click", () => loadActivity().catch((e) => error(e.message)));
$("close-dialog").addEventListener("click", () => $("document-dialog").close());
loadHealth().catch(() => { $("connection-label").textContent = "Server unavailable"; error("The local API is unavailable. Start the server using the README instructions."); });
