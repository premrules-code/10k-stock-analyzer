"""
Database module for 10-K analyzer

Handles:
- Company storage
- Filing metadata storage
- Structured financial data (JSON)
- PostgreSQL with SQLAlchemy
"""

from sqlalchemy import create_engine, text, Column, Integer, String, DateTime, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Dict, List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import json

load_dotenv()
logger = logging.getLogger(__name__)

Base = declarative_base()


class Company(Base):
    """Companies table"""
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    cik = Column(String(10), nullable=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Filing(Base):
    """Filings table"""
    __tablename__ = 'filings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    fiscal_year = Column(Integer, nullable=False, index=True)
    fiscal_quarter = Column(Integer, nullable=True)
    accession_number = Column(String(50), nullable=False)
    filing_type = Column(String(10), nullable=False)
    filing_date = Column(DateTime, nullable=True)
    file_path = Column(String(500), nullable=True)
    structured_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint on company_id and fiscal_year (one filing per fiscal year per company)
    __table_args__ = (
        UniqueConstraint('company_id', 'fiscal_year', name='uq_company_fiscal_year'),
    )


class Database:
    """Database operations manager"""
    
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        
        if not self.database_url:
            raise ValueError("DATABASE_URL not found in environment variables")
        
        self.engine = create_engine(self.database_url, echo=False, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        logger.info("✅ Database connection established")
    
    def add_company(self, ticker: str, company_name: str = None, cik: str = None, 
                   sector: str = None, industry: str = None) -> int:
        """Add or update a company"""
        
        if not company_name:
            company_name = ticker
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO companies (ticker, company_name, cik, sector, industry, created_at, updated_at)
                VALUES (:ticker, :name, :cik, :sector, :industry, NOW(), NOW())
                ON CONFLICT (ticker) 
                DO UPDATE SET 
                    company_name = EXCLUDED.company_name,
                    cik = COALESCE(EXCLUDED.cik, companies.cik),
                    sector = COALESCE(EXCLUDED.sector, companies.sector),
                    industry = COALESCE(EXCLUDED.industry, companies.industry),
                    updated_at = NOW()
                RETURNING id
                """),
                {"ticker": ticker, "name": company_name, "cik": cik, "sector": sector, "industry": industry}
            )
            conn.commit()
            company_id = result.scalar()
            logger.info(f"✅ Company {ticker} stored (ID: {company_id})")
            return company_id
    
    def get_company(self, ticker: str) -> Optional[Dict]:
        """Get company by ticker"""
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, ticker, company_name, cik, sector, industry FROM companies WHERE ticker = :ticker"),
                {"ticker": ticker}
            ).fetchone()
        
        if result:
            return {
                "id": result[0], "ticker": result[1], "company_name": result[2],
                "cik": result[3], "sector": result[4], "industry": result[5]
            }
        return None
    
    def get_all_companies(self) -> List[Dict]:
        """Get all companies"""
        
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT id, ticker, company_name, cik, sector, industry FROM companies ORDER BY ticker"))
        
        companies = []
        for row in result:
            companies.append({
                "id": row[0], "ticker": row[1], "company_name": row[2],
                "cik": row[3], "sector": row[4], "industry": row[5]
            })
        return companies
    
    def add_filing(self, company_id: int, filing_data: Dict, structured_data: Dict = None) -> int:
        """Add or update a filing"""
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO filings (company_id, fiscal_year, fiscal_quarter, accession_number,
                                   filing_type, filing_date, file_path, structured_data, created_at, updated_at)
                VALUES (:company_id, :year, :quarter, :accession, :type, :date, :path, :data, NOW(), NOW())
                ON CONFLICT (company_id, fiscal_year)
                DO UPDATE SET file_path = EXCLUDED.file_path,
                            structured_data = EXCLUDED.structured_data,
                            updated_at = NOW()
                RETURNING id
                """),
                {
                    "company_id": company_id, "year": filing_data.get("fiscal_year"),
                    "quarter": filing_data.get("fiscal_quarter"), "accession": filing_data["accession"],
                    "type": filing_data.get("filing_type", "10-K"), "date": filing_data.get("filing_date"),
                    "path": filing_data.get("file_path"),
                    "data": json.dumps(structured_data) if structured_data else None
                }
            )
            conn.commit()
            filing_id = result.scalar()
            logger.info(f"✅ Filing stored (ID: {filing_id})")
            return filing_id
    
    def get_filing(self, ticker: str, fiscal_year: int, quarter: int = None) -> Optional[Dict]:
        """Get filing by ticker and year"""
        
        with self.engine.connect() as conn:
            if quarter:
                query = """
                SELECT f.id, f.fiscal_year, f.fiscal_quarter, f.accession_number, f.filing_type, 
                       f.filing_date, f.file_path, f.structured_data
                FROM filings f JOIN companies c ON f.company_id = c.id
                WHERE c.ticker = :ticker AND f.fiscal_year = :year AND f.fiscal_quarter = :quarter
                """
                params = {"ticker": ticker, "year": fiscal_year, "quarter": quarter}
            else:
                query = """
                SELECT f.id, f.fiscal_year, f.fiscal_quarter, f.accession_number, f.filing_type,
                       f.filing_date, f.file_path, f.structured_data
                FROM filings f JOIN companies c ON f.company_id = c.id
                WHERE c.ticker = :ticker AND f.fiscal_year = :year AND f.filing_type = '10-K'
                """
                params = {"ticker": ticker, "year": fiscal_year}
            
            result = conn.execute(text(query), params).fetchone()
        
        if result:
            return {
                "id": result[0], "fiscal_year": result[1], "fiscal_quarter": result[2],
                "accession_number": result[3], "filing_type": result[4], "filing_date": result[5],
                "file_path": result[6], "structured_data": json.loads(result[7]) if result[7] else None
            }
        return None
    
    def get_filings_by_year(self, fiscal_year: int) -> List[Dict]:
        """Get all filings for a specific year"""
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT c.ticker, c.company_name, f.fiscal_year, f.accession_number, f.structured_data
                FROM filings f JOIN companies c ON f.company_id = c.id
                WHERE f.fiscal_year = :year ORDER BY c.ticker
                """),
                {"year": fiscal_year}
            )
        
        filings = []
        for row in result:
            structured_data = json.loads(row[4]) if row[4] else {}
            filings.append({
                "ticker": row[0], "company": row[1], "fiscal_year": row[2], "accession": row[3],
                "revenue": structured_data.get("revenue"), "net_income": structured_data.get("net_income"),
                "total_assets": structured_data.get("total_assets"), "structured_data": structured_data
            })
        return filings
    
    def get_filings_by_company(self, company_id: int) -> List[Dict]:
        """Get all filings for a specific company"""
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT id, fiscal_year, accession_number, filing_type, filing_date, structured_data
                FROM filings
                WHERE company_id = :company_id
                ORDER BY fiscal_year DESC
                """),
                {"company_id": company_id}
            )
        
        filings = []
        for row in result:
            structured_data = json.loads(row[5]) if row[5] else {}
            filings.append({
                "id": row[0], "fiscal_year": row[1], "accession_number": row[2],
                "filing_type": row[3], "filing_date": row[4],
                "structured_data": structured_data
            })
        return filings
    
    def close(self):
        """Close database connection"""
        self.session.close()
        self.engine.dispose()
        logger.info("Database connection closed")