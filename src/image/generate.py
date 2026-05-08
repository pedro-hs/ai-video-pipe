import cv2
import gc
import numpy as np
import os
import sys
import torch

from PIL import Image as PILImage, ImageEnhance, ImageFilter
from diffusers import StableDiffusionXLPipeline
from pathlib import Path

from image.face_blur import apply_face_blur
from env import SAVE_ORIGINAL_IMAGE, ENABLE_FACE_BLUR, USE_CHEYENNE_CHECKPOINT, USE_TRADITIONAL_CHECKPOINT
from constants import IMAGE_EXTENSION

# Configure PyTorch CUDA memory allocator to reduce fragmentation
# This helps prevent OOM errors during long batch generations (especially at high resolutions)
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'

SDXL_INFERENCE_STEPS = 25
SDXL_GUIDANCE_SCALE = 5

def generate_single_image_with_prompt(pipe, prompt, width, height, negative_prompt='', use_adetailer=None, output_dir=None, image_index=None):
    torch.cuda.empty_cache()

    try:
        image = pipe(
            prompt,
            negative_prompt=negative_prompt or '',
            num_inference_steps=SDXL_INFERENCE_STEPS,
            height=height,
            width=width,
            guidance_scale=SDXL_GUIDANCE_SCALE
        ).images[0]

        if SAVE_ORIGINAL_IMAGE and output_dir and image_index is not None:
            original_image_path = os.path.join(output_dir, f'image_{image_index:02d}_original.{IMAGE_EXTENSION}')
            image.save(original_image_path, IMAGE_EXTENSION, optimize=True)

        if ENABLE_FACE_BLUR:
            image = apply_face_blur(pipe, image, output_dir=output_dir)
            # Aggressive cleanup after face blur to free YOLO model memory
            # YOLO model and predictions can consume significant GPU memory (3+ GB)
            try:
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
                gc.collect()
                torch.cuda.empty_cache()
            except:
                pass

        image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))

        frame = convert_image_to_frame(image)
        del image
        gc.collect()
        torch.cuda.empty_cache()

        return frame, prompt

    except Exception as e:
        from logger import log_error
        log_error(f'Image generation failed: {e}', step='generate_image')
        test_image = np.full((height, width, 3), [255, 0, 0], dtype=np.uint8)
        return test_image, prompt

def load_sdxl_model():
    clean_cuda_cache()
    torch.cuda.set_per_process_memory_fraction(0.95)

    try:
        pipe = create_pipe(variant='fp16')
    except Exception as e:
        pipe = create_pipe()

    pipe = pipe.to('cuda')
    setup_memory_optimizations(pipe)
    return pipe

def create_pipe(variant = None):
    if USE_CHEYENNE_CHECKPOINT:
        project_root = Path(__file__).parent.parent.parent
        checkpoint_path = project_root / 'models' / 'CHEYENNE_v18.safetensors'
        if not checkpoint_path.exists():
            raise FileNotFoundError(f'Checkpoint file not found: {checkpoint_path}. Set USE_CHEYENNE_CHECKPOINT=false or ensure the checkpoint file exists.')
        return StableDiffusionXLPipeline.from_single_file(
            str(checkpoint_path),
            torch_dtype=torch.float16,
            use_safetensors=True
        )

    if USE_TRADITIONAL_CHECKPOINT:
        project_root = Path(__file__).parent.parent.parent
        checkpoint_path = project_root / 'models' / 'traditionalPainting_v02.safetensors'
        if not checkpoint_path.exists():
            raise FileNotFoundError(f'Checkpoint file not found: {checkpoint_path}. Set USE_TRADITIONAL_CHECKPOINT=false or ensure the checkpoint file exists.')
        return StableDiffusionXLPipeline.from_single_file(
            str(checkpoint_path),
            torch_dtype=torch.float16,
            use_safetensors=True
        )

    return StableDiffusionXLPipeline.from_pretrained(
        'stabilityai/stable-diffusion-xl-base-1.0',
        torch_dtype=torch.float16,
        cache_dir='models',
        variant=variant,
        use_safetensors=True
    )

def convert_image_to_frame(image):
    frame = np.array(image)

    if frame.size == 0:
        return np.zeros((960, 1280, 3), dtype=np.uint8)

    if len(frame.shape) == 3:
        if frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        if frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

    return frame

def setup_memory_optimizations(pipe):
    try:
        pipe.enable_xformers_memory_efficient_attention()
    except Exception as e:
        pipe.enable_attention_slicing()

    try:
        pipe.enable_vae_tiling()
    except Exception as e:
        pipe.enable_vae_slicing()

    torch.cuda.empty_cache()

def unload_model(pipe):
    if pipe is not None:
        del pipe
        clean_cuda_cache()

def clean_cuda_cache():
    torch.cuda.empty_cache()
    gc.collect()

def save_bgr_image_as_png(image_bgr, output_path):
    rgb_image = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    pil_image = PILImage.fromarray(rgb_image)
    pil_image.save(output_path, IMAGE_EXTENSION, optimize=True)
