# EduVerify AI — Benchmark & Evaluation Suite

This directory contains the standardized benchmarking dataset, evaluation scripts, and reporting harness for **EduVerify AI**. It provides rigorous testing across forensic authenticity classification, image tampering detection, and multimodal handwriting OCR fidelity.

---

## 1. Directory Structure

```
evaluation/
├── images/
│   ├── real_photo/           # Authentic physical camera captures
│   ├── real_scan/            # Authentic flatbed scanner digitizations
│   ├── ai_generated/         # Synthetic / AI-generated handwriting
│   ├── edited_real/          # Digitally edited/tampered genuine notes
│   ├── handwritten_clear/    # Clean, high-legibility handwriting
│   ├── handwritten_blurry/   # Faint, cursive, blurry, low-res handwriting
│   ├── printed_text/         # Machine-printed, typeset documents
│   └── no_text/              # Blank pages, line-only paper, diagrams
├── transcriptions/           # Ground truth .txt files for OCR CER/WER benchmarks
├── results/                  # Raw JSON responses saved by run_evaluation.py
├── ground_truth.csv          # Master annotation file for benchmark targets
├── run_evaluation.py         # Automated API testing harness
├── calculate_metrics.py      # Statistical evaluation & metrics calculation engine
├── evaluation_report.md      # Auto-generated markdown benchmark report
└── README.md                 # This documentation
```

---

## 2. Image Categories & Submission Guidelines

To ensure comprehensive forensic validation, test images belong to 8 distinct categories:

### 1. `images/real_photo/`
* **What belongs here**: Authentic physical student handwritten work photographed using smartphone or digital cameras.
* **Forensic characteristics**: Natural camera sensor noise, authentic EXIF metadata (Make/Model, ISO, exposure), micro-variations in pen pressure, paper texture, and natural environmental lighting.

### 2. `images/real_scan/`
* **What belongs here**: Authentic student handwritten notes digitized via flatbed, document, or mobile scanner apps.
* **Forensic characteristics**: High geometric consistency, uniform lighting, absence of physical camera depth-of-field, potential scanner driver EXIF tags.

### 3. `images/ai_generated/`
* **What belongs here**: Synthetic handwriting generated using AI diffusion models (Stable Diffusion, Midjourney, Flux), GAN-based handwriting synthesizers, digital handwriting fonts, or pen-plotter SVG engines.
* **Forensic characteristics**: Unnatural stroke smoothing, absence of organic sensor grain ($\sigma^2_{\text{Laplacian}} < 50$), uniform stroke thickness, repetitive letter shapes.

### 4. `images/edited_real/`
* **What belongs here**: Authentic handwritten notes that have been digitally altered, spliced, retouched, or manipulated using editing tools (Adobe Photoshop, Canva, GIMP, Procreate).
* **Forensic characteristics**: Software tags in EXIF, localized sharpening/blur boundaries, cut-and-paste compression mismatches, altered numerical scores or words.

### 5. `images/handwritten_clear/`
* **What belongs here**: High-contrast, upright, neatly penned handwriting with clear baselines and standard lighting.
* **Purpose**: Serves as the gold standard benchmark for verbatim OCR transcription accuracy (target: CER $< 5\%$, WER $< 10\%$).

### 6. `images/handwritten_blurry/`
* **What belongs here**: Challenging real-world student submissions: motion blur, out-of-focus camera captures, faint pencil strokes, extreme cursiveness, uneven shadows, or low resolution.
* **Purpose**: Benchmarks the adaptive contrast enhancement and robustness of Qwen2-VL under degraded conditions.

### 7. `images/printed_text/`
* **What belongs here**: Machine-printed, typeset documents (textbooks, printed assignment prompts, laser-printed exams, worksheets).
* **Purpose**: Tests whether the system correctly detects non-handwritten, machine-typeset fonts.

### 8. `images/no_text/`
* **What belongs here**: Blank notebook paper, empty ruled sheets, pencil sketches, geometry drawings without words, or non-document photographs.
* **Purpose**: Validates system safeguards against hallucination—ensures the engine outputs zero words and does not invent ghost text.

---

## 3. Strict Ethical, Consent & De-Identification Rules

> [!CAUTION]
> **Zero Tolerance for Personal & Student Identifiers**
> All benchmark images must strictly protect student privacy and comply with educational data protection standards (FERPA / GDPR guidelines).

### Mandatory Requirements Before Adding Any Image:
1. **Informed Consent**:
   * All handwritten samples must be contributed voluntarily with explicit permission from the author.
2. **Strict De-Identification (No PII)**:
   * **Student Names**: MUST NOT appear anywhere on the image.
   * **Faces or Reflections**: Absolutely no photos showing student faces, hands with identifiable marks, or reflections.
   * **Student Roll / Registration / ID Numbers**: MUST NOT be included.
   * **Institutional Names / Course Codes**: Redact any specific school, university, or teacher names.
   * **Personal Data**: No email addresses, phone numbers, signatures, or physical addresses.
3. **Physical / Digital Redaction**:
   * If historic sample notes contain student headers, digitally crop or apply opaque black bounding boxes over the student header before placing the image in this directory.

---

## 4. Ground Truth File Format (`ground_truth.csv`)

The master annotation file `ground_truth.csv` maps each image to its expected forensic verdict and reference transcription:

```csv
filename,category,expected_status,expected_synthetic,expected_edited,expected_has_text,transcription_file,notes
sample_real_01.jpg,real_photo,genuine,False,False,True,sample_real_01.txt,Genuine biology notebook page
sample_ai_01.png,ai_generated,concern,True,False,True,sample_ai_01.txt,Diffusion-generated cursive essay
sample_blank.jpg,no_text,uncertain,False,False,False,,Blank ruled notebook sheet
```

### Column Specifications:
* `filename`: The exact image filename (e.g., `note_01.jpg`) residing in one of the `images/*/` subdirectories.
* `category`: One of the 8 category folder names.
* `expected_status`: Expected fusion verdict (`genuine`, `concern`, or `uncertain`).
* `expected_synthetic`: `True` if synthetically generated; `False` if physical capture.
* `expected_edited`: `True` if digitally altered in photo editing software; `False` otherwise.
* `expected_has_text`: `True` if legible handwriting is present; `False` for blank/diagram-only pages.
* `transcription_file`: Filename of the ground truth `.txt` file located in `evaluation/transcriptions/` (leave blank if no text).
* `notes`: Optional context describing the sample.

---

## 5. How to Run the Evaluation Harness

### Prerequisites
Ensure your FastAPI backend is running with PyTorch CUDA:
```powershell
# From eduverify-ai/backend/
uvicorn main:app --port 8000 --reload
```

### Step 1: Run Automated Benchmarks
Processes all images across all category folders through `POST /api/v1/analyze`:
```powershell
python run_evaluation.py
```
* Optional flags:
  * `--url http://localhost:8000`: Target different server host/port.
  * `--category handwritten_clear`: Run only a specific image category.

Raw responses are automatically saved into `evaluation/results/{image_name}.json`.

### Step 2: Compute Metrics & Generate Report
Compares raw results against `ground_truth.csv` and reference transcriptions:
```powershell
python calculate_metrics.py
```

### Outputs Generated:
1. **Terminal Summary**: Real-time accuracy, precision, recall, F1, and average CER/WER.
2. **`evaluation_report.md`**: Complete markdown report with confusion matrices and per-image forensic score breakdowns.
