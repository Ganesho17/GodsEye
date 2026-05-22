import os
import time
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

# Core configs & security
from backend.app.core.config import settings
from backend.app.core.database import engine, Base, get_db

# Routers
from backend.app.api.auth import router as auth_router, seed_default_admin
from backend.app.api.cameras import router as cameras_router, seed_default_camera
from backend.app.api.alerts import router as alerts_router
from backend.app.api.chat import router as chat_router

# WebSockets manager & AI pipeline
from backend.app.websocket.manager import manager
from backend.app.ai.pipeline import pipeline_manager
from backend.app.db.models import Camera

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan context manager.
    Handles startup table validation, seeding, and spins up surveillance camera pipelines.
    Gracefully shuts down running threads on exit.
    """
    # 1. Initialize SQLite Database tables
    print("Database System: Synchronizing physical database schemas...")
    Base.metadata.create_all(bind=engine)
    
    # 2. Seed default admin credentials and webcam configuration
    db: Session = next(get_db())
    try:
        seed_default_admin(db)
        seed_default_camera(db)
        
        # 3. Spin up surveillance pipelines for all active cameras automatically
        active_cameras = db.query(Camera).filter(Camera.is_active == True).all()
        print(f"Pipeline Coordinator: Launching {len(active_cameras)} active video feeds...")
        for cam in active_cameras:
            pipeline_manager.start_pipeline(cam.id)
    except Exception as e:
        print(f"Startup Lifespan Exception: {e}")
    finally:
        db.close()
        
    yield
    
    # 4. Cleanup pipelines on system shutdown
    print("System Shutdown: Tearing down active surveillance pipelines...")
    pipeline_manager.stop_all()
    print("System Shutdown: All background threads released successfully.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="GodsEye Advanced AI Surveillance & Threat Prediction Console",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configurations for cross-origin communications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits all origin links for development ease
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount statically stored threat screenshots to be accessible web-wide
app.mount("/screenshots", StaticFiles(directory=settings.SCREENSHOTS_DIR), name="screenshots")

# Mount API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(cameras_router, prefix=settings.API_V1_STR)
app.include_router(alerts_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)

@app.get("/")
def get_root():
    """Root health check confirmation."""
    return {
        "status": "healthy",
        "service": "GodsEye Threat Core Security API",
        "timestamp": time.time()
    }

# --- Live MJPEG Boundary Video Feeds ---
@app.get("/api/cameras/{camera_id}/stream")
def get_live_video_feed(camera_id: int):
    """
    Returns an HTTP MJPEG stream boundary sequence of plain frames.
    Client renders overlays natively on Canvas layers mapping WebSockets coordinates.
    """
    pipeline = pipeline_manager.get_pipeline(camera_id)
    if not pipeline:
        # Spin up pipeline on-demand if camera exists in DB
        db: Session = next(get_db())
        try:
            cam = db.query(Camera).filter(Camera.id == camera_id).first()
            if not cam:
                raise HTTPException(status_code=404, detail="Surveillance node camera not found.")
            pipeline = pipeline_manager.start_pipeline(camera_id)
        finally:
            db.close()
            
    def frame_generator():
        while True:
            # Yield boundaries sequence
            frame_bytes = pipeline.get_current_frame_jpeg()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.04)  # Limit transmission cycle to match 25 FPS
            
    return StreamingResponse(
        frame_generator(), 
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# --- WebSocket Channels Routing ---
@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """WebSocket channel broadcasting real-time person coords bounding boxes and telemetry."""
    await manager.connect_telemetry(websocket)
    try:
        while True:
            # Maintain active connection channel pinging
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_telemetry(websocket)
    except Exception:
        manager.disconnect_telemetry(websocket)

@app.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket):
    """WebSocket channel broadcasting high-severity alarm event tickets instantly."""
    await manager.connect_alerts(websocket)
    try:
        while True:
            # Maintain active connection channel pinging
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_alerts(websocket)
    except Exception:
        manager.disconnect_alerts(websocket)
