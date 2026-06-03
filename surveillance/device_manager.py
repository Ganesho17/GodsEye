"""
surveillance/device_manager.py
God's Eye — Multi-Camera Device Registry & Connection Manager

Manages a live registry of connected camera devices:
  - Laptop webcam (index 0)
  - USB cameras (index 1+)
  - Android IP Webcam streams (http://192.168.x.x:8080/video)
  - IP CCTV / RTSP streams
  - Any cv2.VideoCapture-compatible source

Provides:
  - register_device()    : add a new camera to the registry
  - remove_device()      : disconnect and remove a camera
  - get_active_devices() : return list of all registered devices
  - get_device_cap()     : return the cv2.VideoCapture handle for a device
  - reconnect_device()   : manually trigger a reconnection attempt
"""

import cv2
import threading
import time
import uuid
from datetime import datetime


class CameraDevice:
    """Represents a single registered camera device with connection state."""

    def __init__(self, device_id, name, device_type, source, location="Unknown"):
        self.id = device_id
        self.name = name
        # type: 'webcam' | 'usb' | 'ip' | 'rtsp'
        self.device_type = device_type
        # source: int for webcam/USB, str URL for IP/RTSP
        self.source = source
        self.location = location

        self.cap = None
        self.is_active = False
        self.last_seen = None
        self.error_count = 0
        self.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Per-device lock for thread-safe frame access
        self._lock = threading.Lock()
        self._reconnect_thread = None
        self._stop_event = threading.Event()

    def connect(self):
        """Attempt to open the video capture source."""
        if self.device_type == 'phone':
            with self._lock:
                self.cap = None
                self.is_active = False  # Set to active once a frame is uploaded
                self.latest_frame = None
                self.last_seen = None
                self.error_count = 0
            print(f"[DeviceManager] Phone camera source '{self.name}' initialized (ID: {self.id})")
            return True

        try:
            src = int(self.source) if self.device_type in ('webcam', 'usb') else self.source
            cap = cv2.VideoCapture(src)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                # Minimize internal buffer lag
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                with self._lock:
                    self.cap = cap
                    self.is_active = True
                    self.last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.error_count = 0
                print(f"[DeviceManager] Camera '{self.name}' connected (source: {self.source})")
                return True
            else:
                cap.release()
                self.is_active = False
                print(f"[DeviceManager] Camera '{self.name}' failed to open (source: {self.source})")
                return False
        except Exception as e:
            self.is_active = False
            print(f"[DeviceManager] Camera '{self.name}' connection error: {e}")
            return False

    def disconnect(self):
        """Release the capture handle and mark device as offline."""
        self._stop_event.set()
        with self._lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.is_active = False
        print(f"[DeviceManager] Camera '{self.name}' disconnected.")

    def update_phone_frame(self, frame):
        """Update frame received from the phone camera."""
        with self._lock:
            self.latest_frame = frame
            self.is_active = True
            self.last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.error_count = 0

    def read_frame(self):
        """Thread-safe frame read. Returns (success, frame) tuple."""
        with self._lock:
            if self.device_type == 'phone':
                if hasattr(self, 'latest_frame') and self.latest_frame is not None:
                    # Mark offline if no upload in 10 seconds
                    if self.last_seen:
                        try:
                            last_seen_dt = datetime.strptime(self.last_seen, '%Y-%m-%d %H:%M:%S')
                            if (datetime.now() - last_seen_dt).total_seconds() > 10.0:
                                self.is_active = False
                                return False, None
                        except Exception:
                            pass
                    return True, self.latest_frame
                return False, None

            if self.cap is None or not self.cap.isOpened():
                return False, None
            ret, frame = self.cap.read()
            if ret:
                self.last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            else:
                self.error_count += 1
                if self.error_count > 5:
                    self.is_active = False
            return ret, frame

    def start_auto_reconnect(self, max_retries=10, base_delay=2.0):
        """
        Launches a background thread that tries to reconnect with
        exponential backoff when the camera drops connection.
        """
        def _reconnect_loop():
            retries = 0
            while not self._stop_event.is_set() and retries < max_retries:
                time.sleep(min(base_delay * (2 ** retries), 60.0))  # Max 60s wait
                if self._stop_event.is_set():
                    break
                print(f"[DeviceManager] Reconnecting '{self.name}' (attempt {retries + 1}/{max_retries})...")
                if self.connect():
                    print(f"[DeviceManager] '{self.name}' reconnected successfully.")
                    return
                retries += 1
            print(f"[DeviceManager] '{self.name}' max reconnect attempts reached. Marked offline.")

        self._reconnect_thread = threading.Thread(target=_reconnect_loop, daemon=True)
        self._reconnect_thread.start()

    def to_dict(self):
        """Serialize device state as a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.device_type,
            "source": str(self.source),
            "location": self.location,
            "is_active": self.is_active,
            "last_seen": self.last_seen,
            "error_count": self.error_count,
            "created_at": self.created_at
        }


class DeviceManager:
    """
    Central singleton registry for all registered camera devices.
    Thread-safe — safe to call from multiple Flask/detection threads.
    """

    def __init__(self):
        # device_id -> CameraDevice
        self._devices = {}
        self._lock = threading.Lock()

    def register_device(self, name, device_type, source, location="Unknown", device_id=None):
        """
        Register a new camera device and attempt initial connection.

        Parameters:
            name:        Human-readable label (e.g., 'Gate Camera')
            device_type: 'webcam' | 'usb' | 'ip' | 'rtsp'
            source:      Camera index (int) or URL string
            location:    Descriptive location label
            device_id:   Optional explicit ID; auto-generated UUID if not provided

        Returns:
            CameraDevice instance
        """
        if device_id is None:
            device_id = str(uuid.uuid4())[:8]

        device = CameraDevice(device_id, name, device_type, source, location)

        # Attempt initial connection in background to avoid blocking Flask startup
        def _init_connect():
            connected = device.connect()
            if not connected:
                device.start_auto_reconnect()

        threading.Thread(target=_init_connect, daemon=True).start()

        with self._lock:
            self._devices[device_id] = device

        print(f"[DeviceManager] Registered device: '{name}' (ID: {device_id}, type: {device_type})")
        return device

    def remove_device(self, device_id):
        """Disconnect and remove a device from the registry."""
        with self._lock:
            device = self._devices.pop(device_id, None)

        if device:
            device.disconnect()
            print(f"[DeviceManager] Removed device ID: {device_id}")
            return True
        return False

    def get_device(self, device_id):
        """Returns the CameraDevice for a given ID, or None."""
        with self._lock:
            return self._devices.get(device_id)

    def get_active_devices(self):
        """Returns a list of all registered device dicts."""
        with self._lock:
            return [d.to_dict() for d in self._devices.values()]

    def get_device_cap(self, device_id):
        """Returns the cv2.VideoCapture handle for a device (or None)."""
        device = self.get_device(device_id)
        if device:
            return device.cap
        return None

    def read_frame(self, device_id):
        """Read a frame from the specified device. Returns (success, frame)."""
        device = self.get_device(device_id)
        if device:
            return device.read_frame()
        return False, None

    def reconnect_device(self, device_id):
        """Manually trigger reconnection for a device."""
        device = self.get_device(device_id)
        if device:
            device._stop_event.clear()
            device.start_auto_reconnect()
            return True
        return False

    def get_device_ids(self):
        """Returns a list of all registered device IDs."""
        with self._lock:
            return list(self._devices.keys())

    def register_default_webcam(self):
        """
        Registers the default system webcam (camera index 0) as the
        primary surveillance device. Called automatically on startup.
        """
        return self.register_device(
            name="Primary Webcam",
            device_type="webcam",
            source=0,
            location="Local System",
            device_id="cam_0"
        )


# Global singleton instance — import this in detector.py and app.py
device_manager = DeviceManager()
