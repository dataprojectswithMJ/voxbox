const $ = (id) => document.getElementById(id);

const PARALINGUISTIC_TAGS = [
  "chuckle", "laugh", "sigh", "gasp", "cough", "clear throat", "sniff",
  "groan", "crying", "shush", "whispering",
  "happy", "sarcastic", "angry", "fear", "surprised", "dramatic", "narration", "advertisement",
];

const NAV = {
  actor: [
    { id: "add-voice", label: "My Voices" },
    { id: "dashboard", label: "Dashboard" },
    { id: "approvals", label: "Approvals" },
  ],
  renter: [
    { id: "my-voices", label: "My Voices" },
    { id: "marketplace", label: "Marketplace" },
  ],
};

const state = {
  role: "actor",
  persona: JSON.parse(localStorage.getItem("voxbox_persona") || "null"),
  nonce: null,
  phrase: null,
  mediaRecorder: null,
  chunks: [],
  recordedBlob: null,
  consentConditions: [],
  page: null,
  selectedVoiceId: null,
  pendingRentVoiceId: null,
  approvalsFilterVoiceId: null,
  selectedApprovalIds: new Set(),
};

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function initials(name) {
  return (name || "?").trim().slice(0, 2).toUpperCase();
}

/* ---------------- TOASTS ---------------- */

function toast(message, kind = "default", timeout = 3800) {
  const stack = $("toast-stack");
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<span class="toast-msg">${escapeHtml(message)}</span>`;
  stack.appendChild(el);
  setTimeout(() => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 180);
  }, timeout);
}

/* ---------------- MODALS ---------------- */

function openModal(id) { $(id).classList.add("open"); }
function closeModal(id) { $(id).classList.remove("open"); }

document.querySelectorAll(".modal-overlay").forEach((overlay) => {
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.classList.remove("open");
  });
});

/* ---------------- POPOVER ---------------- */

function togglePopover(id) {
  document.querySelectorAll(".popover").forEach((p) => { if (p.id !== id) p.classList.remove("open"); });
  $(id).classList.toggle("open");
}
document.addEventListener("click", (e) => {
  if (!e.target.closest(".popover-wrap")) {
    document.querySelectorAll(".popover").forEach((p) => p.classList.remove("open"));
  }
});

/* ---------------- LOGIN ---------------- */

async function loadShowcaseSamples() {
  try {
    const res = await fetch("/api/marketplace");
    const voices = await res.json();
    const box = $("showcase-samples");
    if (!voices.length) {
      box.innerHTML = '<p class="meta">No voices published yet.</p>';
      return;
    }
    box.innerHTML = voices.slice(0, 3).map((v) => `
      <div class="sample-card">
        <div class="avatar">${escapeHtml(initials(v.owner_persona_name))}</div>
        <div class="sample-body">
          <div class="sample-name">${escapeHtml(v.label)}</div>
          <div class="sample-meta">by ${escapeHtml(v.owner_persona_name || "—")} · $${Number(v.price_per_100_words || 0).toFixed(2)}/100 words</div>
          <audio controls src="/api/base_voices/${v.filename}"></audio>
        </div>
      </div>
    `).join("");
  } catch {
    $("showcase-samples").innerHTML = '<p class="meta">Samples unavailable right now.</p>';
  }
}

async function loadLoginPersonas() {
  const res = await fetch(`/api/personas?role=${state.role}`);
  const personas = await res.json();
  const select = $("login-persona");
  select.innerHTML = personas.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
}

document.querySelectorAll(".role-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".role-tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.role = btn.dataset.role;
    $("login-progress-bar").style.width = "55%";
    $("login-progress-label").textContent = "Step 2 of 2";
    loadLoginPersonas();
  });
});

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("login-error").textContent = "";
  const form = new FormData();
  form.append("persona_id", $("login-persona").value);
  form.append("password", $("login-password").value);
  form.append("role", state.role);
  try {
    const res = await fetch("/api/login", { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail || "Login failed");
    const persona = await res.json();
    state.persona = persona;
    localStorage.setItem("voxbox_persona", JSON.stringify(persona));
    enterApp();
  } catch (err) {
    $("login-error").textContent = err.message;
  }
});

$("logout-btn").addEventListener("click", () => {
  state.persona = null;
  localStorage.removeItem("voxbox_persona");
  $("view-app").style.display = "none";
  $("view-login").style.display = "grid";
});

/* ---------------- APP SHELL / NAV ---------------- */

function enterApp() {
  $("view-login").style.display = "none";
  $("view-app").style.display = "flex";
  $("nav-username").textContent = state.persona.name;
  $("nav-role").textContent = state.persona.role;
  $("nav-avatar").textContent = initials(state.persona.name);

  const links = NAV[state.persona.role];
  $("nav-links").innerHTML = links.map((l) => `<button data-page="${l.id}" title="${l.label}"><span class="dot"></span><span class="label">${l.label}</span></button>`).join("");
  $("nav-links").querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => goToPage(btn.dataset.page));
  });

  renderTagPalette();
  loadConsentConditions();
  goToPage(links[0].id);
}

$("sidebar-collapse-btn").addEventListener("click", () => {
  const sidebar = document.querySelector(".sidebar");
  sidebar.classList.toggle("collapsed");
  $("sidebar-collapse-btn").innerHTML = sidebar.classList.contains("collapsed") ? "&raquo;" : "&laquo;";
});

function goToPage(pageId) {
  state.page = pageId;
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  $(`page-${pageId}`).classList.add("active");
  $("nav-links").querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.page === pageId));

  if (pageId === "marketplace") loadMarketplace();
  if (pageId === "my-voices") { state.selectedVoiceId = null; showMyVoicesGrid(); loadRentedVoices(); }
  if (pageId === "add-voice") { loadMyVoices(); }
  if (pageId === "dashboard") loadDashboard();
  if (pageId === "approvals") { state.selectedApprovalIds.clear(); loadApprovals(); }
}

/* ---------------- ADD VOICE MODAL ---------------- */

$("open-add-voice-modal").addEventListener("click", () => {
  resetRecordingUI();
  fetchPhrase();
  openModal("add-voice-modal");
});
$("close-add-voice-modal").addEventListener("click", () => closeModal("add-voice-modal"));

/* ---------------- TAGS ---------------- */

function renderTagPalette() {
  const palette = $("tag-palette");
  palette.innerHTML = "";
  PARALINGUISTIC_TAGS.forEach((tag) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tag-btn";
    btn.textContent = `[${tag}]`;
    btn.addEventListener("click", () => insertTag(tag));
    palette.appendChild(btn);
  });
}

function insertTag(tag) {
  const textarea = $("rent-script");
  const insertion = `[${tag}] `;
  const start = textarea.selectionStart ?? textarea.value.length;
  const end = textarea.selectionEnd ?? textarea.value.length;
  textarea.value = textarea.value.slice(0, start) + insertion + textarea.value.slice(end);
  const cursor = start + insertion.length;
  textarea.focus();
  textarea.setSelectionRange(cursor, cursor);
  updateCostEstimate();
}

async function loadConsentConditions() {
  const res = await fetch("/api/consent-conditions");
  state.consentConditions = await res.json();
  const box = $("consent-checklist");
  box.innerHTML = state.consentConditions.map((c) => `
    <label class="checkbox-tag">
      <input type="checkbox" value="${c}" /> ${c.replace(/_/g, " ")}
    </label>
  `).join("");
}

/* ---------------- ACTOR: ADD VOICE ---------------- */

function resetRecordingUI() {
  state.recordedBlob = null;
  $("preview-audio").style.display = "none";
  $("preview-audio").removeAttribute("src");
  $("save-row").style.display = "none";
  $("record-status").textContent = "";
  $("record-error").textContent = "";
  $("voice-label").value = "";
}

async function fetchPhrase() {
  $("phrase-text").textContent = "Loading phrase…";
  const res = await fetch("/api/phrase");
  const data = await res.json();
  state.nonce = data.nonce;
  state.phrase = data.phrase;
  $("phrase-text").textContent = `“${data.phrase}”`;
  $("preview-audio").style.display = "none";
  $("save-row").style.display = "none";
  state.recordedBlob = null;
  $("record-error").textContent = "";
}

async function toggleRecording() {
  const btn = $("record-btn");
  if (!state.mediaRecorder || state.mediaRecorder.state === "inactive") {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      state.chunks = [];
      state.mediaRecorder = new MediaRecorder(stream);
      state.mediaRecorder.ondataavailable = (e) => state.chunks.push(e.data);
      state.mediaRecorder.onstop = () => {
        state.recordedBlob = new Blob(state.chunks, { type: "audio/webm" });
        const url = URL.createObjectURL(state.recordedBlob);
        const audioEl = $("preview-audio");
        audioEl.src = url;
        audioEl.style.display = "block";
        $("save-row").style.display = "block";
        stream.getTracks().forEach((t) => t.stop());
      };
      state.mediaRecorder.start();
      btn.textContent = "Stop recording";
      btn.classList.add("recording");
      $("record-status").textContent = "Recording…";
    } catch (err) {
      $("record-error").textContent = `Microphone access failed: ${err.message}`;
    }
  } else {
    state.mediaRecorder.stop();
    btn.textContent = "Start recording";
    btn.classList.remove("recording");
    $("record-status").textContent = "Recorded. Review below, then publish.";
  }
}

function redoRecording() {
  state.recordedBlob = null;
  $("preview-audio").style.display = "none";
  $("preview-audio").removeAttribute("src");
  $("save-row").style.display = "none";
  $("record-status").textContent = "Ready to record again.";
  $("record-error").textContent = "";
}

async function saveVoice() {
  if (!state.recordedBlob) return;
  const btn = $("save-voice-btn");
  btn.disabled = true;
  $("record-error").textContent = "";
  try {
    const checked = Array.from(document.querySelectorAll("#consent-checklist input:checked")).map((i) => i.value);
    const form = new FormData();
    form.append("nonce", state.nonce);
    form.append("label", $("voice-label").value.trim());
    form.append("owner_persona_id", state.persona.id);
    form.append("consent_conditions", JSON.stringify(checked));
    form.append("price_per_100_words", $("voice-price").value || "0");
    form.append("audio", state.recordedBlob, "recording.webm");
    const res = await fetch("/api/voices", { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail || "Save failed");
    closeModal("add-voice-modal");
    toast("Voice published to the marketplace.", "success");
    await loadMyVoices();
  } catch (err) {
    $("record-error").textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

async function loadMyVoices() {
  const res = await fetch("/api/voices");
  const voices = (await res.json()).filter((v) => v.owner_persona_id === state.persona.id);
  const grid = $("voices-list");
  grid.innerHTML = voices.length ? "" : '<p class="empty">No voices published yet — click "+ Add Voice" to record your first one.</p>';
  voices.slice().reverse().forEach((v) => {
    const conditions = (v.consent_conditions || []).map((c) => `<span class="pill">${escapeHtml(c.replace(/_/g, " "))}</span>`).join("");
    const card = document.createElement("div");
    card.className = "voice-card";
    card.innerHTML = `
      <div class="card-top">
        <div>
          <div class="voice-name">${escapeHtml(v.label)}</div>
          <div class="voice-owner">${new Date(v.created_at).toLocaleDateString()}</div>
        </div>
        <span class="price-tag">$${Number(v.price_per_100_words || 0).toFixed(2)}/100w</span>
      </div>
      <div class="tags">${conditions || '<span class="pill">no consent scopes</span>'}</div>
      <audio controls src="/api/base_voices/${v.filename}"></audio>
    `;
    grid.appendChild(card);
  });
}

/* ---------------- RENTER: MARKETPLACE ---------------- */

async function loadMarketplace() {
  const grid = $("marketplace-grid");
  grid.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
  const res = await fetch(`/api/marketplace?renter_persona_id=${state.persona.id}`);
  const voices = await res.json();
  grid.innerHTML = voices.length ? "" : '<p class="empty">No voices published yet.</p>';
  voices.forEach((v) => {
    const conditions = (v.consent_conditions || []).map((c) => `<span class="pill">${escapeHtml(c.replace(/_/g, " "))}</span>`).join("");
    const card = document.createElement("div");
    card.className = "voice-card";
    card.innerHTML = `
      <div class="card-top">
        <div>
          <div class="voice-name">${escapeHtml(v.label)}</div>
          <div class="voice-owner">by ${escapeHtml(v.owner_persona_name || "—")}</div>
        </div>
        <span class="price-tag">$${Number(v.price_per_100_words || 0).toFixed(2)}/100w</span>
      </div>
      <div class="tags">${conditions || '<span class="pill">no consent scopes</span>'}</div>
      <audio controls src="/api/base_voices/${v.filename}"></audio>
      <button class="${v.is_rented ? "secondary" : "primary"} block rent-btn" ${v.is_rented ? "disabled" : ""}>
        ${v.is_rented ? "Already rented" : "Rent this voice"}
      </button>
    `;
    if (!v.is_rented) {
      card.querySelector(".rent-btn").addEventListener("click", () => openRentModal(v));
    }
    grid.appendChild(card);
  });
}

function openRentModal(voice) {
  state.pendingRentVoiceId = voice.id;
  const conditions = (voice.consent_conditions || []).map((c) => `<span class="pill">${escapeHtml(c.replace(/_/g, " "))}</span>`).join("");
  $("rent-modal-body").innerHTML = `
    <div class="voice-card" style="box-shadow:none">
      <div class="card-top">
        <div>
          <div class="voice-name">${escapeHtml(voice.label)}</div>
          <div class="voice-owner">by ${escapeHtml(voice.owner_persona_name || "—")}</div>
        </div>
        <span class="price-tag">$${Number(voice.price_per_100_words || 0).toFixed(2)}/100w</span>
      </div>
      <div class="tags">${conditions || '<span class="pill">no consent scopes</span>'}</div>
      <audio controls src="/api/base_voices/${voice.filename}"></audio>
    </div>
  `;
  openModal("rent-modal");
}
$("close-rent-modal").addEventListener("click", () => closeModal("rent-modal"));

$("confirm-rent-btn").addEventListener("click", async () => {
  const voiceId = state.pendingRentVoiceId;
  if (!voiceId) return;
  const btn = $("confirm-rent-btn");
  btn.disabled = true;
  try {
    const form = new FormData();
    form.append("renter_persona_id", state.persona.id);
    form.append("voice_id", voiceId);
    const res = await fetch("/api/voice-rentals", { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail || "Rental failed");
    closeModal("rent-modal");
    toast("Voice unlocked — find it under My Voices.", "success");
    await loadMarketplace();
  } catch (err) {
    toast(err.message, "danger");
  } finally {
    btn.disabled = false;
  }
});

async function loadRentedVoices() {
  const res = await fetch(`/api/voice-rentals?renter_persona_id=${state.persona.id}`);
  const rentals = await res.json();
  const voicesRes = await fetch("/api/voices");
  const voicesById = new Map((await voicesRes.json()).map((v) => [v.id, v]));

  const grid = $("my-voices-grid");
  grid.innerHTML = rentals.length ? "" : '<p class="empty">No rented voices yet — visit the Marketplace to rent one.</p>';
  rentals.forEach((r) => {
    const v = voicesById.get(r.voice_id);
    const card = document.createElement("div");
    card.className = "voice-card";
    card.innerHTML = `
      <div class="card-top">
        <div class="voice-name">${escapeHtml(r.voice_label)}</div>
        <span class="price-tag">$${Number(v?.price_per_100_words ?? 0).toFixed(2)}/100w</span>
      </div>
      ${v ? `<audio controls src="/api/base_voices/${v.filename}"></audio>` : '<p class="meta">Voice no longer available</p>'}
      <button class="primary block generate-open-btn" ${v ? "" : "disabled"}>Generate</button>
    `;
    card.querySelector(".generate-open-btn").addEventListener("click", () =>
      selectVoiceForGeneration(r.voice_id, r.voice_label, v?.price_per_100_words ?? 0)
    );
    grid.appendChild(card);
  });
}

function showMyVoicesGrid() {
  $("my-voices-grid").style.display = "grid";
  $("generate-panel").style.display = "none";
}

function selectVoiceForGeneration(voiceId, label, pricePer100Words) {
  state.selectedVoiceId = voiceId;
  state.selectedVoicePrice = pricePer100Words;
  $("my-voices-grid").style.display = "none";
  $("generate-panel").style.display = "block";
  $("generate-voice-title").textContent = label;
  $("generate-voice-price").textContent = `$${Number(pricePer100Words).toFixed(2)} per 100 words generated`;
  $("rent-script").value = "";
  $("rental-status").textContent = "";
  updateCostEstimate();
  loadVoiceSubmissions();
  loadVoiceOutputs();
}

$("back-to-my-voices").addEventListener("click", () => { state.selectedVoiceId = null; showMyVoicesGrid(); });

function updateCostEstimate() {
  if (!state.selectedVoiceId) return;
  const price = Number(state.selectedVoicePrice) || 0;
  const words = $("rent-script").value.trim().split(/\s+/).filter(Boolean).length;
  const cost = (words / 100) * price;
  $("script-word-count").textContent = `${words} word${words === 1 ? "" : "s"}`;
  $("script-cost-value").textContent = `$${cost.toFixed(2)}`;
}

/* ---------------- RENTER: GENERATE / SUBMISSIONS ---------------- */

async function submitRental() {
  const voiceId = state.selectedVoiceId;
  const script = $("rent-script").value.trim();
  const status = $("rental-status");
  if (!voiceId) { status.textContent = "No voice selected."; return; }
  if (!script) { status.textContent = "Enter a script."; return; }

  const btn = $("submit-rental-btn");
  btn.disabled = true;
  status.textContent = "";

  // Optimistic UI: show a pending row immediately
  const list = $("rentals-list");
  if (list.querySelector(".empty")) list.innerHTML = "";
  const pendingLi = document.createElement("li");
  pendingLi.className = "pending";
  pendingLi.innerHTML = `
    <div class="row-top">
      <strong>Submitting…</strong>
      <span class="status-badge">screening</span>
    </div>
    <div class="meta">"${escapeHtml(script)}"</div>
  `;
  list.prepend(pendingLi);

  try {
    const form = new FormData();
    form.append("renter_persona_id", state.persona.id);
    form.append("voice_id", voiceId);
    form.append("script", script);
    const res = await fetch("/api/rentals", { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail || "Submission failed");
    const rental = await res.json();
    $("rent-script").value = "";
    updateCostEstimate();

    if (rental.status === "approved") toast("Script auto-approved — audio generated.", "success");
    else if (rental.status === "denied") toast("Script was denied by screening.", "danger");
    else toast("Script sent to the voice owner for manual review.", "warn");

    await Promise.all([loadVoiceSubmissions(), loadVoiceOutputs()]);
  } catch (err) {
    status.textContent = err.message;
    toast(err.message, "danger");
    pendingLi.remove();
  } finally {
    btn.disabled = false;
  }
}

async function loadVoiceSubmissions() {
  const res = await fetch("/api/rentals");
  const rentals = await res.json();
  const mine = rentals.filter((r) => r.renter_persona_id === state.persona.id && r.voice_id === state.selectedVoiceId);
  const list = $("rentals-list");
  list.innerHTML = mine.length ? "" : '<li class="empty">No submissions yet.</li>';
  mine.slice().reverse().forEach((r) => {
    const li = document.createElement("li");
    const flags = (r.flags || []).map((f) => `<span class="pill">${escapeHtml(f.replace(/_/g, " "))}</span>`).join("") || '<span class="meta">none</span>';
    li.innerHTML = `
      <div class="row-top">
        <strong>${escapeHtml(r.voice_label)}</strong>
        <span class="status-badge status-${r.status}">${r.status.replace(/_/g, " ")}</span>
      </div>
      <div class="meta">"${escapeHtml(r.script)}"</div>
      <div class="tags" style="margin-top:0.35rem">${flags}</div>
      <div class="meta" style="margin-top:0.25rem">${new Date(r.created_at).toLocaleString()}</div>
    `;
    list.appendChild(li);
  });
}

async function loadVoiceOutputs() {
  const res = await fetch("/api/outputs");
  const outputs = (await res.json()).filter((o) => o.voice_id === state.selectedVoiceId);
  const list = $("outputs-list");
  list.innerHTML = outputs.length ? "" : '<li class="empty">No generated audio yet.</li>';
  outputs.slice().reverse().forEach((o) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="row-top"><strong>${escapeHtml(o.voice_label)}</strong><span class="price-tag">$${Number(o.charge ?? 0).toFixed(2)}</span></div>
      <div class="meta">"${escapeHtml(o.text)}" · ${o.word_count ?? "?"} words · ${new Date(o.created_at).toLocaleString()}</div>
      <audio controls src="/api/outputs/${o.filename}"></audio>
    `;
    list.appendChild(li);
  });
}

$("rent-script").addEventListener("input", updateCostEstimate);

/* ---------------- ACTOR: DASHBOARD ---------------- */

async function loadDashboard() {
  const res = await fetch(`/api/dashboard?owner_persona_id=${state.persona.id}`);
  const data = await res.json();

  $("dashboard-stats").innerHTML = `
    <div class="stat-tile accent">
      <div class="value">$${data.total_revenue.toFixed(2)}</div>
      <div class="label">Total revenue</div>
    </div>
    <div class="stat-tile">
      <div class="value">${data.voices.length}</div>
      <div class="label">Published voices</div>
    </div>
    <div class="stat-tile">
      <div class="value">${data.voices.reduce((s, v) => s + v.usage_count, 0)}</div>
      <div class="label">Total generations</div>
    </div>
  `;

  const list = $("dashboard-list");
  list.innerHTML = data.voices.length ? "" : '<li class="empty">Publish a voice to see stats here.</li>';
  data.voices.slice().sort((a, b) => b.revenue - a.revenue).forEach((v) => {
    const li = document.createElement("li");
    const idle = v.usage_count === 0;
    li.innerHTML = `
      <div class="row-top">
        <strong>${escapeHtml(v.label)}</strong>
        <span class="price-tag">$${v.revenue.toFixed(2)}</span>
      </div>
      <div class="meta">$${Number(v.price_per_100_words).toFixed(2)} / 100 words · ${v.usage_count} generation(s)</div>
      ${idle ? '<div class="meta" style="color:var(--warn)">No generations yet — unused inventory earns nothing.</div>' : ""}
    `;
    list.appendChild(li);
  });
}

/* ---------------- ACTOR: APPROVALS ---------------- */

function updateBulkButtons() {
  const n = state.selectedApprovalIds.size;
  $("bulk-approve-btn").disabled = n === 0;
  $("bulk-deny-btn").disabled = n === 0;
  $("bulk-approve-btn").textContent = n ? `Approve selected (${n})` : "Approve selected";
  $("bulk-deny-btn").textContent = n ? `Deny selected (${n})` : "Deny selected";
}

async function loadApprovals() {
  const res = await fetch("/api/rentals?status=pending_actor_review");
  const rentals = await res.json();
  const mine = rentals.filter((r) => r.owner_persona_id === state.persona.id);

  // Filter popover options
  const voiceOptions = [...new Map(mine.map((r) => [r.voice_id, r.voice_label])).entries()];
  const popover = $("approvals-filter-popover");
  popover.innerHTML = [`<button data-voice="" class="${!state.approvalsFilterVoiceId ? "active" : ""}">All voices</button>`]
    .concat(voiceOptions.map(([id, label]) => `<button data-voice="${id}" class="${state.approvalsFilterVoiceId === id ? "active" : ""}">${escapeHtml(label)}</button>`))
    .join("");
  popover.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.approvalsFilterVoiceId = btn.dataset.voice || null;
      $("approvals-filter-btn").textContent = `Filter: ${btn.dataset.voice ? btn.textContent : "All voices"}`;
      popover.classList.remove("open");
      loadApprovals();
    });
  });

  const visible = state.approvalsFilterVoiceId ? mine.filter((r) => r.voice_id === state.approvalsFilterVoiceId) : mine;

  const list = $("review-list");
  list.innerHTML = visible.length ? "" : '<li class="empty">Nothing awaiting your review.</li>';
  state.selectedApprovalIds = new Set([...state.selectedApprovalIds].filter((id) => visible.some((r) => r.id === id)));

  visible.slice().reverse().forEach((r) => {
    const li = document.createElement("li");
    const flags = (r.flags || []).map((f) => {
      const blocked = f === "hate_violence" || f === "impersonation";
      return `<span class="flag-pill${blocked ? " blocked" : ""}">${escapeHtml(f.replace(/_/g, " "))}</span>`;
    }).join("") || '<span class="meta">no flags</span>';

    li.innerHTML = `
      <div class="row-top">
        <label class="select-row">
          <input type="checkbox" class="approval-check" ${state.selectedApprovalIds.has(r.id) ? "checked" : ""} />
          <strong>${escapeHtml(r.voice_label)}</strong>
        </label>
        <span class="meta">from ${escapeHtml(r.renter_persona_name)}</span>
      </div>
      <div class="meta" style="margin:0.35rem 0">Flagged: ${flags}</div>
      <div class="meta">"${escapeHtml(r.script)}"</div>
      ${r.screening_note ? `<div class="meta">note: ${escapeHtml(r.screening_note)}</div>` : ""}
      <div class="record-controls" style="margin-top:0.6rem">
        <button class="primary small approve-btn">Approve</button>
        <button class="danger small deny-btn">Deny</button>
      </div>
    `;
    li.querySelector(".approval-check").addEventListener("change", (e) => {
      if (e.target.checked) state.selectedApprovalIds.add(r.id);
      else state.selectedApprovalIds.delete(r.id);
      updateBulkButtons();
    });
    li.querySelector(".approve-btn").addEventListener("click", () => decideRental(r.id, "approve"));
    li.querySelector(".deny-btn").addEventListener("click", () => decideRental(r.id, "deny"));
    list.appendChild(li);
  });

  updateBulkButtons();
}

$("approvals-filter-btn").addEventListener("click", () => togglePopover("approvals-filter-popover"));

async function decideRental(rentalId, decision) {
  const form = new FormData();
  form.append("decider_persona_id", state.persona.id);
  form.append("decision", decision);
  const res = await fetch(`/api/rentals/${rentalId}/decision`, { method: "POST", body: form });
  if (!res.ok) {
    toast((await res.json()).detail || "Decision failed", "danger");
    return;
  }
  toast(decision === "approve" ? "Script approved — audio generated." : "Script denied.", decision === "approve" ? "success" : "warn");
  state.selectedApprovalIds.delete(rentalId);
  await loadApprovals();
}

async function bulkDecide(decision) {
  const ids = [...state.selectedApprovalIds];
  if (!ids.length) return;
  const btn = decision === "approve" ? $("bulk-approve-btn") : $("bulk-deny-btn");
  btn.disabled = true;
  let ok = 0, fail = 0;
  for (const id of ids) {
    const form = new FormData();
    form.append("decider_persona_id", state.persona.id);
    form.append("decision", decision);
    const res = await fetch(`/api/rentals/${id}/decision`, { method: "POST", body: form });
    if (res.ok) ok++; else fail++;
  }
  state.selectedApprovalIds.clear();
  toast(`${ok} script(s) ${decision === "approve" ? "approved" : "denied"}${fail ? `, ${fail} failed` : ""}.`, fail ? "warn" : "success");
  await loadApprovals();
}

$("bulk-approve-btn").addEventListener("click", () => bulkDecide("approve"));
$("bulk-deny-btn").addEventListener("click", () => bulkDecide("deny"));

/* ---------------- WIRING ---------------- */

$("new-phrase-btn").addEventListener("click", fetchPhrase);
$("record-btn").addEventListener("click", toggleRecording);
$("redo-recording-btn").addEventListener("click", redoRecording);
$("save-voice-btn").addEventListener("click", saveVoice);
$("submit-rental-btn").addEventListener("click", submitRental);

loadLoginPersonas();
loadShowcaseSamples();
if (state.persona) {
  enterApp();
}
