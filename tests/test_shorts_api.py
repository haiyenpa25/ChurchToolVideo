import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services import transcript_service as transcripts


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(transcripts, "SUBTITLES_DIR", tmp_path)
    data = {"video_id": "sample", "duration": 100, "sentences": [
        {"id": "S0001", "start": 0, "end": 65, "text": "Đức tin và hy vọng", "words": []}]}
    (tmp_path / "sample.json").write_text(json.dumps(data), encoding="utf-8")
    return TestClient(app)


def test_prompt_and_preview_endpoints(client):
    prompt = client.get("/api/shorts/prompt/sample")
    assert prompt.status_code == 200 and "S0001" in prompt.json()["prompt"]
    response = client.post("/api/shorts/preview", json={"video_id":"sample", "raw_text": 'CLIP 1: Đức tin\nS0001 -> S0001'})
    assert response.status_code == 200
    assert response.json()["clips"][0]["total_duration_sec"] == 65.15
    assert client.get("/api/shorts/prompt/sample?num_clips=50").status_code == 422


def test_reject_invalid_data_and_logo(client):
    assert client.post("/api/shorts/preview", json={"video_id":"../sample", "raw_text":""}).status_code == 422
    assert client.post("/api/shorts/render", json={"video_id":"sample", "clips":[]}).status_code == 422
    assert client.post("/api/shorts/logo", files={"file":("fake.png", b"not PNG", "image/png")}).status_code == 400
