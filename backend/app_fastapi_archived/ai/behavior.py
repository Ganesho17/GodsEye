import math
import cv2
import numpy as np
import time
from typing import List, Dict

def check_point_in_polygon(point: tuple, polygon: List[List[float]], width: int, height: int) -> bool:
    """
    Checks if a normalized pixel point coordinates fall within a normalized polygon zone boundaries.
    Uses OpenCV pointPolygonTest.
    """
    if len(polygon) < 3:
        return False
        
    abs_poly = np.array([[int(pt[0] * width), int(pt[1] * height)] for pt in polygon], dtype=np.int32)
    abs_pt = (int(point[0]), int(point[1]))
    
    return cv2.pointPolygonTest(abs_poly, abs_pt, False) >= 0

class BehaviorAnalyzerEngine:
    def __init__(self):
        # track_id -> timestamp when they first entered the restricted zone
        self.zone_entry_times: Dict[int, float] = {}
        
        # bag_id (index) -> dict of static bag profiles
        # Keeps track of bag detections to verify if they are abandoned
        self.abandoned_bags_history: List[dict] = []

    def analyze_activities(
        self, 
        detections: List[dict], 
        zone_coords: List[List[float]], 
        width: int, 
        height: int,
        loitering_limit: float = 10.0
    ) -> dict:
        """
        Runs heuristics over active detections lists.
        Returns:
            dict of results:
            {
                "intruder_ids": List[int],
                "loiterer_ids": List[int],
                "running_ids": List[int],
                "abandoned_bags": List[dict],
                "crowd_surge": bool,
                "is_breached": bool
            }
        """
        current_time = time.time()
        
        intruder_ids = []
        loiterer_ids = []
        running_ids = []
        abandoned_bags = []
        is_breached = False
        
        # 1. Intrusion & Loitering Checks
        active_tids_in_zone = set()
        
        for d in detections:
            if d["class"] != "PERSON" or d["track_id"] is None:
                continue
                
            tid = d["track_id"]
            anchor = d["anchor"]
            
            # Check point-in-polygon restricted zone breach
            in_zone = check_point_in_polygon(anchor, zone_coords, width, height)
            
            if in_zone:
                is_breached = True
                intruder_ids.append(tid)
                active_tids_in_zone.add(tid)
                
                # Loitering countdown timer
                if tid not in self.zone_entry_times:
                    self.zone_entry_times[tid] = current_time
                    
                dwell = current_time - self.zone_entry_times[tid]
                if dwell > loiterer_limit:
                    loiterer_ids.append(tid)
            else:
                # Target moved out of restricted polygon; remove loitering tracker scope
                self.zone_entry_times.pop(tid, None)
                
        # Clean up obsolete loitering targets no longer tracked inside restricted zone
        for tid in list(self.zone_entry_times.keys()):
            if tid not in active_tids_in_zone:
                self.zone_entry_times.pop(tid, None)

        # 2. Running & Velocity Speed Diagnostics
        for d in detections:
            if d["class"] != "PERSON" or d["track_id"] is None:
                continue
                
            tid = d["track_id"]
            trajectory = d.get("trajectory", [])
            
            if len(trajectory) >= 3:
                # Measure physical coordinate movement displacement over historical track list
                # Trajectory points are formatted as (x, y) anchors
                oldest_pt = trajectory[0]
                newest_pt = trajectory[-1]
                
                dx = newest_pt[0] - oldest_pt[0]
                dy = newest_pt[1] - oldest_pt[1]
                dist = math.sqrt(dx**2 + dy**2)
                
                # Minimum threshold check to classify high speed running (displacement > 200px/s)
                # Centroid tracker trims coordinates histories to 2-3s window, so average speed is robust
                if dist > 180.0:
                    running_ids.append(tid)

        # 3. Abandoned Bags Heuristics
        # Find all BAG objects and PERSON objects
        bags = [d for d in detections if d["class"] == "BAG"]
        people = [d for d in detections if d["class"] == "PERSON"]
        
        for bag in bags:
            b_center = bag["anchor"]
            
            # Check proximity to nearest human
            min_dist_to_human = 999999.0
            for person in people:
                p_center = person["anchor"]
                dist = math.sqrt((b_center[0] - p_center[0])**2 + (b_center[1] - p_center[1])**2)
                if dist < min_dist_to_human:
                    min_dist_to_human = dist
                    
            # If the closest human is far (distance > 300px), analyze historical duration
            if min_dist_to_human > 300.0:
                # Target bag has been left unattended! Match against previous static listings
                matched = False
                for prev in self.abandoned_bags_history:
                    p_cent = prev["anchor"]
                    dist_to_prev = math.sqrt((b_center[0] - p_cent[0])**2 + (b_center[1] - p_cent[1])**2)
                    
                    if dist_to_prev < 15.0: # Stable static position
                        matched = True
                        prev["last_seen"] = current_time
                        duration = current_time - prev["birth_time"]
                        
                        if duration > 5.0: # Unattended static warning for > 5 seconds
                            abandoned_bags.append({
                                "class": "BAG",
                                "bbox": bag["bbox"],
                                "anchor": b_center,
                                "duration": int(duration)
                            })
                        break
                        
                if not matched:
                    # New unattended bag found; log entry index
                    self.abandoned_bags_history.append({
                        "anchor": b_center,
                        "birth_time": current_time,
                        "last_seen": current_time
                    })
                    
        # Prune old static bag indices that are no longer detected (stale for > 5.0 seconds)
        self.abandoned_bags_history = [
            b for b in self.abandoned_bags_history if current_time - b["last_seen"] <= 5.0
        ]

        return {
            "intruder_ids": list(set(intruder_ids)),
            "loiterer_ids": list(set(loiterer_ids)),
            "running_ids": list(set(running_ids)),
            "abandoned_bags": abandoned_bags,
            "is_breached": is_breached
        }
