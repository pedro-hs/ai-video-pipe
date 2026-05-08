import numpy as np
import sys

from pathlib import Path
from PIL import ImageFilter, Image
from ultralytics import YOLO
from torchvision.transforms.functional import to_pil_image
from huggingface_hub import hf_hub_download

sys.path.insert(0, str(Path(__file__).parent.parent / 'models'))

FACE_DETECTION_CONFIDENCE = 0.3
SIZE_THRESHOLD_RATIO = 0.04
CONFIDENCE_THRESHOLD = 0.5
MAX_SIZE_RATIO = 0.3
BLUR_RADIUS_RATIO = 0.05
BLUR_PADDING_RATIO = 0.05
MIN_BLUR_RADIUS = 2
MIN_PADDING = 4
BLUR_OPACITY = 0.7

def _get_yolo_model_path():
    model_path = Path(__file__).parent.parent / 'models' / 'yolo' / 'face_yolov8n.pt'
    if not model_path.exists():
        from logger import log
        log('Downloading YOLO face detection model...', step='face_blur')
        return hf_hub_download(
            'Bingsu/adetailer',
            'face_yolov8n.pt',
            local_dir=str(model_path.parent),
            local_dir_use_symlinks=False
        )
    return str(model_path)

def _load_face_detection_model():
    model_path = _get_yolo_model_path()
    return YOLO(model_path)

def _detect_faces(model, image):
    predictions = model(image, conf=FACE_DETECTION_CONFIDENCE)
    boxes = predictions[0].boxes.xyxy.cpu().numpy()
    confidences = predictions[0].boxes.conf.cpu().numpy()
    masks_data = predictions[0].masks
    # Delete predictions object to free GPU memory immediately
    del predictions
    return boxes, confidences, masks_data

def _extract_masks(masks_data, boxes, image_size):
    if masks_data is not None:
        return [
            to_pil_image(masks_data.data[i], mode='L').resize(image_size)
            for i in range(len(boxes))
        ]
    return None

def _calculate_face_size(bbox):
    x_min, y_min, x_max, y_max = bbox.astype(int)
    width = x_max - x_min
    height = y_max - y_min
    return min(width, height)

def _should_blur_face(face_size, confidence, image_size):
    size_threshold = image_size * SIZE_THRESHOLD_RATIO
    is_too_small = face_size < size_threshold
    is_low_confidence = confidence < CONFIDENCE_THRESHOLD
    return is_too_small or is_low_confidence

def _calculate_blur_region(bbox, face_size, image_width, image_height):
    padding = max(MIN_PADDING, int(face_size * BLUR_PADDING_RATIO))
    x_min, y_min, x_max, y_max = bbox.astype(int)
    x_min_blur = max(0, x_min - padding)
    y_min_blur = max(0, y_min - padding)
    x_max_blur = min(image_width, x_max + padding)
    y_max_blur = min(image_height, y_max + padding)
    return x_min_blur, y_min_blur, x_max_blur, y_max_blur

def _calculate_blur_radius(face_size):
    return max(MIN_BLUR_RADIUS, int(face_size * BLUR_RADIUS_RATIO))

def _prepare_mask_for_blending(mask_array):
    if len(mask_array.shape) == 2:
        return np.stack([mask_array] * 3, axis=-1)
    return mask_array

def _blend_blurred_region(blurred_array, original_array, mask_array):
    mask_3d = _prepare_mask_for_blending(mask_array)
    blended = (
        blurred_array * mask_3d * BLUR_OPACITY +
        original_array * (1 - mask_3d * BLUR_OPACITY)
    ).astype(np.uint8)
    return blended

def _apply_face_blur(image, bbox, mask, face_size):
    x_min, y_min, x_max, y_max = _calculate_blur_region(
        bbox, face_size, image.width, image.height
    )
    blur_radius = _calculate_blur_radius(face_size)
    
    face_region = image.crop((x_min, y_min, x_max, y_max))
    blurred_face = face_region.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    
    mask_region = mask.crop((x_min, y_min, x_max, y_max))
    mask_region = mask_region.resize(blurred_face.size)
    
    blurred_array = np.array(blurred_face)
    original_array = np.array(face_region)
    mask_array = np.array(mask_region).astype(np.float32) / 255.0
    
    blended_array = _blend_blurred_region(blurred_array, original_array, mask_array)
    blended_image = Image.fromarray(blended_array)
    image.paste(blended_image, (x_min, y_min))
    
    return image

def _process_faces(image, boxes, confidences, masks):
    image_size = min(image.width, image.height)
    blurred_count = 0
    skipped_count = 0
    rejected_count = 0
    
    for index, bbox in enumerate(boxes):
        face_size = _calculate_face_size(bbox)
        confidence = confidences[index]
        
        max_size = image_size * MAX_SIZE_RATIO
        if face_size > max_size:
            rejected_count += 1
            continue
        
        if not _should_blur_face(face_size, confidence, image_size):
            skipped_count += 1
            continue
        
        _apply_face_blur(image, bbox, masks[index], face_size)
        blurred_count += 1
    
    if blurred_count > 0 or skipped_count > 0 or rejected_count > 0:
        from logger import log_success
        log_success(f'Blurred {blurred_count} face(s), kept {skipped_count} unblurred, rejected {rejected_count} invalid detection(s)', step='face_blur')
    return image

def apply_face_blur(pipe, image, face_prompt=None, face_negative_prompt=None, output_dir=None):
    import torch
    import gc
    
    model = None
    try:
        model = _load_face_detection_model()
        boxes, confidences, masks_data = _detect_faces(model, image)
        
        if boxes.size == 0:
            # No faces found - cleanup before returning
            if model is not None:
                try:
                    # Try to move YOLO model to CPU to free GPU memory
                    if hasattr(model, 'model'):
                        model.model.to('cpu')
                    del model
                    torch.cuda.empty_cache()
                except:
                    if model is not None:
                        del model
            return image
        
        masks = _extract_masks(masks_data, boxes, image.size)
        if masks is None:
            return image
        
        result = _process_faces(image, boxes, confidences, masks)
        
        # Clean up intermediate data
        del boxes, confidences, masks_data, masks
        
        return result
    except Exception as e:
        from logger import log_warning
        log_warning(f'Face blurring failed: {e}', step='face_blur')
        return image
    finally:
        # Always cleanup YOLO model to free GPU memory
        try:
            # Safely get model variable using locals() to avoid "referenced before assignment" error
            cleanup_model = locals().get('model')
            if cleanup_model is not None:
                try:
                    # Move YOLO model back to CPU if it's on GPU
                    if hasattr(cleanup_model, 'model'):
                        try:
                            cleanup_model.model.to('cpu')
                        except:
                            pass
                    del cleanup_model
                except:
                    pass
                # Force GPU memory cleanup
                try:
                    torch.cuda.empty_cache()
                    gc.collect()
                except:
                    pass
        except:
            # Ignore any errors during cleanup - ensure we don't crash on cleanup
            pass
