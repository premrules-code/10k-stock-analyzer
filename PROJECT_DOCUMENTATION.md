# 📊 10-K Stock Analyzer - Complete Project Documentation

## 🎯 Project Overview

**What it does:**
A Streamlit web application that downloads and analyzes SEC 10-K filings (annual reports) using AI. Users can ask questions about any public company and get cited answers extracted from their official filings.

**Key Innovation:**
Uses separate vector databases per company to prevent data contamination, ensuring Apple's data never mixes with Nvidia's data.

**Tech Stack:**
- **Frontend:** Streamlit (Python web framework)
- **AI/LLM:** OpenAI GPT-4 via LlamaIndex
- **Vector Database:** Supabase PostgreSQL with pgvector
- **Data Source:** SEC EDGAR API
- **Deployment:** Railway (Docker container)

---

## 🏗️ Architecture Overview

```
User Interface (Streamlit)
         ↓
    app.py (UI Logic)
         ↓
    rag_engine.py (Core AI Engine)
         ↓
    ┌─────────────┬──────────────┬────────────────┐
    ↓             ↓              ↓                ↓
SEC EDGAR    Supabase        OpenAI          Database
(10-K Files)  (Vectors)      (LLM/Embeddings) (Metadata)
```

---

## 📁 Project Structure

```
10k-stock-analyzer/
│
├── src/
│   ├── app.py              ⭐ Streamlit UI (main entry point)
│   ├── rag_engine.py       ⭐ Core AI engine (RAG implementation)
│   ├── database.py         📊 Database operations
│   ├── downloader.py       📥 SEC filing downloader
│   └── config/
│       └── openai.py       ⚙️ Configuration constants
│
├── .streamlit/
│   └── config.toml         🔧 Streamlit server config
│
├── Dockerfile              🐳 Container definition
├── railway.json            🚂 Railway deployment config
├── requirements.txt        📦 Python dependencies
└── .env                    🔐 Environment variables (local only)
```

---

## 🔍 DETAILED FILE BREAKDOWN

---

## ⭐ 1. app.py - Streamlit User Interface

### Purpose:
The main entry point that users interact with. Handles all UI logic, user input, and displays results.

### Key Components:

#### A. Initialization (Lines 1-50)
```python
import streamlit as st
from src.rag_engine import StockAnalyzer

# Page configuration
st.set_page_config(
    page_title="10-K Stock Analyzer",
    page_icon="📊",
    layout="wide"
)

# Session State Management
if "analyzer" not in st.session_state:
    st.session_state.analyzer = StockAnalyzer()
    st.session_state.current_ticker = None

analyzer = st.session_state.analyzer
```

**What this does:**
- Imports Streamlit and the AI engine
- Sets up page layout and title
- Creates ONE analyzer instance per user session (not cached globally)
- Tracks which company is currently loaded

**Why session state matters:**
- Prevents recreating the analyzer on every button click
- Maintains state when user switches between companies
- Stores current ticker so we know which company is loaded

---

#### B. Sidebar - Company Selection (Lines 51-150)

```python
with st.sidebar:
    st.header("🏢 Company Analysis")
    
    # Show analyzed companies
    companies = analyzer.get_analyzed_companies()
    if companies:
        st.success(f"✅ {len(companies)} companies analyzed")
        
        # Dropdown to select company
        selected = st.selectbox(
            "Query Company",
            options=[c["ticker"] for c in companies]
        )
        
        # Load the selected company's index
        if selected and selected != st.session_state.current_ticker:
            with st.spinner(f"Loading {selected} index..."):
                success = analyzer.load_company_index(selected)
                if success:
                    st.session_state.current_ticker = selected
                    st.success(f"✅ Loaded {selected}")
```

**Flow:**
1. Get list of companies from database
2. Display in dropdown
3. When user selects a company:
   - Check if it's different from currently loaded one
   - Call `load_company_index()` to load that company's vectors
   - Update session state
   - Show success message

**Critical:** This is where we switch between companies! Each selection loads a different vector table (`chunks_aapl`, `chunks_nvda`, etc.)

---

#### C. Sidebar - Add New Company (Lines 151-200)

```python
st.subheader("➕ Analyze New Company")
new_ticker = st.text_input("Ticker Symbol", placeholder="AAPL").upper()
num_filings = st.slider("Number of filings", 1, 3, 1)

if st.button("📥 Download & Analyze"):
    if new_ticker:
        with st.spinner(f"Analyzing {new_ticker}... (2-3 minutes)"):
            success = analyzer.analyze_company(new_ticker, num_filings)
            if success:
                st.session_state.current_ticker = new_ticker
                st.success(f"✅ {new_ticker} analyzed!")
                st.balloons()
                st.rerun()
```

**Flow:**
1. User enters ticker (e.g., "AAPL")
2. Clicks "Download & Analyze"
3. Shows spinner (this takes 2-3 minutes)
4. Calls `analyze_company()` which:
   - Downloads 10-K from SEC
   - Processes into chunks
   - Creates embeddings
   - Stores in `chunks_aapl` table
5. Updates session state
6. Refreshes page to show new company

**Why `st.rerun()`:** Forces page refresh so dropdown shows the new company

---

#### D. Main Content - Question Input (Lines 201-300)

```python
if st.session_state.current_ticker:
    ticker = st.session_state.current_ticker
    
    st.header(f"💬 Ask Questions About {ticker}")
    
    # Check if query engine is ready
    if not analyzer.query_engine:
        st.error("⚠️ Query engine not ready. Please reselect company.")
    else:
        question = st.text_area(
            "Your Question",
            placeholder=f"What were {ticker}'s revenues last year?",
            height=100
        )
        
        ask_button = st.button("🔍 Ask Question")
        
        if ask_button and question:
            with st.spinner("🤔 Analyzing 10-K filing..."):
                result = analyzer.ask(question)
```

**Flow:**
1. Check if a company is loaded
2. Validate query engine exists
3. Show text area for question
4. When user clicks "Ask Question":
   - Show spinner
   - Call `analyzer.ask(question)`
   - Wait for AI response

**Validation:** Ensures we don't try to query before company is loaded

---

#### E. Display Results (Lines 301-400)

```python
if result:
    # Display answer with highlighted citations
    st.markdown("### 📝 Answer")
    
    answer_text = result["answer"]
    
    # Highlight citations
    def highlight_citations(text):
        pattern = r'\[Source (\d+)\]'
        highlighted = re.sub(
            pattern,
            r'<span class="citation">[Source \1]</span>',
            text
        )
        return highlighted
    
    highlighted_answer = highlight_citations(answer_text)
    st.markdown(highlighted_answer, unsafe_allow_html=True)
    
    # Citation metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"**Citations:** {result['num_citations']}")
    
    with col2:
        st.markdown(f"**Sources Used:** {result['num_sources']}")
    
    with col3:
        quality = "✅ Well-Cited" if result["has_proper_citations"] else "⚠️ No Citations"
        st.markdown(f"**Quality:** {quality}")
    
    with col4:
        # Verify all sources are from correct ticker
        correct_ticker = all(s['ticker'] == ticker for s in result['sources'])
        ticker_status = "✅ Verified" if correct_ticker else "⚠️ Mixed"
        st.markdown(f"**Ticker:** {ticker_status}")
```

**Flow:**
1. Get answer from result dictionary
2. Highlight `[Source X]` tags with CSS styling
3. Display answer with pretty formatting
4. Show metrics in 4 columns:
   - Number of citations
   - Number of sources used
   - Citation quality (are there citations?)
   - Ticker verification (all from correct company?)

**Critical Check:** The ticker verification ensures no data mixing!

---

#### F. Source Details Display (Lines 401-500)

```python
# Display detailed sources
if result["sources"]:
    st.markdown("### 📚 Source Details")
    
    for source in result["sources"]:
        ticker_emoji = "✅" if source['ticker'] == ticker else "⚠️"
        
        with st.expander(
            f"{ticker_emoji} Source {source['source_number']}: "
            f"{source['ticker']} {source['filing_type']} - "
            f"FY{source['fiscal_year']} "
            f"(Relevance: {source['relevance_score']})",
            expanded=False
        ):
            # Show metadata
            st.markdown(f"**Company:** {source['ticker']}")
            st.markdown(f"**Filing Type:** {source['filing_type']}")
            st.markdown(f"**Fiscal Year:** {source['fiscal_year']}")
            st.markdown(f"**Relevance Score:** {source['relevance_score']}")
            
            # Show text excerpt
            st.text_area(
                "Source Text",
                value=source['text_excerpt'],
                height=150
            )
```

**Flow:**
1. Loop through each source returned by the query
2. Create expandable section for each
3. Show metadata (company, year, relevance)
4. Show actual text that was used
5. Add ✅ or ⚠️ emoji to show if source is from correct ticker

**User Benefit:** Users can verify the AI's citations are accurate

---

### Complete app.py Flow:

```
User visits app
    ↓
Session state initialized (creates analyzer)
    ↓
Sidebar: Shows companies dropdown
    ↓
User selects AAPL → load_company_index("AAPL")
    ↓
Main area: Shows question input
    ↓
User types: "What were revenues?"
    ↓
User clicks "Ask Question" → analyzer.ask(question)
    ↓
Display answer with citations
    ↓
Show source details for verification
```

---

## ⭐ 2. rag_engine.py - Core AI Engine

### Purpose:
The brain of the application. Handles downloading 10-K files, processing them, creating vector embeddings, and answering questions using RAG (Retrieval-Augmented Generation).

---

### Key Components:

#### A. Class Initialization (Lines 1-100)

```python
class StockAnalyzer:
    """AI-powered 10-K analysis engine with SEPARATE vector stores per company"""
    
    def __init__(self):
        # Configure AI models
        Settings.llm = OpenAI(model="gpt-4-turbo-preview", temperature=0.1)
        Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
        Settings.chunk_size = 1024
        Settings.chunk_overlap = 200
        
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
```

**What this sets up:**
- **LLM:** GPT-4 for answering questions (temperature=0.1 for consistency)
- **Embeddings:** OpenAI text-embedding-3-small for vector creation
- **Chunking:** Splits documents into 1024-char chunks with 200-char overlap
- **Components:**
  - `downloader`: Gets 10-K files from SEC
  - `database`: Manages PostgreSQL operations
  - `vector_stores`: Cache to avoid recreating connections
  - `index`: LlamaIndex vector index
  - `query_engine`: The actual Q&A engine
- **Database params:** Supabase connection details

**Why chunk overlap?** Ensures important context isn't lost at chunk boundaries

---

#### B. Vector Store Creation (Lines 101-150)

```python
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
```

**Critical Innovation:** Each company gets its own table!

**Flow:**
1. Ticker comes in (e.g., "AAPL")
2. Create table name: `chunks_aapl`
3. Check if we already have a connection to this table
4. If not, create new PGVectorStore connection
5. Cache it in `self.vector_stores` dictionary
6. Return the vector store

**Result:**
- `chunks_aapl` → Apple's vectors
- `chunks_nvda` → Nvidia's vectors
- **No mixing possible!**

**Why cache?** Avoid creating multiple connections to same table

---

#### C. Analyze Company - Main Processing (Lines 151-300)

```python
def analyze_company(self, ticker: str, num_filings: int = 1):
    """Download and analyze a company's 10-K with dedicated vector store"""
    
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
    
    # Step 4: Get ticker-specific vector store
    vector_store = self._get_vector_store_for_ticker(ticker)
    
    # Step 5: Build vector index in ticker-specific table
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    self.index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True
    )
    
    # Step 6: Create query engine
    self._create_query_engine()
    
    self.current_ticker = ticker
    return True
```

**Detailed Flow:**

**Step 1: Download (30 seconds)**
```python
filings = self.downloader.download_10k(ticker, num_filings=1)
# Downloads from SEC EDGAR API
# Result: [{file_path: "data/AAPL/0000320193-23-000077.htm", ...}]
```

**Step 2: Store Metadata (1 second)**
```python
company_id = self.database.add_company(ticker)
# Inserts into companies table:
# id | ticker | company_name
# 1  | AAPL   | Apple Inc.
```

**Step 3: Process Text (10 seconds)**
```python
for filing in filings:
    # Store filing record
    filing_id = self.database.add_filing(company_id, filing)
    # Inserts into filings table:
    # id | company_id | fiscal_year | file_path
    # 1  | 1          | 2023        | data/AAPL/...
    
    # Extract text from HTML
    text = self.downloader.extract_text(filing["file_path"])
    # Removes HTML tags, cleans formatting
    # Result: ~500KB of plain text
    
    # Create Document with metadata
    doc = Document(
        text=text,
        metadata={
            "ticker": "AAPL",
            "fiscal_year": 2023,
            ...
        }
    )
```

**Step 4: Get Vector Store (1 second)**
```python
vector_store = self._get_vector_store_for_ticker("AAPL")
# Creates/gets connection to chunks_aapl table
```

**Step 5: Build Index (90 seconds - the slow part!)**
```python
self.index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context,
    show_progress=True
)
```

**What happens internally:**
1. Split 500KB text into chunks (1024 chars each)
   - Result: ~500 chunks
2. For each chunk, call OpenAI embeddings API
   - Creates 1536-dimension vector per chunk
   - 500 chunks × 100ms = 50 seconds
3. Store in `chunks_aapl` table:
   ```sql
   INSERT INTO chunks_aapl (id, embedding, metadata, text)
   VALUES (1, [0.123, -0.456, ...], {...}, 'chunk text')
   ```
4. Create vector index for fast similarity search

**Step 6: Create Query Engine (1 second)**
```python
self._create_query_engine()
# Sets up the Q&A system
```

**Total time: ~2-3 minutes**

---

#### D. Load Company Index (Lines 301-350)

```python
def load_company_index(self, ticker: str):
    """Load an existing company's index from its dedicated vector store"""
    
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
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # Load index from vector store
    self.index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context
    )
    
    # Create query engine
    self._create_query_engine()
    
    self.current_ticker = ticker
    return True
```

**Flow:**
1. Get vector store connection for ticker's table
2. Verify company exists in database
3. Load existing vectors from `chunks_aapl` table
4. Create index from loaded vectors (no embedding needed!)
5. Create query engine
6. Ready to answer questions!

**Fast:** Only takes ~2-3 seconds because vectors already exist!

**Difference from analyze_company:**
- `analyze_company`: Download → Process → Embed → Store (2-3 minutes)
- `load_company_index`: Load existing → Ready (2-3 seconds)

---

#### E. Create Query Engine (Lines 351-450)

```python
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
        
        "Question: {query_str}\n\n"
        
        "Provide a detailed, well-structured answer with complete citations:"
    )
    
    self.query_engine = self.index.as_query_engine(
        similarity_top_k=5,
        response_mode="compact",
        text_qa_template=citation_qa_template
    )
```

**What this creates:**
- A query engine that searches vectors and generates answers
- Custom prompt template that enforces citations
- Configuration:
  - `similarity_top_k=5`: Return 5 most relevant chunks
  - `response_mode="compact"`: Concise answers
  - `text_qa_template`: Custom prompt with citation rules

**The prompt is critical:** It trains GPT-4 to always cite sources!

---

#### F. Ask Question (Lines 451-550)

```python
def ask(self, question: str):
    """Ask a question about the 10-K and get a cited answer"""
    
    if not self.query_engine:
        logger.error("❌ No company loaded!")
        return None
    
    logger.info(f"💬 Q: {question}")
    logger.info(f"🎯 Querying {self.current_ticker}'s dedicated vector store")
    
    # Query the index
    response = self.query_engine.query(question)
    
    answer = str(response)
    
    # Extract detailed source information
    sources = []
    for i, node in enumerate(response.source_nodes, 1):
        source_text = node.text if hasattr(node, 'text') else node.node.text
        
        source_info = {
            "source_number": i,
            "ticker": node.metadata.get("ticker", self.current_ticker),
            "fiscal_year": node.metadata.get("fiscal_year", "Unknown"),
            "filing_type": node.metadata.get("filing_type", "10-K"),
            "accession": node.metadata.get("accession", "N/A"),
            "relevance_score": round(node.score, 3),
            "text_excerpt": source_text[:300] + "...",
            "full_text": source_text
        }
        sources.append(source_info)
    
    # Count citations
    citations_found = re.findall(r'\[Source \d+\]', answer)
    
    # Verify all sources are from correct ticker
    mismatched_sources = [s for s in sources if s['ticker'] != self.current_ticker]
    if mismatched_sources:
        logger.warning(f"⚠️ Found {len(mismatched_sources)} sources from other companies!")
    else:
        logger.info(f"✅ All sources verified from {self.current_ticker}")
    
    return {
        "answer": answer,
        "sources": sources,
        "num_sources": len(sources),
        "num_citations": len(citations_found),
        "has_proper_citations": len(citations_found) > 0
    }
```

**Detailed Flow:**

**1. Validation**
```python
if not self.query_engine:
    return None
# Ensures company is loaded before querying
```

**2. Query Execution**
```python
response = self.query_engine.query(question)
```

**What happens internally:**
1. **Embedding Creation:**
   ```python
   question_embedding = embed_model.embed("What were revenues?")
   # Creates 1536-dimension vector for the question
   ```

2. **Vector Search:**
   ```sql
   SELECT id, text, metadata, embedding <=> question_embedding AS distance
   FROM chunks_aapl
   ORDER BY distance
   LIMIT 5;
   ```
   - Finds 5 most similar chunks using cosine similarity
   - Returns: 5 chunks with highest relevance scores

3. **Context Building:**
   ```python
   context = """
   [Source 1]: "Apple's net sales were $383.3 billion..."
   [Source 2]: "Revenue decreased 3% compared to..."
   [Source 3]: "iPhone sales contributed $200.6 billion..."
   [Source 4]: "Services revenue increased to $85.2 billion..."
   [Source 5]: "Geographic breakdown shows Americas at..."
   """
   ```

4. **LLM Call:**
   ```python
   prompt = f"""
   You are a financial analyst...
   
   CONTEXT:
   {context}
   
   Question: {question}
   
   Provide answer with citations:
   """
   
   answer = gpt4.complete(prompt)
   ```

5. **Response:**
   ```
   "Apple's total net sales were $383.3 billion in fiscal 2023 [Source 1], 
   representing a 3% decrease from $394.3 billion in 2022 [Source 2]. 
   iPhone contributed $200.6 billion [Source 3], while Services grew to 
   $85.2 billion [Source 4]."
   ```

**3. Source Extraction**
```python
for i, node in enumerate(response.source_nodes, 1):
    source_info = {
        "source_number": i,
        "ticker": node.metadata.get("ticker"),
        "relevance_score": node.score,
        "text_excerpt": node.text[:300]
    }
```

Extracts metadata from each source chunk that was used.

**4. Citation Counting**
```python
citations_found = re.findall(r'\[Source \d+\]', answer)
# Counts how many [Source X] tags are in the answer
```

**5. Verification**
```python
mismatched_sources = [s for s in sources if s['ticker'] != self.current_ticker]
# Ensures all sources are from the correct company!
```

**6. Return Result**
```python
return {
    "answer": "Apple's revenues were...",
    "sources": [{...}, {...}, ...],
    "num_citations": 4,
    "has_proper_citations": True
}
```

---

### Complete rag_engine.py Flow:

```
analyze_company("AAPL")
    ↓
Download 10-K from SEC (30s)
    ↓
Extract text from HTML (10s)
    ↓
Split into 500 chunks of 1024 chars
    ↓
Create embeddings for each chunk (90s)
    ↓
Store in chunks_aapl table
    ↓
Build vector index
    ↓
Create query engine
    ↓
Ready for questions!

---

load_company_index("AAPL")
    ↓
Connect to chunks_aapl table (2s)
    ↓
Load existing vectors
    ↓
Create query engine
    ↓
Ready for questions!

---

ask("What were revenues?")
    ↓
Embed question → [0.123, -0.456, ...]
    ↓
Search chunks_aapl for similar vectors
    ↓
Return top 5 most relevant chunks
    ↓
Build context from chunks
    ↓
Send to GPT-4 with citation prompt
    ↓
Get answer with [Source X] tags
    ↓
Extract source metadata
    ↓
Verify all from correct ticker
    ↓
Return to UI for display
```

---

## 🔄 COMPLETE END-TO-END FLOW

### Scenario: User Analyzes Apple and Asks Question

```
1. User visits app
   └─ Streamlit loads
   └─ app.py initializes
   └─ Creates StockAnalyzer instance
   └─ Session state: {analyzer: StockAnalyzer(), current_ticker: None}

2. User enters "AAPL" and clicks "Download & Analyze"
   └─ app.py: calls analyzer.analyze_company("AAPL")
   
3. rag_engine.py: analyze_company("AAPL")
   ├─ downloader.download_10k("AAPL")
   │  ├─ Queries SEC EDGAR API
   │  ├─ Downloads HTML file
   │  └─ Returns: [{file_path: "data/AAPL/...", fiscal_year: 2023}]
   │
   ├─ database.add_company("AAPL")
   │  └─ INSERT INTO companies (ticker) VALUES ('AAPL') RETURNING id
   │
   ├─ downloader.extract_text(file_path)
   │  ├─ Parses HTML
   │  ├─ Removes tags
   │  └─ Returns: 500KB plain text
   │
   ├─ Create Document with metadata
   │  └─ Document(text=text, metadata={ticker: "AAPL", year: 2023})
   │
   ├─ _get_vector_store_for_ticker("AAPL")
   │  └─ Creates PGVectorStore(table_name="chunks_aapl")
   │
   ├─ VectorStoreIndex.from_documents(documents)
   │  ├─ Chunks text into 500 pieces
   │  ├─ For each chunk:
   │  │  ├─ Call OpenAI: embed_model.embed(chunk_text)
   │  │  ├─ Get: [0.123, -0.456, 0.789, ...] (1536 numbers)
   │  │  └─ INSERT INTO chunks_aapl (embedding, text, metadata)
   │  └─ Creates index for fast search
   │
   └─ _create_query_engine()
      └─ Sets up Q&A system with citation prompt

4. Back to app.py: Success! Show "✅ AAPL analyzed!"
   └─ Session state: {analyzer: StockAnalyzer(), current_ticker: "AAPL"}
   └─ Page refreshes, shows AAPL in dropdown

5. User types: "What were Apple's revenues last year?"
   └─ User clicks "Ask Question"
   └─ app.py: calls analyzer.ask(question)

6. rag_engine.py: ask("What were Apple's revenues last year?")
   ├─ Embed question
   │  └─ OpenAI: embed_model.embed("What were Apple's revenues last year?")
   │  └─ Returns: [0.234, 0.567, -0.123, ...] (1536 numbers)
   │
   ├─ Vector search in chunks_aapl
   │  └─ SQL: SELECT * FROM chunks_aapl 
   │           ORDER BY embedding <=> question_embedding 
   │           LIMIT 5
   │  └─ Returns 5 most similar chunks:
   │     [
   │       {text: "Net sales totaled $383.3 billion...", score: 0.89},
   │       {text: "Fiscal 2023 revenue decreased 3%...", score: 0.85},
   │       {text: "Geographic breakdown shows...", score: 0.82},
   │       ...
   │     ]
   │
   ├─ Build context string
   │  └─ context = "[Source 1]: Net sales totaled...\n
   │                [Source 2]: Fiscal 2023 revenue...\n
   │                [Source 3]: Geographic breakdown..."
   │
   ├─ Send to GPT-4
   │  └─ prompt = "You are a financial analyst...
   │                CONTEXT: {context}
   │                Question: {question}
   │                Provide answer with citations:"
   │  └─ OpenAI: chat.completions.create(messages=[prompt])
   │  └─ GPT-4 responds:
   │     "Apple's total net sales were $383.3 billion in fiscal 2023 
   │      [Source 1], representing a 3% decrease from $394.3 billion 
   │      in 2022 [Source 2]. The Americas region contributed $169.0 
   │      billion [Source 3]..."
   │
   ├─ Extract sources
   │  └─ For each chunk used:
   │     {source_number: 1, ticker: "AAPL", text_excerpt: "...", score: 0.89}
   │
   ├─ Count citations
   │  └─ Find all [Source X] tags in answer
   │  └─ Count: 3 citations found
   │
   ├─ Verify ticker
   │  └─ Check all sources have ticker="AAPL"
   │  └─ Result: ✅ All verified
   │
   └─ Return result dictionary

7. Back to app.py: Display results
   ├─ Show answer with highlighted [Source X] tags
   ├─ Show metrics: 3 citations, 5 sources, ✅ Verified
   └─ Show expandable source details with text excerpts

8. User sees complete answer with verifiable sources! ✅
```

---

## 🔑 Key Innovations

### 1. Separate Tables Architecture
```
Traditional (❌ Bad):
document_chunks
├─ Apple chunk 1
├─ Apple chunk 2
├─ Nvidia chunk 1  ← Can leak into Apple queries!
└─ Nvidia chunk 2

Our Solution (✅ Good):
chunks_aapl          chunks_nvda
├─ Apple chunk 1     ├─ Nvidia chunk 1
└─ Apple chunk 2     └─ Nvidia chunk 2

100% isolation! No mixing possible!
```

### 2. Citation System
- Custom prompt template enforces citations
- Every fact must have [Source X] tag
- Sources are extracted and verified
- User can see exact text that was used

### 3. Session State Management
- One analyzer per user session
- Proper company switching
- No global caching issues

### 4. Metadata Tracking
- Every chunk knows its ticker, year, filing type
- Verification on every query
- Detailed source information displayed

---

## 📊 Performance Characteristics

### First-Time Company Analysis:
```
Download 10-K:     ~30 seconds
Extract text:      ~10 seconds
Create embeddings: ~90 seconds (500 chunks × OpenAI API)
Store vectors:     ~10 seconds
Total:            ~2-3 minutes
```

### Loading Existing Company:
```
Connect to DB:     ~1 second
Load vectors:      ~1 second
Create index:      ~1 second
Total:            ~2-3 seconds
```

### Answering Question:
```
Embed question:    ~100ms
Vector search:     ~50ms (PostgreSQL pgvector)
LLM generation:    ~2-5 seconds (GPT-4)
Total:            ~3-6 seconds
```

---

## 🎯 Summary

**What the app does:**
1. Downloads SEC 10-K filings
2. Processes them into searchable chunks
3. Creates AI embeddings for each chunk
4. Stores in separate database tables per company
5. Answers questions using RAG
6. Provides cited, verifiable answers

**Key files:**
- `app.py`: User interface and flow control
- `rag_engine.py`: AI/ML processing and query engine
- `database.py`: PostgreSQL operations
- `downloader.py`: SEC EDGAR integration

**Data flow:**
SEC → Download → Process → Embed → Store → Query → Answer → Display

**Innovation:**
Separate vector tables prevent data contamination, ensuring perfect isolation between companies.

---

This architecture ensures:
✅ No data mixing between companies
✅ Fast queries after initial processing
✅ Verifiable, cited answers
✅ Scalable to many companies
✅ Production-ready deployment
