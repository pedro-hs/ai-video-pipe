let generating = false;
let generatingImage = false;
let generatingAudio = false;

function setProgressFill(fillId, percent) {
    const fill = document.getElementById(fillId);
    if (!fill) return;
    fill.style.width = percent + '%';
    fill.textContent = Math.round(percent) + '%';
}

function getStageLabel(stageMap, stage) {
    return stageMap[stage] || stage;
}

function writeText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function renderInto(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
}

function videoCard(video) {
    const folder = video.folder || video.filename.split('/')[0];
    const hasFolder = video.folder !== null && video.folder !== undefined;
    const thumbPath = video.thumb_path || (hasFolder ? `/api/videos/${encodeURIComponent(folder)}/thumb` : null);
    const videoPath = video.path;
    const hasPortuguese = video.has_portuguese || false;
    const portuguesePath = video.portuguese_path || null;
    const hasPortugueseNarration = video.has_portuguese_narration || false;
    const hasEnglish = video.has_english || false;
    const englishPath = video.english_path || null;
    const hasSpanish = video.has_spanish || false;
    const spanishPath = video.spanish_path || null;
    const hasEnglishNarration = video.has_english_narration || false;
    const hasSpanishNarration = video.has_spanish_narration || false;
    const hasShortsPt = video.has_shorts_pt || false;
    const hasShortsEn = video.has_shorts_en || false;
    const hasShortsEs = video.has_shorts_es || false;
    
    // Create a safe, unique ID for the video element based on folder name
    // Use a simple hash-like approach for uniqueness
    const folderHash = folder.replace(/[^a-zA-Z0-9]/g, '-').substring(0, 50);
    const videoId = `video-${folderHash}-${Math.random().toString(36).substr(2, 9)}`;
    
    const allShortsGenerated = (!hasPortugueseNarration || hasShortsPt) && (!hasEnglishNarration || hasShortsEn) && (!hasSpanishNarration || hasShortsEs);
    const generateAllShortsButton = allShortsGenerated 
        ? `<button disabled class="btn btn-small" style="background: #6c757d; opacity: 0.7; cursor: not-allowed; font-weight: bold;" id="shorts-btn-${folderHash}">✅ 🌐 Todos os Shorts (Já Gerados)</button>`
        : `<button onclick="generateShorts('${folder.replace(/'/g, "\\'")}')" class="btn btn-small" style="background: #9c27b0; font-weight: bold;" id="shorts-btn-${folderHash}">🎬 🌐 Gerar Todos os Shorts</button>`;
    
    return `
        <div class="video-item">
            <div id="preview-${videoId}" class="video-preview-container" style="position: relative; width: 100%; background: #000; border-radius: 8px; overflow: hidden; cursor: pointer; min-height: 200px; display: block;" onclick="playVideo('${videoId}', '${videoPath.replace(/'/g, "\\'")}')">
                ${thumbPath ? `
                    <img src="${thumbPath}" alt="Video thumbnail" style="width: 100%; height: auto; display: block; min-height: 200px; object-fit: cover;" 
                         onerror="this.onerror=null; this.style.display='none'; this.nextElementSibling.style.display='flex';">
                ` : ''}
                <div style="width: 100%; height: 200px; display: ${thumbPath ? 'none' : 'flex'}; align-items: center; justify-content: center; background: #333; color: #fff; position: absolute; top: 0; left: 0;">
                    <span>🎬 Clique para reproduzir</span>
                </div>
                <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.7); border-radius: 50%; width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; pointer-events: none; z-index: 1;">
                    <span style="color: white; font-size: 24px;">▶️</span>
                </div>
            </div>
            <div id="player-${videoId}" style="display: none;">
                <video controls style="width: 100%;" preload="none">
                    <source src="" type="video/mp4">
                    Seu navegador não suporta vídeo HTML5.
                </video>
            </div>
            <div class="video-info">
                <h4>${video.filename.replace('.mp4', '').replace(/_/g, ' ')}</h4>
                <div class="video-meta">📅 ${video.created}</div>
                <div class="video-meta">💾 ${video.size}</div>
                <div class="video-actions">
                    ${hasFolder ? `<button onclick="editVideo('${folder.replace(/'/g, "\\'")}')" class="btn btn-small" style="background: #28a745;">✏️ Editar</button>` : `<button disabled class="btn btn-small" style="background: #28a745; opacity: 0.5; cursor: not-allowed;">✏️ Editar</button>`}
                    <a href="${videoPath}" download class="btn btn-small">⬇️ Download</a>
                    ${hasPortuguese && portuguesePath ? `<a href="${portuguesePath}" download class="btn btn-small" style="background: #28a745;">🇧🇷 Download Português</a>` : ((hasEnglish || hasSpanish) && hasFolder ? `<button onclick="openPortugueseModal('${folder.replace(/'/g, "\\'")}')" class="btn btn-small" style="background: #007bff;">🇧🇷 Generate Portuguese</button>` : '')}
                    ${hasEnglish && englishPath ? `<a href="${englishPath}" download class="btn btn-small" style="background: #28a745;">🇬🇧 Download English</a>` : (hasFolder ? `<button onclick="openEnglishModal('${folder.replace(/'/g, "\\'")}')" class="btn btn-small" style="background: #007bff;">🇬🇧 Generate English</button>` : '')}
                    ${hasSpanish && spanishPath ? `<a href="${spanishPath}" download class="btn btn-small" style="background: #28a745;">🇪🇸 Download Spanish</a>` : (hasFolder ? `<button onclick="openSpanishModal('${folder.replace(/'/g, "\\'")}')" class="btn btn-small" style="background: #007bff;">🇪🇸 Generate Spanish</button>` : '')}
                    ${hasFolder ? `<div style="display: flex; gap: 5px; flex-wrap: wrap; margin-top: 5px;">
                        ${generateAllShortsButton}
                        ${hasPortugueseNarration ? (hasShortsPt ? `<button disabled class="btn btn-small" style="background: #6c757d; opacity: 0.7; cursor: not-allowed;" id="shorts-btn-pt-${folderHash}">✅ 🇧🇷 Shorts PT (Já Gerados)</button>` : `<button onclick="generateShortsForLanguage('${folder.replace(/'/g, "\\'")}', 'pt')" class="btn btn-small" style="background: #9c27b0;" id="shorts-btn-pt-${folderHash}">🎬 🇧🇷 Shorts PT</button>`) : ''}
                        ${hasEnglishNarration ? (hasShortsEn ? `<button disabled class="btn btn-small" style="background: #6c757d; opacity: 0.7; cursor: not-allowed;" id="shorts-btn-en-${folderHash}">✅ 🇬🇧 Shorts EN (Já Gerados)</button>` : `<button onclick="generateShortsForLanguage('${folder.replace(/'/g, "\\'")}', 'en')" class="btn btn-small" style="background: #9c27b0;" id="shorts-btn-en-${folderHash}">🎬 🇬🇧 Shorts EN</button>`) : ''}
                        ${hasSpanishNarration ? (hasShortsEs ? `<button disabled class="btn btn-small" style="background: #6c757d; opacity: 0.7; cursor: not-allowed;" id="shorts-btn-es-${folderHash}">✅ 🇪🇸 Shorts ES (Já Gerados)</button>` : `<button onclick="generateShortsForLanguage('${folder.replace(/'/g, "\\'")}', 'es')" class="btn btn-small" style="background: #9c27b0;" id="shorts-btn-es-${folderHash}">🎬 🇪🇸 Shorts ES</button>`) : ''}
                    </div>` : ''}
                </div>
            </div>
        </div>
    `;
}

function playVideo(videoId, videoPath) {
    const preview = document.getElementById(`preview-${videoId}`);
    const player = document.getElementById(`player-${videoId}`);
    
    if (!preview || !player) {
        console.error('Video elements not found:', videoId);
        return;
    }
    
    const video = player.querySelector('video');
    const source = video ? video.querySelector('source') : null;
    
    if (!video || !source) {
        console.error('Video or source element not found');
        return;
    }
    
    // Hide preview, show player
    preview.style.display = 'none';
    player.style.display = 'block';
    
    // Load video only when user clicks
    source.src = videoPath;
    video.load();
    
    // Play video
    video.play().catch(err => {
        console.error('Error playing video:', err);
        // If autoplay fails, user can click play button
    });
}

function videosEmptyState() {
    return `
        <div class="empty-state">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
            </svg>
            <p>Nenhum vídeo gerado ainda</p>
            <p style="margin-top: 10px;">Vá para a aba "Gerar Vídeo" para criar seu primeiro vídeo!</p>
        </div>
    `;
}

function imageCard(image) {
    return `
        <div class="video-item">
            <img src="${image.path}" alt="${image.filename}" style="width: 100%; height: 200px; object-fit: cover; background: #000;">
            <div class="video-info">
                <h4>${image.filename.replace('.png', '').replace(/_/g, ' ')}</h4>
                <div class="video-meta">📅 ${image.created}</div>
                <div class="video-meta">💾 ${image.size}</div>
                <div class="video-actions">
                    <a href="${image.path}" download class="btn btn-small">⬇️ Download</a>
                    <button onclick="deleteImage('${image.filename}')" class="btn btn-small" style="background: #dc3545;">🗑️ Deletar</button>
                </div>
            </div>
        </div>
    `;
}

function imagesEmptyState() {
    return `
        <div class="empty-state">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
            </svg>
            <p>Nenhuma imagem gerada ainda</p>
            <p style="margin-top: 10px;">Vá para a aba "Gerar Imagem" para criar sua primeira imagem!</p>
        </div>
    `;
}

function audioCard(audio) {
    return `
        <div class="video-item">
            <audio controls style="width: 100%; margin-bottom: 10px;">
                <source src="${audio.path}" type="audio/wav">
                Seu navegador não suporta áudio HTML5.
            </audio>
            <div class="video-info">
                <h4>${audio.filename.replace('.wav', '').replace(/_/g, ' ')}</h4>
                <div class="video-meta">📅 ${audio.created}</div>
                <div class="video-meta">💾 ${audio.size}</div>
                <div class="video-actions">
                    <a href="${audio.path}" download class="btn btn-small">⬇️ Download</a>
                    <button onclick="regenerateAudio('${audio.filename}')" class="btn btn-small" style="background: #28a745;">🔄 Regenerar</button>
                    <button onclick="deleteAudio('${audio.filename}')" class="btn btn-small" style="background: #dc3545;">🗑️ Deletar</button>
                </div>
            </div>
        </div>
    `;
}

function audiosEmptyState() {
    return `
        <div class="empty-state">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"></path>
            </svg>
            <p>Nenhum áudio gerado ainda</p>
            <p style="margin-top: 10px;">Use o formulário acima para gerar seus primeiros áudios!</p>
        </div>
    `;
}

function initializeAppData() {
    checkStatus();
    loadVideos();
}

function setupPeriodicTasks() {
    setInterval(checkStatus, 30000);
    setInterval(loadVideos, 120000);
    setInterval(loadImages, 120000);
}

function initializeStatusChecks() {
    checkGenerationStatusOnLoad();
}

function createPollingSystem() {
    let statusInterval;
    let isPollingActive = false;
    let imageStatusInterval;
    let isImagePollingActive = false;

    window.startMinimalPolling = function() {
        if (!statusInterval && !isPollingActive) {
            isPollingActive = true;
            statusInterval = setInterval(checkGenerationStatus, 30000);
            console.log('Minimal polling started (30s interval - idle mode)');
        }
    };

    window.startActivePolling = function() {
        if (statusInterval) {
            clearInterval(statusInterval);
        }
        isPollingActive = true;
        statusInterval = setInterval(checkGenerationStatus, 7000);
        console.log('Active polling started (7s interval)');
    };

    window.stopPolling = function() {
        if (statusInterval) {
            clearInterval(statusInterval);
            statusInterval = null;
        }
        isPollingActive = false;
        console.log('All polling stopped');
    };

    window.startImageGenerationPolling = function() {
        if (imageStatusInterval) {
            clearInterval(imageStatusInterval);
        }
        isImagePollingActive = true;
        imageStatusInterval = setInterval(checkImageGenerationStatus, 2000);
        console.log('Image generation polling started (2s interval)');
    };

    window.stopImageGenerationPolling = function() {
        if (imageStatusInterval) {
            clearInterval(imageStatusInterval);
            imageStatusInterval = null;
        }
        isImagePollingActive = false;
        console.log('Image generation polling stopped');
    };

    return { startMinimalPolling: window.startMinimalPolling };
}

const WORDS_PER_SECOND = 2.4; // Portuguese TTS speech rate
const SILENCE_DURATION = 2; // seconds per silence marker

function calculateDurationFromNarration() {
    const narrationElement = document.getElementById('narration');
    const durationDisplay = document.getElementById('estimatedDuration');
    
    if (!narrationElement || !durationDisplay) {
        return 0;
    }
    
    const narration = narrationElement.value;
    
    if (!narration || narration.trim().length === 0) {
        durationDisplay.textContent = '~0 segundos (digite o roteiro acima)';
        return 0;
    }
    
    // Remove silence markers for word count
    const textWithoutSilence = narration.replace(/\(silence\)/gi, ' ');
    const words = textWithoutSilence.split(/\s+/).filter(w => w.trim().length > 0);
    const wordCount = words.length;
    
    // Calculate estimated duration
    let estimatedDuration = wordCount / WORDS_PER_SECOND;
    
    // Add duration for silence markers
    const silenceCount = (narration.match(/\(silence\)/gi) || []).length;
    estimatedDuration += silenceCount * SILENCE_DURATION;
    
    // Minimum 5 seconds
    estimatedDuration = Math.max(5, estimatedDuration);
    
    // Format duration display
    const minutes = Math.floor(estimatedDuration / 60);
    const seconds = Math.floor(estimatedDuration % 60);
    let durationText = '';
    if (minutes > 0) {
        durationText = `${minutes} min ${seconds}s`;
    } else {
        durationText = `${seconds}s`;
    }
    
    durationDisplay.textContent = `~${durationText} (${wordCount} palavras)`;
    
    return estimatedDuration;
}

function handleDOMContentLoaded() {
    initializeAppData();
    setupPeriodicTasks();
    initializeStatusChecks();
    
    // Load default image resolution from API
    loadDefaultImageResolution();
    
    const pollingSystem = createPollingSystem();
    pollingSystem.startMinimalPolling();
    console.log('Minimal polling system started - maximum 1 API call per 30 seconds when idle');
    
    // Initialize duration display
    calculateDurationFromNarration();
}

document.addEventListener('DOMContentLoaded', handleDOMContentLoaded);

function isValidNarration(narration) {
    return !!narration && narration.trim().length > 0;
}

function beginVideoGenerationUIState() {
    generating = true;
    document.getElementById('generateBtn').disabled = true;
    document.getElementById('loading').classList.add('active');
    document.getElementById('progressBar').classList.add('active');
    document.getElementById('statusMonitor').classList.add('active');
    lastAlertedStatus = null;
    document.getElementById('imagePrompts').innerHTML = '<span style="opacity: 0.7;">Aguardando geração das imagens...</span>';
    document.getElementById('narrationScript').innerHTML = '<span style="opacity: 0.7;">Processando roteiro de narração...</span>';
    document.getElementById('statusMonitor').classList.add('active');
    document.getElementById('progressBar').classList.add('active');
    document.getElementById('stopBtn').style.display = 'block';
    
    if (typeof startActivePolling === 'function') {
        startActivePolling();
    }
}

async function requestVideoGeneration(payload, musicFiles) {
    // If music files are present, use FormData, otherwise use JSON
    if (musicFiles && musicFiles.length > 0) {
        const formData = new FormData();
        formData.append('data', JSON.stringify(payload));
        // Append all music files
        for (let i = 0; i < musicFiles.length; i++) {
            formData.append('musics', musicFiles[i]);
        }
        const response = await fetch('/api/generate', {
            method: 'POST',
            body: formData
        });
        return await response.json();
    } else {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        return await response.json();
    }
}

function handleVideoGenerationFailureCleanup() {
    generating = false;
    document.getElementById('generateBtn').disabled = false;
    document.getElementById('loading').classList.remove('active');
}

async function handleGenerateFormSubmit(e) {
    e.preventDefault();
    if (generating) return;

    const narration = document.getElementById('narration').value;
    const style = document.getElementById('style').value;
    const negative_prompt = document.getElementById('negativePrompt').value.trim();
    const language = document.getElementById('videoLanguage').value;
    const musicFiles = document.getElementById('musics').files;

    if (!isValidNarration(narration)) {
        showAlert('Por favor, insira o roteiro de narração', 'error');
        return;
    }

    beginVideoGenerationUIState();

    try {
        const data = await requestVideoGeneration({
            narration,
            style,
            negative_prompt,
            language
        }, musicFiles);

        if (data.success) {
            const musicCount = musicFiles && musicFiles.length > 0 ? ` (${musicFiles.length} música(s) anexada(s))` : '';
            showAlert('✅ Vídeo sendo gerado!' + musicCount + ' Acompanhe o progresso em tempo real abaixo.', 'success');
            document.getElementById('narration').value = '';
            document.getElementById('estimatedDuration').textContent = '~0 segundos (digite o roteiro acima)';
            // Clear music files input
            document.getElementById('musics').value = '';
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
            handleVideoGenerationFailureCleanup();
        }
    } catch (error) {
        showAlert('❌ Erro ao conectar com o servidor: ' + error.message, 'error');
        handleVideoGenerationFailureCleanup();
    }
}

function isValidImagePrompt(prompt) {
    return !!prompt && prompt.trim().length > 0;
}

function beginImageGenerationUIState() {
    generatingImage = true;
    document.getElementById('generateImageBtn').disabled = true;
    document.getElementById('imageLoading').classList.add('active');
    document.getElementById('imageProgressBar').classList.add('active');
    document.getElementById('imageStatusMonitor').classList.add('active');
    lastAlertedImageStatus = null;
    document.getElementById('stopImageBtn').style.display = 'block';
    
    // Start polling for image generation status
    startImageGenerationPolling();
}

async function requestImageGeneration(payload) {
    const response = await fetch('/api/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    return await response.json();
}

function handleImageGenerationFailureCleanup() {
    generatingImage = false;
    document.getElementById('generateImageBtn').disabled = false;
    document.getElementById('imageLoading').classList.remove('active');
}

let defaultImageWidth = 1280;
let defaultImageHeight = 960;

async function loadDefaultImageResolution() {
    try {
        const response = await fetch('/api/images/default-resolution');
        const data = await response.json();
        if (data.success) {
            defaultImageWidth = data.width;
            defaultImageHeight = data.height;
            
            // Set default values in inputs
            const widthInput = document.getElementById('imageWidth');
            const heightInput = document.getElementById('imageHeight');
            const defaultResolutionSpan = document.getElementById('defaultImageResolution');
            
            if (widthInput) widthInput.value = defaultImageWidth;
            if (heightInput) heightInput.value = defaultImageHeight;
            if (defaultResolutionSpan) {
                defaultResolutionSpan.textContent = `${defaultImageWidth}x${defaultImageHeight}`;
            }
        }
    } catch (error) {
        console.error('Error loading default image resolution:', error);
        // Fallback to hardcoded defaults if API fails
        const widthInput = document.getElementById('imageWidth');
        const heightInput = document.getElementById('imageHeight');
        if (widthInput) widthInput.value = defaultImageWidth;
        if (heightInput) heightInput.value = defaultImageHeight;
    }
}

async function handleGenerateImageFormSubmit(e) {
    e.preventDefault();
    if (generatingImage) return;

    const prompt = document.getElementById('imagePrompt').value;
    const widthInput = document.getElementById('imageWidth');
    const heightInput = document.getElementById('imageHeight');
    const negative_prompt = document.getElementById('imageNegativePrompt').value.trim();
    
    if (!isValidImagePrompt(prompt)) {
        showAlert('Por favor, insira um prompt para a imagem', 'error');
        return;
    }

    // Get width and height from inputs, fallback to defaults
    const width = widthInput && widthInput.value ? parseInt(widthInput.value) : defaultImageWidth;
    const height = heightInput && heightInput.value ? parseInt(heightInput.value) : defaultImageHeight;
    
    // Validate dimensions
    if (isNaN(width) || isNaN(height) || width < 256 || width > 2048 || height < 256 || height > 2048) {
        showAlert('Por favor, insira dimensões válidas (256-2048)', 'error');
        return;
    }

    beginImageGenerationUIState();

    try {
        const data = await requestImageGeneration({ prompt, width, height, negative_prompt });
        if (data.success) {
            showAlert('✅ Geração de imagem iniciada! Acompanhe o progresso em tempo real.', 'success');
            // Don't clear prompt here - wait for completion
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
            handleImageGenerationFailureCleanup();
        }
    } catch (error) {
        showAlert('❌ Erro ao conectar com o servidor: ' + error.message, 'error');
        handleImageGenerationFailureCleanup();
    }
}

document.getElementById('generateImageForm').addEventListener('submit', handleGenerateImageFormSubmit);
document.getElementById('generateForm').addEventListener('submit', handleGenerateFormSubmit);

async function handleGenerateAudioFormSubmit(e) {
    e.preventDefault();
    if (generatingAudio) return;

    const audioText = document.getElementById('audioText').value.trim();
    
    if (!audioText) {
        showAlert('Por favor, insira o texto para gerar áudios', 'error');
        return;
    }

    generatingAudio = true;
    document.getElementById('generateAudioBtn').disabled = true;
    document.getElementById('audioLoading').style.display = 'block';
    document.getElementById('audioResults').innerHTML = '';

    const audioLanguage = document.getElementById('audioLanguage').value;

    try {
        const response = await fetch('/api/generate-audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                audio_text: audioText,
                language: audioLanguage
            })
        });
        const data = await response.json();

        if (data.success) {
            showAlert(`✅ ${data.message}`, 'success');
            document.getElementById('audioText').value = '';
            document.getElementById('audioLoadingText').textContent = `Gerando ${data.count} áudio(s)...`;
            
            // Wait a bit then reload audios
            setTimeout(() => {
                loadAudios();
                generatingAudio = false;
                document.getElementById('generateAudioBtn').disabled = false;
                document.getElementById('audioLoading').style.display = 'none';
            }, 3000);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
            generatingAudio = false;
            document.getElementById('generateAudioBtn').disabled = false;
            document.getElementById('audioLoading').style.display = 'none';
        }
    } catch (error) {
        showAlert('❌ Erro ao conectar com o servidor: ' + error.message, 'error');
        generatingAudio = false;
        document.getElementById('generateAudioBtn').disabled = false;
        document.getElementById('audioLoading').style.display = 'none';
    }
}

document.getElementById('generateAudioForm').addEventListener('submit', handleGenerateAudioFormSubmit);

async function loadAudios() {
    try {
        const response = await fetch('/api/audios');
        const data = await response.json();
        if (data.success) {
            const html = data.audios.length === 0
                ? audiosEmptyState()
                : data.audios.map(audioCard).join('');
            renderInto('audioGrid', html);
        }
    } catch (error) {
        console.error('Erro ao carregar áudios:', error);
    }
}

async function deleteAudio(filename) {
    await performDeleteOperation({
        confirmMessage: `Tem certeza que deseja deletar "${filename}"?`,
        apiEndpoint: `/api/audios/${filename}`,
        successMessage: '✅ Áudio deletado com sucesso!',
        errorMessage: '❌ Erro ao deletar áudio',
        refreshFunction: loadAudios
    });
}

async function deleteAllAudios() {
    await performDeleteOperation({
        confirmMessage: '⚠️ Tem certeza que deseja DELETAR TODOS OS ÁUDIOS? Esta ação não pode ser desfeita!',
        apiEndpoint: '/api/audios/all',
        successMessage: '✅',
        errorMessage: '❌ Erro ao deletar áudios',
        refreshFunction: loadAudios
    });
}

async function regenerateAudio(filename) {
    const text = prompt('Digite o texto para regenerar este áudio:');
    if (!text) return;

    // Get language from selector if available, otherwise default to Portuguese
    const audioLanguageElement = document.getElementById('audioLanguage');
    const language = audioLanguageElement ? audioLanguageElement.value : 'pt';

    try {
        const response = await fetch(`/api/audios/${filename}/regenerate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                text,
                language: language
            })
        });
        const data = await response.json();

        if (data.success) {
            showAlert('✅ Regeneração iniciada! O áudio será atualizado em breve.', 'success');
            setTimeout(() => loadAudios(), 5000);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('❌ Erro ao conectar com o servidor', 'error');
        console.error('Error:', error);
    }
}

async function stopGeneration() {
    if (!confirm('⚠️ Tem certeza que deseja parar a geração atual? Isso cancelará todo o processo.')) {
        return;
    }
    try {
        const response = await fetch('/api/generation/stop', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showAlert('⛔ Geração cancelada com sucesso!', 'success');
            if (typeof stopPolling === 'function') stopPolling();
            document.getElementById('stopBtn').style.display = 'none';
        } else {
            showAlert('❌ Erro ao parar geração: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('❌ Erro ao conectar com o servidor', 'error');
        console.error('Error:', error);
    }
}

async function stopImageGeneration() {
    if (!confirm('⚠️ Tem certeza que deseja parar a geração da imagem atual?')) {
        return;
    }
    try {
        const response = await fetch('/api/generation/stop', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showAlert('⛔ Geração de imagem cancelada com sucesso!', 'success');
            document.getElementById('stopImageBtn').style.display = 'none';
            handleImageGenerationFailureCleanup();
        } else {
            showAlert('❌ Erro ao parar geração da imagem: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('❌ Erro ao conectar com o servidor', 'error');
        console.error('Error:', error);
    }
}

async function loadVideos() {
    try {
        console.log('[DEBUG] Loading videos...');
        const response = await fetch('/api/videos');
        
        if (!response.ok) {
            console.error('[ERROR] Response not OK:', response.status, response.statusText);
            showAlert('❌ Erro ao carregar vídeos: ' + response.statusText, 'error');
            renderInto('videoGrid', videosEmptyState());
            return;
        }
        
        const data = await response.json();
        console.log('[DEBUG] Videos response:', data);
        
        if (data.success) {
            console.log('[DEBUG] Found', data.videos ? data.videos.length : 0, 'videos');
            if (data.videos && data.videos.length > 0) {
                const html = data.videos.map(videoCard).join('');
                renderInto('videoGrid', html);
            } else {
                console.log('[DEBUG] No videos found, showing empty state');
                renderInto('videoGrid', videosEmptyState());
            }
        } else {
            console.error('[ERROR] Error loading videos:', data.error);
            showAlert('❌ Erro ao carregar vídeos: ' + (data.error || 'Erro desconhecido'), 'error');
            renderInto('videoGrid', videosEmptyState());
        }
    } catch (error) {
        console.error('[ERROR] Exception loading videos:', error);
        showAlert('❌ Erro ao conectar com o servidor para carregar vídeos: ' + error.message, 'error');
        renderInto('videoGrid', videosEmptyState());
    }
}

async function loadImages() {
    try {
        const response = await fetch('/api/images');
        const data = await response.json();
        if (data.success) {
            const html = data.images.length === 0
                ? imagesEmptyState()
                : data.images.map(imageCard).join('');
            renderInto('imageGrid', html);
        }
    } catch (error) {
        console.error('Erro ao carregar imagens:', error);
    }
}

async function performDeleteOperation(config) {
    const { confirmMessage, apiEndpoint, successMessage, errorMessage, refreshFunction } = config;
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    try {
        const response = await fetch(apiEndpoint, { method: 'DELETE' });
        const data = await response.json();
        
        if (data.success) {
            const message = data.deleted_count 
                ? `${successMessage} ${data.deleted_count} item(s) deletado(s) com sucesso!`
                : successMessage;
            showAlert(message, 'success');
            refreshFunction();
        } else {
            showAlert(`${errorMessage}: ${data.error}`, 'error');
        }
    } catch (error) {
        showAlert(errorMessage, 'error');
        console.error('Erro:', error);
    }
}

async function deleteImage(filename) {
    await performDeleteOperation({
        confirmMessage: `Tem certeza que deseja deletar "${filename}"?`,
        apiEndpoint: `/api/images/${filename}`,
        successMessage: '✅ Imagem deletada com sucesso!',
        errorMessage: '❌ Erro ao deletar imagem',
        refreshFunction: loadImages
    });
}

async function deleteAllImages() {
    await performDeleteOperation({
        confirmMessage: '⚠️ Tem certeza que deseja DELETAR TODAS AS IMAGENS? Esta ação não pode ser desfeita!',
        apiEndpoint: '/api/images/all',
        successMessage: '✅',
        errorMessage: '❌ Erro ao deletar imagens',
        refreshFunction: loadImages
    });
}

function showAlert(message, type) {
    const alerts = document.getElementById('alerts');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    alerts.appendChild(alert);
    setTimeout(() => { alert.remove(); }, 5000);
}

function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById(`tab-${tabName}`).classList.add('active');
    const tabs = Array.from(document.querySelectorAll('.tabs .tab'));
    const matching = tabs.find(btn => {
        const handler = btn.getAttribute('onclick') || '';
        return handler.includes(`showTab('${tabName}')`);
    });
    if (matching) matching.classList.add('active');
    if (tabName === 'videos') {
        loadVideos();
    } else if (tabName === 'images') {
        loadImages();
    } else if (tabName === 'audio') {
        loadAudios();
    }
}

// currentReviewData is now in paragraph-review.js

// English Export Modal Functions
function openEnglishModal(folder) {
    document.getElementById('englishModalFolder').value = folder;
    document.getElementById('englishNarrationText').value = '';
    // Reset button states and ensure visibility
    const analyzeBtn = document.getElementById('englishExportBtn');
    const directBtn = document.getElementById('englishExportDirectBtn');
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = 'Gerar com Análise';
        analyzeBtn.style.display = 'inline-block';
        analyzeBtn.style.visibility = 'visible';
    }
    if (directBtn) {
        directBtn.disabled = false;
        directBtn.textContent = 'Gerar sem Análise';
        directBtn.style.display = 'inline-block';
        directBtn.style.visibility = 'visible';
        console.log('Direct button found and made visible');
    } else {
        console.error('englishExportDirectBtn not found!');
    }
    document.getElementById('englishModal').style.display = 'block';
}

function closeEnglishModal() {
    document.getElementById('englishModal').style.display = 'none';
}

function submitEnglishExportDirect() {
    const folder = document.getElementById('englishModalFolder').value;
    const narration = document.getElementById('englishNarrationText').value.trim();
    
    if (!narration) {
        alert('Por favor, cole a narração em inglês.');
        return;
    }
    
    // Disable buttons and show loading
    const directBtn = document.getElementById('englishExportDirectBtn');
    const analyzeBtn = document.getElementById('englishExportBtn');
    directBtn.disabled = true;
    analyzeBtn.disabled = true;
    directBtn.textContent = 'Gerando...';
    
    // Generate directly without analysis
    alert('Geração do vídeo em inglês iniciada! Aguarde alguns minutos...');
    proceedWithExport(folder, narration, 'en', []);
    closeEnglishModal();
    
    // Re-enable buttons after a delay (in case of error)
    setTimeout(() => {
        directBtn.disabled = false;
        analyzeBtn.disabled = false;
        directBtn.textContent = 'Gerar sem Análise';
    }, 2000);
}

function submitEnglishExport() {
    const folder = document.getElementById('englishModalFolder').value;
    const narration = document.getElementById('englishNarrationText').value.trim();
    
    if (!narration) {
        alert('Por favor, cole a narração em inglês.');
        return;
    }
    
    // Disable buttons and show loading
    const submitBtn = document.getElementById('englishExportBtn');
    const directBtn = document.getElementById('englishExportDirectBtn');
    submitBtn.disabled = true;
    directBtn.disabled = true;
    submitBtn.textContent = 'Analisando...';
    
    // First, analyze and get suggestions
    fetch(`/api/videos/${folder}/export-english`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            narration_en: narration,
            mode: 'review'
        })
    })
    .then(res => res.json())
    .then(data => {
        submitBtn.disabled = false;
        directBtn.disabled = false;
        submitBtn.textContent = 'Gerar com Análise';
        
        console.log('Analysis response:', data);
        
        if (data.success) {
            // Always show review modal if we have paragraphs data
            if (data.paragraphs && Array.isArray(data.paragraphs) && data.paragraphs.length > 0) {
                console.log(`Showing review modal with ${data.paragraphs.length} paragraphs`);
                currentReviewData = {
                    folder: folder,
                    narration: narration,
                    language: 'en',
                    paragraphs: data.paragraphs,
                    portuguese_paragraphs: data.portuguese_paragraphs || []
                };
                showReviewModal(data.paragraphs, 'en', data.portuguese_paragraphs || [], folder, data.total_pt_duration, data.total_current_duration);
                closeEnglishModal();
            } else {
                // No paragraphs data - proceed directly
                console.log('No paragraphs data, proceeding directly');
                alert('Análise concluída. Iniciando geração do vídeo...');
                proceedWithExport(folder, narration, 'en', []);
            }
        } else {
            alert('Erro: ' + (data.error || 'Erro desconhecido'));
        }
    })
    .catch(err => {
        alert('Erro ao analisar: ' + err.message);
        submitBtn.disabled = false;
        directBtn.disabled = false;
        submitBtn.textContent = 'Gerar com Análise';
    });
}

// Portuguese Export Modal Functions
function openPortugueseModal(folder) {
    document.getElementById('portugueseModalFolder').value = folder;
    document.getElementById('portugueseNarrationText').value = '';
    const exportBtn = document.getElementById('portugueseExportBtn');
    if (exportBtn) {
        exportBtn.disabled = false;
        exportBtn.textContent = 'Gerar Vídeo';
        exportBtn.style.display = 'inline-block';
        exportBtn.style.visibility = 'visible';
    }
    document.getElementById('portugueseModal').style.display = 'block';
}

function closePortugueseModal() {
    document.getElementById('portugueseModal').style.display = 'none';
}

function submitPortugueseExport() {
    const folder = document.getElementById('portugueseModalFolder').value;
    const narration = document.getElementById('portugueseNarrationText').value.trim();
    
    if (!narration) {
        alert('Por favor, cole a narração em português.');
        return;
    }
    
    // Disable button and show loading
    const exportBtn = document.getElementById('portugueseExportBtn');
    exportBtn.disabled = true;
    exportBtn.textContent = 'Gerando...';
    
    // Generate directly (no review mode for Portuguese)
    fetch(`/api/videos/${folder}/export-portuguese`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            narration_pt: narration,
            mode: 'apply'
        })
    })
    .then(res => res.json())
    .then(data => {
        exportBtn.disabled = false;
        exportBtn.textContent = 'Gerar Vídeo';
        
        if (data.success) {
            alert('✅ Geração do vídeo em português iniciada! Aguarde alguns minutos...');
            closePortugueseModal();
            // Refresh video list after delay
            setTimeout(() => loadVideos(), 5000);
        } else {
            alert('Erro: ' + (data.error || 'Erro desconhecido'));
        }
    })
    .catch(err => {
        exportBtn.disabled = false;
        exportBtn.textContent = 'Gerar Vídeo';
        alert('Erro ao exportar: ' + err.message);
    });
}

// Spanish Export Modal Functions
function openSpanishModal(folder) {
    document.getElementById('spanishModalFolder').value = folder;
    document.getElementById('spanishNarrationText').value = '';
    // Reset button states and ensure visibility
    const analyzeBtn = document.getElementById('spanishExportBtn');
    const directBtn = document.getElementById('spanishExportDirectBtn');
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = 'Gerar com Análise';
        analyzeBtn.style.display = 'inline-block';
        analyzeBtn.style.visibility = 'visible';
    }
    if (directBtn) {
        directBtn.disabled = false;
        directBtn.textContent = 'Gerar sem Análise';
        directBtn.style.display = 'inline-block';
        directBtn.style.visibility = 'visible';
        console.log('Direct button found and made visible');
    } else {
        console.error('spanishExportDirectBtn not found!');
    }
    document.getElementById('spanishModal').style.display = 'block';
}

function closeSpanishModal() {
    document.getElementById('spanishModal').style.display = 'none';
}

function submitSpanishExportDirect() {
    const folder = document.getElementById('spanishModalFolder').value;
    const narration = document.getElementById('spanishNarrationText').value.trim();
    
    if (!narration) {
        alert('Por favor, cole a narração em espanhol.');
        return;
    }
    
    // Disable buttons and show loading
    const directBtn = document.getElementById('spanishExportDirectBtn');
    const analyzeBtn = document.getElementById('spanishExportBtn');
    directBtn.disabled = true;
    analyzeBtn.disabled = true;
    directBtn.textContent = 'Gerando...';
    
    // Generate directly without analysis
    alert('Geração do vídeo em espanhol iniciada! Aguarde alguns minutos...');
    proceedWithExport(folder, narration, 'es', []);
    closeSpanishModal();
    
    // Re-enable buttons after a delay (in case of error)
    setTimeout(() => {
        directBtn.disabled = false;
        analyzeBtn.disabled = false;
        directBtn.textContent = 'Gerar sem Análise';
    }, 2000);
}

function submitSpanishExport() {
    const folder = document.getElementById('spanishModalFolder').value;
    const narration = document.getElementById('spanishNarrationText').value.trim();
    
    if (!narration) {
        alert('Por favor, cole a narração em espanhol.');
        return;
    }
    
    // Disable buttons and show loading
    const submitBtn = document.getElementById('spanishExportBtn');
    const directBtn = document.getElementById('spanishExportDirectBtn');
    submitBtn.disabled = true;
    directBtn.disabled = true;
    submitBtn.textContent = 'Analisando...';
    
    // First, analyze and get suggestions
    fetch(`/api/videos/${folder}/export-spanish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            narration_es: narration,
            mode: 'review'
        })
    })
    .then(res => res.json())
    .then(data => {
        submitBtn.disabled = false;
        directBtn.disabled = false;
        submitBtn.textContent = 'Gerar com Análise';
        
        if (data.success) {
            // Always show review modal if we have paragraphs data
            if (data.paragraphs && Array.isArray(data.paragraphs) && data.paragraphs.length > 0) {
                currentReviewData = {
                    folder: folder,
                    narration: narration,
                    language: 'es',
                    paragraphs: data.paragraphs,
                    portuguese_paragraphs: data.portuguese_paragraphs || []
                };
                showReviewModal(data.paragraphs, 'es', data.portuguese_paragraphs || [], folder, data.total_pt_duration, data.total_current_duration);
                closeSpanishModal();
            } else {
                // No paragraphs data - proceed directly
                alert('Análise concluída. Iniciando geração do vídeo...');
                proceedWithExport(folder, narration, 'es', []);
            }
        } else {
            alert('Erro: ' + (data.error || 'Erro desconhecido'));
        }
    })
    .catch(err => {
        alert('Erro ao analisar: ' + err.message);
        submitBtn.disabled = false;
        directBtn.disabled = false;
        submitBtn.textContent = 'Gerar com Análise';
    });
}

// Shorts Generation Function for specific language
function generateShortsForLanguage(folder, language) {
    const folderHash = folder.replace(/[^a-zA-Z0-9]/g, '-').substring(0, 50);
    const btn = document.getElementById(`shorts-btn-${language}-${folderHash}`);
    
    if (!btn) {
        alert('Erro: Botão não encontrado');
        return;
    }
    
    // Disable button and show loading
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Gerando...';
    btn.style.opacity = '0.6';
    
    const languageNames = {'pt': 'Português', 'en': 'English', 'es': 'Español'};
    const languageEmoji = {'pt': '🇧🇷', 'en': '🇬🇧', 'es': '🇪🇸'};
    
    // Call API
    fetch(`/api/videos/${encodeURIComponent(folder)}/shorts/${language}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        btn.disabled = false;
        btn.textContent = originalText;
        btn.style.opacity = '1';
        
        if (data.success) {
            const count = data.count;
            const langName = languageNames[language];
            
            let message = `✅ ${count} shorts ${langName} gerados com sucesso!\n\n`;
            message += `${languageEmoji[language]} ${langName}: ${count} shorts\n`;
            message += `\nOs shorts foram salvos em shorts/${language}/ dentro do vídeo.`;
            
            alert(message);
            
            // Reload videos to show updated list
            loadVideos();
        } else {
            alert('Erro ao gerar shorts: ' + (data.error || 'Erro desconhecido'));
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.textContent = originalText;
        btn.style.opacity = '1';
        alert('Erro ao gerar shorts: ' + err.message);
    });
}

// Shorts Generation Function (all languages - kept for backward compatibility)
function generateShorts(folder) {
    const folderHash = folder.replace(/[^a-zA-Z0-9]/g, '-').substring(0, 50);
    const btn = document.getElementById(`shorts-btn-${folderHash}`);
    
    if (!btn) {
        alert('Erro: Botão não encontrado');
        return;
    }
    
    // Disable button and show loading
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Gerando Shorts...';
    btn.style.opacity = '0.6';
    
    // Call API
    fetch(`/api/videos/${encodeURIComponent(folder)}/shorts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        btn.disabled = false;
        btn.textContent = originalText;
        btn.style.opacity = '1';
        
        if (data.success) {
            const total = data.counts.total;
            const ptCount = data.counts.pt;
            const enCount = data.counts.en;
            const esCount = data.counts.es;
            
            let message = `✅ ${total} shorts gerados com sucesso!\n\n`;
            if (ptCount > 0) message += `🇧🇷 Português: ${ptCount}\n`;
            if (enCount > 0) message += `🇬🇧 Inglês: ${enCount}\n`;
            if (esCount > 0) message += `🇪🇸 Espanhol: ${esCount}\n`;
            
            message += `\nOs shorts foram salvos na pasta "shorts" dentro do vídeo.`;
            
            alert(message);
            
            // Reload videos to show updated list
            loadVideos();
        } else {
            alert('Erro ao gerar shorts: ' + (data.error || 'Erro desconhecido'));
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.textContent = originalText;
        btn.style.opacity = '1';
        alert('Erro ao gerar shorts: ' + err.message);
    });
}

// Close modal when clicking outside
window.onclick = function(event) {
    const englishModal = document.getElementById('englishModal');
    const spanishModal = document.getElementById('spanishModal');
    // Note: reviewModal does NOT close when clicking outside (user requirement)
    if (event.target == englishModal) {
        closeEnglishModal();
    }
    if (event.target == spanishModal) {
        closeSpanishModal();
    }
    // reviewModal is excluded - it only closes via Cancel button or X button
}

// Review Modal Functions moved to paragraph-review.js
