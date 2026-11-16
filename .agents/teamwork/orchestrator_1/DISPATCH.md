## 2026-11-16T13:51:00Z
Fix the image rotation bug in the EduVerify AI backend. The model is rotating uploaded images even when they are already straight/upright. The user uploaded a straight image and the "Submitted Document" preview in the frontend shows it rotated 180° (upside down).

## Project Context
- Workspace: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai`
- Backend: `Deepfake/eduverify-ai/backend` (FastAPI)
- Frontend: React at `localhost:5173`
- Backend runs on `localhost:8000`
- Python venv: `Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe`
- The backend must be run with `BypassSandbox: true` because the Python binary is in WindowsApps.

## The Bug
When a user uploads a straight, upright handwritten document image through the frontend, the backend rotates it (often 180°) before returning it. The rotated image appears upside down in the "Submitted Document" panel on the analysis results page.

## Root Cause Location
The rotation happens in `backend/api/services/ocr.py` in the `extract_ocr()` function (around line 270+). The function:
1. Reads the image
2. Tries to detect if it's sideways or inverted using stroke analysis and reading flow heuristics
3. Evaluates OCR at multiple rotation angles (0°, 180°, and sometimes 90°/270°)
4. Picks the "best" angle based on word count and reading flow score
5. Returns the rotated image as `oriented_image_base64` which the frontend displays

The problem is that the reading flow heuristic (`score_reading_flow()` in `orientation.py`) and the comparison logic incorrectly prefer 180° over 0° for many normal upright documents, especially those with technical content (Computer Generations, CPU, RAM, etc.).

## Required Fix
The `oriented_image_base64` returned to the frontend should be the ORIGINAL uploaded image (at 0° with EXIF normalization only). The OCR text extraction can internally try different rotations to get the best transcription, but the IMAGE returned to the frontend must always be the original orientation the user uploaded.

Key files to examine and fix:
- `backend/api/services/ocr.py` - the `extract_ocr()` function, specifically `oriented_image_base64` output
- `backend/api/services/orientation.py` - the helper functions
- `backend/api/router.py` - the `/analyze` endpoint

## Important Constraints
- All 33 existing pytest tests must continue to pass: `python -m pytest Deepfake\eduverify-ai\backend\tests -q`
- The OCR transcription quality should not degrade - internally the OCR engine can still try rotations to get the best text, but the displayed image must stay upright
- The `oriented_image_base64` field in the API response is what the frontend uses for the "Submitted Document" display
- Do NOT change the frontend code - fix this in the backend only
- After fixing, restart the backend server and verify the fix works


## 2026-11-16T14:09:50Z
The user has confirmed to continue. Please resume your execution and continue the fix, testing, and verification.


## 2026-11-16T15:50:29Z
Fix the document image rotation defect where upright uploaded images are rotated sideways during processing and frontend display. Strictly preserve raw uploaded image bytes verbatim for the submitted document display so that uploaded images remain exactly in their uploaded orientation.

Integrity mode: development

## Verification Resources
- Backend pytest suite: `python -m pytest Deepfake/eduverify-ai/backend/tests -q`
- Categorized test images in the evaluation directory: `Deepfake/eduverify-ai/backend/evaluation/images/`
- User sample artifact from report EV-35D17C96: `C:/Users/Pritam Mondal/.gemini/antigravity/brain/8a979481-0fb5-468e-8f32-d21e217e7787/.user_uploaded/media_1794843355919_2564ee42.jpg`

## Requirements

### R1. Verbatim Preservation of Uploaded Image for Display
The image displayed in the frontend "Submitted Document" panel (`oriented_image_base64` and preview state) must preserve the raw uploaded image bytes verbatim without applying unwanted rotations, EXIF transpositions, or transformations that alter the user's uploaded orientation.

### R2. Backend Orientation & OCR Pipeline Defect Resolution
Investigate and resolve unwanted rotation across the backend pipeline (including `backend/api/services/ocr.py`, `backend/api/services/orientation.py`, `backend/api/services/fusion.py`, and `backend/api/router.py`), ensuring that internal orientation detection or deskewing does not corrupt upright document orientation or cause false-positive 90-degree sideways rotations.

### R3. Frontend Display and Session State Consistency
Ensure the frontend (`src/pages/DashboardPage.jsx`, `src/pages/UploadPage.jsx`) consistently displays the submitted document in its true uploaded orientation across analysis results, page navigations, and direct report lookups (such as `/analysis/:id`).

### R4. Verification and Regression Testing
Ensure that all existing backend pytest tests pass cleanly and that verification succeeds against the categorized test images under `Deepfake/eduverify-ai/backend/evaluation/images/` and the sample handwritten notebook image from report EV-35D17C96.

## Acceptance Criteria

### Display Orientation Fidelity
- [ ] Uploading an upright document (such as the handwritten spiral notebook sample from report EV-35D17C96) displays the document upright in the "Submitted Document" panel on the frontend, with no 90-degree sideways rotation.
- [ ] `oriented_image_base64` in the analysis report payload preserves the raw uploaded document orientation verbatim.

### Pipeline and Test Suite Integrity
- [ ] All tests in `Deepfake/eduverify-ai/backend/tests` run and pass with zero failures: `python -m pytest Deepfake/eduverify-ai/backend/tests -q`.
- [ ] Testing across sample images in `Deepfake/eduverify-ai/backend/evaluation/images/` demonstrates no unwanted rotation on upright documents.
