"""
EduVerify AI - Metric Calculation & Benchmarking Engine
========================================================
Reads ground_truth.csv and matching inference results from results/*.json.
Computes:
  1. Classification Metrics (Accuracy, Precision, Recall, F1-Score)
  2. Multi-class Confusion Matrix (Genuine, Concern, Uncertain)
  3. OCR Character Error Rate (CER) and Word Error Rate (WER)
  4. Outputs a structured markdown evaluation report to evaluation_report.md
"""

import os
import sys
import csv
import json
from pathlib import Path
from typing import List, Dict, Tuple, Any

EVAL_DIR = Path(__file__).resolve().parent
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth.csv"
RESULTS_DIR = EVAL_DIR / "results"
TRANSCRIPTIONS_DIR = EVAL_DIR / "transcriptions"
REPORT_PATH = EVAL_DIR / "evaluation_report.md"


def levenshtein_distance(seq1, seq2):
    """Calculates edit distance between two sequences (chars or word tokens)."""
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
    """Character Error Rate = edit_distance(ref_chars, hyp_chars) / len(ref_chars)."""
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    return min(1.0, levenshtein_distance(ref_chars, hyp_chars) / len(ref_chars))


def compute_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate = edit_distance(ref_words, hyp_words) / len(ref_words)."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return min(1.0, levenshtein_distance(ref_words, hyp_words) / len(ref_words))


def evaluate():
    if not GROUND_TRUTH_PATH.exists():
        print(f"[ERROR] {GROUND_TRUTH_PATH} does not exist.")
        sys.exit(1)

    with open(GROUND_TRUTH_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records = [r for r in reader if r.get("filename", "").strip()]

    if not records:
        print("[INFO] ground_truth.csv is empty. Add benchmark entries with ground truth annotations.")
        print(f"Format: filename,category,expected_status,expected_synthetic,expected_edited,expected_has_text,transcription_file,notes")
        return

    total = len(records)
    evaluated = 0
    missing_results = 0

    # Metrics accumulators
    status_matrix = {
        "genuine": {"genuine": 0, "concern": 0, "uncertain": 0, "other": 0},
        "concern": {"genuine": 0, "concern": 0, "uncertain": 0, "other": 0},
        "uncertain": {"genuine": 0, "concern": 0, "uncertain": 0, "other": 0},
    }

    correct_status_count = 0
    cer_scores = []
    wer_scores = []
    detailed_rows = []

    for row in records:
        fname = row["filename"].strip()
        stem = Path(fname).stem
        expected_status = row.get("expected_status", "").strip().lower()
        res_file = RESULTS_DIR / f"{stem}.json"

        if not res_file.exists():
            missing_results += 1
            detailed_rows.append({
                "filename": fname,
                "category": row.get("category", ""),
                "expected": expected_status,
                "predicted": "NO_RESULT",
                "match": False,
                "cer": "N/A",
                "wer": "N/A",
                "notes": "Run run_evaluation.py first"
            })
            continue

        evaluated += 1
        with open(res_file, "r", encoding="utf-8") as rf:
            res_data = json.load(rf)

        pred_status = res_data.get("status", "unknown").lower()
        is_match = (expected_status == pred_status)
        if is_match:
            correct_status_count += 1

        if expected_status in status_matrix:
            if pred_status in status_matrix[expected_status]:
                status_matrix[expected_status][pred_status] += 1
            else:
                status_matrix[expected_status]["other"] += 1

        # OCR evaluation
        cer_str, wer_str = "N/A", "N/A"
        trans_file_name = row.get("transcription_file", "").strip()
        if trans_file_name:
            trans_path = TRANSCRIPTIONS_DIR / trans_file_name
            if trans_path.exists():
                with open(trans_path, "r", encoding="utf-8") as tf:
                    ref_text = tf.read().strip()
                pred_text = res_data.get("extracted_text", "").strip()

                c_score = compute_cer(ref_text, pred_text)
                w_score = compute_wer(ref_text, pred_text)
                cer_scores.append(c_score)
                wer_scores.append(w_score)
                cer_str = f"{c_score * 100:.1f}%"
                wer_str = f"{w_score * 100:.1f}%"

        detailed_rows.append({
            "filename": fname,
            "category": row.get("category", ""),
            "expected": expected_status,
            "predicted": pred_status,
            "match": is_match,
            "cer": cer_str,
            "wer": wer_str,
            "notes": res_data.get("signals", {}).get("visual", {}).get("label", "")
        })

    # Summary metrics
    accuracy = (correct_status_count / evaluated * 100) if evaluated > 0 else 0.0
    avg_cer = (sum(cer_scores) / len(cer_scores) * 100) if cer_scores else None
    avg_wer = (sum(wer_scores) / len(wer_scores) * 100) if wer_scores else None

    # Binary Genuine Precision / Recall
    tp_gen = status_matrix["genuine"]["genuine"]
    fp_gen = status_matrix["concern"]["genuine"] + status_matrix["uncertain"]["genuine"]
    fn_gen = status_matrix["genuine"]["concern"] + status_matrix["genuine"]["uncertain"]

    prec_gen = (tp_gen / (tp_gen + fp_gen) * 100) if (tp_gen + fp_gen) > 0 else 0.0
    rec_gen = (tp_gen / (tp_gen + fn_gen) * 100) if (tp_gen + fn_gen) > 0 else 0.0
    f1_gen = (2 * prec_gen * rec_gen / (prec_gen + rec_gen)) if (prec_gen + rec_gen) > 0 else 0.0

    print("=== Evaluation Summary ===")
    print(f"Ground Truth Items: {total} | Results Found: {evaluated} | Missing: {missing_results}")
    print(f"Status Classification Accuracy: {accuracy:.1f}%")
    print(f"Likely Genuine Precision: {prec_gen:.1f}% | Recall: {rec_gen:.1f}% | F1: {f1_gen:.1f}%")
    if avg_cer is not None:
        print(f"Average OCR CER: {avg_cer:.1f}% | Average WER: {avg_wer:.1f}%")

    # Generate Report
    report_content = f"""# EduVerify AI — Forensic & OCR Evaluation Report
*Generated by calculate_metrics.py*

---

## 1. Executive Summary

| Metric | Score | Target Standard |
| :--- | :--- | :--- |
| **Total Test Submissions** | {evaluated} / {total} | Benchmark Suite |
| **Classification Accuracy** | **{accuracy:.1f}%** | > 90% |
| **Genuine Class Precision** | **{prec_gen:.1f}%** | > 90% (Low False Accusations) |
| **Genuine Class Recall** | **{rec_gen:.1f}%** | > 85% |
| **Genuine Class F1-Score** | **{f1_gen:.1f}%** | > 88% |
| **Average Character Error Rate (CER)** | **{f'{avg_cer:.1f}%' if avg_cer is not None else 'N/A'}** | < 10% on clean handwriting |
| **Average Word Error Rate (WER)** | **{f'{avg_wer:.1f}%' if avg_wer is not None else 'N/A'}** | < 15% on clean handwriting |

---

## 2. Decision Confusion Matrix

| Ground Truth \\ Predicted | Predicted: Genuine | Predicted: Concern | Predicted: Uncertain | Other |
| :--- | :---: | :---: | :---: | :---: |
| **Actual: Genuine** | **{status_matrix['genuine']['genuine']}** | {status_matrix['genuine']['concern']} | {status_matrix['genuine']['uncertain']} | {status_matrix['genuine']['other']} |
| **Actual: Concern** | {status_matrix['concern']['genuine']} | **{status_matrix['concern']['concern']}** | {status_matrix['concern']['uncertain']} | {status_matrix['concern']['other']} |
| **Actual: Uncertain** | {status_matrix['uncertain']['genuine']} | {status_matrix['uncertain']['concern']} | **{status_matrix['uncertain']['uncertain']}** | {status_matrix['uncertain']['other']} |

---

## 3. Detailed Submission Benchmark Results

| Filename | Category | Expected Status | Predicted Status | Match | CER | WER | Forensic Signal Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
"""
    for r in detailed_rows:
        match_icon = "✅" if r["match"] else "❌"
        report_content += f"| `{r['filename']}` | {r['category']} | {r['expected']} | {r['predicted']} | {match_icon} | {r['cer']} | {r['wer']} | {r['notes']} |\n"

    report_content += """
---

## 4. Evaluation Notes & Protocol
* Evaluated against the live FastAPI `/api/v1/analyze` pipeline.
* OCR metrics are evaluated against reference transcriptions in `evaluation/transcriptions/`.
* Images adhere to the de-identification and consent requirements detailed in `evaluation/README.md`.
"""

    with open(REPORT_PATH, "w", encoding="utf-8") as rf:
        rf.write(report_content)

    print(f"\nReport written to: {REPORT_PATH}")


if __name__ == "__main__":
    evaluate()

