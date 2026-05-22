FROM python:3.10-slim

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install critical OpenCV & PyTorch OS-level system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Force python pathway alignments
ENV PYTHONPATH=/workspace

# Install dependencies first to optimize Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source directories
COPY . /workspace/backend

EXPOSE 8000

# Run FastAPI under standard uvicorn worker bindings
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
