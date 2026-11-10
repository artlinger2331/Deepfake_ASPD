"""
EduVerify AI - Unit Test Suite for Multi-Signal Scoring Engine
==============================================================
Tests all components of the improved scoring pipeline:
  1. Visual score normalization & multi-feature extraction.
  2. Image quality factor adjustment.
  3. Metadata anomaly score calculation.
  4. C2PA / provenance score calculation.
  5. OCR & consistency score calculation.
  6. Multi-signal fusion formula and weights.
  7. Threshold classification (likely_genuine, uncertain, concern).
  8. API response schema and backward compatibility.
"""

import pytest
import numpy as np
from PIL import Image

from api.config import (
    VISUAL_WEIGHTS,
    FUSION_WEIGHTS,
    THRESHOLDS,
    QUALITY_FACTORS
)
from api.services.vision import (
    compute_laplacian_score,
    compute_local_noise_score,
    compute_fft_spectral_score,
    compute_texture_uniformity_score,
    compute_compression_artifact_score,
    evaluate_image_quality,
    process_vision
)
from api.services.metadata import (
    calculate_metadata_anomaly_score,
    process_metadata
)
from api.services.fusion import (
    calculate_provenance_score,
    calculate_ocr_consistency_score,
    fuse_results
)


# =============================================================================
# 1. Visual Score Normalization & Features
# =============================================================================

def test_visual_score_normalization_and_features():
    """Verify that all visual feature functions return values strictly normalized to [0.0, 1.0]."""
    # Create natural synthetic test patch
    np.random.seed(42)
    gray = np.random.randint(180, 240, (300, 300), dtype=np.uint8)

    # 1. Laplacian
    s_lap, raw_lap = compute_laplacian_score(gray)
    assert 0.0 <= s_lap <= 1.0
    assert raw_lap >= 0.0

    # 2. Local noise
    s_noise, raw_noise = compute_local_noise_score(gray)
    assert 0.0 <= s_noise <= 1.0
    assert raw_noise >= 0.0

    # 3. FFT spectral
    s_fft, raw_fft = compute_fft_spectral_score(gray)
    assert 0.0 <= s_fft <= 1.0
    assert 0.0 <= raw_fft <= 1.0

    # 4. Texture uniformity
    s_tex, raw_cv = compute_texture_uniformity_score(gray)
    assert 0.0 <= s_tex <= 1.0

    # 5. Compression
    s_comp, raw_comp = compute_compression_artifact_score(gray)
    assert 0.0 <= s_comp <= 1.0


def test_visual_sterile_vs_noisy_noise_score():
    """Verify that sterile background yields higher synthetic score than authentic camera noise."""
    # Sterile uniform background (AI characteristic)
    sterile = np.full((200, 200), 240, dtype=np.uint8)
    s_sterile, _ = compute_local_noise_score(sterile)

    # Physical noisy background (Real camera sensor noise)
    noisy = (np.full((200, 200), 240, dtype=np.float32) + np.random.normal(0, 5.0, (200, 200))).clip(0, 255).astype(np.uint8)
    s_noisy, _ = compute_local_noise_score(noisy)

    assert s_sterile > s_noisy, "Sterile synthetic background must score higher than natural camera noise."


# =============================================================================
# 2. Image Quality Adjustment Factor
# =============================================================================

def test_image_quality_adjustment_factor():
    """Verify that degraded images receive low/medium Q factor to avoid false accusations."""
    # Low resolution blurry underexposed image
    dark_blurry = np.full((150, 150, 3), 20, dtype=np.uint8)
    gray_dark = cv2_gray = np.full((150, 150), 20, dtype=np.uint8)

    q_low, label_low, notes_low = evaluate_image_quality(dark_blurry, gray_dark)
    assert q_low == QUALITY_FACTORS.low
    assert label_low == "low"
    assert len(notes_low) > 0

    # High quality well-lit image
    high_res = np.random.randint(100, 220, (1200, 1200, 3), dtype=np.uint8)
    gray_high = np.random.randint(100, 220, (1200, 1200), dtype=np.uint8)
    q_high, label_high, notes_high = evaluate_image_quality(high_res, gray_high)
    assert q_high == QUALITY_FACTORS.high
    assert label_high == "high"


# =============================================================================
# 3. Metadata Anomaly Score Calculation
# =============================================================================

def test_metadata_score_calculation_rules():
    """Verify all explicit arithmetic rules for Metadata Anomaly Score (M)."""
    # Case A: Normal camera metadata present
    # Has camera (M - 0.15) and has timestamp -> M = 0.0
    score_cam, status_cam, _ = calculate_metadata_anomaly_score(
        has_exif=True,
        camera_make_model="Apple iPhone 14",
        software_used="",
        timestamp="2026:10:15 14:30:00",
        raw_tags={"Image Make": "Apple", "Image Model": "iPhone 14"}
    )
    assert score_cam == 0.0
    assert status_cam == "authentic_camera_exif"

    # Case B: Editing software detected (Photoshop)
    # M = 0.45 (editing) - 0.15 (camera) = 0.30
    score_edit, status_edit, _ = calculate_metadata_anomaly_score(
        has_exif=True,
        camera_make_model="Canon EOS",
        software_used="Adobe Photoshop 2024",
        timestamp="2026:10:15 14:30:00",
        raw_tags={"Image Software": "Adobe Photoshop 2024"}
    )
    assert score_edit == 0.30
    assert status_edit == "editing_software_detected"

    # Case C: Metadata completely absent (WhatsApp / web upload)
    # M = 0.20 (absent) + 0.15 (no cam) + 0.10 (no time) = 0.45
    score_absent, status_absent, _ = calculate_metadata_anomaly_score(
        has_exif=False,
        camera_make_model="",
        software_used="",
        timestamp="",
        raw_tags={}
    )
    assert score_absent == 0.45
    assert status_absent == "metadata_absent"

    # Case D: Screenshot indicators present
    score_ss, status_ss, _ = calculate_metadata_anomaly_score(
        has_exif=True,
        camera_make_model="",
        software_used="Screenshot Utility",
        timestamp="",
        raw_tags={"Image Software": "Screenshot Utility"}
    )
    # 0.15 (no cam) + 0.10 (no time) + 0.10 (screenshot) = 0.35
    assert score_ss >= 0.35
    assert "screenshot" in status_ss


# =============================================================================
# 4. C2PA Provenance Score Calculation
# =============================================================================

def test_c2pa_provenance_score_calculation():
    """Verify C2PA / Content Credentials rules."""
    # 1. Valid with AI declared
    p_ai, st_ai, _ = calculate_provenance_score({
        "data": {"c2pa_credentials": True, "is_valid": True, "ai_generation_declared": True}
    })
    assert p_ai == 0.70
    assert st_ai == "ai_declared_c2pa"

    # 2. Valid with editing declared
    p_edit, st_edit, _ = calculate_provenance_score({
        "data": {"c2pa_credentials": True, "is_valid": True, "editing_declared": True}
    })
    assert p_edit == 0.40
    assert st_edit == "editing_declared_c2pa"

    # 3. Invalid credentials
    p_inv, st_inv, _ = calculate_provenance_score({
        "data": {"c2pa_credentials": True, "is_invalid": True}
    })
    assert p_inv == 0.30
    assert st_inv == "invalid_credentials"

    # 4. Missing credentials (Must not be penalized)
    p_none, st_none, _ = calculate_provenance_score({
        "data": {"c2pa_credentials": False}
    })
    assert p_none == 0.00
    assert st_none == "credentials_not_found"


# =============================================================================
# 5. OCR & Consistency Score Calculation
# =============================================================================

def test_ocr_consistency_score_calculation():
    """Verify OCR & consistency checks for hallucinated loops and natural variations."""
    # Degenerate loop tokens (diffusion hallucination)
    loop_text = "the word test the word test the word test the word test the word test the word test"
    ocr_data = {"data": {"extracted_text": loop_text, "confidence_score": 95.0, "word_count": 18}}
    c_score, status, obs = calculate_ocr_consistency_score(ocr_data, {}, {})
    assert c_score >= 0.20
    assert any("repetitive" in o.lower() for o in obs)

    # Clean natural student text
    natural_text = "Problem 1: Solve for x. The quadratic equation yields x = 3 and x = -5."
    ocr_natural = {"data": {"extracted_text": natural_text, "confidence_score": 92.0, "word_count": 14}}
    c_nat, status_nat, _ = calculate_ocr_consistency_score(ocr_natural, {}, {})
    assert c_nat == 0.0
    assert status_nat == "natural_consistency"


# =============================================================================
# 6. Multi-Signal Fusion Formula & Weights
# =============================================================================

def test_fusion_formula_and_weights():
    """
    Test configurable fusion formula:
      S = (w_v * V_adj) + (w_m * M) + (w_p * P) + (w_c * C)
    With default weights:
      w_v = 0.50, w_m = 0.20, w_p = 0.20, w_c = 0.10
    """
    vision_mock = {"data": {"raw_visual_score": 0.80, "quality_factor": 1.0, "adjusted_visual_score": 0.80}}
    meta_mock = {"data": {"metadata_anomaly_score": 0.50, "metadata_status": "sparse_metadata"}}
    hw_mock = {"data": {"text": "Simple line", "word_count": 2}}
    ocr_mock = {"data": {"extracted_text": "Simple line", "word_count": 2, "confidence_score": 85.0}}

    # Provenance = 0.0, Consistency = 0.0
    # S = 0.50 * 0.80 + 0.20 * 0.50 + 0.20 * 0.0 + 0.10 * 0.0 = 0.40 + 0.10 = 0.50
    report = fuse_results(vision_mock, ocr_mock, hw_mock, meta_mock)
    assert report["ai_generation_signal_score"] == 0.50
    assert report["fusion"]["weights"]["visual"] == 0.50
    assert report["fusion"]["weights"]["metadata"] == 0.20


# =============================================================================
# 7. Decision Threshold Classification
# =============================================================================

def test_decision_threshold_classification():
    """Verify verdict transitions across thresholds T1=0.45 and T2=0.70."""
    t1 = THRESHOLDS.likely_genuine  # 0.45
    t2 = THRESHOLDS.concern         # 0.70

    # 1. Below T1 -> likely_genuine
    res_low = fuse_results(
        {"data": {"raw_visual_score": 0.15, "quality_factor": 1.0, "adjusted_visual_score": 0.15}},
        {"data": {"extracted_text": "Natural text", "word_count": 10}},
        {},
        {"data": {"metadata_anomaly_score": 0.0, "camera_make_model": "Sony A7"}}
    )
    # S = 0.50*0.15 + 0.20*0.0 = 0.075 < 0.45
    assert res_low["final_verdict"] == "likely_genuine"
    assert res_low["status"] == "genuine"

    # 2. Between T1 and T2 -> uncertain
    res_mid = fuse_results(
        {"data": {"raw_visual_score": 0.70, "quality_factor": 1.0, "adjusted_visual_score": 0.70}},
        {"data": {"extracted_text": "Natural text", "word_count": 10}},
        {},
        {"data": {"metadata_anomaly_score": 0.45, "metadata_status": "metadata_absent"}}
    )
    # S = 0.50*0.70 + 0.20*0.45 = 0.35 + 0.09 = 0.44 -> wait, 0.44 is near threshold
    # If S = 0.50:
    res_mid2 = fuse_results(
        {"data": {"raw_visual_score": 0.80, "quality_factor": 1.0, "adjusted_visual_score": 0.80}},
        {"data": {"extracted_text": "Natural text", "word_count": 10}},
        {},
        {"data": {"metadata_anomaly_score": 0.50, "metadata_status": "metadata_absent"}}
    )
    # S = 0.50*0.80 + 0.20*0.50 = 0.50 -> between 0.45 and 0.70
    assert res_mid2["final_verdict"] == "uncertain"
    assert res_mid2["status"] == "uncertain"

    # 3. Above T2 -> concern
    res_high = fuse_results(
        {"data": {"raw_visual_score": 0.90, "quality_factor": 1.0, "adjusted_visual_score": 0.90}},
        {"data": {"extracted_text": "AI generated loops", "word_count": 10}},
        {},
        {"data": {"metadata_anomaly_score": 0.90, "software_used": "Photoshop", "c2pa_credentials": True, "is_valid": True, "ai_generation_declared": True}}
    )
    # S = 0.50*0.90 + 0.20*0.90 + 0.20*0.70 = 0.45 + 0.18 + 0.14 = 0.77 >= 0.70
    assert res_high["final_verdict"] == "concern"
    assert res_high["status"] == "concern"


# =============================================================================
# 8. API Response Format & Backward Compatibility
# =============================================================================

def test_api_response_format_and_backward_compatibility():
    """Verify all required new fields and legacy dashboard compatibility fields are present."""
    report = fuse_results(
        {"data": {"raw_visual_score": 0.30, "quality_factor": 0.85, "adjusted_visual_score": 0.255}},
        {"data": {"extracted_text": "Sample student test line", "word_count": 4, "confidence_score": 90.0, "oriented_image_base64": "data:image/jpeg;base64,ABC"}},
        {"data": {"text": "Sample student test line", "word_count": 4}},
        {"data": {"metadata_anomaly_score": 0.30, "metadata_status": "sparse_metadata", "software_used": None, "camera_make_model": None}}
    )

    # Required specification fields
    assert "ai_generation_signal_score" in report
    assert report["score_type"] == "uncalibrated_signal_score"
    assert "final_verdict" in report
    assert "confidence" in report
    assert report["confidence_basis"] == "multi-signal fusion"

    assert "visual" in report["signals"]
    assert "raw_score" in report["signals"]["visual"]
    assert "adjusted_score" in report["signals"]["visual"]
    assert "quality_factor" in report["signals"]["visual"]

    assert "metadata" in report["signals"]
    assert "score" in report["signals"]["metadata"]
    assert "provenance" in report["signals"]
    assert "ocr_consistency" in report["signals"]

    assert "fusion" in report
    assert "formula" in report["fusion"]
    assert "weights" in report["fusion"]
    assert "thresholds" in report["fusion"]

    assert "recommended_actions" in report
    assert len(report["recommended_actions"]) >= 3
    assert "limitations" in report
    assert "disclaimer" in report

    # Legacy frontend compatibility fields
    assert "id" in report
    assert "status" in report
    assert "statusLabel" in report
    assert "confidenceScore" in report
    assert "extracted_text" in report
    assert "oriented_image_base64" in report
    assert report["oriented_image_base64"] == "data:image/jpeg;base64,ABC"
    assert "ocr" in report["signals"]
    assert "consistency" in report["signals"]
    assert "raw_inputs" in report
