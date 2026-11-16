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
