import datetime
from backend.app.core.config import settings

class ThreatMatrixEvaluator:
    @staticmethod
    def calculate_threat(
        has_intrusion: bool,
        has_weapon: bool,
        has_violence: bool,
        crowd_count: int,
        has_running: bool,
        has_loitering: bool
    ) -> tuple:
        """
        Dynamically calculates a numeric threat score (0-100) and maps it to a level.
        Incorporates specific weighting indices:
          - Weapon Detected: +40
          - Violence Warning: +35
          - Restricted Intrusion: +30
          - Crowd Surge: +20
          - Running/Abnormal movement: +10
          - Loitering detected: +5
        
        Applies a temporal scaling modifier: during configured peak hours, crowd-based
        threat points scale higher, and ambient risk shifts dynamically.
        
        Returns:
            threat_score (int): Scaled value clamped from 0 to 100
            threat_level (str): LOW, MEDIUM, HIGH, or CRITICAL
        """
        score = 0
        
        # 1. Base heuristic points aggregation
        if has_weapon:
            score += 40
        if has_violence:
            score += 35
        if has_intrusion:
            score += 30
        if has_running:
            score += 10
        if has_loitering:
            score += 5
            
        # 2. Crowd Surge evaluation
        # If crowd count exceeds the configured crowd threshold, apply crowd surge points
        if crowd_count >= settings.CROWD_THRESHOLD:
            score += 20
            
        # 3. Peak Hour Scaling Modifiers
        current_hour = datetime.datetime.now().hour
        is_peak_hour = settings.PEAK_START <= current_hour <= settings.PEAK_END
        
        if is_peak_hour:
            # During peak security hours, raise threat margins slightly to trigger alert sensitives
            if crowd_count > settings.CROWD_THRESHOLD * 1.5:
                score += 10
        else:
            # During off-peak hours (night/early morning), any single motion is slightly higher risk
            if has_intrusion or has_running:
                score += 5

        # Clamp threat score between 0 and 100
        threat_score = max(0, min(100, score))
        
        # 4. Map to threat level categorizations
        if threat_score <= 15:
            threat_level = "LOW"
        elif threat_score <= 35:
            threat_level = "MEDIUM"
        elif threat_score <= 60:
            threat_level = "HIGH"
        else:
            threat_level = "CRITICAL"
            
        return threat_score, threat_level
