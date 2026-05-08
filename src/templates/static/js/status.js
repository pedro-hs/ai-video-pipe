if (typeof window.lastAlertedStatus === 'undefined') window.lastAlertedStatus = null;
if (typeof window.lastAlertedImageStatus === 'undefined') window.lastAlertedImageStatus = null;
if (typeof window.isActiveGeneration === 'undefined') window.isActiveGeneration = false;

function setProgress(percent) { setProgressFill('progressFill', percent); }
function setImageProgress(percent) { setProgressFill('imageProgressFill', percent); }

function formatTime(seconds) {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
}

function updateGpuStatus(status) {
    if (status.gpu_stats) {
        writeText('statusGPU', `${status.gpu_stats.gpu_usage}%`);
        writeText('statusMemory', `${status.gpu_stats.memory_used_mb} / ${status.gpu_stats.memory_total_mb} MB`);
        const tempElement = document.getElementById('statusTemp');
        tempElement.textContent = `${status.gpu_stats.temperature}°C`;
        tempElement.className = 'status-value gpu-temp';
        if (status.gpu_stats.temperature < 70) {
            tempElement.classList.add('normal');
        } else if (status.gpu_stats.temperature < 80) {
            tempElement.classList.add('warning');
        }
    } else {
        writeText('statusGPU', `${status.gpu_usage}%`);
    }
}

function updateGeneratedPrompts(status) {
    if (status.image_prompts && status.image_prompts.length > 0) {
        const promptsHtml = status.image_prompts.map((prompt) => `
            <div style="margin-bottom: 8px; padding: 8px; background: rgba(255,255,255,0.1); border-radius: 5px;">
                <strong style=\"color: #ffd700;\">${prompt}</strong>
            </div>`).join('');
        document.getElementById('imagePrompts').innerHTML = promptsHtml;
    }
    if (status.narration_script && status.narration_script.trim() !== '') {
        document.getElementById('narrationScript').innerHTML = `<span style="opacity: 1;">${status.narration_script}</span>`;
    }
}

function updateImageStatusUI(status) {
    setImageProgress(status.progress_percent);
    const stageNames = {
        'idle': '💤 Idle',
        'loading': '🤖 Carregando SDXL',
        'generating': '🎨 Gerando Imagem',
        'saving': '💾 Salvando',
        'complete': '✅ Completo',
        'error': '❌ Erro'
    };
    writeText('imageStatusStage', getStageLabel(stageNames, status.stage));
    writeText('imageStatusProgress', Math.round(status.progress_percent) + '%');
    writeText('imageStatusGPU', `${(status.gpu_stats ? status.gpu_stats.gpu_usage : status.gpu_usage)}%`);
    writeText('imageStatusMessage', status.message);
}

function onVideoIdle() {
    document.getElementById('statusMonitor').classList.remove('active');
    document.getElementById('progressBar').classList.remove('active');
    document.getElementById('stopBtn').style.display = 'none';
}

function cleanVideoMonitor() {
    document.getElementById('generateBtn').disabled = false;
    document.getElementById('loading').classList.remove('active');
    setTimeout(() => {
        onVideoIdle();
    }, 5000);
}

function onVideoComplete(statusKey) {
    showAlert('✅ Vídeo concluído com sucesso! Verifique "Meus Vídeos".', 'success');
    loadVideos();
    lastAlertedStatus = statusKey;
    generating = false;
    cleanVideoMonitor();
}

function onVideoError(statusKey, message) {
    showAlert('❌ Erro na geração: ' + message, 'error');
    lastAlertedStatus = statusKey;
    generating = false;
    cleanVideoMonitor();
}

function onVideoActive(status) {
    if (!document.getElementById('statusMonitor').classList.contains('active')) {
        document.getElementById('statusMonitor').classList.add('active');
        document.getElementById('progressBar').classList.add('active');
    }
    document.getElementById('stopBtn').style.display = 'block';
    if (status.stage === 'loading' || status.stage === 'generating') {
        lastAlertedStatus = null;
    }
}

function updatePollingState(status) {
    const wasActive = isActiveGeneration;
    isActiveGeneration = status.is_active || status.stage !== 'idle';
    if (wasActive && !isActiveGeneration) {
        console.log('Generation completed, switching to minimal polling (30s)');
        stopPolling();
        setTimeout(() => startMinimalPolling(), 1000);
    } else if (!wasActive && isActiveGeneration) {
        console.log('Generation started, switching to active polling (2s)');
        startActivePolling();
    }
}

function onImageIdle() {
    document.getElementById('imageStatusMonitor').classList.remove('active');
    document.getElementById('imageProgressBar').classList.remove('active');
    document.getElementById('stopImageBtn').style.display = 'none';
}

function cleanImageMonitor() {
    document.getElementById('generateImageBtn').disabled = false;
    document.getElementById('imageLoading').classList.remove('active');
    if (typeof stopImageGenerationPolling === 'function') {
        stopImageGenerationPolling();
    }
    setTimeout(() => {
        onImageIdle();
    }, 5000);
}

function onImageComplete(statusKey) {
    showAlert('✅ Imagem concluída com sucesso! Verifique "Minhas Imagens".', 'success');
    loadImages();
    lastAlertedImageStatus = statusKey;
    generatingImage = false;
    cleanImageMonitor();
}

function onImageError(statusKey, message) {
    showAlert('❌ Erro na geração da imagem: ' + message, 'error');
    lastAlertedImageStatus = statusKey;
    generatingImage = false;
    cleanImageMonitor();
}

function onImageActive(status) {
    if (!document.getElementById('imageStatusMonitor').classList.contains('active')) {
        document.getElementById('imageStatusMonitor').classList.add('active');
        document.getElementById('imageProgressBar').classList.add('active');
    }
    document.getElementById('stopImageBtn').style.display = 'block';
    if (status.stage === 'loading' || status.stage === 'generating') {
        lastAlertedImageStatus = null;
    }
}

async function checkGenerationStatusOnLoad() {
    try {
        const response = await fetch('/api/generation/status');
        const data = await response.json();
        if (data.success && data.status && data.status.is_active) {
            document.getElementById('stopBtn').style.display = 'block';
            updateStatusUI(data.status);
        }
    } catch (error) {
        console.error('Error checking initial status:', error);
    }
}

async function checkGenerationStatus() {
    try {
        const response = await fetch('/api/generation/status');
        const data = await response.json();
        if (data.success && data.status) {
            const status = data.status;
            const statusKey = status.timestamp + '_' + status.stage;
            updateStatusUI(status);
            const isNewStatus = lastAlertedStatus !== statusKey;

            if (status.stage === 'complete' && isNewStatus) {
                onVideoComplete(statusKey);
            } else if (status.stage === 'error' && isNewStatus) {
                onVideoError(statusKey, status.message);
            } else if (status.is_active) {
                onVideoActive(status);
            } else if (status.stage === 'idle' && !generating) {
                // Only hide status monitor if user is not currently generating
                onVideoIdle();
            }

            updatePollingState(status);
        }
    } catch (error) {
        console.error('Error checking generation status:', error);
    }
}

async function checkImageGenerationStatus() {
    try {
        const response = await fetch('/api/generation/status');
        const data = await response.json();
        if (data.success && data.status) {
            const status = data.status;
            const statusKey = status.timestamp + '_' + status.stage;
            updateImageStatusUI(status);
            const isNewStatus = lastAlertedImageStatus !== statusKey;

            if (status.stage === 'complete' && isNewStatus && generatingImage) {
                onImageComplete(statusKey);
            } else if (status.stage === 'error' && isNewStatus && generatingImage) {
                onImageError(statusKey, status.message);
            } else if (status.is_active && generatingImage) {
                onImageActive(status);
            } else if (!generatingImage && status.stage === 'idle') {
                onImageIdle();
            } else if ((status.stage === 'complete' || status.stage === 'error') && !generatingImage && isNewStatus) {
                // Status is complete/error but we're not generating (e.g., page refresh)
                // Clean up UI and reset status to idle after a delay
                cleanImageMonitor();
                // Reset status to idle after showing completion message
                setTimeout(() => {
                    if (typeof stopImageGenerationPolling === 'function') {
                        stopImageGenerationPolling();
                    }
                }, 5000);
            }
        }
    } catch (error) {
        console.error('Error checking image generation status:', error);
    }
}

function forceRefreshStatus() {
    checkGenerationStatus();
    showAlert('🔄 Status atualizado!', 'info');
}

function forceRefreshImageStatus() {
    checkImageGenerationStatus();
    showAlert('🔄 Status da imagem atualizado!', 'info');
}


function updateTerminalLogs(status) {
    const terminalEl = document.getElementById('terminalLogs');
    if (!terminalEl) return;
    
    if (!status.logs || status.logs.length === 0) {
        terminalEl.innerHTML = '<div style="color: #858585; font-style: italic;">Aguardando logs...</div>';
        return;
    }
    
    const logsHtml = status.logs.map(log => {
        const timestamp = new Date(log.timestamp).toLocaleTimeString('pt-BR');
        let color = '#d4d4d4'; // default
        let icon = 'ℹ️';
        
        switch(log.level) {
            case 'success':
                color = '#4ec9b0';
                icon = '✅';
                break;
            case 'error':
                color = '#f48771';
                icon = '❌';
                break;
            case 'warning':
                color = '#dcdcaa';
                icon = '⚠️';
                break;
        }
        
        let line = `<span style="color: #858585;">[${timestamp}]</span> <span style="color: ${color};">${icon} ${log.message}</span>`;
        
        if (log.step) {
            line += ` <span style="color: #569cd6;">[Step: ${log.step}]</span>`;
        }
        
        if (log.progress) {
            line += ` <span style="color: #ce9178;">[Progress: ${log.progress}]</span>`;
        }
        
        return `<div style="margin-bottom: 4px;">${line}</div>`;
    }).join('');
    
    terminalEl.innerHTML = logsHtml;
    
    // Auto-scroll to bottom
    terminalEl.scrollTop = terminalEl.scrollHeight;
}

function clearTerminalLogs() {
    // Clear logs from status (backend will handle this)
    fetch('/api/generation/clear-logs', { method: 'POST' })
        .then(() => {
            const terminalEl = document.getElementById('terminalLogs');
            if (terminalEl) {
                terminalEl.innerHTML = '<div style="color: #858585; font-style: italic;">Logs limpos...</div>';
            }
        })
        .catch(err => console.error('Error clearing logs:', err));
}

function updateStatusUI(status) {
    setProgress(status.progress_percent);
    const stageNames = {
        'idle': '💤 Idle',
        'loading': '🎨 Gerando Imagens',
        'generating': '🎬 Criando Vídeo',
        'interpolating': '🎬 Criando Vídeo',
        'saving': '💾 Salvando Vídeo',
        'video_done': '✅ Vídeo Pronto',
        'narration': '📝 Gerando Roteiro',
        'audio': '🎙️ Gerando Áudio',
        'merging': '🔊 Combinando Mídia',
        'complete': '✅ Concluído',
        'error': '❌ Erro'
    };
    writeText('statusStage', getStageLabel(stageNames, status.stage));
    updateGpuStatus(status);
    writeText('statusMessage', status.message);
    updateGeneratedPrompts(status);
    updateTerminalLogs(status);
}

async function checkStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        if (data.success) {
            updateServiceStatus('ollama', data.services.ollama);
            updateServiceStatus('ai', data.services.ai_processor);
        }
    } catch (error) {
        console.error('Erro ao verificar status:', error);
    }
}

function updateServiceStatus(service, online) {
    const element = document.getElementById(`status-${service}`);
    const dot = element.querySelector('.status-dot');
    if (online) {
        element.classList.add('online');
        element.classList.remove('offline');
        dot.classList.add('online');
        dot.classList.remove('offline');
    } else {
        element.classList.add('offline');
        element.classList.remove('online');
        dot.classList.add('offline');
        dot.classList.remove('online');
    }
}

