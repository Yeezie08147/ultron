/**
 * UI sound cues (Web Audio, zero-latency) to mask the think delay:
 *  - blip()         : a soft "I heard you" chirp when the user finishes talking
 *  - thinkingStart(): a gentle processing hum while JARVIS thinks
 *  - thinkingStop() : fade the hum out
 * All synthesized locally, so there is no dead silence during the ~2.5s wait.
 */
export interface Cues {
  blip(): void;
  thinkingStart(): void;
  thinkingStop(): void;
}

export function createCues(ctx: AudioContext): Cues {
  let humGain: GainNode | null = null;
  let nodes: OscillatorNode[] = [];

  function wake() {
    if (ctx.state === "suspended") ctx.resume().catch(() => { /* */ });
  }

  function blip() {
    wake();
    const now = ctx.currentTime;
    const o = ctx.createOscillator();
    o.type = "triangle";
    o.frequency.setValueAtTime(620, now);
    o.frequency.exponentialRampToValueAtTime(940, now + 0.08);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, now);
    g.gain.exponentialRampToValueAtTime(0.13, now + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, now + 0.2);
    o.connect(g).connect(ctx.destination);
    o.start(now); o.stop(now + 0.22);
  }

  function thinkingStart() {
    if (humGain) return;
    wake();
    const now = ctx.currentTime;
    humGain = ctx.createGain();
    humGain.gain.setValueAtTime(0.0001, now);
    humGain.gain.linearRampToValueAtTime(0.03, now + 0.18); // soft

    const filt = ctx.createBiquadFilter();
    filt.type = "lowpass"; filt.frequency.value = 560;
    humGain.connect(filt).connect(ctx.destination);

    // soft two-note chord
    for (const f of [196, 247]) {
      const o = ctx.createOscillator();
      o.type = "sine"; o.frequency.value = f;
      o.connect(humGain); o.start(); nodes.push(o);
    }
    // slow tremolo so it shimmers instead of droning
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 4.5;
    const lfoGain = ctx.createGain(); lfoGain.gain.value = 0.018;
    lfo.connect(lfoGain).connect(humGain.gain);
    lfo.start(); nodes.push(lfo);
  }

  function thinkingStop() {
    if (!humGain) return;
    const now = ctx.currentTime;
    const g = humGain, ns = nodes;
    humGain = null; nodes = [];
    g.gain.cancelScheduledValues(now);
    g.gain.setValueAtTime(g.gain.value, now);
    g.gain.linearRampToValueAtTime(0.0001, now + 0.25);
    setTimeout(() => { for (const n of ns) { try { n.stop(); } catch { /* */ } } }, 320);
  }

  return { blip, thinkingStart, thinkingStop };
}
