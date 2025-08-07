#!/usr/bin/env python3
"""
Final DocuPipe Utility Extractor - Production Ready
Combines AI extraction with pattern matching fallback
"""

import json
import time
import base64
import pandas as pd
import re
from pathlib import Path
from datetime import datetime
import requests

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

class ProductionUtilityExtractor:
    """Production-ready utility data extractor with multiple extraction methods"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.app_url = "https://app.docupipe.ai"
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-Key": api_key
        }
        
        # Utility patterns for text extraction
        self.utility_patterns = {
            'structure_id': r'\b([A-Z]{1,3}[-]?\d{1,4}[A-Z]?)\b',
            'elevation': r'(\d+\.?\d*)\s*["\']?\s*(?:ft|feet|\')',
            'diameter': r'(\d+\.?\d*)\s*["\']?\s*(?:in|inch|")',
            'length': r'(\d+\.?\d*)\s*["\']?\s*(?:ft|feet|lf|\')',
            'pipe_material': r'\b(PVC|HDPE|STEEL|CONCRETE|RCP|DIP|CI|CMP)\b',
            'structure_type': r'\b(MH|MANHOLE|CB|CATCH\s*BASIN|INLET|OUTLET)\b'
        }
        
        # Output setup
        self.output_dir = Path("production_extractions")
        self.output_dir.mkdir(exist_ok=True)
        
        self.results = []

    def extract_from_document(self, pdf_path):
        """Complete extraction pipeline for a single document"""
        try:
            log(f"Processing: {pdf_path.name}")
            
            # Step 1: Upload and get text
            doc_text, doc_id = self.upload_and_get_text(pdf_path)
            
            if not doc_text:
                log(f"Failed to get text from {pdf_path.name}", "WARNING")
                return None
            
            # Check if this is a utility document
            if not self.is_utility_document(doc_text):
                log(f"Skipping non-utility document: {pdf_path.name}")
                return None
            
            log(f"Utility document confirmed: {pdf_path.name}")
            
            # Step 2: Try AI extraction first
            ai_data = self.try_ai_extraction(doc_id, pdf_path.name)
            
            # Step 3: Fallback to pattern extraction
            pattern_data = self.extract_with_patterns(doc_text)
            
            # Step 4: Combine results
            combined_data = self.combine_extractions(ai_data, pattern_data)
            
            if combined_data:
                result = {
                    "filename": pdf_path.name,
                    "doc_id": doc_id,
                    "timestamp": datetime.now().isoformat(),
                    "ai_extraction_count": len(ai_data) if ai_data else 0,
                    "pattern_extraction_count": len(pattern_data),
                    "total_records": len(combined_data),
                    "data": combined_data,
                    "source_text_length": len(doc_text)
                }
                
                self.results.append(result)
                
                # Save individual result
                output_file = self.output_dir / f"{pdf_path.stem}_extraction.json"
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                log(f"SUCCESS: {pdf_path.name} - {len(combined_data)} records extracted")
                return result
            else:
                log(f"No data extracted from {pdf_path.name}")
                return None
                
        except Exception as e:
            log(f"ERROR processing {pdf_path.name}: {str(e)}", "ERROR")
            return None

    def upload_and_get_text(self, pdf_path):
        """Upload PDF and extract text content"""
        try:
            with open(pdf_path, 'rb') as f:
                file_content = base64.b64encode(f.read()).decode()
            
            payload = {
                "document": {
                    "file": {
                        "contents": file_content,
                        "filename": pdf_path.name
                    }
                },
                "dataset": "production_utility"
            }
            
            response = requests.post(f"{self.app_url}/document", json=payload, headers=self.headers)
            
            if response.status_code != 200:
                return None, None
            
            upload_result = response.json()
            job_id = upload_result["jobId"]
            doc_id = upload_result["documentId"]
            
            # Wait for processing
            if not self.wait_for_job(job_id):
                return None, None
            
            # Get document text
            response = requests.get(f"{self.app_url}/document/{doc_id}", headers=self.headers)
            
            if response.status_code == 200:
                doc_data = response.json()
                text = doc_data.get("result", {}).get("text", "")
                return text, doc_id
            
            return None, None
            
        except Exception as e:
            log(f"Upload error: {str(e)}", "ERROR")
            return None, None

    def wait_for_job(self, job_id, max_wait=180):
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
                    
            except Exception:
                pass
                
        return False

    def is_utility_document(self, text):
        """Check if document contains utility infrastructure content"""
        utility_keywords = [
            'pipe', 'manhole', 'invert', 'rim elevation', 'storm', 'sewer',
            'drainage', 'catch basin', 'structure table', 'pipe table',
            'sanitary', 'water main', 'force main', 'swppp'
        ]
        
        text_lower = text.lower()
        found_keywords = [kw for kw in utility_keywords if kw in text_lower]
        
        return len(found_keywords) >= 2

    def try_ai_extraction(self, doc_id, filename):
        """Attempt AI-based extraction with schema generation"""
        try:
            log(f"Attempting AI extraction for: {filename}")
            
            payload = {
                "schemaName": f"utility_prod_{doc_id[:8]}",
                "documentIds": [doc_id],
                "instructions": """
                Extract utility infrastructure data from tables including:
                - Structure IDs and connections
                - Elevation data (rim, invert, sump)
                - Pipe specifications (diameter, material, length)
                - Location information
                
                Focus on numerical data with units (feet, inches).
                """,
                "guidelines": "Extract tabular data only. Include units when specified.",
                "standardizeUsingSchema": True
            }
            
            response = requests.post(f"{self.app_url}/schema/autogenerate", json=payload, headers=self.headers)
            
            if response.status_code != 200:
                return None
            
            schema_result = response.json()
            schema_job_id = schema_result["jobId"]
            
            # Wait for schema generation
            if not self.wait_for_job(schema_job_id, max_wait=120):
                return None
            
            # Get schema results with longer wait for standardizations
            time.sleep(10)  # Additional wait for standardizations
            
            response = requests.get(f"{self.app_url}/schema/autogenerate/{schema_job_id}", headers=self.headers)
            
            if response.status_code == 200:
                schema_info = response.json()
                standardization_ids = schema_info.get("standardizationIds", [])
                
                # Try to get standardizations with retries
                extracted_data = []
                for std_id in standardization_ids:
                    for retry in range(3):
                        time.sleep(5)  # Wait between retries
                        response = requests.get(f"{self.app_url}/standardization/{std_id}", headers=self.headers)
                        
                        if response.status_code == 200:
                            std_data = response.json()
                            if std_data:
                                extracted_data.append(std_data)
                                break
                        elif response.status_code == 404:
                            time.sleep(10)  # Wait longer if not ready
                
                if extracted_data:
                    log(f"AI extraction successful: {len(extracted_data)} standardizations")
                    return self.process_ai_data(extracted_data)
            
            return None
            
        except Exception as e:
            log(f"AI extraction error: {str(e)}", "WARNING")
            return None

    def process_ai_data(self, standardizations):
        """Process AI standardization results"""
        processed_data = []
        
        for std in standardizations:
            if isinstance(std, dict):
                # Extract data from standardization
                data = std.get("data", std)
                
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and len(item) > 1:
                            processed_data.append(self.normalize_ai_item(item))
                elif isinstance(data, dict) and len(data) > 1:
                    processed_data.append(self.normalize_ai_item(data))
        
        return [item for item in processed_data if item]

    def normalize_ai_item(self, item):
        """Normalize AI extracted item to standard format"""
        normalized = {
            "extraction_method": "ai",
            "from_structure_id": None,
            "to_structure_id": None,
            "rim_elev_ft": None,
            "invert_elev_ft": None,
            "pipe_diameter_in": None,
            "pipe_material": None,
            "pipe_length_ft": None,
            "structure_type": None,
            "raw_data": json.dumps(item)
        }
        
        # Map fields from AI extraction
        for key, value in item.items():
            if not isinstance(key, str) or not value:
                continue
            
            key_lower = key.lower()
            
            if 'structure' in key_lower and 'id' in key_lower:
                if 'from' in key_lower or 'start' in key_lower:
                    normalized["from_structure_id"] = str(value)
                elif 'to' in key_lower or 'end' in key_lower:
                    normalized["to_structure_id"] = str(value)
                else:
                    normalized["from_structure_id"] = str(value)
            
            elif 'rim' in key_lower and 'elev' in key_lower:
                normalized["rim_elev_ft"] = self.extract_number(value)
            
            elif 'invert' in key_lower and 'elev' in key_lower:
                normalized["invert_elev_ft"] = self.extract_number(value)
            
            elif 'diameter' in key_lower:
                normalized["pipe_diameter_in"] = self.extract_number(value)
            
            elif 'material' in key_lower:
                normalized["pipe_material"] = str(value)
            
            elif 'length' in key_lower:
                normalized["pipe_length_ft"] = self.extract_number(value)
            
            elif 'type' in key_lower:
                normalized["structure_type"] = str(value)
        
        # Only return if has meaningful data
        meaningful_fields = [v for k, v in normalized.items() if k not in ["extraction_method", "raw_data"] and v is not None]
        return normalized if len(meaningful_fields) >= 2 else None

    def extract_with_patterns(self, text):
        """Extract utility data using regex patterns"""
        extracted_data = []
        
        # Split text into lines for analysis
        lines = text.split('\n')
        
        # Look for table-like structures
        for i, line in enumerate(lines):
            if self.looks_like_data_row(line):
                extracted_item = self.extract_from_line(line)
                if extracted_item:
                    extracted_data.append(extracted_item)
        
        log(f"Pattern extraction found: {len(extracted_data)} items")
        return extracted_data

    def looks_like_data_row(self, line):
        """Check if line looks like a data row with utility information"""
        line = line.strip()
        
        # Skip headers and empty lines
        if not line or len(line) < 10:
            return False
        
        # Look for patterns that suggest utility data
        has_structure_id = bool(re.search(self.utility_patterns['structure_id'], line))
        has_elevation = bool(re.search(self.utility_patterns['elevation'], line))
        has_diameter = bool(re.search(self.utility_patterns['diameter'], line))
        
        # Line should have at least 2 utility indicators
        indicators = sum([has_structure_id, has_elevation, has_diameter])
        
        return indicators >= 2

    def extract_from_line(self, line):
        """Extract utility data from a single line"""
        extracted = {
            "extraction_method": "pattern",
            "from_structure_id": None,
            "to_structure_id": None,
            "rim_elev_ft": None,
            "invert_elev_ft": None,
            "pipe_diameter_in": None,
            "pipe_material": None,
            "pipe_length_ft": None,
            "structure_type": None,
            "source_line": line.strip()
        }
        
        # Extract structure IDs
        structure_matches = re.findall(self.utility_patterns['structure_id'], line)
        if len(structure_matches) >= 2:
            extracted["from_structure_id"] = structure_matches[0]
            extracted["to_structure_id"] = structure_matches[1]
        elif len(structure_matches) == 1:
            extracted["from_structure_id"] = structure_matches[0]
        
        # Extract elevations
        elevation_matches = re.findall(self.utility_patterns['elevation'], line)
        if elevation_matches:
            # First elevation often rim, second often invert
            extracted["rim_elev_ft"] = float(elevation_matches[0])
            if len(elevation_matches) > 1:
                extracted["invert_elev_ft"] = float(elevation_matches[1])
        
        # Extract diameter
        diameter_matches = re.findall(self.utility_patterns['diameter'], line)
        if diameter_matches:
            extracted["pipe_diameter_in"] = float(diameter_matches[0])
        
        # Extract length
        length_matches = re.findall(self.utility_patterns['length'], line)
        if length_matches:
            extracted["pipe_length_ft"] = float(length_matches[0])
        
        # Extract material
        material_matches = re.findall(self.utility_patterns['pipe_material'], line, re.IGNORECASE)
        if material_matches:
            extracted["pipe_material"] = material_matches[0]
        
        # Extract structure type
        type_matches = re.findall(self.utility_patterns['structure_type'], line, re.IGNORECASE)
        if type_matches:
            extracted["structure_type"] = type_matches[0]
        
        # Only return if has meaningful data
        meaningful_fields = [v for k, v in extracted.items() if k not in ["extraction_method", "source_line"] and v is not None]
        return extracted if len(meaningful_fields) >= 2 else None

    def extract_number(self, value):
        """Extract numeric value from string"""
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Extract first number from string
            match = re.search(r'(\d+\.?\d*)', value)
            if match:
                return float(match.group(1))
        
        return None

    def combine_extractions(self, ai_data, pattern_data):
        """Combine AI and pattern extraction results"""
        combined = []
        
        # Add AI data first (higher quality)
        if ai_data:
            combined.extend(ai_data)
        
        # Add pattern data
        if pattern_data:
            combined.extend(pattern_data)
        
        # Remove duplicates based on structure IDs
        seen_structures = set()
        unique_data = []
        
        for item in combined:
            # Create identifier for deduplication
            from_id = item.get("from_structure_id")
            to_id = item.get("to_structure_id")
            identifier = f"{from_id}_{to_id}"
            
            if identifier not in seen_structures:
                seen_structures.add(identifier)
                unique_data.append(item)
        
        return unique_data

    def process_batch(self, folder_path, max_docs=20):
        """Process batch of documents"""
        folder = Path(folder_path)
        pdfs = list(folder.rglob("*.pdf"))
        
        log(f"Found {len(pdfs)} total PDFs")
        
        if max_docs:
            pdfs = pdfs[:max_docs]
            log(f"Processing first {max_docs} documents")
        
        for i, pdf_path in enumerate(pdfs, 1):
            log(f"[{i}/{len(pdfs)}] Processing: {pdf_path.name}")
            
            result = self.extract_from_document(pdf_path)
            
            if result:
                log(f"SUCCESS: {pdf_path.name}")
            
            time.sleep(1)  # Rate limiting
            
            # Export every 5 successful extractions
            if len(self.results) > 0 and len(self.results) % 5 == 0:
                self.export_results(f"batch_{len(self.results)}")
        
        # Final export
        self.export_results("final")
        self.print_summary()

    def export_results(self, suffix=""):
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
            return
        
        # Create DataFrame
        df = pd.DataFrame(all_rows)
        
        # Export files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"utility_extractions_{suffix}_{timestamp}"
        
        # CSV
        csv_path = self.output_dir / f"{base_name}.csv"
        df.to_csv(csv_path, index=False)
        log(f"Exported CSV: {csv_path}")
        
        # Excel
        excel_path = self.output_dir / f"{base_name}.xlsx"
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='All_Data', index=False)
            
            # Separate by extraction method
            ai_data = df[df['extraction_method'] == 'ai']
            pattern_data = df[df['extraction_method'] == 'pattern']
            
            if not ai_data.empty:
                ai_data.to_excel(writer, sheet_name='AI_Extractions', index=False)
            
            if not pattern_data.empty:
                pattern_data.to_excel(writer, sheet_name='Pattern_Extractions', index=False)
        
        log(f"Exported Excel: {excel_path}")

    def print_summary(self):
        """Print processing summary"""
        if not self.results:
            log("No successful extractions")
            return
        
        total_records = sum(len(r["data"]) for r in self.results)
        ai_records = sum(r["ai_extraction_count"] for r in self.results)
        pattern_records = sum(r["pattern_extraction_count"] for r in self.results)
        
        log("=" * 60)
        log("PRODUCTION UTILITY EXTRACTION SUMMARY")
        log("=" * 60)
        log(f"Successful documents: {len(self.results)}")
        log(f"Total utility records: {total_records}")
        log(f"AI extractions: {ai_records}")
        log(f"Pattern extractions: {pattern_records}")
        log(f"Output directory: {self.output_dir}")

def main():
    """Main execution"""
    API_KEY = "EahPwLpsITdU4bZZ9iNSaeu2W7f2"
    civil_plans_folder = r"C:\Users\Zaryab Jibu\Desktop\Python\utility-ai-platform\Civil Plan Sets"
    
    log("Starting Production Utility DocuPipe Extraction")
    
    extractor = ProductionUtilityExtractor(API_KEY)
    
    # Process 15 documents for comprehensive testing
    extractor.process_batch(civil_plans_folder, max_docs=15)

if __name__ == "__main__":
    main()
