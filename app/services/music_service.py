"""Persistent background audio and church outro videos, stored separately from temporary files."""
import hashlib
import json
import re
import uuid
from app.config import MUSIC_DIR, OUTROS_DIR, ALLOWED_EXTENSIONS, DB_PATH
from app.services.ffmpeg_service import get_media_info
from app.services.sqlite_service import connect


def _record_asset_meta(kind: str, asset_id: str, name: str, duration: float):
    try:
        with connect(DB_PATH) as db:
            db.execute("CREATE TABLE IF NOT EXISTS editor_settings(key TEXT PRIMARY KEY,data TEXT NOT NULL)")
            row = db.execute("SELECT data FROM editor_settings WHERE key='media_assets'").fetchone()
            assets = json.loads(row[0]) if row else {}
            assets[f"{kind}:{asset_id}"] = {"id": asset_id, "kind": kind, "name": name[:200], "duration": round(duration, 2)}
            db.execute("INSERT OR REPLACE INTO editor_settings VALUES ('media_assets',?)", (json.dumps(assets, ensure_ascii=False),))
    except Exception:
        pass


def _load_asset_meta() -> dict:
    try:
        with connect(DB_PATH) as db:
            db.execute("CREATE TABLE IF NOT EXISTS editor_settings(key TEXT PRIMARY KEY,data TEXT NOT NULL)")
            row = db.execute("SELECT data FROM editor_settings WHERE key='media_assets'").fetchone()
            return json.loads(row[0]) if row else {}
    except Exception:
        return {}


def music_path(music_id):
    if not re.fullmatch(r'[a-f0-9]{32}', music_id or ''):
        raise ValueError('Mã âm thanh không hợp lệ.')
    path = MUSIC_DIR / f'{music_id}.audio'
    if not path.is_file():
        raise FileNotFoundError('Không tìm thấy nhạc nền đã tải lên.')
    return path


def save_music(file):
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    staging = MUSIC_DIR / f'{uuid.uuid4().hex}.partial'
    hasher = hashlib.sha256()
    size = 0
    try:
        with staging.open('wb') as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > 50 * 1024 * 1024:
                    raise ValueError('Âm thanh tối đa 50 MB.')
                hasher.update(chunk)
                output.write(chunk)
        meta = get_media_info(staging)
        if not meta.get('has_audio') or meta.get('duration', 0) <= 0:
            raise ValueError('Tệp không có âm thanh hợp lệ.')
        if meta['duration'] > 7200:
            raise ValueError('Âm thanh tối đa 2 giờ.')
        music_id = hasher.hexdigest()[:32]
        path = MUSIC_DIR / f'{music_id}.audio'
        staging.replace(path)
        name = (file.filename or 'Nhạc nền')[:200]
        _record_asset_meta('music', music_id, name, meta['duration'])
        return {'music_id': music_id, 'name': name,
                'duration': meta['duration'], 'url': f'/api/shorts/music/{music_id}'}
    except Exception:
        staging.unlink(missing_ok=True)
        raise


def list_music():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    meta_map = _load_asset_meta()
    items = []
    for p in sorted(MUSIC_DIR.glob('*.audio'), key=lambda f: f.stat().st_mtime, reverse=True):
        if re.fullmatch(r'[a-f0-9]{32}\.audio', p.name):
            mid = p.stem
            info = meta_map.get(f"music:{mid}", {})
            items.append({
                'music_id': mid,
                'name': info.get('name') or f'Nhạc nền ({mid[:6]})',
                'duration': info.get('duration', 0),
                'url': f'/api/shorts/music/{mid}',
                'size': p.stat().st_size,
            })
    return items


def outro_path(outro_id):
    if not re.fullmatch(r'[a-f0-9]{32}', outro_id or ''):
        raise ValueError('Mã video outro không hợp lệ.')
    for ext in ('.mp4', '.mov', '.webm', '.mkv', '.m4v'):
        candidate = OUTROS_DIR / f'{outro_id}{ext}'
        if candidate.is_file():
            return candidate
    raise FileNotFoundError('Không tìm thấy video outro đã tải lên.')


def save_outro(file):
    OUTROS_DIR.mkdir(parents=True, exist_ok=True)
    raw_name = file.filename or 'Outro Hội Thánh.mp4'
    ext = '.' + raw_name.rsplit('.', 1)[-1].lower() if '.' in raw_name else '.mp4'
    if ext not in ALLOWED_EXTENSIONS:
        ext = '.mp4'
    staging = OUTROS_DIR / f'{uuid.uuid4().hex}.partial'
    hasher = hashlib.sha256()
    size = 0
    try:
        with staging.open('wb') as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > 100 * 1024 * 1024:
                    raise ValueError('Video outro tối đa 100 MB.')
                hasher.update(chunk)
                output.write(chunk)
        meta = get_media_info(staging)
        if not meta.get('width') or not meta.get('height') or meta.get('duration', 0) <= 0:
            raise ValueError('Tệp không phải là video outro hợp lệ.')
        if meta['duration'] > 60:
            raise ValueError('Video outro tối đa 60 giây.')
        outro_id = hasher.hexdigest()[:32]
        path = OUTROS_DIR / f'{outro_id}{ext}'
        staging.replace(path)
        name = raw_name[:200]
        _record_asset_meta('outro', outro_id, name, meta['duration'])
        return {
            'outro_id': outro_id,
            'name': name,
            'duration': round(meta['duration'], 2),
            'width': meta['width'],
            'height': meta['height'],
            'url': f'/api/shorts/outro/{outro_id}',
        }
    except Exception:
        staging.unlink(missing_ok=True)
        raise


def list_outros():
    OUTROS_DIR.mkdir(parents=True, exist_ok=True)
    meta_map = _load_asset_meta()
    items = []
    for p in sorted(OUTROS_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
        if p.is_file() and p.suffix.lower() in ('.mp4', '.mov', '.webm', '.mkv', '.m4v') and re.fullmatch(r'[a-f0-9]{32}', p.stem):
            oid = p.stem
            info = meta_map.get(f"outro:{oid}", {})
            items.append({
                'outro_id': oid,
                'name': info.get('name') or f'Outro ({oid[:6]}{p.suffix})',
                'duration': info.get('duration', 0),
                'url': f'/api/shorts/outro/{oid}',
                'size': p.stat().st_size,
            })
    return items
