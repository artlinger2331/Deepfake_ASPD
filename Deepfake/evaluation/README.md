# EduVerify AI — Forensic Evaluation Dataset & Guidelines

This directory contains the independent evaluation harness, dataset structure, and performance metrics calculation suite for **EduVerify AI**.

---

## Folder Structure

```text
evaluation/
├── images/
│   ├── real_photo/       # Authentic photographs of physical student handwritten work (mobile camera captures)
│   ├── real_scan/        # Flatbed or optical scanner captures of authentic student work
│   ├── ai_generated/     # Synthetic handwriting (Diffusion models, GANs, digital font rendering)
│   ├── edited_real/      # Real student submissions modified using Photoshop, Canva, GIMP, etc.
│   └── difficult_real/   # Authentic notes with harsh lighting, severe slant, faint ink, or low resolution
├── transcriptions/       # (Optional) Ground-truth reference text files: {image_id}_reference.txt
├── results/              # Output directory for raw API JSON responses and evaluation_results.csv
├── ground_truth.csv      # Human-annotated ground-truth labels and optical metadata
├── run_evaluation.py     # Evaluation runner hitting POST /api/v1/analyze
├── calculate_metrics.py  # Statistical metrics, confusion matrices, and ROC-style threshold evaluations
├── test_evaluation.py   # Unit and integration tests for the evaluation harness
└── evaluation_report.md  # Comprehensive evaluation audit report
```

---

## Dataset Privacy & Ethics Protocol

1. **De-identification**:
   * All images submitted to the evaluation set **MUST** be stripped of personal identifying information (PII).
   * **Do NOT include**: student names, roll numbers, student ID numbers, institutional affiliations, email addresses, or visible student faces/reflections.
   * If an assignment header contains student identifiers, black them out or crop them before ingestion.

2. **Informed Consent**:
   * Authentic student samples must be collected with permission or derived from open, de-identified academic benchmark corpora.

3. **No External Transmission**:
   * The evaluation harness runs strictly against local endpoints (`http://127.0.0.1:8000`). No student data or submission images are uploaded to external cloud services or commercial APIs.

4. **Pedagogical Use Only**:
   * Results from this evaluation suite measure the statistical reliability of the forensic decision-support pipeline. A high synthetic score or metadata flag must **never** be used as standalone evidence of academic dishonesty.

