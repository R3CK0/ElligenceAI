import os
from pathlib import Path
from typing import List, Dict, Optional
import docx
from pptx import Presentation
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import json
from datetime import datetime, UTC
import uuid
from pdf_parser import PDFParser
import fitz  # PyMuPDF

class DocumentParser:
    def __init__(self):
        # Google Docs API setup
        self.SCOPES = ['https://www.googleapis.com/auth/documents.readonly']
        self.credentials = None
        self.service = None
        self._setup_google_auth()
        self.pdf_parser = PDFParser()
    
    def _setup_google_auth(self):
        """Set up Google Docs API authentication."""
        if os.path.exists('token.json'):
            self.credentials = Credentials.from_authorized_user_file('token.json', self.SCOPES)
        
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                self.credentials = flow.run_local_server(port=0)
            
            with open('token.json', 'w') as token:
                token.write(self.credentials.to_json())
        
        self.service = build('docs', 'v1', credentials=self.credentials)
    
    def parse_document(self, file_path: Path, file_type: str) -> List[Dict]:
        """Parse a document based on its type."""
        try:
            if file_type.lower() == '.docx':
                return self._parse_word_doc(file_path)
            elif file_type.lower() == '.txt':
                return self._parse_txt(file_path)
            elif file_type.lower() == '.pptx':
                return self._parse_pptx(file_path)
            elif file_type.lower() == '.gdoc':
                return self._parse_gdoc(file_path)
            elif file_type.lower() == '.pdf':
                return self._parse_pdf(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        except Exception as e:
            print(f"Error parsing document {file_path}: {e}")
            return []
    
    def _parse_pdf(self, file_path: Path) -> List[Dict]:
        """Parse PDF file using PyMuPDF."""
        chunks = []
        doc = fitz.open(file_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            # Create chunks with overlap
            chunks.extend(self._create_chunk_with_overlap(
                text=text,
                page_number=page_num + 1,
                source_file=file_path.name
            ))
        
        doc.close()
        return chunks
    
    def _parse_pptx(self, file_path: Path) -> List[Dict]:
        """Parse PowerPoint file using python-pptx."""
        chunks = []
        prs = Presentation(file_path)
        
        for slide_num, slide in enumerate(prs.slides, 1):
            # Extract text from all shapes in the slide
            slide_text = []
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    slide_text.append(shape.text)
            
            # Join all text with newlines
            text = "\n".join(slide_text)
            
            # Create chunks with overlap
            chunks.extend(self._create_chunk_with_overlap(
                text=text,
                page_number=slide_num,
                source_file=file_path.name
            ))
        
        return chunks
    
    def _parse_word_doc(self, file_path: Path) -> List[Dict]:
        """Parse a Word document with overlapping chunks."""
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        
        return self._create_chunk_with_overlap(paragraphs, 1)
    
    def _parse_txt(self, file_path: Path) -> List[Dict]:
        """Parse a text file with overlapping chunks."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split content into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        return self._create_chunk_with_overlap(paragraphs, 1)
    
    def _parse_gdoc(self, file_path: Path) -> List[Dict]:
        """Parse Google Doc file."""
        # Extract document ID from the file content
        with open(file_path, 'r') as f:
            doc_data = json.load(f)
            doc_id = doc_data.get('doc_id')
        
        if not doc_id:
            raise ValueError("No document ID found in the Google Doc file")
        
        # Get the document content
        document = self.service.documents().get(documentId=doc_id).execute()
        
        # Extract text content
        text = ""
        for element in document.get('body', {}).get('content', []):
            if 'paragraph' in element:
                for para_element in element['paragraph']['elements']:
                    if 'textRun' in para_element:
                        text += para_element['textRun']['content']
                text += "\n"
        
        return self._create_chunk_with_overlap(
            text=text,
            page_number=1,
            source_file=file_path.name
        )
    
    def _create_chunk_with_overlap(self, text: str, page_number: int, source_file: str) -> List[Dict]:
        """Create chunks with overlap from text."""
        chunks = []
        words = text.split()
        chunk_size = 1000  # words per chunk
        overlap = 200  # words overlap
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            
            chunks.append({
                "content": chunk_text,
                "page_number": page_number,
                "uuid": str(uuid.uuid4()),
                "source_file": source_file,
                "word_count": len(chunk_words),
                "created_at": datetime.now().isoformat()
            })
        
        return chunks

def main():
    # Example usage
    parser = DocumentParser()
    
    # Test with different file types
    test_files = [
        ("example.docx", ".docx"),
        ("example.txt", ".txt"),
        ("example.pptx", ".pptx"),
        ("example.gdoc", ".gdoc"),
        ("example.pdf", ".pdf")
    ]
    
    for file_name, file_type in test_files:
        file_path = Path(file_name)
        if file_path.exists():
            chunks = parser.parse_document(file_path, file_type)
            print(f"\nParsed {file_name}:")
            print(f"Number of chunks: {len(chunks)}")
            for i, chunk in enumerate(chunks, 1):
                print(f"\nChunk {i}:")
                print(f"Page: {chunk['page_number']}")
                print(f"Word count: {chunk['word_count']}")
                print(f"Preview: {chunk['content'][:100]}...")

if __name__ == "__main__":
    main() 