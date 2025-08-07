FROM python:3.11-slim

# (Optional) install build tools for some wheels; PyMuPDF ships manylinux wheels so this is usually enough.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Create a writeable data volume inside the container
ENV DATA_DIR=/data
RUN mkdir -p $DATA_DIR/raw_pdfs $DATA_DIR/images $DATA_DIR/annotations

COPY streamlit_app.py ./
COPY schema.yaml ./

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
