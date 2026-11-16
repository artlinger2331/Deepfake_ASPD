import sys, cv2
sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")
from api.services.ocr import process_ocr

with open(r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\handwritten_clear\WhatsApp Image 2026-11-10 at 11.18.24 PM.jpeg", "rb") as f:
    b = f.read()

res = process_ocr(b)
print("Extracted text for IMG_018:")
print(res.get("data", {}).get("extracted_text"))

