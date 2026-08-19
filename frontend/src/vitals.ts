/**
 * Mini arc-reactor vitals widget — a small corner HUD on the main JARVIS
 * screen. Concentric CPU/MEM/GPU rings + readouts, styled to match the orb
 * HUD. Polls /api/vitals.
 */
export function initVitals(canvas: HTMLCanvasElement, readoutEl: HTMLElement, analyser?: AnalyserNode) {
  const ctx = canvas.getContext("2d")!;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const SIZE = 132;
  canvas.width = SIZE * dpr;
  canvas.height = SIZE * dpr;
  canvas.style.width = SIZE + "px";
  canvas.style.height = SIZE + "px";
  ctx.scale(dpr, dpr);

  const rings = [
    { key: "gpu", r: 0.42, val: 0, target: 0 },
    { key: "mem", r: 0.31, val: 0, target: 0 },
    { key: "cpu", r: 0.20, val: 0, target: 0 },
  ];
  const hue = (v: number) => 50 - v * 40; // gold (50) -> red (10) as load climbs
  const col = (v: number, a = 1) => `hsla(${hue(v)},95%,58%,${a})`;

  const freq = analyser ? new Uint8Array(analyser.frequencyBinCount) : null;
  let amp = 0;

  let t = 0;
  function draw() {
    t += 0.016;
    ctx.clearRect(0, 0, SIZE, SIZE);
    const c = SIZE / 2, R = SIZE / 2;

    // react to JARVIS's voice (same analyser the orb uses): pulse + breathe
    let target = 0;
    if (analyser && freq) {
      analyser.getByteFrequencyData(freq);
      let s = 0; for (let i = 0; i < freq.length; i++) s += freq[i];
      target = Math.min(1, (s / freq.length) / 90);
    }
    amp += (target - amp) * 0.3;
    const breathe = 1 + 0.018 * Math.sin(t * 1.6) + amp * 0.08;
    ctx.save();
    ctx.translate(c, c); ctx.scale(breathe, breathe); ctx.translate(-c, -c);

    // rotating tick ring
    ctx.save(); ctx.translate(c, c); ctx.rotate(t * 0.12);
    for (let i = 0; i < 36; i++) {
      const a = (i / 36) * Math.PI * 2;
      const big = i % 9 === 0;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * R * 0.49, Math.sin(a) * R * 0.49);
      ctx.lineTo(Math.cos(a) * R * (big ? 0.43 : 0.46), Math.sin(a) * R * (big ? 0.43 : 0.46));
      ctx.strokeStyle = big ? "rgba(255,196,46,.55)" : "rgba(255,196,46,.22)";
      ctx.lineWidth = 1; ctx.stroke();
    }
    ctx.restore();

    for (const ring of rings) {
      ring.val += (ring.target - ring.val) * 0.08;
      const rad = R * ring.r;
      ctx.beginPath(); ctx.arc(c, c, rad, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(120,90,20,.35)"; ctx.lineWidth = R * 0.07; ctx.stroke();
      const s = -Math.PI / 2;
      ctx.beginPath(); ctx.arc(c, c, rad, s, s + ring.val * Math.PI * 2);
      ctx.strokeStyle = col(ring.val); ctx.lineWidth = R * 0.07; ctx.lineCap = "round";
      ctx.shadowColor = col(ring.val, 0.85); ctx.shadowBlur = 7; ctx.stroke(); ctx.shadowBlur = 0;
    }

    // pulsing core
    const overall = (rings[0].val + rings[1].val + rings[2].val) / 3;
    const pr = R * 0.15 * (0.9 + 0.1 * Math.sin(t * 2.2) + amp * 0.85);
    const g = ctx.createRadialGradient(c, c, 0, c, c, pr);
    g.addColorStop(0, "#fffbe6");
    g.addColorStop(0.5, col(overall, 1));
    g.addColorStop(1, "rgba(120,80,10,0)");
    ctx.beginPath(); ctx.arc(c, c, pr, 0, Math.PI * 2);
    ctx.fillStyle = g; ctx.shadowColor = col(overall, 0.85); ctx.shadowBlur = 14 + amp * 28;
    ctx.fill(); ctx.shadowBlur = 0;

    ctx.restore();
    requestAnimationFrame(draw);
  }
  draw();

  async function poll() {
    try {
      const v = await (await fetch("/api/vitals")).json();
      const gpu = v.gpu || {};
      rings[0].target = Math.min(1, (gpu.util || 0) / 100);
      rings[1].target = Math.min(1, (v.mem_pct || 0) / 100);
      rings[2].target = Math.min(1, (v.cpu || 0) / 100);
      readoutEl.innerHTML =
        `<span class="vk">CPU</span> <span class="vv">${(v.cpu || 0).toFixed(0)}%</span>` +
        `<span class="vk">MEM</span> <span class="vv">${v.mem_used_gb}/${v.mem_total_gb}G</span>` +
        (gpu.util == null
          ? `<span class="vk">GPU</span> <span class="vv">n/a</span>`
          : `<span class="vk">GPU</span> <span class="vv">${gpu.util.toFixed(0)}% ${gpu.temp.toFixed(0)}°</span>`);
    } catch { /* keep last */ }
  }
  poll();
  setInterval(poll, 1500);
}
