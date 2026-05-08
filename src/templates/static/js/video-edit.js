/**
 * Video editing functionality
 * Handles editing of video image prompts and audio segments
 */

let currentEditingVideo = null;
let currentVideoEditData = null;
let isGenerating = false; // Changed from isImageGenerating to isGenerating

/**
 * Disable all regenerate buttons (image and audio)
 */
function disableAllRegenerateButtons() {
    const imageButtons = document.querySelectorAll('button[onclick*="updateImagePrompt"]');
    const audioButtons = document.querySelectorAll('button[onclick*="updateAudioSegment"]');
    const allButtons = [...imageButtons, ...audioButtons];
    allButtons.forEach(button => {
        button.disabled = true;
        button.style.opacity = '0.6';
        button.style.cursor = 'not-allowed';
    });
    
    // Also disable regenerate all buttons
    const regenerateAllButtons = document.querySelectorAll('button[onclick*="regenerateAllAudios"]');
    regenerateAllButtons.forEach(button => {
        button.disabled = true;
        button.style.opacity = '0.6';
        button.style.cursor = 'not-allowed';
    });
    
    // Disable batch regenerate button
    const regenerateSelectedBtn = document.getElementById('regenerateSelectedBtn');
    if (regenerateSelectedBtn) {
        regenerateSelectedBtn.disabled = true;
        regenerateSelectedBtn.style.opacity = '0.6';
        regenerateSelectedBtn.style.cursor = 'not-allowed';
    }
}

/**
 * Enable all regenerate buttons (image and audio)
 */
function enableAllRegenerateButtons() {
    const imageButtons = document.querySelectorAll('button[onclick*="updateImagePrompt"]');
    const audioButtons = document.querySelectorAll('button[onclick*="updateAudioSegment"]');
    const allButtons = [...imageButtons, ...audioButtons];
    allButtons.forEach(button => {
        button.disabled = false;
        button.style.opacity = '1';
        button.style.cursor = 'pointer';
    });
    
    // Also enable regenerate all buttons
    const regenerateAllButtons = document.querySelectorAll('button[onclick*="regenerateAllAudios"]');
    regenerateAllButtons.forEach(button => {
        button.disabled = false;
        button.style.opacity = '1';
        button.style.cursor = 'pointer';
    });
    
    // Enable batch regenerate button
    const regenerateSelectedBtn = document.getElementById('regenerateSelectedBtn');
    if (regenerateSelectedBtn) {
        regenerateSelectedBtn.disabled = false;
        regenerateSelectedBtn.style.opacity = '1';
        regenerateSelectedBtn.style.cursor = 'pointer';
    }
}

/**
 * Open the video edit modal and load video data
 * @param {string} folder - Video folder name
 */
async function editVideo(folder) {
    if (typeof folder === 'undefined' || folder === null) {
        console.error('editVideo called without folder parameter');
        return;
    }
    currentEditingVideo = folder;
    document.getElementById('videoEditModal').style.display = 'flex';
    // Disable body scroll
    document.body.style.overflow = 'hidden';
    document.getElementById('videoEditContent').innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Carregando dados do vídeo...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/videos/${encodeURIComponent(folder)}/edit`);
        const data = await response.json();
        
        if (data.success) {
            currentVideoEditData = data;
            await renderVideoEditModal(data);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
            closeVideoEditModal();
        }
    } catch (error) {
        showAlert('❌ Erro ao carregar dados do vídeo: ' + error.message, 'error');
        closeVideoEditModal();
    }
}

/**
 * Close the video edit modal
 */
function closeVideoEditModal() {
    document.getElementById('videoEditModal').style.display = 'none';
    // Re-enable body scroll
    document.body.style.overflow = '';
    // Reset generation state
    isGenerating = false;
    enableAllRegenerateButtons();
    currentEditingVideo = null;
    currentVideoEditData = null;
}

/**
 * Switch between tabs in the video edit modal
 * @param {string} tabName - Tab name ('images', 'audios-pt', 'audios-en', or 'audios-es')
 */
function showVideoEditTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('#videoEditContent .tab-content').forEach(content => {
        content.style.display = 'none';
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('#videoEditContent .tab').forEach(tab => {
        tab.classList.remove('active');
        tab.style.color = '#666';
        tab.style.borderBottomColor = 'transparent';
    });
    
    // Show selected tab content
    const selectedContent = document.getElementById(`video-edit-tab-${tabName}`);
    if (selectedContent) {
        selectedContent.style.display = 'block';
    }
    
    // Add active class to selected tab
    const tabs = Array.from(document.querySelectorAll('#videoEditContent .tab'));
    const matching = tabs.find(btn => {
        const handler = btn.getAttribute('onclick') || '';
        return handler.includes(`showVideoEditTab('${tabName}')`);
    });
    if (matching) {
        matching.classList.add('active');
        matching.style.color = '#667eea';
        matching.style.borderBottomColor = '#667eea';
    }
}

/**
 * Render the video edit modal with image prompts and audio segments
 * @param {Object} data - Video edit data from API
 */
async function renderVideoEditModal(data) {
    const content = document.getElementById('videoEditContent');
    
    // Image prompts section - render with loading placeholders first
    const imagePromptsHtml = data.image_prompts.map((prompt, index) => {
        const imageExists = data.image_files[index] && data.image_files[index].exists;
        const imageNumber = index + 1; // 1-based index
        
        return `
        ${index === 0 ? `
        <div style="margin-bottom: 10px; text-align: center;">
            <button onclick="showInsertImageDialog(${imageNumber})" class="btn btn-small" style="background: #28a745; width: auto; padding: 8px 16px;">
                ➕ Inserir Imagem Antes da Imagem ${imageNumber}
            </button>
        </div>
        ` : ''}
        <div class="edit-item" style="margin-bottom: 10px; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #fff;">
            <div style="display: flex; gap: 10px; align-items: flex-start; flex-wrap: nowrap;">
                <div style="flex: 0 0 33.333%; max-width: 33.333%;">
                    ${imageExists ? 
                        `<div id="thumb-container-${index}" style="position: relative;">
                            <div style="width: 100%; min-height: 120px; background: #f0f0f0; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999; border: 1px solid #ddd;">
                                <span>Carregando...</span>
                            </div>
                        </div>` : 
                        '<div style="width: 100%; min-height: 120px; background: #f5f5f5; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999; border: 1px solid #ddd;">Imagem não encontrada</div>'}
                </div>
                <div style="flex: 0 0 66.666%; max-width: 66.666%;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <input type="checkbox" id="image-checkbox-${index}" class="image-checkbox" data-image-index="${imageNumber}" style="width: 18px; height: 18px; cursor: pointer;">
                        <h4 style="margin: 0; color: #333; font-size: 15px;">🖼️ Imagem ${imageNumber}</h4>
                    </div>
                    <label style="display: block; margin-bottom: 6px; font-weight: bold; color: #333; font-size: 13px;">Prompt:</label>
                    <textarea 
                        id="image-prompt-${index}" 
                        style="width: 100%; min-height: 120px; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; font-size: 13px; resize: vertical; box-sizing: border-box; line-height: 1.4;"
                    >${escapeHtml(prompt)}</textarea>
                    <div style="display: flex; gap: 8px; margin-top: 6px;">
                        <button onclick="updateImagePrompt(${imageNumber})" class="btn btn-small" style="flex: 1; background: #007bff; padding: 6px; border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 13px;">
                            🔄 Regera Imagem
                        </button>
                        <button onclick="deleteImage(${imageNumber})" class="btn btn-small" style="background: #dc3545; padding: 4px 8px; border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 11px; white-space: nowrap;">
                            🗑️
                        </button>
                    </div>
                </div>
            </div>
        </div>
        <div style="margin-bottom: 10px; text-align: center;">
            <button onclick="showInsertImageDialog(${imageNumber + 1})" class="btn btn-small" style="background: #28a745; width: auto; padding: 8px 16px;">
                ➕ Inserir Imagem Após a Imagem ${imageNumber}
            </button>
        </div>
        `;
    }).join('');
    
    // Audio segments section for each language
    const renderAudioSegmentsHtml = (segments, segmentFiles, language) => {
        if (!segments || segments.length === 0) {
            return '<div style="margin: 20px 0; padding: 30px; text-align: center; background: #f9f9f9; border: 2px dashed #ddd; border-radius: 8px;"><p style="font-size: 16px; color: #666;">Nenhum áudio encontrado para este idioma.</p></div>';
        }
        
        return segments.map((segment, index) => `
            <div class="edit-item" style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
                <div style="flex: 1;">
                    <h4>🎙️ Áudio ${index + 1}</h4>
                    ${segmentFiles[index] && segmentFiles[index].exists ? 
                        `<audio controls style="width: 100%; margin-bottom: 10px;">
                            <source src="${segmentFiles[index].path}" type="audio/wav">
                        </audio>` : 
                        '<p style="color: #999;">Áudio não encontrado</p>'}
                    <textarea 
                        id="audio-segment-${language}-${index}" 
                        style="width: 100%; min-height: 100px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;"
                    >${escapeHtml(segment)}</textarea>
                    <button onclick="updateAudioSegment(${index}, '${language}')" class="btn btn-small" style="margin-top: 10px; background: #007bff;">
                        🔄 Regera Áudio
                    </button>
                </div>
            </div>
        `).join('');
    };
    
    const audioSegmentsHtmlPt = renderAudioSegmentsHtml(data.audio_segments_pt || data.audio_segments || [], data.audio_segment_files_pt || data.audio_segment_files || [], 'pt');
    const audioSegmentsHtmlEn = renderAudioSegmentsHtml(data.audio_segments_en || [], data.audio_segment_files_en || [], 'en');
    const audioSegmentsHtmlEs = renderAudioSegmentsHtml(data.audio_segments_es || [], data.audio_segment_files_es || [], 'es');
    
    content.innerHTML = `
        <div class="tabs" style="display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 2px solid #e0e0e0;">
            <button class="tab active" onclick="showVideoEditTab('images')" style="padding: 15px 30px; background: none; border: none; font-size: 16px; font-weight: 600; color: #667eea; cursor: pointer; border-bottom: 3px solid #667eea; transition: all 0.3s;">🖼️ Imagens</button>
            <button class="tab" onclick="showVideoEditTab('audios-pt')" style="padding: 15px 30px; background: none; border: none; font-size: 16px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; transition: all 0.3s;">🎙️ Áudios (PT)</button>
            <button class="tab" onclick="showVideoEditTab('audios-en')" style="padding: 15px 30px; background: none; border: none; font-size: 16px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; transition: all 0.3s;">🎙️ Áudios (EN)</button>
            <button class="tab" onclick="showVideoEditTab('audios-es')" style="padding: 15px 30px; background: none; border: none; font-size: 16px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; transition: all 0.3s;">🎙️ Áudios (ES)</button>
        </div>
        
        <div id="video-edit-tab-images" class="tab-content" style="display: block;">
            <div style="margin-bottom: 20px; padding: 15px; background: #f9f9f9; border: 1px solid #ddd; border-radius: 8px;">
                <label style="display: block; margin-bottom: 8px; font-weight: bold; color: #333;">🚫 Prompt Negativo (aplicado a todas as imagens):</label>
                <textarea 
                    id="negative-prompt-global" 
                    style="width: 100%; min-height: 80px; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; font-size: 13px; resize: vertical; box-sizing: border-box; line-height: 1.5;"
                >${escapeHtml(data.negative_prompt || '')}</textarea>
            </div>
            <div id="imagePromptsSection">
                ${imagePromptsHtml || `
                <div style="margin: 20px 0; padding: 30px; text-align: center; background: #f9f9f9; border: 2px dashed #ddd; border-radius: 8px;">
                    <p style="font-size: 16px; color: #666; margin-bottom: 15px;">Nenhuma imagem encontrada neste vídeo.</p>
                    <button onclick="showInsertImageDialog(1)" class="btn btn-small" style="background: #28a745; width: auto; padding: 8px 16px; margin-top: 10px;">
                        ➕ Criar Primeira Imagem
                    </button>
                </div>
                `}
            </div>
            ${imagePromptsHtml ? `
            <div style="margin-top: 20px; padding: 15px; background: #f0f8ff; border: 2px solid #007bff; border-radius: 8px; text-align: center;">
                <button onclick="regenerateSelectedImages()" id="regenerateSelectedBtn" class="btn" style="background: #28a745; width: auto; padding: 10px 20px; font-size: 16px; font-weight: bold;">
                    🔄 Regerar Imagens Selecionadas
                </button>
                <p style="margin-top: 10px; color: #666; font-size: 13px;">
                    Selecione as imagens usando as caixas de seleção acima e clique no botão para regenerar todas de uma vez (modelo carregado apenas uma vez).
                </p>
            </div>
            ` : ''}
        </div>
        
        <div id="video-edit-tab-audios-pt" class="tab-content" style="display: none;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="margin: 0;">🎙️ Segmentos de Áudio (Português)</h3>
                <button onclick="regenerateAllAudios('pt')" class="btn btn-small" style="background: #28a745; width: auto; padding: 8px 16px;">
                    🔄 Regera Todos os Áudios
                </button>
            </div>
            <div id="audioSegmentsSectionPt">
                ${audioSegmentsHtmlPt}
            </div>
        </div>
        
        <div id="video-edit-tab-audios-en" class="tab-content" style="display: none;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="margin: 0;">🎙️ Segmentos de Áudio (English)</h3>
                <button onclick="regenerateAllAudios('en')" class="btn btn-small" style="background: #28a745; width: auto; padding: 8px 16px;">
                    🔄 Regera Todos os Áudios
                </button>
            </div>
            <div id="audioSegmentsSectionEn">
                ${audioSegmentsHtmlEn}
            </div>
        </div>
        
        <div id="video-edit-tab-audios-es" class="tab-content" style="display: none;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="margin: 0;">🎙️ Segmentos de Áudio (Español)</h3>
                <button onclick="regenerateAllAudios('es')" class="btn btn-small" style="background: #28a745; width: auto; padding: 8px 16px;">
                    🔄 Regera Todos os Áudios
                </button>
            </div>
            <div id="audioSegmentsSectionEs">
                ${audioSegmentsHtmlEs}
            </div>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background: #f0f0f0; border-radius: 8px;">
            <button onclick="mergeVideo()" class="btn" style="width: 100%; background: #28a745; font-size: 18px; margin-bottom: 15px;">
                🎬 Mesclar Vídeo Novamente (Regera animated.mp4)
            </button>
            <p style="margin-top: 10px; color: #666; text-align: center; margin-bottom: 15px;">
                Regera o vídeo animated.mp4 a partir das imagens e mescla com áudio PT, 
                <p style="font-size: 12px; text-align: center;">
                *usa narration.wav existente, se não existe cria com audio segmets, se audio segments não existe, cria
                </p>
            </p>
            
            ${(data.has_animated && (data.has_pt_narration || data.has_en_narration || data.has_es_narration)) ? `
                <div style="border-top: 2px solid #ddd; padding-top: 15px; margin-top: 15px;">
                    <p style="color: #666; text-align: center; margin-bottom: 10px; font-weight: bold;">
                        Mesclar reutilizando animated.mp4 existente, usa narration.wav existente
                        <p style="font-size: 12px; text-align: center;">
                        *usa narration.wav existente, se não existe cria com audio segmets, se audio segments não existe, cria
                        </p>
                    </p>
                    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        ${data.has_pt_narration ? `
                            <button onclick="mergeVideoLanguage('pt')" class="btn" style="flex: 1; min-width: 150px; background: #007bff; font-size: 16px;">
                                🎬 Mesclar Vídeo Novamente (PT)
                            </button>
                        ` : ''}
                        ${data.has_en_narration ? `
                            <button onclick="mergeVideoLanguage('en')" class="btn" style="flex: 1; min-width: 150px; background: #007bff; font-size: 16px;">
                                🎬 Mesclar Vídeo Novamente (EN)
                            </button>
                        ` : ''}
                        ${data.has_es_narration ? `
                            <button onclick="mergeVideoLanguage('es')" class="btn" style="flex: 1; min-width: 150px; background: #007bff; font-size: 16px;">
                                🎬 Mesclar Vídeo Novamente (ES)
                            </button>
                        ` : ''}
                    </div>
                    <p style="margin-top: 10px; color: #666; text-align: center; font-size: 12px;">
                        Reutiliza o animated.mp4 existente (mais rápido - não regera o vídeo)
                    </p>
                </div>
            ` : ''}
            
            ${(data.has_pt_final_narration || data.has_en_final_narration || data.has_es_final_narration) ? `
                <div style="border-top: 2px solid #ddd; padding-top: 15px; margin-top: 15px;">
                    <p style="color: #666; text-align: center; margin-bottom: 10px; font-weight: bold;">
                        Deletar Narração Final (mantém apenas segmentos):
                    </p>
                    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        ${data.has_pt_final_narration ? `
                            <button onclick="deleteFinalNarration('pt')" class="btn" style="flex: 1; min-width: 150px; background: #dc3545; font-size: 16px;">
                                🗑️ Deletar Narração Final (PT)
                            </button>
                        ` : ''}
                        ${data.has_en_final_narration ? `
                            <button onclick="deleteFinalNarration('en')" class="btn" style="flex: 1; min-width: 150px; background: #dc3545; font-size: 16px;">
                                🗑️ Deletar Narração Final (EN)
                            </button>
                        ` : ''}
                        ${data.has_es_final_narration ? `
                            <button onclick="deleteFinalNarration('es')" class="btn" style="flex: 1; min-width: 150px; background: #dc3545; font-size: 16px;">
                                🗑️ Deletar Narração Final (ES)
                            </button>
                        ` : ''}
                    </div>
                    <p style="margin-top: 10px; color: #666; text-align: center; font-size: 12px;">
                        Deleta narration_0.wav, mantendo apenas os segmentos de áudio. O arquivo pode ser regerado ao clicar em Mesclar Novamente.
                    </p>
                </div>
            ` : ''}
        </div>
    `;
    
    // Ensure buttons are enabled when modal content is rendered
    isGenerating = false;
    enableAllRegenerateButtons();
    
    // Load thumbnails sequentially, one at a time
    await loadThumbnailsSequentially(data);
}

/**
 * Load thumbnails sequentially to avoid overwhelming the server
 * @param {Object} data - Video edit data from API
 */
async function loadThumbnailsSequentially(data) {
    for (let index = 0; index < data.image_prompts.length; index++) {
        const imageExists = data.image_files[index] && data.image_files[index].exists;
        
        if (!imageExists) {
            continue;
        }
        
        const thumbUrl = `/api/videos/${encodeURIComponent(data.folder)}/thumb/${index + 1}`;
        const container = document.getElementById(`thumb-container-${index}`);
        
        if (!container) {
            continue;
        }
        
        try {
            // Load image as blob to ensure it's fully loaded
            const response = await fetch(thumbUrl);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const blob = await response.blob();
            const imageUrl = URL.createObjectURL(blob);
            
            // Create and insert the image
            const img = document.createElement('img');
            img.src = imageUrl;
            img.alt = `Thumbnail ${index + 1}`;
            img.style.cssText = 'width: 100%; max-width: 100%; border-radius: 8px; border: 1px solid #eee; display: block; box-shadow: 0 2px 4px rgba(0,0,0,0.1);';
            
            img.onerror = () => {
                container.innerHTML = '<div style="width: 100%; min-height: 120px; background: #f5f5f5; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999; border: 1px solid #ddd;">Erro ao carregar</div>';
                URL.revokeObjectURL(imageUrl);
            };
            
            container.innerHTML = '';
            container.appendChild(img);
            
            // Small delay to prevent overwhelming the server (optional, but helps)
            await new Promise(resolve => setTimeout(resolve, 50));
            
        } catch (error) {
            console.error(`Error loading thumbnail ${index + 1}:`, error);
            container.innerHTML = '<div style="width: 100%; min-height: 150px; background: #f5f5f5; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999; border: 1px solid #ddd;">Erro ao carregar</div>';
        }
    }
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Update an image prompt and regenerate the image
 * @param {number} index - Image index (1-based)
 */
async function updateImagePrompt(index) {
    if (!currentEditingVideo || isGenerating) return;
    
    const promptElement = document.getElementById(`image-prompt-${index - 1}`);
    if (!promptElement) {
        showAlert('❌ Elemento não encontrado', 'error');
        return;
    }
    
    const prompt = promptElement.value;
    if (!prompt) {
        showAlert('❌ Por favor, insira um prompt', 'error');
        return;
    }
    
    // Get negative prompt from the global field
    const negativePromptElement = document.getElementById('negative-prompt-global');
    const negative_prompt = negativePromptElement ? negativePromptElement.value : '';
    
    // Disable all regenerate buttons
    isGenerating = true;
    disableAllRegenerateButtons();
    
    // Show loading state for this specific image
    const container = document.getElementById(`thumb-container-${index - 1}`);
    if (container) {
        container.innerHTML = '<div style="width: 100%; min-height: 120px; background: #f0f0f0; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999; border: 1px solid #ddd;"><span>Gerando...</span></div>';
    }
    
    try {
        // Update prompt
        const updateResponse = await fetch(`/api/videos/${encodeURIComponent(currentEditingVideo)}/update-image-prompt/${index}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, negative_prompt })
        });
        
        const updateData = await updateResponse.json();
        
        if (updateData.success) {
            showAlert(`✅ Imagem ${index} está sendo regerada... Aguarde alguns segundos.`, 'success');
            // Poll for image completion and load only this thumbnail
            await pollAndLoadThumbnail(currentEditingVideo, index - 1);
        } else {
            showAlert('❌ Erro: ' + updateData.error, 'error');
            // Restore previous state on error
            if (container) {
                await loadSingleThumbnail(currentEditingVideo, index - 1);
            }
            // Re-enable buttons on error
            isGenerating = false;
            enableAllRegenerateButtons();
        }
    } catch (error) {
        showAlert('❌ Erro ao atualizar imagem: ' + error.message, 'error');
        // Restore previous state on error
        if (container) {
            await loadSingleThumbnail(currentEditingVideo, index - 1);
        }
        // Re-enable buttons on error
        isGenerating = false;
        enableAllRegenerateButtons();
    }
}

/**
 * Load a single thumbnail by index
 * @param {string} folder - Video folder name
 * @param {number} index - Image index (0-based)
 */
async function loadSingleThumbnail(folder, index) {
    const thumbUrl = `/api/videos/${encodeURIComponent(folder)}/thumb/${index + 1}`;
    const container = document.getElementById(`thumb-container-${index}`);
    
    if (!container) {
        return;
    }
    
    try {
        // Load image as blob to ensure it's fully loaded
        const response = await fetch(thumbUrl);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const blob = await response.blob();
        const imageUrl = URL.createObjectURL(blob);
        
        // Create and insert the image
        const img = document.createElement('img');
        img.src = imageUrl;
        img.alt = `Thumbnail ${index + 1}`;
        img.style.cssText = 'width: 100%; max-width: 100%; border-radius: 8px; border: 1px solid #eee; display: block; box-shadow: 0 2px 4px rgba(0,0,0,0.1);';
        
        img.onerror = () => {
            container.innerHTML = '<div style="width: 100%; min-height: 120px; background: #f5f5f5; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999; border: 1px solid #ddd;">Erro ao carregar</div>';
            URL.revokeObjectURL(imageUrl);
        };
        
        container.innerHTML = '';
        container.appendChild(img);
        
    } catch (error) {
        console.error(`Error loading thumbnail ${index + 1}:`, error);
        container.innerHTML = '<div style="width: 100%; min-height: 120px; background: #f5f5f5; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999; border: 1px solid #ddd;">Erro ao carregar</div>';
    }
}

/**
 * Poll for image file existence and load thumbnail when ready
 * @param {string} folder - Video folder name
 * @param {number} index - Image index (0-based)
 * @param {number} maxAttempts - Maximum polling attempts (default: 30)
 * @param {number} intervalMs - Polling interval in milliseconds (default: 2000)
 * @param {number} initialDelayMs - Initial delay before starting to poll in milliseconds (default: 40000)
 */
async function pollAndLoadThumbnail(folder, index, maxAttempts = 30, intervalMs = 2000, initialDelayMs = 40000) {
    // Wait for initial delay before starting to poll (image generation takes time)
    await new Promise(resolve => setTimeout(resolve, initialDelayMs));
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        try {
            // Try to load the thumbnail
            const thumbUrl = `/api/videos/${encodeURIComponent(folder)}/thumb/${index + 1}`;
            const response = await fetch(thumbUrl, { method: 'HEAD' });
            
            if (response.ok) {
                // Image exists, load the thumbnail
                await loadSingleThumbnail(folder, index);
                // Re-enable buttons after successful load
                isGenerating = false;
                enableAllRegenerateButtons();
                return;
            }
        } catch (error) {
            // Continue polling on error
        }
        
        // Wait before next attempt
        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
    
    // If we get here, image didn't appear in time
    const container = document.getElementById(`thumb-container-${index}`);
    if (container) {
        container.innerHTML = '<div style="width: 100%; min-height: 120px; background: #f5f5f5; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999; border: 1px solid #ddd;">Timeout ao carregar</div>';
    }
    // Re-enable buttons on timeout
    isGenerating = false;
    enableAllRegenerateButtons();
}

/**
 * Update an audio segment text and regenerate the audio
 * @param {number} index - Audio segment index (0-based)
 * @param {string} language - Language code ('pt', 'en', or 'es')
 */
async function updateAudioSegment(index, language = 'pt') {
    if (!currentEditingVideo || isGenerating) return;
    
    const textElement = document.getElementById(`audio-segment-${language}-${index}`);
    if (!textElement) {
        showAlert('❌ Elemento não encontrado', 'error');
        return;
    }
    
    const text = textElement.value;
    if (!text) {
        showAlert('❌ Por favor, insira o texto do áudio', 'error');
        return;
    }
    
    // Disable all regenerate buttons
    isGenerating = true;
    disableAllRegenerateButtons();
    
    try {
        // Update audio segment
        const updateResponse = await fetch(`/api/videos/${encodeURIComponent(currentEditingVideo)}/update-audio-segment/${index}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, language })
        });
        
        const updateData = await updateResponse.json();
        
        if (updateData.success) {
            showAlert(`✅ Áudio ${index + 1} está sendo regerando... Aguarde alguns segundos.`, 'success');
            // Poll for audio completion and update only this audio segment
            await pollAndLoadAudio(currentEditingVideo, index, language);
        } else {
            showAlert('❌ Erro: ' + updateData.error, 'error');
            // Re-enable buttons on error
            isGenerating = false;
            enableAllRegenerateButtons();
        }
    } catch (error) {
        showAlert('❌ Erro ao atualizar áudio: ' + error.message, 'error');
        // Re-enable buttons on error
        isGenerating = false;
        enableAllRegenerateButtons();
    }
}

/**
 * Load and update a single audio segment
 * @param {string} folder - Video folder name
 * @param {number} index - Audio segment index (0-based)
 * @param {string} language - Language code ('pt', 'en', or 'es')
 */
async function loadSingleAudioSegment(folder, index, language = 'pt') {
    const audioUrl = `/api/videos/${encodeURIComponent(folder)}/audio-segment/${index}?lang=${language}`;
    
    try {
        const response = await fetch(audioUrl);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        // Find the audio container for this segment based on language
        const sectionId = `audioSegmentsSection${language.charAt(0).toUpperCase() + language.slice(1)}`;
        const audioContainer = document.querySelector(`#${sectionId} .edit-item:nth-child(${index + 1})`);
        if (!audioContainer) {
            return;
        }
        
        // Update the audio element
        const audioElement = audioContainer.querySelector('audio');
        if (audioElement) {
            // Reload the audio source
            const source = audioElement.querySelector('source');
            if (source) {
                source.src = audioUrl + '&t=' + Date.now(); // Add timestamp to force reload
                audioElement.load();
            }
        } else {
            // Create new audio element if it doesn't exist
            const h4 = audioContainer.querySelector('h4');
            if (h4 && h4.nextSibling) {
                const audio = document.createElement('audio');
                audio.controls = true;
                audio.style.cssText = 'width: 100%; margin-bottom: 10px;';
                const source = document.createElement('source');
                source.src = audioUrl;
                source.type = 'audio/wav';
                audio.appendChild(source);
                h4.parentNode.insertBefore(audio, h4.nextSibling);
            }
        }
    } catch (error) {
        console.error(`Error loading audio segment ${index + 1}:`, error);
    }
}

/**
 * Poll for audio segment file existence and update when ready
 * @param {string} folder - Video folder name
 * @param {number} index - Audio segment index (0-based)
 * @param {string} language - Language code ('pt', 'en', or 'es')
 * @param {number} maxAttempts - Maximum polling attempts (default: 30)
 * @param {number} intervalMs - Polling interval in milliseconds (default: 2000)
 * @param {number} initialDelayMs - Initial delay before starting to poll in milliseconds (default: 5000)
 */
async function pollAndLoadAudio(folder, index, language = 'pt', maxAttempts = 30, intervalMs = 2000, initialDelayMs = 5000) {
    // Wait for initial delay before starting to poll (audio generation takes time)
    await new Promise(resolve => setTimeout(resolve, initialDelayMs));
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        try {
            // Try to check if audio segment exists
            const audioUrl = `/api/videos/${encodeURIComponent(folder)}/audio-segment/${index}?lang=${language}`;
            const response = await fetch(audioUrl, { method: 'HEAD' });
            
            if (response.ok) {
                // Audio exists, update the audio element
                await loadSingleAudioSegment(folder, index, language);
                // Re-enable buttons after successful load
                isGenerating = false;
                enableAllRegenerateButtons();
                return;
            }
        } catch (error) {
            // Continue polling on error
        }
        
        // Wait before next attempt
        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
    
    // If we get here, audio didn't appear in time
    // Re-enable buttons on timeout
    isGenerating = false;
    enableAllRegenerateButtons();
}

/**
 * Merge video and audio after edits
 */
async function mergeVideo() {
    if (!currentEditingVideo) return;
    
    // Detect which language to use (priority: pt > en > es)
    let language = 'pt';
    if (currentVideoEditData) {
        if (currentVideoEditData.has_pt_narration) {
            language = 'pt';
        } else if (currentVideoEditData.has_en_narration) {
            language = 'en';
        } else if (currentVideoEditData.has_es_narration) {
            language = 'es';
        }
    }
    
    const langNames = {
        'pt': 'português',
        'en': 'inglês',
        'es': 'espanhol'
    };
    const langName = langNames[language] || language;
    
    if (!confirm(`⚠️ Isso irá regerar o vídeo em ${langName} com as alterações. Isso pode levar alguns minutos. Continuar?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/videos/${encodeURIComponent(currentEditingVideo)}/merge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language: language })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`✅ Vídeo em ${langName} está sendo mesclado... Isso pode levar alguns minutos.`, 'success');
            // Close modal and refresh video list after delay
            setTimeout(() => {
                closeVideoEditModal();
                if (typeof loadVideos === 'function') {
                    loadVideos();
                }
            }, 3000);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('❌ Erro ao mesclar vídeo: ' + error.message, 'error');
    }
}

/**
 * Merge video and audio for a specific language, reusing existing animated.mp4
 * @param {string} language - Language code ('pt', 'en', or 'es')
 */
async function mergeVideoLanguage(language) {
    if (!currentEditingVideo) return;
    
    const langNames = {
        'pt': 'português',
        'en': 'inglês',
        'es': 'espanhol'
    };
    const langName = langNames[language] || language;
    
    if (!confirm(`⚠️ Isso irá mesclar o vídeo em ${langName} reutilizando o animated.mp4 existente. Isso é mais rápido pois não regera o vídeo. Continuar?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/videos/${encodeURIComponent(currentEditingVideo)}/merge/${language}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`✅ Vídeo em ${langName} está sendo mesclado... Isso é mais rápido pois reutiliza o animated.mp4 existente.`, 'success');
            // Close modal and refresh video list after delay
            setTimeout(() => {
                closeVideoEditModal();
                if (typeof loadVideos === 'function') {
                    loadVideos();
                }
            }, 3000);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('❌ Erro ao mesclar vídeo: ' + error.message, 'error');
    }
}

/**
 * Delete final narration file for a specific language, keeping only audio segments
 * @param {string} language - Language code ('pt', 'en', or 'es')
 */
async function deleteFinalNarration(language) {
    if (!currentEditingVideo) return;
    
    const langNames = {
        'pt': 'português',
        'en': 'inglês',
        'es': 'espanhol'
    };
    const langName = langNames[language] || language;
    
    if (!confirm(`⚠️ Isso irá deletar o arquivo final de narração (narration_0.wav) em ${langName}, mantendo apenas os segmentos de áudio. O arquivo pode ser regera a partir dos segmentos quando necessário. Continuar?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/videos/${encodeURIComponent(currentEditingVideo)}/delete-narration/${language}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`✅ Arquivo final de narração em ${langName} deletado. Segmentos de áudio preservados.`, 'success');
            // Reload the modal to update the UI
            setTimeout(() => {
                editVideo(currentEditingVideo);
            }, 1000);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('❌ Erro ao deletar narração: ' + error.message, 'error');
    }
}

/**
 * Regenerate all audio segments for the current video
 * @param {string} language - Language code ('pt', 'en', or 'es')
 */
async function regenerateAllAudios(language = 'pt') {
    if (!currentEditingVideo || isGenerating) return;
    
    const langNames = {
        'pt': 'português',
        'en': 'inglês',
        'es': 'espanhol'
    };
    const langName = langNames[language] || language;
    
    if (!confirm(`⚠️ Isso irá regera TODOS os áudios do vídeo em ${langName}. Isso pode levar alguns minutos. Continuar?`)) {
        return;
    }
    
    // Disable all regenerate buttons
    isGenerating = true;
    disableAllRegenerateButtons();
    
    try {
        const response = await fetch(`/api/videos/${encodeURIComponent(currentEditingVideo)}/regenerate-all-audios`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`✅ Todos os áudios em ${langName} estão sendo regera... Aguarde alguns minutos.`, 'success');
            
            // Poll for all audio segments to be ready
            await pollAndLoadAllAudios(currentEditingVideo, language);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
            // Re-enable buttons on error
            isGenerating = false;
            enableAllRegenerateButtons();
        }
    } catch (error) {
        showAlert('❌ Erro ao regera áudios: ' + error.message, 'error');
        // Re-enable buttons on error
        isGenerating = false;
        enableAllRegenerateButtons();
    }
}

/**
 * Poll for all audio segments to be ready and update them
 * @param {string} folder - Video folder name
 * @param {string} language - Language code ('pt', 'en', or 'es')
 * @param {number} maxAttempts - Maximum polling attempts (default: 60)
 * @param {number} intervalMs - Polling interval in milliseconds (default: 3000)
 * @param {number} initialDelayMs - Initial delay before starting to poll in milliseconds (default: 10000)
 */
async function pollAndLoadAllAudios(folder, language = 'pt', maxAttempts = 60, intervalMs = 3000, initialDelayMs = 10000) {
    // Wait for initial delay before starting to poll (audio generation takes time)
    await new Promise(resolve => setTimeout(resolve, initialDelayMs));
    
    // First, get the number of audio segments from the modal based on language
    const sectionId = `audioSegmentsSection${language.charAt(0).toUpperCase() + language.slice(1)}`;
    const audioSegmentsSection = document.getElementById(sectionId);
    if (!audioSegmentsSection) {
        isGenerating = false;
        enableAllRegenerateButtons();
        return;
    }
    
    const audioItems = audioSegmentsSection.querySelectorAll('.edit-item');
    const segmentCount = audioItems.length;
    
    if (segmentCount === 0) {
        isGenerating = false;
        enableAllRegenerateButtons();
        return;
    }
    
    // Track which segments have been loaded
    const loadedSegments = new Set();
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        // Try to load all segments that haven't been loaded yet
        for (let index = 0; index < segmentCount; index++) {
            if (loadedSegments.has(index)) {
                continue; // Already loaded
            }
            
            try {
                const audioUrl = `/api/videos/${encodeURIComponent(folder)}/audio-segment/${index}?lang=${language}`;
                const response = await fetch(audioUrl, { method: 'HEAD' });
                
                if (response.ok) {
                    // Audio exists, update the audio element
                    await loadSingleAudioSegment(folder, index, language);
                    loadedSegments.add(index);
                }
            } catch (error) {
                // Continue checking other segments
            }
        }
        
        // If all segments are loaded, we're done
        if (loadedSegments.size === segmentCount) {
            isGenerating = false;
            enableAllRegenerateButtons();
            showAlert('✅ Todos os áudios foram regerados com sucesso!', 'success');
            return;
        }
        
        // Wait before next attempt
        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
    
    // If we get here, not all audios appeared in time
    isGenerating = false;
    enableAllRegenerateButtons();
    showAlert('⚠️ Alguns áudios podem ainda estar sendo gerados. Verifique manualmente.', 'error');
}

// Modal now only closes via the close button - removed click-outside-to-close behavior

/**
 * Show dialog to insert a new image at a specific index
 * @param {number} index - Image index (1-based) where to insert
 */
function showInsertImageDialog(index) {
    if (!currentEditingVideo || isGenerating) return;
    
    // Get negative prompt from the global field
    const negativePromptElement = document.getElementById('negative-prompt-global');
    const negative_prompt = negativePromptElement ? negativePromptElement.value : '';
    
    const promptText = window.prompt(`Digite o prompt para a nova imagem que será inserida na posição ${index}:\n\n(Pressione Cancelar para cancelar)`);
    
    if (promptText === null) {
        return; // User cancelled
    }
    
    if (!promptText.trim()) {
        showAlert('❌ O prompt não pode estar vazio', 'error');
        return;
    }
    
    // Confirm insertion
    if (!confirm(`⚠️ Isso irá inserir uma nova imagem na posição ${index} e renomear todas as imagens subsequentes. Continuar?`)) {
        return;
    }
    
    // Disable all regenerate buttons
    isGenerating = true;
    disableAllRegenerateButtons();
    
    // Show loading message
    showAlert(`✅ Inserindo imagem na posição ${index}... Isso pode levar alguns minutos.`, 'success');
    
    // Call backend to insert image
    insertImageAt(currentEditingVideo, index, promptText, negative_prompt);
}

/**
 * Insert a new image at a specific index
 * @param {string} folder - Video folder name
 * @param {number} index - Image index (1-based) where to insert
 * @param {string} prompt - Image generation prompt
 * @param {string} negative_prompt - Negative prompt
 */
async function insertImageAt(folder, index, prompt, negative_prompt) {
    try {
        const response = await fetch(`/api/videos/${encodeURIComponent(folder)}/insert-image/${index}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, negative_prompt })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`✅ Imagem está sendo inserida na posição ${index}... Aguarde alguns minutos.`, 'success');
            // Reload the video edit modal after insertion
            await pollAndReloadModal(folder, index);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
            // Re-enable buttons on error
            isGenerating = false;
            enableAllRegenerateButtons();
        }
    } catch (error) {
        showAlert('❌ Erro ao inserir imagem: ' + error.message, 'error');
        // Re-enable buttons on error
        isGenerating = false;
        enableAllRegenerateButtons();
    }
}

/**
 * Poll for image insertion completion and reload the modal
 * @param {string} folder - Video folder name
 * @param {number} index - Image index that was inserted
 * @param {number} maxAttempts - Maximum polling attempts (default: 30)
 * @param {number} intervalMs - Polling interval in milliseconds (default: 2000)
 * @param {number} initialDelayMs - Initial delay before starting to poll in milliseconds (default: 40000)
 */
async function pollAndReloadModal(folder, index, maxAttempts = 30, intervalMs = 2000, initialDelayMs = 40000) {
    // Wait for initial delay before starting to poll (image generation takes time)
    await new Promise(resolve => setTimeout(resolve, initialDelayMs));
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        try {
            // Check if the image exists
            const thumbUrl = `/api/videos/${encodeURIComponent(folder)}/thumb/${index}`;
            const response = await fetch(thumbUrl, { method: 'HEAD' });
            
            if (response.ok) {
                // Image exists, reload the modal
                showAlert('✅ Imagem inserida com sucesso! Recarregando...', 'success');
                await editVideo(folder);
                // Re-enable buttons after reload
                isGenerating = false;
                enableAllRegenerateButtons();
                return;
            }
        } catch (error) {
            // Continue polling on error
        }
        
        // Wait before next attempt
        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
    
    // If we get here, image didn't appear in time
    showAlert('⚠️ A imagem pode ainda estar sendo gerada. Recarregue o modal manualmente.', 'error');
    // Re-enable buttons on timeout
    isGenerating = false;
    enableAllRegenerateButtons();
}

/**
 * Delete an image at a specific index
 * @param {number} index - Image index (1-based) to delete
 */
async function deleteImage(index) {
    if (!currentEditingVideo || isGenerating) return;
    
    // Confirm deletion
    if (!confirm(`⚠️ Isso irá deletar a imagem ${index} e renomear todas as imagens subsequentes. Tem certeza?`)) {
        return;
    }
    
    // Double confirmation
    if (!confirm(`⚠️ Tem certeza absoluta que deseja deletar a imagem ${index}? Esta ação não pode ser desfeita.`)) {
        return;
    }
    
    // Disable all regenerate buttons
    isGenerating = true;
    disableAllRegenerateButtons();
    
    // Show loading message
    showAlert(`🗑️ Deletando imagem ${index}...`, 'success');
    
    try {
        const response = await fetch(`/api/videos/${encodeURIComponent(currentEditingVideo)}/delete-image/${index}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`✅ Imagem ${index} está sendo deletada... Aguarde alguns segundos.`, 'success');
            // Reload the video edit modal after deletion
            await pollAndReloadModalAfterDelete(currentEditingVideo);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
            // Re-enable buttons on error
            isGenerating = false;
            enableAllRegenerateButtons();
        }
    } catch (error) {
        showAlert('❌ Erro ao deletar imagem: ' + error.message, 'error');
        // Re-enable buttons on error
        isGenerating = false;
        enableAllRegenerateButtons();
    }
}

/**
 * Poll for image deletion completion and reload the modal
 * @param {string} folder - Video folder name
 * @param {number} maxAttempts - Maximum polling attempts (default: 10)
 * @param {number} intervalMs - Polling interval in milliseconds (default: 1000)
 */
async function pollAndReloadModalAfterDelete(folder, maxAttempts = 10, intervalMs = 1000) {
    // Wait a short delay before starting to poll (deletion is fast)
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Reload the modal immediately since deletion is fast
    showAlert('✅ Imagem deletada com sucesso! Recarregando...', 'success');
    await editVideo(folder);
    // Re-enable buttons after reload
    isGenerating = false;
    enableAllRegenerateButtons();
}

/**
 * Regenerate selected images in batch (model loaded only once)
 */
async function regenerateSelectedImages() {
    if (!currentEditingVideo || isGenerating) return;
    
    const checkboxes = document.querySelectorAll('.image-checkbox:checked');
    if (checkboxes.length === 0) {
        showAlert('❌ Por favor, selecione pelo menos uma imagem para regenerar', 'error');
        return;
    }
    
    const selectedIndices = Array.from(checkboxes).map(cb => parseInt(cb.getAttribute('data-image-index')));
    selectedIndices.sort((a, b) => a - b);
    
    if (!confirm(`⚠️ Isso irá regenerar ${selectedIndices.length} imagem(ns) selecionada(s). O modelo será carregado apenas uma vez. Isso pode levar alguns minutos. Continuar?`)) {
        return;
    }
    
    const negativePromptElement = document.getElementById('negative-prompt-global');
    const negative_prompt = negativePromptElement ? negativePromptElement.value : '';
    
    const imagePrompts = selectedIndices.map(index => {
        const promptElement = document.getElementById(`image-prompt-${index - 1}`);
        return {
            index: index,
            prompt: promptElement ? promptElement.value : ''
        };
    });
    
    const invalidPrompts = imagePrompts.filter(ip => !ip.prompt.trim());
    if (invalidPrompts.length > 0) {
        showAlert(`❌ Por favor, preencha os prompts das imagens selecionadas (imagens: ${invalidPrompts.map(ip => ip.index).join(', ')})`, 'error');
        return;
    }
    
    isGenerating = true;
    disableAllRegenerateButtons();
    
    const allCheckboxes = document.querySelectorAll('.image-checkbox');
    allCheckboxes.forEach(cb => {
        cb.disabled = true;
    });
    
    selectedIndices.forEach(index => {
        const container = document.getElementById(`thumb-container-${index - 1}`);
        if (container) {
            container.innerHTML = '<div style="width: 100%; min-height: 120px; background: #f0f0f0; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999; border: 1px solid #ddd;"><span>Gerando...</span></div>';
        }
    });
    
    try {
        const response = await fetch(`/api/videos/${encodeURIComponent(currentEditingVideo)}/regenerate-images-batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_prompts: imagePrompts,
                negative_prompt: negative_prompt
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`✅ ${selectedIndices.length} imagem(ns) está(ão) sendo regenerada(s)... Aguarde alguns minutos.`, 'success');
            await pollAndLoadSelectedThumbnails(currentEditingVideo, selectedIndices);
        } else {
            showAlert('❌ Erro: ' + data.error, 'error');
            selectedIndices.forEach(index => {
                loadSingleThumbnail(currentEditingVideo, index - 1);
            });
            isGenerating = false;
            enableAllRegenerateButtons();
            const allCheckboxes = document.querySelectorAll('.image-checkbox');
            allCheckboxes.forEach(cb => {
                cb.disabled = false;
            });
        }
    } catch (error) {
        showAlert('❌ Erro ao regenerar imagens: ' + error.message, 'error');
        selectedIndices.forEach(index => {
            loadSingleThumbnail(currentEditingVideo, index - 1);
        });
        isGenerating = false;
        enableAllRegenerateButtons();
        if (regenerateBtn) {
            regenerateBtn.disabled = false;
            regenerateBtn.style.opacity = '1';
            regenerateBtn.style.cursor = 'pointer';
        }
    }
}

/**
 * Poll for selected thumbnails to be ready and load them
 * @param {string} folder - Video folder name
 * @param {number[]} indices - Array of image indices (1-based) to poll for
 * @param {number} maxAttempts - Maximum polling attempts (default: 30)
 * @param {number} intervalMs - Polling interval in milliseconds (default: 2000)
 * @param {number} initialDelayMs - Initial delay before starting to poll in milliseconds (default: 40000)
 */
async function pollAndLoadSelectedThumbnails(folder, indices, maxAttempts = 30, intervalMs = 2000, initialDelayMs = 40000) {
    await new Promise(resolve => setTimeout(resolve, initialDelayMs));
    
    const loadedIndices = new Set();
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        for (const index of indices) {
            if (loadedIndices.has(index)) {
                continue;
            }
            
            try {
                const thumbUrl = `/api/videos/${encodeURIComponent(folder)}/thumb/${index}`;
                const response = await fetch(thumbUrl, { method: 'HEAD' });
                
                if (response.ok) {
                    await loadSingleThumbnail(folder, index - 1);
                    loadedIndices.add(index);
                }
            } catch (error) {
                // Continue polling
            }
        }
        
        if (loadedIndices.size === indices.length) {
            isGenerating = false;
            enableAllRegenerateButtons();
            const allCheckboxes = document.querySelectorAll('.image-checkbox');
            allCheckboxes.forEach(cb => {
                cb.disabled = false;
            });
            showAlert('✅ Todas as imagens foram regeneradas com sucesso!', 'success');
            return;
        }
        
        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
    
    const remaining = indices.filter(i => !loadedIndices.has(i));
    if (remaining.length > 0) {
        showAlert(`⚠️ Algumas imagens podem ainda estar sendo geradas (imagens: ${remaining.join(', ')}). Verifique manualmente.`, 'error');
    }
    
    isGenerating = false;
    enableAllRegenerateButtons();
    const allCheckboxes = document.querySelectorAll('.image-checkbox');
    allCheckboxes.forEach(cb => {
        cb.disabled = false;
    });
}

if (typeof window !== 'undefined') {
    window.editVideo = editVideo;
    window.closeVideoEditModal = closeVideoEditModal;
    window.updateImagePrompt = updateImagePrompt;
    window.updateAudioSegment = updateAudioSegment;
    window.regenerateSelectedImages = regenerateSelectedImages;
    window.deleteImage = deleteImage;
    window.showInsertImageDialog = showInsertImageDialog;
    window.mergeVideo = mergeVideo;
    window.mergeVideoLanguage = mergeVideoLanguage;
    window.deleteFinalNarration = deleteFinalNarration;
    window.regenerateAllAudios = regenerateAllAudios;
    window.showVideoEditTab = showVideoEditTab;
}

