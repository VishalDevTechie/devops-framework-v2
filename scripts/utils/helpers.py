# scripts/utils/helpers.py
import subprocess
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

def run_command(command: str, cwd: Optional[str] = None, timeout: int = 600) -> Dict[str, Any]:
    """Execute a shell command and return results"""
    print(f" Executing: {command}")
    if cwd:
        print(f"   Working directory: {cwd}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'command': command
        }
    
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': f'Command timed out after {timeout} seconds',
            'command': command
        }
    except Exception as e:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': str(e),
            'command': command
        }

def ensure_directory(directory_path: str) -> None:
    """Ensure directory exists"""
    Path(directory_path).mkdir(parents=True, exist_ok=True)

def find_files(directory: str, pattern: str) -> List[str]:
    """Find files matching pattern in directory"""
    path = Path(directory)
    if not path.exists():
        return []
    
    return [str(f) for f in path.rglob(pattern) if f.is_file()]

def copy_file(src: str, dst: str) -> bool:
    """Copy file from src to dst"""
    try:
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f" Failed to copy {src} to {dst}: {e}")
        return False

def get_file_size(file_path: str) -> int:
    """Get file size in bytes"""
    try:
        return Path(file_path).stat().st_size
    except:
        return 0

def format_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"