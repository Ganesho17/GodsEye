"""
surveillance/crowd_surge.py
God's Eye — Standalone Crowd Surge Detection Module

Monitors crowd count time-series data to detect sudden abnormal gatherings.
Supports configurable:
  - surge_threshold   : minimum crowd count delta to classify as a surge
  - surge_window_sec  : time window for rate-of-change calculation
  - off_peak multiplier: 1.5x threat score escalation outside business hours

Usage:
    from surveillance.crowd_surge import CrowdSurgeDetector
    surge = CrowdSurgeDetector(peak_start=8, peak_end=18)
    result = surge.update(current_person_count)
    if result['is_surge']:
        print("CROWD SURGE DETECTED!")
"""

import time
import threading
from datetime import datetime


class CrowdSurgeDetector:
    """
    Tracks crowd count history and detects sudden surges using
    a rate-of-change approach over a configurable sliding time window.
    """

    def __init__(self,
                 peak_start=8,
                 peak_end=18,
                 surge_threshold=3,
                 surge_window_sec=2.0,
                 history_max_sec=30.0):
        """
        Parameters:
            peak_start      : Hour (0–23) when peak operational hours begin
            peak_end        : Hour (0–23) when peak operational hours end
            surge_threshold : Minimum person count delta that counts as a surge
            surge_window_sec: Look-back window in seconds for surge calculation
            history_max_sec : Maximum age of crowd data points to retain
        """
        self.peak_start       = peak_start
        self.peak_end         = peak_end
        self.surge_threshold  = surge_threshold
        self.surge_window_sec = surge_window_sec
        self.history_max_sec  = history_max_sec

        # Time-series buffer: list of (timestamp, count)
        self._history = []
        self._lock    = threading.Lock()

        # Rolling baseline (exponential moving average)
        self._baseline = 0.0
        self._baseline_alpha = 0.05  # Slow-adapting baseline

    # ------------------------------------------------------------------ #
    #  PUBLIC API                                                          #
    # ------------------------------------------------------------------ #

    def update(self, current_count):
        """
        Feed the current frame's person count and compute surge status.

        Returns a dict:
          {
            'is_surge':            bool,
            'surge_rate':          float  (persons per second),
            'count_delta':         int    (change in count over window),
            'current':             int,
            'baseline':            float,
            'is_outside_peak':     bool,
            'off_peak_multiplier': float  (1.0 or 1.5),
            'crowd_density':       str    ('LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL')
          }
        """
        current_time = time.time()

        with self._lock:
            # Append current reading and prune stale history
            self._history.append((current_time, current_count))
            self._history = [
                pt for pt in self._history
                if current_time - pt[0] <= self.history_max_sec
            ]

            # Update rolling baseline (slow EMA)
            if self._baseline == 0.0:
                self._baseline = float(current_count)
            else:
                self._baseline = (self._baseline_alpha * current_count
                                  + (1 - self._baseline_alpha) * self._baseline)

            # Compute rate of change over the surge window
            is_surge    = False
            surge_rate  = 0.0
            count_delta = 0

            if len(self._history) >= 2:
                # Find oldest point within the surge window
                window_pts = [pt for pt in self._history
                              if current_time - pt[0] <= self.surge_window_sec]
                if len(window_pts) >= 2:
                    oldest = window_pts[0]
                    dt     = current_time - oldest[0]
                    count_delta = current_count - oldest[1]

                    if dt > 0.1:
                        surge_rate = count_delta / dt

                    # Surge = rapid positive growth exceeding threshold
                    if count_delta >= self.surge_threshold and dt > 0.3:
                        is_surge = True

            # Off-peak hour detection
            is_outside_peak     = self._check_outside_peak()
            off_peak_multiplier = 1.5 if is_outside_peak else 1.0

            # Crowd density classification
            crowd_density = self._classify_density(current_count)

        return {
            'is_surge':            is_surge,
            'surge_rate':          round(surge_rate, 2),
            'count_delta':         count_delta,
            'current':             current_count,
            'baseline':            round(self._baseline, 1),
            'is_outside_peak':     is_outside_peak,
            'off_peak_multiplier': off_peak_multiplier,
            'crowd_density':       crowd_density
        }

    def reset(self):
        """Clear all history (e.g., on camera reset)."""
        with self._lock:
            self._history.clear()
            self._baseline = 0.0

    def get_crowd_history(self, max_points=100):
        """
        Returns recent crowd count history as a list of
        {'timestamp': str, 'count': int} dicts — suitable for API responses.
        """
        with self._lock:
            recent = self._history[-max_points:]
        return [
            {
                'timestamp': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'),
                'count': cnt
            }
            for ts, cnt in recent
        ]

    # ------------------------------------------------------------------ #
    #  PRIVATE HELPERS                                                     #
    # ------------------------------------------------------------------ #

    def _check_outside_peak(self):
        """Returns True if the current time falls outside peak hours."""
        now          = datetime.now()
        current_hour = now.hour + now.minute / 60.0

        if self.peak_start <= self.peak_end:
            # Daytime window (e.g., 08:00–18:00)
            is_peak = self.peak_start <= current_hour <= self.peak_end
        else:
            # Overnight window (e.g., 22:00–06:00)
            is_peak = current_hour >= self.peak_start or current_hour <= self.peak_end

        return not is_peak

    @staticmethod
    def _classify_density(count):
        """Classifies crowd density into a categorical label."""
        if count <= 2:
            return 'LOW'
        elif count <= 6:
            return 'MEDIUM'
        elif count <= 15:
            return 'HIGH'
        else:
            return 'CRITICAL'
