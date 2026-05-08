import os
import glob
import threading
from io import BytesIO

from flask import Blueprint, jsonify, send_file, request
from PIL import Image

from constants import OUTPUT_DIR_VIDEOS, IMAGE_EXTENSION, AUDIO_EXTENSION, VIDEO_EXTENSION
from audio.generate import split_narration_by_phrases
from audio.files import get_audio_duration
from audio.piper import generate_tts_batch
from audio.utils import combine_audio_segments_with_silence, DEFAULT_SILENCE_DURATION
from app.images import generate_image_to_path
from video.merge import merge_video_audio
from video.files import save_final_video
from video.generate import generate_video_from_images
from video.utils import calculate_video_params
from logger import log, log_success, log_error
from env import VIDEO_WIDTH, VIDEO_HEIGHT

app = Blueprint('video_edit', __name__)

@app.route('/api/videos/<path:folder>/edit', methods=['GET'])
def get_video_edit_data(folder):
    """Get video folder data for editing (image prompts, audio segments, etc.)."""
    try:
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder) or not os.path.isdir(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        image_prompts = read_image_prompts_from_file(video_folder)
        
        # Load audio segments for all languages
        audio_segments_pt = read_audio_segments_from_narration(video_folder, language='pt')
        audio_segments_en = read_audio_segments_from_narration(video_folder, language='en')
        audio_segments_es = read_audio_segments_from_narration(video_folder, language='es')
        
        audio_segment_files_pt = build_audio_segment_files_info(video_folder, folder, audio_segments_pt, language='pt')
        audio_segment_files_en = build_audio_segment_files_info(video_folder, folder, audio_segments_en, language='en')
        audio_segment_files_es = build_audio_segment_files_info(video_folder, folder, audio_segments_es, language='es')
        
        image_files = build_image_files_info(video_folder, folder, image_prompts)
        theme, style, negative_prompt = read_style_file(video_folder)
        
        # Check which language narrations exist (for merge buttons)
        has_pt_narration = os.path.exists(os.path.join(video_folder, 'narration', 'pt', 'narration.txt'))
        has_en_narration = os.path.exists(os.path.join(video_folder, 'narration', 'en', 'narration.txt'))
        has_es_narration = os.path.exists(os.path.join(video_folder, 'narration', 'es', 'narration.txt'))
        
        # Check if final narration files exist (for delete buttons)
        from constants import AUDIO_EXTENSION
        has_pt_final_narration = os.path.exists(os.path.join(video_folder, 'narration', 'pt', f'narration_0.{AUDIO_EXTENSION}'))
        has_en_final_narration = os.path.exists(os.path.join(video_folder, 'narration', 'en', f'narration_0.{AUDIO_EXTENSION}'))
        has_es_final_narration = os.path.exists(os.path.join(video_folder, 'narration', 'es', f'narration_0.{AUDIO_EXTENSION}'))
        
        # Check if animated.mp4 exists (required for language merge buttons)
        animated_video = os.path.join(video_folder, 'visuals', 'animated.mp4')
        has_animated = os.path.exists(animated_video)
        
        return jsonify({
            'success': True,
            'folder': folder,
            'image_prompts': image_prompts,
            'audio_segments': audio_segments_pt,  # Keep for backward compatibility
            'audio_segment_files': audio_segment_files_pt,  # Keep for backward compatibility
            'audio_segments_pt': audio_segments_pt,
            'audio_segment_files_pt': audio_segment_files_pt,
            'audio_segments_en': audio_segments_en,
            'audio_segment_files_en': audio_segment_files_en,
            'audio_segments_es': audio_segments_es,
            'audio_segment_files_es': audio_segment_files_es,
            'image_files': image_files,
            'theme': theme,
            'style': style,
            'negative_prompt': negative_prompt,
            'has_pt_narration': has_pt_narration,
            'has_en_narration': has_en_narration,
            'has_es_narration': has_es_narration,
            'has_pt_final_narration': has_pt_final_narration,
            'has_en_final_narration': has_en_final_narration,
            'has_es_final_narration': has_es_final_narration,
            'has_animated': has_animated
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/image/<int:index>', methods=['GET'])
def get_video_image(folder, index):
    """Get image from video folder by index."""
    try:
        video_folder = get_video_folder_path(folder)
        image_path = get_image_path(video_folder, index)
        if os.path.exists(image_path):
            return send_file(image_path, mimetype=f'image/{IMAGE_EXTENSION}')
        return jsonify({'error': 'Image not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/thumb', methods=['GET'])
@app.route('/api/videos/<path:folder>/thumb/<int:index>', methods=['GET'])
def get_video_thumb(folder, index=None):
    """Get thumbnail of image from video folder. If index is provided, returns thumbnail of that image."""
    try:
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder) or not os.path.isdir(video_folder):
            return jsonify({'error': 'Video folder not found'}), 404
        
        image_path = find_image_path_for_thumbnail(video_folder, index)
        if not image_path:
            return jsonify({'error': 'No images found in video folder'}), 404
        
        thumb_io = create_thumbnail_from_image(image_path)
        return send_file(thumb_io, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/audio-segment/<int:index>', methods=['GET'])
def get_video_audio_segment(folder, index):
    """Get audio segment from video folder by index and language."""
    try:
        video_folder = get_video_folder_path(folder)
        language = request.args.get('lang', 'pt')  # Default to Portuguese
        
        audio_path = get_audio_segment_path(video_folder, index, language)
        
        if os.path.exists(audio_path):
            return send_file(audio_path, mimetype=f'audio/{AUDIO_EXTENSION}')
        
        # Fallback to main narration file if segment doesn't exist
        lang_folder = os.path.join(video_folder, 'narration', language)
        narration_path = os.path.join(lang_folder, f'narration_0.{AUDIO_EXTENSION}')
        
        if os.path.exists(narration_path):
            return send_file(narration_path, mimetype=f'audio/{AUDIO_EXTENSION}')
        
        return jsonify({'error': 'Audio segment not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/update-image-prompt/<int:index>', methods=['POST'])
def update_image_prompt(folder, index):
    """Update an image prompt and regenerate the image."""
    try:
        data = request.get_json() or {}
        prompt = data.get('prompt', '')
        negative_prompt = data.get('negative_prompt', '')
        
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt is required'}), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        update_prompt_in_file(video_folder, index, prompt)
        
        # Use negative_prompt from request if provided, otherwise read from style file
        if not negative_prompt:
            negative_prompt = read_negative_prompt_from_style_file(video_folder)
        
        width, height = VIDEO_WIDTH, VIDEO_HEIGHT
        
        thread = threading.Thread(
            target=regenerate_image_async,
            args=(video_folder, index, prompt, width, height, negative_prompt)
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Regenerating image {index}...'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/regenerate-images-batch', methods=['POST'])
def regenerate_images_batch(folder):
    """Regenerate multiple images in batch (model loaded only once)."""
    try:
        data = request.get_json() or {}
        image_prompts = data.get('image_prompts', [])
        negative_prompt = data.get('negative_prompt', '')
        
        if not image_prompts:
            return jsonify({'success': False, 'error': 'At least one image prompt is required'}), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        for img_data in image_prompts:
            index = img_data.get('index')
            prompt = img_data.get('prompt', '')
            if not prompt:
                return jsonify({'success': False, 'error': f'Prompt is required for image {index}'}), 400
            update_prompt_in_file(video_folder, index, prompt)
        
        if not negative_prompt:
            negative_prompt = read_negative_prompt_from_style_file(video_folder)
        
        width, height = VIDEO_WIDTH, VIDEO_HEIGHT
        
        thread = threading.Thread(
            target=regenerate_images_batch_async,
            args=(video_folder, image_prompts, width, height, negative_prompt)
        )
        thread.start()
        
        indices = [img['index'] for img in image_prompts]
        return jsonify({
            'success': True,
            'message': f'Regenerating {len(indices)} image(s)...',
            'indices': indices
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/insert-image/<int:index>', methods=['POST'])
def insert_image(folder, index):
    """Insert a new image at a specific index, renaming subsequent images."""
    try:
        data = request.get_json() or {}
        prompt = data.get('prompt', '')
        negative_prompt = data.get('negative_prompt', '')
        
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt is required'}), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        # Use negative_prompt from request if provided, otherwise read from style file
        if not negative_prompt:
            negative_prompt = read_negative_prompt_from_style_file(video_folder)
        
        width, height = VIDEO_WIDTH, VIDEO_HEIGHT
        
        thread = threading.Thread(
            target=insert_image_async,
            args=(video_folder, index, prompt, width, height, negative_prompt)
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Inserting image at position {index}...'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/delete-image/<int:index>', methods=['DELETE'])
def delete_image(folder, index):
    """Delete an image at a specific index, renaming subsequent images."""
    try:
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        thread = threading.Thread(
            target=delete_image_async,
            args=(video_folder, index)
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Deleting image at position {index}...'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/update-audio-segment/<int:index>', methods=['POST'])
def update_audio_segment(folder, index):
    """Update an audio segment text and regenerate the audio."""
    try:
        data = request.get_json() or {}
        text = data.get('text', '')
        language = data.get('language', 'pt')  # Default to Portuguese for backward compatibility
        
        if not text:
            return jsonify({'success': False, 'error': 'Text is required'}), 400
        
        if language not in ['pt', 'en', 'es']:
            return jsonify({'success': False, 'error': 'Invalid language. Use "pt", "en", or "es"'}), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        thread = threading.Thread(
            target=regenerate_audio_segment_async,
            args=(video_folder, index, text, language)
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Regenerating audio segment {index} for {language}...'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/regenerate-all-audios', methods=['POST'])
def regenerate_all_audios(folder):
    """Regenerate all audio segments for a video."""
    try:
        data = request.get_json() or {}
        language = data.get('language', 'pt')  # Default to Portuguese for backward compatibility
        
        if language not in ['pt', 'en', 'es']:
            return jsonify({'success': False, 'error': 'Invalid language. Use "pt", "en", or "es"'}), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        thread = threading.Thread(
            target=regenerate_all_audios_async,
            args=(video_folder, language)
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Regenerating all audio segments for {language}...'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/merge', methods=['POST'])
def merge_video(folder):
    """Re-merge video and audio after edits (regenerates animated.mp4)."""
    try:
        data = request.get_json() or {}
        language = data.get('language', 'pt')
        
        if language not in ['pt', 'en', 'es']:
            return jsonify({'success': False, 'error': 'Invalid language. Use "pt", "en", or "es"'}), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        thread = threading.Thread(
            target=merge_video_async,
            args=(video_folder, folder, language)
        )
        thread.start()
        
        lang_name = {'pt': 'Portuguese', 'en': 'English', 'es': 'Spanish'}[language]
        return jsonify({
            'success': True,
            'message': f'Regenerating animated.mp4 and merging with {lang_name} audio...'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/merge/<language>', methods=['POST'])
def merge_video_language(folder, language):
    """Re-merge video and audio for a specific language, reusing existing animated.mp4."""
    try:
        if language not in ['pt', 'en', 'es']:
            return jsonify({'success': False, 'error': 'Invalid language. Use "pt", "en", or "es"'}), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        # Check if animated.mp4 exists (required for language merge)
        animated_video = os.path.join(video_folder, 'visuals', 'animated.mp4')
        if not os.path.exists(animated_video):
            return jsonify({
                'success': False,
                'error': 'animated.mp4 not found. Please use "Mesclar Vídeo Novamente" first to generate it.'
            }), 404
        
        # Check if language narration exists
        lang_folder = os.path.join(video_folder, 'narration', language)
        narration_file = os.path.join(lang_folder, 'narration.txt')
        if not os.path.exists(narration_file):
            lang_name = {'pt': 'Portuguese', 'en': 'English', 'es': 'Spanish'}[language]
            return jsonify({
                'success': False,
                'error': f'{lang_name} narration not found. Please generate the {language} version first.'
            }), 404
        
        thread = threading.Thread(
            target=merge_video_async_language,
            args=(video_folder, folder, language)
        )
        thread.start()
        
        lang_name = {'pt': 'Portuguese', 'en': 'English', 'es': 'Spanish'}[language]
        return jsonify({
            'success': True,
            'message': f'Merging {lang_name} video (reusing animated.mp4)...'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos/<path:folder>/delete-narration/<language>', methods=['DELETE'])
def delete_final_narration(folder, language):
    """Delete the final narration file (narration_0.wav) for a specific language, keeping only audio segments."""
    try:
        if language not in ['pt', 'en', 'es']:
            return jsonify({'success': False, 'error': 'Invalid language. Use "pt", "en", or "es"'}), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        from constants import AUDIO_EXTENSION
        
        lang_folder = os.path.join(video_folder, 'narration', language)
        narration_path = os.path.join(lang_folder, f'narration_0.{AUDIO_EXTENSION}')
        
        if not os.path.exists(narration_path):
            lang_name = {'pt': 'Portuguese', 'en': 'English', 'es': 'Spanish'}[language]
            return jsonify({
                'success': False,
                'error': f'{lang_name} final narration file (narration_0.{AUDIO_EXTENSION}) not found'
            }), 404
        
        # Delete the final narration file
        os.remove(narration_path)
        
        lang_name = {'pt': 'Portuguese', 'en': 'English', 'es': 'Spanish'}[language]
        log_success(f'Deleted {lang_name} final narration file (kept audio segments)', step='delete_narration')
        
        return jsonify({
            'success': True,
            'message': f'{lang_name} final narration file deleted. Audio segments preserved.'
        })
    except Exception as e:
        log_error(f'Error deleting final narration: {e}', step='delete_narration')
        return jsonify({'success': False, 'error': str(e)}), 500


def read_image_prompts_from_file(video_folder):
    """Read image prompts from image_prompts.txt file."""
    image_prompts = []
    prompts_file = os.path.join(video_folder, 'visuals', 'image_prompts.txt')
    if os.path.exists(prompts_file):
        with open(prompts_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('Prompt '):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        image_prompts.append(parts[1].strip())
    return image_prompts


def read_audio_segments_from_narration(video_folder, language='pt'):
    """Read narration file from language folder and split into audio segments (phrases)."""
    lang_folder = os.path.join(video_folder, 'narration', language)
    narration_file = os.path.join(lang_folder, 'narration.txt')
    if not os.path.exists(narration_file):
        return []
    
    with open(narration_file, 'r', encoding='utf-8') as f:
        narration_text = f.read()
        phrases, _, _ = split_narration_by_phrases(narration_text)
        return phrases


def read_style_file(video_folder):
    """Read style and negative prompt from style.txt.

    Expected format:
        style.txt
            🎨 Estilo Visual
            <style>

            🚫 Prompt Negativo
            <negative_prompt>
    """
    theme = ''
    style = ''
    negative_prompt = ''

    # Read from style.txt (current format)
    style_file = os.path.join(video_folder, 'visuals', 'style.txt')
    if os.path.exists(style_file):
        with open(style_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if '🎨 Estilo Visual' in content:
                style_lines = content.split('🎨 Estilo Visual', 1)[1].split('🚫', 1)[0].strip().split('\n')
                style = style_lines[0].strip() if style_lines else ''
            if '🚫 Prompt Negativo' in content:
                neg_section = content.split('🚫 Prompt Negativo', 1)[1]
                # Stop at first config marker if present
                neg_section = neg_section.split('⚙️', 1)[0]
                neg_lines = neg_section.strip().split('\n')
                negative_prompt = neg_lines[0].strip() if neg_lines else ''

    return theme, style, negative_prompt


def read_negative_prompt_from_style_file(video_folder):
    """Read only the negative prompt from style.txt."""
    _, _, negative_prompt = read_style_file(video_folder)
    return negative_prompt


def get_video_folder_path(folder):
    """Get full path to video folder."""
    return os.path.join(OUTPUT_DIR_VIDEOS, folder)


def get_image_path(video_folder, index):
    """Get path to image file by index in images subfolder."""
    images_dir = os.path.join(video_folder, 'images')
    return os.path.join(images_dir, f'image_{index:02d}.{IMAGE_EXTENSION}')


def find_audio_segments_directory(video_folder, language='pt'):
    """Find the audio segments directory for specific language.
    
    Args:
        video_folder: Video folder path
        language: Language code ('pt' or 'en')
    """
    # New structure: narration/{language}/audio_segments/
    lang_folder = os.path.join(video_folder, 'narration', language)
    audio_segments_dir = os.path.join(lang_folder, 'audio_segments')
    
    # For Portuguese, check old structure for backward compatibility
    if language == 'pt' and not os.path.exists(audio_segments_dir):
        temp_segments_dir = os.path.join(video_folder, 'temp_segments')
        old_audio_segments_dir = os.path.join(video_folder, 'audio_segments')
        old_audio_segments_pt = os.path.join(video_folder, 'narration', 'pt', 'audio_segments')
        
        if os.path.exists(temp_segments_dir):
            return temp_segments_dir
        elif os.path.exists(old_audio_segments_pt):
            return old_audio_segments_pt
        elif os.path.exists(old_audio_segments_dir):
            # Check if it's the old flat structure (has narration_0.wav directly)
            old_narration = os.path.join(old_audio_segments_dir, f'narration_0.{AUDIO_EXTENSION}')
            if os.path.exists(old_narration):
                return old_audio_segments_dir
    
    # Create directory if it doesn't exist
    os.makedirs(audio_segments_dir, exist_ok=True)
    return audio_segments_dir


def get_audio_segment_path(video_folder, index, language='pt'):
    """Get path to audio segment file by index and language."""
    segments_dir = find_audio_segments_directory(video_folder, language)
    return os.path.join(segments_dir, f'narration_{index}.{AUDIO_EXTENSION}')


def find_image_path_for_thumbnail(video_folder, index=None):
    """Find image path for thumbnail generation."""
    if index is not None:
        image_path = get_image_path(video_folder, index)
        if os.path.exists(image_path):
            return image_path
    
    # Default to first image
    default_path = get_image_path(video_folder, 1)
    if os.path.exists(default_path):
        return default_path
    
    # Find any image in images/ subfolder
    images_dir = os.path.join(video_folder, 'images')
    image_files = sorted(glob.glob(os.path.join(images_dir, f'image_*.{IMAGE_EXTENSION}')))
    return image_files[0] if image_files else None


def build_audio_segment_files_info(video_folder, folder, audio_segments, language='pt'):
    """Build list of audio segment file information for specific language."""
    audio_segment_files = []
    segments_dir = find_audio_segments_directory(video_folder, language)
    
    for i in range(len(audio_segments)):
        audio_file = os.path.join(segments_dir, f'narration_{i}.{AUDIO_EXTENSION}')
        if os.path.exists(audio_file):
            audio_segment_files.append({
                'index': i,
                'path': f'/api/videos/{folder}/audio-segment/{i}?lang={language}',
                'exists': True
            })
        else:
            audio_segment_files.append({
                'index': i,
                'path': None,
                'exists': False
            })
    
    return audio_segment_files


def build_image_files_info(video_folder, folder, image_prompts):
    """Build list of image file information."""
    image_files = []
    for i in range(1, len(image_prompts) + 1):
        image_path = get_image_path(video_folder, i)
        if os.path.exists(image_path):
            image_files.append({
                'index': i,
                'path': f'/api/videos/{folder}/image/{i}',
                'thumb_path': f'/api/videos/{folder}/thumb/{i}',
                'exists': True
            })
        else:
            image_files.append({
                'index': i,
                'path': None,
                'thumb_path': None,
                'exists': False
            })
    
    return image_files


def update_prompt_in_file(video_folder, index, new_prompt):
    """Update a specific prompt in image_prompts.txt file."""
    prompts_file = os.path.join(video_folder, 'visuals', 'image_prompts.txt')
    if not os.path.exists(prompts_file):
        return
    
    prompts = []
    with open(prompts_file, 'r', encoding='utf-8') as f:
        for line in f:
            line_stripped = line.rstrip('\n')
            if line_stripped.startswith('Prompt '):
                parts = line_stripped.split(':', 1)
                if len(parts) == 2:
                    try:
                        prompt_num = int(parts[0].replace('Prompt ', '').strip())
                        if prompt_num == index:
                            prompts.append(f'Prompt {index}: {new_prompt}\n')
                        else:
                            prompts.append(line)
                    except ValueError:
                        prompts.append(line)
                else:
                    prompts.append(line)
            else:
                prompts.append(line)
    
    with open(prompts_file, 'w', encoding='utf-8') as f:
        f.writelines(prompts)


def create_thumbnail_from_image(image_path, max_size=(256, 192)):
    """Create a thumbnail from an image file and return as BytesIO."""
    img = Image.open(image_path)
    
    try:
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
    except AttributeError:
        # Fallback for older Pillow versions
        img.thumbnail(max_size, Image.LANCZOS)
    
    thumb_io = BytesIO()
    img.save(thumb_io, format=IMAGE_EXTENSION, optimize=True)
    thumb_io.seek(0)
    return thumb_io


def regenerate_audio_phrase(video_folder, index, text, language='pt'):
    """Regenerate a single audio phrase."""
    segments_dir = find_audio_segments_directory(video_folder, language)
    os.makedirs(segments_dir, exist_ok=True)
    
    segment_path = os.path.join(segments_dir, f'narration_{index}.{AUDIO_EXTENSION}')
    
    # Use enhanced variation for video generation
    generate_tts_batch(
        texts=[text],
        output_paths=[segment_path],
        language=language,
    )
    log_success(f'Regenerated phrase {index}: {text[:50]}...', step='regenerate_audio')


def regenerate_missing_audio_phrases(video_folder, phrases, language='pt'):
    """Regenerate any missing audio phrase files."""
    segments_dir = find_audio_segments_directory(video_folder, language)
    os.makedirs(segments_dir, exist_ok=True)
    
    # Use enhanced variation for video generation
    for i, phrase_text in enumerate(phrases):
        seg_path = os.path.join(segments_dir, f'narration_{i}.{AUDIO_EXTENSION}')
        if not os.path.exists(seg_path):
            generate_tts_batch(
                texts=[phrase_text],
                output_paths=[seg_path],
                language=language,
            )
            log_success(f'Regenerated missing phrase {i}', step='regenerate_audio')


def collect_audio_segment_paths(video_folder, phrase_count, language='pt'):
    """Collect all audio segment file paths."""
    segments_dir = find_audio_segments_directory(video_folder, language)
    audio_segment_paths = []
    
    for i in range(phrase_count):
        seg_path = os.path.join(segments_dir, f'narration_{i}.{AUDIO_EXTENSION}')
        audio_segment_paths.append(seg_path)
    
    return audio_segment_paths


def recombine_audio_segments(video_folder, audio_segment_paths, silence_positions, language='pt', nosilence_positions=None):
    """Recombine all audio segments into final narration file in language folder."""
    lang_folder = os.path.join(video_folder, 'narration', language)
    os.makedirs(lang_folder, exist_ok=True)
    final_output_path = os.path.join(lang_folder, f'narration_0.{AUDIO_EXTENSION}')
    combine_audio_segments_with_silence(
        audio_segment_paths,
        final_output_path,
        silence_duration=DEFAULT_SILENCE_DURATION,
        silence_positions=silence_positions,
        nosilence_positions=nosilence_positions,
        language=language
    )


def collect_image_paths_in_order(video_folder, image_count):
    """Collect image paths in sequential order."""
    image_paths = []
    for i in range(1, image_count + 1):
        img_path = get_image_path(video_folder, i)
        if os.path.exists(img_path):
            image_paths.append(img_path)
    return image_paths

def regenerate_image_async(video_folder, index, prompt, width, height, negative_prompt):
    """Regenerate a single image in a video folder (async)."""
    try:
        # Ensure images directory exists
        images_dir = os.path.join(video_folder, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        image_path = get_image_path(video_folder, index)
        
        generate_image_to_path(
            prompt=prompt,
            width=width,
            height=height,
            negative_prompt=negative_prompt,
            output_path=image_path,
            output_dir=video_folder,
            image_index=index
        )
        
        log_success(f'Image {index} regenerated successfully', step='regenerate_image')
    except Exception as e:
        log_error(f'Error regenerating image {index}: {e}', step='regenerate_image')
        raise Exception(f'Error regenerating image {index}: {e}')


def regenerate_images_batch_async(video_folder, image_prompts, width, height, negative_prompt):
    """Regenerate multiple images in batch (model loaded only once)."""
    from app.images import ensure_output_directory_exists, cleanup_after_video_generation, manage_ollama_for_video_generation
    from image.generate import load_sdxl_model, generate_single_image_with_prompt, save_bgr_image_as_png
    
    pipe = None
    try:
        was_video_folder = manage_ollama_for_video_generation(video_folder)
        
        images_dir = os.path.join(video_folder, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        log(f'Loading SDXL model for batch regeneration of {len(image_prompts)} image(s)...', step='regenerate_images_batch')
        pipe = load_sdxl_model()
        
        for img_data in image_prompts:
            index = img_data['index']
            prompt = img_data['prompt']
            image_path = get_image_path(video_folder, index)
            
            log(f'Generating image {index}...', step='regenerate_images_batch')
            
            image_array, _ = generate_single_image_with_prompt(
                pipe, prompt, width, height, negative_prompt,
                output_dir=video_folder,
                image_index=index
            )
            
            ensure_output_directory_exists(image_path)
            save_bgr_image_as_png(image_array, image_path)
            
            log_success(f'Image {index} regenerated successfully', step='regenerate_images_batch')
        
        cleanup_after_video_generation(pipe, was_video_folder)
        log_success(f'All {len(image_prompts)} image(s) regenerated successfully', step='regenerate_images_batch')
    except Exception as e:
        if pipe is not None:
            try:
                cleanup_after_video_generation(pipe, manage_ollama_for_video_generation(video_folder))
            except:
                pass
        log_error(f'Error regenerating images batch: {e}', step='regenerate_images_batch')
        raise Exception(f'Error regenerating images batch: {e}')


def update_narration_file(video_folder, phrases, silence_positions, language='pt', nosilence_positions=None):
    """Reconstruct and update narration.txt file with updated phrases in language folder."""
    lang_folder = os.path.join(video_folder, 'narration', language)
    os.makedirs(lang_folder, exist_ok=True)
    narration_file = os.path.join(lang_folder, 'narration.txt')
    
    # Reconstruct narration text from phrases and silence/nosilence positions
    narration_lines = []
    silence_set = set(silence_positions) if silence_positions else set()
    nosilence_set = set(nosilence_positions) if nosilence_positions else set()
    
    for i, phrase in enumerate(phrases):
        line = phrase
        
        # Add separator if not the last phrase
        if i < len(phrases) - 1:
            # Check if there's a silence or nosilence marker after this phrase
            if i in silence_set:
                line += ' (silence)'
            elif i in nosilence_set:
                line += ' (nosilence)'
            else:
                # Only add dot if phrase doesn't already end with one
                if not line.rstrip().endswith('.'):
                    line += '.'
        
        narration_lines.append(line)
    
    # Join with newlines to preserve multi-line format
    narration_text = '\n'.join(narration_lines)
    
    # Write updated narration to file
    with open(narration_file, 'w', encoding='utf-8') as f:
        f.write(narration_text)
    
    log(f'Updated narration/{language}/narration.txt with {len(phrases)} phrases', step='update_narration')


def regenerate_audio_segment_async(video_folder, index, text, language='pt'):
    """Regenerate a single audio phrase and recombine all phrases (async)."""
    try:
        lang_folder = os.path.join(video_folder, 'narration', language)
        narration_file = os.path.join(lang_folder, 'narration.txt')
        if not os.path.exists(narration_file):
            log_error(f'Error: narration/{language}/narration.txt not found', step='regenerate_audio')
            return
        
        with open(narration_file, 'r', encoding='utf-8') as f:
            narration_text = f.read()
            phrases, silence_positions, nosilence_positions = split_narration_by_phrases(narration_text)
        
        if index < 0 or index >= len(phrases):
            log_error(f'Error: Invalid phrase index {index} (total phrases: {len(phrases)})', step='regenerate_audio')
            return
        
        # Update the phrase in the phrases list
        phrases[index] = text
        
        # Reconstruct narration.txt with updated phrase
        update_narration_file(video_folder, phrases, silence_positions, language=language, nosilence_positions=nosilence_positions)
        
        regenerate_audio_phrase(video_folder, index, text, language=language)
        regenerate_missing_audio_phrases(video_folder, phrases, language=language)
        audio_segment_paths = collect_audio_segment_paths(video_folder, len(phrases), language=language)
        recombine_audio_segments(video_folder, audio_segment_paths, silence_positions, language=language, nosilence_positions=nosilence_positions)
        
        log_success(f'Audio phrase {index} regenerated and recombined successfully for {language}', step='regenerate_audio')
    except Exception as e:
        log_error(f'Error regenerating audio phrase: {e}', step='regenerate_audio')
        raise Exception(f'Error regenerating audio phrase: {e}')


def regenerate_all_audios_async(video_folder, language='pt'):
    """Regenerate all audio phrases and recombine (async)."""
    try:
        lang_folder = os.path.join(video_folder, 'narration', language)
        narration_file = os.path.join(lang_folder, 'narration.txt')
        if not os.path.exists(narration_file):
            log_error(f'Error: narration/{language}/narration.txt not found', step='regenerate_all_audios')
            return
        
        with open(narration_file, 'r', encoding='utf-8') as f:
            narration_text = f.read()
            phrases, silence_positions, nosilence_positions = split_narration_by_phrases(narration_text)
        
        if not phrases:
            log_error('Error: No phrases found in narration', step='regenerate_all_audios')
            return
        
        # Regenerate all phrases
        for i, phrase_text in enumerate(phrases):
            regenerate_audio_phrase(video_folder, i, phrase_text, language=language)
        
        # Recombine all segments
        audio_segment_paths = collect_audio_segment_paths(video_folder, len(phrases), language=language)
        recombine_audio_segments(video_folder, audio_segment_paths, silence_positions, language=language, nosilence_positions=nosilence_positions)
        
        log_success(f'All {len(phrases)} audio phrases regenerated and recombined successfully for {language}', step='regenerate_all_audios')
    except Exception as e:
        log_error(f'Error regenerating all audio phrases: {e}', step='regenerate_all_audios')
        raise Exception(f'Error regenerating all audio phrases: {e}')


def ensure_audio_for_merge(video_folder, language='pt'):
    """Ensure narration_0.wav exists, regenerating from segments or creating segments if needed.
    
    Flow:
    1. If narration_0.wav exists → return its path
    2. If segments exist → regenerate narration_0.wav from segments
    3. If narration.txt exists but segments don't → generate all segments, then narration_0.wav
    4. Otherwise → raise exception
    
    Args:
        video_folder: Path to video folder
        language: Language code ('pt', 'en', or 'es')
        
    Returns:
        str: Path to narration_0.wav file
    """
    from video.merge import find_audio_path_for_merge
    from audio.generate import generate_audio
    from constants import AUDIO_EXTENSION
    
    lang_folder = os.path.join(video_folder, 'narration', language)
    narration_path = os.path.join(lang_folder, f'narration_0.{AUDIO_EXTENSION}')
    
    # Step 1: Check if narration_0.wav already exists
    if os.path.exists(narration_path):
        log(f'Using existing narration_0.{AUDIO_EXTENSION} for language {language}', step='merge_video')
        return narration_path
    
    # Step 2: Try to regenerate from existing segments
    try:
        log(f'Attempting to regenerate narration_0.{AUDIO_EXTENSION} from segments for language {language}...', step='merge_video')
        return find_audio_path_for_merge(video_folder, language=language)
    except Exception as e:
        log(f'Could not regenerate from segments: {e}', step='merge_video')
    
    # Step 3: Check if narration.txt exists, generate all segments if it does
    narration_file = os.path.join(lang_folder, 'narration.txt')
    if os.path.exists(narration_file):
        log(f'Generating all audio segments from narration.txt for language {language}...', step='merge_video')
        with open(narration_file, 'r', encoding='utf-8') as f:
            narration_text = f.read()
        
        # Generate all segments and narration_0.wav
        generate_audio(narration_text, video_folder, language=language)
        
        # Verify narration_0.wav was created
        if os.path.exists(narration_path):
            log_success(f'Generated audio for language {language}', step='merge_video')
            return narration_path
        else:
            raise Exception(f'Failed to generate narration_0.{AUDIO_EXTENSION} for language {language}')
    else:
        raise Exception(f'narration.txt not found for language {language} and audio segments are missing')


def merge_video_async(video_folder, folder_name, language='pt'):
    """Re-merge video and audio after edits (async). Regenerates animated.mp4 from images and merges with language audio."""
    try:
        lang_name = {'pt': 'Portuguese', 'en': 'English', 'es': 'Spanish'}[language]
        
        image_prompts = read_image_prompts_from_file(video_folder)
        if not image_prompts:
            log_error('Error: No image prompts found', step='merge_video')
            return
        
        # Look for images in images/ subfolder
        images_dir = os.path.join(video_folder, 'images')
        image_files = sorted(glob.glob(os.path.join(images_dir, f'image_*.{IMAGE_EXTENSION}')))
        image_count = len(image_files)
        
        if image_count == 0:
            log_error('Error: No images found', step='merge_video')
            return
        
        # Ensure narration_0.wav exists before calculating duration (uses existing, or creates from segments, or creates segments)
        ensure_audio_for_merge(video_folder, language=language)
        
        # Get duration from audio, fallback to image count if audio not found
        try:
            duration = get_audio_duration(video_folder=video_folder, language=language)
        except (FileNotFoundError, ValueError):
            # Fallback to image count calculation
            duration = len(image_prompts) * 6
        width, height = VIDEO_WIDTH, VIDEO_HEIGHT
        fps = 24
        
        total_frames, actual_image_count, frames_per_image_list = calculate_video_params(
            duration, fps, desired_image_count=len(image_prompts)
        )
        
        image_paths = collect_image_paths_in_order(video_folder, image_count)
        if not image_paths:
            log_error('Error: No valid images found', step='merge_video')
            return
        
        visuals_dir = os.path.join(video_folder, 'visuals')
        os.makedirs(visuals_dir, exist_ok=True)
        output_path = os.path.join(visuals_dir, f'animated.{VIDEO_EXTENSION}')
        log(f'Regenerating animated.mp4 from {len(image_paths)} images...', step='merge_video')
        generate_video_from_images(image_paths, output_path, frames_per_image_list, total_frames, fps, width, height)
        
        # Merge uses narration/{language}/narration_0.wav, with automatic subscription overlay if enabled and detected
        log(f'Merging animated.mp4 with {lang_name} audio...', step='merge_video')
        merge_video_audio(video_folder, language=language)
        
        theme = folder_name.split('_')[0] if '_' in folder_name else folder_name
        save_final_video(video_folder, theme, language=language)
        
        log_success(f'Video merged successfully with {lang_name} audio', step='merge_video')
    except Exception as e:
        lang_name = {'pt': 'Portuguese', 'en': 'English', 'es': 'Spanish'}.get(language, language)
        log_error(f'Error merging video with {lang_name} audio: {e}', step='merge_video')
        raise Exception(f'Error merging video with {lang_name} audio: {e}')


def merge_video_async_language(video_folder, folder_name, language):
    """Re-merge video and audio for a specific language, reusing existing animated.mp4 (async).
    
    Does NOT regenerate animated.mp4 - only merges with language-specific audio.
    """
    try:
        from constants import VIDEO_EXTENSION
        
        lang_name = {'pt': 'Portuguese', 'en': 'English', 'es': 'Spanish'}[language]
        
        # Verify animated.mp4 exists (should have been checked in endpoint, but double-check)
        animated_video = os.path.join(video_folder, 'visuals', f'animated.{VIDEO_EXTENSION}')
        if not os.path.exists(animated_video):
            raise Exception(f'animated.{VIDEO_EXTENSION} not found. Cannot merge without it.')
        
        log(f'Reusing existing animated.mp4 for {lang_name} merge', step='merge_video')
        
        # Ensure narration_0.wav exists for this language (regenerate from segments or create if needed)
        ensure_audio_for_merge(video_folder, language=language)
        
        # Merge existing animated.mp4 with language audio
        log(f'Merging animated video with {lang_name} audio...', step='merge_video')
        merge_video_audio(video_folder, language=language)
        
        # Save final video with appropriate filename based on language
        video_with_audio = os.path.join(video_folder, f'video_with_audio.{VIDEO_EXTENSION}')
        
        if not os.path.exists(video_with_audio):
            raise Exception('Merged video file not found after merge operation')
        
        if language == 'pt':
            # Portuguese: save as final_pt.mp4
            theme = folder_name.split('_')[0] if '_' in folder_name else folder_name
            from video.files import save_final_video
            save_final_video(video_folder, theme)
        else:
            # English/Spanish: save as final_{language}.mp4
            final_filename = f'final_{language}.mp4'
            final_path = os.path.join(video_folder, final_filename)
            
            if os.path.exists(final_path):
                os.remove(final_path)
            os.rename(video_with_audio, final_path)
        
        log_success(f'{lang_name} video merged successfully (reused animated.mp4)', step='merge_video')
            
    except Exception as e:
        lang_name = {'pt': 'Portuguese', 'en': 'English', 'es': 'Spanish'}[language]
        log_error(f'Error merging {lang_name} video: {e}', step='merge_video')
        raise Exception(f'Error merging {lang_name} video: {e}')


def rename_images_after_insert(video_folder, insert_index):
    """Rename all images with index >= insert_index to make room for new image."""
    images_dir = os.path.join(video_folder, 'images')
    if not os.path.exists(images_dir):
        return
    
    # Get all existing image files sorted by index
    image_files = sorted(glob.glob(os.path.join(images_dir, f'image_*.{IMAGE_EXTENSION}')))
    
    # Filter and extract indices
    image_indices = []
    for img_file in image_files:
        basename = os.path.basename(img_file)
        # Extract number from filename like "image_01.png"
        try:
            num_str = basename.replace('image_', '').replace(f'.{IMAGE_EXTENSION}', '')
            img_index = int(num_str)
            if img_index >= insert_index:
                image_indices.append((img_index, img_file))
        except ValueError:
            continue
    
    # Sort by index descending (rename from highest to lowest to avoid conflicts)
    image_indices.sort(key=lambda x: x[0], reverse=True)
    
    # Rename each image to index + 1
    for old_index, old_path in image_indices:
        new_index = old_index + 1
        new_path = os.path.join(images_dir, f'image_{new_index:02d}.{IMAGE_EXTENSION}')
        if os.path.exists(old_path):
            os.rename(old_path, new_path)


def insert_prompt_in_file(video_folder, index, new_prompt):
    """Insert a new prompt at a specific index in image_prompts.txt file, shifting others."""
    visuals_dir = os.path.join(video_folder, 'visuals')
    os.makedirs(visuals_dir, exist_ok=True)
    prompts_file = os.path.join(visuals_dir, 'image_prompts.txt')
    if not os.path.exists(prompts_file):
        # Create new file with the prompt
        with open(prompts_file, 'w', encoding='utf-8') as f:
            f.write(f'Prompt {index}: {new_prompt}\n')
        return
    
    prompts = []
    inserted = False
    
    with open(prompts_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Process all lines and renumber prompts after insertion point
    for line in lines:
        line_stripped = line.rstrip('\n')
        if line_stripped.startswith('Prompt '):
            parts = line_stripped.split(':', 1)
            if len(parts) == 2:
                try:
                    prompt_num = int(parts[0].replace('Prompt ', '').strip())
                    
                    # If we haven't inserted yet and this is the insertion point or after
                    if not inserted and prompt_num >= index:
                        # Insert the new prompt
                        prompts.append(f'Prompt {index}: {new_prompt}\n')
                        inserted = True
                    
                    # Add the existing prompt, renumbering if needed
                    if prompt_num >= index:
                        new_num = prompt_num + 1
                        prompts.append(f'Prompt {new_num}: {parts[1].strip()}\n')
                    else:
                        prompts.append(line)
                except ValueError:
                    prompts.append(line)
            else:
                prompts.append(line)
        else:
            prompts.append(line)
    
    # If we haven't inserted yet (all existing prompts are before index), append it
    if not inserted:
        prompts.append(f'Prompt {index}: {new_prompt}\n')
    
    with open(prompts_file, 'w', encoding='utf-8') as f:
        f.writelines(prompts)


def insert_image_async(video_folder, index, prompt, width, height, negative_prompt):
    """Insert a new image at a specific index (async)."""
    try:
        # Ensure images directory exists
        images_dir = os.path.join(video_folder, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        # Step 1: Rename all images with index >= insert_index (shift them up by 1)
        rename_images_after_insert(video_folder, index)
        
        # Step 2: Insert the prompt in image_prompts.txt
        insert_prompt_in_file(video_folder, index, prompt)
        
        # Step 3: Generate the new image at the insertion index
        image_path = get_image_path(video_folder, index)
        
        generate_image_to_path(
            prompt=prompt,
            width=width,
            height=height,
            negative_prompt=negative_prompt,
            output_path=image_path,
            output_dir=video_folder,
            image_index=index
        )
        
        log_success(f'Image inserted at position {index} successfully', step='insert_image')
    except Exception as e:
        log_error(f'Error inserting image at position {index}: {e}', step='insert_image')
        raise Exception(f'Error inserting image at position {index}: {e}')


def rename_images_after_delete(video_folder, delete_index):
    """Rename all images with index > delete_index to shift them down by 1."""
    images_dir = os.path.join(video_folder, 'images')
    if not os.path.exists(images_dir):
        return
    
    # Get all existing image files sorted by index
    image_files = sorted(glob.glob(os.path.join(images_dir, f'image_*.{IMAGE_EXTENSION}')))
    
    # Filter and extract indices that need to be renamed
    image_indices = []
    for img_file in image_files:
        basename = os.path.basename(img_file)
        # Extract number from filename like "image_01.png"
        try:
            num_str = basename.replace('image_', '').replace(f'.{IMAGE_EXTENSION}', '')
            img_index = int(num_str)
            if img_index > delete_index:
                image_indices.append((img_index, img_file))
        except ValueError:
            continue
    
    # Sort by index ascending (rename from lowest to highest to avoid conflicts)
    image_indices.sort(key=lambda x: x[0])
    
    # Rename each image to index - 1
    for old_index, old_path in image_indices:
        new_index = old_index - 1
        new_path = os.path.join(images_dir, f'image_{new_index:02d}.{IMAGE_EXTENSION}')
        if os.path.exists(old_path):
            os.rename(old_path, new_path)


def remove_prompt_from_file(video_folder, index):
    """Remove a prompt at a specific index from image_prompts.txt file, renumbering subsequent prompts."""
    prompts_file = os.path.join(video_folder, 'visuals', 'image_prompts.txt')
    if not os.path.exists(prompts_file):
        return
    
    prompts = []
    
    with open(prompts_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Process all lines and remove the prompt at the specified index, renumbering subsequent ones
    for line in lines:
        line_stripped = line.rstrip('\n')
        if line_stripped.startswith('Prompt '):
            parts = line_stripped.split(':', 1)
            if len(parts) == 2:
                try:
                    prompt_num = int(parts[0].replace('Prompt ', '').strip())
                    
                    # Skip the prompt at the deletion index
                    if prompt_num == index:
                        continue  # Don't add this line (deleted)
                    
                    # Renumber prompts after the deletion index
                    if prompt_num > index:
                        new_num = prompt_num - 1
                        prompts.append(f'Prompt {new_num}: {parts[1].strip()}\n')
                    else:
                        prompts.append(line)
                except ValueError:
                    prompts.append(line)
            else:
                prompts.append(line)
        else:
            prompts.append(line)
    
    with open(prompts_file, 'w', encoding='utf-8') as f:
        f.writelines(prompts)


def delete_image_async(video_folder, index):
    """Delete an image at a specific index and rename subsequent images (async)."""
    try:
        # Step 1: Delete the image file
        image_path = get_image_path(video_folder, index)
        if os.path.exists(image_path):
            os.remove(image_path)
            log(f'Deleted image file: {image_path}', step='delete_image')
        
        # Step 2: Rename all images with index > delete_index (shift them down by 1)
        rename_images_after_delete(video_folder, index)
        
        # Step 3: Remove the prompt from image_prompts.txt and renumber subsequent prompts
        remove_prompt_from_file(video_folder, index)
        
        log_success(f'Image deleted at position {index} successfully', step='delete_image')
    except Exception as e:
        log_error(f'Error deleting image at position {index}: {e}', step='delete_image')
        raise Exception(f'Error deleting image at position {index}: {e}')
