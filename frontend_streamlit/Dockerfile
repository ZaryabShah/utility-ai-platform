FROM python:3.11-slim

WORKDIR /app

# Install streamlit and requests
RUN pip install streamlit requests

# Copy the app
COPY . /app

EXPOSE 8501

# Run streamlit
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
