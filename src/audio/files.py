"""Audio file operations."""

import os
import numpy as np
import soundfile as sf

from constants import AUDIO_EXTENSION, PARENT_DIR
from audio.utils import DEFAULT_SAMPLE_RATE
from .improve import enhance_audio_quality


def create_silent_audio(output_path, duration=3.0):
    """Create silent audio file of specified duration."""
    silence = np.zeros(int(DEFAULT_SAMPLE_RATE * duration))
    sf.write(output_path, silence, DEFAULT_SAMPLE_RATE)


def save_narration_to_file(video_folder, narration_script, language='pt'):
    """Save narration script to language folder."""
    lang_folder = os.path.join(video_folder, 'narration', language)
    os.makedirs(lang_folder, exist_ok=True)
    narration_file = os.path.join(lang_folder, 'narration.txt')
    with open(narration_file, 'w', encoding='utf-8') as f:
        f.write(narration_script)
    return narration_file


def get_audio_duration(audio_path=None, video_folder=None, language='pt'):
    """Get audio duration in seconds - single unified function for all duration needs.
    
    Args:
        audio_path: Direct path to audio file (e.g., 'path/to/narration_0.wav')
        video_folder: Path to video folder (will look for narration/{language}/narration_0.wav)
        language: Language code when using video_folder ('pt' or 'en', default: 'pt')
    
    Returns:
        Duration in seconds
        
    Raises:
        FileNotFoundError: If audio file does not exist
        ValueError: If audio file exists but duration cannot be read or is invalid
        ValueError: If neither audio_path nor video_folder is provided
        
    Examples:
        # Direct audio file
        duration = get_audio_duration(audio_path='path/to/audio.wav')
        
        # Video folder with language
        duration = get_audio_duration(video_folder='path/to/video', language='pt')
    """
    # Determine the actual audio file path
    if audio_path:
        final_audio_path = audio_path
    elif video_folder:
        lang_folder = os.path.join(video_folder, 'narration', language)
        final_audio_path = os.path.join(lang_folder, f'narration_0.{AUDIO_EXTENSION}')
    else:
        raise ValueError('Either audio_path or video_folder must be provided')
    
    # Check if file exists
    if not os.path.exists(final_audio_path):
        raise FileNotFoundError(f'Audio file not found: {final_audio_path}')
    
    # Read duration from file
    try:
        info = sf.info(final_audio_path)
        duration = float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
        if duration <= 0:
            raise ValueError(f'Invalid audio duration: {duration} seconds (file: {final_audio_path})')
        return duration
    except Exception as e:
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        raise ValueError(f'Failed to read audio duration from {final_audio_path}: {e}')


def apply_fade_in_out(audio_path, fade_duration=0.1):
    """Apply small fade in at start and fade out at end to smooth phrase transitions."""
    data, sample_rate = sf.read(audio_path)
    fade_samples = int(sample_rate * fade_duration)
    
    # Handle both mono and stereo
    if data.ndim == 1:
        # Mono
        data[:fade_samples] *= np.linspace(0, 1, fade_samples)
        data[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    else:
        # Stereo
        fade_in = np.linspace(0, 1, fade_samples).reshape(-1, 1)
        fade_out = np.linspace(1, 0, fade_samples).reshape(-1, 1)
        data[:fade_samples] *= fade_in
        data[-fade_samples:] *= fade_out
    
    sf.write(audio_path, data, sample_rate)


def apply_audio_enhancement(audio_path, save_original=True):
    """
    Apply audio enhancement to an audio file.
    
    Args:
        audio_path: Path to audio file to enhance
        save_original: If True, save original file as .original.wav before enhancement.
                      If None, uses SAVE_ORIGINAL_AUDIO environment variable.
    
    Returns:
        Path to enhanced audio file (same as input path)
    """
    from env import SAVE_ORIGINAL_AUDIO
    
    # Use parameter if provided, otherwise use env variable
    should_save_original = save_original if save_original is not None else SAVE_ORIGINAL_AUDIO
    
    # Load audio
    audio, sample_rate = sf.read(audio_path)
    
    # Convert to mono if stereo
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)
    
    # Save original if requested
    if should_save_original:
        original_path = audio_path.replace(f'.{AUDIO_EXTENSION}', f'.original.{AUDIO_EXTENSION}')
        sf.write(original_path, audio, sample_rate)
    
    # Apply enhancement
    enhanced_audio = enhance_audio_quality(audio, sample_rate)
    
    # Save enhanced audio (overwrite original file)
    sf.write(audio_path, enhanced_audio, sample_rate)
    
    return audio_path

