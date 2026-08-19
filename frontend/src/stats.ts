/**
 * stats.ts — a plain live system graph (CPU / NVIDIA-GPU / RAM) for testing.
 * Self-contained: injects its own panel + canvas and polls /api/vitals. Press
 * `g` to hide.
 */
type V = {
  cpu: number; cpu_cores: number; load1: number;
  mem_pct: number; mem_used_gb: number; mem_total_gb: number;
  gpu: { util: number | null; mem_used: number | null; mem_total: number | null; temp: number | null };
};

export function initTestStats() {
  const N = 90;
  const cpuH: number[] = [], gpuH: number[] = [], memH: number[] = [];

  const panel = document.createElement("div");
  panel.id = "test-stats";
  panel.style.cssText = [
    "position:fixed", "left:18px", "bottom:18px", "z-index:50",
    "width:460px", "background:rgba(6,12,18,0.86)", "border:1px solid rgba(54,211,255,0.35)",
    "border-radius:10px", "padding:10px 12px", "backdrop-filter:blur(6px)",
    "font:12px/1.5 'Segoe UI',monospace", "color:#cfe6f2", "pointer-events:none",
  ].join(";");

  const read = document.createElement("div");
  read.style.cssText = "margin-bottom:6px;letter-spacing:.3px;white-space:nowrap";
  const canvas = document.createElement("canvas");
  canvas.width = 436; canvas.height = 120;
  canvas.style.cssText = "width:436px;height:120px;display:block";
  const legend = document.createElement("div");
  legend.style.cssText = "margin-top:4px;font-size:11px;color:#7e98a8";
  legend.innerHTML =
    '<span style="color:#36d3ff">■</span> CPU &nbsp; ' +
    '<span style="color:#54e0a0">■</span> NVIDIA GPU &nbsp; ' +
    '<span style="color:#ffb547">■</span> RAM &nbsp;&nbsp; <span style="opacity:.7">(press g to hide)</span>';
  panel.append(read, canvas, legend);
  document.body.appendChild(panel);

  const ctx = canvas.getContext("2d")!;
  const W = canvas.width, H = canvas.height;

  function drawGraph() {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = "rgba(120,152,168,0.15)"; ctx.lineWidth = 1;
    for (let p = 0; p <= 100; p += 25) {
      const y = H - (p / 100) * H;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    const line = (hist: number[], color: string) => {
      ctx.strokeStyle = color; ctx.lineWidth = 1.8; ctx.beginPath();
      for (let i = 0; i < hist.length; i++) {
        const x = (i / (N - 1)) * W;
        const y = H - (Math.max(0, Math.min(100, hist[i])) / 100) * H;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      ctx.stroke();
    };
    line(memH, "#ffb547"); line(gpuH, "#54e0a0"); line(cpuH, "#36d3ff");
  }

  async function poll() {
    try {
      const v: V = await (await fetch("/api/vitals")).json();
      const gpu = v.gpu?.util ?? 0;
      const vram = v.gpu?.mem_used != null && v.gpu?.mem_total != null
        ? `${Math.round(v.gpu.mem_used)}/${Math.round(v.gpu.mem_total)}MB` : "n/a";
      const temp = v.gpu?.temp != null ? `${Math.round(v.gpu.temp)}°C` : "—";
      read.innerHTML =
        `<b style="color:#36d3ff">CPU ${Math.round(v.cpu)}%</b> ` +
        `<span style="opacity:.6">(${v.cpu_cores}c, load ${v.load1})</span> &nbsp;|&nbsp; ` +
        `<b style="color:#54e0a0">GPU ${v.gpu?.util != null ? Math.round(v.gpu.util) + "%" : "n/a"}</b> ` +
        `<span style="opacity:.6">${vram} ${temp}</span> &nbsp;|&nbsp; ` +
        `<b style="color:#ffb547">RAM ${Math.round(v.mem_pct)}%</b> ` +
        `<span style="opacity:.6">(${v.mem_used_gb}/${v.mem_total_gb}GB)</span>`;
      // ④ system warning → fire the red alert (GPU overheat / VRAM full / CPU or RAM pegged)
      if ((v.gpu?.temp ?? 0) > 82 || v.cpu > 96 || v.mem_pct > 95 ||
          ((v.gpu?.mem_used ?? 0) / (v.gpu?.mem_total || 1)) > 0.94) {
        window.dispatchEvent(new Event("jarvis-warn"));
      }
      cpuH.push(v.cpu); gpuH.push(gpu); memH.push(v.mem_pct);
      if (cpuH.length > N) { cpuH.shift(); gpuH.shift(); memH.shift(); }
      drawGraph();
    } catch { /* server momentarily unreachable */ }
  }
  poll(); setInterval(poll, 1000);

  document.addEventListener("keydown", (e) => {
    if (e.key === "g" || e.key === "G") panel.style.display = panel.style.display === "none" ? "block" : "none";
  });
}
