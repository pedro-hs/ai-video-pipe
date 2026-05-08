"""Centralized logging system - emits to both terminal (full) and frontend (terminal view)."""
import json
import os
from datetime import datetime
from typing import Optional
from constants import STATUS_FILE

# Log levels
LOG_INFO = 'info'
LOG_SUCCESS = 'success'
LOG_WARNING = 'warning'
LOG_ERROR = 'error'

# Terminal icons
TERMINAL_ICONS = {
    LOG_INFO: 'ℹ️',
    LOG_SUCCESS: '✅',
    LOG_WARNING: '⚠️',
    LOG_ERROR: '❌'
}


def _get_existing_logs():
    """Get existing logs from status file."""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r') as f:
                status = json.load(f)
                return status.get('logs', [])
    except:
        pass
    return []


def _add_log_to_status(level: str, message: str, step: Optional[str] = None, progress: Optional[str] = None):
    """Add log entry to status file."""
    try:
        logs = _get_existing_logs()
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'step': step,
            'progress': progress
        }
        
        # Keep only last 100 logs to avoid file bloat
        logs.append(log_entry)
        if len(logs) > 100:
            logs = logs[-100:]
        
        # Update status file with logs
        from status import get_status
        status = get_status()
        status['logs'] = logs
        
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        # Fallback: just print if status update fails
        print(f'Warning: Could not update status logs: {e}', flush=True)


def _format_terminal_message(level: str, message: str, step: Optional[str] = None, progress: Optional[str] = None) -> str:
    """Format message for terminal output."""
    icon = TERMINAL_ICONS.get(level, 'ℹ️')
    timestamp = datetime.now().strftime('%H:%M:%S')
    
    parts = [f'[{timestamp}] {icon} {message}']
    if step:
        parts.append(f'[Step: {step}]')
    if progress:
        parts.append(f'[Progress: {progress}]')
    
    return ' | '.join(parts)


def log(
    message: str,
    level: str = LOG_INFO,
    step: Optional[str] = None,
    progress: Optional[str] = None,
    stage: Optional[str] = None,
    progress_percent: Optional[int] = None,
    **status_kwargs
):
    """
    Centralized logging - emits to both terminal (full) and frontend (terminal view).
    
    Args:
        message: Log message
        level: Log level (info, success, warning, error)
        step: Current step name (e.g., 'generate_audio', 'generate_image', 'merge')
        progress: Progress string (e.g., '3/40 images', '3/6 batches')
        stage: Status stage (for status update)
        progress_percent: Progress percentage (0-100)
        **status_kwargs: Additional status parameters
    
    Examples:
        log('Starting video generation...')
        log('Generating images...', step='generate_image', progress='3/40 images', stage='generating', progress_percent=50)
        log('Failed to generate image', level=LOG_ERROR, step='generate_image')
    """
    # Terminal output (full details)
    terminal_msg = _format_terminal_message(level, message, step, progress)
    print(terminal_msg, flush=True)
    
    # Add to status logs (for frontend terminal view)
    _add_log_to_status(level, message, step, progress)
    
    # Update status if stage/progress provided
    if stage is not None or progress_percent is not None:
        # Build frontend message with step and progress
        frontend_message = message
        if step:
            frontend_message = f'[{step}] {frontend_message}'
        if progress:
            frontend_message = f'{frontend_message} ({progress})'
        
        from status import update_status
        update_status(
            stage=stage or 'idle',
            progress_percent=progress_percent or 0,
            message=frontend_message,
            **status_kwargs
        )


def log_step(step: str, message: str, current: Optional[int] = None, total: Optional[int] = None, **kwargs):
    """
    Convenience function for step logging with progress.
    
    Args:
        step: Step name (e.g., 'generate_image', 'generate_audio', 'merge')
        message: Log message
        current: Current item number
        total: Total items
        **kwargs: Additional log parameters
    
    Examples:
        log_step('generate_image', 'Generating images...', current=3, total=40)
    """
    progress = None
    if current is not None and total is not None:
        progress = f'{current}/{total}'
        # Add context based on step
        if 'image' in step.lower():
            progress += ' images'
        elif 'audio' in step.lower() or 'batch' in step.lower():
            progress += ' batches'
        elif 'merge' in step.lower():
            progress += ' segments'
    
    log(message, step=step, progress=progress, **kwargs)


def log_success(message: str, **kwargs):
    """Log success message."""
    log(message, level=LOG_SUCCESS, **kwargs)


def log_error(message: str, **kwargs):
    """Log error message."""
    log(message, level=LOG_ERROR, **kwargs)


def log_warning(message: str, **kwargs):
    """Log warning message."""
    log(message, level=LOG_WARNING, **kwargs)


