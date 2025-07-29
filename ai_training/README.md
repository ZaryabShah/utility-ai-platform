# AI Training Pipeline

## Overview
This module implements the machine learning pipeline for extracting structured data from civil engineering PDFs using YOLOv8 for field detection.

## Architecture
- **Data Pipeline**: PDF processing and annotation handling
- **Model Training**: YOLOv8-based field detection
- **Evaluation**: Performance metrics and validation

## Configuration
Edit `configs/training_config.yaml` to customize:
- PDF source directories (`dataset.raw_pdf_roots`)
- Training parameters (`model` section)
- Output paths and export formats

## Usage

### 1. Data Preparation
```bash
python scripts/data_pipeline.py --config configs/training_config.yaml
```
This will:
- Discover PDFs recursively in configured directories
- Render pages to PNG images (cached)
- Load annotations from Streamlit interface
- Create train/val/test splits by document
- Export YOLO-compatible dataset

### 2. Model Training
```bash
python scripts/model_trainer.py --config configs/training_config.yaml
```
This will:
- Train YOLOv8 model on the dataset
- Save best model checkpoint
- Export to multiple formats (ONNX, TorchScript)

### 3. Evaluation Only
```bash
python scripts/model_trainer.py --mode eval --model models/best_field_detector.pt
```

### 4. Prediction
```bash
python scripts/model_trainer.py --mode predict --image path/to/test/image.png
```

## Output Structure
```
data/
├── manifest.jsonl          # PDF inventory
├── images/                 # Rendered pages (cached)
│   └── <doc_id>/
│       └── page_001.png
├── splits/                 # Train/val/test splits
│   ├── train.txt
│   ├── val.txt
│   └── test.txt
└── yolo/                   # YOLOv8 dataset
    ├── images/
    │   ├── train/
    │   ├── val/
    │   └── test/
    ├── labels/
    │   ├── train/
    │   ├── val/
    │   └── test/
    ├── dataset.yaml
    └── runs/              # Training results

models/
└── best_field_detector.pt  # Trained model
```

## Field Detection Classes
The model detects these civil engineering table fields:
1. from_structure_id
2. from_structure_type
3. casting
4. location
5. rim_elev_ft
6. outlet_invert_elev_ft
7. sump_elev_ft
8. to_structure_id
9. inlet_invert_elev_ft
10. pipe_diameter_in
11. pipe_type
12. run_length_ft
13. length_in_pvmt_ft
14. length_in_road_ft
15. pipe_material

## Requirements
- Python 3.11+
- CUDA GPU (optional, for faster training)
- 8GB+ RAM recommended
- Storage for rendered images and model artifacts

## Integration with Main Pipeline
1. Use Streamlit interface to create annotations
2. Run data pipeline to prepare training dataset
3. Train YOLOv8 model for field detection
4. Integrate trained model with DocuPipe OCR for complete extraction pipeline
