from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import upload

app = FastAPI(title="Utility AI Platform API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router)

@app.get("/")
async def root():
    return {"message": "Utility AI Platform API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
