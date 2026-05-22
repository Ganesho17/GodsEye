from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.db.models import Incident, Camera
from datetime import datetime, timedelta

def get_system_analytics(db: Session) -> dict:
    """
    Aggregates database records to return premium dashboard telemetry.
    Generates dataset mappings tailored directly for Recharts panels:
      - Threat level distributions
      - Hourly incident occurrence timelines
      - Alert frequency distributions
      - Camera threat summaries
    """
    # 1. Broad statistics
    total_incidents = db.query(Incident).count()
    unresolved_incidents = db.query(Incident).filter(Incident.is_resolved == False).count()
    critical_incidents = db.query(Incident).filter(Incident.threat_level == "CRITICAL").count()
    active_cameras = db.query(Camera).filter(Camera.is_active == True).count()
    
    # 2. Threat level classification ratios (for Pie Charts)
    threat_levels = db.query(
        Incident.threat_level, func.count(Incident.id)
    ).group_by(Incident.threat_level).all()
    
    threat_level_dist = {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0
    }
    for level, count in threat_levels:
        if level in threat_level_dist:
            threat_level_dist[level] = count
            
    pie_data = [
        {"name": k, "value": v, "color": c} for k, v, c in [
            ("LOW", threat_level_dist["LOW"], "#10B981"),       # Neon Emerald
            ("MEDIUM", threat_level_dist["MEDIUM"], "#F59E0B"),   # Glowing Amber
            ("HIGH", threat_level_dist["HIGH"], "#EF4444"),       # Vibrant Red
            ("CRITICAL", threat_level_dist["CRITICAL"], "#8B5CF6") # Deep Violet
        ]
    ]

    # 3. Incident Type Frequency (for Bar Charts)
    types_query = db.query(
        Incident.incident_type, func.count(Incident.id)
    ).group_by(Incident.incident_type).all()
    
    bar_data = []
    type_colors = {
        "INTRUSION": "#3B82F6",      # Cyber Blue
        "WEAPON": "#EF4444",         # Red Alert
        "VIOLENCE": "#EC4899",       # Hot Pink
        "CROWD_ALERT": "#10B981",    # Emerald
        "UNATTENDED_OBJECT": "#F59E0B" # Amber
    }
    
    for inc_type, count in types_query:
        bar_data.append({
            "type": inc_type,
            "count": count,
            "color": type_colors.get(inc_type, "#64748B")
        })

    # Ensure empty categories are initialized to display cleanly
    tracked_types = ["INTRUSION", "WEAPON", "VIOLENCE", "CROWD_ALERT", "UNATTENDED_OBJECT"]
    found_types = [b["type"] for b in bar_data]
    for t in tracked_types:
        if t not in found_types:
            bar_data.append({
                "type": t,
                "count": 0,
                "color": type_colors[t]
            })

    # 4. Hourly Timeline Aggregations (for Line Charts over the last 12 hours)
    now = datetime.utcnow()
    timeline_data = []
    
    for i in range(11, -1, -1):
        target_hour = now - timedelta(hours=i)
        start_time = target_hour.replace(minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        
        count = db.query(Incident).filter(
            Incident.timestamp >= start_time,
            Incident.timestamp < end_time
        ).count()
        
        avg_score = db.query(func.avg(Incident.threat_score)).filter(
            Incident.timestamp >= start_time,
            Incident.timestamp < end_time
        ).scalar() or 0
        
        timeline_data.append({
            "hour": start_time.strftime("%H:00"),
            "incidents": count,
            "average_threat": round(float(avg_score), 1)
        })

    # 5. Camera Threat Rank Summaries (for rankings list)
    cam_ranks = []
    cams = db.query(Camera).all()
    for cam in cams:
        inc_count = db.query(Incident).filter(Incident.camera_id == cam.id).count()
        max_threat = db.query(func.max(Incident.threat_score)).filter(Incident.camera_id == cam.id).scalar() or 0
        cam_ranks.append({
            "camera_id": cam.id,
            "name": cam.name,
            "location": cam.location,
            "incidents_count": inc_count,
            "max_threat": max_threat
        })
        
    cam_ranks = sorted(cam_ranks, key=lambda x: x["incidents_count"], reverse=True)[:5]

    return {
        "summary": {
            "total_incidents": total_incidents,
            "unresolved_incidents": unresolved_incidents,
            "critical_incidents": critical_incidents,
            "active_cameras": active_cameras
        },
        "pie_data": pie_data,
        "bar_data": bar_data,
        "timeline_data": timeline_data,
        "camera_rankings": cam_ranks
    }
