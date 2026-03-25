# ============================================================
# AutoClaim — HuggingFace Space Dockerfile
#
# This image runs the full FastAPI backend including:
#   - PyTorch + YOLO (damage detection)
#   - EasyOCR (license plate reading)
#   - Gemini + Groq AI (forensic analysis)
#   - Price API (merged into main app)
#
# HuggingFace Spaces: 16 GB RAM, 50 GB disk, port 7860 required.
# ============================================================

FROM python:3.11-slim

# System dependencies for OpenCV, EasyOCR, and psycopg2
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    gcc \
    g++ \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set YOLO config dir to a writable path (avoids /root/.config/Ultralytics warning)
ENV YOLO_CONFIG_DIR=/tmp

# Copy and install full requirements (torch + YOLO + EasyOCR included)
COPY Autoclaim-V3/autoclaim_project/server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server source code
COPY Autoclaim-V3/autoclaim_project/server .

# Download YOLO model weights at build time (bypasses HF 10MB LFS limit)
# Files are hosted on GitHub (pushed via git add -f from local)
RUN mkdir -p /app/models && \
    wget -q --show-progress \
      "https://github.com/Basilsabu10/Autoclaim-V3/raw/hf-deploy/Autoclaim-V3/autoclaim_project/server/models/best.pt" \
      -O /app/models/best.pt && \
    wget -q --show-progress \
      "https://github.com/Basilsabu10/Autoclaim-V3/raw/hf-deploy/Autoclaim-V3/autoclaim_project/server/models/damage_seg_best.pt" \
      -O /app/models/damage_seg_best.pt && \
    echo "[OK] YOLO models downloaded" && \
    ls -lh /app/models/

# HuggingFace Spaces always serves on port 7860
EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
