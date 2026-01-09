"""
Database operations for Supabase
"""
from sqlalchemy import create_engine, text
from typing import Dict, List
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class Database:
    """Handles all database operations"""
    
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL not found in .env file")
        
        self.engine = create_engine(self.database_url)
    
    def add_company(self, ticker: str, company_name: str = None) -> int:
        """Add or update company, return company_id"""
        if not company_name:
            company_name = ticker
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO companies (ticker, company_name, cik)
                VALUES (:ticker, :name, :ticker)
                ON CONFLICT (ticker) 
                DO UPDATE SET company_name = :name
                RETURNING id
                """),
                {"ticker": ticker, "name": company_name}
            )
            conn.commit()
            company_id = result.scalar()
            logger.info(f"✅ Company {ticker} stored (ID: {company_id})")
            return company_id
    
    def add_filing(self, company_id: int, filing_data: Dict) -> int:
        """Add filing, return filing_id"""
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO filings 
                (company_id, fiscal_year, accession_number, file_path)
                VALUES (:company_id, :year, :accession, :path)
                ON CONFLICT (accession_number) 
                DO UPDATE SET file_path = :path
                RETURNING id
                """),
                {
                    "company_id": company_id,
                    "year": filing_data["fiscal_year"],
                    "accession": filing_data["accession"],
                    "path": filing_data["file_path"]
                }
            )
            conn.commit()
            filing_id = result.scalar()
            logger.info(f"✅ Filing stored (ID: {filing_id})")
            return filing_id
    
    def get_companies(self) -> List[Dict]:
        """Get all companies"""
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT ticker, company_name FROM companies ORDER BY ticker")
            )
            return [{"ticker": row[0], "name": row[1]} for row in result]