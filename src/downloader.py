from sec_edgar_downloader import Downloader
from pathlib import Path
from bs4 import BeautifulSoup
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SECDownloader:
    """Download 10-K filings from SEC EDGAR"""
    
    def __init__(self, data_dir="./data/raw"):
        self.data_dir = data_dir
        # SEC requires company name and email
        self.downloader = Downloader(
            "YourCompany", 
            "your.email@example.com",
            data_dir
        )
        Path(data_dir).mkdir(parents=True, exist_ok=True)
    
    def download_10k(self, ticker: str, num_filings: int = 1):
        """Download recent 10-K filings"""
        logger.info(f"📥 Downloading {ticker} 10-K (last {num_filings} filing(s))...")
        
        try:
            # FIXED: Use 'limit' instead of 'amount'
            self.downloader.get("10-K", ticker, limit=num_filings)
            
            filings = self._find_filings(ticker)
            logger.info(f"✅ Downloaded {len(filings)} filing(s) for {ticker}")
            return filings
        except Exception as e:
            logger.error(f"❌ Error downloading {ticker}: {e}")
            return []
    
    def _find_filings(self, ticker: str):
        """Find downloaded filing files"""
        filing_dir = Path(self.data_dir) / "sec-edgar-filings" / ticker / "10-K"
        filings = []
        
        if filing_dir.exists():
            for folder in sorted(filing_dir.iterdir(), reverse=True):
                if folder.is_dir():
                    # Find main document
                    for file in folder.glob("*.txt"):
                        if "full-submission" in file.name.lower():
                            filings.append({
                                "ticker": ticker,
                                "file_path": str(file),
                                "accession": folder.name,
                                "fiscal_year": self._extract_year(folder.name)
                            })
                            break
        return filings
    
    def _extract_year(self, accession: str) -> int:
        """Extract fiscal year from accession number"""
        try:
            # Accession format: 0000320193-23-000106
            parts = accession.split("-")
            if len(parts) >= 2:
                year_part = parts[1]
                year = 2000 + int(year_part)
                return year
        except:
            pass
        return 2024
    
    def extract_text(self, file_path: str) -> str:
        """Extract clean text from filing"""
        logger.info(f"📄 Parsing {Path(file_path).name}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Parse HTML if needed
            if '<html' in content.lower() or '<HTML' in content:
                soup = BeautifulSoup(content, 'lxml')
                text = soup.get_text(separator='\n', strip=True)
            else:
                text = content
            
            # Clean up whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)
            text = re.sub(r' +', ' ', text)
            text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
            
            logger.info(f"✅ Extracted {len(text):,} characters")
            return text
        
        except Exception as e:
            logger.error(f"❌ Error parsing file: {e}")
            return ""


if __name__ == "__main__":
    downloader = SECDownloader()
    
    print("\n" + "="*60)
    print("Testing SEC Downloader")
    print("="*60)
    
    filings = downloader.download_10k("AAPL", num_filings=1)
    
    if filings:
        print(f"\n✅ Successfully downloaded {len(filings)} filing(s)")
        print(f"   Ticker: {filings[0]['ticker']}")
        print(f"   Year: {filings[0]['fiscal_year']}")
        print(f"   Accession: {filings[0]['accession']}")
        
        text = downloader.extract_text(filings[0]["file_path"])
        print(f"\n📊 Sample text (first 500 chars):")
        print(text[:500])
        print("...")
    else:
        print("\n❌ No filings downloaded")