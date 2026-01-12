"""
Tool Definitions with LangFuse Observability
"""

from llama_index.core.tools import FunctionTool
from langfuse.decorators import observe, langfuse_context
from typing import List, Dict, Optional
import json
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class ToolsFactory:
    """Factory for creating agent tools with observability"""
    
    def __init__(self, db, rag_engine, agent=None):
        """
        Initialize tools factory
        
        Args:
            db: Database instance
            rag_engine: RAG engine instance
            agent: Agent instance (for storing sources)
        """
        self.db = db
        self.rag_engine = rag_engine
        self.agent = agent
    
    def create_all_tools(self) -> List[FunctionTool]:
        """Create all available tools"""
        
        return [
            self.create_financial_data_tool(),
            self.create_search_tool(),
            self.create_comparison_tool()
        ]
    
    def create_financial_data_tool(self) -> FunctionTool:
        """
        Tool for getting exact financial metrics from database
        """
        
        @observe(name="get_financial_data_tool")
        def get_financial_data(ticker: str, fiscal_year: int, quarter: int = None) -> dict:
            """
            Get exact financial metrics from structured database
            
            Args:
                ticker: Stock ticker (e.g., 'AAPL')
                fiscal_year: Fiscal year (e.g., 2023)
                quarter: Optional fiscal quarter (1-4)
            
            Returns:
                Dictionary with financial metrics (revenue, net_income, assets, etc.)
            """
            
            # Update trace metadata
            langfuse_context.update_current_observation(
                metadata={
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "quarter": quarter
                }
            )
            
            try:
                logger.info(f"\n🔧 Tool: get_financial_data({ticker}, {fiscal_year}, quarter={quarter})")
                
                # Build query
                if quarter:
                    query = text("""
                        SELECT structured_data 
                        FROM filings f
                        JOIN companies c ON f.company_id = c.id
                        WHERE c.ticker = :ticker 
                          AND f.fiscal_year = :year
                          AND f.fiscal_quarter = :quarter
                          AND f.filing_type = '10-K'
                    """)
                    params = {"ticker": ticker, "year": fiscal_year, "quarter": quarter}
                else:
                    query = text("""
                        SELECT structured_data 
                        FROM filings f
                        JOIN companies c ON f.company_id = c.id
                        WHERE c.ticker = :ticker 
                          AND f.fiscal_year = :year
                          AND f.filing_type = '10-K'
                    """)
                    params = {"ticker": ticker, "year": fiscal_year}
                
                with self.db.engine.connect() as conn:
                    result = conn.execute(query, params).fetchone()
                
                if result and result[0]:
                    # JSONB column returns dict directly (not string)
                    financial_data = result[0]
                    
                    # Handle case where it might be a string (shouldn't happen with JSONB)
                    if isinstance(financial_data, str):
                        financial_data = json.loads(financial_data)
                    
                    logger.info(f"   ✅ Found data: {list(financial_data.keys())}")
                    
                    output = {
                        "ticker": ticker,
                        "fiscal_year": fiscal_year,
                        "quarter": quarter,
                        "data": financial_data
                    }
                    
                    # Update observation with success
                    langfuse_context.update_current_observation(
                        output=output,
                        metadata={"success": True, "data_keys": list(financial_data.keys())}
                    )
                    
                    return output
                else:
                    msg = f"No financial data found for {ticker} in {fiscal_year}"
                    logger.warning(f"   ⚠️  {msg}")
                    
                    langfuse_context.update_current_observation(
                        level="WARNING",
                        output={"error": msg}
                    )
                    
                    return {"error": msg}
            
            except Exception as e:
                logger.error(f"   ❌ Tool error: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                
                langfuse_context.update_current_observation(
                    level="ERROR",
                    output={"error": str(e)}
                )
                
                return {"error": str(e)}
        
        return FunctionTool.from_defaults(
            fn=get_financial_data,
            name="get_financial_data",
            description="""Get exact financial metrics from company 10-K filings.
            
Use this tool for questions about:
- Revenue, net income, earnings
- Assets, liabilities, equity
- Specific financial numbers from balance sheet or income statement

Examples:
- "What was Apple's revenue in 2023?" → get_financial_data("AAPL", 2023)
- "Show me Microsoft's net income for 2022" → get_financial_data("MSFT", 2022)

Returns: Dictionary with financial metrics including revenue, net_income, total_assets, etc.
"""
        )
    
    def create_search_tool(self) -> FunctionTool:
        """
        Tool for semantic search through 10-K documents
        """
        
        @observe(name="search_10k_tool")
        def search_10k(query: str, ticker: str, fiscal_year: int = None) -> dict:
            """
            Search 10-K filings semantically for qualitative information
            
            Args:
                query: Search query (e.g., "What are the main risk factors?")
                ticker: Stock ticker (e.g., 'AAPL')
                fiscal_year: Optional fiscal year to filter by
            
            Returns:
                Dictionary with answer and sources
            """
            
            langfuse_context.update_current_observation(
                metadata={
                    "query": query[:100],
                    "ticker": ticker,
                    "fiscal_year": fiscal_year
                }
            )
            
            try:
                logger.info(f"\n🔧 Tool: search_10k('{query[:50]}...', {ticker}, {fiscal_year})")
                
                result = self.rag_engine.ask(
                    question=query,
                    ticker=ticker,
                    fiscal_year=fiscal_year,
                    temperature=0.1
                )
                
                logger.info(f"   ✅ Found {result.get('num_sources', 0)} sources")
                
                # Store sources globally for the agent to access
                if self.agent:
                    self.agent.last_tool_sources = result.get('sources', [])
                    logger.info(f"   ✅ Stored {len(self.agent.last_tool_sources)} sources for citations")
                
                langfuse_context.update_current_observation(
                    output={"num_sources": result.get('num_sources', 0)},
                    metadata={"success": True}
                )
                
                return result
            
            except Exception as e:
                logger.error(f"   ❌ Tool error: {str(e)}")
                
                langfuse_context.update_current_observation(
                    level="ERROR",
                    output={"error": str(e)}
                )
                
                return {"error": str(e)}
        
        return FunctionTool.from_defaults(
            fn=search_10k,
            name="search_10k",
            description="""Search 10-K filings semantically for qualitative information.

Use this tool for questions about:
- Business description and strategy
- Products and services
- Risk factors
- Management discussion and analysis
- Any qualitative/narrative information

Examples:
- "What are Apple's main products?" → search_10k("main products", "AAPL")
- "What risks does Microsoft face?" → search_10k("risk factors", "MSFT", 2023)

Returns: Dictionary with answer and cited sources
"""
        )
    
    def create_comparison_tool(self) -> FunctionTool:
        """
        Tool for comparing companies
        """
        
        @observe(name="compare_companies_tool")
        def compare_companies(tickers: List[str], metric: str, fiscal_year: int) -> dict:
            """
            Compare financial metrics across multiple companies
            
            Args:
                tickers: List of stock tickers (e.g., ['AAPL', 'MSFT', 'GOOGL'])
                metric: Metric to compare (e.g., 'revenue', 'net_income', 'total_assets')
                fiscal_year: Fiscal year to compare
            
            Returns:
                Dictionary with comparison results and winner
            """
            
            langfuse_context.update_current_observation(
                metadata={
                    "tickers": tickers,
                    "metric": metric,
                    "fiscal_year": fiscal_year
                }
            )
            
            try:
                logger.info(f"\n🔧 Tool: compare_companies({tickers}, '{metric}', {fiscal_year})")
                
                results = []
                
                for ticker in tickers:
                    query = text("""
                        SELECT structured_data 
                        FROM filings f
                        JOIN companies c ON f.company_id = c.id
                        WHERE c.ticker = :ticker 
                          AND f.fiscal_year = :year
                          AND f.filing_type = '10-K'
                    """)
                    
                    with self.db.engine.connect() as conn:
                        result = conn.execute(query, {"ticker": ticker, "year": fiscal_year}).fetchone()
                    
                    if result and result[0]:
                        # JSONB returns dict directly
                        data = result[0]
                        
                        # Handle string case
                        if isinstance(data, str):
                            data = json.loads(data)
                        
                        value = data.get(metric)
                        if value:
                            results.append({
                                "ticker": ticker,
                                "metric": metric,
                                "value": value,
                                "year": fiscal_year
                            })
                
                if not results:
                    msg = f"No data found for comparison"
                    logger.warning(f"   ⚠️  {msg}")
                    
                    langfuse_context.update_current_observation(
                        level="WARNING",
                        output={"error": msg}
                    )
                    
                    return {"error": msg}
                
                # Sort by value (descending)
                results.sort(key=lambda x: x['value'], reverse=True)
                
                logger.info(f"   ✅ Compared {len(results)} companies")
                
                output = {
                    "comparison": results,
                    "winner": results[0],
                    "metric": metric,
                    "year": fiscal_year
                }
                
                langfuse_context.update_current_observation(
                    output={"num_companies": len(results), "winner": results[0]['ticker']},
                    metadata={"success": True}
                )
                
                return output
            
            except Exception as e:
                logger.error(f"   ❌ Tool error: {str(e)}")
                
                langfuse_context.update_current_observation(
                    level="ERROR",
                    output={"error": str(e)}
                )
                
                return {"error": str(e)}
        
        return FunctionTool.from_defaults(
            fn=compare_companies,
            name="compare_companies",
            description="""Compare financial metrics across multiple companies.

Use this tool for questions about:
- Which company has higher/lower X
- Ranking companies by metric
- Side-by-side comparisons

Examples:
- "Which had higher revenue, Apple or Microsoft in 2023?" 
  → compare_companies(["AAPL", "MSFT"], "revenue", 2023)
- "Rank these by assets" 
  → compare_companies(["AAPL", "MSFT", "GOOGL"], "total_assets", 2023)

Returns: Dictionary with ranked results and winner
"""
        )