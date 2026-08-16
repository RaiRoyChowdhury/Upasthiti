# SmartAttend AI backend - Docker image for local development.
# Optional (per spec: "if practical") - the normal venv-based local setup
# documented in README.md works without this and remains the primary path.
#
# NOTE: opencv-python-headless/insightface/onnxruntime are real, heavy
# dependencies - this image will take a while to build the first time.
# See docs/computer-vision.md for the same install-risk notes that apply
# to a plain venv install.

FROM python:3.11-slim

# 1. Install system build dependencies and OpenCV requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Pre-download face models into the Docker image 
# This prevents Render from downloading 281MB on every cold start!
RUN python -c "import insightface; insightface.app.FaceAnalysis(name='buffalo_l').prepare(ctx_id=-1)"

# 4. Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]