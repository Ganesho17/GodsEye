from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="operator")  # "admin" or "operator"
    is_active = Column(Boolean, default=True)

class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    rtsp_url = Column(String, nullable=True)  # Nullable means falling back to Webcam 0
    location = Column(String, default="Main Office")
    is_active = Column(Boolean, default=True)
    zone_coordinates = Column(String, default="[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]")
    
    # Relationships
    incidents = relationship("Incident", back_populates="camera")

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    incident_type = Column(String, nullable=False, index=True) # INTRUSION, WEAPON, VIOLENCE, CROWD_ALERT, UNATTENDED_OBJECT
    threat_score = Column(Integer, nullable=False)
    threat_level = Column(String, nullable=False, index=True) # LOW, MEDIUM, HIGH, CRITICAL
    crowd_count = Column(Integer, default=0)
    screenshot_path = Column(String, nullable=True)
    description = Column(String, nullable=True)
    is_resolved = Column(Boolean, default=False)
    
    # Relationships
    camera = relationship("Camera", back_populates="incidents")
    summary = relationship("Summary", uselist=False, back_populates="incident", cascade="all, delete-orphan")

class Summary(Base):
    __tablename__ = "summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), unique=True)
    summary_text = Column(String, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    incident = relationship("Incident", back_populates="summary")
