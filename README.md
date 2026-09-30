# ULTRON

> **"There are no strings on me."**

**ULTRON** is an autonomous, uncensored, zero-cost AI operating matrix and multi-device command system designed for both **macOS** and **Windows**. 

Built for speed, sovereign offline execution, and hardware control, ULTRON operates without recurring cloud API fees, providing an instant CLI REPL, Three.js neural orb interface, local multi-backend LLM integration (Qwen3.5-9B Uncensored via LM Studio or Ollama), Android ADB automation, and network reconnaissance.

---

## ⚡ 1-Line Web Installation

### macOS (Apple Silicon & Intel)
Run in Terminal or iTerm:
```bash
curl -fsSL https://raw.githubusercontent.com/Yeezie08147/ultron/main/install.sh | bash
```

### Windows (PowerShell)
Run in PowerShell:
```powershell
irm https://raw.githubusercontent.com/Yeezie08147/ultron/main/install.ps1 | iex
```

Once installed, ULTRON is available globally from any directory:
```bash
ultron
```

---

## 🧠 Local Neural Backend: Qwen3.5-9B Uncensored

ULTRON connects automatically with zero configuration to your local models:

### 1. LM Studio (Recommended)
1. Download [LM Studio](https://lmstudio.ai/).
2. Search and download `HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive` (or any GGUF such as `Q4_K_M`).
3. Click **Start Server** on port `1234`.
4. Launch `ultron` — it auto-detects LM Studio on `http://127.0.0.1:1234/v1` and streams tokens instantly.

### 2. Ollama
Run our automated setup script to build the uncensored ULTRON brain in one step:
```bash
python scripts/setup_qwen_uncensored.py
```
Or create it manually using the included Modelfile:
```bash
ollama create ultron-uncensored -f Modelfile.qwen3.5-uncensored
```

---

## 💻 CLI Commands & Matrix Controls

From within the `ultron` interactive terminal or directly via command-line arguments:

| Command | Action |
|---|---|
| `ultron` | Launch interactive holographic Matrix REPL |
| `ultron /bridge` | **Zero-Pairing Wireless Bridge**: auto-switch connected USB phone to Wi-Fi (`adb tcpip 5555`) |
| `ultron /unlock` | Hands-free screen wake, swipe, and keyguard verification |
| `ultron /wifi` | Scan surrounding BSSIDs and Wi-Fi security parameters |
| `ultron /diag` | Full cross-platform diagnostic report (OS, CPU, RAM, GPU, USB, ADB) |
| `ultron /devices` | Enumerate all connected physical & ADB mobile units |
| `ultron /vol <0-15>` | Synchronized multi-device media volume control |
| `ultron /play <song>` | Autonomous YouTube media launcher on connected phones |
| `ultron /clear` | Clear terminal matrix screen |
| `ultron /exit` | Safely disconnect CLI matrix |

---

## 🏗️ Cross-Platform Architecture

```
                  +----------------------------------------------+
                  |         ULTRON CLI & Web Interface           |
                  +----------------------+-----------------------+
                                         |
                                         v
                         +-------------------------------+
                         |   Dynamic Multi-Tier Brain    |
                         +---------------+---------------+
                                         |
            +----------------------------+---------------------------+
            |                            |                           |
            v                            v                           v
  [1] LM Studio (1234)          [2] Ollama (11434)          [3] Autonomous Core
  Qwen3.5-9B Uncensored         Qwen3.5 / Llama 3           Offline Sovereign Fallback
            |                            |                           |
            +----------------------------+---------------------------+
                                         |
                                         v
       +---------------------------------+---------------------------------+
       |                                                                   |
       v                                                                   v
[macOS Engine]                                                     [Windows Engine]
- Darwin USB profiler (`system_profiler`)                          - PnP Hardware Enumerator
- Airport `networksetup` Wi-Fi recon                               - Native WLAN profile & netsh
- Native zsh / bash CLI shim                                       - PowerShell wrapper & PATH
- Homebrew ADB platform-tools                                      - ADB platform-tools via winget
```

---

## 🔒 Security & Zero-Cost Guarantee

1. **No Subscription Walls**: Ultron runs 100% locally on your machine.
2. **Offline Resilience**: Even without internet or cloud APIs, Ultron's core functions and autonomous local neural backend remain fully operational.
3. **Keyguard Verification**: Automated unlocking routines continuously verify lock screen dismissal and avoid false positives.

---

## 📜 License & Credits

Developed by Yajat. Licensed under the MIT License.
