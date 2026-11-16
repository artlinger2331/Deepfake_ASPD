# Handoff Report — Orientation Heuristics & Router Deep Dive (Explorer 2)

## 1. Observation

### 1.1 `Deepfake/eduverify-ai/backend/api/services/orientation.py`
In `orientation.py`, the following functions govern orientation and reading flow:

1. **`normalize_image(pil_img: Image.Image) -> Image.Image`** (lines 16-21):
   ```python
   def normalize_image(pil_img: Image.Image) -> Image.Image:
       """Applies EXIF rotation normalization and converts to RGB."""
       img = ImageOps.exif_transpose(pil_img)
       if img.mode != "RGB":
           img = img.convert("RGB")
       return img
   ```
   Directly normalizes EXIF orientation metadata while preserving the original uploaded pixel coordinates (0° orientation).

2. **`score_reading_flow(text: str) -> int`** (lines 77-118):
   ```python
   def score_reading_flow(text: str) -> int:
       lines = [l.strip() for l in text.splitlines() if l.strip()]
       if not lines:
           return -100
           
       score = 0
       first_line = lines[0].lower()
       last_line = lines[-1].lower()
       
       # Positive signals for beginning of document:
       title_starters = [
           'half', 'title', 'experiment', 'chapter', 'topic', 'definition',
           'note', 'when', 'if ', 'the ', 'a ', 'an ', 'in ', 'for ', 'to '
       ]
       if any(lines[0].lower().startswith(k) for k in title_starters):
           score += 10
       if len(lines[0].split()) <= 4 and lines[0][0].isupper():
           score += 5
           
       # Negative signals (bottom-first indicators at top of page):
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
           
       return score
   ```
   **Empirical Python Test Results on Real Document Texts:**
   Executing `score_reading_flow()` via Python:
   - Upright student note with date header and definition at the bottom (`Date: 12/10/2026 ... Definition: CPU processes instructions.`):
     **Result: `-35`**
   - Upright technical document starting with `Computer Generations` and ending with `Definition of CPU: ...`:
     **Result: `-10`**
   - Candidate 180° inverted transcription of the same text (where definition becomes line 1):
     **Result: `+15`**
   - Overfitted sample `evaluation/transcriptions/half_adder_notes.txt`:
     Upright: `+15`, Inverted: `-25`.

3. **`detect_stroke_is_sideways(pil_img: Image.Image) -> bool`** (lines 45-75):
   Sobel edge angle ratio computation (`ratio = np.mean(angles < 30) / (np.mean(angles > 60) + 1e-6)`).
   Observation: Although imported in `ocr.py:265`, `detect_stroke_is_sideways` is **never actually invoked** anywhere in `ocr.py` or the rest of the backend codebase.

4. **`image_to_base64_data_uri(pil_img: Image.Image) -> str`** (lines 164-171):
   Converts PIL image to JPEG base64 Data URI (`data:image/jpeg;base64,...`).

### 1.2 `Deepfake/eduverify-ai/backend/api/services/ocr.py`
In `ocr.py:271-353`:
```python
raw_img = normalize_image(Image.open(io.BytesIO(image_bytes)))
...
img0, text0, words0, flow0 = evaluate_candidate(0)
w0_count = len(words0)
...
need_alternative_test = (w0_count < 8) or (flow0 < 0)

if need_alternative_test:
    candidates_to_try = [180]
    if w0_count < 5:
        candidates_to_try.extend([90, 270])
        
    for alt_angle in candidates_to_try:
        img_alt, text_alt, words_alt, flow_alt = evaluate_candidate(alt_angle)
        w_alt = len(words_alt)
        ...
        is_significantly_better = (
            (w_alt >= 15 and w_alt > w0_count * 1.5 + 8) or
            (flow0 < 0 and flow_alt >= 5 and w_alt >= w0_count)
        )
        if is_significantly_better:
            best_angle = alt_angle
            best_img = img_alt
            best_text = text_alt
            best_words = words_alt
            break
...
result["oriented_image_base64"] = image_to_base64_data_uri(best_img)
```
- Line 307: `need_alternative_test = (w0_count < 8) or (flow0 < 0)`.
- Line 322: `(flow0 < 0 and flow_alt >= 5 and w_alt >= w0_count)` triggers rotation swap to 180°.
- Line 352: `result["oriented_image_base64"] = image_to_base64_data_uri(best_img)` exports `best_img` (which is upside down at 180°).

### 1.3 `Deepfake/eduverify-ai/backend/api/router.py`
In `router.py:12-61`:
```python
@router.post("/analyze", response_model=Dict[str, Any])
def analyze_image(file: UploadFile = File(...)):
    ...
    file_bytes = file.file.read()
    ...
    ocr_result = process_ocr(file_bytes)
    ...
    final_report = fuse_results(vision_result, ocr_result, handwriting_result, metadata_result)
    return final_report
```
- `router.py` does not touch, modify, or inspect `oriented_image_base64`.
- It delegates directly to `process_ocr()` and `fuse_results()`.
- There are no other endpoints in `router.py` or other backend routes referencing `oriented_image_base64`.

### 1.4 `Deepfake/eduverify-ai/backend/api/services/fusion.py`
In `fusion.py`:
- Line 280: `oriented_image_base64 = ocr_info.get("oriented_image_base64", "")`
- Line 398: `"oriented_image_base64": oriented_image_base64,`
Pans `oriented_image_base64` directly into the returned payload from `ocr_data`.

### 1.5 Frontend Consumption: `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx`
In `DashboardPage.jsx:282-288`:
```jsx
<div className="analyzed-image-wrapper">
  {(report.oriented_image_base64 || previewImage) ? (
    <img 
      src={report.oriented_image_base64 || previewImage} 
      alt="Student Assignment Preview" 
      className="analyzed-image"
      style={{ width: '100%', maxHeight: '420px', objectFit: 'contain', borderRadius: '8px' }}
    />
  ) : ( ... )}
</div>
```
The "Submitted Document" preview renders `report.oriented_image_base64` whenever present, overriding client `previewImage`.

### 1.6 Backend Test Suite Status
Running `& "Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe" -m pytest Deepfake\eduverify-ai\backend\tests -q`:
```
33 passed in 0.82s
```
- `backend/tests/test_scoring.py:309, 347, 348` tests that `fuse_results` preserves `oriented_image_base64` provided in mock data.
- Neither `test_scoring.py` nor `test_evaluation.py` calls `extract_ocr` or `process_ocr` directly.

---

## 2. Logic Chain

1. **Premise (User Requirement)**:
   The user reported that uploaded upright images are displayed upside down (180°) in the frontend "Submitted Document" preview. The user requires that `oriented_image_base64` returned to the frontend must always be the original uploaded image (0° with EXIF normalization only).
2. **Observation -> Root Cause of Display Flipping**:
   In `ocr.py:352`, the API assigns `result["oriented_image_base64"] = image_to_base64_data_uri(best_img)`. When candidate 180° is selected as `best_angle`, `best_img` is the 180°-rotated PIL image. Passing this to `image_to_base64_data_uri` encodes the upside-down image, which `DashboardPage.jsx:284` displays.
3. **Observation -> Root Cause of Reading Flow Heuristic Inversion**:
   In `orientation.py:score_reading_flow()`:
   - Lines 105-112: Notebook headers containing `Date:` or `Page:` (standard student notebook headers) are mistakenly penalized as "bottom-first indicators" (`score -= 10` and `score -= 15`), penalizing upright documents by -25 points.
   - Line 115: If any definition exists near the end of notes (e.g. `Definition of CPU`), `score -= 15`.
   - Lines 95-102: Upright titles like `Computer Generations` or `CPU Architecture` are omitted from `title_starters`, yielding 0 positive points.
   - Consequence: An upright document scores `flow0 = -35`.
4. **Observation -> Cascade into OCR Candidate Selection**:
   In `ocr.py:307`, `need_alternative_test = (w0_count < 8) or (flow0 < 0)`.
   Because `flow0 = -35 < 0`, `need_alternative_test` evaluates to `True`, triggering candidate 180° even if 0° had high word counts (e.g. 50+ words).
   In candidate 180°, the former bottom line (e.g. `Definition: ...`) becomes line 1, scoring `+15`.
   In `ocr.py:320-324`, condition `(flow0 < 0 and flow_alt >= 5 and w_alt >= w0_count)` evaluates to `True`, forcing `best_angle = 180`.
5. **Observation -> Isolation of `router.py`**:
   `router.py` simply takes `file_bytes`, passes them to `process_ocr()`, and forwards `ocr_result` to `fuse_results()`. It has no knowledge of image rotation or base64 decoding.
6. **Deduction -> Required Architecture Alignment**:
   - `router.py` requires NO code modifications.
   - `orientation.py`: `score_reading_flow` must be corrected so upright student documents (with `Date:`, `Page:`, or general headings) do not receive bogus negative scores.
   - `ocr.py`:
     - Guarantee display orientation: Always assign `result["oriented_image_base64"] = image_to_base64_data_uri(raw_img)`.
     - Guard candidate selection: Do not trigger alternative rotation tests if 0° orientation already extracted sufficient legitimate words (`w0_count >= 8`).

---

## 3. Caveats

1. **VLM Forensics Image Input**:
   `ocr.py:355` executes `vlm_forensics = evaluate_vlm_forensics(best_img)`. If internal OCR candidate rotation is retained for text extraction, `best_img` is the image used for VLM inference. Because synthetic handwriting features (uniformity, baseline rigidity) are invariant or slightly clearer when upright, using the upright image is preferred.
2. **Deskewing vs. 90/180/270 Rotation**:
   The prompt specifies: "The `oriented_image_base64` returned to the frontend should be the ORIGINAL uploaded image (at 0° with EXIF normalization only)." `raw_img` is exactly `normalize_image(Image.open(io.BytesIO(image_bytes)))`. Fine deskewing (`apply_fine_deskew`) modifies rotation by minor degrees (-20° to +20°); to strictly meet "ORIGINAL uploaded image at 0° with EXIF normalization only", `raw_img` should be used directly for `oriented_image_base64`.
3. **Frontend Exemption**:
   As stipulated in instructions, frontend code (`DashboardPage.jsx`) must not be modified.

---

## 4. Conclusion

### Summary of Findings
1. **The Bug**:
   `ocr.py` line 352 returns `image_to_base64_data_uri(best_img)` instead of the EXIF-normalized 0° image `raw_img`.
2. **The Heuristic Trigger**:
   `orientation.py:score_reading_flow()` penalizes standard notebook headers (`Date:`, `Page:`) and concluding definitions, driving `flow0` negative (-35). In `ocr.py`, `(flow0 < 0)` forces evaluation of 180° and swaps to 180° whenever `w_alt >= w0_count`.
3. **Component Responsibilities**:
   - `router.py`: **Keep intact**. No changes required.
   - `orientation.py`: Fix `score_reading_flow()` to eliminate false negative penalties on `Date:` and `Page:` headers and expand title matching.
   - `ocr.py`: Change `result["oriented_image_base64"]` to encode `raw_img` (always 0°), and guard `need_alternative_test` so upright text with `w0_count >= 8` is never flipped away from 0°.

### Recommended Code Snippets for Implementer

#### Snippet A: `Deepfake/eduverify-ai/backend/api/services/ocr.py`
**Line 307 (Candidate Search Trigger):**
```python
# BEFORE:
need_alternative_test = (w0_count < 8) or (flow0 < 0)

# AFTER:
# If 0° already produces legitimate words (>= 8), the document is already upright and readable.
# Do not trigger alternative rotation merely because heuristic flow score was low.
need_alternative_test = (w0_count < 8)
```

**Line 352 (Returned Image):**
```python
# BEFORE:
result["oriented_image_base64"] = image_to_base64_data_uri(best_img)

# AFTER:
# Always return the original uploaded image at 0° with EXIF normalization only
result["oriented_image_base64"] = image_to_base64_data_uri(raw_img)
```

#### Snippet B: `Deepfake/eduverify-ai/backend/api/services/orientation.py`
**Lines 95-118 (`score_reading_flow`):**
```python
# In bottom_first_starters, remove 'page:' and 'date:':
bottom_first_starters = [
    'it produces', 'it accepts', 'it has', 'and ', 'or ', 'that adds',
    'which is', 'then ', 'pg.', 'fig.'
]

# Remove the regex penalties for page/date on first line (or make them positive title indicators):
# In student notebooks, Date: and Page: are standard top-of-page headers:
if re.search(r'\bpage\s*[:\.]?\s*\d+', first_line) or re.search(r'\bdate\s*[:\.]', first_line):
    score += 5  # Top-of-page header is a positive upright signal
```

#### Snippet C: `Deepfake/eduverify-ai/backend/api/router.py`
**NO CHANGES REQUIRED**. Retain existing code as is.

---

## 5. Verification Method

### 5.1 Unit Test Verification
Run the 33 backend tests using the GPU virtual environment python executable:
```powershell
& "Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe" -m pytest Deepfake\eduverify-ai\backend\tests -q
```
**Expected Outcome**: 33 passed in < 1.5s.

### 5.2 Heuristic Flow Score Verification
Execute the following verification script in PowerShell:
```powershell
& "Deepfake\eduverify-ai\backend\venv_gpu\Scripts\python.exe" -c "
import sys
sys.path.insert(0, r'Deepfake\eduverify-ai\backend')
from api.services.orientation import score_reading_flow

doc_tech = '''Date: 12/10/2026\nComputer Generations\n1st Gen: Vacuum Tubes\n2nd Gen: Transistors\nDefinition: CPU processes instructions.'''
score = score_reading_flow(doc_tech)
print(f'Technical document flow score: {score}')
assert score >= 0, f'Expected non-negative score for upright technical document, got {score}'
print('Heuristic verification passed!')
"
```

### 5.3 Invalidation Conditions
This analysis and proposed fix would be invalidated if:
1. The frontend specifically required backend-rotated coordinates for bounding box overlay rendering (verified: `DashboardPage.jsx` does not overlay bounding boxes on `analyzed-image`; it simply renders `src={report.oriented_image_base64 || previewImage}`).
2. `test_scoring.py` had an assertion checking that `oriented_image_base64` changes when candidate angle is non-zero (verified: `test_scoring.py` lines 309, 347, 348 only assert that `fuse_results` preserves whatever string is passed in `ocr_mock`).
