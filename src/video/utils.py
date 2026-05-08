"""Utility functions for video generation."""
from env import USE_VARIABLE_IMAGE_DURATION

IMAGE_DURATION = 8
SHORT_IMAGE_DURATION = 4
LONG_IMAGE_DURATION = 10
SHORT_DURATION_IMAGE_COUNT = 6
WORDS_PER_SECOND = 2.4
SILENCE_DURATION = 2

def calculate_duration_from_narration(narration_script):
    """Calculate estimated duration from narration script word count."""
    if not narration_script or not narration_script.strip():
        return 5  # Minimum 5 seconds
    
    # Remove silence markers for word count
    text_without_silence = narration_script.replace('(silence)', ' ')
    words = [w for w in text_without_silence.split() if w.strip()]
    word_count = len(words)
    
    # Calculate estimated duration from words
    estimated_duration = word_count / WORDS_PER_SECOND
    
    # Add duration for silence markers
    silence_count = narration_script.count('(silence)')
    estimated_duration += silence_count * SILENCE_DURATION
    
    # Minimum 5 seconds
    return max(5, estimated_duration)

def get_image_duration(image_index):
    if USE_VARIABLE_IMAGE_DURATION and image_index < SHORT_DURATION_IMAGE_COUNT:
        return SHORT_IMAGE_DURATION
    elif USE_VARIABLE_IMAGE_DURATION:
        return LONG_IMAGE_DURATION
    return IMAGE_DURATION


def calculate_image_count_for_duration(duration):
    if not USE_VARIABLE_IMAGE_DURATION:
        return max(1, int(duration / IMAGE_DURATION))
    
    short_phase_total = SHORT_DURATION_IMAGE_COUNT * SHORT_IMAGE_DURATION
    if duration <= short_phase_total:
        return max(1, int(duration / SHORT_IMAGE_DURATION))
    
    remaining_duration = duration - short_phase_total
    additional_images = int(remaining_duration / LONG_IMAGE_DURATION)
    return SHORT_DURATION_IMAGE_COUNT + max(1, additional_images)


def get_image_start_time(image_index):
    if not USE_VARIABLE_IMAGE_DURATION:
        return image_index * IMAGE_DURATION
    
    if image_index <= SHORT_DURATION_IMAGE_COUNT:
        return image_index * SHORT_IMAGE_DURATION
    
    short_phase_total = SHORT_DURATION_IMAGE_COUNT * SHORT_IMAGE_DURATION
    return short_phase_total + (image_index - SHORT_DURATION_IMAGE_COUNT) * LONG_IMAGE_DURATION


def get_image_index_for_time(time_seconds):
    if not USE_VARIABLE_IMAGE_DURATION:
        return int(time_seconds / IMAGE_DURATION)
    
    short_phase_total = SHORT_DURATION_IMAGE_COUNT * SHORT_IMAGE_DURATION
    if time_seconds < short_phase_total:
        return int(time_seconds / SHORT_IMAGE_DURATION)
    
    remaining_time = time_seconds - short_phase_total
    return SHORT_DURATION_IMAGE_COUNT + int(remaining_time / LONG_IMAGE_DURATION)


def calculate_frames_per_image_list(image_count, fps):
    return [int(get_image_duration(i) * fps) for i in range(image_count)]


def calculate_video_params(duration, fps, desired_image_count=None):
    if desired_image_count:
        image_count = max(1, int(desired_image_count))
    else:
        image_count = calculate_image_count_for_duration(duration)
    frames_per_image_list = calculate_frames_per_image_list(image_count, fps)
    total_frames = int(round(duration * fps))
    return total_frames, image_count, frames_per_image_list
