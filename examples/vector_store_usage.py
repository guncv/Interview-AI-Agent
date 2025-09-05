#!/usr/bin/env python3
"""
Example script demonstrating how to use the vector store factory pattern.

This script shows:
1. How to use the factory to create different vector stores
2. How to store and search documents
3. How to switch between Chroma and Pinecone
"""

import os
import sys
from typing import List

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from internal.adapters.vector_db.factory import get_vector_store
from internal.adapters.vector_db.embedder import create_embedder
from internal.service.vector_service import VectorService

def example_direct_factory_usage():
    """Example of using the factory directly."""
    print("=== Direct Factory Usage Example ===")
    
    # Create an embedder
    embedder = create_embedder(
        api_key="your-openai-api-key",  # Replace with actual key
        model="text-embedding-3-small"
    )
    
    # Create Chroma vector store
    print("Creating Chroma vector store...")
    chroma_store = get_vector_store(
        kind="chroma",
        embedder=embedder,
        collection_name="example_collection",
        persist_directory="./example_chroma"
    )
    
    # Add some documents
    documents = [
        "Python is a programming language",
        "Machine learning uses algorithms to learn from data",
        "Vector databases store embeddings for similarity search"
    ]
    
    ids = ["doc1", "doc2", "doc3"]
    metadatas = [
        {"topic": "programming", "language": "python"},
        {"topic": "ai", "type": "machine_learning"},
        {"topic": "database", "type": "vector"}
    ]
    
    chroma_store.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    print(f"Added {chroma_store.count()} documents to Chroma")
    
    # Search for similar documents
    results = chroma_store.query_by_text("What is Python?", k=2)
    print(f"Search results for 'What is Python?':")
    for item in results.items:
        print(f"  - {item.document} (score: {item.score})")
    
    # Clean up
    chroma_store.close()

def example_vector_service_usage():
    """Example of using the VectorService wrapper."""
    print("\n=== Vector Service Usage Example ===")
    
    # The VectorService automatically uses the factory and config
    # Make sure to set VECTOR_DB environment variable or update config
    try:
        vector_service = VectorService()
        
        # Add documents
        documents = [
            "Software engineering involves designing and building software systems",
            "Data science combines statistics, programming, and domain expertise",
            "DevOps focuses on automation and collaboration between teams"
        ]
        
        vector_service.add_documents(
            ids=["eng1", "ds1", "devops1"],
            documents=documents,
            metadatas=[
                {"field": "software_engineering", "level": "intermediate"},
                {"field": "data_science", "level": "advanced"},
                {"field": "devops", "level": "intermediate"}
            ]
        )
        
        print(f"Added {vector_service.get_document_count()} documents")
        
        # Search
        results = vector_service.search_by_text("What is software engineering?", k=2)
        print(f"Search results:")
        for item in results.items:
            print(f"  - {item.document} (score: {item.score})")
        
        # Clean up
        vector_service.close()
        
    except Exception as e:
        print(f"Error with VectorService: {e}")
        print("Make sure to set up your environment variables and config properly")

def example_environment_switching():
    """Example of switching between vector stores using environment variables."""
    print("\n=== Environment Switching Example ===")
    
    # Set environment variable to switch vector stores
    os.environ["VECTOR_DB"] = "chroma"  # or "pinecone"
    
    # The factory will automatically use the environment variable
    try:
        store = get_vector_store(
            embedder=create_embedder("your-api-key"),
            collection_name="env_test"
        )
        print(f"Created {type(store).__name__} vector store")
        store.close()
    except Exception as e:
        print(f"Error creating vector store: {e}")

if __name__ == "__main__":
    print("Vector Store Factory Pattern Examples")
    print("=" * 50)
    
    # Note: These examples require proper API keys and configuration
    print("Note: Make sure to set up your OpenAI API key and vector store configuration")
    print()
    
    # Run examples
    example_direct_factory_usage()
    example_vector_service_usage()
    example_environment_switching()
    
    print("\n" + "=" * 50)
    print("Examples completed!")
    print("\nTo use in your application:")
    print("1. Set VECTOR_DB environment variable (chroma or pinecone)")
    print("2. Configure your API keys in the config file")
    print("3. Use VectorService for easy integration")
    print("4. Or use get_vector_store() directly for more control")
