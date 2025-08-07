#!/usr/bin/env python3
"""
Debug DocuPipe responses to understand data structure
"""

import json
import requests
from pathlib import Path

def debug_docupipe_response():
    """Check what DocuPipe returns for a processed document"""
    
    API_KEY = "EahPwLpsITdU4bZZ9iNSaeu2W7f2"
    headers = {
        "accept": "application/json",
        "X-API-Key": API_KEY
    }
    
    # Use a recent document ID from the processing above
    # Let's check the last processed document
    doc_id = "ARWzz6Hh"  # From the last upload (1. Architectural Drawings A1.1.pdf)
    
    print(f"Debugging document: {doc_id}")
    
    try:
        # Get document data
        response = requests.get(f"https://app.docupipe.ai/document/{doc_id}", headers=headers)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Save full response for inspection
            with open("debug_response.json", "w") as f:
                json.dump(data, f, indent=2)
            
            print("Full response saved to debug_response.json")
            
            # Print structure overview
            print("\nResponse structure:")
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        print(f"  {key}: {type(value).__name__} (length: {len(value) if hasattr(value, '__len__') else 'N/A'})")
                    else:
                        print(f"  {key}: {type(value).__name__} = {str(value)[:100]}")
            
            # Look for text content
            if "data" in data:
                print(f"\nData section type: {type(data['data'])}")
                if isinstance(data["data"], dict):
                    print("Data keys:", list(data["data"].keys()))
                elif isinstance(data["data"], str):
                    print("Data content preview:", data["data"][:500])
            
            # Check for OCR or extracted text
            text_fields = ["text", "content", "extracted_text", "ocr_text", "raw_text"]
            for field in text_fields:
                if field in data:
                    print(f"\nFound {field}: {len(str(data[field]))} characters")
                    if isinstance(data[field], str):
                        print(f"Preview: {data[field][:200]}...")
        
        else:
            print(f"Error response: {response.text}")
    
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    debug_docupipe_response()
