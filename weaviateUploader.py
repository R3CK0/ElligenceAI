import weaviate
from weaviate.classes.config import Property, DataType, Configure
from weaviate.classes.init import Auth
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime, UTC
import uuid
from openai import OpenAI
import streamlit as st

class WeaviateUploader:
    def __init__(self):
        # Get Weaviate URL and format it correctly
        
        #if not weaviate_url.endswith(".weaviate.cloud"):
        #    weaviate_url = f"https://{weaviate_url}.weaviate.cloud"
        
        # Initialize Weaviate client
        self.client = weaviate.connect_to_weaviate_cloud(
            cluster_url= st.secrets["environment"]["WEAVIATE_URL"],
            auth_credentials=Auth.api_key(st.secrets["environment"]["WEAVIATE_API_KEY"]),
            headers={
                "X-OpenAI-Api-Key": st.secrets["environment"]["OPENAI_API_KEY"]
            }
        )
        
        # Create schema if it doesn't exist
        self._create_schema()
    
    def _create_schema(self):
        """Create the schema for text chunks if it doesn't exist."""
        try:
            # Check if the collection exists
            if not self.client.collections.exists("TextChunk"):
                # Define the schema
                self.client.collections.create(
                    "TextChunk",
                    properties= [
                        Property(
                            name="content",
                            data_type=DataType.TEXT,
                            description="The content of the text chunk"
                        ),
                        Property(
                            name="source_file",
                            data_type=DataType.TEXT,
                            description="The source file name"
                        ),
                        Property(
                            name="page_number",
                            data_type=DataType.INT,
                            description="The page number in the source file"
                        ),
                        Property(
                            name="chunk_uuid",
                            data_type=DataType.TEXT,
                            description="Unique identifier for the chunk"
                        ),
                        Property(
                            name="word_count",
                            data_type=DataType.INT,
                            description="Number of words in the chunk"
                        ),
                        Property(
                            name="created_at",
                            data_type=DataType.DATE,
                            description="When the chunk was created"
                        )
                    ],
                    vectorizer_config= Configure.Vectorizer.text2vec_openai()
                )
                
                print("Created TextChunk collection")
            else:
                print("TextChunk collection already exists")
                
        except Exception as e:
            print(f"Error creating schema: {e}")
            raise
    
    def upload_text_file(self, content: str, source_file: str, page_number: int = 1, chunk_uuid: str = None) -> bool:
        """Upload a text file to Weaviate."""
        try:
            if chunk_uuid is None:
                chunk_uuid = str(uuid.uuid4())
            
            # Prepare the data object
            data_object = {
                "content": content,
                "source_file": source_file,
                "page_number": page_number,
                "chunk_uuid": chunk_uuid,
                "word_count": len(content.split()),
                "created_at": datetime.now(UTC).isoformat()
            }
            
            # Insert the data object
            self.client.collections.get("TextChunk").data.insert(data_object)
            return True
            
        except Exception as e:
            print(f"Error uploading text file: {e}")
            return False
    
    def upload_directory(self, directory_path: str) -> Dict[str, int]:
        """Upload all text files in a directory."""
        results = {"success": 0, "failed": 0}
        directory = Path(directory_path)
        
        for file_path in directory.glob("*.txt"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                if self.upload_text_file(content, file_path.name):
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                results["failed"] += 1
        
        return results
    
    def close(self):
        """Close the Weaviate client connection."""
        if hasattr(self, 'client'):
            self.client.close()

# if __name__ == "__main__":
#     # Example usage
#     uploader = WeaviateUploader()
    
#     # Upload a single file
#     with open("example.txt", "r", encoding="utf-8") as f:
#         content = f.read()
#     uploader.upload_text_file(content, "example.txt")
    
#     # Upload all files in a directory
#     results = uploader.upload_directory("documents")
#     print(f"Upload results: {results}")
    
#     uploader.close() 