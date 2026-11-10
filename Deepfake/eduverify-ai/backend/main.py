from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.router import router as api_router

app = FastAPI(
    title="EduVerify AI Backend",
    description="Backend for analyzing images using Vision, OCR, and Metadata extraction fused via Gemma 4",
    version="1.0.0"
)

# Configure CORS to accept all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the main API router
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}
