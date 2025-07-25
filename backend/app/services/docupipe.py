import httpx
import os
import base64

DOCUPIPE_URL = os.getenv("DOCUPIPE_URL", "https://api.docupipe.com/v1/parse")
DOCUPIPE_TOKEN = os.getenv("DOCUPIPE_TOKEN")

async def send_to_docupipe(pdf_bytes: bytes) -> dict:
    if not DOCUPIPE_TOKEN:
        # Return mock data for testing when no token is provided
        return {
            "status": "success",
            "message": "Mock DocuPipe response - no token provided",
            "data": {
                "text_extracted": "Sample text from civil engineering plan",
                "entities": [
                    {"type": "pipe", "location": "Section A", "diameter": "12 inch"},
                    {"type": "manhole", "location": "Junction 1", "depth": "8 feet"}
                ],
                "confidence": 0.85
            }
        }
    
    headers = {"Authorization": f"Bearer {DOCUPIPE_TOKEN}"}
    data = {
        "file_name": "plan.pdf",
        "content": base64.b64encode(pdf_bytes).decode(),
        "content_encoding": "base64"
    }
    
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(DOCUPIPE_URL, json=data, headers=headers)
        r.raise_for_status()
        return r.json()
