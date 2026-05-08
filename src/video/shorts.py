"""Generate vertical shorts from final videos by splitting at silence markers."""

import os
import subprocess
import glob
import cv2
from pathlib import Path
from logger import log, log_error, log_success
from constants import VIDEO_EXTENSION, AUDIO_EXTENSION
from audio.generate import split_narration_by_phrases
from audio.files import get_audio_duration
from audio.utils import DEFAULT_SILENCE_DURATION, LANGUAGE_GAP_DURATIONS, DEFAULT_GAP_DURATION
from video.merge import get_video_duration_from_ffprobe
from video.utils import get_image_start_time, get_image_duration, get_image_index_for_time
from ultralytics import YOLO

SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
PERSON_DETECTION_CONFIDENCE = 0.25
SUBTITLE_FONT_SIZE = 55
SUBTITLE_COLOR = 'yellow'
SUBTITLE_BORDER_COLOR = 'black'
SUBTITLE_BORDER_WIDTH = 4
SUBTITLE_POSITION_Y = 'h/2+400'
SUBTITLE_WORDS_PER_GROUP = 6
SUBTITLE_WORDS_PER_LINE = 3
SUBTITLE_BACKGROUND_ENABLED = True
SUBTITLE_BACKGROUND_COLOR = 'black@0.5'
SUBTITLE_BACKGROUND_BORDER = 40
SUBTITLE_BACKGROUND_VERTICAL_PADDING = 7

def _extract_ffmpeg_error_message(output):
    """Extract meaningful error message from FFmpeg output, skipping version/config info.
    
    Args:
        output: Full FFmpeg stderr/stdout output
        
    Returns:
        Extracted error message string
    """
    if not output:
        return 'Unknown error'
    
    lines = output.split('\n')
    error_keywords = ['error', 'Error', 'ERROR', 'failed', 'Failed', 'FAILED', 'Invalid', 'invalid', 'INVALID']
    version_keywords = ['ffmpeg version', 'built with', 'configuration:', 'lib', 'configuration']
    
    error_lines = []
    skip_version_section = True
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if skip_version_section:
            if any(keyword in line for keyword in version_keywords):
                continue
            skip_version_section = False
        
        if any(keyword in line for keyword in error_keywords):
            error_lines.append(line)
    
    if error_lines:
        error_msg = '\n'.join(error_lines)
        if len(error_msg) > 500:
            error_msg = error_msg[:497] + '...'
        return error_msg
    
    last_lines = [line.strip() for line in lines[-10:] if line.strip()]
    if last_lines:
        error_msg = '\n'.join(last_lines)
        if len(error_msg) > 500:
            error_msg = error_msg[:497] + '...'
        return error_msg
    
    return output[:500] if len(output) > 500 else output

def _run_subprocess(cmd, timeout=120, error_context=''):
    """Run subprocess command with consistent error handling.
    
    Args:
        cmd: Command list to execute
        timeout: Timeout in seconds
        error_context: Context string for error messages
        
    Returns:
        Tuple of (success: bool, stderr: str or stdout: str)
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stderr if result.stderr else result.stdout
    except subprocess.TimeoutExpired:
        log_error(f'Subprocess timed out after {timeout}s{": " + error_context if error_context else ""}', step='shorts')
        return False, f'Timeout after {timeout}s'
    except Exception as e:
        log_error(f'Subprocess error{": " + error_context if error_context else ""}: {e}', step='shorts')
        return False, str(e)


def _cleanup_files(file_paths):
    """Remove multiple files, ignoring errors.
    
    Args:
        file_paths: List of file paths to remove
    """
    for file_path in file_paths:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass


def _cleanup_directory(dir_path):
    """Remove directory if it exists, ignoring errors.
    
    Args:
        dir_path: Directory path to remove
    """
    if dir_path and os.path.exists(dir_path):
        try:
            import shutil
            shutil.rmtree(dir_path)
        except Exception:
            pass


def _create_concat_list(concat_file_path, video_files):
    """Create FFmpeg concat list file.
    
    Args:
        concat_file_path: Path to concat list file
        video_files: List of video file paths
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(concat_file_path, 'w') as f:
            for video_file in video_files:
                f.write(f"file '{os.path.abspath(video_file)}'\n")
        return True
    except Exception as e:
        log_error(f'Failed to create concat list: {e}', step='shorts')
        return False


def _run_ffmpeg_concat(concat_file_path, output_path, timeout=300):
    """Run FFmpeg concat command.
    
    Args:
        concat_file_path: Path to concat list file
        output_path: Output video path
        timeout: Timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file_path,
        '-c', 'copy',
        output_path
    ]
    
    success, error = _run_subprocess(cmd, timeout=timeout, error_context='FFmpeg concat')
    if not success:
        error_msg = _extract_ffmpeg_error_message(error)
        log_error(f'FFmpeg concat failed: {error_msg}', step='shorts')
    return success


def _validate_video_duration(video_path, min_duration=0.5):
    """Validate video duration.
    
    Args:
        video_path: Path to video file
        min_duration: Minimum valid duration in seconds
        
    Returns:
        Duration if valid, None otherwise
    """
    duration = get_video_duration_from_ffprobe(video_path)
    if not duration or duration < min_duration:
        log_error(f'Invalid video duration ({duration:.2f}s): {video_path}', step='shorts')
        return None
    return duration


def _extract_video_segment_ffmpeg(input_path, output_path, start_time, duration, timeout=60):
    """Extract video segment using FFmpeg.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        start_time: Start time in seconds
        duration: Duration in seconds
        timeout: Timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-c:a', 'copy',
        output_path
    ]
    
    success, error = _run_subprocess(cmd, timeout=timeout, error_context='Video segment extraction')
    if not success:
        error_msg = _extract_ffmpeg_error_message(error)
        log_error(f'Failed to extract segment: {error_msg}', step='shorts')
    return success



def _get_yolo_person_model_path():
    """Get path to YOLO person detection model."""
    model_path = Path(__file__).parent.parent.parent / 'models' / 'yolo' / 'yolov8n.pt'
    return str(model_path)


def _load_person_detection_model():
    """Load YOLO person detection model."""
    try:
        model_path = _get_yolo_person_model_path()
        if not os.path.exists(model_path):
            log_error(f'YOLO model not found: {model_path}', step='shorts')
            return None
        return YOLO(model_path)
    except Exception as e:
        log_error(f'Failed to load YOLO model: {e}', step='shorts')
        return None


def _cleanup_model(model):
    """Cleanup YOLO model from GPU memory."""
    if model is not None:
        try:
            if hasattr(model, 'model'):
                model.model.to('cpu')
            del model
            import torch
            torch.cuda.empty_cache()
        except:
            pass



def detect_main_subject_center(frame, model):
    """Detect the biggest person in frame and return their center x coordinate."""
    try:
        results = model(frame, classes=[0], conf=PERSON_DETECTION_CONFIDENCE, verbose=False)
        
        if len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
            return None
        
        boxes = results[0].boxes.xyxy.cpu().numpy()
        confidences = results[0].boxes.conf.cpu().numpy()
        
        biggest_area = 0
        biggest_center_x = None
        
        for box, conf in zip(boxes, confidences):
            x_min, y_min, x_max, y_max = box
            area = (x_max - x_min) * (y_max - y_min)
            
            if area > biggest_area:
                biggest_area = area
                biggest_center_x = (x_min + x_max) / 2.0
        
        return biggest_center_x
        
    except Exception as e:
        log_error(f'Error detecting person in frame: {e}', step='shorts')
        return None



def _parse_silence_start_line(line):
    """Parse silence_start line from ffmpeg output."""
    try:
        parts = line.split('silence_start:')
        if len(parts) > 1:
            return float(parts[1].strip())
    except (ValueError, IndexError):
        pass
    return None


def _parse_silence_end_line(line):
    """Parse silence_end line from ffmpeg output."""
    try:
        parts = line.split('silence_end:')
        if len(parts) > 1:
            silence_end_str = parts[1].split('|')[0].strip()
            return float(silence_end_str)
    except (ValueError, IndexError):
        pass
    return None


def _extract_silence_periods_from_ffmpeg_output(output_lines):
    """Extract silence periods from ffmpeg silencedetect output."""
    silence_periods = []
    silence_start = None
    
    for line in output_lines:
        if 'silence_start' in line:
            silence_start = _parse_silence_start_line(line)
        elif 'silence_end' in line and silence_start is not None:
            silence_end = _parse_silence_end_line(line)
            if silence_end and silence_end > silence_start:
                silence_periods.append((silence_start, silence_end))
            silence_start = None
    
    return silence_periods


def detect_silence_in_audio(audio_path, min_silence_duration=0.5, silence_threshold=-30):
    """Detect silence periods in audio file using ffmpeg silencedetect."""
    try:
        cmd = [
            'ffmpeg', '-i', audio_path,
            '-af', f'silencedetect=noise={silence_threshold}dB:d={min_silence_duration}',
            '-f', 'null', '-'
        ]
        
        success, error_output = _run_subprocess(cmd, timeout=300, error_context='Silence detection')
        
        if not success:
            error_msg = _extract_ffmpeg_error_message(error_output)
            log_error(f'FFmpeg silence detection failed: {error_msg}', step='shorts')
            return []
        
        silence_periods = _extract_silence_periods_from_ffmpeg_output(error_output.split('\n'))
        log(f'Detected {len(silence_periods)} silence period(s) in audio', step='shorts')
        return silence_periods
        
    except Exception as e:
        log_error(f'Error detecting silence in audio: {e}', step='shorts')
        return []


def find_silence_period_near_timestamp(audio_silence_periods, target_time, tolerance=5.0):
    """Find the actual silence period in audio that corresponds to a narration silence marker."""
    if not audio_silence_periods:
        return None
    
    best_match = None
    min_distance = float('inf')
    
    for silence_start, silence_end in audio_silence_periods:
        if silence_start <= target_time <= silence_end:
            return (silence_start, silence_end)
        
        silence_middle = (silence_start + silence_end) / 2.0
        distance_to_start = abs(silence_start - target_time)
        distance_to_end = abs(silence_end - target_time)
        distance_to_middle = abs(silence_middle - target_time)
        
        min_dist = min(distance_to_start, distance_to_end, distance_to_middle)
        if min_dist < tolerance and min_dist < min_distance:
            min_distance = min_dist
            best_match = (silence_start, silence_end)
    
    return best_match



def _get_narration_data(video_folder, language):
    """Load and parse narration data for a language."""
    narration_file = os.path.join(video_folder, 'narration', language, 'narration.txt')
    if not os.path.exists(narration_file):
        return None, None, None, None
    
    try:
        with open(narration_file, 'r', encoding='utf-8') as f:
            narration_text = f.read()
        
        phrases, silence_positions, nosilence_positions = split_narration_by_phrases(narration_text)
        if not phrases:
            return None, None, None, None
        
        lang_folder = os.path.join(video_folder, 'narration', language)
        audio_segments_dir = os.path.join(lang_folder, 'audio_segments')
        
        return phrases, silence_positions, nosilence_positions, audio_segments_dir
    except Exception as e:
        log_error(f'Error loading narration data: {e}', step='shorts')
        return None, None, None, None


def _calculate_phrase_timestamps(phrases, silence_positions, nosilence_positions, audio_segments_dir, language):
    """Calculate approximate timestamps for each phrase."""
    silence_set = set(silence_positions) if silence_positions else set()
    nosilence_set = set(nosilence_positions) if nosilence_positions else set()
    gap_duration = LANGUAGE_GAP_DURATIONS.get(language, DEFAULT_GAP_DURATION)
    
    timestamps = []
    current_time = 0.0
    
    for i, phrase in enumerate(phrases):
        segment_path = os.path.join(audio_segments_dir, f'narration_{i}.{AUDIO_EXTENSION}')
        
        if os.path.exists(segment_path):
            segment_duration = get_audio_duration(audio_path=segment_path)
            phrase_end = current_time + segment_duration
            timestamps.append(phrase_end)
            current_time = phrase_end
            
            if i in silence_set:
                current_time += DEFAULT_SILENCE_DURATION
            elif i not in nosilence_set:
                current_time += gap_duration
        else:
            log_error(f'Audio segment not found: {segment_path}', step='shorts')
    
    return timestamps



def _validate_video_for_splits(final_video, language):
    """Validate video file exists and has valid duration."""
    if not os.path.exists(final_video):
        log_error(f'Final {language} video not found: {final_video}', step='shorts')
        return None
    
    video_duration = get_video_duration_from_ffprobe(final_video)
    if not video_duration or video_duration <= 0:
        log_error(f'Invalid video duration: {video_duration}', step='shorts')
        return None
    
    return video_duration


def _match_silence_markers_to_audio_periods(silence_positions, approximate_timestamps, audio_silence_periods):
    """Match narration silence markers with actual detected silence periods."""
    sorted_silences = sorted(silence_positions)
    matched_silence_periods = []
    available_silences = list(audio_silence_periods)
    
    for silence_idx in sorted_silences:
        if silence_idx < len(approximate_timestamps):
            expected_silence_time = approximate_timestamps[silence_idx]
            matched_silence = find_silence_period_near_timestamp(available_silences, expected_silence_time, tolerance=5.0)
            
            if matched_silence:
                matched_silence_periods.append(matched_silence)
                available_silences.remove(matched_silence)
                distance = min(abs(matched_silence[0] - expected_silence_time), abs(matched_silence[1] - expected_silence_time))
                log(f'Matched silence {len(matched_silence_periods)}: {matched_silence[0]:.2f}-{matched_silence[1]:.2f}s (expected at {expected_silence_time:.2f}s, distance: {distance:.2f}s)', step='shorts')
            else:
                closest = None
                min_dist = float('inf')
                for s_start, s_end in available_silences:
                    dist = min(abs(s_start - expected_silence_time), abs(s_end - expected_silence_time), abs((s_start + s_end) / 2 - expected_silence_time))
                    if dist < min_dist:
                        min_dist = dist
                        closest = (s_start, s_end)
                
                if closest:
                    log_error(f'Could not match silence marker {silence_idx} at expected time {expected_silence_time:.2f}s (closest: {closest[0]:.2f}-{closest[1]:.2f}s, distance: {min_dist:.2f}s)', step='shorts')
                else:
                    log_error(f'Could not match silence marker {silence_idx} at expected time {expected_silence_time:.2f}s', step='shorts')
    
    matched_silence_periods.sort(key=lambda x: x[0])
    return matched_silence_periods


def _create_splits_from_matched_silences(matched_silence_periods, video_duration):
    """Create split timestamps from matched silence periods."""
    START_BUFFER = 0.0
    splits = []
    
    if not matched_silence_periods:
        return splits
    
    first_silence_start = matched_silence_periods[0][0]
    if first_silence_start > 0.1:
        splits.append((0.0, first_silence_start))
    
    for i in range(len(matched_silence_periods) - 1):
        segment_start = matched_silence_periods[i][1] + START_BUFFER
        segment_end = matched_silence_periods[i + 1][0]
        
        if segment_end > segment_start + 0.1:
            splits.append((segment_start, segment_end))
    
    last_segment_start = matched_silence_periods[-1][1] + START_BUFFER
    if video_duration > last_segment_start + 0.1:
        splits.append((last_segment_start, video_duration))
    
    return splits


def calculate_split_timestamps(video_folder, language):
    """Calculate start/end times for each short segment based on (silence) markers in narration."""
    try:
        final_video = os.path.join(video_folder, f'final_{language}.{VIDEO_EXTENSION}')
        video_duration = _validate_video_for_splits(final_video, language)
        if not video_duration:
            return []
        
        phrases, silence_positions, nosilence_positions, audio_segments_dir = _get_narration_data(video_folder, language)
        if phrases is None:
            return []
        
        if not os.path.exists(audio_segments_dir):
            log_error(f'Audio segments directory not found: {audio_segments_dir}', step='shorts')
            return []
        
        narration_audio = os.path.join(video_folder, 'narration', language, f'narration_0.{AUDIO_EXTENSION}')
        if not os.path.exists(narration_audio):
            log_error(f'Narration audio file not found: {narration_audio}', step='shorts')
            return []
        
        audio_silence_periods = detect_silence_in_audio(narration_audio, min_silence_duration=0.3, silence_threshold=-30)
        
        if not audio_silence_periods:
            log_error('No silence periods detected in audio, creating one short', step='shorts')
            return [(0.0, video_duration)]
        
        approximate_timestamps = _calculate_phrase_timestamps(phrases, silence_positions, nosilence_positions, audio_segments_dir, language)
        
        if not approximate_timestamps:
            log_error('No phrase timestamps calculated', step='shorts')
            return []
        
        if not silence_positions:
            log(f'No silence markers, creating one short from entire video', step='shorts')
            return [(0.0, video_duration)]
        
        matched_silence_periods = _match_silence_markers_to_audio_periods(silence_positions, approximate_timestamps, audio_silence_periods)
        
        if len(matched_silence_periods) != len(silence_positions):
            log_error(f'Matched {len(matched_silence_periods)} silences but expected {len(silence_positions)}', step='shorts')
        
        if not matched_silence_periods:
            log_error('No silence periods matched, creating one short', step='shorts')
            return [(0.0, video_duration)]
        
        splits = _create_splits_from_matched_silences(matched_silence_periods, video_duration)
        log(f'Calculated {len(splits)} split(s) for {language} video based on {len(silence_positions)} silence marker(s) in narration', step='shorts')
        return splits
        
    except Exception as e:
        log_error(f'Error calculating split timestamps: {e}', step='shorts')
        return []



def _calculate_crop_dimensions(source_width, source_height):
    """Calculate crop dimensions for portrait shorts.
    
    Args:
        source_width: Source video/image width
        source_height: Source video/image height
        
    Returns:
        Tuple of (crop_width, crop_height, scaled_height, pad_top, default_crop_x)
    """
    crop_width = int(source_width * 0.35)
    crop_height = source_height
    scaled_height = int(crop_height * SHORTS_WIDTH / crop_width)
    total_padding = SHORTS_HEIGHT - scaled_height
    pad_top = int(total_padding * 0.3)
    default_crop_x = (source_width - crop_width) // 2
    
    return crop_width, crop_height, scaled_height, pad_top, default_crop_x



def _build_crop_filters(crop_filter, scaled_height, pad_top):
    """Build crop filter attempts with blur options."""
    base_scale = f'{crop_filter},scale={SHORTS_WIDTH}:{scaled_height}'
    blur_base = f'split[sharp][to_blur];[to_blur]'
    blur_scale = f'gblur=sigma=30:steps=4,scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=increase,crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}[blurred_bg];[blurred_bg][sharp]overlay=0:{pad_top}'
    boxblur_scale = f'boxblur=luma_radius=30:luma_power=4:chroma_radius=30:chroma_power=4,scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=increase,crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}[blurred_bg];[blurred_bg][sharp]overlay=0:{pad_top}'
    
    return [
        ('gblur on borders only with edge padding', f'{base_scale},{blur_base}{blur_scale}'),
        ('boxblur on borders only with edge padding', f'{base_scale},{blur_base}{boxblur_scale}'),
        ('gblur on borders only with black padding', f'{base_scale},{blur_base}{blur_scale}'),
        ('boxblur on borders only with black padding', f'{base_scale},{blur_base}{boxblur_scale}'),
        ('edge padding without blur', f'{base_scale},pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:0:{pad_top}:edge'),
        ('black padding without blur', f'{base_scale},pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:0:{pad_top}:black'),
    ]


def _run_ffmpeg_filter(input_path, output_path, filter_complex, use_expression=False, timeout=120):
    """Run ffmpeg with a filter complex."""
    cmd = ['ffmpeg', '-y', '-i', input_path]
    
    if use_expression:
        cmd.extend(['-filter_complex', filter_complex])
    else:
        cmd.extend(['-vf', filter_complex])
    
    cmd.extend([
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'copy',
        output_path
    ])
    
    return _run_subprocess(cmd, timeout=timeout, error_context='FFmpeg filter')


def _apply_crop_with_blur(input_path, output_path, crop_filter, crop_width, crop_height, scaled_height, pad_top, duration=None, fps=24):
    """Apply crop filter with blur options to a video segment or image.
    
    Args:
        input_path: Input video or image path
        output_path: Output video path
        crop_filter: FFmpeg crop filter string
        crop_width: Crop width in pixels
        crop_height: Crop height in pixels
        scaled_height: Scaled height for output
        pad_top: Top padding for output
        duration: Optional duration in seconds (for images)
        fps: Frames per second (for images)
    """
    try:
        filter_attempts = _build_crop_filters(crop_filter, scaled_height, pad_top)
        use_expression = 't' in crop_filter
        
        is_image = input_path.lower().endswith(('.png', '.jpg', '.jpeg'))
        
        for attempt_name, filter_complex in filter_attempts:
            if is_image and duration:
                return _apply_crop_with_blur_to_image(input_path, output_path, crop_filter, crop_width, crop_height, scaled_height, pad_top, duration, fps)
            else:
                success, error = _run_ffmpeg_filter(input_path, output_path, filter_complex, use_expression, timeout=120)
                if success:
                    return True
        
        log_error(f'Failed to apply crop with blur: {attempt_name}', step='shorts')
        return False
        
    except Exception as e:
        log_error(f'Error cropping segment: {e}', step='shorts')
        return False



def _extract_segment(input_path, output_path, start_time, duration):
    """Extract a video segment using ffmpeg."""
    return _extract_video_segment_ffmpeg(input_path, output_path, start_time, duration, timeout=60)


def _calculate_transition_duration(crop_x, previous_crop_x, crop_width, total_duration):
    """Calculate transition duration based on crop distance."""
    distance = abs(crop_x - previous_crop_x)
    distance_threshold = crop_width * 0.3
    transition_duration = 1.0 if distance < distance_threshold else 4.0
    return min(transition_duration, total_duration - 0.1)


def _create_transition_segment(video_path, segment_start, transition_duration, previous_crop_x, crop_x, crop_width, crop_height, scaled_height, pad_top, transition_part):
    """Create transition segment with animated crop."""
    temp_transition = transition_part.replace('.mp4', '_temp.mp4')
    if not _extract_segment(video_path, temp_transition, segment_start, transition_duration):
        log_error(f'Failed to extract transition', step='shorts')
        return False
    
    crop_x_expr = f"{previous_crop_x}+({crop_x}-{previous_crop_x})*(t/{transition_duration})"
    crop_filter = f"crop={crop_width}:{crop_height}:{crop_x_expr}:0"
    
    success = _apply_crop_with_blur(temp_transition, transition_part, crop_filter, crop_width, crop_height, scaled_height, pad_top)
    _cleanup_files([temp_transition])
    return success


def _create_hold_segment(video_path, hold_start, hold_duration, crop_x, crop_width, crop_height, scaled_height, pad_top, hold_part):
    """Create hold segment with static crop."""
    temp_hold = hold_part.replace('.mp4', '_temp.mp4')
    if not _extract_segment(video_path, temp_hold, hold_start, hold_duration):
        log_error(f'Failed to extract hold', step='shorts')
        return False
    
    crop_filter = f"crop={crop_width}:{crop_height}:{crop_x}:0"
    success = _apply_crop_with_blur(temp_hold, hold_part, crop_filter, crop_width, crop_height, scaled_height, pad_top)
    _cleanup_files([temp_hold])
    return success


def _crop_segment_with_transition(video_path, output_path, segment_start, duration, previous_crop_x, crop_x, crop_width, crop_height, scaled_height, pad_top):
    """Crop segment with transition animation between crop positions."""
    transition_duration = _calculate_transition_duration(crop_x, previous_crop_x, crop_width, duration)
    hold_duration = duration - transition_duration
    
    temp_dir = os.path.dirname(output_path)
    transition_part = os.path.join(temp_dir, f'transition_{os.path.basename(output_path)}')
    hold_part = os.path.join(temp_dir, f'hold_{os.path.basename(output_path)}')
    
    if not _create_transition_segment(video_path, segment_start, transition_duration, previous_crop_x, crop_x, crop_width, crop_height, scaled_height, pad_top, transition_part):
        return False
    
    hold_start = segment_start + transition_duration
    if not _create_hold_segment(video_path, hold_start, hold_duration, crop_x, crop_width, crop_height, scaled_height, pad_top, hold_part):
        _cleanup_files([transition_part])
        return False
    
    concat_list = os.path.join(temp_dir, f'concat_{os.path.basename(output_path)}.txt')
    if not _create_concat_list(concat_list, [transition_part, hold_part]):
        _cleanup_files([transition_part, hold_part])
        return False
    
    success = _run_ffmpeg_concat(concat_list, output_path, timeout=120)
    _cleanup_files([transition_part, hold_part, concat_list])
    return success


def _crop_segment_simple(video_path, output_path, segment_start, duration, crop_x, crop_width, crop_height, scaled_height, pad_top):
    """Crop segment without transition (simple case)."""
    temp_segment = output_path.replace('.mp4', '_temp_segment.mp4')
    if not _extract_segment(video_path, temp_segment, segment_start, duration):
        log_error(f'Failed to extract segment', step='shorts')
        return False
    
    crop_filter = f"crop={crop_width}:{crop_height}:{crop_x}:0"
    success = _apply_crop_with_blur(temp_segment, output_path, crop_filter, crop_width, crop_height, scaled_height, pad_top)
    _cleanup_files([temp_segment])
    return success


def _crop_single_image_segment(video_path, output_path, source_width, source_height, crop_x, segment_start, segment_end, previous_crop_x=None):
    """Crop a single image segment with specific crop_x position."""
    try:
        crop_width, crop_height, scaled_height, pad_top, _ = _calculate_crop_dimensions(source_width, source_height)
        duration = segment_end - segment_start
        
        if previous_crop_x is not None and previous_crop_x != crop_x and duration > 1.0:
            return _crop_segment_with_transition(video_path, output_path, segment_start, duration, previous_crop_x, crop_x, crop_width, crop_height, scaled_height, pad_top)
        else:
            return _crop_segment_simple(video_path, output_path, segment_start, duration, crop_x, crop_width, crop_height, scaled_height, pad_top)
        
    except Exception as e:
        log_error(f'Error cropping image segment: {e}', step='shorts')
        return False


def _calculate_crop_x_from_subject_center(normalized_center, source_width, crop_width, default_crop_x):
    """Calculate crop_x position from normalized subject center."""
    if normalized_center is not None:
        subject_pixel_x = normalized_center * source_width
        crop_x_value = int(subject_pixel_x - crop_width / 2)
        return max(0, min(crop_x_value, source_width - crop_width))
    return default_crop_x


def _crop_video_segments_with_subject_centers(video_path, output_path, source_width, source_height, subject_centers, video_duration, crop_width, crop_height, scaled_height, pad_top, default_crop_x):
    """Crop video using subject-centered cropping for multiple segments."""
    log(f'Processing {len(subject_centers)} image segment(s) with subject-centered cropping', step='shorts')
    
    temp_dir = os.path.join(os.path.dirname(output_path), 'temp_crop_segments')
    os.makedirs(temp_dir, exist_ok=True)
    
    segment_files = []
    sorted_centers = sorted(subject_centers.items())
    previous_crop_x = None
    
    for idx, (image_idx, normalized_center) in enumerate(sorted_centers):
        crop_x_value = _calculate_crop_x_from_subject_center(normalized_center, source_width, crop_width, default_crop_x)
        segment_start = get_image_start_time(image_idx)
        segment_end = min(get_image_start_time(image_idx) + get_image_duration(image_idx), video_duration)
        segment_output = os.path.join(temp_dir, f'segment_{image_idx:03d}.mp4')
        
        if not _crop_single_image_segment(video_path, segment_output, source_width, source_height, 
                                           crop_x_value, segment_start, segment_end, previous_crop_x):
            log_error(f'Failed to crop segment {image_idx}', step='shorts')
            _cleanup_directory(temp_dir)
            return False
        
        segment_files.append(segment_output)
        previous_crop_x = crop_x_value
    
    last_image_idx = sorted_centers[-1][0]
    last_segment_end = get_image_start_time(last_image_idx) + get_image_duration(last_image_idx)
    if last_segment_end < video_duration - 0.5:
        segment_start = last_segment_end
        segment_end = video_duration
        segment_output = os.path.join(temp_dir, f'segment_default.mp4')
        if _crop_single_image_segment(video_path, segment_output, source_width, source_height,
                                     default_crop_x, segment_start, segment_end):
            segment_files.append(segment_output)
            
            concat_list_file = os.path.join(temp_dir, 'concat_list.txt')
    if not _create_concat_list(concat_list_file, segment_files):
        _cleanup_directory(temp_dir)
        return False
    
    success = _run_ffmpeg_concat(concat_list_file, output_path, timeout=300)
    _cleanup_directory(temp_dir)
    return success


def _crop_video_single_pass(video_path, output_path, crop_width, crop_height, scaled_height, pad_top, default_crop_x):
    """Crop entire video in a single pass (default case)."""
    crop_x = default_crop_x
    crop_filter = f"crop={crop_width}:{crop_height}:{crop_x}:0"
    
    filter_attempts = _build_crop_filters(crop_filter, scaled_height, pad_top)
    last_error = None
    
    for attempt_name, filter_complex in filter_attempts:
        success, error = _run_ffmpeg_filter(video_path, output_path, filter_complex, use_expression=False, timeout=300)
        if success:
            if attempt_name != filter_attempts[0][0]:
                log(f'Success with fallback: {attempt_name}', step='shorts')
            break
        
        last_error = error
        if attempt_name != filter_attempts[-1][0]:
            log(f'{attempt_name} failed, trying next fallback', step='shorts')
    else:
        full_error = _extract_ffmpeg_error_message(last_error)
        log_error(f'FFmpeg crop failed with all methods. Last error: {full_error}', step='shorts')
        return False
    
    if not os.path.exists(output_path):
        log_error(f'Output file not created: {output_path}', step='shorts')
        return False
    
    return True


def crop_to_portrait(video_path, output_path, source_width, source_height, subject_centers=None):
    """Crop video from 16:9 landscape to 9:16 portrait (1080x1920)."""
    try:
        video_duration = get_video_duration_from_ffprobe(video_path)
        if not video_duration or video_duration <= 0:
            log_error('Invalid video duration', step='shorts')
            return False
        
        crop_width, crop_height, scaled_height, pad_top, default_crop_x = _calculate_crop_dimensions(source_width, source_height)
        
        if subject_centers and len(subject_centers) > 0:
            return _crop_video_segments_with_subject_centers(video_path, output_path, source_width, source_height, subject_centers, video_duration, crop_width, crop_height, scaled_height, pad_top, default_crop_x)
        else:
            return _crop_video_single_pass(video_path, output_path, crop_width, crop_height, scaled_height, pad_top, default_crop_x)
        
    except Exception as e:
        log_error(f'Error cropping video: {e}', step='shorts')
        return False



def _calculate_next_time(phrase_end, i, silence_set, nosilence_set, gap_duration):
    """Calculate next time after processing a phrase.
    
    Args:
        phrase_end: End time of the phrase
        i: Phrase index
        silence_set: Set of silence position indices
        nosilence_set: Set of no-silence position indices
        gap_duration: Default gap duration
        
    Returns:
        Next time value
    """
    next_time = phrase_end
    if i in silence_set:
        next_time += DEFAULT_SILENCE_DURATION
    elif i not in nosilence_set:
        next_time += gap_duration
    return next_time


def _calculate_word_timings_for_phrase(phrase, phrase_start, phrase_end, start_time, end_time, word_duration):
    """Calculate word timings for a phrase within the segment time range."""
    word_timings = []
    words = phrase.strip().split()
    
    if not words:
        return word_timings
    
    for word_idx, word in enumerate(words):
        word_start_abs = phrase_start + (word_idx * word_duration)
        word_end_abs = word_start_abs + word_duration
        
        if word_end_abs >= start_time and word_start_abs <= end_time:
            word_start_rel = max(0.0, word_start_abs - start_time)
            word_end_rel = min(end_time - start_time, word_end_abs - start_time)
            word_timings.append((word, word_start_rel, word_end_rel))
    
    return word_timings


def _process_phrase_with_audio_segment(i, phrase, current_time, start_time, end_time, audio_segments_dir, silence_set, nosilence_set, gap_duration):
    """Process phrase when audio segment file exists."""
    segment_path = os.path.join(audio_segments_dir, f'narration_{i}.{AUDIO_EXTENSION}')
    segment_duration = get_audio_duration(audio_path=segment_path)
    phrase_start = current_time
    phrase_end = current_time + segment_duration
    
    word_timings = []
    if phrase_end >= start_time and phrase_start <= end_time:
        words_per_second = len(phrase.strip().split()) / segment_duration if segment_duration > 0 else 2.5
        word_duration = 1.0 / words_per_second
        word_timings = _calculate_word_timings_for_phrase(phrase, phrase_start, phrase_end, start_time, end_time, word_duration)
    
    next_time = _calculate_next_time(phrase_end, i, silence_set, nosilence_set, gap_duration)
    return word_timings, next_time


def _process_phrase_without_audio_segment(i, phrase, current_time, start_time, end_time):
    """Process phrase when audio segment file doesn't exist (fallback estimation)."""
    words = phrase.strip().split()
    word_timings = []
    
    if words:
        estimated_duration = len(words) * 0.4
        phrase_start = current_time
        phrase_end = current_time + estimated_duration
        
        if phrase_end >= start_time and phrase_start <= end_time:
            word_duration = 0.4
            word_timings = _calculate_word_timings_for_phrase(phrase, phrase_start, phrase_end, start_time, end_time, word_duration)
        
        next_time = phrase_end
    else:
        next_time = current_time
    
    return word_timings, next_time


def _process_phrase_for_word_timings(i, phrase, current_time, start_time, end_time, audio_segments_dir, silence_set, nosilence_set, gap_duration):
    """Process a phrase and return word timings."""
    segment_path = os.path.join(audio_segments_dir, f'narration_{i}.{AUDIO_EXTENSION}')
    
    if os.path.exists(segment_path):
        return _process_phrase_with_audio_segment(i, phrase, current_time, start_time, end_time, audio_segments_dir, silence_set, nosilence_set, gap_duration)
    else:
        return _process_phrase_without_audio_segment(i, phrase, current_time, start_time, end_time)


def get_word_timings_for_segment(video_folder, language, start_time, end_time):
    """Get word-level timings for a specific time segment."""
    try:
        phrases, silence_positions, nosilence_positions, audio_segments_dir = _get_narration_data(video_folder, language)
        if phrases is None:
            return []
        
        if not os.path.exists(audio_segments_dir):
            return []
        
        silence_set = set(silence_positions) if silence_positions else set()
        nosilence_set = set(nosilence_positions) if nosilence_positions else set()
        gap_duration = LANGUAGE_GAP_DURATIONS.get(language, DEFAULT_GAP_DURATION)
        
        word_timings = []
        current_time = 0.0
        
        for i, phrase in enumerate(phrases):
            phrase_timings, current_time = _process_phrase_for_word_timings(
                i, phrase, current_time, start_time, end_time, audio_segments_dir,
                silence_set, nosilence_set, gap_duration
            )
            word_timings.extend(phrase_timings)
        
        return word_timings
        
    except Exception as e:
        log_error(f'Error getting word timings for segment: {e}', step='shorts')
        return []



def _get_font_option():
    """Get font file option for ffmpeg (without colon prefix)."""
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            return f"fontfile={font_path}"
    return ''


def _escape_text_for_ffmpeg(text):
    """Escape text for ffmpeg drawtext filter."""
    escaped = text.replace('\\', '\\\\')
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace(':', '\\:')
    escaped = escaped.replace('[', '\\[')
    escaped = escaped.replace(']', '\\]')
    escaped = escaped.replace('=', '\\=')
    escaped = escaped.replace(',', '\\,')
    escaped = escaped.replace(';', '\\;')
    escaped = escaped.replace('|', '\\|')
    escaped = escaped.replace('(', '\\(')
    escaped = escaped.replace(')', '\\)')
    escaped = escaped.replace('{', '\\{')
    escaped = escaped.replace('}', '\\}')
    return escaped


def _build_drawtext_line(text, y_position, group_start_time, group_end_time, font_param, textfile_path=None):
    """Build a drawtext filter line for subtitles.
    
    Args:
        text: Text to display
        y_position: Y position expression
        group_start_time: Start time (unused, kept for compatibility)
        group_end_time: End time (unused, kept for compatibility)
        font_param: Font parameter string
        textfile_path: Optional path to textfile (more reliable for special chars)
    
    Note: Since we extract segments with -ss and -t, we don't need enable parameter.
    """
    if textfile_path and os.path.exists(textfile_path):
        abs_path = os.path.abspath(textfile_path)
        escaped_path = abs_path.replace("'", "'\\''")
        drawtext = f"drawtext=textfile='{escaped_path}'"
    else:
        escaped_text = _escape_text_for_ffmpeg(text)
        drawtext = f"drawtext=text='{escaped_text}'"
    
    drawtext += (
        f":fontsize={SUBTITLE_FONT_SIZE}"
        f":fontcolor={SUBTITLE_COLOR}"
        f":borderw={SUBTITLE_BORDER_WIDTH}"
        f":bordercolor={SUBTITLE_BORDER_COLOR}"
        f":x=(w-text_w)/2"
        f":y={y_position}"
    )
    
    if SUBTITLE_BACKGROUND_ENABLED:
        drawtext += f":box=1:boxcolor={SUBTITLE_BACKGROUND_COLOR}:boxborderw={SUBTITLE_BACKGROUND_VERTICAL_PADDING}"
    
    if font_param:
        drawtext += f":{font_param}"
    
    return drawtext


def _check_video_has_audio(video_path):
    """Check if video has audio stream."""
    probe_cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'stream=codec_type',
        '-of', 'default=noprint_wrappers=1:nokey=1', video_path
    ]
    success, output = _run_subprocess(probe_cmd, timeout=10, error_context='Check audio stream')
    return success and output.strip() == 'audio'


def _create_textfile_for_subtitle_line(text, textfile_path):
    """Create textfile for subtitle line text."""
    try:
        with open(textfile_path, 'w', encoding='utf-8') as f:
            f.write(text)
        return textfile_path
    except Exception as e:
        log_error(f'Failed to create textfile: {e}', step='shorts')
        return None


def _split_words_into_lines(group_words):
    """Split word group into two lines."""
    line1_words = group_words[:SUBTITLE_WORDS_PER_LINE]
    line2_words = group_words[SUBTITLE_WORDS_PER_LINE:]
    line1_text = ' '.join([w[0] for w in line1_words])
    line2_text = ' '.join([w[0] for w in line2_words]) if line2_words else ''
    return line1_text, line2_text


def _build_ffmpeg_command_for_subtitle_segment(input_path, segment_start, segment_duration, drawtext_line1, drawtext_line2, has_audio, segment_path):
    """Build FFmpeg command for creating subtitle segment."""
    if drawtext_line2:
        filter_complex = f"[0:v]{drawtext_line1}[v1];[v1]{drawtext_line2}[v]"
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-ss', str(segment_start),
            '-t', str(segment_duration),
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
        ]
    else:
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-ss', str(segment_start),
            '-t', str(segment_duration),
            '-vf', drawtext_line1,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
        ]
    
    if has_audio:
        cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
    else:
        cmd.append('-an')
    
    cmd.append(segment_path)
    return cmd


def _create_blank_segment(input_path, segment_start, segment_duration, has_audio, segment_path):
    """Create blank video segment without subtitles as fallback."""
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-ss', str(segment_start),
        '-t', str(segment_duration),
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
    ]
    if has_audio:
        cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
    else:
        cmd.append('-an')
    cmd.append(segment_path)
    
    success, _ = _run_subprocess(cmd, timeout=120, error_context='Blank segment')
    return success


def _create_subtitle_segment_for_group(input_path, group_idx, group_words, video_duration, font_param, line_spacing, temp_dir, has_audio):
    """Create subtitle segment for a word group."""
    line1_text, line2_text = _split_words_into_lines(group_words)
    
    segment_start = group_words[0][1]
    segment_end = min(group_words[-1][2], video_duration)
    segment_duration = segment_end - segment_start
    
    if segment_duration <= 0:
        return None
    
    line1_y = f"({SUBTITLE_POSITION_Y})-{SUBTITLE_FONT_SIZE//2}"
    textfile_line1 = os.path.join(temp_dir, f'text_line1_{group_idx:04d}.txt')
    textfile_line1 = _create_textfile_for_subtitle_line(line1_text, textfile_line1)
    drawtext_line1 = _build_drawtext_line(line1_text, line1_y, 0.0, segment_duration, font_param, textfile_line1)
    
    drawtext_line2 = None
    if line2_text:
        line2_y = f"({SUBTITLE_POSITION_Y})+{line_spacing//2}"
        textfile_line2 = os.path.join(temp_dir, f'text_line2_{group_idx:04d}.txt')
        textfile_line2 = _create_textfile_for_subtitle_line(line2_text, textfile_line2)
        drawtext_line2 = _build_drawtext_line(line2_text, line2_y, 0.0, segment_duration, font_param, textfile_line2)
    
    segment_path = os.path.join(temp_dir, f'segment_{group_idx:04d}.mp4')
    cmd = _build_ffmpeg_command_for_subtitle_segment(input_path, segment_start, segment_duration, drawtext_line1, drawtext_line2, has_audio, segment_path)
    
    success, error_output = _run_subprocess(cmd, timeout=120, error_context=f'Subtitle segment {group_idx}')
    if success:
        seg_duration = _validate_video_duration(segment_path, min_duration=0.1)
        if seg_duration:
            return segment_path
        _cleanup_files([segment_path])
    else:
        error_lines = error_output.split('\n') if error_output else []
        error_msg = next((line for line in error_lines if 'Error' in line or 'error' in line or 'Invalid' in line or 'reinitializing' in line or 'evaluating' in line), None)
        if not error_msg and error_lines:
            error_msg = '\n'.join(error_lines[-5:])
        if not error_msg:
            error_msg = error_output[:500] if error_output else 'Unknown error'
        
        filter_used = drawtext_line2 if drawtext_line2 else drawtext_line1
        log_error(f'Failed to create subtitle segment {group_idx}: {error_msg}', step='shorts')
        log_error(f'Filter used (first 200 chars): {str(filter_used)[:200]}', step='shorts')
        log_error(f'Text content - line1: {line1_text[:50]}, line2: {line2_text[:50] if line2_text else "none"}', step='shorts')
        
        log(f'Creating blank segment {group_idx} to maintain continuity', step='shorts')
        if _create_blank_segment(input_path, segment_start, segment_duration, has_audio, segment_path):
            seg_duration = _validate_video_duration(segment_path, min_duration=0.1)
            if seg_duration:
                log(f'Created blank segment {group_idx} to fill gap', step='shorts')
                return segment_path
        _cleanup_files([segment_path])
    
    return None


def _add_simple_word_subtitles(input_path, output_path, word_timings, font_option):
    """Word-by-word subtitle implementation using segment-based approach."""
    try:
        if not word_timings:
            import shutil
            shutil.copy2(input_path, output_path)
            return True
        
        font_param = f':{font_option}' if font_option else ''
        video_duration = get_video_duration_from_ffprobe(input_path)
        if not video_duration:
            log_error('Could not get video duration for subtitle segments', step='shorts')
            return False
        
        temp_dir = os.path.dirname(output_path)
        os.makedirs(temp_dir, exist_ok=True)
        
        has_audio = _check_video_has_audio(input_path)
        line_spacing = SUBTITLE_FONT_SIZE
        if SUBTITLE_BACKGROUND_ENABLED:
            line_spacing += (2 * SUBTITLE_BACKGROUND_VERTICAL_PADDING) + 10
        
        segment_files = []
        try:
            group_idx = 0
            for group_start in range(0, len(word_timings), SUBTITLE_WORDS_PER_GROUP):
                group_end = min(group_start + SUBTITLE_WORDS_PER_GROUP, len(word_timings))
                group_words = word_timings[group_start:group_end]
                
                if not group_words:
                    continue
                
                segment_path = _create_subtitle_segment_for_group(input_path, group_idx, group_words, video_duration, font_param, line_spacing, temp_dir, has_audio)
                if segment_path:
                    segment_files.append(segment_path)
                    group_idx += 1
            
            if not segment_files:
                log_error('No subtitle segments created', step='shorts')
                return False
            
            concat_file = os.path.join(temp_dir, 'concat_list.txt')
            if not _create_concat_list(concat_file, segment_files):
                return False
            
            success = _run_ffmpeg_concat(concat_file, output_path, timeout=300)
            if success:
                log(f'Successfully created subtitles using segment-based method ({len(segment_files)} segments)', step='shorts')
                return True
            return False
                
        finally:
            _cleanup_files(segment_files)
            concat_file = os.path.join(temp_dir, 'concat_list.txt') if 'temp_dir' in locals() else None
            _cleanup_files([concat_file] if concat_file else [])
            text_files = glob.glob(os.path.join(temp_dir, 'text_line*.txt'))
            _cleanup_files(text_files)
        
    except Exception as e:
        log_error(f'Error in segment-based subtitle: {e}', step='shorts')
        return False


def add_subtitles_to_video(input_path, output_path, word_timings):
    """Add word-by-word subtitles to a video using segment-based approach."""
    font_option = _get_font_option()
    return _add_simple_word_subtitles(input_path, output_path, word_timings, font_option)



def map_split_to_images(start_time, end_time, image_count):
    """Map a time segment to image indices (1-based).
    
    Args:
        start_time: Start time in seconds
        end_time: End time in seconds
        image_count: Total number of images
        
    Returns:
        List of image indices (1-based) that belong to this segment
    """
    image_indices = []
    
    start_image_idx = get_image_index_for_time(start_time) + 1
    end_image_idx = get_image_index_for_time(end_time - 0.1) + 1
    
    start_image_idx = max(1, min(start_image_idx, image_count))
    end_image_idx = max(1, min(end_image_idx, image_count))
    
    for idx in range(start_image_idx, end_image_idx + 1):
        image_indices.append(idx)
    
    return image_indices if image_indices else [1]


def get_subject_centers_for_images(image_paths, source_width):
    """Get main subject center positions for each image.
    
    Args:
        image_paths: List of image file paths
        source_width: Original image width
        
    Returns:
        Dict mapping image index (0-based) to normalized center x coordinate, or None
    """
    model = None
    try:
        model = _load_person_detection_model()
        if model is None:
            return None
        
        subject_centers = {}
        
        for idx, image_path in enumerate(image_paths):
            if not os.path.exists(image_path):
                log_error(f'Image not found: {image_path}', step='shorts')
                subject_centers[idx] = None
                continue
            
            frame = cv2.imread(image_path)
            if frame is None:
                log_error(f'Failed to load image: {image_path}', step='shorts')
                subject_centers[idx] = None
                continue
            
            center_x = detect_main_subject_center(frame, model)
            if center_x is not None:
                normalized_center = center_x / source_width
                subject_centers[idx] = normalized_center
                log(f'Detected main subject at image {idx+1}: center_x={normalized_center:.3f}', step='shorts')
            else:
                subject_centers[idx] = None
                log(f'No person detected in image {idx+1}, will use default center', step='shorts')
            
            del frame
        
        return subject_centers if subject_centers else None
        
    except Exception as e:
        log_error(f'Error getting subject centers from images: {e}', step='shorts')
        return None
    finally:
        _cleanup_model(model)


def _apply_crop_with_blur_to_image(input_path, output_path, crop_filter, crop_width, crop_height, scaled_height, pad_top, duration, fps=24):
    """Apply crop filter with blur options to an image, creating a video."""
    try:
        filter_attempts = _build_crop_filters(crop_filter, scaled_height, pad_top)
        use_expression = 't' in crop_filter
        
        num_frames = int(duration * fps)
        
        for attempt_name, filter_complex in filter_attempts:
            if use_expression:
                full_filter = f"loop=loop={num_frames}:size=1:start=0,setpts=PTS-STARTPTS,{filter_complex}"
                cmd = ['ffmpeg', '-y', '-loop', '1', '-i', input_path, '-filter_complex', full_filter]
            else:
                full_filter = f"loop=loop={num_frames}:size=1:start=0,setpts=PTS-STARTPTS,{filter_complex}"
                cmd = ['ffmpeg', '-y', '-loop', '1', '-i', input_path, '-vf', full_filter]
            
            cmd.extend([
                '-t', str(duration),
                '-r', str(fps),
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                output_path
            ])
            
            success, error = _run_subprocess(cmd, timeout=120, error_context=f'Crop with blur to image (attempt: {attempt_name})')
            if success:
                return True
            else:
                if attempt_name == filter_attempts[0][0]:
                    error_msg = _extract_ffmpeg_error_message(error)
                    log_error(f'Failed to apply crop with blur to image (attempt: {attempt_name}): {error_msg}', step='shorts')
        
        return False
        
    except Exception as e:
        log_error(f'Error cropping image: {e}', step='shorts')
        return False


def _calculate_image_segment_duration(idx, num_images, total_duration, image_duration):
    """Calculate duration for a specific image segment."""
    if idx == num_images - 1:
        return total_duration - (image_duration * idx)
    return image_duration


def _determine_crop_x_for_image(idx, subject_centers, source_width, crop_width, default_crop_x):
    """Determine crop_x position for an image based on subject center."""
    if subject_centers and idx in subject_centers and subject_centers[idx] is not None:
        subject_pixel_x = subject_centers[idx] * source_width
        crop_x_value = int(subject_pixel_x - crop_width / 2)
        return max(0, min(crop_x_value, source_width - crop_width))
    return default_crop_x


def _create_image_segment_with_transition(img_path, idx, previous_crop_x, crop_x_value, segment_duration, crop_width, crop_height, scaled_height, pad_top, temp_dir, fps):
    """Create image segment with transition animation."""
    transition_duration = _calculate_transition_duration(crop_x_value, previous_crop_x, crop_width, segment_duration)
    hold_duration = segment_duration - transition_duration
    
    transition_part = os.path.join(temp_dir, f'transition_{idx:03d}.{VIDEO_EXTENSION}')
    hold_part = os.path.join(temp_dir, f'hold_{idx:03d}.{VIDEO_EXTENSION}')
    
    crop_x_expr = f"{previous_crop_x}+({crop_x_value}-{previous_crop_x})*(t/{transition_duration})"
    crop_filter = f"crop={crop_width}:{crop_height}:{crop_x_expr}:0"
    
    if not _apply_crop_with_blur_to_image(img_path, transition_part, crop_filter, crop_width, crop_height, scaled_height, pad_top, transition_duration, fps):
        log_error(f'Failed to create transition segment {idx}', step='shorts')
        return None
    
    crop_filter = f"crop={crop_width}:{crop_height}:{crop_x_value}:0"
    if not _apply_crop_with_blur_to_image(img_path, hold_part, crop_filter, crop_width, crop_height, scaled_height, pad_top, hold_duration, fps):
        log_error(f'Failed to create hold segment {idx}', step='shorts')
        _cleanup_files([transition_part])
        return None
    
    segment_output = os.path.join(temp_dir, f'segment_{idx:03d}.{VIDEO_EXTENSION}')
    concat_list = os.path.join(temp_dir, f'concat_{idx:03d}.txt')
    if not _create_concat_list(concat_list, [transition_part, hold_part]):
        _cleanup_files([transition_part, hold_part])
        return None
    
    success = _run_ffmpeg_concat(concat_list, segment_output, timeout=120)
    _cleanup_files([transition_part, hold_part, concat_list])
    
    if not success:
        log_error(f'Failed to concatenate transition and hold for segment {idx}', step='shorts')
        return None
    
    return segment_output


def _create_image_segment_simple(img_path, idx, crop_x_value, segment_duration, crop_width, crop_height, scaled_height, pad_top, temp_dir, fps):
    """Create image segment without transition (simple case)."""
    segment_output = os.path.join(temp_dir, f'segment_{idx:03d}.{VIDEO_EXTENSION}')
    crop_filter = f"crop={crop_width}:{crop_height}:{crop_x_value}:0"
    
    if not _apply_crop_with_blur_to_image(img_path, segment_output, crop_filter, crop_width, crop_height, scaled_height, pad_top, segment_duration, fps):
        log_error(f'Failed to create segment {idx}', step='shorts')
        return None
    
    return segment_output


def _create_segment_for_image(img_path, idx, previous_crop_x, crop_x_value, segment_duration, crop_width, crop_height, scaled_height, pad_top, temp_dir, fps):
    """Create video segment for a single image."""
    if previous_crop_x is not None and previous_crop_x != crop_x_value and segment_duration > 1.0:
        return _create_image_segment_with_transition(img_path, idx, previous_crop_x, crop_x_value, segment_duration, crop_width, crop_height, scaled_height, pad_top, temp_dir, fps)
    else:
        return _create_image_segment_simple(img_path, idx, crop_x_value, segment_duration, crop_width, crop_height, scaled_height, pad_top, temp_dir, fps)


def _create_animated_video_from_images_ffmpeg(image_paths, output_path, subject_centers, source_width, source_height, duration, fps=24):
    """Create animated video from images using ffmpeg with cropping and blur.
    
    Args:
        image_paths: List of image file paths
        output_path: Output video path
        subject_centers: Dict mapping image index (0-based) to normalized center x
        source_width: Original image width
        source_height: Original image height
        duration: Video duration in seconds
        fps: Frames per second
        
    Returns:
        True if successful, False otherwise
    """
    try:
        crop_width, crop_height, scaled_height, pad_top, default_crop_x = _calculate_crop_dimensions(source_width, source_height)
        
        num_images = len(image_paths)
        if num_images == 0:
            log_error('No images provided', step='shorts')
            return False
        
        image_duration = duration / num_images if num_images > 0 else duration
        
        temp_dir = os.path.dirname(output_path)
        os.makedirs(temp_dir, exist_ok=True)
        segment_files = []
        previous_crop_x = None
        
        for idx, img_path in enumerate(image_paths):
            crop_x_value = _determine_crop_x_for_image(idx, subject_centers, source_width, crop_width, default_crop_x)
            segment_duration = _calculate_image_segment_duration(idx, num_images, duration, image_duration)
            
            segment_output = _create_segment_for_image(img_path, idx, previous_crop_x, crop_x_value, segment_duration, crop_width, crop_height, scaled_height, pad_top, temp_dir, fps)
            
            if segment_output:
                segment_files.append(segment_output)
                previous_crop_x = crop_x_value
        
        if not segment_files:
            log_error('No segments created', step='shorts')
            return False
        
        concat_list_file = os.path.join(temp_dir, 'concat_all.txt')
        if not _create_concat_list(concat_list_file, segment_files):
            _cleanup_files(segment_files)
            return False
        
        success = _run_ffmpeg_concat(concat_list_file, output_path, timeout=300)
        
        _cleanup_files(segment_files + [concat_list_file])
        
        if not success:
            return False
        
        return True
        
    except Exception as e:
        log_error(f'Error creating animated video from images: {e}', step='shorts')
        return False


def create_animated_video_from_image_list(image_paths, output_path, subject_centers, source_width, source_height, duration):
    """Create a single animated video from a list of images with cropping and effects.
    
    Args:
        image_paths: List of image file paths
        output_path: Output video path
        subject_centers: Dict mapping image index (0-based) to normalized center x, or None
        source_width: Original image width
        source_height: Original image height
        duration: Video duration in seconds
        
    Returns:
        True if successful, False otherwise
    """
    if not image_paths:
        log_error('No images provided for animated video', step='shorts')
        return False
    
    log(f'Creating animated video from {len(image_paths)} images (duration: {duration:.2f}s)', step='shorts')
    
    return _create_animated_video_from_images_ffmpeg(
        image_paths, output_path, subject_centers, source_width, source_height, duration
    )


def _find_all_images_in_folder(video_folder):
    """Find all images in the video folder."""
    images_dir = os.path.join(video_folder, 'images')
    if not os.path.exists(images_dir):
        log_error(f'Images directory not found: {images_dir}', step='shorts')
        return None, None
    
    from constants import IMAGE_EXTENSION
    image_pattern = os.path.join(images_dir, f'image_*.{IMAGE_EXTENSION}')
    all_images = sorted(glob.glob(image_pattern))
    
    if not all_images:
        log_error(f'No images found in {images_dir}', step='shorts')
        return None, None
    
    return all_images, images_dir


def _get_image_dimensions_from_first_image(first_image_path):
    """Get source dimensions from first image."""
    first_img = cv2.imread(first_image_path)
    if first_img is None:
        log_error(f'Failed to load first image: {first_image_path}', step='shorts')
        return None, None
    
    source_height, source_width = first_img.shape[:2]
    del first_img
    return source_width, source_height


def _get_image_paths_for_split(all_images, image_indices):
    """Get image file paths for a split based on image indices."""
    segment_image_paths = []
    for img_idx in image_indices:
        if img_idx <= len(all_images):
            segment_image_paths.append(all_images[img_idx - 1])
    return segment_image_paths


def _create_animated_video_for_split(idx, start_time, end_time, all_images, image_count, source_width, source_height, visuals_shorts_dir):
    """Create animated video for a single split."""
    log(f'Creating animated video {idx}: {start_time:.2f}s - {end_time:.2f}s', step='shorts')
    
    image_indices = map_split_to_images(start_time, end_time, image_count)
    log(f'Split {idx} maps to images: {image_indices}', step='shorts')
    
    segment_image_paths = _get_image_paths_for_split(all_images, image_indices)
    if not segment_image_paths:
        log_error(f'No images found for split {idx}', step='shorts')
        return None
    
    subject_centers = get_subject_centers_for_images(segment_image_paths, source_width)
    duration = end_time - start_time
    animated_path = os.path.join(visuals_shorts_dir, f'animated_{idx:02d}.{VIDEO_EXTENSION}')
    
    if not create_animated_video_from_image_list(
        segment_image_paths, animated_path, subject_centers, 
        source_width, source_height, duration
    ):
        log_error(f'Failed to create animated video {idx}', step='shorts')
        return None
    
    log_success(f'Created animated video {idx}: animated_{idx:02d}.{VIDEO_EXTENSION}', step='shorts')
    return animated_path


def create_animated_videos_from_images(video_folder, splits):
    """Create animated videos from images for each split segment.
    
    Args:
        video_folder: Path to video folder
        splits: List of (start_time, end_time) tuples
        
    Returns:
        List of created animated video paths
    """
    try:
        all_images, images_dir = _find_all_images_in_folder(video_folder)
        if not all_images:
            return []
        
        image_count = len(all_images)
        log(f'Found {image_count} images in {images_dir}', step='shorts')
        
        source_width, source_height = _get_image_dimensions_from_first_image(all_images[0])
        if not source_width or not source_height:
            return []
        
        visuals_shorts_dir = os.path.join(video_folder, 'visuals', 'shorts')
        os.makedirs(visuals_shorts_dir, exist_ok=True)
        
        animated_videos = []
        for idx, (start_time, end_time) in enumerate(splits, 1):
            animated_path = _create_animated_video_for_split(idx, start_time, end_time, all_images, image_count, source_width, source_height, visuals_shorts_dir)
            if animated_path:
                animated_videos.append(animated_path)
        
        log_success(f'Created {len(animated_videos)} animated video(s) in {visuals_shorts_dir}', step='shorts')
        return animated_videos
        
    except Exception as e:
        log_error(f'Error creating animated videos from images: {e}', step='shorts')
        return []



def _extract_audio_segment_from_audio(audio_file, start_time, segment_duration, temp_audio_path):
    """Extract audio segment from audio file and save to temp file."""
    cmd = [
        'ffmpeg', '-y',
        '-i', audio_file,
        '-ss', str(start_time),
        '-t', str(segment_duration),
        '-acodec', 'pcm_s16le',
        '-ar', '44100',
        '-ac', '1',
        temp_audio_path
    ]
    
    success, error = _run_subprocess(cmd, timeout=60, error_context='Audio segment extraction')
    if not success:
        error_msg = _extract_ffmpeg_error_message(error)
        log_error(f'Failed to extract audio segment: {error_msg}', step='shorts')
        return False
    return True


def _add_subtitles_to_animated_video(animated_video, animated_duration, word_timings, temp_with_subtitles_path):
    """Add subtitles to animated video and validate result."""
    if not word_timings:
        return None
    
    log(f'Got {len(word_timings)} word timings, adding subtitles', step='shorts')
    if not add_subtitles_to_video(animated_video, temp_with_subtitles_path, word_timings):
        log_error(f'Failed to add subtitles, using animated video without subtitles', step='shorts')
        return None
    
    subtitle_duration = _validate_video_duration(temp_with_subtitles_path)
    if subtitle_duration and abs(subtitle_duration - animated_duration) < 5.0:
        log(f'Successfully added subtitles (duration: {subtitle_duration:.2f}s)', step='shorts')
        return temp_with_subtitles_path
    else:
        subtitle_dur_str = f'{subtitle_duration:.2f}s' if subtitle_duration else 'None'
        log_error(f'Subtitle video duration mismatch (animated: {animated_duration:.2f}s, subtitle: {subtitle_dur_str}), using animated video without subtitles', step='shorts')
        return None


def _merge_video_with_audio_at_speed(video_path, audio_path, output_path, expected_duration):
    """Merge video and audio at 1.15x speed."""
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
        '-filter_complex', '[0:v]setpts=PTS/1.15[v];[1:a]atempo=1.15[a]',
        '-map', '[v]',
        '-map', '[a]',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-t', str(expected_duration / 1.15),
        output_path
    ]
    
    success, error = _run_subprocess(cmd, timeout=120, error_context='Merge video and audio')
    if not success:
        error_msg = _extract_ffmpeg_error_message(error)
        log_error(f'Failed to merge video and audio: {error_msg}', step='shorts')
        return False
    return True


def _process_single_short(video_folder, language, idx, start_time, end_time, animated_video, shorts_dir):
    """Process a single short video segment."""
    log(f'Processing {language} short {idx}: {start_time:.2f}s - {end_time:.2f}s', step='shorts')
    
    if not os.path.exists(animated_video):
        log_error(f'Animated video not found: {animated_video}', step='shorts')
        return None
    
    short_filename = f'short_{idx:02d}.{VIDEO_EXTENSION}'
    short_path = os.path.join(shorts_dir, short_filename)
    segment_duration = end_time - start_time
    
    temp_dir = os.path.join(shorts_dir, f'temp_short_{idx}')
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        narration_audio = os.path.join(video_folder, 'narration', language, f'narration_0.{AUDIO_EXTENSION}')
        if not os.path.exists(narration_audio):
            log_error(f'Narration audio file not found: {narration_audio}', step='shorts')
            return None
        
        temp_audio = os.path.join(temp_dir, f'temp_audio.{AUDIO_EXTENSION}')
        if not _extract_audio_segment_from_audio(narration_audio, start_time, segment_duration, temp_audio):
            return None
        
        animated_duration = _validate_video_duration(animated_video, min_duration=0.5)
        if not animated_duration:
            return None
        
        word_timings = get_word_timings_for_segment(video_folder, language, start_time, end_time)
        temp_with_subtitles = os.path.join(temp_dir, f'temp_subtitles.{VIDEO_EXTENSION}')
        video_to_merge = _add_subtitles_to_animated_video(animated_video, animated_duration, word_timings, temp_with_subtitles) or animated_video
        
        audio_duration = get_audio_duration(audio_path=temp_audio)
        if not audio_duration:
            log_error(f'Failed to get audio duration for {language} short {idx}', step='shorts')
            return None
        
        log(f'Merging: video={animated_duration:.2f}s, audio={audio_duration:.2f}s, expected={segment_duration:.2f}s', step='shorts')
        if not _merge_video_with_audio_at_speed(video_to_merge, temp_audio, short_path, segment_duration):
            return None
        
        if not _validate_video_duration(short_path, min_duration=0.5):
            _cleanup_files([short_path])
            return None
        
        log_success(f'Generated {language} short {idx}: {short_filename}', step='shorts')
        return short_path
    
    finally:
        _cleanup_directory(temp_dir)


def generate_shorts_for_language(video_folder, language, animated_videos):
    """Generate shorts for one language version using pre-created animated videos.
    
    Args:
        video_folder: Path to video folder
        language: Language code (pt, en, es)
        animated_videos: List of animated video paths (animated_01.mp4, animated_02.mp4, etc.)
        
    Returns:
        List of generated short video paths
    """
    try:
        final_video = os.path.join(video_folder, f'final_{language}.{VIDEO_EXTENSION}')
        if not os.path.exists(final_video):
            log(f'Final {language} video not found: {final_video}', step='shorts')
            return []
        
        splits = calculate_split_timestamps(video_folder, language)
        if not splits:
            log_error(f'No splits calculated for {language} video', step='shorts')
            return []
        
        if len(animated_videos) != len(splits):
            log_error(f'Mismatch: {len(animated_videos)} animated videos but {len(splits)} splits for {language}', step='shorts')
            return []
        
        shorts_dir = os.path.join(video_folder, 'shorts', language)
        os.makedirs(shorts_dir, exist_ok=True)
        
        generated_shorts = []
        for idx, (start_time, end_time) in enumerate(splits, 1):
            short_path = _process_single_short(video_folder, language, idx, start_time, end_time, animated_videos[idx - 1], shorts_dir)
            if short_path:
                generated_shorts.append(short_path)
        
        return generated_shorts
        
    except Exception as e:
        log_error(f'Error generating shorts for {language}: {e}', step='shorts')
        return []


def _find_splits_from_available_language(video_folder):
    """Find splits from first available language video."""
    for language in ['pt', 'en', 'es']:
        final_video = os.path.join(video_folder, f'final_{language}.{VIDEO_EXTENSION}')
        if os.path.exists(final_video):
            splits = calculate_split_timestamps(video_folder, language)
            if splits:
                log(f'Using splits from {language} video ({len(splits)} splits)', step='shorts')
                return splits
    return None


def _get_existing_animated_videos(visuals_shorts_dir, expected_count):
    """Get list of existing animated videos."""
    animated_videos = []
    if os.path.exists(visuals_shorts_dir):
        for idx in range(1, expected_count + 1):
            animated_path = os.path.join(visuals_shorts_dir, f'animated_{idx:02d}.{VIDEO_EXTENSION}')
            if os.path.exists(animated_path):
                animated_videos.append(animated_path)
    return animated_videos


def _ensure_animated_videos_exist(video_folder, splits):
    """Ensure animated videos exist, creating them if needed."""
    visuals_shorts_dir = os.path.join(video_folder, 'visuals', 'shorts')
    animated_videos = _get_existing_animated_videos(visuals_shorts_dir, len(splits))
    
    if len(animated_videos) != len(splits):
        log(f'Creating {len(splits)} animated video(s) from images...', step='shorts')
        animated_videos = create_animated_videos_from_images(video_folder, splits)
        
        if not animated_videos or len(animated_videos) != len(splits):
            log_error(f'Failed to create animated videos ({len(animated_videos)}/{len(splits)} created)', step='shorts')
            return None
    else:
        log(f'Using existing {len(animated_videos)} animated video(s)', step='shorts')
    
    return animated_videos


def generate_all_shorts(video_folder):
    """Generate shorts for all available language versions (pt, en, es).
    
    Creates animated videos from images once, then uses them for all languages.
    """
    try:
        if not os.path.exists(video_folder):
            raise Exception(f'Video folder not found: {video_folder}')
        
        log(f'Starting shorts generation for folder: {os.path.basename(video_folder)}', step='shorts')
        
        splits = _find_splits_from_available_language(video_folder)
        if not splits:
            log_error('No splits found for any language, cannot create animated videos', step='shorts')
            return {'pt': [], 'en': [], 'es': []}
        
        animated_videos = _ensure_animated_videos_exist(video_folder, splits)
        if not animated_videos:
            return {'pt': [], 'en': [], 'es': []}
        
        result = {'pt': [], 'en': [], 'es': []}
        for language in ['pt', 'en', 'es']:
            shorts = generate_shorts_for_language(video_folder, language, animated_videos)
            result[language] = shorts
        
        total_shorts = sum(len(shorts) for shorts in result.values())
        log_success(f'Generated {total_shorts} shorts total (pt: {len(result["pt"])}, en: {len(result["en"])}, es: {len(result["es"])})', step='shorts')
        
        return result
        
    except Exception as e:
        log_error(f'Error generating all shorts: {e}', step='shorts')
        raise
