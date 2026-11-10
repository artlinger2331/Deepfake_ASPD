from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict, Any

from .services.vision import process_vision
from .services.ocr import process_ocr
from .services.metadata import process_metadata
from .services.handwriting import process_handwriting
from .services.fusion import fuse_results

router = APIRouter()

@router.post("/analyze", response_model=Dict[str, Any])
def analyze_image(file: UploadFile = File(...)):
    """
    Main endpoint to process an uploaded image.
    Executed synchronously on threadpool to keep FastAPI responsive during GPU model inference.
    """
    is_image = False
    if file.content_type and file.content_type.startswith("image/"):
        is_image = True
    elif file.filename and file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')):
        is_image = True
        
    if not is_image:
        raise HTTPException(status_code=400, detail="File provided is not an image.")
    
    file_bytes = file.file.read()
    
    try:
        # Step 1: Vision analysis
        vision_result = process_vision(file_bytes)
        
        # Step 2: GPU Multimodal OCR (Qwen2-VL)
        ocr_result = process_ocr(file_bytes)
        ocr_text = ocr_result.get("data", {}).get("extracted_text", "")
        
        # Step 3: Handwriting extraction (skip TrOCR hallucination when Qwen succeeds)
        if not ocr_text or ocr_text.startswith("ERROR:"):
            handwriting_result = process_handwriting(file_bytes)
        else:
            handwriting_result = {
                "status": "success",
                "module": "handwriting",
                "data": {
                    "text": ocr_text,
                    "word_count": ocr_result.get("data", {}).get("word_count", 0),
                    "confidence": ocr_result.get("data", {}).get("confidence_score", 90.0) / 100.0,
                    "is_readable": True
                }
            }
            
        # Step 4: Metadata (EXIF/C2PA)
        metadata_result = process_metadata(file_bytes)
        
        # Step 5: Multi-Signal Ethical Fusion
        final_report = fuse_results(vision_result, ocr_result, handwriting_result, metadata_result)
        
        return final_report
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
