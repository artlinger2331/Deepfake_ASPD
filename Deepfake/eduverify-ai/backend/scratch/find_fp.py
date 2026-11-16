import sys, csv
sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")
from api.services.vision import process_vision
from api.services.metadata import process_metadata

gt_path = r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\ground_truth.csv"
with open(gt_path, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

for r in rows:
    cat = r["category"]
    fname = r["file_name"]
    lbl = r["true_label"].lower()
    img_id = r["image_id"]
    if lbl not in ["ai_generated", "edited_real"]:
        p = rf"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\{cat}\{fname}"
        with open(p, "rb") as f: b = f.read()
        v_res = process_vision(b)
        v_data = v_res.get("data", {})
        v_adj = float(v_data.get("adjusted_visual_score", 0.0))
        if v_adj > 0.45:
            print(f"FP sample: {img_id} {cat} {fname} -> v_adj={v_adj:.4f}")

