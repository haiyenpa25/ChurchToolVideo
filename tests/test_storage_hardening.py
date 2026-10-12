import sqlite3
import os
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.services import task_manager as tasks, project_service, library_service, llm_service


def test_sqlite_connections_close_after_store_operations(tmp_path, monkeypatch):
    original = sqlite3.connect
    connections = []
    class Connection(sqlite3.Connection):
        closed = False
        def close(self): self.closed = True; super().close()
    def connect(*args, **kwargs):
        connection = original(*args, **kwargs, factory=Connection)
        connections.append(connection)
        return connection
    monkeypatch.setattr(sqlite3, "connect", connect)
    store = project_service.ProjectStore(tmp_path / "data.db")
    store.save("sample", title="Title"); store.get("sample"); store.list()
    manager = tasks.TaskManager(tmp_path / "tasks.db")
    task_id = manager.create_task(); manager.complete_task(task_id, {})
    library = library_service.Library(tmp_path / "library.db", tmp_path / "library")
    library.search(); library.sources()
    assert connections and all(connection.closed for connection in connections)


def test_progress_writes_are_throttled_but_completion_is_saved(tmp_path, monkeypatch):
    manager = tasks.TaskManager(tmp_path / "data.db")
    task_id = manager.create_task()
    writes = []
    original = tasks.sqlite3.connect
    def connect(*args, **kwargs): writes.append(1); return original(*args, **kwargs)
    monkeypatch.setattr(tasks.sqlite3, "connect", connect)
    monkeypatch.setattr(tasks.time, "time", lambda: 10000000000)
    for pct in range(1, 51): manager.update_task(task_id, progress=pct)
    manager.complete_task(task_id, {"done": True})
    assert len(writes) <= 3
    assert tasks.TaskManager(tmp_path / "data.db").get_task(task_id).result == {"done": True}


def test_library_rejects_invalid_file_before_moving(tmp_path, monkeypatch):
    store = library_service.Library(tmp_path / "data.db", tmp_path / "library")
    source = tmp_path / "broken.mp4"; source.write_bytes(b"broken")
    monkeypatch.setattr(library_service, "get_media_info", lambda p: {"duration": 0, "width": None, "height": None})
    with pytest.raises(ValueError): store.add(source, kind="short", video_id="sample", title="Title")
    assert source.exists()
    assert store.search()[1] == 0


def test_locked_library_file_keeps_database_row(tmp_path, monkeypatch):
    store = library_service.Library(tmp_path / "data.db", tmp_path / "library")
    source = tmp_path / "source.mp4"; source.write_bytes(b"video")
    monkeypatch.setattr(library_service, "get_media_info", lambda p: {"duration": 1, "width": 320, "height": 180})
    monkeypatch.setattr(store, "_thumbnail", lambda *a: False)
    item = store.add(source, kind="short", video_id="sample", title="Title")
    original = Path.unlink
    def unlink(path, *args, **kwargs):
        if path == store.file_path(item): raise PermissionError("file in use")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(PermissionError): store.delete(item["id"])
    assert store.get(item["id"])["title"] == "Title"


def test_llm_retries_transient_statuses_with_backoff(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key"); monkeypatch.setenv("OPENAI_MODEL", "model")
    statuses = iter([429, 503, 200]); calls, delays = [], []
    def post(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(status_code=next(statuses), json=lambda: {"output": [{"content": [{"type": "output_text", "text": "done"}]}]})
    monkeypatch.setattr(llm_service.httpx, "post", post)
    monkeypatch.setattr(llm_service, "sleep", delays.append)
    assert llm_service.call_llm("prompt", "openai") == "done"
    assert len(calls) == 3 and delays == [1, 2]


def test_maintenance_only_removes_old_temporary_files(tmp_path, monkeypatch):
    from app.services import maintenance
    from app import config
    paths = {}
    for name in ("AUDIO_DIR", "TMP_DIR", "PACKAGES_DIR", "SEGMENTS_DIR", "UPLOADS_DIR", "SUBTITLES_DIR", "SHORTS_DIR"):
        directory = tmp_path / name; directory.mkdir(); monkeypatch.setattr(config, name, directory)
        paths[name] = directory / "old.dat"; paths[name].write_bytes(b"data")
        old = time.time() - 90000; os.utime(paths[name], (old, old))
    manager = tasks.TaskManager(); running = manager.create_task(); done = manager.create_task()
    manager.complete_task(done, {})
    manager.get_task(running).created_at = manager.get_task(done).created_at = time.time() - 31 * 86400
    monkeypatch.setattr(maintenance, "task_manager", manager)
    maintenance.maintain_storage()
    assert all(path.exists() for path in paths.values())
    manager.complete_task(running, {})
    maintenance.maintain_storage()
    assert not paths["TMP_DIR"].exists() and paths["UPLOADS_DIR"].exists()
    assert manager.get_task(done) is None


def test_upload_response_does_not_expose_absolute_path(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(main, "get_media_info", lambda p: {"duration": 1, "width": 320, "height": 180, "duration_formatted": "00:00:01"})
    monkeypatch.setattr(main, "project_store", SimpleNamespace(save=lambda *a, **k: None))
    response = TestClient(main.app).post("/api/upload", files={"file": ("sample.mp4", b"video", "video/mp4")})
    assert response.status_code == 200
    assert response.json()["file_path"] == response.json()["filename"]
