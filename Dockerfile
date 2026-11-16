FROM python:3.12-slim

# Set timezone & environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

# Install system dependencies (curl untuk healthcheck, libglib & libgomp untuk OpenCV & NumPy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Jalankan sebagai user non-root (UID 1000 agar cocok dengan pemilik folder logs/ & data/ di VPS)
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/logs /app/data \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI server
CMD ["python", "main.py"]
