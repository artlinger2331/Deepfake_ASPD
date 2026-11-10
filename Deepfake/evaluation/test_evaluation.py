"""
Unit and Integration Tests for EduVerify AI Evaluation Harness
==============================================================
Tests verify ground-truth parsing, metrics calculation, edit-distance (WER/CER),
API error handling, and file resilience without requiring GPU model downloads.
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

# Ensure evaluation directory is in python path
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from calculate_metrics import (
    load_csv,
    levenshtein_distance,
    compute_wer_cer,
    is_real_class,
    is_concerning_verdict,
    calculate_decision_metrics,
    calculate_visual_score_analysis,
    calculate_metadata_c2pa,
    calculate_ocr_metrics
)
from run_evaluation import load_ground_truth, evaluate_single_image, check_backend_health


class TestEvaluationSuite(unittest.TestCase):

    def test_levenshtein_and_wer_cer(self):
        ref = "When you buy from a small business"
        hyp = "When you buy from small business"  # 1 deletion: 'a'
        wer, cer = compute_wer_cer(ref, hyp)
        self.assertTrue(0.0 < wer <= 0.20)
        self.assertTrue(0.0 < cer <= 0.10)

        # Exact match test
        wer_exact, cer_exact = compute_wer_cer(ref, ref)
        self.assertEqual(wer_exact, 0.0)
        self.assertEqual(cer_exact, 0.0)

    def test_ground_truth_loading(self):
        gt_path = current_dir / "ground_truth.csv"
        self.assertTrue(gt_path.exists())
        gt = load_ground_truth(gt_path)
        self.assertTrue(len(gt) > 0)
        # Verify standard columns exist
        first_item = next(iter(gt.values()))
        for col in ["image_id", "category", "true_label", "source"]:
            self.assertIn(col, first_item)

    def test_decision_metrics_calculation(self):
        # 2 True Negatives, 1 True Positive, 1 False Positive
        sample_data = [
            {"true_label": "real_photo", "predicted_verdict": "genuine"},        # TN
            {"true_label": "difficult_real", "predicted_verdict": "genuine"},    # TN
            {"true_label": "real_photo", "predicted_verdict": "concern"},        # FP
            {"true_label": "ai_generated", "predicted_verdict": "concern"},      # TP
        ]

        metrics = calculate_decision_metrics(sample_data)
        self.assertEqual(metrics["total_evaluated"], 4)
        self.assertEqual(metrics["true_positives"], 1)
        self.assertEqual(metrics["true_negatives"], 2)
        self.assertEqual(metrics["false_positives"], 1)
        self.assertEqual(metrics["false_negatives"], 0)
        self.assertEqual(metrics["accuracy"], 0.75)
        self.assertEqual(metrics["precision"], 0.50)
        self.assertEqual(metrics["recall"], 1.0)

    def test_missing_transcription_does_not_crash(self):
        sample_data = [
            {"image_id": "NON_EXISTENT_999", "fallback_used": "false"}
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            res = calculate_ocr_metrics(sample_data, Path(tmpdir))
            self.assertEqual(res["references_available_count"], 0)
            self.assertEqual(res["average_wer"], "N/A")
            self.assertEqual(res["average_cer"], "N/A")

    def test_api_failure_handled_gracefully(self):
        import requests
        original_post = requests.post

        class MockResponse:
            status_code = 500
            text = "Internal Server Error"
            def json(self):
                return {}

        try:
            requests.post = lambda *args, **kwargs: MockResponse()

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                tf.write(b"\xFF\xD8\xFF\xE0\x00\x10JFIF")
                tf_path = Path(tf.name)

            item = {
                "image_id": "TEST_FAIL_001",
                "file_name": tf_path.name,
                "file_path": tf_path,
                "true_label": "real_photo",
                "category": "real_photo"
            }
            res = evaluate_single_image("http://127.0.0.1:8000", item, timeout=5)
            self.assertEqual(res["predicted_verdict"], "error")
            self.assertIn("500", res["error_message"])
        finally:
            requests.post = original_post
            if tf_path.exists():
                tf_path.unlink()


if __name__ == "__main__":
    unittest.main()
