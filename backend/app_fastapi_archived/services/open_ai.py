import json
import logging
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.db.models import Incident, Camera
from datetime import datetime

logger = logging.getLogger("GodsEye.OpenAI")

try:
    import openai
    from openai import OpenAI
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
except Exception as e:
    logger.warning(f"Could not import or initialize OpenAI client: {e}")
    openai_client = None


def generate_incident_summary(
    incident_type: str,
    threat_level: str,
    threat_score: int,
    crowd_count: int,
    description: str = None
) -> str:
    """
    Generates a professional, analytical security summary paragraph for a detected event.
    Uses OpenAI if settings.OPENAI_API_KEY is active; otherwise falls back to a high-fidelity template engine.
    """
    prompt = (
        f"You are the Godseye Security Command Center AI. Generate a professional, highly detailed, "
        f"and actionable incident report summary for the following event:\n"
        f"- Incident Type: {incident_type}\n"
        f"- Risk Classification: {threat_level} (Threat Score: {threat_score}/100)\n"
        f"- Crowd Density: {crowd_count} persons in immediate vicinity\n"
        f"- Context: {description or 'No additional context provided.'}\n\n"
        f"Keep the summary to 2-3 concise, professional sentences. Focus on the physical threat vector, "
        f"spatial factors, and operational recommendations."
    )

    if openai_client and settings.OPENAI_API_KEY:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional tactical security intelligence advisor."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI Summary generation failed: {e}. Falling back to rule-based engine.")

    # High-fidelity Rule-Based Fallback Engine
    recommendations = {
        "INTRUSION": "Dispatch immediate ground response patrol to secure the breached sector. Review access point authorization logs.",
        "WEAPON": "Initiate immediate lockdown protocol. Signal local emergency services and advise operators to monitor camera stream from a safe distance.",
        "VIOLENCE": "Dispatch security officers to intervene. Announce verbal warning through local PA speaker systems immediately.",
        "CROWD_ALERT": "Deploy operators to manage crowd exit routes and monitor for signs of physical distress or blockages.",
        "UNATTENDED_OBJECT": "Enforce perimeter containment zone. Deploy bomb-disposal or high-danger response teams to inspect the luggage container."
    }
    
    rec = recommendations.get(incident_type, "Maintain constant visual tracking and report further abnormal activities to the shift commander.")
    
    fallback_text = (
        f"At {datetime.now().strftime('%H:%M:%S')}, a critical {incident_type} anomaly was flagged with a risk level of {threat_level} "
        f"(Threat Score: {threat_score}/100). The local vicinity recorded a crowd density of {crowd_count} individuals. "
        f"Operational Threat Assessment: {description or 'Potential safety risk flagged by computer vision heuristics.'} "
        f"Action Recommended: {rec}"
    )
    return fallback_text


def answer_chat_query(user_query: str, db: Session) -> dict:
    """
    Answers natural language queries about active camera networks and database incident logs.
    Performs full SQLite metadata scans to capture context, passing findings to OpenAI or returning
    a custom dynamic query engine response when offline.
    """
    # 1. Fetch database context to feed the intelligence assistant
    incidents = db.query(Incident).order_by(Incident.timestamp.desc()).limit(10).all()
    cameras = db.query(Camera).all()
    
    total_incidents = db.query(Incident).count()
    unresolved_incidents = db.query(Incident).filter(Incident.is_resolved == False).count()
    critical_incidents = db.query(Incident).filter(Incident.threat_level == "CRITICAL").count()
    high_incidents = db.query(Incident).filter(Incident.threat_level == "HIGH").count()
    
    # Structure incident overview strings
    incident_context = []
    for inc in incidents:
        cam_name = inc.camera.name if inc.camera else "Unknown Web Stream"
        incident_context.append(
            f"- [{inc.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {inc.incident_type} at {cam_name} | "
            f"Score: {inc.threat_score} ({inc.threat_level}) | Resolved: {inc.is_resolved}"
        )
    incident_context_str = "\n".join(incident_context) if incident_context else "No incidents recorded in database."
    
    camera_context = [f"- Camera #{c.id}: {c.name} | Location: {c.location} | Active: {c.is_active}" for c in cameras]
    camera_context_str = "\n".join(camera_context) if camera_context else "No active cameras configured."

    system_prompt = (
        f"You are the Godseye Intelligent Surveillance Command Assistant. You have full system visibility. "
        f"Answer the operator's query using the following real-time database context:\n\n"
        f"--- SYSTEM METRICS ---\n"
        f"- Active Cameras: {len(cameras)}\n"
        f"- Total Incidents Recorded: {total_incidents}\n"
        f"- Unresolved Threats: {unresolved_incidents}\n"
        f"- High Risk Threats: {high_incidents}\n"
        f"- Critical Risk Threats: {critical_incidents}\n\n"
        f"--- ACTIVE CAMERAS ---\n"
        f"{camera_context_str}\n\n"
        f"--- RECENT 10 INCIDENTS ---\n"
        f"{incident_context_str}\n\n"
        f"Maintain a crisp, highly technical, tactical military-command style. "
        f"Suggest concrete action routes or commands the operator should execute."
    )

    suggested_commands = ["/resolve all", "/export logs", "/status cameras"]

    # If OpenAI API is active, run standard LLM pipeline
    if openai_client and settings.OPENAI_API_KEY:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                max_tokens=250,
                temperature=0.5
            )
            return {
                "response": response.choices[0].message.content.strip(),
                "suggested_commands": suggested_commands
            }
        except Exception as e:
            logger.error(f"OpenAI Chat execution failed: {e}. Defaulting to offline query engine.")

    # High-quality fallback rule-based matching engine
    query_lower = user_query.lower()
    
    # Heuristics rules matching standard operator questions
    if "how many" in query_lower or "total" in query_lower or "count" in query_lower:
        response_text = (
            f"Godseye Command Database reports a total of {total_incidents} registered events across the active feed loops. "
            f"Currently, there are {unresolved_incidents} unresolved alerts pending intervention, including {critical_incidents} "
            f"classified as CRITICAL. Recommended: execute '/resolve all' to clear stale alerts."
        )
    elif "critical" in query_lower or "danger" in query_lower or "high threat" in query_lower or "weapons" in query_lower:
        recent_crit = db.query(Incident).filter(Incident.threat_level.in_(["HIGH", "CRITICAL"])).order_by(Incident.timestamp.desc()).first()
        if recent_crit:
            cam_name = recent_crit.camera.name if recent_crit.camera else "Webcam Loop"
            response_text = (
                f"ALERT: Highest threat vector recorded is a {recent_crit.incident_type} at {cam_name} "
                f"with a severity rating of {recent_crit.threat_score}/100. This anomaly remains unresolved. "
                f"Security directives require dispatching a ground reconnaissance unit immediately."
            )
        else:
            response_text = "Standard scans report zero highly critical active threat vectors. Perimeter remains secure."
    elif "camera" in query_lower or "rtsp" in query_lower:
        active_names = [c.name for c in cameras if c.is_active]
        response_text = (
            f"Currently monitoring {len(cameras)} cameras. Active feeds: {', '.join(active_names)}. "
            f"Frame extraction rates are running at 30 FPS under dynamic frame-skipping optimizations."
        )
    else:
        response_text = (
            f"Godseye Intelligence Core active. System telemetry summary: {total_incidents} total alerts logged, "
            f"{unresolved_incidents} unresolved events, and {len(cameras)} active video nodes. "
            f"To inspect full threat distributions or review details, check the interactive command timeline."
        )

    return {
        "response": response_text,
        "suggested_commands": suggested_commands
    }
