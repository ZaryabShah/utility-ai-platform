#!/usr/bin/env python3
"""
Underground Utilities AI Training with DocuPipe
Extracts structured table data from civil engineering PDFs for AI training
"""

import os
import json
import time
import base64
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('docupipe_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DocuPipeTrainer:
    """Extracts structured data from utility PDFs using DocuPipe API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.app_url = "https://app.docupipe.ai"
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-Key": api_key
        }
        
        # Civil engineering schema mapping
        self.field_schema = {
            "from_structure_id": ["from_structure_id", "from_structure", "upstream_id", "manhole_from"],
            "from_structure_type": ["from_structure_type", "structure_type", "upstream_type", "type"],
            "casting": ["casting", "frame_cover", "frame", "cover", "frame_and_cover"],
            "location": ["location", "address", "coordinates", "position"],
            "rim_elev_ft": ["rim_elev_ft", "rim_elevation", "rim_elev", "ground_elevation"],
            "outlet_invert_elev_ft": ["outlet_invert_elev_ft", "outlet_invert", "invert_out", "outlet_elevation"],
            "sump_elev_ft": ["sump_elev_ft", "sump_elevation", "sump_depth", "bottom_elevation"],
            "to_structure_id": ["to_structure_id", "to_structure", "downstream_id", "manhole_to"],
            "inlet_invert_elev_ft": ["inlet_invert_elev_ft", "inlet_invert", "invert_in", "inlet_elevation"],
            "pipe_diameter_in": ["pipe_diameter_in", "diameter", "pipe_size", "size_inches"],
            "pipe_type": ["pipe_type", "pipe_class", "classification", "material_type"],
            "run_length_ft": ["run_length_ft", "length", "pipe_length", "distance"],
            "length_in_pvmt_ft": ["length_in_pvmt_ft", "pavement_length", "in_pavement", "pvmt_length"],
            "length_in_road_ft": ["length_in_road_ft", "road_length", "in_roadway", "roadway_length"],
            "pipe_material": ["pipe_material", "material", "pipe_spec", "specification"]
        }
        
        # Create output directories
        self.output_dir = Path("docupipe_outputs")
        self.checkpoints_dir = self.output_dir / "checkpoints"
        self.csv_dir = self.output_dir / "csv_exports"
        self.logs_dir = self.output_dir / "processing_logs"
        
        for dir_path in [self.output_dir, self.checkpoints_dir, self.csv_dir, self.logs_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Track processing
        self.processed_docs = []
        self.successful_extractions = []
        self.failed_extractions = []

    def discover_pdfs(self, folder_path: str) -> List[Path]:
        """Find all PDF files in the given folder"""
        folder = Path(folder_path)
        if not folder.exists():
            logger.error(f"Folder not found: {folder_path}")
            return []
        
        pdfs = list(folder.rglob("*.pdf"))
        logger.info(f"Found {len(pdfs)} PDF files in {folder_path}")
        return pdfs

    def upload_document(self, pdf_path: Path, dataset_name: str = "utility_training") -> Optional[Dict]:
        """Upload a PDF to DocuPipe for processing"""
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
                "dataset": dataset_name
            }
            
            url = f"{self.app_url}/document"
            response = requests.post(url, json=payload, headers=self.headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Uploaded {pdf_path.name} - Job ID: {result['jobId']}")
                return {
                    "job_id": result["jobId"],
                    "doc_id": result["documentId"],
                    "filename": pdf_path.name,
                    "filepath": str(pdf_path)
                }
            else:
                logger.error(f"❌ Failed to upload {pdf_path.name}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error uploading {pdf_path.name}: {str(e)}")
            return None

    def wait_for_processing(self, job_id: str, max_wait: int = 300) -> bool:
        """Wait for DocuPipe to finish processing a document"""
        url = f"{self.app_url}/job/{job_id}"
        
        for attempt in range(max_wait // 5):
            try:
                response = requests.get(url, headers=self.headers)
                if response.status_code == 200:
                    status = response.json()["status"]
                    
                    if status == "completed":
                        logger.info(f"✅ Job {job_id} completed")
                        return True
                    elif status == "error":
                        logger.error(f"❌ Job {job_id} failed")
                        return False
                    
                    logger.info(f"⏳ Job {job_id} status: {status} (attempt {attempt + 1})")
                    time.sleep(5)
                else:
                    logger.warning(f"⚠️  Failed to check status for job {job_id}")
                    
            except Exception as e:
                logger.error(f"❌ Error checking job status: {str(e)}")
                
        logger.error(f"❌ Timeout waiting for job {job_id}")
        return False

    def get_document_results(self, doc_id: str) -> Optional[Dict]:
        """Retrieve processed document results from DocuPipe"""
        try:
            url = f"{self.app_url}/document/{doc_id}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Failed to get document {doc_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error retrieving document {doc_id}: {str(e)}")
            return None

    def create_schema_for_doc(self, doc_id: str) -> Optional[str]:
        """Auto-generate a schema for the document to extract table data"""
        try:
            url = f"{self.app_url}/schema/autogenerate"
            payload = {
                "schemaName": f"utility_tables_{doc_id[:8]}",
                "documentIds": [doc_id],
                "instructions": """
                Extract structured data from utility engineering tables including:
                - Pipe tables with structure IDs, elevations, pipe specifications
                - Storm drainage tables with manholes, invert elevations, pipe materials
                - SWPPP (Storm Water Pollution Prevention Plan) tables
                - Focus on tables with numerical data like elevations, pipe sizes, lengths
                - Preserve the tabular structure and relationships between fields
                """,
                "guidelines": """
                - Extract data from tables only, ignore non-tabular text
                - Maintain relationships between connected structures
                - Include units where specified (feet, inches, etc.)
                - Handle both pipe and structure information
                """,
                "standardizeUsingSchema": True
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            
            if response.status_code == 200:
                result = response.json()
                schema_job_id = result["jobId"]
                
                # Wait for schema generation
                if self.wait_for_processing(schema_job_id, max_wait=180):
                    # Get the completed schema job
                    schema_url = f"{self.app_url}/schema/autogenerate/{schema_job_id}"
                    schema_response = requests.get(schema_url, headers=self.headers)
                    
                    if schema_response.status_code == 200:
                        schema_result = schema_response.json()
                        schema_id = schema_result.get("schemaId")
                        standardization_ids = schema_result.get("standardizationIds", [])
                        
                        logger.info(f"✅ Generated schema {schema_id} for document {doc_id}")
                        return {
                            "schema_id": schema_id,
                            "standardization_ids": standardization_ids
                        }
                        
            logger.error(f"❌ Failed to generate schema for document {doc_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error generating schema: {str(e)}")
            return None

    def get_standardization_results(self, std_id: str) -> Optional[Dict]:
        """Get standardized data extraction results"""
        try:
            url = f"{self.app_url}/standardization/{std_id}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Failed to get standardization {std_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error retrieving standardization: {str(e)}")
            return None

    def map_to_schema(self, extracted_data: Dict) -> List[Dict]:
        """Map extracted data to our predefined civil engineering schema"""
        mapped_rows = []
        
        if not isinstance(extracted_data, dict):
            return mapped_rows
        
        # Handle different data structures that DocuPipe might return
        data_to_process = []
        
        if "data" in extracted_data:
            data_to_process = extracted_data["data"]
        elif isinstance(extracted_data, list):
            data_to_process = extracted_data
        elif isinstance(extracted_data, dict):
            data_to_process = [extracted_data]
        
        if not isinstance(data_to_process, list):
            data_to_process = [data_to_process]
        
        for item in data_to_process:
            if not isinstance(item, dict):
                continue
                
            mapped_row = {}
            
            # Map each field in our schema
            for target_field, possible_keys in self.field_schema.items():
                value = None
                
                # Try to find the value using different possible key names
                for key in possible_keys:
                    if key in item:
                        value = item[key]
                        break
                    
                    # Try case-insensitive matching
                    for item_key in item.keys():
                        if isinstance(item_key, str) and key.lower() in item_key.lower():
                            value = item[item_key]
                            break
                    
                    if value is not None:
                        break
                
                mapped_row[target_field] = value
            
            # Only add rows that have some meaningful data
            if any(mapped_row.values()):
                mapped_rows.append(mapped_row)
        
        return mapped_rows

    def save_checkpoint(self, doc_info: Dict, extracted_data: List[Dict], schema_info: Dict = None):
        """Save successful extraction as checkpoint"""
        timestamp = datetime.now().isoformat()
        checkpoint = {
            "timestamp": timestamp,
            "document": doc_info,
            "schema_info": schema_info,
            "extracted_rows": len(extracted_data),
            "data": extracted_data,
            "success": True
        }
        
        filename = f"checkpoint_{doc_info['doc_id'][:8]}_{timestamp.replace(':', '-')}.json"
        checkpoint_path = self.checkpoints_dir / filename
        
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        
        logger.info(f"💾 Saved checkpoint: {checkpoint_path}")
        return checkpoint_path

    def export_to_csv(self, all_extractions: List[Dict], filename: str = None):
        """Export all successful extractions to CSV and Excel"""
        if not all_extractions:
            logger.warning("No data to export")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"utility_extractions_{timestamp}"
        
        # Combine all data
        all_rows = []
        for extraction in all_extractions:
            doc_name = extraction["document"]["filename"]
            for row in extraction["data"]:
                row_with_source = row.copy()
                row_with_source["source_document"] = doc_name
                row_with_source["extraction_timestamp"] = extraction["timestamp"]
                all_rows.append(row_with_source)
        
        if not all_rows:
            logger.warning("No rows to export")
            return
        
        # Create DataFrame
        df = pd.DataFrame(all_rows)
        
        # Export to CSV
        csv_path = self.csv_dir / f"{filename}.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"📊 Exported to CSV: {csv_path}")
        
        # Export to Excel with multiple sheets
        excel_path = self.csv_dir / f"{filename}.xlsx"
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # All data in one sheet
            df.to_excel(writer, sheet_name='All_Extractions', index=False)
            
            # Separate sheets by document
            for extraction in all_extractions:
                doc_name = extraction["document"]["filename"]
                safe_name = "".join(c for c in doc_name if c.isalnum() or c in (' ', '-', '_'))[:31]
                
                doc_df = pd.DataFrame(extraction["data"])
                if not doc_df.empty:
                    doc_df.to_excel(writer, sheet_name=safe_name, index=False)
        
        logger.info(f"📊 Exported to Excel: {excel_path}")
        return excel_path

    def process_document(self, pdf_path: Path) -> bool:
        """Process a single PDF document through the complete pipeline"""
        logger.info(f"🔄 Processing: {pdf_path.name}")
        
        # Step 1: Upload document
        upload_result = self.upload_document(pdf_path)
        if not upload_result:
            self.failed_extractions.append({"file": str(pdf_path), "error": "Upload failed"})
            return False
        
        # Step 2: Wait for processing
        if not self.wait_for_processing(upload_result["job_id"]):
            self.failed_extractions.append({"file": str(pdf_path), "error": "Processing timeout"})
            return False
        
        # Step 3: Generate schema and standardize
        schema_result = self.create_schema_for_doc(upload_result["doc_id"])
        if not schema_result:
            self.failed_extractions.append({"file": str(pdf_path), "error": "Schema generation failed"})
            return False
        
        # Step 4: Get standardized results
        extracted_data = []
        for std_id in schema_result["standardization_ids"]:
            std_result = self.get_standardization_results(std_id)
            if std_result:
                mapped_data = self.map_to_schema(std_result)
                extracted_data.extend(mapped_data)
        
        if extracted_data:
            # Save checkpoint
            checkpoint_path = self.save_checkpoint(upload_result, extracted_data, schema_result)
            
            extraction_record = {
                "timestamp": datetime.now().isoformat(),
                "document": upload_result,
                "schema_info": schema_result,
                "extracted_rows": len(extracted_data),
                "data": extracted_data,
                "checkpoint_path": str(checkpoint_path)
            }
            
            self.successful_extractions.append(extraction_record)
            logger.info(f"✅ Successfully extracted {len(extracted_data)} rows from {pdf_path.name}")
            return True
        else:
            self.failed_extractions.append({"file": str(pdf_path), "error": "No data extracted"})
            logger.warning(f"⚠️  No data extracted from {pdf_path.name}")
            return False

    def process_folder(self, folder_path: str, max_docs: int = None):
        """Process all PDFs in a folder"""
        logger.info(f"🚀 Starting batch processing: {folder_path}")
        
        pdfs = self.discover_pdfs(folder_path)
        if not pdfs:
            logger.error("No PDFs found to process")
            return
        
        if max_docs:
            pdfs = pdfs[:max_docs]
            logger.info(f"Processing first {max_docs} documents")
        
        # Process each PDF
        for i, pdf_path in enumerate(pdfs, 1):
            logger.info(f"📄 [{i}/{len(pdfs)}] Processing: {pdf_path.name}")
            
            try:
                success = self.process_document(pdf_path)
                
                # Export current results every 5 successful extractions
                if len(self.successful_extractions) > 0 and len(self.successful_extractions) % 5 == 0:
                    self.export_to_csv(self.successful_extractions, f"incremental_{len(self.successful_extractions)}")
                
                # Small delay to respect rate limits
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Error processing {pdf_path.name}: {str(e)}")
                self.failed_extractions.append({"file": str(pdf_path), "error": str(e)})
        
        # Final export
        if self.successful_extractions:
            final_export = self.export_to_csv(self.successful_extractions, "final_extractions")
            logger.info(f"🎉 Final export completed: {final_export}")
        
        # Summary
        self.print_summary()

    def print_summary(self):
        """Print processing summary"""
        total = len(self.successful_extractions) + len(self.failed_extractions)
        success_rate = (len(self.successful_extractions) / total * 100) if total > 0 else 0
        
        logger.info("\n" + "="*50)
        logger.info("📊 PROCESSING SUMMARY")
        logger.info("="*50)
        logger.info(f"Total documents processed: {total}")
        logger.info(f"Successful extractions: {len(self.successful_extractions)}")
        logger.info(f"Failed extractions: {len(self.failed_extractions)}")
        logger.info(f"Success rate: {success_rate:.1f}%")
        
        if self.successful_extractions:
            total_rows = sum(ext["extracted_rows"] for ext in self.successful_extractions)
            logger.info(f"Total data rows extracted: {total_rows}")
        
        logger.info(f"Outputs saved to: {self.output_dir}")
        logger.info(f"Checkpoints: {self.checkpoints_dir}")
        logger.info(f"CSV exports: {self.csv_dir}")


def main():
    """Main execution function"""
    # Your DocuPipe API key
    API_KEY = "EahPwLpsITdU4bZZ9iNSaeu2W7f2"
    
    # Initialize trainer
    trainer = DocuPipeTrainer(API_KEY)
    
    # Process the Civil Plan Sets folder
    civil_plans_folder = r"C:\Users\Zaryab Jibu\Desktop\Python\utility-ai-platform\Civil Plan Sets"
    
    # Start with a small batch for testing
    logger.info("🚀 Starting Underground Utilities AI Training Pipeline")
    logger.info(f"Processing folder: {civil_plans_folder}")
    
    # Process first 5 documents for testing
    trainer.process_folder(civil_plans_folder, max_docs=5)

if __name__ == "__main__":
    main()
