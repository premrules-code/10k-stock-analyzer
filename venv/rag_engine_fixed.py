import sys
from pathlib import Path

# Ensure project root is on sys.path
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

# Import configuration
from src.config.openai import (
    OPENAI_MODEL,
    OPENAI_EMBEDDING_MODEL,
    OPENAI_TEMPERATURE,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)


class StockAnalyzer:
    """AI-powered 10-K analysis engine with Supabase and detailed citations"""
    
    def __init__(self):
        # Configure AI models
        Settings.llm = OpenAI(model=OPENAI_MODEL, temperature=OPENAI_TEMPERATURE)
        Settings.embed_model = OpenAIEmbedding(model=OPENAI_EMBEDDING_MODEL)
        Settings.chunk_size = CHUNK_SIZE
        Settings.chunk_overlap = CHUNK_OVERLAP
        
        # Setup LangFuse observability
        self._setup_observability()
        
        self.downloader = SECDownloader()
        self.database = Database()
        self.vector_store = None
        self.index = None
        self.query_engine = None
        self.current_ticker = None
    
    def _setup_observability(self):
        """Setup LangFuse for cost tracking"""
        # Skip if credentials not provided
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
    
    def connect_to_supabase(self):
        """Connect to Supabase Postgres database"""
        logger.info("🔌 Connecting to Supabase...")
        
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not found in .env")
        
        # Create PGVectorStore
        self.vector_store = PGVectorStore.from_params(
            database=os.getenv("SUPABASE_DB", "postgres"),
            host=os.getenv("SUPABASE_HOST"),
            password=os.getenv("SUPABASE_PASSWORD"),
            port=int(os.getenv("SUPABASE_PORT", 5432)),
            user=os.getenv("SUPABASE_USER", "postgres"),
            table_name="document_chunks",
            embed_dim=1536
        )
        
        logger.info("✅ Connected to Supabase!")
        return self.vector_store
    
    def load_company_index(self, ticker: str):
        """
        Load an existing company's index from Supabase with PROPER FILTERING
        """
        logger.info(f"📂 Loading index for {ticker}...")
        
        try:
            # Ensure vector store is connected
            if not self.vector_store:
                self.connect_to_supabase()
            
            # Get company metadata from database
            with self.database.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT id FROM companies WHERE ticker = :ticker"),
                    {"ticker": ticker}
                )
                company_data = result.fetchone()
                
                if not company_data:
                    logger.error(f"❌ Company {ticker} not found in database")
                    return False
            
            # Create storage context with filtered vector store
            storage_context = StorageContext.from_defaults(
                vector_store=self.vector_store
            )
            
            # Load index from vector store
            self.index = VectorStoreIndex.from_vector_store(
                self.vector_store,
                storage_context=storage_context
            )
            
            # Create a FILTERED query engine that only searches this ticker's documents
            self._create_query_engine(filter_ticker=ticker)
            
            self.current_ticker = ticker
            logger.info(f"✅ Loaded {ticker} index successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load {ticker}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_query_engine(self, filter_ticker=None):
        """Create query engine with detailed citation prompt and optional filtering"""
        from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
        
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
        
        # Build query engine args
        query_engine_args = {
            "similarity_top_k": 5,
            "response_mode": "compact",
            "text_qa_template": citation_qa_template
        }
        
        # Add metadata filter if ticker specified
        if filter_ticker:
            filters = MetadataFilters(
                filters=[
                    ExactMatchFilter(key="ticker", value=filter_ticker)
                ]
            )
            query_engine_args["filters"] = filters
            logger.info(f"🔍 Query engine filtered to ticker: {filter_ticker}")
        
        self.query_engine = self.index.as_query_engine(**query_engine_args)
        
        logger.info("✅ Query engine created with citation support")
    
    def analyze_company(self, ticker: str, num_filings: int = 1):
        """Download and analyze a company's 10-K with detailed citation support"""
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
            
            # Create document with enriched metadata for citations
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
        
        # Step 4: Connect to Supabase
        if not self.vector_store:
            self.connect_to_supabase()
        
        # Step 5: Build vector index
        logger.info("🔨 Building vector index and storing in Supabase...")
        storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        self.index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True
        )
        
        # Step 6: Create query engine
        self._create_query_engine(filter_ticker=ticker)
        
        self.current_ticker = ticker
        logger.info(f"✅ {ticker} ready for questions with citation support!")
        return True
    
    def ask(self, question: str):
        """Ask a question about the 10-K and get a cited answer"""
        if not self.query_engine:
            logger.error("❌ No company loaded! Please select or analyze a company first.")
            return None
        
        logger.info(f"\n💬 Q: {question}")
        response = self.query_engine.query(question)
        
        answer = str(response)
        
        # Extract detailed source information with text previews
        sources = []
        for i, node in enumerate(response.source_nodes, 1):
            # Get the actual text from this source
            source_text = node.text if hasattr(node, 'text') else node.node.text
            
            source_info = {
                "source_number": i,
                "ticker": node.metadata.get("ticker", "Unknown"),
                "fiscal_year": node.metadata.get("fiscal_year", "Unknown"),
                "filing_type": node.metadata.get("filing_type", "10-K"),
                "accession": node.metadata.get("accession", "N/A"),
                "relevance_score": round(node.score, 3) if hasattr(node, 'score') else None,
                "text_excerpt": source_text[:300] + "..." if len(source_text) > 300 else source_text,
                "full_text": source_text  # For detailed display
            }
            sources.append(source_info)
        
        # Count citations in answer
        citations_found = re.findall(r'\[Source \d+\]', answer)
        
        logger.info(f"📝 A: {answer[:200]}...")
        logger.info(f"📚 Sources: {len(sources)} | Citations in answer: {len(citations_found)}")
        
        return {
            "answer": answer,
            "sources": sources,
            "num_sources": len(sources),
            "num_citations": len(citations_found),
            "has_proper_citations": len(citations_found) > 0
        }
    
    def get_analyzed_companies(self):
        """Get list of companies stored in database"""
        return self.database.get_companies()


# Test the system
if __name__ == "__main__":
    analyzer = StockAnalyzer()
    
    # Test connection
    analyzer.connect_to_supabase()
    
    # Analyze Apple (if not already done)
    print("\n" + "="*70)
    print("Would you like to analyze a company? (y/n)")
    if input().lower() == 'y':
        ticker = input("Enter ticker symbol (e.g., AAPL): ").upper()
        success = analyzer.analyze_company(ticker)
        
        if not success:
            print("❌ Analysis failed")
            exit(1)
    
    # Test questions with citations
    print("\n" + "="*70)
    print("🧪 TESTING CITATION QUALITY")
    print("="*70)
    
    questions = [
        "What were Apple's total revenues in the most recent fiscal year?",
        "What are Apple's main business risks?",
        "How much did Apple spend on research and development?"
    ]
    
    for q in questions:
        print(f"\n{'='*70}")
        print(f"Q: {q}")
        print('='*70)
        
        result = analyzer.ask(q)
        
        if result:
            print(f"\n📝 ANSWER:\n{result['answer']}\n")
            
            print(f"📊 CITATION ANALYSIS:")
            print(f"   Citations found: {result['num_citations']}")
            print(f"   Sources used: {result['num_sources']}")
            print(f"   Properly cited: {'✅ Yes' if result['has_proper_citations'] else '❌ No'}")
            
            print(f"\n📚 SOURCE DETAILS:")
            for source in result['sources']:
                print(f"\n   [Source {source['source_number']}] "
                      f"{source['ticker']} {source['filing_type']} "
                      f"FY{source['fiscal_year']}")
                print(f"   Relevance: {source['relevance_score']}")
                print(f"   Excerpt: {source['text_excerpt'][:150]}...")
        
        print("\n" + "-"*70)
