import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.services.task_manager import TaskManager
from app.services.project_service import ProjectStore
from app.services import llm_service
from app.services.reframe_service import crop_expression
from app.main import app


def test_task_and_project_survive_restart(tmp_path):
    path=tmp_path / "state.sqlite3"
    first=TaskManager(path)
    complete=first.create_task()
    interrupted=first.create_task()
    first.complete_task(complete,{"clips":[{"file_url":"/workspace/shorts/test.mp4"}]})
    restarted=TaskManager(path)
    assert restarted.get_task(complete).status=="COMPLETED"
    assert restarted.get_task(complete).result["clips"]
    assert restarted.get_task(interrupted).status=="FAILED"
    assert "khởi động lại" in restarted.get_task(interrupted).error
    ProjectStore(path).save("video", clips=[{"title":"Đức tin"}])
    assert ProjectStore(path).get("video")["clips"][0]["title"]=="Đức tin"
    restarted.cleanup_old_tasks(0)
    assert not TaskManager(path).list_tasks()


@pytest.mark.parametrize("provider,prefix,payload", [
    ("openai","OPENAI",{"output":[{"type":"reasoning"},{"content":[{"type":"output_text","text":'{"clips":[]}'}]}]}),
    ("gemini","GEMINI",{"candidates":[{"content":{"parts":[{"text":'{"clips":[]}'}]}}]}),
    ("claude","ANTHROPIC",{"content":[{"type":"text","text":'{"clips":[]}'}]}),
])
def test_llm_provider_contracts(provider,prefix,payload,monkeypatch):
    monkeypatch.setenv(prefix+"_API_KEY","test-secret")
    monkeypatch.setenv(prefix+"_MODEL","test-model")
    requests=[]
    def post(url,**kwargs):
        requests.append((url,kwargs)); return SimpleNamespace(status_code=200,json=lambda:payload)
    monkeypatch.setattr(llm_service.httpx,"post",post)
    assert llm_service.generate_shorts_text("transcript",provider)=='{"clips":[]}'
    assert requests[0][1]["timeout"]==120
    assert "test-secret" not in json.dumps(llm_service.available_providers())
    if provider=="openai": assert requests[0][1]["json"]["store"] is False
    if provider=="gemini": assert requests[0][1]["headers"]["x-goog-api-key"]=="test-secret"
    if provider=="claude": assert requests[0][1]["headers"]["anthropic-version"]=="2023-06-01"


def test_llm_error_does_not_leak_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","private-key")
    monkeypatch.setenv("OPENAI_MODEL","model")
    monkeypatch.setattr(llm_service.httpx,"post",lambda *a,**k:SimpleNamespace(status_code=401))
    with pytest.raises(RuntimeError,match="HTTP 401") as error:
        llm_service.generate_shorts_text("transcript","openai")
    assert "private-key" not in str(error.value)


def test_optional_auth_protects_api_media_and_cross_origin(monkeypatch):
    monkeypatch.setenv("CHURCH_PASSWORD","mật-khẩu-thử")
    client=TestClient(app)
    assert client.get("/api/projects").status_code==401
    assert client.get("/workspace/shorts/example.mp4").status_code==401
    assert client.get("/api/auth/status").json()["authenticated"] is False
    assert client.post("/api/auth/login",json={"password":"incorrect"}).status_code==401
    response=client.post("/api/auth/login",json={"password":"mật-khẩu-thử"})
    assert response.status_code==200 and "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/projects").status_code==200
    assert client.post("/api/auth/logout",headers={"Origin":"https://other.example"}).status_code==403
    client.cookies.set("church_session","invalid")
    assert client.get("/api/projects").status_code==401
    client.post("/api/auth/logout")
    assert client.get("/api/auth/status").json()["authenticated"] is False


def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CHURCH_PASSWORD",raising=False)
    assert TestClient(app).get("/api/projects").status_code==200


def test_reframe_expression_interpolates_numeric_positions():
    expression=crop_expression([(0,.2),(1,.8),(2,.5)])
    assert "if(lt(t,1.000)" in expression
    assert "0.600000" in expression


def test_generation_worker_parses_and_persists(monkeypatch,tmp_path):
    from app import shorts_api
    from app.services import task_manager, project_service, transcript_service
    from app.models.schemas import ShortsGenerateRequest
    manager=TaskManager(tmp_path/"state.sqlite3")
    store=ProjectStore(tmp_path/"state.sqlite3")
    monkeypatch.setattr(task_manager,"task_manager",manager)
    monkeypatch.setattr(project_service,"project_store",store)
    monkeypatch.setattr(transcript_service,"SUBTITLES_DIR",tmp_path)
    transcript_service.save_transcript("sample",100,[{"start_sec":1,"end_sec":70,"text":"Đức tin"}])
    monkeypatch.setattr(llm_service,"generate_shorts_text",lambda *a:'{"clips":[{"title":"Đức tin","parts":[{"from":"S0001","to":"S0001"}]}]}')
    task_id=manager.create_task()
    shorts_api.generate_worker(task_id,ShortsGenerateRequest(video_id="sample",provider="openai"))
    assert manager.get_task(task_id).status=="COMPLETED"
    assert store.get("sample")["clips"][0]["parts"][0]["from_id"]=="S0001"
