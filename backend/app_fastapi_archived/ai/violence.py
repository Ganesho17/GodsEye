import math
import time
from typing import List, Dict

class ViolenceDetectorEngine:
    def __init__(self):
        # track_id -> recent movement vectors to measure trajectory angles
        self.movement_vectors: Dict[int, list] = {}

    def calculate_vector_angle(self, v1: tuple, v2: tuple) -> float:
        """Computes the angle difference in degrees between two movement vectors."""
        dot_prod = v1[0]*v2[0] + v1[1]*v2[1]
        mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
        mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
        
        if mag1 < 0.1 or mag2 < 0.1:
            return 0.0
            
        cos_theta = dot_prod / (mag1 * mag2)
        # Clamping cos_theta due to floating point noise
        cos_theta = max(-1.0, min(1.0, cos_theta))
        
        return math.degrees(math.acos(cos_theta))

    def evaluate_violence(self, detections: List[dict]) -> tuple:
        """
        Runs relative motion violence metrics.
        Args:
            detections: List of parsed detection dicts.
        Returns:
            is_violence: bool, indicating if violence is detected
            probability: float, dynamic probability score from 0.0 to 1.0
            alert_msg: str descriptive alert
        """
        people = [d for d in detections if d["class"] == "PERSON" and d["track_id"] is not None]
        
        # We need at least two tracked human targets to analyze inter-human fights/violence
        if len(people) < 2:
            return False, 0.0, "Perimeter Secure"

        violence_detected = False
        max_prob = 0.0
        details = "Normal Activity"

        # Compare every pair of detected tracked humans
        for i in range(len(people)):
            p1 = people[i]
            tid1 = p1["track_id"]
            c1 = p1["anchor"]
            traj1 = p1.get("trajectory", [])
            
            for j in range(i + 1, len(people)):
                p2 = people[j]
                tid2 = p2["track_id"]
                c2 = p2["anchor"]
                traj2 = p2.get("trajectory", [])
                
                # Metric A: Calculate Proximity (Centroid distance)
                dx = c1[0] - c2[0]
                dy = c1[1] - c2[1]
                distance = math.sqrt(dx**2 + dy**2)
                
                # Proximity indicator: True if they are extremely close/overlapping (distance < 90px)
                is_close = distance < 90.0
                
                # Metric B: Calculate velocities and acceleration spikes
                v1_speed = 0.0
                v2_speed = 0.0
                erratic_motion = False
                
                if len(traj1) >= 3 and len(traj2) >= 3:
                    # Calculate vector changes
                    vec1_prev = (traj1[-2][0] - traj1[-3][0], traj1[-2][1] - traj1[-3][1])
                    vec1_curr = (traj1[-1][0] - traj1[-2][0], traj1[-1][1] - traj1[-2][1])
                    
                    vec2_prev = (traj2[-2][0] - traj2[-3][0], traj2[-2][1] - traj2[-3][1])
                    vec2_curr = (traj2[-1][0] - traj2[-2][0], traj2[-1][1] - traj2[-2][1])
                    
                    # Calculate trajectory angles
                    angle1 = self.calculate_vector_angle(vec1_prev, vec1_curr)
                    angle2 = self.calculate_vector_angle(vec2_prev, vec2_curr)
                    
                    # Calculate speeds
                    v1_speed = math.sqrt(vec1_curr[0]**2 + vec1_curr[1]**2)
                    v2_speed = math.sqrt(vec2_curr[0]**2 + vec2_curr[1]**2)
                    
                    # Erratic indicator: sudden trajectory direction shift (angle > 75 degrees) with high speed
                    if (angle1 > 75.0 and v1_speed > 12.0) or (angle2 > 75.0 and v2_speed > 12.0):
                        erratic_motion = True

                # Metric C: Human bounding box intersection / repeated overlap
                box1 = p1["bbox"]
                box2 = p2["bbox"]
                
                # Check bounding box overlap ratio (Intersection over Union - IoU style)
                ix1 = max(box1[0], box2[0])
                iy1 = max(box1[1], box2[1])
                ix2 = min(box1[2], box2[2])
                iy2 = min(box1[3], box2[3])
                
                i_area = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                
                # Bounding boxes overlap if area of intersection is greater than zero
                is_overlapping = i_area > 0

                # --- Core Aggression Probability Matrix Scoring ---
                aggression_score = 0.0
                
                if is_close:
                    aggression_score += 0.25
                if is_overlapping:
                    aggression_score += 0.25
                if erratic_motion:
                    aggression_score += 0.20
                    
                # High speed physical contact adds substantial threat scoring points
                if is_close and (v1_speed > 15.0 or v2_speed > 15.0):
                    aggression_score += 0.30
                    
                if aggression_score > max_prob:
                    max_prob = aggression_score
                    
                if max_prob >= 0.65:
                    violence_detected = True
                    details = f"PHYSICAL ALTERCATION WARNING: Target #{tid1} and Target #{tid2} exhibiting highly aggressive overlap patterns."
                    break
            
            if violence_detected:
                break
                
        return violence_detected, round(max_prob, 2), details
