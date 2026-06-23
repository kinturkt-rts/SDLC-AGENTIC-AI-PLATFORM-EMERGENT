import streamlit as st
import httpx
import os
from typing import Optional, Dict, List
import time

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# HTTP helpers with follow_redirects=True to prevent FastAPI 307 errors
def _get(url: str, headers: Dict = None, params: Dict = None) -> httpx.Response:
    """GET request helper"""
    return httpx.get(url, headers=headers, params=params, follow_redirects=True, timeout=30.0)

def _post(url: str, headers: Dict = None, json: Dict = None, files: Dict = None, data: Dict = None) -> httpx.Response:
    """POST request helper"""
    return httpx.post(url, headers=headers, json=json, files=files, data=data, follow_redirects=True, timeout=30.0)

def _delete(url: str, headers: Dict = None) -> httpx.Response:
    """DELETE request helper"""
    return httpx.delete(url, headers=headers, follow_redirects=True, timeout=30.0)

def _ensure_api_reachable():
    """Check if API is reachable and healthy"""
    try:
        response = _get(f"{API_BASE_URL}/health")
        if response.status_code != 200:
            st.error(f"API health check failed: {response.status_code}")
            st.stop()
    except Exception as e:
        st.error(f"Cannot reach API at {API_BASE_URL}: {str(e)}")
        st.stop()

def get_auth_headers() -> Dict[str, str]:
    """Get authorization headers with JWT token"""
    if "access_token" not in st.session_state:
        return {}
    return {"Authorization": f"Bearer {st.session_state.access_token}"}

def login_user(email: str, password: str) -> bool:
    """Login user and store token"""
    try:
        response = _post(
            f"{API_BASE_URL}/auth/token",
            json={"email": email, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.access_token = data["access_token"]
            st.session_state.token_expires_in = data["expires_in"]
            return True
        else:
            st.error(f"Login failed: {response.json().get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        st.error(f"Login error: {str(e)}")
        return False

def get_user_profile() -> Optional[Dict]:
    """Get current user profile"""
    try:
        response = _get(
            f"{API_BASE_URL}/auth/me",
            headers=get_auth_headers()
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception:
        return None

def get_collections() -> List[Dict]:
    """Get user's accessible collections"""
    try:
        response = _get(
            f"{API_BASE_URL}/collections",
            headers=get_auth_headers()
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except Exception:
        return []

def get_documents(collection_id: int) -> List[Dict]:
    """Get documents in a collection"""
    try:
        response = _get(
            f"{API_BASE_URL}/collections/{collection_id}/documents",
            headers=get_auth_headers()
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except Exception:
        return []

def upload_document(collection_id: int, file, title: str) -> bool:
    """Upload a document to a collection"""
    try:
        files = {"file": file}
        data = {"title": title}
        
        response = _post(
            f"{API_BASE_URL}/collections/{collection_id}/documents",
            headers=get_auth_headers(),
            files=files,
            data=data
        )
        
        if response.status_code == 201:
            return True
        else:
            st.error(f"Upload failed: {response.json().get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        st.error(f"Upload error: {str(e)}")
        return False

def ask_question(collection_id: int, question: str, session_id: Optional[int] = None) -> Optional[Dict]:
    """Ask a question in a collection"""
    try:
        payload = {"message": question}
        if session_id:
            payload["session_id"] = session_id
        
        response = _post(
            f"{API_BASE_URL}/collections/{collection_id}/chat",
            headers=get_auth_headers(),
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Chat failed: {response.json().get('detail', 'Unknown error')}")
            return None
    except Exception as e:
        st.error(f"Chat error: {str(e)}")
        return None

def get_chat_history(collection_id: int, session_id: int) -> List[Dict]:
    """Get chat history for a session"""
    try:
        response = _get(
            f"{API_BASE_URL}/collections/{collection_id}/chat/{session_id}",
            headers=get_auth_headers()
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except Exception:
        return []

# Main Streamlit app
def main():
    st.set_page_config(
        page_title="Policy RAG Portal",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Check API connectivity
    _ensure_api_reachable()
    
    # Initialize session state
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = None
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    
    # Login page
    if not st.session_state.access_token:
        st.title("Policy RAG Portal")
        st.markdown("### Login")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="admin@company.com")
            password = st.text_input("Password", type="password", placeholder="admin123")
            submitted = st.form_submit_button("Login")
            
            if submitted and email and password:
                if login_user(email, password):
                    st.success("Login successful!")
                    st.rerun()
        
        st.markdown("---")
        st.markdown("**Demo Credentials:**")
        st.markdown("- Admin: admin@company.com / admin123")
        st.markdown("- Contributor: hr@company.com / hr123")
        st.markdown("- Viewer: employee@company.com / emp123")
        
        return
    
    # Get user profile
    if not st.session_state.user_profile:
        profile = get_user_profile()
        if profile:
            st.session_state.user_profile = profile
        else:
            st.error("Failed to get user profile. Please login again.")
            st.session_state.access_token = None
            st.rerun()
    
    # Sidebar
    with st.sidebar:
        st.title("Policy RAG Portal")
        
        if st.session_state.user_profile:
            st.markdown(f"**User:** {st.session_state.user_profile['email']}")
            st.markdown(f"**Role:** {st.session_state.user_profile['role']}")
            
            if st.button("Logout"):
                st.session_state.access_token = None
                st.session_state.user_profile = None
                st.session_state.current_session_id = None
                st.rerun()
        
        st.markdown("---")
        
        # Collection selector
        collections = get_collections()
        if collections:
            collection_names = [f"{c['name']} ({c['document_count']} docs)" for c in collections]
            selected_idx = st.selectbox(
                "Select Collection",
                range(len(collections)),
                format_func=lambda i: collection_names[i],
                key="collection_selector"
            )
            
            selected_collection = collections[selected_idx] if selected_idx is not None else None
        else:
            st.warning("No collections available")
            selected_collection = None
    
    # Main content
    if not selected_collection:
        st.title("Welcome to Policy RAG Portal")
        st.markdown("""
        This portal allows you to:
        - Upload and organize policy documents
        - Ask questions about company policies
        - Get answers with proper citations
        
        Please select a collection from the sidebar to get started.
        """)
        return
    
    # Collection tabs
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📄 Documents", "👥 Members"])
    
    with tab1:
        st.header(f"Chat - {selected_collection['name']}")
        st.markdown(selected_collection.get('description', 'No description available'))
        
        # Chat interface
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Show citations for assistant messages
                if message["role"] == "assistant" and "citations" in message:
                    if message["citations"]:
                        with st.expander("📚 Sources"):
                            for i, citation in enumerate(message["citations"], 1):
                                st.markdown(
                                    f"{i}. **{citation['document_title']}** (Page {citation.get('page_number', 'N/A')}) "
                                    f"- Confidence: {citation['confidence']:.2f}\n\n"
                                    f"*{citation['content_preview']}*"
                                )
        
        # Chat input
        if prompt := st.chat_input("Ask a question about the policies..."):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get response from API
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = ask_question(
                        selected_collection["id"],
                        prompt,
                        st.session_state.current_session_id
                    )
                    
                    if response:
                        # Update session ID
                        st.session_state.current_session_id = response["session_id"]
                        
                        # Display answer
                        st.markdown(response["answer"])
                        
                        # Show confidence and citations
                        col1, col2 = st.columns([1, 3])
                        
                        with col1:
                            confidence = response["confidence"]
                            if confidence >= 0.8:
                                st.success(f"Confidence: {confidence:.2f}")
                            elif confidence >= 0.5:
                                st.warning(f"Confidence: {confidence:.2f}")
                            else:
                                st.error(f"Confidence: {confidence:.2f}")
                        
                        with col2:
                            if response["refused"]:
                                st.info("⚠️ Answer refused due to low confidence")
                        
                        citations = response.get("citations", [])
                        if citations:
                            with st.expander("📚 Sources"):
                                for i, citation in enumerate(citations, 1):
                                    st.markdown(
                                        f"{i}. **{citation['document_title']}** (Page {citation.get('page_number', 'N/A')}) "
                                        f"- Confidence: {citation['confidence']:.2f}\n\n"
                                        f"*{citation['content_preview']}*"
                                    )
                        
                        # Add assistant message to chat history
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response["answer"],
                            "citations": citations
                        })
                    else:
                        st.error("Failed to get response. Please try again.")
    
    with tab2:
        st.header(f"Documents - {selected_collection['name']}")
        
        # Upload section (only for contributors)
        if selected_collection["user_role"] == "contributor":
            with st.expander("📤 Upload Document"):
                with st.form("upload_form"):
                    uploaded_file = st.file_uploader(
                        "Choose a PDF file",
                        type=["pdf"],
                        help="Only PDF files are supported"
                    )
                    title = st.text_input(
                        "Document Title",
                        placeholder="e.g., Employee Handbook 2024"
                    )
                    
                    if st.form_submit_button("Upload"):
                        if uploaded_file and title:
                            with st.spinner("Uploading and processing document..."):
                                if upload_document(selected_collection["id"], uploaded_file, title):
                                    st.success("Document uploaded successfully! Processing will continue in the background.")
                                    time.sleep(1)
                                    st.rerun()
                        else:
                            st.error("Please provide both a file and a title")
        
        # Document list
        st.subheader("Documents in Collection")
        documents = get_documents(selected_collection["id"])
        
        if documents:
            for doc in documents:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{doc['title']}**")
                        st.markdown(f"*Uploaded: {doc['created_at'][:10]}*")
                    
                    with col2:
                        status = doc["status"]
                        if status == "success":
                            st.success(f"✅ {status.title()}")
                        elif status == "processing":
                            st.warning(f"⏳ {status.title()}")
                        elif status == "failed":
                            st.error(f"❌ {status.title()}")
                        else:
                            st.info(f"📄 {status.title()}")
                    
                    with col3:
                        st.markdown(f"**{doc['chunk_count']}** chunks")
                    
                    st.markdown("---")
        else:
            st.info("No documents in this collection yet.")
    
    with tab3:
        st.header(f"Members - {selected_collection['name']}")
        
        # Show user's role in collection
        st.info(f"Your role: **{selected_collection['user_role']}**")
        
        st.markdown("""
        **Role Permissions:**
        - **Viewer**: Can chat and view documents
        - **Contributor**: Can upload documents + viewer permissions
        - **Admin**: Can manage members + contributor permissions
        """)
        
        if selected_collection["user_role"] != "admin":
            st.warning("Only admins can manage collection members.")

if __name__ == "__main__":
    main()
