import array
import io
import math
import subprocess
import zipfile
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from app.config import FFMPEG_BIN
from app.models.schemas import ShortClip, ClipPart, ShortsRenderOptions
from app.services import music_service, shorts_render_service as renderer
from test_shorts_render import sample_video


@pytest.fixture
def music_file(tmp_path, monkeypatch):
    monkeypatch.setattr(music_service, 'MUSIC_DIR', tmp_path/'music')
    path=tmp_path/'tone.wav'
    subprocess.run([FFMPEG_BIN,'-v','error','-y','-f','lavfi','-i','sine=f=880:d=4',str(path)],check=True)
    return path


def upload(path):
    return music_service.save_music(UploadFile(io.BytesIO(path.read_bytes()),filename=path.name))


def test_music_api_validates_and_keeps_original_file(music_file, monkeypatch):
    from app import main
    monkeypatch.delenv('CHURCH_PASSWORD',raising=False)
    client=TestClient(main.app)
    response=client.post('/api/shorts/music',files={'file':('Nhạc nền.wav',music_file.read_bytes(),'audio/wav')})
    assert response.status_code==200
    data=response.json()
    assert client.get(data['url']).content==music_file.read_bytes()
    assert client.post('/api/shorts/music',files={'file':('fake.mp3',b'not audio')}).status_code==400
    assert len(list(music_service.MUSIC_DIR.iterdir()))==1
    with pytest.raises(ValueError): music_service.music_path('../source')
    assert client.get('/api/shorts/music/'+'f'*32).status_code==404


@pytest.mark.integration
def test_music_mixes_after_join_with_delay_and_fades(sample_video,music_file):
    data=upload(music_file)
    clip=ShortClip(id=1,parts=[ClipPart(start_sec=s,end_sec=s+.8) for s in (0,3,6)])
    options=ShortsRenderOptions(aspect='source',encoder='x264',burn_subtitles=False,loudnorm=False,
        music_id=data['music_id'],music_start=1,music_delay=.5,music_volume=.5,voice_volume=0,
        music_fade_in=.2,music_fade_out=.5)
    output=renderer.render_short(sample_video,clip,options)
    result=subprocess.run([FFMPEG_BIN,'-v','error','-i',str(output),'-vn','-ac','1','-ar','8000','-f','f32le','pipe:1'],capture_output=True,check=True)
    samples=array.array('f');samples.frombytes(result.stdout)
    def rms(a,b):
        values=samples[round(a*8000):round(b*8000)]
        return math.sqrt(sum(v*v for v in values)/len(values))
    assert len(samples)/8000==pytest.approx(2.4,abs=.08)
    assert rms(.1,.3)<.0001 # Muted source and music has not started.
    assert rms(1,1.4)>.02 # Music continues across joined source parts.
    assert rms(2.25,2.35)<rms(1,1.4)*.4 # Fade ends with the output clip.
    with pytest.raises(ValueError,match='Mốc bắt đầu nhạc'):
        renderer.render_short(sample_video,clip,options.model_copy(update={'music_start':5}))


@pytest.mark.integration
def test_backup_restores_music_with_new_id(sample_video,music_file,tmp_path,monkeypatch):
    from app.services import backup_service as backup,transcript_service
    from app.services.project_service import ProjectStore
    for module in (backup,transcript_service):
        monkeypatch.setattr(module,'UPLOADS_DIR',tmp_path)
        monkeypatch.setattr(module,'SUBTITLES_DIR',tmp_path/'subtitles')
    monkeypatch.setattr(backup,'BACKUPS_DIR',tmp_path/'backups')
    (tmp_path/'subtitles').mkdir()
    data=upload(music_file)
    store=ProjectStore(tmp_path/'projects.db')
    store.save('input',video={'original_name':'Bài giảng.mp4'},clips=[{'id':1,'parts':[{'start_sec':0,'end_sec':1}]}],
        options={'music_id':data['music_id'],'music_name':'Nhạc nền','music_volume':.2})
    package=backup.create_backup(store,'input')
    path=backup.BACKUPS_DIR/package['filename']
    with zipfile.ZipFile(path) as archive: assert archive.read('music.audio')==music_file.read_bytes()
    restored=backup.restore_backup(store,path)
    options=restored['options']
    assert options['music_id']!=data['music_id'] and options['music_volume']==.2
    assert music_service.music_path(options['music_id']).read_bytes()==music_file.read_bytes()


@pytest.mark.integration
def test_sha256_dedup_assets_and_outro_backup(sample_video, music_file, tmp_path, monkeypatch):
    from app import main
    from app.services import backup_service as backup, transcript_service
    from app.services.project_service import ProjectStore

    monkeypatch.delenv('CHURCH_PASSWORD', raising=False)
    monkeypatch.setattr(music_service, 'OUTROS_DIR', tmp_path / 'outros')
    monkeypatch.setattr(music_service, 'DB_PATH', tmp_path / 'projects.db')
    for module in (backup, transcript_service):
        monkeypatch.setattr(module, 'UPLOADS_DIR', tmp_path)
        monkeypatch.setattr(module, 'SUBTITLES_DIR', tmp_path / 'subtitles')
    monkeypatch.setattr(backup, 'BACKUPS_DIR', tmp_path / 'backups')
    (tmp_path / 'subtitles').mkdir(exist_ok=True)

    # 1. SHA-256 deduplication for Music & Outro uploads
    m1 = upload(music_file)
    m2 = upload(music_file)
    assert m1['music_id'] == m2['music_id']
    assert len(list(music_service.MUSIC_DIR.iterdir())) == 1

    o1 = music_service.save_outro(UploadFile(io.BytesIO(sample_video.read_bytes()), filename='Outro.mp4'))
    o2 = music_service.save_outro(UploadFile(io.BytesIO(sample_video.read_bytes()), filename='Outro.mp4'))
    assert o1['outro_id'] == o2['outro_id']
    assert len(list(music_service.OUTROS_DIR.iterdir())) == 1

    # 2. /api/shorts/assets lists uploaded music and outros
    client = TestClient(main.app)
    assets = client.get('/api/shorts/assets').json()
    assert any(m['music_id'] == m1['music_id'] for m in assets['music'])
    assert any(o['outro_id'] == o1['outro_id'] for o in assets['outros'])

    # 3. Backup & Restore preserves outro video
    store = ProjectStore(tmp_path / 'projects.db')
    store.save('input', video={'original_name': 'Bài giảng.mp4'}, clips=[{'id': 1, 'parts': [{'start_sec': 0, 'end_sec': 1}]}],
               options={'outro_id': o1['outro_id'], 'outro_name': 'Outro.mp4'})
    package = backup.create_backup(store, 'input')
    path = backup.BACKUPS_DIR / package['filename']
    with zipfile.ZipFile(path) as archive:
        assert archive.read('outro.mp4') == sample_video.read_bytes()
    restored = backup.restore_backup(store, path)
    assert restored['options']['outro_id'] and restored['options']['outro_id'] != o1['outro_id']
    assert music_service.outro_path(restored['options']['outro_id']).read_bytes() == sample_video.read_bytes()

