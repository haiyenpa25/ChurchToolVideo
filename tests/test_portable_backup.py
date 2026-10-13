import json
import zipfile
import pytest
from app.services import backup_service as backup,transcript_service,ffmpeg_service
from app.services.project_service import ProjectStore


@pytest.fixture
def backup_project(tmp_path,monkeypatch):
    for name in ('uploads','subtitles','logos','backups'): (tmp_path/name).mkdir()
    for module in (backup,transcript_service):
        for name in ('uploads','subtitles'):
            monkeypatch.setattr(module,name.upper()+'_DIR',tmp_path/name)
    monkeypatch.setattr(backup,'LOGOS_DIR',tmp_path/'logos')
    monkeypatch.setattr(backup,'BACKUPS_DIR',tmp_path/'backups')
    monkeypatch.setattr(ffmpeg_service,'get_media_info',lambda _:{'width':320,'height':180,'duration':4})
    store=ProjectStore(tmp_path/'projects.db')
    (tmp_path/'uploads/sample.mp4').write_bytes(b'original video')
    store.save('sample',video={'original_name':'Bài giảng.mp4'},clips=[{'id':1,'title':'A','parts':[{'start_sec':0,'end_sec':2}]}])
    store.review_clip('sample',1,True)
    transcript_service.save_transcript('sample',4,[{'start_sec':0,'end_sec':2,'text':'Chúa yêu thương'}])
    return store,tmp_path


def test_portable_backup_roundtrip_adds_project_and_preserves_source(backup_project):
    store,root=backup_project
    result=backup.create_backup(store,'sample')
    restored=backup.restore_backup(store,backup.BACKUPS_DIR/result['filename'])
    video_id=restored['video_id']
    assert video_id!='sample'
    assert (root/f'uploads/{video_id}.mp4').read_bytes()==b'original video'
    assert (root/'uploads/sample.mp4').read_bytes()==b'original video'
    assert store.get('sample')['clips'][0]['review']['approved']
    assert not restored['clips'][0]['review']['approved']
    assert transcript_service.load_transcript(video_id)['video_id']==video_id
    assert len(backup.list_backups())==1


@pytest.mark.parametrize('name',['../outside.txt','C:/outside.txt','source.exe'])
def test_restore_rejects_unsafe_members_before_writing(backup_project,name):
    store,root=backup_project
    path=root/'bad.zip'
    with zipfile.ZipFile(path,'w') as archive: archive.writestr(name,'bad')
    with pytest.raises(ValueError): backup.restore_backup(store,path)
    assert len(store.list())==1 and len(list((root/'uploads').iterdir()))==1


def test_restore_rejects_tampered_checksum(backup_project):
    store,root=backup_project
    result=backup.create_backup(store,'sample')
    with zipfile.ZipFile(backup.BACKUPS_DIR/result['filename']) as original:
        members={name:original.read(name) for name in original.namelist()}
    members['source.mp4']=b'tampered'
    path=root/'bad.zip'
    with zipfile.ZipFile(path,'w') as archive:
        for name,data in members.items(): archive.writestr(name,data)
    with pytest.raises(ValueError,match='checksum'): backup.restore_backup(store,path)
    assert len(store.list())==1
