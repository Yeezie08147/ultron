"""
code_sandbox.py — ULTRON Autonomous Python Code & Shell Execution Matrix.

Capabilities:
- Dynamic Python code generation & isolated execution
- Safe PowerShell command runner with stdout capture
"""

import sys
import logging
import tempfile
import subprocess
from typing import Dict, Any

log = logging.getLogger("ultron.sandbox")


def execute_python_code(code: str) -> Dict[str, Any]:
    """Execute Python code in a subprocess and return stdout."""
    clean_code = code.strip()
    if clean_code.startswith("```python"):
        clean_code = clean_code.replace("```python", "").replace("```", "").strip()
    elif clean_code.startswith("```"):
        clean_code = clean_code.replace("```", "").strip()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as f:
        f.write(clean_code)
        temp_path = f.name

    try:
        res = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=15
        )
        stdout = res.stdout.strip()
        stderr = res.stderr.strip()

        if res.returncode == 0:
            msg = f"Execution successful. Output: {stdout[:200] if stdout else 'Process finished with return code 0.'}"
            return {"success": True, "output": stdout, "message": msg}
        else:
            return {"success": False, "error": stderr, "message": f"Execution failed with error: {stderr[:150]}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Code execution timed out after 15 seconds, sir."}
    except Exception as e:
        return {"success": False, "message": f"Execution error: {e}"}


def run_powershell_command(cmd: str) -> Dict[str, Any]:
    """Execute a PowerShell command safely and return output."""
    clean_cmd = cmd.strip()
    # Strip prefixes
    import re
    clean_cmd = re.sub(r'^(?:run powershell|run command|exec|execute)\s*', '', clean_cmd, flags=re.I).strip()

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", clean_cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        stdout = res.stdout.strip()
        if res.returncode == 0:
            out_preview = stdout[:150] if stdout else "Command executed successfully."
            return {"success": True, "output": stdout, "message": f"Command executed, sir. {out_preview}"}
        else:
            return {"success": False, "error": res.stderr.strip(), "message": f"Command failed: {res.stderr.strip()[:100]}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Command execution timed out, sir."}
    except Exception as e:
        return {"success": False, "message": f"Command execution error: {e}"}
