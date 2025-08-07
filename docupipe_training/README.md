# Underground Utilities AI Training with DocuPipe

This module extracts structured table data from civil engineering PDFs using the DocuPipe API to create training datasets for AI model development.

## Overview

The system processes PDF documents containing utility plans and extracts:
- **Pipe tables** - Structure connections, pipe specifications, elevations
- **Structure tables** - Manholes, catch basins, junction boxes with elevations  
- **SWPPP tables** - Storm Water Pollution Prevention Plan data

## Quick Start

1. **Install dependencies:**
```bash
cd docupipe_training
pip install -r requirements.txt
```

2. **Run the extraction pipeline:**
```bash
python docupipe_trainer.py
```

## System Architecture

### DocuPipeTrainer Class
- **API Integration**: Direct connection to DocuPipe processing endpoints
- **Schema Mapping**: Translates extracted data to standardized civil engineering fields
- **Checkpoint System**: Saves successful extractions for recovery and analysis
- **Batch Processing**: Handles large document collections with rate limiting

### Data Pipeline Flow
1. **Document Discovery** - Scans folders for PDF files
2. **Upload & Processing** - Sends PDFs to DocuPipe API
3. **Schema Generation** - Auto-creates extraction templates for utility tables
4. **Data Standardization** - Maps raw extractions to predefined schema
5. **Export & Checkpointing** - Saves results in CSV/Excel with recovery points

## Schema Mapping

The system maps DocuPipe extractions to these standardized fields:

```python
Civil Engineering Schema:
- from_structure_id, to_structure_id
- rim_elev_ft, outlet_invert_elev_ft, inlet_invert_elev_ft, sump_elev_ft  
- pipe_diameter_in, pipe_type, pipe_material
- run_length_ft, length_in_pvmt_ft, length_in_road_ft
- from_structure_type, casting, location
```

## Output Structure

```
docupipe_outputs/
├── checkpoints/           # JSON files with extraction details
├── csv_exports/          # CSV and Excel files with combined data
└── processing_logs/      # Detailed processing logs
```

## Configuration

- **API Key**: Set in `docupipe_trainer.py` main function
- **Input Folder**: Civil Plan Sets directory path
- **Batch Size**: Configurable max_docs parameter for testing
- **Schema**: Customizable field mapping in `field_schema` dictionary

## Features

- **Intelligent Table Detection**: Focuses on utility-specific tables only
- **Multi-format Export**: Both CSV and Excel with separate sheets per document
- **Error Recovery**: Checkpoint system allows resuming from failures
- **Progress Tracking**: Real-time logging and success rate monitoring
- **Rate Limiting**: Respects API limits with automatic delays

## Usage Examples

```python
# Initialize with API key
trainer = DocuPipeTrainer("your_api_key_here")

# Process specific folder
trainer.process_folder("/path/to/civil/plans", max_docs=10)

# Process single document
success = trainer.process_document(Path("example.pdf"))
```

## Expected Output

The system generates training data in this format:

| from_structure_id | rim_elev_ft | pipe_diameter_in | pipe_material | source_document |
|-------------------|-------------|------------------|---------------|-----------------|
| MH-1             | 825.45      | 12              | PVC           | site_plan_1.pdf |
| MH-2             | 823.12      | 8               | HDPE          | site_plan_1.pdf |

This structured data is ready for AI training pipelines and underground utilities estimation models.
