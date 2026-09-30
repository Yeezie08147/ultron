"""
standalone_engine.py — ULTRON Standalone Local Neural Engine.

Runs GGUF models directly within ULTRON with ZERO external GUI applications:
- No LM Studio required
- No Ollama required
- 100% self-contained in ~/.ultron/

Capabilities:
- Auto-detects or downloads portable llama-server into ~/.ultron/bin/
- Auto-downloads GGUF model (Qwen3.5-9B-Uncensored) into ~/.ultron/models/
- Starts background OpenAI-compatible server on http://127.0.0.1:8080/v1
"""

import os
import sys
import time
import json
import shutil
import urllib.request
import subprocess
from pathlib import Path
from typing import Optional

ULTRON_HOME = Path(os.getenv("USERPROFILE" if sys.platform == "win32" else "HOME", ".")) / ".ultron"
BIN_DIR = ULTRON_HOME / "bin"
MODELS_DIR = ULTRON_HOME / "models"
PORT = 8088

DEFAULT_MODEL_URL = "https://huggingface.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive/resolve/main/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
DEFAULT_MODEL_FILENAME = "Qwen3.5-9B-Uncensored-Q4_K_M.gguf"

# Optional ultra-light 1.5B model for low-spec systems (<8GB RAM)
LIGHT_MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
LIGHT_MODEL_FILENAME = "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"


def get_llama_server_path() -> Optional[Path]:
    """Find llama-server binary in ~/.ultron/bin, system PATH, WinGet, or Homebrew."""
    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    
    # 1. Check ~/.ultron/bin/
    local_bin = BIN_DIR / exe_name
    if local_bin.exists():
        return local_bin
    
    # 2. Check system PATH
    which_path = shutil.which("llama-server")
    if which_path:
        return Path(which_path)

    # 3. Windows WinGet Package Locations
    if sys.platform == "win32":
        import glob
        local_app = os.getenv("LOCALAPPDATA", "")
        if local_app:
            matches = glob.glob(f"{local_app}/Microsoft/WinGet/Packages/**/{exe_name}", recursive=True)
            if matches:
                return Path(matches[0])
            win_apps = Path(local_app) / "Microsoft" / "WindowsApps" / exe_name
            if win_apps.exists():
                return win_apps

    # 4. macOS Homebrew standard locations
    if sys.platform == "darwin":
        for hb in ["/opt/homebrew/bin/llama-server", "/usr/local/bin/llama-server"]:
            p = Path(hb)
            if p.exists():
                return p

    return None


def is_engine_running() -> bool:
    """Check if standalone engine is online on port 8080."""
    try:
        import httpx
        with httpx.Client(timeout=0.6) as c:
            r = c.get(f"http://127.0.0.1:{PORT}/v1/models")
            return r.status_code == 200
    except Exception:
        return False


def download_with_progress(url: str, dest_path: Path, label: str = "File"):
    """Download file with visual progress bar."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(".downloading")

    print(f"\n[*] Downloading {label}...")
    print(f"    Source: {url}")
    print(f"    Target: {dest_path}")

    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100.0, downloaded * 100.0 / total_size)
            mb_down = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            bar = "#" * int(percent // 2) + "-" * (50 - int(percent // 2))
            sys.stdout.write(f"\r    [{bar}] {percent:.1f}% ({mb_down:.1f}/{mb_total:.1f} MB)")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, str(temp_path), reporthook=reporthook)
        print()
        if temp_path.exists():
            if dest_path.exists():
                dest_path.unlink()
            temp_path.rename(dest_path)
        print(f"[OK] Download complete: {dest_path.name}")
        return True
    except Exception as e:
        print(f"\n[ERROR] Download failed: {e}")
        if temp_path.exists():
            temp_path.unlink()
        return False


def install_llama_binary() -> Optional[Path]:
    """Install or fetch portable llama-server binary."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    exe_name = "llama-server.exe" if sys.platform == "win313" or sys.platform == "win32" else "llama-server"
    target_bin = BIN_DIR / exe_name

    if sys.platform == "darwin":
        # macOS Homebrew attempt
        if shutil.which("brew"):
            print("[*] Installing llama.cpp via Homebrew...")
            subprocess.run(["brew", "install", "llama.cpp"], check=False)
            which_path = shutil.which("llama-server")
            if which_path:
                return Path(which_path)

    elif sys.platform == "win32":
        # Windows winget attempt
        if shutil.which("winget"):
            print("[*] Installing llama.cpp via winget (no GUI required)...")
            res = subprocess.run(["winget", "install", "ggml.llamacpp", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements"], check=False)
            which_path = shutil.which("llama-server")
            if which_path:
                return Path(which_path)

    return get_llama_server_path()


def find_local_gguf(preferred: str = "") -> Optional[Path]:
    """Scan ~/.ultron/models/ and existing cache directories for GGUF files."""
    # 1. Check ~/.ultron/models/
    if MODELS_DIR.exists():
        if preferred:
            for p in MODELS_DIR.rglob("*.gguf"):
                if preferred.lower() in p.name.lower():
                    return p
        models = [p for p in MODELS_DIR.rglob("*.gguf") if p.stat().st_size > 100_000_000]
        if models:
            return models[0]

    # 2. Check ~/.lmstudio/models/ if user has existing models cached
    user_home = Path(os.getenv("USERPROFILE" if sys.platform == "win32" else "HOME", "."))
    lm_models = user_home / ".lmstudio" / "models"
    if lm_models.exists():
        if preferred:
            for p in lm_models.rglob("*.gguf"):
                if preferred.lower() in p.name.lower():
                    return p
        models = [p for p in lm_models.rglob("*.gguf") if p.stat().st_size > 100_000_000]
        if models:
            return models[0]

    return None


def start_server(model_name: str = "default", background: bool = True):
    """Start standalone llama-server on port 8080."""
    if is_engine_running():
        print(f"[OK] ULTRON Standalone Engine is ALREADY running on http://127.0.0.1:{PORT}/v1")
        return True

    # 1. Locate binary
    bin_path = get_llama_server_path()
    if not bin_path:
        print("[!] Standalone binary not found. Installing now...")
        bin_path = install_llama_binary()
        if not bin_path:
            print("[ERROR] Could not install llama-server automatically.")
            print("On Windows: winget install ggml.llamacpp --source winget")
            print("On macOS:   brew install llama.cpp")
            return False

    # 2. Locate model
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    existing_model = find_local_gguf(model_name if model_name != "default" else "")
    if existing_model:
        model_file = existing_model
        print(f"[*] Detected local GGUF model: {model_file.name}")
    else:
        if model_name == "light":
            model_file = MODELS_DIR / LIGHT_MODEL_FILENAME
            model_url = LIGHT_MODEL_URL
        else:
            model_file = MODELS_DIR / DEFAULT_MODEL_FILENAME
            model_url = DEFAULT_MODEL_URL

        if not model_file.exists():
            print(f"[!] Model {model_file.name} not found locally.")
            ok = download_with_progress(model_url, model_file, label=f"Model ({model_file.name})")
            if not ok:
                return False

    print(f"\n[*] Starting ULTRON Standalone Neural Engine...")
    print(f"    Binary: {bin_path}")
    print(f"    Model:  {model_file}")
    print(f"    Port:   {PORT}")

    cmd = [
        str(bin_path),
        "-m", str(model_file),
        "--port", str(PORT),
        "--host", "127.0.0.1",
        "-c", "4096",
        "-ngl", "99"
    ]

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    if background:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags
        )
        print(f"[*] Engine spawned (PID: {proc.pid}). Waiting for initialization...")
        for _ in range(30):
            time.sleep(1)
            if is_engine_running():
                print(f"[SUCCESS] ULTRON Standalone Neural Engine ONLINE on http://127.0.0.1:{PORT}/v1")
                print(f"Zero external software required. 100% self-contained in {ULTRON_HOME}")
                return True
        print("[!] Engine process started, but model is still loading weights.")
        return True
    else:
        subprocess.run(cmd)
        return True


def stop_server():
    """Stop the running standalone engine."""
    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", exe_name], capture_output=True)
    else:
        subprocess.run(["killall", exe_name], capture_output=True)
    time.sleep(1)
    if not is_engine_running():
        print("[OK] Standalone engine stopped.")
    else:
        print("[!] Could not terminate engine.")


def main():
    args = sys.argv[1:]
    cmd = args[0].lower() if args else "status"

    if cmd in ("status", "--status"):
        if is_engine_running():
            print(f"[ONLINE] ULTRON Standalone Engine is running on http://127.0.0.1:{PORT}/v1")
        else:
            bin_path = get_llama_server_path()
            print(f"[STANDBY] Standalone Engine is offline.")
            print(f"  Binary: {'Found (' + str(bin_path) + ')' if bin_path else 'Not installed'}")
            print(f"  Run 'python scripts/standalone_engine.py start' to launch.")
    elif cmd in ("start", "--start"):
        model_type = args[1] if len(args) > 1 else "default"
        start_server(model_type, background=True)
    elif cmd in ("stop", "--stop"):
        stop_server()
    elif cmd in ("download", "--download"):
        model_type = args[1] if len(args) > 1 else "default"
        target = MODELS_DIR / (LIGHT_MODEL_FILENAME if model_type == "light" else DEFAULT_MODEL_FILENAME)
        url = LIGHT_MODEL_URL if model_type == "light" else DEFAULT_MODEL_URL
        download_with_progress(url, target, label=f"Model ({target.name})")
    else:
        print("Usage: python scripts/standalone_engine.py [status|start|stop|download]")


if __name__ == "__main__":
    main()
