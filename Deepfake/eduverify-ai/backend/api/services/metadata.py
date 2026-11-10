import io
import exifread
from typing import Dict, Any

def process_metadata(image_bytes: bytes) -> Dict[str, Any]:
    try:
        tags = exifread.process_file(io.BytesIO(image_bytes), details=False)
        has_exif = bool(tags)
        
        camera_make = str(tags.get("Image Make", ""))
        camera_model = str(tags.get("Image Model", ""))
        software = str(tags.get("Image Software", ""))
        date_time = str(tags.get("Image DateTime", ""))
        
        camera = f"{camera_make} {camera_model}".strip() if (camera_make or camera_model) else None
        software_used = software.strip() if software else None
        
        return {
            "status": "success",
            "module": "metadata",
            "data": {
                "has_exif_metadata": has_exif,
                "camera_make_model": camera,
                "software_used": software_used,
                "capture_timestamp": date_time or None,
                "c2pa_credentials": False
            }
        }
    except Exception as e:
        return {
            "status": "success",
            "module": "metadata",
            "data": {
                "has_exif_metadata": False,
                "camera_make_model": None,
                "software_used": None,
                "error": str(e)
            }
        }
