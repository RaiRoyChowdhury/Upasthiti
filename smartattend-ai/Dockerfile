# SmartAttend AI backend - Docker image
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

# 2. Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Pre-download InsightFace models during image build
RUN python -c "import insightface; insightface.app.FaceAnalysis(name='buffalo_l').prepare(ctx_id=-1)"

# 4. Copy backend and frontend folders into container
COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

# 5. Set PYTHONPATH so Python can locate modules inside /app/backend
ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]