python << 'EOF'
# Test all key imports
try:
    from llama_index.core import Settings, VectorStoreIndex, Document, StorageContext
    print("✅ Core imports OK")
    
    from llama_index.llms.openai import OpenAI
    print("✅ OpenAI LLM OK")
    
    from llama_index.embeddings.openai import OpenAIEmbedding
    print("✅ OpenAI Embeddings OK")
    
    from llama_index.vector_stores.postgres import PGVectorStore
    print("✅ Postgres Vector Store OK")
    
    from llama_index.callbacks.langfuse import LangfuseCallbackHandler
    print("✅ LangFuse OK")
    
    import streamlit
    print("✅ Streamlit OK")
    
    from sec_edgar_downloader import Downloader
    print("✅ SEC Downloader OK")
    
    from bs4 import BeautifulSoup
    print("✅ BeautifulSoup OK")
    
    import psycopg2
    print("✅ Postgres Driver OK")
    
    from sqlalchemy import create_engine
    print("✅ SQLAlchemy OK")
    
    print("\n🎉 ALL DEPENDENCIES INSTALLED CORRECTLY!")
    print("🚀 You're ready to build your 10-K analyzer!")
    
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("\nRun: pip install llama-index llama-index-vector-stores-postgres langfuse streamlit sec-edgar-downloader beautifulsoup4 lxml python-dotenv pandas psycopg2-binary sqlalchemy")
EOF
