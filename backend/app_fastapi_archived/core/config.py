import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "GodsEye"
    API_V1_STR: str = "/api"
    
    # Security Configurations (Defaults are for developer demo; override via env in prod)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours log expiration
    
    # Path configuration
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # GodsEye/
    SCREENSHOTS_DIR: str = os.path.join(BASE_DIR, "screenshots")
    YOLO_MODEL_PATH: str = os.path.join(BASE_DIR, "models", "yolov8n.pt")
    
    # Database
    # Default is SQLite for instant zero-configuration startup; override via DATABASE_URL env
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'database', 'godseye_prod.db')}")
    
    # AI configurations
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Core system defaults
    CROWD_THRESHOLD: int = 5
    LOITERING_THRESHOLD: float = 10.0
    PEAK_START: int = 8
    PEAK_END: int = 18
    
    class Config:
        case_sensitive = True

# Create screenshots & database folder structures proactively
os.makedirs(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "screenshots"), exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "database"), exist_ok=True)

settings = Settings()
