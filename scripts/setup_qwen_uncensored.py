"""
setup_qwen_uncensored.py -- Automated Setup & Verification for Qwen3.5-9B Uncensored.
Configures and tests:
  - LM Studio: HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive (GGUF Q4_K_M)
  - Ollama: hf.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive:Q4_K_M
Works on both macOS and Windows.
"""

import sys
import subprocess
import json
import time

try:
    import httpx
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx"], check=True)
    import httpx

ORANGE = "\033[38;5;208m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"

print(f"{ORANGE}{BOLD}======================================================================{RESET}")
print(f"{ORANGE}{BOLD}   ULTRON // QWEN 3.5 9B UNCENSORED BACKEND SETUP & VERIFIER{RESET}")
print(f"{ORANGE}{BOLD}======================================================================{RESET}\n")

# 1. Check LM Studio
print(f"{CYAN}[1/2] Checking LM Studio Local Server (http://127.0.0.1:1234/v1)...{RESET}")
lm_studio_ok = False
try:
    r = httpx.get("http://127.0.0.1:1234/v1/models", timeout=1.5)
    if r.status_code == 200:
        models = [m.get("id") for m in r.json().get("data", [])]
        print(f"  {GREEN}[OK] LM Studio Server is ONLINE!{RESET}")
        print(f"  Loaded Models: {', '.join(models) if models else 'Standby'}")
        lm_studio_ok = True
        
        # Test generation
        print(f"  Testing inference with LM Studio...")
        test_r = httpx.post(
            "http://127.0.0.1:1234/v1/chat/completions",
            json={
                "model": models[0] if models else "HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive",
                "messages": [{"role": "user", "content": "Ultron status test. Respond in 5 words."}],
                "max_tokens": 30
            },
            timeout=10.0
        )
        if test_r.status_code == 200:
            ans = test_r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            print(f"  {GREEN}[SUCCESS] LM Studio Output:{RESET} \"{ans}\"")
except Exception:
    print(f"  {YELLOW}[-] LM Studio is not currently running on port 1234.{RESET}")
    print(f"      To use LM Studio:")
    print(f"      1. In LM Studio, search: {BOLD}HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive{RESET}")
    print(f"      2. Select {BOLD}Q4_K_M (6.55 GB){RESET} and download.")
    print(f"      3. Navigate to the '<->' (Local Server) tab and click {GREEN}'Start Server'{RESET} on port 1234.")

# 2. Check Ollama
print(f"\n{CYAN}[2/2] Checking Ollama Server (http://127.0.0.1:11434)...{RESET}")
try:
    r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=1.5)
    if r.status_code == 200:
        models = [m.get("name") for m in r.json().get("models", [])]
        print(f"  {GREEN}[OK] Ollama is ONLINE!{RESET}")
        print(f"  Installed Models: {', '.join(models) if models else 'None'}")
        
        has_uncensored = any("qwen" in m.lower() or "uncensored" in m.lower() for m in models)
        if not has_uncensored:
            print(f"\n  {YELLOW}[*] To pull Qwen 3.5 9B Uncensored directly into Ollama, run:{RESET}")
            print(f"      {BOLD}ollama run hf.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive:Q4_K_M{RESET}")
            print(f"      OR create custom model via: {BOLD}ollama create ultron-uncensored -f Modelfile.qwen3.5-uncensored{RESET}")
except Exception:
    print(f"  {YELLOW}[-] Ollama server is not running.{RESET}")

print(f"\n{GREEN}{BOLD}Setup scan complete. ULTRON will auto-route to whichever backend is online.{RESET}\n")
