import json
import subprocess
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import library_api
from app.config import FFMPEG_BIN, FFPROBE_BIN
from app.main import app
from app.models.schemas import ShortClip, ClipPart, ShortsRenderOptions
from app.services import library_service, shorts_render_service as renderer
from app.services.captions_service import write_ass
from app.services.library_service import Library, fold, transcript_text


def make_video(path, size="320x180", seconds=2):
    subprocess.run([FFMPEG_BIN, "-y", "-f", "lavfi", "-i", f"testsrc2=s={size}:r=30:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=f=400:d={seconds}", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(path)], capture_output=True, check=True)
    return path


@pytest.fixture
def store(tmp_path, monkeypatch):
    store = Library(tmp_path / "db.sqlite3", tmp_path / "library")
    monkeypatch.setattr(library_api, "library", store)
    monkeypatch.setattr(library_service, "library", store)
    return store


def add(store, tmp_path, title, **kwargs):
    safe_tmp = fold(title).replace(" ", "_").replace("?", "").replace("*", "").replace("|", "")
    video = make_video(tmp_path / f"{safe_tmp}.mp4")
    return store.add(video, kind=kwargs.pop("kind", "short"), video_id=kwargs.pop("video_id", "sermon1"),
                     title=title, **kwargs)


def test_fold_strips_vietnamese_accents():
    assert fold("  Đức TIN và   Hy Vọng ") == "duc tin va hy vong"


def test_transcript_text_only_overlapping_sentences():
    transcript = {"sentences": [{"start": 0, "end": 5, "text": "Một"}, {"start": 5, "end": 9, "text": "Hai"},
                                {"start": 20, "end": 25, "text": "Ba"}]}
    assert transcript_text(transcript, [{"start_sec": 4, "end_sec": 8}, {"start_sec": 21, "end_sec": 22}]) == "Một Hai Ba"
    assert transcript_text(None, [{"start_sec": 0, "end_sec": 1}]) == ""


def test_add_moves_file_and_makes_thumbnail(store, tmp_path):
    source = make_video(tmp_path / "render.mp4")
    item = store.add(source, kind="short", video_id="sermon1", title="Đức tin", aspect="9:16")
    assert not source.exists() and store.file_path(item).exists()
    assert item["platforms"] == ["TikTok", "YouTube Shorts", "Reels Facebook/Instagram"]
    assert item["duration_sec"] == pytest.approx(2, abs=0.2)
    assert (store.thumbs / f"{item['id']}.jpg").exists()


def test_search_filters_sort_and_accent_free_query(store, tmp_path):
    faith = add(store, tmp_path, "Đức tin vững vàng", aspect="9:16", text="Hãy tin cậy Chúa")
    add(store, tmp_path, "Lời cầu nguyện", aspect="16:9", kind="segment", video_id="sermon2")
    hope = add(store, tmp_path, "Hy vọng", aspect="9:16", source_name="Chúa nhật 12-10")
    assert [i["id"] for i in store.search("duc TIN")[0]] == [faith["id"]]
    assert [i["id"] for i in store.search("tin cay chua")[0]] == [faith["id"]]
    assert [i["id"] for i in store.search("chua nhat")[0]] == [hope["id"]]
    assert store.search(aspect="9:16")[1] == 2
    assert store.search(kind="segment")[0][0]["title"] == "Lời cầu nguyện"
    assert store.search(video_id="sermon2")[1] == 1
    assert [i["title"] for i in store.search(sort="title")[0]] == ["Đức tin vững vàng", "Hy vọng", "Lời cầu nguyện"]
    assert store.search("100%")[1] == 0
    items, total = store.search(limit=1, offset=1)
    assert total == 3 and len(items) == 1


def test_update_tags_favorite_and_delete(store, tmp_path):
    item = add(store, tmp_path, "Ân điển")
    updated = store.update(item["id"], tags=["Giáng sinh", " giáng sinh ", "Giáng sinh", ""], favorite=True, title=None)
    assert updated["tags"] == ["Giáng sinh", "giáng sinh"] and updated["favorite"] and updated["title"] == "Ân điển"
    assert store.search("giang sinh", favorite=True)[1] == 1
    store.delete(item["id"])
    assert not store.file_path(item).exists() and store.search()[1] == 0
    with pytest.raises(FileNotFoundError):
        store.get(item["id"])


def test_zip_uses_readable_unique_names(store, tmp_path):
    from datetime import datetime
    first = add(store, tmp_path, "Bình an", aspect="9:16", speaker="Hoàng Nam Tiến")
    second = add(store, tmp_path, "Bình an?", aspect="9:16", speaker="Hoàng Nam Tiến")
    date_prefix = datetime.fromtimestamp(first["created_at"]).strftime("%Y%m%d")
    with zipfile.ZipFile(store.zip([first, second], tmp_path / "out.zip")) as archive:
        assert archive.namelist() == [
            f"{date_prefix}_Bình an_Hoàng Nam Tiến v1.mp4",
            f"{date_prefix}_Bình an_Hoàng Nam Tiến v2.mp4",
        ]


def test_library_api_round_trip(store, tmp_path):
    item = add(store, tmp_path, "Phước hạnh", aspect="1:1")
    client = TestClient(app)
    listing = client.get("/api/library", params={"q": "phuoc", "aspect": "1:1"}).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == item["id"]
    assert client.get("/api/library/sources").json() == [{"video_id": "sermon1", "source_name": "sermon1", "count": 1}]
    patched = client.patch(f"/api/library/{item['id']}", json={"title": "Phước hạnh thật", "tags": ["vui mừng"]})
    assert patched.status_code == 200 and patched.json()["title"] == "Phước hạnh thật"
    download = client.get(f"/api/library/{item['id']}/download")
    assert download.status_code == 200 and "Ph%C6%B0%E1%BB%9Bc" in download.headers["content-disposition"]
    zipped = client.post("/api/library/zip", json={"ids": [item["id"]]})
    assert zipped.status_code == 200 and client.get(zipped.json()["zip_url"]).status_code == 200
    assert client.post("/api/library/delete", json={"ids": [item["id"]]}).json() == {"deleted": 1}
    assert client.get(f"/api/library/{item['id']}").status_code == 404


def test_library_api_rejects_bad_input(store):
    client = TestClient(app)
    assert client.get("/api/library/xyz").status_code == 422
    assert client.get("/api/library", params={"sort": "drop table"}).status_code == 422
    assert client.post("/api/library/zip", json={"ids": ["../x"]}).status_code == 422
    assert client.post("/api/library/zip", json={"ids": []}).status_code == 422


def test_formats_endpoint_lists_platforms():
    data = TestClient(app).get("/api/shorts/formats").json()
    assert {a["aspect"] for a in data["aspects"]} == {"9:16", "16:9", "1:1", "4:5"}
    shorts = next(p for p in data["platforms"] if p["id"] == "youtube_shorts")
    assert shorts["aspect"] == "9:16" and shorts["max_sec"] == 180


def test_output_aspects_dedupes_and_falls_back():
    assert ShortsRenderOptions(aspect="16:9").output_aspects() == ["16:9"]
    assert ShortsRenderOptions(aspects=["9:16", "1:1", "9:16"]).output_aspects() == ["9:16", "1:1"]
    with pytest.raises(ValueError):
        ShortsRenderOptions(aspect="21:9")


@pytest.mark.parametrize("aspect,size", [("1:1", "1080:1080"), ("4:5", "1080:1350"), ("16:9", "1920:1080")])
def test_video_filter_sizes(aspect, size):
    for reframe in ("crop", "blur_pad"):
        assert f"scale={size}" in renderer.video_filter(ShortsRenderOptions(aspect=aspect, reframe=reframe))


def test_vertical_captions_stay_above_platform_ui(tmp_path):
    part = ClipPart(start_sec=0, end_sec=2)
    transcript = {"sentences": [{"start": 0, "end": 2, "text": "Chúa yêu bạn"}]}
    write_ass(tmp_path / "v.ass", part, transcript, 1080, 1920, aspect="9:16")
    write_ass(tmp_path / "h.ass", part, transcript, 1920, 1080, aspect="16:9")
    assert ",60,60,672,1" in (tmp_path / "v.ass").read_text(encoding="utf-8")
    assert ",60,60,86,1" in (tmp_path / "h.ass").read_text(encoding="utf-8")


@pytest.mark.integration
@pytest.mark.parametrize("aspect,expected", [("1:1", (1080, 1080)), ("4:5", (1080, 1350))])
def test_render_new_aspects(tmp_path, monkeypatch, aspect, expected):
    video = make_video(tmp_path / "input.mp4", seconds=3)
    monkeypatch.setattr(renderer, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(renderer, "SHORTS_DIR", tmp_path / "shorts")
    clip = ShortClip(id=1, parts=[ClipPart(start_sec=0, end_sec=1)])
    output = renderer.render_short(video, clip, ShortsRenderOptions(aspect=aspect, reframe="crop", encoder="x264"))
    assert output.name.endswith(f"_{aspect.replace(':', 'x')}.mp4")
    stream = json.loads(subprocess.run([FFPROBE_BIN, "-v", "error", "-select_streams", "v:0", "-show_streams", "-of", "json",
                                        str(output)], capture_output=True, text=True, check=True).stdout)["streams"][0]
    assert (stream["width"], stream["height"]) == expected


@pytest.mark.integration
def test_render_worker_exports_each_aspect_into_library(store, tmp_path, monkeypatch):
    from app import config, shorts_api
    from app.models.schemas import ShortsRenderRequest
    from app.services import transcript_service
    from app.services import project_service, task_manager as tasks
    task_manager=tasks.TaskManager(tmp_path/'tasks.db')
    monkeypatch.setattr(tasks,'task_manager',task_manager)
    monkeypatch.setattr(project_service,'project_store',project_service.ProjectStore(tmp_path/'projects.db'))
    video = make_video(tmp_path / "sermon.mp4", seconds=3)
    monkeypatch.setattr(transcript_service, "find_video", lambda _: video)
    monkeypatch.setattr(shorts_api, "load_transcript",
                        lambda _: {"sentences": [{"start": 0, "end": 2, "text": "Ân điển của Chúa"}]})
    monkeypatch.setattr(config, "PACKAGES_DIR", tmp_path)
    monkeypatch.setattr(renderer, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(renderer, "SHORTS_DIR", tmp_path / "shorts")
    req = ShortsRenderRequest(video_id="sermon1", clips=[ShortClip(id=1, title="Ân điển", parts=[ClipPart(start_sec=0, end_sec=1)])],
                              options=ShortsRenderOptions(aspects=["9:16", "16:9"], encoder="x264"))
    task_id = task_manager.create_task(message="test")
    shorts_api.render_worker(task_id, req)
    result = task_manager.get_task(task_id).result
    assert [c["aspect"] for c in result["clips"]] == ["9:16", "16:9"]
    assert store.search("an dien cua chua")[1] == 2
    assert not list((tmp_path / "shorts").iterdir())
    with zipfile.ZipFile(tmp_path / result["zip_url"].rsplit("/", 1)[1]) as archive:
        names = sorted(archive.namelist())
        assert len(names) == 4
        assert any(n.endswith("_Ân điển_Hội Thánh v1.mp4") for n in names)
        srt_name = next(n for n in names if n.endswith(".srt"))
        assert "Ân điển" in archive.read(srt_name).decode("utf-8")
    assert result["clips"][0]["srt_url"].endswith("/subtitle")


def test_standard_filename_and_gdrive_local_sync(store, tmp_path, monkeypatch):
    from app.services import gdrive_service
    env_file = tmp_path / ".env"
    sync_dir = tmp_path / "gdrive_local"
    env_file.write_text(
        f"DEFAULT_SPEAKER_NAME=Mục sư A\n"
        f"FILENAME_ASCII_SLUG=false\n"
        f"GDRIVE_ENABLED=true\n"
        f"GDRIVE_AUTO_SYNC=true\n"
        f"GDRIVE_SUBFOLDER_BY_MONTH=false\n"
        f"GDRIVE_LOCAL_SYNC_DIR={sync_dir.as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gdrive_service, "ENV_FILE", env_file)

    srt_file = tmp_path / "sub.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nChúa ban phước\n", encoding="utf-8")
    item = add(
        store,
        tmp_path,
        "*GIÓ* TẦNG NÀO | GẶP *MÂY* TẦNG ĐÓ",
        aspect="9:16",
        speaker="Diễn giả: Hoàng Nam Tiến | Giăng 3:16",
        subtitle=srt_file,
    )
    assert item["speaker"] == "Hoàng Nam Tiến"
    assert item["version"] == 1
    assert item["export_filename"].endswith("_GIÓ TẦNG NÀO GẶP MÂY TẦNG ĐÓ_Hoàng Nam Tiến v1.mp4")

    # Second render of same topic increments version to v2 automatically
    item_v2 = add(
        store,
        tmp_path,
        "GIÓ TẦNG NÀO GẶP MÂY TẦNG ĐÓ",
        aspect="9:16",
        speaker="Hoàng Nam Tiến",
    )
    assert item_v2["version"] == 2
    assert item_v2["export_filename"].endswith("_GIÓ TẦNG NÀO GẶP MÂY TẦNG ĐÓ_Hoàng Nam Tiến v2.mp4")

    # Sync item v1 to Google Drive local sync folder via API (automatically frees workspace/library copy)
    client = TestClient(app)
    resp = client.post(f"/api/library/{item['id']}/gdrive-sync")
    assert resp.status_code == 200
    synced = resp.json()
    assert synced["gdrive_status"] == "synced"
    assert synced["local_deleted"] is True
    assert not store.file_path(item).exists()
    assert (sync_dir / item["export_filename"]).is_file()
    assert (sync_dir / Path(item["export_filename"]).with_suffix(".srt")).is_file()
    assert client.get(f"/api/library/{item['id']}/download").status_code == 200
    assert client.get(f"/api/library/{item['id']}/stream").status_code == 200
    zip_cloud = client.post("/api/library/zip", json={"ids": [item["id"]]})
    assert zip_cloud.status_code == 200
    pub_cloud = client.post(f"/api/library/{item['id']}/publication-package", json={"platform": "youtube_shorts"})
    assert pub_cloud.status_code == 200

    # Place a new file on Google Drive and pull it into the Library without copying to workspace/library
    make_video(sync_dir / "20261021_Đức tin chiến thắng_Mục sư Nguyễn Văn B v3.mp4")
    pull_resp = client.post("/api/library/gdrive-pull")
    assert pull_resp.status_code == 200
    pulled = pull_resp.json()
    assert pulled["added"] == 1
    pulled_item = pulled["items"][0]
    assert pulled_item["title"] == "Đức tin chiến thắng"
    assert pulled_item["speaker"] == "Mục sư Nguyễn Văn B"
    assert pulled_item["version"] == 3
    assert pulled_item["local_deleted"] is True
    assert not store.file_path(pulled_item).exists()

    # Extract folder ID from full URL and save via API
    cfg_resp = client.post(
        "/api/library/gdrive/config",
        json={
            "folder_id": "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz?usp=sharing",
            "default_speaker": "Mục sư B",
        },
    )
    assert cfg_resp.status_code == 200
    assert cfg_resp.json()["folder_id"] == "1AbCdEfGhIjKlMnOpQrStUvWxYz"
    assert cfg_resp.json()["default_speaker"] == "Mục sư B"

    # 1.8: Pulling again does not create duplicate items for already-known filenames/paths
    pull_again = client.post("/api/library/gdrive-pull")
    assert pull_again.status_code == 200
    assert pull_again.json()["added"] == 0

    # 1.6: free_local_storage_for_synced must NOT delete workspace/library video if gdrive_local_path is missing on disk
    item_v2_updated = store.update(
        item_v2["id"],
        gdrive_status="synced",
        gdrive_local_path=str(sync_dir / "missing_deleted_file.mp4"),
        gdrive_file_id="",
    )
    assert store.file_path(item_v2_updated).is_file()
    free_resp = client.post("/api/library/gdrive-free-space")
    assert free_resp.status_code == 200
    assert store.file_path(item_v2_updated).is_file()

    # 1.7: sync_library_item is idempotent when already synced and file exists in sync_dir
    sync_v2 = client.post(f"/api/library/{item_v2['id']}/gdrive-sync")
    assert sync_v2.status_code == 200
    synced_v2_path = Path(sync_v2.json()["gdrive_local_path"])
    assert synced_v2_path.is_file()
    mtime_before = synced_v2_path.stat().st_mtime_ns
    sync_v2_again = client.post(f"/api/library/{item_v2['id']}/gdrive-sync")
    assert sync_v2_again.status_code == 200
    assert synced_v2_path.stat().st_mtime_ns == mtime_before

    # 1.4 & 1.5: OAuth callback escapes XSS in ?error= and validates CSRF state parameter
    xss_resp = client.get("/api/library/gdrive/oauth-callback", params={"error": "<script>alert(1)</script>"})
    assert xss_resp.status_code == 400
    assert "<script>alert(1)</script>" not in xss_resp.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in xss_resp.text

    bad_state_resp = client.get("/api/library/gdrive/oauth-callback", params={"code": "fake_code", "state": "wrong_state"})
    assert bad_state_resp.status_code == 400
    assert "state mismatch" in bad_state_resp.text

    # 1.9: Reject internal app directories or system folders for local_sync_dir
    bad_dir_resp = client.post(
        "/api/library/gdrive/config",
        json={"local_sync_dir": str(gdrive_service.BASE_DIR / "app")},
    )
    assert bad_dir_resp.status_code == 400


