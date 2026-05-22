import time
import math
import cv2
import numpy as np

class BehaviorAnalyzer:
    def __init__(self):
        # track_id -> birth timestamp (when track was first seen)
        self.track_birthtimes = {}
        
        # track_id -> list of (timestamp, centroid_coords)
        self.track_history = {}
        
        # track_id -> timestamp when last seen (to prune dead tracks)
        self.last_seen = {}
        
        # history of total crowd counts: list of (timestamp, count)
        self.crowd_history = []
        
        # Lock for thread safety
        import threading
        self.lock = threading.Lock()

    def update(self, detections, zone_coords, width, height, loitering_threshold=10.0, running_threshold=200.0):
        """
        Updates tracking history and checks for loitering, running, perimeter intrusions, 
        and crowd surges.
        
        Parameters:
            detections: list of parsed detection dicts from YoloDetector
            zone_coords: list of [x, y] normalized coordinates defining the restricted zone
            width: frame width
            height: frame height
            loitering_threshold: seconds a person must stay in frame to be considered loitering
            running_threshold: pixels per second to classify as running
            
        Returns:
            dict containing active security behavior events
        """
        current_time = time.time()
        
        active_track_ids = set()
        loitering_ids = []
        running_ids = []
        intruder_ids = []
        unattended_items = []
        
        person_count = 0
        
        # Convert normalized zone coords to absolute OpenCV polygon points
        polygon = np.array([[int(pt[0] * width), int(pt[1] * height)] for pt in zone_coords], dtype=np.int32)
        
        with self.lock:
            # 1. Prune stale tracks to prevent memory leaks (inactive for > 5.0 seconds)
            stale_ids = [tid for tid, lseen in self.last_seen.items() if current_time - lseen > 5.0]
            for tid in stale_ids:
                self.track_birthtimes.pop(tid, None)
                self.track_history.pop(tid, None)
                self.last_seen.pop(tid, None)
                
            # 2. Analyze individual detections
            for det in detections:
                cls_name = det['class']
                x1, y1, x2, y2 = det['bbox']
                px, py = det['feet']
                track_id = det['track_id']
                conf = det['conf']
                
                # Check point-in-polygon restricted zone intrusion
                is_inside_restricted = False
                if len(polygon) > 2:
                    is_inside_restricted = cv2.pointPolygonTest(polygon, (px, py), False) >= 0
                
                if cls_name == 'PERSON':
                    person_count += 1
                    
                    # If we have a track ID, run temporal and velocity calculations
                    if track_id is not None:
                        active_track_ids.add(track_id)
                        self.last_seen[track_id] = current_time
                        
                        # A. Loitering Check
                        if track_id not in self.track_birthtimes:
                            self.track_birthtimes[track_id] = current_time
                        duration = current_time - self.track_birthtimes[track_id]
                        if duration > loitering_threshold:
                            loitering_ids.append(track_id)
                            
                        # B. Running / Velocity Check
                        cx = (x1 + x2) / 2.0
                        cy = (y1 + y2) / 2.0
                        
                        if track_id not in self.track_history:
                            self.track_history[track_id] = []
                        self.track_history[track_id].append((current_time, (cx, cy)))
                        
                        # Keep only the last 2.0 seconds of position history
                        self.track_history[track_id] = [pt for pt in self.track_history[track_id] if current_time - pt[0] <= 2.0]
                        
                        # Compute velocity using a 1.0 second lookback window (filters out high-frequency noise)
                        history = self.track_history[track_id]
                        if len(history) >= 2:
                            # Find oldest point in the window
                            oldest_pt = history[0]
                            for pt in history:
                                if current_time - pt[0] <= 1.0:
                                    oldest_pt = pt
                                    break
                                    
                            dt = current_time - oldest_pt[0]
                            if dt > 0.1:  # Prevent divide by zero or extreme noise
                                ox, oy = oldest_pt[1]
                                dist = math.sqrt((cx - ox)**2 + (cy - oy)**2)
                                speed = dist / dt  # pixels per second
                                
                                if speed > running_threshold:
                                    running_ids.append(track_id)
                                    
                        # C. Intrusion Check
                        if is_inside_restricted:
                            intruder_ids.append(track_id)
                    else:
                        # Fallback for untracked persons inside zone
                        if is_inside_restricted:
                            # Represent untracked persons with key -1
                            intruder_ids.append(-1)
                else:
                    # Office instruments check (BOTTLE, LAPTOP, NOTEBOOK, PEN, KEYS, WEAPON)
                    # If they are inside the secure restricted zone, track them
                    if is_inside_restricted:
                        unattended_items.append({
                            'class': cls_name,
                            'bbox': [x1, y1, x2, y2],
                            'conf': conf,
                            'centroid': (int((x1+x2)/2), int((y1+y2)/2))
                        })
            
            # 3. Crowd Surge Rate of Change Analysis
            self.crowd_history.append((current_time, person_count))
            # Keep last 5.0 seconds of history
            self.crowd_history = [pt for pt in self.crowd_history if current_time - pt[0] <= 5.0]
            
            crowd_surge = False
            if len(self.crowd_history) >= 2:
                # Find the crowd count from ~2.0 seconds ago
                past_pt = self.crowd_history[0]
                for pt in self.crowd_history:
                    if current_time - pt[0] <= 2.0:
                        past_pt = pt
                        break
                
                count_diff = person_count - past_pt[1]
                dt = current_time - past_pt[0]
                
                # If crowd count grows by 3 or more people in 2 seconds, trigger crowd surge
                if count_diff >= 3 and dt > 0.5:
                    crowd_surge = True
                    
        return {
            'loitering_ids': list(set(loitering_ids)),
            'running_ids': list(set(running_ids)),
            'intruder_ids': list(set(intruder_ids)),
            'unattended_items': unattended_items,
            'crowd_surge': crowd_surge,
            'is_restricted_breached': len(intruder_ids) > 0,
            'current_person_count': person_count
        }
