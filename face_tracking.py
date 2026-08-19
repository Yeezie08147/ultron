"""
face_tracking.py — ULTRON Digital Face Tracking & Video Stabilization.

Software-based alternatives to hardware gimbal tracking and gyro stabilization:
  - Face tracking: detects face via Haar cascades, digitally crops/pans to center
  - Video stabilization: uses optical flow to smooth out camera shake

Runs as a background thread, can be started/stopped via voice commands.
"""

import cv2
import numpy as np
import threading
import logging
import time
from typing import Optional

log = logging.getLogger("jarvis.facetrack")

# Global state
_tracking_thread: Optional[threading.Thread] = None
_tracking_active = False
_stabilization_enabled = False


class FaceTracker:
    """Digital face tracking — crops webcam feed to keep face centered."""
    
    def __init__(self, camera_index: int = 0, zoom_factor: float = 1.5,
                 smoothing: float = 0.15, output_width: int = 1280, output_height: int = 720):
        self.camera_index = camera_index
        self.zoom_factor = zoom_factor
        self.smoothing = smoothing  # lower = smoother panning
        self.output_width = output_width
        self.output_height = output_height
        
        # Face detector (Haar cascade — fast, reliable, no mediapipe needed)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Smoothed center position
        self.smooth_x = 0.5
        self.smooth_y = 0.5
        
        # Stabilization state
        self.prev_gray = None
        self.transforms = []
    
    def _detect_face(self, frame):
        """Detect the largest face in frame, return (cx, cy, w, h) normalized."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = frame.shape[:2]
        
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        
        if len(faces) == 0:
            return None
        
        # Pick the largest face
        largest = max(faces, key=lambda f: f[2] * f[3])
        fx, fy, fw, fh = largest
        
        # Return normalized center
        cx = (fx + fw / 2) / w
        cy = (fy + fh / 2) / h
        return (cx, cy, fw / w, fh / h)
    
    def _crop_around_center(self, frame, cx, cy):
        """Crop a region around (cx, cy) with the zoom factor applied."""
        h, w = frame.shape[:2]
        crop_w = int(w / self.zoom_factor)
        crop_h = int(h / self.zoom_factor)
        
        # Calculate crop origin
        x1 = int(cx * w - crop_w / 2)
        y1 = int(cy * h - crop_h / 2)
        
        # Clamp to frame bounds
        x1 = max(0, min(x1, w - crop_w))
        y1 = max(0, min(y1, h - crop_h))
        
        cropped = frame[y1:y1 + crop_h, x1:x1 + crop_w]
        return cv2.resize(cropped, (self.output_width, self.output_height))
    
    def _stabilize_frame(self, frame):
        """Simple optical-flow-based digital stabilization."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if self.prev_gray is None:
            self.prev_gray = gray
            return frame
        
        # Estimate motion between frames
        try:
            transform = cv2.estimateRigidTransform(self.prev_gray, gray, False)
            if transform is None:
                # Try the newer API
                warp_matrix = np.eye(2, 3, dtype=np.float32)
                try:
                    _, warp_matrix = cv2.findTransformECC(
                        self.prev_gray, gray, warp_matrix, cv2.MOTION_EUCLIDEAN
                    )
                except cv2.error:
                    self.prev_gray = gray
                    return frame
                transform = warp_matrix
        except Exception:
            # Fallback: use feature matching
            self.prev_gray = gray
            return frame
        
        # Extract translation
        dx = transform[0, 2]
        dy = transform[1, 2]
        
        # Smooth the motion (keep 95% of original, dampen 5%)
        smooth_dx = dx * 0.05
        smooth_dy = dy * 0.05
        
        # Build correction matrix
        correction = np.float32([[1, 0, -smooth_dx], [0, 1, -smooth_dy]])
        stabilized = cv2.warpAffine(frame, correction, (frame.shape[1], frame.shape[0]))
        
        self.prev_gray = gray
        return stabilized
    
    def process_frame(self, frame):
        """Process one frame: detect face, crop/pan, optionally stabilize."""
        # Detect face
        face = self._detect_face(frame)
        
        if face is not None:
            cx, cy, fw, fh = face
            # Smooth the center position (exponential moving average)
            self.smooth_x += (cx - self.smooth_x) * self.smoothing
            self.smooth_y += (cy - self.smooth_y) * self.smoothing
        
        # Crop around smoothed center
        result = self._crop_around_center(frame, self.smooth_x, self.smooth_y)
        
        # Apply stabilization if enabled
        if _stabilization_enabled:
            result = self._stabilize_frame(result)
        
        return result


def _tracking_loop(camera_index: int = 0):
    """Main tracking loop — runs in a background thread."""
    global _tracking_active
    
    tracker = FaceTracker(camera_index=camera_index)
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        log.error("Cannot open webcam")
        _tracking_active = False
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    log.info("Face tracking started")
    
    while _tracking_active:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue
        
        result = tracker.process_frame(frame)
        cv2.imshow("ULTRON - Face Tracking", result)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord('q'):  # ESC or Q to quit
            break
    
    cap.release()
    cv2.destroyAllWindows()
    _tracking_active = False
    log.info("Face tracking stopped")


def start_tracking(camera_index: int = 0):
    """Start face tracking in background thread."""
    global _tracking_thread, _tracking_active
    
    if _tracking_active:
        return "Face tracking is already running."
    
    _tracking_active = True
    _tracking_thread = threading.Thread(target=_tracking_loop, args=(camera_index,), daemon=True)
    _tracking_thread.start()
    return "Face tracking activated."


def stop_tracking():
    """Stop face tracking."""
    global _tracking_active
    _tracking_active = False
    return "Face tracking deactivated."


def toggle_stabilization(enable: bool = True):
    """Toggle digital video stabilization."""
    global _stabilization_enabled
    _stabilization_enabled = enable
    state = "enabled" if enable else "disabled"
    return f"Video stabilization {state}."


def is_tracking() -> bool:
    return _tracking_active
