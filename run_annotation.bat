@echo off
echo Starting PDF Annotation Interface...

cd frontend_streamlit

if not exist "venv" (
    echo Virtual environment not found. Run setup_annotation.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
streamlit run streamlit_app.py

pause
