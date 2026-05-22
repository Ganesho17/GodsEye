from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app.core.database import get_db
from backend.app.db.models import Incident
from backend.app.db.schemas import IncidentResponse
from backend.app.api.auth import get_current_user
from backend.app.services.analytics import get_system_analytics

router = APIRouter(prefix="/alerts", tags=["Alerts / Incidents"])

@router.get("", response_model=List[IncidentResponse])
def get_alerts(
    db: Session = Depends(get_db),
    camera_id: Optional[int] = Query(None, description="Filter incidents by Camera ID"),
    threat_level: Optional[str] = Query(None, description="Filter incidents by Threat Level (LOW, MEDIUM, HIGH, CRITICAL)"),
    incident_type: Optional[str] = Query(None, description="Filter by Incident Type (e.g. INTRUSION, WEAPON)"),
    is_resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    limit: int = Query(50, ge=1, le=200, description="Page limit for logs pagination"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user)
):
    """Retrieves list of logged threat alerts, filtered by criteria and sorted by timestamp desc."""
    query = db.query(Incident)
    
    if camera_id is not None:
        query = query.filter(Incident.camera_id == camera_id)
    if threat_level is not None:
        query = query.filter(Incident.threat_level == threat_level)
    if incident_type is not None:
        query = query.filter(Incident.incident_type == incident_type)
    if is_resolved is not None:
        query = query.filter(Incident.is_resolved == is_resolved)
        
    return query.order_by(Incident.timestamp.desc()).limit(limit).offset(offset).all()

@router.get("/stats")
def get_dashboard_statistics(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Retrieves rich statistical dataset aggregates formatted directly for Recharts panels."""
    try:
        return get_system_analytics(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compile dashboard metrics: {str(e)}"
        )

@router.put("/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_alert(incident_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Marks a specific incident as resolved and closes the active security ticket."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident alert not found.")
        
    incident.is_resolved = True
    db.commit()
    db.refresh(incident)
    return incident

@router.post("/resolve-all")
def resolve_all_alerts(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Bulk resolves all active unresolved alerts, returning the count of closed tickets."""
    unresolved = db.query(Incident).filter(Incident.is_resolved == False).all()
    count = len(unresolved)
    for inc in unresolved:
        inc.is_resolved = True
    db.commit()
    return {"status": "success", "resolved_count": count}
