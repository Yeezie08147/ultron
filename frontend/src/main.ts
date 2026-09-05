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

  if (type === "audio") {
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
      if (subGhzLogConsole && (txt.includes("Sub-GHz") || txt.includes("RF") || txt.includes("NFC") || txt.includes("RFID") || txt.includes("Infrared") || txt.includes("iButton") || txt.includes("MHz") || txt.includes("BadUSB"))) {
        subGhzLogConsole.textContent = `[${new Date().toLocaleTimeString()}] ${txt}`;
      }
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
    if (subGhzLogConsole && txt && (txt.includes("Sub-GHz") || txt.includes("RF") || txt.includes("NFC") || txt.includes("RFID") || txt.includes("Infrared") || txt.includes("iButton") || txt.includes("MHz") || txt.includes("BadUSB"))) {
      subGhzLogConsole.textContent = `[${new Date().toLocaleTimeString()}] ${txt}`;
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

const btnMute = document.getElementById("btn-mute")!;
const btnMenu = document.getElementById("btn-menu");
const menuDropdown = document.getElementById("menu-dropdown");
const btnRestart = document.getElementById("btn-restart");
const btnFixSelf = document.getElementById("btn-fix-self");

// Sub-GHz Controls
const btnSubGhz = document.getElementById("btn-subghz");
const subGhzModal = document.getElementById("subghz-modal");
const btnSubGhzClose = document.getElementById("btn-subghz-close");
const subGhzFreqSelect = document.getElementById("subghz-freq") as HTMLSelectElement | null;
const btnSubGhzRead = document.getElementById("btn-subghz-read");
const btnSubGhzRaw = document.getElementById("btn-subghz-raw");
const btnNfcRead = document.getElementById("btn-nfc-read");
const btnRfidRead = document.getElementById("btn-rfid-read");
const btnIrRead = document.getElementById("btn-ir-read");
const btnIbuttonRead = document.getElementById("btn-ibutton-read");
const subGhzLogConsole = document.getElementById("subghz-log-console");

btnSubGhz?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (subGhzModal) {
    subGhzModal.style.display = subGhzModal.style.display === "none" ? "block" : "none";
  }
});

btnSubGhzClose?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (subGhzModal) subGhzModal.style.display = "none";
});

btnSubGhzRead?.addEventListener("click", (e) => {
  e.stopPropagation();
  const freq = subGhzFreqSelect ? subGhzFreqSelect.value : "433.92";
  if (subGhzLogConsole) subGhzLogConsole.textContent = `[${new Date().toLocaleTimeString()}] Listening for digital Sub-GHz RF packet at ${freq} MHz...`;
  socket.send({ type: "chat", text: `read sub ghz at ${freq}` });
});

btnSubGhzRaw?.addEventListener("click", (e) => {
  e.stopPropagation();
  const freq = subGhzFreqSelect ? subGhzFreqSelect.value : "433.92";
  if (subGhzLogConsole) subGhzLogConsole.textContent = `[${new Date().toLocaleTimeString()}] Recording raw IQ waveform stream at ${freq} MHz...`;
  socket.send({ type: "chat", text: `read raw sub ghz at ${freq}` });
});

btnNfcRead?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (subGhzLogConsole) subGhzLogConsole.textContent = `[${new Date().toLocaleTimeString()}] Scanning High-Frequency (13.56 MHz) NFC Tag...`;
  socket.send({ type: "chat", text: "read nfc" });
});

btnRfidRead?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (subGhzLogConsole) subGhzLogConsole.textContent = `[${new Date().toLocaleTimeString()}] Reading 125 kHz RFID Proximity Tag...`;
  socket.send({ type: "chat", text: "read rfid" });
});

btnIrRead?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (subGhzLogConsole) subGhzLogConsole.textContent = `[${new Date().toLocaleTimeString()}] Demodulating 38 kHz Infrared signal...`;
  socket.send({ type: "chat", text: "read ir" });
});

btnIbuttonRead?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (subGhzLogConsole) subGhzLogConsole.textContent = `[${new Date().toLocaleTimeString()}] Reading 1-Wire Dallas DS1990A key...`;
  socket.send({ type: "chat", text: "read ibutton" });
});

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

btnRestart?.addEventListener("click", async (e) => {
  e.stopPropagation();
  if (menuDropdown) menuDropdown.style.display = "none";
  statusEl.textContent = "restarting...";
  try {
    await fetch("/api/restart", { method: "POST" });
    // Wait a few seconds then reload
    setTimeout(() => window.location.reload(), 4000);
  } catch {
    statusEl.textContent = "restart failed";
  }
});

btnFixSelf?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (menuDropdown) menuDropdown.style.display = "none";
  // Activate work mode on the WebSocket session (JARVIS becomes Claude Code's voice)
  socket.send({ type: "fix_self" });
  statusEl.textContent = "entering work mode...";
});

// Settings button
const btnSettings = document.getElementById("btn-settings")!;
btnSettings.addEventListener("click", (e) => {
  e.stopPropagation();
  if (menuDropdown) menuDropdown.style.display = "none";
  openSettings();
});

// First-time setup detection — check after a short delay for server readiness
setTimeout(() => {
  checkFirstTimeSetup();
}, 2000);
