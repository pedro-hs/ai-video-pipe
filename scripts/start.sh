#!/bin/bash

# Video Pipeline - Start Services
echo "🚀 Starting Video Pipeline services..."

# Stop any existing services first
echo "🛑 Stopping existing services..."
if [ -f "./scripts/stop.sh" ]; then
    ./scripts/stop.sh
    echo ""
fi

# Check if virtual environment exists
if [ ! -d "./venv" ]; then
    echo "❌ Virtual environment not found! Run setup first."
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source ./venv/bin/activate

# Check if Ollama binary exists (prefer system binary, fallback to local)
if command -v ollama >/dev/null 2>&1; then
    OLLAMA_BIN=$(command -v ollama)
    echo "✅ Using system Ollama: $OLLAMA_BIN"
elif [ -f "./models/ollama/ollama" ]; then
    OLLAMA_BIN="./models/ollama/ollama"
    echo "✅ Using local Ollama: $OLLAMA_BIN"
else
    echo "❌ Ollama binary not found! Install Ollama first."
    exit 1
fi

# Set Ollama environment variables
export OLLAMA_GPU_LAYERS=32 
export OLLAMA_FLASH_ATTENTION=1 
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MODELS=$(pwd)/models/ollama/models
export OLLAMA_LOW_VRAM_THRESHOLD=0
export CUDA_VISIBLE_DEVICES=0
# disable firefox hardware acceleration
export MOZ_ACCELERATED=0
export MOZ_WEBRENDER=0

# Ensure CUDA libraries are accessible (Ollama bundles CUDA runtime and plugins)
# Ollama needs both the base plugin directory and the CUDA subdirectory
if [ -d "/usr/local/lib/ollama/cuda_v13" ]; then
    export LD_LIBRARY_PATH="/usr/local/lib/ollama/cuda_v13:/usr/local/lib/ollama:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
    echo "✅ CUDA v13 libraries found"
elif [ -d "/usr/local/lib/ollama/cuda_v12" ]; then
    export LD_LIBRARY_PATH="/usr/local/lib/ollama/cuda_v12:/usr/local/lib/ollama:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
    echo "✅ CUDA v12 libraries found"
else
    export LD_LIBRARY_PATH="/usr/local/lib/ollama:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
    echo "⚠️  CUDA libraries not found in standard location"
fi

echo "📋 Environment check:"
echo "   OLLAMA_MODELS=$OLLAMA_MODELS"
echo "   CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
echo "   OLLAMA_GPU_LAYERS=$OLLAMA_GPU_LAYERS"
echo "   LD_LIBRARY_PATH=$LD_LIBRARY_PATH"

# Start Ollama
echo "🦙 Starting Ollama server..."
$OLLAMA_BIN serve &
OLLAMA_PID=$!

# Wait for Ollama to start
echo "⏳ Waiting for Ollama to initialize..."
sleep 3

# Start web interface
echo "🌐 Starting Web Interface at http://localhost:8080"
echo "🛑 Press Ctrl+C to stop all services"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    
    # Kill Ollama
    if kill -0 $OLLAMA_PID 2>/dev/null; then
        kill $OLLAMA_PID
        sleep 2
        kill -9 $OLLAMA_PID 2>/dev/null || true
    fi
    
    echo "✅ All services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start web interface in foreground
python src/app/app.py
