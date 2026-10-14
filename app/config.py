import os
import shutil
import ipaddress
import logging
import sys
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", BASE_DIR / "workspace"))

UPLOADS_DIR = WORKSPACE_DIR / "uploads"
AUDIO_DIR = WORKSPACE_DIR / "audio"
SUBTITLES_DIR = WORKSPACE_DIR / "subtitles"
SEGMENTS_DIR = WORKSPACE_DIR / "segments"
PACKAGES_DIR = WORKSPACE_DIR / "packages"
SHORTS_DIR = WORKSPACE_DIR / "shorts"
TMP_DIR = WORKSPACE_DIR / "tmp"
LOGOS_DIR = WORKSPACE_DIR / "logos"
MUSIC_DIR = WORKSPACE_DIR / "music"
# Kept clips live here; workspace cleanup never touches this folder.
LIBRARY_DIR = WORKSPACE_DIR / "library"
FONTS_DIR = BASE_DIR / "app" / "assets" / "fonts"
DB_PATH = WORKSPACE_DIR / "projects.sqlite3"


def validate_bind_host(host):
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host.lower() == "localhost"
    if not loopback and not os.getenv("CHURCH_PASSWORD", "").strip():
        message = "Phải đặt CHURCH_PASSWORD trước khi mở máy chủ ra mạng."
        logging.getLogger(__name__).error(message)
        raise RuntimeError(message)


def server_bind_host():
    for i, arg in enumerate(sys.argv):
        if arg == "--host" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if arg.startswith("--host="):
            return arg.split("=", 1)[1]
    return os.getenv("CHURCH_HOST", os.getenv("UVICORN_HOST", "127.0.0.1"))

for directory in [WORKSPACE_DIR, UPLOADS_DIR, AUDIO_DIR, SUBTITLES_DIR, SEGMENTS_DIR, PACKAGES_DIR, SHORTS_DIR, TMP_DIR, LOGOS_DIR, MUSIC_DIR, LIBRARY_DIR, LIBRARY_DIR / "thumbs"]:
    directory.mkdir(parents=True, exist_ok=True)

# FFmpeg discovery
def find_binary(name: str) -> str:
    # 1. Environment variable override
    env_var = f"{name.upper()}_PATH"
    if os.getenv(env_var) and Path(os.getenv(env_var)).exists():
        return os.getenv(env_var)

    # Finder shells may lack Homebrew in PATH. The full build includes libass.
    if sys.platform == 'darwin':
        for directory in ('opt/ffmpeg-full/bin', 'bin'):
            for prefix in ('/opt/homebrew', '/usr/local'):
                candidate = Path(prefix) / directory / name
                if candidate.is_file():
                    return str(candidate)

    # 2. Check system PATH
    found = shutil.which(name)
    if found:
        return found

    # 3. Check Windows WinGet standard installation
    local_app_data = os.getenv("LOCALAPPDATA", "")
    if local_app_data:
        winget_pattern = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pattern.exists():
            for p in winget_pattern.glob(f"**/{name}.exe"):
                if p.is_file():
                    return str(p)

    # 4. Check project local bin
    local_bin = BASE_DIR / "bin" / (f"{name}.exe" if sys.platform == 'win32' else name)
    if local_bin.exists():
        return str(local_bin)

    return name  # fallback to name in PATH

FFMPEG_BIN = find_binary("ffmpeg")
FFPROBE_BIN = find_binary("ffprobe")

# Whisper settings
DEFAULT_WHISPER_MODEL = os.getenv("DEFAULT_WHISPER_MODEL", "base")


def bounded_setting(name, default, minimum=1, maximum=32):
    value = int(os.getenv(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f'{name} phải nằm trong khoảng {minimum}–{maximum}.')
    return value


WHISPER_CPU_THREADS = bounded_setting('WHISPER_CPU_THREADS', 4)
WHISPER_BATCH_SIZE = bounded_setting('WHISPER_BATCH_SIZE', 8, maximum=16)
FFMPEG_THREADS = bounded_setting('FFMPEG_THREADS', 0, minimum=0)
FFMPEG_FILTER_THREADS = bounded_setting('FFMPEG_FILTER_THREADS', 0, minimum=0)
FFMPEG_HWACCEL = os.getenv('FFMPEG_HWACCEL', 'auto')
if FFMPEG_HWACCEL not in ('auto','cuda','none'):
    raise ValueError('FFMPEG_HWACCEL phải là auto, cuda hoặc none.')
TRIM_WORKERS = bounded_setting('TRIM_WORKERS', 2, maximum=4)
SUPPORTED_MODELS = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]
ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "4096"))  # 4GB
