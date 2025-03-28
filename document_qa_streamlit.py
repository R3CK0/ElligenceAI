import streamlit as st
import weaviate
from weaviate.classes.config import Property, DataType, Configure
from weaviate.classes.init import Auth
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime
import uuid
from openai import OpenAI
import tempfile
import hashlib

# Load environment variables
load_dotenv(override=True)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Weaviate client
client = weaviate.connect_to_weaviate_cloud(
    cluster_url=os.getenv("WEAVIATE_URL"),
    auth_credentials=Auth.api_key(os.getenv("WEAVIATE_API_KEY")),
    headers={
        "X-OpenAI-Api-Key": os.getenv("OPENAI_API_KEY")
    }
)

# User credentials (in production, use a secure database)
USERS = {
    "admin": hashlib.sha256("your_secure_password".encode()).hexdigest()
}

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hashlib.sha256(st.session_state["username"].encode()).hexdigest() in USERS and \
           hashlib.sha256(st.session_state["password"].encode()).hexdigest() == USERS[hashlib.sha256(st.session_state["username"].encode()).hexdigest()]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show inputs for username + password.
    st.text_input("Username", on_change=password_entered, key="username")
    st.text_input("Password", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state:
        st.error("😕 User not known or password incorrect")
    return False

def reformat_query(query: str) -> str:
    """Use GPT-4 to reformat the query to better understand user intent."""
    try:
        prompt = f"""Given the following question, reformat it to better capture the user's intent and include relevant keywords.
        Focus on extracting the core question and any important context.
        Return only the reformatted query, no explanations.
        
        Original question: {query}
        
        Reformatted query:"""
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at understanding and reformatting questions to capture their true intent."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        st.error(f"Error reformatting query: {e}")
        return query

def search_relevant_sections(query: str, limit: int = 15) -> List[Dict[str, str]]:
    """Search for relevant sections using semantic search."""
    try:
        # First reformat the query
        print("Adjusting the query...")
        reformatted_query = reformat_query(query)
        print(reformatted_query)
        
        # Perform the search
        print("Searching for relevant sections...")
        result = (
            client.collections
            .get("TextChunk")
            .query
            .hybrid(
                query=reformatted_query,
                limit=limit
            )
        )
        
        # Process and return the results
        sections = []
        for obj in result.objects:
            sections.append({
                "content": obj.properties["content"],
                "source_file": obj.properties["source_file"],
                "page_number": obj.properties["page_number"]
            })
        
        return sections
        
    except Exception as e:
        st.error(f"Error searching sections: {e}")
        return []

def analyze_and_summarize(sections: List[Dict[str, str]], query: str) -> Dict[str, str]:
    """Use GPT-4 to analyze and summarize the retrieved sections."""
    try:
        # Prepare the sections for GPT
        sections_text = "\n\n".join([
            f"Source: {section['source_file']}\nPage: {section['page_number']}\nContent: {section['content']}"
            for section in sections
        ])
        
        prompt = f"""Given the following retrieved sections and the user's question, analyze the content and provide:
        1. A concise summary of the relevant information
        2. A strategy for answering the question
        
        In the case where the information is not present, simply return "Not enough information in the database to answer the question".
        
        User Question: {query}
        
        Retrieved Sections:
        {sections_text}
        
        Analysis:"""
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing information from retrieved sections and formulating answer strategies."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=750
        )
        
        analysis = response.choices[0].message.content.strip()
        
        # Parse the analysis into components
        summary = ""
        strategy = ""
        has_info = False
        
        for line in analysis.split('\n'):
            if "summary:" in line.lower():
                summary = line.split(':', 1)[1].strip()
            elif "strategy:" in line.lower():
                strategy = line.split(':', 1)[1].strip()
            elif "information present:" in line.lower():
                has_info = "yes" in line.lower()
        
        return {
            "summary": summary,
            "strategy": strategy,
            "has_info": has_info
        }
        
    except Exception as e:
        st.error(f"Error analyzing sections: {e}")
        return {
            "summary": "Error analyzing content",
            "strategy": "Unable to determine strategy",
            "has_info": False
        }

def generate_answer(question: str, sections: List[Dict[str, str]], analysis: Dict[str, str]) -> str:
    """Generate the final answer using O3-mini."""
    try:
        # Prepare the prompt
        prompt = f"""Based on the following information, provide a clear and concise answer to the user's question.
        
        Question: {question}
        
        Retrieved Information:
        {analysis['summary']}
        
        Answer Strategy:
        {analysis['strategy']}
        
        Please provide a direct answer to the question:"""
        
        response = openai_client.chat.completions.create(
            model="o3-mini",
            messages=[
                {"role": "system", "content": "You are an expert at providing clear and accurate answers based on available information."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        st.error(f"Error generating answer: {e}")
        return "Sorry, I encountered an error while generating the answer."

def initialize_chat_history():
    """Initialize chat history in session state if it doesn't exist."""
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I'm your document Q&A assistant. You can upload documents and ask questions about them."}
        ]

def main():
    st.set_page_config(
        page_title="Document Q&A System",
        page_icon="📚",
        layout="wide"
    )
    
    # Check authentication
    if not check_password():
        st.stop()  # Do not continue if check_password() returned False
    
    st.title("📚 Document Question Answering System")
    st.markdown("""
    This system allows you to:
    1. Upload documents to the knowledge base
    2. Ask questions about the uploaded documents
    3. Get AI-powered answers based on the document content
    """)
    
    # Add logout button in sidebar
    with st.sidebar:
        if st.button("Logout"):
            st.session_state["password_correct"] = False
            st.rerun()
    
    # Initialize chat history
    initialize_chat_history()
    
    # File uploader
    with st.sidebar:
        st.header("Upload Documents")
        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=["txt", "pdf"],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                # Create a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = Path(tmp_file.name)
                
                # Upload to Weaviate
                try:
                    with open(tmp_file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Upload to Weaviate
                    client.collections.get("TextChunk").data.insert({
                        "content": content,
                        "source_file": uploaded_file.name,
                        "created_at": datetime.now().isoformat(),
                        "word_count": len(content.split()),
                        "chunk_uuid": str(uuid.uuid4())
                    })
                    
                    st.success(f"Successfully uploaded {uploaded_file.name}")
                except Exception as e:
                    st.error(f"Error uploading {uploaded_file.name}: {str(e)}")
                finally:
                    # Clean up temporary file
                    os.unlink(tmp_file_path)
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your documents..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Search for relevant sections
                    relevant_sections = search_relevant_sections(prompt)
                    
                    if relevant_sections:
                        # Analyze and summarize the sections
                        analysis = analyze_and_summarize(relevant_sections, prompt)
                        
                        # Generate the answer
                        answer = generate_answer(prompt, relevant_sections, analysis)
                        
                        # Display the answer
                        st.write(answer)
                        
                        # Show relevant sections in expandable sections
                        with st.expander("View Retrieved Information"):
                            st.write("**Analysis Summary:**")
                            st.write(analysis["summary"])
                            st.write("\n**Answer Strategy:**")
                            st.write(analysis["strategy"])
                            st.write("\n**Source Documents:**")
                            for i, section in enumerate(relevant_sections, 1):
                                st.markdown(f"""
                                **Section {i}**
                                - **Source:** {section['source_file']}
                                - **Page:** {section['page_number']}
                                """)
                                st.text_area(f"Content {i}", section["content"], height=200)
                    else:
                        answer = "I couldn't find any relevant information to answer your question. Please try rephrasing it."
                        st.warning(answer)
                except Exception as e:
                    answer = f"I encountered an error while processing your question: {str(e)}"
                    st.error(answer)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": answer})

if __name__ == "__main__":
    main()
    client.close() 