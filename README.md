# Document Q&A System

A secure, AI-powered document question-answering system built with Streamlit, Weaviate, and OpenAI. This system allows users to upload documents and ask questions about them, providing AI-generated answers based on the document content.

## Features

- 🔒 Secure user authentication
- 📚 Document upload (PDF and TXT files)
- 🤖 AI-powered question answering
- 💬 Interactive chat interface with history
- 🔍 Semantic search using Weaviate
- 📊 Document analysis and summarization
- 📝 Source document tracking

## Prerequisites

- Python 3.9 or higher
- OpenAI API key
- Weaviate Cloud account
- Streamlit account (for deployment)

## Installation

1. Clone the repository:
   ```bash
   git clone <your-repository-url>
   cd document-qa-system
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   WEAVIATE_URL=your_weaviate_url
   WEAVIATE_API_KEY=your_weaviate_api_key
   ```

4. Create a `.streamlit/secrets.toml` file with your user credentials:
   ```toml
   [users]
   admin = "your_password_hash"
   ```

## Local Development

Run the app locally:
```bash
streamlit run document_qa_streamlit.py
```

## Deployment

### Option 1: Streamlit Community Cloud (Recommended)

1. Push your code to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Sign in with your GitHub account
4. Click "New app"
5. Select your repository and the main file (`document_qa_streamlit.py`)
6. Add your secrets in the Streamlit Cloud dashboard:
   ```toml
   [users]
   admin = "your_password_hash"
   ```
7. Add your environment variables:
   ```toml
   OPENAI_API_KEY = "your-openai-api-key"
   WEAVIATE_URL = "your-weaviate-url"
   WEAVIATE_API_KEY = "your-weaviate-api-key"
   ```
8. Deploy!

### Option 2: Docker Deployment

1. Build the Docker image:
   ```bash
   docker build -t document-qa-app .
   ```

2. Run the container:
   ```bash
   docker run -p 8501:8501 \
     -e OPENAI_API_KEY=your_openai_api_key \
     -e WEAVIATE_URL=your_weaviate_url \
     -e WEAVIATE_API_KEY=your_weaviate_api_key \
     document-qa-app
   ```

## Usage

1. Access the deployed URL
2. Log in with your credentials:
   - Username: `admin`
   - Password: Your chosen password
3. Upload documents using the sidebar
4. Ask questions about the uploaded documents
5. View AI-generated answers and source documents

## Security Features

- Password hashing using SHA-256
- Secure credential storage in environment variables
- XSRF protection enabled
- Session state management
- Secure logout functionality

## Project Structure

```
document-qa-system/
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml
├── document_qa_streamlit.py
├── weaviateUploader.py
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for GPT models
- Weaviate for vector database
- Streamlit for the web framework 