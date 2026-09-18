# ==============================================================================
# ChurchToolVideo - Production Dockerfile
# Đóng gói khép kín: Python 3.11, FFmpeg OS-level, faster-whisper, FastAPI
# ==============================================================================

FROM python:3.11-slim

# Ngăn Python tạo file .pyc và bật unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WORKSPACE_DIR=/app/workspace

WORKDIR /app

# Cài đặt FFmpeg và các thư viện hệ thống cần thiết
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn ứng dụng
COPY app/ ./app/

# Tạo các thư mục workspace mặc định
RUN mkdir -p /app/workspace/uploads \
             /app/workspace/audio \
             /app/workspace/subtitles \
             /app/workspace/segments \
             /app/workspace/packages

# Volume mount cho dữ liệu
VOLUME ["/app/workspace"]

# Cổng dịch vụ FastAPI
EXPOSE 8000

# Khởi chạy Uvicorn ASGI Server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
