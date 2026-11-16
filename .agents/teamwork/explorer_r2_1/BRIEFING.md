# BRIEFING — 2026-11-16T16:08:30Z

## Mission
Investigate the backend image processing pipeline (`ocr.py`, `orientation.py`, `fusion.py`, `router.py`) to resolve upright uploaded images being rotated sideways during processing and frontend display, and identify how to strictly preserve raw uploaded image bytes verbatim for display.

## 🔒 My Identity
- Archetype: Explorer
- Roles: Backend Pipeline Explorer
- Working directory: c:\Users\Pritam Mondal\Desktop\Hacktoberfest
- State folder: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_r2_1
- Original parent: 5714076c-7510-482f-91f0-ab2972da0d15
- Milestone: Investigation of backend image rotation and verbatim raw byte preservation

## 🔒 Key Constraints
- Read-only investigation — do NOT implement / modify source code
- Produce full analysis and handoff report at handoff.md in state folder
- Update progress.md regularly
- Send message to parent orchestrator upon completion

## Current Parent
- Conversation ID: 5714076c-7510-482f-91f0-ab2972da0d15
- Updated: 2026-11-16T16:08:30Z

## Investigation State
- **Explored paths**:
  - `Deepfake/eduverify-ai/backend/api/services/ocr.py`
  - `Deepfake/eduverify-ai/backend/api/services/orientation.py`
  - `Deepfake/eduverify-ai/backend/api/services/fusion.py`
  - `Deepfake/eduverify-ai/backend/api/router.py`
  - `Deepfake/eduverify-ai/backend/tests/test_orientation.py`
  - `Deepfake/eduverify-ai/backend/tests/test_orientation_adversarial.py`
  - `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx`
  - `Deepfake/eduverify-ai/src/pages/UploadPage.jsx`
- **Key findings**:
  1. `oriented_image_base64` was generated via `image_to_base64_data_uri(raw_img)` where `raw_img` was opened and translocated with `ImageOps.exif_transpose` and re-encoded to JPEG quality 85. This caused format conversion (e.g. PNG to lossy JPEG), EXIF strip/distortion, and broke byte-for-byte fidelity.
  2. `detect_stroke_is_sideways` in `orientation.py` produces severe false positives on lined/ruled notebook pages (such as EV-35D17C96) because horizontal rules generate dominant vertical Sobel gradients (`sobely` >> `sobelx`), lowering the ratio to 0.266 (< 0.90) and falsely declaring `is_sideways = True`.
  3. Internal candidate search in `ocr.py`: when word count at 0° is < 5, candidate orientations [90, 270] are tested, and previously `oriented_image_base64` was set to `best_img`.
  4. Neither `fusion.py` nor `router.py` alters images; `fusion.py` passes `ocr_data['data']['oriented_image_base64']` straight through, and frontend `DashboardPage.jsx` renders `report.oriented_image_base64 || previewImage`.
  5. The definitive solution for verbatim preservation is implementing `raw_bytes_to_base64_data_uri(image_bytes)` which inspects magic bytes (JPEG, PNG, WebP, GIF, BMP, TIFF) and directly base64 encodes the exact uploaded bytes without PIL decode or re-encoding.
- **Unexplored areas**: None for backend pipeline scope.

## Key Decisions Made
- Formulate concrete recommendations for Worker:
  - Add `raw_bytes_to_base64_data_uri` in `orientation.py`.
  - Use `raw_bytes_to_base64_data_uri(image_bytes)` in `ocr.py` for `oriented_image_base64`.
  - Pass optional `filename` from `router.py` through `process_ocr` to `extract_ocr`.
  - Update `test_orientation_adversarial.py` line 312 to expect `data:image/png;base64,` for PNG input.
  - Add unit tests verifying byte-for-byte equality `base64.b64decode(uri.split(',')[1]) == original_bytes`.

## Artifact Index
- `.agents/teamwork/explorer_r2_1/DISPATCH.md` — Dispatch record
- `.agents/teamwork/explorer_r2_1/BRIEFING.md` — Working memory and context
- `.agents/teamwork/explorer_r2_1/progress.md` — Heartbeat and status
- `.agents/teamwork/explorer_r2_1/handoff.md` — Final handoff report
