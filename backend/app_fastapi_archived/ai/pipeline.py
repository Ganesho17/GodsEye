import os
import cv2
import time
import json
import queue
import threading
import math
import numpy as np
from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.db.models import Camera, Incident, Summary
from backend.app.ai.detector import YoloDetectorWrapper
from backend.app.ai.tracker import CentroidTracker
from backend.app.ai.behavior import BehaviorAnalyzerEngine
from backend.app.ai.violence import ViolenceDetectorEngine
from backend.app.ai.threat import ThreatMatrixEvaluator
from backend.app.websocket.manager import manager
from backend.app.services.open_ai import generate_incident_summary

class SurveillancePipeline:
    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self.running = False
        self.frame_queue = queue.Queue(maxsize=2)
        
        # Core engines
        self.detector = YoloDetectorWrapper()
        self.tracker = CentroidTracker()
        self.behavior_analyzer = BehaviorAnalyzerEngine()
        self.violence_detector = ViolenceDetectorEngine()
        
        # Threads
        self.capture_thread = None
        self.processing_thread = None
        
        # Dynamic settings loaded from camera record
        self.camera_name = "Camera Feed"
        self.rtsp_url = None
        self.zone_coords = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
        
        # Shared states
        self.latest_raw_frame = None
        self.latest_telemetry = {}
        self.lock = threading.Lock()
        
        # Anti-spam alert throttle: mapping incident_type -> epoch timestamp
        self.alert_throttles = {}
        
        # Simulated feed state (in case webcam/RTSP fails or is missing)
        self.simulated_mode = False
        
        # Initialize camera settings from DB
        self._load_camera_config()

    def _load_camera_config(self):
        """Fetches RTSP settings and custom alert polygon coordinate vertices from DB."""
        db: Session = SessionLocal()
        try:
            cam = db.query(Camera).filter(Camera.id == self.camera_id).first()
            if cam:
                self.camera_name = cam.name
                self.rtsp_url = cam.rtsp_url
                if cam.zone_coordinates:
                    try:
                        self.zone_coords = json.loads(cam.zone_coordinates)
                    except Exception:
                        pass
        finally:
            db.close()

    def start(self):
        """Launches threaded OpenCV extraction loop and background heuristics evaluator workers."""
        if self.running:
            return
        self.running = True
        
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        
        self.capture_thread.start()
        self.processing_thread.start()
        print(f"Pipeline [Camera {self.camera_id}]: Threaded video pipelines started.")

    def stop(self):
        """Gracefully tears down execution loops and releases active device contexts."""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)
        print(f"Pipeline [Camera {self.camera_id}]: Pipelines terminated.")

    def _capture_loop(self):
        """
        Isolated fast-path thread dedicated strictly to grabbing raw frames.
        Flushes buffer lag by overwriting queue slots continuously.
        """
        # Determine source (None or empty/0 triggers default webcam index 0)
        source = 0
        if self.rtsp_url:
            source = self.rtsp_url
            try:
                # Support integer indexes mapped from strings e.g. "1" -> 1
                source = int(self.rtsp_url)
            except ValueError:
                pass
                
        # On Windows, DirectShow (cv2.CAP_DSHOW) resolves slow start / fail to open local webcams
        if isinstance(source, int) and os.name == 'nt':
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(source)
        
        # Probe frame extraction
        if not cap.isOpened():
            print(f"Pipeline Warning: Physical stream capture {source} failed. Enabling synthetic command console simulation.")
            self.simulated_mode = True
            cap.release()
        else:
            # Configure buffer sizing parameters
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
        frame_interval = 1.0 / 30.0 # Force 30 FPS target
        
        while self.running:
            start_time = time.time()
            
            if self.simulated_mode:
                # Render state-of-the-art diagnostic mock frames
                frame = self._generate_simulated_frame()
            else:
                ret, raw_frame = cap.read()
                if not ret:
                    print("Pipeline: Lost video frame stream. Falling back to synthetic console simulation.")
                    self.simulated_mode = True
                    cap.release()
                    continue
                # Downsample frame slightly to optimize processing
                frame = cv2.resize(raw_frame, (640, 480))

            with self.lock:
                self.latest_raw_frame = frame.copy()
                
            # Feed frame queue, popping older slots to prevent lag accumulation
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self.frame_queue.put(frame)
            
            # Bound capture rate to prevent CPU resource thrashing
            elapsed = time.time() - start_time
            sleep_time = max(0.001, frame_interval - elapsed)
            time.sleep(sleep_time)
            
        if not self.simulated_mode:
            cap.release()

    def _processing_loop(self):
        """
        Dedicated core processing thread.
        Evaluates YOLO neural networks, parses tracker coordinates, and runs heuristics.
        """
        frame_counter = 0
        
        while self.running:
            try:
                # Fetch fresh frame from grabber thread
                frame = self.frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue
                
            frame_counter += 1
            
            # --- Dynamic Frame Skipping ---
            # To sustain 30 FPS fluid rendering on mid-tier CPUs, skip heavy YOLO inference
            # on every other frame, falling back to cached telemetry overlays.
            if frame_counter % 2 != 0:
                # Perform full vision-heuristics loop
                height, width, _ = frame.shape
                
                # 1. Run YOLO object & weapon inference
                raw_detections = self.detector.run_inference(frame)
                
                # 2. Update persistent tracker indexes
                tracked_detections = self.tracker.update(raw_detections)
                
                # 3. Analyze spatial & behavioral actions
                behavior_metrics = self.behavior_analyzer.analyze_activities(
                    tracked_detections, self.zone_coords, width, height
                )
                
                # 4. Run violence / physical alteration indicators
                is_violence, violence_prob, violence_details = self.violence_detector.evaluate_violence(tracked_detections)
                
                # Parse metrics list to determine threat scores
                has_intrusion = behavior_metrics["is_breached"]
                has_loitering = len(behavior_metrics["loiterer_ids"]) > 0
                has_running = len(behavior_metrics["running_ids"]) > 0
                has_weapon = any(d["class"] == "WEAPON" for d in tracked_detections)
                has_abandoned = len(behavior_metrics["abandoned_bags"]) > 0
                
                crowd_count = sum(1 for d in tracked_detections if d["class"] == "PERSON")
                
                # 5. Evaluate overall threat status Matrix
                threat_score, threat_level = ThreatMatrixEvaluator.calculate_threat(
                    has_intrusion=has_intrusion,
                    has_weapon=has_weapon,
                    has_violence=is_violence,
                    crowd_count=crowd_count,
                    has_running=has_running,
                    has_loitering=has_loitering
                )
                
                # Assemble telemetry payload dict
                telemetry = {
                    "camera_id": self.camera_id,
                    "timestamp": time.time(),
                    "threat_score": threat_score,
                    "threat_level": threat_level,
                    "crowd_count": crowd_count,
                    "detections": tracked_detections,
                    "behavior": {
                        "intruder_ids": behavior_metrics["intruder_ids"],
                        "loiterer_ids": behavior_metrics["loiterer_ids"],
                        "running_ids": behavior_metrics["running_ids"],
                        "abandoned_bags": behavior_metrics["abandoned_bags"],
                        "is_violence": is_violence,
                        "violence_details": violence_details,
                        "is_breached": has_intrusion
                    },
                    "zone_coordinates": self.zone_coords
                }
                
                with self.lock:
                    self.latest_telemetry = telemetry
                    
                # Broadcast real-time frames coordinates via WebSockets connection pool
                # Telemetry streams at ~15Hz
                manager.broadcast_telemetry(telemetry)
                
                # 6. Trigger and store critical alerts
                self._evaluate_and_log_alerts(telemetry, frame)
                
            time.sleep(0.01)

    def _evaluate_and_log_alerts(self, telemetry: dict, frame: np.ndarray):
        """Evaluates telemetry triggers, commits logged records, and broadcasts alerts instantly."""
        # Define alert-worthy heuristics
        triggers = []
        
        if telemetry["behavior"]["is_breached"]:
            triggers.append(("INTRUSION", 30, "Restricted zone polygon boundary breached."))
        if any(d["class"] == "WEAPON" for d in telemetry["detections"]):
            triggers.append(("WEAPON", 40, "Potential visual weapon vector flagged in proximity."))
        if telemetry["behavior"]["is_violence"]:
            triggers.append(("VIOLENCE", 35, telemetry["behavior"]["violence_details"]))
        if len(telemetry["behavior"]["abandoned_bags"]) > 0:
            triggers.append(("UNATTENDED_OBJECT", 25, "Stationary luggage container left unattended for over 5s."))
        if telemetry["crowd_count"] >= settings.CROWD_THRESHOLD:
            triggers.append(("CROWD_ALERT", 20, f"Vicinity crowd density reached critical threshold ({telemetry['crowd_count']} persons)."))
            
        current_time = time.time()
        
        for inc_type, base_score, details in triggers:
            # Threat throttling: enforce a minimum 10.0s cooldown per alert classification type
            last_alert = self.alert_throttles.get(inc_type, 0.0)
            if current_time - last_alert > 10.0:
                self.alert_throttles[inc_type] = current_time
                
                # Commit logging event inside an isolated database transactional thread scope
                threading.Thread(
                    target=self._persist_alert_record,
                    args=(inc_type, telemetry["threat_score"], telemetry["threat_level"], telemetry["crowd_count"], details, frame.copy()),
                    daemon=True
                ).start()

    def _persist_alert_record(self, inc_type: str, score: int, level: str, crowd: int, desc: str, frame: np.ndarray):
        """Locks connection context to write database incident rows and generate AI summaries."""
        db: Session = SessionLocal()
        try:
            # 1. Create a physical JPEG snapshot screenshot
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cam_{self.camera_id}_{inc_type}_{timestamp_str}.jpg"
            screenshot_path = os.path.join(settings.SCREENSHOTS_DIR, filename)
            cv2.imwrite(screenshot_path, frame)
            
            # Store the relative web-accessible server path
            relative_screenshot_path = f"/screenshots/{filename}"
            
            # 2. Add Incident record row
            incident = Incident(
                camera_id=self.camera_id,
                incident_type=inc_type,
                threat_score=score,
                threat_level=level,
                crowd_count=crow,
                screenshot_path=relative_screenshot_path,
                description=desc,
                is_resolved=False
            )
            db.add(incident)
            db.commit()
            db.refresh(incident)
            
            # 3. Request professional incident summaries from the OpenAI service
            summary_text = generate_incident_summary(
                incident_type=inc_type,
                threat_level=level,
                threat_score=score,
                crowd_count=crowd,
                description=desc
            )
            
            # Persist summary
            summary = Summary(
                incident_id=incident.id,
                summary_text=summary_text
            )
            db.add(summary)
            db.commit()
            
            # Assemble alert notification dictionary
            alert_notification = {
                "id": incident.id,
                "timestamp": incident.timestamp.isoformat(),
                "camera_id": self.camera_id,
                "camera_name": self.camera_name,
                "incident_type": inc_type,
                "threat_score": score,
                "threat_level": level,
                "crowd_count": crowd,
                "screenshot_path": relative_screenshot_path,
                "description": desc,
                "summary": summary_text,
                "is_resolved": False
            }
            
            # Broadcast instant JSON alert package via active WebSockets alerts pool
            manager.broadcast_alert(alert_notification)
            print(f"Pipeline [Camera {self.camera_id}]: Critical {inc_type} alert logged and broadcasted.")
            
        except Exception as e:
            print(f"Pipeline Persistent Logging Error: {e}")
            db.rollback()
        finally:
            db.close()

    def get_current_frame_jpeg(self) -> bytes:
        """Encodes the latest frame array matrix into a JPEG byte sequence to feed MJPEG routers."""
        with self.lock:
            if self.latest_raw_frame is None:
                # Return standard 640x480 dark placeholders
                img = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(img, "CONNECTING SOURCE...", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 116, 139), 2)
                _, encoded = cv2.imencode('.jpg', img)
                return encoded.tobytes()
            
            frame_copy = self.latest_raw_frame.copy()
            
        _, encoded = cv2.imencode('.jpg', frame_copy)
        return encoded.tobytes()

    def get_telemetry(self) -> dict:
        """Returns the latest evaluated coordinate telemetry dict."""
        with self.lock:
            return self.latest_telemetry

    def _generate_simulated_frame(self) -> np.ndarray:
        """
        Creates elegant dark-space synthetic security feeds.
        Generates floating, colorized vector matrices, crosshairs, and tracking paths.
        """
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Drawing grid patterns representing HUD telemetry
        for x in range(0, 640, 40):
            cv2.line(img, (x, 0), (x, 480), (15, 23, 42), 1)
        for y in range(0, 480, 40):
            cv2.line(img, (0, y), (640, y), (15, 23, 42), 1)
            
        # Draw secure polygon boundaries
        pts = np.array([[int(pt[0] * 640), int(pt[1] * 480)] for pt in self.zone_coords], np.int32)
        pts = pts.reshape((-1, 1, 2))
        
        # Color restricted zone depending on live clock cycles (pulse neon orange/red)
        cycle = math.sin(time.time() * 3.0)
        alpha = int(120 + 35 * cycle)
        cv2.polylines(img, [pts], True, (0, 140, 255), 2) # Orange
        
        # Overlay standard command center statistics
        cv2.putText(img, f"SOURCE: {self.camera_name.upper()} | SIMULATION SYSTEM ACTIVE", (20, 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (94, 234, 212), 1, cv2.LINE_AA)
                    
        cv2.putText(img, f"TIME: {datetime.now().strftime('%H:%M:%S')}", (480, 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 116, 139), 1, cv2.LINE_AA)

        # Draw a beautiful cybernetic HUD compass in corner
        cv2.circle(img, (580, 420), 30, (30, 41, 59), 2)
        cv2.line(img, (580, 390), (580, 450), (148, 163, 184), 1)
        cv2.line(img, (550, 420), (610, 420), (148, 163, 184), 1)
        
        # Render clean simulation output
        return img

# Global manager handling multiple camera pipelines simultaneously
class SurveillancePipelineManager:
    def __init__(self):
        self.pipelines = {}
        self.lock = threading.Lock()

    def start_pipeline(self, camera_id: int) -> SurveillancePipeline:
        """Spins up a pipeline instance for the given camera, recycling active channels."""
        with self.lock:
            if camera_id in self.pipelines:
                self.pipelines[camera_id].stop()
                
            pipeline = SurveillancePipeline(camera_id)
            self.pipelines[camera_id] = pipeline
            pipeline.start()
            return pipeline

    def stop_pipeline(self, camera_id: int):
        """Stops the active pipeline channel."""
        with self.lock:
            if camera_id in self.pipelines:
                self.pipelines[camera_id].stop()
                del self.pipelines[camera_id]

    def get_pipeline(self, camera_id: int) -> SurveillancePipeline:
        """Retrieves active pipeline instance."""
        with self.lock:
            return self.pipelines.get(camera_id)

    def stop_all(self):
        """Cleans up all pipeline streams."""
        with self.lock:
            for pid, pipeline in list(self.pipelines.items()):
                pipeline.stop()
            self.pipelines.clear()

pipeline_manager = SurveillancePipelineManager()
