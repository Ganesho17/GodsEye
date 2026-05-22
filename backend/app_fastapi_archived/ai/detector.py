import threading
from ultralytics import YOLO
from backend.app.core.config import settings

class YoloDetectorWrapper:
    def __init__(self):
        self.model_path = settings.YOLO_MODEL_PATH
        self.model = None
        self.model_loaded = False
        self.lock = threading.Lock()
        
        # COCO class mapping indexes into enterprise secure ontology:
        # 0 -> PERSON
        # 2 -> VEHICLE (car), 3 -> VEHICLE (motorcycle), 5 -> VEHICLE (bus), 7 -> VEHICLE (truck)
        # 24 -> BAG (backpack), 26 -> BAG (handbag), 28 -> BAG (suitcase)
        # 67 -> PHONE (cell phone)
        # 43 -> WEAPON (knife), 76 -> WEAPON (scissors proxy)
        self.COCO_MAP = {
            0: "PERSON",
            2: "VEHICLE", 3: "VEHICLE", 5: "VEHICLE", 7: "VEHICLE",
            24: "BAG", 26: "BAG", 28: "BAG",
            67: "PHONE",
            43: "WEAPON", 76: "WEAPON"
        }
        
        # Start background load thread
        threading.Thread(target=self._lazy_load, daemon=True).start()

    def _lazy_load(self):
        """Loads weights binary asynchronously in background thread context."""
        try:
            print(f"YOLO Wrapper: Attempting to initialize weights from {self.model_path}...")
            loaded_model = YOLO(self.model_path)
            with self.lock:
                self.model = loaded_model
                self.model_loaded = True
            print("YOLO Wrapper: Ultralytics YOLOv8 network successfully initialized.")
        except Exception as e:
            print(f"YOLO Wrapper: Core initialization failed: {e}")

    def run_inference(self, frame):
        """
        Executes YOLOv8 object detection on a raw image matrix.
        Returns:
            list of dict containing parsed results:
            [
                {
                    "class": str,     # PERSON, VEHICLE, BAG, PHONE, WEAPON
                    "bbox": [x1, y1, x2, y2],
                    "conf": float,
                    "anchor": (px, py) # bottom-center coordinate anchor
                }
            ]
        """
        parsed_results = []
        if frame is None:
            return parsed_results
            
        with self.lock:
            if not self.model_loaded or self.model is None:
                return parsed_results
                
            try:
                # Execute inference synchronously inside lock scope to maintain thread safety
                results = self.model(frame, verbose=False)
                
                if len(results) > 0 and results[0].boxes is not None:
                    boxes = results[0].boxes
                    for box in boxes:
                        cls_idx = int(box.cls[0].item())
                        
                        if cls_idx in self.COCO_MAP:
                            conf = float(box.conf[0].item())
                            
                            # Filter weak confidence scores (minimum 30% ratio)
                            if conf < 0.30:
                                continue
                                
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                            
                            # Center feet bottom boundary coordinates as anchoring point
                            px = int((x1 + x2) / 2)
                            py = int(y2)
                            
                            parsed_results.append({
                                "class": self.COCO_MAP[cls_idx],
                                "bbox": [x1, y1, x2, y2],
                                "conf": conf,
                                "anchor": (px, py)
                            })
            except Exception as e:
                print(f"YOLO Wrapper: Inference processing error: {e}")
                
        return parsed_results
