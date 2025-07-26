import os
from pathlib import Path
import time
import uuid
import json
import yaml
import io

import streamlit as st
from PIL import Image
import fitz  # PyMuPDF
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="PDF Annotation Sandbox", layout="wide")

# --- Config & paths ---
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
RAW_PDF_DIR = DATA_DIR / "raw_pdfs"
IMG_DIR = DATA_DIR / "images"
ANN_DIR = DATA_DIR / "annotations"
SCHEMA_PATH = Path(os.getenv("SCHEMA_PATH", "schema.yaml"))

for p in [RAW_PDF_DIR, IMG_DIR, ANN_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# --- Load label schema ---
if SCHEMA_PATH.exists():
    labels_cfg = yaml.safe_load(SCHEMA_PATH.read_text())
    LABELS = labels_cfg.get("labels", [])
else:
    LABELS = []

# --- Helpers ---
def pdf_to_images(pdf_path: Path, dpi: int = 144):
    """Render PDF pages to PNG images; cache on disk."""
    doc = fitz.open(pdf_path)
    out_paths = []
    for pno, page in enumerate(doc, start=1):
        img_path = IMG_DIR / f"{pdf_path.stem}_p{pno}.png"
        if not img_path.exists():
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            img_path.write_bytes(img_bytes)
        out_paths.append(img_path)
    return out_paths

def list_pdfs():
    items = sorted(RAW_PDF_DIR.glob("*.pdf"))
    return items

def save_annotations(doc_id: str, page_index: int, ann_list):
    """Append annotations to a JSONL file (one record per page save)."""
    rec = {
        "doc_id": doc_id,
        "page_index": page_index,
        "timestamp": int(time.time()),
        "annotations": ann_list,
        "schema_labels": LABELS,
    }
    out_path = ANN_DIR / f"{doc_id}.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return out_path

def load_existing_annotations(doc_id: str):
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

# --- Sidebar: upload & doc list ---
st.sidebar.header("1) Add PDFs to label")
uploaded = st.sidebar.file_uploader("Upload PDF(s)", type=["pdf"], accept_multiple_files=True)
if uploaded:
    for uf in uploaded:
        out = RAW_PDF_DIR / uf.name
        out.write_bytes(uf.getvalue())
    st.sidebar.success(f"Saved {len(uploaded)} PDF(s) to {RAW_PDF_DIR}")

st.sidebar.header("2) Choose a document")
pdfs = list_pdfs()
if not pdfs:
    st.info("Upload a PDF using the left sidebar.")
    st.stop()

doc_paths = {p.name: p for p in pdfs}
doc_name = st.sidebar.selectbox("Document", list(doc_paths.keys()))
doc_path = doc_paths[doc_name]
doc_id = doc_path.stem

# Render images (cached)
page_imgs = pdf_to_images(doc_path, dpi=144)
num_pages = len(page_imgs)
page_no = st.sidebar.number_input("Page", min_value=1, max_value=max(1, num_pages), value=1, step=1) - 1

st.sidebar.markdown("---")
st.sidebar.header("Labels")
if not LABELS:
    st.sidebar.warning("No labels found. Edit schema.yaml and restart.")
label_choice = st.sidebar.selectbox("Current label", LABELS if LABELS else ["(no labels)"])

st.sidebar.markdown("---")
st.sidebar.header("Shortcuts")
col_a, col_b = st.sidebar.columns(2)
export_btn = col_a.button("Export index")  # create a simple index CSV
show_prev_annotations = col_b.checkbox("Show saved boxes", value=True)

# --- Main canvas ---
img = Image.open(page_imgs[page_no])
w, h = img.size
st.subheader(f"Annotating: {doc_name} | Page {page_no+1} / {num_pages}")

canvas_result = st_canvas(
    fill_color="rgba(255, 165, 0, 0.2)",
    stroke_width=2,
    stroke_color="#ff1100",
    background_image=img,
    update_streamlit=True,
    height=int(h * 0.9) if h > 1200 else h,
    width=w,
    drawing_mode="rect",
    key=f"canvas_{doc_id}_{page_no}",
)

# Show existing annotations (read-only overlay info)
existing = load_existing_annotations(doc_id) if show_prev_annotations else []

with st.expander("Saved annotations for this document (all pages)", expanded=False):
    for rec in existing:
        st.write(f"p{rec['page_index']+1}: {len(rec['annotations'])} boxes @ {time.ctime(rec['timestamp'])}")

# --- Controls ---
st.markdown("### Label current selections and Save")

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
                "page_width": w,
                "page_height": h,
            })

col1, col2, col3 = st.columns(3)
with col1:
    save_btn = st.button("💾 Save page annotations")
with col2:
    clear_btn = st.button("🧹 Clear (don't save)")
with col3:
    next_btn = st.button("➡ Next page")

if save_btn and new_boxes:
    out_path = save_annotations(doc_id, page_no, new_boxes)
    st.success(f"Saved {len(new_boxes)} box(es) to {out_path.name}")
elif save_btn and not new_boxes:
    st.warning("No boxes to save. Draw at least one rectangle.")

if clear_btn:
    st.rerun()

if next_btn:
    if page_no + 1 < num_pages:
        st.rerun()
    else:
        st.info("This is the last page.")

# Optionally export a tiny dataset index CSV
if export_btn:
    import csv
    idx_path = DATA_DIR / "dataset_index.csv"
    # naive index: count pages and total saved boxes
    total_boxes = 0
    for p in list_pdfs():
        doc_id = p.stem
        anns = load_existing_annotations(doc_id)
        total_boxes += sum(len(rec.get("annotations", [])) for rec in anns)
    with idx_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["num_pdfs", "num_pages_rendered", "total_boxes"])  # simplified
        writer.writerow([len(pdfs), sum([len(pdf_to_images(p)) for p in pdfs]), total_boxes])
    st.success(f"Wrote index to {idx_path}")
    st.download_button("Download dataset_index.csv", data=idx_path.read_bytes(), file_name="dataset_index.csv")
