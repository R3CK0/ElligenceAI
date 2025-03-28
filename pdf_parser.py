import os
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import fitz  # PyMuPDF
import re
from tqdm import tqdm
from dataclasses import dataclass
from datetime import datetime
import base64
from openai import OpenAI
from dotenv import load_dotenv

@dataclass
class PageContent:
    """Data class to hold page content including text and image."""
    page_number: int
    text: str
    image_path: Optional[str] = None
    image_description: Optional[str] = None

class PDFParser:
    def __init__(self, input_dir: str = "pdfs", output_dir: str = "chunks", image_dir: str = "images"):
        """
        Initialize the PDF parser.
        
        Args:
            input_dir (str): Directory containing PDF files
            output_dir (str): Directory where text chunks will be saved
            image_dir (str): Directory where page images will be saved
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.image_dir = Path(image_dir)
        
        # Create necessary directories
        for directory in [self.output_dir, self.image_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize OpenAI client
        load_dotenv(override=True)
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def convert_page_to_image(self, page: fitz.Page, output_path: Path) -> str:
        """
        Convert a PDF page to an image.
        
        Args:
            page (fitz.Page): PyMuPDF page object
            output_path (Path): Path where the image should be saved
            
        Returns:
            str: Path to the saved image
        """
        # Set zoom factor for better quality
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        
        # Get the page as an image
        pix = page.get_pixmap(matrix=mat)
        
        # Save the image
        pix.save(output_path)
        return str(output_path)
    
    def get_image_description(self, image_path: str, page_text: str) -> str:
        """
        Use OpenAI's vision capabilities to describe the image with context from the page text.
        
        Args:
            image_path (str): Path to the image file
            page_text (str): Text content of the page
            
        Returns:
            str: Generated description of the image
        """
        try:
            # Read the image file
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Prepare the prompt
            prompt = f"""Based on the following page text and the image, provide a detailed description of what you see in the image. 
            Use the page text as context to better understand the image content.
            Focus on visual elements, layout, and any text or diagrams visible in the image. 
            If no meaningful image, diagram, illustration, etc. is visible, simply return a summary.
            The image description should be in the same language as the page text.
            
            Page Text:
            {page_text}
            
            Please describe the image:"""
            
            # Call OpenAI API
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating image description: {str(e)}")
            return "Error generating image description."
    
    def extract_page_content(self, page: fitz.Page, pdf_name: str) -> PageContent:
        """
        Extract text and convert page to image.
        
        Args:
            page (fitz.Page): PyMuPDF page object
            pdf_name (str): Name of the PDF file
            
        Returns:
            PageContent: Object containing page number, text, and image information
        """
        # Extract text
        text = page.get_text().strip()
        
        # Convert page to image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_filename = f"page_{page.number + 1}_{timestamp}_{uuid.uuid4().hex[:8]}.png"
        image_path = self.image_dir / image_filename
        
        # Save the page as an image
        saved_image_path = self.convert_page_to_image(page, image_path)
        
        # Get image description
        image_description = self.get_image_description(saved_image_path, text)
        
        return PageContent(
            page_number=page.number + 1,
            text=text,
            image_path=saved_image_path,
            image_description=image_description
        )
    
    def extract_text_from_pdf(self, pdf_path: Path) -> List[PageContent]:
        """
        Extract text and convert pages to images.
        
        Args:
            pdf_path (Path): Path to the PDF file
            
        Returns:
            List[PageContent]: List of PageContent objects containing text and image information
        """
        pages = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in tqdm(range(len(doc)), desc=f"Processing {pdf_path.name}"):
                page = doc[page_num]
                page_content = self.extract_page_content(page, pdf_path.name)
                pages.append(page_content)
            doc.close()
        except Exception as e:
            print(f"Error processing {pdf_path}: {str(e)}")
        return pages
    
    def create_overlapping_chunks(self, pages: List[PageContent], overlap_percentage: float = 0.2) -> List[Dict[str, any]]:
        """
        Create text chunks with overlap between pages.
        
        Args:
            pages (List[PageContent]): List of pages with their content
            overlap_percentage (float): Percentage of overlap between chunks
            
        Returns:
            List[Dict[str, any]]: List of chunks with their metadata
        """
        chunks = []
        for i in range(len(pages)):
            current_page = pages[i]
            current_text = current_page.text
            
            # Add image description if available
            if current_page.image_description:
                current_text += f"\n\n[Image Description for Page {current_page.page_number}]:\n{current_page.image_description}"
            
            # Calculate overlap size
            words = current_text.split()
            overlap_size = int(len(words) * overlap_percentage)
            
            # Create chunk with current page
            chunk = {
                "uuid": str(uuid.uuid4()),
                "page_number": current_page.page_number,
                "text": current_text,
                "start_word": 0,
                "end_word": len(words),
                "image_path": current_page.image_path
            }
            chunks.append(chunk)
            
            # Add overlap with next page if it exists
            if i < len(pages) - 1:
                next_page = pages[i + 1]
                next_text = next_page.text
                
                # Add image description for next page if available
                if next_page.image_description:
                    next_text += f"\n\n[Image Description for Page {next_page.page_number}]:\n{next_page.image_description}"
                
                next_words = next_text.split()
                
                # Create overlap chunk
                overlap_chunk = {
                    "uuid": str(uuid.uuid4()),
                    "page_number": f"{current_page.page_number}-{next_page.page_number}",
                    "text": " ".join(words[-overlap_size:] + next_words[:overlap_size]),
                    "start_word": len(words) - overlap_size,
                    "end_word": overlap_size,
                    "image_path": None  # No image for overlap chunks
                }
                chunks.append(overlap_chunk)
        
        return chunks
    
    def save_chunks(self, chunks: List[Dict[str, any]], pdf_name: str):
        """
        Save text chunks to files.
        
        Args:
            chunks (List[Dict[str, any]]): List of chunks to save
            pdf_name (str): Name of the original PDF file
        """
        for chunk in chunks:
            # Create filename with UUID
            filename = f"{chunk['uuid']}.txt"
            filepath = self.output_dir / filename
            
            # Prepare metadata
            metadata = {
                "uuid": chunk["uuid"],
                "source_pdf": pdf_name,
                "page_number": chunk["page_number"],
                "start_word": chunk["start_word"],
                "end_word": chunk["end_word"],
                "image_path": chunk["image_path"]
            }
            
            # Save chunk with metadata
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Metadata: {metadata}\n\n")
                f.write(chunk["text"])
    
    def process_pdf(self, pdf_path: Path) -> List[Dict[str, any]]:
        """
        Process a single PDF file.
        
        Args:
            pdf_path (Path): Path to the PDF file
            
        Returns:
            List[Dict[str, any]]: List of processed chunks
        """
        print(f"\nProcessing {pdf_path.name}...")
        
        # Extract text and convert pages to images
        pages = self.extract_text_from_pdf(pdf_path)
        if not pages:
            print(f"No content extracted from {pdf_path.name}")
            return []
        
        # Create overlapping chunks
        chunks = self.create_overlapping_chunks(pages)
        
        # Save chunks
        self.save_chunks(chunks, pdf_path.name)
        print(f"Created {len(chunks)} chunks from {pdf_path.name}")
        
        return chunks
    
    def process_directory(self) -> Dict[str, List[Dict[str, any]]]:
        """
        Process all PDF files in the input directory.
        
        Returns:
            Dict[str, List[Dict[str, any]]]: Dictionary mapping PDF names to their chunks
        """
        pdf_files = list(self.input_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in {self.input_dir}")
            return {}
        
        results = {}
        print(f"Found {len(pdf_files)} PDF files to process")
        for pdf_path in pdf_files:
            chunks = self.process_pdf(pdf_path)
            results[pdf_path.name] = chunks
        
        return results

# def main():
#     # Create parser instance
#     parser = PDFParser()
    
#     # Process all PDFs in the input directory
#     results = parser.process_directory()
    
#     # Print summary
#     for pdf_name, chunks in results.items():
#         print(f"\nSummary for {pdf_name}:")
#         print(f"Total chunks: {len(chunks)}")
#         print(f"Total pages with images: {sum(1 for chunk in chunks if chunk['image_path'] is not None)}")

# if __name__ == "__main__":
#     main() 