/**
 * JARVIS — Multi-mode particle visualization.
 *
 * Floating particles with line connections between nearby ones.
 * Lines fade in/out based on state. Transition tumble on state change.
 * Speaking pulls particles closer for denser connections.
 */

import * as THREE from "three";

export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "alert";

export interface Orb {
  setState(s: OrbState): void;
  setAnalyser(a: AnalyserNode | null): void;
  getColor(): [number, number, number];   // current smoothly-lerped colour (0-255)
  destroy(): void;
}

export function createOrb(canvas: HTMLCanvasElement): Orb {
  let destroyed = false;
  const N = 2000;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x080402, 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 1000);
  camera.position.z = 100;

  // ── Particles ──
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(N * 3);
  const vel = new Float32Array(N * 3);
  const phase = new Float32Array(N);

  for (let i = 0; i < N; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = Math.pow(Math.random(), 0.5) * 25;
    pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    pos[i * 3 + 2] = r * Math.cos(phi);
    phase[i] = Math.random() * 1000;
  }

  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));

  const mat = new THREE.PointsMaterial({
    color: 0xFF7800, size: 0.4, transparent: true, opacity: 0.6,
    sizeAttenuation: true, blending: THREE.AdditiveBlending, depthWrite: false,
  });

  const points = new THREE.Points(geo, mat);
  scene.add(points);

  // ── Glow layer (Group 2 / item 3) ──
  // A second pass over the SAME particle geometry, drawn much larger and very
  // faint with additive blending. Each particle gets a soft halo so the cloud
  // reads as luminous rather than as hard pinpricks — barely-there on purpose.
  // Shares `geo`, so it costs one extra draw call and zero extra simulation.
  const glowMat = new THREE.PointsMaterial({
    color: 0xFF7800, size: 2.4, transparent: true, opacity: 0.05,
    sizeAttenuation: true, blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const glowPoints = new THREE.Points(geo, glowMat);
  scene.add(glowPoints);

  // ── Halo (Group 2 / item 4) ──
  // One large additive sprite behind the cloud — a faint radial wash that gives
  // the orb an ambient bloom without any post-processing. White gradient tinted
  // by the sprite colour (additive), so it follows the live state colour.
  const haloCanvas = document.createElement("canvas");
  haloCanvas.width = haloCanvas.height = 256;
  const hctx = haloCanvas.getContext("2d")!;
  const grad = hctx.createRadialGradient(128, 128, 0, 128, 128, 128);
  grad.addColorStop(0.0, "rgba(255,255,255,1.0)");
  grad.addColorStop(0.25, "rgba(255,255,255,0.55)");
  grad.addColorStop(0.55, "rgba(255,255,255,0.16)");
  grad.addColorStop(1.0, "rgba(255,255,255,0.0)");
  hctx.fillStyle = grad;
  hctx.fillRect(0, 0, 256, 256);
  const haloTex = new THREE.CanvasTexture(haloCanvas);
  const haloMat = new THREE.SpriteMaterial({
    map: haloTex, color: 0xFF7800, transparent: true, opacity: 0.12,
    blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false,
  });
  const halo = new THREE.Sprite(haloMat);
  halo.scale.set(150, 150, 1);
  halo.position.z = -20;            // sit behind the particle cloud
  scene.add(halo);

  // ── Core hint (Phase 2 / item 17) ──
  // A small, faint additive sprite at the cloud's centre so the orb reads as
  // having a "heart" — a slightly brighter concentration of light. Reuses the
  // halo's radial texture; sits just in FRONT of the cloud and follows the live
  // state colour (unlike the trailing halo). Kept low-opacity on purpose.
  const coreMat = new THREE.SpriteMaterial({
    map: haloTex, color: 0xFF7800, transparent: true, opacity: 0.16,
    blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false,
  });
  const core = new THREE.Sprite(coreMat);
  core.scale.set(22, 22, 1);
  scene.add(core);

  // ── Connection lines ──
  const MAX_LINES = 8000;
  const linePos = new Float32Array(MAX_LINES * 6);
  const lineGeo = new THREE.BufferGeometry();
  lineGeo.setAttribute("position", new THREE.BufferAttribute(linePos, 3));
  lineGeo.setDrawRange(0, 0);

  const lineMat = new THREE.LineBasicMaterial({
    color: 0xFF7800, transparent: true, opacity: 0.0,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });

  const lines = new THREE.LineSegments(lineGeo, lineMat);
  scene.add(lines);

  // ── Electrons — bright dots that travel along connections ──
  const MAX_ELECTRONS = 200;
  const electronGeo = new THREE.BufferGeometry();
  const electronPos = new Float32Array(MAX_ELECTRONS * 3);
  electronGeo.setAttribute("position", new THREE.BufferAttribute(electronPos, 3));
  electronGeo.setDrawRange(0, 0);

  const electronMat = new THREE.PointsMaterial({
    color: 0xffffff, size: 0.8, transparent: true, opacity: 1.0,
    sizeAttenuation: true, blending: THREE.AdditiveBlending, depthWrite: false,
  });

  const electrons = new THREE.Points(electronGeo, electronMat);
  scene.add(electrons);

  // Each electron: start point, end point, progress (0-1), speed
  interface Electron { sx: number; sy: number; sz: number; ex: number; ey: number; ez: number; t: number; speed: number; }
  const activeElectrons: Electron[] = [];
  let electronSpawnRate = 0;
  let targetElectronRate = 0;
  let lastElectronSpawn = 0; // timestamp of last spawn

  // Store active connections for electron spawning
  let activeConnections: { x1: number; y1: number; z1: number; x2: number; y2: number; z2: number }[] = [];

  // ── State ──
  let state: OrbState = "idle";
  let targetRadius = 25, currentRadius = 25;
  let targetSpeed = 0.3, currentSpeed = 0.3;
  let targetBright = 0.6, currentBright = 0.6;
  let targetSize = 0.4, currentSize = 0.4;
  let lineAmount = 0, targetLineAmount = 0;
  let lineDistance = 8;

  // Transition tumble
  let spinX = 0, spinY = 0, spinZ = 0;
  let transitionEnergy = 0;
  let lastState: OrbState = "idle";

  // (20) settle-after-speak: timestamp of the most recent speaking→other change,
  // used to drive a quick damped overshoot so the orb doesn't snap back to idle.
  let settleStart = -100;

  // (9) idle colour drift: reused HSL scratch object so we don't allocate per frame.
  const _hsl = { h: 0, s: 0, l: 0 };

  // Depth Z
  let cloudZ = 0, cloudZVel = 0;

  // ── Audio ──
  let analyser: AnalyserNode | null = null;
  let freqData = new Uint8Array(64);
  let bass = 0, mid = 0;

  // Phase 1 (life & motion): smoothed voice envelope drives the speaking swell;
  // a slow breath factor gives the whole orb a calm idle expand/contract.
  let voiceEnv = 0;

  const clock = new THREE.Clock();

  // ── Frame throttling ──
  // At idle nothing meaningful is happening, so we don't need 60fps — that just
  // pegs a CPU core (and the dGPU) for a barely-perceptible drift animation.
  // Cap idle to ~22fps; run full rate while listening/thinking/speaking so the
  // audio-reactive motion stays smooth. We still drive the loop via rAF (so the
  // browser throttles us when the tab is hidden) but skip the heavy per-frame
  // work until enough wall-time has elapsed for the current state's budget.
  const IDLE_FPS = 22;
  const IDLE_FRAME_MS = 1000 / IDLE_FPS;
  let lastFrameMs = 0;

  function animate() {
    if (destroyed) return;
    requestAnimationFrame(animate);

    // Throttle: at idle, only do real work ~22x/sec. Full rate otherwise.
    if (state === "idle") {
      const nowMs = performance.now();
      if (nowMs - lastFrameMs < IDLE_FRAME_MS) return;
      lastFrameMs = nowMs;
    } else {
      lastFrameMs = performance.now();
    }

    const t = clock.getElapsedTime();

    switch (state) {
      case "idle":
        targetRadius = 28; targetSpeed = 0.2; targetBright = 0.5; targetSize = 0.35;
        targetLineAmount = 0.15; targetElectronRate = 0; break;
      case "listening":
        targetRadius = 22; targetSpeed = 0.3; targetBright = 0.65; targetSize = 0.4;
        targetLineAmount = 0.3; targetElectronRate = 0.02; break;
      case "thinking":
        targetRadius = 20; targetSpeed = 1.2; targetBright = 0.9; targetSize = 0.45;
        targetLineAmount = 0.6; targetElectronRate = 0.2; break;
      case "speaking":
        targetRadius = 15; targetSpeed = 0.6; targetBright = 1.0; targetSize = 0.5;
        targetLineAmount = 1.0; targetElectronRate = 0.6; break;
      case "alert":
        targetRadius = 30; targetSpeed = 2.0; targetBright = 1.0; targetSize = 0.6;
        targetLineAmount = 1.0; targetElectronRate = 1.0; break;
    }

    currentRadius += (targetRadius - currentRadius) * 0.02;
    currentSpeed += (targetSpeed - currentSpeed) * 0.02;
    currentBright += (targetBright - currentBright) * 0.02;
    currentSize += (targetSize - currentSize) * 0.02;
    lineAmount += (targetLineAmount - lineAmount) * 0.02;
    electronSpawnRate += (targetElectronRate - electronSpawnRate) * 0.02;

    // Transition energy
    if (state !== lastState) {
      transitionEnergy = 1.0;
      // (20) settle-after-speak: trigger the damped overshoot when leaving speaking.
      if (lastState === "speaking") settleStart = t;
      lastState = state;
    }
    transitionEnergy *= 0.985;
    if (transitionEnergy > 0.05) {
      spinX += transitionEnergy * 0.012 * Math.sin(t * 1.7);
      spinY += transitionEnergy * 0.015;
      spinZ += transitionEnergy * 0.008 * Math.cos(t * 1.3);
    }

    // Audio
    bass = 0; mid = 0;
    if (analyser) {
      analyser.getByteFrequencyData(freqData);
      let bSum = 0, mSum = 0;
      for (let i = 0; i < 8; i++) bSum += freqData[i];
      for (let i = 8; i < 24; i++) mSum += freqData[i];
      bass = bSum / (8 * 255); mid = mSum / (16 * 255);
    }

    // Depth Z breathing
    let zTarget = Math.sin(t * 0.12) * 8;
    if (state === "thinking") zTarget = Math.sin(t * 0.3) * 15 + Math.sin(t * 0.9) * 6;
    else if (state === "speaking") zTarget = Math.sin(t * 0.15) * 6 - bass * 10;
    cloudZVel += (zTarget - cloudZ) * 0.008;
    cloudZVel *= 0.94;
    cloudZ += cloudZVel;

    points.rotation.x = spinX; points.rotation.y = spinY; points.rotation.z = spinZ;
    points.position.z = cloudZ;
    lines.rotation.x = spinX; lines.rotation.y = spinY; lines.rotation.z = spinZ;
    lines.position.z = cloudZ;
    // Glow shares the particle transform (same geometry, soft oversized halo).
    glowPoints.rotation.x = spinX; glowPoints.rotation.y = spinY; glowPoints.rotation.z = spinZ;
    glowPoints.position.z = cloudZ;

    // ── Phase 1: breathing + voice swell ──
    // (2) Idle "breathing": a slow, calm in/out, strongest at idle, present-but-
    //     subtle in other states so the orb never looks frozen.
    // (1) Expressive voice pulse: while speaking, the whole cloud swells with
    //     JARVIS's voice envelope; while listening it settles gently inward.
    const amp = Math.max(bass, mid * 0.85);
    voiceEnv += (amp - voiceEnv) * 0.18;            // fast attack/decay — tracks speech
    const breathAmt = state === "idle" ? 0.045 : 0.02;
    const breath = Math.sin(t * 0.8) * breathAmt;   // ~8s calm cycle
    let orbScale = 1 + breath;
    if (state === "speaking") orbScale += voiceEnv * 0.13;   // swell with the voice
    else if (state === "listening") orbScale -= 0.03;        // attentive, drawn inward
    // (20) settle-after-speak: a quick swell-and-settle damped sine after speaking.
    const se = t - settleStart;
    if (se >= 0 && se < 2.5) orbScale += Math.sin(se * 6) * Math.exp(-se * 2.5) * 0.05;
    // Apply uniformly so particles, glow, lines and electrons stay aligned.
    points.scale.setScalar(orbScale);
    glowPoints.scale.setScalar(orbScale);
    lines.scale.setScalar(orbScale);
    electrons.scale.setScalar(orbScale);

    // ── Update particles ──
    const p = geo.getAttribute("position") as THREE.BufferAttribute;
    const a = p.array as Float32Array;

    for (let i = 0; i < N; i++) {
      const i3 = i * 3;
      let x = a[i3], y = a[i3 + 1], z = a[i3 + 2];
      const px = phase[i];

      vel[i3] += Math.sin(t * 0.05 + px) * 0.001 * currentSpeed;
      vel[i3 + 1] += Math.cos(t * 0.06 + px * 1.3) * 0.001 * currentSpeed;
      vel[i3 + 2] += Math.sin(t * 0.055 + px * 0.7) * 0.001 * currentSpeed;
      vel[i3] += Math.sin(t * 0.02 + px * 2.1 + y * 0.1) * 0.0008 * currentSpeed;
      vel[i3 + 1] += Math.cos(t * 0.025 + px * 1.7 + z * 0.1) * 0.0008 * currentSpeed;
      vel[i3 + 2] += Math.sin(t * 0.022 + px * 0.9 + x * 0.1) * 0.0008 * currentSpeed;

      const dist = Math.sqrt(x * x + y * y + z * z) || 0.01;
      const pull = Math.max(0, dist - currentRadius) * 0.002 + 0.0003;
      vel[i3] -= (x / dist) * pull;
      vel[i3 + 1] -= (y / dist) * pull;
      vel[i3 + 2] -= (z / dist) * pull;

      if (bass > 0.05) {
        vel[i3] += (x / dist) * bass * 0.02;
        vel[i3 + 1] += (y / dist) * bass * 0.02;
        vel[i3 + 2] += (z / dist) * bass * 0.02;
      }
      if (state === "speaking" && mid > 0.1) {
        const pulse = Math.sin(t * 8 + px);
        vel[i3] += (x / dist) * mid * 0.012 * pulse;
        vel[i3 + 1] += (y / dist) * mid * 0.012 * pulse;
      }

      vel[i3] *= 0.992; vel[i3 + 1] *= 0.992; vel[i3 + 2] *= 0.992;
      a[i3] += vel[i3]; a[i3 + 1] += vel[i3 + 1]; a[i3 + 2] += vel[i3 + 2];
    }
    p.needsUpdate = true;

    // ── Update lines ──
    if (lineAmount > 0.01) {
      const lp = lineGeo.getAttribute("position") as THREE.BufferAttribute;
      const la = lp.array as Float32Array;
      let lineCount = 0;
      const maxDist = lineDistance * (1 + bass * 0.5);
      const maxDistSq = maxDist * maxDist;
      const step = Math.max(1, Math.floor(N / 600));

      for (let i = 0; i < N && lineCount < MAX_LINES; i += step) {
        const i3 = i * 3;
        const x1 = a[i3], y1 = a[i3 + 1], z1 = a[i3 + 2];
        for (let j = i + step; j < N && lineCount < MAX_LINES; j += step) {
          const j3 = j * 3;
          const dx = a[j3] - x1, dy = a[j3 + 1] - y1, dz = a[j3 + 2] - z1;
          if (dx * dx + dy * dy + dz * dz < maxDistSq) {
            const idx = lineCount * 6;
            la[idx] = x1; la[idx+1] = y1; la[idx+2] = z1;
            la[idx+3] = a[j3]; la[idx+4] = a[j3+1]; la[idx+5] = a[j3+2];
            lineCount++;
          }
        }
      }
      lineGeo.setDrawRange(0, lineCount * 2);
      lp.needsUpdate = true;
      lineMat.opacity = lineAmount * 0.12;

      // Store connections for electron spawning
      activeConnections = [];
      for (let c = 0; c < Math.min(lineCount, 500); c++) {
        const ci = c * 6;
        activeConnections.push({
          x1: la[ci], y1: la[ci+1], z1: la[ci+2],
          x2: la[ci+3], y2: la[ci+4], z2: la[ci+5],
        });
      }
    } else {
      lineGeo.setDrawRange(0, 0);
      activeConnections = [];
    }

    // ── Update electrons — only during thinking ──
    // One fires off every ~1 second, max 3 alive, takes 2-4s to travel
    if (activeConnections.length > 0 && electronSpawnRate > 0.005) {
      if (activeElectrons.length < 3 && (t - lastElectronSpawn) > 1.0) {
        const conn = activeConnections[Math.floor(Math.random() * activeConnections.length)];
        // speed: 1/fps * speed = progress per frame. At 60fps, speed 0.005 = 200 frames = 3.3s
        activeElectrons.push({
          sx: conn.x1, sy: conn.y1, sz: conn.z1,
          ex: conn.x2, ey: conn.y2, ez: conn.z2,
          t: 0,
          speed: 0.003 + Math.random() * 0.003, // 2-4 seconds to travel
        });
        lastElectronSpawn = t;
      }
    }

    // Update electron positions
    const ep = electronGeo.getAttribute("position") as THREE.BufferAttribute;
    const ea = ep.array as Float32Array;
    let aliveCount = 0;

    for (let e = activeElectrons.length - 1; e >= 0; e--) {
      const el = activeElectrons[e];
      el.t += el.speed;
      if (el.t >= 1) {
        activeElectrons.splice(e, 1);
        continue;
      }
      const ei = aliveCount * 3;
      ea[ei] = el.sx + (el.ex - el.sx) * el.t;
      ea[ei + 1] = el.sy + (el.ey - el.sy) * el.t;
      ea[ei + 2] = el.sz + (el.ez - el.sz) * el.t;
      aliveCount++;
    }

    electronGeo.setDrawRange(0, aliveCount);
    ep.needsUpdate = true;

    // Electrons follow the same rotation/position as the main group
    electrons.rotation.x = spinX; electrons.rotation.y = spinY; electrons.rotation.z = spinZ;
    electrons.position.z = cloudZ;

    mat.opacity = currentBright + bass * 0.08;
    mat.size = currentSize + bass * 0.05;

    // Glow tracks the particles: scaled-up size, low opacity that lifts gently
    // with brightness + audio. Denser states (thinking/speaking) glow a touch more.
    glowMat.size = (currentSize + bass * 0.05) * 5.0;
    glowMat.opacity = 0.022 + (currentBright - 0.5) * 0.035 + bass * 0.03;
    // Halo: faint ambient wash that breathes with brightness and bass.
    // (8) halo voice-pulse: brighten gently with JARVIS's voice while speaking.
    haloMat.opacity = 0.05 + (currentBright - 0.5) * 0.06 + bass * 0.04
      + (state === "speaking" ? voiceEnv * 0.10 : 0);
    halo.position.z = cloudZ - 20;
    // (8) and let the halo swell a hair with the voice while speaking.
    const haloSwell = 150 * (1 + (state === "speaking" ? voiceEnv * 0.04 : 0));
    halo.scale.set(haloSwell, haloSwell, 1);

    // (17) core hint: sits just in front of the cloud, breathes/voices with orbScale.
    core.position.z = cloudZ + 2;
    core.scale.setScalar(22 * orbScale);
    coreMat.opacity = 0.16 + (state === "speaking" ? voiceEnv * 0.08 : 0);

    // per-state colour — distinct hues, crisper transitions
    const stateColor =
      state === "listening" ? 0xFFAA1E :   // green-teal — attentive
      state === "thinking"  ? 0xDC3C14 :   // gold — processing
      state === "speaking"  ? 0xFF8C32 :   // royal blue — active
      state === "alert"     ? 0xC81E1E :   // red — error / alert
                              0xFF7800;     // bright cyan — idle
    const sc = new THREE.Color(stateColor);
    // (9) idle colour drift: nudge the cyan a hair warmer/cooler on a slow sine so
    // idle never looks flat. Magnitude ≈0.015 hue — barely perceptible.
    if (state === "idle") {
      sc.getHSL(_hsl);
      let h = _hsl.h + Math.sin(t * 0.15) * 0.015;
      h = ((h % 1) + 1) % 1;               // wrap into [0,1)
      sc.setHSL(h, _hsl.s, _hsl.l);
    }
    mat.color.lerp(sc, 0.07);              // smooth — not mushy (0.04), not abrupt (0.12)
    lineMat.color.lerp(sc, 0.07);
    glowMat.color.lerp(sc, 0.07);
    coreMat.color.lerp(sc, 0.07);          // (17) core follows the particles
    // (22) colour afterglow: halo lerps slower than the particles, so the OLD
    // colour lingers briefly in the wash while the cloud adopts the new one.
    haloMat.color.lerp(sc, 0.025);

    camera.position.x = Math.sin(t * 0.02) * 5;
    camera.position.y = Math.cos(t * 0.03) * 3;
    camera.lookAt(0, 0, cloudZ * 0.2);

    renderer.render(scene, camera);
  }

  function onResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }

  window.addEventListener("resize", onResize);
  animate();

  return {
    setState(s: OrbState) { state = s; },
    setAnalyser(a: AnalyserNode | null) {
      analyser = a;
      if (a) freqData = new Uint8Array(a.frequencyBinCount);
    },
    getColor() {
      return [Math.round(mat.color.r * 255), Math.round(mat.color.g * 255), Math.round(mat.color.b * 255)] as [number, number, number];
    },
    destroy() {
      destroyed = true;
      window.removeEventListener("resize", onResize);
      haloTex.dispose();
      renderer.dispose();
    },
  };
}
