# ==============================================
# 🐳 Groweasy-Invoice Production Dockerfile
# Flask + Gunicorn + Docker Best Practices
# ==============================================

# --- Base Image (lightweight & secure) ---
FROM python:3.11-slim

# --- Set working directory ---
WORKDIR /app

# --- Install system dependencies (optional for ReportLab/Pillow) ---
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Copy dependency list first (for caching efficiency) ---
COPY requirements.txt .

# --- Install Python dependencies ---
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy project source code ---
COPY . .

# --- Expose app port ---
EXPOSE 5000

# --- Environment variables ---
ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1

# --- Start Gunicorn WSGI server ---
# `app:app` means "from app.py import app"
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "app:app"]

# ==============================================
# ✅ Production-ready Docker image for Flask app
# ==============================================
