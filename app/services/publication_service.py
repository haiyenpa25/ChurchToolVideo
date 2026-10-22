import json
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from threading import BoundedSemaphore
from pathlib import Path
from app.config import FFMPEG_BIN, PACKAGES_DIR
from app.services.formats import PLATFORMS
from app.services.library_service import download_name

_package_slot = BoundedSemaphore(1)


class PublicationBusy(Exception):
    pass


def build_publication_package(library,item_id,platform):
    if not _package_slot.acquire(blocking=False):
        raise PublicationBusy('Đang tạo gói phát hành khác. Hãy đợi hoàn tất rồi thử lại.')
    try:
        return _build_publication_package(library,item_id,platform)
    finally:
        _package_slot.release()


def _build_publication_package(library,item_id,platform):
    item=library.get(item_id)
    target=next((p for p in PLATFORMS if p['id']==platform),None)
    if not target: raise ValueError('Nền tảng không hợp lệ.')
    if item['aspect']!=target['aspect']:
        raise ValueError(f"Nền tảng cần tỉ lệ {target['aspect']}; hãy render tỉ lệ này trước.")
    has_video = library.has_accessible_video(item) if hasattr(library, "has_accessible_video") else library.file_path(item).is_file()
    if not has_video:
        raise FileNotFoundError('Thiếu video đã xuất.')
    subtitle=library.subtitle_path(item)
    if item.get('srt_filename') and (not subtitle or not subtitle.is_file()): raise FileNotFoundError('Thiếu SRT đã lưu.')
    PACKAGES_DIR.mkdir(parents=True,exist_ok=True)
    local_video = library.file_path(item)
    est_video_bytes = local_video.stat().st_size if local_video.is_file() else int(item.get('file_size') or 0)
    required=est_video_bytes+(subtitle.stat().st_size if subtitle and subtitle.is_file() else 0)+32*1024**2
    if shutil.disk_usage(PACKAGES_DIR).free<required:
        raise ValueError('Không đủ dung lượng tạo gói phát hành. Hãy dọn tệp tạm rồi thử lại.')
    description='\n\n'.join(part for part in (item['title'],item.get('hook'), ' '.join('#'+tag.replace(' ','') for tag in item.get('tags',[]))) if part)
    warnings=[]
    if target['max_sec'] and item['duration_sec']>target['max_sec']:
        warnings.append('Thời lượng vượt mức khuyến nghị đã cấu hình; kiểm tra điều kiện hiện tại của nền tảng trước khi đăng.')
    metadata={'platform':target['label'],'title':item['title'],'description':description,'aspect':item['aspect'],
        'duration_seconds':item['duration_sec'],'publication_status':item.get('publication_status','exported'),'warnings':warnings}
    output=PACKAGES_DIR/f'publication_{uuid.uuid4().hex}.zip'
    pending=output.with_suffix('.partial')
    try:
        with tempfile.TemporaryDirectory(dir=PACKAGES_DIR) as staging:
            video = library.resolve_video_path(item, staging) if hasattr(library, "resolve_video_path") else local_video
            if not video.is_file():
                raise FileNotFoundError('Thiếu video đã xuất.')
            cover=Path(staging)/'cover.jpg'
            try:
                subprocess.run([FFMPEG_BIN,'-v','error','-y','-ss',str(min(1,item['duration_sec']/2)),'-i',str(video),'-frames:v','1','-q:v','2',str(cover)],capture_output=True,check=True,timeout=60)
            except subprocess.SubprocessError:
                raise ValueError('Không tạo được ảnh bìa từ video; video có thể bị hỏng.') from None
            with zipfile.ZipFile(pending,'w',zipfile.ZIP_STORED) as archive:
                archive.write(video,download_name(item))
                if subtitle and subtitle.is_file(): archive.write(subtitle,'subtitles.srt')
                archive.write(cover,'cover.jpg')
                archive.writestr('description.txt',description)
                archive.writestr('metadata.json',json.dumps(metadata,ensure_ascii=False,indent=2))
                archive.writestr('README.txt','Kiểm tra video, phụ đề, mô tả và ảnh bìa trước khi đăng. Gói này không tự đăng lên nền tảng.\n'+'\n'.join(warnings))
        pending.replace(output)
    finally: pending.unlink(missing_ok=True)
    return {'zip_url':f'/api/download/zip/{output.name}','warnings':warnings}
