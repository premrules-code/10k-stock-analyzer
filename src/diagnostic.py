"""
Diagnostic script to check vector database contents
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

print("="*70)
print("CHECKING DATABASE CONTENTS")
print("="*70)

# Check companies table
print("\n📊 COMPANIES TABLE:")
with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM companies"))
    for row in result:
        print(f"  ID: {row[0]}, Ticker: {row[1]}, Name: {row[2]}")

# Check filings table
print("\n📄 FILINGS TABLE:")
with engine.connect() as conn:
    result = conn.execute(text("SELECT id, company_id, fiscal_year, accession_number FROM filings"))
    for row in result:
        print(f"  Filing ID: {row[0]}, Company ID: {row[1]}, Year: {row[2]}, Accession: {row[3]}")

# Check document_chunks table and metadata
print("\n📚 DOCUMENT CHUNKS TABLE (checking metadata):")
with engine.connect() as conn:
    # Get sample chunks to see metadata structure
    result = conn.execute(text("""
        SELECT id, metadata, LEFT(text, 100) as text_preview 
        FROM document_chunks 
        LIMIT 10
    """))
    
    for i, row in enumerate(result, 1):
        print(f"\n  Chunk {i}:")
        print(f"    ID: {row[0]}")
        print(f"    Metadata: {row[1]}")
        print(f"    Text preview: {row[2]}...")

# Count chunks per ticker (if metadata exists)
print("\n📈 CHUNK COUNTS BY TICKER:")
with engine.connect() as conn:
    try:
        result = conn.execute(text("""
            SELECT metadata->>'ticker' as ticker, COUNT(*) as chunk_count
            FROM document_chunks
            GROUP BY metadata->>'ticker'
        """))
        for row in result:
            print(f"  {row[0]}: {row[1]} chunks")
    except Exception as e:
        print(f"  ⚠️ Could not group by ticker: {e}")

print("\n" + "="*70)
