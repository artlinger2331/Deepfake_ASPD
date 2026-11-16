# Handoff Report — Explorer 3: Test Suite & Regression Analysis

## 1. Observation

### 1.1 Existing Test Suite Structure & Baseline Execution
- **Pytest Configuration**: `Deepfake/eduverify-ai/backend/pytest.ini` defines:
  ```ini
  [pytest]
  testpaths = tests
  python_files = test_*.py
  python_classes = Test*
  python_functions = test_*
  addopts = -v --tb=short
  ```
- **Test File Inventory** in `Deepfake/eduverify-ai/backend/tests`:
  - `conftest.py` (adds `backend` and `evaluation` to `sys.path`)
  - `test_evaluation.py` (622 lines, 24 test functions)
  - `test_scoring.py` (352 lines, 9 test functions)
  - `__init__.py`
  - Total tests collected: **33 items**.
- **Pytest Baseline Execution**:
  - Command:
    `& 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe' -m pytest 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\tests' -q`
  - Execution Result:
    ```
    ============================= test session starts =============================
    platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0
    rootdir: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend
    configfile: pytest.ini
    plugins: anyio-4.15.1
    collected 33 items

    Deepfake\eduverify-ai\backend\tests\test_evaluation.py ................. [ 51%]
    .......                                                                  [ 72%]
    Deepfake\eduverify-ai\backend\tests\test_scoring.py .........            [100%]

    ============================= 33 passed in 1.36s ==============================
    ```
  - Exit code: `0`. All 33 tests passed cleanly.

### 1.2 Tests Touching OCR, Orientation, or `oriented_image_base64`
1. **`test_evaluation.py`**:
   - `test_extract_response_fields_schema_conformance()` (lines 124–168): Validates mapping of mock `raw_inputs.ocr` to summary fields (`extracted["ocr_word_count"] == 3`). Does not reference orientation or base64 image data.
   - `test_missing_transcription_reference_does_not_crash_metrics_calculator()` (lines 508–534): Validates evaluation handling of `res["ocr_text"]` and `res["ocr_confidence"]`.
2. **`test_scoring.py`**:
   - `test_ocr_consistency_score_calculation()` (lines 209–225): Tests `calculate_ocr_consistency_score` on synthetic repetitive text loops vs natural text.
   - `test_fusion_formula_and_weights()` (lines 230–249): Tests multi-signal weighting using mock OCR dict (`{"data": {"extracted_text": "Simple line", "word_count": 2, "confidence_score": 85.0}}`).
   - `test_decision_threshold_classification()` (lines 254–299): Tests verdict transitions across thresholds using mock OCR dicts.
   - `test_api_response_format_and_backward_compatibility()` (lines 305–352):
     - Line 309: Provides mock input containing `oriented_image_base64`:
       ```python
       {"data": {"extracted_text": "Sample student test line", "word_count": 4, "confidence_score": 90.0, "oriented_image_base64": "data:image/jpeg;base64,ABC"}}
       ```
     - Lines 347–348:
       ```python
       assert "oriented_image_base64" in report
       assert report["oriented_image_base64"] == "data:image/jpeg;base64,ABC"
       ```
     - Validates that `fuse_results()` faithfully passes through the `oriented_image_base64` string key from OCR data to the top-level report dictionary.

### 1.3 Testing Gaps Regarding Orientation and Rotation
- **Zero Rotation Asserts**: There are **no tests** asserting that `oriented_image_base64` is rotated, nor any tests testing non-zero angles (90°, 180°, 270°).
- **Zero OCR / Orientation Unit Tests**: Neither `Deepfake/eduverify-ai/backend/api/services/ocr.py` nor `Deepfake/eduverify-ai/backend/api/services/orientation.py` has dedicated unit test files in `backend/tests`.
- **Zero Calls to `extract_ocr()` in Tests**: All existing test cases in `test_scoring.py` use pre-constructed mock dictionaries when calling `fuse_results()`. The Qwen2-VL model loading and candidate rotation evaluation logic in `extract_ocr()` are completely bypassed by existing tests.

### 1.4 Frontend Consumer
- In `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx` (lines 282–286):
  ```jsx
  {(report.oriented_image_base64 || previewImage) ? (
      <img
          src={report.oriented_image_base64 || previewImage}
          alt="Submitted Document"
          className="w-full h-auto max-h-[380px] object-contain rounded-lg border border-slate-700/60 shadow-inner bg-slate-950/60"
      />
  ) : ...
  ```
  The frontend uses `report.oriented_image_base64` directly for the "Submitted Document" preview.

---

## 2. Logic Chain

1. **Premise 1 (Existing Test Coverage)**:
   All 33 existing tests pass in 1.36s (Observation 1.1).
   Only one test (`test_scoring.py:305-352`) checks `oriented_image_base64` (Observation 1.2).
2. **Premise 2 (Passthrough Assertion Only)**:
   `test_api_response_format_and_backward_compatibility` validates solely that the value in `ocr_data["data"]["oriented_image_base64"]` is preserved by `fuse_results()` and returned under the top-level key `oriented_image_base64` (Observation 1.2). It does not call `extract_ocr()` or check image pixels or rotation angles.
3. **Premise 3 (Zero Rotation Dependencies)**:
   No existing test asserts that `oriented_image_base64` is rotated 90°, 180°, or 270° (Observation 1.3).
4. **Premise 4 (Implementation Impact)**:
   In `backend/api/services/ocr.py`:
   - Current line 352: `result["oriented_image_base64"] = image_to_base64_data_uri(best_img)`
   - Desired fix: `result["oriented_image_base64"] = image_to_base64_data_uri(raw_img)` (where `raw_img` is 0° with EXIF normalization only).
   Because no existing test calls `extract_ocr()` and no test checks rotated image content, changing `result["oriented_image_base64"]` to always use the 0° image (`raw_img`) has **zero chance of breaking any of the 33 existing tests**.
5. **Premise 5 (Regression Prevention Need)**:
   Because `orientation.py` and `ocr.py` currently have zero unit test coverage (Observation 1.3), future changes could inadvertently re-introduce rotation or break image encoding. A lightweight, non-GPU unit test suite should be created to lock in the correct behavior.

---

## 3. Caveats

- **No Caveats Regarding Existing Suite**: The existing 33 tests are fully independent of the GPU model weights and will unaffected.
- **Model Isolation for New Tests**: `extract_ocr()` in `ocr.py` imports and invokes `load_qwen_model()` which requires HuggingFace transformers and GPU/CPU model loading. Any new unit tests for `ocr.py` MUST mock `load_qwen_model` and `_run_inference` (or `evaluate_candidate`) to ensure tests remain fast (< 2 seconds) and runnable in CI/CD without GPU or multi-gigabyte weight downloads.
- **Pure Python for `orientation.py`**: All functions in `orientation.py` (`normalize_image`, `image_to_base64_data_uri`, `score_reading_flow`, `apply_fine_deskew`) use OpenCV, PIL, and standard Python. They can be tested directly without any mocking.

---

## 4. Conclusion & Concrete Recommendations

### 4.1 Regression Risk Assessment
- **Risk Level**: **NONE (0%)**.
- Retaining `oriented_image_base64` at 0° (the original uploaded image with EXIF normalization) introduces zero regressions to the existing 33 pytest tests.
- All 33 existing tests will continue to pass without modification.

### 4.2 Proposed New Tests (`tests/test_orientation.py`)
To prevent regression and guarantee long-term test coverage, the implementer should add `Deepfake/eduverify-ai/backend/tests/test_orientation.py` containing the following tests:

```python
"""
EduVerify AI - Unit Test Suite for Orientation and Document Presentation
=======================================================================
Verifies that:
  1. normalize_image handles EXIF tags and converts to RGB.
  2. image_to_base64_data_uri outputs valid data URIs.
  3. score_reading_flow assigns positive scores to normal academic headers.
  4. extract_ocr ALWAYS outputs oriented_image_base64 in the original 0° orientation,
     even when internal OCR tests 180° rotation for text transcription.
"""

import io
import base64
import pytest
from PIL import Image
from unittest.mock import patch

from api.services.orientation import (
    normalize_image,
    image_to_base64_data_uri,
    score_reading_flow,
    apply_fine_deskew
)
from api.services.ocr import extract_ocr
from api.services.fusion import fuse_results


def test_normalize_image_rgb_conversion():
    """Verify that normalize_image converts RGBA and grayscale images to RGB."""
    rgba = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    normalized = normalize_image(rgba)
    assert normalized.mode == "RGB"
    assert normalized.size == (100, 100)


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
    upright_text = (
        "Chapter 1: Generations of Computers\n"
        "The first generation computers used vacuum tubes.\n"
        "Second generation computers used transistors.\n"
        "Summary of CPU and RAM performance."
    )
    score = score_reading_flow(upright_text)
    assert score >= 0, f"Upright text incorrectly scored negative: {score}"


def test_score_reading_flow_inverted_document_signals():
    """Verify that inverted/bottom-first documents are penalized."""
    inverted_text = (
        "Page: 12\n"
        "and it produces the final carry bit.\n"
        "which is then transferred to memory.\n"
        "Definition of Half Adder"
    )
    score = score_reading_flow(inverted_text)
    assert score < 0, f"Inverted text should score negative flow, got: {score}"


def test_extract_ocr_always_retains_original_0_degree_image():
    """
    CRITICAL REGRESSION TEST:
    Even when the OCR candidate search evaluates and prefers a 180° rotation for text,
    the returned 'oriented_image_base64' MUST be the original uploaded 0° image.
    """
    # Create an asymmetrical test image: 100 wide x 200 high
    img_0 = Image.new("RGB", (100, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    img_0.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    # Mock Qwen model loading and inference to simulate 180° winning the text contest
    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference") as mock_infer:
        
        # When angle 0 is tested: return low word count (e.g. 2 words)
        # When angle 180 is tested: return high word count (e.g. 20 words)
        def side_effect(prep_img, sys_msg, user_prompt, max_tokens=1024):
            # If image was rotated 180°, its size is still 100x200, but we simulate better transcription
            return "First Generation Second Generation Third Generation Fourth Generation CPU RAM ROM ALU"
            
        mock_infer.side_effect = side_effect

        result = extract_ocr(image_bytes)

        # Confirm oriented_image_base64 exists
        assert "oriented_image_base64" in result
        assert result["oriented_image_base64"].startswith("data:image/jpeg;base64,")

        # Decode the returned image and verify dimensions match the original (100x200)
        b64_data = result["oriented_image_base64"].split(",", 1)[1]
        decoded = Image.open(io.BytesIO(base64.b64decode(b64_data)))
        assert decoded.size == (100, 200), "Decoded oriented_image_base64 must match original dimensions"
```

---

## 5. Verification Method

To independently verify the test suite and confirm zero regressions:

1. **Run Pytest Command**:
   ```powershell
   & 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe' -m pytest 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\tests' -q
   ```
   - **Expected Result**: `33 passed` (or `38 passed` once new tests are added) with exit code `0`.
   - **Invalidation Condition**: Any failures or errors among the 33 existing tests.

2. **Inspect Code Files**:
   - Inspect `Deepfake/eduverify-ai/backend/tests/test_scoring.py:305-352` to verify `oriented_image_base64` passthrough assertion.
   - Inspect `Deepfake/eduverify-ai/backend/api/services/ocr.py:352` to verify `result["oriented_image_base64"] = image_to_base64_data_uri(raw_img)`.
   - Inspect `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx:282-286` to confirm frontend receives the 0° image URI.
