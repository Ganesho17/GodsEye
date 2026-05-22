import math
import time
from typing import List, Dict

class CentroidTracker:
    def __init__(self, max_disappeared=30):
        self.next_track_id = 1
        
        # track_id -> centroid coords (cx, cy)
        self.centroids: Dict[int, tuple] = {}
        
        # track_id -> frames missing
        self.disappeared: Dict[int, int] = {}
        
        # track_id -> complete history of (timestamp, bbox, anchor_pt)
        self.track_history: Dict[int, List[dict]] = {}
        
        # track_id -> epoch birth time
        self.birth_times: Dict[int, float] = {}
        
        self.max_disappeared = max_disappeared

    def register(self, bbox: list, anchor: tuple):
        """Creates a new tracking slot with a persistent index."""
        tid = self.next_track_id
        cx = int((bbox[0] + bbox[2]) / 2)
        cy = int((bbox[1] + bbox[3]) / 2)
        
        self.centroids[tid] = (cx, cy)
        self.disappeared[tid] = 0
        self.birth_times[tid] = time.time()
        
        self.track_history[tid] = [{
            "timestamp": time.time(),
            "bbox": bbox,
            "anchor": anchor
        }]
        
        self.next_track_id += 1
        return tid

    def deregister(self, tid: int):
        """Cleans up and removes inactive tracking slot profiles."""
        self.centroids.pop(tid, None)
        self.disappeared.pop(tid, None)
        self.track_history.pop(tid, None)
        self.birth_times.pop(tid, None)

    def update(self, detections: List[dict]) -> List[dict]:
        """
        Updates coordinate matching based on Euclidean distances between current and historical centroids.
        Args:
            detections: List of parsed detection dicts.
        Returns:
            tracked_detections: Bounding boxes combined with persistent track IDs.
        """
        current_time = time.time()
        
        # If no active detections are passed, mark all current active tracks as disappeared by 1
        if len(detections) == 0:
            for tid in list(self.disappeared.keys()):
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    self.deregister(tid)
            return []

        # Filter only PERSON class objects for tracking, as other objects are usually static
        # or don't require persistent trajectories for loitering/violence/speed models
        person_detections = [d for d in detections if d["class"] == "PERSON"]
        other_detections = [d for d in detections if d["class"] != "PERSON"]
        
        # Calculate centroids for current frame's person bounding boxes
        input_centroids = []
        for d in person_detections:
            bbox = d["bbox"]
            cx = int((bbox[0] + bbox[2]) / 2)
            cy = int((bbox[1] + bbox[3]) / 2)
            input_centroids.append((cx, cy))

        # If no tracks are currently active, register all new person centroids
        if len(self.centroids) == 0:
            for idx, d in enumerate(person_detections):
                tid = self.register(d["bbox"], d["anchor"])
                d["track_id"] = tid
                d["dwell_time"] = 0.0
                d["trajectory"] = [(d["anchor"])]
        else:
            track_ids = list(self.centroids.keys())
            track_centroids = list(self.centroids.values())
            
            # Compute Euclidean distances between all historical tracks and current input centroids
            D = []
            for t_cent in track_centroids:
                row = []
                for i_cent in input_centroids:
                    dist = math.sqrt((t_cent[0] - i_cent[0])**2 + (t_cent[1] - i_cent[1])**2)
                    row.append(dist)
                D.append(row)
                
            # Perform a simple greedy match of closest centroids (distance threshold < 120px)
            matched_inputs = set()
            matched_tracks = set()
            
            for t_idx in range(len(track_centroids)):
                if len(input_centroids) == 0:
                    break
                # Find minimum distance index
                min_val = 999999.0
                min_idx = -1
                for i_idx, val in enumerate(D[t_idx]):
                    if val < min_val and i_idx not in matched_inputs:
                        min_val = val
                        min_idx = i_idx
                        
                if min_idx != -1 and min_val < 120.0:  # 120px max jump margin
                    tid = track_ids[t_idx]
                    matched_inputs.add(min_idx)
                    matched_tracks.add(tid)
                    
                    # Update coordinate centroid
                    self.centroids[tid] = input_centroids[min_idx]
                    self.disappeared[tid] = 0
                    
                    # Commit history log
                    matching_det = person_detections[min_idx]
                    self.track_history[tid].append({
                        "timestamp": current_time,
                        "bbox": matching_det["bbox"],
                        "anchor": matching_det["anchor"]
                    })
                    
                    # Crop track history logs to avoid memory bloat (keep last 5.0 seconds)
                    self.track_history[tid] = [
                        h for h in self.track_history[tid] if current_time - h["timestamp"] <= 5.0
                    ]
                    
                    matching_det["track_id"] = tid
                    matching_det["dwell_time"] = current_time - self.birth_times[tid]
                    matching_det["trajectory"] = [h["anchor"] for h in self.track_history[tid]]
            
            # For unmatched tracks, mark as disappeared by 1
            for tid in track_ids:
                if tid not in matched_tracks:
                    self.disappeared[tid] += 1
                    if self.disappeared[tid] > self.max_disappeared:
                        self.deregister(tid)
                        
            # For unmatched inputs, register them as new tracks
            for i_idx, d in enumerate(person_detections):
                if i_idx not in matched_inputs:
                    tid = self.register(d["bbox"], d["anchor"])
                    d["track_id"] = tid
                    d["dwell_time"] = 0.0
                    d["trajectory"] = [d["anchor"]]

        # Merge tracked persons and static elements to formulate unified telemetry list
        for other in other_detections:
            other["track_id"] = None
            other["dwell_time"] = 0.0
            other["trajectory"] = []
            
        return person_detections + other_detections
