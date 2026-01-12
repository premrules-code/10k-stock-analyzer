"""
Multi-Company Stock Analyzer with RAG and LangFuse Observability
"""

from llama_index.core import VectorStoreIndex, Settings, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
from llama_index.core.callbacks import CallbackManager
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.postgres import PGVectorStore
from langfuse.decorators import observe, langfuse_context
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class MultiCompanyStockAnalyzer:
    """
    RAG-based analyzer for multiple companies' 10-K filings
    Uses a single vector table with metadata filtering
    """
    
    def __init__(self):
        """Initialize the analyzer with vector store and LLM"""
        
        logger.info("\n" + "="*70)
        logger.info("🔧 INITIALIZING RAG ENGINE")
        logger.info("="*70 + "\n")
        
        # 1. Database connection
        logger.info("1️⃣  Connecting to vector database...")
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment")
        
        # Parse connection details
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        
        self.vector_store = PGVectorStore.from_params(
            database=parsed.path[1:],
            host=parsed.hostname,
            password=parsed.password,
            port=parsed.port or 5432,
            user=parsed.username,
            table_name="chunks_all_companies",
            embed_dim=1536,
        )
        
        logger.info("   ✅ Vector store connected")
        
        # 2. OpenAI setup
        logger.info("\n2️⃣  Setting up OpenAI...")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.embed_model = OpenAIEmbedding(
            model="text-embedding-3-small",
            api_key=openai_api_key,
            embed_batch_size=10  # Reduce batch size to avoid rate limits
        )
        
        self.llm = OpenAI(
            model="gpt-4",
            temperature=0.1,
            api_key=openai_api_key
        )
        
        logger.info("   ✅ OpenAI models initialized")
        
        # 3. LangFuse observability (optional)
        logger.info("\n3️⃣  Setting up LangFuse observability...")
        self.langfuse_handler = None
        
        try:
            langfuse_public = os.getenv("LANGFUSE_PUBLIC_KEY")
            langfuse_secret = os.getenv("LANGFUSE_SECRET_KEY")
            langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            
            if langfuse_public and langfuse_secret:
                # Try new import first
                try:
                    from langfuse.llama_index import LlamaIndexCallbackHandler
                    
                    self.langfuse_handler = LlamaIndexCallbackHandler(
                        public_key=langfuse_public,
                        secret_key=langfuse_secret,
                        host=langfuse_host
                    )
                    logger.info(f"   ✅ LangFuse enabled: {langfuse_host}")
                
                except ImportError:
                    logger.warning("   ⚠️  LangFuse LlamaIndex integration not available")
                    logger.info("   ℹ️  Install with: pip install langfuse")
            else:
                logger.info("   ℹ️  LangFuse disabled (no API keys)")
        
        except Exception as e:
            logger.warning(f"   ⚠️  LangFuse setup failed: {str(e)}")
            logger.info("   ℹ️  Continuing without observability...")
        
        # 4. Configure LlamaIndex Settings
        logger.info("\n4️⃣  Configuring LlamaIndex settings...")
        Settings.embed_model = self.embed_model
        Settings.llm = self.llm
        Settings.chunk_size = 512
        Settings.chunk_overlap = 50
        
        if self.langfuse_handler:
            Settings.callback_manager = CallbackManager([self.langfuse_handler])
            logger.info("   ✅ LangFuse callback registered")
        
        logger.info("   ✅ Settings configured")
        
        # 5. Load or create index
        logger.info("\n5️⃣  Loading vector index...")
        self.index = self.load_index()
        logger.info("   ✅ Index ready")
        
        logger.info("\n" + "="*70)
        logger.info("✅ RAG ENGINE READY")
        logger.info("="*70 + "\n")
    
    def load_index(self) -> VectorStoreIndex:
        """Load existing index from vector store or create new one"""
        
        try:
            storage_context = StorageContext.from_defaults(
                vector_store=self.vector_store
            )
            
            index = VectorStoreIndex.from_vector_store(
                vector_store=self.vector_store,
                storage_context=storage_context
            )
            
            logger.info("   ✅ Loaded existing index")
            return index
        
        except Exception as e:
            logger.info(f"   ℹ️  Creating new index")
            
            storage_context = StorageContext.from_defaults(
                vector_store=self.vector_store
            )
            
            index = VectorStoreIndex(
                nodes=[],
                storage_context=storage_context
            )
            
            return index
    
    @observe(name="rag_index_company")
    def analyze_company(
        self,
        ticker: str,
        text: str,
        metadata: Dict
    ) -> None:
        """
        Add company filing to RAG index
        
        Args:
            ticker: Stock ticker symbol
            text: Full filing text
            metadata: Company and filing metadata
        """
        
        langfuse_context.update_current_observation(
            metadata={
                "ticker": ticker,
                "text_length": len(text),
                "metadata_keys": list(metadata.keys())
            }
        )
        
        logger.info(f"\n📊 Adding {ticker} to RAG index...")
        
        # Ensure ticker is in metadata
        metadata["ticker"] = ticker
        
        # Convert all metadata values to strings (required for filtering)
        for key, value in metadata.items():
            if value is not None:
                metadata[key] = str(value)
        
        # Parse text into chunks
        parser = SentenceSplitter(
            chunk_size=512,
            chunk_overlap=50
        )
        
        document = Document(
            text=text,
            metadata=metadata
        )
        
        nodes = parser.get_nodes_from_documents([document])
        
        logger.info(f"   • Created {len(nodes)} text chunks")
        logger.info(f"   • Metadata: {list(metadata.keys())}")
        
        # Insert into index (embeddings tracked by LangFuse automatically)
        self.index.insert_nodes(nodes)
        
        logger.info(f"   ✅ {ticker} added to RAG index ({len(nodes)} chunks)\n")
        
        langfuse_context.update_current_observation(
            output={"num_chunks": len(nodes)},
            metadata={"success": True}
        )
    
    @observe(name="rag_vector_search")
    def ask(
        self,
        question: str,
        ticker: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> Dict:
        """
        Ask a question with vector search - automatically tracked by LangFuse
        
        Args:
            question: User question
            ticker: Filter by ticker (optional)
            fiscal_year: Filter by year (optional)
            temperature: LLM temperature
            max_tokens: Max response tokens
        
        Returns:
            Dictionary with answer, sources, and metadata
        """
        
        # Set metadata for observability
        langfuse_context.update_current_observation(
            metadata={
                "question_length": len(question),
                "ticker": ticker,
                "fiscal_year": fiscal_year,
                "temperature": temperature
            }
        )
        
        logger.info(f"\n🔍 RAG Query: '{question[:50]}...'")
        logger.info(f"   Filters: ticker={ticker}, year={fiscal_year}")
        
        # Build metadata filters
        metadata_filters = None
        filters_applied = {}
        
        if ticker or fiscal_year:
            filter_list = []
            
            if ticker:
                filter_list.append(ExactMatchFilter(key="ticker", value=ticker))
                filters_applied["ticker"] = ticker
            
            if fiscal_year:
                # Convert to string for filtering
                filter_list.append(ExactMatchFilter(key="fiscal_year", value=str(fiscal_year)))
                filters_applied["fiscal_year"] = fiscal_year
            
            metadata_filters = MetadataFilters(filters=filter_list)
            logger.info(f"   ✅ Applied filters: {filters_applied}")
        else:
            logger.info("   ℹ️  No filters applied (searching all documents)")
        
        try:
            # Update LLM temperature
            self.llm.temperature = temperature
            
            # Create query engine with filters
            query_engine = self.index.as_query_engine(
                similarity_top_k=5,
                filters=metadata_filters,
                response_mode="tree_summarize",
                verbose=True
            )
            
            # Execute query (embeddings and LLM calls tracked automatically)
            logger.info("   🤔 Executing query...")
            response = query_engine.query(question)
            
            # Extract sources
            sources = []
            if hasattr(response, 'source_nodes'):
                for i, node in enumerate(response.source_nodes):
                    metadata = node.metadata if hasattr(node, 'metadata') else {}
                    node_id = getattr(node, 'node_id', 'unknown')
                    chunk_num = node_id.split('-')[-1] if '-' in str(node_id) else 'N/A'
                    
                    sources.append({
                        "index": i + 1,
                        "text": node.text,  # Full text, not truncated
                        "score": float(node.score) if hasattr(node, 'score') else None,
                        "metadata": metadata,
                        "company_name": metadata.get('company_name', 'Unknown'),
                        "ticker": metadata.get('ticker', 'N/A'),
                        "fiscal_year": metadata.get('fiscal_year', 'N/A'),
                        "filing_date": metadata.get('filing_date', 'N/A'),
                        "accession_number": metadata.get('accession_number', ''),
                        "filing_url": metadata.get('filing_url', ''),
                        "chunk_id": chunk_num
                    })
                
                logger.info(f"   ✅ Found {len(sources)} relevant sources")
            
            result = {
                "answer": str(response),
                "sources": sources,
                "filters_applied": filters_applied,
                "num_sources": len(sources)
            }
            
            logger.info(f"   ✅ Query complete\n")
            
            # Update observation with results
            langfuse_context.update_current_observation(
                output={"num_sources": len(sources)},
                metadata={"success": True}
            )
            
            return result
        
        except Exception as e:
            logger.error(f"   ❌ RAG query failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Mark as error in LangFuse
            langfuse_context.update_current_observation(
                level="ERROR",
                output={"error": str(e)}
            )
            
            return {
                "answer": f"I encountered an error searching the documents: {str(e)}",
                "sources": [],
                "filters_applied": filters_applied,
                "error": str(e)
            }