#!/usr/bin/env python3
"""
Real-time DocuPipe inspection
Upload a small PDF and immediately inspect what we get back
"""

import json
import time
import base64
import requests
from pathlib import Path

def inspect_docupipe_workflow():
    """Upload and inspect a document in real-time"""
    
    API_KEY = "EahPwLpsITdU4bZZ9iNSaeu2W7f2"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-API-Key": API_KEY
    }
    
    # Find a small PDF to test with
    civil_plans_folder = Path(r"C:\Users\Zaryab Jibu\Desktop\Python\utility-ai-platform\Civil Plan Sets")
    pdfs = list(civil_plans_folder.rglob("*.pdf"))
    
    if not pdfs:
        print("No PDFs found")
        return
    
    # Use the first PDF
    test_pdf = pdfs[0]
    print(f"Testing with: {test_pdf.name}")
    
    try:
        # Step 1: Upload
        print("Step 1: Uploading document...")
        
        with open(test_pdf, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode()
        
        payload = {
            "document": {
                "file": {
                    "contents": file_content,
                    "filename": test_pdf.name
                }
            },
            "dataset": "debug_test"
        }
        
        response = requests.post("https://app.docupipe.ai/document", json=payload, headers=headers)
        
        if response.status_code != 200:
            print(f"Upload failed: {response.status_code}")
            print(response.text)
            return
        
        upload_result = response.json()
        doc_id = upload_result["documentId"]
        job_id = upload_result["jobId"]
        
        print(f"Upload successful - Doc ID: {doc_id}, Job ID: {job_id}")
        
        # Step 2: Wait for processing
        print("Step 2: Waiting for processing...")
        
        max_attempts = 60  # 5 minutes max
        for attempt in range(max_attempts):
            response = requests.get(f"https://app.docupipe.ai/job/{job_id}", headers=headers)
            
            if response.status_code == 200:
                status = response.json()["status"]
                print(f"  Status: {status} (attempt {attempt + 1})")
                
                if status == "completed":
                    print("Processing completed!")
                    break
                elif status == "error":
                    print("Processing failed!")
                    return
                
                time.sleep(5)
            else:
                print(f"Status check failed: {response.status_code}")
                
        else:
            print("Timeout waiting for processing")
            return
        
        # Step 3: Get document data and inspect
        print("\nStep 3: Retrieving document data...")
        
        response = requests.get(f"https://app.docupipe.ai/document/{doc_id}", headers=headers)
        
        if response.status_code == 200:
            doc_data = response.json()
            
            # Save full response
            with open("full_docupipe_response.json", "w") as f:
                json.dump(doc_data, f, indent=2)
            
            print("Full response saved to full_docupipe_response.json")
            
            # Analyze structure
            print("\n=== DOCUMENT DATA STRUCTURE ===")
            
            def analyze_structure(obj, path="", max_depth=3, current_depth=0):
                if current_depth > max_depth:
                    return
                
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        
                        if isinstance(value, (dict, list)):
                            size = len(value) if hasattr(value, '__len__') else 0
                            print(f"  {current_path}: {type(value).__name__} (size: {size})")
                            
                            # Show first few keys/items for dicts and lists
                            if isinstance(value, dict) and size > 0:
                                sample_keys = list(value.keys())[:3]
                                print(f"    Sample keys: {sample_keys}")
                            elif isinstance(value, list) and size > 0:
                                print(f"    First item type: {type(value[0]).__name__}")
                            
                            if current_depth < max_depth:
                                analyze_structure(value, current_path, max_depth, current_depth + 1)
                        else:
                            value_str = str(value)[:100] if value else "None"
                            print(f"  {current_path}: {type(value).__name__} = {value_str}")
                
                elif isinstance(obj, list):
                    print(f"{path}: List with {len(obj)} items")
                    if obj:
                        print(f"  First item type: {type(obj[0]).__name__}")
                        if len(obj) > 0:
                            analyze_structure(obj[0], f"{path}[0]", max_depth, current_depth + 1)
            
            analyze_structure(doc_data)
            
            # Look for text content specifically
            print("\n=== SEARCHING FOR TEXT CONTENT ===")
            
            def find_text_content(obj, path=""):
                results = []
                
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        
                        if isinstance(value, str) and len(value) > 50:
                            results.append({
                                "path": current_path,
                                "length": len(value),
                                "preview": value[:200]
                            })
                        elif isinstance(value, (dict, list)):
                            results.extend(find_text_content(value, current_path))
                
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        results.extend(find_text_content(item, f"{path}[{i}]"))
                
                return results
            
            text_content = find_text_content(doc_data)
            
            if text_content:
                print("Found text content:")
                for item in text_content:
                    print(f"  {item['path']}: {item['length']} chars")
                    print(f"    Preview: {item['preview'][:100]}...")
            else:
                print("No significant text content found")
            
            print("\n=== COMPLETE ===")
            print(f"Check full_docupipe_response.json for detailed inspection")
            
        else:
            print(f"Failed to get document: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    inspect_docupipe_workflow()
