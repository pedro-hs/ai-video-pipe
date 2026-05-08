// Paragraph Review and Analysis Module
// Handles the review modal for paragraph duration adjustment

// Global variable to store current review data
let currentReviewData = {
    folder: '',
    narration: '',
    language: '',
    paragraphs: [],
    portuguese_paragraphs: []
};

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper function to format seconds to minutes:seconds
function formatDuration(seconds) {
    const totalSeconds = Math.floor(seconds);
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Function to calculate and update total durations
function updateTotalDurations() {
    if (!currentReviewData.paragraphs || currentReviewData.paragraphs.length === 0) {
        return;
    }
    
    // Portuguese total: sum of target_duration (already includes silences between paragraphs)
    const totalPt = currentReviewData.paragraphs.reduce((sum, p) => sum + (p.target_duration || 0), 0);
    
    // Current language total: sum of current_duration + silences between paragraphs
    const totalCurrent = currentReviewData.paragraphs.reduce((sum, p) => sum + (p.current_duration || 0), 0);
    // Add silences between paragraphs (same calculation as backend)
    const silenceBetweenParagraphs = 1.0; // DEFAULT_SILENCE_DURATION
    const totalCurrentWithSilences = totalCurrent + (currentReviewData.paragraphs.length > 1 ? (currentReviewData.paragraphs.length - 1) * silenceBetweenParagraphs : 0);
    
    // Update the totals display
    const totalsElement = document.getElementById('total-durations-display');
    if (totalsElement) {
        const langName = currentReviewData.language === 'en' ? 'Inglês' : 'Espanhol';
        const langFlag = currentReviewData.language === 'en' ? '🇬🇧' : '🇪🇸';
        totalsElement.innerHTML = `
            <strong>⏱️ Duração Total:</strong><br>
            🇧🇷 Português: <strong>${formatDuration(totalPt)}</strong><br>
            ${langFlag} ${langName}: <strong>${formatDuration(totalCurrentWithSilences)}</strong>
        `;
    }
}

// Show review modal with paragraph analysis
function showReviewModal(paragraphs, language, portugueseParagraphs = [], folder = '', totalPtDuration = null, totalCurrentDuration = null) {
    console.log('showReviewModal called with', paragraphs.length, 'paragraphs');
    console.log('Portuguese paragraphs received:', portugueseParagraphs ? portugueseParagraphs.length : 0, portugueseParagraphs);
    const reviewContent = document.getElementById('reviewContent');
    if (!reviewContent) {
        console.error('reviewContent element not found!');
        return;
    }
    reviewContent.innerHTML = '';
    
    const langName = language === 'en' ? 'Inglês' : 'Espanhol';
    const needsAdjustment = paragraphs.filter(p => Math.abs(p.difference) > 2.0).length;
    const totalParagraphs = paragraphs.length;
    
    console.log(`Total paragraphs: ${totalParagraphs}, Need adjustment: ${needsAdjustment}`);
    console.log('First paragraph portuguese_text:', paragraphs[0]?.portuguese_text);
    
    // Store data in global variable
    currentReviewData.paragraphs = paragraphs;
    currentReviewData.language = language;
    currentReviewData.portuguese_paragraphs = portugueseParagraphs;
    if (folder) {
        currentReviewData.folder = folder;
    }
    
    // Use provided totals or calculate from paragraphs (fallback)
    const totalPt = totalPtDuration !== null ? totalPtDuration : paragraphs.reduce((sum, p) => sum + (p.target_duration || 0), 0);
    const totalCurrent = totalCurrentDuration !== null ? totalCurrentDuration : paragraphs.reduce((sum, p) => sum + (p.current_duration || 0), 0);
    
    // Always show summary
    let summaryHtml = `
        <div style="padding: 15px; background: #e7f3ff; border: 1px solid #007bff; border-radius: 8px; margin-bottom: 20px; color: #004085;">
            <strong>📊 Análise de Duração - ${langName}</strong><br>
            Total de parágrafos analisados: <strong>${totalParagraphs}</strong><br>
            ${needsAdjustment > 0 ? 
                `Parágrafos que precisam de ajuste: <strong>${needsAdjustment}</strong>` : 
                '✅ Todos os parágrafos têm duração adequada!'
            }
        </div>
        <div id="total-durations-display" style="padding: 10px; background: #fff; border: 1px solid #007bff; border-radius: 6px; margin-bottom: 20px;">
            <strong>⏱️ Duração Total:</strong><br>
            🇧🇷 Português: <strong>${formatDuration(totalPt)}</strong><br>
            ${language === 'en' ? '🇬🇧' : '🇪🇸'} ${langName}: <strong>${formatDuration(totalCurrent)}</strong>
        </div>
    `;
    
    if (needsAdjustment === 0) {
        // All paragraphs match - show success message
        summaryHtml += `
            <div style="padding: 20px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 8px; color: #155724; margin-bottom: 20px;">
                <strong>✅ Perfeito!</strong><br>
                Todos os parágrafos já têm duração adequada. Não são necessários ajustes. Você pode gerar o vídeo diretamente.
            </div>
        `;
    }
    document.getElementById('applySelectedBtn').textContent = 'Gerar Vídeo';
    
    // Add tip at the beginning if there are suggestions
    if (needsAdjustment > 0) {
        summaryHtml += `
            <div style="padding: 10px; background: #e7f3ff; border-radius: 6px; color: #0066cc; font-size: 12px; margin-bottom: 20px;">
                💡 <strong>Dica:</strong> Use os botões <span style="background: #28a745; color: white; border-radius: 3px; padding: 2px 6px; font-weight: bold;">+</span> e <span style="background: #dc3545; color: white; border-radius: 3px; padding: 2px 6px;">🗑️</span> para aplicar sugestões diretamente no texto, ou edite manualmente nos campos de texto.
            </div>
        `;
    }
    
    reviewContent.innerHTML = summaryHtml;
    
    // Always show all paragraphs
    paragraphs.forEach((para, index) => {
        // Save original text for revert functionality (before any edits)
        if (!para._originalText) {
            para._originalText = para.original_text;
        }
        
        const hasAddSuggestions = para.suggestions && para.suggestions.add && para.suggestions.add.length > 0;
        const hasRemoveSuggestions = para.suggestions && para.suggestions.remove && para.suggestions.remove.length > 0;
        const hasSuggestions = hasAddSuggestions || hasRemoveSuggestions;
        const paraNeedsAdjustment = Math.abs(para.difference) > 2.0;
        
        const card = document.createElement('div');
        card.style.cssText = 'margin-bottom: 20px; padding: 20px; border: 2px solid #ddd; border-radius: 8px; background: #f9f9f9;';
        card.id = `paragraph-${index}`;
        
        const diffColor = para.difference > 0 ? '#28a745' : '#dc3545';
        const diffText = para.difference > 0 ? `+${para.difference.toFixed(1)}s` : `${para.difference.toFixed(1)}s`;
        
        // Get Portuguese paragraph text (from para.portuguese_text or from array)
        const ptText = para.portuguese_text || (portugueseParagraphs && portugueseParagraphs[index] ? portugueseParagraphs[index] : '');
        
        console.log(`Paragraph ${index + 1}: PT text length = ${ptText.length}, from para.portuguese_text = ${!!para.portuguese_text}, from array = ${!!(portugueseParagraphs && portugueseParagraphs[index])}`);
        
        // Always show side-by-side comparison, even if Portuguese text is empty
        const ptDisplayText = ptText || '(Texto em português não disponível)';
        
        card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h3 style="margin: 0; color: #333;">Parágrafo ${index + 1}/${paragraphs.length}</h3>
                    <div class="duration-info" style="text-align: right;">
                        <div style="font-size: 12px; color: #666;">Duração atual: <strong>${para.current_duration}s</strong></div>
                        <div style="font-size: 12px; color: #666;">Alvo: <strong>${para.target_duration}s</strong></div>
                        <div style="font-size: 14px; color: ${diffColor}; font-weight: bold;">Diferença: ${diffText}</div>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; align-items: stretch;">
                    <div style="padding: 12px; background: #fff; border: 1px solid #ddd; border-radius: 6px; display: flex; flex-direction: column; height: 100%;">
                        <strong style="color: #666; font-size: 12px; margin-bottom: 8px;">🇧🇷 Português (Referência):</strong>
                        <div style="flex: 1; color: #333; line-height: 1.6; white-space: pre-wrap; font-size: 13px; padding: 8px; background: #f5f5f5; border-radius: 4px; overflow-y: auto; min-height: 300px;">${escapeHtml(ptDisplayText)}</div>
                    </div>
                    <div style="padding: 12px; background: #fff; border: 1px solid #ddd; border-radius: 6px; display: flex; flex-direction: column; height: 100%;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <strong style="color: #666; font-size: 12px;">${language === 'en' ? '🇬🇧' : '🇪🇸'} ${langName}:</strong>
                            <div style="display: flex; gap: 6px;">
                                <button onclick="revertParagraphText(${index})" style="background: #6c757d; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-size: 13px; cursor: pointer;" title="Reverter para texto original">↩️ Reverter</button>
                                <button onclick="recalculateParagraphDuration(${index}, '${language}')" style="background: #28a745; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-size: 13px; cursor: pointer;" title="Recalcular duração">🔄 Recalcular</button>
                            </div>
                        </div>
                        <textarea 
                            id="paragraph-text-${index}" 
                            style="flex: 1; width: 100%; color: #333; line-height: 1.6; font-size: 13px; padding: 8px; border: 1px solid #ddd; border-radius: 4px; min-height: 300px; overflow-y: auto; font-family: inherit; resize: vertical;"
                            onchange="updateParagraphText(${index})"
                        >${escapeHtml(para.original_text)}</textarea>
                    </div>
                </div>
                
                ${hasAddSuggestions ? `
                    <div style="margin-bottom: 15px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <strong style="color: #28a745;">➕ Adicionar:</strong>
                            <button onclick="regenerateAddSuggestions(${index}, '${language}')" style="background: #17a2b8; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-size: 12px; cursor: pointer;" title="Regenerar sugestões de adição">🔄 Regenerar</button>
                        </div>
                        <div style="margin-top: 8px; padding: 10px; background: #d4edda; border-radius: 6px;" id="add-suggestions-${index}">
                            ${para.suggestions.add.map((add, i) => {
                                // Handle both old format (string) and new format (object with text and duration)
                                const addText = typeof add === 'string' ? add : (add.text || add);
                                const addDuration = typeof add === 'object' && add.duration !== undefined ? add.duration : null;
                                const durationDisplay = addDuration ? ` <span style="color: #28a745; font-weight: bold; margin-left: 8px;">(~${addDuration}s)</span>` : '';
                                const isLast = i === para.suggestions.add.length - 1;
                                return `
                                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; ${!isLast ? 'border-bottom: 1px solid #c3e6cb; padding-bottom: 8px;' : ''}">
                                        <span style="color: #155724; flex: 1;">${escapeHtml(addText)}</span>
                                        ${durationDisplay}
                                        <button 
                                            onclick="insertSuggestionAtCursor(${index}, ${i}, 'add')" 
                                            style="background: #28a745; color: white; border: none; border-radius: 4px; width: 28px; height: 28px; font-size: 18px; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0;"
                                            title="Inserir no cursor do texto"
                                        >
                                            +
                                        </button>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                ` : ''}
                ${hasRemoveSuggestions ? `
                    <div style="margin-bottom: 15px;">
                        <strong style="color: #dc3545;">➖ Remover:</strong>
                        <div style="margin-top: 8px; padding: 10px; background: #f8d7da; border-radius: 6px;" id="remove-suggestions-${index}">
                            ${para.suggestions.remove.map((remove, i) => {
                                // Handle both old format (string) and new format (object with text and duration)
                                const removeText = typeof remove === 'string' ? remove : (remove.text || remove);
                                const removeDuration = typeof remove === 'object' && remove.duration !== undefined ? remove.duration : null;
                                const durationDisplay = removeDuration ? ` <span style="color: #dc3545; font-weight: bold; margin-left: 8px;">(~${removeDuration}s)</span>` : '';
                                const isLast = i === para.suggestions.remove.length - 1;
                                return `
                                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; ${!isLast ? 'border-bottom: 1px solid #f5c6cb; padding-bottom: 8px;' : ''}">
                                        <span style="color: #721c24; flex: 1;">${escapeHtml(removeText)}</span>
                                        ${durationDisplay}
                                        <button 
                                            onclick="removeSuggestionFromTextarea(${index}, ${i})" 
                                            style="background: #dc3545; color: white; border: none; border-radius: 4px; width: 28px; height: 28px; font-size: 18px; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0;"
                                            title="Remover do texto"
                                        >
                                            🗑️
                                        </button>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                ` : ''}
                ${paraNeedsAdjustment && !hasSuggestions ? `
                    <div style="padding: 10px; background: #fff3cd; border-radius: 6px; color: #856404;">
                        ⚠️ Este parágrafo precisa de ajuste, mas o Ollama não forneceu sugestões. Você pode editar manualmente no campo de texto acima.
                    </div>
                ` : !paraNeedsAdjustment ? `
                    <div style="padding: 10px; background: #d4edda; border-radius: 6px; color: #155724;">
                        ✅ Este parágrafo já tem duração adequada. Nenhum ajuste necessário.
                    </div>
                ` : ''}
            `;
        
        reviewContent.appendChild(card);
    });
    
    const reviewModal = document.getElementById('reviewModal');
    if (reviewModal) {
        reviewModal.style.display = 'block';
        console.log('Review modal displayed');
    } else {
        console.error('reviewModal element not found!');
    }
}

function closeReviewModal() {
    document.getElementById('reviewModal').style.display = 'none';
    currentReviewData = { folder: '', narration: '', language: '', paragraphs: [], portuguese_paragraphs: [] };
}

function updateParagraphText(paraIndex) {
    // Update the paragraph text in currentReviewData when user edits it
    const textarea = document.getElementById(`paragraph-text-${paraIndex}`);
    if (textarea && currentReviewData.paragraphs[paraIndex]) {
        currentReviewData.paragraphs[paraIndex].original_text = textarea.value;
    }
}

function revertParagraphText(paraIndex) {
    // Revert textarea to original text from analysis (before any edits)
    const textarea = document.getElementById(`paragraph-text-${paraIndex}`);
    if (!textarea || !currentReviewData.paragraphs[paraIndex]) return;
    
    const para = currentReviewData.paragraphs[paraIndex];
    // Use _originalText if saved, otherwise fall back to original_text
    const originalText = para._originalText || para.original_text || '';
    
    if (!originalText) {
        alert('Texto original não encontrado.');
        return;
    }
    
    textarea.value = originalText;
    
    // Update stored text to match reverted value
    para.original_text = originalText;
    
    // Trigger change event
    textarea.dispatchEvent(new Event('change'));
}

async function recalculateParagraphDuration(paraIndex, language) {
    const textarea = document.getElementById(`paragraph-text-${paraIndex}`);
    if (!textarea) return;
    
    const editedText = textarea.value.trim();
    if (!editedText) {
        alert('O texto não pode estar vazio.');
        return;
    }
    
    // Update the paragraph text
    if (currentReviewData.paragraphs[paraIndex]) {
        currentReviewData.paragraphs[paraIndex].original_text = editedText;
    }
    
    // Show loading - get button from the paragraph card
    const card = document.getElementById(`paragraph-${paraIndex}`);
    if (!card) return;
    
    const btn = card.querySelector('button[onclick*="recalculateParagraphDuration"]');
    if (!btn) return;
    
    // Also disable revert button
    const revertBtn = card.querySelector('button[onclick*="revertParagraphText"]');
    
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Calculando...';
    if (revertBtn) revertBtn.disabled = true;
    
    try {
        // Call backend to recalculate duration
        // Send cached target_duration to avoid regenerating Portuguese audio
        const response = await fetch(`/api/videos/${currentReviewData.folder}/recalculate-duration`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                paragraph_text: editedText,
                language: language,
                paragraph_index: paraIndex,
                target_duration: currentReviewData.paragraphs[paraIndex].target_duration  // Use cached value from initial analysis
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update the paragraph data with new duration
            if (currentReviewData.paragraphs[paraIndex]) {
                currentReviewData.paragraphs[paraIndex].current_duration = data.duration;
                currentReviewData.paragraphs[paraIndex].difference = data.difference;
                
                // Update the display
                const durationInfo = card.querySelector('.duration-info');
                if (durationInfo) {
                    const diffColor = data.difference > 0 ? '#28a745' : '#dc3545';
                    const diffText = data.difference > 0 ? 
                        `+${data.difference.toFixed(1)}s` : 
                        `${data.difference.toFixed(1)}s`;
                    durationInfo.innerHTML = `
                        <div style="font-size: 12px; color: #666;">Duração atual: <strong>${data.duration.toFixed(2)}s</strong></div>
                        <div style="font-size: 12px; color: #666;">Alvo: <strong>${data.target_duration.toFixed(2)}s</strong></div>
                        <div style="font-size: 14px; color: ${diffColor}; font-weight: bold;">Diferença: ${diffText}</div>
                    `;
                }
                
                // Update total durations display
                updateTotalDurations();
            }
        } else {
            alert('Erro ao recalcular: ' + (data.error || 'Erro desconhecido'));
        }
    } catch (err) {
        alert('Erro ao recalcular duração: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
        if (revertBtn) revertBtn.disabled = false;
    }
}

function insertSuggestionAtCursor(paraIndex, suggestionIndex, type) {
    const textarea = document.getElementById(`paragraph-text-${paraIndex}`);
    if (!textarea) return;
    
    const para = currentReviewData.paragraphs[paraIndex];
    if (!para || !para.suggestions) return;
    
    let suggestionText = '';
    
    if (type === 'add' && para.suggestions.add && para.suggestions.add[suggestionIndex]) {
        const add = para.suggestions.add[suggestionIndex];
        suggestionText = typeof add === 'string' ? add : (add.text || '');
    }
    
    if (!suggestionText) return;
    
    // Get cursor position
    const cursorPos = textarea.selectionStart || textarea.value.length;
    const textBefore = textarea.value.substring(0, cursorPos);
    const textAfter = textarea.value.substring(cursorPos);
    
    // Insert with proper spacing and punctuation
    // Remove trailing punctuation from suggestion if it already has it
    const cleanSuggestion = suggestionText.trim().replace(/[.!?]+$/, '');
    
    let insertText = '';
    const trimmedBefore = textBefore.trim();
    
    if (trimmedBefore.length === 0) {
        // At start of text
        insertText = `${cleanSuggestion}. `;
    } else if (trimmedBefore.endsWith('.') || trimmedBefore.endsWith('!') || trimmedBefore.endsWith('?')) {
        // After sentence ending
        insertText = ` ${cleanSuggestion}.`;
    } else {
        // In middle of sentence
        insertText = ` ${cleanSuggestion}.`;
    }
    
    textarea.value = textBefore + insertText + textAfter;
    
    // Set cursor after inserted text
    const newCursorPos = cursorPos + insertText.length;
    textarea.setSelectionRange(newCursorPos, newCursorPos);
    textarea.focus();
    
    // Trigger change event to update if needed
    textarea.dispatchEvent(new Event('change'));
}

function removeSuggestionFromTextarea(paraIndex, suggestionIndex) {
    const textarea = document.getElementById(`paragraph-text-${paraIndex}`);
    if (!textarea) return;
    
    const para = currentReviewData.paragraphs[paraIndex];
    if (!para || !para.suggestions || !para.suggestions.remove) return;
    
    if (suggestionIndex >= para.suggestions.remove.length) return;
    
    const remove = para.suggestions.remove[suggestionIndex];
    const removeText = typeof remove === 'string' ? remove : (remove.text || '');
    
    if (!removeText) return;
    
    // Remove the text from textarea (case-insensitive, handle punctuation)
    const regex = new RegExp(removeText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const originalValue = textarea.value;
    const newValue = originalValue.replace(regex, '').replace(/\s+/g, ' ').trim();
    
    if (newValue !== originalValue) {
        textarea.value = newValue;
        // Trigger change event
        textarea.dispatchEvent(new Event('change'));
    } else {
        // Text not found - show message
        alert(`O texto "${removeText}" não foi encontrado no parágrafo.`);
    }
}

async function regenerateAddSuggestions(paraIndex, language) {
    const card = document.getElementById(`paragraph-${paraIndex}`);
    if (!card) return;
    
    const regenerateBtn = card.querySelector('button[onclick*="regenerateAddSuggestions"]');
    const suggestionsDiv = document.getElementById(`add-suggestions-${paraIndex}`);
    
    if (!regenerateBtn || !suggestionsDiv) return;
    
    const originalText = regenerateBtn.textContent;
    regenerateBtn.disabled = true;
    regenerateBtn.textContent = 'Gerando...';
    
    try {
        const para = currentReviewData.paragraphs[paraIndex];
        if (!para) {
            alert('Erro: Parágrafo não encontrado.');
            return;
        }
        
        // Get current paragraph text (may have been edited)
        const textarea = document.getElementById(`paragraph-text-${paraIndex}`);
        const paragraphText = textarea ? textarea.value.trim() : para.original_text;
        
        // Calculate duration difference
        const durationDiff = para.target_duration - para.current_duration;
        
        if (durationDiff <= 0) {
            alert('Este parágrafo não precisa de sugestões de adição (duração já é suficiente ou maior que o alvo).');
            return;
        }
        
        // Call backend to regenerate suggestions
        const response = await fetch(`/api/videos/${currentReviewData.folder}/regenerate-suggestions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                paragraph_text: paragraphText,
                duration_diff: durationDiff,
                language: language,
                paragraph_index: paraIndex,
                suggestion_type: 'add'
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.suggestions && data.suggestions.add) {
            // Update paragraph data
            if (!para.suggestions) para.suggestions = { add: [], remove: [] };
            para.suggestions.add = data.suggestions.add;
            
            // Update UI
            suggestionsDiv.innerHTML = data.suggestions.add.map((add, i) => {
                const addText = typeof add === 'string' ? add : (add.text || add);
                const addDuration = typeof add === 'object' && add.duration !== undefined ? add.duration : null;
                const durationDisplay = addDuration ? ` <span style="color: #28a745; font-weight: bold; margin-left: 8px;">(~${addDuration}s)</span>` : '';
                const isLast = i === data.suggestions.add.length - 1;
                return `
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; ${!isLast ? 'border-bottom: 1px solid #c3e6cb; padding-bottom: 8px;' : ''}">
                        <span style="color: #155724; flex: 1;">${escapeHtml(addText)}</span>
                        ${durationDisplay}
                        <button 
                            onclick="insertSuggestionAtCursor(${paraIndex}, ${i}, 'add')" 
                            style="background: #28a745; color: white; border: none; border-radius: 4px; width: 28px; height: 28px; font-size: 18px; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0;"
                            title="Inserir no cursor do texto"
                        >
                            +
                        </button>
                    </div>
                `;
            }).join('');
        } else {
            alert('Erro ao regenerar sugestões: ' + (data.error || 'Erro desconhecido'));
        }
    } catch (err) {
        alert('Erro ao regenerar sugestões: ' + err.message);
    } finally {
        regenerateBtn.disabled = false;
        regenerateBtn.textContent = originalText;
    }
}

function applySelectedSuggestions() {
    const paragraphs = currentReviewData.paragraphs;
    const approvedSuggestions = [];
    const finalParagraphs = [];
    
    paragraphs.forEach((para, index) => {
        // Get edited text from textarea (user has already applied suggestions manually or edited)
        const textarea = document.getElementById(`paragraph-text-${index}`);
        const paragraphText = textarea ? textarea.value.trim() : para.original_text;
        
        // Always use the textarea content (suggestions were already applied via buttons)
        finalParagraphs.push(paragraphText);
        approvedSuggestions.push({
            apply: false,  // No need to apply suggestions - already in textarea
            suggestions: para.suggestions,
            approved_add: [],
            approved_remove: []
        });
    });
    
    // Combine paragraphs with (silence) markers
    const finalNarration = finalParagraphs.join(' (silence) ');
    
    // Proceed with export
    proceedWithExport(
        currentReviewData.folder,
        finalNarration,
        currentReviewData.language,
        approvedSuggestions
    );
    
    closeReviewModal();
}

function proceedWithExport(folder, narration, language, approvedSuggestions) {
    const endpoint = language === 'en' ? 'export-english' : 'export-spanish';
    const fieldName = language === 'en' ? 'narration_en' : 'narration_es';
    const langName = language === 'en' ? 'inglês' : 'espanhol';
    
    fetch(`/api/videos/${folder}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            [fieldName]: narration,
            mode: 'apply',
            approved_suggestions: approvedSuggestions
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(`Export em ${langName} iniciado! Aguarde alguns minutos...`);
            // Refresh video list after delay
            setTimeout(() => loadVideos(), 5000);
        } else {
            alert('Erro: ' + (data.error || 'Erro desconhecido'));
        }
    })
    .catch(err => {
        alert('Erro ao exportar: ' + err.message);
    });
}

