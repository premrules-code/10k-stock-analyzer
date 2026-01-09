"""
Simple diagnostic to check database schema and contents
Run this from your project directory: python diagnostic_simple.py
"""
import os
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("ERROR: sqlalchemy not installed")
    print("Run: pip install sqlalchemy")
    sys.exit(1)

print("="*70)
print("DATABASE DIAGNOSTIC TOOL")
print("="*70)

# Connect to database
database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("ERROR: DATABASE_URL not found in .env file")
    sys.exit(1)

engine = create_engine(database_url)

# 1. Check companies table
print("\n📊 COMPANIES TABLE:")
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT ticker, company_name FROM companies"))
        companies = list(result)
        if companies:
            for row in companies:
                print(f"  ✓ {row[0]} - {row[1]}")
        else:
            print("  (empty)")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 2. Check document_chunks table schema
print("\n📚 DOCUMENT_CHUNKS TABLE SCHEMA:")
try:
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'document_chunks'
            ORDER BY ordinal_position
        """))
        
        schema = list(result)
        if schema:
            for row in schema:
                print(f"  {row[0]}: {row[1]}")
        else:
            print("  ❌ Table 'document_chunks' does not exist!")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 3. Check if there are any tables with 'chunk' in the name
print("\n🔍 LOOKING FOR CHUNK TABLES:")
try:
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%chunk%'
        """))
        
        tables = list(result)
        if tables:
            for row in tables:
                print(f"  ✓ Found table: {row[0]}")
                
                # Get row count
                try:
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM {row[0]}"))
                    count = count_result.scalar()
                    print(f"    Rows: {count}")
                except:
                    pass
        else:
            print("  ❌ No tables with 'chunk' in name found")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 4. List all tables
print("\n📋 ALL TABLES IN DATABASE:")
try:
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        
        for row in result:
            print(f"  • {row[0]}")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 5. If document_chunks exists, check metadata
print("\n🔎 CHECKING METADATA IN CHUNKS:")
try:
    with engine.connect() as conn:
        # First, see if the table exists
        check = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'document_chunks'
            )
        """))
        
        if check.scalar():
            # Get sample metadata
            result = conn.execute(text("""
                SELECT metadata 
                FROM document_chunks 
                LIMIT 5
            """))
            
            for i, row in enumerate(result, 1):
                print(f"  Sample {i}: {row[0]}")
        else:
            print("  ℹ️ 'document_chunks' table does not exist")
            print("  This is normal if you're using separate tables per ticker")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70)
