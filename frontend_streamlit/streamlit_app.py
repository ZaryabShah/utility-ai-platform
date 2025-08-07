import os
import zipfile
import shutil
from pathlib import Path
import time
import uuid
import json
import yaml
import io
from typing import List, Dict, Any

import streamlit as st
from PIL import Image
import fitz  # PyMuPDF
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="Underground Utilities Annotation Interface", layout="wide")

# --- Config & paths ---
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
RAW_PDF_DIR = DATA_DIR / "raw_pdfs"
IMG_DIR = DATA_DIR / "images"
ANN_DIR = DATA_DIR / "annotations"
SCHEMA_PATH = Path(os.getenv("SCHEMA_PATH", "schema.yaml"))

for p in [RAW_PDF_DIR, IMG_DIR, ANN_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# --- Load civil engineering schema ---
DEFAULT_SCHEMA = {
    "labels": [
        "from_structure_id",
        "from_structure_type", 
        "casting",
        "location",
        "rim_elev_ft",
        "outlet_invert_elev_ft",
        "sump_elev_ft",
        "to_structure_id",
        "inlet_invert_elev_ft",
        "pipe_diameter_in",
        "pipe_type",
        "run_length_ft",
        "length_in_pvmt_ft",
        "length_in_road_ft",
        "pipe_material"
    ]
}

if SCHEMA_PATH.exists():
    labels_cfg = yaml.safe_load(SCHEMA_PATH.read_text())
    LABELS = labels_cfg.get("labels", DEFAULT_SCHEMA["labels"])
else:
    LABELS = DEFAULT_SCHEMA["labels"]
    # Create default schema file
    with open(SCHEMA_PATH, 'w') as f:
        yaml.dump(DEFAULT_SCHEMA, f, default_flow_style=False)

# --- Helpers ---
def extract_pdfs_from_zip(zip_file, extract_to: Path):
    """Extract ZIP and recursively find all PDFs."""
    temp_dir = extract_to / "temp_extract"
    temp_dir.mkdir(exist_ok=True)
    
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    
    # Find all PDFs recursively
    pdf_files = []
    for pdf_path in temp_dir.rglob("*.pdf"):
        # Preserve folder structure in filename
        rel_path = pdf_path.relative_to(temp_dir)
        safe_name = str(rel_path).replace(os.sep, "_").replace(" ", "_")
        
        # Truncate filename if too long (Windows has 260 char limit)
        if len(safe_name) > 200:  # Leave room for path and extension
            name_part = safe_name[:-4]  # Remove .pdf
            safe_name = name_part[:190] + "_truncated.pdf"
        
        dest_path = extract_to / safe_name
        
        # Copy PDF to flat structure but keep original path info
        try:
            shutil.copy2(pdf_path, dest_path)
            pdf_files.append((dest_path, str(rel_path)))
        except (OSError, FileNotFoundError) as e:
            # If copy fails, create a shorter name with hash
            import hashlib
            hash_suffix = hashlib.md5(str(pdf_path).encode()).hexdigest()[:8]
            short_name = f"doc_{hash_suffix}.pdf"
            dest_path = extract_to / short_name
            try:
                shutil.copy2(pdf_path, dest_path)
                pdf_files.append((dest_path, str(rel_path)))
            except Exception:
                st.warning(f"Could not extract file: {pdf_path.name}")
    
    # Cleanup temp directory
    shutil.rmtree(temp_dir)
    return pdf_files

def scan_folder_for_pdfs(folder_path: str, copy_to: Path):
    """Recursively scan local folder for PDFs and copy them."""
    source_path = Path(folder_path)
    if not source_path.exists():
        return []
    
    pdf_files = []
    for pdf_path in source_path.rglob("*.pdf"):
        rel_path = pdf_path.relative_to(source_path)
        # Create a shorter, safe filename
        safe_name = str(rel_path).replace(os.sep, "_").replace(" ", "_")
        
        # Truncate filename if too long (Windows has 260 char limit)
        if len(safe_name) > 200:  # Leave room for path and extension
            name_part = safe_name[:-4]  # Remove .pdf
            safe_name = name_part[:190] + "_truncated.pdf"
        
        dest_path = copy_to / safe_name
        
        if not dest_path.exists():
            try:
                shutil.copy2(pdf_path, dest_path)
                pdf_files.append((dest_path, str(rel_path)))
            except (OSError, FileNotFoundError) as e:
                # If copy fails, create a shorter name with hash
                import hashlib
                hash_suffix = hashlib.md5(str(pdf_path).encode()).hexdigest()[:8]
                short_name = f"doc_{hash_suffix}.pdf"
                dest_path = copy_to / short_name
                try:
                    shutil.copy2(pdf_path, dest_path)
                    pdf_files.append((dest_path, str(rel_path)))
                except Exception:
                    st.warning(f"Could not copy file: {pdf_path.name}")
        else:
            pdf_files.append((dest_path, str(rel_path)))
    
    return pdf_files

def pdf_to_images(pdf_path: Path, dpi: int = 144):
    """Render PDF pages to PNG images; cache on disk."""
    doc = fitz.open(pdf_path)
    out_paths = []
    doc_img_dir = IMG_DIR / pdf_path.stem
    doc_img_dir.mkdir(exist_ok=True)
    
    for pno, page in enumerate(doc, start=1):
        img_path = doc_img_dir / f"page_{pno:03d}.png"
        if not img_path.exists():
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            img_path.write_bytes(img_bytes)
        out_paths.append(img_path)
    return out_paths

def list_pdfs():
    """List all PDFs in the data directory."""
    items = sorted(RAW_PDF_DIR.glob("*.pdf"))
    return items

def save_annotations(doc_id: str, page_index: int, row_id: str, ann_list: List[Dict]):
    """Save annotations with row_id for P1 training."""
    rec = {
        "doc_id": doc_id,
        "page_index": page_index,
        "row_id": row_id,
        "timestamp": int(time.time()),
        "annotations": ann_list,
        "schema_labels": LABELS,
        "format_version": "p1_v1"
    }
    out_path = ANN_DIR / f"{doc_id}.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return out_path

def load_existing_annotations(doc_id: str) -> List[Dict]:
    """Load existing annotations for a document."""
    path = ANN_DIR / f"{doc_id}.jsonl"
    if not path.exists():
        return []
    data = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except Exception:
                pass
    return data

def export_dataset_index():
    """Export training dataset index."""
    pdfs = list_pdfs()
    total_annotations = 0
    total_pages = 0
    
    index_data = []
    for pdf_path in pdfs:
        doc_id = pdf_path.stem
        annotations = load_existing_annotations(doc_id)
        page_count = len(pdf_to_images(pdf_path))
        ann_count = len(annotations)
        
        total_annotations += ann_count
        total_pages += page_count
        
        index_data.append({
            "doc_id": doc_id,
            "filename": pdf_path.name,
            "pages": page_count,
            "annotation_records": ann_count,
            "total_boxes": sum(len(rec.get("annotations", [])) for rec in annotations)
        })
    
    return {
        "summary": {
            "total_pdfs": len(pdfs),
            "total_pages": total_pages,
            "total_annotation_records": total_annotations,
            "total_labeled_boxes": sum(item["total_boxes"] for item in index_data)
        },
        "documents": index_data,
        "labels": LABELS,
        "export_timestamp": time.time()
    }

# --- Streamlit UI ---
st.title("🏗️ Underground Utilities Estimation AI Platform")
st.markdown("**Annotation Interface**: Label civil engineering plan fields for AI training")

# === SIDEBAR: PDF Management ===
st.sidebar.header("📁 Document Management")

upload_method = st.sidebar.radio(
    "Upload method:",
    ["Upload Files", "Upload ZIP Folder", "Scan Local Path"]
)

if upload_method == "Upload Files":
    uploaded = st.sidebar.file_uploader(
        "Select PDF files", 
        type=["pdf"], 
        accept_multiple_files=True
    )
    if uploaded:
        for uf in uploaded:
            out = RAW_PDF_DIR / uf.name
            out.write_bytes(uf.getvalue())
        st.sidebar.success(f"✅ Added {len(uploaded)} PDF(s)")

elif upload_method == "Upload ZIP Folder":
    zip_file = st.sidebar.file_uploader(
        "Upload ZIP of main folder", 
        type=["zip"]
    )
    if zip_file:
        with st.spinner("Extracting PDFs from ZIP..."):
            pdf_files = extract_pdfs_from_zip(zip_file, RAW_PDF_DIR)
        st.sidebar.success(f"✅ Extracted {len(pdf_files)} PDFs")
        with st.sidebar.expander("Extracted files"):
            for dest_path, orig_path in pdf_files:
                st.sidebar.write(f"📄 {orig_path}")

elif upload_method == "Scan Local Path":
    folder_path = st.sidebar.text_input(
        "Local folder path:", 
        placeholder="/path/to/your/pdf/folder"
    )
    if st.sidebar.button("🔍 Scan Folder"):
        if folder_path:
            with st.spinner("Scanning for PDFs..."):
                pdf_files = scan_folder_for_pdfs(folder_path, RAW_PDF_DIR)
            st.sidebar.success(f"✅ Found {len(pdf_files)} PDFs")
        else:
            st.sidebar.error("Please enter a folder path")

st.sidebar.markdown("---")

# === DOCUMENT SELECTION ===
st.sidebar.header("📋 Select Document")
pdfs = list_pdfs()

if not pdfs:
    st.info("👆 Upload PDFs using the sidebar to begin annotation")
    st.stop()

doc_paths = {p.name: p for p in pdfs}
doc_name = st.sidebar.selectbox("Document:", list(doc_paths.keys()))
doc_path = doc_paths[doc_name]
doc_id = doc_path.stem

# Render pages
with st.spinner("Rendering PDF pages..."):
    page_imgs = pdf_to_images(doc_path, dpi=144)

num_pages = len(page_imgs)
page_no = st.sidebar.number_input(
    "Page:", 
    min_value=1, 
    max_value=max(1, num_pages), 
    value=1, 
    step=1
) - 1

st.sidebar.markdown("---")

# === ANNOTATION CONTROLS ===
st.sidebar.header("🏷️ Annotation")

col1, col2 = st.sidebar.columns(2)
with col1:
    label_choice = st.selectbox("Field Label:", LABELS)
with col2:
    row_id = st.text_input("Row ID:", placeholder="e.g., 07, R1")

st.sidebar.markdown("---")

# === DATASET MANAGEMENT ===
st.sidebar.header("📊 Dataset")

show_existing = st.sidebar.checkbox("Show saved annotations", value=True)

col_a, col_b = st.sidebar.columns(2)
with col_a:
    export_btn = st.button("📈 Export Index")
with col_b:
    clear_doc_btn = st.button("🗑️ Clear Doc")

# === MAIN CANVAS ===
img = Image.open(page_imgs[page_no])
w, h = img.size

st.header(f"📄 {doc_name}")
st.subheader(f"Page {page_no+1} of {num_pages}")

# Display existing annotations if requested
if show_existing:
    existing = load_existing_annotations(doc_id)
    if existing:
        st.info(f"📝 {len(existing)} annotation records saved for this document")

# Canvas for drawing
canvas_result = st_canvas(
    fill_color="rgba(255, 255, 0, 0.3)",  # Yellow highlight for fields
    stroke_width=2,
    stroke_color="#ff0000",
    background_image=img,
    update_streamlit=True,
    height=min(800, h),  # Limit height for better UX
    width=min(1200, w),  # Limit width for better UX
    drawing_mode="rect",
    key=f"canvas_{doc_id}_{page_no}_{row_id}",  # Include row_id in key
)

# === ANNOTATION PROCESSING ===
st.markdown("### 💾 Save Annotations")

# Collect rectangles from canvas
new_boxes = []
if canvas_result.json_data is not None:
    for obj in canvas_result.json_data.get("objects", []):
        if obj.get("type") == "rect":
            left = float(obj.get("left", 0.0))
            top = float(obj.get("top", 0.0))
            width = float(obj.get("width", 0.0))
            height = float(obj.get("height", 0.0))
            
            new_boxes.append({
                "bbox": [left, top, width, height],
                "label": label_choice,
                "row_id": row_id,
                "page_width": w,
                "page_height": h,
                "confidence": 1.0  # Human annotation
            })

col1, col2, col3, col4 = st.columns(4)

with col1:
    save_btn = st.button("💾 Save Page", type="primary")
with col2:
    clear_btn = st.button("🧹 Clear Canvas")
with col3:
    prev_btn = st.button("⬅️ Previous")
with col4:
    next_btn = st.button("➡️ Next")

# Handle button actions
if save_btn:
    if new_boxes and row_id.strip():
        out_path = save_annotations(doc_id, page_no, row_id.strip(), new_boxes)
        st.success(f"✅ Saved {len(new_boxes)} annotation(s) for row '{row_id}' to {out_path.name}")
    elif not new_boxes:
        st.warning("⚠️ Draw at least one rectangle to save")
    else:
        st.warning("⚠️ Enter a Row ID before saving")

if clear_btn:
    st.rerun()

if prev_btn and page_no > 0:
    st.rerun()

if next_btn and page_no + 1 < num_pages:
    st.rerun()

# === DATASET EXPORT ===
if export_btn:
    index_data = export_dataset_index()
    
    st.subheader("📊 Dataset Summary")
    st.json(index_data["summary"])
    
    # Create downloadable JSON
    index_json = json.dumps(index_data, indent=2)
    st.download_button(
        "📥 Download Full Index",
        data=index_json,
        file_name=f"dataset_index_{int(time.time())}.json",
        mime="application/json"
    )

if clear_doc_btn:
    ann_file = ANN_DIR / f"{doc_id}.jsonl"
    if ann_file.exists():
        ann_file.unlink()
        st.success(f"🗑️ Cleared annotations for {doc_id}")
    else:
        st.info("No annotations to clear for this document")

# === STATUS BAR ===
with st.expander("📈 Current Session Stats", expanded=False):
    if pdfs:
        total_annotations = sum(len(load_existing_annotations(p.stem)) for p in pdfs)
        st.metric("Documents", len(pdfs))
        st.metric("Total Pages", sum(len(pdf_to_images(p)) for p in pdfs))
        st.metric("Annotation Records", total_annotations)
