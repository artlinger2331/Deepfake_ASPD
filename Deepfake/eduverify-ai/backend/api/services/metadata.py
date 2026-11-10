"""
EduVerify AI - Metadata & Forensic Anomaly Scoring Service
==========================================================
Extracts EXIF sensor tags, software manipulation indicators, screenshot markers,
and calculates the Metadata Anomaly Score (M).

Formula:
  M = 0.0
  if editing_software:     M += 0.45
  if camera_missing:       M += 0.15
  if timestamp_missing:    M += 0.10
  if screenshot_indicator: M += 0.10
  if metadata_absent:      M += 0.20
  if normal_camera_present: M -= 0.15
  Clamp M between 0.0 and 1.0.

Ethical Rule:
  Missing metadata alone must never produce an accusation.
  Normal camera metadata reduces suspicion.
"""

import io
import exifread
from typing import Dict, Any, Tuple


EDITING_APPS = [
    "photoshop", "gimp", "canva", "procreate", "lightroom",
    "paint.net", "pixlr", "snapseed", "picsart", "corel", "illustrator"
]

SCREENSHOT_MARKERS = [
    "screenshot", "screen shot", "captura de pantalla", "screencap", "screen-capture"
]


def calculate_metadata_anomaly_score(
    has_exif: bool,
    camera_make_model: str,
    software_used: str,
    timestamp: str,
    raw_tags: Dict[str, Any]
) -> Tuple[float, str, list]:
    """
    Computes the calibrated metadata anomaly score (M) clamped to [0.0, 1.0].
    Returns: (score, status_label, explanation_list)
    """
    m = 0.0
    reasons = []
    
    # 1. Complete absence check
    if not has_exif or not raw_tags:
        m += 0.20
        m += 0.15  # camera missing
        m += 0.10  # timestamp missing
        reasons.append("EXIF metadata is absent (standard for messaging app/web compression like WhatsApp).")
        m = max(0.0, min(1.0, m))
        return round(m, 4), "metadata_absent", reasons

    # 2. Editing software check
    soft_lower = (software_used or "").lower()
    has_editing = any(app in soft_lower for app in EDITING_APPS)
    if has_editing:
        m += 0.45
        reasons.append(f"Image modification or export software detected: {software_used}.")

    # 3. Camera make/model check
    has_camera = bool(camera_make_model and camera_make_model.strip())
    if not has_camera:
        m += 0.15
        reasons.append("Hardware camera optical sensor model is not specified.")
    else:
        # Physical camera hardware present -> reduces score
        m -= 0.15
        reasons.append(f"Authentic physical optical sensor metadata found: {camera_make_model}.")

    # 4. Timestamp check
    has_timestamp = bool(timestamp and timestamp.strip())
    if not has_timestamp:
        m += 0.10
        reasons.append("Original capture timestamp is absent.")
    else:
        reasons.append(f"Creation timestamp preserved: {timestamp}.")

    # 5. Screenshot indicators check
    is_screenshot = False
    all_tag_strings = " ".join([str(v) for v in raw_tags.values()]).lower()
    if any(marker in all_tag_strings for marker in SCREENSHOT_MARKERS) or any(marker in soft_lower for marker in SCREENSHOT_MARKERS):
        is_screenshot = True
        m += 0.10
        reasons.append("Display capture / screenshot indicators identified in image tags.")

    # Clamp final score
    m_clamped = max(0.0, min(1.0, m))

    # Derive primary status label
    if has_editing:
        status_label = "editing_software_detected"
    elif is_screenshot:
        status_label = "screenshot_detected"
    elif has_camera:
        status_label = "authentic_camera_exif"
    elif not has_exif:
        status_label = "metadata_absent"
    else:
        status_label = "sparse_metadata"

    return round(m_clamped, 4), status_label, reasons


def process_metadata(image_bytes: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Extracts EXIF metadata tags and returns structured metadata metrics.
    """
    try:
        tags = exifread.process_file(io.BytesIO(image_bytes), details=False)
        has_exif = bool(tags)

        camera_make = str(tags.get("Image Make", "")).strip()
        camera_model = str(tags.get("Image Model", "")).strip()
        software = str(tags.get("Image Software", "")).strip()
        date_time = str(tags.get("Image DateTime", "")).strip()

        # Filename screenshot check fallback
        if filename and any(m in filename.lower() for m in SCREENSHOT_MARKERS):
            if "Image Software" not in tags:
                tags["Image Software"] = "Screenshot"
                software = "Screenshot Capture"

        camera = f"{camera_make} {camera_model}".strip() if (camera_make or camera_model) else None
        software_used = software if software else None

        score, status_label, explanations = calculate_metadata_anomaly_score(
            has_exif=has_exif,
            camera_make_model=camera or "",
            software_used=software_used or "",
            timestamp=date_time or "",
            raw_tags=tags
        )

        return {
            "status": "success",
            "module": "metadata",
            "data": {
                "metadata_anomaly_score": score,
                "metadata_status": status_label,
                "has_exif_metadata": has_exif,
                "camera_make_model": camera,
                "software_used": software_used,
                "capture_timestamp": date_time or None,
                "c2pa_credentials": False,
                "explanations": explanations
            }
        }
    except Exception as e:
        return {
            "status": "success",
            "module": "metadata",
            "data": {
                "metadata_anomaly_score": 0.45,
                "metadata_status": "metadata_absent",
                "has_exif_metadata": False,
                "camera_make_model": None,
                "software_used": None,
                "capture_timestamp": None,
                "c2pa_credentials": False,
                "explanations": [f"Metadata parse exception handled: {str(e)}"]
            }
        }
