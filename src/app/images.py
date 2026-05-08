import os
import threading
import time
from datetime import datetime

from flask import Blueprint, jsonify, send_file, request
from constants import OUTPUT_DIR_IMAGES, IMAGE_EXTENSION
from app.utils import list_files, delete_files_by_pattern
from image.generate import load_sdxl_model, generate_single_image_with_prompt, save_bgr_image_as_png, unload_model
from logger import log, log_error
from ollama_client import stop_ollama_temporarily, restart_ollama
from env import VIDEO_WIDTH, VIDEO_HEIGHT
from status import update_status
        

app = Blueprint('images', __name__)

@app.route('/api/generate-image', methods=['POST'])
def generate_image():
    """Generate a new image from prompt and parameters."""
    try:
        data = request.get_json()
        is_valid, error_message = validate_image_request(data)
        if not is_valid:
            return jsonify({'success': False, 'error': error_message}), 400
        
        params = extract_image_request_data(data)
        
        thread = threading.Thread(
            target=generate_image_async,
            args=(params['prompt'], params['width'], params['height'], params['negative_prompt'])
        )
        thread.start()
        
        response = build_image_generation_response(params['prompt'], params['width'], params['height'])
        return jsonify(response)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/images', methods=['GET'])
def list_images():
    """List all generated images."""
    try:
        images = list_files(OUTPUT_DIR_IMAGES, f'*.{IMAGE_EXTENSION}', 'images')
        return jsonify({'success': True, 'images': images})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/images/<filename>')
def get_image(filename):
    """Get image file by filename."""
    try:
        image_path = get_image_path(filename)
        if os.path.exists(image_path):
            return send_file(image_path, mimetype=f'image/{IMAGE_EXTENSION}')
        return jsonify({'error': 'Imagem não encontrada'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/images/<filename>', methods=['DELETE'])
def delete_image(filename):
    """Delete an image file."""
    try:
        image_path = get_image_path(filename)
        if delete_image_file(image_path):
            return jsonify({'success': True, 'message': 'Imagem deletada'})
        return jsonify({'success': False, 'error': 'Imagem não encontrada'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/images/all', methods=['DELETE'])
def delete_all_images():
    """Delete all images."""
    try:
        deleted_count = delete_all_image_files()
        return jsonify({
            'success': True,
            'message': f'{deleted_count} imagem(s) deletada(s)',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/images/default-resolution', methods=['GET'])
def get_default_image_resolution():
    """Get default resolution from environment variables (VIDEO_WIDTH, VIDEO_HEIGHT)."""
    return jsonify({
        'success': True,
        'width': VIDEO_WIDTH,
        'height': VIDEO_HEIGHT
    })

def validate_image_request(data):
    """Validate image generation request data."""
    prompt = data.get('prompt', '')
    if not prompt:
        return False, 'Prompt é obrigatório'
    return True, None


def extract_image_request_data(data):
    """Extract and return image generation parameters from request data."""
    return {
        'prompt': data.get('prompt', ''),
        'width': data.get('width', VIDEO_WIDTH),
        'height': data.get('height', VIDEO_HEIGHT),
        'negative_prompt': data.get('negative_prompt', '')
    }


def get_image_path(filename):
    """Get full path to image file."""
    return os.path.join(OUTPUT_DIR_IMAGES, filename)


def generate_image_filename():
    """Generate a unique filename for a new image."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f'image_{timestamp}.{IMAGE_EXTENSION}'


def get_output_path_for_image(filename):
    """Get full output path for an image file."""
    return os.path.join(OUTPUT_DIR_IMAGES, filename)


def truncate_prompt(prompt, max_length=50):
    """Truncate prompt text for display purposes."""
    return prompt[:max_length] + '...' if len(prompt) > max_length else prompt


def is_video_folder_path(output_dir):
    """Check if output directory is a video folder (not the images directory)."""
    if not output_dir:
        return False
    
    abs_output_dir = os.path.abspath(output_dir)
    abs_images_dir = os.path.abspath(OUTPUT_DIR_IMAGES)
    return not abs_output_dir.startswith(abs_images_dir)


def ensure_output_directory_exists(output_path):
    """Ensure the output directory for the image exists."""
    output_dir_path = os.path.dirname(output_path)
    if output_dir_path:
        os.makedirs(output_dir_path, exist_ok=True)


def generate_image_with_model(prompt, width, height, negative_prompt, output_dir=None, image_index=None):
    """Generate image using SDXL model."""
    pipe = load_sdxl_model()
    image_array, full_prompt = generate_single_image_with_prompt(
        pipe, prompt, width, height, negative_prompt,
        output_dir=output_dir, image_index=image_index
    )
    return pipe, image_array


def save_generated_image(image_array, output_path):
    """Save generated image array to file."""
    save_bgr_image_as_png(image_array, output_path)


def manage_ollama_for_video_generation(output_dir):
    """Stop and restart Ollama if generating for video folder (to free GPU memory)."""
    
    if is_video_folder_path(output_dir):
        log('🛑 Stopping Ollama for image generation...', step='ollama_management')
        stop_ollama_temporarily()
        return True
    return False


def cleanup_after_video_generation(pipe, was_video_folder):
    """Clean up model and restart Ollama after video folder image generation."""
    if was_video_folder:
        unload_model(pipe)
        log('🔄 Restarting Ollama...', step='ollama_management')
        restart_ollama()
        time.sleep(3)


def generate_image_to_path(prompt, width, height, negative_prompt, output_path, output_dir=None, image_index=None):
    """
    Generate an image and save it to a specific path.
    This is a reusable function that can be called from both regular image generation
    and video editing endpoints.
    
    Args:
        prompt: Image generation prompt
        width: Image width
        height: Image height
        negative_prompt: Negative prompt
        output_path: Full path where the image should be saved
        output_dir: Optional output directory (for original image saving)
        image_index: Optional image index (for original image saving)
    
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    try:
        was_video_folder = manage_ollama_for_video_generation(output_dir)
        
        pipe, image_array = generate_image_with_model(
            prompt, width, height, negative_prompt, output_dir, image_index
        )
        
        ensure_output_directory_exists(output_path)
        save_generated_image(image_array, output_path)
        
        cleanup_after_video_generation(pipe, was_video_folder)
        
        return True, None
    except Exception as e:
        error_msg = f'Error generating image: {e}'
        log_error(error_msg, step='generate_image')
        return False, error_msg


def delete_image_file(image_path):
    """Delete an image file."""
    if os.path.exists(image_path):
        os.remove(image_path)
        return True
    return False


def delete_all_image_files():
    """Delete all image files in the images directory."""
    return delete_files_by_pattern(OUTPUT_DIR_IMAGES, f'*.{IMAGE_EXTENSION}')


def build_image_generation_response(prompt, width, height):
    """Build response for image generation request."""
    return {
        'success': True,
        'message': f'✅ Geração de imagem iniciada!',
        'info': f'Acompanhe o progresso em tempo real abaixo.',
        'prompt': truncate_prompt(prompt),
        'dimensions': f'{width}x{height}',
        'note': 'A imagem está sendo gerada. Monitore o status abaixo.'
    }


def generate_image_async(prompt, width, height, negative_prompt):
    """Generate image asynchronously in background thread."""
    try:
        # Update status: starting image generation
        update_status('loading', progress_percent=0, message='Carregando modelo SDXL...')
        
        filename = generate_image_filename()
        output_path = get_output_path_for_image(filename)
        
        # Update status: generating image
        update_status('generating', progress_percent=50, message=f'Gerando imagem: {truncate_prompt(prompt)}...')
        
        success, error_msg = generate_image_to_path(
            prompt, width, height, negative_prompt, output_path
        )
        
        if success:
            # Update status: complete
            update_status('complete', progress_percent=100, message=f'Imagem gerada com sucesso: {filename}')
        else:
            # Update status: error
            update_status('error', progress_percent=0, message=f'Erro ao gerar imagem: {error_msg}')
    except Exception as e:
        error_msg = f'Error generating image: {e}'
        log_error(error_msg, step='generate_image')
        update_status('error', progress_percent=0, message=error_msg)
