import os
import re
import threading

from flask import Blueprint, jsonify, send_file, request
from datetime import datetime

from constants import OUTPUT_DIR_AUDIOS, SPEAKER_VOICE_PATH, AUDIO_EXTENSION
from app.utils import list_files, delete_files_by_pattern
from audio.piper import generate_tts_batch
from logger import log_error

AUDIO_LANGUAGE = 'pt'

app = Blueprint('audio', __name__)

@app.route('/api/generate-audio', methods=['POST'])
def generate_audio():
    try:
        data = request.get_json()
        audio_text = data.get('audio_text', '')
        language = data.get('language', 'pt')  # Default to Portuguese

        if not audio_text:
            return jsonify({'success': False, 'error': 'Texto é obrigatório'}), 400

        # Validate language
        if language not in ['pt', 'en']:
            language = 'pt'  # Default to Portuguese if invalid

        segments = split_audio_text(audio_text)

        if not segments:
            return jsonify({'success': False, 'error': 'Nenhum texto válido encontrado'}), 400

        thread = threading.Thread(target=run_audio_generation, args=(segments, language))
        thread.start()

        lang_name = 'Português' if language == 'pt' else 'English'
        return jsonify({
            'success': True,
            'message': f'✅ Geração de {len(segments)} áudio(s) em {lang_name} iniciada!',
            'count': len(segments)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audios', methods=['GET'])
def list_audios():
    try:
        audios = list_files(OUTPUT_DIR_AUDIOS, f'*.{AUDIO_EXTENSION}', 'audios')
        return jsonify({'success': True, 'audios': audios})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audios/<filename>')
def get_audio(filename):
    try:
        audio_path = os.path.join(OUTPUT_DIR_AUDIOS, filename)
        if os.path.exists(audio_path):
            mimetype = f'audio/{AUDIO_EXTENSION}'
            return send_file(audio_path, mimetype=mimetype)
        else:
            return jsonify({'error': 'Áudio não encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/audios/<filename>', methods=['DELETE'])
def delete_audio(filename):
    try:
        audio_path = os.path.join(OUTPUT_DIR_AUDIOS, filename)
        if os.path.exists(audio_path):
            os.remove(audio_path)
            return jsonify({'success': True, 'message': 'Áudio deletado'})
        return jsonify({'success': False, 'error': 'Áudio não encontrado'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audios/all', methods=['DELETE'])
def delete_all_audios():
    try:
        deleted_count = delete_files_by_pattern(OUTPUT_DIR_AUDIOS, f'*.{AUDIO_EXTENSION}')
        return jsonify({
            'success': True,
            'message': f'{deleted_count} áudio(s) deletado(s)',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audios/<filename>/regenerate', methods=['POST'])
def regenerate_audio(filename):
    try:
        data = request.get_json()
        text = data.get('text', '')
        language = data.get('language', 'pt')  # Default to Portuguese

        if not text:
            return jsonify({'success': False, 'error': 'Texto é obrigatório para regenerar'}), 400

        # Validate language
        if language not in ['pt', 'en']:
            language = 'pt'  # Default to Portuguese if invalid

        thread = threading.Thread(target=run_audio_regeneration, args=(filename, text, language))
        thread.start()

        return jsonify({
            'success': True,
            'message': '✅ Regeneração iniciada!'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def run_audio_generation(segments, language='pt'):
    """Generate audio segments.
    
    Args:
        segments: List of text segments to convert to audio
        language: Language code ('pt' for Portuguese, 'en' for English). Defaults to 'pt'.
    """
    try:
        os.makedirs(OUTPUT_DIR_AUDIOS, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_paths = []

        for index, text in enumerate(segments):
            filename = generate_audio_filename(timestamp, index)
            output_path = os.path.join(OUTPUT_DIR_AUDIOS, filename)
            output_paths.append(output_path)

        # Use default settings (use_enhanced_variation=False) for standalone audio generation
        generate_tts_batch(
            texts=segments,
            output_paths=output_paths,
            language=language,
        )
    except Exception as e:
        log_error(f'Error generating audio: {e}', step='generate_audio')


def run_audio_regeneration(filename, text, language='pt'):
    """Regenerate a single audio file.
    
    Args:
        filename: Name of the audio file to regenerate
        text: Text to convert to audio
        language: Language code ('pt' for Portuguese, 'en' for English). Defaults to 'pt'.
    """
    try:
        audio_path = os.path.join(OUTPUT_DIR_AUDIOS, filename)
        if not os.path.exists(audio_path):
            return

        # Use default settings (use_enhanced_variation=False) for standalone audio generation
        generate_tts_batch(
            texts=[text],
            output_paths=[audio_path],
            language=language,
        )
    except Exception as e:
        log_error(f'Error regenerating audio: {e}', step='regenerate_audio')

def split_audio_text(text):
    segments = re.split(r'\n\s*\n+', text.strip())
    return [seg.strip() for seg in segments if seg.strip()]

def generate_audio_filename(timestamp, index):
    return f'audio_{timestamp}_{index+1:03d}.{AUDIO_EXTENSION}'
