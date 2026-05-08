import sys
import os
import argparse
import glob
import cv2
import re
import traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
sys.path.insert(0, SRC_DIR)

from constants import IMAGE_EXTENSION, VIDEO_EXTENSION, AUDIO_EXTENSION
from env import VIDEO_WIDTH, VIDEO_HEIGHT, USE_KEN_BURNS_EFFECT

DEFAULT_DURATION = 30.0
DEFAULT_FPS = 24
VIDEO_FILENAME = f'animated.{VIDEO_EXTENSION}'
AUDIO_FILENAME = f'narration_0.{AUDIO_EXTENSION}'
IMAGE_PATTERN = f'image_*.{IMAGE_EXTENSION}'

try:
    from video.generate import (
        save_final_video,
        calculate_video_params
    )
    from video.merge import find_audio_path_for_merge, merge_video_audio
    from audio.files import get_audio_duration
    from video.effects import (
        save_video_streaming_ken_burns,
        save_video_streaming_simple
    )
except ImportError as e:
    print(f'❌ Error importing modules: {e}')
    print(f'Running on root and activate virtual environment')
    sys.exit(1)

def _parse_arguments():
    parser = argparse.ArgumentParser(
        description='Merge video and audio for a failed generation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s como_era_a_vida_de_um_sol_818_20251103_003338
  %(prog)s /full/path/to/folder
        '''
    )
    parser.add_argument(
        'folder',
        help='Folder name (from output/videos/) or full path to the video folder'
    )
    return parser.parse_args()


def _resolve_output_folder(folder_path):
    if os.path.isabs(folder_path):
        return folder_path
    return os.path.join(PROJECT_ROOT, 'output', 'videos', folder_path)


def _validate_folder_exists(folder_path):
    if not os.path.exists(folder_path):
        print(f'❌ Error: Folder not found: {folder_path}')
        sys.exit(1)


def _get_file_paths(output_folder):
    visuals_dir = os.path.join(output_folder, 'visuals')
    video_path = os.path.join(visuals_dir, VIDEO_FILENAME)
    audio_path = os.path.join(output_folder, 'narration', 'pt', AUDIO_FILENAME)
    return video_path, audio_path


def _print_file_status(output_folder, video_path, audio_path):
    print(f'📁 Working with folder: {output_folder}')
    print(f'   Video file: {"✅" if os.path.exists(video_path) else "❌"} {video_path}')
    print(f'   Audio file: {"✅" if os.path.exists(audio_path) else "❌"} {audio_path}')


def _extract_image_number(filename):
    match = re.search(r'image_(\d+)', os.path.basename(filename))
    return int(match.group(1)) if match else 0


def _find_and_sort_images(output_folder):
    # Look for images in the images/ subfolder first, then fallback to root folder for backward compatibility
    images_dir = os.path.join(output_folder, 'images')
    if os.path.exists(images_dir):
        image_pattern = os.path.join(images_dir, IMAGE_PATTERN)
    else:
        # Fallback to root folder for old videos
        image_pattern = os.path.join(output_folder, IMAGE_PATTERN)
    
    image_files = glob.glob(image_pattern)
    
    if not image_files:
        print(f'\n❌ Error: No images found in folder and video file doesnt exist. Expected images named: image_01.{IMAGE_EXTENSION}, image_02.{IMAGE_EXTENSION}, etc.')
        print(f'   Searched in: {images_dir if os.path.exists(images_dir) else output_folder}')
        sys.exit(1)
    
    image_files.sort(key=_extract_image_number)
    return image_files

def _get_image_dimensions(image_files):
    width = VIDEO_WIDTH
    height = VIDEO_HEIGHT
    
    if image_files:
        first_img = cv2.imread(image_files[0])
        if first_img is not None:
            img_height, img_width = first_img.shape[:2]
            if img_height != height or img_width != width:
                print(f'   ⚠️  Image dimensions ({img_width}x{img_height}) don\'t match expected ({width}x{height})')
                width = img_width
                height = img_height
            del first_img
    
    return width, height


def _create_video_from_images(output_folder, audio_path):
    print(f'\n📹 Video file not found. Looking for images to create it...')
    
    image_files = _find_and_sort_images(output_folder)
    print(f'   Found {len(image_files)} images')
    
    # Ensure narration_0.wav exists (regenerate from segments if needed)
    try:
        find_audio_path_for_merge(output_folder, language='pt')
    except Exception as e:
        print(f'   ⚠️  Warning: Could not regenerate narration_0.wav: {e}')
        print('   Will try to continue with existing audio file...')
    
    try:
        duration = get_audio_duration(audio_path=audio_path)
        print(f'   Audio duration: {duration:.1f}s')
    except (FileNotFoundError, ValueError) as e:
        print(f'   ⚠️  Error getting audio duration: {e}')
        sys.exit(1)
    width, height = _get_image_dimensions(image_files)
    
    try:
        total_frames, _, frames_per_image = calculate_video_params(
            duration, DEFAULT_FPS, desired_image_count=len(image_files)
        )
        
        visuals_dir = os.path.join(output_folder, 'visuals')
        os.makedirs(visuals_dir, exist_ok=True)
        output_path = os.path.join(visuals_dir, VIDEO_FILENAME)
        print(f'\n🎬 Creating video from {len(image_files)} images...')
        print(f'   Duration: {duration:.1f}s, FPS: {DEFAULT_FPS}, Resolution: {width}x{height}')
        
        if USE_KEN_BURNS_EFFECT:
            save_video_streaming_ken_burns(
                image_files, output_path, frames_per_image, total_frames, DEFAULT_FPS, width, height
            )
        else:
            save_video_streaming_simple(
                image_files, output_path, frames_per_image, total_frames, DEFAULT_FPS, width, height
            )
    except Exception as e:
        print(f'\n❌ Error creating video from images: {e}')
        traceback.print_exc()
        sys.exit(1)


def _extract_theme_from_folder_name(folder_path):
    folder_name = os.path.basename(folder_path)
    return folder_name.split('_')[0] if '_' in folder_name else folder_name


def _merge_and_save_final_video(output_folder, audio_path):
    if not os.path.exists(audio_path):
        print(f'\n⚠️  Warning: Audio file not found: {audio_path}')
        print('   Will use silent audio as fallback...')
    
    try:
        print(f'\n🔊 Merging video and audio...')
        merge_video_audio(output_folder, language='pt')
        print('✅ Merge completed successfully!')
        
        print('💾 Saving final video...')
        theme = _extract_theme_from_folder_name(output_folder)
        final_path = save_final_video(output_folder, theme)
        print(f'\n✅ Final video saved: {final_path}')
    
    except Exception as e:
        print(f'\n❌ Error during merge: {e}')
        traceback.print_exc()
        sys.exit(1)


def main():
    args = _parse_arguments()
    output_folder = _resolve_output_folder(args.folder)
    _validate_folder_exists(output_folder)
    
    video_path, audio_path = _get_file_paths(output_folder)
    _print_file_status(output_folder, video_path, audio_path)
    
    if not os.path.exists(video_path):
        _create_video_from_images(output_folder, audio_path)
    
    _merge_and_save_final_video(output_folder, audio_path)


if __name__ == '__main__':
    main()
