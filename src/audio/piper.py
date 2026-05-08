"""Piper TTS model operations."""

import os
import wave
import subprocess
import sys
import shutil

from constants import PARENT_DIR

# Hardcoded Portuguese Brazilian model
PIPER_MODEL_NAME = 'pt_BR-faber-medium'
DEFAULT_LANGUAGE = 'pt'

# English model
PIPER_EN_MODEL_NAME = 'en_GB-alba-medium'
DEFAULT_EN_LANGUAGE = 'en'

# Spanish model
PIPER_ES_MODEL_NAME = 'es_ES-sharvard-medium'
DEFAULT_ES_LANGUAGE = 'es'

# Model storage location
MODELS_DIR = os.path.join(PARENT_DIR, 'models', 'piper')

# VALORES DEFAULT
#  {
#      'length_scale': 1, # voice speed -> 1;default - 1.1;slower - 0.9:faster
#      'volume': 1.0,
#      'noise_scale': 0.667, # noise variation -> 0.667;default - 0.5;lower - 0.7;more
#      'noise_w_scale': 0.8,  # speaking variation -> 0.8;default - 0.7;lower - 0.9;more
#      'normalize_audio': True
#  }

ENGLISH_SYN_CONFIG = {
    'length_scale': 1,      # default
    'volume': 1.0,
    'noise_scale': 0.667,   # default
    'noise_w_scale': 1,     # more speaking variation
    'normalize_audio': True
}

PORTUGUESE_SYN_CONFIG = {
    'length_scale': 1.15,    # slower
    'volume': 1.0,
    'noise_scale': 0.5,     # lower variation
    'noise_w_scale': 1.2,   # more speaking variation
    'normalize_audio': True
}

SPANISH_SYN_CONFIG = {
    'length_scale': 1,      # default
    'volume': 1.0,
    'noise_scale': 0.667,   # default
    'noise_w_scale': 1.2,   # more speaking variation
    'normalize_audio': True
}


def _get_piper_models_dir():
    """Get the directory where Piper models should be stored."""
    # Create models/piper if it doesn't exist
    os.makedirs(MODELS_DIR, exist_ok=True)
    return MODELS_DIR


def _load_piper_voice():
    """Load Piper voice model with CUDA (mandatory)."""
    try:
        from piper import PiperVoice
        
        # Get the model file path
        models_dir = _get_piper_models_dir()
        model_file = f'{PIPER_MODEL_NAME}.onnx'
        model_path = os.path.join(models_dir, model_file)
        
        # Check if model exists
        if not os.path.exists(model_path):
            raise Exception(
                f'Piper model not found: {model_path}\n'
                f'Run ./scripts/install.sh to download the model.'
            )
        
        # Load voice with CUDA (mandatory, no fallback)
        voice = PiperVoice.load(model_path, use_cuda=True)
        return voice
    except ImportError as e:
        raise Exception(
            f'piper-tts package not installed. Error: {e}\n'
            f'Install with: pip install piper-tts'
        )
    except Exception as e:
        error_msg = str(e)
        if 'cuda' in error_msg.lower() or 'gpu' in error_msg.lower():
            raise Exception(
                f'CUDA/GPU required for Piper TTS but not available. Error: {e}\n'
                f'Make sure onnxruntime-gpu is installed and CUDA is available.'
            )
        raise Exception(f'Failed to load Piper voice model: {e}')


def _load_piper_voice_english():
    """Load English Piper voice model with CUDA (mandatory)."""
    try:
        from piper import PiperVoice
        
        # Get the model file path
        models_dir = _get_piper_models_dir()
        model_file = f'{PIPER_EN_MODEL_NAME}.onnx'
        model_path = os.path.join(models_dir, model_file)
        
        # Check if model exists - raise error if not found
        if not os.path.exists(model_path):
            raise Exception(
                f'English Piper model not found: {model_path}\n'
                f'Download with: piper-download --model {PIPER_EN_MODEL_NAME} --output-dir {models_dir}'
            )
        
        # Load voice with CUDA (mandatory, no fallback)
        voice = PiperVoice.load(model_path, use_cuda=True)
        return voice
    except ImportError as e:
        raise Exception(
            f'piper-tts package not installed. Error: {e}\n'
            f'Install with: pip install piper-tts'
        )
    except Exception as e:
        error_msg = str(e)
        if 'cuda' in error_msg.lower() or 'gpu' in error_msg.lower():
            raise Exception(
                f'CUDA/GPU required for Piper TTS but not available. Error: {e}\n'
                f'Make sure onnxruntime-gpu is installed and CUDA is available.'
            )
        raise Exception(f'Failed to load English Piper voice model: {e}')


def _load_piper_voice_spanish():
    """Load Spanish Piper voice model with CUDA (mandatory)."""
    try:
        from piper import PiperVoice
        
        # Get the model file path
        models_dir = _get_piper_models_dir()
        model_file = f'{PIPER_ES_MODEL_NAME}.onnx'
        model_path = os.path.join(models_dir, model_file)
        
        # Check if model exists - raise error if not found
        if not os.path.exists(model_path):
            raise Exception(
                f'Spanish Piper model not found: {model_path}\n'
                f'Download with: piper-download --model {PIPER_ES_MODEL_NAME} --output-dir {models_dir}'
            )
        
        # Load voice with CUDA (mandatory, no fallback)
        voice = PiperVoice.load(model_path, use_cuda=True)
        return voice
    except ImportError as e:
        raise Exception(
            f'piper-tts package not installed. Error: {e}\n'
            f'Install with: pip install piper-tts'
        )
    except Exception as e:
        error_msg = str(e)
        if 'cuda' in error_msg.lower() or 'gpu' in error_msg.lower():
            raise Exception(
                f'CUDA/GPU required for Piper TTS but not available. Error: {e}\n'
                f'Make sure onnxruntime-gpu is installed and CUDA is available.'
            )
        raise Exception(f'Failed to load Spanish Piper voice model: {e}')


def _generate_speech_with_piper(voice, text, output_path, language):
    """Generate speech from text using Piper TTS model.
    
    Args:
        voice: PiperVoice instance
        text: Text to synthesize
        output_path: Output WAV file path
        language: Optional language code ('pt' for Portuguese, 'en' for English, 'es' for Spanish).
                  If None, will be auto-detected from voice model.
        use_enhanced_variation: If True, use enhanced variation settings for Portuguese.
                                Only applies to video generation. Defaults to False.
    """
    try:
        from piper import PiperVoice, SynthesisConfig
        
        if language == 'en':
            syn_config = SynthesisConfig(**ENGLISH_SYN_CONFIG)
        elif language == 'pt':
            syn_config = SynthesisConfig(**PORTUGUESE_SYN_CONFIG)
        elif language == 'es':
            syn_config = SynthesisConfig(**SPANISH_SYN_CONFIG)
        else:
            raise Exception('Error while detecting language')
        
        # Use synthesize_wav with synthesis config
        with wave.open(output_path, 'wb') as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)
    except Exception as e:
        raise Exception(f'Piper TTS synthesis failed: {e}')


def generate_tts_batch(texts, output_paths, language='pt'):
    """Generate TTS audio for multiple texts in batch using Piper.
    
    Args:
        texts: List of texts to synthesize
        output_paths: List of output file paths
        language: Language code ('pt' for Portuguese, 'en' for English, 'es' for Spanish). Defaults to 'pt'.
        use_enhanced_variation: If True, use enhanced variation settings for Portuguese.
                                Only applies to video generation. Defaults to False.
    """
    try:
        if len(texts) != len(output_paths):
            raise ValueError('Number of texts must match number of output paths')
        
        # Load appropriate voice model based on language
        if language == 'en':
            model_name = PIPER_EN_MODEL_NAME
            voice = _load_piper_voice_english()
        elif language == 'es':
            model_name = PIPER_ES_MODEL_NAME
            voice = _load_piper_voice_spanish()
        else:
            model_name = PIPER_MODEL_NAME
            voice = _load_piper_voice()
        
        print(f'📦 Loading Piper TTS model ({model_name}) for {len(texts)} segments...', flush=True)
        
        for i, (text, output_path) in enumerate(zip(texts, output_paths), 1):
            _generate_speech_with_piper(voice, text, output_path, language)
        
        return True
        
    except Exception as e:
        raise Exception(f'Piper TTS batch generation failed: {e}')

