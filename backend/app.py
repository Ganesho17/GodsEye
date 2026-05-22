import time
import json
import queue
import sys
import os
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

# Add root folder to sys.path to enable modular package imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database.database as database
from backend.detector import IntelligentDetector

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)  # Enable Cross-Origin Resource Sharing for easy React communication

# Ensure database is initialized
database.init_db()

# Initialize our singleton Intelligent Detector coordinator
detector = IntelligentDetector()

# Directory for screenshots
SCREENSHOTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../screenshots'))
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

@app.route('/')
def index():
    """Serves the main frontend React application dashboard."""
    return app.send_static_file('index.html')

@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    """Serves alert snapshots stored on disk statically."""
    return send_from_directory(SCREENSHOTS_DIR, filename)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Returns current system metrics, active diagnostics, and configurations."""
    stats = {
        "crowd_count": detector.current_crowd_count,
        "threat_level": detector.current_threat_level,
        "threat_score": detector.current_threat_score,
        "active_intruders": detector.active_intruders,
        "active_unattended_objects": detector.active_unattended_objects,
        "item_counts": detector.current_item_counts,
        "unattended_item_counts": detector.unattended_item_counts,
        "active_diagnostics": detector.active_diagnostics,
        
        # Settings
        "crowd_threshold": detector.crowd_threshold,
        "use_webcam": detector.use_webcam,
        "zone_coords": detector.zone_coords,
        "peak_start": detector.peak_start,
        "peak_end": detector.peak_end,
        "loitering_threshold": detector.loitering_threshold,
        
        "yolo_loaded": detector.yolo.model_loaded
    }
    return jsonify(stats)

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Handles getting or updating detection configurations in real-time."""
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        detector.update_settings(data)
        return jsonify({"message": "Settings updated successfully", "settings": data})
    else:
        settings = {
            "crowd_threshold": detector.crowd_threshold,
            "zone_coords": detector.zone_coords,
            "use_webcam": detector.use_webcam,
            "peak_start": detector.peak_start,
            "peak_end": detector.peak_end,
            "loitering_threshold": detector.loitering_threshold
        }
        return jsonify(settings)

@app.route('/api/video_feed')
def video_feed():
    """MJPEG stream endpoint. Returns the continuously updated detection feed."""
    def gen():
        while True:
            frame = detector.get_latest_frame()
            if frame is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.04)  # Read at ~25 FPS
            
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/alerts/stream')
def alerts_stream():
    """Server-Sent Events (SSE) route pushing instant security breaches to the dashboard."""
    def event_stream():
        # Connection established notification
        yield f"data: {json.dumps({'type': 'SYSTEM', 'message': 'Connected to live alarm server.'})}\n\n"
        
        while True:
            try:
                # Retrieve from queue. We use a 12s timeout to regularly send keep-alive pings.
                alert = detector.alert_queue.get(timeout=12.0)
                yield f"data: {json.dumps(alert)}\n\n"
            except queue.Empty:
                # Keep-alive Ping to prevent browser/proxy timeouts
                yield f"data: {json.dumps({'type': 'PING'})}\n\n"
            except Exception as e:
                print(f"SSE Client stream disconnected: {e}")
                break
                
    response = Response(event_stream(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'  # Prevents caching issues in standard reverse proxies
    return response

@app.route('/api/logs', methods=['GET', 'DELETE'])
def handle_logs():
    """Retrieve security incidents or wipe history."""
    if request.method == 'DELETE':
        database.clear_incidents()
        return jsonify({"message": "Incident logs successfully cleared."})
    else:
        threat_filter = request.args.get('threat_level', 'ALL')
        logs = database.get_incidents(threat_level=threat_filter)
        
        # Format the screenshots with static endpoint paths and add descriptions
        for log in logs:
            if log.get('screenshot'):
                # Make screenshot URL accessible via our static file endpoint
                log['snapshot'] = f"/screenshots/{log['screenshot']}"
            else:
                log['snapshot'] = None
                
            # Dynamically reconstruct event description if not present
            itype = log.get('incident_type')
            ccount = log.get('crowd_count', 0)
            level = log.get('threat_level')
            if itype == 'INTRUSION':
                if level == 'HIGH':
                    log['description'] = f"RESTRICTED AREA INTRUSION: Suspect breached secure perimeter."
                else:
                    log['description'] = "PERIMETER SECURE BREACH: Secure zone safety calculations exceeded threshold limit."
            elif itype == 'WEAPON':
                log['description'] = "CRITICAL WEAPON DETECTION: Suspect carrying an active weapon/firearm proxy spotted."
            elif itype == 'CROWD_ALERT':
                log['description'] = f"CROWD COUNT EXCEEDED: {ccount} persons present outside peak operational limits."
            elif itype == 'UNATTENDED_OBJECT':
                log['description'] = f"UNATTENDED OBJECT DETECTED inside secure zone."
            else:
                log['description'] = f"Security alert logged with threat score {log.get('threat_score')}."
                
        return jsonify(logs)

if __name__ == '__main__':
    print("GodsEye backend starting on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True)