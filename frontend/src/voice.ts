/**
 * Voice input (Web Speech API) and audio output (AudioContext) for JARVIS.
 */

// ---------------------------------------------------------------------------
// Speech Recognition
// ---------------------------------------------------------------------------

export interface VoiceInput {
  start(): void;
  stop(): void;
  pause(): void;
  resume(): void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const webkitSpeechRecognition: any;

export function createVoiceInput(
  onTranscript: (text: string) => void,
  onError: (msg: string) => void
): VoiceInput {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const SR = (window as any).SpeechRecognition || (typeof webkitSpeechRecognition !== "undefined" ? webkitSpeechRecognition : null);
  if (!SR) {
    onError("Speech recognition not supported in this browser");
    return { start() {}, stop() {}, pause() {}, resume() {} };
  }

  const recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  let shouldListen = false;
  let paused = false;

  recognition.onresult = (event: any) => {
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) {
        const text = event.results[i][0].transcript.trim();
        if (text) onTranscript(text);
      }
    }
  };

  recognition.onend = () => {
    if (shouldListen && !paused) {
      try {
        recognition.start();
      } catch {
        // Already started
      }
    }
  };

  recognition.onerror = (event: any) => {
    if (event.error === "not-allowed") {
      onError("Microphone access denied. Please allow microphone access.");
      shouldListen = false;
    } else if (event.error === "no-speech") {
      // Normal, just restart
    } else if (event.error === "aborted") {
      // Expected during pause
    } else {
      console.warn("[voice] recognition error:", event.error);
    }
  };

  return {
    start() {
      shouldListen = true;
      paused = false;
      try {
        recognition.start();
      } catch {
        // Already started
      }
    },
    stop() {
      shouldListen = false;
      paused = false;
      recognition.stop();
    },
    pause() {
      paused = true;
      recognition.stop();
    },
    resume() {
      paused = false;
      if (shouldListen) {
        try {
          recognition.start();
        } catch {
          // Already started
        }
      }
    },
  };
}

// ---------------------------------------------------------------------------
// Local STT capture — Silero VAD (in-browser) endpoints each utterance, then we
// ship the captured audio to the server as raw 16 kHz mono Int16 PCM for local
// Whisper transcription. This replaces the Web Speech API (no cutoff, proper
// endpointing, no cloud). One utterance == one binary WebSocket frame.
//
// AUDIO CONTRACT (must match server.py voice_handler): raw PCM, 16000 Hz, mono,
// signed 16-bit little-endian. No WAV header. Silero's onSpeechEnd already hands
// us Float32 @16 kHz, so we only need Float32 -> Int16.
// ---------------------------------------------------------------------------

import { MicVAD as SileroMicVAD } from "@ricky0123/vad-web";

export interface LocalSTT {
  start(): Promise<void>;   // request mic + start VAD
  destroy(): Promise<void>;
  // Gate normal queries (set true while JARVIS speaks). VAD keeps running so we
  // can still detect a real barge-in via onSpeechStart/onBargeIn.
  setGated(gated: boolean): void;
  isReady(): boolean;
}

function float32ToInt16PCM(f32: Float32Array): ArrayBuffer {
  const out = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const s = Math.max(-1, Math.min(1, f32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out.buffer;
}

export function createLocalSTT(opts: {
  // Fired with the encoded utterance (16 kHz mono Int16 PCM) when NOT gated.
  onUtterance: (pcm: ArrayBuffer) => void;
  // Fired when the user starts speaking while gated (i.e. a barge-in candidate).
  onBargeIn: () => void;
  onError: (msg: string) => void;
}): LocalSTT {
  let vad: SileroMicVAD | null = null;
  let gated = false;
  let ready = false;
  // Minimum captured samples (16 kHz) to count as a real utterance — Silero's
  // minSpeechFrames already filters most misfires, this is a belt-and-braces.
  const MIN_SAMPLES = 16000 * 0.3; // 0.3s

  return {
    async start() {
      if (vad) return;
      try {
        vad = await SileroMicVAD.new({
          // Serve Silero model + onnxruntime wasm locally (no CDN, fully offline).
          baseAssetPath: window.location.origin + "/vad/",
          onnxWASMBasePath: window.location.origin + "/vad/",
          model: "v5",
          // Endpointing tuned to avoid cutting the user off mid-thought while
          // still ending promptly when they actually stop.
          positiveSpeechThreshold: 0.5,
          negativeSpeechThreshold: 0.35,
          redemptionMs: 800,        // balanced: lets you finish, replies sooner
                                    // (was 560 — too eager, cut users off mid-sentence)
          minSpeechMs: 130,         // ignore blips shorter than this
          preSpeechPadMs: 320,      // keep more of the sentence's leading audio
          getStream: () =>
            navigator.mediaDevices.getUserMedia({
              audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1,
              },
            }),
          onSpeechStart: () => {
            // While JARVIS is speaking, a genuine speech-start is a barge-in.
            if (gated) opts.onBargeIn();
          },
          onSpeechEnd: (audio: Float32Array) => {
            // Drop the captured turn entirely if we're gated — JARVIS's own
            // voice (echo) or chatter while he speaks must never become a query.
            if (gated) return;
            if (audio.length < MIN_SAMPLES) return;
            opts.onUtterance(float32ToInt16PCM(audio));
          },
          onVADMisfire: () => {
            /* too short — ignore */
          },
        });
        await vad.start();
        ready = true;
      } catch (err) {
        console.error("[stt] VAD init failed:", err);
        const coi = (self as any).crossOriginIsolated;
        const sab = typeof SharedArrayBuffer !== "undefined";
        const msg = (err as any)?.message || String(err);
        opts.onError(`VAD fail: ${msg} [coi=${coi} sab=${sab}]`);
      }
    },
    async destroy() {
      ready = false;
      try {
        await vad?.destroy();
      } catch {
        /* ignore */
      }
      vad = null;
    },
    setGated(g: boolean) {
      gated = g;
    },
    isReady() {
      return ready;
    },
  };
}

// ---------------------------------------------------------------------------
// Mic VAD — detects the user speaking so we can barge-in (interrupt JARVIS).
// Uses a SEPARATE echo-cancelled mic stream so it doesn't trigger on JARVIS's
// own voice coming out of the speakers.
// (Retained for the legacy Web Speech path; the local-STT path uses the Silero
// VAD above for both capture AND barge-in.)
// ---------------------------------------------------------------------------

export interface MicVAD {
  enable(): void;   // start watching for the user's voice (call while JARVIS speaks)
  disable(): void;  // stop watching
}

export function createMicVAD(onSpeechStart: () => void, getOutputLevel?: () => number): MicVAD {
  let ctx: AudioContext | null = null;
  let stream: MediaStream | null = null;
  let analyser: AnalyserNode | null = null;
  let raf = 0;
  let enabled = false;
  let hot = 0;

  const THRESHOLD = 0.085; // RMS energy floor for real speech
  const FRAMES = 6;        // sustained frames (~100ms) before firing

  async function ensure() {
    if (ctx) return;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      ctx = new AudioContext();
      const src = ctx.createMediaStreamSource(stream);
      analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      src.connect(analyser);
      const buf = new Uint8Array(analyser.fftSize);
      const loop = () => {
        if (analyser) {
          analyser.getByteTimeDomainData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i++) {
            const v = (buf[i] - 128) / 128;
            sum += v * v;
          }
          const rms = Math.sqrt(sum / buf.length);
          // Only treat as the USER speaking if the mic clearly exceeds JARVIS's
          // own output level — so its voice from an external speaker (echo)
          // never trips the barge-in, but you talking over it still does.
          const out = getOutputLevel ? getOutputLevel() : 0;
          if (enabled && rms > THRESHOLD && rms > out * 1.15 + 0.03) {
            if (++hot >= FRAMES) { hot = 0; onSpeechStart(); }
          } else {
            hot = 0;
          }
        }
        raf = requestAnimationFrame(loop);
      };
      loop();
    } catch (err) {
      console.warn("[vad] mic unavailable:", err);
    }
  }

  return {
    enable() { enabled = true; hot = 0; ensure(); },
    disable() { enabled = false; hot = 0; },
  };
}

// ---------------------------------------------------------------------------
// Audio Player
// ---------------------------------------------------------------------------

export interface AudioPlayer {
  enqueue(base64: string): Promise<void>;
  stop(): void;
  getAnalyser(): AnalyserNode;
  onFinished(cb: () => void): void;
}

export function createAudioPlayer(): AudioPlayer {
  const audioCtx = new AudioContext();
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = 0.8;
  analyser.connect(audioCtx.destination);

  const queue: AudioBuffer[] = [];
  let isPlaying = false;
  let currentSource: AudioBufferSourceNode | null = null;
  let finishedCallback: (() => void) | null = null;

  function playNext() {
    if (queue.length === 0) {
      isPlaying = false;
      currentSource = null;
      finishedCallback?.();
      return;
    }

    isPlaying = true;
    const buffer = queue.shift()!;
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    currentSource = source;

    source.onended = () => {
      if (currentSource === source) {
        playNext();
      }
    };

    source.start();
  }

  return {
    async enqueue(base64: string) {
      // Resume audio context (browser autoplay policy)
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }

      try {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
          bytes[i] = binary.charCodeAt(i);
        }
        const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer.slice(0));
        queue.push(audioBuffer);
        if (!isPlaying) playNext();
      } catch (err) {
        console.error("[audio] decode error:", err);
        // Skip bad audio, continue
        if (!isPlaying && queue.length > 0) playNext();
      }
    },

    stop() {
      queue.length = 0;
      if (currentSource) {
        try {
          currentSource.stop();
        } catch {
          // Already stopped
        }
        currentSource = null;
      }
      isPlaying = false;
    },

    getAnalyser() {
      return analyser;
    },

    onFinished(cb: () => void) {
      finishedCallback = cb;
    },
  };
}
