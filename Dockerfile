# ---------------------------------------------------------
# GrowEasy Invoice – Phase 5-B (Modular Build - Fixed)
# ---------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies for WeasyPrint, Pillow, QR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libpng-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Copy files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Railway uses $PORT
EXPOSE 8080

# Railway prefers string CMD
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 300 --workers 2 --worker-class gevent app:app