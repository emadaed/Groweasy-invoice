# GrowEasy Invoice – Phase 5-B (Production-Ready + WeasyPrint Fixed for Bookworm)
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies - CORRECTED PACKAGE NAMES FOR DEBIAN BOOKWORM
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    # === WeasyPrint Critical Dependencies (Fixed names) ===
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangocairo-1.0-0 \
    libcairo2 \
    libcairo-gobject2 \
    libgobject-2.0-0 \          # ← hyphen instead of dot
    libglib2.0-0 \              # ← hyphen
    libgraphite2-3 \
    libicu72 \
    # === Pillow Dependencies ===
    libjpeg62-turbo-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    # === PostgreSQL ===
    libpq-dev \
    # === XML/HTML ===
    libxml2-dev \
    libxslt1-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements for caching
COPY requirements.txt .

# Install Python packages
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

# Railway uses $PORT
CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers 2 \
    --worker-class gevent \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    app:app