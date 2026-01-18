# ---------------------------------------------------------
# GrowEasy Invoice – Phase 5-B (Production-Ready)
# ---------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies for WeasyPrint, Pillow, QR, and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core system tools
    build-essential \
    pkg-config \
    # Cairo & Pango (for WeasyPrint/pycairo)
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpango1.0-dev \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libgdk-pixbuf2.0-dev \
    # Fonts & graphics
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    zlib1g-dev \
    # Database
    libpq-dev \
    # XML/HTML processing
    libxml2-dev \
    libxslt1-dev \
    # SSL
    libssl-dev \
    libffi-dev \
    # Other
    shared-mime-info \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies using pre-built wheels where possible
RUN pip install --upgrade pip setuptools wheel && \
    # Pre-download problematic packages to ensure correct versions
    pip download --no-deps \
        pycairo==1.29.0 \
        Pillow==10.2.0 \
        psycopg2-binary==2.9.9 \
        weasyprint==61.0 && \
    # Install all requirements
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