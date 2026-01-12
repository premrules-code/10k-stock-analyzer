"""
SEC EDGAR Downloader Module
Downloads 10-K filings from SEC EDGAR database
"""

from sec_edgar_downloader import Downloader
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict, Optional
import os
import re
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class SECDownloader:
    """
    Downloads and processes SEC 10-K filings
    """
    
    def __init__(self):
        """Initialize SEC downloader"""
        
        # SEC requires user identification
        company_name = os.getenv("SEC_USER_NAME", "Individual Investor")
        email = os.getenv("SEC_USER_EMAIL", "user@example.com")
        
        if not company_name or not email:
            raise ValueError(
                "SEC_USER_NAME and SEC_USER_EMAIL must be set in .env file. "
                "The SEC requires this information to access EDGAR."
            )
        
        # Initialize downloader with user info
        self.downloader = Downloader(
            company_name=company_name,
            email_address=email
        )
        
        # Set download directory
        self.download_dir = Path("data/raw")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ SEC Downloader initialized (User: {company_name})")
    
    def download_10k(
        self, 
        ticker: str, 
        num_filings: int = 1,
        after_date: Optional[str] = None,
        before_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Download 10-K filings for a company
        
        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            num_filings: Number of recent filings to download (default: 1)
            after_date: Only download filings after this date (YYYY-MM-DD)
            before_date: Only download filings before this date (YYYY-MM-DD)
        
        Returns:
            List of dictionaries with filing metadata and file paths
        """
        
        ticker = ticker.upper()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📥 DOWNLOADING 10-K FILINGS FOR {ticker}")
        logger.info(f"{'='*70}")
        logger.info(f"Number of filings: {num_filings}")
        if after_date:
            logger.info(f"After date: {after_date}")
        if before_date:
            logger.info(f"Before date: {before_date}")
        logger.info(f"{'='*70}\n")
        
        try:
            # Download filings using correct parameters
            download_count = self.downloader.get(
                "10-K",              # Filing type
                ticker,              # Ticker symbol
                limit=num_filings,   # ✅ CORRECT: limit (not amount)
                after=after_date,    # Optional: filter by date
                before=before_date,  # Optional: filter by date
                download_details=True
            )
            
            if download_count == 0:
                logger.warning(f"⚠️  No 10-K filings found for {ticker}")
                return []
            
            logger.info(f"✅ Downloaded {download_count} filing(s)\n")
            
            # Find downloaded files
            filings = self._find_downloaded_files(ticker)
            
            logger.info(f"📁 Found {len(filings)} filing file(s)")
            for filing in filings:
                logger.info(f"   • {filing['accession']}")
            
            return filings
        
        except Exception as e:
            logger.error(f"❌ Download failed: {str(e)}")
            raise
    
    def _find_downloaded_files(self, ticker: str) -> List[Dict]:
        """
        Find downloaded filing files
        
        Args:
            ticker: Stock ticker
        
        Returns:
            List of filing metadata dictionaries
        """
        
        # sec-edgar-downloader saves files in: sec-edgar-filings/{ticker}/10-K/{accession}/
        base_path = Path("sec-edgar-filings") / ticker / "10-K"
        
        if not base_path.exists():
            logger.warning(f"Download directory not found: {base_path}")
            return []
        
        filings = []
        
        # Iterate through accession number directories
        for accession_dir in base_path.iterdir():
            if not accession_dir.is_dir():
                continue
            
            # Find the main filing document
            filing_file = None
            
            # Try different possible filenames
            possible_files = [
                accession_dir / "full-submission.txt",
                accession_dir / "primary-document.html",
            ]
            
            # Also check for any .htm or .html files
            for file in accession_dir.glob("*.htm*"):
                possible_files.append(file)
            
            for possible_file in possible_files:
                if possible_file.exists():
                    filing_file = possible_file
                    break
            
            if filing_file:
                filings.append({
                    "ticker": ticker,
                    "accession": accession_dir.name,
                    "file_path": str(filing_file.absolute()),
                    "filing_type": "10-K"
                })
        
        # Sort by accession number (most recent first)
        filings.sort(key=lambda x: x["accession"], reverse=True)
        
        return filings
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract clean text from SEC filing HTML/XML
        
        Args:
            file_path: Path to filing document
        
        Returns:
            Cleaned text content
        """
        
        logger.info(f"📄 Extracting text from: {Path(file_path).name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Parse HTML/XML
            soup = BeautifulSoup(content, 'lxml')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Remove page numbers
            text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
            
            # Remove excessive newlines
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            logger.info(f"✅ Extracted {len(text):,} characters")
            
            return text
        
        except Exception as e:
            logger.error(f"❌ Text extraction failed: {str(e)}")
            return ""


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    downloader = SECDownloader()
    filings = downloader.download_10k("AAPL", num_filings=1)
    
    if filings:
        text = downloader.extract_text(filings[0]["file_path"])
        print(f"\nExtracted {len(text)} characters")