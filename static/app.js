"use strict";

const $ = (id) => document.getElementById(id);
let last = null;
let settingsLoaded = false;

async function post(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Pmail": "1" },
    body: JSON.stringify(body || {}),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}

function setDot(el, kind) { el.className = "dot " + (kind || ""); }

function render(s) {
  last = s;
  const c = s.counts;
  $("setup").hidden = s.credentials;
  $("warning").hidden = !s.warning;
  $("warning").textContent = s.warning || "";
  $("emails").textContent = c.emails.toLocaleString() + " emails";
  $("emails-detail").textContent = `${(c.emails - c.bulk).toLocaleString()} personal, ${c.bulk.toLocaleString()} newsletters and notifications`;
  $("archive").textContent = s.archive;

  const svc = s.service;
  const mail = { starting: ["Starting…", "busy"], syncing: ["Syncing…", "busy"],
    watching: ["Live: watching for new mail", "ok"], error: [svc.mail_error, "err"] }[svc.mail] || [svc.mail, ""];
  $("mail-state").textContent = mail[0] + (svc.last_sync && svc.mail !== "error" ? ` · last full sync ${svc.last_sync.slice(11, 16)}` : "");
  setDot($("mail-dot"), mail[1]);

  $("summaries").textContent = `${c.summarized.toLocaleString()} of ${c.threads.toLocaleString()}`;
  $("summaries-detail").textContent = "personal conversations summarized";
  const aiState = { idle: ["Up to date", "ok"], working: ["Summarizing: " + (svc.ai_current || "…"), "busy"],
    paused: ["Paused", ""], off: ["Off", ""], error: [svc.ai_error, "err"] }[svc.ai] || [svc.ai, ""];
  $("ai-state").textContent = aiState[0];
  setDot($("ai-dot"), aiState[1]);
  $("pause").textContent = svc.ai === "paused" ? "Resume" : "Pause";
  $("pause").hidden = svc.ai === "off";

  $("log").textContent = s.log.slice().reverse().join("\n") || "Nothing yet.";
  if (!settingsLoaded) loadSettings(s);
}

function loadSettings(s) {
  settingsLoaded = true;
  const f = $("settings");
  const st = s.settings;
  f.range.value = st.since ? "date" : "all";
  f.since.value = st.since || "";
  f.ai_engine.value = st.ai_engine;
  f.sync_minutes.value = st.sync_minutes;
  const models = s.ollama_models || [];
  const options = models.includes(st.ollama_model) ? models : [st.ollama_model, ...models];
  f.ollama_model.replaceChildren(...options.map((m) => new Option(m, m, false, m === st.ollama_model)));
  $("ollama-help").textContent = s.ollama_models === null
    ? "Ollama isn't running. Install it from ollama.com and start it, then pull a model, e.g. `ollama pull qwen2.5:7b`."
    : "Smaller models are faster on a laptop CPU; larger ones write better summaries.";
}

async function refresh() {
  try {
    render(await (await fetch("/api/status")).json());
  } catch {
    $("mail-state").textContent = "The tool isn't running. Start it with Start.bat (Windows), Start.command (Mac) or Start.sh (Linux).";
    setDot($("mail-dot"), "err");
  }
}

$("creds").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  try {
    await post("/api/credentials", { username: f.username.value, password: f.password.value });
    f.reset();
    $("creds-msg").textContent = "Saved. Connecting…";
    refresh();
  } catch (err) { $("creds-msg").textContent = err.message; }
});

$("settings").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const since = f.range.value === "all" ? "all" : f.range.value === "today" ? "today" : f.since.value;
  if (f.range.value === "date" && !since) { $("settings-msg").textContent = "Pick a date."; return; }
  try {
    await post("/api/settings", {
      since, ai_engine: f.ai_engine.value, ollama_model: f.ollama_model.value,
      sync_minutes: Number(f.sync_minutes.value),
    });
    $("settings-msg").textContent = "Saved.";
    settingsLoaded = false;
    refresh();
  } catch (err) { $("settings-msg").textContent = err.message; }
});

$("sync").addEventListener("click", () => post("/api/sync").then(refresh));
$("pause").addEventListener("click", () =>
  post("/api/ai", { paused: last && last.service.ai !== "paused" }).then(refresh));

refresh();
setInterval(refresh, 3000);
