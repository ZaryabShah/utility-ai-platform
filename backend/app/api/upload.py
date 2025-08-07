from fastapi import APIRouter, UploadFile, File, HTTPException
from ..services.docupipe import send_to_docupipe

router = APIRouter(prefix="/upload", tags=["upload"])

@router.post("")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    pdf_bytes = await file.read()
    try:
        result_json = await send_to_docupipe(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result_json
