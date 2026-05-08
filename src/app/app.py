from flask import Flask, render_template
import os
import sys

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from constants import (
    OUTPUT_DIR, OUTPUT_DIR_VIDEOS, OUTPUT_DIR_IMAGES,
    OUTPUT_DIR_AUDIOS, OUTPUT_DIR_TEMP, FLASK_HOST, FLASK_PORT
)
from app.videos import app as video_app
from app.video_edit import app as video_edit_app
from app.images import app as image_app
from app.audio import app as audio_app
from app.translate import app as translate_app
from app.system import app as system_app, check_ollama_on_startup

PARENT_DIR = os.path.dirname(SRC_DIR)
TEMPLATES_DIR = os.path.join(SRC_DIR, 'templates')
STATIC_DIR = os.path.join(SRC_DIR, 'templates', 'static')

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)

app.register_blueprint(video_app)
app.register_blueprint(video_edit_app)
app.register_blueprint(image_app)
app.register_blueprint(audio_app)
app.register_blueprint(translate_app)
app.register_blueprint(system_app)


@app.route('/')
def index():
    return render_template('index.html')


def create_output_directories():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR_VIDEOS, exist_ok=True)
    os.makedirs(OUTPUT_DIR_IMAGES, exist_ok=True)
    os.makedirs(OUTPUT_DIR_AUDIOS, exist_ok=True)
    os.makedirs(OUTPUT_DIR_TEMP, exist_ok=True)


if __name__ == '__main__':
    create_output_directories()
    
    print(f'🌐 Starting web interface at http://localhost:{FLASK_PORT}')
    
    check_ollama_on_startup()
    
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True, use_reloader=False)

