import json
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from app.config import FFMPEG_BIN, PACKAGES_DIR
from app.services.formats import PLATFORMS
from app.services.library_service import download_name


def build_publication_package(library,item_id,platform):
    item=library.get(item_id)
    target=next((p for p in PLATFORMS if p['id']==platform),None)
    if not target: raise ValueError('Nền tảng không hợp lệ.')
    if item['aspect']!=target['aspect']:
        raise ValueError(f"Nền tảng cần tỉ lệ {target['aspect']}; hãy render tỉ lệ này trước.")
    video=library.file_path(item)
    if not video.is_file(): raise FileNotFoundError('Thiếu video đã xuất.')
    subtitle=library.subtitle_path(item)
    if item.get('srt_filename') and (not subtitle or not subtitle.is_file()): raise FileNotFoundError('Thiếu SRT đã lưu.')
    description='\n\n'.join(part for part in (item['title'],item.get('hook'), ' '.join('#'+tag.replace(' ','') for tag in item.get('tags',[]))) if part)
    warnings=[]
    if target['max_sec'] and item['duration_sec']>target['max_sec']:
        warnings.append('Thời lượng vượt mức khuyến nghị đã cấu hình; kiểm tra điều kiện hiện tại của nền tảng trước khi đăng.')
    metadata={'platform':target['label'],'title':item['title'],'description':description,'aspect':item['aspect'],
        'duration_seconds':item['duration_sec'],'publication_status':item.get('publication_status','exported'),'warnings':warnings}
    output=PACKAGES_DIR/f'publication_{uuid.uuid4().hex}.zip'
    pending=output.with_suffix('.partial')
    try:
        with tempfile.TemporaryDirectory() as staging:
            cover=Path(staging)/'cover.jpg'
            subprocess.run([FFMPEG_BIN,'-v','error','-y','-ss',str(min(1,item['duration_sec']/2)),'-i',str(video),'-frames:v','1','-q:v','2',str(cover)],capture_output=True,check=True,timeout=60)
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
