import streamlit as st
import sys
from pathlib import Path
import re

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.rag_engine import StockAnalyzer
import pandas as pd

# Page config
st.set_page_config(
    page_title="10-K Stock Analyzer",
    page_icon="📊",
    layout="wide"
)

# Custom CSS for better citation display
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .citation {
        background-color: #e3f2fd;
        padding: 2px 6px;
        border-radius: 3px;
        font-weight: 600;
        color: #1976d2;
    }
    .source-box {
        background-color: #f5f5f5;
        padding: 15px;
        border-left: 4px solid #667eea;
        margin: 10px 0;
        border-radius: 5px;
    }
    .metric-good {
        color: #4caf50;
        font-weight: bold;
    }
    .metric-warning {
        color: #ff9800;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize analyzer (NOT cached - we need to reload for different companies)
if "analyzer" not in st.session_state:
    st.session_state.analyzer = StockAnalyzer()
    st.session_state.analyzer.connect_to_supabase()
    st.session_state.current_ticker = None

analyzer = st.session_state.analyzer

# Header
st.markdown('<p class="main-header">📊 10-K Stock Analysis AI</p>', unsafe_allow_html=True)
st.markdown("**Powered by Supabase + OpenAI GPT-4 | With Detailed Citations**")

# Sidebar
with st.sidebar:
    st.header("🏢 Company Analysis")
    
    # Show analyzed companies
    companies = analyzer.get_analyzed_companies()
    if companies:
        st.success(f"✅ {len(companies)} companies analyzed")
        df = pd.DataFrame(companies)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        selected = st.selectbox(
            "Query Company",
            options=[c["ticker"] for c in companies],
            index=0,
            key="company_selector"
        )
        
        # CRITICAL FIX: Load the selected company's index
        if selected and selected != st.session_state.current_ticker:
            with st.spinner(f"Loading {selected} index..."):
                try:
                    # Load existing index from Supabase for this company
                    success = analyzer.load_company_index(selected)
                    if success:
                        st.session_state.current_ticker = selected
                        st.success(f"✅ Loaded {selected}")
                    else:
                        st.error(f"❌ Failed to load {selected}")
                except Exception as e:
                    st.error(f"Error loading company: {str(e)}")
    else:
        st.info("No companies analyzed yet")
    
    st.markdown("---")
    
    # Add new company
    st.subheader("➕ Analyze New Company")
    new_ticker = st.text_input("Ticker Symbol", placeholder="AAPL").upper()
    num_filings = st.slider("Number of filings", 1, 3, 1)
    
    if st.button("📥 Download & Analyze", type="primary", use_container_width=True):
        if new_ticker:
            with st.spinner(f"Analyzing {new_ticker}... (2-3 minutes)"):
                try:
                    success = analyzer.analyze_company(new_ticker, num_filings=num_filings)
                    if success:
                        st.session_state.current_ticker = new_ticker
                        st.success(f"✅ {new_ticker} analyzed!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to analyze {new_ticker}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    import traceback
                    with st.expander("🐛 Debug Info"):
                        st.code(traceback.format_exc())
        else:
            st.warning("Please enter a ticker symbol")
    
    st.markdown("---")
    st.caption("**💡 Popular Tickers:**")
    st.caption("AAPL • MSFT • GOOGL • TSLA • AMZN • META • NVDA")

# Main content
if st.session_state.current_ticker:
    ticker = st.session_state.current_ticker
    
    st.header(f"💬 Ask Questions About {ticker}")
    
    # Check if query engine is ready
    if not analyzer.query_engine:
        st.error("⚠️ Query engine not ready. Please reselect the company or analyze a new one.")
        if st.button("🔄 Reload Company"):
            st.rerun()
    else:
        with st.expander("📌 Example Questions"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                **Financial Questions:**
                - What were the total revenues last year?
                - What are the profit margins?
                - How much was spent on R&D?
                - What is the debt-to-equity ratio?
                """)
            with col2:
                st.markdown("""
                **Strategic Questions:**
                - What are the main business risks?
                - What is the company's growth strategy?
                - Who are the main competitors?
                - What markets does the company serve?
                """)
        
        question = st.text_area(
            "Your Question",
            placeholder=f"What were {ticker}'s revenues in the most recent fiscal year?",
            height=100,
            key="question_input"
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            ask_button = st.button("🔍 Ask Question", type="primary", use_container_width=True)
        
        if ask_button and question:
            with st.spinner("🤔 Analyzing 10-K filing..."):
                try:
                    result = analyzer.ask(question)
                    
                    if result:
                        # Display answer with highlighted citations
                        st.markdown("### 📝 Answer")
                        
                        answer_text = result["answer"]
                        
                        # Highlight citations with custom styling
                        def highlight_citations(text):
                            # Replace [Source X] with styled version
                            pattern = r'\[Source (\d+)\]'
                            highlighted = re.sub(
                                pattern,
                                r'<span class="citation">[Source \1]</span>',
                                text
                            )
                            return highlighted
                        
                        highlighted_answer = highlight_citations(answer_text)
                        st.markdown(highlighted_answer, unsafe_allow_html=True)
                        
                        # Citation quality metrics
                        st.markdown("---")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            citations_class = "metric-good" if result["num_citations"] > 0 else "metric-warning"
                            st.markdown(f"**Citations:** <span class='{citations_class}'>{result['num_citations']}</span>", 
                                      unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown(f"**Sources Used:** <span class='metric-good'>{result['num_sources']}</span>", 
                                      unsafe_allow_html=True)
                        
                        with col3:
                            quality = "✅ Well-Cited" if result["has_proper_citations"] else "⚠️ No Citations"
                            st.markdown(f"**Quality:** {quality}")
                        
                        # Display detailed sources
                        if result["sources"]:
                            st.markdown("---")
                            st.markdown("### 📚 Source Details")
                            
                            for source in result["sources"]:
                                with st.expander(
                                    f"📄 Source {source['source_number']}: "
                                    f"{source['ticker']} {source['filing_type']} - "
                                    f"FY{source['fiscal_year']} "
                                    f"(Relevance: {source['relevance_score']})",
                                    expanded=False
                                ):
                                    st.markdown(f"**Company:** {source['ticker']}")
                                    st.markdown(f"**Filing Type:** {source['filing_type']}")
                                    st.markdown(f"**Fiscal Year:** {source['fiscal_year']}")
                                    st.markdown(f"**Relevance Score:** {source['relevance_score']}")
                                    st.markdown(f"**Accession Number:** {source['accession']}")
                                    
                                    st.markdown("**Text Excerpt:**")
                                    st.text_area(
                                        "Source Text",
                                        value=source['text_excerpt'],
                                        height=150,
                                        key=f"source_{source['source_number']}_{question[:20]}",
                                        label_visibility="collapsed"
                                    )
                        
                        # Add to history
                        if "qa_history" not in st.session_state:
                            st.session_state["qa_history"] = []
                        
                        st.session_state["qa_history"].append({
                            "ticker": ticker,
                            "question": question,
                            "answer": answer_text[:200] + "...",
                            "citations": result["num_citations"]
                        })
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    with st.expander("🐛 Debug Information"):
                        st.code(traceback.format_exc())
        
        # Show Q&A history
        if "qa_history" in st.session_state and st.session_state["qa_history"]:
            st.markdown("---")
            st.subheader("📜 Recent Questions")
            
            for i, qa in enumerate(reversed(st.session_state["qa_history"][-5:]), 1):
                with st.expander(f"{qa['ticker']}: {qa['question'][:60]}... ({qa['citations']} citations)"):
                    st.markdown(f"**Q:** {qa['question']}")
                    st.markdown(f"**A:** {qa['answer']}")
                    st.caption(f"Citations: {qa['citations']}")

else:
    # Welcome screen
    st.info("👈 Select a company from the sidebar or add a new one to get started")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🤖 AI-Powered")
        st.write("GPT-4 analyzes 100+ page documents")
    
    with col2:
        st.markdown("### 📚 Well-Cited")
        st.write("Every fact includes source citations")
    
    with col3:
        st.markdown("### ☁️ Cloud Database")
        st.write("Supabase Postgres with pgvector")
    
    st.markdown("---")
    st.subheader("🔄 How It Works")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**1️⃣ Download**")
        st.caption("Fetch 10-K from SEC EDGAR")
    
    with col2:
        st.markdown("**2️⃣ Process**")
        st.caption("Chunk & embed documents")
    
    with col3:
        st.markdown("**3️⃣ Store**")
        st.caption("Save to Supabase pgvector")
    
    with col4:
        st.markdown("**4️⃣ Query**")
        st.caption("AI answers with citations")

st.markdown("---")
st.caption("Built with ❤️ using LlamaIndex • OpenAI • Supabase")
