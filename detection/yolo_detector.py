import cv2
import numpy as np
import threading
from ultralytics import YOLO

class YoloDetector:
    def __init__(self, model_path="models/yolov8n.pt"):
        self.model_path = model_path
        self.model = None
        self.model_loaded = False
        self.lock = threading.Lock()
        
        # Class mappings for GodsEye custom ontology
        # Maps COCO class indices to GodsEye classes
        # Cell phone (67) and Scissors (76) act as webcam weapon proxies
        # Remote (65) acts as Keys proxy, Toothbrush (79) acts as Pen proxy
        self.YOLO_TO_CUSTOM_MAP = {
            0: 'PERSON',
            43: 'WEAPON',     # COCO knife -> WEAPON
            67: 'WEAPON',     # COCO cell phone -> WEAPON proxy
            76: 'WEAPON',     # COCO scissors -> WEAPON proxy
     
        }
        
        # Color definitions for HUD (BGR format)
        self.CLASS_COLORS = {
            'PERSON': (255, 240, 0),     # Cyan
            'WEAPON': (50, 50, 255)      # Hot Neon Red
        }
        
        # Start background load thread
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        """Loads YOLOv8 in the background to ensure instantaneous startup."""
        try:
            print(f"YoloDetector: Initializing model from {self.model_path}...")
            loaded_model = YOLO(self.model_path)
            with self.lock:
                self.model = loaded_model
                self.model_loaded = True
            print("YoloDetector: YOLOv8 model loaded successfully.")
        except Exception as e:
            print(f"YoloDetector: Error loading YOLOv8 model: {e}")

    def process_frame(self, frame):
        """
        Runs YOLOv8 tracking on the frame and returns a parsed list of detections.
        Returns:
            parsed_detections: list of dicts containing:
                {
                    'track_id': int or None,
                    'class': str,
                    'bbox': [x1, y1, x2, y2],
                    'conf': float,
                    'feet': (px, py)  # spatial coordinate anchor
                }
        """
        parsed_detections = []
        if frame is None:
            return parsed_detections
            
        with self.lock:
            if not self.model_loaded or self.model is None:
                return parsed_detections
            
            try:
                # Run YOLOv8 Multi-Object Tracking with persistent states
                results = self.model.track(frame, persist=True, verbose=False)
                
                if len(results) > 0 and results[0].boxes is not None:
                    boxes = results[0].boxes
                    for box in boxes:
                        cls_idx = int(box.cls[0].item())
                        
                        # Only keep relevant classes in our custom ontology
                        if cls_idx in self.YOLO_TO_CUSTOM_MAP:
                            custom_cls = self.YOLO_TO_CUSTOM_MAP[cls_idx]
                            conf = float(box.conf[0].item())
                            
                            # Filter low-confidence detections
                            if conf < 0.30:
                                continue
                                
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                            
                            # Get persistent tracking ID if available, else None
                            track_id = None
                            if box.id is not None:
                                track_id = int(box.id[0].item())
                                
                            # Bottom-center coordinate used as the spatial anchor (e.g. feet on the floor)
                            px = int((x1 + x2) / 2)
                            py = int(y2)
                            
                            parsed_detections.append({
                                'track_id': track_id,
                                'class': custom_cls,
                                'bbox': [x1, y1, x2, y2],
                                'conf': conf,
                                'feet': (px, py)
                            })
            except Exception as e:
                print(f"YoloDetector: Exception during frame inference: {e}")
                
        return parsed_detections