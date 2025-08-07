@echo off
echo Setting up PDF Annotation Environment...

cd frontend_streamlit

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing requirements...
pip install -r requirements.txt

echo Setup complete! To run the annotation app:
echo 1. cd frontend_streamlit
echo 2. venv\Scripts\activate.bat
echo 3. streamlit run streamlit_app.py

pause
