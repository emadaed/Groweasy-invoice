# ============================================================
# GrowEasy-Invoice  |  Dockerfile (Phase 4.2 – Stable Build)
# Target: Render Cloud / AWS EB / Local Docker
# Runtime: Python 3.13-slim + Flask 3 + Gunicorn + WeasyPrint
# ============================================================

# ---- Base image ----
FROM python:3.13-slim

# ---- Metadata ----
LABEL maintainer="GrowEasy DevOps <dev@jugnu.org>"
LABEL version="4.2"
LABEL description="GrowEasy-Invoice – Flask + WeasyPrint + Gunicorn (Stable Build)"

# ---- System dependencies for WeasyPrint & Pillow & psycopg2 ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    fontconfig \
    fonts-dejavu-core \
    libpq-dev \
    build-essential \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# ---- App setup ----
WORKDIR /app

# Copy dependency list first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy entire project ----
COPY . .

# ---- Environment configuration ----
# NOTE: FLASK_ENV is deprecated → using FLASK_DEBUG instead
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_DEBUG=0 \
    PORT=8080

# ---- Expose port ----
EXPOSE 8080

# ---- Launch command ----
# Gunicorn production server (3 workers, 120s timeout)
CMD ["gunicorn", "--workers=3", "--timeout", "120", "--graceful-timeout", "20", "-b", "0.0.0.0:8080", "app:app"]
