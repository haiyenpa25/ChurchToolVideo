from threading import Event
import pytest
from fastapi.testclient import TestClient
from app import main
from app.services import task_manager as tasks, transcript_service


def test_bounded_queue_returns_429_without_creating_task():
    manager = tasks.TaskManager()
    queue = tasks.BoundedTaskQueue(1, max_pending=1)
    started, release = Event(), Event()
    def worker(task_id):
        started.set()
        release.wait(5)
        manager.complete_task(task_id, {})
    try:
        first = queue.submit(manager, worker)
        assert started.wait(2)
        second = queue.submit(manager, worker)
        assert "vị trí 1" in manager.get_task(second).message
        with pytest.raises(tasks.QueueFull):
            queue.submit(manager, worker)
        assert len(manager.list_tasks()) == 2
    finally:
        release.set()
        queue.executor.shutdown(wait=True)
    assert manager.get_task(first).status == "COMPLETED"


def test_render_endpoint_returns_429_when_queue_is_full(tmp_path, monkeypatch):
    from app import shorts_api
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(transcript_service, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(shorts_api, "submit_task", lambda *a, **k: (_ for _ in ()).throw(__import__("fastapi").HTTPException(429, "Queue full")))
    monkeypatch.setattr(main, "get_media_info", lambda p: {"duration": 3})
    from app.services import ffmpeg_service
    monkeypatch.setattr(ffmpeg_service, "get_media_info", lambda p: {"duration": 3})
    response = TestClient(main.app).post("/api/shorts/render", json={"video_id": "sample", "clips": [
        {"id": 1, "parts": [{"start_sec": 0, "end_sec": 1}]}]})
    assert response.status_code == 429


def test_render_request_limits_total_words_and_duration():
    from app.models.schemas import ShortsRenderRequest
    from pydantic import ValidationError
    word = {"w": "a", "start": 0, "end": 1}
    with pytest.raises(ValidationError):
        ShortsRenderRequest(video_id="sample", clips=[{"id": 1, "parts": [
            {"start_sec": 0, "end_sec": 1, "words": [word] * 10000}] * 6}])
    with pytest.raises(ValidationError):
        ShortsRenderRequest(video_id="sample", clips=[{"id": 1, "parts": [{"start_sec": 0, "end_sec": 901}]}])


def test_invalid_video_upload_is_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(main, "get_media_info", lambda p: {"duration": 0, "width": None, "height": None})
    response = TestClient(main.app).post("/api/upload", files={"file": ("broken.mp4", b"invalid", "video/mp4")})
    assert response.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_interrupted_upload_removes_partial_file(tmp_path, monkeypatch):
    from io import BytesIO
    from starlette.datastructures import UploadFile
    class BrokenStream(BytesIO):
        def read(self, size):
            if self.tell(): raise OSError("disconnected")
            return super().read(size)
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    with pytest.raises(OSError):
        main.upload_video(UploadFile(filename="sample.mp4", file=BrokenStream(b"video")))
    assert list(tmp_path.iterdir()) == []
