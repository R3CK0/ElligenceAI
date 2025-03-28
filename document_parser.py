import os
from pathlib import Path
from typing import List, Dict, Optional
import docx
from pptx import Presentation
import tempfile
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json
from datetime import datetime, UTC
import uuid
from pdf_parser import PDFParser
import win32com.client
import pythoncom
import time

class DocumentParser:
    def __init__(self):
        # Google Docs API setup
        self.SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        self.creds = None
        self.service = None
        self._setup_google_docs()
        self.pdf_parser = PDFParser()
    
    def _setup_google_docs(self):
        """Set up Google Docs API credentials."""
        try:
            # Load credentials from secrets
            if os.path.exists('token.json'):
                self.creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                    self.creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open('token.json', 'w') as token:
                    token.write(self.creds.to_json())
            
            self.service = build('docs', 'v1', credentials=self.creds)
        except Exception as e:
            print(f"Warning: Google Docs setup failed: {e}")
            self.service = None
    
    def parse_document(self, file_path: Path, file_type: str) -> List[Dict]:
        """Parse a document based on its type."""
        try:
            if file_type.lower() == '.docx':
                return self._parse_word_doc(file_path)
            elif file_type.lower() == '.txt':
                return self._parse_txt(file_path)
            elif file_type.lower() == '.pptx':
                return self._convert_and_parse_pptx(file_path)
            elif file_type.lower() == '.gdoc':
                return self._parse_google_doc(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        except Exception as e:
            print(f"Error parsing document {file_path}: {e}")
            return []
    
    def _convert_pptx_to_pdf(self, pptx_path: Path) -> Path:
        """Convert PowerPoint to PDF using PowerPoint COM automation."""
        try:
            # Initialize COM
            pythoncom.CoInitialize()
            
            # Create temporary PDF path
            pdf_path = pptx_path.with_suffix('.pdf')
            
            # Create PowerPoint application object
            powerpoint = win32com.client.Dispatch("PowerPoint.Application")
            powerpoint.Visible = True
            
            # Open the presentation
            presentation = powerpoint.Presentations.Open(str(pptx_path.absolute()))
            
            # Save as PDF
            presentation.SaveAs(str(pdf_path.absolute()), 32)  # 32 is the PDF format code
            
            # Close presentation and PowerPoint
            presentation.Close()
            powerpoint.Quit()
            
            # Clean up COM
            pythoncom.CoUninitialize()
            
            return pdf_path
            
        except Exception as e:
            print(f"Error converting PowerPoint to PDF: {e}")
            raise
    
    def _convert_and_parse_pptx(self, pptx_path: Path) -> List[Dict]:
        """Convert PowerPoint to PDF and parse it using PDFParser."""
        try:
            # Convert to PDF
            pdf_path = self._convert_pptx_to_pdf(pptx_path)
            
            # Parse the PDF
            chunks = self.pdf_parser.process_pdf(pdf_path)
            
            # Clean up temporary PDF file
            pdf_path.unlink()
            
            return chunks
            
        except Exception as e:
            print(f"Error processing PowerPoint file: {e}")
            return []
    
    def _create_chunk_with_overlap(self, content: List[str], page_number: int, 
                                 current_word_count: int, max_words_per_chunk: int = 1000,
                                 overlap_words: int = 200) -> List[Dict]:
        """Create chunks with overlap from content."""
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for paragraph in content:
            words = paragraph.split()
            current_word_count += len(words)
            
            if current_word_count >= max_words_per_chunk:
                # Create a new chunk
                chunks.append({
                    "content": " ".join(current_chunk),
                    "page_number": page_number,
                    "uuid": str(uuid.uuid4()),
                    "created_at": datetime.now(UTC).isoformat()
                })
                
                # Keep the last few paragraphs for overlap
                overlap_text = []
                overlap_word_count = 0
                for p in reversed(current_chunk):
                    p_words = p.split()
                    if overlap_word_count + len(p_words) <= overlap_words:
                        overlap_text.insert(0, p)
                        overlap_word_count += len(p_words)
                    else:
                        break
                
                current_chunk = overlap_text
                current_word_count = overlap_word_count
            
            current_chunk.append(paragraph)
        
        # Add the last chunk if it exists
        if current_chunk:
            chunks.append({
                "content": " ".join(current_chunk),
                "page_number": page_number,
                "uuid": str(uuid.uuid4()),
                "created_at": datetime.now(UTC).isoformat()
            })
        
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
    
    def _parse_google_doc(self, file_path: Path) -> List[Dict]:
        """Parse a Google Doc with overlapping chunks."""
        if not self.service:
            raise ValueError("Google Docs service not initialized")
        
        try:
            # Extract document ID from the file path or content
            doc_id = self._extract_doc_id(file_path)
            
            # Get the document content
            document = self.service.documents().get(documentId=doc_id).execute()
            
            # Extract paragraphs
            paragraphs = []
            for element in document.get('body').get('content'):
                if 'paragraph' in element:
                    paragraph = element.get('paragraph')
                    text = self._extract_text_from_paragraph(paragraph)
                    if text.strip():
                        paragraphs.append(text)
            
            return self._create_chunk_with_overlap(paragraphs, 1)
            
        except Exception as e:
            print(f"Error parsing Google Doc: {e}")
            return []
    
    def _extract_text_from_paragraph(self, paragraph: Dict) -> str:
        """Extract text from a Google Docs paragraph element."""
        text = ""
        for element in paragraph.get('elements', []):
            if 'textRun' in element:
                text += element['textRun'].get('content', '')
        return text
    
    def _extract_doc_id(self, file_path: Path) -> str:
        """Extract Google Doc ID from file path or content."""
        with open(file_path, 'r') as f:
            content = f.read()
            return content.strip()

def main():
    # Example usage
    parser = DocumentParser()
    
    # Test with different file types
    test_files = [
        ("example.docx", ".docx"),
        ("example.txt", ".txt"),
        ("example.pptx", ".pptx"),
        ("example.gdoc", ".gdoc")
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
                print(f"Word count: {len(chunk['content'].split())}")
                print(f"Preview: {chunk['content'][:100]}...")

if __name__ == "__main__":
    main() 