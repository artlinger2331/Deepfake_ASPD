# Dispatch for Challenger 1 (Image Orientation Empirical Verification)

Please read:
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\ORIGINAL_REQUEST.md`
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\orchestrator_1\SCOPE.md`
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\worker_ocr_1\handoff.md`

Your state folder is: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\challenger_ocr_1\`
Write your findings and verdict to: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\challenger_ocr_1\handoff.md`.

## Task
1. Adversarially stress test the fix by writing and running test scripts:
   - Python executable: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe` (with `BypassSandbox: true`).
   - Create test images with various aspect ratios, EXIF orientation tags (e.g. EXIF 1, 3, 6, 8), color modes (RGB, RGBA, L).
   - Test that `extract_ocr` and `normalize_image` + `image_to_base64_data_uri` ALWAYS produce the 0° image data URI.
   - Verify that simulated candidate tests at 180° / 90° / 270° NEVER cause `oriented_image_base64` to return a rotated image.
2. Run pytest suite:
   `& 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe' -m pytest 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\tests' -q` (use `BypassSandbox: true`).
3. Deliver your empirical verdict: `CONFIRM CORRECTNESS` or `REJECT` in your `handoff.md`.
