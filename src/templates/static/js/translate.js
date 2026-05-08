let translating = false;

function showTranslateTab() {
    // This function is called when the translate tab is shown
    // Can be used for initialization if needed
}

async function handleTranslateFormSubmit(e) {
    e.preventDefault();
    if (translating) return;

    const text = document.getElementById('translateText').value.trim();
    const targetLanguage = document.getElementById('translateTargetLanguage').value;

    if (!text) {
        showAlert('Por favor, insira o texto para traduzir', 'error');
        return;
    }

    translating = true;
    const translateBtn = document.getElementById('translateBtn');
    const translateLoading = document.getElementById('translateLoading');
    const translateResult = document.getElementById('translateResult');
    const translateResultText = document.getElementById('translateResultText');
    const copyBtn = document.getElementById('copyTranslateBtn');

    // Update UI
    translateBtn.disabled = true;
    translateBtn.textContent = '🔄 Traduzindo...';
    translateLoading.style.display = 'block';
    translateResult.style.display = 'none';
    translateResultText.textContent = '';

    try {
        const response = await fetch('/api/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: text,
                target_language: targetLanguage
            })
        });

        const data = await response.json();

        if (data.success) {
            translateResultText.textContent = data.translated_text;
            translateResult.style.display = 'block';
            copyBtn.style.display = 'inline-block';
            
            const langName = data.target_language_name || (targetLanguage === 'en' ? 'Inglês' : 'Espanhol');
            showAlert(`✅ Texto traduzido para ${langName} com sucesso!`, 'success');
        } else {
            showAlert('❌ Erro: ' + (data.error || 'Erro desconhecido'), 'error');
            translateResult.style.display = 'none';
        }
    } catch (error) {
        showAlert('❌ Erro ao conectar com o servidor: ' + error.message, 'error');
        translateResult.style.display = 'none';
    } finally {
        translating = false;
        translateBtn.disabled = false;
        translateBtn.textContent = '🌐 Traduzir';
        translateLoading.style.display = 'none';
    }
}

function copyTranslatedText() {
    const translateResultText = document.getElementById('translateResultText');
    const text = translateResultText.textContent;

    if (!text) {
        showAlert('Nenhum texto para copiar', 'error');
        return;
    }

    // Use modern clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showAlert('✅ Texto copiado para a área de transferência!', 'success');
        }).catch(err => {
            console.error('Error copying to clipboard:', err);
            fallbackCopyTextToClipboard(text);
        });
    } else {
        fallbackCopyTextToClipboard(text);
    }
}

function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showAlert('✅ Texto copiado para a área de transferência!', 'success');
        } else {
            showAlert('❌ Erro ao copiar texto. Tente selecionar e copiar manualmente.', 'error');
        }
    } catch (err) {
        console.error('Fallback copy failed:', err);
        showAlert('❌ Erro ao copiar texto. Tente selecionar e copiar manualmente.', 'error');
    } finally {
        document.body.removeChild(textArea);
    }
}

// Initialize form handler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const translateForm = document.getElementById('translateForm');
    if (translateForm) {
        translateForm.addEventListener('submit', handleTranslateFormSubmit);
    }

    const copyBtn = document.getElementById('copyTranslateBtn');
    if (copyBtn) {
        copyBtn.addEventListener('click', copyTranslatedText);
    }
});
