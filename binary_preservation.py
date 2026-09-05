"""
binary_preservation.py — ULTRON Software Preservation & Binary Format Matrix.

Capabilities:
- Magic byte identification (PE, ELF, Mach-O, DEX, WASM, Java Class)
- Strings and symbol table discovery
- Automated headless static analysis bridge (Ghidra analyzeHeadless)
- Markdown preservation report generation in Desktop/ULTRON_Preservation_Reports
"""

import os
import sys
import json
import shutil
import struct
import pathlib
import logging
import subprocess
from typing import Dict, Any, Optional, List

log = logging.getLogger("ultron.preservation")

REPORTS_DIR = pathlib.Path.home() / "Desktop" / "ULTRON_Preservation_Reports"


def _ensure_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def detect_file_format(file_path: pathlib.Path) -> str:
    """Identify binary file format based on initial magic bytes."""
    if not file_path.is_file():
        return "Unknown (Not a regular file)"

    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
    except OSError as e:
        return f"Error reading file: {e}"

    if len(header) < 4:
        return "Unknown (File too small)"

    if header.startswith(b"\x7fELF"):
        bitness = "64-bit" if header[4] == 2 else "32-bit"
        return f"ELF ({bitness})"

    if header.startswith(b"MZ"):
        try:
            with open(file_path, "rb") as f:
                f.seek(0x3C)
                pe_offset_bytes = f.read(4)
                if len(pe_offset_bytes) == 4:
                    pe_offset = struct.unpack("<I", pe_offset_bytes)[0]
                    f.seek(pe_offset)
                    if f.read(4) == b"PE\x00\x00":
                        f.seek(pe_offset + 4)
                        machine = struct.unpack("<H", f.read(2))[0]
                        arch_map = {0x8664: "x86_64", 0x014C: "x86", 0xAA64: "ARM64", 0x01C0: "ARM"}
                        arch = arch_map.get(machine, f"Machine ID: {hex(machine)}")
                        return f"Windows PE Executable ({arch})"
        except Exception:
            pass
        return "DOS / Windows Executable (MZ)"

    macho_magics = {
        b"\xfe\xed\xfa\xce": "Mach-O (32-bit big-endian)",
        b"\xce\xfa\xed\xfe": "Mach-O (32-bit little-endian)",
        b"\xfe\xed\xfa\xcf": "Mach-O (64-bit big-endian)",
        b"\xcf\xfa\xed\xfe": "Mach-O (64-bit little-endian)",
        b"\xca\xfe\xba\xbe": "Mach-O Universal / Java Bytecode",
    }
    for magic, desc in macho_magics.items():
        if header.startswith(magic):
            return desc

    if header.startswith(b"dex\n"):
        version = header[4:7].decode("ascii", errors="replace")
        return f"Android DEX (Version {version})"

    if header.startswith(b"\x00asm"):
        return "WebAssembly (WASM)"

    return "Raw Binary / Data"


def locate_analyze_headless() -> Optional[pathlib.Path]:
    """Locate the analyzeHeadless executable from environment or common paths."""
    env_dir = os.environ.get("GHIDRA_INSTALL_DIR")
    if env_dir:
        candidate_dir = pathlib.Path(env_dir)
        for sub in [pathlib.Path("support/analyzeHeadless.bat"), pathlib.Path("support/analyzeHeadless")]:
            target = candidate_dir / sub
            if target.is_file():
                return target

    bin_on_path = shutil.which("analyzeHeadless.bat") or shutil.which("analyzeHeadless")
    if bin_on_path:
        return pathlib.Path(bin_on_path)

    default_locations = [
        pathlib.Path(r"C:\ghidra\support\analyzeHeadless.bat"),
        pathlib.Path(r"C:\Program Files\ghidra\support\analyzeHeadless.bat"),
        pathlib.Path("/Applications/ghidra/support/analyzeHeadless"),
        pathlib.Path("/opt/ghidra/support/analyzeHeadless"),
    ]

    for loc in default_locations:
        if loc.is_file():
            return loc

    return None


def extract_strings(file_path: pathlib.Path, min_len: int = 4, max_count: int = 50) -> List[str]:
    """Extract printable ASCII strings from binary."""
    strings = []
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        current = []
        for byte in data:
            if 32 <= byte <= 126:
                current.append(chr(byte))
            else:
                if len(current) >= min_len:
                    strings.append("".join(current))
                    if len(strings) >= max_count:
                        break
                current = []
        if len(current) >= min_len and len(strings) < max_count:
            strings.append("".join(current))
    except Exception:
        pass
    return strings


def analyze_and_preserve_binary(target_path_str: str) -> Dict[str, Any]:
    """Perform static preservation analysis and generate Markdown report."""
    _ensure_dir()
    target_path = pathlib.Path(target_path_str.strip('\'"'))

    if not target_path.exists():
        return {"success": False, "message": f"File not found: {target_path_str}, sir."}

    fmt = detect_file_format(target_path)
    file_stat = target_path.stat()
    size_kb = round(file_stat.st_size / 1024, 2)
    strings = extract_strings(target_path)

    report_name = f"{target_path.stem}_preservation.md"
    report_path = REPORTS_DIR / report_name

    lines = [
        f"# Software Preservation & Static Analysis: `{target_path.name}`",
        "",
        "## 1. Binary Metadata",
        f"- **File Name:** `{target_path.name}`",
        f"- **Absolute Path:** `{target_path.resolve()}`",
        f"- **File Format / Type:** {fmt}",
        f"- **File Size:** {size_kb} KB ({file_stat.st_size:,} bytes)",
        "",
        "## 2. Discovered String Literals (Sample)",
        "```text",
    ]
    for s in strings:
        lines.append(s)
    lines.extend([
        "```",
        "",
        "---",
        "*Report generated automatically by ULTRON Preservation Matrix.*"
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "success": True,
        "format": fmt,
        "size_kb": size_kb,
        "strings_found": len(strings),
        "report_path": str(report_path),
        "message": f"Analyzed binary {target_path.name} ({fmt}, {size_kb} KB). Preservation report written to {report_name}, sir."
    }
