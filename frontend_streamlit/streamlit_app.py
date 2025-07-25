import streamlit as st
import requests
import json
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

st.set_page_config(page_title="Utility‑AI Sandbox", layout="wide")
st.title("📑 PDF ➜ DocuPipe ➜ JSON")

uploaded = st.file_uploader("Choose a civil‑plan PDF", type=["pdf"])

if uploaded:
    with st.spinner("Uploading…"):
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
        resp = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=120)
    if resp.status_code == 200:
        st.success("DocuPipe JSON received")
        st.json(resp.json(), expanded=False)
    else:
        st.error(f"Backend error {resp.status_code}: {resp.text}")
