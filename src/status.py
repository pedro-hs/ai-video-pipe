import json
import os
from datetime import datetime
from constants import STATUS_FILE

def update_status(stage, progress_percent=0, gpu_usage=0, message='', narration_script='', image_prompts=None):
    status = {
        'stage': stage,
        'progress_percent': progress_percent,
        'gpu_usage': gpu_usage,
        'message': message,
        'narration_script': narration_script,
        'image_prompts': image_prompts or [],
        'timestamp': datetime.now().isoformat(),
        'is_active': stage not in ['complete', 'error', 'idle']
    }
    
    # Preserve existing logs
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r') as f:
                existing_status = json.load(f)
                status['logs'] = existing_status.get('logs', [])
        except:
            status['logs'] = []
    else:
        status['logs'] = []
    
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        print(f'Warning: Could not write status file: {e}', flush=True)

def get_status():
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    
    return create_idle_status()

def create_idle_status():
    return {
        'stage': 'idle',
        'progress_percent': 0,
        'gpu_usage': 0,
        'message': 'No active generation',
        'is_active': False,
        'logs': []
    }

def clear_status():
    try:
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
    except:
        pass
