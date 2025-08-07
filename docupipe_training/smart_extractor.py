#!/usr/bin/env python3
"""
Smart DocuPipe Utility Extractor
Focuses on documents with utility keywords and uses schema generation
"""

import json
import time
import base64
import pandas as pd
from pathlib import Path
from datetime import datetime
import requests

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

class SmartUtilityExtractor:
    """Smart extractor that focuses on utility-relevant documents"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.app_url = "https://app.docupipe.ai"
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-Key": api_key
        }
        
        # Keywords that indicate utility/infrastructure documents
        self.utility_keywords = [
            'pipe', 'manhole', 'invert', 'rim elevation', 'storm', 'sewer',
            'drainage', 'utilities', 'infrastructure', 'swppp', 'storm water',
            'catch basin', 'structure table', 'pipe table', 'utility plan',
            'sanitary', 'water main', 'force main', 'junction box'
        ]
        
        # Schema for utility data extraction
        self.utility_schema = {
            "from_structure_id": "Structure identifier where pipe starts",
            "from_structure_type": "Type of starting structure (manhole, catch basin, etc.)",
            "casting": "Frame and cover specifications", 
            "location": "Physical location or address",
            "rim_elev_ft": "Ground elevation at structure in feet",
            "outlet_invert_elev_ft": "Outlet pipe invert elevation in feet",
            "sump_elev_ft": "Bottom of structure elevation in feet",
            "to_structure_id": "Structure identifier where pipe ends", 
            "inlet_invert_elev_ft": "Inlet pipe invert elevation in feet",
            "pipe_diameter_in": "Pipe diameter in inches",
            "pipe_type": "Pipe classification or type",
            "run_length_ft": "Pipe length in feet",
            "length_in_pvmt_ft": "Length of pipe in pavement in feet",
            "length_in_road_ft": "Length of pipe in roadway in feet",
            "pipe_material": "Pipe material specification"
        }
        
        # Output setup
        self.output_dir = Path("smart_extractions")
        self.output_dir.mkdir(exist_ok=True)
        
        self.successful_extractions = []
        self.skipped_documents = []
        self.failed_documents = []

    def scan_document_for_utility_content(self, pdf_path):
        """Quick scan to check if document likely contains utility data"""
        try:
            log(f"Scanning: {pdf_path.name}")
            
            with open(pdf_path, 'rb') as f:
                file_content = base64.b64encode(f.read()).decode()
            
            payload = {
                "document": {
                    "file": {
                        "contents": file_content,
                        "filename": pdf_path.name
                    }
                },
                "dataset": "utility_scan"
            }
            
            # Upload and process
            response = requests.post(f"{self.app_url}/document", json=payload, headers=self.headers)
            
            if response.status_code != 200:
                log(f"Upload failed: {pdf_path.name}", "WARNING")
                return False, None
            
            upload_result = response.json()
            job_id = upload_result["jobId"]
            doc_id = upload_result["documentId"]
            
            # Wait for processing (shorter timeout for scanning)
            if not self.wait_for_job(job_id, max_wait=120):
                log(f"Processing timeout: {pdf_path.name}", "WARNING")
                return False, None
            
            # Get document text
            response = requests.get(f"{self.app_url}/document/{doc_id}", headers=self.headers)
            
            if response.status_code != 200:
                log(f"Failed to get document: {pdf_path.name}", "WARNING")
                return False, None
            
            doc_data = response.json()
            
            # Extract all text
            full_text = ""
            if "result" in doc_data and "text" in doc_data["result"]:
                full_text = doc_data["result"]["text"]
            
            # Check for utility keywords
            text_lower = full_text.lower()
            found_keywords = [kw for kw in self.utility_keywords if kw in text_lower]
            
            is_utility_doc = len(found_keywords) >= 2  # Need at least 2 utility keywords
            
            log(f"Scan result - {pdf_path.name}: {'UTILITY' if is_utility_doc else 'SKIP'} (keywords: {len(found_keywords)})")
            
            if is_utility_doc:
                return True, {"doc_id": doc_id, "keywords": found_keywords, "text_length": len(full_text)}
            else:
                return False, None
                
        except Exception as e:
            log(f"Scan error {pdf_path.name}: {str(e)}", "ERROR")
            return False, None

    def wait_for_job(self, job_id, max_wait=300):
        """Wait for job completion"""
        for attempt in range(max_wait // 5):
            try:
                response = requests.get(f"{self.app_url}/job/{job_id}", headers=self.headers)
                if response.status_code == 200:
                    status = response.json()["status"]
                    
                    if status == "completed":
                        return True
                    elif status == "error":
                        return False
                    
                    time.sleep(5)
                else:
                    log(f"Status check failed: {response.status_code}", "WARNING")
                    
            except Exception as e:
                log(f"Status check error: {str(e)}", "WARNING")
                
        return False

    def extract_with_schema(self, doc_id, filename):
        """Use DocuPipe schema generation for intelligent extraction"""
        try:
            log(f"Generating schema for: {filename}")
            
            payload = {
                "schemaName": f"utility_extraction_{doc_id[:8]}",
                "documentIds": [doc_id],
                "instructions": """
                Extract structured data from utility infrastructure tables, specifically:
                
                1. PIPE TABLES: Extract pipe specifications including:
                   - Structure connections (from/to structure IDs)
                   - Pipe properties (diameter, material, length)
                   - Elevation data (invert elevations)
                   
                2. STRUCTURE TABLES: Extract structure information including:
                   - Structure IDs and types (manholes, catch basins, etc.)
                   - Elevation data (rim elevation, sump elevation)
                   - Location information
                   
                3. STORM WATER TABLES: Extract SWPPP related data including:
                   - Drainage infrastructure
                   - Storm water management features
                   
                Focus on numerical data like elevations (feet), pipe sizes (inches), and lengths (feet).
                Preserve relationships between connected structures and pipes.
                """,
                "guidelines": """
                - Extract only tabular data, ignore narrative text
                - Include units when specified (ft, in, etc.)
                - Maintain structure-to-structure relationships
                - Extract both pipe and structure information
                - Focus on engineering/construction data
                """,
                "standardizeUsingSchema": True
            }
            
            response = requests.post(f"{self.app_url}/schema/autogenerate", json=payload, headers=self.headers)
            
            if response.status_code != 200:
                log(f"Schema generation failed: {response.status_code}", "ERROR")
                return None
            
            schema_result = response.json()
            schema_job_id = schema_result["jobId"]
            
            # Wait for schema generation
            if not self.wait_for_job(schema_job_id, max_wait=180):
                log(f"Schema generation timeout", "ERROR")
                return None
            
            # Get schema results
            response = requests.get(f"{self.app_url}/schema/autogenerate/{schema_job_id}", headers=self.headers)
            
            if response.status_code != 200:
                log(f"Failed to get schema results: {response.status_code}", "ERROR")
                return None
            
            schema_info = response.json()
            schema_id = schema_info.get("schemaId")
            standardization_ids = schema_info.get("standardizationIds", [])
            
            log(f"Schema generated: {schema_id} with {len(standardization_ids)} standardizations")
            
            # Get standardized data
            extracted_data = []
            for std_id in standardization_ids:
                response = requests.get(f"{self.app_url}/standardization/{std_id}", headers=self.headers)
                
                if response.status_code == 200:
                    std_data = response.json()
                    extracted_data.append(std_data)
                else:
                    log(f"Failed to get standardization {std_id}: {response.status_code}", "WARNING")
            
            return {
                "schema_id": schema_id,
                "standardizations": extracted_data,
                "raw_count": len(extracted_data)
            }
            
        except Exception as e:
            log(f"Schema extraction error: {str(e)}", "ERROR")
            return None

    def process_utility_documents(self, folder_path, max_docs=None):
        """Process utility documents with smart filtering"""
        folder = Path(folder_path)
        pdfs = list(folder.rglob("*.pdf"))
        
        log(f"Found {len(pdfs)} total PDFs")
        
        if max_docs:
            pdfs = pdfs[:max_docs]
            log(f"Processing first {max_docs} documents")
        
        utility_docs = []
        
        # Phase 1: Scan for utility documents
        log("=== PHASE 1: SCANNING FOR UTILITY DOCUMENTS ===")
        
        for i, pdf_path in enumerate(pdfs, 1):
            log(f"[{i}/{len(pdfs)}] Scanning: {pdf_path.name}")
            
            is_utility, scan_info = self.scan_document_for_utility_content(pdf_path)
            
            if is_utility:
                utility_docs.append((pdf_path, scan_info))
                log(f"FOUND utility document: {pdf_path.name}")
            else:
                self.skipped_documents.append(str(pdf_path))
            
            time.sleep(1)  # Rate limiting
        
        log(f"Found {len(utility_docs)} utility documents out of {len(pdfs)} total")
        
        # Phase 2: Extract from utility documents
        if utility_docs:
            log("=== PHASE 2: EXTRACTING FROM UTILITY DOCUMENTS ===")
            
            for i, (pdf_path, scan_info) in enumerate(utility_docs, 1):
                log(f"[{i}/{len(utility_docs)}] Extracting: {pdf_path.name}")
                
                try:
                    extraction_result = self.extract_with_schema(scan_info["doc_id"], pdf_path.name)
                    
                    if extraction_result and extraction_result["standardizations"]:
                        # Process standardizations into structured data
                        structured_data = self.process_standardizations(extraction_result["standardizations"])
                        
                        result = {
                            "filename": pdf_path.name,
                            "doc_id": scan_info["doc_id"],
                            "keywords_found": scan_info["keywords"],
                            "timestamp": datetime.now().isoformat(),
                            "schema_id": extraction_result["schema_id"],
                            "extraction_count": len(structured_data),
                            "data": structured_data
                        }
                        
                        self.successful_extractions.append(result)
                        
                        # Save individual result
                        output_file = self.output_dir / f"{pdf_path.stem}_extraction.json"
                        with open(output_file, 'w') as f:
                            json.dump(result, f, indent=2)
                        
                        log(f"SUCCESS: {pdf_path.name} - {len(structured_data)} records extracted")
                    else:
                        self.failed_documents.append(str(pdf_path))
                        log(f"FAILED: No data extracted from {pdf_path.name}")
                    
                    time.sleep(2)  # Rate limiting
                    
                except Exception as e:
                    self.failed_documents.append(str(pdf_path))
                    log(f"ERROR: {pdf_path.name}: {str(e)}", "ERROR")
        
        # Export results
        self.export_final_results()
        self.print_summary()

    def process_standardizations(self, standardizations):
        """Convert DocuPipe standardizations to structured utility data"""
        structured_data = []
        
        for std in standardizations:
            if isinstance(std, dict):
                # Try different data access patterns
                data = std.get("data", std)
                
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            structured_data.append(self.map_to_utility_schema(item))
                elif isinstance(data, dict):
                    structured_data.append(self.map_to_utility_schema(data))
        
        return [item for item in structured_data if item]  # Remove empty items

    def map_to_utility_schema(self, raw_item):
        """Map raw extraction to utility schema"""
        if not isinstance(raw_item, dict):
            return None
        
        mapped = {}
        
        # Map each schema field
        for schema_field, description in self.utility_schema.items():
            value = None
            
            # Direct field matching
            if schema_field in raw_item:
                value = raw_item[schema_field]
            else:
                # Fuzzy matching
                for key, val in raw_item.items():
                    if isinstance(key, str):
                        key_lower = key.lower()
                        field_parts = schema_field.lower().split('_')
                        
                        # Check if key contains field parts
                        if any(part in key_lower for part in field_parts if len(part) > 2):
                            value = val
                            break
            
            mapped[schema_field] = value
        
        # Include raw data for reference
        mapped["raw_extraction"] = json.dumps(raw_item)
        
        # Only return if has meaningful data
        meaningful_fields = [v for k, v in mapped.items() if k != "raw_extraction" and v is not None]
        
        return mapped if len(meaningful_fields) >= 2 else None

    def export_final_results(self):
        """Export all results to CSV and Excel"""
        if not self.successful_extractions:
            log("No successful extractions to export")
            return
        
        # Combine all data
        all_rows = []
        for extraction in self.successful_extractions:
            for row in extraction["data"]:
                row_with_meta = row.copy()
                row_with_meta["source_filename"] = extraction["filename"]
                row_with_meta["keywords_found"] = ", ".join(extraction["keywords_found"])
                row_with_meta["extraction_timestamp"] = extraction["timestamp"]
                all_rows.append(row_with_meta)
        
        if not all_rows:
            log("No data rows to export")
            return
        
        # Create DataFrame
        df = pd.DataFrame(all_rows)
        
        # Export files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # CSV
        csv_path = self.output_dir / f"smart_utility_extractions_{timestamp}.csv"
        df.to_csv(csv_path, index=False)
        log(f"Exported CSV: {csv_path}")
        
        # Excel with multiple sheets
        excel_path = self.output_dir / f"smart_utility_extractions_{timestamp}.xlsx"
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # All data
            df.to_excel(writer, sheet_name='All_Utility_Data', index=False)
            
            # Summary sheet
            summary_data = []
            for extraction in self.successful_extractions:
                summary_data.append({
                    "Filename": extraction["filename"],
                    "Keywords_Found": ", ".join(extraction["keywords_found"]),
                    "Records_Extracted": extraction["extraction_count"],
                    "Timestamp": extraction["timestamp"]
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Extraction_Summary', index=False)
            
            # Individual document sheets
            for extraction in self.successful_extractions[:10]:  # Limit to first 10
                if extraction["data"]:
                    sheet_name = extraction["filename"][:31].replace('.pdf', '')
                    doc_df = pd.DataFrame(extraction["data"])
                    doc_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        log(f"Exported Excel: {excel_path}")

    def print_summary(self):
        """Print processing summary"""
        total = len(self.successful_extractions) + len(self.skipped_documents) + len(self.failed_documents)
        
        log("=" * 60)
        log("SMART UTILITY EXTRACTION SUMMARY")
        log("=" * 60)
        log(f"Total documents processed: {total}")
        log(f"Utility documents found: {len(self.successful_extractions) + len(self.failed_documents)}")
        log(f"Successful extractions: {len(self.successful_extractions)}")
        log(f"Failed extractions: {len(self.failed_documents)}")
        log(f"Non-utility documents skipped: {len(self.skipped_documents)}")
        
        if self.successful_extractions:
            total_records = sum(ext["extraction_count"] for ext in self.successful_extractions)
            log(f"Total utility records extracted: {total_records}")
            
            # Show sample keywords found
            all_keywords = []
            for ext in self.successful_extractions:
                all_keywords.extend(ext["keywords_found"])
            
            unique_keywords = list(set(all_keywords))
            log(f"Utility keywords found: {', '.join(unique_keywords[:10])}")

def main():
    """Main execution"""
    API_KEY = "EahPwLpsITdU4bZZ9iNSaeu2W7f2"
    civil_plans_folder = r"C:\Users\Zaryab Jibu\Desktop\Python\utility-ai-platform\Civil Plan Sets"
    
    log("Starting Smart Utility DocuPipe Extraction")
    log(f"Folder: {civil_plans_folder}")
    
    extractor = SmartUtilityExtractor(API_KEY)
    
    # Process first 10 documents for testing
    extractor.process_utility_documents(civil_plans_folder, max_docs=10)

if __name__ == "__main__":
    main()
