"""Export video with language narration - reusing existing video and images."""

import os
import shutil
from logger import log, log_success, log_error
from audio.files import get_audio_duration
from audio.generate import generate_audio
from video.merge import merge_video_audio
from constants import VIDEO_EXTENSION, AUDIO_EXTENSION


# Language configuration mapping
LANGUAGE_CONFIG = {
    'en': {
        'name': 'English',
        'step': 'export_english',
        'final_filename': 'final_en.mp4'
    },
    'es': {
        'name': 'Spanish',
        'step': 'export_spanish',
        'final_filename': 'final_es.mp4'
    }
}


def save_narration_to_file(video_folder, narration, language):
    """Save narration to narration/{language}/narration.txt."""
    lang_folder = os.path.join(video_folder, 'narration', language)
    os.makedirs(lang_folder, exist_ok=True)
    narration_file = os.path.join(lang_folder, 'narration.txt')
    with open(narration_file, 'w', encoding='utf-8') as f:
        f.write(narration)
    return narration_file


def generate_language_video(video_folder, narration, language):
    """Generate language version of video reusing images and video.
    
    This function reuses the animated.mp4 video and all images,
    only regenerating the audio in the specified language and saving to audio_segments/{language}/.
    
    Args:
        video_folder: Path to video folder
        narration: Narration text in the target language
        language: Language code ('en' for English, 'es' for Spanish)
        
    Returns:
        dict: Result with success status and video path
    """
    if language not in LANGUAGE_CONFIG:
        raise ValueError(f'Unsupported language: {language}. Supported: {list(LANGUAGE_CONFIG.keys())}')
    
    config = LANGUAGE_CONFIG[language]
    lang_name = config['name']
    step_name = config['step']
    final_filename = config['final_filename']
    
    try:
        log(f'Generating {lang_name} version...', step=step_name, stage='audio', progress_percent=10)
        
        # Check if animated video exists
        animated_video = os.path.join(video_folder, 'visuals', 'animated.mp4')
        if not os.path.exists(animated_video):
            raise Exception('animated.mp4 not found in visuals folder')
        
        # Save narration to narration/{language}/narration.txt
        narration_file = save_narration_to_file(video_folder, narration, language)
        log(f'{lang_name} narration saved', step=step_name, stage='audio', progress_percent=20)
        
        # Get duration from Portuguese audio in narration/pt/narration_0.wav
        pt_folder = os.path.join(video_folder, 'narration', 'pt')
        pt_audio_path = os.path.join(pt_folder, f'narration_0.{AUDIO_EXTENSION}')
        if not os.path.exists(pt_audio_path):
            raise Exception(f'Portuguese audio not found: {pt_audio_path}')
        
        duration = get_audio_duration(video_folder=video_folder, language='pt')
        
        # Generate audio (saves to narration/{language}/narration_0.wav and narration/{language}/audio_segments/)
        log(f'Generating {lang_name} audio...', step=step_name, stage='audio', progress_percent=30)
        generate_audio(narration, video_folder, language=language)
        
        # Audio is saved in narration/{language}/narration_0.wav
        lang_folder = os.path.join(video_folder, 'narration', language)
        lang_audio_path = os.path.join(lang_folder, f'narration_0.{AUDIO_EXTENSION}')
        if not os.path.exists(lang_audio_path):
            raise Exception(f'{lang_name} audio file not generated')
        
        log(f'Merging video with {lang_name} audio...', step=step_name, stage='merging', progress_percent=70)
        
        # Merge video with audio (uses narration/{language}/narration_0.wav), with automatic subscription overlay if enabled and detected
        merge_video_audio(video_folder, language=language)
        
        # Rename merged video to language version
        video_with_audio = os.path.join(video_folder, f'video_with_audio.{VIDEO_EXTENSION}')
        final_path = os.path.join(video_folder, final_filename)
        
        if not os.path.exists(video_with_audio):
            raise Exception('Merged video file not found')
        
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(video_with_audio, final_path)
        log_success(f'{lang_name} video generated successfully', step=step_name)
        
        return {
            'success': True,
            'message': f'{lang_name} video generated successfully',
            'video_path': final_path,
            'narration': narration
        }
    except Exception as e:
        log_error(f'{lang_name} export error: {e}', step=step_name)
        raise


def save_english_narration_to_file(video_folder, english_narration):
    """Save English narration to narration/en/narration.txt."""
    return save_narration_to_file(video_folder, english_narration, 'en')


def save_spanish_narration_to_file(video_folder, spanish_narration):
    """Save Spanish narration to narration/es/narration.txt."""
    return save_narration_to_file(video_folder, spanish_narration, 'es')


def generate_english_video(video_folder, english_narration):
    """Generate English version of video reusing images and video.
    
    This function reuses the animated.mp4 video and all images,
    only regenerating the audio in English and saving to audio_segments/en/.
    
    Args:
        video_folder: Path to video folder
        english_narration: English narration text
        
    Returns:
        dict: Result with success status and video path
    """
    result = generate_language_video(video_folder, english_narration, 'en')
    # Maintain backward compatibility with original return structure
    if 'narration' in result:
        result['english_narration'] = result.pop('narration')
    return result


def generate_spanish_video(video_folder, spanish_narration):
    """Generate Spanish version of video reusing images and video.
    
    This function reuses the animated.mp4 video and all images,
    only regenerating the audio in Spanish and saving to audio_segments/es/.
    
    Args:
        video_folder: Path to video folder
        spanish_narration: Spanish narration text
        
    Returns:
        dict: Result with success status and video path
    """
    result = generate_language_video(video_folder, spanish_narration, 'es')
    # Maintain backward compatibility with original return structure
    if 'narration' in result:
        result['spanish_narration'] = result.pop('narration')
    return result


def generate_portuguese_video(video_folder, portuguese_narration):
    """Generate Portuguese version of video reusing images and video.
    
    This function reuses the animated.mp4 video and all images,
    only regenerating the audio in Portuguese and saving to audio_segments/pt/.
    Uses EN or ES audio for duration if Portuguese audio doesn't exist.
    
    Args:
        video_folder: Path to video folder
        portuguese_narration: Portuguese narration text
        
    Returns:
        dict: Result with success status and video path
    """
    try:
        log('Generating Portuguese version...', step='export_portuguese', stage='audio', progress_percent=10)
        
        # Check if animated video exists
        animated_video = os.path.join(video_folder, 'visuals', 'animated.mp4')
        if not os.path.exists(animated_video):
            raise Exception('animated.mp4 not found in visuals folder')
        
        # Save narration to narration/pt/narration.txt
        narration_file = save_narration_to_file(video_folder, portuguese_narration, 'pt')
        log('Portuguese narration saved', step='export_portuguese', stage='audio', progress_percent=20)
        
        # Get duration from EN or ES audio (since PT doesn't exist yet)
        duration = None
        for lang in ['en', 'es']:
            lang_folder = os.path.join(video_folder, 'narration', lang)
            lang_audio_path = os.path.join(lang_folder, f'narration_0.{AUDIO_EXTENSION}')
            if os.path.exists(lang_audio_path):
                duration = get_audio_duration(video_folder=video_folder, language=lang)
                log(f'Using {lang} audio duration: {duration:.2f}s', step='export_portuguese')
                break
        
        if duration is None:
            raise Exception('No audio found (EN, ES) to determine duration. Cannot generate Portuguese version.')
        
        # Generate audio (saves to narration/pt/narration_0.wav and narration/pt/audio_segments/)
        log('Generating Portuguese audio...', step='export_portuguese', stage='audio', progress_percent=30)
        generate_audio(portuguese_narration, video_folder, language='pt')
        
        # Audio is saved in narration/pt/narration_0.wav
        pt_folder = os.path.join(video_folder, 'narration', 'pt')
        pt_audio_path = os.path.join(pt_folder, f'narration_0.{AUDIO_EXTENSION}')
        if not os.path.exists(pt_audio_path):
            raise Exception('Portuguese audio file not generated')
        
        log('Merging video with Portuguese audio...', step='export_portuguese', stage='merging', progress_percent=70)
        
        # Merge video with audio (uses narration/pt/narration_0.wav), with automatic subscription overlay if enabled and detected
        merge_video_audio(video_folder, language='pt')
        
        # Rename merged video to Portuguese version
        video_with_audio = os.path.join(video_folder, f'video_with_audio.{VIDEO_EXTENSION}')
        final_path = os.path.join(video_folder, 'final_pt.mp4')
        
        if not os.path.exists(video_with_audio):
            raise Exception('Merged video file not found')
        
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(video_with_audio, final_path)
        log_success('Portuguese video generated successfully', step='export_portuguese')
        
        return {
            'success': True,
            'message': 'Portuguese video generated successfully',
            'video_path': final_path,
            'portuguese_narration': portuguese_narration
        }
    except Exception as e:
        log_error(f'Portuguese export error: {e}', step='export_portuguese')
        raise







