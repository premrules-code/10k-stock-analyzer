"""
Improved 10-K Structured Data Extractor - Multi-Year Support with Apple Fix
Handles inconsistent column spacing and multiple table formats
"""

from bs4 import BeautifulSoup
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


class FilingMetadata(BaseModel):
    """Metadata from 10-K filing"""
    company_name: str
    cik: str
    accession_number: str
    filing_date: datetime
    fiscal_year_end: datetime


class KeyMetrics(BaseModel):
    """Key financial metrics extracted from 10-K"""
    revenue: Optional[float] = None
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_expenses: Optional[float] = None
    research_development: Optional[float] = None
    selling_general_admin: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    stockholders_equity: Optional[float] = None
    
    cash_and_equivalents: Optional[float] = None
    operating_cash_flow: Optional[float] = None


class Structured10K(BaseModel):
    """Complete structured 10-K data"""
    metadata: FilingMetadata
    key_metrics: KeyMetrics


class TenKStructuredExtractor:
    """Extract structured data from 10-K HTML filings - supports multi-year extraction"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract(self, file_path: str) -> Structured10K:
        """
        Extract structured data from 10-K filing (most recent year only)
        
        For backwards compatibility - returns only most recent year
        Use extract_all_years() to get all years from filing
        
        Args:
            file_path: Path to 10-K HTML file
        
        Returns:
            Structured10K object for most recent year
        """
        all_years = self.extract_all_years(file_path)
        return all_years[0] if all_years else None
    
    def extract_all_years(self, file_path: str) -> List[Structured10K]:
        """
        Extract structured data for ALL years in the 10-K filing
        
        Args:
            file_path: Path to 10-K HTML file
        
        Returns:
            List of Structured10K objects, one per year (most recent first)
        """
        
        self.logger.info(f"Extracting data from {file_path}")
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'lxml')
        
        # Extract metadata (same for all years in filing)
        base_metadata = self._extract_metadata(content, soup)
        
        # Extract financial metrics for all years
        all_years_metrics = self._extract_all_years_metrics(soup, base_metadata)
        
        # Create Structured10K for each year
        results = []
        
        for year_data in all_years_metrics:
            # Update metadata with specific year
            year_metadata = FilingMetadata(
                company_name=base_metadata.company_name,
                cik=base_metadata.cik,
                accession_number=base_metadata.accession_number,
                filing_date=base_metadata.filing_date,
                fiscal_year_end=year_data['fiscal_year_end']
            )
            
            results.append(Structured10K(
                metadata=year_metadata,
                key_metrics=year_data['metrics']
            ))
        
        self.logger.info(f"✅ Extracted {len(results)} years of data")
        
        return results
    
    def _extract_metadata(self, content: str, soup: BeautifulSoup) -> FilingMetadata:
        """Extract filing metadata from SEC header"""
        
        company_match = re.search(r'COMPANY CONFORMED NAME:\s*(.+)', content)
        company_name = company_match.group(1).strip() if company_match else "Unknown"
        
        cik_match = re.search(r'CENTRAL INDEX KEY:\s*(\d+)', content)
        cik = cik_match.group(1).strip() if cik_match else "0000000000"
        
        accession_match = re.search(r'ACCESSION NUMBER:\s*(\S+)', content)
        accession = accession_match.group(1).strip() if accession_match else "0000000000-00-000000"
        
        filing_date_match = re.search(r'FILED AS OF DATE:\s*(\d{8})', content)
        if filing_date_match:
            date_str = filing_date_match.group(1)
            filing_date = datetime.strptime(date_str, "%Y%m%d")
        else:
            filing_date = datetime.now()
        
        fiscal_match = re.search(r'FISCAL YEAR END:\s*(\d{4})', content)
        if fiscal_match:
            month_day = fiscal_match.group(1)
            fiscal_year_end = datetime.strptime(f"{filing_date.year}{month_day}", "%Y%m%d")
        else:
            fiscal_year_end = filing_date
        
        return FilingMetadata(
            company_name=company_name,
            cik=cik,
            accession_number=accession,
            filing_date=filing_date,
            fiscal_year_end=fiscal_year_end
        )
    
    def _extract_all_years_metrics(self, soup: BeautifulSoup, filing_metadata: FilingMetadata) -> List[Dict]:
        """
        Extract key financial metrics for ALL years in the filing
        Process consolidated statements LAST to ensure they override segment data
        
        Returns:
            List of dicts, each containing fiscal_year_end and KeyMetrics
        """
        
        all_years = []
        tables = soup.find_all('table')
        
        self.logger.info(f"Found {len(tables)} tables in filing")
        
        # Separate consolidated and non-consolidated tables
        consolidated_tables = []
        segment_tables = []
        
        for table_idx, table in enumerate(tables):
            table_text = table.get_text().lower()
            
            # Skip table of contents
            if 'page' in table_text[:500]:
                continue
            
            # Check if it's a consolidated statement
            is_consolidated = any(keyword in table_text for keyword in [
                'consolidated statements',
                'consolidated income',
                'consolidated balance'
            ])
            
            # Categorize income statements
            if any(keyword in table_text for keyword in [
                'consolidated statements of income',
                'consolidated statements of operations',
                'statements of income',
                'statements of operations'
            ]) or ('net sales' in table_text and 'income' in table_text):
                
                if is_consolidated:
                    consolidated_tables.append(('income', table_idx, table))
                else:
                    segment_tables.append(('income', table_idx, table))
            
            # Categorize balance sheets
            elif any(keyword in table_text for keyword in [
                'consolidated balance sheets',
                'balance sheets'
            ]):
                if is_consolidated:
                    consolidated_tables.append(('balance', table_idx, table))
                else:
                    segment_tables.append(('balance', table_idx, table))
            
            # Categorize cash flow statements
            elif any(keyword in table_text for keyword in [
                'consolidated statements of cash flows',
                'statements of cash flows'
            ]):
                if is_consolidated:
                    consolidated_tables.append(('cashflow', table_idx, table))
                else:
                    segment_tables.append(('cashflow', table_idx, table))
        
        # Process segment tables FIRST, then consolidated tables LAST
        # This ensures consolidated data takes precedence
        income_found = False
        balance_found = False
        cashflow_found = False
        
        for tables_to_process in [segment_tables, consolidated_tables]:
            for stmt_type, table_idx, table in tables_to_process:
                if stmt_type == 'income':
                    self.logger.info(f"✅ Found income statement in table {table_idx}")
                    income_found = True
                    years_data = self._extract_multi_year_income_statement(table)
                    
                    if years_data:
                        self.logger.info(f"   📊 Extracted {len(years_data)} years from income statement")
                        for year_data in years_data:
                            existing = next((y for y in all_years if y['fiscal_year_end'] == year_data['fiscal_year_end']), None)
                            
                            if existing:
                                self._merge_metrics(existing['metrics'], year_data['metrics'], is_consolidated=(tables_to_process == consolidated_tables))
                            else:
                                all_years.append(year_data)
                    else:
                        self.logger.warning(f"   ⚠️  Could not parse income statement in table {table_idx}")
                
                elif stmt_type == 'balance':
                    self.logger.info(f"✅ Found balance sheet in table {table_idx}")
                    balance_found = True
                    years_data = self._extract_multi_year_balance_sheet(table)
                    
                    if years_data:
                        self.logger.info(f"   📊 Extracted {len(years_data)} years from balance sheet")
                        for year_data in years_data:
                            existing = next((y for y in all_years if y['fiscal_year_end'] == year_data['fiscal_year_end']), None)
                            
                            if existing:
                                self._merge_metrics(existing['metrics'], year_data['metrics'], is_consolidated=(tables_to_process == consolidated_tables))
                            else:
                                all_years.append(year_data)
                    else:
                        self.logger.warning(f"   ⚠️  Could not parse balance sheet in table {table_idx}")
                
                elif stmt_type == 'cashflow':
                    self.logger.info(f"✅ Found cash flow statement in table {table_idx}")
                    cashflow_found = True
                    years_data = self._extract_multi_year_cash_flow(table)
                    
                    if years_data:
                        self.logger.info(f"   📊 Extracted {len(years_data)} years from cash flow")
                        for year_data in years_data:
                            existing = next((y for y in all_years if y['fiscal_year_end'] == year_data['fiscal_year_end']), None)
                            
                            if existing:
                                self._merge_metrics(existing['metrics'], year_data['metrics'], is_consolidated=(tables_to_process == consolidated_tables))
                            else:
                                all_years.append(year_data)
                    else:
                        self.logger.warning(f"   ⚠️  Could not parse cash flow in table {table_idx}")
        
        # Deduplicate: Keep only ONE entry per fiscal year
        # Preference: consolidated > larger revenue > first found
        unique_years = {}
        
        for year_data in all_years:
            fy = year_data['fiscal_year_end'].year
            
            if fy not in unique_years:
                unique_years[fy] = year_data
            else:
                # Already have this year - compare and keep the better one
                existing_revenue = unique_years[fy]['metrics'].revenue
                new_revenue = year_data['metrics'].revenue
                
                # If new has revenue and existing doesn't, or new is larger, use new
                if new_revenue is not None:
                    if existing_revenue is None or new_revenue > existing_revenue:
                        self.logger.info(f"   📊 Updated FY {fy} revenue: {new_revenue:,.0f}")
                        unique_years[fy] = year_data
        
        all_years = list(unique_years.values())
        self.logger.info(f"   🔄 Deduplicated to {len(all_years)} unique fiscal years")
        
        # Sort by fiscal year (most recent first)
        all_years.sort(key=lambda x: x['fiscal_year_end'], reverse=True)
        
        # FILTER: Only keep years within reasonable range of filing date
        filing_year = filing_metadata.filing_date.year
        filtered_years = []
        
        for year_data in all_years:
            year = year_data['fiscal_year_end'].year
            years_diff = abs(filing_year - year)
            
            if years_diff <= 5 and year >= (filing_year - 4):
                filtered_years.append(year_data)
            else:
                self.logger.debug(f"   🗑️  Filtered out FY {year} (too old, {years_diff} years from filing date)")
        
        if filtered_years:
            all_years = filtered_years
            self.logger.info(f"   🔍 Filtered to {len(all_years)} recent years (within 5 years of filing)")
        
        # Summary log
        self.logger.info(f"📈 EXTRACTION SUMMARY:")
        self.logger.info(f"   Income Statement: {'✅ Found' if income_found else '❌ Not Found'}")
        self.logger.info(f"   Balance Sheet: {'✅ Found' if balance_found else '❌ Not Found'}")
        self.logger.info(f"   Cash Flow: {'✅ Found' if cashflow_found else '❌ Not Found'}")
        self.logger.info(f"   Total years extracted (after filtering): {len(all_years)}")
        
        if not all_years:
            self.logger.warning("⚠️  No financial data extracted - check 10-K HTML structure")
        
        return all_years
    
    def _extract_multi_year_income_statement(self, table) -> List[Dict]:
        """Extract metrics from income statement - APPLE FIXED WITH DYNAMIC COLUMN DETECTION"""
        
        rows = table.find_all('tr')
        if not rows:
            return []
        
        # Get header text from multiple rows
        header_text = ' '.join([r.get_text().lower() for r in rows[:3]])
        
        # Determine unit multiplier
        unit_multiplier = 1_000_000 if 'millions' in header_text or '$ in millions' in header_text else 1_000
        
        # CHECK FIRST 5 ROWS FOR YEARS
        year_columns = []
        year_row_idx = None
        
        for header_row_idx in range(min(5, len(rows))):
            header_cells = rows[header_row_idx].find_all(['th', 'td'])
            
            for col_idx in range(len(header_cells)):
                cell_text = header_cells[col_idx].get_text().strip()
                
                if not cell_text:
                    continue
                
                fiscal_year_end = None
                year = None
                
                # Pattern 1: Full date like "September 28, 2024"
                year_match = re.search(r'(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+\d{1,2},?\s+(\d{4})', cell_text.lower())
                
                if year_match:
                    year = int(year_match.group(2))
                    try:
                        fiscal_year_end = datetime.strptime(cell_text.replace(',', ''), "%B %d %Y")
                    except:
                        try:
                            fiscal_year_end = datetime.strptime(cell_text.replace(',', ''), "%b %d %Y")
                        except:
                            fiscal_year_end = datetime(year, 9, 30)
                
                # Pattern 2: Just year like "2025", "2024" (APPLE USES THIS)
                if not year:
                    year_match = re.search(r'^\s*(20\d{2})\s*$', cell_text)
                    if year_match:
                        year = int(year_match.group(1))
                        fiscal_year_end = datetime(year, 9, 30)
                
                # Pattern 3: Year anywhere in text
                if not year:
                    year_match = re.search(r'\b(20\d{2})\b', cell_text)
                    if year_match:
                        year = int(year_match.group(1))
                        fiscal_year_end = datetime(year, 12, 31)
                
                if year and fiscal_year_end:
                    # Check if we already have this column index
                    if not any(yc['col_idx'] == col_idx for yc in year_columns):
                        year_columns.append({
                            'col_idx': col_idx,
                            'fiscal_year_end': fiscal_year_end,
                            'metrics': KeyMetrics()
                        })
                        year_row_idx = header_row_idx
                        self.logger.info(f"  ✅ Found FY {fiscal_year_end.year} in col {col_idx} (row {header_row_idx})")
            
            # If we found years in this row, stop checking other rows
            if year_columns:
                break
        
        if not year_columns:
            self.logger.warning("  ⚠️  No year columns found in any header row")
            return []
        
        # Determine data start row (Apple: row after years)
        if year_row_idx is not None:
            data_start_row = year_row_idx + 1
            self.logger.info(f"  📍 Data starts at row {data_start_row}")
        else:
            data_start_row = 2
        
        # Extract data
        for row_idx, row in enumerate(rows[data_start_row:], start=data_start_row):
            row_text = row.get_text().lower()
            cells = row.find_all(['td', 'th'])
            
            if len(cells) < 2:
                continue
            
            for year_col in year_columns:
                year_col_idx = year_col['col_idx']
                
                # APPLE FIX: Try multiple column offsets
                # Apple's tables have inconsistent spacing:
                # - FY 2025: Year col 1 → Value col 2 (offset +1)
                # - FY 2024: Year col 3 → Value col 6 (offset +3)
                # - FY 2023: Year col 5 → Value col 6 (offset +1)
                attempts = [
                    year_col_idx + 1,  # Most common: next column
                    year_col_idx + 2,  # Sometimes: Year | $ | Value
                    year_col_idx + 3,  # Apple: Year | empty | $ | Value
                    year_col_idx + 4,  # More spacing
                    year_col_idx       # Fallback: same column
                ]
                
                value = None
                value_col_idx = None
                
                for try_col in attempts:
                    if try_col >= len(cells):
                        continue
                    
                    cell_text = cells[try_col].get_text().strip()
                    
                    # Skip cells with just "$" or empty
                    if not cell_text or cell_text == '$':
                        continue
                    
                    cell_value = self._extract_number(cell_text)
                    
                    if cell_value is not None and abs(cell_value) >= 10:
                        value = cell_value
                        value_col_idx = try_col
                        break
                
                if value is None or abs(value) < 10:
                    continue
                
                value = value * unit_multiplier
                metrics = year_col['metrics']
                fy = year_col['fiscal_year_end'].year
                
                # Match metrics - SIMPLIFIED PATTERNS
                
                # Revenue / Net Sales (prefer "total")
                if 'net sales' in row_text and 'cost' not in row_text:
                    is_total = 'total' in row_text
                    
                    if metrics.revenue is None:
                        metrics.revenue = value
                        self.logger.info(f"    ✅ [FY {fy}] Revenue: ${value:,.0f} (row {row_idx}, col {value_col_idx})")
                    elif is_total and value > (metrics.revenue or 0):
                        metrics.revenue = value
                        self.logger.info(f"    ✅ [FY {fy}] Revenue TOTAL: ${value:,.0f}")
                
                # Cost of Sales / Cost of Revenue
                elif 'cost of sales' in row_text or 'cost of revenue' in row_text or 'cost of products and services' in row_text:
                    if metrics.cost_of_revenue is None or abs(value) > abs(metrics.cost_of_revenue or 0):
                        metrics.cost_of_revenue = abs(value)
                        self.logger.info(f"    ✅ [FY {fy}] Cost: ${value:,.0f}")
                
                # Gross Margin / Gross Profit
                elif 'gross margin' in row_text or 'gross profit' in row_text:
                    if metrics.gross_profit is None or value > (metrics.gross_profit or 0):
                        metrics.gross_profit = value
                        self.logger.info(f"    ✅ [FY {fy}] Gross Profit: ${value:,.0f}")
                
                # Research and Development
                elif 'research and development' in row_text or 'research & development' in row_text:
                    if metrics.research_development is None or value > (metrics.research_development or 0):
                        metrics.research_development = value
                        self.logger.info(f"    ✅ [FY {fy}] R&D: ${value:,.0f}")
                
                # SG&A
                elif 'selling, general and administrative' in row_text or 'sales, general and administrative' in row_text:
                    if metrics.selling_general_admin is None or value > (metrics.selling_general_admin or 0):
                        metrics.selling_general_admin = value
                        self.logger.info(f"    ✅ [FY {fy}] SG&A: ${value:,.0f}")
                
                # Total Operating Expenses
                elif 'total operating expenses' in row_text and 'income' not in row_text:
                    if metrics.operating_expenses is None or value > (metrics.operating_expenses or 0):
                        metrics.operating_expenses = value
                        self.logger.info(f"    ✅ [FY {fy}] Op Exp: ${value:,.0f}")
                
                # Operating Income
                elif ('operating income' in row_text or 'income from operations' in row_text) and 'non-operating' not in row_text:
                    if metrics.operating_income is None or value > (metrics.operating_income or 0):
                        metrics.operating_income = value
                        self.logger.info(f"    ✅ [FY {fy}] Op Income: ${value:,.0f}")
                
                # Net Income
                elif row_text.strip().startswith('net income') and 'diluted' not in row_text and 'basic' not in row_text:
                    if metrics.net_income is None or value > (metrics.net_income or 0):
                        metrics.net_income = value
                        self.logger.info(f"    ✅ [FY {fy}] Net Income: ${value:,.0f}")
        
        return year_columns
    
    def _extract_multi_year_balance_sheet(self, table) -> List[Dict]:
        """Extract metrics from balance sheet - APPLE FIXED WITH DYNAMIC COLUMN DETECTION"""
        
        rows = table.find_all('tr')
        if not rows:
            return []
        
        header_text = ' '.join([r.get_text().lower() for r in rows[:3]])
        unit_multiplier = 1_000_000 if 'millions' in header_text else 1_000
        
        # Find year columns
        year_columns = []
        year_row_idx = None
        
        for header_row_idx in range(min(5, len(rows))):
            header_cells = rows[header_row_idx].find_all(['th', 'td'])
            
            for col_idx in range(len(header_cells)):
                cell_text = header_cells[col_idx].get_text().strip()
                
                year_match = re.search(r'\b(20\d{2})\b', cell_text)
                if year_match:
                    year = int(year_match.group(1))
                    
                    if not any(yc['col_idx'] == col_idx for yc in year_columns):
                        year_columns.append({
                            'col_idx': col_idx,
                            'fiscal_year_end': datetime(year, 9, 30),
                            'metrics': KeyMetrics()
                        })
                        year_row_idx = header_row_idx
                        self.logger.info(f"  ✅ Found FY {year} in col {col_idx}")
            
            if year_columns:
                break
        
        if not year_columns:
            return []
        
        # Data starts after year row
        data_start_row = (year_row_idx + 1) if year_row_idx is not None else 2
        
        # Extract data
        for row in rows[data_start_row:]:
            row_text = row.get_text().lower()
            cells = row.find_all(['td', 'th'])
            
            if len(cells) < 2:
                continue
            
            for year_col in year_columns:
                year_col_idx = year_col['col_idx']
                
                # APPLE FIX: Try multiple column offsets
                attempts = [
                    year_col_idx + 1,
                    year_col_idx + 2,
                    year_col_idx + 3,
                    year_col_idx + 4,
                    year_col_idx
                ]
                
                value = None
                
                for try_col in attempts:
                    if try_col >= len(cells):
                        continue
                    
                    cell_text = cells[try_col].get_text().strip()
                    
                    if not cell_text or cell_text == '$':
                        continue
                    
                    cell_value = self._extract_number(cell_text)
                    
                    if cell_value is not None:
                        value = cell_value
                        break
                
                if value is None:
                    continue
                
                value = value * unit_multiplier
                metrics = year_col['metrics']
                fy = year_col['fiscal_year_end'].year
                
                # Total Assets
                if 'total assets' in row_text and 'liabilities' not in row_text:
                    if metrics.total_assets is None or value > (metrics.total_assets or 0):
                        metrics.total_assets = value
                        self.logger.info(f"    ✅ [FY {fy}] Total Assets: ${value:,.0f}")
                
                # Total Liabilities
                elif 'total liabilities' in row_text:
                    if metrics.total_liabilities is None or value > (metrics.total_liabilities or 0):
                        metrics.total_liabilities = value
                        self.logger.info(f"    ✅ [FY {fy}] Total Liabilities: ${value:,.0f}")
                
                # Stockholders Equity
                elif 'total stockholders' in row_text or "total shareholders' equity" in row_text:
                    if metrics.stockholders_equity is None or value > (metrics.stockholders_equity or 0):
                        metrics.stockholders_equity = value
                        self.logger.info(f"    ✅ [FY {fy}] Equity: ${value:,.0f}")
                
                # Cash and Cash Equivalents
                elif 'cash and cash equivalents' in row_text and 'restricted' not in row_text:
                    if metrics.cash_and_equivalents is None or value > (metrics.cash_and_equivalents or 0):
                        metrics.cash_and_equivalents = value
                        self.logger.info(f"    ✅ [FY {fy}] Cash: ${value:,.0f}")
        
        return year_columns
    
    def _extract_multi_year_cash_flow(self, table) -> List[Dict]:
        """Extract metrics from cash flow statement - APPLE FIXED WITH DYNAMIC COLUMN DETECTION"""
        
        rows = table.find_all('tr')
        if not rows:
            return []
        
        header_text = ' '.join([r.get_text().lower() for r in rows[:3]])
        unit_multiplier = 1_000_000 if 'millions' in header_text else 1_000
        
        # Find year columns
        year_columns = []
        year_row_idx = None
        
        for header_row_idx in range(min(5, len(rows))):
            header_cells = rows[header_row_idx].find_all(['th', 'td'])
            
            for col_idx in range(len(header_cells)):
                cell_text = header_cells[col_idx].get_text().strip()
                
                year_match = re.search(r'\b(20\d{2})\b', cell_text)
                if year_match:
                    year = int(year_match.group(1))
                    
                    if not any(yc['col_idx'] == col_idx for yc in year_columns):
                        year_columns.append({
                            'col_idx': col_idx,
                            'fiscal_year_end': datetime(year, 9, 30),
                            'metrics': KeyMetrics()
                        })
                        year_row_idx = header_row_idx
                        self.logger.info(f"  ✅ Found FY {year} in col {col_idx}")
            
            if year_columns:
                break
        
        if not year_columns:
            return []
        
        # Data starts after year row
        data_start_row = (year_row_idx + 1) if year_row_idx is not None else 2
        
        # Extract data
        for row in rows[data_start_row:]:
            row_text = row.get_text().lower()
            cells = row.find_all(['td', 'th'])
            
            if len(cells) < 2:
                continue
            
            for year_col in year_columns:
                year_col_idx = year_col['col_idx']
                
                # APPLE FIX: Try multiple column offsets
                attempts = [
                    year_col_idx + 1,
                    year_col_idx + 2,
                    year_col_idx + 3,
                    year_col_idx + 4,
                    year_col_idx
                ]
                
                value = None
                
                for try_col in attempts:
                    if try_col >= len(cells):
                        continue
                    
                    cell_text = cells[try_col].get_text().strip()
                    
                    if not cell_text or cell_text == '$':
                        continue
                    
                    cell_value = self._extract_number(cell_text)
                    
                    if cell_value is not None:
                        value = cell_value
                        break
                
                if value is None:
                    continue
                
                value = value * unit_multiplier
                metrics = year_col['metrics']
                fy = year_col['fiscal_year_end'].year
                
                # Operating Cash Flow
                if 'net cash provided by operating activities' in row_text or 'net cash from operating activities' in row_text:
                    if metrics.operating_cash_flow is None or abs(value) > abs(metrics.operating_cash_flow or 0):
                        metrics.operating_cash_flow = value
                        self.logger.info(f"    ✅ [FY {fy}] Operating Cash Flow: ${value:,.0f}")
        
        return year_columns
    
    def _merge_metrics(self, existing: KeyMetrics, new: KeyMetrics, is_consolidated: bool = False):
        """
        Merge new metrics into existing metrics with smart logic:
        - For consolidated data (is_consolidated=True), ALWAYS overwrite with consolidated values
        - For segment data, only fill NULL values
        """
        
        for field in KeyMetrics.model_fields:
            existing_val = getattr(existing, field)
            new_val = getattr(new, field)
            
            # If existing is None, always take the new value
            if existing_val is None and new_val is not None:
                setattr(existing, field, new_val)
            
            # If both have values and this is consolidated data, ALWAYS use consolidated
            elif existing_val is not None and new_val is not None:
                if is_consolidated:
                    # For consolidated data, ALWAYS overwrite with the new value
                    # Consolidated statements take precedence over segment data
                    setattr(existing, field, new_val)
                    if field == 'revenue' and isinstance(new_val, (int, float)):
                        self.logger.debug(f"   ✅ Merging consolidated {field}: {new_val:,.0f}")
    
    def _extract_number(self, text: str) -> Optional[float]:
        """
        Extract number from text, handling various formats
        
        Examples:
            "$416,161" → 416161.0
            "(1,234)" → -1234.0
            "1234.56" → 1234.56
        """
        
        cleaned = text.replace('$', '').replace(' ', '').strip()
        
        # Handle negative numbers in parentheses
        is_negative = False
        if cleaned.startswith('(') and cleaned.endswith(')'):
            is_negative = True
            cleaned = cleaned[1:-1]
        
        # Remove commas
        cleaned = cleaned.replace(',', '')
        
        try:
            value = float(cleaned)
            return -value if is_negative else value
        except:
            return None