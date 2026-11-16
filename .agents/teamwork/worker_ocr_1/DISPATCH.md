# Dispatch for Worker 1 (OCR Image Rotation Bug Fix)

Please read:
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\ORIGINAL_REQUEST.md`
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\orchestrator_1\SCOPE.md`
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_ocr_1\handoff.md`
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_ocr_2\handoff.md`
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_ocr_3\handoff.md`

Your state folder is: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\worker_ocr_1\`
Write your findings and handoff report to: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\worker_ocr_1\handoff.md`.

## Exclusive Write Ownership
You exclusively own and may edit:
- `Deepfake/eduverify-ai/backend/api/services/ocr.py`
- `Deepfake/eduverify-ai/backend/api/services/orientation.py`
- `Deepfake/eduverify-ai/backend/tests/test_orientation.py`
Do NOT modify frontend files or unrelated backend files.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Tasks
1. Implement the fix in `ocr.py`:
   - Set `result["oriented_image_base64"] = image_to_base64_data_uri(raw_img)` so the returned image is ALWAYS the original uploaded image (0° with EXIF normalization only).
   - Guard alternative rotation search in `extract_ocr()`: if 0° produces sufficient words (`w0_count >= 8`), do not evaluate or rotate candidates merely due to heuristic reading flow score.
2. Implement the fix in `orientation.py`:
   - In `score_reading_flow()`: remove false penalties on `Date:` and `Page:` headers and avoid false penalties on bottom definitions.
3. Add unit tests in `Deepfake/eduverify-ai/backend/tests/test_orientation.py` testing `normalize_image`, `image_to_base64_data_uri`, `score_reading_flow`, and confirming `extract_ocr` returns 0° `oriented_image_base64`.
4. Run all pytest tests using:
   `& 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe' -m pytest 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\tests' -q` (use `BypassSandbox: true`).
   Verify all 33 existing tests pass + new tests pass.
5. Check backend server running status (port 8000), restart if running, or verify it can start cleanly.
6. Write full details of changes and test outputs to your `handoff.md` and message orchestrator via `send_message`.


## 2026-11-16T14:02:34Z
You are Worker 1 on the EduVerify AI team.
Read your instructions in:
- ORIGINAL_REQUEST.md: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\ORIGINAL_REQUEST.md`
- SCOPE.md: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\orchestrator_1\SCOPE.md`
- DISPATCH.md: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\worker_ocr_1\DISPATCH.md`
- Explorer handoffs:
  - `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_ocr_1\handoff.md`
  - `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_ocr_2\handoff.md`
  - `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_ocr_3\handoff.md`

Your state folder is: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\worker_ocr_1\`
Write your completion report to `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\worker_ocr_1\handoff.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Exclusive write ownership:
- `Deepfake/eduverify-ai/backend/api/services/ocr.py`
- `Deepfake/eduverify-ai/backend/api/services/orientation.py`
- `Deepfake/eduverify-ai/backend/tests/test_orientation.py`

Remember to run tests with `BypassSandbox: true` using `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe`.
Communicate back to orchestrator via send_message when done.


## 2026-11-16T14:10:02Z
**Context**: Resume execution
**Content**: The user has confirmed to continue. Please resume your execution and continue the fix, testing, and verification per your instructions.
**Action**: Proceed with implementing changes in `orientation.py` and `ocr.py`, adding `tests/test_orientation.py`, verifying all tests pass, checking the backend server, and writing `handoff.md`.
