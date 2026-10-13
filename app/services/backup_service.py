"""Portable, additive project backups. Restore always creates a fresh project ID."""
import hashlib
import json
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from app.config import WORKSPACE_DIR, UPLOADS_DIR, SUBTITLES_DIR, LOGOS_DIR, ALLOWED_EXTENSIONS
from app.services.transcript_service import find_video
from app.models.schemas import ProjectSaveRequest

BACKUPS_DIR=WORKSPACE_DIR/'backups'
MAX_UNPACKED=20*1024**3


def checksum(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''): value.update(chunk)
    return value.hexdigest()


def create_backup(store,video_id):
    project=store.get(video_id)
    source=find_video(video_id)
    BACKUPS_DIR.mkdir(parents=True,exist_ok=True)
    files={'source'+source.suffix.lower():source}
    for suffix in ('.json','.srt','.vtt'):
        path=SUBTITLES_DIR/f'{video_id}{suffix}'
        if path.exists(): files['transcript'+suffix]=path
    logo=project.get('options',{}).get('logo_id')
    if logo:
        path=LOGOS_DIR/f'{logo}.png'
        if not path.exists(): raise ValueError('Thiếu logo của dự án; chưa tạo được bản sao đầy đủ.')
        files['logo.png']=path
    size=sum(path.stat().st_size for path in files.values())
    if size>MAX_UNPACKED or shutil.disk_usage(BACKUPS_DIR).free<size+256*1024**2:
        raise ValueError('Không đủ dung lượng tạo sao lưu hoặc dự án vượt 20 GB.')
    backup_id=uuid.uuid4().hex
    output=BACKUPS_DIR/f'project_{backup_id}.zip'
    pending=output.with_suffix('.partial')
    manifest={'format':'ChurchToolVideo','version':1,'project':project,
        'files':{name:{'size':path.stat().st_size,'sha256':checksum(path)} for name,path in files.items()}}
    manifest_json=json.dumps(manifest,ensure_ascii=False)
    if len(manifest_json.encode('utf-8'))>5*1024**2:
        raise ValueError('Nội dung biên tập vượt giới hạn 5 MB của manifest sao lưu.')
    try:
        with zipfile.ZipFile(pending,'w',zipfile.ZIP_STORED) as archive:
            archive.writestr('manifest.json',manifest_json)
            for name,path in files.items(): archive.write(path,name)
        pending.replace(output)
    finally: pending.unlink(missing_ok=True)
    return {'id':backup_id,'filename':output.name,'bytes':output.stat().st_size,'download_url':f'/api/backups/{backup_id}/download'}


def restore_backup(store,archive_path):
    BACKUPS_DIR.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        entries=archive.infolist(); names=[entry.filename for entry in entries]
        allowed=r'^(manifest\.json|source\.(mp4|mkv|mov|avi|webm|m4v)|transcript\.(json|srt|vtt)|logo\.png)$'
        if len(names)!=len(set(names)) or len(names)>7 or any(not re.fullmatch(allowed,name) for name in names):
            raise ValueError('Cấu trúc bản sao lưu không hợp lệ.')
        if sum(entry.file_size for entry in entries)>MAX_UNPACKED:
            raise ValueError('Bản sao lưu giải nén vượt 20 GB.')
        if 'manifest.json' not in names or archive.getinfo('manifest.json').file_size>5*1024**2:
            raise ValueError('Thiếu manifest hoặc manifest quá lớn.')
        manifest=json.loads(archive.read('manifest.json'))
        if manifest.get('format')!='ChurchToolVideo' or manifest.get('version')!=1:
            raise ValueError('Phiên bản sao lưu không được hỗ trợ.')
        assets=manifest.get('files',{})
        if set(assets)!=set(names)-{'manifest.json'}:
            raise ValueError('Danh sách tài sản không khớp manifest.')
        sources=[name for name in assets if name.startswith('source.')]
        if len(sources)!=1: raise ValueError('Bản sao lưu phải có một video gốc.')
        project=manifest.get('project',{})
        editor=ProjectSaveRequest.model_validate(project)
        if shutil.disk_usage(UPLOADS_DIR).free<sum(e.file_size for e in entries)+256*1024**2:
            raise ValueError('Không đủ dung lượng khôi phục.')
        with tempfile.TemporaryDirectory(dir=BACKUPS_DIR) as staging:
            root=Path(staging)
            for name,info in assets.items():
                target=root/name
                with archive.open(name) as original,target.open('wb') as output: shutil.copyfileobj(original,output,1024*1024)
                if target.stat().st_size!=info.get('size') or checksum(target)!=info.get('sha256'):
                    raise ValueError('Tài sản bị hỏng hoặc checksum không khớp.')
            from app.services.ffmpeg_service import get_media_info
            if 'logo.png' in assets:
                logo=root/'logo.png'
                if logo.stat().st_size>2*1024**2 or not logo.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('Logo sao lưu không phải PNG hợp lệ.')
                dimensions=get_media_info(logo)
                if not dimensions.get('width') or max(dimensions['width'],dimensions['height'])>4096:
                    raise ValueError('Kích thước logo không hợp lệ.')
            meta=get_media_info(root/sources[0])
            if not meta.get('width') or meta.get('duration',0)<=0: raise ValueError('Video sao lưu không hợp lệ.')
            video_id=uuid.uuid4().hex[:12]
            created=[]
            try:
                for name in assets:
                    if name.startswith('source.'):
                        destination=UPLOADS_DIR/(video_id+Path(name).suffix)
                    elif name.startswith('transcript.'):
                        destination=SUBTITLES_DIR/(video_id+Path(name).suffix)
                        if name.endswith('.json'):
                            data=json.loads((root/name).read_text(encoding='utf-8')); data['video_id']=video_id
                            (root/name).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
                    else:
                        logo_id=uuid.uuid4().hex; destination=LOGOS_DIR/f'{logo_id}.png'; editor.options.logo_id=logo_id
                    shutil.copyfile(root/name,destination); created.append(destination)
                if 'logo.png' not in assets: editor.options.logo_id=None
                for clip in editor.clips: clip.review.approved=False
                payload=editor.model_dump(exclude={'expected_revision','brand_id'})
                video=dict(project.get('video',{})); video.update(video_id=video_id,filename=video_id+Path(sources[0]).suffix,
                    file_path=str(UPLOADS_DIR/(video_id+Path(sources[0]).suffix)),duration_seconds=meta['duration'])
                return store.save(video_id,video=video,**payload)
            except Exception:
                for path in created: path.unlink(missing_ok=True)
                raise


def list_backups():
    BACKUPS_DIR.mkdir(parents=True,exist_ok=True)
    return [{'id':p.stem.removeprefix('project_'),'filename':p.name,'bytes':p.stat().st_size,'created_at':p.stat().st_mtime,
        'download_url':f"/api/backups/{p.stem.removeprefix('project_')}/download"} for p in sorted(BACKUPS_DIR.glob('project_*.zip'),key=lambda p:p.stat().st_mtime,reverse=True)
        if re.fullmatch(r'project_[a-f0-9]{32}\.zip',p.name)]
