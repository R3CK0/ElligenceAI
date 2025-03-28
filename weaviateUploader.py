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
import hashlib

class WeaviateUploader:
    def __init__(self, collection_name: str = "TextChunk"):
        """
        Initialize the Weaviate uploader.
        
        Args:
            collection_name (str): Name of the Weaviate collection to use
        """
        # Load environment variables
        load_dotenv(override=True)
        
        # Initialize Weaviate client with cloud connection
        self.client = weaviate.connect_to_weaviate_cloud(
            cluster_url=os.getenv("WEAVIATE_URL"),
            auth_credentials=Auth.api_key(os.getenv("WEAVIATE_API_KEY")),
            headers={
                "X-OpenAI-Api-Key": os.getenv("OPENAI_API_KEY")
            }
        )
        
        self.collection_name = collection_name
        self._create_schema()
    
    def _create_schema(self):
        """Create the Weaviate schema if it doesn't exist."""
        try:
            # Check if collection exists
            collections = self.client.collections.list_all()
            collection_names = [collection.name for collection in collections]
            
            if self.collection_name not in collection_names:
                # Define the schema
                class_obj = {
                    "class": self.collection_name,
                    "description": "A collection of text chunks with their metadata",
                    "vectorizer": "text2vec-openai",
                    "vectorIndexConfig": {
                        "distance": "cosine"
                    },
                    "properties": [
                        Property(
                            name="content",
                            data_type=DataType.TEXT,
                            description="The text content of the chunk"
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
                    ]
                }
                
                # Create the collection
                self.client.collections.create(class_obj)
                print(f"Created collection: {self.collection_name}")
            else:
                print(f"Collection {self.collection_name} already exists")
        
        except Exception as e:
            print(f"Error creating schema: {str(e)}")
            raise
    
    def upload_text_file(self, file_path: Path, metadata: Optional[Dict] = None) -> bool:
        """
        Upload a text file to Weaviate.
        
        Args:
            file_path (Path): Path to the text file
            metadata (Dict, optional): Additional metadata to include
            
        Returns:
            bool: True if upload was successful, False otherwise
        """
        try:
            # Read the text file
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Extract metadata from file name if not provided
            if metadata is None:
                metadata = {}
            
            # Add basic metadata
            metadata.update({
                "source_file": file_path.name,
                "created_at": datetime.now().isoformat(),
                "word_count": len(content.split())
            })
            
            # Generate a UUID for the chunk
            chunk_uuid = str(uuid.uuid4())
            metadata["chunk_uuid"] = chunk_uuid
            
            # Upload to Weaviate
            self.client.collections.get(self.collection_name).data.insert({
                "content": content,
                **metadata
            })
            
            print(f"Successfully uploaded {file_path.name}")
            return True
            
        except Exception as e:
            print(f"Error uploading {file_path.name}: {str(e)}")
            return False
    
    def upload_directory(self, directory_path: Path, pattern: str = "*.txt") -> Dict[str, bool]:
        """
        Upload all text files in a directory to Weaviate.
        
        Args:
            directory_path (Path): Path to the directory containing text files
            pattern (str): File pattern to match (default: "*.txt")
            
        Returns:
            Dict[str, bool]: Dictionary mapping file names to upload success status
        """
        results = {}
        directory = Path(directory_path)
        
        if not directory.exists():
            print(f"Directory not found: {directory}")
            return results
        
        # Process all matching files
        for file_path in directory.glob(pattern):
            success = self.upload_text_file(file_path)
            results[file_path.name] = success
        
        return results
    
    def close(self):
        """Close the Weaviate client connection."""
        self.client.close()

def main():
    # Example usage
    uploader = WeaviateUploader()
    
    try:
        # Upload a single file
        file_path = Path("test_processed/page_content/page_001.txt")
        if file_path.exists():
            success = uploader.upload_text_file(file_path)
            print(f"Upload success: {success}")
        
        # Upload all files in a directory
        directory_path = Path("test_processed/page_content")
        if directory_path.exists():
            results = uploader.upload_directory(directory_path)
            print("\nUpload Results:")
            for file_name, success in results.items():
                print(f"{file_name}: {'Success' if success else 'Failed'}")
    
    finally:
        uploader.close()

if __name__ == "__main__":
    #main()

    password = "elligenceAI"
    hash = hashlib.sha256(password.encode()).hexdigest()
    print(hash) 