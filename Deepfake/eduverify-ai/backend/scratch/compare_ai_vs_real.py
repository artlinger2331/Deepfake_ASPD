import sys
sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")
from api.services.vision import process_vision

images = [
    (r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\ai_generated\Handwritten Winter Essay.png", "AI - Winter Essay"),
    (r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\handwritten_clear\WhatsApp Image 2026-11-10 at 11.18.24 PM.jpeg", "Real - WhatsApp Lyrics"),
    (r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\real_scan\DocScanner 14-Oct-2026 01-56 AM_page_1.jpg", "Real - DocScanner 1")
]

for p, label in images:
    with open(p, "rb") as f:
        res = process_vision(f.read())
    d = res["data"]
    print(f"{label:25s}: raw={d['raw_visual_score']:.4f}, adj={d['adjusted_visual_score']:.4f}, Q={d['quality_factor']}")
