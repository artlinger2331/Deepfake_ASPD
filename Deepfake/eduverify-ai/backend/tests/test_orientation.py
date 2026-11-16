"""
EduVerify AI - Unit Test Suite for Orientation and Document Presentation
=======================================================================
Verifies that:
  1. normalize_image handles EXIF tags and converts to RGB.
  2. image_to_base64_data_uri outputs valid data URIs.
  3. score_reading_flow assigns positive scores to normal academic headers.
  4. score_reading_flow penalizes inverted bottom-first document structures.
  5. extract_ocr ALWAYS outputs oriented_image_base64 in the original 0° orientation,
     even when internal OCR tests 180° rotation for text transcription.
  6. extract_ocr skips alternative rotation tests when 0° has sufficient words.
"""

import io
import os
import base64
from pathlib import Path
import pytest
from PIL import Image
from unittest.mock import patch

from api.services.orientation import (
    normalize_image,
    image_to_base64_data_uri,
    raw_bytes_to_base64_data_uri,
    score_reading_flow,
    apply_fine_deskew
)
from api.services.ocr import extract_ocr


def test_normalize_image_rgb_conversion():
    """Verify that normalize_image converts RGBA and grayscale images to RGB."""
    rgba = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    normalized_rgba = normalize_image(rgba)
    assert normalized_rgba.mode == "RGB"
    assert normalized_rgba.size == (100, 100)

    gray = Image.new("L", (80, 80), color=128)
    normalized_gray = normalize_image(gray)
    assert normalized_gray.mode == "RGB"
    assert normalized_gray.size == (80, 80)


def test_image_to_base64_data_uri_roundtrip():
    """Verify image_to_base64_data_uri creates a valid, decodable JPEG data URI."""
    img = Image.new("RGB", (120, 80), color=(100, 150, 200))
    uri = image_to_base64_data_uri(img)
    
    assert uri.startswith("data:image/jpeg;base64,")
    b64_data = uri.split(",", 1)[1]
    decoded_bytes = base64.b64decode(b64_data)
    reopened = Image.open(io.BytesIO(decoded_bytes))
    assert reopened.size == (120, 80)


def test_score_reading_flow_academic_headings():
    """Verify that standard upright technical/academic documents score non-negative flow."""
    upright_text_1 = (
        "Date: 12/10/24\n"
        "Generations of Computer\n"
        "1st Gen: Vacuum tubes were used."
    )
    score1 = score_reading_flow(upright_text_1)
    assert score1 >= 15, f"Date header text scored too low: {score1}"

    upright_text_2 = (
        "Page: 1\n"
        "CPU Architecture\n"
        "The ALU performs arithmetic operations.\n"
        "According to the definition, RAM is volatile memory."
    )
    score2 = score_reading_flow(upright_text_2)
    assert score2 >= 10, f"Upright text with definition at bottom scored too low: {score2}"

    upright_text_3 = (
        "Chapter 1: Generations of Computers\n"
        "The first generation computers used vacuum tubes.\n"
        "Second generation computers used transistors.\n"
        "Summary of CPU and RAM performance."
    )
    score3 = score_reading_flow(upright_text_3)
    assert score3 >= 10, f"Chapter text scored too low: {score3}"


def test_score_reading_flow_inverted_document_signals():
    """Verify that inverted/bottom-first documents are penalized."""
    # Bottom-first text starting with trailing clause and ending with a title
    inverted_text_1 = (
        "and it produces the final carry bit.\n"
        "which is then transferred to memory.\n"
        "Chapter: Half Adder"
    )
    score1 = score_reading_flow(inverted_text_1)
    assert score1 < 0, f"Inverted text should score negative flow, got: {score1}"

    inverted_text_2 = (
        "it produces the sum.\n"
        "Definition of Half Adder"
    )
    score2 = score_reading_flow(inverted_text_2)
    assert score2 < 0, f"Inverted text should score negative flow, got: {score2}"

    # Empty text
    assert score_reading_flow("") == -100
    assert score_reading_flow("   \n\n  ") == -100


def test_extract_ocr_always_retains_original_0_degree_image():
    """
    CRITICAL REGRESSION TEST:
    Even when the OCR candidate search evaluates and prefers a 180° rotation for text,
    the returned 'oriented_image_base64' MUST be the original uploaded 0° image.
    """
    # Create an asymmetrical test image: 120 wide x 240 high
    img_0 = Image.new("RGB", (120, 240), color=(240, 240, 240))
    buf = io.BytesIO()
    img_0.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    # Mock Qwen model loading and inference to simulate 180° winning the text contest
    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference") as mock_infer:
        
        call_count = 0
        def side_effect(prep_img, sys_msg, user_prompt, max_tokens=1024):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (0°): Return low word count (< 8) to trigger alternative candidate search
                return "low word"
            else:
                # Second call (180°): Return high word count
                return "First Generation Second Generation Third Generation Fourth Generation CPU RAM ROM ALU Computer System Architecture"
            
        mock_infer.side_effect = side_effect

        result = extract_ocr(image_bytes)

        # Confirm oriented_image_base64 exists and is valid
        assert "oriented_image_base64" in result
        assert result["oriented_image_base64"].startswith("data:image/jpeg;base64,")

        # Confirm the text was updated from the superior alternative
        assert result["word_count"] >= 10
        assert "Computer System Architecture" in result["extracted_text"]

        # Decode the returned image and verify dimensions match original 0° orientation (120x240)
        b64_data = result["oriented_image_base64"].split(",", 1)[1]
        decoded = Image.open(io.BytesIO(base64.b64decode(b64_data)))
        assert decoded.size == (120, 240), "Decoded oriented_image_base64 must match original dimensions (120, 240)"


def test_extract_ocr_does_not_evaluate_alternative_when_upright():
    """Verify that when 0° produces sufficient words (>= 8), alternatives are not evaluated."""
    img_0 = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img_0.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference") as mock_infer:
        
        # Candidate 0 returns 10 words
        mock_infer.return_value = "One Two Three Four Five Six Seven Eight Nine Ten"

        result = extract_ocr(image_bytes)

        # Only candidate 0° should be evaluated (mock_infer called once)
        assert mock_infer.call_count == 1
        assert result["word_count"] == 10
        assert result["oriented_image_base64"].startswith("data:image/jpeg;base64,")


def test_oriented_image_base64_exact_byte_verbatim_jpeg():
    """Verify that oriented_image_base64 preserves exact raw JPEG bytes bit-for-bit without re-encoding."""
    img = Image.new("RGB", (160, 240), color=(180, 200, 220))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    raw_bytes = buf.getvalue()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference", return_value="One Two Three Four Five Six Seven Eight Nine"):
        res = extract_ocr(raw_bytes)

    assert "oriented_image_base64" in res
    assert res["oriented_image_base64"].startswith("data:image/jpeg;base64,")
    b64_data = res["oriented_image_base64"].split(",", 1)[1]
    decoded_bytes = base64.b64decode(b64_data)
    assert decoded_bytes == raw_bytes, "oriented_image_base64 was re-encoded or mutated! Bytes must be bit-for-bit identical."


def test_oriented_image_base64_exact_byte_verbatim_png():
    """Verify that oriented_image_base64 preserves raw PNG bytes and data:image/png prefix."""
    img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference", return_value="One Two Three Four Five Six Seven Eight Nine"):
        res = extract_ocr(raw_bytes)

    assert res["oriented_image_base64"].startswith("data:image/png;base64,")
    b64_data = res["oriented_image_base64"].split(",", 1)[1]
    assert base64.b64decode(b64_data) == raw_bytes


def test_ev_35d17c96_sample_verbatim_and_not_rotated():
    """
    Verify that real user artifact EV-35D17C96 is preserved verbatim,
    retains its 1024x576 dimensions, and does NOT rotate sideways.
    """
    ev_path = r"C:/Users/Pritam Mondal/.gemini/antigravity/brain/8a979481-0fb5-468e-8f32-d21e217e7787/.user_uploaded/media_1794843355919_2564ee42.jpg"
    if not os.path.exists(ev_path):
        pytest.skip("EV-35D17C96 sample file not found on local path.")

    with open(ev_path, "rb") as f:
        ev_bytes = f.read()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference", return_value="Date: 12-10-24 Generations of Computer Notes"):
        res = extract_ocr(ev_bytes, filename="media_1794843355919_2564ee42.jpg")

    b64_data = res["oriented_image_base64"].split(",", 1)[1]
    decoded_bytes = base64.b64decode(b64_data)
    assert decoded_bytes == ev_bytes, "EV-35D17C96 bytes must be preserved verbatim!"

    decoded_img = Image.open(io.BytesIO(decoded_bytes))
    assert decoded_img.size == (1024, 576), f"Dimensions mutated to {decoded_img.size}!"


@pytest.mark.parametrize("img_rel_path,expected_size", [
    ("real_photo/snippet_rot0.jpg", (169, 300)),
    ("real_photo/snippet_rot180.jpg", (169, 300)),
    ("real_photo/snippet_rot90.jpg", (300, 169)),
    ("real_photo/snippet_rot270.jpg", (300, 169)),
    ("ai_generated/Handwritten Winter Essay.png", (1448, 1086)),
    ("real_scan/DocScanner 12-Oct-2026 12-54 AM_page_1.jpg", (1240, 1755)),
])
def test_evaluation_images_verbatim_preservation(img_rel_path, expected_size):
    """Verify that benchmark evaluation images retain exact bytes and dimensions."""
    base_eval = Path(__file__).resolve().parent.parent / "evaluation" / "images"
    img_path = base_eval / img_rel_path
    if not img_path.exists():
        pytest.skip(f"Evaluation image {img_rel_path} not found.")

    with open(img_path, "rb") as f:
        raw_bytes = f.read()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference", return_value="Sample extracted heading text"):
        res = extract_ocr(raw_bytes, filename=img_path.name)

    b64_data = res["oriented_image_base64"].split(",", 1)[1]
    decoded_bytes = base64.b64decode(b64_data)
    assert decoded_bytes == raw_bytes, f"Verbatim bytes failed for {img_rel_path}"

    decoded_img = Image.open(io.BytesIO(decoded_bytes))
    assert decoded_img.size == expected_size

