"""Audio generation module - Public API for backward compatibility."""
import os

from logger import log, log_error
from constants import AUDIO_EXTENSION
from .piper import _load_piper_voice, _generate_speech_with_piper, _load_piper_voice_english, _load_piper_voice_spanish
from .utils import combine_audio_segments_with_silence, DEFAULT_SILENCE_DURATION
from .files import (
    create_silent_audio,
    save_narration_to_file,
    get_audio_duration,
    apply_fade_in_out
)

def split_narration_by_phrases(narration_script):
    """
    Split narration by dots and track silence/nosilence positions.
    Returns: (phrases, silence_positions, nosilence_positions)
    - phrases: list of phrase texts
    - silence_positions: list of indices where longer silence should be inserted after phrase
    - nosilence_positions: list of indices where trailing silence should be removed from audio segment
    """
    phrases = []
    silence_positions = []
    nosilence_positions = []
    
    # Split by (silence) markers
    parts = narration_script.split('(silence)')
    
    for part_idx, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        
        # Check for nosilence markers in this part
        nosilence_parts = part.split('(nosilence)')
        
        for nosilence_idx, nosilence_part in enumerate(nosilence_parts):
            nosilence_part = nosilence_part.strip()
            if not nosilence_part:
                continue
            
            # Split by dots, preserving the dots with the phrases
            split_parts = nosilence_part.split('.')
            for i, p in enumerate(split_parts):
                p = p.strip()
                if p:
                    # Add dot back if this isn't the last part, or if original ended with dot
                    if i < len(split_parts) - 1 or nosilence_part.rstrip().endswith('.'):
                        p = p + '.'
                    phrases.append(p)
            
            # If this is not the last nosilence part in this section, mark nosilence position
            if nosilence_idx < len(nosilence_parts) - 1 and phrases:
                nosilence_positions.append(len(phrases) - 1)
        
        # If this is not the last part (after (silence)), mark silence position after the last phrase
        if part_idx < len(parts) - 1 and phrases:
            last_phrase_idx = len(phrases) - 1
            # Only add to silence_positions if not already in nosilence_positions
            if last_phrase_idx not in nosilence_positions:
                silence_positions.append(last_phrase_idx)
    
    return phrases, silence_positions, nosilence_positions


def generate_audio(narration_script, output_folder, language='pt'):
    """Generate audio from narration script.
    
    Args:
        narration_script: Narration text
        output_folder: Output folder path
        language: Language code ('pt' for Portuguese, 'en' for English, 'es' for Spanish)
    """
    try:
        # Split by phrases and track silence/nosilence positions
        phrases, silence_positions, nosilence_positions = split_narration_by_phrases(narration_script)
        
        if not phrases:
            raise Exception('No phrases found in narration script')
        
        log(f'Split narration into {len(phrases)} phrases', step='generate_audio')
        if silence_positions:
            log(f'Found {len(silence_positions)} silence markers', step='generate_audio')
        if nosilence_positions:
            log(f'Found {len(nosilence_positions)} nosilence markers', step='generate_audio')
        
        output_dir = output_folder
        # Create language folder: narration/pt/, narration/en/, or narration/es/
        lang_folder = os.path.join(output_dir, 'narration', language)
        os.makedirs(lang_folder, exist_ok=True)
        
        # Audio segments go to {language}/audio_segments/
        audio_segments_dir = os.path.join(lang_folder, 'audio_segments')
        os.makedirs(audio_segments_dir, exist_ok=True)
        
        audio_segment_paths = []
        
        # Load appropriate voice model based on language
        print(f'📦 Loading Piper TTS model ({language}) for {len(phrases)} phrases...', flush=True)
        if language == 'en':
            voice = _load_piper_voice_english()
        elif language == 'es':
            voice = _load_piper_voice_spanish()
        else:
            voice = _load_piper_voice()
        
        # Generate audio for each phrase
        # Use enhanced variation for video generation (use_enhanced_variation=True)
        for i, phrase in enumerate(phrases):
            output_path = os.path.join(audio_segments_dir, f'narration_{i}.{AUDIO_EXTENSION}')
            _generate_speech_with_piper(voice, phrase, output_path, language)
            if os.path.exists(output_path):
                audio_segment_paths.append(output_path)
        
        if not audio_segment_paths:
            raise Exception('Failed to generate any audio segments')
        
        # Combined audio goes to narration/{language}/narration_0.wav
        final_output_path = os.path.join(lang_folder, f'narration_0.{AUDIO_EXTENSION}')
        
        # Combine with silence positions
        combine_audio_segments_with_silence(
            audio_segment_paths, 
            final_output_path, 
            silence_duration=DEFAULT_SILENCE_DURATION,
            silence_positions=silence_positions,
            nosilence_positions=nosilence_positions,
            language=language
        )
        
        return [final_output_path]
    except Exception as e:
        log_error(f'Audio generation error: {e}', step='generate_audio')
        raise
