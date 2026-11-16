import io
import re
from collections import Counter
from typing import Dict, Any, Tuple, Optional
from PIL import Image
import torch

# Initialize processor and model globally to avoid reloading on every request
qwen_processor = None
qwen_model = None
model_id = "Qwen/Qwen2-VL-2B-Instruct"

def load_qwen_model():
    global qwen_processor, qwen_model
    if qwen_processor is not None and qwen_model is not None:
        return
        
    try:
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        
        print(f"[OCR] Loading {model_id} on {device.upper()} (dtype: {dtype})...")
        qwen_processor = AutoProcessor.from_pretrained(model_id)
        qwen_model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_id, 
            torch_dtype=dtype,
            device_map="cuda" if torch.cuda.is_available() else "cpu"
        )
        print(f"[OCR] Successfully loaded {model_id} on {device.upper()}")
    except Exception as e:
        error_str = str(e)
        print(f"[OCR] Failed to load {model_id}: {error_str}")
        raise ValueError(f"Failed to load Qwen model: {error_str}")

def clean_extracted_text(text: str) -> str:
    """Removes model tags, code fence wrappers, preambles, and conversational meta-commentary."""
    cleaned = re.sub(r'<\|[^>]+\|>', '', text).strip()
    cleaned = re.sub(r'```[a-zA-Z]*', '', cleaned)
    cleaned = cleaned.replace('```', '')
    
    # Strip any leading 'Text:' prefix or conversational LLM introductions
    cleaned = re.sub(r'^Text:\s*', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'^(The transcription of the handwritten text|Here is the transcribed text|Here\'s a breakdown of each part)[^:\n]*:?', '', cleaned, flags=re.IGNORECASE).strip()
        
    lines = cleaned.splitlines()
    filtered_lines = []
    seen_lines_count = Counter()
    
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            filtered_lines.append("")
            continue
            
        # Skip standalone coordinate lines like (151,81),(908,870)
        cleaned_line = re.sub(r'<\|[^>]+\|>', '', line_clean).strip()
        is_coord = bool(re.match(r'^[\s\(\)\[\]0-9,.:;/\-_]+$', cleaned_line)) and not bool(re.search(r'[A-Za-z]{2,}', cleaned_line))
        if is_coord:
            continue
            
        # Deduplicate consecutive degenerate loop lines (e.g. repeated > 2 times)
        seen_lines_count[line_clean] += 1
        if seen_lines_count[line_clean] <= 2:
            filtered_lines.append(line)
            
    return "\n".join(filtered_lines).strip()

def _run_inference(image: Image.Image, system_msg: str, user_prompt: str,
                   max_tokens: int = 1024) -> str:
    from qwen_vl_utils import process_vision_info
    
    messages = [
        {"role": "system", "content": system_msg},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": user_prompt}
            ]
        }
    ]
    
    # Use assistant prefill with Text:\n to force pure verbatim transcription mode and prevent bounding box coordinates
    prompt = qwen_processor.apply_chat_template(
        messages, 
        tokenize=False, 
        add_generation_prompt=False
    )
    prompt += "<|im_start|>assistant\nText:\n"
    
    image_inputs, video_inputs = process_vision_info(messages)
    
    inputs = qwen_processor(
        text=[prompt],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt"
    )
    
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        
    generate_ids = qwen_model.generate(
        **inputs, 
        max_new_tokens=max_tokens,
        repetition_penalty=1.15,
        no_repeat_ngram_size=5
    )
    
    generated_ids_trimmed = [
        out_ids[len(inputs.input_ids[0]):] for out_ids in generate_ids
    ]
    
    output = qwen_processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0].strip()
    
    return output

def _run_forensic_inference(image: Image.Image, system_msg: str, user_prompt: str,
                            max_tokens: int = 180) -> str:
    from qwen_vl_utils import process_vision_info
    
    messages = [
        {"role": "system", "content": system_msg},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": user_prompt}
            ]
        }
    ]
    
    prompt = qwen_processor.apply_chat_template(
        messages, 
        tokenize=False, 
        add_generation_prompt=True
    )
    
    image_inputs, video_inputs = process_vision_info(messages)
    
    inputs = qwen_processor(
        text=[prompt],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt"
    )
    
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        
    generate_ids = qwen_model.generate(
        **inputs, 
        max_new_tokens=max_tokens
    )
    
    generated_ids_trimmed = [
        out_ids[len(inputs.input_ids[0]):] for out_ids in generate_ids
    ]
    
    output = qwen_processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0].strip()
    
    return output

def evaluate_vlm_forensics(image: Image.Image) -> Dict[str, Any]:
    """
    Multimodal visual forensic evaluation for synthetic handwriting and AI notebook artifacts.
    Evaluates stroke geometry, baseline slant, glyph variation, and paper lighting.
    """
    default_res = {
        "vlm_synthetic_score": 0.50,
        "vlm_verdict": "uncertain",
        "confidence": "MODERATE",
        "reasons": []
    }
    
    if qwen_model is None or qwen_processor is None:
        return default_res
        
    try:
        prep = image.copy()
        if max(prep.size) > 1024:
            prep.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            
        sys_msg = (
            "You are an objective document forensic assistant. Carefully inspect the visual handwriting strokes.\n"
            "Real human handwriting has organic imperfections, variations in pen pressure, ink thickness, "
            "natural slant, and physical paper texture.\n"
            "AI generation or digital font rendering exhibits identical carbon-copy letter glyphs, machine-rigid baselines, "
            "and unnatural stroke uniformity."
        )
        user_prompt = (
            "Examine the physical handwriting in this document image.\n"
            "CRITICAL: Base your decision ONLY on the visual strokes, ink, and penmanship. "
            "DO NOT judge based on the topic or subject matter (lecture notes about computers, technology, or science are normal student coursework).\n"
            "Does this exhibit natural human handwriting variations, or is it synthetic/AI-generated text?\n"
            "Respond strictly in this format:\n"
            "VERDICT: [AUTHENTIC_PHYSICAL or AI_GENERATED]\n"
            "REASONS:\n"
            "- [observation 1]\n"
            "- [observation 2]"
        )
        
        raw_output = _run_forensic_inference(prep, sys_msg, user_prompt, max_tokens=150)
        
        verdict = "uncertain"
        score = 0.50
        conf_str = "MODERATE"
        
        upper = raw_output.upper()
        # Parse verdict line
        verdict_part = upper.split("VERDICT:")[1].splitlines()[0] if "VERDICT:" in upper else upper
        if "AI_GENERATED" in verdict_part:
            verdict = "ai_generated"
            score = 0.90
            conf_str = "HIGH"
        elif "AUTHENTIC_PHYSICAL" in verdict_part or "AUTHENTIC" in verdict_part:
            verdict = "authentic"
            score = 0.15
            conf_str = "HIGH"
            
        reasons = []
        for line in raw_output.splitlines():
            line_str = line.strip()
            if line_str.startswith(("-", "•", "*")):
                cleaned_line = line_str.lstrip("-•* ").strip()
                if cleaned_line and len(cleaned_line) > 5:
                    reasons.append(cleaned_line)
            elif re.match(r'^\d+[\.\)]\s*', line_str):
                cleaned_line = re.sub(r'^\d+[\.\)]\s*', '', line_str).strip()
                if cleaned_line and len(cleaned_line) > 5:
                    reasons.append(cleaned_line)
                    
        return {
            "vlm_synthetic_score": round(score, 4),
            "vlm_verdict": verdict,
            "confidence": conf_str,
            "reasons": reasons[:3],
            "raw_response": raw_output
        }
    except Exception as e:
        print(f"[OCR] VLM forensic evaluation exception: {e}")
        return default_res

def extract_ocr(image_bytes: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
    from .orientation import raw_bytes_to_base64_data_uri
    verbatim_data_uri = raw_bytes_to_base64_data_uri(image_bytes, filename=filename)

    result = {
        "extracted_text": "",
        "confidence_score": 0.0,
        "word_count": 0,
        "is_readable": False,
        "oriented_image_base64": verbatim_data_uri
    }
    
    try:
        load_qwen_model()
        
        from .orientation import (
            normalize_image, 
            detect_stroke_is_sideways,
            score_reading_flow,
            apply_fine_deskew, 
            image_to_base64_data_uri,
            raw_bytes_to_base64_data_uri
        )
        
        raw_img = normalize_image(Image.open(io.BytesIO(image_bytes)))
        # Strictly preserve raw uploaded image bytes verbatim for display
        result["oriented_image_base64"] = verbatim_data_uri
        
        sys_msg = (
            "You are a master document OCR engine. Accurately transcribe all handwritten text, "
            "cursive handwriting, notes, formulas, and code from the provided image verbatim line by line from top to bottom. "
            "Even if the handwriting is messy, cursive, slanted, hazy, faint, or hard to read, decipher every word, "
            "letter, and character to the best of your ability. Do not omit or skip words. "
            "Do not modify, correct, or rewrite any words, spelling, or grammar. Transcribe the exact handwriting as written."
        )
        user_prompt = "Read and transcribe all handwritten text on this page verbatim line by line from top to bottom."
        
        def evaluate_candidate(angle: int) -> Tuple[Image.Image, str, list, int]:
            img = raw_img.rotate(angle, expand=True) if angle != 0 else raw_img
            img, _ = apply_fine_deskew(img)
            prep = img.copy()
            if max(prep.size) > 1200:
                prep.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            raw_text = _run_inference(prep, sys_msg, user_prompt, max_tokens=1024)
            cleaned = clean_extracted_text(raw_text)
            words = [w for w in cleaned.split() if re.search(r'[A-Za-z0-9]', w)]
            flow = score_reading_flow(cleaned)
            return img, cleaned, words, flow
            
        # Stage 1: Always evaluate candidate 0° (the natural, upright orientation as uploaded)
        img0, text0, words0, flow0 = evaluate_candidate(0)
        w0_count = len(words0)
        print(f"[OCR] Candidate 0° (Original): {w0_count} words, flow score={flow0}. Top line: {text0.splitlines()[:1]}")
        
        best_angle = 0
        best_img = img0
        best_text = text0
        best_words = words0
        
        # Only search alternative orientations if 0° failed to read text:
        # If 0° already produces legitimate words (>= 8),
        # the document is already straight and upright. Never rotate it away from 0°.
        need_alternative_test = (w0_count < 8)
        
        if need_alternative_test:
            candidates_to_try = [180]
            if w0_count < 5:
                candidates_to_try.extend([90, 270])
                
            for alt_angle in candidates_to_try:
                img_alt, text_alt, words_alt, flow_alt = evaluate_candidate(alt_angle)
                w_alt = len(words_alt)
                print(f"[OCR] Candidate {alt_angle}°: {w_alt} words, flow score={flow_alt}. Top line: {text_alt.splitlines()[:1]}")
                
                # Require substantial superiority to rotate away from 0°
                is_significantly_better = (
                    (w_alt >= 12 and w_alt > w0_count * 2 + 5) or
                    (w0_count == 0 and w_alt >= 5)
                )
                if is_significantly_better:
                    print(f"[OCR] Selected {alt_angle}° as superior orientation (words={w_alt}, flow={flow_alt} vs 0° words={w0_count}, flow={flow0})")
                    best_angle = alt_angle
                    best_img = img_alt
                    best_text = text_alt
                    best_words = words_alt
                    break
                else:
                    print(f"[OCR] Retained 0° (alternative {alt_angle}° not significantly better)")
                
        word_count = len(best_words)
        
        # Dynamic confidence score based on word volume
        if word_count >= 20:
            confidence_score = 95.0
        elif word_count >= 10:
            confidence_score = 90.0
        elif word_count >= 4:
            confidence_score = 82.0
        elif word_count > 0:
            confidence_score = 70.0
        else:
            confidence_score = 0.0
            
        result["extracted_text"] = best_text
        result["confidence_score"] = confidence_score
        result["word_count"] = word_count
        result["is_readable"] = word_count > 0
        # The returned image ALWAYS strictly preserves raw uploaded image bytes verbatim
        result["oriented_image_base64"] = verbatim_data_uri
        
        # Stage 3: Dedicated VLM Forensic Pass on upright document
        vlm_forensics = evaluate_vlm_forensics(best_img)
        result["vlm_forensics"] = vlm_forensics
        
    except Exception as e:
        error_msg = f"ERROR: {str(e)}"
        print(f"[OCR] {error_msg}")
        result["extracted_text"] = error_msg
        
    return result

def process_ocr(image_bytes: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Multimodal OCR service using GPU-accelerated Qwen2-VL.
    """
    data = extract_ocr(image_bytes, filename=filename)
    return {
        "status": "success",
        "module": "ocr",
        "data": data
    }
