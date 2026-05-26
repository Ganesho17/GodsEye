"""
surveillance/threat_score.py
God's Eye — Centralized Threat Score Engine

Calculates a numeric threat score (0–100) from active behavioral events
and maps it to a categorical threat level.

Updated Scoring Matrix:
  +40  WEAPON detected
  +30  Restricted zone intrusion (perimeter breach)
  +20  Abnormal crowd surge
  +15  Suspicious movement (running)
  +10  Loitering detected
  +10  Crowd limit exceeded

Threat Levels:
  CRITICAL  score > 70
  HIGH      score > 35
  MEDIUM    score > 15
  LOW       score 0–15

Off-peak multiplier:
  If the crowd limit is exceeded outside configured peak hours → score × 1.5
"""

from datetime import datetime


class ThreatScoreEngine:
    """
    Evaluates real-time behavioral events and produces a calibrated
    threat score with automatic level classification.

    Compatible with all existing callers — calculate_threat() signature
    is preserved with no breaking changes.
    """

    def __init__(self, peak_start=8, peak_end=18):
        """
        Parameters:
            peak_start: Hour (0-23) when peak business hours begin
            peak_end:   Hour (0-23) when peak business hours end
        """
        self.peak_start = peak_start
        self.peak_end   = peak_end

        # ---- Threat Score Weight Table ----
        self.WEIGHTS = {
            'WEAPON':              40,   # Weapon detected in frame
            'INTRUSION':           30,   # Restricted zone perimeter breach
            'SURGE':               20,   # Rapid abnormal crowd growth
            'RUNNING':             15,   # Abnormal movement speed / panic running
            'LOITERING':           10,   # Persistent presence beyond threshold
            'CROWD_LIMIT_EXCEEDED': 10,  # Crowd count above configured max
        }

        # ---- Threat Level Thresholds ----
        self.THRESHOLDS = {
            'CRITICAL': 70,
            'HIGH':     35,
            'MEDIUM':   15,
            # LOW = everything below MEDIUM
        }

    def check_peak_hours(self):
        """
        Checks whether the current time falls outside peak operational hours.
        Supports both same-day ranges (08:00–18:00) and overnight ranges (22:00–06:00).

        Returns:
            True if OUTSIDE peak hours (off-peak), False if within peak hours.
        """
        now          = datetime.now()
        current_hour = now.hour + now.minute / 60.0

        if self.peak_start <= self.peak_end:
            # Standard daytime range
            is_peak = self.peak_start <= current_hour <= self.peak_end
        else:
            # Overnight/wraparound range
            is_peak = current_hour >= self.peak_start or current_hour <= self.peak_end

        return not is_peak  # Return True if OFF-peak

    def calculate_threat(self, active_behaviors, has_weapon, crowd_count, crowd_threshold):
        """
        Calculates the threat score and level from active surveillance events.

        Parameters:
            active_behaviors: dict from BehaviorAnalyzer.update()
            has_weapon:       bool — weapon detected in the current frame
            crowd_count:      int  — number of persons detected this frame
            crowd_threshold:  int  — user-configured crowd capacity limit

        Returns:
            Tuple (threat_score: int, threat_level: str, triggers: list[str])
        """
        score    = 0
        triggers = []

        # 1. ---- Weapon Detected ----
        if has_weapon:
            score += self.WEIGHTS['WEAPON']
            triggers.append('WEAPON_DETECTED')

        # 2. ---- Restricted Zone Intrusion ----
        if active_behaviors.get('is_restricted_breached', False):
            score += self.WEIGHTS['INTRUSION']
            triggers.append('PERIMETER_BREACH')

        # 3. ---- Crowd Surge ----
        if active_behaviors.get('crowd_surge', False):
            score += self.WEIGHTS['SURGE']
            triggers.append('CROWD_SURGE')

        # 4. ---- Abnormal Movement Speed (Running) ----
        if len(active_behaviors.get('running_ids', [])) > 0:
            score += self.WEIGHTS['RUNNING']
            triggers.append('ABNORMAL_SPEED')

        # 5. ---- Loitering ----
        if len(active_behaviors.get('loitering_ids', [])) > 0:
            score += self.WEIGHTS['LOITERING']
            triggers.append('LOITERING')

        # 6. ---- Crowd Limit Enforcement ----
        is_outside_peak    = self.check_peak_hours()
        is_crowd_exceeded  = crowd_count > crowd_threshold

        if is_crowd_exceeded:
            # Only add crowd score if surge wasn't already counted (avoid double-counting)
            if 'CROWD_SURGE' not in triggers:
                score += self.WEIGHTS['CROWD_LIMIT_EXCEEDED']
                triggers.append('CROWD_LIMIT_EXCEEDED')

            # Off-peak amplifier: 1.5× multiplier when crowd is high outside business hours
            if is_outside_peak:
                score = int(score * 1.5)
                triggers.append('OFF_PEAK_ESCALATION')

        # 7. ---- Clamp and Classify ----
        score = min(100, max(0, score))

        if score >= self.THRESHOLDS['CRITICAL']:
            level = 'CRITICAL'
        elif score >= self.THRESHOLDS['HIGH']:
            level = 'HIGH'
        elif score >= self.THRESHOLDS['MEDIUM']:
            level = 'MEDIUM'
        else:
            level = 'LOW'

        return score, level, triggers
