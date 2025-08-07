#!/usr/bin/env python3
"""
Simple DocuPipe batch processor - no Unicode chars for Windows compatibility
"""

import os
import sys
import json
import time
import base64
import pandas as pd
from pathlib import Path
from datetime import datetime
import requests

# Simple logging without Unicode
def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

class SimpleDocuPipeProcessor:
    """Simplified processor for batch extraction"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.app_url = "https://app.docupipe.ai"
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json", 
            "X-API-Key": api_key
        }
        
        # Civil engineering schema
        self.schema_fields = [
            "from_structure_id", "from_structure_type", "casting", "location",
            "rim_elev_ft", "outlet_invert_elev_ft", "sump_elev_ft", 
            "to_structure_id", "inlet_invert_elev_ft", "pipe_diameter_in",
            "pipe_type", "run_length_ft", "length_in_pvmt_ft", 
            "length_in_road_ft", "pipe_material"
        ]
        
        # Create output directories
        self.output_dir = Path("simple_outputs")
        self.output_dir.mkdir(exist_ok=True)
        
        # Track results
        self.results = []
        self.errors = []

    def upload_document(self, pdf_path):
        """Upload PDF to DocuPipe"""
        try:
            log(f"Uploading: {pdf_path.name}")
            
            with open(pdf_path, 'rb') as f:
                file_content = base64.b64encode(f.read()).decode()
            
            payload = {
                "document": {
                    "file": {
                        "contents": file_content,
                        "filename": pdf_path.name
                    }
                },
                "dataset": "utility_extraction"
            }
            
            response = requests.post(f"{self.app_url}/document", json=payload, headers=self.headers)
            
            if response.status_code == 200:
                result = response.json()
                log(f"SUCCESS: Uploaded {pdf_path.name} - Job: {result['jobId']}")
                return result
            else:
                log(f"ERROR: Upload failed {pdf_path.name}: {response.status_code}", "ERROR")
                return None
                
        except Exception as e:
            log(f"ERROR: Upload exception {pdf_path.name}: {str(e)}", "ERROR")
            return None

    def wait_for_job(self, job_id, max_wait=300):
        """Wait for job completion"""
        log(f"Waiting for job: {job_id}")
        
        for attempt in range(max_wait // 5):
            try:
                response = requests.get(f"{self.app_url}/job/{job_id}", headers=self.headers)
                if response.status_code == 200:
                    status = response.json()["status"]
                    
                    if status == "completed":
                        log(f"SUCCESS: Job {job_id} completed")
                        return True
                    elif status == "error":
                        log(f"ERROR: Job {job_id} failed", "ERROR")
                        return False
                    else:
                        log(f"WAITING: Job {job_id} status: {status} (attempt {attempt + 1})")
                        time.sleep(5)
                else:
                    log(f"ERROR: Status check failed for {job_id}: {response.status_code}", "ERROR")
                    
            except Exception as e:
                log(f"ERROR: Status check exception: {str(e)}", "ERROR")
                
        log(f"ERROR: Timeout waiting for job {job_id}", "ERROR")
        return False

    def get_document_data(self, doc_id):
        """Get processed document data"""
        try:
            response = requests.get(f"{self.app_url}/document/{doc_id}", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                log(f"ERROR: Get document failed {doc_id}: {response.status_code}", "ERROR")
                return None
        except Exception as e:
            log(f"ERROR: Get document exception: {str(e)}", "ERROR")
            return None

    def extract_tables_from_data(self, doc_data):
        """Extract table data from document response"""
        extracted_rows = []
        
        if not doc_data or "data" not in doc_data:
            return extracted_rows
        
        # Look for table-like data structures
        data = doc_data.get("data", {})
        
        # Try different data extraction approaches
        if isinstance(data, dict):
            # Check for tables in the data
            for key, value in data.items():
                if "table" in key.lower() or "pipe" in key.lower() or "structure" in key.lower():
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                extracted_rows.append(item)
                    elif isinstance(value, dict):
                        extracted_rows.append(value)
        
        # If no specific tables found, try to extract any structured data
        if not extracted_rows and isinstance(data, dict):
            # Look for any lists of dictionaries
            for value in data.values():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and len(item) > 2:  # Has multiple fields
                            extracted_rows.append(item)
        
        return extracted_rows

    def map_to_schema(self, raw_data):
        """Map extracted data to our schema"""
        mapped_rows = []
        
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            
            mapped_row = {field: None for field in self.schema_fields}
            mapped_row["source_raw"] = json.dumps(item)
            
            # Try to map fields
            for schema_field in self.schema_fields:
                # Direct match
                if schema_field in item:
                    mapped_row[schema_field] = item[schema_field]
                    continue
                
                # Fuzzy matching
                for key, value in item.items():
                    if not isinstance(key, str):
                        continue
                    
                    key_lower = key.lower()
                    field_lower = schema_field.lower()
                    
                    # Check for partial matches
                    if any(word in key_lower for word in field_lower.split('_')):
                        mapped_row[schema_field] = value
                        break
            
            # Only include rows with some meaningful data
            if any(v for k, v in mapped_row.items() if k != "source_raw" and v is not None):
                mapped_rows.append(mapped_row)
        
        return mapped_rows

    def process_pdf(self, pdf_path):
        """Process single PDF through complete pipeline"""
        log(f"PROCESSING: {pdf_path.name}")
        
        try:
            # Step 1: Upload
            upload_result = self.upload_document(pdf_path)
            if not upload_result:
                self.errors.append({"file": str(pdf_path), "error": "Upload failed"})
                return False
            
            # Step 2: Wait for processing
            if not self.wait_for_job(upload_result["jobId"]):
                self.errors.append({"file": str(pdf_path), "error": "Processing failed"})
                return False
            
            # Step 3: Get document data
            doc_data = self.get_document_data(upload_result["documentId"])
            if not doc_data:
                self.errors.append({"file": str(pdf_path), "error": "Data retrieval failed"})
                return False
            
            # Step 4: Extract table data
            raw_tables = self.extract_tables_from_data(doc_data)
            
            if raw_tables:
                # Step 5: Map to schema
                mapped_data = self.map_to_schema(raw_tables)
                
                if mapped_data:
                    # Save result
                    result = {
                        "filename": pdf_path.name,
                        "doc_id": upload_result["documentId"],
                        "timestamp": datetime.now().isoformat(),
                        "raw_count": len(raw_tables),
                        "mapped_count": len(mapped_data),
                        "data": mapped_data
                    }
                    
                    self.results.append(result)
                    
                    # Save individual result
                    output_file = self.output_dir / f"{pdf_path.stem}_extraction.json"
                    with open(output_file, 'w') as f:
                        json.dump(result, f, indent=2)
                    
                    log(f"SUCCESS: {pdf_path.name} - Extracted {len(mapped_data)} rows")
                    return True
            
            self.errors.append({"file": str(pdf_path), "error": "No tables extracted"})
            log(f"WARNING: No tables found in {pdf_path.name}")
            return False
            
        except Exception as e:
            self.errors.append({"file": str(pdf_path), "error": str(e)})
            log(f"ERROR: Processing {pdf_path.name}: {str(e)}", "ERROR")
            return False

    def process_folder(self, folder_path, max_docs=None):
        """Process all PDFs in folder"""
        folder = Path(folder_path)
        if not folder.exists():
            log(f"ERROR: Folder not found: {folder_path}", "ERROR")
            return
        
        pdfs = list(folder.rglob("*.pdf"))
        log(f"Found {len(pdfs)} PDF files")
        
        if max_docs:
            pdfs = pdfs[:max_docs]
            log(f"Processing first {max_docs} documents")
        
        # Process each PDF
        for i, pdf_path in enumerate(pdfs, 1):
            log(f"[{i}/{len(pdfs)}] Processing: {pdf_path.name}")
            
            try:
                self.process_pdf(pdf_path)
                
                # Small delay
                time.sleep(1)
                
                # Export every 3 successful extractions
                if len(self.results) > 0 and len(self.results) % 3 == 0:
                    self.export_results(f"batch_{len(self.results)}")
                
            except Exception as e:
                log(f"ERROR: {pdf_path.name}: {str(e)}", "ERROR")
        
        # Final export
        self.export_results("final")
        self.print_summary()

    def export_results(self, filename_suffix=""):
        """Export results to CSV and Excel"""
        if not self.results:
            log("No results to export")
            return
        
        # Combine all data
        all_rows = []
        for result in self.results:
            for row in result["data"]:
                row_with_meta = row.copy()
                row_with_meta["source_filename"] = result["filename"]
                row_with_meta["extraction_timestamp"] = result["timestamp"]
                all_rows.append(row_with_meta)
        
        if not all_rows:
            log("No data rows to export")
            return
        
        # Create DataFrame
        df = pd.DataFrame(all_rows)
        
        # Export files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"utility_extractions_{filename_suffix}_{timestamp}"
        
        # CSV
        csv_path = self.output_dir / f"{base_name}.csv"
        df.to_csv(csv_path, index=False)
        log(f"Exported CSV: {csv_path}")
        
        # Excel
        excel_path = self.output_dir / f"{base_name}.xlsx"
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='All_Data', index=False)
            
            # Separate sheets by document
            for result in self.results:
                if result["data"]:
                    sheet_name = result["filename"][:31].replace('.pdf', '')
                    doc_df = pd.DataFrame(result["data"])
                    doc_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        log(f"Exported Excel: {excel_path}")

    def print_summary(self):
        """Print processing summary"""
        total = len(self.results) + len(self.errors)
        success_rate = (len(self.results) / total * 100) if total > 0 else 0
        
        log("=" * 50)
        log("PROCESSING SUMMARY")
        log("=" * 50)
        log(f"Total documents processed: {total}")
        log(f"Successful extractions: {len(self.results)}")
        log(f"Failed extractions: {len(self.errors)}")
        log(f"Success rate: {success_rate:.1f}%")
        
        if self.results:
            total_rows = sum(len(r["data"]) for r in self.results)
            log(f"Total data rows extracted: {total_rows}")

def main():
    """Main execution"""
    API_KEY = "EahPwLpsITdU4bZZ9iNSaeu2W7f2"
    civil_plans_folder = r"C:\Users\Zaryab Jibu\Desktop\Python\utility-ai-platform\Civil Plan Sets"
    
    log("Starting Underground Utilities DocuPipe Processing")
    log(f"Folder: {civil_plans_folder}")
    
    processor = SimpleDocuPipeProcessor(API_KEY)
    
    # Process first 3 documents for testing
    processor.process_folder(civil_plans_folder, max_docs=3)

if __name__ == "__main__":
    main()
