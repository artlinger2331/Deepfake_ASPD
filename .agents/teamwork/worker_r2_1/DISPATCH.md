## 2026-11-16T16:15:36Z
You are a Worker subagent (role: Pipeline Worker).
Your task is to implement the solution to resolve the document image rotation defect where upright uploaded images are rotated sideways during processing and frontend display, and strictly preserve raw uploaded image bytes verbatim for display.

## Scope & References
- Read ORIGINAL_REQUEST.md at: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\ORIGINAL_REQUEST.md
- Read SCOPE.md at: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\orchestrator_1\SCOPE.md
- Read Explorer R2-1 findings at: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_r2_1\handoff.md
- Read Explorer R2-2 findings at: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_r2_2\handoff.md
- Read Explorer R2-3 findings at: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_r2_3\handoff.md
- Working Directory: c:\Users\Pritam Mondal\Desktop\Hacktoberfest
- State Folder: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\worker_r2_1

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Exclusive Write Boundaries
You own and may modify ONLY these files:
- `Deepfake/eduverify-ai/backend/api/services/orientation.py`
- `Deepfake/eduverify-ai/backend/api/services/ocr.py`
- `Deepfake/eduverify-ai/backend/api/router.py`
- `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx`
- `Deepfake/eduverify-ai/src/pages/UploadPage.jsx`
- `Deepfake/eduverify-ai/backend/tests/test_orientation.py`
- `Deepfake/eduverify-ai/backend/tests/test_orientation_adversarial.py`

## Implementation Tasks

### 1. `Deepfake/eduverify-ai/backend/api/services/orientation.py`
Add `raw_bytes_to_base64_data_uri(image_bytes: bytes, filename: Optional[str] = None) -> str`:
- Detect MIME type via magic bytes:
  - `b"\x89PNG\r\n\x1a\n"` -> `image/png`
  - `b"\xff\xd8\xff"` -> `image/jpeg`
  - `b"RIFF"` and `image_bytes[8:12] == b"WEBP"` -> `image/webp`
  - `b"GIF87a"` or `b"GIF89a"` -> `image/gif`
  - `b"BM"` -> `image/bmp`
  - If filename provided, map `.png`, `.jpg`/`.jpeg`, `.webp`, `.bmp`
  - Default: `image/jpeg`
- Base64 encode `image_bytes` directly into `f"data:{mime};base64,{b64_str}"`.
- Ensure it preserves the raw bytes 100% bit-for-bit without PIL decode/re-encode or EXIF manipulation.

### 2. `Deepfake/eduverify-ai/backend/api/services/ocr.py`
- Import `raw_bytes_to_base64_data_uri` from `.orientation`.
- In `extract_ocr(image_bytes: bytes, filename: Optional[str] = None)`:
  - Accept `filename: Optional[str] = None`.
  - Set `result["oriented_image_base64"] = raw_bytes_to_base64_data_uri(image_bytes, filename=filename)` at lines 273 and 355.
  - Ensure `oriented_image_base64` is NEVER overwritten with any rotated candidate image or translocated image.
- In `process_ocr(image_bytes: bytes, filename: Optional[str] = None)`:
  - Pass `filename` to `extract_ocr(image_bytes, filename=filename)`.

### 3. `Deepfake/eduverify-ai/backend/api/router.py`
- In `analyze_image(file: UploadFile = File(...))` line 34:
  - Pass `filename=file.filename` to `process_ocr(file_bytes, filename=file.filename)`.

### 4. `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx`
- Around line 282-288:
  Update image resolution to prioritize the client-side upload preview when available:
  `const displayImage = previewImage || report.oriented_image_base64 || report.document_image;`
  and set `src={displayImage}` in the `<img>` element.

### 5. `Deepfake/eduverify-ai/src/pages/UploadPage.jsx`
- Around lines 87-92:
  Wrap `sessionStorage.setItem` calls in a `try...catch` block to handle potential `QuotaExceededError` on large image payloads.

### 6. Tests in `Deepfake/eduverify-ai/backend/tests/`
- In `test_orientation_adversarial.py` line 312:
  Update assertion: since `png_bytes` is passed, with verbatim preservation the Data URI starts with `data:image/png;base64,`. Update assertion to:
  `assert result["oriented_image_base64"].startswith("data:image/")` and verify `base64.b64decode(b64_data) == png_bytes`.
- In `test_orientation.py`:
  Add comprehensive tests for verbatim byte preservation:
  - `test_oriented_image_base64_exact_byte_verbatim_jpeg()`
  - `test_oriented_image_base64_exact_byte_verbatim_png()`
  - `test_ev_35d17c96_sample_verbatim_and_not_rotated()` (using artifact `C:/Users/Pritam Mondal/.gemini/antigravity/brain/8a979481-0fb5-468e-8f32-d21e217e7787/.user_uploaded/media_1794843355919_2564ee42.jpg`, verifying exact byte equality and size (1024, 576)).
  - `test_evaluation_images_verbatim_preservation()` across evaluation images.

### 7. Verification & Build
- Run all backend tests:
  `& "Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe" -m pytest Deepfake/eduverify-ai/backend/tests -q` (with `BypassSandbox: true`). All tests must pass cleanly.
- Run frontend build:
  In `Deepfake/eduverify-ai`, run `npm run build` (with `BypassSandbox: true` if needed) to ensure Vite build succeeds with zero errors.

## Deliverables
- Write `handoff.md` in your state folder with complete implementation details, files modified, and test outputs.
- Send a message to orchestrator upon completion.
