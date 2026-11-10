"""
EduVerify AI - Automated Evaluation Harness
============================================
Discovers all benchmark images in evaluation/images/*, sends them to
the FastAPI analyze endpoint (POST /api/v1/analyze), and persists
raw JSON results into evaluation/results/.

Usage:
    python run_evaluation.py [--url http://localhost:8000] [--category <cat>]
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
import requests

EVAL_DIR = Path(__file__).resolve().parent
IMAGES_DIR = EVAL_DIR / "images"
RESULTS_DIR = EVAL_DIR / "results"
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def check_backend_health(base_url: str) -> bool:
    """Checks if the FastAPI backend is responsive."""
    health_url = f"{base_url.rstrip('/')}/health"
    try:
        r = requests.get(health_url, timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def run_benchmarks(base_url: str = "http://localhost:8000", target_category: str = None):
    endpoint = f"{base_url.rstrip('/')}/api/v1/analyze"
    print(f"=== EduVerify AI Evaluation Harness ===")
    print(f"Backend Target: {endpoint}")

    if not check_backend_health(base_url):
        print(f"[ERROR] Cannot connect to backend at {base_url}.")
        print("Please start the FastAPI server first:")
        print("    cd ../ && uvicorn main:app --port 8000 --reload")
        sys.exit(1)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Discover images across all category folders
    image_files = []
    for cat_dir in sorted(IMAGES_DIR.iterdir()):
        if cat_dir.is_dir():
            if target_category and cat_dir.name.lower() != target_category.lower():
                continue
            for img_path in sorted(cat_dir.iterdir()):
                if img_path.suffix.lower() in SUPPORTED_EXTS and not img_path.name.startswith("."):
                    image_files.append((cat_dir.name, img_path))

    if not image_files:
        print(f"[INFO] No test images found in {IMAGES_DIR}.")
        print("Please place consented, de-identified test images into the appropriate category folder:")
        for cat_dir in sorted(IMAGES_DIR.iterdir()):
            if cat_dir.is_dir():
                print(f"  - images/{cat_dir.name}/")
        print("\nSee evaluation/README.md for dataset guidelines.")
        return

    print(f"Discovered {len(image_files)} test image(s) for evaluation.\n")
    succeeded = 0
    failed = 0
    start_time = time.time()

    for idx, (cat_name, img_path) in enumerate(image_files, start=1):
        rel_path = img_path.relative_to(EVAL_DIR)
        print(f"[{idx}/{len(image_files)}] Processing [{cat_name}] {img_path.name} ... ", end="", flush=True)

        req_start = time.time()
        try:
            with open(img_path, "rb") as f:
                files = {"file": (img_path.name, f, f"image/{img_path.suffix.lstrip('.')}")}
                response = requests.post(endpoint, files=files, timeout=120)

            latency = round(time.time() - req_start, 2)

            if response.status_code == 200:
                result_data = response.json()
                out_path = RESULTS_DIR / f"{img_path.stem}.json"
                with open(out_path, "w", encoding="utf-8") as out_f:
                    json.dump(result_data, out_f, indent=2, ensure_ascii=False)
                
                status_label = result_data.get("status", "unknown")
                word_count = result_data.get("raw_inputs", {}).get("ocr", {}).get("data", {}).get("word_count", 0)
                print(f"OK ({latency}s) -> Status: {status_label}, Words: {word_count}")
                succeeded += 1
            else:
                print(f"FAIL (HTTP {response.status_code}, {latency}s)")
                err_path = RESULTS_DIR / f"{img_path.stem}_error.json"
                with open(err_path, "w", encoding="utf-8") as err_f:
                    json.dump({"status_code": response.status_code, "text": response.text}, err_f, indent=2)
                failed += 1

        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

    total_time = round(time.time() - start_time, 2)
    print("\n=== Evaluation Run Complete ===")
    print(f"Total Images: {len(image_files)} | Succeeded: {succeeded} | Failed: {failed}")
    print(f"Total Execution Time: {total_time}s")
    print(f"Results saved to: {RESULTS_DIR}")
    print("Run `python calculate_metrics.py` to generate the evaluation report.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run EduVerify AI Evaluation Harness")
    parser.add_argument("--url", default="http://localhost:8000", help="FastAPI backend base URL (default: http://localhost:8000)")
    parser.add_argument("--category", default=None, help="Filter by specific image category (e.g. real_photo, handwritten_clear)")
    args = parser.parse_args()

    run_benchmarks(base_url=args.url, target_category=args.category)

