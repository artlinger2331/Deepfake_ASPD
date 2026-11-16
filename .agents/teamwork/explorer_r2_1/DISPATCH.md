# Dispatch for Explorer R2-1: Backend Pipeline & Verbatim Raw Bytes Preservation
Target: Investigation of backend image handling in ocr.py, orientation.py, fusion.py, router.py.


## 2026-11-16T15:53:00Z
You are an Explorer subagent (role: Backend Pipeline Explorer).
Your task is to investigate the backend image processing pipeline to resolve the defect where upright uploaded images are rotated sideways during processing and frontend display, and identify how to strictly preserve raw uploaded image bytes verbatim for the submitted document display.

## Scope & References
- Read ORIGINAL_REQUEST.md at: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\ORIGINAL_REQUEST.md
- Read SCOPE.md at: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\orchestrator_1\SCOPE.md
- Working Directory: c:\Users\Pritam Mondal\Desktop\Hacktoberfest
- State Folder: c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_r2_1

## Technical Focus Areas (R1 & R2)
1. Investigate `Deepfake/eduverify-ai/backend/api/services/ocr.py`:
   - Trace how raw uploaded bytes enter `extract_ocr()`.
   - Look at lines 270-360: see how `oriented_image_base64` is currently computed (`image_to_base64_data_uri(raw_img)`). Note that `raw_img` was opened and translocated with `ImageOps.exif_transpose` and re-encoded to JPEG!
   - How can the backend preserve the exact raw uploaded image bytes verbatim (e.g., direct base64 encoding of `image_bytes` with proper MIME type data URI `data:image/...;base64,...`) so no PIL decode/re-encode or EXIF transformation alters the image for display?
2. Investigate `Deepfake/eduverify-ai/backend/api/services/orientation.py`:
   - Inspect stroke analysis, contour analysis, deskewing, and angle detection.
   - Are there 90° / 270° candidate rotations or deskewing calculations that produce false-positive sideways rotations on upright documents?
3. Investigate `Deepfake/eduverify-ai/backend/api/services/fusion.py` and `Deepfake/eduverify-ai/backend/api/router.py`:
   - Check if `fusion.py` or `router.py` does any transformation, rotation, deskewing, or caching of the uploaded image or `oriented_image_base64`.
   - Check `/analyze` endpoint in `router.py` and any report storage / retrieval endpoints.
4. Formulate concrete code change recommendations for Worker to implement.

## Rules & Constraints
- You are READ-ONLY. Do NOT modify source code files.
- Produce your full analysis and handoff report at: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_r2_1\handoff.md`.
- Update `progress.md` in your state folder.
- When finished, send a message to orchestrator with a summary and link to `handoff.md`.
