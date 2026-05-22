import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.db.models import Camera
from backend.app.db.schemas import CameraCreate, CameraResponse
from backend.app.api.auth import get_current_user

router = APIRouter(prefix="/cameras", tags=["Cameras"])

@router.get("", response_model=List[CameraResponse])
def list_cameras(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Lists all active and registered surveillance camera configurations."""
    return db.query(Camera).all()

@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def create_camera(camera_in: CameraCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Registers a new surveillance camera channel."""
    # Ensure zone_coordinates is valid JSON
    try:
        if camera_in.zone_coordinates:
            json.loads(camera_in.zone_coordinates)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zone coordinates must be a valid JSON array of points e.g. '[[0.1, 0.1], [0.9, 0.1]]'"
        )

    new_cam = Camera(
        name=camera_in.name,
        rtsp_url=camera_in.rtsp_url,
        location=camera_in.location,
        is_active=camera_in.is_active if camera_in.is_active is not None else True,
        zone_coordinates=camera_in.zone_coordinates or "[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]"
    )
    db.add(new_cam)
    db.commit()
    db.refresh(new_cam)
    return new_cam

@router.put("/{camera_id}", response_model=CameraResponse)
def update_camera(camera_id: int, camera_in: CameraCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Updates configuration parameters of a specific camera node."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera config not found.")
        
    try:
        if camera_in.zone_coordinates:
            json.loads(camera_in.zone_coordinates)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zone coordinates must be a valid JSON array of points."
        )
        
    camera.name = camera_in.name
    camera.rtsp_url = camera_in.rtsp_url
    camera.location = camera_in.location
    camera.is_active = camera_in.is_active
    camera.zone_coordinates = camera_in.zone_coordinates
    
    db.commit()
    db.refresh(camera)
    return camera

@router.post("/{camera_id}/zone", response_model=CameraResponse)
def update_camera_zone(camera_id: int, payload: dict, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Dedicated fast-path endpoint to update a secure zone polygon."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera config not found.")
        
    zone = payload.get("zone_coordinates")
    if not zone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'zone_coordinates' payload field.")
        
    try:
        # Validate zone formatting
        if isinstance(zone, list):
            zone_str = json.dumps(zone)
        else:
            json.loads(zone)
            zone_str = zone
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Zone coordinates must be a valid nested coordinate array list."
        )
        
    camera.zone_coordinates = zone_str
    db.commit()
    db.refresh(camera)
    return camera

@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Deletes a camera configuration from database registries."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera config not found.")
    db.delete(camera)
    db.commit()
    return {"detail": "Camera deleted successfully."}

def seed_default_camera(db: Session):
    """Proactively seeds a primary local webcam channel configuration if tables are blank."""
    camera_count = db.query(Camera).count()
    if camera_count == 0:
        print("Database Seed: Initializing primary local webcam channel node...")
        default_camera = Camera(
            name="Primary Webcam Core",
            rtsp_url=None, # Nullable triggers standard computer camera capture 0
            location="Command Entrance A",
            is_active=True,
            zone_coordinates="[[0.15, 0.15], [0.85, 0.15], [0.85, 0.85], [0.15, 0.85]]"
        )
        db.add(default_camera)
        db.commit()
        print("Database Seed: Primary Webcam Core registered successfully.")
