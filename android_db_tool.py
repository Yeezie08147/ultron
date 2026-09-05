"""
android_db_tool.py — ULTRON Android SQLite Database Forensic & Export Matrix.

Capabilities:
- Extract and pull SQLite databases from connected Android devices via ADB
- Export SQLite tables to structured CSV files in Desktop/ULTRON_Database_Exports
- Execute analytical SQL queries on local or extracted database files
"""

import os
import csv
import json
import logging
import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, Any, List

log = logging.getLogger("ultron.dbtool")

EXPORTS_DIR = Path.home() / "Desktop" / "ULTRON_Database_Exports"


def _ensure_dir():
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def extract_android_database(
    device_db_path: str = "/data/system/locksettings.db",
    output_folder: str = ""
) -> Dict[str, Any]:
    """Pull an SQLite database from an Android device via ADB."""
    _ensure_dir()
    out_dir = Path(output_folder) if output_folder else EXPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    db_filename = Path(device_db_path).name or "extracted.db"
    local_db_path = out_dir / db_filename

    # 1. Check ADB connection
    try:
        dev_res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = [l for l in dev_res.stdout.splitlines()[1:] if l.strip() and "device" in l]
        if not lines:
            return {"success": False, "message": "No authorized Android device connected via ADB, sir."}
    except Exception as e:
        return {"success": False, "message": f"ADB execution failed: {e}"}

    # 2. Attempt pull directly or via temporary staging
    pulled = False
    try:
        pull_res = subprocess.run(["adb", "pull", device_db_path, str(local_db_path.resolve())], capture_output=True, text=True, timeout=10)
        if local_db_path.exists() and local_db_path.stat().st_size > 0:
            pulled = True
    except Exception:
        pass

    if not pulled:
        # Try root copy to staging
        try:
            staging = f"/sdcard/{db_filename}"
            subprocess.run(["adb", "shell", f"su -c 'cp {device_db_path} {staging} && chmod 666 {staging}'"], capture_output=True, timeout=10)
            subprocess.run(["adb", "pull", staging, str(local_db_path.resolve())], capture_output=True, timeout=10)
            subprocess.run(["adb", "shell", f"rm -f {staging}"], capture_output=True, timeout=5)
            if local_db_path.exists() and local_db_path.stat().st_size > 0:
                pulled = True
        except Exception as e:
            log.warning(f"Root staging extraction note: {e}")

    if not pulled:
        return {
            "success": False,
            "message": f"Failed to pull {device_db_path}. Ensure USB debugging is active and permissions are granted, sir."
        }

    # Auto-export tables to CSV
    csv_res = export_sqlite_to_csv(str(local_db_path), str(out_dir))
    return {
        "success": True,
        "db_path": str(local_db_path),
        "tables_exported": csv_res.get("tables", []),
        "message": f"Retrieved database {db_filename} from device. Exported {len(csv_res.get('tables', []))} tables to CSV, sir."
    }


def export_sqlite_to_csv(db_file: str, output_folder: str = "") -> Dict[str, Any]:
    """Export all tables of a SQLite database to separate CSV files."""
    _ensure_dir()
    db_path = Path(db_file)
    if not db_path.exists():
        return {"success": False, "message": f"Database file {db_file} not found, sir."}

    out_dir = Path(output_folder) if output_folder else EXPORTS_DIR / db_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    exported_tables = []
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]

        for table_name in tables:
            csv_path = out_dir / f"{table_name}.csv"
            cursor.execute(f'SELECT * FROM "{table_name}";')
            headers = [d[0] for d in cursor.description]
            rows = cursor.fetchall()

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            exported_tables.append(table_name)

        conn.close()
        return {
            "success": True,
            "tables": exported_tables,
            "output_dir": str(out_dir),
            "message": f"Exported {len(exported_tables)} tables ({', '.join(exported_tables[:3])}) to CSV in {out_dir.name}, sir."
        }
    except Exception as e:
        return {"success": False, "message": f"Failed to export tables: {e}"}


def query_sqlite_database(db_file: str, query: str) -> Dict[str, Any]:
    """Execute a read/analytical query on an SQLite database."""
    db_path = Path(db_file)
    if not db_path.exists():
        # Check in default exports dir
        potential = EXPORTS_DIR / db_file
        if potential.exists():
            db_path = potential
        else:
            return {"success": False, "message": f"Database {db_file} not found, sir."}

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(query)

        if cursor.description:
            headers = [d[0] for d in cursor.description]
            rows = cursor.fetchmany(10)
            result_str = f"Found {len(rows)} record(s). Headers: {', '.join(headers)}"
        else:
            conn.commit()
            result_str = f"Query executed. Rows affected: {cursor.rowcount}"

        conn.close()
        return {
            "success": True,
            "query": query,
            "summary": result_str,
            "message": f"SQL query executed on {db_path.name}: {result_str}, sir."
        }
    except Exception as e:
        return {"success": False, "message": f"SQL execution error: {e}"}
