# 🤝 Contributing to EduVerify AI

Welcome to **EduVerify AI**! Whether you are participating through **Hacktoberfest**, a regional hackathon, or open-source fellowship, we are thrilled to have you contribute.

EduVerify AI is built to empower educators with transparent, explainable multimodal AI forensics for student work. We value high-quality contributions that advance our mission while maintaining strict ethical standards.

---

## 🧭 Core Principles & Ethical Guidelines

Before writing code, please review our core tenet:

> [!IMPORTANT]
> **Ethical Decision-Support Mandate**  
> EduVerify AI is strictly an **educator decision-support tool**. It is **never** permitted to automatically accuse a student of academic misconduct based solely on an AI probability score.
> - Any PR that introduces unexplainable "verdicts", punitive automations, or opaque scores without actionable pedagogical context will be closed.
> - All forensic signals must be accompanied by human-readable explanations and confidence metrics.

---

## 🎯 Hackathon & Hacktoberfest Guidelines

We maintain high submission standards to ensure meaningful open-source impact:
- **No Spam / Trivial PRs**: PRs adding a single comment, fixing one typo, or formatting whitespace will not be tagged for Hacktoberfest.
- **Focus on Meaningful Modules**: Prioritize open issues, new forensic signals, UI polish, accessibility, or benchmark datasets.
- **Explainable Work**: Clearly explain your approach and rationale in your PR description.

---

## 🗺️ Contribution Tracks & Ideas

Not sure where to start? Pick from one of our key architectural tracks:

### 🎨 Track 1: Frontend & User Experience (React + Vite)
- [ ] **Export to PDF / Printable Report**: Generate an official, beautifully formatted forensic summary for student-faculty meetings.
- [ ] **Side-by-Side Visual Diff**: Interactive image comparison viewer (original upload vs. enhanced edges / artifact heatmaps).
- [ ] **Accessibility (a11y)**: Ensure keyboard navigability and screen-reader compliance (WCAG 2.1 AA standards).
- [ ] **Batch Upload UI**: Interface supporting multiple student assignment uploads in a single session.

### 🧠 Track 2: AI / ML & Forensics (Python + PyTorch + OpenCV)
- [ ] **Quantized Inference (AWQ / GPTQ / GGUF)**: Add support for 4-bit/8-bit Qwen2-VL inference for systems with < 4GB VRAM.
- [ ] **Cryptographic C2PA Verification**: Integrate `c2pa-python` to inspect cryptographic manifest chains and content credentials.
- [ ] **Frequency-Domain Anomaly Detection**: Enhance `vision.py` with 2D Fast Fourier Transform (FFT) high-frequency spectrum analysis to identify diffusion grid patterns.
- [ ] **Stroke Consistency Metric**: Calculate pen pressure and stroke-width variance across handwritten text lines.

### ⚙️ Track 3: Backend & DevOps (FastAPI + Docker)
- [ ] **Docker & Docker Compose**: Multi-container Dockerfile setup with NVIDIA Container Toolkit support.
- [ ] **Batch Async Queue**: Celery / Redis background worker queue for processing full-class PDF submissions.
- [ ] **Automated CI/CD**: GitHub Actions workflow running `pytest` and ESLint checks on every pull request.

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- **Node.js**: `v18.x` or higher
- **Python**: `3.10` to `3.13`
- **Git** installed and configured
- *(Optional)* **NVIDIA GPU** with CUDA 12.4+ for GPU model acceleration

### 2. Fork & Clone
```bash
git clone https://github.com/<your-username>/Deepfake.git
cd Deepfake/eduverify-ai
```

### 3. Backend Setup
```powershell
cd backend

# Create and activate virtual environment
python -m venv venv_gpu
.\venv_gpu\Scripts\activate   # On Windows
# source venv_gpu/bin/activate # On Linux/macOS

# Install PyTorch with CUDA (or CPU version)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

# Install project dependencies
pip install -r requirements.txt

# Start backend server
python -m uvicorn main:app --port 8000 --reload
```

Test backend health at: `http://127.0.0.1:8000/health`  
Interactive Swagger docs: `http://127.0.0.1:8000/docs`

### 4. Frontend Setup
In a separate terminal:
```bash
cd eduverify-ai
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🌿 Git Branching Convention

Create descriptive branch names using the following prefixes:

| Branch Prefix | Purpose | Example |
| :--- | :--- | :--- |
| `feat/` | New feature or forensic signal | `feat/c2pa-verification` |
| `fix/` | Bug fix or performance patch | `fix/ocr-gpu-vram-leak` |
| `perf/` | Speed and resource optimization | `perf/trocr-lazy-load` |
| `docs/` | Documentation enhancements | `docs/api-specification` |
| `test/` | Adding test cases or datasets | `test/vision-laplacian-suite` |

---

## 💬 Commit Message Standards

We follow the **Conventional Commits** specification:

```
<type>(<scope>): <short imperative summary>

[optional detailed description]

[optional issue reference]
```

### Examples:
- `feat(ocr): add 4-bit quantization support for Qwen2-VL model`
- `fix(dashboard): correct confidence score fallback for low-density text`
- `perf(pipeline): bypass TrOCR execution when multimodal transcription succeeds`
- `docs(readme): add system architecture and end-to-end flowchart`

---

## 📋 Pull Request (PR) Checklist

Before submitting your PR, make sure you complete the following:

- [ ] **Tested Locally**: Code compiles and runs cleanly without console errors or unhandled exceptions.
- [ ] **No Secrets**: Ensure no API keys, private credentials, or personal tokens are committed.
- [ ] **Clean Git History**: Rebase against the latest `main` branch and avoid extraneous merge commits.
- [ ] **Ethical Compliance**: Verify that any modified scoring rules uphold the pedagogical decision-support requirement.
- [ ] **Screenshots / Video**: For UI changes, attach before-and-after screenshots or a short recording.

---

## 🏆 Hackathon Recognition

Every validated contributor during hackathon events will be:
- Credited in our official release notes and repository `CONTRIBUTORS.md`.
- Nominated for Hacktoberfest acceptance tags.
- Welcomed to join future research iterations on explainable academic integrity AI.

Happy hacking! Let's build ethical, transparent AI tools together. 🚀
