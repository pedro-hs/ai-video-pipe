"""Merge video and audio files using ffmpeg."""

import os
import subprocess
import glob
import tempfile

from logger import log, log_error
from constants import AUDIO_EXTENSION, PARENT_DIR, VIDEO_EXTENSION
from audio.files import get_audio_duration
from env import ENABLE_SUBSCRIPTION_OVERLAY, ENABLE_FILM_GRAIN


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
    return 60.0


def get_film_grain_path():
    """Get path to film grain video file.
    
    Film grain video is stored in src/video/subscriptions/ folder.
    """
    video_dir = os.path.dirname(os.path.abspath(__file__))
    film_grain_path = os.path.join(video_dir, 'subscriptions', f'film_grain.{VIDEO_EXTENSION}')
    
    if os.path.exists(film_grain_path):
        return film_grain_path
    
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


def find_audio_path_for_merge(output_folder, language='pt'):
    """Find audio path for merging in language folder, regenerate from segments if missing."""
    lang_folder = os.path.join(output_folder, 'narration', language)
    narration_path = os.path.join(lang_folder, f'narration_0.{AUDIO_EXTENSION}')
    if os.path.exists(narration_path):
        return narration_path

    # Try to regenerate from audio segments using existing functions
    narration_file = os.path.join(lang_folder, 'narration.txt')
    if not os.path.exists(narration_file):
        raise Exception(f'Narration file not found: {narration_file} and narration_0.{AUDIO_EXTENSION} is missing')
    
    try:
        from audio.generate import split_narration_by_phrases
        from app.video_edit import (
            collect_audio_segment_paths,
            recombine_audio_segments
        )
        
        # Read narration and split into phrases with silence positions
        with open(narration_file, 'r', encoding='utf-8') as f:
            narration_text = f.read()
        
        phrases, silence_positions, nosilence_positions = split_narration_by_phrases(narration_text)
        
        if not phrases:
            raise Exception(f'No phrases found in narration file: {narration_file}')
        
        # Collect audio segment paths
        audio_segment_paths = collect_audio_segment_paths(output_folder, len(phrases), language=language)
        
        # Check if at least some segments exist
        existing_segments = [p for p in audio_segment_paths if os.path.exists(p)]
        if not existing_segments:
            raise Exception(f'No audio segments found in {output_folder} for language {language}')
        
        # Recombine segments into narration_0.wav
        recombine_audio_segments(
            output_folder,
            audio_segment_paths,
            silence_positions,
            language=language,
            nosilence_positions=nosilence_positions
        )
        
        # Check if regeneration was successful
        if not os.path.exists(narration_path):
            raise Exception(f'Failed to regenerate narration_0.{AUDIO_EXTENSION} from audio segments')
        
        return narration_path
    except Exception as e:
        log_error(f'Failed to regenerate narration from segments: {e}', step='merge')
        raise


def calculate_merge_timeout(duration):
    """Calculate timeout for merge operation based on duration."""
    return max(60, min(600, int(duration * 2 + 60)))


def find_music_files(output_folder):
    """Find all music files in musics/ directory, sorted alphabetically."""
    musics_dir = os.path.join(output_folder, 'musics')
    if not os.path.exists(musics_dir):
        return []
    
    # Find common audio formats
    audio_extensions = ['*.mp3', '*.wav', '*.m4a', '*.aac', '*.ogg', '*.flac', '*.mp4']
    music_files = []
    for ext in audio_extensions:
        music_files.extend(glob.glob(os.path.join(musics_dir, ext)))
        music_files.extend(glob.glob(os.path.join(musics_dir, ext.upper())))
    
    # Sort alphabetically for sequential playback
    music_files.sort()
    return music_files


def combine_and_process_music(music_files, target_duration, output_folder):
    """Combine music files sequentially, loop if needed, and reduce volume to 20%.
    
    Args:
        music_files: List of music file paths
        target_duration: Target duration in seconds
        output_folder: Video folder path for temporary files
        
    Returns:
        str: Path to processed music file, or None if no music files
    """
    if not music_files:
        return None
    
    log(f'Processing {len(music_files)} music file(s) for {target_duration:.2f}s duration', step='music_processing')
    
    # Create temp directory for processing
    temp_dir = os.path.join(output_folder, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Step 1: Create concat file for sequential combination
        concat_file = os.path.join(temp_dir, 'music_concat.txt')
        with open(concat_file, 'w', encoding='utf-8') as f:
            for music_file in music_files:
                # Use absolute path and escape single quotes
                abs_path = os.path.abspath(music_file).replace("'", "'\\''")
                f.write(f"file '{abs_path}'\n")
        
        # Step 2: Concatenate all music files
        combined_music = os.path.join(temp_dir, 'combined_music.wav')
        concat_cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            combined_music
        ]
        
        result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            log_error(f'Music concatenation failed: {result.stderr[:500]}', step='music_processing')
            return None
        
        if not os.path.exists(combined_music):
            log_error('Combined music file not created', step='music_processing')
            return None
        
        # Step 3: Get combined music duration
        combined_duration = get_audio_duration(audio_path=combined_music)
        log(f'Combined music duration: {combined_duration:.2f}s', step='music_processing')
        
        # Step 4: Loop music if needed to match target duration
        looped_music = os.path.join(temp_dir, 'looped_music.wav')
        if combined_duration < target_duration:
            # Need to loop
            loop_cmd = [
                'ffmpeg', '-y',
                '-stream_loop', '-1',
                '-i', combined_music,
                '-t', str(target_duration),
                '-c', 'copy',
                looped_music
            ]
            result = subprocess.run(loop_cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                log_error(f'Music looping failed: {result.stderr[:500]}', step='music_processing')
                # Fallback: use combined music as-is
                looped_music = combined_music
        else:
            # Trim to target duration if longer
            if combined_duration > target_duration:
                trim_cmd = [
                    'ffmpeg', '-y',
                    '-i', combined_music,
                    '-t', str(target_duration),
                    '-c', 'copy',
                    looped_music
                ]
                result = subprocess.run(trim_cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    log_error(f'Music trimming failed: {result.stderr[:500]}', step='music_processing')
                    looped_music = combined_music
            else:
                looped_music = combined_music
        
        # Step 5: Reduce volume to 20%
        final_music = os.path.join(temp_dir, 'music_20percent.wav')
        volume_cmd = [
            'ffmpeg', '-y',
            '-i', looped_music,
            '-filter:a', 'volume=0.2',
            '-c:a', 'pcm_s16le',
            final_music
        ]
        
        result = subprocess.run(volume_cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            log_error(f'Music volume reduction failed: {result.stderr[:500]}', step='music_processing')
            return None
        
        if not os.path.exists(final_music):
            log_error('Final music file not created', step='music_processing')
            return None
        
        log(f'Music processing complete: {final_music}', step='music_processing')
        return final_music
        
    except subprocess.TimeoutExpired:
        log_error('Music processing timed out', step='music_processing')
        return None
    except Exception as e:
        log_error(f'Error processing music: {e}', step='music_processing')
        return None


def build_ffmpeg_merge_command(video_path, audio_path, output_path, music_path=None, film_grain_path=None, video_duration=None, audio_duration=None):
    """Build ffmpeg command for merging video and audio, optionally with background music and film grain overlay."""
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
    ]
    
    grain_input_idx = 2
    has_music = music_path is not None
    has_film_grain = film_grain_path is not None
    
    if has_music:
        cmd.extend(['-i', music_path])
        grain_input_idx = 3
    
    if has_film_grain:
        cmd.extend(['-stream_loop', '-1', '-i', film_grain_path])
    
    main_width, main_height = get_video_dimensions(video_path)
    
    if has_film_grain or has_music:
        filter_parts = []
        video_output_label = '0:v:0'
        
        if has_film_grain and main_width and main_height:
            filter_parts.append(f'[{grain_input_idx}:v]scale={main_width}:{main_height},format=gray,format=yuv420p[grain_yuv]')
            filter_parts.append(f'[0:v]format=yuv420p[main_yuv];[main_yuv][grain_yuv]blend=c0_mode=screen:c1_mode=normal:c2_mode=normal[v_with_grain]')
            video_output_label = '[v_with_grain]'
        elif has_film_grain:
            log('Film grain enabled but could not determine video dimensions, skipping grain overlay', step='merge')
        
        if has_music:
            filter_parts.append('[1:a]volume=1.0[nar];[2:a]volume=0.2[bgm];[nar][bgm]amix=inputs=2:duration=first[a]')
        
        if filter_parts:
            if has_music:
                cmd.extend([
                    '-filter_complex', ';'.join(filter_parts),
                    '-map', video_output_label,
                    '-map', '[a]',
                ])
            else:
                cmd.extend([
                    '-filter_complex', ';'.join(filter_parts),
                    '-map', video_output_label,
                    '-map', '1:a:0',
                ])
        else:
            cmd.extend([
                '-map', '0:v:0',
                '-map', '1:a:0',
            ])
    else:
        cmd.extend([
            '-map', '0:v:0',
            '-map', '1:a:0',
        ])
    
    cmd.extend([
        '-c:v', 'h264_nvenc',
        '-preset', 'p6',
        '-cq', '22',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-ar', '44100',
        '-movflags', '+faststart',
    ])
    
    if has_film_grain and audio_duration:
        cmd.extend(['-t', str(audio_duration)])
    else:
        cmd.append('-shortest')
    
    cmd.append(output_path)
    
    return cmd


def merge_video_audio(output_folder, language='pt'):
    """Merge video and audio files using ffmpeg.
    Video should already match audio duration (last image extended during generation).
    Without -shortest flag, full audio duration is preserved.
    If video is shorter, ffmpeg will freeze the last frame automatically.
    Automatically includes background music from musics/ folder if present.
    Automatically adds subscription overlay if ENABLE_SUBSCRIPTION_OVERLAY is enabled and subscription is detected.
    """
    try:
        video_path = os.path.join(output_folder, 'visuals', f'animated.{VIDEO_EXTENSION}')
        output_path = os.path.join(output_folder, f'video_with_audio.{VIDEO_EXTENSION}')

        audio_path = find_audio_path_for_merge(output_folder, language)
        try:
            audio_duration = get_audio_duration(audio_path=audio_path)
        except (FileNotFoundError, ValueError):
            raise Exception(f'Cannot get audio duration from {audio_path}')
        
        # Process music files if present
        music_files = find_music_files(output_folder)
        music_path = None
        if music_files:
            music_path = combine_and_process_music(music_files, audio_duration, output_folder)
            if music_path:
                log(f'Including background music in merge', step='merge')
        
        timeout_seconds = calculate_merge_timeout(audio_duration)
        
        film_grain_path = None
        if ENABLE_FILM_GRAIN:
            film_grain_path = get_film_grain_path()
            if film_grain_path:
                log(f'Including film grain overlay', step='merge')
            else:
                log('Film grain enabled but file not found, continuing without grain', step='merge')
        
        # Check if subscription overlay is enabled and should be applied
        if ENABLE_SUBSCRIPTION_OVERLAY:
            from video.subscription import (
                get_subscription_overlay_info,
                build_ffmpeg_merge_with_subscription_command,
                get_video_dimensions,
                get_video_duration_from_ffprobe as get_subscription_video_duration
            )
            
            # Check if subscription overlay is needed
            subscription_info = get_subscription_overlay_info(output_folder, language)
            
            if subscription_info:
                subscription_timestamp = subscription_info['timestamp']
                subscription_video_path = subscription_info['subscription_video_path']
                
                # Validate timestamp is within video duration
                if subscription_timestamp >= 0 and subscription_timestamp < audio_duration:
                    main_width, main_height = get_video_dimensions(video_path)
                    
                    if main_width and main_height:
                        # Calculate overlay duration, ensuring it doesn't extend beyond video
                        subscription_video_duration = get_subscription_video_duration(subscription_video_path)
                        
                        if subscription_video_duration is None:
                            log_error(f'Failed to get subscription video duration, using default 3.0s', step='merge')
                            subscription_video_duration = 3.0
                        
                        overlay_duration = subscription_video_duration
                        if subscription_timestamp + overlay_duration > audio_duration:
                            overlay_duration = max(0.1, audio_duration - subscription_timestamp)
                            log(f'Subscription video ({subscription_video_duration:.2f}s) would extend beyond main video, limiting to {overlay_duration:.2f}s', step='merge')
                        
                        log(f'Subscription video path: {subscription_video_path}', step='merge')
                        log(f'Subscription video exists: {os.path.exists(subscription_video_path)}', step='merge')
                        
                        temp_video_with_grain = video_path
                        if film_grain_path and main_width and main_height:
                            temp_video_path = os.path.join(output_folder, 'temp', 'video_with_grain_for_subscription.mp4')
                            os.makedirs(os.path.dirname(temp_video_path), exist_ok=True)
                            grain_input_idx = 2
                            if music_path:
                                grain_input_idx = 3
                            video_duration_for_grain = get_video_duration_from_ffprobe(video_path)
                            grain_cmd = [
                                'ffmpeg', '-y',
                                '-i', video_path,
                                '-stream_loop', '-1', '-i', film_grain_path,
                                '-filter_complex', f'[1:v]scale={main_width}:{main_height},format=gray,format=yuv420p[grain_yuv];[0:v]format=yuv420p[main_yuv];[main_yuv][grain_yuv]blend=c0_mode=screen:c1_mode=normal:c2_mode=normal[v]',
                                '-map', '[v]',
                                '-c:v', 'h264_nvenc',
                                '-preset', 'p6',
                                '-cq', '22',
                                '-pix_fmt', 'yuv420p',
                            ]
                            if video_duration_for_grain:
                                grain_cmd.extend(['-t', str(video_duration_for_grain)])
                            else:
                                grain_cmd.append('-shortest')
                            grain_cmd.append(temp_video_path)
                            grain_timeout = calculate_merge_timeout(video_duration_for_grain if video_duration_for_grain else audio_duration)
                            try:
                                grain_result = subprocess.run(grain_cmd, timeout=grain_timeout, capture_output=True, text=True)
                                if grain_result.returncode == 0 and os.path.exists(temp_video_path):
                                    temp_video_with_grain = temp_video_path
                                    log('Applied film grain before subscription overlay', step='merge')
                                else:
                                    log_error(f'Film grain processing failed: {grain_result.stderr[:500] if grain_result.stderr else "Unknown error"}', step='merge')
                                    log('Continuing without film grain overlay', step='merge')
                            except subprocess.TimeoutExpired:
                                log_error(f'Film grain processing timed out after {grain_timeout}s, continuing without grain overlay', step='merge')
                        
                        cmd = build_ffmpeg_merge_with_subscription_command(
                            temp_video_with_grain, audio_path, subscription_video_path,
                            subscription_timestamp, main_width, main_height,
                            output_path, overlay_duration, music_path
                        )
                        
                        # Execute subscription merge
                        filter_idx = cmd.index('-filter_complex')
                        log(f'Merging video + audio + subscription overlay in single pass (at {subscription_timestamp:.2f}s for {overlay_duration:.2f}s)', step='merge')
                        log(f'FFmpeg filter: {cmd[filter_idx + 1]}', step='merge')
                        
                        result = subprocess.run(cmd, timeout=timeout_seconds, capture_output=True, text=True)
                        if result.returncode == 0:
                            return
                        
                        log_error(f'Subscription overlay merge failed: {result.stderr[:500]}', step='merge')
                        log_error(f'FFmpeg command: {" ".join(cmd)}', step='merge')
                        log('Falling back to simple merge', step='merge')
        
        # Basic merge (no subscription overlay or subscription not detected)
        video_duration = get_video_duration_from_ffprobe(video_path)
        cmd = build_ffmpeg_merge_command(video_path, audio_path, output_path, music_path, film_grain_path, video_duration, audio_duration)

        result = subprocess.run(cmd, timeout=timeout_seconds, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f'Audio merge failed: {result.stderr}')
    except subprocess.TimeoutExpired:
        raise Exception(f'Audio merge timed out after {timeout_seconds}s')
    except Exception as e:
        log_error(f'Audio merge error: {e}', step='merge')
        raise

