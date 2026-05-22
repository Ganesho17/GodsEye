from datetime import datetime

class ThreatScoreEngine:
    def __init__(self, peak_start=8, peak_end=18):
        """
        Initializes the Threat Score Engine.
        peak_start: hour of day when peak begins (0-23)
        peak_end: hour of day when peak ends (0-23)
        """
        self.peak_start = peak_start
        self.peak_end = peak_end
        
        # Threat score contribution values
        self.WEIGHTS = {
            'WEAPON': 40,
            'INTRUSION': 30,
            'SURGE': 20,
            'RUNNING': 10,
            'LOITERING': 5
        }

    def check_peak_hours(self):
        """
        Determines if the current system local time falls outside peak operational hours.
        Handles overnight intervals seamlessly.
        """
        now = datetime.now()
        current_hour = now.hour + now.minute / 60.0
        
        if self.peak_start <= self.peak_end:
            # Daytime range (e.g., 08:00 to 18:00)
            is_peak = self.peak_start <= current_hour <= self.peak_end
        else:
            # Overnight range (e.g., 22:00 to 06:00)
            is_peak = current_hour >= self.peak_start or current_hour <= self.peak_end
            
        return not is_peak

    def calculate_threat(self, active_behaviors, has_weapon, crowd_count, crowd_threshold):
        """
        Calculates the numeric threat score and maps it to a categorical threat level.
        
        Parameters:
            active_behaviors: dict returned by BehaviorAnalyzer
            has_weapon: bool indicating if any weapon was detected in the frame
            crowd_count: current count of people in frame
            crowd_threshold: user-configured crowd warning threshold
            
        Returns:
            threat_score: int from 0 to 100
            threat_level: str ('LOW', 'MEDIUM', 'HIGH')
            triggers: list of active threat triggers
        """
        score = 0
        triggers = []
        
        # 1. Evaluate individual threat factors
        if has_weapon:
            score += self.WEIGHTS['WEAPON']
            triggers.append("WEAPON_DETECTED")
            
        if active_behaviors.get('is_restricted_breached', False):
            score += self.WEIGHTS['INTRUSION']
            triggers.append("PERIMETER_BREACH")
            
        if active_behaviors.get('crowd_surge', False):
            score += self.WEIGHTS['SURGE']
            triggers.append("CROWD_SURGE")
            
        if len(active_behaviors.get('running_ids', [])) > 0:
            score += self.WEIGHTS['RUNNING']
            triggers.append("ABNORMAL_SPEED")
            
        if len(active_behaviors.get('loitering_ids', [])) > 0:
            score += self.WEIGHTS['LOITERING']
            triggers.append("LOITERING")
            
        # 2. Check Crowd Limits and Peak Operational Hours
        is_outside_peak = self.check_peak_hours()
        is_crowd_exceeded = crowd_count > crowd_threshold
        
        if is_crowd_exceeded:
            # Base crowd warning if not already triggered by surge
            if "CROWD_SURGE" not in triggers:
                score += 15
                triggers.append("CROWD_LIMIT_EXCEEDED")
                
            # If crowd threshold is exceeded outside peak hours, apply 1.5x severity multiplier
            if is_outside_peak:
                score = int(score * 1.5)
                triggers.append("OUT_OF_HOURS_SCALE")
                
        # Clamp threat score between 0 and 100
        score = min(100, max(0, score))
        
        # 3. Categorize numeric score into levels
        if score > 35:
            level = "HIGH"
        elif score > 15:
            level = "MEDIUM"
        else:
            level = "LOW"
            
        return score, level, triggers
