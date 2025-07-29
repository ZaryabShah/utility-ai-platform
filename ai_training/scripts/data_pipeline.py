#!/usr/bin/env python3
"""
Data Pipeline for Underground Utilities AI Training
Handles PDF discovery, page rendering, annotation processing, and dataset splitting.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
import yaml
import fitz  # PyMuPDF
from sklearn.model_selection import train_test_split
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataPipeline:
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.work_dir = Path(self.config['dataset']['work_dir'])
        self.work_dir.mkdir(exist_ok=True)
        
        # Create output directories
        self.images_dir = self.work_dir / "images"
        self.yolo_dir = self.work_dir / "yolo"
        self.splits_dir = self.work_dir / "splits"
        
        for dir_path in [self.images_dir, self.yolo_dir, self.splits_dir]:
            dir_path.mkdir(exist_ok=True)

    def discover_pdfs(self) -> List[Path]:
        """Recursively discover all PDF files in configured roots."""
        pdf_files = []
        for root in self.config['dataset']['raw_pdf_roots']:
            root_path = Path(root)
            if root_path.exists():
                pdfs = list(root_path.rglob("*.pdf"))
                pdf_files.extend(pdfs)
                logger.info(f"Found {len(pdfs)} PDFs in {root}")
            else:
                logger.warning(f"Path does not exist: {root}")
        
        logger.info(f"Total PDFs discovered: {len(pdf_files)}")
        return pdf_files

    def render_pages(self, pdf_files: List[Path]) -> Dict[str, List[Path]]:
        """Render PDF pages to images with caching."""
        dpi = self.config['rendering']['dpi']
        max_pages = self.config['rendering']['max_pages_per_doc']
        
        doc_images = {}
        
        for pdf_path in pdf_files:
            doc_id = pdf_path.stem
            doc_img_dir = self.images_dir / doc_id
            doc_img_dir.mkdir(exist_ok=True)
            
            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc) if max_pages == -1 else min(len(doc), max_pages)
                
                page_paths = []
                for page_num in range(page_count):
                    img_path = doc_img_dir / f"page_{page_num:03d}.png"
                    
                    if not img_path.exists():
                        page = doc[page_num]
                        mat = fitz.Matrix(dpi / 72, dpi / 72)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img_path.write_bytes(pix.tobytes("png"))
                    
                    page_paths.append(img_path)
                
                doc_images[doc_id] = page_paths
                logger.info(f"Rendered {len(page_paths)} pages for {doc_id}")
                
            except Exception as e:
                logger.error(f"Failed to render {pdf_path}: {e}")
        
        return doc_images

    def load_annotations(self) -> Dict[str, List[Dict]]:
        """Load annotation JSONL files."""
        annotations_dir = self.work_dir / "annotations"
        if not annotations_dir.exists():
            logger.warning("No annotations directory found")
            return {}
        
        all_annotations = {}
        for jsonl_file in annotations_dir.glob("*.jsonl"):
            doc_id = jsonl_file.stem
            annotations = []
            
            with open(jsonl_file, 'r') as f:
                for line in f:
                    try:
                        annotation = json.loads(line.strip())
                        annotations.append(annotation)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON in {jsonl_file}: {e}")
            
            all_annotations[doc_id] = annotations
            logger.info(f"Loaded {len(annotations)} annotation records for {doc_id}")
        
        return all_annotations

    def create_splits(self, doc_ids: List[str]) -> Dict[str, List[str]]:
        """Create train/val/test splits by document."""
        config = self.config['dataset']
        train_split = config['train_split']
        val_split = config['val_split']
        
        # First split: train vs temp (test + val)
        train_docs, temp_docs = train_test_split(
            doc_ids, 
            train_size=train_split, 
            random_state=42
        )
        
        # Second split: test vs val from temp
        val_size = val_split / (val_split + config['test_split'])
        val_docs, test_docs = train_test_split(
            temp_docs, 
            train_size=val_size, 
            random_state=42
        )
        
        splits = {
            'train': train_docs,
            'val': val_docs,
            'test': test_docs
        }
        
        # Save splits
        for split_name, docs in splits.items():
            split_file = self.splits_dir / f"{split_name}.txt"
            with open(split_file, 'w') as f:
                f.write('\n'.join(docs))
        
        logger.info(f"Created splits: train={len(train_docs)}, val={len(val_docs)}, test={len(test_docs)}")
        return splits

    def export_yolo_dataset(self, doc_images: Dict[str, List[Path]], 
                          annotations: Dict[str, List[Dict]], 
                          splits: Dict[str, List[str]]):
        """Export annotations to YOLO format."""
        labels = self.config['labels']
        label_to_id = {label: idx for idx, label in enumerate(labels)}
        
        # Create YOLO directory structure
        for split in ['train', 'val', 'test']:
            (self.yolo_dir / 'images' / split).mkdir(parents=True, exist_ok=True)
            (self.yolo_dir / 'labels' / split).mkdir(parents=True, exist_ok=True)
        
        # Process each split
        for split_name, doc_ids in splits.items():
            for doc_id in doc_ids:
                if doc_id not in doc_images or doc_id not in annotations:
                    continue
                
                doc_annotations = annotations[doc_id]
                doc_pages = doc_images[doc_id]
                
                # Group annotations by page
                page_annotations = {}
                for ann_record in doc_annotations:
                    page_idx = ann_record['page_index']
                    if page_idx not in page_annotations:
                        page_annotations[page_idx] = []
                    page_annotations[page_idx].extend(ann_record.get('annotations', []))
                
                # Export each page
                for page_idx, page_path in enumerate(doc_pages):
                    if page_idx in page_annotations:
                        # Copy image
                        img_dest = self.yolo_dir / 'images' / split_name / f"{doc_id}_page_{page_idx:03d}.png"
                        shutil.copy2(page_path, img_dest)
                        
                        # Create label file
                        label_dest = self.yolo_dir / 'labels' / split_name / f"{doc_id}_page_{page_idx:03d}.txt"
                        
                        with open(label_dest, 'w') as f:
                            for ann in page_annotations[page_idx]:
                                label = ann['label']
                                if label in label_to_id:
                                    bbox = ann['bbox']  # [x, y, width, height]
                                    page_w = ann['page_width']
                                    page_h = ann['page_height']
                                    
                                    # Convert to YOLO format (normalized center coordinates)
                                    x_center = (bbox[0] + bbox[2] / 2) / page_w
                                    y_center = (bbox[1] + bbox[3] / 2) / page_h
                                    width = bbox[2] / page_w
                                    height = bbox[3] / page_h
                                    
                                    class_id = label_to_id[label]
                                    f.write(f"{class_id} {x_center} {y_center} {width} {height}\n")
        
        # Create dataset.yaml
        dataset_yaml = {
            'path': str(self.yolo_dir.absolute()),
            'train': 'images/train',
            'val': 'images/val',
            'test': 'images/test',
            'nc': len(labels),
            'names': labels
        }
        
        with open(self.yolo_dir / 'dataset.yaml', 'w') as f:
            yaml.dump(dataset_yaml, f, default_flow_style=False)
        
        logger.info(f"YOLO dataset exported to {self.yolo_dir}")

    def create_manifest(self, pdf_files: List[Path]):
        """Create a manifest of all PDFs for tracking."""
        manifest_data = []
        for pdf_path in pdf_files:
            try:
                doc = fitz.open(pdf_path)
                manifest_data.append({
                    "doc_id": pdf_path.stem,
                    "filename": pdf_path.name,
                    "filepath": str(pdf_path),
                    "pages": len(doc),
                    "size_bytes": pdf_path.stat().st_size,
                    "created_timestamp": pdf_path.stat().st_ctime
                })
                doc.close()
            except Exception as e:
                logger.error(f"Failed to process {pdf_path}: {e}")
        
        manifest_path = self.work_dir / "manifest.jsonl"
        with open(manifest_path, 'w') as f:
            for item in manifest_data:
                f.write(json.dumps(item) + "\n")
        
        logger.info(f"Created manifest with {len(manifest_data)} documents at {manifest_path}")

    def run_pipeline(self):
        """Execute the complete data pipeline."""
        logger.info("Starting Underground Utilities AI data pipeline...")
        
        # Step 1: Discover PDFs
        pdf_files = self.discover_pdfs()
        if not pdf_files:
            logger.error("No PDFs found!")
            return
        
        # Step 2: Create manifest
        self.create_manifest(pdf_files)
        
        # Step 3: Render pages
        doc_images = self.render_pages(pdf_files)
        
        # Step 4: Load annotations
        annotations = self.load_annotations()
        
        # Filter documents with sufficient annotations
        min_annotations = self.config['dataset']['min_annotations_per_doc']
        valid_doc_ids = [
            doc_id for doc_id, anns in annotations.items() 
            if len(anns) >= min_annotations
        ]
        
        if not valid_doc_ids:
            logger.error("No documents with sufficient annotations found!")
            logger.info("Please create annotations using the Streamlit interface first.")
            return
        
        logger.info(f"Found {len(valid_doc_ids)} documents with sufficient annotations")
        
        # Step 5: Create splits
        splits = self.create_splits(valid_doc_ids)
        
        # Step 6: Export YOLO dataset
        self.export_yolo_dataset(doc_images, annotations, splits)
        
        logger.info("Data pipeline completed successfully!")
        logger.info(f"Next step: Run model training with 'python scripts/model_trainer.py'")

def main():
    parser = argparse.ArgumentParser(description="Underground Utilities Data Pipeline")
    parser.add_argument("--config", default="configs/training_config.yaml", 
                       help="Path to training configuration file")
    args = parser.parse_args()
    
    pipeline = DataPipeline(args.config)
    pipeline.run_pipeline()

if __name__ == "__main__":
    main()
