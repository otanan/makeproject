"""
GitHub auto-updater for MakeProject.
Checks for updates, downloads release assets, and replaces the app bundle.
"""

import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Callable
from packaging import version
import requests

from PyQt6.QtCore import QThread, pyqtSignal, QObject

from . import __version__
from .library import UPDATES_DIR, ensure_directories

# GitHub repository info
GITHUB_REPO = "otanan/makeproject"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


class UpdateChecker(QThread):
    """Background thread to check for updates."""
    
    update_available = pyqtSignal(str, str)  # new_version, download_url
    no_update = pyqtSignal()
    error = pyqtSignal(str)
    
    def run(self):
        try:
            result = check_for_update()
            if result:
                new_version, download_url = result
                self.update_available.emit(new_version, download_url)
            else:
                self.no_update.emit()
        except Exception as e:
            self.error.emit(str(e))


class UpdateDownloader(QThread):
    """Background thread to download and install updates."""
    
    progress = pyqtSignal(int)  # 0-100
    finished = pyqtSignal(bool, str)  # success, message
    status = pyqtSignal(str)  # status message
    
    def __init__(self, download_url: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
    
    def run(self):
        try:
            # Check if app is in writable location
            app_path = get_app_path()
            if app_path and not is_writable_location(app_path):
                self.finished.emit(False, 
                    "Cannot update: App is in a protected location.\n"
                    "Please move the app to ~/Applications for automatic updates.")
                return
            
            self.status.emit("Downloading update...")
            
            # Download the update
            ensure_directories()
            zip_path = UPDATES_DIR / "update.zip"
            
            response = requests.get(self.download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        progress = int((downloaded / total_size) * 50)  # 0-50%
                        self.progress.emit(progress)
            
            self.status.emit("Extracting update...")
            self.progress.emit(60)
            
            # Extract the zip with ditto to preserve symlinks inside the app bundle.
            extract_path = UPDATES_DIR / "extracted"
            if extract_path.exists():
                shutil.rmtree(extract_path)
            extract_zip_with_ditto(zip_path, extract_path)
            
            self.progress.emit(80)
            
            # Find the .app in the extracted content
            new_app_path = find_app_in_directory(extract_path)
            if not new_app_path:
                self.finished.emit(False, "Update package does not contain a valid app.")
                return
            
            self.status.emit("Installing update...")
            self.progress.emit(90)
            
            # Replace the current app
            if app_path:
                success, message = replace_app(app_path, new_app_path)
                if success:
                    self.progress.emit(100)
                    self.status.emit("Update installed. Relaunching...")
                self.finished.emit(success, message)
            else:
                self.finished.emit(False, "Could not determine app location.")
                
        except requests.RequestException as e:
            self.finished.emit(False, f"Download failed: {str(e)}")
        except Exception as e:
            self.finished.emit(False, f"Update failed: {str(e)}")


def get_current_version() -> str:
    """Get the current app version."""
    return __version__


def parse_version(version_str: str) -> version.Version:
    """Parse a version string, handling 'v' prefix."""
    clean = version_str.lstrip('vV')
    return version.parse(clean)


def check_for_update() -> Optional[Tuple[str, str]]:
    """
    Check GitHub for a newer version.
    Returns (new_version, download_url) if update available, None otherwise.
    """
    try:
        headers = {'Accept': 'application/vnd.github.v3+json'}
        response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        tag_name = data.get('tag_name', '')
        
        if not tag_name:
            return None
        
        current = parse_version(get_current_version())
        latest = parse_version(tag_name)
        
        if latest > current:
            # Find the .zip asset
            assets = data.get('assets', [])
            for asset in assets:
                if asset.get('name', '').endswith('.zip'):
                    return (tag_name, asset.get('browser_download_url'))
            
            # Fallback to zipball_url
            zipball = data.get('zipball_url')
            if zipball:
                return (tag_name, zipball)
        
        return None
        
    except Exception:
        return None


def get_app_path() -> Optional[Path]:
    """Get the path to the current app bundle."""
    if hasattr(sys, 'frozen'):
        # Running as PyInstaller bundle
        exe_path = Path(sys.executable)
        # Navigate up to find .app
        current = exe_path
        while current.parent != current:
            if current.suffix == '.app':
                return current
            current = current.parent
    
    # Development mode - return None
    return None


def is_writable_location(app_path: Path) -> bool:
    """Check if the app location is writable."""
    try:
        # Check if we can write to the parent directory
        parent = app_path.parent
        test_file = parent / '.update_test'
        test_file.touch()
        test_file.unlink()
        return True
    except (PermissionError, OSError):
        return False


def find_app_in_directory(directory: Path) -> Optional[Path]:
    """Find a .app bundle in the given directory (recursive)."""
    for item in directory.rglob('*.app'):
        if item.is_dir():
            return item
    return None


def extract_zip_with_ditto(zip_path: Path, extract_path: Path) -> None:
    """Extract a zip file using ditto so symlinks are preserved."""
    extract_path.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["ditto", "-x", "-k", str(zip_path), str(extract_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "Unknown error"
        raise RuntimeError(f"Failed to extract update: {stderr}") from exc


def replace_app(old_app: Path, new_app: Path) -> Tuple[bool, str]:
    """Replace the old app with the new one."""
    try:
        backup_path = old_app.parent / f"{old_app.stem}_backup.app"
        
        # Remove old backup if exists
        if backup_path.exists():
            shutil.rmtree(backup_path)
        
        # Move current app to backup
        shutil.move(str(old_app), str(backup_path))
        
        # Move new app to location
        shutil.move(str(new_app), str(old_app))
        
        # Remove backup
        shutil.rmtree(backup_path)
        
        return True, "Update installed successfully."
        
    except Exception as e:
        # Try to restore backup
        if backup_path.exists() and not old_app.exists():
            shutil.move(str(backup_path), str(old_app))
        return False, f"Failed to replace app: {str(e)}"


def relaunch_app(app_path: Path) -> bool:
    """Relaunch the application."""
    try:
        # Use open command on macOS
        subprocess.Popen(['open', '-n', str(app_path)], start_new_session=True)
        return True
    except Exception:
        return False  # Failed to relaunch, user can do it manually


def cleanup_updates():
    """Clean up any leftover update files."""
    try:
        if UPDATES_DIR.exists():
            for item in UPDATES_DIR.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
    except Exception:
        pass  # Cleanup failures are non-critical
