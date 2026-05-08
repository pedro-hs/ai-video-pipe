"""Audio quality improvement functions."""

import numpy as np
from scipy import signal


def reduce_metallic_frequencies(audio, sample_rate):
    """
    Reduce metallic frequencies (1.5-5kHz range) without affecting voice clarity.
    Uses multiple notch filters to target common metallic resonances.
    
    Args:
        audio: Audio array (numpy array)
        sample_rate: Sample rate in Hz
    
    Returns:
        Audio array with reduced metallic frequencies
    """
    # Convert to float32 if needed
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
    
    # Metallic sounds often occur in 1.5-5kHz range, with peaks at different frequencies
    # Use multiple notch filters to target common metallic resonances
    
    # First notch: target 2.5kHz (common metallic resonance causing "duplicated" sound)
    center_freq1 = 2500
    q_factor1 = 1.8  # Moderate bandwidth
    gain_db1 = -7.0  # Stronger reduction to eliminate metallic artifacts
    
    w0_1 = 2 * np.pi * center_freq1 / sample_rate
    alpha_1 = np.sin(w0_1) / (2 * q_factor1)
    A_1 = 10 ** (gain_db1 / 40)
    cos_w0_1 = np.cos(w0_1)
    
    b0_1 = 1 + alpha_1 * A_1
    b1_1 = -2 * cos_w0_1
    b2_1 = 1 - alpha_1 * A_1
    a0_1 = 1 + alpha_1 / A_1
    a1_1 = -2 * cos_w0_1
    a2_1 = 1 - alpha_1 / A_1
    
    b_1 = np.array([b0_1, b1_1, b2_1]) / a0_1
    a_1 = np.array([1, a1_1 / a0_1, a2_1 / a0_1])
    
    audio = signal.lfilter(b_1, a_1, audio)
    
    # Second notch: target 3.2kHz (upper metallic range)
    center_freq2 = 3200
    q_factor2 = 1.8
    gain_db2 = -5.0  # Slightly less aggressive
    
    w0_2 = 2 * np.pi * center_freq2 / sample_rate
    alpha_2 = np.sin(w0_2) / (2 * q_factor2)
    A_2 = 10 ** (gain_db2 / 40)
    cos_w0_2 = np.cos(w0_2)
    
    b0_2 = 1 + alpha_2 * A_2
    b1_2 = -2 * cos_w0_2
    b2_2 = 1 - alpha_2 * A_2
    a0_2 = 1 + alpha_2 / A_2
    a1_2 = -2 * cos_w0_2
    a2_2 = 1 - alpha_2 / A_2
    
    b_2 = np.array([b0_2, b1_2, b2_2]) / a0_2
    a_2 = np.array([1, a1_2 / a0_2, a2_2 / a0_2])
    
    audio = signal.lfilter(b_2, a_2, audio)
    
    return audio


def smooth_voice(audio, sample_rate):
    """
    Smooth the voice by reducing harshness without muffling.
    Keeps voice clear as the original.
    
    Args:
        audio: Audio array (numpy array)
        sample_rate: Sample rate in Hz
    
    Returns:
        Smoothed audio array
    """
    # Convert to float32 if needed
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
    
    # 1. Very gentle high-frequency roll-off to reduce harshness (above 12kHz)
    # Higher cutoff and lower order to prevent muffling while still reducing harshness
    # Only affects very high frequencies that contribute to harshness, not clarity
    nyquist = sample_rate / 2
    high_cutoff_desired = 12000  # Desired cutoff frequency
    
    # Ensure cutoff doesn't exceed Nyquist frequency (normalized freq must be < 1)
    # Use 0.95 of Nyquist as maximum to stay safely below 1
    high_cutoff = min(high_cutoff_desired, nyquist * 0.95)
    
    # Only apply filter if cutoff is reasonable (at least 5kHz)
    if high_cutoff >= 5000:
        sos_high = signal.butter(2, high_cutoff / nyquist, btype='low', output='sos')  # Lower order (was 4)
        audio = signal.sosfilt(sos_high, audio)
    
    # 2. Very gentle de-esser: reduce sibilance only when needed
    # Reduced gain and narrower bandwidth to prevent muffling
    deess_center_desired = 7000  # Desired center frequency
    
    # Ensure de-esser center doesn't exceed Nyquist
    deess_center = min(deess_center_desired, nyquist * 0.95)
    
    # Only apply de-esser if center frequency is reasonable
    if deess_center >= 4000:
        deess_q = 4.0  # Narrower bandwidth to be more selective
        deess_gain = -1.2  # Very gentle reduction (was -2.0) to prevent muffling
        
        w0_deess = 2 * np.pi * deess_center / sample_rate
        alpha_deess = np.sin(w0_deess) / (2 * deess_q)
        A_deess = 10 ** (deess_gain / 40)
        cos_w0_deess = np.cos(w0_deess)
        
        b0_deess = 1 + alpha_deess * A_deess
        b1_deess = -2 * cos_w0_deess
        b2_deess = 1 - alpha_deess * A_deess
        a0_deess = 1 + alpha_deess / A_deess
        a1_deess = -2 * cos_w0_deess
        a2_deess = 1 - alpha_deess / A_deess
        
        b_deess = np.array([b0_deess, b1_deess, b2_deess]) / a0_deess
        a_deess = np.array([1, a1_deess / a0_deess, a2_deess / a0_deess])
        
        audio = signal.lfilter(b_deess, a_deess, audio)
    
    return audio


def enhance_audio_quality(audio, sample_rate):
    """
    Enhance audio quality: apply metallic reduction and voice smoothing.
    Keeps voice clear as the original.
    
    Args:
        audio: Audio array (numpy array)
        sample_rate: Sample rate in Hz
    
    Returns:
        Enhanced audio array
    """
    # Normalize to prevent clipping before processing
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.95
    
    # Apply metallic frequency reduction
    audio = reduce_metallic_frequencies(audio, sample_rate)
    
    # Apply voice smoothing
    audio = smooth_voice(audio, sample_rate)
    
    # Final normalization to prevent clipping
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.95
    
    return audio

