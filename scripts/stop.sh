#!/bin/bash

# Video Pipeline - Stop Services
echo "🛑 Stopping Video Pipeline services..."

# Kill Ollama
echo "🦙 Stopping Ollama..."
pkill -f "ollama serve" 2>/dev/null || true
sleep 2
pkill -9 -f "ollama serve" 2>/dev/null || true

# Kill web interface
echo "🌐 Stopping web interface..."
pkill -f "python.*app.py" 2>/dev/null || true
sleep 2
pkill -9 -f "python.*app.py" 2>/dev/null || true

# Kill generation processes
echo "🎬 Stopping generation processes..."
pkill -f "video_generator.py|generate_audio.py" 2>/dev/null || true
sleep 2
 pkill -9 -f "video_generator.py|generate_audio.py" 2>/dev/null || true

# Aggressively kill the venv Python running this repo (frees CUDA VRAM)
REPO_ROOT="/home/pedro/src/others/vpipe"

echo "🐍 Stopping venv python processes holding GPU memory..."
# Kill any remaining python processes launched from this repo path
pgrep -f "$REPO_ROOT/src" >/dev/null 2>&1 && kill $(pgrep -f "$REPO_ROOT/src") 2>/dev/null || true
sleep 2
pgrep -f "$REPO_ROOT/src" >/dev/null 2>&1 && kill -9 $(pgrep -f "$REPO_ROOT/src") 2>/dev/null || true

# Kill common trainers/launchers if used
pkill -f "torchrun|accelerate-launch" 2>/dev/null || true
sleep 1
pkill -9 -f "torchrun|accelerate-launch" 2>/dev/null || true

# Wait briefly for CUDA contexts to be released
echo "⏳ Waiting for CUDA contexts to release..."
sleep 2

# Clean up status files
echo "🧹 Cleaning up..."
rm -f "./output/temp/generation_status.json" 2>/dev/null || true

echo "✅ All services stopped"
