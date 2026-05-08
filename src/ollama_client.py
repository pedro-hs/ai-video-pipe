import requests
import subprocess
import os
import shutil
import time
from constants import OLLAMA_URL

OLLAMA_MODEL = 'llama3.1:8b'
OLLAMA_TIMEOUT = 180
OLLAMA_HOST = '127.0.0.1:11434'
OLLAMA_GPU_LAYERS = '32'
OLLAMA_FLASH_ATTENTION = '1'
OLLAMA_LOW_VRAM_THRESHOLD = '0'
CUDA_VISIBLE_DEVICES = '0'

OLLAMA_CUDA_V13_PATH = '/usr/local/lib/ollama/cuda_v13'
OLLAMA_CUDA_V12_PATH = '/usr/local/lib/ollama/cuda_v12'
OLLAMA_BASE_PATH = '/usr/local/lib/ollama'
SYSTEM_CUDA_PATH = '/usr/lib/x86_64-linux-gnu'

def _get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _find_ollama_binary():
    system_ollama = shutil.which('ollama')
    if system_ollama:
        return system_ollama
    
    project_root = _get_project_root()
    local_ollama = os.path.join(project_root, 'models', 'ollama', 'ollama')
    return local_ollama

def _get_ollama_models_path():
    project_root = _get_project_root()
    return os.path.join(project_root, 'models', 'ollama', 'models')

def _find_cuda_library_paths():
    cuda_paths = []
    
    if os.path.isdir(OLLAMA_CUDA_V13_PATH):
        cuda_paths.append(OLLAMA_CUDA_V13_PATH)
    elif os.path.isdir(OLLAMA_CUDA_V12_PATH):
        cuda_paths.append(OLLAMA_CUDA_V12_PATH)
    
    if os.path.isdir(OLLAMA_BASE_PATH):
        cuda_paths.append(OLLAMA_BASE_PATH)
    
    if os.path.isdir(SYSTEM_CUDA_PATH):
        cuda_paths.append(SYSTEM_CUDA_PATH)
    
    return cuda_paths

def _build_ld_library_path(cuda_paths, existing_ld_path):
    if not cuda_paths:
        return existing_ld_path
    
    new_paths = ':'.join(cuda_paths)
    if existing_ld_path:
        return f'{new_paths}:{existing_ld_path}'
    return new_paths

def _create_ollama_environment():
    env = os.environ.copy()
    env['OLLAMA_MODELS'] = _get_ollama_models_path()
    env['OLLAMA_HOST'] = OLLAMA_HOST
    env['OLLAMA_GPU_LAYERS'] = OLLAMA_GPU_LAYERS
    env['OLLAMA_FLASH_ATTENTION'] = OLLAMA_FLASH_ATTENTION
    env['OLLAMA_LOW_VRAM_THRESHOLD'] = OLLAMA_LOW_VRAM_THRESHOLD
    env['CUDA_VISIBLE_DEVICES'] = CUDA_VISIBLE_DEVICES
    
    cuda_paths = _find_cuda_library_paths()
    existing_ld_path = env.get('LD_LIBRARY_PATH', '')
    env['LD_LIBRARY_PATH'] = _build_ld_library_path(cuda_paths, existing_ld_path)
    
    return env

def _extract_response(response_data):
    result = response_data.get('response', '').strip()
    if not result:
        raise Exception('Error to call Ollama: Empty response')
    return result

def call_ollama(prompt, max_retries=3, retry_delay=2):
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f'{OLLAMA_URL}/generate',
                json={'model': OLLAMA_MODEL, 'prompt': prompt, 'stream': False},
                timeout=OLLAMA_TIMEOUT
            )
            response.raise_for_status()
            response_data = response.json()
            result = _extract_response(response_data)
            
            if result and 'I can help you with?' not in result:
                return result
            
            last_exception = 'Invalid or empty response from Ollama'
            
        except Exception as e:
            last_exception = str(e)
        
        if attempt < max_retries - 1:
            wait_time = retry_delay * (2 ** attempt)
            print(f'⚠️ Ollama error (attempt {attempt + 1}/{max_retries}): {last_exception}, retrying in {wait_time}s...')
            time.sleep(wait_time)
        else:
            break
    
    raise Exception(f'Error calling Ollama after {max_retries} attempts: {last_exception}')

def stop_ollama_temporarily():
    try:
        subprocess.run(['pkill', '-f', 'ollama'], capture_output=True, text=True)
    except Exception as e:
        print(f'⚠️ Could not stop Ollama: {e}')

def restart_ollama():
    try:
        ollama_path = _find_ollama_binary()
        env = _create_ollama_environment()
        subprocess.Popen([ollama_path, 'serve'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f'⚠️ Could not restart Ollama: {e}')
