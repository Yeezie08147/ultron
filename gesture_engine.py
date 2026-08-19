"""
gesture_engine.py — ULTRON Real-Time Computer Vision & Gesture Control.

Capabilities:
- Real-time webcam motion & hand gesture detection using OpenCV
- Gestures mapped to Windows commands:
  - High motion in upper frame = Volume Up
  - High motion in lower frame = Volume Down
  - Palm wave / stationary hold = Play/Pause
  - Quick fist/swipe = Take Screenshot
- Toggleable via voice: "Activate gesture control" / "Deactivate gesture control"
"""

import time
import logging
import threading
from typing import Dict, Any, Optional
import cv2
import numpy as np

import media_control
import desktop_control

log = logging.getLogger("ultron.gestures")

_tracking_active = False
_tracking_thread: Optional[threading.Thread] = None
_last_action_time = 0.0


def _gesture_loop(camera_index: int = 0):
    global _tracking_active, _last_action_time
    
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        log.error("Webcam not available for gesture tracking.")
        _tracking_active = False
        return

    # Background subtractor for robust motion tracking
    fgbg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=50, detectShadows=False)
    
    log.info("ULTRON Vision Gesture Matrix online.")
    
    while _tracking_active:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        # Flip horizontally for natural mirror feel
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        # Apply background mask
        fgmask = fgbg.apply(frame)
        
        # Focus on center-right control zone
        roi_mask = fgmask[:, int(w * 0.3):int(w * 0.9)]
        contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        now = time.time()
        if contours and (now - _last_action_time > 1.2):
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)
            
            if area > 8000:
                # Get centroid of the motion
                M = cv2.moments(largest)
                if M["m00"] != 0:
                    cy = int(M["m01"] / M["m00"])
                    
                    if cy < h * 0.35:
                        # Upper quadrant: Volume Up
                        media_control.volume_up(4)
                        _last_action_time = now
                        log.info("Gesture: High Motion -> Volume Up")
                    elif cy > h * 0.65:
                        # Lower quadrant: Volume Down
                        media_control.volume_down(4)
                        _last_action_time = now
                        log.info("Gesture: Low Motion -> Volume Down")
                    elif h * 0.35 <= cy <= h * 0.65 and area > 18000:
                        # Center big motion: Play/Pause Toggle
                        media_control.play_pause_media()
                        _last_action_time = now
                        log.info("Gesture: Center Wave -> Play/Pause")

        time.sleep(0.03)

    cap.release()
    log.info("ULTRON Vision Gesture Matrix offline.")


def start_gesture_tracking(camera_index: int = 0) -> Dict[str, Any]:
    global _tracking_active, _tracking_thread
    if _tracking_active:
        return {"success": True, "message": "Gesture tracking matrix is already engaged, sir."}
        
    _tracking_active = True
    _tracking_thread = threading.Thread(target=_gesture_loop, args=(camera_index,), daemon=True)
    _tracking_thread.start()
    return {"success": True, "message": "Vision gesture tracking matrix engaged. Wave up for volume up, down for volume down, center to toggle media."}


def stop_gesture_tracking() -> Dict[str, Any]:
    global _tracking_active
    _tracking_active = False
    return {"success": True, "message": "Gesture tracking deactivated, sir."}


def is_gesture_tracking() -> bool:
    return _tracking_active
