"""
Utility functions for document processing
"""
import os
import shutil
from pathlib import Path
import logging

def setup_directories(*directories):
    """Create multiple directories if they don't exist"""
    for directory in directories:
        if directory:
            os.makedirs(directory, exist_ok=True)
            logging.info(f"Created/verified directory: {directory}")

def safe_move_file(source_path, dest_path, handle_duplicates=True):
    """Safely move a file, handling duplicates if needed"""
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file does not exist: {source_path}")
    
    # Ensure destination directory exists
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
    
    # Handle duplicates
    if handle_duplicates and os.path.exists(dest_path):
        dest_path = get_unique_filename(dest_path)
    
    shutil.move(source_path, dest_path)
    return dest_path

def get_unique_filename(file_path):
    """Generate unique filename if file already exists"""
    if not os.path.exists(file_path):
        return file_path
    
    base_path, ext = os.path.splitext(file_path)
    counter = 1
    
    while os.path.exists(file_path):
        file_path = f"{base_path}_{counter:02d}{ext}"
        counter += 1
    
    return file_path

def clean_filename(filename):
    """Clean filename for cross-platform compatibility"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove multiple underscores
    while '__' in filename:
        filename = filename.replace('__', '_')
    
    # Remove leading/trailing underscores and spaces
    filename = filename.strip('_ ')
    
    return filename

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def get_file_info(file_path):
    """Get basic file information"""
    if not os.path.exists(file_path):
        return None
    
    stat = os.stat(file_path)
    return {
        'size': stat.st_size,
        'size_formatted': format_file_size(stat.st_size),
        'created': stat.st_ctime,
        'modified': stat.st_mtime,
        'extension': os.path.splitext(file_path)[1].lower()
    }

def count_files_by_extension(directory, recursive=True):
    """Count files by extension in a directory"""
    counts = {}
    
    if recursive:
        for root, dirs, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                counts[ext] = counts.get(ext, 0) + 1
    else:
        for file in os.listdir(directory):
            if os.path.isfile(os.path.join(directory, file)):
                ext = os.path.splitext(file)[1].lower()
                counts[ext] = counts.get(ext, 0) + 1
    
    return counts

def backup_file(file_path, backup_dir=None):
    """Create a backup of a file before processing"""
    if not os.path.exists(file_path):
        return None
    
    if backup_dir is None:
        backup_dir = os.path.join(os.path.dirname(file_path), '_backup')
    
    os.makedirs(backup_dir, exist_ok=True)
    
    filename = os.path.basename(file_path)
    backup_path = os.path.join(backup_dir, filename)
    backup_path = get_unique_filename(backup_path)
    
    shutil.copy2(file_path, backup_path)
    logging.info(f"Created backup: {backup_path}")
    
    return backup_path

class ProgressTracker:
    """Simple progress tracking for file operations"""
    
    def __init__(self, total_items, callback=None):
        self.total_items = total_items
        self.completed_items = 0
        self.callback = callback
        self.start_time = None
    
    def start(self):
        """Start progress tracking"""
        import time
        self.start_time = time.time()
        self._update()
    
    def increment(self, items=1):
        """Increment progress"""
        self.completed_items += items
        self._update()
    
    def _update(self):
        """Update progress display"""
        if self.callback:
            percentage = (self.completed_items / self.total_items) * 100
            self.callback(self.completed_items, self.total_items, percentage)
        
        if self.completed_items % 10 == 0 or self.completed_items == self.total_items:
            print(f"Progress: {self.completed_items}/{self.total_items} ({self.completed_items/self.total_items*100:.1f}%)")
    
    def finish(self):
        """Finish progress tracking"""
        if self.start_time:
            import time
            elapsed = time.time() - self.start_time
            print(f"Completed {self.total_items} items in {elapsed:.1f} seconds")
