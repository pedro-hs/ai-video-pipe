from flask import Blueprint, jsonify
import os
import json
import requests
import subprocess
from datetime import datetime
from constants import STATUS_FILE, OLLAMA_URL
from logger import log_warning, log_error
from status import create_idle_status

NVIDIA_SMI_QUERY = '--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu'
NVIDIA_SMI_FORMAT = '--format=csv,noheader,nounits'
NVIDIA_SMI_TIMEOUT = 2
GPU_QUERY_TIMEOUT = 5

app = Blueprint('system', __name__)

@app.route('/api/ollama/status', methods=['GET'])
def get_ollama_status():
    try:
        is_running = check_ollama_status()
        return jsonify({'success': True, 'running': is_running})
    except Exception:
        return jsonify({'success': True, 'running': False})


@app.route('/api/system/status', methods=['GET'])
def get_system_status():
    try:
        is_generating = is_generation_running()
        gpu_usage = get_gpu_usage()
        ollama_running = check_ollama_status()

        return jsonify({
            'success': True,
            'is_generating': is_generating,
            'gpu_usage': gpu_usage,
            'ollama_running': ollama_running
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generation/status', methods=['GET'])
def get_generation_status():
    try:
        status = load_status_file()

        if status is None:
            return jsonify({
                'success': True,
                'status': create_idle_status()
            })

        if status.get('is_active', False) and is_status_stale(status):
            clean_stale_status()
            status = create_idle_status()

        gpu_stats = get_gpu_stats()
        status['gpu_stats'] = gpu_stats

        return jsonify({'success': True, 'status': status})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generation/stop', methods=['POST'])
def stop_generation():
    try:
        stopped, errors = stop_processes()

        if stopped:
            message = format_stop_message(stopped, errors)
            return jsonify({'success': True, 'message': message, 'stopped': stopped})
        else:
            return jsonify({'success': False, 'error': 'No processes found to stop', 'errors': errors}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generation/clear-logs', methods=['POST'])
def clear_logs():
    """Clear logs from status file."""
    try:
        status = load_status_file()
        if status is None:
            status = create_idle_status()
        
        status['logs'] = []
        
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f, indent=2)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



def check_ollama_on_startup():
    try:
        response = requests.get(f'{OLLAMA_URL}/tags', timeout=5)
        if response.status_code != 200:
            log_warning(f'Ollama status: {response.status_code}', step='ollama_check')
    except requests.exceptions.ConnectionError:
        log_error(f'Cannot connect to Ollama at {OLLAMA_URL}', step='ollama_check')
    except Exception:
        pass


def check_ollama_status():
    try:
        response = requests.get(f'{OLLAMA_URL}/tags', timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def get_gpu_stats():
    try:
        result = subprocess.run(
            ['nvidia-smi', NVIDIA_SMI_QUERY, NVIDIA_SMI_FORMAT],
            capture_output=True,
            text=True,
            timeout=NVIDIA_SMI_TIMEOUT
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            return {
                'gpu_usage': int(parts[0].strip()),
                'memory_usage': int(parts[1].strip()),
                'memory_used_mb': int(parts[2].strip()),
                'memory_total_mb': int(parts[3].strip()),
                'temperature': int(parts[4].strip())
            }
    except Exception:
        pass
    return None


def get_gpu_usage():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=GPU_QUERY_TIMEOUT
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0


def is_generation_running():
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'video_generator.py|generate_audio.py'],
            capture_output=True,
            text=True
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def load_status_file():
    if not os.path.exists(STATUS_FILE):
        return None

    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def is_status_stale(status):
    try:
        last_update = datetime.fromisoformat(status.get('timestamp', '1970-01-01T00:00:00'))
        now = datetime.now()
        threshold_seconds = 120
        return (now - last_update).total_seconds() > threshold_seconds
    except Exception:
        return False


def clean_stale_status():
    if os.path.exists(STATUS_FILE):
        try:
            os.remove(STATUS_FILE)
        except Exception:
            pass


def kill_process(pattern, process_name):
    try:
        subprocess.run(['pkill', '-9', '-f', pattern], capture_output=True)
        return process_name, None
    except Exception as e:
        return None, f'{process_name}: {str(e)}'


def stop_processes():
    stopped = []
    errors = []

    video_name, video_error = kill_process('video/generate.py', 'Video generation')
    if video_name:
        stopped.append(video_name)
    if video_error:
        errors.append(video_error)

    audio_name, audio_error = kill_process('audio/generate.py', 'Audio generation')
    if audio_name:
        stopped.append(audio_name)
    if audio_error:
        errors.append(audio_error)

    try:
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
            stopped.append('Status cleared')
    except Exception as e:
        errors.append(f'Status: {str(e)}')

    return stopped, errors


def format_stop_message(stopped, errors):
    message = f'Stopped: {", ".join(stopped)}'
    if errors:
        message += f' | Warnings: {", ".join(errors)}'
    return message


