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
from app.services.transcript_service import find_video, validate_transcript
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
    music=project.get('options',{}).get('music_id')
    if music:
        from app.services.music_service import music_path
        files['music.audio']=music_path(music)
    outro=project.get('options',{}).get('outro_id')
    if outro:
        from app.services.music_service import outro_path
        outro_file=outro_path(outro)
        files['outro'+outro_file.suffix.lower()]=outro_file
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
        if any(entry.flag_bits & 1 for entry in entries):
            raise ValueError('Không hỗ trợ bản sao lưu ZIP có mật khẩu.')
        allowed=r'^(manifest\.json|source\.(mp4|mkv|mov|avi|webm|m4v)|transcript\.(json|srt|vtt)|logo\.png|music\.audio|outro\.(mp4|mkv|mov|avi|webm|m4v))$'
        if len(names)!=len(set(names)) or len(names)>9 or any(not re.fullmatch(allowed,name) for name in names):
            raise ValueError('Cấu trúc bản sao lưu không hợp lệ.')
        if sum(entry.file_size for entry in entries)>MAX_UNPACKED:
            raise ValueError('Bản sao lưu giải nén vượt 20 GB.')
        if 'manifest.json' not in names or archive.getinfo('manifest.json').file_size>5*1024**2:
            raise ValueError('Thiếu manifest hoặc manifest quá lớn.')
        if any(entry.filename.startswith('transcript.') and entry.file_size>50*1024**2 for entry in entries):
            raise ValueError('Tệp transcript trong bản sao lưu quá lớn.')
        manifest=json.loads(archive.read('manifest.json'))
        if not isinstance(manifest,dict):
            raise ValueError('Manifest phải là một đối tượng JSON.')
        if manifest.get('format')!='ChurchToolVideo' or manifest.get('version')!=1:
            raise ValueError('Phiên bản sao lưu không được hỗ trợ.')
        assets=manifest.get('files',{})
        if not isinstance(assets,dict):
            raise ValueError('Danh sách tài sản không hợp lệ.')
        if set(assets)!=set(names)-{'manifest.json'}:
            raise ValueError('Danh sách tài sản không khớp manifest.')
        sources=[name for name in assets if name.startswith('source.')]
        if len(sources)!=1: raise ValueError('Bản sao lưu phải có một video gốc.')
        project=manifest.get('project',{})
        if not isinstance(project,dict) or not isinstance(project.get('video',{}),dict):
            raise ValueError('Thông tin dự án không hợp lệ.')
        editor=ProjectSaveRequest.model_validate(project)
        for name,info in assets.items():
            if (not isinstance(info,dict) or type(info.get('size')) is not int or
                    info['size'] != archive.getinfo(name).file_size or
                    not isinstance(info.get('sha256'),str) or not re.fullmatch(r'[a-f0-9]{64}',info['sha256'])):
                raise ValueError('Thông tin kích thước hoặc checksum tài sản không hợp lệ.')
        # Assets are staged under BACKUPS_DIR, then copied into the workspace: room for both copies.
        if shutil.disk_usage(UPLOADS_DIR).free<2*sum(e.file_size for e in entries)+256*1024**2:
            raise ValueError('Không đủ dung lượng khôi phục.')
        with tempfile.TemporaryDirectory(dir=BACKUPS_DIR) as staging:
            root=Path(staging)
            for name,info in assets.items():
                target=root/name
                with archive.open(name) as original,target.open('wb') as output: shutil.copyfileobj(original,output,1024*1024)
                if target.stat().st_size!=info.get('size') or checksum(target)!=info.get('sha256'):
                    raise ValueError('Tài sản bị hỏng hoặc checksum không khớp.')
            from app.services.ffmpeg_service import get_media_info
            if 'music.audio' in assets:
                music=get_media_info(root/'music.audio')
                if (root/'music.audio').stat().st_size>50*1024**2 or not music.get('has_audio') or not 0<music.get('duration',0)<=7200:
                    raise ValueError('Nhạc nền sao lưu không hợp lệ.')
                if editor.options.music_start>=music['duration']:
                    raise ValueError('Mốc nhạc nền vượt thời lượng âm thanh.')
            if 'logo.png' in assets:
                logo=root/'logo.png'
                if logo.stat().st_size>2*1024**2 or not logo.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('Logo sao lưu không phải PNG hợp lệ.')
                dimensions=get_media_info(logo)
                if not dimensions.get('width') or max(dimensions['width'],dimensions['height'])>4096:
                    raise ValueError('Kích thước logo không hợp lệ.')
            outros=[name for name in assets if name.startswith('outro.')]
            if len(outros)>1: raise ValueError('Bản sao lưu chỉ được có tối đa một video outro.')
            if outros:
                outro_info=get_media_info(root/outros[0])
                if (root/outros[0]).stat().st_size>100*1024**2 or not outro_info.get('width') or not 0<outro_info.get('duration',0)<=60:
                    raise ValueError('Video outro sao lưu không hợp lệ.')
            meta=get_media_info(root/sources[0])
            if not meta.get('width') or meta.get('duration',0)<=0: raise ValueError('Video sao lưu không hợp lệ.')
            if any(p.end_sec > meta['duration'] + .1 for c in editor.clips for p in c.parts):
                raise ValueError('Mốc cắt của dự án vượt thời lượng video gốc.')
            transcript=None
            if 'transcript.json' in assets:
                transcript=validate_transcript(json.loads((root/'transcript.json').read_text(encoding='utf-8')),meta['duration'])
            video_id=uuid.uuid4().hex[:12]
            created=[]
            try:
                for name in assets:
                    if name.startswith('source.'):
                        destination=UPLOADS_DIR/(video_id+Path(name).suffix)
                    elif name.startswith('transcript.'):
                        destination=SUBTITLES_DIR/(video_id+Path(name).suffix)
                        if name.endswith('.json'):
                            transcript['video_id']=video_id
                            (root/name).write_text(json.dumps(transcript,ensure_ascii=False),encoding='utf-8')
                    elif name=='music.audio':
                        from app.services.music_service import MUSIC_DIR
                        MUSIC_DIR.mkdir(parents=True,exist_ok=True)
                        music_id=uuid.uuid4().hex; destination=MUSIC_DIR/f'{music_id}.audio'; editor.options.music_id=music_id
                    elif name.startswith('outro.'):
                        from app.services.music_service import OUTROS_DIR
                        OUTROS_DIR.mkdir(parents=True,exist_ok=True)
                        outro_id=uuid.uuid4().hex; destination=OUTROS_DIR/(outro_id+Path(name).suffix.lower()); editor.options.outro_id=outro_id
                    else:
                        logo_id=uuid.uuid4().hex; destination=LOGOS_DIR/f'{logo_id}.png'; editor.options.logo_id=logo_id
                    created.append(destination); shutil.copyfile(root/name,destination)
                if 'logo.png' not in assets: editor.options.logo_id=None
                if 'music.audio' not in assets: editor.options.music_id=None; editor.options.music_name=''
                if not outros: editor.options.outro_id=None; editor.options.outro_name=''
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
