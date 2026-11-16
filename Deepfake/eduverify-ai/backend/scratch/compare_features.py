import sys, csv, cv2, numpy as np
sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")
from evaluation.train_classifier import extract_features_from_image, FEATURE_NAMES

gt_path = r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\ground_truth.csv"
with open(gt_path, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"{'ID':8s} {'Label':15s} {'fft_ratio':10s} {'noise_std':10s} {'tex_cv':10s} {'lap_var':10s}")
print("-" * 70)
for r in rows:
    cat = r["category"]
    fname = r["file_name"]
    lbl = r["true_label"]
    p = rf"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\{cat}\{fname}"
    img = cv2.imread(p)
    if img is None: continue
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    feat = extract_features_from_image(gray)
    # feat: [s_noise, s_fft, s_lap, s_tex, s_comp, raw_noise, raw_fft, log_lap, raw_cv, raw_comp]
    print(f"{r['image_id']:8s} {lbl:15s} {feat[6]:10.4f} {feat[5]:10.4f} {feat[8]:10.4f} {feat[7]:10.4f}")

