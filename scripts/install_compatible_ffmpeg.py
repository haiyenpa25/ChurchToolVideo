"""Install the verified Windows FFmpeg build locally; leave system binaries untouched."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import httpx

VERSION='8.0.1'
DIGEST='e2aaeaa0fdbc397d4794828086424d4aaa2102cef1fb6874f6ffd29c0b88b673'
URL=f'https://github.com/GyanD/codexffmpeg/releases/download/{VERSION}/ffmpeg-{VERSION}-essentials_build.zip'
ROOT=Path(__file__).resolve().parents[1]


def main():
    if sys.platform!='win32':
        raise SystemExit('This binary package is for Windows; Mac uses Homebrew FFmpeg.')
    target=ROOT/'.tools'/f'ffmpeg-{VERSION}'
    target.mkdir(parents=True,exist_ok=True)
    archive_path=target/'download.zip'
    digest=hashlib.sha256()
    print('Downloading compatible FFmpeg into the project...',flush=True)
    with httpx.stream('GET',URL,follow_redirects=True,timeout=60) as response:
        response.raise_for_status()
        with archive_path.open('wb') as output:
            for chunk in response.iter_bytes(1024*1024):
                output.write(chunk);digest.update(chunk)
    if digest.hexdigest()!=DIGEST:
        archive_path.unlink(missing_ok=True)
        raise SystemExit('Checksum mismatch; package was not installed.')
    with zipfile.ZipFile(archive_path) as archive:
        for basename in ('ffmpeg.exe','ffprobe.exe','LICENSE'):
            member=next(name for name in archive.namelist() if Path(name).name==basename)
            output=target/('bin/'+basename if basename.endswith('.exe') else basename)
            output.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(member) as source,output.open('wb') as destination:
                import shutil
                shutil.copyfileobj(source,destination)
    (target/'source.json').write_text(json.dumps({'url':URL,'sha256':DIGEST,'version':VERSION},indent=2),encoding='utf-8')
    archive_path.unlink()
    print(f'Installed: {target}',flush=True)


if __name__=='__main__':
    main()
