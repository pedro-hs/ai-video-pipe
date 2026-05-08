#!/bin/bash

# Wrapper script to merge video and audio for a failed generation
# Activates venv and runs the Python script
# Usage: ./scripts/merge_video.sh <folder_name>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "❌ Virtual environment not found! Run setup first."
    exit 1
fi

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

# Run the Python script with all arguments
python3 "$SCRIPT_DIR/merge_video.py" "$@"

