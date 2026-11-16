import sys
sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")
from api.services.vision import process_vision
from api.services.ocr import process_ocr
from api.services.metadata import process_metadata
from api.services.fusion import fuse_results

def test_file(path, label):
    with open(path, "rb") as f: b = f.read()
    v_res = process_vision(b)
    o_res = process_ocr(b)
    m_res = process_metadata(b)
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
    rep = fuse_results(v_res, o_res, h_res, m_res)
    print(f"[{label}]")
    print(f"  Score  : {rep['ai_generation_signal_score']}")
    print(f"  Verdict: {rep['final_verdict']}")
    print(f"  V_adj  : {rep['signals']['visual']['adjusted_score']}")
    print(f"  VLM    : {rep['signals']['visual'].get('vlm_forensics', {}).get('vlm_verdict')}")
    print()

test_file(
    r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\handwritten_clear\WhatsApp Image 2026-11-04 at 12.54.22 AM.jpeg",
    "Real Student Work - Clear Hand"
)
test_file(
    r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\real_scan\DocScanner 14-Oct-2026 01-56 AM_page_1.jpg",
    "Real Document Scan"
)

