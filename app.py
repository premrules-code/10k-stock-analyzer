"""
10-K Stock Analyzer - Single Page Application with Citations

Everything you need on one page:
- Chat interface for asking questions
- Company management (download/view)
- Settings and configuration
- Citation system (max 5 sources)
"""

import streamlit as st
import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import time
from datetime import datetime
import logging

# Add src to path
sys.path.append(str(Path(__file__).parent))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="10-K Stock Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS (with Citation Styles)
# ============================================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main header */
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(120deg, #1f77b4, #2ecc71);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
        margin-bottom: 0.5rem;
    }
    
    .sub-header {
        font-size: 1.1rem;
        color: #888;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Chat messages */
    .user-message {
        background: linear-gradient(135deg, #1f77b4, #1565c0);
        color: white;
        padding: 1.2rem 1.5rem;
        border-radius: 18px 18px 4px 18px;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(31, 119, 180, 0.3);
        animation: slideIn 0.3s ease-out;
    }
    
    .assistant-message {
        background: #1a1d29;
        color: #fafafa;
        padding: 1.2rem 1.5rem;
        border-radius: 18px 18px 18px 4px;
        margin: 1rem 0;
        border-left: 4px solid #2ecc71;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        animation: slideIn 0.3s ease-out;
    }
    
    .message-time {
        font-size: 0.8rem;
        opacity: 0.7;
        margin-top: 0.5rem;
    }
    
    /* Citation cards */
    .citation-card {
        background: #1a1d29;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 3px solid #2ecc71;
        transition: all 0.2s;
    }
    
    .citation-card:hover {
        background: #22252f;
        border-left-width: 5px;
    }
    
    .citation-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.5rem;
        align-items: center;
    }
    
    .citation-company {
        color: #2ecc71;
        font-weight: 600;
        font-size: 0.95rem;
    }
    
    .citation-score {
        color: #888;
        font-size: 0.85rem;
        background: rgba(46, 204, 113, 0.1);
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
    }
    
    .citation-meta {
        color: #aaa;
        font-size: 0.85rem;
        margin-bottom: 0.5rem;
        display: flex;
        gap: 1rem;
    }
    
    .citation-text {
        background: #0d1117;
        padding: 0.75rem;
        border-radius: 4px;
        font-size: 0.9rem;
        color: #ddd;
        max-height: 200px;
        overflow-y: auto;
        line-height: 1.5;
        font-family: 'Courier New', monospace;
    }
    
    .citation-text::-webkit-scrollbar {
        width: 6px;
    }
    
    .citation-text::-webkit-scrollbar-track {
        background: #1a1d29;
    }
    
    .citation-text::-webkit-scrollbar-thumb {
        background: #2ecc71;
        border-radius: 3px;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 600;
        margin: 0.2rem;
    }
    
    .status-success {
        background: rgba(46, 204, 113, 0.2);
        color: #2ecc71;
        border: 1px solid rgba(46, 204, 113, 0.3);
    }
    
    .status-error {
        background: rgba(231, 76, 60, 0.2);
        color: #e74c3c;
        border: 1px solid rgba(231, 76, 60, 0.3);
    }
    
    .status-warning {
        background: rgba(243, 156, 18, 0.2);
        color: #f39c12;
        border: 1px solid rgba(243, 156, 18, 0.3);
    }
    
    /* Animations */
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    /* Hide default streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: #1a1d29;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE
# ============================================================================

def init_session_state():
    """Initialize session state variables"""
    
    defaults = {
        'chat_history': [],
        'agent': None,
        'db': None,
        'temperature': 0.1,
        'max_tokens': None,
        'companies': [],
        'processing': False,
        'query_count': 0
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def check_environment():
    """Check if environment is configured"""
    required = ['OPENAI_API_KEY', 'DATABASE_URL', 'SUPABASE_HOST', 'SUPABASE_PASSWORD']
    missing = [var for var in required if not os.getenv(var)]
    return missing

def get_agent():
    """Get or create agent instance"""
    if st.session_state.agent is None:
        try:
            from src.agent import FinancialAgent
            with st.spinner("🤖 Initializing AI Agent..."):
                st.session_state.agent = FinancialAgent()
            st.success("✅ Agent ready!", icon="🤖")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"❌ Failed to initialize agent: {str(e)}")
            return None
    return st.session_state.agent

def get_database():
    """Get or create database instance"""
    if st.session_state.db is None:
        try:
            from src.database import Database
            st.session_state.db = Database()
        except Exception as e:
            st.error(f"❌ Database connection failed: {str(e)}")
            return None
    return st.session_state.db

def add_message(role: str, content: str, citations: list = None):
    """Add message to chat history"""
    st.session_state.chat_history.append({
        "role": role,
        "content": content,
        "citations": citations or [],
        "timestamp": datetime.now()
    })

def render_message(message: dict):
    """Render a chat message with citations"""
    role = message['role']
    content = message.get('content', '')
    citations = message.get('citations', [])
    timestamp = message.get('timestamp', datetime.now())
    time_str = timestamp.strftime("%I:%M %p")
    
    if role == "user":
        st.markdown(f"""
        <div class="user-message">
            <strong>👤 You</strong>
            <div style="margin-top: 0.5rem;">{content}</div>
            <div class="message-time">{time_str}</div>
        </div>
        """, unsafe_allow_html=True)
    
    else:  # assistant
        # Process answer to make citation markers clickable
        answer_html = content
        
        # Convert citation markers [1], [2], etc. to styled superscript links
        import re
        def replace_citation(match):
            num = match.group(1)
            return f'<sup><a href="#citation-{num}" style="color: #007bff; text-decoration: none; font-weight: bold;">[{num}]</a></sup>'
        
        answer_html = re.sub(r'\[(\d+)\]', replace_citation, answer_html)
        
        # Render answer
        st.markdown(f"""
        <div class="assistant-message">
            <strong>🤖 AI Assistant</strong>
            <div style="margin-top: 0.5rem;">{answer_html}</div>
            <div class="message-time">{time_str}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Render citations if available
        if citations and len(citations) > 0:
            st.markdown("---")
            st.markdown(f"### 📚 References ({len(citations)} sources)")
            st.caption("Click each reference to view the full source text from the 10-K filing")
            
            for citation in citations:
                # Create citation metadata
                score_display = f"{citation['score']:.1%}" if citation.get('score') else "N/A"
                chunk_id = citation.get('chunk_id', 'N/A')
                chunk_info = f"Chunk #{chunk_id}" if chunk_id != 'N/A' else ''
                text_len = citation.get('text_length', len(citation['text']))
                filing_url = citation.get('filing_url', '')
                
                # Add anchor for scrolling
                st.markdown(f'<div id="citation-{citation["id"]}"></div>', unsafe_allow_html=True)
                
                # Create expandable citation with full chunk text
                with st.expander(
                    f"[{citation['id']}] {citation['company']} ({citation['ticker']}) - FY {citation['fiscal_year']} | Relevance: {score_display}",
                    expanded=False
                ):
                    # Metadata row
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.caption(f"📅 FY {citation['fiscal_year']}")
                    with col2:
                        st.caption(f"📄 Filed: {citation['filing_date']}")
                    with col3:
                        if chunk_info:
                            st.caption(f"🔖 {chunk_info}")
                    with col4:
                        st.caption(f"📝 {text_len:,} chars")
                    
                    st.markdown("**Full Chunk Text:**")
                    # Display full chunk text using st.code which handles escaping
                    st.code(citation['text'], language="text", line_numbers=False)
                    
                    # Add link to SEC filing
                    if filing_url:
                        st.markdown(f"🔗 [Open full filing on SEC.gov]({filing_url})")

def process_query(question: str):
    """Process user query and return dict with answer and citations"""
    agent = get_agent()
    if not agent:
        return {
            "answer": "❌ Agent not available. Please check your configuration.",
            "citations": []
        }
    
    try:
        temperature = st.session_state.get('temperature', 0.1)
        max_tokens = st.session_state.get('max_tokens', None)
        
        response = agent.ask(question, temperature=temperature, max_tokens=max_tokens)
        st.session_state.query_count += 1
        
        return response  # Returns dict with answer and citations
    
    except Exception as e:
        return {
            "answer": f"❌ Error: {str(e)}",
            "citations": []
        }

# ============================================================================
# SIDEBAR
# ============================================================================

def render_sidebar():
    """Render sidebar with controls and company management"""
    
    with st.sidebar:
        st.markdown("# 📊 10-K Analyzer")
        st.markdown("---")
        
        # Quick Stats
        st.markdown("### 📈 Quick Stats")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Queries", st.session_state.query_count)
        
        with col2:
            num_companies = len(st.session_state.companies)
            st.metric("Companies", num_companies)
        
        st.markdown("---")
        
        # Company Management
        st.markdown("### 🏢 Company Management")
        
        # Load companies from database
        db = get_database()
        if db:
            st.session_state.companies = db.get_all_companies()
        
        if st.session_state.companies:
            st.markdown("**Available Companies:**")
            for company in st.session_state.companies:
                st.markdown(f"• **{company['ticker']}** - {company['company_name']}")
        else:
            st.info("No companies added yet")
        
        st.markdown("---")
        
        # Add new company
        with st.expander("➕ Add Company", expanded=False):
            ticker = st.text_input("Ticker Symbol", placeholder="e.g., AAPL", key="add_ticker")
            num_filings = st.number_input("Number of filings", min_value=1, max_value=5, value=1)
            
            if st.button("📥 Download & Analyze", use_container_width=True, type="primary"):
                if ticker:
                    agent = get_agent()
                    if agent:
                        with st.spinner(f"📥 Downloading {ticker}..."):
                            try:
                                success = agent.analyze_company(ticker.upper(), num_filings)
                                if success:
                                    st.success(f"✅ {ticker.upper()} analyzed!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to analyze {ticker.upper()}")
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                else:
                    st.warning("Please enter a ticker symbol")
        
        st.markdown("---")
        
        # AI Settings
        st.markdown("### 🌡️ AI Settings")
        
        st.session_state.temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=st.session_state.temperature,
            step=0.1,
            help="Lower = more focused, Higher = more creative"
        )
        
        use_limit = st.checkbox("Limit response length")
        if use_limit:
            st.session_state.max_tokens = st.slider(
                "Max tokens",
                min_value=100,
                max_value=2000,
                value=500,
                step=100
            )
        else:
            st.session_state.max_tokens = None
        
        st.markdown("---")
        
        # System Status
        st.markdown("### 🔧 System Status")
        
        # Check environment
        missing = check_environment()
        if not missing:
            st.markdown('<span class="status-badge status-success">✅ Environment OK</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-badge status-error">❌ Missing Config</span>', unsafe_allow_html=True)
        
        # Check database
        if st.session_state.db:
            st.markdown('<span class="status-badge status-success">✅ Database OK</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-badge status-error">❌ Database</span>', unsafe_allow_html=True)
        
        # Check agent
        if st.session_state.agent:
            st.markdown('<span class="status-badge status-success">✅ Agent Ready</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-badge status-warning">⚠️ Agent</span>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Chat Controls
        st.markdown("### 💬 Chat Controls")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                st.success("Chat cleared!")
                time.sleep(1)
                st.rerun()
        
        with col2:
            num_messages = len(st.session_state.chat_history)
            st.metric("Messages", num_messages)

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application"""
    
    # Initialize
    init_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Header
    st.markdown('<div class="main-header">📊 10-K Stock Analyzer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">AI-Powered SEC Filing Analysis with Citations</div>', unsafe_allow_html=True)
    
    # Check environment
    missing = check_environment()
    if missing:
        st.error(f"❌ Missing configuration: {', '.join(missing)}")
        st.info("💡 Please configure your `.env` file")
        return
    
    # Main content area
    col_chat, col_suggestions = st.columns([7, 3])
    
    with col_chat:
        st.markdown("### 💬 Ask Questions")
        
        # Chat container
        chat_container = st.container()
        
        with chat_container:
            if not st.session_state.chat_history:
                # Welcome message
                st.markdown("""
                <div class="assistant-message">
                    <strong>🤖 AI Assistant</strong>
                    <div style="margin-top: 0.5rem;">
                        👋 Hello! I'm your 10-K filing analyst. I can help you with:
                        <br><br>
                        • <strong>Financial data</strong>: Revenue, net income, assets<br>
                        • <strong>Business analysis</strong>: Products, strategy, operations<br>
                        • <strong>Risk assessment</strong>: Key risk factors<br>
                        • <strong>Comparisons</strong>: Compare companies<br>
                        • <strong>Trends</strong>: Analyze performance over time
                        <br><br>
                        📚 <strong>All answers include up to 5 citations</strong> from source documents
                        <br><br>
                        💡 Ask a question below or click a suggested question →
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Render chat history
                for message in st.session_state.chat_history:
                    render_message(message)
        
        # Query input
        st.markdown("---")
        
        with st.form(key="query_form", clear_on_submit=True):
            col1, col2 = st.columns([5, 1])
            
            with col1:
                user_query = st.text_input(
                    "Your question",
                    placeholder="e.g., What was Apple's 2023 revenue?",
                    label_visibility="collapsed"
                )
            
            with col2:
                submit = st.form_submit_button("Send 🚀", use_container_width=True, type="primary")
        
        # Process query
        if submit and user_query:
            # Add user message
            add_message("user", user_query)
            
            # Show processing
            with st.spinner("🤔 Thinking..."):
                response = process_query(user_query)
            
            # Debug: Check response structure
            st.write(f"DEBUG Response type: {type(response)}")
            if isinstance(response, dict):
                st.write(f"DEBUG Response keys: {response.keys()}")
                st.write(f"DEBUG Citations: {response.get('citations', [])[:1]}")  # Show first citation
            
            # Add assistant response with citations
            if isinstance(response, dict):
                add_message(
                    "assistant", 
                    response.get("answer", "No response"),
                    response.get("citations", [])
                )
            else:
                add_message("assistant", str(response))
            
            # Rerun to show messages
            st.rerun()
    
    with col_suggestions:
        st.markdown("### 💡 Suggestions")
        
        suggestions = {
            "Financial": [
                "What was Apple's 2023 revenue?",
                "Show me Microsoft's net income",
                "What are Google's total assets?"
            ],
            "Business": [
                "What are Apple's main products?",
                "Describe Microsoft's strategy",
                "What are Google's risk factors?"
            ],
            "Compare": [
                "Compare AAPL and MSFT revenue",
                "Which had higher income?",
                "Compare profit margins"
            ]
        }
        
        for category, questions in suggestions.items():
            with st.expander(f"📌 {category}", expanded=True):
                for question in questions:
                    if st.button(question, key=f"suggest_{question}", use_container_width=True):
                        # Add to chat and process
                        add_message("user", question)
                        with st.spinner("🤔 Thinking..."):
                            response = process_query(question)
                        if isinstance(response, dict):
                            add_message(
                                "assistant",
                                response.get("answer", "No response"),
                                response.get("citations", [])
                            )
                        else:
                            add_message("assistant", str(response))
                        st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 1rem 0;">
        <p><strong>10-K Stock Analyzer</strong> v1.0.0 | 
        Powered by OpenAI GPT-4 • LlamaIndex • Supabase</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()