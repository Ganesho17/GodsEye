import cv2
import numpy as np
import time
import queue
import threading
import sys
import os
from datetime import datetime

# Add root folder to sys.path to enable modular package imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from detection.yolo_detector import YoloDetector
from surveillance.behavior_analyzer import BehaviorAnalyzer
from surveillance.threat_score import ThreatScoreEngine
import database.database as database
from backend.mock_camera import MockCamera

class IntelligentDetector:
    def __init__(self):
        # Default restricted zone as normalized coordinates
        self.zone_coords = [
            [0.50, 0.38],
            [0.93, 0.38],
            [0.93, 0.88],
            [0.62, 0.88]
        ]
        
        # Threat settings with thread safety
        self.crowd_threshold = 5
        self.use_webcam = True
        self.peak_start = 8
        self.peak_end = 18
        self.loitering_threshold = 10.0
        
        # State variables
        self.current_crowd_count = 0
        self.current_threat_level = "LOW"
        self.current_threat_score = 0
        self.active_intruders = 0
        self.active_unattended_objects = 0
        
        # Custom ontology counts
        self.current_item_counts = {
            'PERSON': 0, 'WEAPON': 0, 'LAPTOP': 0, 'BOTTLE': 0, 'NOTEBOOK': 0, 'PEN': 0, 'KEYS': 0
        }
        self.unattended_item_counts = {
            'BOTTLE': 0, 'WEAPON': 0, 'LAPTOP': 0, 'NOTEBOOK': 0, 'PEN': 0, 'KEYS': 0
        }
        
        self.active_diagnostics = []  # Detailed ticker array for frontend
        
        # Alert Cooldowns to prevent log spamming (seconds)
        self.alert_cooldowns = {
            'INTRUSION': 5.0,
            'WEAPON': 5.0,
            'CROWD_ALERT': 12.0,
            'UNATTENDED_OBJECT': 8.0
        }
        self.last_alert_times = {k: 0.0 for k in self.alert_cooldowns.keys()}
        
        # Alert Queue for Server-Sent Events (SSE)
        self.alert_queue = queue.Queue(maxsize=100)
        
        # Directory paths
        self.screenshots_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../screenshots'))
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # Lock for resource safety
        self.lock = threading.Lock()
        
        # Sub-modules
        self.yolo = YoloDetector()
        self.analyzer = BehaviorAnalyzer()
        self.threat_engine = ThreatScoreEngine(self.peak_start, self.peak_end)
        self.mock_cam = MockCamera()
        
        self.cap = None
        self.running = True
        self.latest_frame_bytes = None
        
        # Start the background frame-processing thread loop
        self.processing_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.processing_thread.start()

    def _run_loop(self):
        """Frame grabber and core processor background thread loop running at ~25 FPS."""
        print("GodsEye Surveillance: Background camera frame processing thread active.")
        while self.running:
            start_time = time.time()
            try:
                frame_bytes = self.process_frame()
                with self.lock:
                    self.latest_frame_bytes = frame_bytes
            except Exception as e:
                print(f"Error in background frame processing loop: {e}")
                time.sleep(0.1)
                
            elapsed = time.time() - start_time
            sleep_needed = max(0.01, 0.04 - elapsed)
            time.sleep(sleep_needed)

    def get_latest_frame(self):
        """Returns the most recent analyzed JPEG bytes thread-safely."""
        with self.lock:
            return self.latest_frame_bytes

    def update_settings(self, settings):
        """Updates configurations dynamically from the API panel."""
        with self.lock:
            if 'crowd_threshold' in settings:
                self.crowd_threshold = int(settings['crowd_threshold'])
            if 'zone_coords' in settings:
                self.zone_coords = settings['zone_coords']
            if 'peak_start' in settings:
                self.peak_start = int(settings['peak_start'])
                self.threat_engine.peak_start = self.peak_start
            if 'peak_end' in settings:
                self.peak_end = int(settings['peak_end'])
                self.threat_engine.peak_end = self.peak_end
            if 'loitering_threshold' in settings:
                self.loitering_threshold = float(settings['loitering_threshold'])
                
            if 'use_webcam' in settings:
                new_mode = bool(settings['use_webcam'])
                if new_mode != self.use_webcam:
                    self.use_webcam = new_mode
                    if not self.use_webcam and self.cap is not None:
                        self.cap.release()
                        self.cap = None
                    elif self.use_webcam:
                        self.init_webcam()

    def init_webcam(self):
        """Tries to boot camera 0, falling back to Mock synthetic mode if offline."""
        try:
            print("GodsEye: Attempting to capture webcam device (camera index 0)...")
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("Warning: Bypassing hardware. Camera 0 was not found. Switching to Synthetic Mock.")
                self.use_webcam = False
                self.cap = None
            else:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                print("GodsEye: Webcam capture successfully opened.")
        except Exception as e:
            print(f"Webcam initialization error: {e}, fallback to synthetic.")
            self.use_webcam = False
            self.cap = None

    def trigger_sse_alert(self, alert):
        """Pushes a new security incident alert record to the SSE queue."""
        try:
            if self.alert_queue.full():
                self.alert_queue.get_nowait()
            self.alert_queue.put_nowait(alert)
        except Exception as e:
            print(f"SSE Alert push error: {e}")

    def save_alert_screenshot(self, frame, level):
        """Grabs the active OpenCV visual frame and writes a JPEG to screenshots folder."""
        try:
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"alert_{timestamp_str}_{level.lower()}.jpg"
            full_path = os.path.join(self.screenshots_dir, filename)
            
            # Save visual image
            cv2.imwrite(full_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            print(f"GodsEye: Successfully saved breach capture snapshot to {full_path}")
            return full_path
        except Exception as e:
            print(f"Error saving alert screenshot: {e}")
            return None

    def process_frame(self):
        """
        Grabs real or mock frames, computes detections, evaluates suspicious activities,
        scores threats, logs breaches with snapshots on disk, renders premium HUD text overlay,
        and returns compressed raw JPEG bytes.
        """
        frame = None
        detections = []
        h, w = 480, 640
        
        # 1. Grab Frame & Raw Detections
        if self.use_webcam:
            if self.cap is None or not self.cap.isOpened():
                self.init_webcam()
                
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    # Run YOLOv8 detection
                    detections = self.yolo.process_frame(frame)
                else:
                    # Capture failed, fallback to mock frame
                    frame, detections = self.mock_cam.get_frame_and_detections()
            else:
                frame, detections = self.mock_cam.get_frame_and_detections()
        else:
            # Map normalized boundary coordinates into absolute values for the mock simulation
            poly_abs = np.array([[int(pt[0] * w), int(pt[1] * h)] for pt in self.zone_coords], dtype=np.int32)
            frame, detections = self.mock_cam.get_frame_and_detections(poly_abs)

        if frame is None:
            # Placeholder frame in case of extreme errors
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
        height, width = frame.shape[:2]
        
        # 2. Get absolute boundary polygon
        polygon = np.array([[int(pt[0] * width), int(pt[1] * height)] for pt in self.zone_coords], dtype=np.int32)
        
        # 3. Analyze Spatial Behavior Tracker
        behaviors = self.analyzer.update(
            detections, self.zone_coords, width, height, 
            loitering_threshold=self.loitering_threshold
        )
        
        # Check weapon presence
        has_weapon = any(d['class'] == 'WEAPON' for d in detections)
        
        # 4. Formulate threat score and map level
        score, level, triggers = self.threat_engine.calculate_threat(
            behaviors, has_weapon, behaviors['current_person_count'], self.crowd_threshold
        )
        
        # Count classes
        current_counts = {k: 0 for k in self.current_item_counts.keys()}
        for d in detections:
            cls = d['class']
            if cls in current_counts:
                current_counts[cls] += 1
                
        # Count unattended items inside restricted zone
        unattended_counts = {k: 0 for k in self.unattended_item_counts.keys()}
        for item in behaviors['unattended_items']:
            cls = item['class']
            if cls in unattended_counts:
                unattended_counts[cls] += 1
                
        # Thread-safe states update
        with self.lock:
            self.current_crowd_count = behaviors['current_person_count']
            self.current_threat_level = level
            self.current_threat_score = score
            self.active_intruders = len(behaviors['intruder_ids'])
            self.active_unattended_objects = len(behaviors['unattended_items'])
            self.current_item_counts = current_counts
            self.unattended_item_counts = unattended_counts
            
            # Formulate AI diagnostics text messages for ticker ticker
            diagnostics = []
            if has_weapon:
                diagnostics.append("WEAPON CARRIER SPOTTED")
            for tid in behaviors['intruder_ids']:
                if tid == -1:
                    diagnostics.append("UNIDENTIFIED INTRUDER SECURE PERIMETER")
                else:
                    diagnostics.append(f"INTRUDER #{tid} PERIMETER BREACH")
            for tid in behaviors['running_ids']:
                diagnostics.append(f"PERSON #{tid} RUNNING AT SUSPICIOUS SPEED")
            for tid in behaviors['loitering_ids']:
                diagnostics.append(f"PERSON #{tid} LOITERING IN AREA")
            if behaviors['crowd_surge']:
                diagnostics.append("CRITICAL CROWD GATHERING SPEED")
            for item in behaviors['unattended_items']:
                diagnostics.append(f"UNATTENDED {item['class']} SECURE SECTOR")
                
            self.active_diagnostics = diagnostics

        # 5. DB Incident logger and SSE publisher
        current_time = time.time()
        
        # Determine active incident alert details
        triggered_alert = False
        incident_type = None
        description = None
        
        if level == "HIGH":
            # Intrusion/weapon breaches take highest priority
            if len(behaviors['intruder_ids']) > 0:
                incident_type = 'INTRUSION'
                description = f"RESTRICTED AREA INTRUSION: {len(behaviors['intruder_ids'])} suspect(s) breached secure perimeter."
            elif has_weapon:
                incident_type = 'WEAPON'
                description = "CRITICAL WEAPON DETECTION: Suspect carrying an active weapon/firearm proxy spotted."
            elif behaviors['crowd_surge']:
                incident_type = 'CROWD_ALERT'
                description = f"CROWD SURGE BREACH: {behaviors['current_person_count']} people gathered rapidly outside operational parameters."
            else:
                incident_type = 'INTRUSION'
                description = "HIGH RISK BREACH: Secure zone safety calculations exceeded threshold limit."
                
        elif level == "MEDIUM":
            if len(behaviors['unattended_items']) > 0:
                incident_type = 'UNATTENDED_OBJECT'
                item_names = list(set(item['class'] for item in behaviors['unattended_items']))
                description = f"UNATTENDED OBJECT DETECTED: {', '.join(item_names)} left secure zone."
            elif behaviors['current_person_count'] > self.crowd_threshold:
                incident_type = 'CROWD_ALERT'
                description = f"CROWD COUNT EXCEEDED: {behaviors['current_person_count']} persons present (Max capacity: {self.crowd_threshold})."
                
        # Save logs if active incident and cooldown timer elapsed
        if incident_type and (current_time - self.last_alert_times[incident_type] > self.alert_cooldowns[incident_type]):
            self.last_alert_times[incident_type] = current_time
            
            # Automatically snap visual JPEG frame on disk
            screenshot_path = self.save_alert_screenshot(frame, level)
            
            # Log to SQLite
            db_record = database.add_incident(
                threat_type=incident_type,
                threat_score=score,
                threat_level=level,
                crowd_count=behaviors['current_person_count'],
                screenshot_path=screenshot_path
            )
            
            # Add full description for SSE alert push and save base path
            db_record['description'] = description
            if screenshot_path:
                db_record['snapshot'] = f"/screenshots/{os.path.basename(screenshot_path)}"
            else:
                db_record['snapshot'] = None
                
            self.trigger_sse_alert(db_record)

        # 6. Render Premium High-Tech visual HUD overlays
        # A. Restricted Zone Polygon (Green/Orange/Flashing red depending on severity)
        zone_color = (60, 220, 60)  # Safe Green
        if level == "MEDIUM":
            zone_color = (40, 140, 240)  # Warning Orange
        elif level == "HIGH":
            # Blinking red effect
            if int(time.time() * 2.5) % 2 == 0:
                zone_color = (50, 50, 255)  # Breach Red
            else:
                zone_color = (20, 20, 140)  # Muted Dark Red
                
        if len(polygon) > 0:
            overlay_poly = frame.copy()
            cv2.fillPoly(overlay_poly, [polygon], zone_color)
            cv2.polylines(frame, [polygon], True, zone_color, 2)
            cv2.addWeighted(overlay_poly, 0.16, frame, 0.84, 0, frame)

        # B. Detections Bounding Boxes
        for d in detections:
            cls = d['class']
            x1, y1, x2, y2 = d['bbox']
            conf = d['conf']
            track_id = d['track_id']
            px, py = d['feet']
            
            # Determine visual box coloring and styling
            color = self.yolo.CLASS_COLORS.get(cls, (200, 200, 200))
            is_intruder = False
            
            if cls == 'PERSON':
                # Check intruder status
                if track_id in behaviors['intruder_ids'] or -1 in behaviors['intruder_ids']:
                    is_intruder = True
                    color = (50, 50, 255)  # Intruder red
                else:
                    color = (255, 240, 0)  # Safe Cyan
            elif cls == 'WEAPON':
                color = (50, 50, 255)  # Critical Weapon Red
                
            # If an instrument is unattended inside secure zone, color it Orange
            is_unattended = any(x1 == u['bbox'][0] and y1 == u['bbox'][1] for u in behaviors['unattended_items'])
            if is_unattended:
                color = (40, 140, 240)  # Unattended warning Orange
                
            # Draw primary rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # If high alert target (intruder or weapon), draw thick corners
            if is_intruder or cls == 'WEAPON':
                l_len = 16
                cv2.line(frame, (x1, y1), (x1 + l_len, y1), color, 4)
                cv2.line(frame, (x1, y1), (x1, y1 + l_len), color, 4)
                cv2.line(frame, (x2, y2), (x2 - l_len, y2), color, 4)
                cv2.line(frame, (x2, y2), (x2, y2 - l_len), color, 4)
                
            # Formulate tag label text
            lbl = f"{cls}"
            if track_id is not None:
                lbl += f" #{track_id}"
                
            # Append behavior flags
            if cls == 'PERSON':
                if is_intruder:
                    lbl = f"INTRUDER PERSON #{track_id}" if track_id else "INTRUDER PERSON"
                else:
                    if track_id in behaviors['running_ids']:
                        lbl += " [RUNNING]"
                    elif track_id in behaviors['loitering_ids']:
                        lbl += " [LOITERING]"
            elif is_unattended:
                lbl = f"UNATTENDED {cls}"
                
            lbl += f" {int(conf*100)}%"
            
            # Draw ribbon background tag
            text_size = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)[0]
            ribbon_w = text_size[0] + 10
            cv2.rectangle(frame, (x1 - 1, y1 - 20), (x1 + ribbon_w, y1), color, -1)
            cv2.putText(frame, lbl, (x1 + 5, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255) if (is_intruder or cls == 'WEAPON' or is_unattended) else (15, 10, 5), 1, cv2.LINE_AA)

        # C. Draw High-Tech Top HUD Ribbon
        cv2.rectangle(frame, (0, 0), (width, 24), (16, 16, 16), -1)
        cv2.line(frame, (0, 24), (width, 24), (60, 60, 60), 1)
        
        cv2.putText(frame, "FEED // ONLINE", (15, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 255, 120), 1, cv2.LINE_AA)
        
        status_text = "YOLOv8-NANO: ACTIVE" if self.yolo.model_loaded else "YOLOv8-NANO: INITIALIZING..."
        if not self.use_webcam:
            status_text = "SURVEILLANCE WORKSPACE: MOCK SIMULATOR"
        cv2.putText(frame, status_text, (140, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)
        
        hud_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]
        cv2.putText(frame, f"TIME: {hud_timestamp}", (width - 220, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)

        # D. Draw High-Tech Bottom HUD Ribbon
        cv2.rectangle(frame, (0, height - 32), (width, height), (16, 16, 16), -1)
        cv2.line(frame, (0, height - 32), (width, height - 32), (60, 60, 60), 1)
        
        cv2.putText(frame, f"PEOPLE: {behaviors['current_person_count']:02d}", (15, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 220, 220), 1, cv2.LINE_AA)
        
        items_hud_str = f"LAPTOP:{current_counts.get('LAPTOP', 0)}  BOTTLE:{current_counts.get('BOTTLE', 0)}  BOOK:{current_counts.get('NOTEBOOK', 0)}  PEN:{current_counts.get('PEN', 0)}  KEYS:{current_counts.get('KEYS', 0)}  WEAPON:{current_counts.get('WEAPON', 0)}"
        cv2.putText(frame, items_hud_str, (110, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1, cv2.LINE_AA)
        
        t_color = (120, 255, 120)
        if level == "MEDIUM":
            t_color = (40, 170, 255)
        elif level == "HIGH":
            t_color = (60, 60, 255)
            
        cv2.putText(frame, f"THREAT: {level} ({score:02d}/100)", (width - 210, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, t_color, 1, cv2.LINE_AA)

        # 7. Compress and return JPG bytes
        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return jpeg.tobytes()

    def __del__(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()