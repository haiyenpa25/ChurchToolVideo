"""Persistent background audio, stored separately from temporary extracted audio."""
import re
import uuid
from app.config import MUSIC_DIR
from app.services.ffmpeg_service import get_media_info


def music_path(music_id):
    if not re.fullmatch(r'[a-f0-9]{32}', music_id or ''):
        raise ValueError('Mã âm thanh không hợp lệ.')
    path = MUSIC_DIR / f'{music_id}.audio'
    if not path.is_file():
        raise FileNotFoundError('Không tìm thấy nhạc nền đã tải lên.')
    return path


def save_music(file):
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    music_id = uuid.uuid4().hex
    path = MUSIC_DIR / f'{music_id}.audio'
    size = 0
    try:
        with path.open('wb') as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > 50 * 1024 * 1024:
                    raise ValueError('Âm thanh tối đa 50 MB.')
                output.write(chunk)
        meta = get_media_info(path)
        if not meta.get('has_audio') or meta.get('duration', 0) <= 0:
            raise ValueError('Tệp không có âm thanh hợp lệ.')
        if meta['duration'] > 7200:
            raise ValueError('Âm thanh tối đa 2 giờ.')
        return {'music_id': music_id, 'name': (file.filename or 'Nhạc nền')[:200],
                'duration': meta['duration'], 'url': f'/api/shorts/music/{music_id}'}
    except Exception:
        path.unlink(missing_ok=True)
        raise
