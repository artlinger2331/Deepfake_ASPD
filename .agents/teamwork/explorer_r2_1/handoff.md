# Handoff Report: Backend Pipeline & Verbatim Raw Bytes Preservation

**Author**: Explorer Subagent (Role: Backend Pipeline Explorer)  
**Date**: 2026-11-16T16:10:00Z  
**Target Milestone**: R1 & R2 Backend Orientation Defect Resolution & Verbatim Byte Preservation  

---

## 1. Observation

### 1.1 Backend Image Ingestion in `router.py`
In `Deepfake/eduverify-ai/backend/api/router.py` (lines 27-58):
```python
27:     file_bytes = file.file.read()
...
34:         ocr_result = process_ocr(file_bytes)
...
56:         final_report = fuse_results(vision_result, ocr_result, handwriting_result, metadata_result)
57:         
58:         return final_report
```
- Direct observation: `router.py` reads `file_bytes` as raw Python `bytes` and passes it synchronously to `process_ocr(file_bytes)`.
- `router.py` performs no image transformation, decoding, or caching.
- There are no separate backend report persistence/retrieval endpoints in `router.py` or `main.py`; reports are returned directly as JSON to the client.

### 1.2 `oriented_image_base64` Generation in `ocr.py`
In `Deepfake/eduverify-ai/backend/api/services/ocr.py` (lines 263-274, 354-356):
```python
263:         from .orientation import (
264:             normalize_image, 
265:             detect_stroke_is_sideways,
266:             score_reading_flow,
267:             apply_fine_deskew, 
268:             image_to_base64_data_uri
269:         )
270:         
271:         raw_img = normalize_image(Image.open(io.BytesIO(image_bytes)))
272:         # Always set oriented_image_base64 to the original uploaded image (0° with EXIF normalization only)
273:         result["oriented_image_base64"] = image_to_base64_data_uri(raw_img)
...
354:         # The returned image is ALWAYS the original uploaded image (0° with EXIF normalization only)
355:         result["oriented_image_base64"] = image_to_base64_data_uri(raw_img)
```
- Direct observation: `result["oriented_image_base64"]` is currently computed using `image_to_base64_data_uri(raw_img)` where `raw_img` is the result of `normalize_image(Image.open(io.BytesIO(image_bytes)))`.
- In `orientation.py` lines 16-21:
  ```python
  def normalize_image(pil_img: Image.Image) -> Image.Image:
      """Applies EXIF rotation normalization and converts to RGB."""
      img = ImageOps.exif_transpose(pil_img)
      if img.mode != "RGB":
          img = img.convert("RGB")
      return img
  ```
- In `orientation.py` lines 167-174:
  ```python
  def image_to_base64_data_uri(pil_img: Image.Image) -> str:
      """Encodes a PIL image into a base64 Data URI for frontend display."""
      import base64
      buffered = io.BytesIO()
      rgb_img = pil_img.convert("RGB")
      rgb_img.save(buffered, format="JPEG", quality=85, optimize=True)
      b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
      return f"data:image/jpeg;base64,{b64_str}"
  ```
- This implementation:
  1. Executes `ImageOps.exif_transpose(pil_img)` which rotates or transposes pixel arrays if an EXIF orientation tag is present.
  2. Discards original format (re-encodes PNG, WebP, etc. as JPEG at quality 85).
  3. Drops EXIF metadata tags from the output JPEG data URI.
  4. Violates verbatim byte-for-byte fidelity with the user's uploaded document file.

### 1.3 Orientation Analysis Flaw in `orientation.py`
In `Deepfake/eduverify-ai/backend/api/services/orientation.py` (lines 45-74):
```python
45: def detect_stroke_is_sideways(pil_img: Image.Image) -> bool:
...
70:     angles = np.rad2deg(np.arctan2(np.abs(sobely[edge_mask]), np.abs(sobelx[edge_mask])))
71:     ratio = np.mean(angles < 30) / (np.mean(angles > 60) + 1e-6)
72:     is_sideways = ratio < 0.90
73:     print(f"[Orientation] Stroke alignment ratio={ratio:.3f} -> is_sideways={is_sideways}")
74:     return is_sideways
```
- Empirical execution of `detect_stroke_is_sideways` on user sample artifact `media_1794843355919_2564ee42.jpg`:
  ```
  [Orientation] Stroke alignment ratio=0.266 -> is_sideways=True
  ```
- Physical cause: On lined student paper and spiral notebooks, the horizontal ruled lines generate dominant vertical Sobel gradients (`sobely` >> `sobelx`), which concentrate angles > 60°. This forces the stroke ratio down to ~0.26, causing a massive false positive where upright notebooks are judged to be sideways.
- In git commit `0be82cd18dd4906cad9e92e93af0543df0b30ce8`, this exact false positive caused `extract_ocr` to prioritize candidates [90, 270] and return `image_to_base64_data_uri(best_img)`, rotating upright notebook submissions 90° sideways.

### 1.4 Downstream Fusion and Frontend Presentation
- In `Deepfake/eduverify-ai/backend/api/services/fusion.py` (lines 280, 398):
  `oriented_image_base64 = ocr_info.get("oriented_image_base64", "")`
  `fusion.py` passes `oriented_image_base64` straight through to `report["oriented_image_base64"]`.
- In `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx` (lines 282-288):
  ```jsx
  {(report.oriented_image_base64 || previewImage) ? (
    <img 
      src={report.oriented_image_base64 || previewImage} 
      alt="Student Assignment Preview" 
      className="analyzed-image"
      style={{ width: '100%', maxHeight: '420px', objectFit: 'contain', borderRadius: '8px' }}
    />
  ) : ...
  ```
  `report.oriented_image_base64` takes precedence over `previewImage`.

### 1.5 Unit Test Suite Baseline
- Execution of `Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe -m pytest Deepfake/eduverify-ai/backend/tests -q`:
  ```
  ============================= 114 passed in 6.24s =============================
  ```
- In `Deepfake/eduverify-ai/backend/tests/test_orientation_adversarial.py` line 312:
  `assert result["oriented_image_base64"].startswith("data:image/jpeg;base64,")`
  This test was coupled to the previous behavior where PNG was coerced into JPEG.

---

## 2. Logic Chain

1. **Step 1 (Root Cause of Sideways Defect)**: In earlier iterations, `detect_stroke_is_sideways` evaluated upright spiral notebooks as sideways (ratio 0.266 < 0.90) due to horizontal notebook ruling lines. The OCR engine selected 90° rotation and returned the rotated image as `oriented_image_base64`.
2. **Step 2 (Defect in Intermediate Mitigation)**: Although `ocr.py` lines 273 and 355 attempted to keep `oriented_image_base64` at 0° using `image_to_base64_data_uri(raw_img)`, `raw_img` is decoded via PIL and transformed by `ImageOps.exif_transpose`, then re-encoded to JPEG.
   - If an image has an EXIF orientation tag, `exif_transpose` flips/rotates the raster pixels and strips the EXIF tag during re-encoding.
   - Re-encoding non-JPEG formats (PNG, WebP) destroys transparency and creates lossy recompression artifacts.
   - Most importantly, it fails Requirement R1: "preserve raw uploaded image bytes verbatim for the submitted document display so that uploaded images remain exactly in their uploaded orientation."
3. **Step 3 (Verbatim Preservation Mechanism)**: Direct base64 encoding of `image_bytes`:
   - Inspects the magic bytes of `image_bytes`:
     - PNG: `b'\x89PNG\r\n\x1a\n'` -> `image/png`
     - JPEG: `b'\xff\xd8\xff'` -> `image/jpeg`
     - WebP: `b'RIFF' ... b'WEBP'` -> `image/webp`
     - Fallback via extension or `image/jpeg`
   - Encodes `image_bytes` directly into `f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"`.
   - Guaranteed byte-for-byte exact equality: `base64.b64decode(uri.split(',')[1]) == image_bytes`.
   - Empirically verified against evaluation dataset samples:
     - `Handwritten Winter Essay.png`: `Byte-for-byte exact equality: True` (`data:image/png;base64,...`)
     - `DocScanner 14-Oct-2026 01-56 AM_page_1.jpg`: `Byte-for-byte exact equality: True` (`data:image/jpeg;base64,...`)
4. **Step 4 (OCR Pipeline Isolation)**: Internal orientation candidate evaluation (e.g., testing 180°, 90°, 270° to help Qwen2-VL read rotated text) is strictly an inference aid. The candidate angle selection for text transcription must NEVER overwrite `result["oriented_image_base64"]`.
5. **Step 5 (Candidate Selection Guardrails)**: In `ocr.py`, candidate 0° is evaluated first. Alternative sideways candidates [90, 270] are only considered if 0° produces `< 5` words, and must be guarded by reading flow criteria (`w_alt >= 10 and flow_alt >= 0`) to prevent random hallucinations on faint text from triggering a false-positive rotation.

---

## 3. Caveats

- **Caveat 1**: `ImageOps.exif_transpose` remains active in `normalize_image(pil_img)` strictly for internal model consumption (`raw_img` passed to Qwen2-VL), ensuring the AI vision model sees upright pixels if EXIF orientation metadata was supplied by the camera. This does not affect `oriented_image_base64` because `oriented_image_base64` is generated directly from raw `image_bytes`.
- **Caveat 2**: When `test_orientation_adversarial.py` line 312 is updated to reflect that PNG uploads now preserve `data:image/png;base64,` rather than converting to JPEG, all 114 tests plus new tests pass cleanly.
- **Caveat 3**: Frontend image rendering relies on standard browser data URI decoding. Modern web browsers automatically respect EXIF orientation on raw JPEG data URIs (`image-orientation: from-image`).

---

## 4. Conclusion & Concrete Code Change Recommendations

### 4.1 Summary of Changes
1. Implement `raw_bytes_to_base64_data_uri(image_bytes: bytes, filename: Optional[str] = None) -> str` in `orientation.py`.
2. Update `extract_ocr` in `ocr.py` to populate `result["oriented_image_base64"]` with `raw_bytes_to_base64_data_uri(image_bytes)`.
3. Retain `image_to_base64_data_uri(pil_img)` in `orientation.py` for backward compatibility.
4. Pass `file.filename` from `router.py` into `process_ocr` -> `extract_ocr` as an optional parameter.
5. Update `test_orientation_adversarial.py` line 312 to assert `data:image/png;base64,` on PNG inputs and add byte-for-byte verbatim unit tests.

### 4.2 Exact Code Diffs for Worker Implementation

#### Change A: `Deepfake/eduverify-ai/backend/api/services/orientation.py`
Add `raw_bytes_to_base64_data_uri`:
```python
def raw_bytes_to_base64_data_uri(image_bytes: bytes, filename: Optional[str] = None) -> str:
    """
    Directly encodes the exact raw uploaded image bytes into a base64 Data URI,
    strictly preserving verbatim bytes without PIL decoding, EXIF transpositions,
    rotations, or lossy re-encoding.
    """
    import base64

    # Sniff MIME type from magic bytes
    mime_type = "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        mime_type = "image/png"
    elif image_bytes.startswith(b"RIFF") and len(image_bytes) >= 12 and image_bytes[8:12] == b"WEBP":
        mime_type = "image/webp"
    elif image_bytes.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    elif image_bytes.startswith((b"GIF87a", b"GIF89a")):
        mime_type = "image/gif"
    elif image_bytes.startswith(b"BM"):
        mime_type = "image/bmp"
    elif image_bytes.startswith((b"II*\x00", b"MM\x00*")):
        mime_type = "image/tiff"
    elif filename:
        ext = filename.lower().split(".")[-1]
        mime_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "tif": "image/tiff",
            "tiff": "image/tiff"
        }
        mime_type = mime_map.get(ext, "image/jpeg")

    b64_str = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{b64_str}"
```

#### Change B: `Deepfake/eduverify-ai/backend/api/services/ocr.py`
Import and use `raw_bytes_to_base64_data_uri`:
```python
# In imports (around line 263):
from .orientation import (
    normalize_image, 
    detect_stroke_is_sideways,
    score_reading_flow,
    apply_fine_deskew, 
    image_to_base64_data_uri,
    raw_bytes_to_base64_data_uri
)

# In extract_ocr signature:
def extract_ocr(image_bytes: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
...
    # Lines 271-274:
    raw_img = normalize_image(Image.open(io.BytesIO(image_bytes)))
    # Always preserve raw uploaded image bytes verbatim for display
    verbatim_data_uri = raw_bytes_to_base64_data_uri(image_bytes, filename=filename)
    result["oriented_image_base64"] = verbatim_data_uri
...
    # Line 355:
    result["oriented_image_base64"] = verbatim_data_uri

# In process_ocr:
def process_ocr(image_bytes: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
    data = extract_ocr(image_bytes, filename=filename)
    return {
        "status": "success",
        "module": "ocr",
        "data": data
    }
```

#### Change C: `Deepfake/eduverify-ai/backend/api/router.py`
Pass `file.filename` to `process_ocr`:
```python
# Around line 34:
ocr_result = process_ocr(file_bytes, filename=file.filename or "")
```

#### Change D: `Deepfake/eduverify-ai/backend/tests/test_orientation_adversarial.py`
Update line 312:
```python
# Before:
assert result["oriented_image_base64"].startswith("data:image/jpeg;base64,")

# After:
assert result["oriented_image_base64"].startswith("data:image/png;base64,")
```
Add new verbatim preservation verification tests:
```python
def test_extract_ocr_preserves_raw_bytes_verbatim_jpeg():
    """Verify that extract_ocr preserves raw JPEG bytes verbatim without re-encoding."""
    img = Image.new("RGB", (120, 160), color=(180, 200, 220))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    raw_bytes = buf.getvalue()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference", return_value="One Two Three Four Five Six Seven Eight Nine Ten"):
        res = extract_ocr(raw_bytes)
        uri = res["oriented_image_base64"]
        assert uri.startswith("data:image/jpeg;base64,")
        b64_data = uri.split(",", 1)[1]
        decoded = base64.b64decode(b64_data)
        assert decoded == raw_bytes, "Returned image bytes do not match raw uploaded bytes verbatim!"


def test_extract_ocr_preserves_raw_bytes_verbatim_png():
    """Verify that extract_ocr preserves raw PNG bytes verbatim without re-encoding to JPEG."""
    img = Image.new("RGBA", (80, 120), color=(50, 100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    with patch("api.services.ocr.load_qwen_model", return_value=None), \
         patch("api.services.ocr.evaluate_vlm_forensics", return_value={"vlm_verdict": "authentic"}), \
         patch("api.services.ocr._run_inference", return_value="Title: Engineering Physics Lab"):
        res = extract_ocr(raw_bytes)
        uri = res["oriented_image_base64"]
        assert uri.startswith("data:image/png;base64,")
        b64_data = uri.split(",", 1)[1]
        decoded = base64.b64decode(b64_data)
        assert decoded == raw_bytes, "Returned PNG bytes do not match raw uploaded bytes verbatim!"
```

---

## 5. Verification Method

### 5.1 Test Execution Command
Run the backend pytest suite:
```powershell
Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe -m pytest Deepfake/eduverify-ai/backend/tests -q
```
Expected result: All 114+ tests pass cleanly (100% pass rate).

### 5.2 Verbatim Byte Preservation Verification
Run the following verification script:
```powershell
Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe -c "
import base64
from api.services.orientation import raw_bytes_to_base64_data_uri

# Test PNG
with open(r'Deepfake/eduverify-ai/backend/evaluation/images/ai_generated/Handwritten Winter Essay.png', 'rb') as f:
    png_bytes = f.read()
uri_png = raw_bytes_to_base64_data_uri(png_bytes)
assert uri_png.startswith('data:image/png;base64,')
assert base64.b64decode(uri_png.split(',')[1]) == png_bytes
print('PNG verbatim check: PASS')

# Test JPEG
with open(r'Deepfake/eduverify-ai/backend/evaluation/images/real_scan/DocScanner 14-Oct-2026 01-56 AM_page_1.jpg', 'rb') as f:
    jpg_bytes = f.read()
uri_jpg = raw_bytes_to_base64_data_uri(jpg_bytes)
assert uri_jpg.startswith('data:image/jpeg;base64,')
assert base64.b64decode(uri_jpg.split(',')[1]) == jpg_bytes
print('JPEG verbatim check: PASS')
"
```

### 5.3 Invalidation Conditions
This analysis would be invalidated if:
1. The frontend requires server-side EXIF stripping or server-side downsampling due to browser memory limits. (Inspection of `DashboardPage.jsx` confirmed modern HTML `<img>` tag with CSS `maxHeight: 420px; objectFit: contain` handles raw data URIs seamlessly).
2. The user explicitly requested an automatic image rotation feature in the UI to rotate physical photographs. (Requirement R1 specifically commands: "preserve raw uploaded image bytes verbatim for the submitted document display so that uploaded images remain exactly in their uploaded orientation").
