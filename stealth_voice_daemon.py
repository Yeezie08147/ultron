"""
stealth_voice_daemon.py — ULTRON Autonomous Background Voice Daemon (GPT-6 Astra / Jarvis Engine).

Features:
- Continuous ambient microphone listening with zero taskbar / window requirement
- Full Desktop Access: shell commands, apps, typing, clicking, window control, volume, lock
- Dynamic time greeting ("Good morning / afternoon / evening, sir.") on "Show yourself"
- Edge-TTS neural speech with SSL bypass and Windows SAPI fallback
- SmartThings IoT, Sub-GHz RF, F.R.A.N.K SDR Radio & Neural Brain matrix dispatch
"""

import os
import re
import ssl
import time
import asyncio
import logging
import threading
import subprocess
import speech_recognition as sr
from typing import Callable, Optional, Dict, Any

log = logging.getLogger("ultron.stealth_daemon")

# Bypass SSL verification for Edge-TTS on Windows
try:
    import edge_tts.communicate
    edge_tts.communicate._SSL_CTX.check_hostname = False
    edge_tts.communicate._SSL_CTX.verify_mode = ssl.CERT_NONE
except Exception:
    pass

# Wake trigger prefixes (optional — direct commands are also handled)
WAKE_TRIGGERS = [
    "ultron",
    "hey ultron",
    "ok ultron",
    "altron",
    "oltron",
    "all tron",
    "ultra on",
    "jarvis",
    "hey jarvis"
]

_daemon_running = False
_is_listening_muted = False
_toggle_hud_callback: Optional[Callable[[bool], None]] = None


def set_hud_callback(cb: Callable[[bool], None]):
    """Set callback to show or hide the visual HUD window."""
    global _toggle_hud_callback
    _toggle_hud_callback = cb


def toggle_mute_listening() -> bool:
    """Toggle microphone mute state."""
    global _is_listening_muted
    _is_listening_muted = not _is_listening_muted
    state = "MUTED" if _is_listening_muted else "ACTIVE"
    log.info(f"Background voice listening: {state}")
    return _is_listening_muted


def get_time_greeting() -> str:
    """Generate dynamic time-of-day greeting."""
    hr = time.localtime().tm_hour
    if 4 <= hr < 12:
        return "Good morning, sir."
    elif 12 <= hr < 17:
        return "Good afternoon, sir."
    else:
        return "Good evening, sir."


def speak_response_sync(text: str):
    """Synthesize and play audio response synchronously or in a thread."""
    if not text:
        return
    clean_text = re.sub(r'[*_#`~"\n\r]', ' ', text).strip()
    
    # 1. Edge-TTS with SSL bypass
    spoken = False
    try:
        import edge_tts
        import tempfile

        async def _gen_edge():
            c = edge_tts.Communicate(clean_text, "en-GB-RyanNeural", pitch="+0Hz", rate="+5%")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tmp = fp.name
            await c.save(tmp)
            return tmp

        mp3_path = asyncio.run(_gen_edge())
        ps_cmd = f'Add-Type -AssemblyName presentationCore; $p = New-Object System.Windows.Media.MediaPlayer; $p.Open([System.Uri]"{mp3_path}"); $p.Play(); Start-Sleep -Milliseconds {int(len(clean_text) * 75 + 1000)}; $p.Close(); Remove-Item -Force "{mp3_path}" -ErrorAction SilentlyContinue'
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        spoken = True
    except Exception:
        pass

    # 2. Native Windows SAPI Speech Synthesizer fallback
    if not spoken:
        try:
            escaped = clean_text.replace("'", "''")
            ps_sapi = f'Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Rate = 1; $synth.Speak(\'{escaped}\')'
            subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_sapi],
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception as e:
            log.warning(f"TTS audio note: {e}")


def speak_response(text: str):
    """Dispatch speech response in background thread for zero-latency execution."""
    threading.Thread(target=speak_response_sync, args=(text,), daemon=True).start()


def execute_voice_command(phrase: str):
    """Full Desktop Access: Execute any voice command with zero limitations."""
    clean = phrase.strip().lower()
    log.info(f"Processing command: '{clean}'")

    # 1. "Show yourself" & HUD visibility commands
    if any(p in clean for p in [
        "show yourself", "reveal yourself", "show hud", "show window",
        "open hud", "wake up", "restore window", "reveal window",
        "appear", "come online", "turn on app", "where are you", "are you there"
    ]):
        if _toggle_hud_callback:
            _toggle_hud_callback(True)
        greeting = get_time_greeting()
        msg = f"{greeting} Systems fully online and responding. I am here and at your command."
        speak_response(msg)
        return

    # 2. Stealth / Hide commands
    if any(p in clean for p in ["hide hud", "hide window", "stealth mode", "ghost mode", "minimize to tray", "hide yourself"]):
        if _toggle_hud_callback:
            _toggle_hud_callback(False)
        speak_response("Stealth mode active. Running in the background, sir.")
        return

    # 3. Direct Shell Command Execution ("run command ...", "execute ...", "powershell ...")
    if clean.startswith("run command ") or clean.startswith("execute command ") or clean.startswith("powershell "):
        cmd_str = re.sub(r'^(?:run command|execute command|powershell)\s+', '', phrase, flags=re.IGNORECASE).strip()
        import desktop_control
        res = desktop_control.execute_shell_command(cmd_str)
        speak_response(f"Executed: {res.get('message', 'Command finished.')}")
        return

    # 4. Minimize / Show Desktop
    if any(p in clean for p in ["minimize all", "show desktop", "minimize windows"]):
        import desktop_control
        desktop_control.minimize_all()
        speak_response("Desktop revealed, sir.")
        return

    # 5. Lock Workstation
    if any(p in clean for p in ["lock pc", "lock computer", "lock screen", "lock workstation"]):
        import desktop_control
        desktop_control.lock_pc()
        speak_response("Workstation locked, sir.")
        return

    # 6. Volume Management
    if any(p in clean for p in ["volume up", "louder", "turn up volume"]):
        import desktop_control
        desktop_control.volume_up()
        speak_response("Volume increased, sir.")
        return
    if any(p in clean for p in ["volume down", "quieter", "lower volume"]):
        import desktop_control
        desktop_control.volume_down()
        speak_response("Volume decreased, sir.")
        return
    if any(p in clean for p in ["mute audio", "mute sound", "mute volume", "unmute"]):
        import desktop_control
        desktop_control.mute_volume()
        speak_response("Audio mute toggled, sir.")
        return

    # 7. Typing Injection ("type ...", "write ...")
    if clean.startswith("type ") or clean.startswith("write "):
        text_to_type = re.sub(r'^(?:type|write)\s+', '', phrase, flags=re.IGNORECASE).strip()
        import desktop_control
        desktop_control.type_text(text_to_type)
        speak_response(f"Typed {len(text_to_type)} characters, sir.")
        return

    # 8. Web Search
    if clean.startswith("search for ") or clean.startswith("google ") or clean.startswith("search web for "):
        q = re.sub(r'^(?:search for|google|search web for)\s+', '', phrase, flags=re.IGNORECASE).strip()
        import desktop_control
        desktop_control.search_web_browser(q)
        speak_response(f"Searched for {q}, sir.")
        return

    # 9. Screenshot
    if any(p in clean for p in ["take screenshot", "take a screenshot", "capture screen", "screenshot"]):
        import desktop_control
        desktop_control.capture_screenshot()
        speak_response("Screenshot captured to Desktop, sir.")
        return

    # 10. Open App / Launch
    if clean.startswith("open ") or clean.startswith("launch ") or clean.startswith("start "):
        app_name = re.sub(r'^(?:open|launch|start)\s+', '', phrase, flags=re.IGNORECASE).strip()
        import desktop_control
        res = desktop_control.open_app(app_name)
        speak_response(res.get("message", f"Opened {app_name}, sir."))
        return

    # 11. Close App / Terminate
    if clean.startswith("close ") or clean.startswith("terminate ") or clean.startswith("kill "):
        app_name = re.sub(r'^(?:close|terminate|kill)\s+', '', phrase, flags=re.IGNORECASE).strip()
        import desktop_control
        res = desktop_control.close_app(app_name)
        speak_response(res.get("message", f"Closed {app_name}, sir."))
        return

    # 12. SmartThings & Multi-Device Control
    if any(p in clean for p in ["turn on all lights", "all lights on"]):
        import smartthings_matrix
        asyncio.run(smartthings_matrix.control_all_lights("on"))
        speak_response("All lights powered on, sir.")
        return
    if any(p in clean for p in ["turn off all lights", "all lights off"]):
        import smartthings_matrix
        asyncio.run(smartthings_matrix.control_all_lights("off"))
        speak_response("All lights powered off, sir.")
        return
    if any(p in clean for p in ["movie mode", "cinema mode", "good night", "all off"]):
        import smartthings_matrix
        res = asyncio.run(smartthings_matrix.execute_smart_scene(clean))
        speak_response(res.get("message", "Scene executed, sir."))
        return

    # 13. Sub-GHz Radio & F.R.A.N.K
    if "sub ghz" in clean or "sub-ghz" in clean:
        import sub_ghz
        res = sub_ghz.read(433.92)
        speak_response(res.get("message", "Sub-GHz read complete, sir."))
        return
    if "frank" in clean or "radio signal" in clean:
        import frank_radio
        res = frank_radio.record_raw_signal(100000000)
        speak_response(res.get("message", "Radio signal recorded, sir."))
        return

    # 14. Server fast action detection fallback
    try:
        from server import detect_action_fast
        action = detect_action_fast(clean)
        if action:
            act_type = action.get("action", "")
            if act_type == "speak_direct":
                speak_response(action.get("text", "Handled, sir."))
                return
    except Exception:
        pass

    # 15. Intelligent Brain Answering (Ollama Local / Frontier Matrix)
    try:
        from ollama_brain import generate_response
        ans = generate_response(phrase)
        speak_response(ans)
    except Exception:
        speak_response("Command processed, sir.")


def _background_listener_loop():
    """Continuous microphone listening loop with speech recognition."""
    global _daemon_running
    log.info("Starting ULTRON Full Desktop Background Voice Listener...")

    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.energy_threshold = 220
    r.pause_threshold = 0.5
    r.non_speaking_duration = 0.3

    try:
        mic = sr.Microphone()
        with mic as source:
            r.adjust_for_ambient_noise(source, duration=0.8)
    except Exception as e:
        log.error(f"Microphone init error: {e}")
        return

    log.info("ULTRON Background Voice Daemon online. Listening for full desktop commands...")

    def audio_callback(recognizer: sr.Recognizer, audio: sr.AudioData):
        if _is_listening_muted:
            return

        text = ""
        try:
            text = recognizer.recognize_google(audio).strip()
        except Exception:
            pass

        if not text:
            return

        log.info(f"Heard voice: '{text}'")
        t_lower = text.lower()

        # Check if wake trigger is present in phrase
        matched_trigger = None
        for trigger in WAKE_TRIGGERS:
            if trigger in t_lower:
                matched_trigger = trigger
                break

        if matched_trigger:
            idx = t_lower.find(matched_trigger)
            command_part = text[idx + len(matched_trigger):].strip(" ,:.-")
            if command_part:
                threading.Thread(target=execute_voice_command, args=(command_part,), daemon=True).start()
            else:
                greeting = get_time_greeting()
                speak_response_sync(f"{greeting} At your service, sir.")
        else:
            # Full Desktop Access: No wake word required for direct commands!
            threading.Thread(target=execute_voice_command, args=(text,), daemon=True).start()

    try:
        stop_fn = r.listen_in_background(mic, audio_callback, phrase_time_limit=6)
        while _daemon_running:
            time.sleep(1)
        stop_fn(wait_for_stop=False)
    except Exception as e:
        log.error(f"Listener loop crashed: {e}")


def start_stealth_daemon():
    """Start background voice daemon."""
    global _daemon_running
    if _daemon_running:
        return
    _daemon_running = True
    t = threading.Thread(target=_background_listener_loop, daemon=True)
    t.start()


def stop_stealth_daemon():
    """Stop background voice daemon."""
    global _daemon_running
    _daemon_running = False
