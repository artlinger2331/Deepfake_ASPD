import sys
from pathlib import Path
backend_dir = Path("Deepfake/eduverify-ai/backend").resolve()
sys.path.insert(0, str(backend_dir))

import cv2
import numpy as np
import csv
from api.services.vision import (
    compute_laplacian_score,
    compute_local_noise_score,
    compute_fft_spectral_score,
    compute_texture_uniformity_score,
    compute_compression_artifact_score,
    evaluate_image_quality
)

gt_path = backend_dir / "evaluation" / "ground_truth.csv"
img_base = backend_dir / "evaluation" / "images"

with open(gt_path, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"Analyzing {len(rows)} images...")
print(f"{'ID':<8} {'Cat':<18} {'Label':<12} {'LapVar':<10} {'NoiseStd':<10} {'FFTRatio':<10} {'TexCV':<10} {'CompRatio':<10}")

data_by_label = {}

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
    
    _, lap_var = compute_laplacian_score(gray)
    _, noise_std = compute_local_noise_score(gray)
    _, fft_ratio = compute_fft_spectral_score(gray)
    _, tex_cv = compute_texture_uniformity_score(gray)
    _, comp_ratio = compute_compression_artifact_score(gray)
    
    if t_label not in data_by_label:
        data_by_label[t_label] = []
    data_by_label[t_label].append({
        "id": r["image_id"],
        "name": fname,
        "cat": cat,
        "lap_var": lap_var,
        "noise_std": noise_std,
        "fft_ratio": fft_ratio,
        "tex_cv": tex_cv,
        "comp_ratio": comp_ratio
    })
    print(f"{r['image_id']:<8} {cat:<18} {t_label:<12} {lap_var:<10.1f} {noise_std:<10.2f} {fft_ratio:<10.4f} {tex_cv:<10.4f} {comp_ratio:<10.4f}")

print("\n" + "="*80)
print("EMPIRICAL FEATURE DISTRIBUTIONS ACROSS DATASET:")
print("="*80)
for lbl, items in data_by_label.items():
    laps = [x["lap_var"] for x in items]
    noises = [x["noise_std"] for x in items]
    ffts = [x["fft_ratio"] for x in items]
    cvs = [x["tex_cv"] for x in items]
    comps = [x["comp_ratio"] for x in items]
    print(f"\n[{lbl.upper()}] (N={len(items)} samples):")
    print(f"  Laplacian Var : mean={np.mean(laps):.1f}, median={np.median(laps):.1f}, min={np.min(laps):.1f}, max={np.max(laps):.1f}")
    print(f"  Noise Std     : mean={np.mean(noises):.2f}, median={np.median(noises):.2f}, min={np.min(noises):.2f}, max={np.max(noises):.2f}")
    print(f"  FFT Ratio     : mean={np.mean(ffts):.4f}, median={np.median(ffts):.4f}, min={np.min(ffts):.4f}, max={np.max(ffts):.4f}")
    print(f"  Texture CV    : mean={np.mean(cvs):.4f}, median={np.median(cvs):.4f}, min={np.min(cvs):.4f}, max={np.max(cvs):.4f}")
    print(f"  Comp Ratio    : mean={np.mean(comps):.4f}, median={np.median(comps):.4f}, min={np.min(comps):.4f}, max={np.max(comps):.4f}")

