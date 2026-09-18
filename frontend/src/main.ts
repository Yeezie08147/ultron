/**
 * JARVIS — Main entry point.
 *
 * Wires together the orb visualization, WebSocket communication,
 * speech recognition, and audio playback into a single experience.
 */

import { createOrb, type OrbState } from "./orb";
import { createVoiceInput, createAudioPlayer } from "./voice";
import { createSocket } from "./ws";
import { openSettings, checkFirstTimeSetup } from "./settings";
import "./style.css";

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type State = "idle" | "listening" | "thinking" | "speaking";
let currentState: State = "idle";
let isMuted = false;

const statusEl = document.getElementById("status-text")!;
const errorEl = document.getElementById("error-text")!;

function showError(msg: string) {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 5000);
}

function updateStatus(state: State) {
  const labels: Record<State, string> = {
    idle: "",
    listening: "listening...",
    thinking: "thinking...",
    speaking: "",
  };
  statusEl.textContent = labels[state];
}

// ---------------------------------------------------------------------------
// Init components
// ---------------------------------------------------------------------------

const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
const orb = createOrb(canvas);

// ── Neural Stack Screen & Device Matrix State ──
let isScreenLocked = true;
const hudStateEl = document.getElementById("hud-state");
const actionBannerEl = document.getElementById("action-banner");
const actionBannerText = document.getElementById("action-banner-text");
const matrixListEl = document.getElementById("matrix-devices-list");

function setActionBanner(text: string) {
  if (actionBannerText) actionBannerText.textContent = text;
  if (actionBannerEl) {
    actionBannerEl.style.opacity = "1";
    setTimeout(() => {
      if (actionBannerEl) actionBannerEl.style.opacity = "0.75";
    }, 4000);
  }
}

function updateScreenLockUI(locked: boolean) {
  isScreenLocked = locked;
  document.body.setAttribute("data-screen", locked ? "locked" : "unlocked");
  orb.setLocked(locked);
  if (hudStateEl) hudStateEl.textContent = locked ? "SYSTEM LOCKED" : "ONLINE";
  setActionBanner(locked ? "SYSTEM LOCKED" : "SYSTEM UNLOCKED // ULTRON ACTIVE");
}

function renderDeviceMatrix(devices: any[]) {
  if (!matrixListEl) return;
  if (!Array.isArray(devices) || devices.length === 0) {
    matrixListEl.innerHTML = `
      <div class="matrix-empty">
        <div class="matrix-empty-icon">📱</div>
        <div class="matrix-empty-title">NO DEVICES CONNECTED</div>
        <div class="matrix-empty-sub">Connect Android phone via USB (with USB Debugging) to link with ULTRON</div>
      </div>
    `;
    return;
  }
  matrixListEl.innerHTML = devices.map((d: any) => {
    const isDevLocked = d.status === "LOCKED";
    const badgeClass = isDevLocked ? "locked" : "unlocked";
    const bat = d.battery ? `🔋 ${d.battery}%` : "🔋 --";
    const media = d.media && d.media !== "Standby" ? ` • ${d.media}` : "";
    return `
      <div class="matrix-card">
        <div class="matrix-card-top">
          <span class="dev-name">${d.name || "Device"}</span>
          <span class="dev-badge ${badgeClass}">${d.status}</span>
        </div>
        <div class="matrix-card-sub">${d.serial || "ADB"} • ${bat}${media}</div>
      </div>
    `;
  }).join("");
}

const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
const WS_URL = `${wsProto}//${window.location.host}/ws/voice`;
const socket = createSocket(WS_URL);

const audioPlayer = createAudioPlayer();
orb.setAnalyser(audioPlayer.getAnalyser());

function transition(newState: State) {
  if (newState === currentState) return;
  currentState = newState;
  orb.setState(newState as OrbState);
  updateStatus(newState);

  switch (newState) {
    case "idle":
      if (!isMuted) voiceInput.resume();
      break;
    case "listening":
      if (!isMuted) voiceInput.resume();
      break;
    case "thinking":
      voiceInput.pause();
      break;
    case "speaking":
      voiceInput.pause();
      break;
  }
}

// ---------------------------------------------------------------------------
// Voice input
// ---------------------------------------------------------------------------

const voiceInput = createVoiceInput(
  (text: string) => {
    // Cancel any current JARVIS response before sending new input
    audioPlayer.stop();
    // User spoke — send transcript
    socket.send({ type: "transcript", text, isFinal: true });
    transition("thinking");
  },
  (msg: string) => {
    showError(msg);
  }
);

// ---------------------------------------------------------------------------
// Audio playback finished
// ---------------------------------------------------------------------------

audioPlayer.onFinished(() => {
  transition("idle");
});

// ---------------------------------------------------------------------------
// WebSocket messages
// ---------------------------------------------------------------------------

socket.onMessage((msg) => {
  const type = msg.type as string;

  if (type === "screen_state") {
    updateScreenLockUI(!!msg.locked);
  } else if (type === "device_matrix_update") {
    renderDeviceMatrix(msg.devices as any[]);
  } else if (type === "transcript") {
    const txt = String(msg.text || "");
    if (txt) {
      console.log("[transcript]", txt);
      setActionBanner(`User: "${txt}"`);
      const captionEl = document.getElementById("caption");
      if (captionEl) captionEl.textContent = `User: "${txt}"`;
      if (currentState === "idle") {
        transition("thinking");
      }
    }
  } else if (type === "audio") {
    const audioData = msg.data as string;
    console.log("[audio] received", audioData ? `${audioData.length} chars` : "EMPTY", "state:", currentState);
    if (audioData) {
      if (currentState !== "speaking") {
        transition("speaking");
      }
      audioPlayer.enqueue(audioData);
    } else {
      // TTS failed — no audio but still need to return to idle
      console.warn("[audio] no data received, returning to idle");
      transition("idle");
    }
    // Log text for debugging
    const txt = String(msg.text || "");
    if (txt) {
      console.log("[ULTRON]", txt);
      setActionBanner(txt);
      const captionEl = document.getElementById("caption");
      if (captionEl) captionEl.textContent = txt;
    }
  } else if (type === "status") {
    const state = msg.state as string;
    if (state === "thinking" && currentState !== "thinking") {
      transition("thinking");
    } else if (state === "working") {
      // Task spawned — show thinking with a different label
      transition("thinking");
      statusEl.textContent = "working...";
    } else if (state === "idle") {
      transition("idle");
    }
  } else if (type === "text") {
    // Text fallback when TTS fails
    const txt = String(msg.text || "");
    console.log("[ULTRON]", txt);
    if (txt) {
      setActionBanner(txt);
      const captionEl = document.getElementById("caption");
      if (captionEl) captionEl.textContent = txt;
    }
  } else if (type === "task_spawned") {
    console.log("[task]", "spawned:", msg.task_id, msg.prompt);
  } else if (type === "task_complete") {
    console.log("[task]", "complete:", msg.task_id, msg.status, msg.summary);
  }
});

// ---------------------------------------------------------------------------
// Kick off
// ---------------------------------------------------------------------------

// Start listening after a brief delay for the orb to render
setTimeout(() => {
  voiceInput.start();
  transition("listening");
}, 1000);

// Resume AudioContext on ANY user interaction (browser autoplay policy)
function ensureAudioContext() {
  const ctx = audioPlayer.getAnalyser().context as AudioContext;
  if (ctx.state === "suspended") {
    ctx.resume().then(() => console.log("[audio] context resumed"));
  }
}
document.addEventListener("click", ensureAudioContext);
document.addEventListener("touchstart", ensureAudioContext);
document.addEventListener("keydown", ensureAudioContext, { once: true });

// Try to resume audio context on load
ensureAudioContext();

// ---------------------------------------------------------------------------
// UI Controls
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// UI Controls & Dropdown Menu
// ---------------------------------------------------------------------------

const btnMute = document.getElementById("btn-mute")!;
const btnMenu = document.getElementById("btn-menu");
const menuDropdown = document.getElementById("menu-dropdown");
const btnSettings = document.getElementById("btn-settings");
const btnChangePass = document.getElementById("btn-change-pass");
const btnLockSystem = document.getElementById("btn-lock-system");
const btnAbout = document.getElementById("btn-about");

btnMute.addEventListener("click", (e) => {
  e.stopPropagation();
  isMuted = !isMuted;
  btnMute.classList.toggle("muted", isMuted);
  if (isMuted) {
    voiceInput.pause();
    transition("idle");
  } else {
    voiceInput.resume();
    transition("listening");
  }
});

btnMenu?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (menuDropdown) menuDropdown.style.display = menuDropdown.style.display === "none" ? "block" : "none";
});

document.addEventListener("click", (e) => {
  const target = e.target as HTMLElement;
  if (menuDropdown && !target.closest("#btn-menu")) menuDropdown.style.display = "none";
});

btnSettings?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (menuDropdown) menuDropdown.style.display = "none";
  openSettings();
});

btnAbout?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (menuDropdown) menuDropdown.style.display = "none";
  setActionBanner("ULTRON // Autonomous Cybernetic Intelligence");
});

// ---------------------------------------------------------------------------
// Master Passcode & Security Matrix Flow
// ---------------------------------------------------------------------------

const authModal = document.getElementById("auth-modal");
const authBox = document.querySelector(".auth-box") as HTMLElement | null;
const authTitle = document.getElementById("auth-title");
const authSubtitle = document.getElementById("auth-subtitle");
const authFieldConfirm = document.getElementById("auth-field-confirm");
const authInputPass = document.getElementById("auth-input-pass") as HTMLInputElement | null;
const authInputConfirm = document.getElementById("auth-input-confirm") as HTMLInputElement | null;
const authErrorMsg = document.getElementById("auth-error-msg");
const btnAuthSubmit = document.getElementById("btn-auth-submit");
const authForm = document.getElementById("auth-form");

let authMode: "setup" | "login" | "change" = "login";

function showAuthError(msg: string) {
  if (authErrorMsg) {
    authErrorMsg.textContent = msg;
    authErrorMsg.style.display = "block";
  }
  if (authBox) {
    authBox.classList.remove("shake");
    void authBox.offsetWidth;
    authBox.classList.add("shake");
  }
}

function clearAuthError() {
  if (authErrorMsg) {
    authErrorMsg.textContent = "";
    authErrorMsg.style.display = "none";
  }
}

function openAuthModal(mode: "setup" | "login" | "change") {
  authMode = mode;
  clearAuthError();
  if (authInputPass) authInputPass.value = "";
  if (authInputConfirm) authInputConfirm.value = "";

  if (mode === "setup") {
    if (authTitle) authTitle.textContent = "CREATE MASTER PASSCODE";
    if (authSubtitle) authSubtitle.textContent = "SET A SECURITY PASSCODE TO INITIALIZE ULTRON";
    if (authFieldConfirm) authFieldConfirm.style.display = "block";
    if (btnAuthSubmit) btnAuthSubmit.textContent = "CREATE & UNLOCK";
    if (authInputPass) authInputPass.placeholder = "Enter Master Passcode";
  } else if (mode === "login") {
    if (authTitle) authTitle.textContent = "ULTRON SECURITY MATRIX";
    if (authSubtitle) authSubtitle.textContent = "ENTER MASTER PASSCODE TO UNLOCK SYSTEM";
    if (authFieldConfirm) authFieldConfirm.style.display = "none";
    if (btnAuthSubmit) btnAuthSubmit.textContent = "UNLOCK ULTRON";
    if (authInputPass) authInputPass.placeholder = "Master Passcode";
  } else if (mode === "change") {
    if (authTitle) authTitle.textContent = "CHANGE MASTER PASSCODE";
    if (authSubtitle) authSubtitle.textContent = "ENTER CURRENT AND NEW PASSCODE";
    if (authFieldConfirm) authFieldConfirm.style.display = "block";
    if (btnAuthSubmit) btnAuthSubmit.textContent = "UPDATE PASSCODE";
    if (authInputPass) authInputPass.placeholder = "Current Passcode";
    if (authInputConfirm) authInputConfirm.placeholder = "New Passcode";
  }

  if (authModal) authModal.style.display = "flex";
  setTimeout(() => authInputPass?.focus(), 150);
}

function closeAuthModal() {
  if (authModal) authModal.style.display = "none";
  clearAuthError();
}

async function checkAuthStatus() {
  try {
    const token = localStorage.getItem("ultron_session_token") || "";
    const res = await fetch("/api/auth/status", {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    
    if (!data.has_password) {
      openAuthModal("setup");
      updateScreenLockUI(true);
    } else if (!data.authenticated) {
      openAuthModal("login");
      updateScreenLockUI(true);
    } else {
      closeAuthModal();
      updateScreenLockUI(!!data.screen_locked);
    }
  } catch (e) {
    console.warn("Auth check error:", e);
  }
}

authForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAuthError();
  const pass1 = authInputPass?.value.trim() || "";
  const pass2 = authInputConfirm?.value.trim() || "";

  if (authMode === "setup") {
    if (pass1.length < 3) {
      showAuthError("Passcode must be at least 3 characters.");
      return;
    }
    if (pass1 !== pass2) {
      showAuthError("Passcodes do not match.");
      return;
    }
    try {
      const res = await fetch("/api/auth/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pass1 })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        showAuthError(data.error || "Failed to create passcode.");
        return;
      }
      localStorage.setItem("ultron_session_token", data.token);
      closeAuthModal();
      updateScreenLockUI(false);
      setActionBanner("MASTER PASSCODE CREATED // ACCESS GRANTED");
      socket.send({ type: "chat", text: "report status" });
    } catch {
      showAuthError("Connection error. Try again.");
    }
  } else if (authMode === "login") {
    if (!pass1) {
      showAuthError("Enter master passcode.");
      return;
    }
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pass1 })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        showAuthError(data.error || "Invalid master passcode.");
        return;
      }
      localStorage.setItem("ultron_session_token", data.token);
      closeAuthModal();
      updateScreenLockUI(false);
      setActionBanner("ACCESS GRANTED // WELCOME BACK, SIR");
    } catch {
      showAuthError("Connection error. Try again.");
    }
  } else if (authMode === "change") {
    if (!pass1 || !pass2) {
      showAuthError("Both current and new passcodes are required.");
      return;
    }
    if (pass2.length < 3) {
      showAuthError("New passcode must be at least 3 characters.");
      return;
    }
    try {
      const res = await fetch("/api/auth/change", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password: pass1, new_password: pass2 })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        showAuthError(data.error || "Failed to update passcode.");
        return;
      }
      closeAuthModal();
      setActionBanner("MASTER PASSCODE UPDATED");
    } catch {
      showAuthError("Connection error.");
    }
  }
});

btnLockSystem?.addEventListener("click", async (e) => {
  e.stopPropagation();
  if (menuDropdown) menuDropdown.style.display = "none";
  localStorage.removeItem("ultron_session_token");
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch {}
  updateScreenLockUI(true);
  openAuthModal("login");
});

btnChangePass?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (menuDropdown) menuDropdown.style.display = "none";
  openAuthModal("change");
});

// ---------------------------------------------------------------------------
// Chat Input & Action Buttons
// ---------------------------------------------------------------------------

const chatInput = document.getElementById("chat-input") as HTMLInputElement | null;
chatInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && chatInput.value.trim()) {
    const text = chatInput.value.trim();
    chatInput.value = "";
    audioPlayer.stop();
    socket.send({ type: "chat", text });
    transition("thinking");
    setActionBanner(text);
  }
});

const btnQuickUnlock = document.getElementById("btn-quick-unlock");
const btnMatrixToggle = document.getElementById("btn-matrix-toggle");
const btnMatrixMinimize = document.getElementById("btn-matrix-minimize");
const deviceMatrixHud = document.getElementById("device-matrix-hud");
const btnActionUnlockPhones = document.getElementById("btn-action-unlock-phones");
const btnActionPlaySong = document.getElementById("btn-action-play-song");
const btnActionTogglePc = document.getElementById("btn-action-toggle-pc");

btnQuickUnlock?.addEventListener("click", () => {
  openAuthModal("login");
});

btnMatrixToggle?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (deviceMatrixHud) {
    deviceMatrixHud.style.display = deviceMatrixHud.style.display === "none" ? "block" : "none";
  }
});

btnMatrixMinimize?.addEventListener("click", (e) => {
  e.stopPropagation();
  deviceMatrixHud?.classList.toggle("minimized");
});

btnActionUnlockPhones?.addEventListener("click", () => {
  setActionBanner("Unlocking mobile devices...");
  socket.send({ type: "chat", text: "unlock my mobile devices" });
});

btnActionPlaySong?.addEventListener("click", () => {
  setActionBanner("Playing favorite song across matrix...");
  socket.send({ type: "chat", text: "play my favorite song in all my devices" });
});

btnActionTogglePc?.addEventListener("click", () => {
  if (isScreenLocked) {
    openAuthModal("login");
  } else {
    setActionBanner("Locking system...");
    socket.send({ type: "action", action: "lock_screen" });
  }
});

// Periodic real-time poll for connected mobile devices
async function pollDevices() {
  try {
    const dRes = await fetch("/api/devices");
    if (dRes.ok) {
      const dData = await dRes.json();
      renderDeviceMatrix(dData.devices || []);
    }
  } catch {}
}

// Initial fetch for screen state & devices
async function initNeuralStackState() {
  try {
    await checkAuthStatus();
    await pollDevices();
  } catch (e) {
    console.warn("Failed to fetch initial state", e);
  }
}
initNeuralStackState();

// Poll devices every 4 seconds
setInterval(pollDevices, 4000);

// Check first time setup after slight delay
setTimeout(() => {
  checkFirstTimeSetup();
}, 2500);

