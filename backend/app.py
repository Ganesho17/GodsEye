"""
backend/app.py
God's Eye — Flask Application Entry Point

Preserves ALL existing API routes unchanged.
Adds new routes modularly:
  - /api/cameras             (CRUD for camera device registry)
  - /api/cameras/<id>/stream (per-camera MJPEG stream)
  - /api/cameras/<id>/stats  (per-camera telemetry)
  - /api/cameras/<id>/zone   (zone coordinates update)
  - /api/alerts              (replaces /api/logs with richer response)
  - /api/alerts/<id>/resolve
  - /api/alerts/resolve-all
  - /api/alerts/stats
  - /api/crowd/history
"""

import time
import json
import queue
import sys
import os

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

# Add root folder to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database.database as database
from backend.detector import IntelligentDetector

# -----------------------------------------------------------------------
# App Setup
# -----------------------------------------------------------------------
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

database.init_db()
detector = IntelligentDetector()

SCREENSHOTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../screenshots'))
os.makedirs(os.path.join(SCREENSHOTS_DIR, 'raw'),       exist_ok=True)
os.makedirs(os.path.join(SCREENSHOTS_DIR, 'annotated'), exist_ok=True)


# -----------------------------------------------------------------------
# Static / Frontend
# -----------------------------------------------------------------------

@app.route('/')
def index():
    return app.send_static_file('index.html')




# -----------------------------------------------------------------------
# EXISTING ROUTES (unchanged — backward compatible)
# -----------------------------------------------------------------------

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Returns current system metrics for the primary camera (cam_0)."""
    stats = detector.get_camera_stats("cam_0")
    # Flatten for backward compatibility with old frontend format
    stats.update({
        "active_unattended_objects": detector.active_unattended_objects,
        "unattended_item_counts":    detector.unattended_item_counts,
        "active_diagnostics":        detector.active_diagnostics,
        "yolo_loaded":               detector.yolo.model_loaded,
    })
    return jsonify(stats)


@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Gets or updates detection configuration for the primary camera."""
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        detector.update_settings(data, camera_id="cam_0")
        return jsonify({"message": "Settings updated", "settings": data})
    else:
        p = detector.get_pipeline("cam_0")
        settings = {
            "crowd_threshold":     p.crowd_threshold    if p else 5,
            "zone_coords":         p.zone_coords        if p else [],
            "use_webcam":          not (p.use_mock      if p else True),
            "peak_start":          p.peak_start         if p else 8,
            "peak_end":            p.peak_end           if p else 18,
            "loitering_threshold": p.loitering_threshold if p else 10.0
        }
        return jsonify(settings)


@app.route('/api/video_feed')
def video_feed():
    """Primary MJPEG stream (cam_0) — preserved for backward compatibility."""
    def gen():
        while True:
            frame = detector.get_latest_frame("cam_0")
            if frame is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.04)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/alerts/stream')
def alerts_stream():
    """SSE stream for the primary camera (cam_0) — preserved unchanged."""
    def event_stream():
        yield f"data: {json.dumps({'type': 'SYSTEM', 'message': 'Connected to live alarm server.'})}\n\n"
        p = detector.get_pipeline("cam_0")
        if p is None:
            return
        while True:
            try:
                alert = p.alert_queue.get(timeout=12.0)
                yield f"data: {json.dumps(alert)}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'PING'})}\n\n"
            except Exception as e:
                print(f"SSE stream error: {e}")
                break

    resp = Response(event_stream(), mimetype='text/event-stream')
    resp.headers['Cache-Control']    = 'no-cache'
    resp.headers['Connection']       = 'keep-alive'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


@app.route('/api/logs', methods=['GET', 'DELETE'])
def handle_logs():
    """Existing logs endpoint — preserved for backward compatibility."""
    if request.method == 'DELETE':
        database.clear_incidents()
        return jsonify({"message": "Logs cleared."})

    threat_filter = request.args.get('threat_level', 'ALL')
    logs = database.get_incidents(threat_level=threat_filter)
    _enrich_logs(logs)
    return jsonify(logs)


# -----------------------------------------------------------------------
# NEW: CAMERA MANAGEMENT ROUTES
# -----------------------------------------------------------------------

@app.route('/api/cameras', methods=['GET'])
def list_cameras():
    """Returns all registered camera devices from DB + active status."""
    db_devices = database.get_devices()

    # Merge with live pipeline status
    active_ids = set(detector.get_all_camera_ids())
    for dev in db_devices:
        dev['is_active'] = dev['id'] in active_ids

    # If no devices registered yet, return default cam_0
    if not db_devices:
        db_devices = [{
            'id':         'cam_0',
            'name':       'Primary Webcam',
            'type':       'webcam',
            'source':     '0',
            'location':   'Local System',
            'is_active':  True,
            'created_at': 'System Default',
            'zone_coordinates': json.dumps([[0.02, 0.55], [0.45, 0.55], [0.45, 0.98], [0.02, 0.98]])
        }]

    return jsonify(db_devices)


@app.route('/api/cameras', methods=['POST'])
def add_camera():
    """Registers a new camera device and starts its pipeline."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    camera_id   = data.get('id', f"cam_{int(time.time())}")
    name        = data.get('name', 'Unnamed Camera')
    device_type = data.get('type', 'ip')
    source      = data.get('source', '')
    location    = data.get('location', 'Unknown')

    if not source:
        return jsonify({"error": "Camera source is required"}), 400

    success = detector.add_camera(camera_id, name, device_type, source, location)
    if success:
        return jsonify({"message": f"Camera '{name}' registered successfully.", "id": camera_id}), 201
    else:
        return jsonify({"error": "Camera ID already exists"}), 409


@app.route('/api/cameras/<camera_id>', methods=['PUT'])
def update_camera(camera_id):
    """Updates settings for a specific camera."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    detector.update_settings(data, camera_id=camera_id)
    return jsonify({"message": "Camera settings updated."})


@app.route('/api/cameras/<camera_id>', methods=['DELETE'])
def delete_camera(camera_id):
    """Removes a camera pipeline and registration."""
    if camera_id == "cam_0":
        return jsonify({"error": "Cannot remove the primary camera."}), 400
    success = detector.remove_camera(camera_id)
    if success:
        return jsonify({"message": f"Camera {camera_id} removed."})
    return jsonify({"error": "Camera not found."}), 404


@app.route('/api/cameras/<camera_id>/zone', methods=['POST'])
def update_camera_zone(camera_id):
    """Updates the restricted zone polygon for a specific camera."""
    data = request.get_json()
    if not data or 'zone_coordinates' not in data:
        return jsonify({"error": "zone_coordinates required"}), 400
    detector.update_settings({'zone_coords': data['zone_coordinates']}, camera_id=camera_id)
    return jsonify({"message": "Zone updated.", "zone_coordinates": data['zone_coordinates']})


@app.route('/api/cameras/<camera_id>/stream')
def camera_stream(camera_id):
    """Per-camera MJPEG stream endpoint."""
    def gen():
        while True:
            frame = detector.get_latest_frame(camera_id)
            if frame is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.04)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/cameras/<camera_id>/stats', methods=['GET'])
def camera_stats(camera_id):
    """Returns per-camera telemetry stats."""
    stats = detector.get_camera_stats(camera_id)
    if not stats:
        return jsonify({"error": f"Camera {camera_id} not found."}), 404
    return jsonify(stats)


@app.route('/api/cameras/<camera_id>/alerts/stream')
def camera_alerts_stream(camera_id):
    """SSE alert stream for a specific camera."""
    def event_stream():
        yield f"data: {json.dumps({'type': 'SYSTEM', 'message': f'Connected to alerts for camera {camera_id}.'})}\n\n"
        p = detector.get_pipeline(camera_id)
        if p is None:
            yield f"data: {json.dumps({'type': 'ERROR', 'message': 'Camera not found.'})}\n\n"
            return
        while True:
            try:
                alert = p.alert_queue.get(timeout=12.0)
                yield f"data: {json.dumps(alert)}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'PING'})}\n\n"
            except Exception:
                break

    resp = Response(event_stream(), mimetype='text/event-stream')
    resp.headers['Cache-Control']    = 'no-cache'
    resp.headers['Connection']       = 'keep-alive'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


# -----------------------------------------------------------------------
# NEW: ALERTS ROUTES (richer than /api/logs)
# -----------------------------------------------------------------------

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """
    Returns incident alerts with optional filters.
    Params: threat_level, camera_id, limit, is_resolved
    """
    threat_filter  = request.args.get('threat_level', 'ALL')
    camera_filter  = request.args.get('camera_id', None)
    limit          = int(request.args.get('limit', 200))
    is_resolved    = request.args.get('is_resolved', None)

    logs = database.get_incidents(threat_level=threat_filter, camera_id=camera_filter, limit=limit)

    # Optional resolved filter
    if is_resolved is not None:
        resolved_bool = is_resolved.lower() in ('true', '1', 'yes')
        logs = [l for l in logs if l['is_resolved'] == resolved_bool]

    _enrich_logs(logs)
    return jsonify(logs)


@app.route('/api/alerts/<int:alert_id>/resolve', methods=['PUT'])
def resolve_alert(alert_id):
    """Marks a single alert as resolved."""
    database.resolve_incident(alert_id)
    return jsonify({"message": f"Alert #{alert_id} resolved."})


@app.route('/api/alerts/resolve-all', methods=['POST'])
def resolve_all_alerts():
    """Bulk-resolves all outstanding alerts."""
    database.resolve_all_incidents()
    return jsonify({"message": "All alerts resolved."})


@app.route('/api/alerts/stats', methods=['GET'])
def alert_stats():
    """Returns summary statistics (total, unresolved, level breakdown)."""
    return jsonify(database.get_alert_stats())


# -----------------------------------------------------------------------
# NEW: CROWD ANALYTICS
# -----------------------------------------------------------------------

@app.route('/api/crowd/history', methods=['GET'])
def crowd_history():
    """Returns time-series crowd count data for charting."""
    camera_id = request.args.get('camera_id', None)
    hours     = int(request.args.get('hours', 24))
    limit     = int(request.args.get('limit', 500))
    data      = database.get_crowd_history(camera_id=camera_id, hours=hours, limit=limit)
    return jsonify(data)


@app.route('/api/crowd/surge', methods=['GET'])
def crowd_surge_status():
    """Returns current crowd surge status for all active cameras."""
    results = {}
    for cam_id in detector.get_all_camera_ids():
        p = detector.get_pipeline(cam_id)
        if p:
            results[cam_id] = {
                'camera_name':  p.camera_name,
                'crowd_count':  p.current_crowd_count,
                'crowd_density': p.crowd_density,
                'threat_level': p.current_threat_level,
                'threat_score': p.current_threat_score,
            }
    return jsonify(results)


# -----------------------------------------------------------------------
# AUTH STUBS (satisfy frontend JWT checks — no auth enforcement)
# -----------------------------------------------------------------------

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json() or {}
    return jsonify({
        "access_token": "godseye_local_token",
        "user": {"name": data.get("email", "Operator"), "role": "admin"}
    })


@app.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    data = request.get_json() or {}
    return jsonify({"message": "User created.", "user": {"name": data.get("name", "User"), "role": "operator"}})


@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    return jsonify({"name": "Operator", "role": "admin", "email": "admin@godseye.local"})


# -----------------------------------------------------------------------
# Helper: Enrich log records with descriptions and URLs
# -----------------------------------------------------------------------

@app.route('/api/screenshots/<path:filename>')
def serve_screenshot(filename):
    """Serves raw or annotated screenshots by relative path (supports subdirs)."""
    return send_from_directory(SCREENSHOTS_DIR, filename)

def _enrich_logs(logs):
    """In-place enrichment of log records with UI-ready fields."""
    for log in logs:
        if log.get('annotated_path'):
            log['screenshot_path'] = f"/api/screenshots/annotated/{log['annotated_path']}"
        elif log.get('screenshot'):
            log['screenshot_path'] = f"/api/screenshots/raw/{log['screenshot']}"
        else:
            log['screenshot_path'] = None
            
        log['snapshot'] = log['screenshot_path']

        itype  = log.get('incident_type', '')
        level  = log.get('threat_level', '')
        count  = log.get('crowd_count', 0)
        cam    = log.get('camera_name', 'Unknown Camera')

        if itype == 'INTRUSION':
            log['description'] = f"RESTRICTED AREA INTRUSION detected on {cam}."
        elif itype == 'WEAPON':
            log['description'] = f"WEAPON DETECTED on {cam}. Immediate response required."
        elif itype == 'CROWD_ALERT':
            log['description'] = f"CROWD ALERT on {cam}: {count} persons detected."
        elif itype == 'UNATTENDED_OBJECT':
            log['description'] = f"UNATTENDED OBJECT in secure zone on {cam}."
        else:
            log['description'] = log.get('explanation') or f"Security event detected on {cam}."

        log['summary'] = log.get('explanation') or log['description']


if __name__ == '__main__':
    print("GodsEye backend starting on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True)