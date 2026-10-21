from fastapi.testclient import TestClient
from app import main


def test_cpu_choice_is_forwarded_from_api_to_worker(monkeypatch,tmp_path):
    monkeypatch.delenv('CHURCH_PASSWORD',raising=False)
    monkeypatch.setattr(main,'find_video',lambda _:tmp_path/'sample.mp4')
    calls=[]
    def submit(*args,**kwargs):
        calls.append(kwargs)
        return 'test-task'
    monkeypatch.setattr(main,'submit_task',submit)
    client=TestClient(main.app)
    response=client.post('/api/transcribe',json={'video_id':'sample','model_size':'tiny','device':'cpu'})
    assert response.status_code==200 and response.json()['task_id']=='test-task'
    assert calls[0]['device']=='cpu' and calls[0]['decoding_mode']=='quality'
    assert client.post('/api/transcribe',json={'video_id':'sample','device':'metal'}).status_code==422
