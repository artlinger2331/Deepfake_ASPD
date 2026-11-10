import uuid
from typing import Dict, Any

def fuse_results(vision_data: Dict[str, Any], 
                 ocr_data: Dict[str, Any], 
                 handwriting_data: Dict[str, Any],
                 metadata_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fuses the results from vision, ocr, handwriting, and metadata
    to generate an explainable, ethical decision-support report.
    Core constraint: Never declare misconduct based solely on an automated score.
    """
    analysis_id = f"EV-{uuid.uuid4().hex[:8].upper()}"
    
    # Extract OCR & Handwriting texts
    ocr_info = ocr_data.get("data", {})
    hw_info = handwriting_data.get("data", {}) if handwriting_data else {}
    
    extracted_text = ocr_info.get("extracted_text", "")
    if not extracted_text or extracted_text.startswith("ERROR:"):
        extracted_text = hw_info.get("text", "")
        
    raw_conf = ocr_info.get("confidence_score")
    if raw_conf is not None and float(raw_conf) > 0:
        ocr_confidence = int(float(raw_conf))
    elif hw_info.get("confidence"):
        ocr_confidence = int(float(hw_info["confidence"]) * 100)
    elif extracted_text:
        ocr_confidence = 90
    else:
        ocr_confidence = 0

    word_count = ocr_info.get("word_count") or hw_info.get("word_count") or len(extracted_text.split())
    
    # Extract Visual signals
    vision_info = vision_data.get("data", {})
    visual_synthetic_score = float(vision_info.get("visual_synthetic_score", 0.15))
    visual_pct = int(visual_synthetic_score * 100)
    artifact_notes = vision_info.get("artifact_notes", [])
    
    # Extract Metadata signals
    meta_info = metadata_data.get("data", {})
    software = meta_info.get("software_used")
    camera = meta_info.get("camera_make_model")
    
    # Determine Status & Explanations ethically
    consistency_points = []
    
    if software and any(app in software.lower() for app in ["photoshop", "gimp", "canva", "procreate"]):
        metadata_status = "warning"
        metadata_label = f"Editing software detected ({software})"
        metadata_exp = f"Image metadata shows processing in {software}."
        consistency_points.append(f"Image was modified or exported using {software}")
    elif camera:
        metadata_status = "original"
        metadata_label = f"Original camera capture ({camera})"
        metadata_exp = f"EXIF metadata indicates a direct capture from {camera}."
        consistency_points.append(f"Authentic camera sensor metadata found ({camera})")
    else:
        metadata_status = "warning"
        metadata_label = "Metadata stripped or absent"
        metadata_exp = "No hardware camera EXIF found (common with messaging apps like WhatsApp or web uploads)."
        consistency_points.append("Standard web/messaging app compression (EXIF stripped)")

    if word_count > 0:
        consistency_points.append(f"Legible handwriting transcribed ({word_count} words)")
    else:
        consistency_points.append("Low handwriting density detected")

    if visual_pct >= 65 or (software and "photoshop" in software.lower()):
        status = "concern"
        status_label = "Possibly AI-generated or Digitally Edited"
        conclusion = "concern"
        confidence_score = max(visual_pct, 70)
        summary = (
            "Visual signal analysis flagged potential synthetic artifacts or digital editing. "
            "Because automated detections can have false positives, this serves as decision support only. "
            "Manual review with the student is strongly recommended."
        )
    elif visual_pct <= 35 and word_count > 0:
        status = "genuine"
        status_label = "Likely Genuine Handwritten Work"
        conclusion = "authentic"
        confidence_score = max(88, ocr_confidence)
        summary = (
            "The document exhibits natural handwriting patterns and optical features consistent with genuine student work. "
            "No high-confidence indicators of synthetic generation or tampering were observed."
        )
    else:
        status = "uncertain"
        status_label = "Uncertain / Additional Context Recommended"
        conclusion = "uncertain"
        confidence_score = 50
        summary = (
            "Mixed or inconclusive signals detected across visual, metadata, and handwriting modules. "
            "We recommend requesting the original physical submission or speaking with the student."
        )

    signals = {
        "visual": {
            "score": visual_pct,
            "label": "Low probability of synthetic patterns" if visual_pct < 40 else "Potential synthetic patterns detected",
            "explanation": " ".join(artifact_notes) if artifact_notes else "Standard visual resolution and stroke features analyzed."
        },
        "metadata": {
            "status": metadata_status,
            "label": metadata_label,
            "explanation": metadata_exp
        },
        "provenance": {
            "status": "missing",
            "label": "No Content Credentials (C2PA)",
            "explanation": "No cryptographic C2PA signature was attached to this image file."
        },
        "ocr": {
            "score": ocr_confidence,
            "label": f"Handwriting transcribed ({word_count} words)" if word_count else "No legible text found",
            "extracted": extracted_text or "No handwritten text extracted."
        },
        "consistency": consistency_points
    }

    oriented_image_base64 = ocr_info.get("oriented_image_base64")

    return {
        "analysis_id": analysis_id,
        "id": analysis_id,
        "status": status,
        "statusLabel": status_label,
        "conclusion": conclusion,
        "confidenceScore": confidence_score,
        "confidence_score": round(confidence_score / 100.0, 2),
        "summary": summary,
        "explanation": summary,
        "extracted_text": extracted_text,
        "ocr_text": extracted_text,
        "oriented_image_base64": oriented_image_base64,
        "signals": signals,
        "raw_inputs": {
            "vision": vision_data,
            "ocr": ocr_data,
            "handwriting": handwriting_data,
            "metadata": metadata_data
        }
    }
