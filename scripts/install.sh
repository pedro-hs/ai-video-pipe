#!/bin/bash

# Video Pipeline - Local Setup Script
# This script sets up the video generation app to run locally without Docker

set -e

echo "🚀 Setting up Video Pipeline for local development..."

# Check if we're in the right directory
if [ ! -f "../requirements.txt" ]; then
    echo "❌ Error: Please run this script from the scripts directory"
    exit 1
fi

# Check and install required system packages
echo "🔧 Checking system dependencies..."
REQUIRED_PACKAGES="python3-venv python3-pip python3-dev build-essential curl wget git ffmpeg libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libavfilter-dev libswscale-dev libswresample-dev"

# Check if running on Debian/Ubuntu
if command -v apt-get >/dev/null 2>&1; then
    echo "📋 Checking for required packages on Debian/Ubuntu..."
    
    # Check which packages are missing
    MISSING_PACKAGES=""
    for package in $REQUIRED_PACKAGES; do
        if ! dpkg -l | grep -q "^ii  $package "; then
            MISSING_PACKAGES="$MISSING_PACKAGES $package"
        fi
    done
    
    if [ -n "$MISSING_PACKAGES" ]; then
        echo "📦 Installing missing packages:$MISSING_PACKAGES"
        echo "This requires sudo privileges..."
        sudo apt update
        sudo apt install -y $MISSING_PACKAGES
        if [ $? -ne 0 ]; then
            echo "❌ Failed to install required packages"
            echo "Please run: sudo apt install -y $MISSING_PACKAGES"
            exit 1
        fi
        echo "✅ Required packages installed"
    else
        echo "✅ All required packages are already installed"
    fi
else
    echo "⚠️ Not on Debian/Ubuntu system. Please ensure you have:"
    echo "   - python3-venv (or equivalent)"
    echo "   - python3-pip"
    echo "   - build-essential (or equivalent)"
    echo "   - curl, wget, git"
fi

# Remove existing venv if it exists and failed
# if [ -d "../venv" ]; then
#     echo "🗑️ Removing existing virtual environment..."
#     rm -rf ../venv
# fi

# Create Python virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv ../venv

# Check if virtual environment was created successfully
if [ ! -d "../venv" ] || [ ! -f "../venv/bin/python" ]; then
    echo "❌ Failed to create virtual environment"
    echo ""
    echo "Common solutions:"
    echo "1. Install python3-venv: sudo apt install python3-venv"
    echo "2. Check Python version: python3 --version"
    echo "3. Try: python3 -m ensurepip --default-pip"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source ../venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "📚 Installing Python dependencies..."
pip install -r ../requirements.txt

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p ../output/temp
mkdir -p ../sounds
mkdir -p ../models
mkdir -p ../models/ollama
mkdir -p ../models/piper
mkdir -p ../models/yolo

# Download Piper voice models
echo "📥 Downloading Piper voice models..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIPER_MODEL_DIR="$PROJECT_ROOT/models/piper"

# Function to download and copy Piper model
download_piper_model() {
    local MODEL_NAME=$1
    local MODEL_FILE="$PIPER_MODEL_DIR/$MODEL_NAME.onnx"
    
    if [ ! -f "$MODEL_FILE" ]; then
        echo "   Downloading: $MODEL_NAME..."
        # Change to models/piper directory to ensure download happens there
        cd "$PIPER_MODEL_DIR"
        python3 -m piper.download_voices "$MODEL_NAME"
        cd "$PROJECT_ROOT"
        
        # Search for downloaded model in common locations and copy to models/piper
        FOUND_MODEL=false
        SEARCH_LOCATIONS=(
            "$HOME/.local/share/piper/voices/$MODEL_NAME.onnx"
            "$HOME/.local/share/piper/voices/$MODEL_NAME/$MODEL_NAME.onnx"
            "$PIPER_MODEL_DIR/$MODEL_NAME.onnx"
        )
        
        for model_path in "${SEARCH_LOCATIONS[@]}"; do
            if [ -f "$model_path" ]; then
                # Only copy if not already in the target directory
                if [ "$model_path" != "$MODEL_FILE" ]; then
                    cp "$model_path" "$PIPER_MODEL_DIR/"
                    # Also copy JSON config file
                    json_path="${model_path%.onnx}.onnx.json"
                    if [ -f "$json_path" ]; then
                        cp "$json_path" "$PIPER_MODEL_DIR/"
                    fi
                    echo "   ✅ Piper model copied to $PIPER_MODEL_DIR"
                else
                    echo "   ✅ Piper model already in $PIPER_MODEL_DIR"
                fi
                FOUND_MODEL=true
                break
            fi
        done
        
        if [ "$FOUND_MODEL" = false ]; then
            echo "   ⚠️  Piper model downloaded but not found in expected locations"
            echo "   Please check if model was downloaded successfully"
        fi
    else
        echo "   ✅ Piper voice model already exists: $MODEL_FILE"
    fi
}

# Download Portuguese model
download_piper_model "pt_BR-faber-medium"

# Download English model
download_piper_model "en_GB-alba-medium"

# Download Spanish model
download_piper_model "es_ES-sharvard-medium"

# Download YOLO person detection model
echo "📥 Downloading YOLO person detection model..."
YOLO_MODEL_DIR="$PROJECT_ROOT/models/yolo"
YOLO_MODEL_FILE="$YOLO_MODEL_DIR/yolov8n.pt"

if [ ! -f "$YOLO_MODEL_FILE" ]; then
    echo "   Downloading YOLOv8n model for person detection..."
    
    # Ensure directory exists
    mkdir -p "$YOLO_MODEL_DIR"
    
    # Download directly to target location (no cache, no copies)
    "$PROJECT_ROOT/venv/bin/python" << PYTHON_SCRIPT
import os
import urllib.request
from pathlib import Path

model_dir = "$YOLO_MODEL_DIR"
model_path = os.path.join(model_dir, 'yolov8n.pt')

print(f"Downloading YOLOv8n directly to {model_path}...")
try:
    # Download directly from GitHub releases (official source)
    url = "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt"
    print(f"Downloading from {url}...")
    
    # Download with progress
    def show_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(100, (downloaded / total_size) * 100) if total_size > 0 else 0
        print(f"\r   Progress: {percent:.1f}%", end='', flush=True)
    
    urllib.request.urlretrieve(url, model_path, reporthook=show_progress)
    print(f"\n✅ YOLO model downloaded to {model_path}")
    
    # Verify file exists and has reasonable size (> 1MB)
    if os.path.exists(model_path):
        file_size = os.path.getsize(model_path)
        if file_size < 1024 * 1024:  # Less than 1MB is suspicious
            print(f"⚠️  Warning: Downloaded file seems too small ({file_size} bytes)")
            os.remove(model_path)
            raise Exception("Downloaded file is too small")
        print(f"   File size: {file_size / (1024*1024):.2f} MB")
    else:
        raise Exception("File was not created")
        
except Exception as e:
    print(f"\n❌ Error downloading YOLO model: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYTHON_SCRIPT
    
    if [ -f "$YOLO_MODEL_FILE" ]; then
        echo "   ✅ YOLO person detection model downloaded: $YOLO_MODEL_FILE"
    else
        echo "   ⚠️  YOLO model download failed"
        echo "   The model will be downloaded automatically on first use."
    fi
else
    echo "   ✅ YOLO person detection model already exists: $YOLO_MODEL_FILE"
fi

# Download Civitai models
echo "📥 Checking Civitai models..."
MODELS_DIR="$PROJECT_ROOT/models"
CURRENT_DIR="$(pwd)"
cd "$MODELS_DIR"

CHEYENNE_FILE="$MODELS_DIR/CHEYENNE_v18.safetensors"
TRADITIONAL_FILE="$MODELS_DIR/traditionalPainting_v02.safetensors"

if [ -f "656688?type=Model" ] && [ ! -f "$CHEYENNE_FILE" ]; then
    echo "   Renaming existing downloaded file to CHEYENNE_v18.safetensors..."
    mv "656688?type=Model" "$CHEYENNE_FILE"
fi

if [ -f "289591?type=Model" ] && [ ! -f "$TRADITIONAL_FILE" ]; then
    echo "   Renaming existing downloaded file to traditionalPainting_v02.safetensors..."
    mv "289591?type=Model" "$TRADITIONAL_FILE"
fi

if [ ! -f "$CHEYENNE_FILE" ]; then
    echo "   Downloading CHEYENNE_v18.safetensors..."
    wget -O "$CHEYENNE_FILE" "https://civitai.com/api/download/models/656688?type=Model&format=SafeTensor&size=full&fp=fp16"
fi

if [ ! -f "$TRADITIONAL_FILE" ]; then
    echo "   Downloading traditionalPainting_v02.safetensors..."
    wget -O "$TRADITIONAL_FILE" "https://civitai.com/api/download/models/289591?type=Model&format=SafeTensor&size=full&fp=fp16"
fi

cd "$CURRENT_DIR"

# Check for NVIDIA GPU and drivers
echo "🎮 Checking for NVIDIA GPU..."
if command -v nvidia-smi >/dev/null 2>&1; then
    echo "✅ NVIDIA drivers detected"
    nvidia-smi --query-gpu=name --format=csv,noheader | head -1
else
    echo "⚠️ No NVIDIA GPU or drivers detected"
    echo "   GPU acceleration will not be available"
    echo "   Install NVIDIA drivers for better performance"
fi

# Download Ollama binary
echo "🦙 Downloading Ollama..."
cd ../models/ollama
if [ ! -f "ollama" ]; then
    curl -fsSL https://ollama.com/install.sh | sh
    # Move ollama binary to our local directory
    if [ -f "/usr/local/bin/ollama" ]; then
        cp /usr/local/bin/ollama ./ollama
        chmod +x ./ollama
    fi
fi
cd ..

# Set up Ollama environment
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MODELS=$(pwd)/../models/ollama/models

# Force GPU usage to avoid low VRAM mode
export OLLAMA_GPU_LAYERS=32
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_LOW_VRAM_THRESHOLD=0

echo "🔧 GPU Configuration for model pull:"
echo "   OLLAMA_GPU_LAYERS=$OLLAMA_GPU_LAYERS"
echo "   OLLAMA_FLASH_ATTENTION=$OLLAMA_FLASH_ATTENTION"
echo "   OLLAMA_LOW_VRAM_THRESHOLD=$OLLAMA_LOW_VRAM_THRESHOLD"

# Pull required Ollama model with GPU support
echo "📥 Pulling Ollama model (llama3.1:8b) with GPU support..."
# TODO2: PULLING RETURNING ERROR AND NOT PULLING
env OLLAMA_GPU_LAYERS=32 OLLAMA_FLASH_ATTENTION=1 OLLAMA_LOW_VRAM_THRESHOLD=0 ../models/ollama/ollama pull llama3.1:8b

echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "1. Run: ./scripts/start.sh"
echo "2. Open: http://localhost:8080"
echo ""
echo "To activate the virtual environment manually:"
echo "source ../venv/bin/activate"
