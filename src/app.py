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
    .ticker-badge {
        background-color: #667eea;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize analyzer in session state (NOT cached)
if "analyzer" not in st.session_state:
    st.session_state.analyzer = StockAnalyzer()
    st.session_state.current_ticker = None

analyzer = st.session_state.analyzer

# Header
st.markdown('<p class="main-header">📊 10-K Stock Analysis AI</p>', unsafe_allow_html=True)
st.markdown("**Powered by Supabase + OpenAI GPT-4 | Separate Tables Per Company**")

if st.session_state.current_ticker:
    st.markdown(f'<div class="ticker-badge">Currently Analyzing: {st.session_state.current_ticker}</div>', 
                unsafe_allow_html=True)

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
            index=0 if not st.session_state.current_ticker else 
                  ([c["ticker"] for c in companies].index(st.session_state.current_ticker) 
                   if st.session_state.current_ticker in [c["ticker"] for c in companies] else 0),
            key="company_selector"
        )
        
        # Load the selected company's index
        if selected and selected != st.session_state.current_ticker:
            with st.spinner(f"Loading {selected} from table chunks_{selected.lower()}..."):
                try:
                    success = analyzer.load_company_index(selected)
                    if success:
                        st.session_state.current_ticker = selected
                        st.success(f"✅ Loaded {selected}")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to load {selected}")
                except Exception as e:
                    st.error(f"Error loading company: {str(e)}")
                    import traceback
                    with st.expander("🐛 Debug Info"):
                        st.code(traceback.format_exc())
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
    
    st.markdown("---")
    st.caption("**🔧 Architecture:**")
    st.caption(f"Using separate tables per company")
    if st.session_state.current_ticker:
        st.caption(f"Current table: chunks_{st.session_state.current_ticker.lower()}")

# Main content
if st.session_state.current_ticker:
    ticker = st.session_state.current_ticker
    
    st.header(f"💬 Ask Questions About {ticker}")
    
    # Check if query engine is ready
    if not analyzer.query_engine or analyzer.current_ticker != ticker:
        st.error("⚠️ Query engine not ready. Please reselect the company or analyze a new one.")
        if st.button("🔄 Reload Company"):
            st.rerun()
    else:
        with st.expander("📌 Example Questions", expanded=False):
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
            with st.spinner(f"🤔 Analyzing {ticker}'s 10-K filing..."):
                try:
                    result = analyzer.ask(question)
                    
                    if result:
                        # Display answer with highlighted citations
                        st.markdown("### 📝 Answer")
                        
                        answer_text = result["answer"]
                        
                        # Highlight citations with custom styling
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
                        
                        # Citation quality metrics
                        st.markdown("---")
                        col1, col2, col3, col4 = st.columns(4)
                        
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
                        
                        with col4:
                            # Verify all sources are from correct ticker
                            correct_ticker = all(s['ticker'] == ticker for s in result['sources'])
                            ticker_status = "✅ Verified" if correct_ticker else "⚠️ Mixed"
                            st.markdown(f"**Ticker:** {ticker_status}")
                        
                        # Display detailed sources
                        if result["sources"]:
                            st.markdown("---")
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
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.markdown(f"**Company:** {source['ticker']}")
                                        st.markdown(f"**Filing:** {source['filing_type']}")
                                    with col2:
                                        st.markdown(f"**Year:** {source['fiscal_year']}")
                                        st.markdown(f"**Score:** {source['relevance_score']}")
                                    with col3:
                                        st.markdown(f"**Accession:** {source['accession'][:20]}...")
                                    
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
                            "citations": result["num_citations"],
                            "verified": all(s['ticker'] == ticker for s in result['sources'])
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
            
            # Filter history for current ticker
            ticker_history = [qa for qa in st.session_state["qa_history"] if qa['ticker'] == ticker]
            
            if ticker_history:
                for i, qa in enumerate(reversed(ticker_history[-5:]), 1):
                    verified_emoji = "✅" if qa.get('verified', False) else "⚠️"
                    with st.expander(
                        f"{verified_emoji} {qa['ticker']}: {qa['question'][:60]}... "
                        f"({qa['citations']} citations)"
                    ):
                        st.markdown(f"**Q:** {qa['question']}")
                        st.markdown(f"**A:** {qa['answer']}")
                        st.caption(f"Citations: {qa['citations']} | "
                                 f"Verified: {'Yes' if qa.get('verified', False) else 'No'}")
            else:
                st.info(f"No questions asked about {ticker} yet")

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
        st.markdown("### 🔒 Isolated")
        st.write("Separate tables prevent data mixing")
    
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
        st.caption("Save to company-specific table")
    
    with col4:
        st.markdown("**4️⃣ Query**")
        st.caption("AI answers with citations")
    
    st.markdown("---")
    st.subheader("🏗️ Architecture")
    st.markdown("""
    This app uses **separate database tables** for each company:
    - `chunks_aapl` - Apple's vectors
    - `chunks_nvda` - Nvidia's vectors
    - `chunks_msft` - Microsoft's vectors
    
    **Benefits:**
    - ✅ 100% data isolation
    - ✅ No cross-contamination possible
    - ✅ Fast, targeted queries
    - ✅ Easy to delete/update individual companies
    """)

st.markdown("---")
st.caption("Built with ❤️ using LlamaIndex • OpenAI • Supabase • Separate Tables Architecture")
