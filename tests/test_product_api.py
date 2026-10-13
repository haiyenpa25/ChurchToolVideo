import pytest
from fastapi.testclient import TestClient
from app import main, product_api
from app.services.project_service import ProjectStore
from app.services.brand_service import BrandStore


@pytest.fixture
def product_client(tmp_path, monkeypatch):
    from app.services import transcript_service
    monkeypatch.delenv("CHURCH_PASSWORD", raising=False)
    monkeypatch.setattr(main,"project_store",ProjectStore(tmp_path / "data.db"))
    brands=BrandStore(tmp_path / "data.db")
    monkeypatch.setattr(product_api,"brand_store",brands)
    from app.services import brand_service
    monkeypatch.setattr(brand_service,"brand_store",brands)
    monkeypatch.setattr(transcript_service,"UPLOADS_DIR",tmp_path)
    (tmp_path / "sample.mp4").write_bytes(b"video")
    return TestClient(main.app)


def test_editor_api_save_review_restore_and_conflict(product_client):
    client=product_client
    payload={"clips":[{"id":1,"title":"First","parts":[{"start_sec":0,"end_sec":2}]}],"raw_text":"original","brand_id":"thanh-my-loi"}
    saved=client.post("/api/projects/sample",json=payload)
    assert saved.status_code==200 and saved.json()["revision"]==1
    reviewed=client.post("/api/projects/sample/clips/1/review",json={"approved":True,"notes":"Đã nghe","expected_revision":1})
    assert reviewed.status_code==200 and reviewed.json()["clips"][0]["review"]["approved"]
    assert client.post("/api/projects/sample",json={**payload,"expected_revision":1}).status_code==409
    payload["clips"][0]["title"]="Second"
    assert not client.post("/api/projects/sample",json=payload).json()["clips"][0]["review"]["approved"]
    versions=client.get("/api/projects/sample/versions").json()
    assert len(versions)==3
    from unittest.mock import Mock
    manager=Mock(); manager.has_active_tasks.return_value=False
    from pytest import MonkeyPatch
    with MonkeyPatch.context() as patch:
        patch.setattr(main,"task_manager",manager)
        restored=client.post("/api/projects/sample/versions/1/restore",json={"expected_revision":3})
        assert restored.status_code==200 and restored.json()["clips"][0]["title"]=="First"
        manager.has_active_tasks.return_value=True
        assert client.post("/api/projects/sample/versions/1/restore",json={}).status_code==409


def test_brand_api_validation_and_authenticated_access(product_client, monkeypatch):
    client=product_client
    assert client.get("/api/brand-presets").json()[0]["name"]=="Hội thánh Tin lành Thạnh Mỹ Lợi"
    assert client.post("/api/brand-presets",json={"name":"New","accent_color":"#000000"}).status_code==200
    assert client.post("/api/brand-presets",json={"name":"New","logo_id":"../file"}).status_code==422
    monkeypatch.setenv("CHURCH_PASSWORD","test-password")
    assert client.get("/api/brand-presets").status_code==401
    assert client.get("/api/projects/sample/versions").status_code==401


def test_render_checks_saved_review_instead_of_trusting_request(product_client):
    response=product_client.post("/api/shorts/render",json={"video_id":"sample","require_review":True,"clips":[
        {"id":1,"review":{"approved":True},"parts":[{"start_sec":0,"end_sec":1}]}]})
    assert response.status_code==409


def test_workflow_api_glossary_selection_cancel_and_statistics(product_client,tmp_path,monkeypatch):
    from app.services import workflow_service,transcript_service,backup_service
    from app.services.task_manager import TaskManager
    monkeypatch.setattr(workflow_service,'glossary_store',workflow_service.GlossaryStore(tmp_path/'settings.db'))
    monkeypatch.setattr(transcript_service,'SUBTITLES_DIR',tmp_path)
    monkeypatch.setattr(backup_service,'BACKUPS_DIR',tmp_path/'backups')
    monkeypatch.setattr(main,'task_manager',TaskManager())
    client=product_client
    assert client.put('/api/glossary',json={'terms':[' Mục sư An ','Mục sư An']}).json()['terms']==['Mục sư An']
    assert client.put('/api/glossary',json={'terms':['a\nb']}).status_code==422
    transcript_service.save_transcript('sample',4,[{'start_sec':0,'end_sec':2,'text':'Chúa yêu thương'}])
    assert client.get('/api/projects/sample/transcript').status_code==200
    selection=client.post('/api/transcript-selection',json={'video_id':'sample','first':'S0001','last':'S0001'})
    assert selection.status_code==200 and selection.json()['parts'][0]['words'][0]['w']=='Chúa'
    task_id=main.task_manager.create_task()
    assert client.post(f'/api/tasks/{task_id}/cancel').json()['status']=='CANCELLED'
    assert client.post('/api/tasks/missing/cancel').status_code==404
    assert client.get('/api/editor/statistics').json()['tasks']['CANCELLED']==1
    assert client.get('/api/backups/../../download').status_code!=200
    assert client.patch('/api/library/'+'a'*32,json={'publication_url':'javascript:alert(1)'}).status_code==422
    monkeypatch.setenv('CHURCH_PASSWORD','test-password')
    for url in ('/api/glossary','/api/editor/statistics','/api/backups','/api/projects/sample/transcript','/api/projects/sample/waveform'):
        assert client.get(url).status_code==401
