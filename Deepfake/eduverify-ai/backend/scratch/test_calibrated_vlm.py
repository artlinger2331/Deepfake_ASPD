import sys, torch
from PIL import Image

sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")

from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from qwen_vl_utils import process_vision_info

model_id = "Qwen/Qwen2-VL-2B-Instruct"
processor = AutoProcessor.from_pretrained(model_id)
model = Qwen2VLForConditionalGeneration.from_pretrained(
    model_id, 
    torch_dtype=torch.float16, 
    device_map="cuda"
)

def evaluate_neutral(image_path: str):
    img = Image.open(image_path)
    if max(img.size) > 1024:
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        
    messages = [
        {
            "role": "system",
            "content": (
                "You are an objective document analysis assistant. Carefully inspect the handwriting.\n"
                "Real human handwriting has organic imperfections, variations in pen pressure, ink thickness, "
                "inconsistent letter angles, and irregular baselines.\n"
                "Digital font rendering or AI diffusion exhibits carbon-copy letter glyphs, identical recurring letterforms, "
                "and unnaturally rigid baseline alignment."
            )
        },
        {
            "role": "user",
            "content": [
                {"type": "image", "image": img},
                {
                    "type": "text", 
                    "text": (
                        "Examine this handwritten page.\n"
                        "Does this exhibit natural human handwriting variations, or is it synthetic/AI-generated text?\n"
                        "Respond strictly in this format:\n"
                        "VERDICT: [AUTHENTIC_PHYSICAL or AI_GENERATED]\n"
                        "REASONS:\n"
                        "- [observation 1]\n"
                        "- [observation 2]"
                    )
                }
            ]
        }
    ]
    
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt"
    ).to("cuda")
    
    output_ids = model.generate(**inputs, max_new_tokens=150)
    generated_ids = [out[len(inp):] for inp, out in zip(inputs.input_ids, output_ids)]
    output = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return output

print("--- 1. ChatGPT DALL-E 3 Essay (Winter) ---")
print(evaluate_neutral(r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\ai_generated\Handwritten Winter Essay.png"))

print("\n--- 2. Real Document Scan (Engineering Economics) ---")
print(evaluate_neutral(r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\real_scan\DocScanner 14-Oct-2026 01-56 AM_page_1.jpg"))

print("\n--- 3. Real Student Clear Handwriting (WhatsApp Note) ---")
print(evaluate_neutral(r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\handwritten_clear\WhatsApp Image 2026-11-10 at 11.18.24 PM.jpeg"))

