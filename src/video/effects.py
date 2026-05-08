import cv2
import os

from logger import log, log_success

ZOOM_FACTOR_MAX = 0.3
TRANSITION_FRAMES = 10
PROGRESS_UPDATE_INTERVAL = 10

FOURCC_MP4V = 'mp4v'
INTERPOLATION_LANCZOS4 = cv2.INTER_LANCZOS4
INTERPOLATION_LINEAR = cv2.INTER_LINEAR
BORDER_REPLICATE = cv2.BORDER_REPLICATE

def _calculate_smoothstep_easing(progress):
    return progress * progress * (3 - 2 * progress)

def _calculate_zoom_factor(frame_idx, total_frames):
    if total_frames <= 1:
        return 1.0
    progress = frame_idx / max(1, total_frames - 1)
    eased = _calculate_smoothstep_easing(progress)
    return 1.0 + (ZOOM_FACTOR_MAX * eased)

def _get_image_center(img):
    height, width = img.shape[:2]
    return width / 2.0, height / 2.0

def _create_zoom_transform_matrix(img, zoom_factor):
    center_x, center_y = _get_image_center(img)
    return cv2.getRotationMatrix2D((center_x, center_y), 0, zoom_factor)

def _apply_affine_zoom(img, transform_matrix):
    height, width = img.shape[:2]
    return cv2.warpAffine(
        img,
        transform_matrix,
        (width, height),
        flags=INTERPOLATION_LINEAR,
        borderMode=BORDER_REPLICATE
    )

def apply_ken_burns(img, frame_idx, total_frames):
    if total_frames <= 1:
        return img.copy()
    zoom_factor = _calculate_zoom_factor(frame_idx, total_frames)
    transform_matrix = _create_zoom_transform_matrix(img, zoom_factor)
    return _apply_affine_zoom(img, transform_matrix)

def _create_video_writer(output_path, fps, width, height):
    fourcc = cv2.VideoWriter_fourcc(*FOURCC_MP4V)
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not writer.isOpened():
        raise Exception(f'Failed to open video writer for {output_path}')
    return writer

def _load_and_resize_image(image_path, target_width, target_height):
    img = cv2.imread(image_path)
    if img is None:
        return None
    if img.shape[1] != target_width or img.shape[0] != target_height:
        img = cv2.resize(img, (target_width, target_height), interpolation=INTERPOLATION_LANCZOS4)
    return img

def _calculate_crossfade_alpha(frame_idx, transition_start, transition_frames):
    return (frame_idx - transition_start) / transition_frames

def _create_crossfade_frame(current_frame, next_frame, alpha):
    return cv2.addWeighted(current_frame, 1 - alpha, next_frame, alpha, 0)

def _calculate_frames_for_image(frames_per_image, total_frames, frames_written):
    return min(frames_per_image, total_frames - frames_written)

def _calculate_transition_start(frames_for_image):
    return max(0, frames_for_image - TRANSITION_FRAMES)

def _write_simple_frames(writer, img, frames_for_image, frames_written, total_frames):
    for _ in range(frames_for_image):
        writer.write(img)
        frames_written += 1
        if frames_written >= total_frames:
            break
    return frames_written

def _write_ken_burns_frames(writer, img, frames_for_image, frames_written, total_frames):
    for frame_idx in range(frames_for_image):
        frame = apply_ken_burns(img, frame_idx, frames_for_image)
        writer.write(frame)
        frames_written += 1
        if frames_written >= total_frames:
            break
    return frames_written

def _write_frames_with_transition(writer, img, next_img, frames_for_image, frames_written, total_frames, use_ken_burns):
    transition_start = _calculate_transition_start(frames_for_image)
    
    for frame_idx in range(frames_for_image):
        if frame_idx < transition_start:
            if use_ken_burns:
                frame = apply_ken_burns(img, frame_idx, frames_for_image)
            else:
                frame = img
            writer.write(frame)
        else:
            alpha = _calculate_crossfade_alpha(frame_idx, transition_start, TRANSITION_FRAMES)
            if use_ken_burns:
                current_frame = apply_ken_burns(img, frame_idx, frames_for_image)
                next_frame = apply_ken_burns(next_img, 0, frames_for_image)
                frame = _create_crossfade_frame(current_frame, next_frame, alpha)
            else:
                frame = _create_crossfade_frame(img, next_img, alpha)
            writer.write(frame)
        
        frames_written += 1
        if frames_written >= total_frames:
            break
    
    return frames_written

def _update_progress(current_index, total_images):
    from logger import log_step
    should_update = (current_index + 1) % PROGRESS_UPDATE_INTERVAL == 0
    is_last = current_index == total_images - 1
    if should_update or is_last:
        progress = (current_index + 1) / total_images * 100
        log_step('generate_video', f'Processing images...', 
                current=current_index+1, total=total_images)

def _get_frames_for_image(frames_per_image_list, index):
    if isinstance(frames_per_image_list, list):
        return frames_per_image_list[index] if index < len(frames_per_image_list) else frames_per_image_list[-1]
    return frames_per_image_list


def _process_images_for_video(
    image_paths,
    writer,
    frames_per_image_list,
    total_frames,
    width,
    height,
    use_ken_burns
):
    frames_written = 0
    
    for index, img_path in enumerate(image_paths):
        if frames_written >= total_frames:
            break
        
        img = _load_and_resize_image(img_path, width, height)
        if img is None:
            from logger import log_warning
            log_warning(f'Failed to load: {os.path.basename(img_path)}, skipping...', step='generate_video')
            continue
        
        is_last_image = index == len(image_paths) - 1
        next_img = None
        
        if not is_last_image and index + 1 < len(image_paths):
            next_img_path = image_paths[index + 1]
            next_img = _load_and_resize_image(next_img_path, width, height)
        
        frames_for_this_index = _get_frames_for_image(frames_per_image_list, index)
        if is_last_image:
            frames_for_this_image = total_frames - frames_written
        else:
            frames_for_this_image = min(frames_for_this_index, total_frames - frames_written)
        
        if is_last_image or next_img is None:
            if use_ken_burns:
                frames_written = _write_ken_burns_frames(
                    writer, img, frames_for_this_image, frames_written, total_frames
                )
            else:
                frames_written = _write_simple_frames(
                    writer, img, frames_for_this_image, frames_written, total_frames
                )
        else:
            frames_written = _write_frames_with_transition(
                writer, img, next_img, frames_for_this_image,
                frames_written, total_frames, use_ken_burns
            )
            del next_img
        
        del img
        _update_progress(index, len(image_paths))
    
    return frames_written

def save_video_streaming_ken_burns(image_paths, output_path, frames_per_image_list, total_frames, fps, width, height):
    if not image_paths:
        raise Exception('No images found to create video')
    
    log(f'Creating video from {len(image_paths)} images with Ken Burns...', step='generate_video')
    
    writer = _create_video_writer(output_path, fps, width, height)
    
    try:
        frames_written = _process_images_for_video(
            image_paths, writer, frames_per_image_list, total_frames, width, height, use_ken_burns=True
        )
    finally:
        writer.release()
    
    log_success(f'Video created: {output_path} ({frames_written} frames)', step='generate_video')


def save_video_streaming_simple(image_paths, output_path, frames_per_image_list, total_frames, fps, width, height):
    from logger import log, log_success
    if not image_paths:
        raise Exception('No images found to create video')
    
    log(f'Creating video from {len(image_paths)} images...', step='generate_video')
    
    writer = _create_video_writer(output_path, fps, width, height)
    
    try:
        frames_written = _process_images_for_video(
            image_paths, writer, frames_per_image_list, total_frames, width, height, use_ken_burns=False
        )
    finally:
        writer.release()
    
    log_success(f'Video created: {output_path} ({frames_written} frames)', step='generate_video')
