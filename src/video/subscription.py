"""Subscription detection and overlay module - completely isolated implementation."""

import os
import re
import subprocess
from logger import log, log_error
from constants import PARENT_DIR, VIDEO_EXTENSION, AUDIO_EXTENSION
from audio.files import get_audio_duration
from audio.generate import split_narration_by_phrases
from audio.utils import LANGUAGE_GAP_DURATIONS, DEFAULT_GAP_DURATION, DEFAULT_SILENCE_DURATION


# Subscription keywords for each language
SUBSCRIPTION_KEYWORDS = {
    'pt': [
        r'\binscreva[\s-]?se\b',
        r'\binscreve[\s-]?se\b',
        r'\bse\s+inscrev[ae]',
        r'\binscri[çc][ãa]o\b',
        r'\bcanal\b.*\binscri[çc][ãa]o\b',
        r'\bgostou.*\binscreva',
    ],
    'en': [
        r'\bsubscribe\b',
        r'\bsubscription\b',
        r'\bsub\s+to\b',
        r'\blike\s+.*\bsubscribe',
        r'\bsubscribe\s+to\s+.*\bchannel\b',
        r'\bhit\s+the\s+bell\b',
    ],
    'es': [
        r'\bsuscr[ií]bete\b',
        r'\bsuscr[ií]birse\b',
        r'\bsuscripci[óo]n\b',
        r'\bcanal\b.*\bsuscr[ií]be',
        r'\bte\s+suscr[ií]bes\b',
        r'\bme\s+gusta.*\bsuscr[ií]be',
    ]
}


def detect_subscription_in_narration(narration_text, language='pt'):
    """Detect if narration contains subscription request and return phrase index."""
    try:
        phrases, _, _ = split_narration_by_phrases(narration_text)
        keywords = SUBSCRIPTION_KEYWORDS.get(language, SUBSCRIPTION_KEYWORDS['pt'])
        
        for i, phrase in enumerate(phrases):
            phrase_lower = phrase.lower()
            for keyword_pattern in keywords:
                if re.search(keyword_pattern, phrase_lower, re.IGNORECASE):
                    log(f'Subscription detected in phrase {i}: {phrase[:50]}...', step='subscription_detect')
                    return i
        
        return None
    except Exception as e:
        log_error(f'Error detecting subscription: {e}', step='subscription_detect')
        return None


def _get_silence_positions(output_folder, language):
    """Get silence and nosilence position sets from narration file."""
    lang_folder = os.path.join(output_folder, 'narration', language)
    narration_file = os.path.join(lang_folder, 'narration.txt')
    
    if not os.path.exists(narration_file):
        return set(), set()
    
    try:
        with open(narration_file, 'r', encoding='utf-8') as f:
            narration_text = f.read()
            _, silence_positions, nosilence_positions = split_narration_by_phrases(narration_text)
        
        silence_set = set(silence_positions) if silence_positions else set()
        nosilence_set = set(nosilence_positions) if nosilence_positions else set()
        return silence_set, nosilence_set
    except Exception:
        return set(), set()


def _calculate_time_up_to_phrase(output_folder, phrase_index, language, silence_set, nosilence_set):
    """Calculate audio time up to the start of a specific phrase index."""
    lang_folder = os.path.join(output_folder, 'narration', language)
    audio_segments_dir = os.path.join(lang_folder, 'audio_segments')
    
    if not os.path.exists(audio_segments_dir):
        return None
    
    total_time = 0.0
    gap_duration = LANGUAGE_GAP_DURATIONS.get(language, DEFAULT_GAP_DURATION)
    
    for i in range(phrase_index):
        segment_path = os.path.join(audio_segments_dir, f'narration_{i}.{AUDIO_EXTENSION}')
        
        if os.path.exists(segment_path):
            segment_duration = get_audio_duration(audio_path=segment_path)
            total_time += segment_duration
            
            # Add gap between phrases
            if i in silence_set:
                total_time += DEFAULT_SILENCE_DURATION
            elif i not in nosilence_set:
                total_time += gap_duration
    
    return total_time


def _apply_overlay_lead_time(timestamp, lead_time=2.0):
    """Apply lead time offset to timestamp, ensuring non-negative result."""
    result = timestamp - lead_time
    return max(0.0, result)


def calculate_subscription_timestamp(output_folder, subscription_phrase_index, language='pt'):
    """Calculate timestamp to start overlay 2 seconds before subscription phrase occurs in audio."""
    try:
        if subscription_phrase_index is None:
            return None
        
        silence_set, nosilence_set = _get_silence_positions(output_folder, language)
        time_up_to_phrase = _calculate_time_up_to_phrase(
            output_folder, subscription_phrase_index, language, silence_set, nosilence_set
        )
        
        if time_up_to_phrase is None:
            return None
        
        return _apply_overlay_lead_time(time_up_to_phrase)
        
    except Exception as e:
        log_error(f'Error calculating subscription timestamp: {e}', step='subscription_timing')
        return None


def get_subscription_video_path(language='pt'):
    """Get path to subscription animation video for language.
    
    Subscription videos are stored in src/video/subscriptions/ folder.
    """
    subscription_filename = f'subscription_{language}.{VIDEO_EXTENSION}'
    # Get the directory where this module is located (src/video/)
    video_dir = os.path.dirname(os.path.abspath(__file__))
    subscription_path = os.path.join(video_dir, 'subscriptions', subscription_filename)
    
    if os.path.exists(subscription_path):
        return subscription_path
    
    return None


def get_video_dimensions(video_path):
    """Get video width and height using ffprobe."""
    try:
        probe_cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=s=x:p=0', video_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if probe_result.returncode == 0:
            parts = probe_result.stdout.strip().split('x')
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return None, None


def get_video_duration_from_ffprobe(video_path):
    """Get video duration using ffprobe."""
    try:
        probe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if probe_result.returncode == 0:
            return float(probe_result.stdout.strip())
    except Exception:
        pass
    return None


def _read_narration_text(output_folder, language):
    """Read narration text from file."""
    lang_folder = os.path.join(output_folder, 'narration', language)
    narration_file = os.path.join(lang_folder, 'narration.txt')
    
    if not os.path.exists(narration_file):
        return None
    
    try:
        with open(narration_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def get_subscription_overlay_info(output_folder, language='pt'):
    """Detect subscription and return overlay information.
    
    Returns:
        dict with 'timestamp' and 'subscription_video_path', or None if not needed
    """
    try:
        narration_text = _read_narration_text(output_folder, language)
        if not narration_text:
            return None
        
        subscription_phrase_index = detect_subscription_in_narration(narration_text, language)
        if subscription_phrase_index is None:
            return None
        
        subscription_timestamp = calculate_subscription_timestamp(
            output_folder, subscription_phrase_index, language
        )
        if subscription_timestamp is None:
            return None
        
        subscription_video_path = get_subscription_video_path(language)
        if not subscription_video_path:
            log('Subscription detected but video file not found, skipping overlay', step='subscription_detect')
            return None
        
        log(f'Subscription overlay will be added at {subscription_timestamp:.2f}s', step='subscription_detect')
        
        return {
            'timestamp': subscription_timestamp,
            'subscription_video_path': subscription_video_path
        }
        
    except Exception as e:
        log_error(f'Error detecting subscription: {e}', step='subscription_detect')
        return None


def _get_overlay_dimensions(main_height):
    """Calculate overlay dimensions and positioning."""
    max_sub_height = int(main_height * 0.4)  # Max 40% of main video height
    bottom_margin = int(main_height * 0.05)  # 5% margin from bottom
    return max_sub_height, bottom_margin


def _get_chromakey_settings():
    """Get chromakey filter settings for background removal."""
    bg_color = '0x00FF00'  # Green screen - RECOMMENDED
    bg_similarity = '0.3'  # For green screen
    bg_blend = '0.0'  # Fully opaque content, fully transparent background
    return bg_color, bg_similarity, bg_blend


def _build_video_overlay_filter(main_height, subscription_timestamp, overlay_end_time):
    """Build FFmpeg filter for video overlay with chromakey."""
    max_sub_height, bottom_margin = _get_overlay_dimensions(main_height)
    bg_color, bg_similarity, bg_blend = _get_chromakey_settings()
    
    return (
        f"[2:v]chromakey=color={bg_color}:similarity={bg_similarity}:blend={bg_blend},"
        f"format=yuva420p,scale=-1:{max_sub_height}[sub_scaled];"
        f"[0:v][sub_scaled]overlay=(W-w)/2:H-h-{bottom_margin}:"
        f"enable='between(t,{subscription_timestamp},{overlay_end_time})'[v]"
    )


def _build_audio_mixing_filter(subscription_timestamp, overlay_end_time, has_music=False):
    """Build FFmpeg filter for audio mixing with narration boost, optionally including background music."""
    subscription_audio_delay_ms = int(subscription_timestamp * 1000)
    
    if has_music:
        # Mix: narration + subscription + music (at 20%)
        return (
            f"[2:a]asetpts=PTS-STARTPTS,adelay={subscription_audio_delay_ms}|{subscription_audio_delay_ms}[sub_audio_delayed];"
            f"[1:a]volume=1.2[narration_boosted];"
            f"[3:a]volume=0.2[bgm];"
            f"[narration_boosted][sub_audio_delayed][bgm]amix=inputs=3:duration=first:dropout_transition=0:normalize=0,"
            f"volume='if(between(t,{subscription_timestamp},{overlay_end_time}),0.667,1.0)'[a]"
        )
    else:
        # Mix: narration + subscription (original behavior)
        return (
            f"[2:a]asetpts=PTS-STARTPTS,adelay={subscription_audio_delay_ms}|{subscription_audio_delay_ms}[sub_audio_delayed];"
            f"[1:a]volume=1.2[narration_boosted];"
            f"[narration_boosted][sub_audio_delayed]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            f"volume='if(between(t,{subscription_timestamp},{overlay_end_time}),0.667,1.0)'[a]"
        )


def _build_filter_complex(main_height, subscription_timestamp, overlay_end_time, has_music=False):
    """Build complete FFmpeg filter_complex string."""
    video_filter = _build_video_overlay_filter(main_height, subscription_timestamp, overlay_end_time)
    audio_filter = _build_audio_mixing_filter(subscription_timestamp, overlay_end_time, has_music)
    
    return f"{video_filter};{audio_filter}"


def _build_ffmpeg_base_command(video_path, audio_path, subscription_video_path, 
                               subscription_timestamp, output_path, music_path=None):
    """Build base FFmpeg command with inputs."""
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,              # Input 0: main video
        '-i', audio_path,              # Input 1: narration audio
        '-itsoffset', str(subscription_timestamp),
        '-i', subscription_video_path, # Input 2: subscription video (delayed)
    ]
    
    # Add music input if provided
    if music_path:
        cmd.extend(['-i', music_path])  # Input 3: background music
    
    return cmd


def _build_ffmpeg_output_args(output_path):
    """Build FFmpeg output encoding arguments."""
    return [
        '-map', '[v]',                 # Map filtered video
        '-map', '[a]',                 # Map mixed audio
        '-c:v', 'h264_nvenc',
        '-preset', 'p6',
        '-cq', '22',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-ar', '44100',
        '-movflags', '+faststart',
        output_path
    ]


def build_ffmpeg_merge_with_subscription_command(video_path, audio_path, subscription_video_path,
                                                 subscription_timestamp, main_width, main_height,
                                                 output_path, overlay_duration=3.0, music_path=None):
    """Build ffmpeg command for merging video, audio, and subscription overlay in one pass.
    
    The subscription video will play from the start for its full duration (overlay_duration).
    The overlay is positioned at bottom center and only visible during the specified time range.
    Optionally includes background music if music_path is provided.
    """
    overlay_end_time = subscription_timestamp + overlay_duration
    has_music = music_path is not None
    filter_complex = _build_filter_complex(main_height, subscription_timestamp, overlay_end_time, has_music)
    
    base_cmd = _build_ffmpeg_base_command(
        video_path, audio_path, subscription_video_path, subscription_timestamp, output_path, music_path
    )
    output_args = _build_ffmpeg_output_args(output_path)
    
    return base_cmd + ['-filter_complex', filter_complex] + output_args


