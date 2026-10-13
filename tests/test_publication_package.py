import json
import subprocess
import zipfile
import pytest
from app.config import FFMPEG_BIN
from app.services.library_service import Library
from app.services import publication_service


@pytest.mark.integration
def test_publication_package_contains_real_video_subtitle_cover_and_metadata(tmp_path,monkeypatch):
    monkeypatch.setattr(publication_service,'PACKAGES_DIR',tmp_path)
    video=tmp_path/'source.mp4'
    subprocess.run([FFMPEG_BIN,'-v','error','-y','-f','lavfi','-i','color=s=160x160:d=1','-c:v','libx264',str(video)],capture_output=True,check=True)
    subtitle=tmp_path/'source.srt';subtitle.write_text('1\n00:00:00,000 --> 00:00:01,000\nChúa yêu thương\n',encoding='utf-8')
    library=Library(tmp_path/'data.db',tmp_path/'library')
    item=library.add(video,kind='short',video_id='sample',title='Đức tin',aspect='1:1',subtitle=subtitle)
    library.update(item['id'],publication_status='published',publication_url='https://example.com/post')
    assert library.search(publication_status='published')[1]==1
    assert library.search(publication_status='exported')[1]==0
    result=publication_service.build_publication_package(library,item['id'],'square')
    with zipfile.ZipFile(tmp_path/result['zip_url'].split('/')[-1]) as archive:
        assert {'subtitles.srt','cover.jpg','metadata.json','description.txt'}<=set(archive.namelist())
        assert archive.read('cover.jpg').startswith(b'\xff\xd8')
        assert json.loads(archive.read('metadata.json'))['publication_status']=='published'
        assert archive.read('description.txt').decode('utf-8')=='Đức tin'
    with pytest.raises(ValueError,match='9:16'): publication_service.build_publication_package(library,item['id'],'youtube_shorts')
