from pathlib import Path
from types import SimpleNamespace
from app.models.schemas import ShortsRenderRequest
from app import shorts_api
from app.services import task_manager, project_service, shorts_render_service, transcript_service, library_service


def test_batch_failure_keeps_completed_clips_and_hides_internal_error(tmp_path, monkeypatch):
    manager = task_manager.TaskManager()
    store = project_service.ProjectStore(tmp_path / "data.db")
    monkeypatch.setattr(task_manager, "task_manager", manager)
    monkeypatch.setattr(project_service, "project_store", store)
    monkeypatch.setattr(transcript_service, "find_video", lambda _: tmp_path / "source.mp4")
    monkeypatch.setattr(shorts_api, "load_transcript", lambda _: None)
    def render(video, clip, *args):
        if clip.id == 2: raise RuntimeError("ffmpeg stderr C:/private/source.mp4")
        return tmp_path / "done.mp4"
    monkeypatch.setattr(shorts_render_service, "render_short", render)
    item = {"id": "a" * 32, "title": "Done", "platforms": [], "filename": "done.mp4",
            "file_url": "/workspace/library/done.mp4", "srt_url": None, "file_size": 10, "duration_sec": 1}
    monkeypatch.setattr(library_service, "library", SimpleNamespace(add=lambda *a, **k: item))
    req = ShortsRenderRequest(video_id="sample", create_zip=False, clips=[
        {"id": i, "parts": [{"start_sec": 0, "end_sec": 1}]} for i in (1, 2)])
    task_id = manager.create_task()
    shorts_api.render_worker(task_id, req)
    task = manager.get_task(task_id)
    assert task.status == "FAILED" and task.result["partial"]
    assert task.result["clips"][0]["download_url"]
    assert "private" not in task.error and "Mã lỗi:" in task.error
    assert store.get("sample")["render_result"]["partial"]
