from flask import Blueprint, jsonify, request
from googletrans import Translator
from logger import log_error
import re

app = Blueprint('translate', __name__)

# Initialize translator
translator = Translator()

MAX_CHUNK_SIZE = 5000

def split_text_by_sentences(text, max_size):
    """Split text into chunks smaller than max_size, respecting sentence boundaries (.)"""
    if len(text) <= max_size:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by sentences (period followed by space or end of line)
    sentences = re.split(r'(\.\s+)', text)
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        if i + 1 < len(sentences):
            sentence += sentences[i + 1]  # Include the period and space
        
        # If adding this sentence would exceed max_size, save current chunk and start new one
        if current_chunk and len(current_chunk) + len(sentence) > max_size:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += sentence
    
    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

@app.route('/api/translate', methods=['POST'])
def translate():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados inválidos no request'}), 400
            
        text = data.get('text', '').strip()
        target_language = data.get('target_language', 'en')

        if not text:
            return jsonify({'success': False, 'error': 'Texto é obrigatório'}), 400

        # Validate target language
        if target_language not in ['en', 'es']:
            return jsonify({'success': False, 'error': 'Idioma destino inválido. Use "en" para inglês ou "es" para espanhol'}), 400

        # Source language is Portuguese (pt)
        source_lang_code = 'pt'
        target_lang_code = target_language
        
        # Split text into chunks if needed
        chunks = split_text_by_sentences(text, MAX_CHUNK_SIZE)
        
        # Translate each chunk
        translated_chunks = []
        for chunk in chunks:
            try:
                result = translator.translate(chunk, src=source_lang_code, dest=target_lang_code)
                if result and hasattr(result, 'text') and result.text:
                    translated_chunks.append(result.text)
                else:
                    raise ValueError('Resultado da tradução inválido')
            except Exception as e:
                error_msg = str(e)
                log_error(f'Error translating chunk: {error_msg}', step='translate')
                raise Exception(f'Erro ao traduzir: {error_msg}')
        
        # Join translated chunks
        translated_text = ' '.join(translated_chunks)
        
        # Language names for response
        lang_names = {
            'en': 'Inglês',
            'es': 'Espanhol'
        }
        
        return jsonify({
            'success': True,
            'translated_text': translated_text,
            'source_language': 'pt',
            'target_language': target_language,
            'target_language_name': lang_names.get(target_language, target_language)
        })

    except Exception as e:
        error_msg = str(e)
        log_error(f'Error translating text: {error_msg}', step='translate')
        
        user_error = f'Erro ao traduzir: {error_msg}'
        
        return jsonify({'success': False, 'error': user_error}), 500
