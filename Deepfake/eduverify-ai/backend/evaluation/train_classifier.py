"""
EduVerify AI - Calibrated Feature Classifier Training Pipeline
===============================================================
Trains a calibrated Random Forest classifier on multi-scale optical,
frequency, texture, and sensor noise features extracted from benchmark student
documents and synthetic/edited images.

Inputs:
  - evaluation/ground_truth.csv
  - evaluation/images/*

Outputs:
  - backend/models/visual_detector.joblib
  - Cross-validation performance report (Accuracy, ROC-AUC, Precision, Recall, FPR)
"""

import sys
import csv
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import cv2
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    roc_auc_score,
    precision_score,
    recall_score,
    confusion_matrix
)

# Add backend directory to sys.path so we can reuse vision feature scorers
EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.services.vision import (
    compute_laplacian_score,
    compute_local_noise_score,
    compute_fft_spectral_score,
    compute_texture_uniformity_score,
    compute_compression_artifact_score
)

GT_PATH = EVAL_DIR / "ground_truth.csv"
IMAGES_DIR = EVAL_DIR / "images"
MODELS_DIR = BACKEND_DIR / "models"

FEATURE_NAMES = [
    "s_noise",             # Normalized sensor noise score (sterile -> high)
    "s_fft",               # Normalized FFT high-frequency spectral score
    "s_lap",               # Normalized Laplacian edge profile score
    "s_tex",               # Normalized texture uniformity score
    "s_comp",              # Normalized JPEG compression artifact score
    "raw_noise_std",       # Physical background camera sensor noise (Poisson-Gaussian)
    "raw_fft_ratio",       # 2D FFT spectral high-frequency energy ratio
    "log_lap_var",         # Log10-scaled Laplacian edge variance
    "raw_texture_cv",      # Raw patch texture luminance coefficient of variation
    "raw_comp_ratio"       # 8x8 JPEG quantization blockiness ratio
]


def extract_features_from_image(gray: np.ndarray) -> np.ndarray:
    """
    Extracts the 10 standardized forensic & normalized features from a grayscale image.
    Returns: 1D numpy array of length 10 matching FEATURE_NAMES.
    """
    s_lap, raw_lap = compute_laplacian_score(gray)
    s_noise, raw_noise = compute_local_noise_score(gray)
    s_fft, raw_fft = compute_fft_spectral_score(gray)
    s_tex, raw_cv = compute_texture_uniformity_score(gray)
    s_comp, raw_comp = compute_compression_artifact_score(gray)
    log_lap = float(np.log10(raw_lap + 1.0))

    return np.array([
        s_noise, s_fft, s_lap, s_tex, s_comp,
        raw_noise, raw_fft, log_lap, raw_cv, raw_comp
    ], dtype=np.float32)


def load_dataset() -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
    """Loads all annotated images from ground_truth.csv and computes feature vectors."""
    if not GT_PATH.exists():
        raise FileNotFoundError(f"Ground truth file not found at {GT_PATH}")

    with open(GT_PATH, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    X_list = []
    y_list = []
    metadata_list = []

    for r in reader:
        cat = r.get("category", "").strip()
        fname = r.get("file_name", "").strip()
        t_label = r.get("true_label", "").strip().lower()

        # Class 1: Concerning (AI-generated or edited)
        # Class 0: Genuine (Real physical photo or flatbed scan)
        is_concerning = 1 if t_label in ["ai_generated", "edited_real"] else 0

        img_path = IMAGES_DIR / cat / fname
        if not img_path.exists():
            print(f"[WARN] Image file not found: {img_path}")
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            print(f"[WARN] Failed to decode image: {img_path}")
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        feat = extract_features_from_image(gray)

        X_list.append(feat)
        y_list.append(is_concerning)
        metadata_list.append({
            "image_id": r.get("image_id", ""),
            "file_name": fname,
            "category": cat,
            "true_label": t_label,
            "is_concerning": is_concerning,
            "path": img_path
        })

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    return X, y, metadata_list


def train_and_evaluate():
    print("================================================================")
    print("   EduVerify AI - Calibrated Feature Classifier Training        ")
    print("================================================================")
    X, y, meta = load_dataset()
    n_samples, n_features = X.shape
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))

    print(f"Total Samples Loaded : {n_samples}")
    print(f"Class Breakdown       : {n_pos} Concerning (AI / Edited), {n_neg} Authentic (Real Photo / Scan)")
    print(f"Features Extracted   : {n_features} features\n")

    # 1. Stratified 5-Fold Cross Validation for Unbiased Performance Estimation
    skf = StratifiedKFold(n_splits=min(5, min(n_pos, n_neg)), shuffle=True, random_state=42)
    oof_probs = np.zeros(n_samples)

    for train_idx, val_idx in skf.split(X, y):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr = y[train_idx]

        fold_clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            class_weight="balanced",
            random_state=42
        )
        fold_clf.fit(X_tr, y_tr)
        oof_probs[val_idx] = fold_clf.predict_proba(X_val)[:, 1]

    # Evaluate Out-Of-Fold at decision threshold 0.50
    oof_preds = (oof_probs >= 0.50).astype(int)
    acc = accuracy_score(y, oof_preds) * 100
    roc_auc = roc_auc_score(y, oof_probs) * 100
    prec = precision_score(y, oof_preds, zero_division=0) * 100
    rec = recall_score(y, oof_preds, zero_division=0) * 100

    tn, fp, fn, tp = confusion_matrix(y, oof_preds).ravel()
    fpr = (fp / (fp + tn) * 100) if (fp + tn) > 0 else 0.0
    fnr = (fn / (fn + tp) * 100) if (fn + tp) > 0 else 0.0

    print("----------------------------------------------------------------")
    print("5-FOLD STRATIFIED CROSS-VALIDATION RESULTS (Out-of-Fold)")
    print("----------------------------------------------------------------")
    print(f"Accuracy               : {acc:.2f}%")
    print(f"ROC-AUC Score          : {roc_auc:.2f}%")
    print(f"Precision              : {prec:.2f}%")
    print(f"Recall (Sensitivity)   : {rec:.2f}%")
    print(f"False Positive Rate    : {fpr:.2f}% (Falsely accused authentic work)")
    print(f"False Negative Rate    : {fnr:.2f}% (Undetected AI / edited notes)")
    print(f"Confusion Matrix       : TP={tp}, TN={tn}, FP={fp}, FN={fn}\n")

    # 2. Train Final Production Model on Full Dataset
    final_clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        class_weight="balanced",
        random_state=42
    )
    final_clf.fit(X, y)

    # Feature Importances
    importances = final_clf.feature_importances_
    print("----------------------------------------------------------------")
    print("TRAINED FORENSIC FEATURE IMPORTANCES (Random Forest)")
    print("----------------------------------------------------------------")
    for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True):
        bar = "#" * int(imp * 40)
        print(f"  {name:<18} : {imp:6.4f}  {bar}")
    print("----------------------------------------------------------------\n")

    # 3. Export Model Pipeline
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_export_path = MODELS_DIR / "visual_detector.joblib"

    artifact = {
        "model": final_clf,
        "feature_names": FEATURE_NAMES,
        "feature_importances": {k: float(v) for k, v in zip(FEATURE_NAMES, importances)},
        "metrics": {
            "cv_accuracy": float(acc),
            "cv_roc_auc": float(roc_auc),
            "cv_precision": float(prec),
            "cv_recall": float(rec),
            "cv_fpr": float(fpr),
            "cv_fnr": float(fnr),
            "n_samples": n_samples,
            "n_concerning": n_pos,
            "n_authentic": n_neg
        },
        "model_type": "RandomForestClassifier",
        "version": "2.0.0"
    }

    joblib.dump(artifact, model_export_path)
    print(f"[SUCCESS] Trained model successfully saved to:")
    print(f"          {model_export_path}\n")

    # Print predictions on all training samples
    print("----------------------------------------------------------------")
    print(f"{'ID':<8} {'Category':<18} {'True Label':<12} {'P(AI/Concern)':<14} {'Verdict':<12}")
    print("----------------------------------------------------------------")
    final_probs = final_clf.predict_proba(X)[:, 1]
    for m, p in zip(meta, final_probs):
        pred_label = "CONCERN" if p >= 0.50 else "GENUINE"
        is_correct = (m["is_concerning"] == (p >= 0.50))
        check = "[OK]" if is_correct else "[MISS]"
        print(f"{m['image_id']:<8} {m['category']:<18} {m['true_label']:<12} {p:10.4f}     {pred_label:<10} {check}")

    print("================================================================\n")
    return artifact


if __name__ == "__main__":
    train_and_evaluate()
