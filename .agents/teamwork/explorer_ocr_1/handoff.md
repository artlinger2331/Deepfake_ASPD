# Handoff Report: EduVerify AI Backend Image Rotation Bug

## 1. Observation

### Affected Files and Exact Locations
- **`Deepfake/eduverify-ai/backend/api/services/ocr.py`**
  - Line 251: `def extract_ocr(image_bytes: bytes) -> Dict[str, Any]`
  - Line 271: `raw_img = normalize_image(Image.open(io.BytesIO(image_bytes)))`
  - Lines 282–292: `def evaluate_candidate(angle: int) -> Tuple[Image.Image, str, list, int]`
  - Lines 295–297: Candidate 0° evaluation: `img0, text0, words0, flow0 = evaluate_candidate(0)`
  - Line 307: `need_alternative_test = (w0_count < 8) or (flow0 < 0)`
  - Lines 310–333: Candidate 180° evaluation and selection logic:
    ```python
    is_significantly_better = (
        (w_alt >= 15 and w_alt > w0_count * 1.5 + 8) or
        (flow0 < 0 and flow_alt >= 5 and w_alt >= w0_count)
    )
    if is_significantly_better:
        best_angle = alt_angle
        best_img = img_alt
        best_text = text_alt
        best_words = words_alt
    ```
  - Line 352: `result["oriented_image_base64"] = image_to_base64_data_uri(best_img)`
  - Line 355: `vlm_forensics = evaluate_vlm_forensics(best_img)`
- **`Deepfake/eduverify-ai/backend/api/services/orientation.py`**
  - Lines 16–21: `normalize_image()` applies `ImageOps.exif_transpose(pil_img)`.
  - Lines 77–118: `score_reading_flow()`:
    ```python
    bottom_first_starters = [
        'it produces', 'it accepts', 'it has', 'and ', 'or ', 'that adds',
        'which is', 'then ', 'page:', 'date:', 'pg.', 'fig.'
    ]
    if any(first_line.startswith(k) for k in bottom_first_starters):
        score -= 10
    if re.search(r'\bpage\s*[:\.]?\s*\d+', first_line) or re.search(r'\bdate\s*[:\.]', first_line):
        score -= 15
        
    # Inverted document signals (heading/definition found at the very bottom line):
    if any(k in last_line for k in ['definition', 'half adder', 'title', 'experiment', 'chapter']):
        score -= 15
    ```
- **`Deepfake/eduverify-ai/backend/api/services/fusion.py`**
  - Line 280: `oriented_image_base64 = ocr_info.get("oriented_image_base64", "")`
  - Line 398: `"oriented_image_base64": oriented_image_base64` in `final_report`.
- **`Deepfake/eduverify-ai/backend/api/router.py`**
  - Lines 34, 56: Calls `process_ocr(file_bytes)` and forwards result to `fuse_results()`.
- **`Deepfake/eduverify-ai/src/pages/DashboardPage.jsx`**
  - Line 282: `{(report.oriented_image_base64 || previewImage) ? (`
  - Line 284: `<img src={report.oriented_image_base64 || previewImage} ... />`

### Empirical Test Output
Running `score_reading_flow()` on standard upright student assignment notes:
```python
# Sample 1 with standard top notebook header: "Date: 12/10/24"
Result: score_reading_flow = -20  (due to date: in bottom_first_starters and date regex)

# Sample 3 ending with technical sentence: "According to the definition, RAM is volatile."
Result: score_reading_flow = -10  (due to 'definition' in last_line)
```

---

## 2. Logic Chain

1. **EXIF Normalization**: When an image is uploaded, `ocr.py:271` calls `normalize_image(Image.open(io.BytesIO(image_bytes)))`. This produces `raw_img`, which is correctly oriented at 0° with EXIF tags applied.
2. **False Trigger of Orientation Search**:
   - `evaluate_candidate(0)` transcribes the upright document at 0° and calls `score_reading_flow(cleaned)`.
   - In standard student notebook pages, the top line often includes metadata such as `Date: ...` or `Page: ...`. In `orientation.py:105-112`, `score_reading_flow` penalizes `date:` and `page:` as negative indicators (`score -= 10` and `score -= 15`), yielding `flow0 = -20` or `-25`.
   - Similarly, if technical notes end with words like "definition" (e.g. "...definition of RAM"), line 116 penalizes it with `score -= 15`.
   - In `ocr.py:307`, `need_alternative_test = (w0_count < 8) or (flow0 < 0)`. Because `flow0 < 0`, this evaluates to `True`, triggering candidate angle search (180°) even when `w0_count` is large (e.g., 50+ words).
3. **Inversion to 180°**:
   - At 180°, candidate 180° is evaluated. If its transcribed first line starts with an uppercase word with <= 4 words, `flow_alt` gets `+5`.
   - In `ocr.py:321-323`, the comparison condition is:
     `(flow0 < 0 and flow_alt >= 5 and w_alt >= w0_count)`
   - Because `flow0 < 0`, `flow_alt >= 5`, and `w_alt >= w0_count` (due to identical document content or model hallucinations), `is_significantly_better` evaluates to `True`.
   - As a result, `best_angle = 180` and `best_img = img_alt` (180° rotated, upside down).
4. **Upside-Down Display in Frontend**:
   - `ocr.py:352` sets `result["oriented_image_base64"] = image_to_base64_data_uri(best_img)`.
   - `fusion.py` passes `oriented_image_base64` directly into `final_report["oriented_image_base64"]`.
   - `DashboardPage.jsx:284` receives `report.oriented_image_base64` and renders it in the "Submitted Document" preview, causing the upright document to appear rotated 180° (upside down).
5. **Conclusion**: Two coordinated fixes are required:
   - **Primary Display Requirement**: `result["oriented_image_base64"]` must ALWAYS be encoded directly from `raw_img` (0° with EXIF normalization only), completely decoupled from candidate rotation angle.
   - **Internal OCR Robustness**: Correct `score_reading_flow()` in `orientation.py` and tightening angle switching in `ocr.py` so that upright documents are never falsely switched to 180° internally.

---

## 3. Caveats

- **Upside-Down Uploads**: If a user genuinely uploads an upside-down document (180° inverted), OCR text extraction can still test 180° and extract the correct text if 0° failed (`w0_count < 8` and `w_alt` is substantially higher). However, per the specification, `oriented_image_base64` returned for display will remain the original uploaded image (at 0° with EXIF normalization).
- **Frontend Independence**: The frontend code (`DashboardPage.jsx`) must not be modified; it expects `oriented_image_base64` as a data URI string.
- **Python Environment**: On this Windows machine, the Python executable is located in `Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe` (in WindowsApps) and commands must be run with `BypassSandbox: true`.

---

## 4. Conclusion & Proposed Implementation

### Proposal 1: Fix `Deepfake/eduverify-ai/backend/api/services/ocr.py`
In `extract_ocr()`:
1. Immediately after normalizing `raw_img`, populate `result["oriented_image_base64"] = image_to_base64_data_uri(raw_img)`.
2. Restrict `need_alternative_test` so that it only runs if 0° truly failed to yield readable text (`w0_count < 8`). If 0° already produced >= 8 words, do not search alternative angles.
3. Remove the fragile clause `(flow0 < 0 and flow_alt >= 5 and w_alt >= w0_count)`. Require substantial word count dominance (`w_alt >= 12 and w_alt > w0_count * 2 + 5`) to justify rotating internally away from 0°.
4. Ensure `result["oriented_image_base64"]` is NEVER overwritten with `best_img`.

#### Code Diff for `ocr.py`:
```diff
--- a/Deepfake/eduverify-ai/backend/api/services/ocr.py
+++ b/Deepfake/eduverify-ai/backend/api/services/ocr.py
@@ -270,6 +270,8 @@ def extract_ocr(image_bytes: bytes) -> Dict[str, Any]:
         )
         
         raw_img = normalize_image(Image.open(io.BytesIO(image_bytes)))
+        # Always set oriented_image_base64 to the original uploaded image (0° with EXIF normalization only)
+        result["oriented_image_base64"] = image_to_base64_data_uri(raw_img)
         
         sys_msg = (
             "You are a master document OCR engine. Accurately transcribe all handwritten text, "
@@ -304,7 +306,7 @@ def extract_ocr(image_bytes: bytes) -> Dict[str, Any]:
         # Only search alternative orientations if 0° failed to read text:
         # If 0° already produces legitimate words (>= 8) and non-negative reading flow (>= 0),
         # the document is already straight and upright. Never rotate it away from 0°.
-        need_alternative_test = (w0_count < 8) or (flow0 < 0)
+        need_alternative_test = (w0_count < 8)
         
         if need_alternative_test:
             candidates_to_try = [180]
@@ -318,10 +320,10 @@ def extract_ocr(image_bytes: bytes) -> Dict[str, Any]:
                 print(f"[OCR] Candidate {alt_angle}°: {w_alt} words, flow score={flow_alt}. Top line: {text_alt.splitlines()[:1]}")
                 
                 # Require substantial superiority to rotate away from 0°
-                is_significantly_better = (
-                    (w_alt >= 15 and w_alt > w0_count * 1.5 + 8) or
-                    (flow0 < 0 and flow_alt >= 5 and w_alt >= w0_count)
-                )
+                is_significantly_better = (
+                    (w_alt >= 12 and w_alt > w0_count * 2 + 5) or
+                    (w0_count == 0 and w_alt >= 5)
+                )
                 if is_significantly_better:
                     print(f"[OCR] Selected {alt_angle}° as superior orientation (words={w_alt}, flow={flow_alt} vs 0° words={w0_count}, flow={flow0})")
                     best_angle = alt_angle
@@ -349,7 +351,7 @@ def extract_ocr(image_bytes: bytes) -> Dict[str, Any]:
         result["confidence_score"] = confidence_score
         result["word_count"] = word_count
         result["is_readable"] = word_count > 0
-        result["oriented_image_base64"] = image_to_base64_data_uri(best_img)
+        # oriented_image_base64 is already preserved as the 0° original image with EXIF normalization
         
         # Stage 3: Dedicated VLM Forensic Pass on upright document
         vlm_forensics = evaluate_vlm_forensics(best_img)
```

---

### Proposal 2: Fix `Deepfake/eduverify-ai/backend/api/services/orientation.py`
In `score_reading_flow()`:
1. Expand `title_starters` to include computer science and academic course topics (`'computer'`, `'generation'`, `'cpu'`, `'ram'`, `'rom'`, `'unit'`, `'lecture'`, `'assignment'`, `'question'`, `'q.'`, `'q1'`, `'section'`, `'intro'`, `'hardware'`, `'software'`, `'algorithm'`, `'system'`, `'date'`, `'page'`, `'pg'`).
2. Notebook headers (`date:`, `page:`) at the top line are positive indicators (`+10`), not bottom-first indicators. Remove them from `bottom_first_starters`.
3. Remove penalizing `'definition'` in `last_line`, which frequently appears in normal technical conclusions/summaries.

#### Code Diff for `orientation.py`:
```diff
--- a/Deepfake/eduverify-ai/backend/api/services/orientation.py
+++ b/Deepfake/eduverify-ai/backend/api/services/orientation.py
@@ -95,26 +95,28 @@ def score_reading_flow(text: str) -> int:
     # Positive signals for beginning of document:
     title_starters = [
         'half', 'title', 'experiment', 'chapter', 'topic', 'definition',
-        'note', 'when', 'if ', 'the ', 'a ', 'an ', 'in ', 'for ', 'to '
+        'note', 'when', 'if ', 'the ', 'a ', 'an ', 'in ', 'for ', 'to ',
+        'computer', 'generation', 'cpu', 'ram', 'rom', 'unit', 'lecture',
+        'assignment', 'question', 'q.', 'q1', 'section', 'intro', 'hardware',
+        'software', 'algorithm', 'system', 'date', 'page', 'pg'
     ]
     if any(lines[0].lower().startswith(k) for k in title_starters):
         score += 10
-    if len(lines[0].split()) <= 4 and lines[0][0].isupper():
+    if re.search(r'\b(date|page|pg)\s*[:\.]', first_line):
+        score += 10
+    if len(lines[0].split()) <= 6 and (lines[0][0].isupper() or lines[0][0].isdigit()):
         score += 5
         
     # Negative signals (bottom-first indicators at top of page):
     bottom_first_starters = [
         'it produces', 'it accepts', 'it has', 'and ', 'or ', 'that adds',
-        'which is', 'then ', 'page:', 'date:', 'pg.', 'fig.'
+        'which is', 'therefore '
     ]
     if any(first_line.startswith(k) for k in bottom_first_starters):
         score -= 10
-    if re.search(r'\bpage\s*[:\.]?\s*\d+', first_line) or re.search(r'\bdate\s*[:\.]', first_line):
-        score -= 15
         
     # Inverted document signals (heading/definition found at the very bottom line):
-    if any(k in last_line for k in ['definition', 'half adder', 'title', 'experiment', 'chapter']):
+    if len(last_line.split()) <= 4 and any(last_line.startswith(k) for k in ['title:', 'experiment:', 'chapter:']):
         score -= 15
         
     return score
```

---

## 5. Verification Method

### Test Suite Execution
Run the full existing test suite to ensure all 33 tests pass without regression:
```powershell
& "Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe" -m pytest Deepfake\eduverify-ai\backend\tests -q
```
Expected result: `33 passed`.

### Reading Flow Score Verification
Verify that technical document headers and definitions score positively:
```powershell
& "Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe" -c "
import sys; sys.path.insert(0, r'Deepfake\eduverify-ai\backend')
from api.services.orientation import score_reading_flow

assert score_reading_flow('''Date: 12/10/24\nComputer Generations\n1st Gen vacuum tubes''') >= 15
assert score_reading_flow('''Generations of Computer\n1st Gen computers\nRAM memory''') >= 10
assert score_reading_flow('''CPU Architecture\nALU and CU\nBy definition, RAM is volatile''') >= 10
print('Reading flow verification passed!')
"
```

### Image Orientation Invariant Verification
Ensure `extract_ocr(image_bytes)["oriented_image_base64"]` equals `image_to_base64_data_uri(raw_img)` (0° orientation):
- Inspect `result["oriented_image_base64"]` against a known base64 encoding of the test image.
- Verify that regardless of any candidate evaluation, the preview image returned to the frontend remains upright.
