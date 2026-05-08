import os
import numpy as np
import soundfile as sf

DEFAULT_SAMPLE_RATE = 44100
DEFAULT_SILENCE_DURATION = 1

# Language-specific gap durations (small pauses between phrases) in seconds
LANGUAGE_GAP_DURATIONS = {
    'pt': 0.3,
    'en': 0.3,
    'es': 0.3,
}

# Default gap duration if language not specified
DEFAULT_GAP_DURATION = 0.3

def _convert_to_mono(audio):
    if len(audio.shape) > 1:
        return np.mean(audio, axis=1)
    return audio


def load_and_prepare_audio(audio_path):
    audio, sample_rate = sf.read(audio_path)
    audio = _convert_to_mono(audio)
    return audio, sample_rate

def _create_silence(sample_rate, duration):
    silence_samples = int(sample_rate * duration)
    return np.zeros(silence_samples)


def _trim_trailing_silence(audio, sample_rate, threshold=0.01, min_silence_duration=0.05):
    """
    Remove trailing silence from audio segment.
    
    Args:
        audio: Audio array
        sample_rate: Sample rate
        threshold: Amplitude threshold below which is considered silence (default: 0.01)
        min_silence_duration: Minimum duration of silence to trim (seconds, default: 0.05)
    
    Returns:
        Trimmed audio array
    """
    if len(audio) == 0:
        return audio
    
    # Calculate absolute amplitude
    abs_audio = np.abs(audio)
    
    # Find the last sample that exceeds the threshold
    # Work backwards from the end
    min_silence_samples = int(sample_rate * min_silence_duration)
    silence_count = 0
    last_non_silence_idx = len(audio)
    
    for i in range(len(audio) - 1, -1, -1):
        if abs_audio[i] > threshold:
            # Found non-silence, check if we had enough silence before
            if silence_count >= min_silence_samples:
                # Trim from the last non-silence position
                last_non_silence_idx = i + 1
            break
        else:
            silence_count += 1
    
    # Trim the audio
    return audio[:last_non_silence_idx]


def _load_audio_segment(audio_path, final_sample_rate):
    if not os.path.exists(audio_path):
        return None, None
    
    audio, sample_rate = load_and_prepare_audio(audio_path)
    
    if final_sample_rate is None:
        return audio, sample_rate
    
    if sample_rate != final_sample_rate:
        return audio, sample_rate
    
    return audio, sample_rate


def combine_audio_segments_with_silence(audio_segments, output_path, silence_duration, sample_rate=DEFAULT_SAMPLE_RATE, silence_positions=None, nosilence_positions=None, language='pt'):
    """
    Combine audio segments with silence inserted between all segments.
    Removes natural pause from segments marked with (nosilence).
    Adds small language-specific pauses between all phrases.
    
    Args:
        audio_segments: List of audio file paths
        output_path: Output file path
        silence_duration: Duration of silence in seconds (inserted at silence_positions)
        sample_rate: Target sample rate
        silence_positions: List of indices where longer silence should be inserted
        nosilence_positions: List of indices where trailing silence should be removed from audio segment
        language: Language code ('pt', 'en', 'es') to determine gap duration between phrases
    """
    if not audio_segments:
        raise ValueError('No audio segments provided')
    
    combined_audio = []
    final_sample_rate = None
    
    # Get language-specific gap duration
    gap_duration = LANGUAGE_GAP_DURATIONS.get(language, DEFAULT_GAP_DURATION)
    
    # Convert to sets for faster lookup
    silence_indices = set(silence_positions) if silence_positions else set()
    nosilence_indices = set(nosilence_positions) if nosilence_positions else set()
    
    for index, audio_path in enumerate(audio_segments):
        audio, sr = _load_audio_segment(audio_path, final_sample_rate)
        
        if audio is None:
            continue
        
        if final_sample_rate is None:
            final_sample_rate = sr
        
        # Remove trailing silence if marked with (nosilence)
        if index in nosilence_indices:
            audio = _trim_trailing_silence(audio, final_sample_rate)
        
        combined_audio.append(audio)
        
        # Add small pause between phrases (except for last segment and nosilence positions)
        if index < len(audio_segments) - 1 and index not in nosilence_indices:
            gap = _create_silence(final_sample_rate, gap_duration)
            combined_audio.append(gap)
        
        # Insert longer silence at specified positions (after the gap if both exist)
        if index in silence_indices:
            silence = _create_silence(final_sample_rate, silence_duration)
            combined_audio.append(silence)

    if not combined_audio:
        raise ValueError('No valid audio segments to combine')
    
    final_audio = np.concatenate(combined_audio)
    sf.write(output_path, final_audio, final_sample_rate)
    
    # Apply audio enhancement after combining
    from audio.files import apply_audio_enhancement
    apply_audio_enhancement(output_path, save_original=None)  # None = use env variable
    
    return final_audio, final_sample_rate
