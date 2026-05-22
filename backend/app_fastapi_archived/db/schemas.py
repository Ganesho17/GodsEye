from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None

# --- User Schemas ---
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: Optional[str] = "operator"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

# --- Camera Schemas ---
class CameraBase(BaseModel):
    name: str
    rtsp_url: Optional[str] = None
    location: Optional[str] = "Main Office"
    is_active: Optional[bool] = True
    zone_coordinates: Optional[str] = "[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]"

class CameraCreate(CameraBase):
    pass

class CameraResponse(CameraBase):
    id: int

    class Config:
        from_attributes = True

# --- Summary Schemas ---
class SummaryBase(BaseModel):
    summary_text: str

class SummaryResponse(SummaryBase):
    id: int
    incident_id: int
    generated_at: datetime

    class Config:
        from_attributes = True

# --- Incident Schemas ---
class IncidentBase(BaseModel):
    incident_type: str
    threat_score: int
    threat_level: str
    crowd_count: int
    screenshot_path: Optional[str] = None
    description: Optional[str] = None
    is_resolved: Optional[bool] = False

class IncidentResponse(IncidentBase):
    id: int
    timestamp: datetime
    camera_id: Optional[int] = None
    summary: Optional[SummaryBase] = None

    class Config:
        from_attributes = True

# --- Security Assistant / Chat Schemas ---
class ChatQuery(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    suggested_commands: Optional[List[str]] = []

# --- System Settings Schemas ---
class SettingsUpdate(BaseModel):
    crowd_threshold: Optional[int] = None
    loitering_threshold: Optional[float] = None
    peak_start: Optional[int] = None
    peak_end: Optional[int] = None
    use_webcam: Optional[bool] = None

class SettingsResponse(BaseModel):
    crowd_threshold: int
    loitering_threshold: float
    peak_start: int
    peak_end: int
    use_webcam: bool
