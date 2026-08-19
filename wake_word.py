"""
wake_word.py — ULTRON Resilient Wake-Word Detection Engine.

Listens continuously for "ULTRON" (and common phonetic variations)
to wake up ULTRON, restore the UI, and activate voice listening.
"""

import time
import logging
import speech_recognition as sr
from typing import Callable

log = logging.getLogger("ultron.wake")

# Phonetic & alias triggers for ULTRON
WAKE_TRIGGERS = [
    "ultron",
    "altron",
    "all tron",
    "oltron",
    "ultra on",
    "ultra",
    "hey ultron",
    "ok ultron",
    "wake up ultron",
    "jarvis",
    "hey jarvis",
]


def start_wake_word_listener(on_wake_callback: Callable[[], None]):
    """Start background audio listener for the wake word."""
    log.info("Initializing ULTRON Wake Word Engine...")
    
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.energy_threshold = 300
    r.pause_threshold = 0.5
    r.non_speaking_duration = 0.3

    try:
        m = sr.Microphone()
    except Exception as e:
        log.error(f"No microphone found for wake word: {e}")
        return

    try:
        with m as source:
            r.adjust_for_ambient_noise(source, duration=1.0)
    except Exception as e:
        log.warning(f"Ambient noise adjustment skipped: {e}")

    log.info("Listening for 'ULTRON'...")

    def callback(recognizer: sr.Recognizer, audio: sr.AudioData):
        text = ""
        
        # 1. Primary: Google Speech Recognition (Fast, highly accurate)
        try:
            text = recognizer.recognize_google(audio).lower().strip()
        except sr.UnknownValueError:
            pass
        except Exception:
            # 2. Fallback: Offline Sphinx
            try:
                text = recognizer.recognize_sphinx(audio).lower().strip()
            except Exception:
                pass

        if text:
            # Check for any trigger phrase
            matched = any(trigger in text for trigger in WAKE_TRIGGERS)
            if matched:
                log.info(f"Wake word detected in phrase: '{text}'")
                try:
                    on_wake_callback()
                except Exception as e:
                    log.error(f"Error in wake callback: {e}")

    # Listen in background thread with 2.5-second phrase windows
    try:
        stop_listening = r.listen_in_background(m, callback, phrase_time_limit=3)
        while True:
            time.sleep(1)
    except Exception as e:
        log.error(f"Wake word listener crashed: {e}")
