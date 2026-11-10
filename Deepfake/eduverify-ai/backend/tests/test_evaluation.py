"""
EduVerify AI - Pytest Test Suite for Evaluation Scripts
========================================================
Tests the functionality and robustness of:
  - evaluation/run_evaluation.py
  - evaluation/calculate_metrics.py
  - evaluation/ground_truth.csv

Covers all 7 target cases:
  1. Ground-truth CSV loads correctly.
  2. Results CSV loads correctly.
  3. Metrics calculate correctly using sample data.
  4. API failure is handled gracefully.
  5. Missing image does not crash the runner.
  6. Missing transcription reference does not crash the metrics calculator.
  7. Invalid CSV does not crash the scripts.

No real model downloads or active network endpoints are required.
"""

import os
import csv
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import requests

import run_evaluation
import calculate_metrics


# =============================================================================
# Test Case 1: Ground-truth CSV loads correctly
# =============================================================================

def test_ground_truth_csv_loads_correctly_with_valid_schema():
    """Verify that the official ground_truth.csv exists and contains all required schema headers."""
    gt_path = run_evaluation.DEFAULT_GROUND_TRUTH
    assert gt_path.exists(), f"Official ground_truth.csv not found at: {gt_path}"

    expected_columns = [
        "image_id", "file_name", "category", "true_label",
        "contains_handwriting", "contains_printed_text", "contains_no_text",
        "source", "generator", "device", "lighting", "image_quality",
        "reference_transcription_file", "notes"
    ]

    with open(gt_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for col in expected_columns:
            assert col in headers, f"Missing required column in ground_truth.csv: {col}"
        
        rows = list(reader)
        assert len(rows) > 0, "ground_truth.csv must contain at least 1 record."

    # Test that run_evaluation.load_ground_truth indexes by filename and image_id
    gt_map = run_evaluation.load_ground_truth(gt_path)
    assert len(gt_map) > 0, "load_ground_truth should return non-empty map."
    first_row = rows[0]
    fname_key = first_row["file_name"].strip().lower()
    assert fname_key in gt_map, f"Expected filename key '{fname_key}' in loaded ground truth map."


def test_ground_truth_csv_custom_sample_loads_correctly(tmp_path):
    """Verify that custom ground truth CSV files load and parse accurately."""
    sample_csv = tmp_path / "custom_ground_truth.csv"
    with open(sample_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image_id", "file_name", "category", "true_label", "contains_handwriting"])
        writer.writerow(["IMG_001", "scan_1.jpg", "real_scan", "real_scan", "yes"])
        writer.writerow(["IMG_002", "ai_art.png", "ai_generated", "ai_generated", "no"])

    loaded = run_evaluation.load_ground_truth(sample_csv)
    assert "scan_1.jpg" in loaded
    assert "img_001" in loaded
    assert loaded["scan_1.jpg"]["true_label"] == "real_scan"
    assert loaded["ai_art.png"]["category"] == "ai_generated"


# =============================================================================
# Test Case 2: Results CSV loads correctly
# =============================================================================

def test_results_csv_loads_and_merges_correctly(tmp_path, monkeypatch):
    """Verify that evaluation results CSV loads and correctly pairs with ground truth records."""
    gt_file = tmp_path / "ground_truth.csv"
    res_file = tmp_path / "evaluation_results.csv"

    # Write ground truth
    with open(gt_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image_id", "file_name", "category", "true_label", "contains_handwriting", "contains_no_text"])
        writer.writerow(["ID_101", "page1.jpg", "real_photo", "real_photo", "yes", "no"])
        writer.writerow(["ID_102", "page2.png", "ai_generated", "ai_generated", "no", "yes"])

    # Write evaluation results
    with open(res_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image_id", "file_name", "final_verdict", "confidence_score", "visual_synthetic_score", "handwriting_detection"])
        writer.writerow(["ID_101", "page1.jpg", "genuine", "94", "0.12", "True"])
        writer.writerow(["ID_102", "page2.png", "concern", "88", "0.78", "False"])

    # Monkeypatch calculate_metrics file paths
    monkeypatch.setattr(calculate_metrics, "GROUND_TRUTH_PATH", gt_file)
    monkeypatch.setattr(calculate_metrics, "RESULTS_CSV_PATH", res_file)

    merged, has_results = calculate_metrics.load_data()
    assert has_results is True
    assert len(merged) == 2

    # Check pair 1
    assert merged[0]["gt"]["image_id"] == "ID_101"
    assert merged[0]["res"]["final_verdict"] == "genuine"
    assert merged[0]["res"]["visual_synthetic_score"] == "0.12"

    # Check pair 2
    assert merged[1]["gt"]["image_id"] == "ID_102"
    assert merged[1]["res"]["final_verdict"] == "concern"
    assert merged[1]["res"]["handwriting_detection"] == "False"


def test_extract_response_fields_schema_conformance():
    """Verify extract_response_fields parses full API response into all expected result fields."""
    mock_response = {
        "status": "genuine",
        "statusLabel": "Likely Genuine Student Work",
        "conclusion": "No synthetic anomalies detected.",
        "confidenceScore": 92,
        "signals": {
            "visual": {"score": 0.14, "status": "normal"},
            "metadata": {"status": "normal"},
            "provenance": {"status": "missing"},
            "ocr": {"status": "normal"}
        },
        "raw_inputs": {
            "vision": {"data": {"visual_synthetic_score": 0.14}},
            "ocr": {"status": "normal", "data": {"extracted_text": "Sample text line", "word_count": 3, "confidence_score": 95.0}},
            "handwriting": {"status": "normal", "data": {"text": "Sample text line", "word_count": 3, "confidence": 0.95, "is_readable": True}},
            "metadata": {"data": {"camera_make_model": "Apple iPhone 13", "software_used": ""}}
        }
    }
    mock_gt = {"image_id": "TEST_001", "category": "real_photo", "true_label": "real_photo"}
    mock_path = Path("images/real_photo/sample.jpg")

    extracted = run_evaluation.extract_response_fields(
        response_json=mock_response,
        ground_truth=mock_gt,
        image_path=mock_path,
        latency=0.45,
        http_status=200
    )

    assert extracted["image_id"] == "TEST_001"
    assert extracted["file_name"] == "sample.jpg"
    assert extracted["category"] == "real_photo"
    assert extracted["true_label"] == "real_photo"
    assert extracted["final_verdict"] == "genuine"
    assert extracted["confidence_score"] == 92
    assert extracted["visual_synthetic_score"] == 0.14
    assert extracted["ocr_word_count"] == 3
    assert extracted["handwriting_detection"] is True
    assert extracted["camera_make_model"] == "Apple iPhone 13"
    assert extracted["c2pa_status"] == "missing"
    assert extracted["error_message"] == ""


# =============================================================================
# Test Case 3: Metrics calculate correctly using sample data
# =============================================================================

def test_metrics_calculate_correctly_using_sample_data():
    """
    Controlled metric test with 6 known outcomes:
      - 2 Real photos: 1 Genuine (TN), 1 Concern (FP)
      - 1 Real scan: 1 Genuine (TN)
      - 2 AI generated: 1 Concern (TP), 1 Genuine (FN)
      - 1 Edited real: 1 Concern (TP)
    
    Expected Section A totals:
      Total = 6
      TP = 2 (1 AI + 1 Edited)
      TN = 2 (1 Real photo + 1 Real scan)
      FP = 1 (1 Real photo falsely accused)
      FN = 1 (1 AI missed)
      Accuracy = (2 + 2) / 6 = 66.67%
      Precision = 2 / (2 + 1) = 66.67%
      Recall = 2 / (2 + 1) = 66.67%
      FPR = 1 / (1 + 2) = 33.33%
      FNR = 1 / (1 + 2) = 33.33%
    """
    merged_data = [
        # 1. Real photo -> Genuine (TN)
        {"gt": {"true_label": "real_photo", "category": "real_photo"}, "res": {"final_verdict": "genuine", "visual_synthetic_score": "0.10"}},
        # 2. Real photo -> Concern (FP - False Positive)
        {"gt": {"true_label": "real_photo", "category": "real_photo"}, "res": {"final_verdict": "concern", "visual_synthetic_score": "0.45"}},
        # 3. Real scan -> Genuine (TN)
        {"gt": {"true_label": "real_scan", "category": "real_scan"}, "res": {"final_verdict": "likely_genuine", "visual_synthetic_score": "0.08"}},
        # 4. AI Generated -> Concern (TP)
        {"gt": {"true_label": "ai_generated", "category": "ai_generated"}, "res": {"final_verdict": "concern", "visual_synthetic_score": "0.82"}},
        # 5. AI Generated -> Genuine (FN - Missed Manipulation)
        {"gt": {"true_label": "ai_generated", "category": "ai_generated"}, "res": {"final_verdict": "genuine", "visual_synthetic_score": "0.25"}},
        # 6. Edited Real -> Concern (TP)
        {"gt": {"true_label": "edited_real", "category": "edited_real"}, "res": {"final_verdict": "edited_real", "visual_synthetic_score": "0.70"}},
    ]

    metrics = calculate_metrics.evaluate_all(merged_data)
    sec_a = metrics["section_a"]

    assert sec_a["total_evaluated"] == 6
    assert sec_a["tp"] == 2
    assert sec_a["tn"] == 2
    assert sec_a["fp"] == 1
    assert sec_a["fn"] == 1

    assert round(sec_a["accuracy"], 2) == 66.67
    assert round(sec_a["precision"], 2) == 66.67
    assert round(sec_a["recall"], 2) == 66.67
    assert round(sec_a["fpr"], 2) == 33.33
    assert round(sec_a["fnr"], 2) == 33.33

    # Category breakdown accuracy
    cats = sec_a["by_category_breakdown"]
    assert cats["real_photo"]["total"] == 2
    assert cats["real_photo"]["correct"] == 1
    assert cats["real_photo"]["accuracy"] == 50.0

    assert cats["real_scan"]["total"] == 1
    assert cats["real_scan"]["correct"] == 1
    assert cats["real_scan"]["accuracy"] == 100.0

    assert cats["ai_generated"]["total"] == 2
    assert cats["ai_generated"]["correct"] == 1
    assert cats["ai_generated"]["accuracy"] == 50.0

    assert cats["edited_real"]["total"] == 1
    assert cats["edited_real"]["correct"] == 1
    assert cats["edited_real"]["accuracy"] == 100.0


def test_metrics_visual_synthetic_score_sweeps_and_distributions():
    """Verify Section B calculations for score averages and threshold sweeps."""
    merged_data = [
        {"gt": {"true_label": "real_photo", "category": "real_photo"}, "res": {"visual_synthetic_score": "0.10"}},
        {"gt": {"true_label": "real_photo", "category": "real_photo"}, "res": {"visual_synthetic_score": "0.20"}},
        {"gt": {"true_label": "ai_generated", "category": "ai_generated"}, "res": {"visual_synthetic_score": "0.80"}},
        {"gt": {"true_label": "edited_real", "category": "edited_real"}, "res": {"visual_synthetic_score": "0.60"}}
    ]

    metrics = calculate_metrics.evaluate_all(merged_data)
    sec_b = metrics["section_b"]

    assert round(sec_b["avg_real"], 2) == 0.15
    assert round(sec_b["avg_ai"], 2) == 0.80
    assert round(sec_b["avg_edited"], 2) == 0.60

    # Test threshold sweeps: At th=0.5, real items (0.10, 0.20) are below, AI (0.80) & edited (0.60) are above
    th_5 = sec_b["threshold_sweeps"][0.5]
    assert th_5["accuracy"] == 100.0
    assert th_5["precision"] == 100.0
    assert th_5["recall"] == 100.0


def test_metrics_metadata_and_c2pa_forensics():
    """Verify Section C and D calculations for metadata and C2PA credentials."""
    merged_data = [
        # Real with camera metadata
        {"gt": {"true_label": "real_photo"}, "res": {"camera_make_model": "Nikon D3500", "software_used": "", "c2pa_status": "missing"}},
        # Real without camera metadata
        {"gt": {"true_label": "real_scan"}, "res": {"camera_make_model": "", "software_used": "", "c2pa_status": "valid"}},
        # AI with generation software
        {"gt": {"true_label": "ai_generated"}, "res": {"software_used": "Midjourney v6", "c2pa_status": "invalid"}},
        # Edited with Photoshop
        {"gt": {"true_label": "edited_real"}, "res": {"software_used": "Adobe Photoshop 2024", "c2pa_status": "tampered"}}
    ]

    metrics = calculate_metrics.evaluate_all(merged_data)
    sec_c = metrics["section_c"]
    sec_d = metrics["section_d"]

    # 1 out of 2 real images had camera metadata (50%)
    assert sec_c["pct_real_normal_metadata"] == 50.0
    assert sec_c["pct_real_no_metadata"] == 50.0
    # 1 out of 1 AI image had software detected (100%)
    assert sec_c["pct_ai_software_detected"] == 100.0
    # 1 out of 1 edited image had software detected (100%)
    assert sec_c["pct_edited_software_detected"] == 100.0

    # C2PA: 4 total, 1 valid, 2 invalid/tampered, 1 missing
    assert sec_d["pct_valid_credentials"] == 25.0
    assert sec_d["pct_invalid_credentials"] == 50.0
    assert sec_d["pct_no_credentials"] == 25.0


def test_metrics_handwriting_and_no_text_detection():
    """Verify Section E (Handwriting) and Section G (No-Text) detection metrics."""
    merged_data = [
        # Handwriting true positive
        {"gt": {"contains_handwriting": "yes", "contains_no_text": "no"}, "res": {"handwriting_detection": "True", "no_text_detection": "False"}},
        # Handwriting true negative / no-text true positive
        {"gt": {"contains_handwriting": "no", "contains_no_text": "yes"}, "res": {"handwriting_detection": "False", "no_text_detection": "True"}},
        # False handwriting alarm on printed text
        {"gt": {"contains_handwriting": "no", "contains_printed_text": "yes", "contains_no_text": "no"}, "res": {"handwriting_detection": "True", "no_text_detection": "False"}}
    ]

    metrics = calculate_metrics.evaluate_all(merged_data)
    sec_e = metrics["section_e"]
    sec_g = metrics["section_g"]

    # Handwriting: TP=1, TN=1, FP=1, FN=0 -> Acc = 2/3 = 66.67%
    assert round(sec_e["accuracy"], 2) == 66.67
    assert sec_e["tp"] == 1
    assert sec_e["fp"] == 1

    # No text: TP=1, TN=2, FP=0, FN=0 -> Acc = 100%
    assert sec_g["accuracy"] == 100.0
    assert sec_g["tp"] == 1
    assert sec_g["tn"] == 2


def test_levenshtein_cer_and_wer_distance_accuracy():
    """Verify that Levenshtein distance, CER, and WER match exact algorithmic standards."""
    # Identical strings
    assert calculate_metrics.compute_cer("hello world", "hello world") == 0.0
    assert calculate_metrics.compute_wer("hello world", "hello world") == 0.0

    # 1 character substitution in 5 characters -> CER = 0.2
    assert round(calculate_metrics.compute_cer("abcde", "abxde"), 2) == 0.20

    # 1 word substitution in 2 words -> WER = 0.5
    assert round(calculate_metrics.compute_wer("hello world", "hello there"), 2) == 0.50

    # Empty string edge cases
    assert calculate_metrics.compute_cer("", "") == 0.0
    assert calculate_metrics.compute_wer("", "") == 0.0
    assert calculate_metrics.compute_cer("nonempty", "") == 1.0


# =============================================================================
# Test Case 4: API failure is handled gracefully
# =============================================================================

def test_api_failure_handled_gracefully_on_http_500(tmp_path):
    """Verify that run_evaluation handles HTTP 500 error responses without crashing."""
    img_dir = tmp_path / "images" / "real_photo"
    img_dir.mkdir(parents=True)
    test_img = img_dir / "sample_failure.jpg"
    test_img.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00")

    out_dir = tmp_path / "results"
    gt_file = tmp_path / "gt.csv"
    with open(gt_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image_id", "file_name", "category", "true_label"])
        writer.writerow(["FAIL_001", "sample_failure.jpg", "real_photo", "real_photo"])

    # Mock health check and POST 500
    mock_post_res = MagicMock()
    mock_post_res.status_code = 500
    mock_post_res.text = "Internal Server Error: GPU Out of Memory"
    mock_post_res.json.side_effect = ValueError("Not JSON")

    with patch("run_evaluation.check_backend_connection", return_value=(True, None)):
        with patch("requests.post", return_value=mock_post_res):
            run_evaluation.run_evaluation(
                api_url="http://127.0.0.1:8000/api/v1/analyze",
                input_dir=img_dir,
                output_dir=out_dir,
                ground_truth_path=gt_file
            )

    # Verify results CSV was created and contains the error
    res_csv = out_dir / "evaluation_results.csv"
    assert res_csv.exists()
    with open(res_csv, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert reader[0]["http_status"] == "500"
        assert "HTTP 500" in reader[0]["error_message"]

    # Verify JSON response file was saved
    resp_json = out_dir / "FAIL_001_response.json"
    assert resp_json.exists()


def test_api_failure_handled_gracefully_on_timeout(tmp_path):
    """Verify that run_evaluation handles network timeouts cleanly without halting."""
    img_dir = tmp_path / "images" / "real_photo"
    img_dir.mkdir(parents=True)
    test_img = img_dir / "sample_timeout.jpg"
    test_img.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF")

    out_dir = tmp_path / "results"
    gt_file = tmp_path / "gt.csv"
    with open(gt_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image_id", "file_name", "category", "true_label"])
        writer.writerow(["TO_001", "sample_timeout.jpg", "real_photo", "real_photo"])

    with patch("run_evaluation.check_backend_connection", return_value=(True, None)):
        with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out")):
            run_evaluation.run_evaluation(
                api_url="http://127.0.0.1:8000/api/v1/analyze",
                input_dir=img_dir,
                output_dir=out_dir,
                ground_truth_path=gt_file
            )

    res_csv = out_dir / "evaluation_results.csv"
    assert res_csv.exists()
    with open(res_csv, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert "timed out" in reader[0]["error_message"].lower()


def test_api_failure_handled_gracefully_on_connection_error(tmp_path):
    """Verify that run_evaluation handles ConnectionError during image POST."""
    img_dir = tmp_path / "images" / "real_photo"
    img_dir.mkdir(parents=True)
    test_img = img_dir / "sample_conn.jpg"
    test_img.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF")

    out_dir = tmp_path / "results"
    gt_file = tmp_path / "gt.csv"
    with open(gt_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image_id", "file_name", "category", "true_label"])
        writer.writerow(["CONN_001", "sample_conn.jpg", "real_photo", "real_photo"])

    with patch("run_evaluation.check_backend_connection", return_value=(True, None)):
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection aborted")):
            run_evaluation.run_evaluation(
                api_url="http://127.0.0.1:8000/api/v1/analyze",
                input_dir=img_dir,
                output_dir=out_dir,
                ground_truth_path=gt_file
            )

    res_csv = out_dir / "evaluation_results.csv"
    assert res_csv.exists()
    with open(res_csv, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert "connection aborted" in reader[0]["error_message"].lower()


def test_backend_connection_check_handles_unreachable_server():
    """Verify check_backend_connection accurately reports connection refusal and success."""
    # Test connection refused
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
        is_up, err = run_evaluation.check_backend_connection("http://127.0.0.1:8000/api/v1/analyze")
        assert is_up is False
        assert "connection refused" in err.lower()

    # Test healthy backend
    mock_ok = MagicMock()
    mock_ok.status_code = 200
    with patch("requests.get", return_value=mock_ok):
        is_up, err = run_evaluation.check_backend_connection("http://127.0.0.1:8000/api/v1/analyze")
        assert is_up is True
        assert err is None


# =============================================================================
# Test Case 5: Missing image does not crash the runner
# =============================================================================

def test_missing_image_does_not_crash_runner_discover_images():
    """Verify discover_images safely returns an empty list for non-existent paths."""
    missing_dir = Path("non_existent_folder_path_xyz")
    found = run_evaluation.discover_images(missing_dir)
    assert found == []


def test_empty_input_directory_does_not_crash_runner(tmp_path):
    """Verify discover_images returns empty list when directory only contains non-image files."""
    empty_dir = tmp_path / "empty_dataset"
    empty_dir.mkdir()
    (empty_dir / ".gitkeep").write_text("", encoding="utf-8")
    (empty_dir / "notes.txt").write_text("Not an image", encoding="utf-8")

    found = run_evaluation.discover_images(empty_dir)
    assert found == []


def test_run_evaluation_exits_gracefully_when_no_images_found(tmp_path):
    """Verify run_evaluation exits cleanly with code 0 when input directory has no images."""
    empty_dir = tmp_path / "empty_dataset"
    empty_dir.mkdir()
    out_dir = tmp_path / "results"

    with patch("run_evaluation.check_backend_connection", return_value=(True, None)):
        with pytest.raises(SystemExit) as exc_info:
            run_evaluation.run_evaluation(
                api_url="http://127.0.0.1:8000/api/v1/analyze",
                input_dir=empty_dir,
                output_dir=out_dir
            )
        assert exc_info.value.code == 0


# =============================================================================
# Test Case 6: Missing transcription reference does not crash the metrics calculator
# =============================================================================

def test_missing_transcription_reference_does_not_crash_metrics_calculator():
    """Verify evaluate_all handles missing reference transcript files gracefully without crashing."""
    merged_data = [
        {
            "gt": {
                "image_id": "NO_REF_001",
                "reference_transcription_file": "missing_ref_file.txt"
            },
            "res": {
                "ocr_text": "Transcribed draft line",
                "ocr_confidence": "88.5",
                "fallback_usage": "False"
            }
        }
    ]

    metrics = calculate_metrics.evaluate_all(merged_data)
    sec_h = metrics["section_h"]

    assert sec_h["has_references"] is False
    assert sec_h["avg_cer"] is None
    assert sec_h["avg_wer"] is None
    assert sec_h["pct_correct_transcription"] is None
    assert sec_h["evaluated_transcriptions"] == 0
    assert sec_h["avg_confidence"] == 88.5


def test_print_and_save_report_succeeds_with_missing_transcription_references(tmp_path):
    """Verify print_and_save_report correctly writes markdown report when transcriptions are missing."""
    merged_data = [
        {"gt": {"true_label": "real_photo", "category": "real_photo"}, "res": {"final_verdict": "genuine"}}
    ]
    metrics = calculate_metrics.evaluate_all(merged_data)
    report_file = tmp_path / "test_report.md"

    calculate_metrics.print_and_save_report(metrics, report_file)
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")

    assert "Transcription accuracy cannot be measured yet." in content
    assert "This evaluation does not prove that EduVerify AI can determine academic misconduct." in content


# =============================================================================
# Test Case 7: Invalid CSV does not crash the scripts
# =============================================================================

def test_load_ground_truth_with_non_existent_csv():
    """Verify load_ground_truth handles missing CSV file paths gracefully."""
    missing_path = Path("non_existent_file_abc.csv")
    loaded = run_evaluation.load_ground_truth(missing_path)
    assert loaded == {}


def test_load_ground_truth_with_empty_csv(tmp_path):
    """Verify load_ground_truth handles 0-byte CSV files without crashing."""
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")
    loaded = run_evaluation.load_ground_truth(empty_csv)
    assert loaded == {}


def test_load_ground_truth_with_malformed_csv(tmp_path):
    """Verify load_ground_truth parses malformed CSV content safely."""
    malformed_csv = tmp_path / "malformed.csv"
    malformed_csv.write_text("random,unmatched\nvalues,with,different,counts\n", encoding="utf-8")
    loaded = run_evaluation.load_ground_truth(malformed_csv)
    assert isinstance(loaded, dict)


def test_calculate_metrics_with_corrupted_numerical_values():
    """Verify evaluate_all ignores invalid strings in score/confidence fields without crashing."""
    merged_data = [
        {
            "gt": {"true_label": "real_photo", "category": "real_photo"},
            "res": {
                "final_verdict": "genuine",
                "visual_synthetic_score": "corrupted_string_not_a_float",
                "ocr_confidence": "invalid_number",
                "confidence_score": "NaN_or_null"
            }
        }
    ]

    metrics = calculate_metrics.evaluate_all(merged_data)
    assert metrics["section_a"]["total_evaluated"] == 1
    # Should safely treat visual synthetic score as unparsed
    assert metrics["section_b"]["avg_real"] == 0.0


def test_calculate_metrics_with_missing_keys_in_records():
    """Verify evaluate_all handles empty or partially missing dictionary records gracefully."""
    merged_data = [
        {"gt": {}, "res": {}},
        {"gt": {"random_key": "val"}, "res": {"other_key": "val"}}
    ]

    metrics = calculate_metrics.evaluate_all(merged_data)
    assert isinstance(metrics, dict)
    assert metrics["section_a"]["total_evaluated"] == 1
    assert metrics["section_a"]["accuracy"] == 0.0
