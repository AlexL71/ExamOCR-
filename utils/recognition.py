import os
import torch
import streamlit as st
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from qwen_vl_utils import process_vision_info

QWEN_PATH = "Qwen/Qwen2.5-VL-7B-Instruct"

OCR_PROMPT = """You are a Korean OCR engine for handwritten 원고지 (Wongoji).

STRICT TRANSCRIPTION RULES:
1. Merge Lines: The text is written on a grid. Do NOT keep line breaks just because the grid line ended. Join them into complete sentences.
2. Paragraphs: Only insert a line break (\n) if there is a distinct paragraph indentation (a clearly empty start of a line).
3. Spacing: Insert a space ONLY when there is a clearly empty grid cell between words.
4. Accuracy: Output exactly what is written. Do not paraphrase or autocorrect spelling.
5. Empty Page: If the image contains ONLY the grid with NO handwriting, output exactly: [EMPTY]
6. Output: Return ONLY the transcribed text. Do not output explanations.
"""

@st.cache_resource
def load_qwen_model():
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )
    
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        QWEN_PATH,
        quantization_config=bnb_config,
        device_map="cuda"
    )
    
    processor = AutoProcessor.from_pretrained(
        QWEN_PATH, 
        use_fast=False, 
        min_pixels=256 * 28 * 28, 
        max_pixels=1280 * 28 * 28
    )
    return model, processor

def transcribe_qwen(image_path):
    if not os.path.exists(image_path): 
        return "Error: Image not found."
    
    try:
        model, processor = load_qwen_model()
        
        messages = [{"role": "user", "content": [
            {"type": "image", "image": image_path},
            {"type": "text", "text": OCR_PROMPT}
        ]}]
        
        text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        
        inputs = processor(
            text=[text_prompt],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=False,
                num_beams=1
            )
            
        prompt_len = inputs["input_ids"].shape[-1]
        final_text = processor.batch_decode(generated_ids[:, prompt_len:], skip_special_tokens=True)[0].strip()
        
        torch.cuda.empty_cache()
        return final_text
        
    except Exception as e:
        return f"Error: {str(e)}"