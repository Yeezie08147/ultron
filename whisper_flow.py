"""
whisper_flow.py — ULTRON Whisper Flow Audio Transcription Engine.

Capabilities:
- Streaming & batch audio transcription using Whisper models / faster-whisper / WebRTC flow
- Seamless audio buffer processing for local voice interactions
"""

import io
import os
import wave
import tempfile
import logging
from typing import Dict, Any, Optional

log = logging.getLogger("ultron.whisperflow")

_whisper_model = None


def load_whisper_flow():
    """Lazily load local Whisper pipeline if available."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            _whisper_model = whisper.load_model("base")
            log.info("Whisper model loaded successfully.")
        except Exception:
            try:
                from faster_whisper import WhisperModel
                _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
                log.info("Faster-Whisper model loaded successfully.")
            except Exception as e:
                log.warning(f"Local Whisper model not found (fallback to standard speech pipeline): {e}")
    return _whisper_model


def transcribe_audio_bytes(audio_bytes: bytes) -> Dict[str, Any]:
    """Transcribe raw audio bytes using Whisper flow."""
    model = load_whisper_flow()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_bytes)
        temp_wav = f.name

    try:
        if model:
            if hasattr(model, "transcribe"):
                # OpenAI Whisper or Faster-Whisper
                result = model.transcribe(temp_wav)
                if isinstance(result, tuple):
                    # Faster-whisper returns (segments, info)
                    segments, _ = result
                    text = " ".join([s.text for s in segments]).strip()
                elif isinstance(result, dict):
                    text = result.get("text", "").strip()
                else:
                    text = str(result).strip()

                return {"success": True, "text": text, "message": text}
    except Exception as e:
        log.warning(f"Whisper transcription failed: {e}")
    finally:
        try:
            os.remove(temp_wav)
        except Exception:
            pass

    return {"success": False, "text": "", "message": "Voice audio stream processed."}
