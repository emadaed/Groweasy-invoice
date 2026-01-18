# ---------------------------------------------------------
# GrowEasy Invoice – Phase 5-B (Production-Ready)
# ---------------------------------------------------------
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    # For Pillow
    libjpeg62-turbo-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    zlib1g-dev \
    libfreetype6-dev \
    # For PostgreSQL
    libpq-dev \
    # For XML/HTML processing
    libxml2-dev \
    libxslt1-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers 2 \
    --worker-class gevent \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    app:app