"""
EduVerify AI - Automated Evaluation Harness
============================================
Benchmarks the running EduVerify AI FastAPI backend against real, synthetic,
and edited document images.

Key Features:
  - Reads images from evaluation/images/ (or custom --input-dir).
  - Matches each image against evaluation/ground_truth.csv.
  - Sends multipart POST to /api/v1/analyze.
  - Saves raw JSON responses to evaluation/results/{image_id}_response.json.
  - Generates evaluation/results/evaluation_results.csv extracting all actual API fields.
  - Handles API failures gracefully and continues processing remaining images.

Usage:
    python run_evaluation.py [--api-url http://127.0.0.1:8000/api/v1/analyze]
                             [--input-dir ./images]
                             [--output-dir ./results]
                             [--limit 10]
                             [--timeout 60]
"""

import os
import sys
import csv
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import requests

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_GROUND_TRUTH = EVAL_DIR / "ground_truth.csv"
DEFAULT_INPUT_DIR = EVAL_DIR / "images"
DEFAULT_OUTPUT_DIR = EVAL_DIR / "results"
DEFAULT_API_URL = "http://127.0.0.1:8001/api/v1/analyze"
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def check_backend_connection(api_url: str) -> tuple[bool, Optional[str]]:
    """Verifies that the backend server is reachable before starting."""
    parsed = urlparse(api_url)
    health_url = f"{parsed.scheme}://{parsed.netloc}/health"
    try:
        r = requests.get(health_url, timeout=4)
        return r.status_code == 200, None
    except requests.exceptions.ConnectionError:
        return False, f"Connection refused at {parsed.netloc}. Is the FastAPI server running?"
    except Exception as e:
        return False, str(e)


def load_ground_truth(gt_path: Path) -> Dict[str, Dict[str, Any]]:
    """Loads ground_truth.csv indexed by file_name (lowercase)."""
    gt_map = {}
    if not gt_path.exists():
        print(f"[WARN] Ground truth file not found at {gt_path}. Proceeding without metadata matching.")
        return gt_map

    with open(gt_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = (row.get("file_name") or row.get("filename") or "").strip()
            if fname:
                gt_map[fname.lower()] = row
                img_id = row.get("image_id", "").strip()
                if img_id:
                    gt_map[img_id.lower()] = row
    return gt_map


def discover_images(input_dir: Path) -> List[Path]:
    """Finds all supported image files in input_dir and its subdirectories."""
    images = []
    if not input_dir.exists():
        return images

    for p in sorted(input_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS and not p.name.startswith("."):
            images.append(p)
    return images


def extract_response_fields(response_json: Dict[str, Any], ground_truth: Dict[str, Any],
                           image_path: Path, latency: float, http_status: int,
                           error_msg: str = "") -> Dict[str, Any]:
    """
    Extracts the actual response fields from the EduVerify AI backend API.
    Inspects response schema from api/services/fusion.py and raw_inputs.
    """
    signals = response_json.get("signals", {})
    raw_inputs = response_json.get("raw_inputs", {})
    
    # Raw module data blocks
    vision_data = raw_inputs.get("vision", {}).get("data", {})
    ocr_data = raw_inputs.get("ocr", {}).get("data", {})
    hw_data = raw_inputs.get("handwriting", {}).get("data", {})
    meta_data = raw_inputs.get("metadata", {}).get("data", {})

    # Visual synthetic score
    visual_synthetic_score = vision_data.get("visual_synthetic_score")
    if visual_synthetic_score is None:
        visual_synthetic_score = signals.get("visual", {}).get("score")

    # OCR extraction fields
    ocr_status = raw_inputs.get("ocr", {}).get("status", "unknown" if http_status == 200 else "error")
    ocr_extracted_text = ocr_data.get("extracted_text") or response_json.get("extracted_text", "")
    ocr_text_presence = bool(ocr_extracted_text and not ocr_extracted_text.startswith("ERROR:"))
    ocr_word_count = ocr_data.get("word_count", 0)
    ocr_confidence = ocr_data.get("confidence_score", 0.0)

    # Handwriting extraction fields
    hw_status = raw_inputs.get("handwriting", {}).get("status", "unknown" if http_status == 200 else "error")
    hw_text = hw_data.get("text", "")
    hw_text_presence = bool(hw_text and not hw_text.startswith("ERROR:"))
    hw_word_count = hw_data.get("word_count", 0)
    hw_conf_raw = hw_data.get("confidence", 0.0)
    hw_confidence = round(hw_conf_raw * 100, 2) if (hw_conf_raw and hw_conf_raw <= 1.0) else hw_conf_raw
    hw_detected = bool(hw_data.get("is_readable", False)) or ocr_text_presence

    # Fallback usage: If primary Qwen OCR failed/errored and secondary handwriting module was used
    primary_ocr_failed = not ocr_text_presence or str(ocr_extracted_text).startswith("ERROR:")
    fallback_usage = bool(primary_ocr_failed and hw_text_presence)

    # Text presence detection
    total_words = max(ocr_word_count, hw_word_count)
    no_text_detection = (total_words == 0) and not ocr_text_presence

    # Printed-text detection note: The current backend does not have an explicit typeface classifier
    printed_text_detection = "not_supported"

    return {
        "image_id": ground_truth.get("image_id", image_path.stem),
        "file_name": image_path.name,
        "category": ground_truth.get("category", image_path.parent.name),
        "true_label": ground_truth.get("true_label", "unknown"),
        "http_status": http_status,
        "response_time_seconds": round(latency, 3),
        "final_verdict": response_json.get("status", "error" if http_status != 200 else "unknown"),
        "status_label": response_json.get("statusLabel", ""),
        "conclusion": response_json.get("conclusion", ""),
        "confidence_score": response_json.get("confidenceScore", 0),
        "visual_synthetic_score": visual_synthetic_score if visual_synthetic_score is not None else "",
        "content_classification": response_json.get("conclusion", ""),
        "metadata_status": signals.get("metadata", {}).get("status", ""),
        "camera_make_model": meta_data.get("camera_make_model") or "",
        "software_used": meta_data.get("software_used") or "",
        "c2pa_status": signals.get("provenance", {}).get("status", "missing"),
        "ocr_status": ocr_status,
        "ocr_text_presence": ocr_text_presence,
        "ocr_word_count": ocr_word_count,
        "ocr_confidence": ocr_confidence,
        "handwriting_detection": hw_detected,
        "handwriting_transcription_status": hw_status,
        "handwriting_text_presence": hw_text_presence,
        "handwriting_word_count": hw_word_count,
        "handwriting_confidence": hw_confidence,
        "printed_text_detection": printed_text_detection,
        "no_text_detection": no_text_detection,
        "fallback_usage": fallback_usage,
        "error_message": error_msg or ("" if http_status == 200 else f"HTTP {http_status}")
    }


def run_evaluation(api_url: str, input_dir: Path, output_dir: Path,
                   limit: Optional[int] = None, timeout: int = 60,
                   ground_truth_path: Path = DEFAULT_GROUND_TRUTH,
                   in_process: bool = False):
    print("========================================================")
    print("         EduVerify AI - Automated Evaluation Harness    ")
    print("========================================================")
    print(f"Target Mode         : {'In-Process ASGI TestClient' if in_process else f'HTTP API ({api_url})'}")
    print(f"Input Images Dir    : {input_dir}")
    print(f"Output Results Dir  : {output_dir}")
    print(f"Request Timeout     : {timeout}s")
    if limit:
        print(f"Processing Limit    : {limit} images")
    print("--------------------------------------------------------\n")

    # 1. Backend Initialization / Connectivity Check
    client = None
    if in_process:
        backend_dir = Path(__file__).resolve().parent.parent
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        print("[SUCCESS] In-process FastAPI ASGI client initialized.\n")
    else:
        is_up, err_detail = check_backend_connection(api_url)
        if not is_up:
            print(f"[FATAL ERROR] Cannot connect to backend server!")
            print(f"Reason: {err_detail}\n")
            print("Please start the FastAPI backend server first:")
            print("  Option 1: Double-click run_project.bat from the repository root")
            print("  Option 2: Run in terminal:")
            print("            cd eduverify-ai/backend")
            print("            uvicorn main:app --port 8001 --reload\n")
            sys.exit(1)

        print("[SUCCESS] FastAPI backend is active and responsive.\n")

    # 2. Discover Images & Ground Truth
    gt_map = load_ground_truth(ground_truth_path)
    images = discover_images(input_dir)

    if not images:
        print(f"[INFO] No supported images found in '{input_dir}'.")
        print("To run benchmarks, place consented, de-identified images into:")
        print("  evaluation/images/real_photo/")
        print("  evaluation/images/real_scan/")
        print("  evaluation/images/ai_generated/")
        print("  evaluation/images/edited_real/")
        print("  evaluation/images/handwritten_clear/")
        print("  evaluation/images/handwritten_blurry/")
        print("  evaluation/images/printed_text/")
        print("  evaluation/images/no_text/\n")
        print("See evaluation/README.md for dataset and de-identification guidelines.")
        sys.exit(0)

    if limit and limit > 0:
        images = images[:limit]

    print(f"Discovered {len(images)} benchmark image(s) to process.\n")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_out_path = output_dir / "evaluation_results.csv"

    results_summary = []
    total_count = len(images)
    succeeded = 0
    failed = 0
    start_total_time = time.time()

    csv_fieldnames = [
        "image_id", "file_name", "category", "true_label", "http_status",
        "response_time_seconds", "final_verdict", "status_label", "conclusion",
        "confidence_score", "visual_synthetic_score", "content_classification",
        "metadata_status", "camera_make_model", "software_used", "c2pa_status",
        "ocr_status", "ocr_text_presence", "ocr_word_count", "ocr_confidence",
        "handwriting_detection", "handwriting_transcription_status",
        "handwriting_text_presence", "handwriting_word_count",
        "handwriting_confidence", "printed_text_detection", "no_text_detection",
        "fallback_usage", "error_message"
    ]

    for idx, img_path in enumerate(images, start=1):
        gt_info = gt_map.get(img_path.name.lower()) or gt_map.get(img_path.stem.lower()) or {}
        image_id = gt_info.get("image_id", img_path.stem)
        category = gt_info.get("category", img_path.parent.name)

        print(f"[{idx}/{total_count}] Processing [{category}] {img_path.name} (ID: {image_id}) ... ", end="", flush=True)

        t0 = time.time()
        http_status = 0
        response_json = {}
        error_msg = ""

        try:
            mime_type = f"image/{img_path.suffix.lstrip('.').lower()}"
            if mime_type == "image/jpg":
                mime_type = "image/jpeg"

            with open(img_path, "rb") as f:
                file_bytes = f.read()

            files = {"file": (img_path.name, file_bytes, mime_type)}
            if client is not None:
                r = client.post("/api/v1/analyze", files=files)
            else:
                r = requests.post(api_url, files=files, timeout=timeout)

            latency = time.time() - t0
            http_status = r.status_code

            if http_status == 200:
                response_json = r.json()
                succeeded += 1
                v = response_json.get("status", "unknown")
                w = response_json.get("raw_inputs", {}).get("ocr", {}).get("data", {}).get("word_count", 0)
                print(f"OK ({latency:.2f}s) -> Verdict: {v}, Words: {w}")
            else:
                failed += 1
                error_msg = f"HTTP {http_status}: {r.text[:120]}"
                response_json = {"error": error_msg, "status_code": http_status}
                print(f"FAIL ({latency:.2f}s) -> HTTP {http_status}")

        except requests.exceptions.Timeout:
            latency = time.time() - t0
            failed += 1
            error_msg = f"Request timed out after {timeout} seconds"
            response_json = {"error": error_msg}
            print(f"TIMEOUT ({latency:.2f}s)")
        except requests.exceptions.RequestException as e:
            latency = time.time() - t0
            failed += 1
            error_msg = str(e)
            response_json = {"error": error_msg}
            print(f"ERROR ({latency:.2f}s) -> {e}")

        # 1. Save raw JSON response as evaluation/results/{image_id}_response.json
        json_out_path = output_dir / f"{image_id}_response.json"
        with open(json_out_path, "w", encoding="utf-8") as jf:
            json.dump(response_json, jf, indent=2, ensure_ascii=False)

        # 2. Extract structured fields
        extracted_row = extract_response_fields(
            response_json=response_json,
            ground_truth=gt_info,
            image_path=img_path,
            latency=latency,
            http_status=http_status,
            error_msg=error_msg
        )
        results_summary.append(extracted_row)

    # 3. Create or update evaluation_results.csv
    with open(csv_out_path, mode="w", newline="", encoding="utf-8") as cf:
        writer = csv.DictWriter(cf, fieldnames=csv_fieldnames)
        writer.writeheader()
        writer.writerows(results_summary)

    total_time = time.time() - start_total_time
    print("\n========================================================")
    print("               Evaluation Run Finished                  ")
    print("========================================================")
    print(f"Total Submissions Evaluated : {total_count}")
    print(f"Successful Analyses         : {succeeded}")
    print(f"Failed / Errored Requests   : {failed}")
    print(f"Total Wall Time             : {total_time:.2f}s")
    print(f"Raw JSON Responses Saved    : {output_dir}/*_response.json")
    print(f"Metrics CSV Saved           : {csv_out_path}")
    print("========================================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EduVerify AI Automated Evaluation Harness")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"Backend analysis endpoint URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help=f"Directory containing test image categories (default: {DEFAULT_INPUT_DIR})")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Directory to save JSON responses and CSV (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of images to evaluate (default: all)")
    parser.add_argument("--timeout", type=int, default=60, help="Per-request HTTP timeout in seconds (default: 60)")
    parser.add_argument("--in-process", action="store_true", help="Run evaluation directly in-process via FastAPI TestClient (no HTTP server required)")

    args = parser.parse_args()

    run_evaluation(
        api_url=args.api_url,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        limit=args.limit,
        timeout=args.timeout,
        in_process=args.in_process
    )
