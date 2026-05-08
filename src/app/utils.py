import os
import json
import glob
import re

from datetime import datetime

def format_file_size(size_bytes):
    return f'{size_bytes / (1024*1024):.2f} MB'

def format_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M')

def create_file_info(file_path, base_path, url_prefix):
    filename = os.path.basename(file_path)
    stat = os.stat(file_path)
    return {
        'filename': filename,
        'size': format_file_size(stat.st_size),
        'created': format_timestamp(stat.st_mtime),
        'path': f'/api/{url_prefix}/{filename}'
    }

def list_files(directory, pattern, url_prefix):
    files = glob.glob(os.path.join(directory, pattern))
    file_info_list = []
    for file_path in sorted(files, key=os.path.getmtime, reverse=True):
        file_info_list.append(create_file_info(file_path, directory, url_prefix))
    return file_info_list

def delete_files_by_pattern(directory, pattern):
    files = glob.glob(os.path.join(directory, pattern))
    deleted_count = 0
    for file_path in files:
        try:
            os.remove(file_path)
            deleted_count += 1
        except Exception:
            pass
    return deleted_count
