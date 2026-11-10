"""
Image Orientation and Deskewing Service for EduVerify AI
=========================================================
Analyzes letter stroke alignment and reading flow to ensure documents are
properly oriented (0°, 90°, 180°, or 270°) before OCR extraction.
"""

import io
import re
import cv2
import numpy as np
from PIL import Image, ImageOps
from typing import Tuple, List, Optional


def normalize_image(pil_img: Image.Image) -> Image.Image:
    """Applies EXIF rotation normalization and converts to RGB."""
    img = ImageOps.exif_transpose(pil_img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def enhance_faint_handwriting(pil_img: Image.Image) -> Image.Image:
    """
    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE) and
    subtle stroke sharpening to enhance faint, cursive, or hazy handwriting
    against uneven or degraded paper backgrounds.
    """
    cv_img = np.array(pil_img.convert("RGB"))
    lab = cv2.cvtColor(cv_img, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    
    gaussian = cv2.GaussianBlur(cl, (0, 0), sigmaX=2.0)
    sharpened_l = cv2.addWeighted(cl, 1.3, gaussian, -0.3, 0)
    
    limg = cv2.merge((sharpened_l, a, b))
    enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2RGB)
    return Image.fromarray(enhanced)


def detect_stroke_is_sideways(pil_img: Image.Image) -> bool:
    """
    Analyzes individual letter stroke edge gradients using Sobel operators.
    In upright Latin script, vertical downstrokes (stems of letters like t, l, b, d, h, p)
    produce strong horizontal gradients (dx >> dy), yielding Sobel edge angles near 0°.
    When an image is tilted sideways (90° or 270°), these downstrokes become horizontal (dy >> dx),
    causing edge angles to concentrate > 60°.
    
    Returns True if the document text is oriented vertically/sideways, False if horizontal.
    """
    gray = np.array(pil_img.convert('L'))
    h, w = gray.shape
    scale = 600.0 / max(h, w)
    if scale < 1.0:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(sobelx**2 + sobely**2)
    
    # Filter for significant stroke edges (top 15% gradient magnitudes)
    edge_mask = magnitude > np.percentile(magnitude, 85)
    if not np.any(edge_mask):
        return False
        
    angles = np.rad2deg(np.arctan2(np.abs(sobely[edge_mask]), np.abs(sobelx[edge_mask])))
    ratio = np.mean(angles < 30) / (np.mean(angles > 60) + 1e-6)
    is_sideways = ratio < 0.90
    print(f"[Orientation] Stroke alignment ratio={ratio:.3f} -> is_sideways={is_sideways}")
    return is_sideways


def score_reading_flow(text: str) -> int:
    """
    Analyzes the reading flow of transcribed text to determine if the document
    was read top-to-bottom (correct) or bottom-to-top (inverted).
    
    Upright documents start with titles, headings, or opening sentence clauses.
    Inverted documents start with trailing clauses (it produces, and, or) or
    bottom-of-page metadata (Page: 8, Date:), and end with top-of-page titles.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return -100
        
    score = 0
    first_line = lines[0].lower()
    last_line = lines[-1].lower()
    
    # Positive signals for beginning of document:
    title_starters = [
        'half', 'title', 'experiment', 'chapter', 'topic', 'definition',
        'note', 'when', 'if ', 'the ', 'a ', 'an ', 'in ', 'for ', 'to '
    ]
    if any(lines[0].lower().startswith(k) for k in title_starters):
        score += 10
    if len(lines[0].split()) <= 4 and lines[0][0].isupper():
        score += 5
        
    # Negative signals (bottom-first indicators at top of page):
    bottom_first_starters = [
        'it produces', 'it accepts', 'it has', 'and ', 'or ', 'that adds',
        'which is', 'then ', 'page:', 'date:', 'pg.', 'fig.'
    ]
    if any(first_line.startswith(k) for k in bottom_first_starters):
        score -= 10
    if re.search(r'\bpage\s*[:\.]?\s*\d+', first_line) or re.search(r'\bdate\s*[:\.]', first_line):
        score -= 15
        
    # Inverted document signals (heading/definition found at the very bottom line):
    if any(k in last_line for k in ['definition', 'half adder', 'title', 'experiment', 'chapter']):
        score -= 15
        
    return score


def compute_fine_skew(pil_img: Image.Image) -> float:
    """Calculates fine skew angle in degrees (-20 to +20)."""
    cv_img = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    
    scale = 600.0 / max(h, w)
    if scale < 1.0:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = gray.shape
        
    y1, y2 = int(h * 0.10), int(h * 0.90)
    x1, x2 = int(w * 0.10), int(w * 0.90)
    crop = gray[y1:y2, x1:x2]
    
    _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 3))
    dilated = cv2.dilate(binary, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    angles = []
    for cnt in contours:
        if cv2.contourArea(cnt) > 200:
            rect = cv2.minAreaRect(cnt)
            (cx, cy), (rw, rh), angle = rect
            if rw < rh:
                angle = angle + 90 if angle < 0 else angle - 90
            if abs(angle) < 20:
                angles.append(angle)
                
    return float(np.median(angles)) if angles else 0.0


def apply_fine_deskew(pil_img: Image.Image) -> Tuple[Image.Image, float]:
    """Applies fine deskew if the skew angle is noticeable (>= 1.5 degrees)."""
    angle = compute_fine_skew(pil_img)
    if abs(angle) >= 1.5:
        deskewed = pil_img.rotate(-angle, expand=True, resample=Image.Resampling.BILINEAR, fillcolor=(255, 255, 255))
        return deskewed, angle
    return pil_img, 0.0


def image_to_base64_data_uri(pil_img: Image.Image) -> str:
    """Encodes a PIL image into a base64 Data URI for frontend display."""
    import base64
    buffered = io.BytesIO()
    rgb_img = pil_img.convert("RGB")
    rgb_img.save(buffered, format="JPEG", quality=85, optimize=True)
    b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64_str}"
