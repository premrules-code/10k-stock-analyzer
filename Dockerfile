# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for downloads
RUN mkdir -p data

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8080/_stcore/health || exit 1

# Start with environment variable debugging
CMD echo "====================================" && \
    echo "🔍 ENVIRONMENT VARIABLES CHECK" && \
    echo "====================================" && \
    echo "" && \
    echo "Checking DATABASE_URL..." && \
    if [ -z "$DATABASE_URL" ]; then \
        echo "❌ DATABASE_URL: NOT SET"; \
    else \
        echo "✅ DATABASE_URL: ${DATABASE_URL:0:40}..."; \
    fi && \
    echo "" && \
    echo "Checking OPENAI_API_KEY..." && \
    if [ -z "$OPENAI_API_KEY" ]; then \
        echo "❌ OPENAI_API_KEY: NOT SET"; \
    else \
        echo "✅ OPENAI_API_KEY: ${OPENAI_API_KEY:0:15}..."; \
    fi && \
    echo "" && \
    echo "Checking SUPABASE variables..." && \
    echo "SUPABASE_HOST: ${SUPABASE_HOST:-NOT SET}" && \
    echo "SUPABASE_USER: ${SUPABASE_USER:-NOT SET}" && \
    echo "SUPABASE_PORT: ${SUPABASE_PORT:-NOT SET}" && \
    echo "SUPABASE_DB: ${SUPABASE_DB:-NOT SET}" && \
    if [ -z "$SUPABASE_PASSWORD" ]; then \
        echo "SUPABASE_PASSWORD: NOT SET"; \
    else \
        echo "SUPABASE_PASSWORD: ***SET***"; \
    fi && \
    echo "" && \
    echo "====================================" && \
    echo "📋 All Railway/DB env vars:" && \
    env | grep -E "RAILWAY|DATABASE|SUPABASE|OPENAI" | sort && \
    echo "====================================" && \
    echo "" && \
    echo "🚀 Starting Streamlit..." && \
    echo "" && \
    streamlit run src/app.py \
        --server.port=8080 \
        --server.address=0.0.0.0 \
        --server.headless=true \
        --browser.serverAddress=0.0.0.0 \
        --browser.gatherUsageStats=false \
        --server.enableCORS=false \
        --server.enableXsrfProtection=false
