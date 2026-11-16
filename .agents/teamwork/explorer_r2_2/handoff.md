# Handoff Report: Frontend Display & Session State Consistency (R1 & R3)

**Subagent Role**: Frontend Display Explorer  
**Date**: 2026-11-16  
**Status**: Completed (Read-Only Investigation)  
**State Folder**: `c:\Users\Pritam Mondal\Desktop\Hacktoberfest\.agents\teamwork\explorer_r2_2`

---

## 1. Observation

### 1.1 "Submitted Document" Panel in `DashboardPage.jsx`
- **Location**: `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx:263-299`
- **Component markup**:
  ```jsx
  {/* Submission Preview Card */}
  <motion.div 
    className="card image-preview-card"
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: 0.2 }}
  >
    <div className="card-header-flex">
      <h3 className="section-title">Submitted Document</h3>
      <button 
        className="btn-text btn-sm flex items-center gap-1"
        onClick={() => setShowHighlights(!showHighlights)}
      >
        {showHighlights ? <EyeOff size={16} /> : <Eye size={16} />}
        {showHighlights ? 'Hide Highlights' : 'Show Highlights'}
      </button>
    </div>

    <div className="analyzed-image-wrapper">
      {(report.oriented_image_base64 || previewImage) ? (
        <img 
          src={report.oriented_image_base64 || previewImage} 
          alt="Student Assignment Preview" 
          className="analyzed-image"
          style={{ width: '100%', maxHeight: '420px', objectFit: 'contain', borderRadius: '8px' }}
        />
      ) : (
        <div className="placeholder-assignment">
          ...
        </div>
      )}
    </div>
  </motion.div>
  ```
- **Image Source Expression**:
  `src={report.oriented_image_base64 || previewImage}` (`DashboardPage.jsx:284`)
  - `report` is obtained from `location.state?.report || (storedReportStr ? JSON.parse(storedReportStr) : defaultDemoReport)` (`DashboardPage.jsx:52`).
  - `previewImage` is obtained from `location.state?.previewUrl || sessionStorage.getItem('preview_${id}')` (`DashboardPage.jsx:55`).
  - **Key Observation**: `report.oriented_image_base64` is evaluated **first** in the logical OR operator (`report.oriented_image_base64 || previewImage`). If the backend returns `oriented_image_base64`, `previewImage` is discarded/ignored.

### 1.2 CSS Styles, Transforms, and Canvas Operations
- **Inline style**: `style={{ width: '100%', maxHeight: '420px', objectFit: 'contain', borderRadius: '8px' }}` on `<img>` (`DashboardPage.jsx:287`).
- **CSS classes**:
  - Neither `.analyzed-image-wrapper` nor `.analyzed-image` has CSS rotation or transform rules in `DashboardPage.css`, `App.css`, or `index.css`.
  - Searches for `rotate`, `transform`, `orientation`, and `canvas` confirmed zero rotation transforms or canvas manipulations in the entire frontend source tree (`Deepfake/eduverify-ai/src/`).
  - `object-fit: contain` preserves aspect ratio and prevents stretching or orientation alterations.
  - Browser default `image-orientation: from-image` applies across modern browsers.

### 1.3 Upload Lifecycle in `UploadPage.jsx`
- **File Selection & Preview Generation** (`UploadPage.jsx:26-38`):
  ```javascript
  const processFile = (file) => {
    if (file && (file.type.startsWith('image/') || /\.(jpg|jpeg|png|webp|bmp)$/i.test(file.name))) {
      setSelectedFile(file);
      setErrorMessage(null);
      const reader = new FileReader();
      reader.onload = (e) => {
        setPreviewUrl(e.target.result);
      };
      reader.readAsDataURL(file);
    } else {
      setErrorMessage("Please select a valid image file (JPG, PNG, WebP).");
    }
  };
  ```
  `FileReader.readAsDataURL(file)` reads the exact, uncompressed, raw byte stream from the client's local file input. This is guaranteed to be in the user's true uploaded orientation.
- **Analysis Submission and State Transfer** (`UploadPage.jsx:87-117`):
  ```javascript
  const reportId = reportData.id || reportData.analysis_id || `EV-${Date.now()}`;
  if (previewUrl) {
    sessionStorage.setItem(`preview_${reportId}`, previewUrl);
  }
  sessionStorage.setItem(`report_${reportId}`, JSON.stringify(reportData));
  ...
  setTimeout(() => {
    navigate(`/analysis/${reportId}`, {
      state: {
        report: reportData,
        previewUrl: previewUrl
      }
    });
  }, 400);
  ```
  Both `reportData` (from backend) and `previewUrl` (raw client-side data URL) are passed to `DashboardPage` via router `state` and also saved in `sessionStorage`.

### 1.4 Direct Report Lookups and Navigation Flows
- **Direct Navigation (`/analysis/:id`)**:
  - In `DashboardPage.jsx:51-55`:
    If a user navigates directly to `/analysis/:id` (via URL bar, bookmark, or new browser tab):
    - `location.state` is `undefined`.
    - If accessed within the same session/tab where the upload took place, `sessionStorage.getItem('report_${id}')` and `sessionStorage.getItem('preview_${id}')` successfully restore the report and preview image.
    - If accessed in a new tab or after session clear:
      `sessionStorage` returns `null`.
      `report` falls back to `defaultDemoReport` (`DashboardPage.jsx:11-43`), which lacks `oriented_image_base64`.
      `previewImage` is `null`.
      The UI falls back to `<div className="placeholder-assignment">`.
  - There is currently **no network fetch** (`fetch('/api/v1/...')`) implemented in `DashboardPage.jsx` on mount. The backend itself is stateless with no persistent report storage endpoints.

### 1.5 Storage and Caching Vulnerabilities
- In `UploadPage.jsx:89-91`:
  ```javascript
  if (previewUrl) {
    sessionStorage.setItem(`preview_${reportId}`, previewUrl);
  }
  sessionStorage.setItem(`report_${reportId}`, JSON.stringify(reportData));
  ```
  - Both `preview_${reportId}` (full base64 data URL) and `report_${reportId}` (JSON string embedding `oriented_image_base64`) are written to `sessionStorage` **without a `try...catch` block**.
  - High-resolution phone camera images (3MB–5MB) produce base64 strings of ~4MB–6.5MB. Storing both can easily exceed browser `sessionStorage` quotas (typically 5MB–10MB per origin), triggering an uncaught `QuotaExceededError` that aborts `startAnalysis()` in its `catch` block (`UploadPage.jsx:119-125`), completely preventing navigation to the dashboard.
- In `HistoryPage.jsx`:
  `UploadPage.jsx:95-105` appends reports to `localStorage.getItem('eduverify_history')`, but `HistoryPage.jsx:6-11` uses hardcoded `MOCK_HISTORY` and does not read from `localStorage`.

### 1.6 Frontend Build Verification
- Running `npm run build` in `Deepfake/eduverify-ai`:
  Vite/Rollup builds successfully (`dist/assets/index-B_JqiMXx.js` 295.57 kB).
  Esbuild emits CSS syntax warnings for git merge conflict markers (`<<<<<<< HEAD`, `=======`, `>>>>>>>`) present in `App.css:82` and `UploadPage.css:57, 165`.

---

## 2. Logic Chain

1. **Root Mechanism of the Rotation Defect**:
   - `UploadPage.jsx` captures the user's raw image via `FileReader.readAsDataURL(file)` and displays it in the drop-zone preview. In this step, the preview is **always upright** because it directly reflects the user's uploaded file bytes.
   - When the user clicks "Start Analysis", the file bytes are sent to the backend `/api/v1/analyze`.
   - In the backend pipeline prior to recent fixes:
     - `orientation.detect_stroke_is_sideways(raw_img)` falsely returned `True` for upright documents (e.g., notebook sample `media_1794843355919_2564ee42.jpg`, which yielded `ratio=0.266 -> is_sideways=True`).
     - OCR tested candidate 90° and rotated the image 90° clockwise.
     - The rotated image was encoded and returned in `reportData.oriented_image_base64`.
   - On the frontend in `DashboardPage.jsx:284`:
     ```jsx
     src={report.oriented_image_base64 || previewImage}
     ```
     Because `report.oriented_image_base64` was evaluated **before** `previewImage`, the frontend discarded the upright `previewUrl` and rendered the backend's 90° rotated image.
   - On page refresh or navigating back from History, `sessionStorage.getItem('report_${id}')` also contained this rotated base64 string, cementing the rotation across page reloads.

2. **Why Frontend Priority and Fallback Matter for R1 & R3**:
   - `previewImage` (from `location.state.previewUrl` or `sessionStorage.getItem('preview_${id}')`) is guaranteed to be the user's unadulterated uploaded file data URL created client-side by `FileReader`.
   - If `DashboardPage.jsx` prioritizes `previewImage`:
     `src={previewImage || report.oriented_image_base64 || report.document_image}`
     the frontend will **always** display the user's true uploaded orientation immediately upon upload and across intra-session navigations.
   - When direct report lookup occurs without an active upload session, the frontend falls back to `report.oriented_image_base64` (which the backend must now emit verbatim from raw uploaded bytes without rotation or lossy transformation).

3. **Storage Robustness**:
   - Wrapping `sessionStorage.setItem` in `UploadPage.jsx` in `try...catch` eliminates the risk of silent upload failures caused by storage quota overflow on large image payloads.

---

## 3. Caveats

1. **Backend Statelessness**:
   - The backend currently has no persistence layer (no database, no disk cache of report IDs). Direct URL lookups in a new tab (e.g. `/analysis/EV-12345` with empty `sessionStorage`) cannot query past reports from the backend; they fall back to `defaultDemoReport`.
2. **Merge Conflict Markers**:
   - `App.css` and `UploadPage.css` contain committed merge conflict markers (`<<<<<<< HEAD`). While Vite minification recovers with warnings and builds cleanly, these should be cleaned up during styling maintenance.
3. **Frontend Automated Tests**:
   - The project does not currently contain a frontend test runner (e.g., Vitest or Cypress). Verification relies on static analysis, `npm run build`, and integration verification.

---

## 4. Conclusion

The frontend orientation defect is driven by two interlocking factors:
1. **Frontend Priority Inversion**: In `DashboardPage.jsx:284`, `report.oriented_image_base64` takes precedence over `previewImage`. When the backend previously returned an image rotated 90°, the frontend ignored the true uploaded `previewImage` and rendered the rotated image.
2. **Session Storage Fragility**: `UploadPage.jsx` attempts to store both `previewUrl` and `reportData` in `sessionStorage` without `try...catch`, risking `QuotaExceededError` on large images.

### Concrete Recommendations

#### Recommendation 1: Prioritize Client Upload Preview in `DashboardPage.jsx` (R1 & R3)
In `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx`:
```javascript
// Before (line 284):
src={report.oriented_image_base64 || previewImage}

// Recommended (lines 282-288):
const displayImage = previewImage || report.oriented_image_base64 || report.document_image;

...
<img 
  src={displayImage} 
  alt="Student Assignment Preview" 
  className="analyzed-image"
  style={{ width: '100%', maxHeight: '420px', objectFit: 'contain', borderRadius: '8px' }}
/>
```
*Rationale*: When a document is uploaded in the user session, `previewImage` is the authentic raw file data URL. Prioritizing `previewImage` guarantees visual orientation fidelity across uploads and router navigations, while `report.oriented_image_base64` remains an authoritative fallback for external/direct lookups.

#### Recommendation 2: Quota-Safe `sessionStorage` in `UploadPage.jsx` (R3)
In `Deepfake/eduverify-ai/src/pages/UploadPage.jsx:87-92`:
Wrap `sessionStorage` writes in a `try...catch` block:
```javascript
try {
  if (previewUrl) {
    sessionStorage.setItem(`preview_${reportId}`, previewUrl);
  }
  sessionStorage.setItem(`report_${reportId}`, JSON.stringify(reportData));
} catch (storageErr) {
  console.warn('SessionStorage quota exceeded, preserving report in router state only:', storageErr);
}
```
*Rationale*: Prevents `QuotaExceededError` from aborting the analysis workflow on large image uploads.

#### Recommendation 3: Backend Byte Verbatim Preservation (Coordination with R1/R2)
In `backend/api/services/ocr.py`:
Ensure `oriented_image_base64` uses raw uploaded image bytes directly base64-encoded (e.g. `data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}`) rather than re-encoding via PIL with lossy JPEG compression and `ImageOps.exif_transpose`. This guarantees that both `previewImage` and `report.oriented_image_base64` are byte-identical.

---

## 5. Verification Method

To independently verify the frontend display consistency and build integrity:

1. **Vite Production Build Verification**:
   ```powershell
   cd "Deepfake/eduverify-ai"
   npm run build
   ```
   *Expected Result*: Build completes with exit code 0 and bundles `dist/index.html` and `dist/assets/`.

2. **Source Code Inspection**:
   - Inspect `Deepfake/eduverify-ai/src/pages/DashboardPage.jsx:282-288` to verify image resolution logic.
   - Inspect `Deepfake/eduverify-ai/src/pages/UploadPage.jsx:26-38, 87-117` to verify file reading and navigation state.
   - Verify no CSS rotations exist:
     ```powershell
     git grep -i "rotate" "Deepfake/eduverify-ai/src/"
     ```

3. **End-to-End Navigation & Reload Test (when dev server is active)**:
   - Start frontend: `npm run dev` in `Deepfake/eduverify-ai`.
   - Upload sample notebook image `media_1794843355919_2564ee42.jpg` on `/upload`.
   - Confirm preview on `/upload` is upright.
   - Click "Start Analysis" and observe transition to `/analysis/:id`.
   - Confirm "Submitted Document" panel displays the image upright (1024x576 aspect ratio), not rotated 90° sideways.
   - Refresh the page (`F5`) and confirm the document remains upright.
   - Click "Back to History", then navigate back to `/analysis/:id` and confirm display remains upright.
