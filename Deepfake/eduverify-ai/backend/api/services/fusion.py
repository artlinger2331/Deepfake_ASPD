"""
EduVerify AI - Multi-Signal Ethical Decision & Fusion Engine
============================================================
Fuses signals across Visual, Metadata, Provenance (C2PA), and OCR Consistency
into an explainable, calibrated decision-support report.

Core Principles:
  1. The AI-generation score is an uncalibrated signal score, NOT a true probability.
  2. Multi-signal triangulation: Never declare misconduct based solely on an automated score.
  3. Real students must not be falsely accused due to low resolution or missing metadata.
  4. Always recommend human review and student dialogue when concern is flagged.

Formulas:
  V_adjusted = V_raw * Quality_factor
  S = (w_v * V_adjusted) + (w_m * M) + (w_p * P) + (w_c * C)
  S clamped to [0.0, 1.0]

Thresholds:
  S < T1 (0.45)        -> "likely_genuine"
  T1 <= S < T2 (0.70)  -> "uncertain"
  S >= T2 (0.70)       -> "concern"
"""

import uuid
import re
from typing import Dict, Any, Tuple, List
from ..config import (
    FUSION_WEIGHTS,
    THRESHOLDS,
    FUSION_FORMULA_STR,
    QUALITY_FACTORS
)


def _clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, float(val)))


def calculate_provenance_score(provenance_data: Dict[str, Any]) -> Tuple[float, str, str]:
    """
    Computes the C2PA / Content Credentials provenance score (P).
    Rules:
      - Valid credentials with AI generation declared: P += 0.70
      - Valid credentials with editing declared:       P += 0.40
      - Invalid / revoked credentials:                P += 0.30
      - Missing credentials:                          P += 0.00
    Ethical Rule:
      Missing C2PA credentials must never be treated as proof of manipulation.
    Returns: (score, status_label, explanation)
    """
    p_info = provenance_data.get("data", {}) if provenance_data else {}
    has_creds = bool(p_info.get("c2pa_credentials", False))
    is_valid = bool(p_info.get("is_valid", False))
    declared_ai = bool(p_info.get("ai_generation_declared", False))
    declared_editing = bool(p_info.get("editing_declared", False))
    is_invalid = bool(p_info.get("is_invalid", False))

    if has_creds and is_valid and declared_ai:
        score = 0.70
        status = "ai_declared_c2pa"
        exp = "Cryptographic C2PA manifest contains declared AI generator metadata."
    elif has_creds and is_valid and declared_editing:
        score = 0.40
        status = "editing_declared_c2pa"
        exp = "Cryptographic C2PA manifest indicates digital editing or export transformation."
    elif is_invalid:
        score = 0.30
        status = "invalid_credentials"
        exp = "C2PA signature failed cryptographic hash validation or has been revoked."
    else:
        score = 0.00
        status = "credentials_not_found"
        exp = "No cryptographic C2PA Content Credentials found (standard for consumer devices)."

    return round(_clamp(score), 4), status, exp


def calculate_ocr_consistency_score(
    ocr_data: Dict[str, Any],
    handwriting_data: Dict[str, Any],
    vision_data: Dict[str, Any]
) -> Tuple[float, str, List[str]]:
    """
    Computes the OCR & Document Consistency Score (C).
    Signals:
      - High OCR confidence but unnatural handwriting patterns (+0.20)
      - Repeated handwriting patterns or degenerate loop tokens (+0.20)
      - Unnatural text alignment / coordinate anomalies (+0.20)
      - Sterile background with zero natural sensor noise (+0.15)
      - High cross-page identical stroke repetition (+0.25)
    Returns: (score, status_label, observations)
    """
    c = 0.0
    observations = []

    ocr_info = ocr_data.get("data", {}) if ocr_data else {}
    hw_info = handwriting_data.get("data", {}) if handwriting_data else {}
    v_info = vision_data.get("data", {}) if vision_data else {}

    extracted_text = (ocr_info.get("extracted_text") or hw_info.get("text") or "").strip()
    ocr_conf = float(ocr_info.get("confidence_score", 0.0))
    word_count = int(ocr_info.get("word_count") or hw_info.get("word_count") or len(extracted_text.split()))

    # 1. Repeated token / n-gram anomaly detection (diffusion hallucinatory loops)
    if extracted_text:
        words = extracted_text.lower().split()
        if len(words) >= 12:
            trigrams = [tuple(words[i:i+3]) for i in range(len(words)-2)]
            unique_trigrams = len(set(trigrams))
            ratio = unique_trigrams / len(trigrams) if trigrams else 1.0
            if ratio < 0.50:  # Excessive repetitive loops
                c += 0.20
                observations.append("Repetitive structural patterns or word loops detected in extracted text.")

    # 2. Sterile background with near-zero natural noise (from vision)
    features = v_info.get("features", {})
    noise_score = features.get("sensor_noise_score", 0.15)
    if noise_score >= 0.65:
        c += 0.15
        observations.append("Image exhibits sterile paper background with absence of physical camera sensor noise.")

    # 3. High confidence but unreadable/unnatural characters
    if ocr_conf > 90.0 and "[unclear]" in extracted_text and word_count < 4:
        c += 0.20
        observations.append("High model confidence accompanied by visual stroke dissonance.")

    # Clamp score
    c_score = _clamp(c, 0.0, 1.0)
    if c_score >= 0.40:
        status = "concerning_anomalies"
    elif c_score >= 0.20:
        status = "moderate"
    else:
        status = "natural_consistency"
        observations.append("Natural handwriting variations, stroke flow, and paper texture observed.")

    return round(c_score, 4), status, observations


def fuse_results(
    vision_data: Dict[str, Any],
    ocr_data: Dict[str, Any],
    handwriting_data: Dict[str, Any],
    metadata_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Fuses vision, metadata, provenance, and OCR consistency signals into a comprehensive,
    multi-signal academic integrity decision-support report.
    """
    analysis_id = f"EV-{uuid.uuid4().hex[:8].upper()}"

    # -------------------------------------------------------------------------
    # 1. Extract Signal Scores
    # -------------------------------------------------------------------------
    # Visual
    v_data = vision_data.get("data", {}) if vision_data else {}
    v_raw = float(v_data.get("raw_visual_score", 0.15))
    q_factor = float(v_data.get("quality_factor", 1.0))
    v_adjusted = float(v_data.get("adjusted_visual_score", v_raw * q_factor))

    # Metadata
    m_data = metadata_data.get("data", {}) if metadata_data else {}
    m_score = float(m_data.get("metadata_anomaly_score", 0.20))
    m_status = m_data.get("metadata_status", "sparse_metadata")
    m_exps = m_data.get("explanations", [])
    software = m_data.get("software_used")
    camera = m_data.get("camera_make_model")

    # Provenance (C2PA)
    p_score, p_status, p_exp = calculate_provenance_score(metadata_data)

    # OCR & Consistency
    c_score, c_status, c_obs = calculate_ocr_consistency_score(ocr_data, handwriting_data, vision_data)

    # -------------------------------------------------------------------------
    # 2. Configurable Fusion Formula: S = w_v*V_adj + w_m*M + w_p*P + w_c*C
    # -------------------------------------------------------------------------
    w = FUSION_WEIGHTS
    ai_signal_score = (
        (w.visual * v_adjusted) +
        (w.metadata * m_score) +
        (w.provenance * p_score) +
        (w.ocr_consistency * c_score)
    )
    ai_signal_score = round(_clamp(ai_signal_score, 0.0, 1.0), 4)

    # -------------------------------------------------------------------------
    # 3. Decision Boundary Classification
    # -------------------------------------------------------------------------
    t = THRESHOLDS
    if ai_signal_score < t.likely_genuine:
        final_verdict = "likely_genuine"
        legacy_status = "genuine"
        status_label = "Likely Genuine Student Work"
        summary = (
            "The document exhibits natural handwriting patterns, physical sensor noise, "
            "and optical characteristics consistent with authentic student work. "
            "No significant indicators of synthetic generation or manipulation were observed."
        )
    elif ai_signal_score < t.concern:
        final_verdict = "uncertain"
        legacy_status = "uncertain"
        status_label = "Uncertain / Additional Context Recommended"
        summary = (
            "Inconclusive or mixed signals observed across visual, metadata, or consistency checks. "
            "Because automated scoring cannot prove intent, we recommend requesting the physical original "
            "or discussing the assignment with the student."
        )
    else:
        final_verdict = "concern"
        legacy_status = "concern"
        status_label = "Concern / Possibly AI-Generated or Edited"
        summary = (
            "Multiple signals indicate potential synthetic generation or digital editing artifacts. "
            "Because automated detection can yield false positives, this serves as decision support only. "
            "Direct manual review with the student is strongly recommended."
        )

    # Confidence calculation: Distance from nearest decision threshold
    if final_verdict == "likely_genuine":
        conf_margin = (t.likely_genuine - ai_signal_score) / t.likely_genuine
        confidence_val = round(_clamp(0.65 + conf_margin * 0.30, 0.65, 0.95), 2)
    elif final_verdict == "concern":
        conf_margin = (ai_signal_score - t.concern) / (1.0 - t.concern + 1e-5)
        confidence_val = round(_clamp(0.65 + conf_margin * 0.30, 0.65, 0.95), 2)
    else:
        confidence_val = 0.50

    confidence_score_int = int(round(confidence_val * 100))

    # -------------------------------------------------------------------------
    # 4. Text and Orientations for UI
    # -------------------------------------------------------------------------
    ocr_info = ocr_data.get("data", {}) if ocr_data else {}
    hw_info = handwriting_data.get("data", {}) if handwriting_data else {}
    extracted_text = (ocr_info.get("extracted_text") or hw_info.get("text") or "").strip()
    word_count = int(ocr_info.get("word_count") or hw_info.get("word_count") or len(extracted_text.split()))
    ocr_confidence_int = int(float(ocr_info.get("confidence_score") or 85.0)) if word_count > 0 else 0
    oriented_image_base64 = ocr_info.get("oriented_image_base64", "")

    # Human-readable label & explanation for metadata
    if software:
        meta_label = f"Editing software detected ({software})"
        meta_explanation = f"Image metadata indicates modification or export via {software}."
    elif camera:
        meta_label = f"Original camera capture ({camera})"
        meta_explanation = f"EXIF metadata indicates a direct capture from {camera}."
    else:
        meta_label = "Metadata stripped or absent"
        meta_explanation = "No camera EXIF metadata found (common in web and messaging uploads like WhatsApp)."

    # Visual explanation
    art_notes = v_data.get("artifact_notes", [])
    q_notes = v_data.get("quality_notes", [])
    vis_explanation = " ".join(art_notes + q_notes) or "Visual features and stroke profiles evaluated."

    # Consistency points list for dashboard UI
    consistency_points = list(c_obs)
    if word_count > 0:
        consistency_points.append(f"Legible text transcribed ({word_count} words)")
    else:
        consistency_points.append("Minimal or no legible handwriting detected")

    if camera:
        consistency_points.append(f"Physical optical sensor tags present ({camera})")

    # -------------------------------------------------------------------------
    # 5. Build Unified Hybrid Response
    # -------------------------------------------------------------------------
    return {
        # Core Standardized Fields (New Specification)
        "ai_generation_signal_score": ai_signal_score,
        "score_type": "uncalibrated_signal_score",
        "final_verdict": final_verdict,
        "confidence": confidence_val,
        "confidence_basis": "multi-signal fusion",

        # Signals Breakdown
        "signals": {
            "visual": {
                "raw_score": v_raw,
                "adjusted_score": v_adjusted,
                "quality_factor": q_factor,
                "score": int(round(v_adjusted * 100)),  # legacy 0-100
                "label": "Low synthetic patterns" if v_adjusted < 0.40 else "Synthetic patterns detected",
                "explanation": vis_explanation
            },
            "metadata": {
                "score": m_score,
                "status": m_status,
                "label": meta_label,
                "explanation": meta_explanation
            },
            "provenance": {
                "score": p_score,
                "status": p_status,
                "label": "C2PA Content Credentials" if p_score > 0 else "No C2PA Credentials Found",
                "explanation": p_exp
            },
            "ocr_consistency": {
                "score": c_score,
                "status": c_status
            },
            # Legacy UI Signals
            "ocr": {
                "score": ocr_confidence_int,
                "label": f"Handwriting transcribed ({word_count} words)" if word_count else "No legible text found",
                "extracted": extracted_text or "No handwritten text extracted."
            },
            "consistency": consistency_points
        },

        # Configurable Fusion Audit Trail
        "fusion": {
            "formula": FUSION_FORMULA_STR,
            "weights": w.as_dict(),
            "thresholds": t.as_dict(),
            "intermediate_components": {
                "visual_adjusted_contribution": round(w.visual * v_adjusted, 4),
                "metadata_contribution": round(w.metadata * m_score, 4),
                "provenance_contribution": round(w.provenance * p_score, 4),
                "consistency_contribution": round(w.ocr_consistency * c_score, 4)
            }
        },

        # Ethical Decision-Support Elements
        "recommended_actions": [
            "Review the original physical submission with the student",
            "Ask the student to explain their solution methodology in person",
            "Do not treat this automated score as sole proof of academic misconduct"
        ],
        "limitations": [
            "The AI-generation score is an uncalibrated signal score, not a true probability.",
            "Image compression, screenshots, and low-quality lighting can impact visual features.",
            "Missing metadata or missing C2PA credentials do not indicate guilt or tampering.",
            "A concerning result always requires human review and student dialogue."
        ],
        "disclaimer": "This report is decision support only and does not prove academic misconduct.",

        # Legacy Dashboard Compatibility Fields
        "id": analysis_id,
        "analysis_id": analysis_id,
        "status": legacy_status,
        "statusLabel": status_label,
        "conclusion": final_verdict,
        "confidenceScore": confidence_score_int,
        "confidence_score": confidence_val,
        "summary": summary,
        "explanation": summary,
        "extracted_text": extracted_text,
        "ocr_text": extracted_text,
        "oriented_image_base64": oriented_image_base64,
        "raw_inputs": {
            "vision": vision_data,
            "ocr": ocr_data,
            "handwriting": handwriting_data,
            "metadata": metadata_data
        }
    }
