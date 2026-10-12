import os
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.project_service import ProjectStore


@pytest.fixture
def cleanup_env(tmp_path, monkeypatch):
    files = {}
    for name in ("UPLOADS_DIR", "SUBTITLES_DIR", "SHORTS_DIR", "LOGOS_DIR",
                 "LIBRARY_DIR", "AUDIO_DIR", "TMP_DIR", "PACKAGES_DIR", "SEGMENTS_DIR"):
        directory = tmp_path / name
        directory.mkdir()
        monkeypatch.setattr(main, name, directory)
        files[name] = directory / "sample.dat"
        files[name].write_bytes(b"saved data")
        old = time.time() - 10800
        os.utime(files[name], (old, old))
    video = main.UPLOADS_DIR / "sample.mp4"
    video.write_bytes(b"video")
    store = ProjectStore(tmp_path / "projects.sqlite3")
    store.save("sample", title="Saved project")
    store.save("missing", title="Project without upload")
    monkeypatch.setattr(main, "project_store", store)
    manager = Mock()
    manager.has_active_tasks.return_value = False
    manager.cleanup_old_tasks.return_value = 0
    monkeypatch.setattr(main, "task_manager", manager)
    monkeypatch.delenv("CHURCH_PASSWORD", raising=False)
    return TestClient(main.app), files, store, manager


@pytest.mark.parametrize("query", ["", "?clear_all=true"])
def test_cleanup_preserves_saved_data_and_projects(cleanup_env, query):
    client, files, store, _ = cleanup_env
    nested = main.TMP_DIR / "nested"
    nested.mkdir()
    scratch = nested / "old.dat"
    scratch.write_bytes(b"temp")
    old = time.time() - 10800
    os.utime(scratch, (old, old))
    keep = main.AUDIO_DIR / ".gitkeep"
    keep.touch()

    response = client.post("/api/system/cleanup" + query)

    assert response.status_code == 200
    for name, path in files.items():
        assert path.exists() == (name not in {
            "AUDIO_DIR", "TMP_DIR", "PACKAGES_DIR", "SEGMENTS_DIR"})
    assert (main.UPLOADS_DIR / "sample.mp4").exists()
    assert store.get("sample")["title"] == "Saved project"
    assert store.get("missing")["title"] == "Project without upload"
    assert not scratch.exists()
    assert keep.exists()
    assert response.json()["deleted_files"] == 5
    assert response.json()["failed_files"] == 0


def test_cleanup_counts_failed_deletions(cleanup_env, monkeypatch):
    client, files, _, _ = cleanup_env
    locked = files["AUDIO_DIR"]
    original_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        if path == locked:
            raise PermissionError("File in use")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    response = client.post("/api/system/cleanup?clear_all=true")

    assert response.status_code == 200
    assert response.json()["failed_files"] == 1
    assert response.json()["deleted_files"] == 3
    assert locked.exists()
    assert not files["TMP_DIR"].exists()


def test_cleanup_blocks_active_tasks(cleanup_env):
    client, files, _, manager = cleanup_env
    manager.has_active_tasks.return_value = True

    response = client.post("/api/system/cleanup?clear_all=true")

    assert response.status_code == 409
    assert all(path.exists() for path in files.values())
    manager.cleanup_old_tasks.assert_not_called()


def test_cleanup_default_keeps_recent_temporary_files(cleanup_env):
    client, _, _, _ = cleanup_env
    recent = main.TMP_DIR / "recent.dat"
    recent.write_bytes(b"recent")

    assert client.post("/api/system/cleanup").status_code == 200
    assert recent.exists()


def test_cleanup_confirmation_explains_preserved_data():
    source = (main.STATIC_DIR / "js" / "app.js").read_text(encoding="utf-8")
    assert 'confirm("Chỉ xoá file tạm (audio, gói zip, file trung gian). Video gốc, phụ đề, project và thư viện được giữ nguyên.")' in source
