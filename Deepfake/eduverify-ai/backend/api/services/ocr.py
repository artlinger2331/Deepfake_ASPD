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

def extract_ocr(image_bytes: bytes) -> Dict[str, Any]:
    result = {
        "extracted_text": "",
        "confidence_score": 0.0,
        "word_count": 0,
        "is_readable": False,
        "oriented_image_base64": ""
    }
    
    try:
        load_qwen_model()
        
        from .orientation import (
            normalize_image, 
            detect_stroke_is_sideways,
            score_reading_flow,
            apply_fine_deskew, 
            image_to_base64_data_uri
        )
        
        raw_img = normalize_image(Image.open(io.BytesIO(image_bytes)))
        
        # Stage 1: Individual letter stroke alignment analysis
        is_sideways = detect_stroke_is_sideways(raw_img)
        cand1, cand2 = (90, 270) if is_sideways else (0, 180)
        
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
            
        # Test candidate 1 (0° for normal/inverted, 90° for sideways)
        img1, text1, words1, flow1 = evaluate_candidate(cand1)
        w1_count = len(words1)
        print(f"[OCR] Candidate {cand1}°: {w1_count} words, flow score={flow1}. Top line: {text1.splitlines()[:1]}")
        
        best_angle = cand1
        best_img = img1
        best_text = text1
        best_words = words1
        
        # Determine if candidate 2 (opposite 180° rotation) should be evaluated:
        # - Always test for sideways images (to choose between 90° vs 270°)
        # - Test if candidate 1 had low word count (< 25 words)
        # - Test if candidate 1 had doubtful or inverted reading flow (flow_score < 10)
        need_test_cand2 = is_sideways or (w1_count < 25) or (flow1 < 10)
        
        if need_test_cand2:
            img2, text2, words2, flow2 = evaluate_candidate(cand2)
            w2_count = len(words2)
            print(f"[OCR] Candidate {cand2}°: {w2_count} words, flow score={flow2}. Top line: {text2.splitlines()[:1]}")
            
            rank1 = w1_count + 2 * flow1
            rank2 = w2_count + 2 * flow2
            print(f"[OCR] Comparing candidate ranks -> {cand1}°: {rank1} vs {cand2}°: {rank2}")
            
            if rank2 > rank1:
                print(f"[OCR] Selected {cand2}° as optimal upright orientation")
                best_angle = cand2
                best_img = img2
                best_text = text2
                best_words = words2
            else:
                print(f"[OCR] Retained {cand1}° as optimal upright orientation")
                
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
        result["oriented_image_base64"] = image_to_base64_data_uri(best_img)
        
    except Exception as e:
        error_msg = f"ERROR: {str(e)}"
        print(f"[OCR] {error_msg}")
        result["extracted_text"] = error_msg
        
    return result

def process_ocr(image_bytes: bytes) -> Dict[str, Any]:
    """
    Multimodal OCR service using GPU-accelerated Qwen2-VL.
    """
    data = extract_ocr(image_bytes)
    return {
        "status": "success",
        "module": "ocr",
        "data": data
    }
