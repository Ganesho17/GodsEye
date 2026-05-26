"""
surveillance/alert_visualizer.py
God's Eye — Alert Image Annotator & Screenshot Manager

Responsible for rendering annotated threat images with semantic visual overlays:
  - Colored bounding boxes per threat class/level
  - Contextual threat labels with confidence scores
  - Top/bottom HUD ribbons with camera metadata and timestamps
  - Saving both raw and annotated frames to disk

Color Semantics:
  RED    (#ef4444) → weapons, intruders, HIGH / CRITICAL threats
  ORANGE (#f97316) → suspicious activity, loitering, running
  YELLOW (#eab308) → crowd anomaly, off-peak alerts
  GREEN  (#22c55e) → normal / safe detections

Usage:
    from surveillance.alert_visualizer import AlertVisualizer
    viz = AlertVisualizer(screenshots_dir)
    annotated_path = viz.save_alert_frame(frame, detections, behaviors, level, camera_name)
"""

import cv2
import numpy as np
import os
import time
from datetime import datetime


# --- Color Palette (BGR for OpenCV) ---
COLOR_RED      = (60,  68,  239)   # RED    — weapons, intruders
COLOR_ORANGE   = (30,  115, 249)   # ORANGE — suspicious activity
COLOR_YELLOW   = (20,  179, 234)   # YELLOW — crowd anomalies
COLOR_GREEN    = (83,  197,  34)   # GREEN  — normal detection
COLOR_BLUE     = (220, 130,  59)   # BLUE   — vehicles/objects
COLOR_WHITE    = (240, 240, 240)
COLOR_DARK     = (16,  16,   16)
COLOR_TEAL     = (180, 200,  20)


def _get_class_color(cls, is_intruder=False, is_loiterer=False, is_runner=False):
    """Maps detection class + behavior flags to the appropriate BGR color."""
    if cls == 'WEAPON':
        return COLOR_RED
    if is_intruder:
        return COLOR_RED
    if is_loiterer or is_runner:
        return COLOR_ORANGE
    if cls == 'PERSON':
        return COLOR_GREEN
    if cls in ('CAR', 'MOTORCYCLE', 'TRUCK', 'BUS'):
        return COLOR_BLUE
    if cls in ('BACKPACK', 'SUITCASE'):
        return COLOR_YELLOW
    return COLOR_TEAL


def _get_level_color(level):
    """Maps threat level string to a BGR ribbon color."""
    mapping = {
        'CRITICAL': (180, 30, 220),   # Purple
        'HIGH':     COLOR_RED,
        'MEDIUM':   COLOR_ORANGE,
        'LOW':      COLOR_GREEN
    }
    return mapping.get(level, COLOR_GREEN)


class AlertVisualizer:
    """
    Renders annotated threat images and saves them to the file system.
    Creates both raw/ and annotated/ subdirectories inside screenshots_dir.
    """

    def __init__(self, screenshots_dir):
        self.screenshots_dir = screenshots_dir
        self.raw_dir = os.path.join(screenshots_dir, 'raw')
        self.annotated_dir = os.path.join(screenshots_dir, 'annotated')
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.annotated_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  PUBLIC API                                                          #
    # ------------------------------------------------------------------ #

    def save_alert_frame(self, frame, detections, behaviors, level, camera_name="CAM_0",
                         camera_id="cam_0"):
        """
        High-level entry point: annotates a frame and saves both raw and
        annotated versions to disk.

        Returns:
            dict with keys 'raw_path', 'annotated_path', 'filename_base'
            or None on failure.
        """
        try:
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            filename_base = f"alert_{camera_id}_{timestamp_str}_{level.lower()}"

            # 1. Save raw unmodified frame
            raw_filename  = f"{filename_base}_raw.jpg"
            raw_path      = os.path.join(self.raw_dir, raw_filename)
            cv2.imwrite(raw_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            # 2. Build annotated copy
            annotated_frame = frame.copy()
            self.draw_threat_boxes(annotated_frame, detections, behaviors)
            self.add_hud_overlay(annotated_frame, camera_name, level)

            annotated_filename = f"{filename_base}_annotated.jpg"
            annotated_path     = os.path.join(self.annotated_dir, annotated_filename)
            cv2.imwrite(annotated_path, annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            print(f"[AlertVisualizer] Saved alert frame: {filename_base}")
            return {
                'raw_path':       raw_path,
                'annotated_path': annotated_path,
                'raw_filename':   raw_filename,
                'annotated_filename': annotated_filename,
                'filename_base':  filename_base
            }
        except Exception as e:
            print(f"[AlertVisualizer] Error saving alert frame: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  DRAWING HELPERS                                                     #
    # ------------------------------------------------------------------ #

    def draw_threat_boxes(self, frame, detections, behaviors):
        """
        Draws colored bounding boxes with labels on the frame in-place.

        Parameters:
            frame:      OpenCV BGR image (modified in-place)
            detections: list of detection dicts from YoloDetector
            behaviors:  dict returned by BehaviorAnalyzer
        """
        intruder_ids  = set(behaviors.get('intruder_ids', []))
        loitering_ids = set(behaviors.get('loitering_ids', []))
        running_ids   = set(behaviors.get('running_ids', []))

        for det in detections:
            cls      = det.get('class', 'UNKNOWN')
            bbox     = det.get('bbox', [0, 0, 0, 0])
            conf     = det.get('conf', 0.0)
            track_id = det.get('track_id')

            x1, y1, x2, y2 = [int(v) for v in bbox]

            is_intruder  = (track_id in intruder_ids) or (-1 in intruder_ids)
            is_loiterer  = track_id in loitering_ids
            is_runner    = track_id in running_ids

            color = _get_class_color(cls, is_intruder, is_loiterer, is_runner)

            # Primary rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Corner bracket decoration for high-threat objects
            if cls == 'WEAPON' or is_intruder:
                self._draw_corner_brackets(frame, x1, y1, x2, y2, color, length=18, thickness=4)

            # Build label text — use specific weapon name (KNIFE, GUN, etc.) if available
            label = cls
            if track_id is not None:
                label += f" #{track_id}"
            if cls == 'WEAPON':
                weapon_name = det.get('weapon_name') or 'WEAPON'
                tid_str     = f" #{track_id}" if track_id else ""
                label = f"⚠ {weapon_name}{tid_str}"
            elif is_intruder:
                label = f"INTRUDER #{track_id}"
            elif is_loiterer:
                label += " [LOITERING]"
            elif is_runner:
                label += " [RUNNING]"
            label += f" {int(conf * 100)}%"

            # Draw label ribbon background
            font       = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.38
            thickness  = 1
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
            ribbon_x2  = min(x1 + tw + 12, frame.shape[1])
            cv2.rectangle(frame, (x1 - 1, y1 - 20), (ribbon_x2, y1), color, -1)
            cv2.putText(frame, label, (x1 + 5, y1 - 6),
                        font, font_scale, COLOR_DARK, thickness, cv2.LINE_AA)

    def add_hud_overlay(self, frame, camera_name, level):
        """
        Adds a top HUD ribbon (camera name, timestamp, status) and
        a bottom ribbon (threat level badge) to the frame in-place.
        """
        h, w = frame.shape[:2]
        level_color = _get_level_color(level)

        # --- Top ribbon ---
        cv2.rectangle(frame, (0, 0), (w, 28), COLOR_DARK, -1)
        cv2.line(frame, (0, 28), (w, 28), (60, 60, 60), 1)

        cv2.putText(frame, f"GOD'S EYE  //  {camera_name.upper()}",
                    (12, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 220, 100), 1, cv2.LINE_AA)

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]
        cv2.putText(frame, f"ALERT CAPTURE  {ts}",
                    (w - 280, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1, cv2.LINE_AA)

        # --- Bottom ribbon ---
        cv2.rectangle(frame, (0, h - 30), (w, h), COLOR_DARK, -1)
        cv2.line(frame, (0, h - 30), (w, h - 30), (60, 60, 60), 1)

        level_label = f"THREAT LEVEL: {level}"
        cv2.putText(frame, level_label,
                    (12, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, level_color, 1, cv2.LINE_AA)

        cv2.putText(frame, "GOD'S EYE AI SURVEILLANCE — INCIDENT CAPTURE",
                    (w // 2 - 190, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (90, 90, 90), 1, cv2.LINE_AA)

    # ------------------------------------------------------------------ #
    #  PRIVATE HELPERS                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _draw_corner_brackets(frame, x1, y1, x2, y2, color, length=16, thickness=3):
        """Draws tactical bracket corners on a bounding box."""
        pts = [
            # Top-left
            ((x1, y1 + length), (x1, y1), (x1 + length, y1)),
            # Top-right
            ((x2 - length, y1), (x2, y1), (x2, y1 + length)),
            # Bottom-left
            ((x1, y2 - length), (x1, y2), (x1 + length, y2)),
            # Bottom-right
            ((x2 - length, y2), (x2, y2), (x2, y2 - length)),
        ]
        for p in pts:
            cv2.line(frame, p[0], p[1], color, thickness)
            cv2.line(frame, p[1], p[2], color, thickness)
