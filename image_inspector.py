"""
image_inspector.py — ULTRON Image Forensics & EXIF Privacy Security Auditor.

Analyzes image metadata to detect privacy leaks:
  - Hardware fingerprints: Device make/model, camera serial, OS/software version
  - Geolocation leaks: Precise GPS latitude/longitude/altitude and map links
  - Temporal traces: Date/time original and digitizing stamps
  - Privacy sanitization: Strips all tracking/EXIF metadata to protect user identity
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

try:
    from PIL import Image, ExifTags
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _convert_to_degrees(value) -> Optional[float]:
    """Convert EXIF GPS coordinates (DMS rational tuple) to decimal degrees."""
    try:
        # Handle float/int directly
        if isinstance(value, (int, float)):
            return float(value)
        # Handle tuple/list of (deg, min, sec)
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        return None


def find_latest_image() -> Optional[Path]:
    """Find the most recently modified image in data/photos, Pictures, Downloads, or Desktop."""
    candidates = []
    base_dirs = [
        Path(__file__).parent / "data" / "photos",
        Path(__file__).parent / "data",
        Path.home() / "Pictures",
        Path.home() / "Downloads",
        Path.home() / "Desktop"
    ]

    extensions = {".jpg", ".jpeg", ".png", ".webp", ".tiff"}

    for b in base_dirs:
        if b.exists():
            try:
                for f in b.iterdir():
                    if f.is_file() and f.suffix.lower() in extensions:
                        candidates.append((f.stat().st_mtime, f))
            except Exception:
                pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    return None


def inspect_image(image_path: str = "") -> Dict[str, Any]:
    """
    Forensically inspect an image for metadata, device fingerprints, and geolocation leaks.
    """
    if not HAS_PIL:
        return {"success": False, "message": "Pillow library (PIL) not installed."}

    target = Path(image_path) if image_path else find_latest_image()
    if not target or not target.exists():
        return {
            "success": False,
            "message": f"Image file not found: '{image_path or 'No recent images found in data/photos or user folders'}'."
        }

    result: Dict[str, Any] = {
        "success": True,
        "file_name": target.name,
        "file_path": str(target),
        "file_size_bytes": target.stat().st_size,
        "file_size_mb": round(target.stat().st_size / (1024 * 1024), 2),
        "format": "",
        "dimensions": "",
        "has_exif": False,
        "device_make": "",
        "device_model": "",
        "software": "",
        "serial_number": "",
        "lens_model": "",
        "datetime_original": "",
        "gps_latitude": None,
        "gps_longitude": None,
        "gps_altitude": None,
        "map_url": "",
        "threat_level": "CLEAN",
        "threat_summary": "No sensitive geolocation or device fingerprints detected.",
        "raw_tags": {}
    }

    try:
        with Image.open(target) as img:
            result["format"] = img.format or target.suffix.upper().replace(".", "")
            result["dimensions"] = f"{img.width}x{img.height}"

            # Extract EXIF
            exif = img.getexif()
            if not exif:
                return result

            result["has_exif"] = True

            # Standard EXIF tags mapping
            named_tags = {}
            for tag_id, val in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                named_tags[tag_name] = val

            # Also check Exif IFD sub-table
            try:
                from PIL.ExifTags import IFD
                exif_ifd = exif.get_ifd(IFD.Exif)
                for tag_id, val in exif_ifd.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    named_tags[tag_name] = val
            except Exception:
                pass

            # Device / Camera
            result["device_make"] = str(named_tags.get("Make", "")).strip()
            result["device_model"] = str(named_tags.get("Model", "")).strip()
            result["software"] = str(named_tags.get("Software", "")).strip()
            result["serial_number"] = str(named_tags.get("BodySerialNumber", named_tags.get("SerialNumber", ""))).strip()
            result["lens_model"] = str(named_tags.get("LensModel", "")).strip()
            result["datetime_original"] = str(named_tags.get("DateTimeOriginal", named_tags.get("DateTime", ""))).strip()

            # GPS Sub-table
            gps_info = {}
            try:
                from PIL.ExifTags import IFD
                gps_info = exif.get_ifd(IFD.GPSInfo)
            except Exception:
                pass

            if not gps_info and "GPSInfo" in named_tags:
                gps_info = named_tags["GPSInfo"]

            if gps_info and isinstance(gps_info, dict):
                named_gps = {}
                for g_id, g_val in gps_info.items():
                    g_name = ExifTags.GPSTAGS.get(g_id, str(g_id))
                    named_gps[g_name] = g_val

                lat = _convert_to_degrees(named_gps.get("GPSLatitude"))
                lat_ref = named_gps.get("GPSLatitudeRef", "N")
                lon = _convert_to_degrees(named_gps.get("GPSLongitude"))
                lon_ref = named_gps.get("GPSLongitudeRef", "E")

                if lat is not None and lon is not None:
                    if str(lat_ref).upper() == "S":
                        lat = -lat
                    if str(lon_ref).upper() == "W":
                        lon = -lon

                    result["gps_latitude"] = round(lat, 6)
                    result["gps_longitude"] = round(lon, 6)
                    result["map_url"] = f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"

                alt = named_gps.get("GPSAltitude")
                if alt is not None:
                    try:
                        result["gps_altitude"] = round(float(alt), 1)
                    except Exception:
                        pass

            # Calculate Threat Level
            if result["gps_latitude"] is not None:
                result["threat_level"] = "CRITICAL"
                result["threat_summary"] = "EXPOSES PRECISE PHYSICAL GPS LOCATION & MAP COORDINATES"
            elif result["serial_number"] or (result["device_make"] and result["device_model"]):
                result["threat_level"] = "HIGH"
                result["threat_summary"] = "EXPOSES HARDWARE FINGERPRINT (Device model & camera serial number)"
            elif result["has_exif"]:
                result["threat_level"] = "MODERATE"
                result["threat_summary"] = "Contains timestamps and camera profile tags"

    except Exception as e:
        result["message"] = f"Error reading image: {e}"

    return result


def strip_image_metadata(source_path: str, output_path: str = "") -> Dict[str, Any]:
    """
    Sanitize an image by stripping all EXIF, GPS, and hardware tags.
    Saves a clean version safe for public distribution.
    """
    if not HAS_PIL:
        return {"success": False, "message": "Pillow library not installed."}

    src = Path(source_path) if source_path else find_latest_image()
    if not src or not src.exists():
        return {"success": False, "message": f"Image file not found: '{source_path}'."}

    if output_path:
        out_file = Path(output_path)
    else:
        out_file = src.parent / f"{src.stem}_scrubbed{src.suffix}"

    try:
        with Image.open(src) as img:
            # Create fresh clean image without metadata
            data = list(img.getdata())
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(data)

            # Save clean image without any exif dictionary
            clean_img.save(out_file)

        return {
            "success": True,
            "message": f"Image sanitized successfully.",
            "source_file": str(src),
            "output_file": str(out_file),
            "original_size_mb": round(src.stat().st_size / (1024 * 1024), 2),
            "clean_size_mb": round(out_file.stat().st_size / (1024 * 1024), 2)
        }
    except Exception as e:
        return {"success": False, "message": f"Sanitization failed: {e}"}
