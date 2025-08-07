#!/usr/bin/env python3
"""
Enhanced DocuPipe Utility Extractor with Robust Checkpointing
Includes raw PDF storage, quality validation, and comprehensive progress tracking
"""

import json
import time
import base64
import pandas as pd
import re
import shutil
from pathlib import Path
from datetime import datetime
import requests
from typing import Dict, List, Optional, Tuple

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

class RobustUtilityExtractor:
    """Enhanced utility data extractor with comprehensive checkpointing and validation"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.app_url = "https://app.docupipe.ai"
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-Key": api_key
        }
        
        # Enhanced utility patterns with better filtering
        self.utility_patterns = {
            'structure_id': r'\b([A-Z]{1,3}[-]?\d{1,4}[A-Z]?)\b',
            'manhole_id': r'\b(MH[-]?\d{1,4}[A-Z]?)\b',
            'catch_basin_id': r'\b(CB[-]?\d{1,4}[A-Z]?)\b',
            'elevation': r'(\d+\.?\d*)\s*["\']?\s*(?:ft|feet|\')',
            'diameter': r'(\d+\.?\d*)\s*["\']?\s*(?:in|inch|")',
            'length': r'(\d+\.?\d*)\s*["\']?\s*(?:ft|feet|lf|\')',
            'pipe_material': r'\b(PVC|HDPE|STEEL|CONCRETE|RCP|DIP|CI|CMP|CONCRETE|DUCTILE|IRON)\b',
            'structure_type': r'\b(MANHOLE|CATCH\s*BASIN|INLET|OUTLET|JUNCTION\s*BOX)\b',
            'rim_elevation': r'RIM\s*(?:ELEV)?[:\s]*(\d+\.?\d*)',
            'invert_elevation': r'INVERT[:\s]*(\d+\.?\d*)'
        }
        
        # Keywords that suggest NON-utility content (to filter out)
        self.exclusion_keywords = [
            'graphic scale', 'scale', 'fence', 'bollard', 'pavement', 'asphalt',
            'emergency spillway', 'setback', 'temporary easement', 'chainlink'
        ]
        
        # Setup comprehensive directory structure
        self.session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_output_dir = Path("comprehensive_extraction")
        self.base_output_dir.mkdir(exist_ok=True)
        
        self.session_dir = self.base_output_dir / f"session_{self.session_timestamp}"
        self.session_dir.mkdir(exist_ok=True)
        
        # Subdirectories for organized storage
        self.extractions_dir = self.session_dir / "extractions"
        self.raw_pdfs_dir = self.session_dir / "raw_pdfs"
        self.checkpoints_dir = self.session_dir / "checkpoints"
        self.docupipe_responses_dir = self.session_dir / "docupipe_responses"
        self.validation_dir = self.session_dir / "validation"
        
        for dir_path in [self.extractions_dir, self.raw_pdfs_dir, self.checkpoints_dir, 
                        self.docupipe_responses_dir, self.validation_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Comprehensive tracking
        self.session_log = {
            "session_id": self.session_timestamp,
            "start_time": datetime.now().isoformat(),
            "api_key_used": api_key[:8] + "..." + api_key[-4:],  # Masked for security
            "total_pdfs_found": 0,
            "total_pdfs_processed": 0,
            "utility_documents_found": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "skipped_non_utility": 0,
            "processing_errors": 0,
            "total_utility_records": 0,
            "ai_extraction_records": 0,
            "pattern_extraction_records": 0,
            "quality_validated_records": 0,
            "documents_processed": [],
            "error_log": [],
            "quality_issues": []
        }
        
        self.results = []
        self.checkpoint_frequency = 3  # Save checkpoint every 3 successful extractions

    def save_checkpoint(self, force=False):
        """Save comprehensive checkpoint with all session data"""
        if not force and len(self.results) % self.checkpoint_frequency != 0:
            return
        
        checkpoint_data = {
            "checkpoint_timestamp": datetime.now().isoformat(),
            "session_log": self.session_log,
            "current_results": self.results,
            "processing_statistics": self.calculate_statistics(),
            "data_quality_summary": self.assess_data_quality()
        }
        
        checkpoint_file = self.checkpoints_dir / f"checkpoint_{len(self.results)}_extractions.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        log(f"CHECKPOINT: Saved at {len(self.results)} successful extractions")

    def calculate_statistics(self) -> Dict:
        """Calculate comprehensive processing statistics"""
        if not self.results:
            return {"message": "No results to analyze"}
        
        total_records = sum(len(r["data"]) for r in self.results)
        ai_records = sum(r["ai_extraction_count"] for r in self.results)
        pattern_records = sum(r["pattern_extraction_count"] for r in self.results)
        
        avg_records_per_doc = total_records / len(self.results) if self.results else 0
        success_rate = len(self.results) / max(self.session_log["total_pdfs_processed"], 1) * 100
        
        return {
            "total_documents_processed": len(self.results),
            "total_utility_records": total_records,
            "ai_extraction_records": ai_records,
            "pattern_extraction_records": pattern_records,
            "average_records_per_document": round(avg_records_per_doc, 2),
            "extraction_success_rate": round(success_rate, 2),
            "utility_document_detection_rate": round(
                self.session_log["utility_documents_found"] / 
                max(self.session_log["total_pdfs_processed"], 1) * 100, 2
            )
        }

    def assess_data_quality(self) -> Dict:
        """Assess quality of extracted utility data"""
        if not self.results:
            return {"message": "No data to assess"}
        
        quality_metrics = {
            "total_records": 0,
            "records_with_structure_ids": 0,
            "records_with_elevations": 0,
            "records_with_pipe_specs": 0,
            "records_with_materials": 0,
            "complete_records": 0,  # Records with 4+ fields populated
            "potentially_invalid_records": 0
        }
        
        for result in self.results:
            for record in result["data"]:
                quality_metrics["total_records"] += 1
                
                # Check field completeness
                has_structure_id = bool(record.get("from_structure_id") or record.get("to_structure_id"))
                has_elevation = bool(record.get("rim_elev_ft") or record.get("invert_elev_ft"))
                has_pipe_specs = bool(record.get("pipe_diameter_in") or record.get("pipe_length_ft"))
                has_material = bool(record.get("pipe_material"))
                
                if has_structure_id:
                    quality_metrics["records_with_structure_ids"] += 1
                if has_elevation:
                    quality_metrics["records_with_elevations"] += 1
                if has_pipe_specs:
                    quality_metrics["records_with_pipe_specs"] += 1
                if has_material:
                    quality_metrics["records_with_materials"] += 1
                
                # Count complete records (4+ meaningful fields)
                populated_fields = sum([has_structure_id, has_elevation, has_pipe_specs, has_material])
                if populated_fields >= 3:
                    quality_metrics["complete_records"] += 1
                
                # Check for potentially invalid data
                source_line = record.get("source_line", "").lower()
                if any(keyword in source_line for keyword in self.exclusion_keywords):
                    quality_metrics["potentially_invalid_records"] += 1
        
        # Calculate percentages
        total = quality_metrics["total_records"]
        if total > 0:
            quality_metrics["completeness_percentage"] = round(quality_metrics["complete_records"] / total * 100, 2)
            quality_metrics["validity_percentage"] = round((total - quality_metrics["potentially_invalid_records"]) / total * 100, 2)
        
        return quality_metrics

    def store_raw_pdf(self, pdf_path: Path, doc_id: str) -> str:
        """Store copy of processed PDF with metadata"""
        pdf_copy_name = f"{doc_id}_{pdf_path.name}"
        pdf_copy_path = self.raw_pdfs_dir / pdf_copy_name
        
        # Copy PDF file
        shutil.copy2(pdf_path, pdf_copy_path)
        
        # Create metadata file
        metadata = {
            "original_path": str(pdf_path),
            "original_name": pdf_path.name,
            "doc_id": doc_id,
            "file_size_bytes": pdf_path.stat().st_size,
            "processing_timestamp": datetime.now().isoformat(),
            "storage_path": str(pdf_copy_path)
        }
        
        metadata_path = self.raw_pdfs_dir / f"{doc_id}_{pdf_path.stem}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return str(pdf_copy_path)

    def store_docupipe_response(self, doc_id: str, response_data: Dict, response_type: str):
        """Store raw DocuPipe API responses for debugging"""
        response_file = self.docupipe_responses_dir / f"{doc_id}_{response_type}_response.json"
        
        response_metadata = {
            "doc_id": doc_id,
            "response_type": response_type,
            "timestamp": datetime.now().isoformat(),
            "response_data": response_data
        }
        
        with open(response_file, 'w') as f:
            json.dump(response_metadata, f, indent=2)

    def validate_utility_record(self, record: Dict) -> Tuple[bool, List[str]]:
        """Validate if a record contains genuine utility data"""
        issues = []
        is_valid = True
        
        # Check source line for exclusion keywords
        source_line = record.get("source_line", "").lower()
        for keyword in self.exclusion_keywords:
            if keyword in source_line:
                issues.append(f"Contains exclusion keyword: {keyword}")
                is_valid = False
        
        # Check for reasonable elevation values (typically 0-2000 ft)
        rim_elev = record.get("rim_elev_ft")
        invert_elev = record.get("invert_elev_ft")
        
        if rim_elev and (rim_elev < 0 or rim_elev > 2000):
            issues.append(f"Unrealistic rim elevation: {rim_elev}")
            is_valid = False
        
        if invert_elev and (invert_elev < 0 or invert_elev > 2000):
            issues.append(f"Unrealistic invert elevation: {invert_elev}")
            is_valid = False
        
        # Check for reasonable pipe diameter (typically 4-120 inches)
        diameter = record.get("pipe_diameter_in")
        if diameter and (diameter < 2 or diameter > 120):
            issues.append(f"Unrealistic pipe diameter: {diameter}")
            is_valid = False
        
        # Check for meaningful structure IDs (should be alphanumeric)
        from_id = record.get("from_structure_id")
        to_id = record.get("to_structure_id")
        
        if from_id and not re.match(r'^[A-Z0-9-]+$', from_id):
            issues.append(f"Invalid structure ID format: {from_id}")
        
        if to_id and not re.match(r'^[A-Z0-9-]+$', to_id):
            issues.append(f"Invalid structure ID format: {to_id}")
        
        return is_valid, issues

    def enhanced_pattern_extraction(self, text: str) -> List[Dict]:
        """Enhanced pattern extraction with better filtering"""
        extracted_data = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip lines that are clearly not utility data
            if self.is_excluded_line(line):
                continue
            
            if self.looks_like_utility_data(line):
                extracted_item = self.extract_from_line(line)
                if extracted_item:
                    # Validate the extracted item
                    is_valid, issues = self.validate_utility_record(extracted_item)
                    
                    if is_valid:
                        extracted_data.append(extracted_item)
                    else:
                        # Log quality issues
                        self.session_log["quality_issues"].append({
                            "line": line,
                            "issues": issues,
                            "timestamp": datetime.now().isoformat()
                        })
        
        log(f"Enhanced pattern extraction found: {len(extracted_data)} valid items")
        return extracted_data

    def is_excluded_line(self, line: str) -> bool:
        """Check if line should be excluded from extraction"""
        line_lower = line.lower()
        
        # Check for exclusion keywords
        for keyword in self.exclusion_keywords:
            if keyword in line_lower:
                return True
        
        # Skip lines that look like scales, notes, or general text
        exclusion_patterns = [
            r'graphic scale',
            r'\d+\s*in\.\s*=\s*\d+\s*ft',  # Scale patterns
            r'refer to',
            r'sheet [a-z0-9]+',
            r'construction details',
            r'typical',
            r'\(typ\.\)',
            r'emergency spillway',
            r'temporary easement'
        ]
        
        for pattern in exclusion_patterns:
            if re.search(pattern, line_lower):
                return True
        
        return False

    def looks_like_utility_data(self, line: str) -> bool:
        """Enhanced check for utility data with better filtering"""
        if len(line) < 10:
            return False
        
        # Look for utility-specific patterns
        has_manhole = bool(re.search(self.utility_patterns['manhole_id'], line))
        has_catch_basin = bool(re.search(self.utility_patterns['catch_basin_id'], line))
        has_structure_type = bool(re.search(self.utility_patterns['structure_type'], line, re.IGNORECASE))
        has_rim_elevation = bool(re.search(self.utility_patterns['rim_elevation'], line, re.IGNORECASE))
        has_invert_elevation = bool(re.search(self.utility_patterns['invert_elevation'], line, re.IGNORECASE))
        has_pipe_material = bool(re.search(self.utility_patterns['pipe_material'], line, re.IGNORECASE))
        
        # Must have at least 2 strong utility indicators
        strong_indicators = sum([
            has_manhole, has_catch_basin, has_structure_type,
            has_rim_elevation, has_invert_elevation, has_pipe_material
        ])
        
        return strong_indicators >= 2

    def extract_from_line(self, line: str) -> Optional[Dict]:
        """Enhanced line extraction with better field mapping"""
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
        
        # Extract structure IDs with priority for manholes and catch basins
        manhole_matches = re.findall(self.utility_patterns['manhole_id'], line)
        cb_matches = re.findall(self.utility_patterns['catch_basin_id'], line)
        general_matches = re.findall(self.utility_patterns['structure_id'], line)
        
        # Prioritize specific structure types
        all_structure_ids = manhole_matches + cb_matches + general_matches
        if len(all_structure_ids) >= 2:
            extracted["from_structure_id"] = all_structure_ids[0]
            extracted["to_structure_id"] = all_structure_ids[1]
        elif len(all_structure_ids) == 1:
            extracted["from_structure_id"] = all_structure_ids[0]
        
        # Extract rim elevation (specific pattern)
        rim_matches = re.findall(self.utility_patterns['rim_elevation'], line, re.IGNORECASE)
        if rim_matches:
            extracted["rim_elev_ft"] = float(rim_matches[0])
        
        # Extract invert elevation (specific pattern)
        invert_matches = re.findall(self.utility_patterns['invert_elevation'], line, re.IGNORECASE)
        if invert_matches:
            extracted["invert_elev_ft"] = float(invert_matches[0])
        
        # Extract general elevations if specific ones not found
        if not extracted["rim_elev_ft"] and not extracted["invert_elev_ft"]:
            elevation_matches = re.findall(self.utility_patterns['elevation'], line)
            if elevation_matches:
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
        
        # Only return if has meaningful utility data
        meaningful_fields = [
            extracted["from_structure_id"], extracted["to_structure_id"],
            extracted["rim_elev_ft"], extracted["invert_elev_ft"],
            extracted["pipe_diameter_in"], extracted["pipe_material"],
            extracted["structure_type"]
        ]
        
        if sum(1 for field in meaningful_fields if field is not None) >= 2:
            return extracted
        
        return None

    def extract_from_document(self, pdf_path: Path) -> Optional[Dict]:
        """Enhanced document extraction with comprehensive tracking"""
        try:
            log(f"Processing: {pdf_path.name}")
            self.session_log["total_pdfs_processed"] += 1
            
            # Step 1: Upload and get text
            doc_text, doc_id = self.upload_and_get_text(pdf_path)
            
            if not doc_text:
                self.session_log["processing_errors"] += 1
                self.session_log["error_log"].append({
                    "file": str(pdf_path),
                    "error": "Failed to extract text",
                    "timestamp": datetime.now().isoformat()
                })
                return None
            
            # Store raw PDF and DocuPipe response
            pdf_storage_path = self.store_raw_pdf(pdf_path, doc_id)
            
            # Check if this is a utility document
            if not self.is_utility_document(doc_text):
                self.session_log["skipped_non_utility"] += 1
                log(f"Skipping non-utility document: {pdf_path.name}")
                return None
            
            self.session_log["utility_documents_found"] += 1
            log(f"Utility document confirmed: {pdf_path.name}")
            
            # Step 2: Try AI extraction first
            ai_data = self.try_ai_extraction(doc_id, pdf_path.name)
            
            # Step 3: Enhanced pattern extraction
            pattern_data = self.enhanced_pattern_extraction(doc_text)
            
            # Step 4: Combine and validate results
            combined_data = self.combine_extractions(ai_data, pattern_data)
            
            if combined_data:
                # Validate all records
                validated_data = []
                for record in combined_data:
                    is_valid, issues = self.validate_utility_record(record)
                    if is_valid:
                        validated_data.append(record)
                        self.session_log["quality_validated_records"] += 1
                    else:
                        self.session_log["quality_issues"].append({
                            "file": pdf_path.name,
                            "record": record,
                            "issues": issues,
                            "timestamp": datetime.now().isoformat()
                        })
                
                if validated_data:
                    result = {
                        "filename": pdf_path.name,
                        "doc_id": doc_id,
                        "timestamp": datetime.now().isoformat(),
                        "ai_extraction_count": len(ai_data) if ai_data else 0,
                        "pattern_extraction_count": len(pattern_data),
                        "total_records": len(validated_data),
                        "data": validated_data,
                        "source_text_length": len(doc_text),
                        "pdf_storage_path": pdf_storage_path,
                        "data_quality_score": self.calculate_quality_score(validated_data)
                    }
                    
                    self.results.append(result)
                    self.session_log["successful_extractions"] += 1
                    self.session_log["total_utility_records"] += len(validated_data)
                    self.session_log["ai_extraction_records"] += len(ai_data) if ai_data else 0
                    self.session_log["pattern_extraction_records"] += len(pattern_data)
                    
                    # Track processed document
                    self.session_log["documents_processed"].append({
                        "filename": pdf_path.name,
                        "doc_id": doc_id,
                        "timestamp": datetime.now().isoformat(),
                        "records_extracted": len(validated_data),
                        "quality_score": result["data_quality_score"]
                    })
                    
                    # Save individual result
                    output_file = self.extractions_dir / f"{doc_id}_{pdf_path.stem}_extraction.json"
                    with open(output_file, 'w') as f:
                        json.dump(result, f, indent=2)
                    
                    log(f"SUCCESS: {pdf_path.name} - {len(validated_data)} validated records extracted")
                    
                    # Save checkpoint
                    self.save_checkpoint()
                    
                    return result
            
            self.session_log["failed_extractions"] += 1
            log(f"No valid data extracted from {pdf_path.name}")
            return None
            
        except Exception as e:
            self.session_log["processing_errors"] += 1
            error_info = {
                "file": str(pdf_path),
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.session_log["error_log"].append(error_info)
            log(f"ERROR processing {pdf_path.name}: {str(e)}", "ERROR")
            return None

    def calculate_quality_score(self, records: List[Dict]) -> float:
        """Calculate data quality score for extracted records"""
        if not records:
            return 0.0
        
        total_score = 0
        for record in records:
            record_score = 0
            max_score = 10
            
            # Structure IDs (2 points)
            if record.get("from_structure_id"):
                record_score += 1
            if record.get("to_structure_id"):
                record_score += 1
            
            # Elevation data (3 points)
            if record.get("rim_elev_ft"):
                record_score += 1.5
            if record.get("invert_elev_ft"):
                record_score += 1.5
            
            # Pipe specifications (3 points)
            if record.get("pipe_diameter_in"):
                record_score += 1.5
            if record.get("pipe_material"):
                record_score += 1.5
            
            # Structure type (1 point)
            if record.get("structure_type"):
                record_score += 1
            
            # Length information (1 point)
            if record.get("pipe_length_ft"):
                record_score += 1
            
            total_score += (record_score / max_score) * 100
        
        return round(total_score / len(records), 2)

    def upload_and_get_text(self, pdf_path: Path) -> Tuple[Optional[str], Optional[str]]:
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
                "dataset": "robust_utility_extraction"
            }
            
            response = requests.post(f"{self.app_url}/document", json=payload, headers=self.headers)
            
            if response.status_code != 200:
                return None, None
            
            upload_result = response.json()
            job_id = upload_result["jobId"]
            doc_id = upload_result["documentId"]
            
            # Store upload response
            self.store_docupipe_response(doc_id, upload_result, "upload")
            
            # Wait for processing
            if not self.wait_for_job(job_id):
                return None, None
            
            # Get document text
            response = requests.get(f"{self.app_url}/document/{doc_id}", headers=self.headers)
            
            if response.status_code == 200:
                doc_data = response.json()
                
                # Store document response
                self.store_docupipe_response(doc_id, doc_data, "document")
                
                text = doc_data.get("result", {}).get("text", "")
                return text, doc_id
            
            return None, None
            
        except Exception as e:
            log(f"Upload error: {str(e)}", "ERROR")
            return None, None

    def wait_for_job(self, job_id: str, max_wait: int = 180) -> bool:
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

    def is_utility_document(self, text: str) -> bool:
        """Check if document contains utility infrastructure content"""
        utility_keywords = [
            'pipe', 'manhole', 'invert', 'rim elevation', 'storm', 'sewer',
            'drainage', 'catch basin', 'structure table', 'pipe table',
            'sanitary', 'water main', 'force main', 'swppp'
        ]
        
        text_lower = text.lower()
        found_keywords = [kw for kw in utility_keywords if kw in text_lower]
        
        return len(found_keywords) >= 2

    def try_ai_extraction(self, doc_id: str, filename: str) -> Optional[List[Dict]]:
        """Attempt AI-based extraction with schema generation"""
        try:
            log(f"Attempting AI extraction for: {filename}")
            
            payload = {
                "schemaName": f"robust_utility_{doc_id[:8]}",
                "documentIds": [doc_id],
                "instructions": """
                Extract ONLY genuine utility infrastructure data from tables including:
                - Manhole and structure information with IDs
                - Elevation data (rim elevation, invert elevation) 
                - Pipe specifications (diameter, material, length)
                - Structure connections and types
                
                EXCLUDE non-utility data like:
                - Scale information and drawing notes
                - Fence specifications and bollards
                - Pavement and surface details
                - Emergency spillways and setbacks
                
                Focus on numerical elevation data (feet) and pipe specifications (inches).
                """,
                "guidelines": "Extract only tabular utility infrastructure data. Include units when specified. Exclude drawing annotations and non-utility features.",
                "standardizeUsingSchema": True
            }
            
            response = requests.post(f"{self.app_url}/schema/autogenerate", json=payload, headers=self.headers)
            
            if response.status_code != 200:
                return None
            
            schema_result = response.json()
            schema_job_id = schema_result["jobId"]
            
            # Store schema response
            self.store_docupipe_response(doc_id, schema_result, "schema")
            
            # Wait for schema generation
            if not self.wait_for_job(schema_job_id, max_wait=120):
                return None
            
            # Get schema results with retries
            time.sleep(10)
            
            response = requests.get(f"{self.app_url}/schema/autogenerate/{schema_job_id}", headers=self.headers)
            
            if response.status_code == 200:
                schema_info = response.json()
                standardization_ids = schema_info.get("standardizationIds", [])
                
                # Store schema info response
                self.store_docupipe_response(doc_id, schema_info, "schema_info")
                
                # Try to get standardizations with retries
                extracted_data = []
                for std_id in standardization_ids:
                    for retry in range(3):
                        time.sleep(5)
                        response = requests.get(f"{self.app_url}/standardization/{std_id}", headers=self.headers)
                        
                        if response.status_code == 200:
                            std_data = response.json()
                            if std_data:
                                # Store standardization response
                                self.store_docupipe_response(doc_id, std_data, f"standardization_{std_id}")
                                extracted_data.append(std_data)
                                break
                        elif response.status_code == 404:
                            time.sleep(10)
                
                if extracted_data:
                    log(f"AI extraction successful: {len(extracted_data)} standardizations")
                    return self.process_ai_data(extracted_data)
            
            return None
            
        except Exception as e:
            log(f"AI extraction error: {str(e)}", "WARNING")
            return None

    def process_ai_data(self, standardizations: List[Dict]) -> List[Dict]:
        """Process AI standardization results"""
        processed_data = []
        
        for std in standardizations:
            if isinstance(std, dict):
                data = std.get("data", std)
                
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and len(item) > 1:
                            normalized = self.normalize_ai_item(item)
                            if normalized:
                                processed_data.append(normalized)
                elif isinstance(data, dict) and len(data) > 1:
                    normalized = self.normalize_ai_item(data)
                    if normalized:
                        processed_data.append(normalized)
        
        return processed_data

    def normalize_ai_item(self, item: Dict) -> Optional[Dict]:
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

    def extract_number(self, value) -> Optional[float]:
        """Extract numeric value from string"""
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            match = re.search(r'(\d+\.?\d*)', value)
            if match:
                return float(match.group(1))
        
        return None

    def combine_extractions(self, ai_data: Optional[List[Dict]], pattern_data: List[Dict]) -> List[Dict]:
        """Combine AI and pattern extraction results"""
        combined = []
        
        # Add AI data first (higher quality)
        if ai_data:
            combined.extend(ai_data)
        
        # Add pattern data
        if pattern_data:
            combined.extend(pattern_data)
        
        # Remove duplicates based on structure IDs and content similarity
        seen_structures = set()
        unique_data = []
        
        for item in combined:
            from_id = item.get("from_structure_id", "")
            to_id = item.get("to_structure_id", "")
            rim_elev = item.get("rim_elev_ft", "")
            identifier = f"{from_id}_{to_id}_{rim_elev}"
            
            if identifier not in seen_structures:
                seen_structures.add(identifier)
                unique_data.append(item)
        
        return unique_data

    def process_batch(self, folder_path: str, max_docs: Optional[int] = None) -> None:
        """Process batch of documents with comprehensive tracking"""
        folder = Path(folder_path)
        pdfs = list(folder.rglob("*.pdf"))
        
        self.session_log["total_pdfs_found"] = len(pdfs)
        log(f"Found {len(pdfs)} total PDFs")
        
        if max_docs:
            pdfs = pdfs[:max_docs]
            log(f"Processing first {max_docs} documents")
        
        # Save initial checkpoint
        self.save_checkpoint(force=True)
        
        for i, pdf_path in enumerate(pdfs, 1):
            log(f"[{i}/{len(pdfs)}] Processing: {pdf_path.name}")
            
            result = self.extract_from_document(pdf_path)
            
            if result:
                log(f"SUCCESS: {pdf_path.name} - Quality Score: {result['data_quality_score']}%")
            
            time.sleep(1)  # Rate limiting
        
        # Final processing
        self.session_log["end_time"] = datetime.now().isoformat()
        self.finalize_session()

    def finalize_session(self) -> None:
        """Finalize extraction session with comprehensive reporting"""
        log("Finalizing extraction session...")
        
        # Save final checkpoint
        self.save_checkpoint(force=True)
        
        # Export final results
        self.export_comprehensive_results()
        
        # Generate session report
        self.generate_session_report()
        
        log("Session finalization complete!")

    def export_comprehensive_results(self) -> None:
        """Export results in multiple formats with comprehensive metadata"""
        if not self.results:
            log("No results to export")
            return
        
        # Combine all data
        all_rows = []
        for result in self.results:
            for row in result["data"]:
                row_with_meta = row.copy()
                row_with_meta["source_filename"] = result["filename"]
                row_with_meta["doc_id"] = result["doc_id"]
                row_with_meta["extraction_timestamp"] = result["timestamp"]
                row_with_meta["data_quality_score"] = result["data_quality_score"]
                row_with_meta["pdf_storage_path"] = result["pdf_storage_path"]
                all_rows.append(row_with_meta)
        
        if not all_rows:
            return
        
        # Create DataFrame
        df = pd.DataFrame(all_rows)
        
        # Export files
        base_name = f"comprehensive_utility_extractions_{self.session_timestamp}"
        
        # CSV export
        csv_path = self.session_dir / f"{base_name}.csv"
        df.to_csv(csv_path, index=False)
        log(f"Exported comprehensive CSV: {csv_path}")
        
        # Excel export with multiple sheets
        excel_path = self.session_dir / f"{base_name}.xlsx"
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # All data
            df.to_excel(writer, sheet_name='All_Extractions', index=False)
            
            # By extraction method
            ai_data = df[df['extraction_method'] == 'ai']
            pattern_data = df[df['extraction_method'] == 'pattern']
            
            if not ai_data.empty:
                ai_data.to_excel(writer, sheet_name='AI_Extractions', index=False)
            
            if not pattern_data.empty:
                pattern_data.to_excel(writer, sheet_name='Pattern_Extractions', index=False)
            
            # Quality analysis
            high_quality = df[df['data_quality_score'] >= 70]
            if not high_quality.empty:
                high_quality.to_excel(writer, sheet_name='High_Quality_Data', index=False)
            
            # Session statistics
            stats_df = pd.DataFrame([self.calculate_statistics()])
            stats_df.to_excel(writer, sheet_name='Session_Statistics', index=False)
            
            # Document processing summary
            doc_summary = []
            for doc_info in self.session_log["documents_processed"]:
                doc_summary.append(doc_info)
            
            if doc_summary:
                doc_df = pd.DataFrame(doc_summary)
                doc_df.to_excel(writer, sheet_name='Document_Summary', index=False)
        
        log(f"Exported comprehensive Excel: {excel_path}")

    def generate_session_report(self) -> None:
        """Generate comprehensive session report"""
        report = {
            "session_metadata": {
                "session_id": self.session_timestamp,
                "start_time": self.session_log["start_time"],
                "end_time": self.session_log.get("end_time"),
                "total_processing_time": "Calculated in report"
            },
            "processing_summary": self.session_log,
            "statistics": self.calculate_statistics(),
            "quality_assessment": self.assess_data_quality(),
            "error_summary": {
                "total_errors": len(self.session_log["error_log"]),
                "quality_issues": len(self.session_log["quality_issues"]),
                "error_details": self.session_log["error_log"][:10]  # First 10 errors
            },
            "recommendations": self.generate_recommendations()
        }
        
        # Calculate processing time
        if self.session_log.get("end_time"):
            start = datetime.fromisoformat(self.session_log["start_time"])
            end = datetime.fromisoformat(self.session_log["end_time"])
            duration = end - start
            report["session_metadata"]["total_processing_time"] = str(duration)
        
        # Save report
        report_path = self.session_dir / f"session_report_{self.session_timestamp}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        log(f"Session report saved: {report_path}")
        
        # Print summary to console
        self.print_final_summary(report)

    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on processing results"""
        recommendations = []
        
        stats = self.calculate_statistics()
        quality = self.assess_data_quality()
        
        if stats.get("extraction_success_rate", 0) < 50:
            recommendations.append("Consider refining utility document detection keywords")
        
        if quality.get("validity_percentage", 0) < 80:
            recommendations.append("Review pattern extraction rules to reduce false positives")
        
        if stats.get("ai_extraction_records", 0) == 0:
            recommendations.append("Investigate AI extraction issues - no AI data was successfully extracted")
        
        if quality.get("completeness_percentage", 0) < 60:
            recommendations.append("Consider enhancing extraction patterns to capture more complete utility records")
        
        if len(self.session_log["quality_issues"]) > len(self.results) * 2:
            recommendations.append("High number of quality issues detected - review exclusion patterns")
        
        return recommendations

    def print_final_summary(self, report: Dict) -> None:
        """Print comprehensive final summary"""
        stats = report["statistics"]
        quality = report["quality_assessment"]
        
        log("=" * 80)
        log("COMPREHENSIVE UTILITY EXTRACTION SESSION COMPLETE")
        log("=" * 80)
        log(f"Session ID: {self.session_timestamp}")
        log(f"Total PDFs Found: {self.session_log['total_pdfs_found']}")
        log(f"Total PDFs Processed: {self.session_log['total_pdfs_processed']}")
        log(f"Utility Documents Found: {self.session_log['utility_documents_found']}")
        log(f"Successful Extractions: {self.session_log['successful_extractions']}")
        log(f"Total Utility Records: {self.session_log['total_utility_records']}")
        log(f"Quality Validated Records: {self.session_log['quality_validated_records']}")
        log("")
        log("EXTRACTION BREAKDOWN:")
        log(f"AI Extraction Records: {stats.get('ai_extraction_records', 0)}")
        log(f"Pattern Extraction Records: {stats.get('pattern_extraction_records', 0)}")
        log(f"Average Records per Document: {stats.get('average_records_per_document', 0)}")
        log("")
        log("QUALITY METRICS:")
        log(f"Data Completeness: {quality.get('completeness_percentage', 0)}%")
        log(f"Data Validity: {quality.get('validity_percentage', 0)}%")
        log(f"Records with Structure IDs: {quality.get('records_with_structure_ids', 0)}")
        log(f"Records with Elevations: {quality.get('records_with_elevations', 0)}")
        log(f"Records with Pipe Specs: {quality.get('records_with_pipe_specs', 0)}")
        log("")
        log("OUTPUT LOCATIONS:")
        log(f"Session Directory: {self.session_dir}")
        log(f"Extractions: {self.extractions_dir}")
        log(f"Raw PDFs: {self.raw_pdfs_dir}")
        log(f"Checkpoints: {self.checkpoints_dir}")
        log(f"DocuPipe Responses: {self.docupipe_responses_dir}")
        log("=" * 80)

def main():
    """Main execution"""
    API_KEY = "EahPwLpsITdU4bZZ9iNSaeu2W7f2"
    civil_plans_folder = r"C:\Users\Zaryab Jibu\Desktop\Python\utility-ai-platform\Civil Plan Sets"
    
    log("Starting Robust Utility DocuPipe Extraction with Comprehensive Checkpointing")
    
    extractor = RobustUtilityExtractor(API_KEY)
    
    # Process 20 documents for comprehensive testing
    extractor.process_batch(civil_plans_folder, max_docs=20)

if __name__ == "__main__":
    main()
