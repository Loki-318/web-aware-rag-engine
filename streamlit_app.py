import streamlit as st
import requests
import time
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="RAG Engine",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Base URL
API_URL = "http://api:8000"

# Custom CSS
st.markdown("""
<style>
    .stAlert {
        margin-top: 1rem;
    }
    .source-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f0f2f6;
        margin: 0.5rem 0;
    }
    .metric-card {
        padding: 1rem;
        border-radius: 0.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🤖 RAG Engine - Knowledge Base Interface")
st.markdown("*Scalable Web-Aware Retrieval-Augmented Generation System*")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    # LLM Provider Selection
    st.subheader("🤖 LLM Provider")
    
    # Initialize session state
    if 'current_provider' not in st.session_state:
        st.session_state.current_provider = 'ollama'
    
    llm_provider = st.selectbox(
        "Choose Provider",
        ["ollama", "openai", "gemini"],
        index=["ollama", "openai", "gemini"].index(st.session_state.current_provider),
        help="Select which LLM service to use for generating answers"
    )
    
    # Provider-specific settings
    provider_config = {}
    api_key_valid = True
    
    if llm_provider == "openai":
        st.info("💡 Using OpenAI for production-grade answers")
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.session_state.get('openai_key', ''),
            help="Get your key from platform.openai.com/api-keys"
        )
        openai_model = st.selectbox(
            "Model",
            ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"],
            help="gpt-3.5-turbo is fastest and cheapest"
        )
        
        if openai_key:
            st.session_state.openai_key = openai_key
            provider_config = {"api_key": openai_key, "model": openai_model}
        else:
            api_key_valid = False
            st.warning("⚠️ Please enter your OpenAI API key")
    
    elif llm_provider == "gemini":
        st.info("💡 Using Google Gemini with free tier")
        gemini_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=st.session_state.get('gemini_key', ''),
            help="Get your key from makersuite.google.com/app/apikey"
        )
        gemini_model = st.selectbox(
            "Model",
            ["gemini-pro"],
            help="gemini-pro for text generation"
        )
        
        if gemini_key:
            st.session_state.gemini_key = gemini_key
            provider_config = {"api_key": gemini_key, "model": gemini_model}
        else:
            api_key_valid = False
            st.warning("⚠️ Please enter your Gemini API key")
    
    else:  # ollama
        st.info("💡 Using Ollama (local, free, private)")
        st.caption("Requires Ollama running locally")
        api_key_valid = True  # No key needed for Ollama
    
    # Switch provider button
    # Switch provider button
    if st.button("🔄 Switch Provider", type="primary", use_container_width=True, disabled=not api_key_valid):
        if llm_provider != st.session_state.current_provider:
            with st.spinner(f"Switching to {llm_provider}..."):
                try:
                    response = requests.post(
                        f"{API_URL}/provider/switch",
                        json={"provider": llm_provider, "config": provider_config},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        st.session_state.current_provider = llm_provider
                        st.success(f"✅ Switched to {llm_provider.upper()}")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to switch: {response.json().get('detail', 'Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Show current provider
    try:
        provider_response = requests.get(f"{API_URL}/provider", timeout=5)
        if provider_response.status_code == 200:
            current = provider_response.json().get('provider', 'Unknown')
            st.caption(f"🤖 Active: {current}")
    except:
        pass
    
    st.markdown("---")
    
    # API Status Check
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        if response.status_code == 200:
            st.success("✅ API Connected")
        else:
            st.error("❌ API Error")
    except:
        st.error("❌ API Offline")
    
    st.markdown("---")
    
    # Get stats
    try:
        docs_response = requests.get(f"{API_URL}/documents?limit=1000")
        if docs_response.status_code == 200:
            docs_data = docs_response.json()
            total_docs = docs_data.get('total', 0)
            
            completed = sum(1 for doc in docs_data.get('documents', []) if doc['status'] == 'completed')
            processing = sum(1 for doc in docs_data.get('documents', []) if doc['status'] in ['pending', 'processing'])
            failed = sum(1 for doc in docs_data.get('documents', []) if doc['status'] == 'failed')
            
            st.metric("📚 Total Documents", total_docs)
            st.metric("✅ Completed", completed)
            st.metric("⏳ Processing", processing)
            if failed > 0:
                st.metric("❌ Failed", failed)
    except:
        pass
    
    st.markdown("---")
    st.markdown("### 🔧 Quick Actions")
    if st.button("🔄 Refresh Stats", use_container_width=True):
        st.rerun()
    
    if st.button("📖 View API Docs", use_container_width=True):
        st.markdown(f"[Open API Documentation]({API_URL}/docs)")

# Main content tabs
tab1, tab2, tab3, tab4 = st.tabs(["📥 Ingest URLs", "🔍 Query Knowledge Base", "📊 Document Status", "📈 Analytics"])

# Tab 1: Ingest URLs
with tab1:
    st.header("📥 Ingest Web Content")
    st.markdown("Submit URLs to add them to the knowledge base. The system will fetch, parse, and index the content.")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        url_input = st.text_input(
            "Enter URL",
            placeholder="https://en.wikipedia.org/wiki/Artificial_intelligence",
            help="Enter a valid HTTP/HTTPS URL"
        )
    
    with col2:
        st.write("")
        st.write("")
        ingest_button = st.button("🚀 Ingest URL", type="primary", use_container_width=True)
    
    if ingest_button:
        if not url_input:
            st.error("⚠️ Please enter a URL")
        elif not url_input.startswith(('http://', 'https://')):
            st.error("⚠️ URL must start with http:// or https://")
        else:
            with st.spinner("Submitting URL..."):
                try:
                    response = requests.post(
                        f"{API_URL}/ingest-url",
                        json={"url": url_input},
                        timeout=10
                    )
                    
                    if response.status_code == 202:
                        data = response.json()
                        st.success(f"✅ {data['message']}")
                        st.info(f"📝 Job ID: `{data['job_id']}`")
                        
                        # Store job_id in session state
                        if 'job_ids' not in st.session_state:
                            st.session_state.job_ids = []
                        st.session_state.job_ids.append({
                            'job_id': data['job_id'],
                            'url': data['url'],
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        
                        # Auto-monitor
                        st.markdown("---")
                        st.subheader("📊 Processing Status")
                        status_placeholder = st.empty()
                        progress_bar = st.progress(0)
                        
                        max_attempts = 60
                        for attempt in range(max_attempts):
                            try:
                                status_response = requests.get(f"{API_URL}/status/{data['job_id']}")
                                if status_response.status_code == 200:
                                    status_data = status_response.json()
                                    
                                    status_placeholder.write(f"**Status:** {status_data['status']} | **Chunks:** {status_data['chunk_count']}")
                                    progress_bar.progress((attempt + 1) / max_attempts)
                                    
                                    if status_data['status'] == 'completed':
                                        st.success(f"🎉 Processing complete! Created {status_data['chunk_count']} chunks.")
                                        break
                                    elif status_data['status'] == 'failed':
                                        st.error(f"❌ Processing failed: {status_data.get('error_message', 'Unknown error')}")
                                        break
                            except:
                                pass
                            
                            time.sleep(2)
                    
                    elif response.status_code == 429:
                        st.error("⚠️ Rate limit exceeded. Please wait before submitting more URLs.")
                    else:
                        st.error(f"❌ Error: {response.json().get('detail', 'Unknown error')}")
                
                except requests.exceptions.Timeout:
                    st.error("⏱️ Request timeout. Please try again.")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Recent ingestions
    if 'job_ids' in st.session_state and st.session_state.job_ids:
        st.markdown("---")
        st.subheader("📜 Recent Ingestions")
        for job in reversed(st.session_state.job_ids[-5:]):
            with st.expander(f"🔗 {job['url'][:60]}... - {job['timestamp']}"):
                st.code(f"Job ID: {job['job_id']}")
                if st.button(f"Check Status", key=job['job_id']):
                    try:
                        status_response = requests.get(f"{API_URL}/status/{job['job_id']}")
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            st.json(status_data)
                    except:
                        st.error("Failed to fetch status")

# Tab 2: Query
with tab2:
    st.header("🔍 Query Knowledge Base")
    st.markdown("Ask questions and get grounded answers with source citations.")
    
    question = st.text_area(
        "Enter your question",
        placeholder="What is artificial intelligence?",
        height=100,
        help="Ask any question about the ingested documents"
    )
    
    col1, col2 = st.columns([3, 1])
    with col1:
        top_k = st.slider("Number of sources to retrieve", min_value=1, max_value=10, value=5)
    
    with col2:
        st.write("")
        st.write("")
        query_button = st.button("🔎 Search", type="primary", use_container_width=True)
    
    if query_button:
        if not question.strip():
            st.error("⚠️ Please enter a question")
        else:
            with st.spinner(f"🤖 Searching knowledge base..."):
                try:
                    # Prepare query payload
                    query_payload = {
                        "question": question,
                        "top_k": top_k
                    }
                    
                    # Make API request
                    response = requests.post(
                        f"{API_URL}/query",
                        json=query_payload,
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Answer
                        st.markdown("### 💡 Answer")
                        st.markdown(f"**Question:** *{data['question']}*")
                        
                        # Show which provider was used
                        provider_used = data.get('provider', 'Unknown')
                        st.caption(f"🤖 Generated by: **{provider_used}**")
                        
                        st.markdown("---")
                        st.write(data['answer'])
                        
                        # Sources
                        if data['sources']:
                            st.markdown("---")
                            st.markdown("### 📚 Sources")
                            
                            for idx, source in enumerate(data['sources'], 1):
                                with st.expander(f"📄 Source {idx}: {source['title']} (Relevance: {source['score']:.2%})"):
                                    st.markdown(f"**URL:** [{source['url']}]({source['url']})")
                                    st.markdown(f"**Relevance Score:** {source['score']:.4f}")
                                    st.markdown("**Excerpt:**")
                                    st.info(source['chunk_text'])
                        else:
                            st.warning("⚠️ No relevant sources found in the knowledge base.")
                    
                    elif response.status_code == 429:
                        st.error("⚠️ Rate limit exceeded. Please wait before making more queries.")
                    elif response.status_code == 503:
                        st.error("❌ LLM service unavailable. Please ensure Ollama is running.")
                    else:
                        st.error(f"❌ Error: {response.json().get('detail', 'Unknown error')}")
                
                except requests.exceptions.Timeout:
                    st.error("⏱️ Request timeout. The query took too long to process.")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# Tab 3: Document Status
with tab3:
    st.header("📊 Document Status")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "completed", "processing", "pending", "failed"]
        )
    
    with col2:
        limit = st.number_input("Documents per page", min_value=5, max_value=50, value=10)
    
    with col3:
        st.write("")
        st.write("")
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    # Fetch documents
    try:
        params = {"limit": limit}
        if status_filter != "All":
            params["status"] = status_filter
        
        response = requests.get(f"{API_URL}/documents", params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            if data['documents']:
                st.success(f"Found {data['total']} document(s)")
                
                for doc in data['documents']:
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            status_emoji = {
                                'completed': '✅',
                                'processing': '⏳',
                                'pending': '🔄',
                                'failed': '❌'
                            }.get(doc['status'], '❓')
                            
                            st.markdown(f"{status_emoji} **{doc['title'] or 'Untitled'}**")
                            st.caption(f"🔗 {doc['url']}")
                        
                        with col2:
                            st.metric("Chunks", doc['chunk_count'])
                        
                        with col3:
                            st.metric("Status", doc['status'].upper())
                        
                        if doc.get('error_message'):
                            st.error(f"Error: {doc['error_message']}")
                        
                        st.markdown("---")
            else:
                st.info("📭 No documents found")
        else:
            st.error("Failed to fetch documents")
    
    except Exception as e:
        st.error(f"Error: {str(e)}")

# Tab 4: Analytics
with tab4:
    st.header("📈 Analytics Dashboard")
    
    try:
        response = requests.get(f"{API_URL}/documents?limit=1000")
        
        if response.status_code == 200:
            data = response.json()
            documents = data.get('documents', [])
            
            if documents:
                # Status distribution
                status_counts = {}
                for doc in documents:
                    status = doc['status']
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Status Distribution")
                    fig = go.Figure(data=[go.Pie(
                        labels=list(status_counts.keys()),
                        values=list(status_counts.values()),
                        hole=0.3,
                        marker=dict(colors=['#4CAF50', '#FFC107', '#2196F3', '#F44336'])
                    )])
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader("📦 Chunk Distribution")
                    chunk_data = [doc['chunk_count'] for doc in documents if doc['chunk_count'] > 0]
                    
                    if chunk_data:
                        fig = go.Figure(data=[go.Histogram(
                            x=chunk_data,
                            nbinsx=20,
                            marker=dict(color='#667eea')
                        )])
                        fig.update_layout(
                            xaxis_title="Number of Chunks",
                            yaxis_title="Frequency",
                            height=400
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                # Summary metrics
                st.markdown("---")
                st.subheader("📊 Summary Statistics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                total_chunks = sum(doc['chunk_count'] for doc in documents)
                avg_chunks = total_chunks / len(documents) if documents else 0
                completed_docs = sum(1 for doc in documents if doc['status'] == 'completed')
                success_rate = (completed_docs / len(documents) * 100) if documents else 0
                
                with col1:
                    st.metric("📚 Total Documents", len(documents))
                
                with col2:
                    st.metric("📦 Total Chunks", total_chunks)
                
                with col3:
                    st.metric("📊 Avg Chunks/Doc", f"{avg_chunks:.1f}")
                
                with col4:
                    st.metric("✅ Success Rate", f"{success_rate:.1f}%")
                
                # Recent activity
                st.markdown("---")
                st.subheader("🕐 Recent Activity")
                
                recent_docs = sorted(
                    documents,
                    key=lambda x: x.get('created_at', ''),
                    reverse=True
                )[:5]
                
                for doc in recent_docs:
                    status_color = {
                        'completed': 'green',
                        'processing': 'orange',
                        'pending': 'blue',
                        'failed': 'red'
                    }.get(doc['status'], 'gray')
                    
                    st.markdown(
                        f":{status_color}[**{doc['status'].upper()}**] - "
                        f"{doc['title'] or 'Untitled'} ({doc['chunk_count']} chunks)"
                    )
            else:
                st.info("📭 No documents to analyze")
        else:
            st.error("Failed to fetch analytics data")
    
    except Exception as e:
        st.error(f"Error loading analytics: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <p>🤖 RAG Engine v1.0 | Built with FastAPI, Qdrant, and Ollama</p>
        <p>💡 <a href='http://localhost:8000/docs' target='_blank'>API Documentation</a> | 
        📊 <a href='http://localhost:6333/dashboard' target='_blank'>Qdrant Dashboard</a></p>
    </div>
    """,
    unsafe_allow_html=True
)