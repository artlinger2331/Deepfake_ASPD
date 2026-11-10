# EduVerify AI — Forensic System Evaluation Audit Report

**Evaluation Date**: 2026-11-10 20:20:16  
**Total Images Evaluated**: 4  

---

## 1. Executive Summary & Dataset Breakdown

| Metric | Measured Value |
| :--- | :--- |
| **Total Test Images** | 4 |
| **Authentic Samples** | 4 |
| **Synthetic / Manipulated Samples** | 0 |
| **Ground Truth References Available** | 4 |

---

## 2. Final Decision Performance Metrics

Evaluation grouped into **Not Concerning** (`likely_genuine`) vs. **Concerning** (`uncertain`, `concern`, `possibly_ai_generated`):

| Metric | Result | Benchmark Target | Status |
| :--- | :---: | :---: | :---: |
| **Overall Accuracy** | **100.0%** | $\ge 85.0\%$ | ✅ Passed |
| **Precision** | **0.0%** | $\ge 80.0\%$ | ⚠️ In Progress |
| **Recall (Sensitivity)** | **0.0%** | $\ge 80.0\%$ | ⚠️ In Progress |
| **F1-Score** | **0.0000** | $\ge 0.82$ | ⚠️ In Progress |
| **False-Positive Rate (FPR)** | **0.0%** | $\le 10.0\%$ | ✅ Low Risk |
| **False-Negative Rate (FNR)** | **0.0%** | $\le 15.0\%$ | ✅ Low Risk |

### Confusion Matrix
```
                     Predicted Genuine    Predicted Concerning
Actual Real Samples:        4                    0 (False Alarms)
Actual AI/Edited:           0                    0 (Hits)
```

---

## 3. Visual Synthetic Score Analysis

* **Average Visual Score (Authentic Notes)**: `0.12` (Lower is more natural)
* **Average Visual Score (AI-Generated)**: `0.0`
* **Average Visual Score (Digitally Edited)**: `0.0`
* **Recommended Optimal Threshold**: `0.5`

### False-Positive Rate Across Thresholds
| Tested Threshold | False-Positive Rate on Authentic Work |
| :---: | :---: |
| $\ge 0.3$ | 0.0% |
| $\ge 0.4$ | 0.0% |
| $\ge 0.5$ | 0.0% |
| $\ge 0.6$ | 0.0% |
| $\ge 0.7$ | 0.0% |
| $\ge 0.8$ | 0.0% |

---

## 4. Hardware Metadata & Provenance (C2PA) Analysis

* **Authentic Images with Native Hardware EXIF**: `0.0%`
* **Authentic Images with Stripped EXIF (Messaging App Uploads)**: `100.0%`
* **Manipulated Images with Editing Software Signatures**: `0.0%`
* **C2PA Credentials Found**: `0 (0.0%)`
* **C2PA Credentials Missing / Stripped**: `4 (100.0%)`
* **Ethical Boundary Verification**: PASS: Missing credentials are treated as unprovenanced/standard capture, NEVER as proof of misconduct.

---

## 5. Multimodal Handwriting OCR & Transcription Analysis

| Metric | Result |
| :--- | :--- |
| **Evaluated Reference Transcriptions** | 4 of 4 |
| **Word Error Rate (WER)** | **0.3065** |
| **Character Error Rate (CER)** | **0.239** |
| **High-Fidelity Transcription Rate (WER $\le 15\%$)** | **50.0%** |
| **TrOCR Secondary Fallback Invocations** | 0 |

---

## 6. Robustness & Subgroup Analysis

### Subgroup Distribution
* **Lighting**: `{
  "indoor": {
    "total": 3,
    "genuine": 3,
    "concerning": 0
  },
  "low_light": {
    "total": 1,
    "genuine": 1,
    "concerning": 0
  }
}`
* **Image Quality**: `{
  "medium": {
    "total": 2,
    "genuine": 2,
    "concerning": 0
  },
  "high": {
    "total": 2,
    "genuine": 2,
    "concerning": 0
  }
}`
* **Device**: `{
  "android": {
    "total": 4,
    "genuine": 4,
    "concerning": 0
  }
}`
* **Category**: `{
  "difficult_real": {
    "total": 2,
    "genuine": 2,
    "concerning": 0
  },
  "real_photo": {
    "total": 2,
    "genuine": 2,
    "concerning": 0
  }
}`

---

## 7. Failure Case Analysis & Recommendations

✅ **No catastrophic failure cases or false accusations observed across the evaluated set.**

---

## 8. Limitations

1. **Dataset Breadth**: The current benchmark relies on available verified student handwriting samples. Full validation across flatbed scanners, multiple mobile camera sensors, and state-of-the-art diffusion plotters requires expanding the dataset.
2. **Metadata Stripping**: Online portals and messaging platforms (e.g., WhatsApp, Discord) strip EXIF metadata by default; the system must never rely on missing EXIF as an indicator of manipulation.

---

## 9. Ethical Disclaimer

"This evaluation does not prove that EduVerify AI can determine academic misconduct. It measures system performance on a limited test set. A concerning result requires human review and must not be used as sole evidence against a student."
