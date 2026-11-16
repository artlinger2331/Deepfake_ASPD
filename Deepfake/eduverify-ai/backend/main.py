import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.router import router as api_router

# Windows console / pipe disconnection guard to prevent [WinError 233] on sys.stdout/stderr
class SafeStream:
    def __init__(self, target):
        self._target = target

    def write(self, s):
        try:
            return self._target.write(s)
        except OSError:
            pass

    def flush(self):
        try:
            return self._target.flush()
        except OSError:
            pass

    def __getattr__(self, attr):
        return getattr(self._target, attr)

if sys.platform == "win32":
    if sys.stdout is not None:
        sys.stdout = SafeStream(sys.stdout)
    if sys.stderr is not None:
        sys.stderr = SafeStream(sys.stderr)

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
