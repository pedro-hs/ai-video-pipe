"""Video generation module - Public API for backward compatibility."""
import os
import numpy as np
import time

from logger import log, log_step, log_success, log_error
from env import USE_KEN_BURNS_EFFECT, VIDEO_WIDTH, VIDEO_HEIGHT
from constants import IMAGE_EXTENSION, VIDEO_EXTENSION
from image.generate import generate_single_image_with_prompt, load_sdxl_model, unload_model, save_bgr_image_as_png
from .effects import save_video_streaming_ken_burns, save_video_streaming_simple
from ollama_client import stop_ollama_temporarily, restart_ollama
from audio.generate import generate_audio, save_narration_to_file
from audio.files import get_audio_duration
from .files import (
    create_video_folder,
    write_style_file,
    write_image_prompts_file,
    save_final_video
)
from .utils import calculate_video_params
from .prompts import generate_image_prompts_from_narration
from .merge import merge_video_audio

def get_image_path_for_index(output_dir, index):
    """Get image path for given index in images subfolder."""
    images_dir = os.path.join(output_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    return os.path.join(images_dir, f'image_{index:02d}.{IMAGE_EXTENSION}')


def create_fallback_image(width, height):
    """Create a fallback black image."""
    return np.zeros((height, width, 3), dtype=np.uint8)


def save_image_with_fallback(image, output_dir, index, last_valid_image, width, height):
    """Save image with fallback to last valid image or black image."""
    if image is not None:
        image_path = get_image_path_for_index(output_dir, index)
        save_bgr_image_as_png(image, image_path)
        return image_path
    elif last_valid_image is not None:
        image_path = get_image_path_for_index(output_dir, index)
        save_bgr_image_as_png(last_valid_image, image_path)
        return image_path
    else:
        fallback_image = create_fallback_image(width, height)
        image_path = get_image_path_for_index(output_dir, index)
        save_bgr_image_as_png(fallback_image, image_path)
        del fallback_image
        return image_path


def generate_images_from_prompts(pipe, prompts, output_dir, width, height, negative_prompt, image_count):
    """Generate images from prompts using SDXL model."""
    import torch
    import gc
    from logger import log
    
    image_paths = []
    last_valid_image = None

    for i in range(image_count):
        prompt = prompts[i] if i < len(prompts) else prompts[-1]
        progress = 50 + (i * 20 // image_count)
        log_step('generate_image', f'Gerando imagem {i+1}...', 
                 current=i+1, total=image_count,
                 stage='generating', progress_percent=progress)

        generated_image, _ = generate_single_image_with_prompt(
            pipe, prompt, width, height, negative_prompt,
            output_dir=output_dir, image_index=i+1
        )

        image_path = save_image_with_fallback(
            generated_image, output_dir, i+1, last_valid_image, width, height
        )
        image_paths.append(image_path)

        if generated_image is not None:
            if last_valid_image is not None:
                del last_valid_image
            last_valid_image = generated_image

        # Periodic deep cleanup for long batches to prevent memory accumulation
        if (i + 1) % 20 == 0 and (i + 1) < image_count:
            log(f'Performing deep memory cleanup after image {i+1}/{image_count}...', step='generate_image')
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            gc.collect()
            torch.cuda.empty_cache()
            # Small delay to allow CUDA to free fragmented memory
            time.sleep(0.3)

    if last_valid_image is not None:
        del last_valid_image

    # Final cleanup pass
    torch.cuda.synchronize()
    torch.cuda.empty_cache()
    gc.collect()

    if not image_paths:
        raise Exception('No images generated successfully')

    log_success(f'Generated {len(image_paths)} images', step='generate_image')
    return image_paths


def generate_video_from_images(image_paths, output_path, frames_per_image_list, total_frames, fps, width, height):
    if USE_KEN_BURNS_EFFECT:
        save_video_streaming_ken_burns(image_paths, output_path, frames_per_image_list, total_frames, fps, width, height)
    else:
        save_video_streaming_simple(image_paths, output_path, frames_per_image_list, total_frames, fps, width, height)


def generate_ai_video_with_multiple_prompts(prompts, output_dir, duration, width, height, fps, negative_prompt=''):
    start_time = time.time()
    total_frames, image_count, frames_per_image_list = calculate_video_params(duration, fps, desired_image_count=len(prompts))
    os.makedirs(output_dir, exist_ok=True)
    visuals_dir = os.path.join(output_dir, 'visuals')
    os.makedirs(visuals_dir, exist_ok=True)
    output_path = os.path.join(visuals_dir, f'animated.{VIDEO_EXTENSION}')

    log(f'Generating video: {len(prompts)} prompts, {duration}s, {image_count} images', step='generate_video')

    log('Stopping Ollama...', step='ollama_management')
    stop_ollama_temporarily()

    pipe = load_sdxl_model()
    image_paths = generate_images_from_prompts(pipe, prompts, output_dir, width, height, negative_prompt, image_count)

    unload_model(pipe)
    log('Restarting Ollama...', step='ollama_management')
    restart_ollama()
    time.sleep(3)

    generate_video_from_images(image_paths, output_path, frames_per_image_list, total_frames, fps, width, height)

    elapsed_time = time.time() - start_time
    log_success(f'Video generated in {elapsed_time:.1f}s', step='generate_video')

    log(f'Vídeo salvo com sucesso! ({elapsed_time:.1f}s)', 
        step='save_video', stage='saving', progress_percent=90)

    return output_path

def generate_video_with_prompts(image_prompts, narration_script, duration, fps, output_folder, negative_prompt=''):
    """Generate video with prompts and narration script. Resolution from env variables."""
    try:
        output_path = generate_ai_video_with_multiple_prompts(
            prompts=image_prompts,
            output_dir=output_folder,
            duration=duration,
            width=VIDEO_WIDTH,
            height=VIDEO_HEIGHT,
            fps=fps,
            negative_prompt=negative_prompt
        )
        return output_path
    except Exception as e:
        log_error(f'Video generation error: {e}', step='generate_video')
        raise

def generate_complete_video(narration_script, duration, orientation, style, negative_prompt='', language='pt', music_files=None, video_id=None):
    """Generate a complete video from narration_script to final output. Resolution from env variables."""
    try:
        video_folder = create_video_folder(narration_script)
        write_style_file(video_folder, style, negative_prompt)
        
        # Save music files if provided
        if music_files:
            musics_dir = os.path.join(video_folder, 'musics')
            os.makedirs(musics_dir, exist_ok=True)
            for i, music_file in enumerate(music_files):
                if music_file and music_file.filename:
                    # Preserve original filename or use index if no filename
                    filename = music_file.filename or f'music_{i+1}.mp3'
                    # Sanitize filename
                    import re
                    filename = re.sub(r'[^\w\s.-]', '', filename)
                    if not filename:
                        filename = f'music_{i+1}.mp3'
                    music_path = os.path.join(musics_dir, filename)
                    # Save file content (read and write to handle thread safety)
                    try:
                        # Try to seek and read the file
                        if hasattr(music_file, 'seek'):
                            music_file.seek(0)
                        file_content = music_file.read() if hasattr(music_file, 'read') else None
                        if file_content is None:
                            log_error(f'Cannot read music file: {filename}', step='save_music')
                            continue
                        with open(music_path, 'wb') as f:
                            f.write(file_content)
                        log(f'Saved music file: {filename}', step='save_music')
                    except (AttributeError, IOError, OSError) as e:
                        log_error(f'Error saving music file {filename}: {e}', step='save_music')
                        continue

        fps = 24  # FPS is fixed, resolution comes from env variables

        # Save narration to narration/{language}/narration.txt
        narration_file = save_narration_to_file(video_folder, narration_script, language=language)

        log('Gerando áudio com narração...', step='generate_audio', 
            stage='audio', progress_percent=40, narration_script=narration_script)
        # Generate audio (saves to narration/{language}/narration_0.wav and narration/{language}/audio_segments/)
        generate_audio(narration_script, video_folder, language=language)

        # Get duration from narration/{language}/narration_0.wav
        actual_audio_duration = get_audio_duration(video_folder=video_folder, language=language)

        log('IA criando prompts visuais baseados nas seções da narração...', 
            step='generate_prompts', stage='loading', progress_percent=50, 
            narration_script=narration_script)
        image_prompts = generate_image_prompts_from_narration(narration_file, actual_audio_duration, style)

        write_image_prompts_file(video_folder, image_prompts)

        log(f'Gerando {len(image_prompts)} imagens baseadas na narração...', 
            step='generate_image', stage='generating', progress_percent=60,
            narration_script=narration_script, image_prompts=image_prompts)

        log(f'Gerando vídeo para {actual_audio_duration:.1f}s do áudio...', 
            step='generate_video', stage='generating', progress_percent=75,
            narration_script=narration_script, image_prompts=image_prompts)
        generate_video_with_prompts(image_prompts, narration_script, actual_audio_duration, fps, video_folder, negative_prompt)

        log('Combinando vídeo e áudio...', step='merge', 
            stage='merging', progress_percent=90,
            narration_script=narration_script, image_prompts=image_prompts)

        # Merge uses narration/{language}/narration_0.wav, with automatic subscription overlay if enabled and detected
        merge_video_audio(video_folder, language=language)

        final_path = save_final_video(video_folder, narration_script, language=language)

        log_success('Vídeo finalizado com sucesso!', step='complete',
                   stage='complete', progress_percent=100,
                   narration_script=narration_script, image_prompts=image_prompts)

        return {
            'success': True,
            'message': 'Vídeo gerado com sucesso!',
            'video_path': final_path,
            'video_folder': video_folder
        }
    except Exception as e:
        log_error(f'Error: {str(e)[:100]}', step='error', stage='error', progress_percent=0)
        return {
            'success': False,
            'error': str(e)
        }

