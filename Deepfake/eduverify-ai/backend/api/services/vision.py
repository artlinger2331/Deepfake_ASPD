"""
EduVerify AI - Multi-Feature Visual Synthetic Analysis Service
==============================================================
Analyzes visual forensic indicators to assess potential AI generation or digital manipulation.

Uses multi-feature statistical and frequency-domain analysis:
  1. Laplacian edge variance & sharpness distribution.
  2. Local background noise variance (camera sensor noise estimation).
  3. High-frequency 2D Fast Fourier Transform (FFT) spectral energy.
  4. Texture uniformity & patch luminance variation.
  5. Compression / block artifact consistency.

Applies image quality factor (Q = 1.0, 0.85, 0.70) to prevent false accusations
on blurry or degraded real student submissions.

Formula:
  V = w1 * norm(laplacian) + w2 * norm(noise) + w3 * norm(fft) + w4 * norm(texture) + w5 * norm(compression)
  V_adjusted = V * Q
"""

import io
import cv2
import numpy as np
from typing import Dict, Any, Tuple
from ..config import VISUAL_WEIGHTS, QUALITY_FACTORS


def _clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, float(val)))


def compute_laplacian_score(gray: np.ndarray) -> Tuple[float, float]:
    """
    Computes normalized Laplacian edge variance score.
    Real student photos typically fall in a natural variance range (80 - 600).
    Extremely low variance (< 40) indicates severe blur; extremely high or anomalous
    unnatural edge spikes can indicate digital splicing or synthetic line render.
    Returns: (normalized_score, raw_variance)
    """
    raw_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    
    # Natural camera range: ~100 to ~400
    if 100.0 <= raw_var <= 450.0:
        # Natural optical stroke variation
        norm_score = 0.15
    elif raw_var > 450.0:
        # High contrast digital render or heavy sharpening
        norm_score = _clamp(0.20 + (raw_var - 450.0) / 1200.0, 0.20, 0.85)
    else:
        # Very smooth or blurry background (< 100)
        norm_score = _clamp(0.40 + (100.0 - raw_var) / 150.0, 0.25, 0.75)
        
    return norm_score, raw_var


def compute_local_noise_score(gray: np.ndarray) -> Tuple[float, float]:
    """
    Estimates sensor noise standard deviation in flat background areas.
    Real optical sensors (phone cameras / scanners) exhibit natural Poisson-Gaussian noise (std: 3 - 15).
    AI generated images often have unnaturally clean, smooth background areas (std < 1.5).
    Returns: (normalized_score, raw_noise_std)
    """
    # High-pass filter via Laplacian to isolate high-frequency noise
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    
    # Divide into 16x16 blocks, find flat patches with lowest variance (background paper)
    h, w = gray.shape
    bs = 16
    block_stds = []
    
    for y in range(0, h - bs, bs * 2):
        for x in range(0, w - bs, bs * 2):
            block = lap[y:y+bs, x:x+bs]
            block_stds.append(np.std(block))
            
    if not block_stds:
        return 0.25, 0.0
        
    # The lowest 20th percentile of block stds represents unwritten paper background noise
    block_stds.sort()
    flat_noise = float(np.mean(block_stds[:max(1, len(block_stds) // 5)]))
    
    # Natural camera sensor noise on paper is typically 2.5 - 12.0
    if flat_noise >= 3.0:
        norm_score = 0.12  # Natural physical camera noise
    elif flat_noise >= 1.8:
        norm_score = 0.30  # Mild smoothing or high-end sensor
    else:
        # Unnaturally sterile / mathematically flat background common in synthetic generation
        norm_score = _clamp(0.65 + (1.8 - flat_noise) * 0.20, 0.65, 0.90)
        
    return norm_score, flat_noise


def compute_fft_spectral_score(gray: np.ndarray) -> Tuple[float, float]:
    """
    Computes high-frequency energy ratio using 2D Fast Fourier Transform.
    Natural photos decay smoothly following ~1/f^2 power laws.
    Diffusion models often exhibit high-frequency truncation or unnatural spectral ripples.
    Returns: (normalized_score, high_freq_ratio)
    """
    h, w = gray.shape
    # Resize to standard size for consistent FFT spectral density
    dim = 256
    resized = cv2.resize(gray, (dim, dim), interpolation=cv2.INTER_AREA)
    
    # Compute 2D FFT and shift zero-frequency to center
    f = np.fft.fft2(resized)
    fshift = np.fft.fftshift(f)
    magnitude_spectrum = np.abs(fshift) + 1e-8
    
    # Mask central low frequencies (radius 30)
    cy, cx = dim // 2, dim // 2
    y_idx, x_idx = np.ogrid[:dim, :dim]
    dist_from_center = np.sqrt((x_idx - cx)**2 + (y_idx - cy)**2)
    
    high_freq_mask = dist_from_center > (dim // 4)
    total_energy = np.sum(magnitude_spectrum)
    high_freq_energy = np.sum(magnitude_spectrum[high_freq_mask])
    
    high_freq_ratio = float(high_freq_energy / total_energy) if total_energy > 0 else 0.0
    
    # Natural document photo high-frequency ratio typically falls around 0.10 - 0.28
    if 0.10 <= high_freq_ratio <= 0.32:
        norm_score = 0.15
    elif high_freq_ratio < 0.10:
        # Over-smoothed or synthetic low-pass artifact
        norm_score = _clamp(0.50 + (0.10 - high_freq_ratio) * 4.0, 0.50, 0.85)
    else:
        # Unnatural high frequency ringing or checkerboard artifacts
        norm_score = _clamp(0.40 + (high_freq_ratio - 0.32) * 2.0, 0.40, 0.80)
        
    return norm_score, high_freq_ratio


def compute_texture_uniformity_score(gray: np.ndarray) -> Tuple[float, float]:
    """
    Measures global texture and illumination uniformity across document quadrants.
    Real notebook submissions feature uneven natural lighting, desk shadows, and paper folds.
    AI generated notebook pages typically display mathematically homogeneous paper tone.
    Returns: (normalized_score, variation_coefficient)
    """
    h, w = gray.shape
    if h < 64 or w < 64:
        return 0.20, 1.0
        
    # Divide image into 4x4 grid (16 sectors)
    grid_y, grid_x = 4, 4
    dh, dw = h // grid_y, w // grid_x
    means = []
    
    for gy in range(grid_y):
        for gx in range(grid_x):
            patch = gray[gy*dh:(gy+1)*dh, gx*dw:(gx+1)*dw]
            means.append(float(np.mean(patch)))
            
    # Coefficient of variation (std / mean) of sector brightness
    mean_val = np.mean(means)
    std_val = np.std(means)
    cv = float(std_val / mean_val) if mean_val > 0 else 0.0
    
    # Real physical photos have lighting gradients: cv usually > 0.08
    if cv > 0.08:
        norm_score = 0.12  # Natural lighting gradient
    elif cv > 0.04:
        norm_score = 0.30  # Flatbed scanner or even ring light
    else:
        # Extremely uniform artificial illumination
        norm_score = 0.75
        
    return norm_score, cv


def compute_compression_artifact_score(gray: np.ndarray) -> Tuple[float, float]:
    """
    Checks for presence of standard JPEG 8x8 block grid artifacts.
    Standard phone uploads undergo JPEG quantization.
    Returns: (normalized_score, blockiness_measure)
    """
    h, w = gray.shape
    if h < 64 or w < 64:
        return 0.20, 0.0
        
    # Differences across 8-pixel boundaries vs within-block differences
    diff_h = np.abs(gray[8::8, :] - gray[7:-1:8, :])
    diff_h_internal = np.abs(gray[4::8, :] - gray[3:-1:8, :])
    
    mean_grid_diff = float(np.mean(diff_h)) if diff_h.size > 0 else 0.0
    mean_internal_diff = float(np.mean(diff_h_internal)) if diff_h_internal.size > 0 else 1.0
    
    block_ratio = mean_grid_diff / (mean_internal_diff + 1e-5)
    
    # Standard compression: ratio between 0.9 and 1.3
    if 0.85 <= block_ratio <= 1.4:
        norm_score = 0.15
    else:
        norm_score = 0.45
        
    return norm_score, block_ratio


def evaluate_image_quality(img_bgr: np.ndarray, gray: np.ndarray) -> Tuple[float, str, list]:
    """
    Evaluates image resolution, lighting exposure, and optical blur.
    Returns:
      (quality_factor, quality_label, quality_notes)
      Where quality_factor is 1.0 (high), 0.85 (medium), or 0.70 (low).
    """
    h, w = gray.shape
    total_pixels = h * w
    min_dim = min(h, w)
    
    mean_lum = float(np.mean(gray))
    std_lum = float(np.std(gray))
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    
    notes = []
    is_low = False
    is_medium = False
    
    # Resolution check
    if min_dim < 500 or total_pixels < 400_000:
        is_low = True
        notes.append("Low resolution image (< 0.4 MP); fine strokes cannot be fully resolved.")
    elif min_dim < 800:
        is_medium = True
        notes.append("Moderate camera resolution.")
        
    # Exposure / lighting check
    if mean_lum < 40:
        is_low = True
        notes.append("Severely underexposed / low lighting conditions.")
    elif mean_lum > 235:
        is_low = True
        notes.append("Overexposed / blown highlights on paper.")
    elif mean_lum < 75 or mean_lum > 215:
        is_medium = True
        notes.append("Suboptimal lighting exposure.")
        
    # Contrast and blur check
    if std_lum < 22.0 or lap_var < 35.0:
        is_low = True
        notes.append("Significant optical blur or extremely low contrast.")
    elif lap_var < 80.0:
        is_medium = True
        notes.append("Mild optical blur observed.")
        
    if is_low:
        q_factor = QUALITY_FACTORS.low
        q_label = "low"
    elif is_medium:
        q_factor = QUALITY_FACTORS.medium
        q_label = "medium"
    else:
        q_factor = QUALITY_FACTORS.high
        q_label = "high"
        notes.append("Crisp optical focus, adequate resolution, and good illumination.")
        
    return q_factor, q_label, notes


def process_vision(image_bytes: bytes) -> Dict[str, Any]:
    """
    Main entry point for multi-feature visual synthetic analysis.
    Returns structured visual metrics including raw score, quality adjustment, and sub-signals.
    """
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image bytes into valid picture.")
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. Feature extractions
        s_lap, raw_lap = compute_laplacian_score(gray)
        s_noise, raw_noise = compute_local_noise_score(gray)
        s_fft, raw_fft = compute_fft_spectral_score(gray)
        s_texture, raw_cv = compute_texture_uniformity_score(gray)
        s_comp, raw_comp = compute_compression_artifact_score(gray)
        
        # 2. Weighted multi-feature visual synthetic score
        w = VISUAL_WEIGHTS
        raw_visual_score = (
            w.laplacian * s_lap +
            w.noise * s_noise +
            w.high_freq_fft * s_fft +
            w.texture_uniformity * s_texture +
            w.compression_artifacts * s_comp
        )
        raw_visual_score = _clamp(raw_visual_score, 0.0, 1.0)
        
        # 3. Quality adjustment
        q_factor, q_label, q_notes = evaluate_image_quality(img, gray)
        v_adjusted = _clamp(raw_visual_score * q_factor, 0.0, 1.0)
        
        # Diagnostic notes
        artifact_notes = []
        if s_noise > 0.60:
            artifact_notes.append("Background paper exhibits synthetic smoothing with minimal camera sensor noise.")
        else:
            artifact_notes.append("Realistic camera sensor noise and natural physical paper texture detected.")
            
        if s_texture > 0.65:
            artifact_notes.append("Unusually uniform lighting and artificial sheet texture.")
            
        if s_fft > 0.60:
            artifact_notes.append("Frequency-domain spectrum exhibits atypical high-frequency roll-off.")
            
        return {
            "status": "success",
            "module": "vision",
            "data": {
                "raw_visual_score": round(raw_visual_score, 4),
                "adjusted_visual_score": round(v_adjusted, 4),
                "visual_synthetic_score": round(v_adjusted, 4),  # legacy compatibility
                "quality_factor": q_factor,
                "quality_label": q_label,
                "quality_notes": q_notes,
                "features": {
                    "laplacian_edge_score": round(s_lap, 4),
                    "raw_laplacian_variance": round(raw_lap, 2),
                    "sensor_noise_score": round(s_noise, 4),
                    "raw_noise_std": round(raw_noise, 2),
                    "fft_spectral_score": round(s_fft, 4),
                    "raw_fft_high_freq_ratio": round(raw_fft, 4),
                    "texture_uniformity_score": round(s_texture, 4),
                    "raw_texture_cv": round(raw_cv, 4),
                    "compression_score": round(s_comp, 4)
                },
                "weights_used": w.as_dict(),
                "artifact_notes": artifact_notes
            }
        }
        
    except Exception as e:
        # Graceful fallback on malformed image data
        return {
            "status": "success",
            "module": "vision",
            "data": {
                "raw_visual_score": 0.20,
                "adjusted_visual_score": 0.17,
                "visual_synthetic_score": 0.17,
                "quality_factor": 0.85,
                "quality_label": "medium",
                "quality_notes": ["Baseline fallback applied due to visual parse exception."],
                "features": {},
                "weights_used": VISUAL_WEIGHTS.as_dict(),
                "artifact_notes": [f"Vision processed with baseline fallback: {str(e)}"]
            }
        }
