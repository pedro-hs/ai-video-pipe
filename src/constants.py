import os

IMAGE_EXTENSION = 'png'
AUDIO_EXTENSION = 'wav'
VIDEO_EXTENSION = 'mp4'

# PARENT_DIR should be the project root (vpipe directory)
# constants.py is in src/, so we need to go up 2 levels: src/ -> vpipe/
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = os.path.join(PARENT_DIR, 'output')
OUTPUT_DIR_VIDEOS = os.path.join(PARENT_DIR, 'output', 'videos')
OUTPUT_DIR_IMAGES = os.path.join(PARENT_DIR, 'output', 'images')
OUTPUT_DIR_AUDIOS = os.path.join(PARENT_DIR, 'output', 'audios')
OUTPUT_DIR_TEMP = os.path.join(PARENT_DIR, 'output', 'temp')
OLLAMA_URL = 'http://127.0.0.1:11434/api'

STATUS_FILE = os.path.join(OUTPUT_DIR_TEMP, 'generation_status.json')

VIDEO_FILENAME = f'final_pt.{VIDEO_EXTENSION}'

SPEAKER_VOICE_PATH = os.path.join(PARENT_DIR, 'src', 'audio', 'voices', 'sample_joaquim.wav')

FLASK_HOST = '0.0.0.0'
FLASK_PORT = 8080
