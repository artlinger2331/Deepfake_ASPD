"""
EduVerify AI - Comprehensive Metric Calculation & Evaluation Engine
====================================================================
Evaluates the EduVerify AI FastAPI backend against ground truth standards.

Inputs:
  - evaluation/ground_truth.csv
  - evaluation/results/evaluation_results.csv
  - evaluation/results/{image_id}_response.json (optional for raw text extraction)
  - evaluation/transcriptions/{image_id}_reference.txt (optional for CER/WER)

Sections Evaluated:
  A. AI-generated / Tampering Detection (Accuracy, Precision, Recall, F1, FPR, FNR, Breakdown by Type)
  B. Visual Synthetic Score (Averages, Distribution, Threshold Sweeps at 0.3 - 0.8)
  C. Metadata Forensics (EXIF Presence, Manipulation Software Detection, Metadata FPR)
  D. C2PA / Content Credentials (Audit & Policy Compliance)
  E. Handwriting Detection (Accuracy, F1, False Positives on Printed & No-text)
  F. Printed-text Detection (Evaluation & Capability Reporting)
  G. No-text / Hallucination Detection (Accuracy, Precision, Recall, F1)
  H. Handwriting Transcription (CER, WER, [unclear] Markers, Fallback Rates)

Usage:
    python calculate_metrics.py [--output-report evaluation_report.md]
"""

import os
import sys
import csv
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

EVAL_DIR = Path(__file__).resolve().parent
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth.csv"
RESULTS_DIR = EVAL_DIR / "results"
RESULTS_CSV_PATH = RESULTS_DIR / "evaluation_results.csv"
TRANSCRIPTIONS_DIR = EVAL_DIR / "transcriptions"
DEFAULT_REPORT_PATH = EVAL_DIR / "evaluation_report.md"


def safe_div(num: float, den: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default on zero division."""
    return (num / den) if den != 0 else default


def levenshtein_distance(seq1, seq2) -> int:
    """Calculates Levenshtein edit distance between two sequences."""
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if seq1[i - 1] == seq2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,       # deletion
                dp[i][j - 1] + 1,       # insertion
                dp[i - 1][j - 1] + cost  # substitution
            )
    return dp[m][n]


def compute_cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate."""
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    return min(1.0, levenshtein_distance(ref_chars, hyp_chars) / len(ref_chars))


def compute_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return min(1.0, levenshtein_distance(ref_words, hyp_words) / len(ref_words))


def load_data() -> Tuple[List[Dict[str, Any]], bool]:
    """Loads ground_truth.csv and matches with results/evaluation_results.csv."""
    if not GROUND_TRUTH_PATH.exists():
        print(f"[ERROR] Ground truth file not found at: {GROUND_TRUTH_PATH}")
        sys.exit(1)

    with open(GROUND_TRUTH_PATH, mode="r", encoding="utf-8") as f:
        gt_reader = csv.DictReader(f)
        gt_records = [r for r in gt_reader if (r.get("file_name") or r.get("filename") or "").strip()]

    if not gt_records:
        print("[INFO] ground_truth.csv is empty. Please add benchmark entries.")
        sys.exit(0)

    if not RESULTS_CSV_PATH.exists():
        print(f"[WARN] Results file not found at: {RESULTS_CSV_PATH}")
        print("Please run evaluation/run_evaluation.py first to execute the backend benchmarks.")
        return [], False

    with open(RESULTS_CSV_PATH, mode="r", encoding="utf-8") as f:
        res_reader = csv.DictReader(f)
        res_records = [r for r in res_reader if (r.get("file_name") or r.get("image_id") or "").strip()]

    # Index results by file_name and image_id
    res_map = {}
    for r in res_records:
        fn = (r.get("file_name") or "").strip().lower()
        img_id = (r.get("image_id") or "").strip().lower()
        if fn:
            res_map[fn] = r
        if img_id:
            res_map[img_id] = r

    # Merge records
    merged = []
    for gt in gt_records:
        fn = (gt.get("file_name") or gt.get("filename") or "").strip().lower()
        img_id = (gt.get("image_id") or "").strip().lower()
        res = res_map.get(fn) or res_map.get(img_id) or {}
        merged.append({"gt": gt, "res": res})

    return merged, True


def evaluate_all(merged_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Executes the full evaluation across sections A through H."""
    metrics = {}
    
    total_samples = len(merged_data)
    evaluated_samples = sum(1 for m in merged_data if m["res"])

    # -------------------------------------------------------------------------
    # A. AI-generated / Tampering Detection
    # -------------------------------------------------------------------------
    # Mapping definitions:
    # Not concerning: likely_genuine, genuine
    # Concerning: uncertain, concern, possibly_ai_generated, ai_generated, edited_real
    NOT_CONCERNING_VERDICTS = {"genuine", "likely_genuine", "authentic"}
    CONCERNING_VERDICTS = {"concern", "uncertain", "possibly_ai_generated", "ai_generated", "edited_real"}
    REAL_TRUE_LABELS = {"real_photo", "real_scan"}
    CONCERN_TRUE_LABELS = {"ai_generated", "edited_real"}

    tp = tn = fp = fn = 0
    by_category_counts = {
        "real_photo": {"total": 0, "correct": 0},
        "real_scan": {"total": 0, "correct": 0},
        "ai_generated": {"total": 0, "correct": 0},
        "edited_real": {"total": 0, "correct": 0},
    }

    for item in merged_data:
        res = item["res"]
        if not res:
            continue
        gt = item["gt"]
        t_label = gt.get("true_label", "").strip().lower()
        p_verdict = res.get("final_verdict", "").strip().lower()

        is_actual_concerning = t_label in CONCERN_TRUE_LABELS
        is_pred_concerning = p_verdict in CONCERNING_VERDICTS or p_verdict not in NOT_CONCERNING_VERDICTS

        if is_actual_concerning and is_pred_concerning:
            tp += 1
        elif not is_actual_concerning and not is_pred_concerning:
            tn += 1
        elif not is_actual_concerning and is_pred_concerning:
            fp += 1  # False Accusation
        elif is_actual_concerning and not is_pred_concerning:
            fn += 1  # Missed Tampering

        # Sub-category accuracy
        if t_label in by_category_counts:
            by_category_counts[t_label]["total"] += 1
            if (t_label in REAL_TRUE_LABELS and not is_pred_concerning) or \
               (t_label in CONCERN_TRUE_LABELS and is_pred_concerning):
                by_category_counts[t_label]["correct"] += 1

    accuracy_a = safe_div(tp + tn, tp + tn + fp + fn) * 100
    precision_a = safe_div(tp, tp + fp) * 100
    recall_a = safe_div(tp, tp + fn) * 100
    f1_a = safe_div(2 * precision_a * recall_a, precision_a + recall_a)
    fpr_a = safe_div(fp, fp + tn) * 100  # False Positive Rate
    fnr_a = safe_div(fn, fn + tp) * 100  # False Negative Rate

    cat_breakdown = {}
    for cat, d in by_category_counts.items():
        cat_breakdown[cat] = {
            "total": d["total"],
            "correct": d["correct"],
            "accuracy": safe_div(d["correct"], d["total"]) * 100
        }

    metrics["section_a"] = {
        "total_evaluated": evaluated_samples,
        "accuracy": accuracy_a,
        "precision": precision_a,
        "recall": recall_a,
        "f1": f1_a,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "fpr": fpr_a, "fnr": fnr_a,
        "category_breakdown": cat_breakdown
    }

    # -------------------------------------------------------------------------
    # B. Visual Synthetic Score Analysis
    # -------------------------------------------------------------------------
    scores_real = []
    scores_ai = []
    scores_edited = []
    scores_by_cat = {}
    all_scores_with_label = []

    for item in merged_data:
        res = item["res"]
        if not res:
            continue
        gt = item["gt"]
        t_label = gt.get("true_label", "").strip().lower()
        cat = gt.get("category", "").strip().lower()

        v_score_raw = res.get("visual_synthetic_score")
        if v_score_raw is not None and str(v_score_raw).strip() != "":
            try:
                v_score = float(v_score_raw)
                # Normalize if integer 0-100 was stored
                if v_score > 1.0:
                    v_score /= 100.0

                if t_label in REAL_TRUE_LABELS:
                    scores_real.append(v_score)
                elif t_label == "ai_generated":
                    scores_ai.append(v_score)
                elif t_label == "edited_real":
                    scores_edited.append(v_score)

                scores_by_cat.setdefault(cat, []).append(v_score)
                all_scores_with_label.append((v_score, t_label in CONCERN_TRUE_LABELS))
            except ValueError:
                pass

    # Threshold sweeps at 0.3, 0.4, 0.5, 0.6, 0.7, 0.8
    threshold_results = {}
    for th in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        t_tp = t_tn = t_fp = t_fn = 0
        for score, is_concerning in all_scores_with_label:
            pred_concerning = (score >= th)
            if is_concerning and pred_concerning:
                t_tp += 1
            elif not is_concerning and not pred_concerning:
                t_tn += 1
            elif not is_concerning and pred_concerning:
                t_fp += 1
            elif is_concerning and not pred_concerning:
                t_fn += 1
        t_acc = safe_div(t_tp + t_tn, len(all_scores_with_label)) * 100
        t_prec = safe_div(t_tp, t_tp + t_fp) * 100
        t_rec = safe_div(t_tp, t_tp + t_fn) * 100
        t_f1 = safe_div(2 * t_prec * t_rec, t_prec + t_rec)
        threshold_results[th] = {"accuracy": t_acc, "precision": t_prec, "recall": t_rec, "f1": t_f1}

    cat_dist = {}
    for c, scs in scores_by_cat.items():
        cat_dist[c] = {
            "count": len(scs),
            "mean": safe_div(sum(scs), len(scs)),
            "min": min(scs) if scs else 0.0,
            "max": max(scs) if scs else 0.0
        }

    metrics["section_b"] = {
        "avg_real": safe_div(sum(scores_real), len(scores_real)),
        "avg_ai": safe_div(sum(scores_ai), len(scores_ai)),
        "avg_edited": safe_div(sum(scores_edited), len(scores_edited)),
        "distribution_by_category": cat_dist,
        "threshold_sweeps": threshold_results
    }

    # -------------------------------------------------------------------------
    # C. Metadata Forensics
    # -------------------------------------------------------------------------
    real_total = real_with_metadata = real_without_metadata = 0
    ai_total = ai_with_software = 0
    edited_total = edited_with_software = 0
    real_flagged_as_manipulated = 0

    for item in merged_data:
        res = item["res"]
        if not res:
            continue
        gt = item["gt"]
        t_label = gt.get("true_label", "").strip().lower()

        cam = (res.get("camera_make_model") or "").strip()
        soft = (res.get("software_used") or "").strip().lower()
        meta_status = (res.get("metadata_status") or "").strip().lower()

        has_cam = bool(cam)
        has_software = bool(soft and soft not in ["none", "null", "false"])

        if t_label in REAL_TRUE_LABELS:
            real_total += 1
            if has_cam:
                real_with_metadata += 1
            else:
                real_without_metadata += 1
            if has_software or meta_status == "warning":
                real_flagged_as_manipulated += 1

        elif t_label == "ai_generated":
            ai_total += 1
            if has_software:
                ai_with_software += 1

        elif t_label == "edited_real":
            edited_total += 1
            if has_software:
                edited_with_software += 1

    metrics["section_c"] = {
        "pct_real_normal_metadata": safe_div(real_with_metadata, real_total) * 100,
        "pct_real_no_metadata": safe_div(real_without_metadata, real_total) * 100,
        "pct_ai_software_detected": safe_div(ai_with_software, ai_total) * 100,
        "pct_edited_software_detected": safe_div(edited_with_software, edited_total) * 100,
        "metadata_false_positive_rate": safe_div(real_flagged_as_manipulated, real_total) * 100
    }

    # -------------------------------------------------------------------------
    # D. C2PA / Content Credentials
    # -------------------------------------------------------------------------
    c2pa_total = evaluated_samples
    c2pa_found = c2pa_valid = c2pa_invalid = c2pa_missing = 0
    missing_c2pa_falsely_accused = 0

    for item in merged_data:
        res = item["res"]
        if not res:
            continue
        gt = item["gt"]
        c2pa_stat = (res.get("c2pa_status") or "missing").strip().lower()
        p_verdict = res.get("final_verdict", "").strip().lower()
        t_label = gt.get("true_label", "").strip().lower()

        if c2pa_stat in ["valid", "present", "signed"]:
            c2pa_found += 1
            c2pa_valid += 1
        elif c2pa_stat in ["invalid", "tampered", "revoked"]:
            c2pa_found += 1
            c2pa_invalid += 1
        else:
            c2pa_missing += 1
            # Check if missing C2PA alone improperly condemned an authentic real paper
            if t_label in REAL_TRUE_LABELS and p_verdict == "concern":
                missing_c2pa_falsely_accused += 1

    metrics["section_d"] = {
        "pct_credentials_found": safe_div(c2pa_found, c2pa_total) * 100,
        "pct_valid_credentials": safe_div(c2pa_valid, c2pa_total) * 100,
        "pct_invalid_credentials": safe_div(c2pa_invalid, c2pa_total) * 100,
        "pct_no_credentials": safe_div(c2pa_missing, c2pa_total) * 100,
        "missing_c2pa_falsely_accused_count": missing_c2pa_falsely_accused
    }

    # -------------------------------------------------------------------------
    # E. Handwriting Detection
    # -------------------------------------------------------------------------
    hw_tp = hw_tn = hw_fp = hw_fn = 0
    hw_correct_count = hw_total = 0
    printed_false_hw = printed_total = 0
    notext_false_hw = notext_total = 0

    for item in merged_data:
        res = item["res"]
        if not res:
            continue
        gt = item["gt"]
        has_hw_gt = gt.get("contains_handwriting", "no").strip().lower() == "yes"
        is_printed_gt = gt.get("contains_printed_text", "no").strip().lower() == "yes"
        is_notext_gt = gt.get("contains_no_text", "no").strip().lower() == "yes"

        has_hw_pred = str(res.get("handwriting_detection", "")).strip().lower() in ["true", "1", "yes"]

        if has_hw_gt and has_hw_pred:
            hw_tp += 1
        elif not has_hw_gt and not has_hw_pred:
            hw_tn += 1
        elif not has_hw_gt and has_hw_pred:
            hw_fp += 1
        elif has_hw_gt and not has_hw_pred:
            hw_fn += 1

        if has_hw_gt:
            hw_total += 1
            if has_hw_pred:
                hw_correct_count += 1

        if is_printed_gt and not has_hw_gt:
            printed_total += 1
            if has_hw_pred:
                printed_false_hw += 1

        if is_notext_gt:
            notext_total += 1
            if has_hw_pred:
                notext_false_hw += 1

    hw_acc = safe_div(hw_tp + hw_tn, hw_tp + hw_tn + hw_fp + hw_fn) * 100
    hw_prec = safe_div(hw_tp, hw_tp + hw_fp) * 100
    hw_rec = safe_div(hw_tp, hw_tp + hw_fn) * 100
    hw_f1 = safe_div(2 * hw_prec * hw_rec, hw_prec + hw_rec)

    metrics["section_e"] = {
        "accuracy": hw_acc,
        "precision": hw_prec,
        "recall": hw_rec,
        "f1": hw_f1,
        "tp": hw_tp, "tn": hw_tn, "fp": hw_fp, "fn": hw_fn,
        "pct_handwritten_detected": safe_div(hw_correct_count, hw_total) * 100,
        "pct_printed_falsely_hw": safe_div(printed_false_hw, printed_total) * 100,
        "pct_notext_falsely_hw": safe_div(notext_false_hw, notext_total) * 100
    }

    # -------------------------------------------------------------------------
    # F. Printed-Text Detection
    # -------------------------------------------------------------------------
    pr_tp = pr_tn = pr_fp = pr_fn = 0
    pr_correct = pr_total = 0
    hw_falsely_pr = hw_total_pr = 0
    notext_falsely_pr = notext_total_pr = 0

    for item in merged_data:
        res = item["res"]
        if not res:
            continue
        gt = item["gt"]
        has_pr_gt = gt.get("contains_printed_text", "no").strip().lower() == "yes"
        has_hw_gt = gt.get("contains_handwriting", "no").strip().lower() == "yes"
        is_notext_gt = gt.get("contains_no_text", "no").strip().lower() == "yes"

        has_pr_pred = str(res.get("printed_text_detection", "")).strip().lower() in ["true", "1", "yes"]

        if has_pr_gt and has_pr_pred:
            pr_tp += 1
        elif not has_pr_gt and not has_pr_pred:
            pr_tn += 1
        elif not has_pr_gt and has_pr_pred:
            pr_fp += 1
        elif has_pr_gt and not has_pr_pred:
            pr_fn += 1

        if has_pr_gt:
            pr_total += 1
            if has_pr_pred:
                pr_correct += 1
        if has_hw_gt and not has_pr_gt:
            hw_total_pr += 1
            if has_pr_pred:
                hw_falsely_pr += 1
        if is_notext_gt:
            notext_total_pr += 1
            if has_pr_pred:
                notext_falsely_pr += 1

    pr_acc = safe_div(pr_tp + pr_tn, pr_tp + pr_tn + pr_fp + pr_fn) * 100
    pr_prec = safe_div(pr_tp, pr_tp + pr_fp) * 100
    pr_rec = safe_div(pr_tp, pr_tp + pr_fn) * 100
    pr_f1 = safe_div(2 * pr_prec * pr_rec, pr_prec + pr_rec)

    metrics["section_f"] = {
        "accuracy": pr_acc,
        "precision": pr_prec,
        "recall": pr_rec,
        "f1": pr_f1,
        "tp": pr_tp, "tn": pr_tn, "fp": pr_fp, "fn": pr_fn,
        "pct_printed_detected": safe_div(pr_correct, pr_total) * 100,
        "pct_handwriting_falsely_printed": safe_div(hw_falsely_pr, hw_total_pr) * 100,
        "pct_notext_falsely_printed": safe_div(notext_falsely_pr, notext_total_pr) * 100,
        "capability_note": "Backend currently reports 'not_supported' for printed text classification"
    }

    # -------------------------------------------------------------------------
    # G. No-Text Detection
    # -------------------------------------------------------------------------
    nt_tp = nt_tn = nt_fp = nt_fn = 0

    for item in merged_data:
        res = item["res"]
        if not res:
            continue
        gt = item["gt"]
        is_nt_gt = gt.get("contains_no_text", "no").strip().lower() == "yes"
        is_nt_pred = str(res.get("no_text_detection", "")).strip().lower() in ["true", "1", "yes"]

        if is_nt_gt and is_nt_pred:
            nt_tp += 1
        elif not is_nt_gt and not is_nt_pred:
            nt_tn += 1
        elif not is_nt_gt and is_nt_pred:
            nt_fp += 1
        elif is_nt_gt and not is_nt_pred:
            nt_fn += 1

    nt_acc = safe_div(nt_tp + nt_tn, nt_tp + nt_tn + nt_fp + nt_fn) * 100
    nt_prec = safe_div(nt_tp, nt_tp + nt_fp) * 100
    nt_rec = safe_div(nt_tp, nt_tp + nt_fn) * 100
    nt_f1 = safe_div(2 * nt_prec * nt_rec, nt_prec + nt_rec)

    metrics["section_g"] = {
        "accuracy": nt_acc,
        "precision": nt_prec,
        "recall": nt_rec,
        "f1": nt_f1,
        "tp": nt_tp, "tn": nt_tn, "fp": nt_fp, "fn": nt_fn
    }

    # -------------------------------------------------------------------------
    # H. Handwriting Transcription Accuracy
    # -------------------------------------------------------------------------
    cer_scores = []
    wer_scores = []
    exact_matches = 0
    conf_scores = []
    unclear_count = 0
    fallback_cases = 0
    has_reference_transcriptions = False

    for item in merged_data:
        res = item["res"]
        if not res:
            continue
        gt = item["gt"]
        img_id = gt.get("image_id", "")
        ref_file = gt.get("reference_transcription_file") or gt.get("transcription_file") or ""

        # Check candidate reference paths
        ref_path = None
        if ref_file:
            cand = TRANSCRIPTIONS_DIR / ref_file
            if cand.exists():
                ref_path = cand
        if not ref_path and img_id:
            cand = TRANSCRIPTIONS_DIR / f"{img_id}_reference.txt"
            if cand.exists():
                ref_path = cand

        # Extract predicted text (from raw JSON response if available)
        pred_text = ""
        json_path = RESULTS_DIR / f"{img_id}_response.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as jf:
                    j_data = json.load(jf)
                    pred_text = j_data.get("extracted_text") or j_data.get("ocr_text") or ""
            except Exception:
                pass

        if not pred_text:
            pred_text = res.get("ocr_text") or ""

        # Unclear markers count
        unclear_count += pred_text.count("[unclear]") + pred_text.count("[?]")

        # Fallback count
        if str(res.get("fallback_usage", "")).strip().lower() in ["true", "1", "yes"]:
            fallback_cases += 1

        conf_raw = res.get("ocr_confidence") or res.get("confidence_score")
        if conf_raw is not None and str(conf_raw).strip() != "":
            try:
                conf_scores.append(float(conf_raw))
            except ValueError:
                pass

        # Calculate CER and WER if reference exists
        if ref_path and ref_path.exists():
            has_reference_transcriptions = True
            with open(ref_path, "r", encoding="utf-8") as rf:
                ref_text = rf.read().strip()

            c_err = compute_cer(ref_text, pred_text)
            w_err = compute_wer(ref_text, pred_text)
            cer_scores.append(c_err)
            wer_scores.append(w_err)
            if c_err == 0.0 or w_err < 0.05:
                exact_matches += 1

    metrics["section_h"] = {
        "has_references": has_reference_transcriptions,
        "avg_cer": (safe_div(sum(cer_scores), len(cer_scores)) * 100) if cer_scores else None,
        "avg_wer": (safe_div(sum(wer_scores), len(wer_scores)) * 100) if wer_scores else None,
        "pct_correct_transcription": safe_div(exact_matches, len(cer_scores)) * 100 if cer_scores else None,
        "avg_confidence": safe_div(sum(conf_scores), len(conf_scores)) if conf_scores else 0.0,
        "unclear_markers_count": unclear_count,
        "fallback_cases_count": fallback_cases,
        "evaluated_transcriptions": len(cer_scores)
    }

    return metrics


def print_and_save_report(metrics: Dict[str, Any], output_path: Path):
    """Outputs the complete metrics breakdown to terminal and writes evaluation_report.md."""
    a = metrics["section_a"]
    b = metrics["section_b"]
    c = metrics["section_c"]
    d = metrics["section_d"]
    e = metrics["section_e"]
    f = metrics["section_f"]
    g = metrics["section_g"]
    h = metrics["section_h"]

    print("\n========================================================")
    print("        EduVerify AI - Comprehensive Evaluation Report   ")
    print("========================================================")
    print(f"Total Submissions Evaluated: {a['total_evaluated']}")
    print("--------------------------------------------------------")
    print(f"A. AI-GENERATED / TAMPERING DETECTION:")
    print(f"   Accuracy            : {a['accuracy']:.1f}%")
    print(f"   Precision           : {a['precision']:.1f}%")
    print(f"   Recall              : {a['recall']:.1f}%")
    print(f"   F1-Score            : {a['f1']:.1f}%")
    print(f"   False Positive Rate : {a['fpr']:.1f}% (False Accusations)")
    print(f"   False Negative Rate : {a['fnr']:.1f}% (Missed AI/Edits)")
    print(f"   Confusion Matrix    : TP={a['tp']}, TN={a['tn']}, FP={a['fp']}, FN={a['fn']}")
    print("   Category Accuracy Breakdown:")
    for cat, data in a["category_breakdown"].items():
        print(f"     - {cat:<18}: {data['accuracy']:.1f}% ({data['correct']}/{data['total']})")

    print("\nB. VISUAL SYNTHETIC SCORE:")
    print(f"   Avg Real Score      : {b['avg_real']:.3f}")
    print(f"   Avg AI Score        : {b['avg_ai']:.3f}")
    print(f"   Avg Edited Score    : {b['avg_edited']:.3f}")
    print("   Threshold Sweeps (Score >= Thresh -> Flag Concern):")
    for th, res in b["threshold_sweeps"].items():
        print(f"     Thresh {th:.1f} -> Acc: {res['accuracy']:.1f}%, Prec: {res['precision']:.1f}%, Rec: {res['recall']:.1f}%, F1: {res['f1']:.1f}%")

    print("\nC. METADATA FORENSICS:")
    print(f"   Real with EXIF Hardware : {c['pct_real_normal_metadata']:.1f}%")
    print(f"   Real with Missing EXIF  : {c['pct_real_no_metadata']:.1f}% (WhatsApp/Web)")
    print(f"   AI with Software Tags   : {c['pct_ai_software_detected']:.1f}%")
    print(f"   Edited with Software    : {c['pct_edited_software_detected']:.1f}%")
    print(f"   Metadata False Pos Rate : {c['metadata_false_positive_rate']:.1f}%")

    print("\nD. C2PA PROVENANCE AUDIT:")
    print(f"   Credentials Present     : {d['pct_credentials_found']:.1f}%")
    print(f"   No Credentials          : {d['pct_no_credentials']:.1f}%")
    print(f"   Missing Falsely Accused : {d['missing_c2pa_falsely_accused_count']}")

    print("\nE. HANDWRITING DETECTION:")
    print(f"   Accuracy    : {e['accuracy']:.1f}% | Precision: {e['precision']:.1f}% | Recall: {e['recall']:.1f}% | F1: {e['f1']:.1f}%")
    print(f"   Correctly Detected HW   : {e['pct_handwritten_detected']:.1f}%")
    print(f"   Printed Falsely HW      : {e['pct_printed_falsely_hw']:.1f}%")
    print(f"   No-Text Falsely HW      : {e['pct_notext_falsely_hw']:.1f}%")

    print("\nF. PRINTED-TEXT DETECTION:")
    print(f"   Accuracy    : {f['accuracy']:.1f}% | Recall: {f['recall']:.1f}%")
    print(f"   Note        : {f['capability_note']}")

    print("\nG. NO-TEXT SAFEGUARDS:")
    print(f"   Accuracy    : {g['accuracy']:.1f}% | Precision: {g['precision']:.1f}% | Recall: {g['recall']:.1f}% | F1: {g['f1']:.1f}%")

    print("\nH. HANDWRITING TRANSCRIPTION:")
    if h["has_references"]:
        print(f"   Character Error Rate (CER) : {h['avg_cer']:.1f}%")
        print(f"   Word Error Rate (WER)      : {h['avg_wer']:.1f}%")
        print(f"   Exact / Clean Matches      : {h['pct_correct_transcription']:.1f}%")
    else:
        print("   Character Error Rate (CER) : N/A (No reference .txt files found)")
        print("   Word Error Rate (WER)      : N/A (Transcription accuracy cannot be measured yet)")
    print(f"   Avg Transcription Conf     : {h['avg_confidence']:.1f}%")
    print(f"   [unclear] Markers Found    : {h['unclear_markers_count']}")
    print(f"   Fallback OCR Cases Triggered: {h['fallback_cases_count']}")
    print("========================================================\n")

    # Generate Markdown Report
    report_md = f"""# EduVerify AI — Comprehensive Benchmark & Metrics Report
*Generated by calculate_metrics.py*

---

## A. AI-Generated & Tampering Detection

| Metric | Score | Explanation / Target |
| :--- | :--- | :--- |
| **Overall Accuracy** | **{a['accuracy']:.1f}%** | Correct classifications across all categories |
| **Precision** | **{a['precision']:.1f}%** | Accuracy of positive tampering flags |
| **Recall (Sensitivity)** | **{a['recall']:.1f}%** | Ability to catch synthetic/edited documents |
| **F1-Score** | **{a['f1']:.1f}%** | Harmonic balance between Precision & Recall |
| **False-Positive Rate (FPR)** | **{a['fpr']:.1f}%** | Critical ethical metric: False accusations on real student work |
| **False-Negative Rate (FNR)** | **{a['fnr']:.1f}%** | Undetected synthetic or manipulated submissions |

### Confusion Matrix
| Actual \\ Predicted | Predicted: Not Concerning (Genuine) | Predicted: Concerning (AI / Edited / Uncertain) |
| :--- | :---: | :---: |
| **Actual: Real (Photo / Scan)** | **{a['tn']} (TN)** | **{a['fp']} (FP - False Accusation)** |
| **Actual: Tampered (AI / Edited)** | **{a['fn']} (FN - Missed)** | **{a['tp']} (TP)** |

### Performance Breakdown by Input Category
| Image Category | Evaluated | Correct | Accuracy |
| :--- | :---: | :---: | :---: |
| **Real Camera Photos** (`real_photo`) | {a['category_breakdown']['real_photo']['total']} | {a['category_breakdown']['real_photo']['correct']} | **{a['category_breakdown']['real_photo']['accuracy']:.1f}%** |
| **Real Scans** (`real_scan`) | {a['category_breakdown']['real_scan']['total']} | {a['category_breakdown']['real_scan']['correct']} | **{a['category_breakdown']['real_scan']['accuracy']:.1f}%** |
| **AI-Generated Images** (`ai_generated`) | {a['category_breakdown']['ai_generated']['total']} | {a['category_breakdown']['ai_generated']['correct']} | **{a['category_breakdown']['ai_generated']['accuracy']:.1f}%** |
| **Edited Real Documents** (`edited_real`) | {a['category_breakdown']['edited_real']['total']} | {a['category_breakdown']['edited_real']['correct']} | **{a['category_breakdown']['edited_real']['accuracy']:.1f}%** |

---

## B. Visual Synthetic Score Analysis

* **Average Score for Real Images**: `{b['avg_real']:.3f}`
* **Average Score for AI-Generated Images**: `{b['avg_ai']:.3f}`
* **Average Score for Edited Real Images**: `{b['avg_edited']:.3f}`

### Performance Across Synthetic Thresholds
| Decision Threshold | Accuracy | Precision | Recall | F1-Score |
| :---: | :---: | :---: | :---: | :---: |
"""
    for th, res in b["threshold_sweeps"].items():
        report_md += f"| **Score &ge; {th:.1f}** | {res['accuracy']:.1f}% | {res['precision']:.1f}% | {res['recall']:.1f}% | {res['f1']:.1f}% |\n"

    report_md += f"""
---

## C. Metadata & Sensor Forensics

| Metric | Percentage | Ethical Implication |
| :--- | :---: | :--- |
| **Real Images with Hardware Camera EXIF** | **{c['pct_real_normal_metadata']:.1f}%** | Direct optical sensor evidence |
| **Real Images with Stripped / Absent EXIF** | **{c['pct_real_no_metadata']:.1f}%** | Stripped by WhatsApp/web compression (common in real work) |
| **AI-Generated with Software Tags** | **{c['pct_ai_software_detected']:.1f}%** | Synthetic generators often lack EXIF tags |
| **Edited Images with Software Tags** | **{c['pct_edited_software_detected']:.1f}%** | Adobe Photoshop / Canva / GIMP signature detected |
| **Metadata False-Positive Rate** | **{c['metadata_false_positive_rate']:.1f}%** | Real work falsely flagged due to metadata compression |

---

## D. C2PA / Content Credentials Audit

* **Credentials Found**: `{d['pct_credentials_found']:.1f}%`
* **Valid Cryptographic Signatures**: `{d['pct_valid_credentials']:.1f}%`
* **Invalid / Revoked Credentials**: `{d['pct_invalid_credentials']:.1f}%`
* **Missing Credentials**: `{d['pct_no_credentials']:.1f}%`
* **Policy Compliance**: Missing credentials **{('were NOT' if d['missing_c2pa_falsely_accused_count'] == 0 else 'WERE')}** treated as proof of manipulation ({d['missing_c2pa_falsely_accused_count']} false accusations).

---

## E. Handwriting Detection Performance

| Metric | Score |
| :--- | :--- |
| **Detection Accuracy** | **{e['accuracy']:.1f}%** |
| **Precision** | **{e['precision']:.1f}%** |
| **Recall** | **{e['recall']:.1f}%** |
| **F1-Score** | **{e['f1']:.1f}%** |
| **Handwritten Notes Correctly Detected** | **{e['pct_handwritten_detected']:.1f}%** |
| **Printed Text Incorrectly Flagged as Handwritten** | **{e['pct_printed_falsely_hw']:.1f}%** |
| **Blank / No-Text Incorrectly Flagged as Handwritten** | **{e['pct_notext_falsely_hw']:.1f}%** |

---

## F. Printed-Text Detection Capabilities

* **Accuracy**: `{f['accuracy']:.1f}%` | **Recall**: `{f['recall']:.1f}%`
* **Status**: `{f['capability_note']}`. All readable text is currently transcribed under the general handwriting OCR pipeline.

---

## G. No-Text & Hallucination Safeguards

| Metric | Score | Safeguard Function |
| :--- | :--- | :--- |
| **No-Text Accuracy** | **{g['accuracy']:.1f}%** | Correctly identifying empty/diagram pages |
| **Precision** | **{g['precision']:.1f}%** | Confidence when declaring page has no text |
| **Recall** | **{g['recall']:.1f}%** | Preventing hallucinations on blank paper |
| **F1-Score** | **{g['f1']:.1f}%** | Balanced non-hallucination metric |

---

## H. Handwriting Transcription Fidelity

"""
    if h["has_references"]:
        report_md += f"""* **Character Error Rate (CER)**: **{h['avg_cer']:.1f}%**
* **Word Error Rate (WER)**: **{h['avg_wer']:.1f}%**
* **Exact / Near-Exact Transcriptions**: **{h['pct_correct_transcription']:.1f}%**
"""
    else:
        report_md += """* **Character Error Rate (CER)**: `N/A`
* **Word Error Rate (WER)**: `N/A`
* **Note**: No reference files found in `evaluation/transcriptions/{image_id}_reference.txt`. Transcription accuracy cannot be measured yet.
"""

    report_md += f"""* **Average Model Confidence**: `{h['avg_confidence']:.1f}%`
* **Unclear Markers (`[unclear]`)**: `{h['unclear_markers_count']}`
* **Fallback OCR (TrOCR / Tesseract) Triggered**: `{h['fallback_cases_count']}`

---
*Report auto-generated by EduVerify AI Evaluation Engine.*
"""

    with open(output_path, "w", encoding="utf-8") as rf:
        rf.write(report_md)
    print(f"Detailed Markdown Report written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="EduVerify AI Evaluation Metrics Engine")
    parser.add_argument("--output-report", type=Path, default=DEFAULT_REPORT_PATH, help=f"Path to save markdown report (default: {DEFAULT_REPORT_PATH})")
    args = parser.parse_args()

    merged_data, has_results = load_data()
    if not has_results:
        sys.exit(0)

    metrics = evaluate_all(merged_data)
    print_and_save_report(metrics, args.output_report)


if __name__ == "__main__":
    main()
