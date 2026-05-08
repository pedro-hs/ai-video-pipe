# Local AI Video Generator

Vibe code application that receive speech (text) and generate AI video (image "slideshow" + speech + music). 
`Ollama` create image prompts, `SDXL` generate images, `Piper TTS` to generate speech, and FFMPEG assembly.
Also allow generate image or speech without generating a video.

- You can see the pages layout and AI generated images/speech examples in the folder `examples/`
- SDXL generates bad images, due to that, was added the option to regenerate images and change prompts

### Features:
- Generate image
- Generate speech
- Generate video

### Video Features:
- Add pause in speech, adding the text `(silence)` in narration
- Split video in vertical videos, using `(silence)`
- Zoom (ken burn)
- Film grain filter
- Input background sound through frontend
- Input narration and image style params through frontend
- Detect subscription in narration and add subscription overlay
- Generate videos in english, portuguese, spanish
- Create video in one language, add or remove text in narration (with Ollama suggestions) to keep the same video length, so application can reuse the same visuals for each language
- Edit video, renegerating images or change narration text and regenerate the video with updated images and speech
- Images, narration and prompts of each video is saved in output folder, is possible to regenerate video, you can delete temp/ folder or final videos to save disk space

### Ouput Folder:
- ouput/audios/ ->  generated speech by Piper TTS
- ouput/images/ ->  generated images by SDXL
- ouput/videos/ ->  generated videos
- ouput/videos/[VIDEO_NAME]/images/ ->  generated images for the video (SDXL)
- ouput/videos/[VIDEO_NAME]/musics/ -> background music (Frontend input)
- ouput/videos/[VIDEO_NAME]/narration/[EN/ES/PT]/narration.txt -> narration (Frontend input)
- ouput/videos/[VIDEO_NAME]/narration/[EN/ES/PT]/audio_segments -> audio paragraphs (Piper TTS)
- ouput/videos/[VIDEO_NAME]/visuals/image_prompts.txt ->  Image prompts created by Ollama based on narration sent to SDXL
- ouput/videos/[VIDEO_NAME]/visuals/style.txt -> Params sent to SDXL

## 🚀 Quick Start

### Setup (One-time)
```bash
# Make scripts executable
chmod +x scripts/install.sh scripts/start.sh scripts/stop.sh

# Run setup (installs dependencies, downloads Ollama, sets up environment)
./scripts/install.sh
```

### Start the Application
```bash
# Start all services (Ollama + Web Interface)
./scripts/start.sh
```

## ⚙️ Configuration

### Environment Variables

#### Face Blur Configuration
- **`ENABLE_FACE_BLUR`** (default: `true`): Enable or disable face blurring in generated images
  - Set to `true` to blur distorted faces in generated images
  - Set to `false` to disable face blurring entirely

#### Image Configuration
- **`SAVE_ORIGINAL_IMAGE`** (default: `false`): Save original image before face blur is applied
  - Set to `true` to save `image_XX_original.png` files before face blur processing
  - Set to `false` to only keep the final processed images

#### Video Configuration
- **`USE_KEN_BURNS_EFFECT`** (default: `true`): Enable or disable Ken Burns zoom effect in videos
  - Set to `true` to use Ken Burns zoom effect (smooth zoom and pan transitions)
  - Set to `false` to use simple video effect (static images with crossfade transitions)

#### Setting Environment Variables

**Using .env file**
```bash
# Copy the example file
cp env.example .env

# Edit .env and set your preferred values, the application will automatically load these variables
vi .env
```

## 🔧 Manual Setup (Alternative)

If the automated setup doesn't work, you can set up manually:

### 1. Create Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Install Ollama Locally
```bash
mkdir -p models/ollama
cd models/ollama
curl -fsSL https://ollama.com/install.sh | sh
# Copy ollama binary to our directory if installed system-wide
if [ -f "/usr/local/bin/ollama" ]; then
    cp /usr/local/bin/ollama ./ollama
    chmod +x ./ollama
fi
cd ../..
```

### 3. Download Ollama Model
```bash
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MODELS=$(pwd)/models/ollama/models
export OLLAMA_GPU_LAYERS=32
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_LOW_VRAM_THRESHOLD=0

# Use system ollama or local binary
ollama pull llama3.1:8b
# OR
./models/ollama/ollama pull llama3.1:8b
```

### 4. Create Directories
```bash
mkdir -p output/temp
mkdir -p output/videos
mkdir -p output/images
mkdir -p output/audios
mkdir -p models
mkdir -p src/audio/voices
```

### 5. Start Services
```bash
# Terminal 1: Start Ollama
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MODELS=$(pwd)/models/ollama/models
export OLLAMA_GPU_LAYERS=32
export OLLAMA_FLASH_ATTENTION=1
ollama serve  # or ./models/ollama/ollama serve

# Terminal 2: Start Web Interface
source venv/bin/activate
export PYTHONPATH=$(pwd)/src:$PYTHONPATH
python src/app.py
```
