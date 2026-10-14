"""Check Python packages and the FFmpeg capabilities used by the application."""
import importlib
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    print(f'{platform.system()} {platform.machine()} / Python {platform.python_version()}')
    for module in ('fastapi','uvicorn','dotenv','faster_whisper','av','cv2'):
        try:
            importlib.import_module(module)
        except (ImportError,OSError) as error:
            print(f'Missing/unusable dependency {module}: {error}')
            return 1
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env',override=False)
    from app.config import FFMPEG_BIN,FFPROBE_BIN
    for binary in (FFMPEG_BIN,FFPROBE_BIN):
        try:
            subprocess.run([binary,'-version'],capture_output=True,check=True,timeout=15)
        except (OSError,subprocess.SubprocessError):
            print(f'Missing/unusable binary: {binary}. See docs/INSTALL_LAPTOP.md.')
            return 1
    for option,required in (('-filters',('ass','loudnorm')),('-encoders',('libx264','aac'))):
        result=subprocess.run([FFMPEG_BIN,'-hide_banner',option],capture_output=True,text=True,
                              encoding='utf-8',errors='replace',check=True,timeout=15)
        entries={line.split()[1] for line in result.stdout.splitlines() if len(line.split())>=2}
        missing=set(required)-entries
        if missing:
            print(f'FFmpeg missing: {", ".join(sorted(missing))}. On Mac install ffmpeg-full; see docs/INSTALL_LAPTOP.md.')
            return 1
    print('Ready: dependencies, FFmpeg/FFprobe, subtitles, H.264 and AAC.')
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except subprocess.SubprocessError as error:
        print(f'FFmpeg check failed: {error}')
        raise SystemExit(1)
