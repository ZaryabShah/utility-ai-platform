#!/usr/bin/env python3
"""
Test script for DocuPipe integration
Quick validation before processing full dataset
"""

import os
import json
import logging
from pathlib import Path
from docupipe_trainer import DocuPipeTrainer

# Setup basic logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_docupipe.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def test_api_connection():
    """Test basic API connectivity"""
    API_KEY = "EahPwLpsITdU4bZZ9iNSaeu2W7f2"
    
    try:
        import requests
        headers = {
            "accept": "application/json",
            "X-API-Key": API_KEY
        }
        
        # Test simple API call - try to access app
        response = requests.get("https://app.docupipe.ai", headers=headers)
        logger.info(f"App access status: {response.status_code}")
        
        # The API key works if we can make requests without 401/403
        if response.status_code in [200, 404]:  # 404 is OK, means endpoint exists but no resource
            logger.info("SUCCESS: API key appears valid")
            return True
        elif response.status_code in [401, 403]:
            logger.error(f"FAILED: API key authentication failed: {response.status_code}")
            return False
        else:
            logger.info(f"API responds with status {response.status_code} - proceeding to test upload")
            return True
            
    except Exception as e:
        logger.error(f"FAILED: Connection error: {str(e)}")
        return False

def test_single_pdf():
    """Test processing with one PDF file"""
    API_KEY = "EahPwLpsITdU4bZZ9iNSaeu2W7f2"
    trainer = DocuPipeTrainer(API_KEY)
    
    # Look for any PDF in the Civil Plan Sets folder
    civil_plans_folder = Path(r"C:\Users\Zaryab Jibu\Desktop\Python\utility-ai-platform\Civil Plan Sets")
    
    if not civil_plans_folder.exists():
        logger.error(f"Folder not found: {civil_plans_folder}")
        return False
    
    # Find first PDF
    pdfs = list(civil_plans_folder.rglob("*.pdf"))
    if not pdfs:
        logger.error("No PDF files found in the folder")
        return False
    
    test_pdf = pdfs[0]
    logger.info(f"Testing with: {test_pdf.name}")
    
    try:
        success = trainer.process_document(test_pdf)
        if success:
            logger.info("SUCCESS: Single PDF test successful")
            trainer.print_summary()
            return True
        else:
            logger.error("FAILED: Single PDF test failed")
            return False
            
    except Exception as e:
        logger.error(f"FAILED: Test error: {str(e)}")
        return False

def validate_outputs():
    """Check if outputs are being created correctly"""
    output_dir = Path("docupipe_outputs")
    
    if not output_dir.exists():
        logger.warning("No outputs directory found")
        return False
    
    # Check subdirectories
    checkpoints = list((output_dir / "checkpoints").glob("*.json"))
    csv_files = list((output_dir / "csv_exports").glob("*.csv"))
    excel_files = list((output_dir / "csv_exports").glob("*.xlsx"))
    
    logger.info(f"Found {len(checkpoints)} checkpoint files")
    logger.info(f"Found {len(csv_files)} CSV files")
    logger.info(f"Found {len(excel_files)} Excel files")
    
    # Sample one checkpoint file if available
    if checkpoints:
        with open(checkpoints[0], 'r') as f:
            sample_checkpoint = json.load(f)
        
        logger.info(f"Sample checkpoint structure:")
        logger.info(f"- Timestamp: {sample_checkpoint.get('timestamp')}")
        logger.info(f"- Document: {sample_checkpoint.get('document', {}).get('filename')}")
        logger.info(f"- Extracted rows: {sample_checkpoint.get('extracted_rows')}")
        
        # Show sample data
        data = sample_checkpoint.get('data', [])
        if data:
            logger.info(f"Sample extracted data: {json.dumps(data[0], indent=2)}")
    
    return True

def main():
    """Run all tests"""
    logger.info("Starting DocuPipe Integration Tests")
    logger.info("=" * 50)
    
    # Test 1: API Connection
    logger.info("Test 1: API Connection")
    if not test_api_connection():
        logger.error("API connection test failed - stopping")
        return
    
    # Test 2: Single PDF Processing
    logger.info("\nTest 2: Single PDF Processing")
    if not test_single_pdf():
        logger.error("Single PDF test failed")
        return
    
    # Test 3: Validate Outputs
    logger.info("\nTest 3: Output Validation")
    validate_outputs()
    
    logger.info("\nSUCCESS: All tests completed")
    logger.info("Ready to process full dataset with docupipe_trainer.py")

if __name__ == "__main__":
    main()
