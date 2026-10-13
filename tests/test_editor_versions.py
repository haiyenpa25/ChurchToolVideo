import pytest
from app.services.project_service import ProjectStore


def test_versions_survive_restart_and_restore_preserves_source(tmp_path):
    path = tmp_path / "projects.db"
    store = ProjectStore(path)
    store.save("sample", video={"original_name": "sermon.mp4"})
    first = store.save("sample", clips=[{"id": 1, "title": "First", "parts": []}], options={}, raw_text="first")
    store.save("sample", clips=[{"id": 1, "title": "Second", "parts": []}], raw_text="second")
    store = ProjectStore(path)
    assert len(store.list_versions("sample")) == 2
    restored = store.restore_version("sample", first["revision"])
    assert restored["clips"][0]["title"] == "First"
    assert restored["video"]["original_name"] == "sermon.mp4"
    assert restored["revision"] == 3


def test_identical_autosaves_do_not_create_versions_and_stale_save_is_rejected(tmp_path):
    from app.services.project_service import RevisionConflict
    store = ProjectStore(tmp_path / "projects.db")
    data = store.save("sample", clips=[], options={}, raw_text="")
    store.save("sample", clips=[], options={}, raw_text="", expected_revision=data["revision"])
    assert len(store.list_versions("sample")) == 1
    with pytest.raises(RevisionConflict):
        store.save("sample", raw_text="stale", expected_revision=0)
    assert store.get("sample")["raw_text"] == ""


def test_content_edits_invalidate_review_but_style_edits_do_not(tmp_path):
    store = ProjectStore(tmp_path / "projects.db")
    clip = {"id": 1, "title": "Title", "parts": [{"start_sec": 0, "end_sec": 2}], "style": {"font": "noto"}}
    store.save("sample", clips=[clip])
    reviewed = store.review_clip("sample", 1, True, "Đã nghe ngữ cảnh")
    clip = reviewed["clips"][0]
    clip["style"]["font"] = "bevietnam"
    assert store.save("sample", clips=[clip])["clips"][0]["review"]["approved"]
    clip["parts"][0]["end_sec"] = 3
    assert not store.save("sample", clips=[clip])["clips"][0]["review"]["approved"]


def test_cannot_claim_review_through_normal_save(tmp_path):
    store = ProjectStore(tmp_path / "projects.db")
    data = store.save("sample", clips=[{"id": 1, "parts": [], "review": {"approved": True}}])
    assert not data["clips"][0]["review"]["approved"]


def test_history_is_bounded_and_cross_project_restore_is_rejected(tmp_path):
    store = ProjectStore(tmp_path / "projects.db")
    for i in range(55): store.save("sample", raw_text=str(i))
    assert len(store.list_versions("sample")) == 50
    store.save("another", raw_text="other")
    with pytest.raises(FileNotFoundError): store.restore_version("another", 55)
