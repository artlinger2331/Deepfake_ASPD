# Scope: EduVerify AI Document Image Rotation Defect Resolution

## Architecture
- Backend: FastAPI application located at `Deepfake/eduverify-ai/backend`
- Frontend: React application located at `Deepfake/eduverify-ai/src` (served at `localhost:5173`)
- Services & Modules:
  - `backend/api/services/ocr.py`: OCR extraction, candidate orientation testing, response formatting (`oriented_image_base64`)
  - `backend/api/services/orientation.py`: Stroke and reading flow heuristics, orientation detection, verbatim raw bytes encoding
  - `backend/api/services/fusion.py`: Fusion and pass-through of `oriented_image_base64`
  - `backend/api/router.py`: `/analyze` endpoint (forwarding filename to OCR)
  - `src/pages/DashboardPage.jsx`: Submitted Document display (`displayImage = previewImage || report.oriented_image_base64 || report.document_image`)
  - `src/pages/UploadPage.jsx`: Quota-safe `sessionStorage` handling and upload submission
  - Backend Tests: `Deepfake/eduverify-ai/backend/tests/`

## Feature Inventory & Requirements
| # | Requirement | Description | Status |
|---|-------------|-------------|--------|
| R1 | Verbatim Preservation of Uploaded Image for Display | The image displayed in the frontend "Submitted Document" panel (`oriented_image_base64` and preview state) must preserve the raw uploaded image bytes verbatim without applying unwanted rotations, EXIF transpositions, or transformations that alter the user's uploaded orientation | DONE |
| R2 | Backend Orientation & OCR Pipeline Defect Resolution | Investigate and resolve unwanted rotation across the backend pipeline (`ocr.py`, `orientation.py`, `fusion.py`, `router.py`), ensuring that internal orientation detection or deskewing does not corrupt upright document orientation or cause false-positive 90-degree sideways rotations | DONE |
| R3 | Frontend Display and Session State Consistency | Ensure the frontend (`DashboardPage.jsx`, `UploadPage.jsx`) consistently displays the submitted document in its true uploaded orientation across analysis results, page navigations, and direct report lookups (`/analysis/:id`) | DONE |
| R4 | Verification and Regression Testing | Ensure all existing backend pytest tests pass cleanly and verification succeeds against categorized test images under `Deepfake/eduverify-ai/backend/evaluation/images/` and sample handwritten notebook image from report EV-35D17C96 | DONE |

## Code Layout & Exclusive Write Boundaries for Worker R2-1
- `Deepfake/eduverify-ai/backend/api/services/orientation.py`: implement `raw_bytes_to_base64_data_uri`
- `Deepfake/eduverify-ai/backend/api/services/ocr.py`: use `raw_bytes_to_base64_data_uri` for `oriented_image_base64` and accept `filename` parameter
- `Deepfake/eduverify-ai/backend/api/router.py`: pass `file.filename` to `process_ocr`
- `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx`: prioritize `previewImage || report.oriented_image_base64 || report.document_image`
- `Deepfake/eduverify-ai/src/pages/UploadPage.jsx`: wrap `sessionStorage` in `try...catch`
- `Deepfake/eduverify-ai/backend/tests/test_orientation.py`: add tests for exact bit-for-bit byte preservation and EV-35D17C96 sample
- `Deepfake/eduverify-ai/backend/tests/test_orientation_adversarial.py`: update line 312 assertion for PNG MIME prefix
