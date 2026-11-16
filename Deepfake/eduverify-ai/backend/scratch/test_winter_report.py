import sys, json
sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")
from api.services.vision import process_vision
from api.services.ocr import process_ocr
from api.services.metadata import process_metadata
from api.services.fusion import fuse_results

img_path = r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\ai_generated\Handwritten Winter Essay.png"
with open(img_path, "rb") as f:
    b = f.read()

v_res = process_vision(b)
o_res = process_ocr(b)
m_res = process_metadata(b, filename="Handwritten Winter Essay.png")

ocr_text = o_res.get("data", {}).get("extracted_text", "")
h_res = {
    "status": "success",
    "module": "handwriting",
    "data": {
        "text": ocr_text,
        "word_count": o_res.get("data", {}).get("word_count", 0),
        "confidence": o_res.get("data", {}).get("confidence_score", 90.0) / 100.0,
        "is_readable": True
    }
}

report = fuse_results(v_res, o_res, h_res, m_res)
print("=== ANALYSIS REPORT FOR WINTER ESSAY ===")
print("v_raw                     :", v_res.get("data", {}).get("raw_visual_score"))
print("v_adjusted                :", v_res.get("data", {}).get("adjusted_visual_score"))
print("vlm_forensics             :", json.dumps(o_res.get("data", {}).get("vlm_forensics", {}), indent=2))
print("ai_generation_signal_score:", report["ai_generation_signal_score"])
print("final_verdict             :", report["final_verdict"])
print("confidence_score          :", report["confidenceScore"])
print("summary                   :", report["summary"])
print("intermediate components   :", json.dumps(report["fusion"]["intermediate_components"], indent=2))

