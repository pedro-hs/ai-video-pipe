"""Paragraph analysis and Ollama-based duration adjustment suggestions."""

import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from logger import log, log_error
from audio.generate import generate_audio, split_narration_by_phrases
from audio.files import get_audio_duration
from audio.utils import combine_audio_segments_with_silence, DEFAULT_SILENCE_DURATION, LANGUAGE_GAP_DURATIONS, DEFAULT_GAP_DURATION
from constants import AUDIO_EXTENSION
from ollama_client import call_ollama
import soundfile as sf
import numpy as np
from audio.piper import _load_piper_voice, _load_piper_voice_english, _load_piper_voice_spanish, _generate_speech_with_piper


# Ollama prompt templates
PARAGRAPH_EXPAND_PROMPT = '''You are helping to adjust a narration paragraph to match a specific duration when spoken.

The paragraph needs to be exactly {duration_diff:.1f} seconds LONGER when spoken.

Current paragraph text:
{paragraph_text}

Suggest 4 specific phrases or sentences to ADD that:
- Your response should have the same language of paragraph text
- Maintain the narrative flow and meaning
- Add relevant details, context, or descriptions
- Don't repeat information of the paragraph
- Keep the same tone and style
- Are natural and fit seamlessly into the text
- Will add exactly {duration_diff:.1f} seconds when spoken

Return ONLY the suggested additions, one per line, prefixed with "ADD:". Do not rewrite the entire paragraph.
Example format:
ADD: in the ancient times, when these practices were common
ADD: as archaeological evidence suggests
ADD: during this remarkable period of history

If you cannot suggest good additions, return "NO_SUGGESTIONS".'''

PARAGRAPH_REDUCE_PROMPT = '''You are helping to adjust a narration paragraph to match a specific duration when spoken.

The paragraph needs to be exactly {duration_diff:.1f} seconds SHORTER when spoken.

Current paragraph text:
{paragraph_text}

Suggest 1-3 specific phrases or sentences to REMOVE that:
- Are less essential to the main message
- Can be removed without losing core meaning
- Are redundant or overly descriptive
- Will reduce approximately {duration_diff:.1f} seconds when spoken

Return ONLY the phrases to remove, one per line, prefixed with "REMOVE:". Copy the exact text to remove.
Example format:
REMOVE: as we all know
REMOVE: in many different ways throughout history
REMOVE: which is something that historians have debated

If you cannot suggest good removals, return "NO_SUGGESTIONS".'''


def split_narration_by_paragraphs(narration_text):
    """Split narration by (silence) markers into paragraphs.
    
    Handles variations like '(silence)', ' (silence)', '(silence) ', ' (silence) '.
    
    Returns:
        list: List of paragraph texts (strings), without (silence) markers
    """
    if not narration_text:
        return []
    
    # Normalize the text - replace variations of (silence) with a consistent marker
    import re
    # Match (silence) with optional whitespace around it
    normalized = re.sub(r'\s*\(silence\)\s*', '|||SILENCE|||', narration_text)
    
    # Split by the marker
    parts = normalized.split('|||SILENCE|||')
    
    paragraphs = []
    for part in parts:
        part = part.strip()
        if part:
            paragraphs.append(part)
    
    # If no (silence) markers found, return the whole text as one paragraph
    if len(paragraphs) == 0 and narration_text.strip():
        paragraphs = [narration_text.strip()]
    
    return paragraphs


def combine_paragraphs_with_silence(paragraphs):
    """Combine paragraphs with (silence) markers.
    
    Args:
        paragraphs: List of paragraph texts
        
    Returns:
        str: Combined narration with (silence) markers
    """
    return ' (silence) '.join(paragraphs)


def get_paragraph_phrases(paragraph_text):
    """Get list of phrases from a paragraph (for audio generation).
    
    Args:
        paragraph_text: Paragraph text (may contain (nosilence) markers)
        
    Returns:
        tuple: (phrases, silence_positions, nosilence_positions)
    """
    return split_narration_by_phrases(paragraph_text)


def generate_temp_paragraph_audio(paragraph_text, language, temp_dir, paragraph_index=None):
    """Generate temporary audio for a paragraph to measure duration.
    
    Args:
        paragraph_text: Paragraph text
        language: Language code ('en', 'es', 'pt')
        temp_dir: Temporary directory for audio files
        paragraph_index: Optional paragraph index for logging (to show which paragraph is being processed)
        
    Returns:
        float: Duration in seconds
    """
    try:
        # Log which paragraph is being processed (if index provided)
        if paragraph_index is not None:
            log(f'Generating audio for paragraph {paragraph_index + 1} only (language: {language})', step='recalculate_duration')
        
        # Get phrases from paragraph
        phrases, silence_positions, nosilence_positions = get_paragraph_phrases(paragraph_text)
        
        if not phrases:
            return 0.0
        
        # Create unique temp audio segments directory for this paragraph to avoid conflicts
        # Use paragraph_index if provided, otherwise generate unique identifier
        if paragraph_index is not None:
            temp_segments_dir = os.path.join(temp_dir, f'temp_segments_para_{paragraph_index}')
        else:
            temp_segments_dir = os.path.join(temp_dir, f'temp_segments_{uuid.uuid4().hex[:8]}')
        os.makedirs(temp_segments_dir, exist_ok=True)
        
        # Load appropriate voice
        if language == 'en':
            voice = _load_piper_voice_english()
        elif language == 'es':
            voice = _load_piper_voice_spanish()
        else:
            voice = _load_piper_voice()
        
        # Generate audio for each phrase
        audio_segment_paths = []
        for i, phrase in enumerate(phrases):
            output_path = os.path.join(temp_segments_dir, f'temp_{i}.{AUDIO_EXTENSION}')
            _generate_speech_with_piper(voice, phrase, output_path, language)
            if os.path.exists(output_path):
                audio_segment_paths.append(output_path)
        
        if not audio_segment_paths:
            return 0.0
        
        # Combine with silence - use unique output filename to avoid conflicts
        if paragraph_index is not None:
            temp_output = os.path.join(temp_dir, f'temp_paragraph_{paragraph_index}.{AUDIO_EXTENSION}')
        else:
            temp_output = os.path.join(temp_dir, f'temp_paragraph_{uuid.uuid4().hex[:8]}.{AUDIO_EXTENSION}')
        gap_duration = LANGUAGE_GAP_DURATIONS.get(language, DEFAULT_GAP_DURATION)
        
        combine_audio_segments_with_silence(
            audio_segment_paths,
            temp_output,
            silence_duration=DEFAULT_SILENCE_DURATION,
            silence_positions=silence_positions,
            nosilence_positions=nosilence_positions,
            language=language
        )
        
        # Get duration
        if os.path.exists(temp_output):
            duration = get_audio_duration(audio_path=temp_output)
            if paragraph_index is not None:
                log(f'Paragraph {paragraph_index + 1} duration: {duration:.2f}s', step='recalculate_duration')
            return duration
        
        return 0.0
    except Exception as e:
        log_error(f'Error generating temp paragraph audio: {e}', step='paragraph_analysis')
        return 0.0


def get_portuguese_paragraph_durations(video_folder):
    """Get duration of each Portuguese paragraph from original audio segments.
    
    Uses the original audio segments instead of generating new audio to ensure
    exact match with the video's audio duration and much faster processing.
    
    Args:
        video_folder: Path to video folder
        
    Returns:
        list: List of durations in seconds for each paragraph
    """
    try:
        # Read Portuguese narration
        pt_folder = os.path.join(video_folder, 'narration', 'pt')
        pt_narration_file = os.path.join(pt_folder, 'narration.txt')
        
        if not os.path.exists(pt_narration_file):
            raise Exception(f'Portuguese narration file not found: {pt_narration_file}')
        
        with open(pt_narration_file, 'r', encoding='utf-8') as f:
            pt_narration = f.read()
        
        # Split into paragraphs
        pt_paragraphs = split_narration_by_paragraphs(pt_narration)
        
        # Get original audio segments directory
        audio_segments_dir = os.path.join(pt_folder, 'audio_segments')
        
        # Check if original audio segments exist
        if not os.path.exists(audio_segments_dir):
            raise Exception(f'Original audio segments directory not found: {audio_segments_dir}. Cannot measure paragraph durations without original audio.')
        
        # Split full narration into phrases to map paragraphs to audio segments
        from audio.generate import split_narration_by_phrases
        all_phrases, silence_positions, nosilence_positions = split_narration_by_phrases(pt_narration)
        
        # Map each paragraph to its phrases
        paragraph_phrase_ranges = []
        current_phrase_idx = 0
        
        for para_idx, paragraph in enumerate(pt_paragraphs):
            # Split this paragraph into phrases
            para_phrases, _, _ = split_narration_by_phrases(paragraph)
            
            if not para_phrases:
                paragraph_phrase_ranges.append((current_phrase_idx, current_phrase_idx))
                continue
            
            # Find where these phrases start in the full phrase list
            start_idx = current_phrase_idx
            end_idx = start_idx + len(para_phrases)
            
            # Verify by matching first phrase
            if start_idx < len(all_phrases) and para_phrases:
                if all_phrases[start_idx].strip() != para_phrases[0].strip():
                    # Try to find matching phrase
                    for i in range(len(all_phrases)):
                        if i >= start_idx and i < len(all_phrases) and all_phrases[i].strip() == para_phrases[0].strip():
                            start_idx = i
                            end_idx = start_idx + len(para_phrases)
                            break
            
            paragraph_phrase_ranges.append((start_idx, end_idx))
            current_phrase_idx = end_idx
        
        # Calculate duration for each paragraph using original audio segments
        durations = []
        from audio.utils import LANGUAGE_GAP_DURATIONS, DEFAULT_GAP_DURATION, DEFAULT_SILENCE_DURATION
        
        for para_idx, (start_phrase_idx, end_phrase_idx) in enumerate(paragraph_phrase_ranges):
            paragraph_duration = 0.0
            
            # Sum durations of audio segments for this paragraph's phrases
            for phrase_idx in range(start_phrase_idx, end_phrase_idx):
                segment_path = os.path.join(audio_segments_dir, f'narration_{phrase_idx}.{AUDIO_EXTENSION}')
                
                if os.path.exists(segment_path):
                    segment_duration = get_audio_duration(audio_path=segment_path)
                    paragraph_duration += segment_duration
                    
                    # Add gap between phrases (except last phrase in paragraph)
                    if phrase_idx < end_phrase_idx - 1:
                        gap_duration = LANGUAGE_GAP_DURATIONS.get('pt', DEFAULT_GAP_DURATION)
                        paragraph_duration += gap_duration
                else:
                    log(f'Warning: Audio segment not found: {segment_path}', step='paragraph_analysis')
            
            # Add silence after paragraph (if not last paragraph)
            if para_idx < len(pt_paragraphs) - 1:
                # Check if there's a silence marker after this paragraph
                paragraph_duration += DEFAULT_SILENCE_DURATION
            
            durations.append(paragraph_duration)
            log(f'Paragraph {para_idx + 1} duration from original audio: {paragraph_duration:.2f}s', step='paragraph_analysis')
        
        # Validate against total audio duration
        pt_audio_file = os.path.join(pt_folder, f'narration_0.{AUDIO_EXTENSION}')
        if os.path.exists(pt_audio_file):
            total_pt_duration = get_audio_duration(audio_path=pt_audio_file)
            calculated_total = sum(durations)
            
            log(f'Total PT duration from audio file: {total_pt_duration:.2f}s, Calculated from paragraphs: {calculated_total:.2f}s', step='paragraph_analysis')
            
            # If there's a significant difference, adjust proportions
            if abs(total_pt_duration - calculated_total) > 1.0:
                log(f'Adjusting paragraph durations to match total audio duration (diff: {abs(total_pt_duration - calculated_total):.2f}s)', step='paragraph_analysis')
                if calculated_total > 0:
                    adjustment_factor = total_pt_duration / calculated_total
                    durations = [d * adjustment_factor for d in durations]
                    log(f'Adjusted all paragraph durations by factor {adjustment_factor:.4f}', step='paragraph_analysis')
        
        return durations
        
    except Exception as e:
        log_error(f'Error getting Portuguese paragraph durations from original audio: {e}', step='paragraph_analysis')
        raise


def measure_phrase_duration(phrase_text, language, temp_dir):
    """Measure duration of a single phrase when spoken.
    
    Args:
        phrase_text: Single phrase text
        language: Language code ('en', 'es', 'pt')
        temp_dir: Temporary directory for audio files
        
    Returns:
        float: Duration in seconds
    """
    try:
        if not phrase_text or not phrase_text.strip():
            return 0.0
        
        # Create temp audio file with unique name based on phrase hash
        import hashlib
        phrase_hash = hashlib.md5(phrase_text.encode()).hexdigest()[:8]
        temp_output = os.path.join(temp_dir, f'temp_phrase_{phrase_hash}.{AUDIO_EXTENSION}')
        
        # Load appropriate voice
        if language == 'en':
            voice = _load_piper_voice_english()
        elif language == 'es':
            voice = _load_piper_voice_spanish()
        else:
            voice = _load_piper_voice()
        
        # Generate audio for the phrase
        _generate_speech_with_piper(voice, phrase_text.strip(), temp_output, language)
        
        if os.path.exists(temp_output):
            duration = get_audio_duration(audio_path=temp_output)
            return duration
        
        return 0.0
    except Exception as e:
        log_error(f'Error measuring phrase duration: {e}', step='paragraph_analysis')
        return 0.0


def get_ollama_suggestions(paragraph_text, duration_diff, language):
    """Get Ollama suggestions for adjusting paragraph duration.
    
    Args:
        paragraph_text: Paragraph text to adjust
        duration_diff: Duration difference needed (positive = add, negative = remove)
        language: Language code ('en', 'es')
        
    Returns:
        dict: {'add': [{'text': str, 'duration': float}, ...], 'remove': [{'text': str, 'duration': float}, ...]}
    """
    try:
        if duration_diff > 0:
            # Need to add content
            prompt = PARAGRAPH_EXPAND_PROMPT.format(
                paragraph_text=paragraph_text,
                duration_diff=duration_diff
            )
        else:
            # Need to remove content
            prompt = PARAGRAPH_REDUCE_PROMPT.format(
                paragraph_text=paragraph_text,
                duration_diff=abs(duration_diff)
            )
        
        response = call_ollama(prompt)
        
        suggestions = {'add': [], 'remove': []}
        temp_dir = tempfile.mkdtemp()
        
        try:
            for line in response.split('\n'):
                line = line.strip()
                if not line or line == 'NO_SUGGESTIONS':
                    continue
                
                if line.startswith('ADD:'):
                    suggestion_text = line[4:].strip()
                    if suggestion_text:
                        # Measure duration of this suggestion
                        duration = measure_phrase_duration(suggestion_text, language, temp_dir)
                        suggestions['add'].append({
                            'text': suggestion_text,
                            'duration': round(duration, 2)
                        })
                elif line.startswith('REMOVE:'):
                    suggestion_text = line[7:].strip()
                    if suggestion_text:
                        # For removals, measure the phrase duration
                        duration = measure_phrase_duration(suggestion_text, language, temp_dir)
                        suggestions['remove'].append({
                            'text': suggestion_text,
                            'duration': round(duration, 2)
                        })
        finally:
            # Clean up temp directory
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass
        
        return suggestions
    except Exception as e:
        log_error(f'Error getting Ollama suggestions: {e}', step='paragraph_analysis')
        return {'add': [], 'remove': []}


def get_portuguese_paragraphs(video_folder):
    """Get Portuguese paragraphs from narration file.
    
    Args:
        video_folder: Path to video folder
        
    Returns:
        list: List of Portuguese paragraph texts
    """
    try:
        pt_folder = os.path.join(video_folder, 'narration', 'pt')
        pt_narration_file = os.path.join(pt_folder, 'narration.txt')
        
        if not os.path.exists(pt_narration_file):
            raise Exception(f'Portuguese narration file not found: {pt_narration_file}')
        
        with open(pt_narration_file, 'r', encoding='utf-8') as f:
            pt_narration = f.read()
        
        return split_narration_by_paragraphs(pt_narration)
    except Exception as e:
        log_error(f'Error getting Portuguese paragraphs: {e}', step='paragraph_analysis')
        raise


def analyze_narration_for_adjustment(video_folder, narration_text, language):
    """Analyze narration and get suggestions for duration adjustment.
    
    Args:
        video_folder: Path to video folder
        narration_text: Narration text in target language
        language: Language code ('en', 'es')
        
    Returns:
        dict: {
            'paragraphs': list of paragraph analysis dicts with suggestions,
            'portuguese_paragraphs': list of Portuguese paragraph texts,
            'total_pt_duration': total duration of Portuguese audio (for validation)
        }
    """
    try:
        log(f'Analyzing {language} narration for duration adjustment...', step='paragraph_analysis')
        
        # Get Portuguese paragraphs and their durations from ORIGINAL audio
        pt_paragraphs = get_portuguese_paragraphs(video_folder)
        pt_durations = get_portuguese_paragraph_durations(video_folder)
        
        # Get total duration from original audio file for validation
        pt_folder = os.path.join(video_folder, 'narration', 'pt')
        pt_audio_file = os.path.join(pt_folder, f'narration_0.{AUDIO_EXTENSION}')
        if os.path.exists(pt_audio_file):
            total_pt_duration = get_audio_duration(audio_path=pt_audio_file)
        else:
            total_pt_duration = sum(pt_durations)
        
        # Split target narration into paragraphs
        paragraphs = split_narration_by_paragraphs(narration_text)
        
        if len(paragraphs) != len(pt_durations) or len(paragraphs) != len(pt_paragraphs):
            log_error(
                f'Paragraph count mismatch: {language} has {len(paragraphs)}, Portuguese has {len(pt_paragraphs)} paragraphs and {len(pt_durations)} durations',
                step='paragraph_analysis'
            )
            # Try to match as best as possible
            min_count = min(len(paragraphs), len(pt_durations), len(pt_paragraphs))
            paragraphs = paragraphs[:min_count]
            pt_durations = pt_durations[:min_count]
            pt_paragraphs = pt_paragraphs[:min_count]
        
        # Analyze each paragraph - first measure all durations
        results = []
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Step 1: Measure all paragraph durations first
            paragraph_data = []
            for i, paragraph in enumerate(paragraphs):
                log(f'Measuring paragraph {i+1}/{len(paragraphs)} duration...', step='paragraph_analysis')
                
                # Generate temp audio to measure duration - pass index to ensure unique file paths
                current_duration = generate_temp_paragraph_audio(paragraph, language, temp_dir, paragraph_index=i)
                target_duration = pt_durations[i] if i < len(pt_durations) else current_duration
                duration_diff = target_duration - current_duration
                
                paragraph_data.append({
                    'index': i,
                    'paragraph': paragraph,
                    'current_duration': current_duration,
                    'target_duration': target_duration,
                    'duration_diff': duration_diff,
                    'needs_suggestions': abs(duration_diff) > 2.0
                })
            
            # Step 2: Parallelize Ollama calls for paragraphs that need suggestions
            paragraphs_needing_suggestions = [
                (data['index'], data['paragraph'], data['duration_diff'])
                for data in paragraph_data
                if data['needs_suggestions']
            ]
            
            suggestions_dict = {}
            if paragraphs_needing_suggestions:
                log(f'Getting Ollama suggestions for {len(paragraphs_needing_suggestions)} paragraphs in parallel...', step='paragraph_analysis')
                
                with ThreadPoolExecutor(max_workers=3) as executor:
                    # Submit all Ollama calls
                    future_to_index = {
                        executor.submit(get_ollama_suggestions, paragraph, duration_diff, language): index
                        for index, paragraph, duration_diff in paragraphs_needing_suggestions
                    }
                    
                    # Collect results as they complete
                    for future in as_completed(future_to_index):
                        index = future_to_index[future]
                        try:
                            suggestions = future.result()
                            suggestions_dict[index] = suggestions
                            log(f'Got suggestions for paragraph {index + 1}', step='paragraph_analysis')
                        except Exception as e:
                            log_error(f'Error getting suggestions for paragraph {index + 1}: {e}', step='paragraph_analysis')
                            suggestions_dict[index] = {'add': [], 'remove': []}
            
            # Step 3: Build final results
            for data in paragraph_data:
                suggestions = suggestions_dict.get(data['index'], {'add': [], 'remove': []})
                results.append({
                    'index': data['index'],
                    'original_text': data['paragraph'],
                    'portuguese_text': pt_paragraphs[data['index']] if data['index'] < len(pt_paragraphs) else '',
                    'current_duration': round(data['current_duration'], 2),
                    'target_duration': round(data['target_duration'], 2),
                    'difference': round(data['duration_diff'], 2),
                    'suggestions': suggestions
                })
            
            # Calculate total duration for target language (including silences between paragraphs)
            # Portuguese already includes silences in each paragraph duration
            # For English/Spanish, we need to add silences between paragraphs
            total_current_duration = sum(data['current_duration'] for data in paragraph_data)
            # Add silences between paragraphs (same as Portuguese calculation)
            if len(paragraph_data) > 1:
                total_current_duration += (len(paragraph_data) - 1) * DEFAULT_SILENCE_DURATION
        finally:
            # Clean up temp directory
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass
        
        return {
            'paragraphs': results,
            'portuguese_paragraphs': pt_paragraphs,
            'total_pt_duration': total_pt_duration,
            'total_current_duration': round(total_current_duration, 2) if 'total_current_duration' in locals() else sum(p.get('current_duration', 0) for p in results)
        }
    except Exception as e:
        log_error(f'Error analyzing narration: {e}', step='paragraph_analysis')
        raise


def apply_suggestions_to_paragraph(paragraph_text, suggestions, approved_add, approved_remove):
    """Apply approved suggestions to a paragraph.
    
    Args:
        paragraph_text: Original paragraph text
        suggestions: Dict with 'add' and 'remove' lists (now contains objects with 'text' and 'duration')
        approved_add: List of indices of approved additions
        approved_remove: List of indices of approved removals
        
    Returns:
        str: Adjusted paragraph text
    """
    adjusted = paragraph_text
    
    # Apply removals first (to avoid index issues)
    remove_items = []
    for i in approved_remove:
        if i < len(suggestions['remove']):
            item = suggestions['remove'][i]
            # Handle both old format (string) and new format (object)
            remove_text = item if isinstance(item, str) else item.get('text', '')
            if remove_text:
                remove_items.append(remove_text)
    
    for item in remove_items:
        # Remove the exact phrase (case-insensitive, handle punctuation)
        import re
        pattern = re.escape(item)
        adjusted = re.sub(pattern, '', adjusted, flags=re.IGNORECASE)
        adjusted = re.sub(r'\s+', ' ', adjusted)  # Clean up extra spaces
        adjusted = adjusted.strip()
    
    # Apply additions (add at the end for simplicity, or could be smarter)
    add_items = []
    for i in approved_add:
        if i < len(suggestions['add']):
            item = suggestions['add'][i]
            # Handle both old format (string) and new format (object)
            add_text = item if isinstance(item, str) else item.get('text', '')
            if add_text:
                add_items.append(add_text)
    
    if add_items:
        # Add before the last sentence (before last period)
        if adjusted.rstrip().endswith('.'):
            last_period_idx = adjusted.rstrip().rfind('.')
            before_last = adjusted[:last_period_idx].rstrip()
            last_sentence = adjusted[last_period_idx:].strip()
            additions = '. '.join(add_items)
            adjusted = f'{before_last}. {additions}. {last_sentence}'
        else:
            # No period, just append
            additions = '. '.join(add_items)
            adjusted = f'{adjusted}. {additions}'
    
    return adjusted.strip()

