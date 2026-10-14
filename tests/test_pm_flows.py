"""PM acceptance journey with a fixed STT fixture; media upload, render and ZIP operations are real."""
import io
import subprocess
import time
import zipfile
import pytest
from fastapi.testclient import TestClient


def await_task(client, task_id):
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        response=client.get(f'/api/tasks/{task_id}')
        assert response.status_code==200
        task=response.json()
        if task['status'] in ('COMPLETED','FAILED','CANCELLED'):
            assert task['status']=='COMPLETED',task
            return task['result']
        time.sleep(.05)
    pytest.fail('Task did not finish within 60 seconds')


@pytest.mark.integration
def test_sermon_normalize_review_multiformat_publish_backup_journey(tmp_path,monkeypatch):
    from app import main,config,library_api
    from app.services import transcript_service,whisper_service,shorts_render_service,project_service
    from app.services import task_manager,library_service,backup_service,publication_service
    names=('uploads','audio','subtitles','shorts','tmp','segments','packages','logos')
    dirs={name:tmp_path/name for name in names}
    for directory in dirs.values(): directory.mkdir()
    for module,fields in ((main,names),(config,names),(transcript_service,('uploads','subtitles')),
                          (whisper_service,('subtitles',)),(shorts_render_service,('shorts','tmp')),
                          (backup_service,('uploads','subtitles','logos')),(publication_service,('packages',))):
        for name in fields: monkeypatch.setattr(module,name.upper()+'_DIR',dirs[name])
    monkeypatch.setattr(backup_service,'BACKUPS_DIR',tmp_path/'backups')
    monkeypatch.delenv('CHURCH_PASSWORD',raising=False)
    store=project_service.ProjectStore(tmp_path/'data.db')
    manager=task_manager.TaskManager(tmp_path/'tasks.db')
    library=library_service.Library(tmp_path/'data.db',tmp_path/'library')
    for module in (main,project_service): monkeypatch.setattr(module,'project_store',store)
    for module in (main,task_manager): monkeypatch.setattr(module,'task_manager',manager)
    for module in (library_api,library_service): monkeypatch.setattr(module,'library',library)
    def stt_fixture(audio_path,video_id,**kwargs):
        assert audio_path.is_file() # Real extraction succeeded before our fixed recognition fixture.
        items=[{'start_sec':0,'end_sec':2,'text':'Lễ báp têm và Tiệc Thánh.',
                'words':[{'w':'báp','start':.3,'end':.7}]},
               {'start_sec':2,'end_sec':4,'text':'Môi se và y sơ ra ên.',
                'words':[{'w':'Môi','start':2.1,'end':2.4}]}]
        transcript_service.save_transcript(video_id,6,items)
        from app.services.ffmpeg_service import format_seconds_to_srt
        srt='\n'.join(f'{i}\n{format_seconds_to_srt(s["start_sec"])} --> {format_seconds_to_srt(s["end_sec"])}\n{s["text"]}\n'
                      for i,s in enumerate(items,1))
        (dirs['subtitles']/f'{video_id}.srt').write_text(srt,encoding='utf-8')
        return {'srt_content':srt,'subtitles':items,'total_segments':2}
    monkeypatch.setattr(main,'transcribe_audio',stt_fixture)
    video=tmp_path/'sermon.mp4'
    subprocess.run([config.FFMPEG_BIN,'-v','error','-y','-f','lavfi','-i','testsrc2=s=320x180:r=30:d=6',
                    '-f','lavfi','-i','sine=d=6','-c:v','libx264','-preset','ultrafast','-c:a','aac',str(video)],check=True)
    client=TestClient(main.app)
    uploaded=client.post('/api/upload',files={'file':('sermon.mp4',video.read_bytes(),'video/mp4')})
    assert uploaded.status_code==200
    vid=uploaded.json()['video_id']
    task=client.post('/api/transcribe',json={'video_id':vid,'model_size':'tiny'})
    assert task.status_code==200
    await_task(client,task.json()['task_id'])
    before=transcript_service.load_transcript(vid)
    normalized=client.post(f'/api/subtitles/{vid}/normalize')
    assert normalized.status_code==200
    after=transcript_service.load_transcript(vid)
    assert after['sentences'][0]['text']=='Lễ Báp-têm và Tiệc Thánh.'
    assert after['sentences'][1]['text']=='Môi-se và Y-sơ-ra-ên.'
    assert [s['words'] for s in before['sentences']]==[s['words'] for s in after['sentences']]
    clip=client.post('/api/transcript-selection',json={'video_id':vid,'first':'S0001','last':'S0002'}).json()
    options={'encoder':'x264','aspects':['1:1','9:16'],'burn_subtitles':True}
    project=client.post(f'/api/projects/{vid}',json={'clips':[clip],'options':options}).json()
    request={'video_id':vid,'clips':[clip],'options':options,'expected_revision':project['revision'],'require_review':True}
    assert client.post('/api/shorts/render',json=request).status_code==409
    project=client.post(f'/api/projects/{vid}/clips/1/review',json={'approved':True,'expected_revision':project['revision']}).json()
    # A title edit must invalidate prior approval, even if the client sends approved=true.
    project['clips'][0]['title']='Đã sửa tiêu đề'
    project=client.post(f'/api/projects/{vid}',json={**project,'expected_revision':project['revision']}).json()
    assert not project['clips'][0]['review']['approved']
    project=client.post(f'/api/projects/{vid}/clips/1/review',json={'approved':True,'expected_revision':project['revision']}).json()
    request.update(clips=project['clips'],expected_revision=project['revision'])
    task=client.post('/api/shorts/render',json=request)
    assert task.status_code==200,task.text
    result=await_task(client,task.json()['task_id'])
    assert {c['aspect'] for c in result['clips']}=={'1:1','9:16'}
    for clip in result['clips']:
        assert client.get(clip['download_url']).status_code==200
        assert 'Báp-têm' in client.get(clip['srt_url']).text
    assert client.get(result['zip_url']).status_code==200
    portrait=next(c for c in result['clips'] if c['aspect']=='9:16')
    item_id=portrait['library_id']
    assert client.patch(f'/api/library/{item_id}',json={'publication_status':'published','publication_url':'https://example.com/test-post'}).status_code==200
    package=client.post(f'/api/library/{item_id}/publication-package',json={'platform':'youtube_shorts'})
    assert package.status_code==200
    with zipfile.ZipFile(io.BytesIO(client.get(package.json()['zip_url']).content)) as archive:
        assert {'subtitles.srt','cover.jpg','metadata.json'} <= set(archive.namelist())
    backup=client.post(f'/api/projects/{vid}/backup').json()
    content=client.get(backup['download_url']).content
    restored=client.post('/api/backups/restore',files={'file':('project.zip',content,'application/zip')})
    assert restored.status_code==200,restored.text
    assert restored.json()['video_id']!=vid
    assert not restored.json()['clips'][0]['review']['approved']
    assert project_service.ProjectStore(store.path).get(vid)['clips'][0]['title']=='Đã sửa tiêu đề'
