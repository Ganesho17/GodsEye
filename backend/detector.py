"""
backend/detector.py
God's Eye — Multi-Camera Intelligent Detection Coordinator

Extended to support:
  - Multi-camera pipeline with per-camera thread, analyzer, threat engine, and surge detector
  - Alert Visualizer for annotated RED/ORANGE/YELLOW/GREEN screenshots
  - Smart object filtering (only surveillance-relevant YOLO classes)
  - CRITICAL threat level support
  - Crowd surge standalone module integration

Preserves full backward-compatibility with the primary camera (cam_0) singleton API.
"""

import cv2
import numpy as np
import time
import queue
import threading
import sys
import os
from datetime import datetime

# Add root folder to sys.path for modular imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from detection.yolo_detector import YoloDetector
from surveillance.behavior_analyzer import BehaviorAnalyzer
from surveillance.threat_score import ThreatScoreEngine
from surveillance.crowd_surge import CrowdSurgeDetector
from surveillance.alert_visualizer import AlertVisualizer
from surveillance.device_manager import DeviceManager, device_manager as global_device_manager
import database.database as database
from backend.mock_camera import MockCamera


# -----------------------------------------------------------------------
# Per-Camera Pipeline
# -----------------------------------------------------------------------

class CameraPipeline:
    """
    Encapsulates all detection/analytics state for a single camera feed.
    Each camera gets its own BehaviorAnalyzer, ThreatScoreEngine, etc.
    """

    def __init__(self, camera_id, camera_name, peak_start=8, peak_end=18,
                 use_mock=False, screenshots_dir=None):
        self.camera_id      = camera_id
        self.camera_name    = camera_name
        self.use_mock       = use_mock
        self.screenshots_dir = screenshots_dir or os.path.join(
            os.path.dirname(__file__), '..', 'screenshots'
        )

        # Sub-modules
        self.analyzer      = BehaviorAnalyzer()
        self.threat_engine = ThreatScoreEngine(peak_start, peak_end)
        self.surge_detector = CrowdSurgeDetector(peak_start, peak_end)
        self.visualizer    = AlertVisualizer(os.path.abspath(self.screenshots_dir))
        self.mock_cam      = MockCamera() if use_mock else None

        # Settings
        self.zone_coords        = [[0.02, 0.55], [0.45, 0.55], [0.45, 0.98], [0.02, 0.98]]
        self.crowd_threshold    = 5
        self.loitering_threshold = 10.0
        self.peak_start         = peak_start
        self.peak_end           = peak_end

        # State
        self.current_crowd_count      = 0
        self.current_threat_level     = 'LOW'
        self.current_threat_score     = 0
        self.active_intruders         = 0
        self.active_unattended_objects = 0
        self.current_item_counts      = {
            'PERSON': 0, 'WEAPON': 0, 'CAR': 0, 'MOTORCYCLE': 0,
            'TRUCK': 0, 'BUS': 0, 'BACKPACK': 0, 'SUITCASE': 0
        }
        self.active_diagnostics       = []
        self.crowd_density            = 'LOW'

        # Alert cooldowns per camera (seconds)
        self.alert_cooldowns = {
            'INTRUSION':        5.0,
            'WEAPON':           5.0,
            'CROWD_ALERT':      12.0,
            'UNATTENDED_OBJECT': 8.0,
            'VEHICLE_ALERT':    15.0,
        }
        self.last_alert_times = {k: 0.0 for k in self.alert_cooldowns}

        # SSE alert queue
        self.alert_queue   = queue.Queue(maxsize=100)

        # Frame output (thread-safe)
        self.latest_frame_bytes = None
        self._frame_lock        = threading.Lock()

        # Crowd log throttle (every 5 seconds)
        self._last_crowd_log_time = 0.0

    def get_latest_frame(self):
        with self._frame_lock:
            return self.latest_frame_bytes

    def set_latest_frame(self, jpeg_bytes):
        with self._frame_lock:
            self.latest_frame_bytes = jpeg_bytes

    def push_sse_alert(self, alert):
        """Thread-safe push to SSE queue with overflow protection."""
        try:
            if self.alert_queue.full():
                self.alert_queue.get_nowait()
            self.alert_queue.put_nowait(alert)
        except Exception as e:
            print(f"[Pipeline:{self.camera_id}] SSE push error: {e}")


# -----------------------------------------------------------------------
# Main IntelligentDetector (Multi-Camera Coordinator)
# -----------------------------------------------------------------------

class IntelligentDetector:
    """
    Singleton coordinator that manages one or more CameraPipelines.

    Backward-compatible API:
      - All existing properties (current_crowd_count, current_threat_level, etc.)
        proxy to the primary camera pipeline (cam_0).
      - Existing methods (get_latest_frame, update_settings, etc.) work unchanged.
    """

    def __init__(self):
        # Shared YOLO instance (loaded once, used across all pipelines)
        self.yolo = YoloDetector()

        # Device manager (multi-camera registry)
        self.device_manager = global_device_manager

        # Per-camera pipelines: camera_id -> CameraPipeline
        self._pipelines = {}
        self._pipelines_lock = threading.Lock()

        # Screenshots directory
        self.screenshots_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'screenshots')
        )
        os.makedirs(os.path.join(self.screenshots_dir, 'raw'),       exist_ok=True)
        os.makedirs(os.path.join(self.screenshots_dir, 'annotated'), exist_ok=True)

        # Settings (primary camera — backward compatibility)
        self.crowd_threshold    = 5
        self.use_webcam         = True
        self.peak_start         = 8
        self.peak_end           = 18
        self.loitering_threshold = 10.0
        self.zone_coords        = [[0.02, 0.55], [0.45, 0.55], [0.45, 0.98], [0.02, 0.98]]

        # Primary camera mock fallback
        self.cap      = None
        self.mock_cam = MockCamera()
        self.running  = True

        # Initialize primary camera pipeline
        self._init_primary_camera()

    # ------------------------------------------------------------------ #
    #  PIPELINE MANAGEMENT                                                 #
    # ------------------------------------------------------------------ #

    def _init_primary_camera(self):
        """Registers and starts the primary (cam_0) webcam pipeline."""
        pipeline = CameraPipeline(
            camera_id="cam_0",
            camera_name="Primary Webcam",
            peak_start=self.peak_start,
            peak_end=self.peak_end,
            use_mock=not self.use_webcam,
            screenshots_dir=self.screenshots_dir
        )
        # Try hardware webcam; fall back to mock on failure
        if self.use_webcam:
            pipeline.use_mock = False
            self._try_open_webcam()
        else:
            pipeline.use_mock = True

        with self._pipelines_lock:
            self._pipelines["cam_0"] = pipeline

        # Register in DB
        database.register_device("cam_0", "Primary Webcam", "webcam", "0", "Local System")

        # Start background thread for primary camera
        t = threading.Thread(target=self._pipeline_loop, args=("cam_0",), daemon=True)
        t.start()
        print(f"[IntelligentDetector] Primary camera pipeline started (cam_0)")

    def add_camera(self, camera_id, camera_name, device_type, source, location="Unknown"):
        """
        Registers a new camera and starts its processing pipeline.

        Parameters:
            camera_id:   Unique string ID (e.g., 'cam_1', 'phone_gate')
            camera_name: Display label
            device_type: 'webcam' | 'usb' | 'ip' | 'rtsp'
            source:      Camera index (int) or URL (str)
        """
        with self._pipelines_lock:
            if camera_id in self._pipelines:
                print(f"[IntelligentDetector] Camera {camera_id} already exists.")
                return False

            pipeline = CameraPipeline(
                camera_id=camera_id,
                camera_name=camera_name,
                peak_start=self.peak_start,
                peak_end=self.peak_end,
                use_mock=False,
                screenshots_dir=self.screenshots_dir
            )
            self._pipelines[camera_id] = pipeline

        # Register device
        self.device_manager.register_device(camera_name, device_type, source, location, camera_id)
        database.register_device(camera_id, camera_name, device_type, str(source), location)

        # Start background loop
        t = threading.Thread(target=self._pipeline_loop, args=(camera_id,), daemon=True)
        t.start()
        print(f"[IntelligentDetector] Camera pipeline started: {camera_id} ({camera_name})")
        return True

    def remove_camera(self, camera_id):
        """Stops and removes a camera pipeline (cannot remove cam_0)."""
        if camera_id == "cam_0":
            return False

        with self._pipelines_lock:
            pipeline = self._pipelines.pop(camera_id, None)

        if pipeline:
            self.device_manager.remove_device(camera_id)
            database.delete_device(camera_id)
            print(f"[IntelligentDetector] Camera {camera_id} removed.")
            return True
        return False

    def get_pipeline(self, camera_id="cam_0"):
        with self._pipelines_lock:
            return self._pipelines.get(camera_id)

    def get_all_camera_ids(self):
        with self._pipelines_lock:
            return list(self._pipelines.keys())

    # ------------------------------------------------------------------ #
    #  PROCESSING LOOP (one per camera)                                   #
    # ------------------------------------------------------------------ #

    def _pipeline_loop(self, camera_id):
        """Background frame-processing loop for a single camera."""
        print(f"[IntelligentDetector] Processing loop active for camera: {camera_id}")
        while self.running:
            start_time = time.time()
            try:
                pipeline    = self.get_pipeline(camera_id)
                if pipeline is None:
                    break  # Pipeline was removed

                jpeg_bytes  = self._process_frame(pipeline)
                pipeline.set_latest_frame(jpeg_bytes)

            except Exception as e:
                print(f"[IntelligentDetector] Error in loop [{camera_id}]: {e}")
                time.sleep(0.1)

            elapsed      = time.time() - start_time
            sleep_needed = max(0.01, 0.04 - elapsed)
            time.sleep(sleep_needed)

    def _process_frame(self, pipeline: CameraPipeline):
        """
        Core frame processing for one camera pipeline.
        Grabs frame, runs YOLO, analyzes behavior, scores threat,
        triggers alerts, renders HUD, and returns JPEG bytes.
        """
        frame      = None
        detections = []
        h, w       = 480, 640

        # ---- 1. Frame Acquisition ----
        if pipeline.camera_id == "cam_0" and not pipeline.use_mock:
            # Primary webcam path
            if self.cap is None or not self.cap.isOpened():
                self._try_open_webcam()

            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    detections = self.yolo.process_frame(frame)
                else:
                    frame, detections = pipeline.mock_cam.get_frame_and_detections() if pipeline.mock_cam else (None, [])
            else:
                if pipeline.mock_cam is None:
                    pipeline.mock_cam = MockCamera()
                frame, detections = pipeline.mock_cam.get_frame_and_detections()
        elif pipeline.camera_id == "cam_0" and pipeline.use_mock:
            # Mock mode
            poly_abs = np.array(
                [[int(pt[0] * w), int(pt[1] * h)] for pt in pipeline.zone_coords],
                dtype=np.int32
            )
            if pipeline.mock_cam is None:
                pipeline.mock_cam = MockCamera()
            frame, detections = pipeline.mock_cam.get_frame_and_detections(poly_abs)
        else:
            # Additional cameras via device_manager
            ret, frame = self.device_manager.read_frame(pipeline.camera_id)
            if ret and frame is not None:
                detections = self.yolo.process_frame(frame)
            else:
                # Fallback mock for unavailable cameras
                if pipeline.mock_cam is None:
                    pipeline.mock_cam = MockCamera()
                poly_abs = np.array(
                    [[int(pt[0] * w), int(pt[1] * h)] for pt in pipeline.zone_coords],
                    dtype=np.int32
                )
                frame, detections = pipeline.mock_cam.get_frame_and_detections(poly_abs)

        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

        height, width = frame.shape[:2]

        # ---- 2. Behavior Analysis ----
        behaviors = pipeline.analyzer.update(
            detections, pipeline.zone_coords, width, height,
            loitering_threshold=pipeline.loitering_threshold
        )

        has_weapon = any(d['class'] == 'WEAPON' for d in detections)

        # ---- 3. Threat Scoring ----
        score, level, triggers = pipeline.threat_engine.calculate_threat(
            behaviors, has_weapon, behaviors['current_person_count'], pipeline.crowd_threshold
        )

        # ---- 4. Crowd Surge Analysis ----
        surge_result = pipeline.surge_detector.update(behaviors['current_person_count'])
        if surge_result['is_surge'] and 'CROWD_SURGE' not in triggers:
            behaviors['crowd_surge'] = True
            score = min(100, score + 20)
            if score >= 70:
                level = 'CRITICAL'
            elif score >= 35:
                level = 'HIGH'

        crowd_density = surge_result['crowd_density']

        # ---- 5. Item Counts ----
        current_counts = {k: 0 for k in pipeline.current_item_counts.keys()}
        for d in detections:
            cls = d['class']
            if cls in current_counts:
                current_counts[cls] += 1

        # ---- 6. Thread-Safe State Update ----
        pipeline.current_crowd_count      = behaviors['current_person_count']
        pipeline.current_threat_level     = level
        pipeline.current_threat_score     = score
        pipeline.active_intruders         = len(behaviors['intruder_ids'])
        pipeline.active_unattended_objects = len(behaviors['unattended_items'])
        pipeline.current_item_counts      = current_counts
        pipeline.crowd_density            = crowd_density

        # Build diagnostics ticker messages
        diagnostics = []
        if has_weapon:
            diagnostics.append("⚠ WEAPON CARRIER SPOTTED")
        for tid in behaviors['intruder_ids']:
            diagnostics.append(f"INTRUDER #{tid} PERIMETER BREACH" if tid != -1 else "UNIDENTIFIED INTRUDER IN SECURE ZONE")
        for tid in behaviors['running_ids']:
            diagnostics.append(f"PERSON #{tid} ABNORMAL RUNNING SPEED")
        for tid in behaviors['loitering_ids']:
            diagnostics.append(f"PERSON #{tid} LOITERING IN AREA")
        if behaviors['crowd_surge']:
            diagnostics.append("⚠ CRITICAL CROWD SURGE DETECTED")
        if surge_result['is_outside_peak'] and behaviors['current_person_count'] > pipeline.crowd_threshold:
            diagnostics.append("⚠ OFF-PEAK CROWD LIMIT EXCEEDED (1.5× ESCALATION)")
        for item in behaviors['unattended_items']:
            diagnostics.append(f"UNATTENDED {item['class']} IN SECURE SECTOR")
        pipeline.active_diagnostics = diagnostics

        # ---- 7. Alert Logging & SSE Broadcast ----
        self._evaluate_and_log_alerts(pipeline, frame, detections, behaviors, score, level, has_weapon, surge_result)

        # ---- 8. Crowd History Logging (throttled to every 5s) ----
        current_time = time.time()
        if current_time - pipeline._last_crowd_log_time >= 5.0:
            pipeline._last_crowd_log_time = current_time
            database.log_crowd(pipeline.camera_id, behaviors['current_person_count'], crowd_density)

        # ---- 9. HUD Rendering ----
        frame = self._render_hud(frame, pipeline, detections, behaviors, level, score, current_counts)

        # ---- 10. Compress to JPEG ----
        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return jpeg.tobytes()

    def _evaluate_and_log_alerts(self, pipeline, frame, detections, behaviors, score, level, has_weapon, surge_result):
        """Determines if an alert should be logged and broadcast."""
        current_time  = time.time()
        incident_type = None
        description   = None
        explanation   = None

        if level in ('HIGH', 'CRITICAL'):
            if len(behaviors['intruder_ids']) > 0:
                incident_type = 'INTRUSION'
                description   = f"RESTRICTED AREA INTRUSION: {len(behaviors['intruder_ids'])} suspect(s) breached secure perimeter."
                explanation   = f"Person(s) detected inside the restricted zone. Track IDs: {behaviors['intruder_ids']}."
            elif has_weapon:
                # Collect all specific weapon names detected in this frame
                weapon_names = list(set(
                    d.get('weapon_name') or 'WEAPON'
                    for d in detections if d['class'] == 'WEAPON'
                ))
                weapon_label  = ', '.join(weapon_names) if weapon_names else 'WEAPON'
                incident_type = 'WEAPON'
                description   = f"WEAPON DETECTED: {weapon_label} identified on camera. Suspect is armed."
                explanation   = f"Detected weapon(s): {weapon_label}. YOLOv8 flagged this as a high-threat object. Immediate response required."
            elif behaviors.get('crowd_surge'):
                incident_type = 'CROWD_ALERT'
                description   = f"CROWD SURGE: {behaviors['current_person_count']} people gathered rapidly."
                explanation   = f"Crowd count jumped by {surge_result['count_delta']} persons in {pipeline.surge_detector.surge_window_sec:.1f}s."
            else:
                incident_type = 'INTRUSION'
                description   = "HIGH RISK BREACH: Threat score threshold exceeded."
                explanation   = f"Multiple threat factors active: {', '.join(behaviors.get('triggers', []))}."
        elif level in ('MEDIUM', 'LOW'):
            if len(behaviors.get('intruder_ids', [])) > 0:
                incident_type = 'INTRUSION'
                description   = f"RESTRICTED AREA INTRUSION: {len(behaviors['intruder_ids'])} suspect(s) breached secure perimeter."
                explanation   = f"Person(s) detected inside the restricted zone. Track IDs: {behaviors['intruder_ids']}."
            elif len(behaviors.get('unattended_items', [])) > 0:
                incident_type = 'UNATTENDED_OBJECT'
                item_names    = list(set(item['class'] for item in behaviors['unattended_items']))
                description   = f"UNATTENDED OBJECT(S) DETECTED: {', '.join(item_names)} in secure zone."
                explanation   = "Objects left unattended in the restricted area. Possible abandoned item threat."
            elif behaviors.get('current_person_count', 0) > pipeline.crowd_threshold:
                incident_type = 'CROWD_ALERT'
                description   = f"CROWD COUNT EXCEEDED: {behaviors['current_person_count']} persons (max: {pipeline.crowd_threshold})."
                explanation   = f"Current occupancy ({behaviors['current_person_count']}) exceeds configured limit ({pipeline.crowd_threshold})."
            elif len(behaviors.get('running_ids', [])) > 0:
                incident_type = 'SUSPICIOUS_BEHAVIOR'
                description   = f"SUSPICIOUS BEHAVIOR: Fast movement / running detected."
                explanation   = f"Person(s) running abnormally fast. Track IDs: {behaviors['running_ids']}."
            elif len(behaviors.get('loitering_ids', [])) > 0:
                incident_type = 'SUSPICIOUS_BEHAVIOR'
                description   = f"SUSPICIOUS BEHAVIOR: Loitering detected."
                explanation   = f"Person(s) loitering in area. Track IDs: {behaviors['loitering_ids']}."

        if incident_type and (current_time - pipeline.last_alert_times.get(incident_type, 0) > pipeline.alert_cooldowns.get(incident_type, 5.0)):
            pipeline.last_alert_times[incident_type] = current_time

            # Save annotated + raw screenshots
            viz_result = pipeline.visualizer.save_alert_frame(
                frame, detections, behaviors, level,
                camera_name=pipeline.camera_name,
                camera_id=pipeline.camera_id
            )

            raw_path       = viz_result['raw_path']       if viz_result else None
            annotated_path = viz_result['annotated_path'] if viz_result else None

            # Write to database
            db_record = database.add_incident(
                threat_type=incident_type,
                threat_score=score,
                threat_level=level,
                crowd_count=behaviors['current_person_count'],
                screenshot_path=raw_path,
                camera_id=pipeline.camera_id,
                camera_name=pipeline.camera_name,
                annotated_path=annotated_path,
                explanation=explanation
            )

            db_record['description']   = description
            db_record['summary']       = explanation
            db_record['snapshot']      = f"/api/screenshots/raw/{os.path.basename(raw_path)}"       if raw_path       else None
            db_record['annotated_url'] = f"/api/screenshots/annotated/{os.path.basename(annotated_path)}" if annotated_path else None

            pipeline.push_sse_alert(db_record)

    def _render_hud(self, frame, pipeline, detections, behaviors, level, score, current_counts):
        """Renders the premium high-tech HUD overlays onto the frame."""
        height, width = frame.shape[:2]
        polygon = np.array(
            [[int(pt[0] * width), int(pt[1] * height)] for pt in pipeline.zone_coords],
            dtype=np.int32
        )

        # A. Restricted Zone Polygon
        zone_color = (60, 220, 60)
        if level == 'MEDIUM':
            zone_color = (40, 140, 240)
        elif level in ('HIGH', 'CRITICAL'):
            zone_color = (50, 50, 255) if int(time.time() * 2.5) % 2 == 0 else (20, 20, 140)

        if len(polygon) > 0:
            overlay = frame.copy()
            cv2.fillPoly(overlay, [polygon], zone_color)
            cv2.polylines(frame, [polygon], True, zone_color, 2)
            cv2.addWeighted(overlay, 0.16, frame, 0.84, 0, frame)

        # B. Detection Bounding Boxes
        intruder_ids  = set(behaviors.get('intruder_ids', []))
        loitering_ids = set(behaviors.get('loitering_ids', []))
        running_ids   = set(behaviors.get('running_ids', []))

        for d in detections:
            cls      = d['class']
            x1, y1, x2, y2 = d['bbox']
            conf     = d['conf']
            track_id = d['track_id']

            is_intruder  = (track_id in intruder_ids) or (-1 in intruder_ids)
            is_loiterer  = track_id in loitering_ids
            is_runner    = track_id in running_ids

            # Color logic
            from detection.yolo_detector import YoloDetector as YD
            color = YD.CLASS_COLORS.get(cls, (200, 200, 200))
            if cls == 'WEAPON':
                color = (50, 50, 255)
            elif is_intruder:
                color = (50, 50, 255)
            elif is_loiterer or is_runner:
                color = (40, 140, 240)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            if cls == 'WEAPON' or is_intruder:
                l = 16
                cv2.line(frame, (x1, y1), (x1 + l, y1), color, 4)
                cv2.line(frame, (x1, y1), (x1, y1 + l), color, 4)
                cv2.line(frame, (x2, y2), (x2 - l, y2), color, 4)
                cv2.line(frame, (x2, y2), (x2, y2 - l), color, 4)

            lbl = cls
            if track_id is not None:
                lbl += f" #{track_id}"
            if cls == 'WEAPON':
                # Show specific weapon type: KNIFE, GUN, SCISSORS, BOTTLE, etc.
                weapon_name = d.get('weapon_name') or 'WEAPON'
                tid_str     = f" #{track_id}" if track_id else ""
                lbl = f"⚠ {weapon_name}{tid_str}"
            elif is_intruder:
                lbl = f"INTRUDER #{track_id}"
            elif is_loiterer:
                lbl += " [LOITERING]"
            elif is_runner:
                lbl += " [RUNNING]"
            lbl += f" {int(conf * 100)}%"

            ts = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)[0]
            cv2.rectangle(frame, (x1 - 1, y1 - 20), (x1 + ts[0] + 10, y1), color, -1)
            cv2.putText(frame, lbl, (x1 + 5, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        # C. Top HUD ribbon
        cv2.rectangle(frame, (0, 0), (width, 24), (16, 16, 16), -1)
        cv2.line(frame, (0, 24), (width, 24), (60, 60, 60), 1)
        cv2.putText(frame, f"FEED // {pipeline.camera_name.upper()}", (15, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 255, 120), 1, cv2.LINE_AA)
        model_status = "YOLOv8n: ACTIVE" if self.yolo.model_loaded else "YOLOv8n: LOADING..."
        cv2.putText(frame, model_status, (160, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)
        ts_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]
        cv2.putText(frame, f"TIME: {ts_text}", (width - 225, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)

        # D. Bottom HUD ribbon
        cv2.rectangle(frame, (0, height - 32), (width, height), (16, 16, 16), -1)
        cv2.line(frame, (0, height - 32), (width, height - 32), (60, 60, 60), 1)
        cv2.putText(frame, f"PEOPLE: {behaviors['current_person_count']:02d}", (15, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 220, 220), 1, cv2.LINE_AA)

        counts_str = f"WEAPON:{current_counts.get('WEAPON',0)}  CAR:{current_counts.get('CAR',0)}  MOTO:{current_counts.get('MOTORCYCLE',0)}  BAG:{current_counts.get('BACKPACK',0)}  SUIT:{current_counts.get('SUITCASE',0)}"
        cv2.putText(frame, counts_str, (110, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (160, 160, 160), 1, cv2.LINE_AA)

        t_color = (120, 255, 120)
        if level == 'MEDIUM':
            t_color = (40, 170, 255)
        elif level == 'HIGH':
            t_color = (60, 60, 255)
        elif level == 'CRITICAL':
            t_color = (180, 30, 220)
        cv2.putText(frame, f"THREAT: {level} ({score:02d}/100)", (width - 215, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, t_color, 1, cv2.LINE_AA)

        return frame

    # ------------------------------------------------------------------ #
    #  BACKWARD-COMPATIBLE PRIMARY CAMERA API                             #
    # ------------------------------------------------------------------ #

    def _try_open_webcam(self):
        try:
            self.cap = cv2.VideoCapture(0)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print("[IntelligentDetector] Webcam opened successfully.")
            else:
                self.cap = None
                self.use_webcam = False
                p = self.get_pipeline("cam_0")
                if p:
                    p.use_mock = True
                print("[IntelligentDetector] Webcam unavailable. Falling back to mock simulation.")
        except Exception as e:
            print(f"[IntelligentDetector] Webcam init error: {e}")
            self.cap = None
            self.use_webcam = False

    @property
    def current_crowd_count(self):
        p = self.get_pipeline("cam_0")
        return p.current_crowd_count if p else 0

    @property
    def current_threat_level(self):
        p = self.get_pipeline("cam_0")
        return p.current_threat_level if p else 'LOW'

    @property
    def current_threat_score(self):
        p = self.get_pipeline("cam_0")
        return p.current_threat_score if p else 0

    @property
    def active_intruders(self):
        p = self.get_pipeline("cam_0")
        return p.active_intruders if p else 0

    @property
    def active_unattended_objects(self):
        p = self.get_pipeline("cam_0")
        return p.active_unattended_objects if p else 0

    @property
    def current_item_counts(self):
        p = self.get_pipeline("cam_0")
        return p.current_item_counts if p else {}

    @property
    def unattended_item_counts(self):
        p = self.get_pipeline("cam_0")
        return {} if not p else {k: v for k, v in p.current_item_counts.items() if v > 0}

    @property
    def active_diagnostics(self):
        p = self.get_pipeline("cam_0")
        return p.active_diagnostics if p else []

    @property
    def alert_queue(self):
        p = self.get_pipeline("cam_0")
        return p.alert_queue if p else queue.Queue()

    def get_latest_frame(self, camera_id="cam_0"):
        p = self.get_pipeline(camera_id)
        return p.get_latest_frame() if p else None

    def update_settings(self, settings, camera_id="cam_0"):
        """Updates configuration for a specific camera pipeline."""
        p = self.get_pipeline(camera_id)
        if not p:
            return

        if 'crowd_threshold' in settings:
            p.crowd_threshold    = int(settings['crowd_threshold'])
            self.crowd_threshold = p.crowd_threshold
        if 'zone_coords' in settings:
            p.zone_coords    = settings['zone_coords']
            self.zone_coords = p.zone_coords
        if 'peak_start' in settings:
            p.peak_start = int(settings['peak_start'])
            p.threat_engine.peak_start = p.peak_start
            p.surge_detector.peak_start = p.peak_start
        if 'peak_end' in settings:
            p.peak_end = int(settings['peak_end'])
            p.threat_engine.peak_end = p.peak_end
            p.surge_detector.peak_end = p.peak_end
        if 'loitering_threshold' in settings:
            p.loitering_threshold    = float(settings['loitering_threshold'])
            self.loitering_threshold = p.loitering_threshold
        if 'use_webcam' in settings:
            new_mode = bool(settings['use_webcam'])
            if camera_id == "cam_0" and new_mode != self.use_webcam:
                self.use_webcam = new_mode
                p.use_mock      = not new_mode
                if not new_mode and self.cap is not None:
                    self.cap.release()
                    self.cap = None
                elif new_mode:
                    self._try_open_webcam()

    def get_camera_stats(self, camera_id="cam_0"):
        """Returns a JSON-serializable stats dict for the specified camera."""
        p = self.get_pipeline(camera_id)
        if not p:
            return {}
        return {
            'camera_id':              camera_id,
            'camera_name':            p.camera_name,
            'crowd_count':            p.current_crowd_count,
            'threat_level':           p.current_threat_level,
            'threat_score':           p.current_threat_score,
            'active_intruders':       p.active_intruders,
            'active_unattended':      p.active_unattended_objects,
            'item_counts':            p.current_item_counts,
            'active_diagnostics':     p.active_diagnostics,
            'crowd_density':          p.crowd_density,
            'crowd_threshold':        p.crowd_threshold,
            'zone_coords':            p.zone_coords,
            'loitering_threshold':    p.loitering_threshold,
            'peak_start':             p.peak_start,
            'peak_end':               p.peak_end,
            'yolo_loaded':            self.yolo.model_loaded,
            'use_webcam':             not p.use_mock
        }

    def __del__(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()