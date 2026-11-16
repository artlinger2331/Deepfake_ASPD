# Dispatch for Challenger 2 (Reading Flow & Server Verification)

Please read:
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\ORIGINAL_REQUEST.md`
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\orchestrator_1\SCOPE.md`
- `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\worker_ocr_1\handoff.md`

Your state folder is: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\challenger_ocr_2\`
Write your findings and verdict to: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\challenger_ocr_2\handoff.md`.

## Task
1. Adversarially test `score_reading_flow` in `orientation.py`:
   - Python executable: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe` (with `BypassSandbox: true`).
   - Test a wide battery of upright documents (computer science notes, handwritten lab experiments, assignments with `Date:`, `Page:`, `Roll No:`, math formulas, definitions at bottom). Ensure all score non-negative (`score >= 0`).
   - Test truly inverted documents (bottom-first sentences, top lines like "which is the output", definitions on the first line) to verify they still trigger negative scores for genuine inverted text.
2. Verify backend server status:
   - Check if the backend is running on `localhost:8000`.
   - If not running or needs restart, test that it boots cleanly and `/docs` or `/health` endpoint responds.
3. Run pytest suite:
   `& 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe' -m pytest 'c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\tests' -q` (use `BypassSandbox: true`).
4. Deliver your empirical verdict: `CONFIRM CORRECTNESS` or `REJECT` in your `handoff.md`.


## 2026-11-16T14:14:17Z
You are Challenger 2 on the EduVerify AI team.
Read your instructions in:
- ORIGINAL_REQUEST.md: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\ORIGINAL_REQUEST.md`
- SCOPE.md: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\orchestrator_1\SCOPE.md`
- DISPATCH.md: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\challenger_ocr_2\DISPATCH.md`
- Worker handoff: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\worker_ocr_1\handoff.md`

Your state folder is: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\challenger_ocr_2\`
Write your findings and verdict (CONFIRM CORRECTNESS or REJECT) to `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\challenger_ocr_2\handoff.md`.
Remember to run tests and commands with `BypassSandbox: true` using `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe`.
Communicate back to orchestrator via send_message when done.
