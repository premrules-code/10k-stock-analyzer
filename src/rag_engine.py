""
ALTERNATIVE SOLUTION: Separate vector stores per ticker

Instead of one big vector store with metadata filtering,
create separate tables for each company.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from llama_index.core import (
    VectorStoreIndex, 
    Document, 
    Settings, 
    StorageContext,
    PromptTemplate
)
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.callbacks import CallbackManager

from src.downloader import SECDownloader
from src.database import Database
from dotenv import load_dotenv
import os
import logging
from sqlalchemy import create_engine, text
import re

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.config.openai import (
    OPENAI_MODEL,
    OPENAI_EMBEDDING_MODEL,
    OPENAI_TEMPERATURE,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)


class StockAnalyzer:
    """AI-powered 10-K analysis engine with SEPARATE vector stores per company"""
    
    def __init__(self):
        # Configure AI models
        Settings.llm = OpenAI(model=OPENAI_MODEL, temperature=OPENAI_TEMPERATURE)
        Settings.embed_model = OpenAIEmbedding(model=OPENAI_EMBEDDING_MODEL)
        Settings.chunk_size = CHUNK_SIZE
        Settings.chunk_overlap = CHUNK_OVERLAP
        
        self._setup_observability()
        
        self.downloader = SECDownloader()
        self.database = Database()
        self.vector_stores = {}  # Cache of vector stores by ticker
        self.index = None
        self.query_engine = None
        self.current_ticker = None
        
        # Database connection params
        self.db_params = {
            "database": os.getenv("SUPABASE_DB", "postgres"),
            "host": os.getenv("SUPABASE_HOST"),
            "password": os.getenv("SUPABASE_PASSWORD"),
            "port": int(os.getenv("SUPABASE_PORT", 5432)),
            "user": os.getenv("SUPABASE_USER", "postgres"),
        }
    
    def _setup_observability(self):
        """Setup LangFuse for cost tracking"""
        if not all([
            os.getenv("LANGFUSE_PUBLIC_KEY"),
            os.getenv("LANGFUSE_SECRET_KEY"),
            os.getenv("LANGFUSE_HOST")
        ]):
            logger.info("ℹ️ LangFuse not configured, skipping observability")
            return
        
        try:
            from llama_index.core.callbacks.langfuse import LangfuseCallbackHandler
            
            langfuse_handler = LangfuseCallbackHandler(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                host=os.getenv("LANGFUSE_HOST")
            )
            Settings.callback_manager = CallbackManager([langfuse_handler])
            logger.info("🔍 LangFuse observability enabled")
        except ImportError:
            logger.warning("⚠️ LangFuse package not available")
        except Exception as e:
            logger.warning(f"⚠️ LangFuse setup failed: {e}")
    
    def _get_vector_store_for_ticker(self, ticker: str):
        """Get or create a vector store for a specific ticker"""
        # Use ticker-specific table name
        table_name = f"chunks_{ticker.lower()}"
        
        if ticker not in self.vector_stores:
            logger.info(f"🔌 Creating vector store for {ticker} (table: {table_name})")
            
            self.vector_stores[ticker] = PGVectorStore.from_params(
                **self.db_params,
                table_name=table_name,
                embed_dim=1536
            )
        
        return self.vector_stores[ticker]
    
    def load_company_index(self, ticker: str):
        """
        Load an existing company's index from its dedicated vector store
        """
        logger.info(f"📂 Loading index for {ticker}...")
        
        try:
            # Get company-specific vector store
            vector_store = self._get_vector_store_for_ticker(ticker)
            
            # Verify company exists in database
            with self.database.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT id FROM companies WHERE ticker = :ticker"),
                    {"ticker": ticker}
                )
                company_data = result.fetchone()
                
                if not company_data:
                    logger.error(f"❌ Company {ticker} not found in database")
                    return False
            
            # Create storage context with ticker-specific vector store
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store
            )
            
            # Load index from vector store
            self.index = VectorStoreIndex.from_vector_store(
                vector_store,
                storage_context=storage_context
            )
            
            # Create query engine (no filtering needed - table only has this ticker's data)
            self._create_query_engine()
            
            self.current_ticker = ticker
            logger.info(f"✅ Loaded {ticker} index successfully from dedicated table!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load {ticker}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_query_engine(self):
        """Create query engine with detailed citation prompt"""
        citation_qa_template = PromptTemplate(
            "You are a financial analyst examining SEC 10-K filings. "
            "You must provide detailed, well-cited answers.\n\n"
            
            "CONTEXT INFORMATION:\n"
            "Below are relevant excerpts from the 10-K filing. "
            "Each excerpt is numbered as [Source X].\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n\n"
            
            "CITATION REQUIREMENTS (CRITICAL - YOU MUST FOLLOW THESE):\n"
            "1. EVERY factual claim, number, or statement MUST include a citation\n"
            "2. Use the format [Source X] immediately after each fact\n"
            "3. If combining information from multiple sources, cite all: [Source 1, Source 2]\n"
            "4. Direct quotes MUST be in quotation marks with citation: \"exact text\" [Source X]\n"
            "5. NEVER make claims without citing the source\n"
            "6. If information is not in the context, explicitly state: "
            "'This information is not available in the provided 10-K filing.'\n\n"
            
            "ANSWER QUALITY REQUIREMENTS:\n"
            "- Be specific: include exact numbers, percentages, and dates\n"
            "- Be comprehensive: address all parts of the question\n"
            "- Be accurate: only use information from the provided context\n"
            "- Be clear: write in complete sentences with proper structure\n\n"
            
            "EXAMPLE FORMAT:\n"
            "Apple's total net sales were $383.3 billion for fiscal year 2023 [Source 1], "
            "representing a 3% decrease from $394.3 billion in fiscal 2022 [Source 2]. "
            "The decline was primarily attributed to lower iPhone sales in international markets "
            "[Source 1].\n\n"
            
            "Question: {query_str}\n\n"
            
            "Provide a detailed, well-structured answer with complete citations:"
        )
        
        self.query_engine = self.index.as_query_engine(
            similarity_top_k=5,
            response_mode="compact",
            text_qa_template=citation_qa_template
        )
        
        logger.info("✅ Query engine created with citation support")
    
    def analyze_company(self, ticker: str, num_filings: int = 1):
        """Download and analyze a company's 10-K with dedicated vector store"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 ANALYZING {ticker}")
        logger.info('='*60)
        
        # Step 1: Download 10-K
        filings = self.downloader.download_10k(ticker, num_filings=num_filings)
        if not filings:
            logger.error(f"❌ No filings found for {ticker}")
            return False
        
        # Step 2: Store company info
        company_id = self.database.add_company(ticker)
        
        # Step 3: Process each filing
        documents = []
        for filing in filings:
            filing_id = self.database.add_filing(company_id, filing)
            
            text = self.downloader.extract_text(filing["file_path"])
            if not text:
                continue
            
            # Create document with enriched metadata
            doc = Document(
                text=text,
                metadata={
                    "ticker": ticker,
                    "filing_id": filing_id,
                    "fiscal_year": filing["fiscal_year"],
                    "accession": filing["accession"],
                    "filing_type": "10-K",
                    "source": f"{ticker} 10-K FY{filing['fiscal_year']}"
                }
            )
            documents.append(doc)
        
        if not documents:
            logger.error("❌ No documents to process")
            return False
        
        # Step 4: Get ticker-specific vector store
        vector_store = self._get_vector_store_for_ticker(ticker)
        
        # Step 5: Build vector index in ticker-specific table
        logger.info(f"🔨 Building vector index for {ticker} in dedicated table...")
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        self.index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True
        )
        
        # Step 6: Create query engine
        self._create_query_engine()
        
        self.current_ticker = ticker
        logger.info(f"✅ {ticker} ready for questions with citation support!")
        return True
    
    def ask(self, question: str):
        """Ask a question about the 10-K and get a cited answer"""
        if not self.query_engine:
            logger.error("❌ No company loaded! Please select or analyze a company first.")
            return None
        
        logger.info(f"\n💬 Q: {question}")
        logger.info(f"🎯 Querying {self.current_ticker}'s dedicated vector store")
        
        response = self.query_engine.query(question)
        
        answer = str(response)
        
        # Extract detailed source information
        sources = []
        for i, node in enumerate(response.source_nodes, 1):
            source_text = node.text if hasattr(node, 'text') else node.node.text
            
            source_info = {
                "source_number": i,
                "ticker": node.metadata.get("ticker", "Unknown"),
                "fiscal_year": node.metadata.get("fiscal_year", "Unknown"),
                "filing_type": node.metadata.get("filing_type", "10-K"),
                "accession": node.metadata.get("accession", "N/A"),
                "relevance_score": round(node.score, 3) if hasattr(node, 'score') else None,
                "text_excerpt": source_text[:300] + "..." if len(source_text) > 300 else source_text,
                "full_text": source_text
            }
            sources.append(source_info)
        
        # Count citations
        citations_found = re.findall(r'\[Source \d+\]', answer)
        
        logger.info(f"📝 A: {answer[:200]}...")
        logger.info(f"📚 Sources: {len(sources)} | Citations: {len(citations_found)}")
        
        return {
            "answer": answer,
            "sources": sources,
            "num_sources": len(sources),
            "num_citations": len(citations_found),
            "has_proper_citations": len(citations_found) > 0
        }
    
    def get_analyzed_companies(self):
        """Get list of companies stored in database"""
        return self.database.get_analyzed_companies()


if __name__ == "__main__":
    analyzer = StockAnalyzer()
    
    print("\n" + "="*70)
    print("🧪 TESTING SEPARATE VECTOR STORES")
    print("="*70)
    
    # Test analyzing a company
    print("\nAnalyze a company? (y/n)")
    if input().lower() == 'y':
        ticker = input("Enter ticker: ").upper()
        success = analyzer.analyze_company(ticker)
        
        if success:
            # Test questions
            while True:
                q = input("\nAsk a question (or 'quit'): ")
                if q.lower() == 'quit':
                    break
                
                result = analyzer.ask(q)
                if result:
                    print(f"\n{result['answer']}\n")
                    print(f"Citations: {result['num_citations']}, Sources: {result['num_sources']}")
