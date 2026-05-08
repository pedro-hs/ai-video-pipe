"""File management operations for video generation."""

import os
import re
import time
from datetime import datetime

from logger import log_success, log_error
from constants import PARENT_DIR, VIDEO_EXTENSION
from image.generate import SDXL_INFERENCE_STEPS, SDXL_GUIDANCE_SCALE
from audio.generate import save_narration_to_file


def sanitize_theme_name(theme):
    """Sanitize theme name for use in folder names."""
    return re.sub(r'[^a-zA-Z0-9]', '_', theme)[:25]


def create_video_folder(theme):
    """Create a video folder with sanitized theme name."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    rand_num = str(int(time.time()) % 10000)
    clean_theme = sanitize_theme_name(theme)
    folder_name = f'{clean_theme}_{rand_num}_{timestamp}'
    folder_path = os.path.join(PARENT_DIR, 'output', 'videos', folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def save_final_video(output_folder, theme, language='pt'):
    """Save final video by renaming temporary video file."""
    try:
        temp_video = os.path.join(output_folder, f'video_with_audio.{VIDEO_EXTENSION}')
        final_path = os.path.join(output_folder, f'final_{language}.{VIDEO_EXTENSION}')

        if os.path.exists(temp_video):
            os.rename(temp_video, final_path)
            log_success(f'Final video saved: {final_path}', step='save_video')
            return final_path
        else:
            raise Exception(f'Temporary video not found: {temp_video}')
    except Exception as e:
        log_error(f'Save error: {e}', step='save_video')
        raise


def write_style_file(video_folder, style, negative_prompt):
    """Write style information to a file."""
    visuals_dir = os.path.join(video_folder, 'visuals')
    os.makedirs(visuals_dir, exist_ok=True)
    theme_style_file = os.path.join(visuals_dir, 'style.txt')
    with open(theme_style_file, 'w', encoding='utf-8') as f:
        f.write('🎨 Estilo Visual\n')
        f.write(f'{style}\n\n')
        f.write('🚫 Prompt Negativo\n')
        f.write(f'{negative_prompt}\n\n')
        f.write(f'⚙️ Inference Steps: {SDXL_INFERENCE_STEPS}\n')
        f.write(f'⚙️ Guidance Scale: {SDXL_GUIDANCE_SCALE}\n\n')


def write_image_prompts_file(video_folder, image_prompts):
    """Write image prompts to a file."""
    visuals_dir = os.path.join(video_folder, 'visuals')
    os.makedirs(visuals_dir, exist_ok=True)
    prompts_file = os.path.join(visuals_dir, 'image_prompts.txt')
    with open(prompts_file, 'w', encoding='utf-8') as f:
        for i, prompt in enumerate(image_prompts, 1):
            f.write(f'Prompt {i}: {prompt}\n')


