# Railway Deployment Guide

This project is configured for deployment on Railway with Docker.

## Prerequisites

1. Railway account (https://railway.app)
2. Docker installed locally (for testing)
3. Required environment variables set

## Environment Variables

Set these in the Railway dashboard under "Variables":

### Required
- `OPENAI_API_KEY`: Your OpenAI API key
- `SUPABASE_HOST`: Your Supabase PostgreSQL host
- `SUPABASE_PASSWORD`: Your Supabase PostgreSQL password

### Optional (Defaults Provided)
- `SUPABASE_USER`: Default is `postgres`
- `SUPABASE_PORT`: Default is `5432`
- `SUPABASE_DB`: Default is `postgres`
- `DATABASE_URL`: Auto-generated from Supabase credentials (or set manually)

### Observability (Optional)
- `LANGFUSE_PUBLIC_KEY`: For LangFuse integration
- `LANGFUSE_SECRET_KEY`: For LangFuse integration
- `LANGFUSE_HOST`: For LangFuse integration

## Railway Deployment Steps

### Option 1: Using Railway CLI
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Link project
railway link

# Deploy
railway up
```

### Option 2: Using Railway Dashboard
1. Create a new project on https://railway.app
2. Connect your GitHub repository
3. Railway will automatically detect the `Dockerfile`
4. Set environment variables in the dashboard
5. Deploy button will appear

### Option 3: Using Docker Image
```bash
# Build locally
docker build -t 10k-stock-analyzer .

# Test locally
docker run -e OPENAI_API_KEY="your-key" \
           -e SUPABASE_HOST="your-host" \
           -e SUPABASE_PASSWORD="your-password" \
           10k-stock-analyzer
```

## Database Setup

The application expects a PostgreSQL database with the following schema:

```sql
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    company_name VARCHAR(255),
    cik VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS filings (
    id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(id),
    filing_type VARCHAR(10),
    filing_date DATE,
    fiscal_year INT,
    document_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector store tables are created automatically by LlamaIndex
```

## Monitoring

- Check logs: `railway logs`
- View metrics: Railway dashboard
- LangFuse integration provides token/cost tracking (if configured)

## Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (copy from railway.env)
export $(cat railway.env | xargs)

# Run application
python -m src.app
```

## Troubleshooting

1. **Import errors**: Ensure Python path includes project root
2. **Database connection**: Verify DATABASE_URL format is correct
3. **LangFuse warnings**: These are non-fatal if LangFuse keys aren't set
4. **OpenAI errors**: Check API key is valid and has sufficient quota

## File Structure for Railway

```
.
├── Dockerfile              # Multi-stage Docker build
├── railway.json            # Railway configuration
├── railway.env             # Environment variable template
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
└── src/
    ├── app.py             # Main application entry point
    ├── rag_engine.py      # RAG/AI logic
    ├── database.py        # Database operations
    ├── downloader.py      # SEC EDGAR downloader
    └── config/
        ├── openai.py      # OpenAI configuration
        └── __init__.py
```
