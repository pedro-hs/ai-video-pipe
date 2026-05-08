import os
import glob
import shutil
import threading
import time
import traceback

from flask import Blueprint, jsonify, send_file, request
from datetime import datetime

from constants import OUTPUT_DIR_VIDEOS, VIDEO_FILENAME, VIDEO_EXTENSION
from app.utils import format_file_size, format_timestamp, delete_files_by_pattern
from video.generate import generate_complete_video
from video.utils import calculate_duration_from_narration
from video.export_language import generate_english_video, generate_spanish_video, generate_portuguese_video
from video.shorts import (
    generate_all_shorts, 
    generate_shorts_for_language as generate_shorts_for_lang,
    create_animated_videos_from_images,
    calculate_split_timestamps
)
from video.paragraph_analysis import (
    analyze_narration_for_adjustment, 
    apply_suggestions_to_paragraph, 
    split_narration_by_paragraphs, 
    combine_paragraphs_with_silence,
    generate_temp_paragraph_audio,
    get_portuguese_paragraph_durations,
    get_portuguese_paragraphs
)
from logger import log_error

app = Blueprint('videos', __name__)


class MusicFileWrapper:
    """Wrapper for music file data to preserve content after request context ends."""
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content
        self._position = 0
    
    def seek(self, position):
        self._position = position
    
    def read(self):
        self.seek(0)
        return self._content

@app.route('/api/generate', methods=['POST'])
def generate_video():
    """Generate a new video from narration and parameters."""
    try:
        # Support both JSON and form-data requests
        if request.is_json:
            data = request.get_json()
        else:
            # Extract JSON data from form if present, otherwise use form fields
            json_data = request.form.get('data')
            if json_data:
                import json
                data = json.loads(json_data)
            else:
                data = {
                    'narration': request.form.get('narration'),
                    'orientation': request.form.get('orientation', 'horizontal'),
                    'style': request.form.get('style'),
                    'negative_prompt': request.form.get('negative_prompt', '')
                }
        
        is_valid, error_message = validate_video_request(data)
        if not is_valid:
            return jsonify({'success': False, 'error': error_message}), 400
        
        params = extract_video_request_data(data)
        duration = calculate_duration_from_narration(params['narration'])
        video_id = generate_video_id(params['narration'])
        filename = f'{video_id}.{VIDEO_EXTENSION}'
        
        # Get music files if uploaded (read content immediately while request context is active)
        music_files = []
        if request.files:
            uploaded_files = request.files.getlist('musics')
            for uploaded_file in uploaded_files:
                if uploaded_file and uploaded_file.filename:
                    # Read file content immediately while request context is active
                    uploaded_file.seek(0)
                    file_content = uploaded_file.read()
                    filename = uploaded_file.filename
                    # Create wrapper to preserve file data after request context ends
                    music_files.append(MusicFileWrapper(filename, file_content))
        
        thread = threading.Thread(
            target=generate_video_async,
            args=(params['narration'], duration, params['orientation'], 
                  params['style'], params['negative_prompt'], params['language'], music_files, video_id)
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Geração iniciada!',
            'video_id': video_id,
            'filename': filename,
            'estimated_duration': duration
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/videos', methods=['GET'])
def list_videos():
    """List all generated videos."""
    try:
        videos = list_all_videos()
        return jsonify({'success': True, 'videos': videos})
    except Exception as e:
        error_msg = str(e)
        log_error(f'Error listing videos: {error_msg}', step='list_videos')
        traceback.print_exc()
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route('/api/videos/<path:filename>')
def get_video(filename):
    """Get video file by filename."""
    try:
        video_path = get_video_path(filename)
        if os.path.exists(video_path):
            mimetype = f'video/{VIDEO_EXTENSION}'
            return send_file(video_path, mimetype=mimetype)
        return jsonify({'error': 'Vídeo não encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def validate_video_request(data):
    """Validate video generation request data."""
    required_fields = ['narration', 'style']
    for field in required_fields:
        if not data.get(field):
            return False, 'Roteiro de narração e estilo são obrigatórios'
    return True, None


def extract_video_request_data(data):
    """Extract and return video generation parameters from request data."""
    return {
        'narration': data.get('narration'),
        'orientation': data.get('orientation', 'horizontal'),
        'style': data.get('style'),
        'negative_prompt': data.get('negative_prompt', ''),
        'language': data.get('language', 'pt')
    }


def generate_video_id(theme):
    """Generate a unique video ID from theme."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_part = str(int(time.time()) % 10000)
    theme_max_length = 30
    clean_theme = theme[:theme_max_length].replace(' ', '_').replace('/', '_')
    return f'{clean_theme}_{random_part}_{timestamp}'


def get_video_path(filename):
    """Get full path to video file or folder."""
    return os.path.join(OUTPUT_DIR_VIDEOS, filename)


def get_video_folder_path(folder):
    """Get full path to video folder."""
    return os.path.join(OUTPUT_DIR_VIDEOS, folder)


def get_final_video_path(folder_path):
    """Get path to final video file in folder (checks pt, en, es)."""
    for lang in ['pt', 'en', 'es']:
        video_path = os.path.join(folder_path, f'final_{lang}.{VIDEO_EXTENSION}')
        if os.path.exists(video_path):
            return video_path
    return os.path.join(folder_path, VIDEO_FILENAME)


def is_video_folder(folder_path):
    """Check if folder contains a final video file (pt, en, or es)."""
    for lang in ['pt', 'en', 'es']:
        video_path = os.path.join(folder_path, f'final_{lang}.{VIDEO_EXTENSION}')
        if os.path.exists(video_path):
            return True
    return False


def build_video_info_from_folder(folder_path):
    """Build video info dictionary from folder path."""
    try:
        folder_name = os.path.basename(folder_path)
        final_pt_video = os.path.join(folder_path, 'final_pt.mp4')
        final_en_video = os.path.join(folder_path, 'final_en.mp4')
        final_es_video = os.path.join(folder_path, 'final_es.mp4')
        pt_folder = os.path.join(folder_path, 'narration', 'pt')
        en_folder = os.path.join(folder_path, 'narration', 'en')
        es_folder = os.path.join(folder_path, 'narration', 'es')
        narration_pt_file = os.path.join(pt_folder, 'narration.txt')
        narration_en_file = os.path.join(en_folder, 'narration.txt')
        narration_es_file = os.path.join(es_folder, 'narration.txt')
        
        has_portuguese = os.path.exists(final_pt_video)
        has_english = os.path.exists(final_en_video)
        has_spanish = os.path.exists(final_es_video)
        has_portuguese_narration = os.path.exists(narration_pt_file)
        has_english_narration = os.path.exists(narration_en_file)
        has_spanish_narration = os.path.exists(narration_es_file)
        
        if not (has_portuguese or has_english or has_spanish):
            return None
        
        main_video = final_pt_video if has_portuguese else (final_en_video if has_english else final_es_video)
        stat = os.stat(main_video)
        main_filename = os.path.basename(main_video)
        
        shorts_pt_dir = os.path.join(folder_path, 'shorts', 'pt')
        shorts_en_dir = os.path.join(folder_path, 'shorts', 'en')
        shorts_es_dir = os.path.join(folder_path, 'shorts', 'es')
        
        has_shorts_pt = os.path.exists(shorts_pt_dir) and len(glob.glob(os.path.join(shorts_pt_dir, f'short_*.{VIDEO_EXTENSION}'))) > 0
        has_shorts_en = os.path.exists(shorts_en_dir) and len(glob.glob(os.path.join(shorts_en_dir, f'short_*.{VIDEO_EXTENSION}'))) > 0
        has_shorts_es = os.path.exists(shorts_es_dir) and len(glob.glob(os.path.join(shorts_es_dir, f'short_*.{VIDEO_EXTENSION}'))) > 0
        
        return {
            'filename': f'{folder_name}/{main_filename}',
            'folder': folder_name,
            'size': format_file_size(stat.st_size),
            'created': format_timestamp(stat.st_mtime),
            'path': f'/api/videos/{folder_name}/{main_filename}',
            'thumb_path': f'/api/videos/{folder_name}/thumb',
            'has_portuguese': has_portuguese,
            'portuguese_path': f'/api/videos/{folder_name}/final_pt.mp4' if has_portuguese else None,
            'has_portuguese_narration': has_portuguese_narration,
            'has_english': has_english,
            'english_path': f'/api/videos/{folder_name}/final_en.mp4' if has_english else None,
            'has_english_narration': has_english_narration,
            'has_spanish': has_spanish,
            'spanish_path': f'/api/videos/{folder_name}/final_es.mp4' if has_spanish else None,
            'has_spanish_narration': has_spanish_narration,
            'has_shorts_pt': has_shorts_pt,
            'has_shorts_en': has_shorts_en,
            'has_shorts_es': has_shorts_es
        }
    except Exception as e:
        traceback.print_exc()
        return None


def build_video_info_from_file(video_path, video_folders):
    """Build video info dictionary from video file path."""
    filename = os.path.basename(video_path)
    
    # Skip if this file belongs to a folder we already processed
    if any(filename.startswith(os.path.basename(folder)) for folder in video_folders):
        return None
    
    stat = os.stat(video_path)
    return {
        'filename': filename,
        'folder': None,
        'size': format_file_size(stat.st_size),
        'created': format_timestamp(stat.st_mtime),
        'path': f'/api/videos/{filename}'
    }


def get_safe_mtime(path):
    """Get file modification time safely, handling permission errors."""
    try:
        return os.path.getmtime(path)
    except (OSError, IOError, PermissionError):
        return 0


def find_all_video_folders():
    """Find all folders in videos directory that contain final video files."""
    if not os.path.exists(OUTPUT_DIR_VIDEOS):
        return []
    
    all_dirs = [d for d in glob.glob(os.path.join(OUTPUT_DIR_VIDEOS, '*')) if os.path.isdir(d)]
    return [d for d in all_dirs if is_video_folder(d)]


def find_all_video_files():
    """Find all video files directly in videos directory."""
    return glob.glob(os.path.join(OUTPUT_DIR_VIDEOS, f'*.{VIDEO_EXTENSION}'))


def collect_videos_from_folders(video_folders):
    """Collect video info from all video folders."""
    videos = []
    for folder_path in sorted(video_folders, key=get_safe_mtime, reverse=True):
        try:
            video_info = build_video_info_from_folder(folder_path)
            if video_info:
                videos.append(video_info)
        except Exception as e:
            log_error(f'Error processing video folder {folder_path}: {e}', step='list_videos')
            continue
    return videos


def collect_videos_from_files(video_files, video_folders):
    """Collect video info from all video files (excluding those in folders)."""
    videos = []
    for video_path in sorted(video_files, key=get_safe_mtime, reverse=True):
        try:
            video_info = build_video_info_from_file(video_path, video_folders)
            if video_info:
                videos.append(video_info)
        except Exception as e:
            log_error(f'Error processing video file {video_path}: {e}', step='list_videos')
            continue
    return videos


def list_all_videos():
    """List all videos from folders and files."""
    try:
        video_folders = find_all_video_folders()
        videos = collect_videos_from_folders(video_folders)
        
        video_files = find_all_video_files()
        videos.extend(collect_videos_from_files(video_files, video_folders))
        
        return videos
    except Exception as e:
        log_error(f'Error in list_all_videos: {e}', step='list_videos')
        traceback.print_exc()
        raise


def should_delete_folder(folder_path):
    """Check if folder should be deleted (contains final video or starts with 'video_')."""
    return (is_video_folder(folder_path) or 
            os.path.basename(folder_path).startswith('video_'))


def delete_video_folder(folder_path):
    """Delete a video folder if it meets deletion criteria."""
    try:
        if should_delete_folder(folder_path):
            shutil.rmtree(folder_path)
            return True
    except Exception:
        pass
    return False


def find_all_candidate_folders():
    """Find all candidate folders for deletion."""
    return [d for d in glob.glob(os.path.join(OUTPUT_DIR_VIDEOS, '*')) if os.path.isdir(d)]


def delete_all_video_folders():
    """Delete all video folders that meet deletion criteria."""
    deleted_count = 0
    candidate_dirs = find_all_candidate_folders()
    for folder_path in candidate_dirs:
        if delete_video_folder(folder_path):
            deleted_count += 1
    return deleted_count


def delete_video_file_or_folder(video_path):
    """Delete a video file or folder."""
    if os.path.isdir(video_path):
        shutil.rmtree(video_path)
        return 'Vídeo e pasta deletados'
    else:
        os.remove(video_path)
        return 'Vídeo deletado'

def generate_video_async(narration, duration, orientation, style, negative_prompt, language='pt', music_files=None, video_id=None):
    """Generate video asynchronously in background thread."""
    try:
        generate_complete_video(
            narration_script=narration,
            duration=duration,
            orientation=orientation,
            style=style,
            negative_prompt=negative_prompt,
            language=language,
            music_files=music_files,
            video_id=video_id
        )
    except Exception as e:
        log_error(f'Error generating video: {e}', step='generate_video')


@app.route('/api/videos/<path:folder>/export-english', methods=['POST'])
def export_video_english(folder):
    """Export existing video with English narration (user-provided).
    
    Supports two modes:
    1. Review mode: Returns suggestions for duration adjustment
    2. Apply mode: Applies approved suggestions and generates video
    """
    try:
        data = request.get_json() or {}
        english_narration = data.get('narration_en', '').strip()
        mode = data.get('mode', 'review')  # 'review' or 'apply'
        
        if not english_narration:
            return jsonify({
                'success': False, 
                'error': 'English narration is required'
            }), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        # Check if animated video exists (required for English export)
        animated_video = os.path.join(video_folder, 'visuals', 'animated.mp4')
        if not os.path.exists(animated_video):
            return jsonify({
                'success': False, 
                'error': 'Video not found. Cannot export English version.'
            }), 404
        
        # Check if English version already exists
        final_en_video = os.path.join(video_folder, 'final_en.mp4')
        if os.path.exists(final_en_video) and mode == 'review':
            return jsonify({
                'success': False,
                'error': 'English version already exists'
            }), 400
        
        if mode == 'review':
            # Analyze and return suggestions
            try:
                analysis_result = analyze_narration_for_adjustment(
                    video_folder, english_narration, 'en'
                )
                return jsonify({
                    'success': True,
                    'needs_review': True,
                    'paragraphs': analysis_result['paragraphs'],
                    'portuguese_paragraphs': analysis_result['portuguese_paragraphs']
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Error analyzing narration: {str(e)}'
                }), 500
        
        elif mode == 'apply':
            # Apply approved suggestions and generate video
            approved_suggestions = data.get('approved_suggestions', [])
            
            # Apply suggestions to paragraphs
            paragraphs = split_narration_by_paragraphs(english_narration)
            adjusted_paragraphs = []
            
            for i, paragraph in enumerate(paragraphs):
                if i < len(approved_suggestions):
                    suggestion_data = approved_suggestions[i]
                    if suggestion_data.get('apply', False):
                        adjusted = apply_suggestions_to_paragraph(
                            paragraph,
                            suggestion_data.get('suggestions', {}),
                            suggestion_data.get('approved_add', []),
                            suggestion_data.get('approved_remove', [])
                        )
                        adjusted_paragraphs.append(adjusted)
                    else:
                        adjusted_paragraphs.append(paragraph)
                else:
                    adjusted_paragraphs.append(paragraph)
            
            # Combine adjusted paragraphs
            final_narration = combine_paragraphs_with_silence(adjusted_paragraphs)
            
            # Export in background thread
            thread = threading.Thread(
                target=export_video_english_async,
                args=(video_folder, final_narration, folder)
            )
            thread.start()
            
            return jsonify({
                'success': True,
                'message': 'English export iniciado!'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Invalid mode: {mode}. Use "review" or "apply"'
            }), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def export_video_english_async(video_folder, english_narration, folder_name):
    """Export video in English asynchronously."""
    try:
        generate_english_video(video_folder, english_narration)
    except Exception as e:
        log_error(f'Error exporting English video: {e}', step='export_english')


@app.route('/api/videos/<path:folder>/export-spanish', methods=['POST'])
def export_video_spanish(folder):
    """Export existing video with Spanish narration (user-provided).
    
    Supports two modes:
    1. Review mode: Returns suggestions for duration adjustment
    2. Apply mode: Applies approved suggestions and generates video
    """
    try:
        data = request.get_json() or {}
        spanish_narration = data.get('narration_es', '').strip()
        mode = data.get('mode', 'review')  # 'review' or 'apply'
        
        if not spanish_narration:
            return jsonify({
                'success': False, 
                'error': 'Spanish narration is required'
            }), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        # Check if animated video exists (required for Spanish export)
        animated_video = os.path.join(video_folder, 'visuals', 'animated.mp4')
        if not os.path.exists(animated_video):
            return jsonify({
                'success': False, 
                'error': 'Video not found. Cannot export Spanish version.'
            }), 404
        
        # Check if Spanish version already exists
        final_es_video = os.path.join(video_folder, 'final_es.mp4')
        if os.path.exists(final_es_video) and mode == 'review':
            return jsonify({
                'success': False,
                'error': 'Spanish version already exists'
            }), 400
        
        if mode == 'review':
            # Analyze and return suggestions
            try:
                analysis_result = analyze_narration_for_adjustment(
                    video_folder, spanish_narration, 'es'
                )
                return jsonify({
                    'success': True,
                    'needs_review': True,
                    'paragraphs': analysis_result['paragraphs'],
                    'portuguese_paragraphs': analysis_result['portuguese_paragraphs']
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Error analyzing narration: {str(e)}'
                }), 500
        
        elif mode == 'apply':
            # Apply approved suggestions and generate video
            approved_suggestions = data.get('approved_suggestions', [])
            
            # Apply suggestions to paragraphs
            paragraphs = split_narration_by_paragraphs(spanish_narration)
            adjusted_paragraphs = []
            
            for i, paragraph in enumerate(paragraphs):
                if i < len(approved_suggestions):
                    suggestion_data = approved_suggestions[i]
                    if suggestion_data.get('apply', False):
                        adjusted = apply_suggestions_to_paragraph(
                            paragraph,
                            suggestion_data.get('suggestions', {}),
                            suggestion_data.get('approved_add', []),
                            suggestion_data.get('approved_remove', [])
                        )
                        adjusted_paragraphs.append(adjusted)
                    else:
                        adjusted_paragraphs.append(paragraph)
                else:
                    adjusted_paragraphs.append(paragraph)
            
            # Combine adjusted paragraphs
            final_narration = combine_paragraphs_with_silence(adjusted_paragraphs)
            
            # Export in background thread
            thread = threading.Thread(
                target=export_video_spanish_async,
                args=(video_folder, final_narration, folder)
            )
            thread.start()
            
            return jsonify({
                'success': True,
                'message': 'Spanish export iniciado!'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Invalid mode: {mode}. Use "review" or "apply"'
            }), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def export_video_spanish_async(video_folder, spanish_narration, folder_name):
    """Export video in Spanish asynchronously."""
    try:
        generate_spanish_video(video_folder, spanish_narration)
    except Exception as e:
        log_error(f'Error exporting Spanish video: {e}', step='export_spanish')


@app.route('/api/videos/<path:folder>/export-portuguese', methods=['POST'])
def export_video_portuguese(folder):
    """Export existing video with Portuguese narration (user-provided).
    
    Supports two modes:
    1. Review mode: Returns suggestions for duration adjustment
    2. Apply mode: Applies approved suggestions and generates video
    """
    try:
        data = request.get_json() or {}
        portuguese_narration = data.get('narration_pt', '').strip()
        mode = data.get('mode', 'review')  # 'review' or 'apply'
        
        if not portuguese_narration:
            return jsonify({
                'success': False, 
                'error': 'Portuguese narration is required'
            }), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        # Check if animated video exists (required for Portuguese export)
        animated_video = os.path.join(video_folder, 'visuals', 'animated.mp4')
        if not os.path.exists(animated_video):
            return jsonify({
                'success': False, 
                'error': 'Video not found. Cannot export Portuguese version.'
            }), 404
        
        # Check if Portuguese version already exists
        final_pt_video = os.path.join(video_folder, 'final_pt.mp4')
        if os.path.exists(final_pt_video) and mode == 'review':
            return jsonify({
                'success': False,
                'error': 'Portuguese version already exists'
            }), 400
        
        if mode == 'review':
            # For Portuguese export, review mode is not supported (no PT audio to compare against)
            return jsonify({
                'success': False,
                'error': 'Review mode not supported for Portuguese export. Use direct mode.'
            }), 400
        
        elif mode == 'apply':
            # Apply approved suggestions and generate video
            approved_suggestions = data.get('approved_suggestions', [])
            
            # Apply suggestions to paragraphs
            paragraphs = split_narration_by_paragraphs(portuguese_narration)
            adjusted_paragraphs = []
            
            for i, paragraph in enumerate(paragraphs):
                if i < len(approved_suggestions):
                    suggestion_data = approved_suggestions[i]
                    if suggestion_data.get('apply', False):
                        adjusted = apply_suggestions_to_paragraph(
                            paragraph,
                            suggestion_data.get('suggestions', {}),
                            suggestion_data.get('approved_add', []),
                            suggestion_data.get('approved_remove', [])
                        )
                        adjusted_paragraphs.append(adjusted)
                    else:
                        adjusted_paragraphs.append(paragraph)
                else:
                    adjusted_paragraphs.append(paragraph)
            
            # Combine adjusted paragraphs
            final_narration = combine_paragraphs_with_silence(adjusted_paragraphs)
            
            # Export in background thread
            thread = threading.Thread(
                target=export_video_portuguese_async,
                args=(video_folder, final_narration, folder)
            )
            thread.start()
            
            return jsonify({
                'success': True,
                'message': 'Portuguese export iniciado!'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Invalid mode: {mode}. Use "review" or "apply"'
            }), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def export_video_portuguese_async(video_folder, portuguese_narration, folder_name):
    """Export video in Portuguese asynchronously."""
    try:
        generate_portuguese_video(video_folder, portuguese_narration)
    except Exception as e:
        log_error(f'Error exporting Portuguese video: {e}', step='export_portuguese')


@app.route('/api/videos/<path:folder>/regenerate-suggestions', methods=['POST'])
def regenerate_suggestions(folder):
    """Regenerate Ollama suggestions for a paragraph.
    
    Args:
        folder: Video folder name
        POST body:
            - paragraph_text: Paragraph text
            - duration_diff: Duration difference needed (positive = add, negative = remove)
            - language: Language code ('en', 'es')
            - paragraph_index: Index of the paragraph (0-based)
            - suggestion_type: 'add' or 'remove'
    """
    try:
        data = request.get_json() or {}
        paragraph_text = data.get('paragraph_text', '').strip()
        duration_diff = data.get('duration_diff', 0)
        language = data.get('language', 'en')
        paragraph_index = data.get('paragraph_index', 0)
        suggestion_type = data.get('suggestion_type', 'add')
        
        if not paragraph_text:
            return jsonify({
                'success': False,
                'error': 'Paragraph text is required'
            }), 400
        
        if language not in ['en', 'es']:
            return jsonify({
                'success': False,
                'error': 'Invalid language. Use "en" or "es"'
            }), 400
        
        if suggestion_type not in ['add', 'remove']:
            return jsonify({
                'success': False,
                'error': 'Invalid suggestion_type. Use "add" or "remove"'
            }), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        from video.paragraph_analysis import get_ollama_suggestions
        from logger import log
        
        log(f'Regenerating {suggestion_type} suggestions for paragraph {paragraph_index + 1} (language: {language})', step='regenerate_suggestions')
        
        # Get suggestions from Ollama
        suggestions = get_ollama_suggestions(paragraph_text, duration_diff, language)
        
        # Return only the requested type
        result = {
            'success': True,
            'suggestions': {
                'add': suggestions.get('add', []) if suggestion_type == 'add' else [],
                'remove': suggestions.get('remove', []) if suggestion_type == 'remove' else []
            }
        }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/videos/<path:folder>/recalculate-duration', methods=['POST'])
def recalculate_paragraph_duration(folder):
    """Recalculate duration for a single paragraph after editing.
    
    Args:
        folder: Video folder name
        POST body:
            - paragraph_text: Edited paragraph text
            - language: Language code ('en', 'es')
            - paragraph_index: Index of the paragraph (0-based)
            - target_duration: Optional target duration from initial analysis (avoids regenerating Portuguese audio)
    """
    try:
        data = request.get_json() or {}
        paragraph_text = data.get('paragraph_text', '').strip()
        language = data.get('language', 'en')
        paragraph_index = data.get('paragraph_index', 0)
        target_duration = data.get('target_duration')  # Use cached value if provided
        
        if not paragraph_text:
            return jsonify({
                'success': False,
                'error': 'Paragraph text is required'
            }), 400
        
        if language not in ['en', 'es']:
            return jsonify({
                'success': False,
                'error': 'Invalid language. Use "en" or "es"'
            }), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({'success': False, 'error': 'Video folder not found'}), 404
        
        from video.paragraph_analysis import get_portuguese_paragraphs, generate_temp_paragraph_audio
        from logger import log
        import tempfile
        
        log(f'Recalculating duration for paragraph {paragraph_index + 1} only (not all paragraphs)', step='recalculate_duration')
        
        # If target_duration is provided, use it (from initial analysis cache)
        # Otherwise, measure Portuguese paragraph (fallback - shouldn't happen in normal flow)
        if target_duration is not None:
            log(f'Using cached target duration: {target_duration:.2f}s (no Portuguese audio generation needed)', step='recalculate_duration')
        else:
            # Fallback: get Portuguese paragraph and measure it (shouldn't normally happen)
            pt_paragraphs = get_portuguese_paragraphs(video_folder)
            if paragraph_index >= len(pt_paragraphs):
                return jsonify({
                    'success': False,
                    'error': f'Paragraph index {paragraph_index} out of range'
                }), 400
            
            pt_paragraph = pt_paragraphs[paragraph_index]
            temp_dir_pt = tempfile.mkdtemp()
            try:
                log(f'Measuring Portuguese paragraph {paragraph_index + 1} duration (fallback - should use cached value)', step='recalculate_duration')
                target_duration = generate_temp_paragraph_audio(pt_paragraph, 'pt', temp_dir_pt, paragraph_index=paragraph_index)
            finally:
                try:
                    import shutil
                    shutil.rmtree(temp_dir_pt)
                except:
                    pass
        
        # Create temp directory for measuring edited paragraph only
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Measure ONLY the edited paragraph duration (this is necessary)
            log(f'Measuring edited {language} paragraph {paragraph_index + 1} duration', step='recalculate_duration')
            current_duration = generate_temp_paragraph_audio(paragraph_text, language, temp_dir, paragraph_index=paragraph_index)
            duration_diff = target_duration - current_duration
            
            log(f'Recalculation complete for paragraph {paragraph_index + 1}: current={current_duration:.2f}s, target={target_duration:.2f}s, diff={duration_diff:.2f}s', step='recalculate_duration')
            
            return jsonify({
                'success': True,
                'duration': round(current_duration, 2),
                'target_duration': round(target_duration, 2),
                'difference': round(duration_diff, 2)
            })
        finally:
            # Clean up temp directory
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass
    except Exception as e:
        log_error(f'Error recalculating paragraph duration: {e}', step='recalculate_duration')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/videos/<path:folder>/shorts', methods=['POST'])
def generate_shorts(folder):
    """Generate shorts from final videos in a folder.
    
    Splits videos at silence markers and creates vertical 9:16 format shorts.
    Generates shorts for all available language versions (pt, en, es).
    """
    try:
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({
                'success': False,
                'error': 'Video folder not found'
            }), 404
        
        # Generate shorts for all languages
        result = generate_all_shorts(video_folder)
        
        # Format response with relative paths for frontend
        shorts_info = {}
        for language in ['pt', 'en', 'es']:
            shorts_list = []
            for short_path in result[language]:
                # Get relative path from video folder
                short_filename = os.path.basename(short_path)
                shorts_list.append({
                    'filename': short_filename,
                    'path': f'/api/videos/{folder}/shorts/{language}/{short_filename}'
                })
            shorts_info[language] = shorts_list
        
        total_count = sum(len(shorts) for shorts in shorts_info.values())
        
        return jsonify({
            'success': True,
            'message': f'Generated {total_count} shorts successfully',
            'shorts': shorts_info,
            'counts': {
                'pt': len(shorts_info['pt']),
                'en': len(shorts_info['en']),
                'es': len(shorts_info['es']),
                'total': total_count
            }
        })
        
    except Exception as e:
        log_error(f'Error generating shorts: {e}', step='shorts')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/videos/<path:folder>/shorts/<language>', methods=['POST'])
def generate_shorts_for_language(folder, language):
    """Generate shorts from final video for a specific language.
    
    Splits video at silence markers and creates vertical 9:16 format shorts.
    """
    try:
        if language not in ['pt', 'en', 'es']:
            return jsonify({
                'success': False,
                'error': f'Invalid language: {language}. Must be pt, en, or es.'
            }), 400
        
        video_folder = get_video_folder_path(folder)
        if not os.path.exists(video_folder):
            return jsonify({
                'success': False,
                'error': 'Video folder not found'
            }), 404
        
        # Get splits for this language to determine animated videos needed
        splits = calculate_split_timestamps(video_folder, language)
        if not splits:
            return jsonify({
                'success': False,
                'error': f'No splits calculated for {language} video'
            }), 400
        
        # Check if animated videos exist, create if needed
        visuals_shorts_dir = os.path.join(video_folder, 'visuals', 'shorts')
        animated_videos = []
        
        if os.path.exists(visuals_shorts_dir):
            # Check for existing animated videos
            for idx in range(1, len(splits) + 1):
                animated_path = os.path.join(visuals_shorts_dir, f'animated_{idx:02d}.{VIDEO_EXTENSION}')
                if os.path.exists(animated_path):
                    animated_videos.append(animated_path)
        
        # Create animated videos if they don't exist or are incomplete
        if len(animated_videos) != len(splits):
            animated_videos = create_animated_videos_from_images(video_folder, splits)
            if not animated_videos or len(animated_videos) != len(splits):
                return jsonify({
                    'success': False,
                    'error': f'Failed to create animated videos ({len(animated_videos)}/{len(splits)} created)'
                }), 500
        
        # Generate shorts for single language using animated videos
        shorts_paths = generate_shorts_for_lang(video_folder, language, animated_videos)
        
        # Format response with relative paths for frontend
        shorts_list = []
        for short_path in shorts_paths:
            short_filename = os.path.basename(short_path)
            shorts_list.append({
                'filename': short_filename,
                'path': f'/api/videos/{folder}/shorts/{language}/{short_filename}'
            })
        
        language_names = {'pt': 'Português', 'en': 'English', 'es': 'Español'}
        language_emoji = {'pt': '🇧🇷', 'en': '🇬🇧', 'es': '🇪🇸'}
        
        return jsonify({
            'success': True,
            'message': f'Generated {len(shorts_list)} {language_names[language]} shorts successfully',
            'shorts': shorts_list,
            'language': language,
            'count': len(shorts_list)
        })
        
    except Exception as e:
        log_error(f'Error generating shorts for {language}: {e}', step='shorts')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
