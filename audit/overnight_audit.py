#!/usr/bin/env python3
"""
overnight_audit.py — thorough, self-contained JARVIS backend audit + live HTML report.

Runs DETACHED (independent of any Claude Code session). Does a one-time deep static
diagnostic, then samples runtime health every few minutes through the night, watching
the server log for new errors, and regenerates audit/report.html each pass. Merges in
deep code-analysis findings from audit/code_findings.json when that file appears.

Nothing here mutates the backend — read-only diagnostics only.
"""
import os, sys, json, time, html, sqlite3, subprocess, datetime, traceback

ROOT = "/home/utsav/jarvis"
AUDIT = os.path.join(ROOT, "audit")
LOG = "/tmp/jarvis-server.log"
REPORT = os.path.join(AUDIT, "report.html")
SAMPLES_JSON = os.path.join(AUDIT, "samples.json")
FINDINGS_JSON = os.path.join(AUDIT, "code_findings.json")
STOP_FILE = os.path.join(AUDIT, "STOP")
VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
PORT = 8340

INTERVAL_SEC = 300          # sample every 5 min
MAX_HOURS = 10

CORE_MODULES = [
    "server", "claude_brain", "memory", "jarvis_persona", "dispatch_registry",
    "actions", "planner", "qa", "suggestions", "templates", "tracking",
    "monitor", "vision_build", "work_mode", "ab_testing",
]


def now():
    return datetime.datetime.now()


def ts():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def sh(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except Exception as e:
        return -1, "", f"{type(e).__name__}: {e}"


# ── one-time deep static checks ────────────────────────────────────────────
def check_modules():
    """Import each core module in a fresh subprocess — catches syntax AND import-time
    errors (NameError, missing deps, the exact class of bug as the missing `re` import)."""
    out = []
    for m in CORE_MODULES:
        to = 90 if m == "server" else 30
        rc, so, se = sh(f'cd {ROOT} && {VENV_PY} -c "import {m}"', timeout=to)
        if rc == 0:
            out.append({"module": m, "ok": True, "err": ""})
        else:
            tail = (se.strip().splitlines()[-4:] if se else [])
            out.append({"module": m, "ok": False, "err": "\n".join(tail) or f"exit {rc}"})
    return out


def check_deps():
    keys = ["anthropic", "faster-whisper", "torch", "kokoro", "transformers",
            "fastapi", "uvicorn", "numpy", "piper-tts", "psutil"]
    rc, so, se = sh(f"{VENV_PY} -m pip freeze", timeout=30)
    inst = {}
    for line in so.splitlines():
        if "==" in line:
            n, _, v = line.partition("==")
            inst[n.lower().strip()] = v.strip()
    rows = [{"pkg": k, "version": inst.get(k, "— NOT INSTALLED")} for k in keys]
    # transformers must be 4.49.x (5.x breaks kokoro)
    tv = inst.get("transformers", "")
    warn = []
    if tv and not tv.startswith("4.49"):
        warn.append(f"transformers=={tv} — kokoro needs 4.49.x (5.x broke AlbertModel import)")
    rc2, so2, se2 = sh(f"{VENV_PY} -m pip check", timeout=40)
    return {"rows": rows, "pip_check": so2 or se2 or "OK — no broken requirements", "warn": warn}


def check_db():
    db = os.path.join(ROOT, "data", "jarvis.db")
    if not os.path.exists(db):
        return {"exists": False}
    info = {"exists": True, "size_kb": round(os.path.getsize(db) / 1024, 1)}
    try:
        con = sqlite3.connect(db, timeout=5)
        cur = con.cursor()
        info["integrity"] = cur.execute("PRAGMA integrity_check").fetchone()[0]
        tabs = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        counts = {}
        for t in tabs:
            try:
                counts[t] = cur.execute(f"SELECT COUNT(*) FROM '{t}'").fetchone()[0]
            except Exception as e:
                counts[t] = f"err: {e}"
        info["tables"] = counts
        con.close()
    except Exception as e:
        info["integrity"] = f"ERROR: {e}"
    return info


def check_config():
    env = os.path.join(ROOT, ".env")
    out = {"present": os.path.exists(env), "keys": {}}
    if out["present"]:
        for line in open(env, errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip()
                # never leak secret values
                if any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASS")):
                    out["keys"][k] = "(set)" if v else "(EMPTY)"
                else:
                    out["keys"][k] = v or "(empty)"
    return out


def check_frontend():
    dist = os.path.join(ROOT, "frontend", "dist")
    idx = os.path.join(dist, "index.html")
    out = {"built": os.path.exists(idx)}
    if out["built"]:
        out["mtime"] = datetime.datetime.fromtimestamp(os.path.getmtime(idx)).strftime("%Y-%m-%d %H:%M")
        # newest source file vs build — is the build stale?
        newest = 0
        for r, _, fs in os.walk(os.path.join(ROOT, "frontend", "src")):
            for f in fs:
                newest = max(newest, os.path.getmtime(os.path.join(r, f)))
        out["stale"] = newest > os.path.getmtime(idx)
    return out


def check_git():
    rc, so, se = sh(f"cd {ROOT} && git status --porcelain 2>/dev/null | head -40")
    rc2, br, _ = sh(f"cd {ROOT} && git rev-parse --abbrev-ref HEAD 2>/dev/null")
    return {"branch": br or "(not a git repo)", "dirty": so.splitlines() if so else []}


def collect_static():
    s = {}
    s["host"] = sh("uname -a")[1]
    s["python"] = sh(f"{VENV_PY} --version")[1]
    s["generated"] = ts()
    s["modules"] = check_modules()
    s["deps"] = check_deps()
    s["db"] = check_db()
    s["config"] = check_config()
    s["frontend"] = check_frontend()
    s["git"] = check_git()
    return s


# ── per-loop runtime sample ────────────────────────────────────────────────
def server_proc():
    rc, so, _ = sh("pgrep -af '[s]erver.py'")
    if not so:
        return None
    pid = so.split()[0]
    try:
        import psutil
        p = psutil.Process(int(pid))
        return {"pid": pid, "rss_mb": round(p.memory_info().rss / 1e6, 1),
                "cpu": p.cpu_percent(interval=0.3),
                "started": datetime.datetime.fromtimestamp(p.create_time()).strftime("%H:%M:%S")}
    except Exception:
        return {"pid": pid}


def gpu():
    rc, so, se = sh("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu "
                    "--format=csv,noheader,nounits")
    if rc != 0 or not so:
        return None
    try:
        u, mu, mt, t = [x.strip() for x in so.split(",")]
        return {"util": int(u), "vram_used": int(mu), "vram_total": int(mt), "temp": int(t)}
    except Exception:
        return {"raw": so}


def sysload():
    out = {}
    try:
        import psutil
        out["cpu"] = psutil.cpu_percent(interval=0.3)
        vm = psutil.virtual_memory()
        out["ram_pct"] = vm.percent
        out["ram_used_gb"] = round(vm.used / 1e9, 1)
        out["ram_total_gb"] = round(vm.total / 1e9, 1)
    except Exception:
        pass
    out["load"] = sh("cat /proc/loadavg")[1].split()[:3] if os.path.exists("/proc/loadavg") else []
    out["tmp"] = sh("df -h /tmp | tail -1")[1]
    out["root_disk"] = sh("df -h / | tail -1")[1]
    return out


def probe_endpoints():
    res = {}
    for name, path in [("vitals", "/api/vitals")]:
        rc, so, se = sh(f'curl -s -o /dev/null -w "%{{http_code}} %{{time_total}}" '
                        f'--max-time 8 http://127.0.0.1:{PORT}{path}')
        res[name] = so or se or "no response"
    res["port_listen"] = "yes" if sh(f"ss -ltn 2>/dev/null | grep -q :{PORT} && echo y")[1] == "y" else "NO"
    return res


def collect_sample():
    return {
        "t": ts(),
        "server": server_proc(),
        "gpu": gpu(),
        "sys": sysload(),
        "endpoints": probe_endpoints(),
    }


# ── log analysis ───────────────────────────────────────────────────────────
def analyze_logs():
    if not os.path.exists(LOG):
        return {"present": False}
    try:
        data = open(LOG, errors="replace").read()
    except Exception as e:
        return {"present": True, "err": str(e)}
    lines = data.splitlines()
    err = [l for l in lines if "ERROR" in l or "Traceback" in l or "Exception" in l]
    warn = [l for l in lines if "WARNING" in l or "WARN " in l or "warn" in l.lower()]
    # recurring error signatures (strip timestamps/numbers)
    import re as _re
    sigs = {}
    for l in err:
        sig = _re.sub(r"\d", "#", l)[-120:]
        sigs[sig] = sigs.get(sig, 0) + 1
    top = sorted(sigs.items(), key=lambda x: -x[1])[:12]
    # last tracebacks block
    tb = []
    for i, l in enumerate(lines):
        if "Traceback" in l:
            tb.append("\n".join(lines[i:i + 12]))
    return {"present": True, "lines": len(lines), "errors": len(err), "warnings": len(warn),
            "top_signatures": top, "last_errors": err[-15:], "tracebacks": tb[-3:]}


# ── HTML ───────────────────────────────────────────────────────────────────
def esc(x):
    return html.escape(str(x))


def sev_badge(level):
    c = {"critical": "#ff3b3b", "warning": "#ffb340", "ok": "#29e3a8", "info": "#33c4ff"}.get(level, "#888")
    return f'<span style="background:{c};color:#06080c;padding:1px 8px;border-radius:10px;font-size:11px;font-weight:700">{level.upper()}</span>'


def render(static, samples, logs, findings):
    P = []
    a = P.append
    last = samples[-1] if samples else {}
    # headline counts
    mod_fail = [m for m in static.get("modules", []) if not m["ok"]]
    crit = len(mod_fail) + len([f for f in findings if f.get("severity") == "critical"])
    warns = len(static.get("deps", {}).get("warn", [])) + logs.get("errors", 0 if not logs.get("present") else 0)
    a(f"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="60">
<title>JARVIS Backend Audit</title>
<style>
 body{{background:#06080c;color:#cfe3f2;font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:0 0 60px}}
 .wrap{{max-width:1100px;margin:0 auto;padding:24px}}
 h1{{font-size:26px;color:#33c4ff;margin:0 0 4px}}
 h2{{font-size:18px;color:#9fd2ff;border-bottom:1px solid #15324a;padding-bottom:6px;margin:34px 0 14px}}
 .sub{{color:#6f8aa3;font-size:12px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:14px 0}}
 .card{{background:#0c121b;border:1px solid #15324a;border-radius:10px;padding:12px 14px}}
 .card .k{{color:#6f8aa3;font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
 .card .v{{font-size:20px;font-weight:700;color:#e8f4ff;margin-top:4px}}
 table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:13px}}
 th,td{{text-align:left;padding:6px 10px;border-bottom:1px solid #11283b;vertical-align:top}}
 th{{color:#6f8aa3;font-weight:600;font-size:11px;text-transform:uppercase}}
 pre{{background:#0a0f16;border:1px solid #15324a;border-radius:8px;padding:10px;overflow:auto;color:#bcd;font-size:12px;white-space:pre-wrap}}
 .ok{{color:#29e3a8}} .bad{{color:#ff6a6a}} .warn{{color:#ffb340}}
 code{{color:#9fd2ff}}
</style></head><body><div class="wrap">""")
    a(f"<h1>JARVIS — Backend Audit</h1>")
    a(f'<div class="sub">Generated {esc(static.get("generated"))} · live (auto-refresh 60s) · samples: {len(samples)} · {esc(static.get("host","")[:70])}</div>')

    # summary cards
    a('<div class="grid">')
    srv = last.get("server")
    a(f'<div class="card"><div class="k">Server</div><div class="v {"ok" if srv else "bad"}">{"UP" if srv else "DOWN"}</div></div>')
    a(f'<div class="card"><div class="k">Module failures</div><div class="v {"bad" if mod_fail else "ok"}">{len(mod_fail)}</div></div>')
    a(f'<div class="card"><div class="k">Code findings</div><div class="v">{len(findings)}</div></div>')
    le = logs.get("errors", "—")
    a(f'<div class="card"><div class="k">Log errors</div><div class="v {"warn" if isinstance(le,int) and le else ""}">{le}</div></div>')
    g = last.get("gpu") or {}
    if g:
        a(f'<div class="card"><div class="k">GPU temp / VRAM</div><div class="v">{g.get("temp","?")}° · {g.get("vram_used","?")}/{g.get("vram_total","?")}MB</div></div>')
    sy = last.get("sys") or {}
    if "ram_pct" in sy:
        a(f'<div class="card"><div class="k">RAM</div><div class="v">{sy.get("ram_pct")}%</div></div>')
    a('</div>')

    # CODE FINDINGS (from agents)
    a('<h2>Deep code findings</h2>')
    if not findings:
        a('<p class="sub">Awaiting code-analysis agents… (this section populates when audit/code_findings.json is written).</p>')
    else:
        order = {"critical": 0, "warning": 1, "info": 2}
        for f in sorted(findings, key=lambda x: order.get(x.get("severity"), 3)):
            a(f'<div class="card" style="margin:10px 0">{sev_badge(f.get("severity","info"))} '
              f'<b>{esc(f.get("title",""))}</b> '
              f'<span class="sub">— {esc(f.get("file",""))}{":"+str(f["line"]) if f.get("line") else ""} '
              f'<i>({esc(f.get("agent",""))})</i></span>'
              f'<div style="margin-top:6px">{esc(f.get("detail",""))}</div>'
              + (f'<div style="margin-top:6px;color:#9fd2ff"><b>Fix:</b> {esc(f.get("fix",""))}</div>' if f.get("fix") else "")
              + '</div>')

    # MODULE HEALTH
    a('<h2>Module import health</h2><table><tr><th>Module</th><th>Status</th><th>Error</th></tr>')
    for m in static.get("modules", []):
        st = '<span class="ok">OK</span>' if m["ok"] else '<span class="bad">FAILS</span>'
        a(f'<tr><td><code>{esc(m["module"])}.py</code></td><td>{st}</td><td><pre style="margin:0">{esc(m["err"])}</pre></td></tr>')
    a('</table>')

    # DEPENDENCIES
    d = static.get("deps", {})
    a('<h2>Dependencies</h2>')
    for w in d.get("warn", []):
        a(f'<p class="warn">⚠ {esc(w)}</p>')
    a('<table><tr><th>Package</th><th>Version</th></tr>')
    for r in d.get("rows", []):
        bad = "NOT INSTALLED" in r["version"]
        a(f'<tr><td>{esc(r["pkg"])}</td><td class="{"bad" if bad else ""}">{esc(r["version"])}</td></tr>')
    a('</table>')
    a(f'<div class="sub">pip check: {esc(d.get("pip_check",""))}</div>')

    # LOG ANALYSIS
    a('<h2>Server log analysis</h2>')
    if not logs.get("present"):
        a('<p class="sub">No log file.</p>')
    else:
        a(f'<p class="sub">{logs.get("lines")} lines · <span class="bad">{logs.get("errors")} errors</span> · <span class="warn">{logs.get("warnings")} warnings</span></p>')
        if logs.get("top_signatures"):
            a('<table><tr><th>#</th><th>Recurring error signature</th></tr>')
            for sig, n in logs["top_signatures"]:
                a(f'<tr><td>{n}</td><td><code>{esc(sig)}</code></td></tr>')
            a('</table>')
        for tb in logs.get("tracebacks", []):
            a(f'<pre>{esc(tb)}</pre>')

    # DB
    db = static.get("db", {})
    a('<h2>Database</h2>')
    if not db.get("exists"):
        a('<p class="warn">data/jarvis.db not found.</p>')
    else:
        ic = db.get("integrity", "?")
        a(f'<p>Integrity: <span class="{"ok" if ic=="ok" else "bad"}">{esc(ic)}</span> · {db.get("size_kb")} KB</p>')
        if db.get("tables"):
            a('<table><tr><th>Table</th><th>Rows</th></tr>')
            for t, c in db["tables"].items():
                a(f'<tr><td>{esc(t)}</td><td>{esc(c)}</td></tr>')
            a('</table>')

    # CONFIG + FRONTEND + GIT
    cfg = static.get("config", {})
    a('<h2>Config (.env)</h2><table><tr><th>Key</th><th>Value</th></tr>')
    for k, v in cfg.get("keys", {}).items():
        cls = "warn" if v in ("(EMPTY)", "(empty)") else ""
        a(f'<tr><td>{esc(k)}</td><td class="{cls}">{esc(v)}</td></tr>')
    a('</table>')
    fe = static.get("frontend", {})
    a('<h2>Frontend build</h2>')
    a(f'<p>Built: {"yes" if fe.get("built") else "<span class=bad>NO</span>"}'
      + (f' · {esc(fe.get("mtime"))}' if fe.get("built") else "")
      + (' · <span class="warn">STALE (src newer than build)</span>' if fe.get("stale") else "")
      + '</p>')
    g2 = static.get("git", {})
    a(f'<h2>Git</h2><p class="sub">branch <code>{esc(g2.get("branch"))}</code> · {len(g2.get("dirty",[]))} uncommitted file(s)</p>')
    if g2.get("dirty"):
        a(f'<pre>{esc(chr(10).join(g2["dirty"]))}</pre>')

    # RUNTIME TIMELINE
    a('<h2>Runtime timeline</h2><table><tr><th>Time</th><th>Server</th><th>RSS MB</th><th>CPU%</th><th>RAM%</th><th>GPU%</th><th>VRAM</th><th>GPU°</th><th>vitals</th></tr>')
    for s in samples[-60:][::-1]:
        srv = s.get("server") or {}
        gg = s.get("gpu") or {}
        ss = s.get("sys") or {}
        ep = s.get("endpoints") or {}
        a(f'<tr><td>{esc(s.get("t","")[11:])}</td>'
          f'<td class="{"ok" if srv else "bad"}">{"up" if srv else "DOWN"}</td>'
          f'<td>{esc(srv.get("rss_mb","—"))}</td><td>{esc(srv.get("cpu","—"))}</td>'
          f'<td>{esc(ss.get("ram_pct","—"))}</td><td>{esc(gg.get("util","—"))}</td>'
          f'<td>{esc(gg.get("vram_used","—"))}/{esc(gg.get("vram_total","—"))}</td>'
          f'<td>{esc(gg.get("temp","—"))}</td><td>{esc(ep.get("vitals","—"))}</td></tr>')
    a('</table>')
    a('</div></body></html>')
    return "".join(P)


def main():
    os.makedirs(AUDIT, exist_ok=True)
    start = time.time()
    try:
        static = collect_static()
    except Exception:
        static = {"generated": ts(), "modules": [], "error": traceback.format_exc()}
    samples = []
    if os.path.exists(SAMPLES_JSON):
        try:
            samples = json.load(open(SAMPLES_JSON))
        except Exception:
            samples = []
    i = 0
    while True:
        i += 1
        try:
            samples.append(collect_sample())
            json.dump(samples[-400:], open(SAMPLES_JSON, "w"))
            logs = analyze_logs()
            findings = []
            import glob as _glob
            for fp in sorted(set(_glob.glob(os.path.join(AUDIT, "findings_*.json")) +
                                 ([FINDINGS_JSON] if os.path.exists(FINDINGS_JSON) else []))):
                try:
                    d = json.load(open(fp))
                    findings.extend(d if isinstance(d, list) else d.get("findings", []))
                except Exception:
                    pass
            # refresh static occasionally (every ~6 passes) to re-check modules/build
            if i % 6 == 0:
                try:
                    static = collect_static()
                except Exception:
                    pass
            open(REPORT, "w").write(render(static, samples, logs, findings))
        except Exception:
            try:
                open(os.path.join(AUDIT, "audit_errors.log"), "a").write(ts() + "\n" + traceback.format_exc() + "\n")
            except Exception:
                pass
        if os.path.exists(STOP_FILE) or (time.time() - start) > MAX_HOURS * 3600:
            break
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
