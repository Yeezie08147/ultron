/**
 * Ambient HUD elements that fill the screen with the JARVIS vibe:
 *  - voice waveform (audio-reactive, bottom)
 *  - scrolling telemetry ticker (left edge)
 *  - top-right info panel (link/model/session)
 * All decorative + cheap; driven by the same audio analyser as the orb.
 */
const LOAD_T = performance.now();

// shared accent (set by main.ts per state) so the waveform recolors too
let accent: [number, number, number] = [14, 165, 233];
export function setHudAccent(rgb: [number, number, number]) { accent = rgb; }

export function initWaveform(canvas: HTMLCanvasElement, analyser: AnalyserNode) {
  const ctx = canvas.getContext("2d")!;
  const freq = new Uint8Array(analyser.frequencyBinCount);
  function size() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = canvas.clientHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", size); size();

  const BARS = 96;
  function draw() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    analyser.getByteFrequencyData(freq);
    const bw = w / BARS;
    for (let i = 0; i < BARS; i++) {
      // mirror from the centre for symmetry
      const m = Math.abs(i - BARS / 2) / (BARS / 2);
      const idx = Math.floor(m * freq.length * 0.55);
      const v = (freq[idx] || 0) / 255;
      const bh = Math.max(2, v * h * 0.92 + 1.5);
      ctx.fillStyle = `rgba(${accent[0]},${accent[1]},${accent[2]},${0.18 + v * 0.6})`;
      ctx.fillRect(i * bw + bw * 0.25, h / 2 - bh / 2, bw * 0.5, bh);
    }
    requestAnimationFrame(draw);
  }
  draw();
}

export function initTicker(el: HTMLElement) {
  const phrases = [
    "neural link nominal", "cognition core stable", "vitals within range",
    "vad armed", "tts pipeline ready", "audio context live", "cache warm",
    "subsystem check ok", "listening grid active", "context window 200k",
    "uplink secure", "diagnostics clear", "sensor array nominal",
    "memory index synced", "voice synth online", "latency nominal",
  ];
  const lines: string[] = [];
  let n = 0;
  function stamp() {
    const d = new Date();
    const p = (x: number) => String(x).padStart(2, "0");
    return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }
  function push() {
    const ph = phrases[(n++ * 7) % phrases.length]; // deterministic-ish rotation
    lines.unshift(`${stamp()} ▸ ${ph}`);
    if (lines.length > 14) lines.pop();
    el.innerHTML = lines
      .map((l, i) => `<div style="opacity:${Math.max(0.12, 1 - i * 0.085)}">${l}</div>`)
      .join("");
  }
  push();
  setInterval(push, 1400);
}

export function initInfoPanel(el: HTMLElement, getModel: () => string) {
  function render() {
    const up = Math.floor((performance.now() - LOAD_T) / 1000);
    const hh = String(Math.floor(up / 3600)).padStart(2, "0");
    const mm = String(Math.floor((up % 3600) / 60)).padStart(2, "0");
    const ss = String(up % 60).padStart(2, "0");
    el.innerHTML =
      `<div><span class="ik">LINK</span><span class="iv">SECURE</span></div>` +
      `<div><span class="ik">MODEL</span><span class="iv">${getModel()}</span></div>` +
      `<div><span class="ik">SESSION</span><span class="iv">${hh}:${mm}:${ss}</span></div>`;
  }
  render();
  setInterval(render, 1000);
}
