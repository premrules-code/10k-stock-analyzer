"""
Financial Agent - OpenAI Agent with Complete LangFuse Integration
"""

from llama_index.agent.openai import OpenAIAgent
from llama_index.llms.openai import OpenAI
from llama_index.core.callbacks import CallbackManager
from src.database import Database
from src.rag_engine import MultiCompanyStockAnalyzer
from src.tools import ToolsFactory
from typing import Optional, Dict
from langfuse.decorators import observe, langfuse_context
import logging
import os

logger = logging.getLogger(__name__)


class FinancialAgent:
    """
    AI Agent for 10-K analysis with complete LangFuse tracing
    """
    
    def __init__(self):
        """Initialize agent with tools and LangFuse callbacks"""
        
        logger.info("\n" + "="*70)
        logger.info("🤖 INITIALIZING FINANCIAL AGENT")
        logger.info("="*70 + "\n")
        
        # Initialize components
        logger.info("1️⃣  Initializing database...")
        self.db = Database()
        
        logger.info("2️⃣  Initializing RAG engine...")
        self.rag_engine = MultiCompanyStockAnalyzer()
        
        # Store last tool sources for citation extraction
        self.last_tool_sources = []
        
        # Setup LangFuse callback handler for LlamaIndex
        logger.info("3️⃣  Setting up LangFuse integration...")
        self.langfuse_handler = None
        
        try:
            langfuse_public = os.getenv("LANGFUSE_PUBLIC_KEY")
            langfuse_secret = os.getenv("LANGFUSE_SECRET_KEY")
            langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            
            if langfuse_public and langfuse_secret:
                try:
                    from langfuse.llama_index import LlamaIndexCallbackHandler
                    
                    self.langfuse_handler = LlamaIndexCallbackHandler(
                        public_key=langfuse_public,
                        secret_key=langfuse_secret,
                        host=langfuse_host
                    )
                    
                    logger.info(f"   ✅ LangFuse callback handler enabled")
                    
                except ImportError:
                    logger.warning("   ⚠️  LangFuse LlamaIndex integration not found")
                    logger.info("   ℹ️  Install with: pip install langfuse")
            else:
                logger.info("   ℹ️  LangFuse disabled (no API keys)")
        
        except Exception as e:
            logger.warning(f"   ⚠️  LangFuse setup failed: {str(e)}")
        
        # Create LLM with callback
        logger.info("4️⃣  Creating LLM...")
        self.llm = OpenAI(
            model="gpt-4",
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Attach callback manager to LLM
        if self.langfuse_handler:
            self.llm.callback_manager = CallbackManager([self.langfuse_handler])
        
        # Create tools (pass self so tools can store sources)
        logger.info("5️⃣  Creating tools...")
        tools_factory = ToolsFactory(self.db, self.rag_engine, agent=self)
        self.tools = tools_factory.create_all_tools()
        
        logger.info(f"   ✅ Created {len(self.tools)} tools:")
        for tool in self.tools:
            logger.info(f"      • {tool.metadata.name}")
        
        # Create agent with callback
        logger.info("6️⃣  Creating OpenAI agent...")
        
        agent_callback_manager = None
        if self.langfuse_handler:
            agent_callback_manager = CallbackManager([self.langfuse_handler])
        
        self.agent = OpenAIAgent.from_tools(
            tools=self.tools,
            llm=self.llm,
            verbose=True,
            system_prompt=self._get_system_prompt(),
            callback_manager=agent_callback_manager
        )
        
        logger.info("\n" + "="*70)
        logger.info("✅ FINANCIAL AGENT READY (with LangFuse callbacks)")
        logger.info("="*70 + "\n")
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for agent"""
        
        return """You are a financial analysis assistant specialized in analyzing SEC 10-K filings.

Your capabilities:
- Extract exact financial metrics from databases
- Search 10-K documents semantically
- Compare companies across metrics
- Analyze trends over time

IMPORTANT - Fiscal Year Handling:
- If user asks for "2023" data and not found, try 2024 (companies have different fiscal year ends)
- For "latest" or "most recent", try to find the most recent year available
- Always tell the user which fiscal year the data is actually from

Guidelines for tool usage:
- For SPECIFIC NUMBERS → Use get_financial_data tool
- For QUALITATIVE info → Use search_10k tool  
- For COMPARISONS → Use compare_companies tool

Response guidelines:
- **CRITICAL**: You MUST add citation numbers in square brackets [1], [2], [3] etc. immediately after EVERY fact or statement you make
- Example: "Apple's revenue was $383 billion[1]. The iPhone is their main product[2]."
- Place the citation marker RIGHT AFTER the fact, before the period
- DO NOT include URLs or links in your answer
- DO NOT use markdown citation syntax like [^1^] or [Source](url)
- DO NOT add phrases like "This information is based on..." or "According to the 10-K filing..."
- Simply provide a clear, direct answer with citation markers after each fact
- State which fiscal year the data is from when relevant
- Use precise numbers with commas
- Be concise but complete
- The system will automatically show full source citations below your answer

REMEMBER: Every factual statement MUST have a citation marker [1], [2], etc."""
    
    @observe(name="financial_query")
    def ask(
        self,
        question: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> Dict:
        """
        Ask a question with full tracing
        
        Args:
            question: User question
            temperature: LLM temperature
            max_tokens: Optional token limit
        
        Returns:
            Dictionary with answer and citations
        """
        
        try:
            langfuse_context.update_current_trace(
                user_id="streamlit_user",
                session_id="default_session",
                metadata={
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "question_length": len(question)
                },
                tags=["financial_analysis", "10k_filing"]
            )
        except:
            pass
        
        self.llm.temperature = temperature
        
        logger.info("\n" + "="*70)
        logger.info("💬 NEW QUERY")
        logger.info("="*70)
        logger.info(f"Question: {question}")
        logger.info(f"Temperature: {temperature}")
        logger.info("="*70 + "\n")
        
        try:
            # Clear previous tool sources
            self.last_tool_sources = []
            
            response = self.agent.chat(question)
            
            citations = []
            
            # Try to extract citations from source_nodes (direct RAG)
            if hasattr(response, 'source_nodes') and response.source_nodes:
                logger.info("   📚 Extracting citations from source_nodes...")
                sorted_nodes = sorted(
                    response.source_nodes,
                    key=lambda x: getattr(x, 'score', 0),
                    reverse=True
                )
                
                for i, node in enumerate(sorted_nodes[:5], 1):
                    metadata = node.metadata if hasattr(node, 'metadata') else {}
                    
                    # Get node ID for chunk identification
                    node_id = getattr(node, 'node_id', 'unknown')
                    chunk_num = node_id.split('-')[-1] if '-' in str(node_id) else 'N/A'
                    
                    citation = {
                        "id": i,
                        "company": metadata.get('company_name', 'Unknown Company'),
                        "ticker": metadata.get('ticker', 'N/A'),
                        "fiscal_year": metadata.get('fiscal_year', 'N/A'),
                        "filing_date": metadata.get('filing_date', 'N/A'),
                        "text": node.text,
                        "score": float(getattr(node, 'score', 0)) if hasattr(node, 'score') else None,
                        "chunk_id": chunk_num,
                        "text_length": len(node.text),
                        "accession_number": metadata.get('accession_number', ''),
                        "filing_url": metadata.get('filing_url', '')
                    }
                    
                    citations.append(citation)
            
            # Try to extract citations from tool sources (when using search_10k tool)
            elif self.last_tool_sources:
                logger.info(f"   📚 Extracting citations from {len(self.last_tool_sources)} tool sources...")
                for i, source in enumerate(self.last_tool_sources[:5], 1):
                    if isinstance(source, dict):
                        citation = {
                            "id": i,
                            "company": source.get('company_name', source.get('company', 'Unknown Company')),
                            "ticker": source.get('ticker', 'N/A'),
                            "fiscal_year": source.get('fiscal_year', 'N/A'),
                            "filing_date": source.get('filing_date', 'N/A'),
                            "text": source.get('text', source.get('content', '')),
                            "score": source.get('score'),
                            "chunk_id": source.get('chunk_id', 'N/A'),
                            "text_length": len(source.get('text', source.get('content', ''))),
                            "accession_number": source.get('accession_number', ''),
                            "filing_url": source.get('filing_url', '')
                        }
                        citations.append(citation)
            
            logger.info(f"   ✅ Extracted {len(citations)} citations")

            
            logger.info("\n" + "="*70)
            logger.info("✅ QUERY COMPLETE")
            logger.info("="*70 + "\n")
            
            result = {
                "answer": str(response),
                "citations": citations,
                "has_citations": len(citations) > 0
            }
            
            try:
                langfuse_context.update_current_trace(
                    output={
                        "answer_length": len(str(response)),
                        "num_citations": len(citations)
                    }
                )
            except:
                pass
            
            return result
        
        except Exception as e:
            logger.error(f"\n❌ QUERY FAILED: {str(e)}\n")
            import traceback
            logger.error(traceback.format_exc())
            
            try:
                langfuse_context.update_current_trace(
                    metadata={"error": str(e), "status": "error"}
                )
            except:
                pass
            
            return {
                "answer": f"I encountered an error processing your question: {str(e)}",
                "citations": [],
                "has_citations": False,
                "error": str(e)
            }
    
    @observe(name="company_analysis")
    def analyze_company(self, ticker: str, num_filings: int = 1) -> bool:
        """
        Download and analyze a company's 10-K filings
        
        Args:
            ticker: Stock ticker (e.g., "AAPL")
            num_filings: Number of recent filings to download
        
        Returns:
            True if successful, False otherwise
        """
        
        from src.downloader import SECDownloader
        from src.structured_parser import TenKStructuredExtractor
        
        try:
            langfuse_context.update_current_trace(
                metadata={
                    "ticker": ticker,
                    "num_filings": num_filings
                },
                tags=["download", "sec_filing", ticker]
            )
        except:
            pass
        
        logger.info("\n" + "="*70)
        logger.info(f"📊 ANALYZING {ticker}")
        logger.info("="*70 + "\n")
        
        try:
            # Step 1: Download
            logger.info("STEP 1: Downloading filings from SEC...")
            downloader = SECDownloader()
            filings = downloader.download_10k(ticker, num_filings=num_filings)
            
            if not filings:
                logger.error(f"❌ No filings found for {ticker}")
                try:
                    langfuse_context.update_current_trace(
                        output={"success": False, "reason": "no_filings_found"}
                    )
                except:
                    pass
                return False
            
            logger.info(f"✅ Downloaded {len(filings)} filing(s)\n")
            
            # Step 2: Parse and store each filing (with all years)
            parser = TenKStructuredExtractor()
            total_years_stored = 0
            
            for i, filing in enumerate(filings, 1):
                logger.info(f"STEP 2.{i}: Processing filing {i}/{len(filings)}...")
                logger.info(f"  Accession: {filing['accession']}")
                logger.info(f"  File: {filing['file_path']}")
                
                # Parse structured data - extract ALL years
                logger.info("  • Extracting structured data (all years)...")
                all_years_data = parser.extract_all_years(filing["file_path"])
                
                if not all_years_data:
                    logger.warning(f"  ⚠️  No structured data extracted for {ticker}")
                    logger.warning(f"  ℹ️  This might be due to unusual table formatting")
                    logger.warning(f"  ℹ️  Will still add text to RAG index")
                    
                    # Create a basic entry with minimal data
                    from src.structured_parser import Structured10K, FilingMetadata, KeyMetrics
                    
                    # Get basic metadata
                    with open(filing["file_path"], 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, 'lxml')
                    base_metadata = parser._extract_metadata(content, soup)
                    
                    # Create minimal structured data
                    minimal_data = Structured10K(
                        metadata=base_metadata,
                        key_metrics=KeyMetrics()
                    )
                    
                    all_years_data = [minimal_data]
                
                logger.info(f"  • Found {len(all_years_data)} years of data")
                
                # Store each year as a separate filing
                for structured_10k in all_years_data:
                    fiscal_year = structured_10k.metadata.fiscal_year_end.year
                    
                    logger.info(f"  • Storing FY {fiscal_year} in database...")
                    
                    # Add company
                    company_id = self.db.add_company(
                        ticker=ticker,
                        company_name=structured_10k.metadata.company_name,
                        cik=structured_10k.metadata.cik
                    )
                    
                    # Get structured data as dict
                    structured_data_dict = structured_10k.key_metrics.model_dump()

                    # LOG WHAT WE'RE ABOUT TO INSERT
                    logger.info(f"\n    📊 STRUCTURED DATA TO INSERT FOR FY {fiscal_year}:")
                    logger.info(f"    " + "="*60)
                    for key, value in structured_data_dict.items():
                        if value is not None:
                            if isinstance(value, (int, float)):
                                logger.info(f"    {key:30s}: ${value:,.0f}")
                            else:
                                logger.info(f"    {key:30s}: {value}")
                        else:
                            logger.info(f"    {key:30s}: NULL")
                    logger.info(f"    " + "="*60)

                    # Add filing for this specific year
                    filing_id = self.db.add_filing(
                        company_id=company_id,
                        filing_data={
                            "accession": structured_10k.metadata.accession_number,
                            "fiscal_year": fiscal_year,
                            "filing_type": "10-K",
                            "filing_date": str(structured_10k.metadata.filing_date),
                            "file_path": filing["file_path"]
                        },
                        structured_data=structured_data_dict
                    )

                    logger.info(f"    ✅ FY {fiscal_year} stored (Filing ID: {filing_id})\n")

                    if structured_10k.key_metrics.revenue:

                        logger.info(f"       Revenue: ${structured_10k.key_metrics.revenue:,.0f}")
                    else:
                        logger.warning(f"PREM")
                        logger.warning(f"structured_10k METRICS:"+ str(structured_10k.key_metrics))
                    
                        logger.info(f"       Revenue: Not extracted (unusual table format)")
                    
                    total_years_stored += 1
                
                # Extract text for RAG
                logger.info("  • Extracting text for RAG...")
                text = downloader.extract_text(filing["file_path"])
                
                if text and all_years_data:
                    # Use most recent year's metadata (or first available)
                    most_recent = all_years_data[0]
                    
                    logger.info("  • Adding to RAG index...")
                    self.rag_engine.analyze_company(
                        ticker=ticker,
                        text=text,
                        metadata={
                            "company_name": most_recent.metadata.company_name,
                            "cik": most_recent.metadata.cik,
                            "fiscal_year": most_recent.metadata.fiscal_year_end.year,
                            "filing_date": str(most_recent.metadata.filing_date),
                            "revenue": most_recent.key_metrics.revenue,
                            "net_income": most_recent.key_metrics.net_income,
                            "total_assets": most_recent.key_metrics.total_assets
                        }
                    )
                
                logger.info(f"  ✅ Filing {i} processed successfully\n")
            
            logger.info("="*70)
            logger.info(f"✅ {ticker} ANALYSIS COMPLETE!")
            logger.info(f"   Total years stored: {total_years_stored}")
            logger.info("="*70 + "\n")
            
            try:
                langfuse_context.update_current_trace(
                    output={
                        "success": True,
                        "filings_processed": len(filings),
                        "years_stored": total_years_stored,
                        "ticker": ticker
                    }
                )
            except:
                pass
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Analysis failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            try:
                langfuse_context.update_current_trace(
                    output={
                        "success": False,
                        "error": str(e)
                    },
                    metadata={"status": "error"}
                )
            except:
                pass
            
            return False