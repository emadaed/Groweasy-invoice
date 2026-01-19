# GrowEasy Invoice – Phase 5-B (Production-Ready + WeasyPrint Fixed)
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install ALL required system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    # === WeasyPrint Critical Dependencies ===
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangocairo-1.0-0 \
    libcairo2 \
    libcairo-gobject2 \
    libgobject2.0-0 \
    libglib2.0-0 \
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
    # === PostgreSQL client ===
    libpq-dev \
    # === XML/HTML processing (for premailer, etc.) ===
    libxml2-dev \
    libxslt1-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for caching
COPY requirements.txt .

# Upgrade pip and install Python packages
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

# Use $PORT for Railway compatibility
CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers 2 \
    --worker-class gevent \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    app:app