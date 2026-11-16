import sys, csv, cv2, numpy as np
sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")
from api.services.vision import process_vision
from api.services.metadata import process_metadata
from api.services.fusion import calculate_provenance_score, calculate_ocr_consistency_score, _clamp

gt_path = r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\ground_truth.csv"
with open(gt_path, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

# Pre-extract signals for all 40 images
dataset = []
print("Extracting signals for all 40 dataset images...")
for r in rows:
    cat = r["category"]
    fname = r["file_name"]
    lbl = r["true_label"].lower()
    img_id = r["image_id"]
    p = rf"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\{cat}\{fname}"
    
    with open(p, "rb") as f:
        b = f.read()
        
    v_res = process_vision(b)
    m_res = process_metadata(b, filename=fname)
    
    v_data = v_res.get("data", {})
    v_raw = float(v_data.get("raw_visual_score", 0.15))
    q_fac = float(v_data.get("quality_factor", 1.0))
    v_adj = float(v_data.get("adjusted_visual_score", v_raw * q_fac))
    
    m_data = m_res.get("data", {})
    m_score = float(m_data.get("metadata_anomaly_score", 0.20))
    
    p_score, _, _ = calculate_provenance_score(m_res)
    
    # Simple consistency heuristic based on sensor noise & text
    c_score, _, _ = calculate_ocr_consistency_score({}, {}, v_res)
    
    is_concerning = 1 if lbl in ["ai_generated", "edited_real"] else 0
    
    dataset.append({
        "id": img_id,
        "fname": fname,
        "category": cat,
        "label": lbl,
        "is_concerning": is_concerning,
        "v_adj": v_adj,
        "m_score": m_score,
        "p_score": p_score,
        "c_score": c_score
    })

print(f"Loaded {len(dataset)} items.")

# Test weighting strategies
configs = [
    {
        "name": "Standard Prototype (w_v=0.50, w_m=0.20, w_p=0.20, w_c=0.10)",
        "wv": 0.50, "wm": 0.20, "wp": 0.20, "wc": 0.10, "normalize_no_c2pa": False
    },
    {
        "name": "Active Normalization when C2PA=0 (wv=0.625, wm=0.25, wc=0.125)",
        "wv": 0.50, "wm": 0.20, "wp": 0.20, "wc": 0.10, "normalize_no_c2pa": True
    },
    {
        "name": "Tuned Weights (wv=0.60, wm=0.20, wp=0.10, wc=0.10)",
        "wv": 0.60, "wm": 0.20, "wp": 0.10, "wc": 0.10, "normalize_no_c2pa": False
    },
    {
        "name": "Tuned Normalization (wv=0.60, wm=0.20, wp=0.10, wc=0.10 with norm)",
        "wv": 0.60, "wm": 0.20, "wp": 0.10, "wc": 0.10, "normalize_no_c2pa": True
    }
]

for cfg in configs:
    print("\n" + "=" * 70)
    print(f"CONFIGURATION: {cfg['name']}")
    print("=" * 70)
    
    scores = []
    for item in dataset:
        v = item["v_adj"]
        m = item["m_score"]
        p = item["p_score"]
        c = item["c_score"]
        
        if cfg["normalize_no_c2pa"] and p == 0.0:
            sum_active = cfg["wv"] + cfg["wm"] + cfg["wc"]
            s = (cfg["wv"] / sum_active) * v + (cfg["wm"] / sum_active) * m + (cfg["wc"] / sum_active) * c
        else:
            s = cfg["wv"] * v + cfg["wm"] * m + cfg["wp"] * p + cfg["wc"] * c
            
        s = round(_clamp(s, 0.0, 1.0), 4)
        scores.append((item, s))
        
    # Threshold sweep from 0.30 to 0.75 in steps of 0.05
    print(f"{'T_concern':10s} {'Acc':8s} {'Precision':10s} {'Recall':8s} {'FPR':8s} {'FNR':8s} {'Winter Score & Verdict'}")
    print("-" * 80)
    for T in np.arange(0.35, 0.75, 0.05):
        T = round(float(T), 2)
        y_true = [item["is_concerning"] for item, s in scores]
        y_pred = [1 if s >= T else 0 for item, s in scores]
        
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
        tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
        
        acc = (tp + tn) / len(y_true) * 100
        prec = (tp / (tp + fp) * 100) if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn) * 100) if (tp + fn) > 0 else 0.0
        fpr = (fp / (fp + tn) * 100) if (fp + tn) > 0 else 0.0
        fnr = (fn / (fn + tp) * 100) if (fn + tp) > 0 else 0.0
        
        winter_item, winter_s = [(item, s) for item, s in scores if item["id"] == "IMG_040"][0]
        winter_verdict = "CONCERN" if winter_s >= T else ("UNCERTAIN" if winter_s >= (T - 0.15) else "GENUINE")
        
        print(f"{T:10.2f} {acc:7.1f}% {prec:9.1f}% {rec:7.1f}% {fpr:7.1f}% {fnr:7.1f}%  S={winter_s:.4f} -> {winter_verdict}")

