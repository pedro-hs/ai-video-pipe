"""Generate image prompts from narration script."""

import re
import time

from logger import log, log_success
from prompts import get_image_prompt
from ollama_client import call_ollama
from .utils import calculate_image_count_for_duration


def split_narration_by_sections(narration_file_path):
    """Split narration file into sections by silence markers."""
    try:
        with open(narration_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        sections = content.split('(silence)')
        sections = [section.strip() for section in sections if section.strip()]
        return sections
    except Exception as e:
        raise Exception(f'Failed to read narration file: {e}')


def count_words_in_text(text):
    """Count words in text."""
    return len([w for w in text.split() if w.strip()])


def calculate_section_word_counts(sections):
    """Calculate word counts for each section and total."""
    section_word_counts = []
    total_words = 0
    for section in sections:
        word_count = count_words_in_text(section)
        section_word_counts.append(word_count)
        total_words += word_count
    return section_word_counts, total_words


def calculate_prompts_per_section(section_index, section_word_counts, total_words, num_segments, total_sections):
    """Calculate how many prompts to generate for a section."""
    if total_words > 0:
        word_ratio = section_word_counts[section_index] / total_words
        return max(1, int(round(num_segments * word_ratio)))
    else:
        return max(1, num_segments // total_sections)


def clean_prompt_text(prompt_text):
    """Clean prompt text by removing special characters."""
    return prompt_text.replace('*', '').replace('[', '').replace(']', '').strip()


def parse_prompts_from_ollama_response(response, style):
    """Parse image prompts from Ollama response."""
    section_prompts = []
    response_lines = response.split('\n')
    for line in response_lines:
        line = line.strip()
        match = re.match(r'PROMPT\s*\d+\s*:?\s*(.+)', line, re.IGNORECASE)
        if match:
            prompt_text = clean_prompt_text(match.group(1))
            if prompt_text:
                section_prompts.append(f'{prompt_text}. {style}')
    return section_prompts


def generate_prompts_for_section(section, section_index, section_word_counts, total_words, num_segments, total_sections, style):
    """Generate image prompts for a single section."""
    if section_index > 0:
        time.sleep(0.5)

    prompts_per_section = calculate_prompts_per_section(
        section_index, section_word_counts, total_words, num_segments, total_sections
    )

    prompt = get_image_prompt(section, prompts_per_section)
    response = call_ollama(prompt)

    if not response or 'I can help you with?' in response:
        raise Exception(f'Failed to get response for section {section_index + 1}')

    return parse_prompts_from_ollama_response(response, style)


def normalize_prompt_count(all_prompts, num_segments, style):
    """Normalize prompt count to match expected number of segments."""
    if len(all_prompts) > num_segments:
        return all_prompts[:num_segments]
    elif len(all_prompts) < num_segments:
        while len(all_prompts) < num_segments:
            fallback_prompt = all_prompts[-1] if all_prompts else f'Default scene. {style}'
            all_prompts.append(fallback_prompt)
    return all_prompts


def generate_image_prompts_from_narration(narration_file_path, audio_duration, style):
    num_segments = calculate_image_count_for_duration(audio_duration)
    log(f'Calculating {num_segments} segments for {audio_duration:.1f}s audio', step='generate_prompts')

    sections = split_narration_by_sections(narration_file_path)

    if not sections:
        raise Exception('Narration file is empty or has no valid sections')

    section_word_counts, total_words = calculate_section_word_counts(sections)

    if total_words == 0:
        raise Exception('Narration sections have no words')

    all_prompts = []
    for i, section in enumerate(sections):
        section_prompts = generate_prompts_for_section(
            section, i, section_word_counts, total_words, num_segments, len(sections), style
        )
        if section_prompts:
            all_prompts.extend(section_prompts)

    all_prompts = normalize_prompt_count(all_prompts, num_segments, style)

    log_success(f'Generated {len(all_prompts)} image prompts', step='generate_prompts')
    return all_prompts

