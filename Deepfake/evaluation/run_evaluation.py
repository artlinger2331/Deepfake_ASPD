#!/usr/bin/env python3
"""
EduVerify AI - End-to-End Evaluation Runner
===========================================
Submits evaluation benchmark images to the live FastAPI /api/v1/analyze endpoint,
logs raw responses as individual JSON artifacts, and generates a structured
evaluation_results.csv for statistical metrics calculation.
"""

import os
import sys
import time
import json
import csv
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' library is required. Install via: pip install requests")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="EduVerify AI System Evaluation Runner")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the FastAPI backend (default: http://127.0.0.1:8000)"
    )
    parser.add_argument(
        "--input-dir",
        default="images",
        help="Directory containing categorized subfolders of images (default: images)"
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Directory to save raw JSON responses and results CSV (default: results)"
    )
    parser.add_argument(
        "--ground-truth",
        default="ground_truth.csv",
        help="Path to ground_truth.csv annotations file (default: ground_truth.csv)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of images to evaluate"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="HTTP request timeout in seconds per image (default: 90s)"
    )
    return parser.parse_args()


def check_backend_health(base_url: str, timeout: int = 5) -> bool:
    """Verifies that the FastAPI server is reachable and responsive."""
    health_url = f"{base_url.rstrip('/')}/health"
    docs_url = f"{base_url.rstrip('/')}/docs"
    try:
        r = requests.get(health_url, timeout=timeout)
        if r.status_code == 200:
            return True
    except requests.RequestException:
        pass

    try:
        r = requests.get(docs_url, timeout=timeout)
        if r.status_code == 200:
            return True
    except requests.RequestException:
        return False
    return False


def load_ground_truth(csv_path: Path) -> Dict[str, Dict[str, str]]:
    """Loads ground truth metadata indexed by image_id and file_name."""
    ground_truth = {}
    if not csv_path.exists():
        print(f"[WARNING] Ground truth file not found at: {csv_path}")
        return ground_truth

    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            img_id = row.get("image_id", "").strip()
            fname = row.get("file_name", "").strip()
            if img_id:
                ground_truth[img_id] = row
            if fname and fname not in ground_truth:
                ground_truth[fname] = row
    return ground_truth


def find_evaluation_images(input_dir: Path, ground_truth: Dict[str, Dict[str, str]]):
    """Discovers all evaluation images inside categorized subdirectories."""
    images = []
    supported_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

    if not input_dir.exists():
        print(f"[ERROR] Input directory not found: {input_dir}")
        return images

    # Scan recursive directories
    for path in sorted(input_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in supported_extensions:
            file_name = path.name
            parent_cat = path.parent.name

            # Match against ground truth by filename or stem
            gt_info = ground_truth.get(file_name) or ground_truth.get(path.stem)
            image_id = gt_info.get("image_id", path.stem) if gt_info else path.stem
            true_label = gt_info.get("true_label", parent_cat) if gt_info else parent_cat
            category = gt_info.get("category", parent_cat) if gt_info else parent_cat

            images.append({
                "image_id": image_id,
                "file_name": file_name,
                "file_path": path,
                "true_label": true_label,
                "category": category,
                "gt_info": gt_info or {}
            })
    return images


def evaluate_single_image(api_url: str, image_item: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """Posts a single image to the API endpoint and records performance metrics."""
    endpoint = f"{api_url.rstrip('/')}/api/v1/analyze"
    img_path = image_item["file_path"]
    img_id = image_item["image_id"]
    true_label = image_item["true_label"]

    result = {
        "image_id": img_id,
        "file_name": image_item["file_name"],
        "true_label": true_label,
        "predicted_verdict": "error",
        "confidence": 0.0,
        "visual_synthetic_score": 0.0,
        "content_classification": "unknown",
        "metadata_status": "unknown",
        "c2pa_status": "unknown",
        "ocr_status": "failed",
        "ocr_word_count": 0,
        "ocr_confidence": 0.0,
        "handwriting_transcription_status": "failed",
        "handwriting_word_count": 0,
        "handwriting_confidence": 0.0,
        "is_readable": False,
        "fallback_used": False,
        "response_time_seconds": 0.0,
        "error_message": "",
        "raw_json": None
    }

    start_time = time.time()
    try:
        with open(img_path, "rb") as f:
            files = {"file": (image_item["file_name"], f, "image/jpeg")}
            response = requests.post(endpoint, files=files, timeout=timeout)

        elapsed = time.time() - start_time
        result["response_time_seconds"] = round(elapsed, 3)

        if response.status_code == 200:
            data = response.json()
            result["raw_json"] = data

            # Extract final verdicts
            result["predicted_verdict"] = data.get("status") or data.get("conclusion") or "unknown"
            result["confidence"] = float(data.get("confidence_score") or data.get("confidenceScore") or 0.0)
            result["content_classification"] = data.get("conclusion") or data.get("statusLabel") or "unknown"

            # Signals
            signals = data.get("signals", {})
            vis_sig = signals.get("visual", {})
            meta_sig = signals.get("metadata", {})
            prov_sig = signals.get("provenance", {})
            ocr_sig = signals.get("ocr", {})

            # Visual Synthetic Score
            raw_vis = data.get("raw_inputs", {}).get("vision", {}).get("data", {})
            raw_v_score = raw_vis.get("visual_synthetic_score")
            if raw_v_score is not None:
                result["visual_synthetic_score"] = round(float(raw_v_score), 4)
            elif vis_sig.get("score") is not None:
                result["visual_synthetic_score"] = round(float(vis_sig.get("score")) / 100.0, 4)

            # Metadata & C2PA status
            result["metadata_status"] = meta_sig.get("status") or "unknown"
            result["c2pa_status"] = prov_sig.get("status") or "missing"

            # OCR / Handwriting extraction
            raw_ocr = data.get("raw_inputs", {}).get("ocr", {}).get("data", {})
            raw_hw = data.get("raw_inputs", {}).get("handwriting", {}).get("data", {})

            ocr_text = raw_ocr.get("extracted_text") or data.get("extracted_text") or ""
            ocr_words = raw_ocr.get("word_count", len(ocr_text.split()))
            ocr_conf = raw_ocr.get("confidence_score", 0.0)

            result["ocr_status"] = "success" if ocr_words > 0 else ("empty" if ocr_text else "failed")
            result["ocr_word_count"] = int(ocr_words)
            result["ocr_confidence"] = round(float(ocr_conf), 2)

            hw_text = raw_hw.get("text") or ocr_text
            hw_words = raw_hw.get("word_count", ocr_words)
            hw_conf = raw_hw.get("confidence", ocr_conf / 100.0 if ocr_conf > 1.0 else ocr_conf)

            result["handwriting_transcription_status"] = "success" if hw_words > 0 else "empty"
            result["handwriting_word_count"] = int(hw_words)
            result["handwriting_confidence"] = round(float(hw_conf) * 100 if float(hw_conf) <= 1.0 else float(hw_conf), 2)
            result["is_readable"] = bool(raw_ocr.get("is_readable", ocr_words > 0))

            # Detect if TrOCR or secondary fallback occurred
            hw_module_status = data.get("raw_inputs", {}).get("handwriting", {}).get("status")
            if ocr_text.startswith("ERROR:") or not ocr_text:
                result["fallback_used"] = True
            else:
                result["fallback_used"] = False

        else:
            result["error_message"] = f"HTTP {response.status_code}: {response.text[:200]}"
            print(f"  [FAIL] {img_id}: HTTP {response.status_code}")

    except Exception as e:
        elapsed = time.time() - start_time
        result["response_time_seconds"] = round(elapsed, 3)
        result["error_message"] = str(e)
        print(f"  [ERROR] {img_id}: {str(e)}")

    return result


def main():
    args = parse_args()
    script_dir = Path(__file__).resolve().parent

    input_dir = (script_dir / args.input_dir).resolve()
    output_dir = (script_dir / args.output_dir).resolve()
    gt_path = (script_dir / args.ground_truth).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    results_csv_path = output_dir / "evaluation_results.csv"

    print("==========================================================")
    print("           EduVerify AI - Evaluation Runner               ")
    print("==========================================================")
    print(f"API Target Endpoint: {args.api_url}/api/v1/analyze")
    print(f"Input Directory:     {input_dir}")
    print(f"Output Directory:    {output_dir}")
    print(f"Ground Truth File:   {gt_path}")
    print("----------------------------------------------------------")

    # Step 1: Health check
    print("[1/4] Checking backend connectivity...")
    if not check_backend_health(args.api_url):
        print(f"[FATAL] Backend is not reachable at: {args.api_url}")
        print("Please start the FastAPI backend server first:")
        print("  Windows:  .\\run_project.bat")
        print("  Manual:   cd Deepfake\\eduverify-ai\\backend && python -m uvicorn main:app --port 8000 --reload")
        sys.exit(1)
    print("      Backend is online and accepting requests.")

    # Step 2: Load ground truth
    print("[2/4] Loading ground truth annotations...")
    ground_truth = load_ground_truth(gt_path)
    print(f"      Loaded annotations for {len(ground_truth)} entries.")

    # Step 3: Discover images
    print("[3/4] Scanning evaluation dataset images...")
    images = find_evaluation_images(input_dir, ground_truth)
    if not images:
        print(f"[ERROR] No evaluation images found in {input_dir}")
        print("Please place images into evaluation/images/ subdirectories (e.g., real_photo/, difficult_real/).")
        sys.exit(1)

    if args.limit and args.limit > 0:
        images = images[:args.limit]
    print(f"      Found {len(images)} images scheduled for evaluation.")

    # Step 4: Execute evaluation
    print("[4/4] Executing forensic analysis against live API...")
    fieldnames = [
        "image_id",
        "file_name",
        "true_label",
        "predicted_verdict",
        "confidence",
        "visual_synthetic_score",
        "content_classification",
        "metadata_status",
        "c2pa_status",
        "ocr_status",
        "ocr_word_count",
        "ocr_confidence",
        "handwriting_transcription_status",
        "handwriting_word_count",
        "handwriting_confidence",
        "is_readable",
        "fallback_used",
        "response_time_seconds",
        "error_message"
    ]

    all_results = []
    for idx, item in enumerate(images, start=1):
        img_id = item["image_id"]
        print(f"  [{idx}/{len(images)}] Evaluating {img_id} ({item['category']})...", end="", flush=True)

        res = evaluate_single_image(args.api_url, item, args.timeout)
        all_results.append(res)

        # Save individual raw JSON
        if res.get("raw_json"):
            json_file = output_dir / f"{img_id}_response.json"
            with open(json_file, "w", encoding="utf-8") as jf:
                json.dump(res["raw_json"], jf, indent=2)

        verdict = res["predicted_verdict"]
        latency = res["response_time_seconds"]
        print(f" Done ({latency}s) -> Verdict: {verdict}")

    # Write summary results CSV
    with open(results_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            row_dict = {k: r.get(k, "") for k in fieldnames}
            writer.writerow(row_dict)

    print("----------------------------------------------------------")
    print(f"[SUCCESS] Evaluation complete!")
    print(f"  Results saved to: {results_csv_path}")
    print(f"  Individual JSON responses saved in: {output_dir}")
    print("Run calculate_metrics.py to compute performance metrics and generate report.")


if __name__ == "__main__":
    main()
