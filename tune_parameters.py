import sys
from pathlib import Path
backend_dir = Path("Deepfake/eduverify-ai/backend").resolve()
sys.path.insert(0, str(backend_dir))

import cv2
import numpy as np
import csv

gt_path = backend_dir / "evaluation" / "ground_truth.csv"
img_base = backend_dir / "evaluation" / "images"

with open(gt_path, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

# Pre-extract raw features for all images
samples = []
for r in rows:
    cat = r["category"]
    fname = r["file_name"]
    t_label = r["true_label"]
    img_path = img_base / cat / fname
    if not img_path.exists():
        continue
    img = cv2.imread(str(img_path))
    if img is None:
        continue
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. Laplacian
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    
    # 2. Sensor noise (lowest 20% blocks)
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    h, w = gray.shape
    bs = 16
    block_stds = []
    for y in range(0, h - bs, bs * 2):
        for x in range(0, w - bs, bs * 2):
            block = lap[y:y+bs, x:x+bs]
            block_stds.append(float(np.std(block)))
    block_stds.sort()
    noise_std = float(np.mean(block_stds[:max(1, len(block_stds) // 5)])) if block_stds else 0.0
    
    # 3. FFT high freq ratio
    dim = 256
    resized = cv2.resize(gray, (dim, dim), interpolation=cv2.INTER_AREA)
    f = np.fft.fft2(resized)
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift) + 1e-8
    cy, cx = dim // 2, dim // 2
    y_idx, x_idx = np.ogrid[:dim, :dim]
    dist = np.sqrt((x_idx - cx)**2 + (y_idx - cy)**2)
    high_mask = dist > (dim // 4)
    fft_ratio = float(np.sum(mag[high_mask]) / np.sum(mag))
    
    # 4. Background tone homogeneity (patches with lowest laplacian variance)
    # This checks paper fiber variation in actual unwritten regions
    patch_means = []
    for y in range(0, h - 32, 32):
        for x in range(0, w - 32, 32):
            p_gray = gray[y:y+32, x:x+32]
            p_var = float(cv2.Laplacian(p_gray, cv2.CV_64F).var())
            if p_var < 50.0:  # purely paper background
                patch_means.append(float(np.mean(p_gray)))
    bg_cv = float(np.std(patch_means) / (np.mean(patch_means) + 1e-5)) if len(patch_means) >= 4 else 0.10
    
    samples.append({
        "id": r["image_id"],
        "name": fname,
        "cat": cat,
        "true_label": t_label,
        "lap_var": lap_var,
        "noise_std": noise_std,
        "fft_ratio": fft_ratio,
        "bg_cv": bg_cv
    })

print(f"Loaded {len(samples)} valid samples.")

# Test scoring formulas
def evaluate_scoring_formula(w_noise, w_fft, w_lap, w_bg, noise_th, fft_low, fft_high):
    ai_scores = []
    real_scores = []
    edited_scores = []
    
    for s in samples:
        # Score noise
        n = s["noise_std"]
        if n < noise_th:
            s_noise = min(1.0, 0.65 + (noise_th - n) * 0.25)
        elif n < 3.0:
            s_noise = 0.35
        else:
            s_noise = 0.12
            
        # Score FFT
        f = s["fft_ratio"]
        if f > fft_high:
            s_fft = min(1.0, 0.60 + (f - fft_high) * 2.5)
        elif f < fft_low:
            s_fft = min(1.0, 0.60 + (fft_low - f) * 4.0)
        else:
            s_fft = 0.15
            
        # Score Laplacian
        l = s["lap_var"]
        if l < 50.0:
            s_lap = 0.70
        elif l > 1200.0:
            s_lap = min(0.85, 0.25 + (l - 1200.0) / 4000.0)
        else:
            s_lap = 0.15
            
        # Score Background CV
        b = s["bg_cv"]
        if b < 0.025:
            s_bg = 0.75
        elif b < 0.06:
            s_bg = 0.40
        else:
            s_bg = 0.12
            
        score = (w_noise * s_noise) + (w_fft * s_fft) + (w_lap * s_lap) + (w_bg * s_bg)
        score = min(1.0, max(0.0, score))
        
        lbl = s["true_label"]
        if lbl == "ai_generated":
            ai_scores.append((score, s["id"], s["cat"]))
        elif lbl in ["real_photo", "real_scan"]:
            real_scores.append((score, s["id"], s["cat"]))
        elif lbl == "edited_real":
            edited_scores.append((score, s["id"], s["cat"]))
            
    avg_ai = np.mean([x[0] for x in ai_scores])
    avg_real = np.mean([x[0] for x in real_scores])
    avg_edited = np.mean([x[0] for x in edited_scores])
    
    # Classification: concerning if score >= 0.45
    tp = sum(1 for x in ai_scores if x[0] >= 0.45) + sum(1 for x in edited_scores if x[0] >= 0.45)
    fn = sum(1 for x in ai_scores if x[0] < 0.45) + sum(1 for x in edited_scores if x[0] < 0.45)
    fp = sum(1 for x in real_scores if x[0] >= 0.45)
    tn = sum(1 for x in real_scores if x[0] < 0.45)
    
    acc = (tp + tn) / (tp + tn + fp + fn) * 100
    rec = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    prec = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    fpr = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0
    
    return {
        "avg_ai": avg_ai,
        "avg_real": avg_real,
        "avg_edited": avg_edited,
        "acc": acc,
        "prec": prec,
        "rec": rec,
        "fpr": fpr,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn
    }

# Grid search for optimal parameters
best_res = None
best_score = -1.0
best_params = None

for w_noise in [0.35, 0.40, 0.45]:
    for w_fft in [0.25, 0.30, 0.35]:
        for w_bg in [0.15, 0.20]:
            w_lap = round(1.0 - w_noise - w_fft - w_bg, 2)
            if w_lap < 0.05:
                continue
            for nth in [2.3, 2.5, 2.8]:
                res = evaluate_scoring_formula(w_noise, w_fft, w_lap, w_bg, nth, 0.35, 0.52)
                # Optimization metric: maximize separation (avg_ai - avg_real) and F1 score with low FPR
                f1 = 2 * res["prec"] * res["rec"] / (res["prec"] + res["rec"]) if (res["prec"] + res["rec"]) > 0 else 0
                sep = res["avg_ai"] - res["avg_real"]
                obj = (f1 * 0.6) + (sep * 100 * 0.4) - (res["fpr"] * 0.5)
                if obj > best_score:
                    best_score = obj
                    best_res = res
                    best_params = (w_noise, w_fft, w_lap, w_bg, nth)

print("\n" + "="*80)
print("OPTIMIZATION RESULTS:")
print("="*80)
print(f"Optimal Weights: Noise={best_params[0]}, FFT={best_params[1]}, Lap={best_params[2]}, BgCV={best_params[3]}")
print(f"Optimal Noise Threshold: {best_params[4]}")
print(f"Avg AI Score     : {best_res['avg_ai']:.4f} (Target: > 0.65)")
print(f"Avg Real Score   : {best_res['avg_real']:.4f} (Target: < 0.30)")
print(f"Avg Edited Score : {best_res['avg_edited']:.4f} (Target: ~ 0.55)")
print(f"Accuracy         : {best_res['acc']:.2f}%")
print(f"Precision        : {best_res['prec']:.2f}%")
print(f"Recall           : {best_res['rec']:.2f}%")
print(f"False Pos Rate   : {best_res['fpr']:.2f}%")
print(f"Confusion Matrix : TP={best_res['tp']}, TN={best_res['tn']}, FP={best_res['fp']}, FN={best_res['fn']}")
