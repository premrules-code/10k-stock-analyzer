# ============================================================================
# Simple Dockerfile for Railway/Local Testing
# ============================================================================
FROM python:3.11-slim

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL application code (INCLUDING app.py)
COPY . .

# Verify app.py exists (debugging step)
RUN ls -la app.py || echo "ERROR: app.py not found!"

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8080", \
     "--server.headless", "true", \
     "--browser.gatherUsageStats", "false"]