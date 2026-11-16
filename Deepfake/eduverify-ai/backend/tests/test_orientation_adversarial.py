"""
Adversarial Empirical Stress Tests for EduVerify AI Image Orientation
====================================================================
Empirically tests and stress-tests:
1. EXIF orientation tags (1, 2, 3, 4, 5, 6, 7, 8) handling in normalize_image.
2. Multiple Pillow color modes (RGB, RGBA, L, 1, P, CMYK, LA).
3. Extreme aspect ratios (ultra-tall, ultra-wide, large resolution preservation).
4. Asymmetric corner-marker verification ensuring oriented_image_base64 is NEVER rotated,
   even when internal OCR candidate evaluations select 180°, 90°, or 270°.
5. OCR candidate skipping when 0° has >= 8 words.
6. Corrupt / missing EXIF gracefully handled.
"""

import io
import base64
import pytest
from typing import Tuple, List, Optional
import numpy as np
from PIL import Image, ImageOps
from unittest.mock import patch

from api.services.orientation import (
    normalize_image,
    image_to_base64_data_uri,
    score_reading_flow,
    apply_fine_deskew
)
from api.services.ocr import extract_ocr


# EXIF tag 0x0112 is Orientation
EXIF_ORIENTATION_TAG = 0x0112


def _create_image_with_exif(width: int, height: int, orientation_tag: int) -> bytes:
    """Helper to create a JPEG byte stream with a specific EXIF orientation tag."""
    img = Image.new("RGB", (width, height), color=(200, 220, 240))
    exif = img.getexif()
    exif[EXIF_ORIENTATION_TAG] = orientation_tag
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _create_asymmetric_image(width: int = 100, height: int = 200) -> Tuple[Image.Image, bytes]:
    """
    Creates an image with distinct asymmetric colored patches at the four corners:
      - Top-Left (0, 0): RED (255, 0, 0)
      - Top-Right (w, 0): GREEN (0, 255, 0)
      - Bottom-Left (0, h): BLUE (0, 0, 255)
      - Bottom-Right (w, h): YELLOW (255, 255, 0)
    """
    arr = np.full((height, width, 3), 128, dtype=np.uint8)
    # 20x20 corner patches
    pw = min(20, width // 2)
    ph = min(20, height // 2)
    arr[0:ph, 0:pw] = [255, 0, 0]        # Top-Left: Red
    arr[0:ph, width-pw:width] = [0, 255, 0] # Top-Right: Green
    arr[height-ph:height, 0:pw] = [0, 0, 255] # Bottom-Left: Blue
    arr[height-ph:height, width-pw:width] = [255, 255, 0] # Bottom-Right: Yellow
    
    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return img, buf.getvalue()


# ==============================================================================
# Suite 1: EXIF Orientations (Tags 1, 2, 3, 4, 5, 6, 7, 8)
# ==============================================================================

@pytest.mark.parametrize("orientation_tag,expected_transposed_size", [
    (1, (100, 200)),  # Normal
    (2, (100, 200)),  # Mirrored horizontal
    (3, (100, 200)),  # Rotated 180
    (4, (100, 200)),  # Mirrored vertical
    (5, (200, 100)),  # Transposed
    (6, (200, 100)),  # Rotated 90 CW (transposed aspect ratio)
    (7, (200, 100)),  # Transverse
    (8, (200, 100)),  # Rotated 270 CW (transposed aspect ratio)
])
def test_exif_orientation_normalization(orientation_tag, expected_transposed_size):
    """
    Empirically verify that normalize_image correctly applies EXIF transpose,
    converts to RGB, and that image_to_base64_data_uri produces an unencumbered
    JPEG that decodes to the expected visual dimensions.
    """
    img_bytes = _create_image_with_exif(100, 200, orientation_tag)
    pil_in = Image.open(io.BytesIO(img_bytes))
    
    normalized = normalize_image(pil_in)
    assert normalized.mode == "RGB"
    assert normalized.size == expected_transposed_size
    
    # Verify base64 conversion produces valid JPEG without EXIF orientation tag
    uri = image_to_base64_data_uri(normalized)
    assert uri.startswith("data:image/jpeg;base64,")
    
    decoded_bytes = base64.b64decode(uri.split(",", 1)[1])
    reopened = Image.open(io.BytesIO(decoded_bytes))
    assert reopened.size == expected_transposed_size
    # Verify the output image has no conflicting EXIF orientation
    out_exif = reopened.getexif()
    assert EXIF_ORIENTATION_TAG not in out_exif or out_exif[EXIF_ORIENTATION_TAG] == 1


# ==============================================================================
# Suite 2: Color Modes Stress Testing
# ==============================================================================

@pytest.mark.parametrize("mode,color", [
    ("RGB", (100, 150, 200)),
    ("RGBA", (100, 150, 200, 128)),
    ("L", 128),
    ("1", 1),
    ("P", 1),
    ("CMYK", (50, 100, 150, 20)),
    ("LA", (128, 200)),
])
def test_various_color_modes_normalized_to_rgb(mode, color):
    """Verify that normalize_image reliably converts any input color mode to RGB without failure."""
    img = Image.new(mode, (120, 80), color=color)
    normalized = normalize_image(img)
    assert normalized.mode == "RGB"
    assert normalized.size == (120, 80)
    
    # Must also be encodable to data URI
    uri = image_to_base64_data_uri(normalized)
    assert uri.startswith("data:image/jpeg;base64,")
    decoded = Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))
    assert decoded.mode == "RGB"
    assert decoded.size == (120, 80)


# ==============================================================================
# Suite 3: Aspect Ratios and High Resolution Preservation
# ==============================================================================

@pytest.mark.parametrize("size", [
    (50, 500),    # Ultra-tall (1:10)
    (500, 50),    # Ultra-wide (10:1)
    (333, 333),   # Square
    (15, 15),     # Tiny
    (2400, 1800), # Large high-res image (> 1200 thumbnail threshold)
])
def test_aspect_ratios_and_resolution_preservation(size):
    """
    Verify that oriented_image_base64 preserves the original uploaded dimensions,
    even when size exceeds 1200px (ensuring thumbnailing for inference did NOT mutate raw_img).
    """
    img = Image.new("RGB", size, color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference", return_value="One Two Three Four Five Six Seven Eight Nine Ten"):
        
        result = extract_ocr(image_bytes)
        
        b64_data = result["oriented_image_base64"].split(",", 1)[1]
        decoded = Image.open(io.BytesIO(base64.b64decode(b64_data)))
        assert decoded.size == size, f"Expected size {size}, got {decoded.size} - resolution was mutated!"


# ==============================================================================
# Suite 4: Adversarial Candidate Evaluation & Asymmetric Pixel Verification
# ==============================================================================

def test_adversarial_180_candidate_selected_but_image_remains_0():
    """
    Empirically test that when 0° has 0 words and 180° candidate produces 15 words,
    the OCR text is taken from 180°, but the returned image matches 0° exactly in pixel space.
    """
    orig_img, image_bytes = _create_asymmetric_image(100, 200)
    
    call_angles = []
    
    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference") as mock_infer:
        
        def infer_side_effect(prep_img, sys_msg, user_prompt, max_tokens=1024):
            # Record that inference was called
            nonlocal call_angles
            call_angles.append(len(call_angles))
            if len(call_angles) == 1:
                # 0° candidate returns 0 words
                return ""
            elif len(call_angles) == 2:
                # 180° candidate returns 15 words
                return "First Generation Second Generation Computer Architecture CPU RAM ROM Motherboard Storage Cache Processing Unit"
            return ""
            
        mock_infer.side_effect = infer_side_effect
        
        result = extract_ocr(image_bytes)
        
        # Verify text was taken from 180° candidate
        assert result["word_count"] >= 12
        assert "Computer Architecture" in result["extracted_text"]
        
        # Decode oriented_image_base64
        b64_data = result["oriented_image_base64"].split(",", 1)[1]
        decoded = Image.open(io.BytesIO(base64.b64decode(b64_data)))
        assert decoded.size == (100, 200)
        
        # Check corner colors to prove ZERO rotation in returned image
        dec_arr = np.array(decoded)
        # Top-left corner (0:10, 0:10) should be predominantly RED
        tl_mean = np.mean(dec_arr[2:8, 2:8], axis=(0, 1))
        assert tl_mean[0] > 200 and tl_mean[1] < 50 and tl_mean[2] < 50, f"Top-Left is not Red: {tl_mean}"
        
        # Top-right corner (0:10, 90:100) should be predominantly GREEN
        tr_mean = np.mean(dec_arr[2:8, 92:98], axis=(0, 1))
        assert tr_mean[1] > 200 and tr_mean[0] < 50 and tr_mean[2] < 50, f"Top-Right is not Green: {tr_mean}"
        
        # Bottom-left corner (190:200, 0:10) should be predominantly BLUE
        bl_mean = np.mean(dec_arr[192:198, 2:8], axis=(0, 1))
        assert bl_mean[2] > 200 and bl_mean[0] < 50 and bl_mean[1] < 50, f"Bottom-Left is not Blue: {bl_mean}"


def test_adversarial_90_and_270_candidate_selected_but_image_remains_0():
    """
    Empirically test that when 0° has 1 word (< 5 words), 180° fails, and 90° wins,
    oriented_image_base64 retains the original 0° orientation and aspect ratio (100x200),
    not the 90°-rotated aspect ratio (200x100).
    """
    orig_img, image_bytes = _create_asymmetric_image(100, 200)
    
    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference") as mock_infer:
        
        call_count = 0
        def infer_side_effect(prep_img, sys_msg, user_prompt, max_tokens=1024):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 0° returns 1 word
                return "smudge"
            elif call_count == 2:
                # 180° returns 2 words (not significantly better)
                return "faint smudge"
            elif call_count == 3:
                # 90° returns 16 words (significantly better!)
                return "The fundamental unit of data processing is the Central Processing Unit which reads instructions"
            return ""
            
        mock_infer.side_effect = infer_side_effect
        
        result = extract_ocr(image_bytes)
        
        # Verify text was selected from 90°
        assert result["word_count"] >= 12
        assert "Central Processing Unit" in result["extracted_text"]
        
        # Crucial check: oriented_image_base64 must NOT be rotated 90°!
        # If it were rotated 90°, size would be (200, 100), but original is (100, 200)
        b64_data = result["oriented_image_base64"].split(",", 1)[1]
        decoded = Image.open(io.BytesIO(base64.b64decode(b64_data)))
        assert decoded.size == (100, 200), f"Size flipped to {decoded.size}! Image was rotated!"
        
        # Corner colors must still match 0°
        dec_arr = np.array(decoded)
        tl_mean = np.mean(dec_arr[2:8, 2:8], axis=(0, 1))
        assert tl_mean[0] > 200, f"Top-Left should be Red, got {tl_mean}"


def test_adversarial_sufficient_words_completely_skips_alternative_search():
    """
    Verify that when 0° has >= 8 words, candidates [180, 90, 270] are never even tested,
    ensuring zero unnecessary model evaluations.
    """
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference") as mock_infer:
        
        # 8 words at 0°
        mock_infer.return_value = "One Two Three Four Five Six Seven Eight"
        
        result = extract_ocr(image_bytes)
        
        # Exactly 1 inference call
        assert mock_infer.call_count == 1
        assert result["word_count"] == 8
        assert result["oriented_image_base64"].startswith("data:image/jpeg;base64,")


# ==============================================================================
# Suite 5: Robustness with PNG Transparencies, Corrupt Bytes, & Flow Edge Cases
# ==============================================================================

def test_extract_ocr_with_png_rgba_input():
    """Verify that extract_ocr processes PNG images with an alpha channel seamlessly."""
    png_img = Image.new("RGBA", (150, 100), color=(50, 100, 150, 128))
    buf = io.BytesIO()
    png_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference", return_value="Title: Engineering Physics Assignment"):
        
        result = extract_ocr(png_bytes)
        assert result["oriented_image_base64"].startswith("data:image/")
        b64_data = result["oriented_image_base64"].split(",", 1)[1]
        decoded_bytes = base64.b64decode(b64_data)
        assert decoded_bytes == png_bytes
        decoded = Image.open(io.BytesIO(decoded_bytes))
        assert decoded.size == (150, 100)


def test_extract_ocr_corrupt_bytes_gracefully_handled():
    """Verify that extract_ocr catches bad/corrupt image bytes without crashing."""
    corrupt_bytes = b"CORRUPT_NOT_AN_IMAGE_PAYLOAD_123456"
    with patch("api.services.ocr.load_qwen_model", return_value=None):
        result = extract_ocr(corrupt_bytes)
        assert "ERROR:" in result["extracted_text"]
        assert result["is_readable"] is False
        assert result["word_count"] == 0


def test_reading_flow_additional_edge_cases():
    """Verify flow scores across various numbering, capitalization, and trailing clauses."""
    # Numbered heading with capitalization scores positive upright flow
    text_numbered = "1. Introduction to Quantum Computing\nSuperposition is a core property."
    assert score_reading_flow(text_numbered) > 0

    # Inverted document ending with 'definition of'
    inverted_def = "which satisfies all constraints.\nDefinition of Boolean Algebra"
    assert score_reading_flow(inverted_def) < 0

    # Sentence that happens to contain definition in the middle of concluding paragraph (not short standalone heading)
    normal_conclusion = "Conclusion\nAs shown in the lab, this matches the classical definition of resistance."
    # Last line has 11 words (> 6 words), so it should not trigger the standalone heading inverted penalty (-15)
    score_conclusion = score_reading_flow(normal_conclusion)
    assert score_conclusion >= 0


# ==============================================================================
# Suite 5: Adversarial Reading Flow Battery (Upright & Inverted Documents)
# ==============================================================================

@pytest.mark.parametrize("doc_name,text", [
    ("CS Notes - Operating Systems", "Computer Science - Unit 1\nIntroduction to Operating Systems\nProcess management and memory allocation"),
    ("CS Notes - Generations", "Generations of Computer\nFirst generation: vacuum tubes\nSecond generation: transistors\nThird generation: integrated circuits"),
    ("CS Notes - CPU Architecture", "CPU Architecture and Design\nALU, Control Unit, and Registers\nBus interconnection structure"),
    ("CS Notes - RAM and ROM", "RAM and ROM Differences\nRAM is volatile memory whereas ROM is non-volatile\nCache memory hierarchy"),
    ("CS Notes - Algorithms", "Algorithm Analysis\nTime complexity O(n log n)\nSpace complexity O(n)"),
    ("CS Notes - Software Lab", "Software Engineering Lab\nAgile methodologies and sprint cycles\nDeployment pipeline"),
    ("CS Notes - Hardware", "Hardware Architecture\nVon Neumann model\nStored program concept"),
    ("CS Notes - System Design", "System Design Notes\nLoad balancers and reverse proxies\nMicroservices architecture"),
    ("Lab Exp - Study of Logic Gates", "Experiment No: 3\nAim: Study of logic gates\nApparatus: IC 7400, IC 7408, IC 7432\nProcedure and observations"),
    ("Assignment - Data Structures", "Assignment 4: Data Structures\nQuestion 1: Implement a binary search tree\nSolution: We define a Node class with left and right pointers"),
    ("Question - Half Adder", "Q.1 Describe the working of Half Adder\nA half adder adds two single binary digits\nSum = A XOR B, Carry = A AND B"),
    ("Lecture - Distributed DB", "Lecture 12: Distributed Databases\nCAP Theorem: Consistency, Availability, Partition tolerance"),
    ("Section - OS Questions", "Section B: Operating Systems\nQuestion: Explain page fault handling"),
    ("Metadata - Date Page Roll", "Date: 15-11-2024\nPage: 12\nRoll No: 1024\nTopic: Binary Addition\nAdding two bits produces sum and carry"),
    ("Metadata - Pg Date Physics", "Pg. 5\nDate: 2024/10/05\nPhysics Lab Experiment\nMeasuring gravitational acceleration"),
    ("Metadata - Roll Name DBMS", "Roll No: CS-2024-042\nName: Alex Smith\nDatabase Management Systems\nRelational Algebra operations"),
    ("Math - Calculus Notes", "Calculus Notes\nIntegral of x^2 dx = x^3/3 + C\nDerivative of sin(x) = cos(x)"),
    ("Math - Linear Algebra", "Linear Algebra\nEigenvalues and Eigenvectors: Av = lambda v\nMatrix determinant calculation"),
    ("Math - Probability", "Probability and Statistics\nP(A|B) = P(B|A) * P(A) / P(B)\nBayes Theorem and conditional distributions"),
    ("Def at bottom - Logic Gates", "Digital Logic Design\nLogic gates are the basic building blocks.\nIn summary, the definition of half adder is a combinational circuit adding two bits."),
    ("Def at bottom - Data Structures", "Data Structures\nArrays allow constant time indexing.\nFinally, the formal definition of linked list is a linear collection of data elements."),
    ("Def at bottom - Networks", "Computer Networks\nTCP provides reliable ordered byte streams.\nBy definition, UDP is a connectionless datagram protocol."),
    ("Natural starter - The", "The system architecture consists of three tiers: presentation, application, and database."),
    ("Natural starter - When", "When the processor executes an instruction, it performs fetch, decode, and execute cycles."),
    ("Natural starter - In", "In this experiment, we measure the resistance using a Wheatstone bridge."),
    ("Natural starter - For", "For every positive integer n, the mathematical induction base case holds."),
    ("Natural starter - To", "To implement the queue, we use a circular array."),
    ("Natural starter - An", "An inverted index is a database data structure storing a mapping from words to documents."),
    ("Natural starter - A", "A binary search tree has the property that left children are smaller than the parent."),
])
def test_adversarial_reading_flow_upright_documents_score_non_negative(doc_name, text):
    """
    Verify that all realistic upright student documents (CS notes, lab experiments,
    metadata headers, math formulas, terminal definitions) score non-negative flow.
    """
    score = score_reading_flow(text)
    assert score >= 0, f"Upright document '{doc_name}' incorrectly penalized with score {score}!\nText:\n{text}"


@pytest.mark.parametrize("doc_name,text", [
    ("Trailing starter - it produces", "it produces the final carry bit.\nwhich is then routed to the next stage.\nChapter 3: Full Adder Design"),
    ("Trailing starter - it accepts", "it accepts two inputs A and B.\nand produces sum and carry.\nExperiment 1: Half Adder"),
    ("Trailing starter - it has", "it has low latency and high bandwidth.\nMemory Hierarchy\nCPU Architecture"),
    ("Trailing starter - and hence", "and hence the circuit is verified.\nTruth Table\nTitle: Logic Gates Lab"),
    ("Trailing starter - or false", "or false if any condition fails.\nBoolean Expressions\nTopic: Discrete Math"),
    ("Trailing starter - that adds", "that adds two numbers.\nBinary Adder\nDefinition of Half Adder"),
    ("Trailing starter - which is", "which is the output voltage.\nAmplifier Circuit\nExperiment 2"),
    ("Trailing starter - then", "then the result is stored in the accumulator.\nALU Operations\nChapter 4: Microprocessors"),
    ("Trailing starter - therefore", "therefore the algorithm terminates in O(n) time.\nCorrectness Proof\nAlgorithm: Merge Sort"),
    ("Trailing starter - hence", "hence the theorem is proved.\nMathematical Induction\nChapter 1: Foundations"),
    ("Inverted bottom title - Title", "The circuit was tested on the breadboard.\nAll measurements were recorded accurately.\nTitle: Half Adder Experiment"),
    ("Inverted bottom title - Experiment", "The experimental error was within 2 percent.\nResults agree with theoretical values.\nExperiment 5"),
    ("Inverted bottom title - Chapter", "Thus vacuum tubes consumed large amounts of electrical power.\nChapter 1: History of Computers"),
    ("Inverted bottom title - Topic", "The truth table matches the expected Boolean functions.\nTopic: Combinational Circuits"),
    ("Inverted bottom title - Half Adder", "The carry output is generated using an AND gate.\nHalf Adder"),
    ("Inverted bottom title - Definition of", "The sum output is generated using an XOR gate.\nDefinition of Half Adder"),
    ("Inverted bottom title - Definition:", "A full adder is composed of two half adders and an OR gate.\nDefinition: Full Adder"),
    ("Empty document", ""),
    ("Whitespace only", "   \n\n\t  "),
])
def test_adversarial_reading_flow_inverted_documents_score_negative(doc_name, text):
    """
    Verify that genuine inverted/bottom-first documents are properly penalized
    with a negative score.
    """
    score = score_reading_flow(text)
    assert score < 0, f"Inverted document '{doc_name}' failed to receive negative score! Got: {score}\nText:\n{text}"


# ==============================================================================
# Suite 6: Backend Server & Health Check In-Memory Verification
# ==============================================================================

def test_backend_server_app_boots_and_health_responds():
    """Verify that the FastAPI application instantiates cleanly and /health responds."""
    from main import app, health_check
    
    assert app.title == "EduVerify AI Backend"
    res = health_check()
    assert res == {"status": "ok"}
    route_paths = [getattr(route, "path", "") for route in app.routes]
    assert "/health" in route_paths

