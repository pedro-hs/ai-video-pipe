import os

def _get_bool_env(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ('true', '1', 'yes', 'on')

def _get_int_env(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default

def _get_env(key: str) -> str:
    return os.getenv(key)

ENABLE_FACE_BLUR = _get_bool_env('ENABLE_FACE_BLUR', default=True)
SAVE_ORIGINAL_IMAGE = _get_bool_env('SAVE_ORIGINAL_IMAGE', default=False)
USE_KEN_BURNS_EFFECT = _get_bool_env('USE_KEN_BURNS_EFFECT', default=True)
SAVE_ORIGINAL_AUDIO = _get_bool_env('SAVE_ORIGINAL_AUDIO', default=False)
ENABLE_SUBSCRIPTION_OVERLAY = _get_bool_env('ENABLE_SUBSCRIPTION_OVERLAY', default=True)
ENABLE_FILM_GRAIN = _get_bool_env('ENABLE_FILM_GRAIN', default=True)
USE_CHEYENNE_CHECKPOINT = _get_bool_env('USE_CHEYENNE_CHECKPOINT', default=False)
USE_TRADITIONAL_CHECKPOINT = _get_bool_env('USE_TRADITIONAL_CHECKPOINT', default=True)
USE_VARIABLE_IMAGE_DURATION = _get_bool_env('USE_VARIABLE_IMAGE_DURATION', default=True)

# Resolution (used for both video and image generation)
VIDEO_WIDTH = _get_int_env('VIDEO_WIDTH', default=1920)
VIDEO_HEIGHT = _get_int_env('VIDEO_HEIGHT', default=1088)

# TODO2: pq nao ta pegando no .env?
