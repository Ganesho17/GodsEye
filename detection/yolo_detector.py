"""
detection/yolo_detector.py
God's Eye — YOLOv8 Object Detection & Tracking Engine

Fix: Knife / small weapon detection improvements:
  - Lowered WEAPON confidence threshold from 0.30 -> 0.15 (knives are small and low-confidence)
  - Added class 42 (fork) and 44 (spoon) as additional WEAPON proxies (YOLOv8 often
    confuses held knives/weapons with adjacent COCO cutlery classes)
  - Added class 39 (bottle) as WEAPON proxy for thrown/held bottle threats
  - Decoupled WEAPON confidence threshold from general MIN_CONFIDENCE
  - Added iou_threshold tuning for better small-object overlap handling
"""

import cv2
import numpy as np
import threading
from ultralytics import YOLO


# ==========================================================================
# SURVEILLANCE CLASS WHITELIST
# Only these COCO class indices will be processed. All others are discarded.
# ==========================================================================
ALLOWED_COCO_INDICES = {
    0,   # person
    2,   # car
    3,   # motorcycle
    5,   # bus
    7,   # truck
    24,  # backpack
    26,  # handbag
    28,  # suitcase
    39,  # bottle          -> WEAPON proxy (thrown bottle / improvised weapon)
    42,  # fork            -> WEAPON proxy (YOLOv8 frequently confuses knife with fork)
    43,  # knife           -> WEAPON  ← PRIMARY knife class
    44,  # spoon           -> WEAPON proxy (adjacent class to knife; avoids misses)
    76,  # scissors        -> WEAPON proxy (sharp object)
    67,  # cell phone      -> WEAPON proxy (resembles pistol grip in overhead CCTV)
    77,  # teddy bear      -> SUITCASE (luggage context)
}

# Classes that map to WEAPON — used for lower confidence threshold
WEAPON_COCO_INDICES = {39, 42, 43, 44, 76, 67}


class YoloDetector:
    """
    Wraps a YOLOv8 model with multi-object tracking (ByteTrack/BoT-SORT).
    Filters detections to surveillance-relevant classes only.

    Key fix: weapon-class detections use a lower confidence threshold (0.15)
    to catch knives and small held objects that are otherwise suppressed.
    """

    # ------------------------------------------------------------------
    # COCO index -> GodsEye custom class mapping
    # ------------------------------------------------------------------
    YOLO_TO_CUSTOM_MAP = {
        0:  'PERSON',
        2:  'CAR',
        3:  'MOTORCYCLE',
        5:  'BUS',
        7:  'TRUCK',
        24: 'BACKPACK',
        26: 'BACKPACK',    # handbag -> backpack
        28: 'SUITCASE',
        39: 'WEAPON',      # bottle  -> improvised weapon proxy
        42: 'WEAPON',      # fork    -> knife/weapon proxy (common YOLOv8 confusion)
        43: 'WEAPON',      # knife   -> WEAPON (primary)
        44: 'WEAPON',      # spoon   -> knife-adjacent proxy
        67: 'WEAPON',      # cell phone -> pistol proxy in overhead angle
        76: 'WEAPON',      # scissors -> sharp weapon proxy
        77: 'SUITCASE',    # teddy bear -> luggage
    }

    # ------------------------------------------------------------------
    # COCO index -> Specific weapon display name
    # Used for HUD labels and alert descriptions
    # ------------------------------------------------------------------
    WEAPON_NAME_MAP = {
        39: 'BOTTLE',               # thrown/held bottle — improvised weapon
        42: 'KNIFE (PROXY/FORK)',   # fork misclassified as knife (YOLOv8 confusion)
        43: 'KNIFE',                # primary knife class
        44: 'KNIFE (PROXY/SPOON)',  # spoon misclassified as knife (adjacent class)
        67: 'GUN PROXY (PHONE)',    # cell phone from overhead angle resembles pistol grip
        76: 'SCISSORS',             # sharp bladed object
    }

    # ------------------------------------------------------------------
    # HUD color definitions (BGR for OpenCV)
    # ------------------------------------------------------------------
    CLASS_COLORS = {
        'PERSON':     (255, 240,   0),   # Cyan-Yellow
        'WEAPON':     ( 50,  50, 255),   # Hot Neon Red
        'CAR':        (200, 150,  50),   # Warm Blue
        'MOTORCYCLE': (180, 120,  80),   # Dusty Blue
        'BUS':        (160, 100, 100),   # Muted Indigo
        'TRUCK':      (140,  80, 120),   # Muted Purple
        'BACKPACK':   ( 40, 200, 200),   # Teal
        'SUITCASE':   ( 60, 180, 220),   # Orange-Teal
    }

    def __init__(self, model_path="models/yolov8s.pt"):
        import os
        if not os.path.isabs(model_path):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            self.model_path = os.path.join(base_dir, model_path)
        else:
            self.model_path = model_path
        self.model        = None
        self.model_loaded = False
        self.lock         = threading.Lock()

        # General minimum confidence for non-weapon classes
        self.MIN_CONFIDENCE = 0.30

        # Lower threshold for weapons — knives are small and typically
        # detected at 0.15–0.25 confidence range
        self.WEAPON_CONFIDENCE = 0.15

        # IOU threshold for NMS
        self.IOU_THRESHOLD = 0.45

        # Launch model loading in background thread for zero-blocking startup
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        """Loads YOLOv8 weights in the background for instant startup."""
        try:
            print(f"[YoloDetector] Loading model from {self.model_path}...")
            # Automatically download yolov8s.pt if not present, and cache it
            loaded_model = YOLO(self.model_path)
            with self.lock:
                self.model        = loaded_model
                self.model_loaded = True
            print("[YoloDetector] YOLOv8 model loaded and ready.")
        except Exception as e:
            print(f"[YoloDetector] Error loading model: {e}")

    def process_frame(self, frame):
        """
        Runs YOLOv8 tracking inference in a single high-performance pass.
        
        Uses WEAPON_CONFIDENCE (0.15) to ensure we capture small objects like knives,
        and post-filters non-weapon classes using MIN_CONFIDENCE (0.30) to avoid false positives.

        Returns:
            List of detection dicts:
            {
                'track_id': int or None,
                'class':    str,
                'bbox':     [x1, y1, x2, y2],
                'conf':     float,
                'feet':     (px, py)
            }
        """
        parsed_detections = []
        if frame is None:
            return parsed_detections

        with self.lock:
            if not self.model_loaded or self.model is None:
                return parsed_detections

            try:
                # Run single-pass tracking at the lowest threshold (0.15)
                # This ensures small weapons aren't pre-filtered out by NMS.
                track_results = self.model.track(
                    frame,
                    persist=True,
                    verbose=False,
                    conf=self.WEAPON_CONFIDENCE,
                    iou=self.IOU_THRESHOLD
                )

                if len(track_results) > 0 and track_results[0].boxes is not None:
                    for box in track_results[0].boxes:
                        cls_idx = int(box.cls[0].item())
                        if cls_idx not in ALLOWED_COCO_INDICES:
                            continue
                        
                        custom_cls = self.YOLO_TO_CUSTOM_MAP.get(cls_idx)
                        if custom_cls is None:
                            continue
                        
                        conf = float(box.conf[0].item())
                        
                        # Post-filter non-weapon classes with a higher threshold (0.30)
                        # to maintain high precision and prevent noise/false positives.
                        is_weapon = cls_idx in WEAPON_COCO_INDICES
                        gate_conf = self.WEAPON_CONFIDENCE if is_weapon else self.MIN_CONFIDENCE
                        if conf < gate_conf:
                            continue

                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                        track_id = int(box.id[0].item()) if box.id is not None else None
                        weapon_name = self.WEAPON_NAME_MAP.get(cls_idx) if is_weapon else None

                        parsed_detections.append({
                            'track_id':   track_id,
                            'class':      custom_cls,
                            'weapon_name': weapon_name,
                            'bbox':       [x1, y1, x2, y2],
                            'conf':       conf,
                            'feet':       (int((x1 + x2) / 2), int(y2))
                        })

            except Exception as e:
                print(f"[YoloDetector] Inference exception: {e}")

        return parsed_detections

    @staticmethod
    def _iou(boxA, boxB):
        """
        Computes Intersection over Union between two bounding boxes.
        boxes are [x1, y1, x2, y2] format.
        """
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        inter_w = max(0, xB - xA)
        inter_h = max(0, yB - yA)
        inter   = inter_w * inter_h

        if inter == 0:
            return 0.0

        areaA = max(1, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
        areaB = max(1, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))
        union = areaA + areaB - inter

        return inter / union