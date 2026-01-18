# ---------------------------------------------------------
# GrowEasy Invoice – Phase 5-B (Production-Ready)
# ---------------------------------------------------------
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install ONLY NECESSARY system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core build tools
    build-essential \
    pkg-config \
    # Pillow requirements
    libjpeg62-turbo-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    zlib1g-dev \
    libfreetype6-dev \
    # PostgreSQL client
    libpq-dev \
    # XML processing (for some HTML parsing)
    libxml2-dev \
    libxslt1-dev \
    # SSL
    libssl-dev \
    libffi-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (simplified - no pre-download needed)
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Railway uses $PORT
EXPOSE 8080

# Production-ready Gunicorn configuration
CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers 2 \
    --worker-class gevent \
    --timeout 300 \
    --keepalive 5 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app