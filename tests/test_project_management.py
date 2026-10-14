import pytest
from fastapi.testclient import TestClient
from app.services.project_service import ProjectStore, RevisionConflict


def test_trash_restore_preserves_history_and_rejects_stale_writes(tmp_path):
    store=ProjectStore(tmp_path/'projects.db')
    original=store.save('sermon',clips=[],raw_text='Original sermon')
    renamed=store.manage('sermon',title='Sunday sermon',expected_revision=original['revision'])
    with pytest.raises(RevisionConflict):
        store.manage('sermon',deleted=True,expected_revision=original['revision'])
    deleted=store.manage('sermon',deleted=True,expected_revision=renamed['revision'])
    assert store.list()==[]
    assert store.list(include_deleted=True)[0]['title']=='Sunday sermon'
    with pytest.raises(FileNotFoundError): store.get('sermon')
    with pytest.raises(RevisionConflict): store.save('sermon',raw_text='Stale autosave')
    with pytest.raises(RevisionConflict): store.save_clip_render('sermon',1,status='RUNNING')
    restored=store.manage('sermon',deleted=False,expected_revision=deleted['revision'])
    assert restored['raw_text']=='Original sermon'
    assert restored['revision']==deleted['revision']+1
    assert len(store.list())==1 and store.list(include_deleted=True)==[]
    assert store.list_versions('sermon')


def test_management_api_validation_conflicts_and_restore(tmp_path,monkeypatch):
    from app import main
    store=ProjectStore(tmp_path/'projects.db')
    saved=store.save('sermon',clips=[])
    monkeypatch.setattr(main,'project_store',store)
    monkeypatch.delenv('CHURCH_PASSWORD',raising=False)
    monkeypatch.setattr(main.task_manager,'has_active_tasks',lambda:False)
    client=TestClient(main.app)
    assert client.patch('/api/projects/sermon',json={'title':'   ','expected_revision':saved['revision']}).status_code==422
    assert client.request('DELETE','/api/projects/sermon',json={}).status_code==422
    renamed=client.patch('/api/projects/sermon',json={'title':' Sunday   sermon ','expected_revision':saved['revision']})
    assert renamed.status_code==200 and renamed.json()['title']=='Sunday sermon'
    assert client.request('DELETE','/api/projects/sermon',json={'expected_revision':saved['revision']}).status_code==409
    deleted=client.request('DELETE','/api/projects/sermon',json={'expected_revision':renamed.json()['revision']})
    assert deleted.status_code==200
    assert client.get('/api/projects').json()==[]
    assert len(client.get('/api/projects?trash=true').json())==1
    restored=client.post('/api/projects/sermon/restore',json={'expected_revision':deleted.json()['revision']})
    assert restored.status_code==200
    monkeypatch.setattr(main.task_manager,'has_active_tasks',lambda:True)
    assert client.patch('/api/projects/sermon',json={'title':'Busy','expected_revision':restored.json()['revision']}).status_code==409
